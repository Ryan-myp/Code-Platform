#!/usr/bin/env python3
"""轻量 SPA 静态服务器 - 支持前端路由 fallback，内存占用极低"""
import http.server
import socketserver
import os
import sys

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5173


class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        # 静态资源直接服务
        if self.path.startswith("/assets/") or self.path.startswith("/favicon"):
            return super().do_GET()
        # 其他所有路径返回 index.html（SPA fallback）
        if not self.path.startswith("/api/"):
            self.path = "/index.html"
        return super().do_GET()


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    os.chdir(DIST_DIR)
    with ThreadedHTTPServer(("127.0.0.1", PORT), SPAHandler) as httpd:
        print(f"SPA server on http://localhost:{PORT} (dist: {DIST_DIR})")
        httpd.serve_forever()
