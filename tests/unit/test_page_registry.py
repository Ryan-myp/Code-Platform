"""页面权限注册一致性测试（防回归）。

背景：页面可见性控制要求「Sidebar 入口 / 路由守卫 / 后端 PAGES 注册表」三方对齐。
历史事故：新增页面只在 Sidebar + AccessGuard 注册、遗漏后端 permissions.PAGES，
导致 /api/access/pages 查不到 → Sidebar 入口被过滤、直达 URL 被重定向（admin 也不例外）。

覆盖：
- admin 登录 /api/access/pages 全部可见且无锁定
- free 用户默认（无可见性配置）全部可见且无锁定
- 三方注册表对齐：Sidebar pageId ⊆ PAGES；AccessGuard path ⊆ PAGES；useAccess 映射 ⊆ PAGES
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


def _client() -> TestClient:
    from main import app

    return TestClient(app)


def _login(username: str, password: str) -> dict:
    resp = _client().post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _backend_page_ids() -> set[str]:
    from permissions import PAGES

    return {p["id"] for p in PAGES}


class TestAccessPagesApi:
    def test_admin_all_pages_visible_and_unlocked(self, auth_headers):
        """admin 登录：全部注册页面可见且无锁定。"""
        resp = _client().get("/api/access/pages", headers=auth_headers)
        assert resp.status_code == 200
        pages = resp.json()
        assert len(pages) == len(_backend_page_ids())
        assert all(not p.get("locked") for p in pages)

    def test_admin_can_see_admin_only_pages(self, test_db_path):
        """admin 可见范围档位不影响 admin 本人（admin 级页面可见）。"""
        from permissions import set_visibility

        set_visibility("page", "data-analyzer", "admin")
        headers = _login("admin", "admin123")
        pages = _client().get("/api/access/pages", headers=headers).json()
        assert any(p["id"] == "data-analyzer" for p in pages)

    def test_free_user_default_all_visible(self, test_db_path):
        """无可见性配置时，普通用户全部可见且无锁定。"""
        from common.auth import register_user

        register_user("reg_check_user", "pass123456")
        headers = _login("reg_check_user", "pass123456")
        resp = _client().get("/api/access/pages", headers=headers)
        pages = resp.json()
        assert len(pages) == len(_backend_page_ids())
        assert all(not p.get("locked") for p in pages)

    def test_free_user_locked_on_pro_page(self, test_db_path):
        """页面设为 pro 后，普通用户可见但锁定（requires=pro）。"""
        from common.auth import register_user
        from permissions import set_visibility

        set_visibility("page", "data-analyzer", "pro")
        register_user("reg_lock_user", "pass123456")
        headers = _login("reg_lock_user", "pass123456")
        pages = _client().get("/api/access/pages", headers=headers).json()
        page = next(p for p in pages if p["id"] == "data-analyzer")
        assert page["locked"] is True
        assert page["requires"] == "pro"
        # 恢复默认，避免影响其他测试
        set_visibility("page", "data-analyzer", "all")


class TestPageRegistryAlignment:
    """三方注册表对齐（Sidebar / AccessGuard / useAccess vs 后端 PAGES）。"""

    def test_sidebar_page_ids_registered_backend(self):
        """Sidebar 所有 pageId 必须已注册到后端 PAGES。"""
        sidebar = (FRONTEND_DIR / "src/components/Sidebar.jsx").read_text(encoding="utf-8")
        sidebar_ids = set(re.findall(r"pageId: '([\w-]+)'", sidebar))
        missing = sidebar_ids - _backend_page_ids()
        assert not missing, f"Sidebar 有入口但后端 PAGES 未注册: {missing}"

    def test_access_guard_paths_registered_backend(self):
        """路由守卫所有 path 必须已注册到后端 PAGES。"""
        app_src = (FRONTEND_DIR / "src/App.jsx").read_text(encoding="utf-8")
        guard_paths = set(re.findall(r'<AccessGuard\s+path="([^"]+)"', app_src))
        missing = {p.lstrip("/") for p in guard_paths} - _backend_page_ids()
        assert not missing, f"AccessGuard 有守卫但后端 PAGES 未注册: {missing}"

    def test_useaccess_mapping_registered_backend(self):
        """useAccess 路径映射的所有页面 id 必须已注册到后端 PAGES。"""
        hook = (FRONTEND_DIR / "src/hooks/useAccess.js").read_text(encoding="utf-8")
        mapped_ids = set(re.findall(r": '([\w-]+)'", hook))
        missing = mapped_ids - _backend_page_ids()
        assert not missing, f"useAccess 有映射但后端 PAGES 未注册: {missing}"
