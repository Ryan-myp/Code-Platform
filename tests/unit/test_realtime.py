"""WebSocket 实时频道（realtime）单元测试。

覆盖：任务频道归属校验（4403/4404/管理特权）、无 token 拒绝（4401）、
正常订阅 + 心跳、非任务频道不受归属校验限制。
"""

import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from common.db import get_db
from realtime import _check_task_channel_access


def _login_token(client) -> str:
    """admin 登录拿 JWT（conftest init_db 已预置 admin/admin123）。"""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"login failed: {resp.text}"
    return resp.json()["access_token"]


def _insert_task(task_id: str, created_by: str) -> None:
    from task_queue import _ensure_table

    conn = get_db()
    try:
        _ensure_table(conn)
        conn.execute(
            "INSERT INTO async_tasks (id, type, status, payload, created_by, created_at) VALUES (?,?,?,?,?,?)",
            (task_id, "tq_ws", "pending", "{}", created_by, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


class TestTaskChannelAccess:
    """归属校验纯函数测试（不经 WebSocket 层，覆盖全分支）。"""

    def test_owner_allowed(self, setup_test_db):
        _insert_task("task_ws_1", "alice")
        deny = asyncio.run(_check_task_channel_access("task:task_ws_1", {"sub": "alice", "role": "user"}))
        assert deny is None

    def test_other_user_forbidden(self, setup_test_db):
        _insert_task("task_ws_1", "alice")
        deny = asyncio.run(_check_task_channel_access("task:task_ws_1", {"sub": "bob", "role": "user"}))
        assert deny is not None
        assert deny[0] == 4403

    def test_admin_allowed_any_task(self, setup_test_db):
        _insert_task("task_ws_1", "alice")
        deny = asyncio.run(_check_task_channel_access("task:task_ws_1", {"sub": "root", "role": "admin"}))
        assert deny is None

    def test_nonexistent_task_not_found(self, setup_test_db):
        deny = asyncio.run(_check_task_channel_access("task:no_such_id", {"sub": "alice", "role": "user"}))
        assert deny is not None
        assert deny[0] == 4404

    def test_user_channel_self_only(self, setup_test_db):
        deny = asyncio.run(_check_task_channel_access("task:user:alice", {"sub": "alice", "role": "user"}))
        assert deny is None
        deny2 = asyncio.run(_check_task_channel_access("task:user:alice", {"sub": "bob", "role": "user"}))
        assert deny2 is not None
        assert deny2[0] == 4403

    def test_non_task_channel_unrestricted(self, setup_test_db):
        deny = asyncio.run(_check_task_channel_access("chat:agent_1", {"sub": "bob", "role": "user"}))
        assert deny is None


class TestWebSocketEndpoint:
    """端到端：无 token 拒绝 + 正常订阅心跳。"""

    def test_no_token_rejected(self, setup_test_db):
        from main import app

        client = TestClient(app)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/chat:agent_1"):
                pass
        assert exc.value.code == 4401

    def test_owner_subscribes_and_ping_pong(self, setup_test_db):
        from main import app

        client = TestClient(app)
        _insert_task("task_ws_2", "admin")
        token = _login_token(client)
        with client.websocket_connect(f"/ws/task:task_ws_2?token={token}") as ws:
            ws.send_text("ping")
            assert ws.receive_text() == "pong"

    def test_other_user_subscribe_rejected(self, setup_test_db):
        """端到端越权验证：非任务创建者的普通用户订阅被 4403 拒绝。"""
        from main import app

        client = TestClient(app)
        _insert_task("task_ws_3", "alice")
        # 注册普通用户 bob
        resp = client.post("/api/auth/register", json={"username": "bob", "password": "bob123"})
        assert resp.status_code in (200, 201), f"register failed: {resp.text}"
        resp = client.post("/api/auth/login", json={"username": "bob", "password": "bob123"})
        assert resp.status_code == 200
        bob_token = resp.json()["access_token"]
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(f"/ws/task:task_ws_3?token={bob_token}"):
                pass
        assert exc.value.code == 4403
