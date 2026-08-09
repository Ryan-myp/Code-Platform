#!/usr/bin/env python3
"""轻量 SPA 静态服务器 - 支持前端路由 fallback，内存占用极低"""
import http.server
import os
import socketserver
import sys

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def end_headers(self):
        # 带 hash 的构建资源内容寻址：永久缓存；HTML 每次验证（no-cache 配合 ETag 304），
        # 避免浏览器缓存旧 index.html 导致"部署后仍看到旧页面"
        if self.path.startswith("/assets/"):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        # SEO 基础设施：robots/sitemap 由后端按 Host 动态生成（避免 SPA fallback 吞掉）
        if self.path in ("/robots.txt", "/sitemap.xml"):
            return self._proxy_backend()
        # 静态资源直接服务（含 PWA：sw.js / manifest / 图标）
        if self.path.startswith(("/assets/", "/favicon", "/icons/", "/sw.js", "/manifest.webmanifest")):
            return super().do_GET()
        # 其他所有路径返回 index.html（SPA fallback）
        if not self.path.startswith("/api/"):
            self.path = "/index.html"
        return super().do_GET()

    def _proxy_backend(self):
        """转发 robots/sitemap 到后端 8888（动态生成，含 Host 绝对 URL）。"""
        import http.client

        try:
            conn = http.client.HTTPConnection("127.0.0.1", 8888, timeout=5)
            conn.request("GET", self.path, headers={"Host": self.headers.get("Host", "localhost:8888")})
            resp = conn.getresponse()
            body = resp.read()
            self.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() in ("content-type", "content-length", "cache-control", "etag"):
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)
            conn.close()
        except Exception:
            self.send_error(502, "backend unavailable")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.chdir(DIST_DIR)
    with ThreadedHTTPServer(("127.0.0.1", PORT), SPAHandler) as httpd:
        print(f"SPA server on http://localhost:{PORT} (dist: {DIST_DIR})")
        httpd.serve_forever()
