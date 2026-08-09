"""SEO 基础设施（获客：robots / sitemap 动态生成）单元测试。

覆盖：
- /robots.txt：200、text/plain、公开页可抓、运营页禁抓、Sitemap 绝对地址
- /sitemap.xml：200、application/xml、核心工具页收录、公开分享内容收录
- XML 转义：分享标题含 & / < 等特殊字符不破坏 sitemap
- X-Forwarded-Proto：反代 https 时生成 https 绝对 URL
"""

import uuid
from datetime import datetime

from fastapi.testclient import TestClient


def _insert_user(username: str) -> str:
    """直接插入测试用户（绕过注册接口），返回 user_id。"""
    from common.auth import hash_password
    from common.db import get_db

    uid = f"u_{uuid.uuid4().hex[:8]}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, membership, used_today,
                                  last_quota_date, total_usage, bonus_quota)
               VALUES (?,?,?,?,?,?,?,?,0)""",
            (
                uid,
                username,
                hash_password("pass123456"),
                "user",
                "free",
                0,
                datetime.now().strftime("%Y-%m-%d"),
                0,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return uid


def _insert_share(user_id: str, title: str = "SEO 测试分享") -> dict:
    """创建分享并返回完整记录。"""
    from common.auth import create_share, get_share

    created = create_share(user_id, "text", title, "SEO 测试内容：小团智能平台能力展示")
    full = get_share(created["share_code"])
    assert full is not None
    return full


# ══════════════════════════════════════════════════════════════
# robots.txt
# ══════════════════════════════════════════════════════════════


class TestRobotsTxt:
    def test_robots_txt_basic(self, test_db_path):
        """robots.txt：200 + text/plain + 核心指令齐全。"""
        from main import app

        client = TestClient(app)
        resp = client.get("/robots.txt", headers={"Host": "example.com"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/plain")
        body = resp.text
        assert "User-agent: *" in body
        assert "Allow: /" in body
        assert "Disallow: /api/" in body
        assert "Disallow: /admin" in body
        assert "Sitemap: http://example.com/sitemap.xml" in body

    def test_robots_sitemap_uses_forwarded_proto(self, test_db_path):
        """反代 https 场景：Sitemap 地址跟随 X-Forwarded-Proto。"""
        from main import app

        client = TestClient(app)
        resp = client.get(
            "/robots.txt",
            headers={"Host": "example.com", "X-Forwarded-Proto": "https"},
        )
        assert "Sitemap: https://example.com/sitemap.xml" in resp.text


# ══════════════════════════════════════════════════════════════
# sitemap.xml
# ══════════════════════════════════════════════════════════════


class TestSitemapXml:
    def test_sitemap_core_pages(self, test_db_path):
        """sitemap：200 + application/xml + 核心工具页收录。"""
        from main import app

        client = TestClient(app)
        resp = client.get("/sitemap.xml", headers={"Host": "example.com"})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/xml")
        body = resp.text
        assert body.startswith("<?xml")
        for path in ("/", "/tool-hub", "/ppt-factory", "/digital-human", "/data-analyzer"):
            assert f"<loc>http://example.com{path}</loc>" in body
        assert "priority>0.9" in body

    def test_sitemap_includes_shares(self, test_db_path):
        """公开分享内容收录进 sitemap（浏览量/时效）。"""
        from main import app

        client = TestClient(app)
        uid = _insert_user("seo_share_owner")
        share = _insert_share(uid)
        resp = client.get("/sitemap.xml", headers={"Host": "example.com"})
        assert resp.status_code == 200
        assert f"<loc>http://example.com/share/{share['share_code']}</loc>" in resp.text
        assert "priority>0.6</priority>" in resp.text

    def test_sitemap_xml_escaping(self, test_db_path):
        """分享标题/内容含 & < > 等字符时 XML 仍合法（转义不破坏）。"""
        from main import app

        client = TestClient(app)
        uid = _insert_user("seo_escape_owner")
        share = _insert_share(uid, "收益 & 增长 <快报>")
        resp = client.get("/sitemap.xml", headers={"Host": "example.com"})
        assert resp.status_code == 200
        # XML 合法且未被特殊字符破坏
        assert resp.text.count("<url>") == resp.text.count("</url>")
        assert "&amp;" in resp.text or share["share_code"] in resp.text
        # 可被标准 XML 解析（解析自产可信内容；ElementTree 默认忽略 DTD、不加载外部实体）
        import xml.etree.ElementTree as ET

        ET.fromstring(resp.text)  # 解析失败会抛异常

    def test_sitemap_forwarded_https(self, test_db_path):
        """反代 https 场景：loc 为 https 绝对地址。"""
        from main import app

        client = TestClient(app)
        resp = client.get(
            "/sitemap.xml",
            headers={"Host": "example.com", "X-Forwarded-Proto": "https"},
        )
        assert "<loc>https://example.com/</loc>" in resp.text
