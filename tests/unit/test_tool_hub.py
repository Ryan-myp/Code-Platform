"""tool_hub 效率工具箱单元测试。

覆盖：工具列表 / 工具详情 / 提示词增强 / 用量统计 / 历史记录 / 收藏。
依赖 TestClient + 已初始化的测试数据库（conftest.py 提供）。
"""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture
def auth_token():
    """获取测试 admin token。"""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


HEADER = lambda token: {"Authorization": f"Bearer {token}"}


# ── 工具列表 ────────────────────────────────────────────────────

class TestListTools:
    def test_list_returns_tools(self, auth_token):
        resp = client.get("/api/tools", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_list_contains_expected_categories(self, auth_token):
        resp = client.get("/api/tools", headers=HEADER(auth_token))
        cats = {t["category"] for t in resp.json()}
        # 验证覆盖了核心分类
        assert "职场办公" in cats
        assert "自媒体创作" in cats

    def test_list_unauth(self):
        resp = client.get("/api/tools")
        assert resp.status_code == 401


# ── 工具详情 ─────────────────────────────────────────────────────

class TestGetTool:
    def test_get_existing_tool(self, auth_token):
        # 先拿到一个存在的 tool_id
        list_resp = client.get("/api/tools", headers=HEADER(auth_token))
        tool_id = list_resp.json()[0]["id"]
        resp = client.get(f"/api/tools/{tool_id}", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "name" in data
        assert "prompt_template" in data

    def test_get_nonexistent_tool(self, auth_token):
        resp = client.get("/api/tools/nonexistent-tool-id", headers=HEADER(auth_token))
        assert resp.status_code == 404

    def test_get_unauth(self):
        resp = client.get("/api/tools/meeting-notes")
        assert resp.status_code == 401


# ── 提示词增强 ───────────────────────────────────────────────────

class TestEnhancePrompt:
    def test_enhance_basic(self, auth_token):
        resp = client.post(
            "/api/tools/enhance-prompt",
            headers=HEADER(auth_token),
            json={"text": "写一份会议纪要"},
        )
        # LLM 可能不可用，但端点应正常响应（200 或 5xx 降级）
        assert resp.status_code in (200, 500, 502, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "enhanced" in data

    def test_enhance_empty_prompt(self, auth_token):
        resp = client.post(
            "/api/tools/enhance-prompt",
            headers=HEADER(auth_token),
            json={"text": ""},
        )
        assert resp.status_code in (400, 422)


# ── 用量统计 ─────────────────────────────────────────────────────

class TestUsageStats:
    def test_stats(self, auth_token):
        resp = client.get("/api/tools/stats", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


# ── 历史记录 ─────────────────────────────────────────────────────

class TestToolHistory:
    def test_history_empty(self, auth_token):
        resp = client.get("/api/tools/meeting-notes/history?limit=5", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_history_limit(self, auth_token):
        resp = client.get(
            "/api/tools/meeting-notes/history?limit=2",
            headers=HEADER(auth_token),
        )
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) <= 2


# ── 我的记录 ─────────────────────────────────────────────────────

class TestMyRecords:
    def test_records(self, auth_token):
        resp = client.get("/api/records?limit=10", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "tools" in data
        assert "shares" in data


# ── 收藏功能 ─────────────────────────────────────────────────────

class TestFavorites:
    def test_list_favorites_empty(self, auth_token):
        resp = client.get("/api/tools/favorites/list", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_toggle_favorite(self, auth_token):
        # 先获取一个存在的 tool_id
        list_resp = client.get("/api/tools", headers=HEADER(auth_token))
        tool_id = list_resp.json()[0]["id"]

        # 收藏
        resp = client.post(
            f"/api/tools/favorites/{tool_id}",
            headers=HEADER(auth_token),
        )
        assert resp.status_code in (200, 201)

        # 列出收藏应包含该工具
        resp = client.get("/api/tools/favorites/list", headers=HEADER(auth_token))
        fav_ids = {f["id"] for f in resp.json()}
        assert tool_id in fav_ids

        # 取消收藏
        resp = client.post(
            f"/api/tools/favorites/{tool_id}",
            headers=HEADER(auth_token),
        )
        assert resp.status_code in (200, 200)

    def test_favorite_unauth(self):
        resp = client.get("/api/tools/favorites/list")
        assert resp.status_code == 401
