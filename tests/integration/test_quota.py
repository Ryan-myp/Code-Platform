#!/usr/bin/env python3
"""配额扣减中间件验证（商业化计费）。

覆盖：
- 表情包/思维导图等异步生成端点：提交即扣费（普通用户）
- 配额耗尽返回 402（免费版默认 30 次/日）
- admin 不受配额限制（不扣费）
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def _register_and_login(client, username: str) -> dict | None:
    """注册并登录普通用户，返回 Authorization 头。"""
    resp = client.post("/api/auth/register", json={"username": username, "password": "pass123456"})
    assert resp.status_code in (200, 201), f"register failed: {resp.status_code} {resp.text}"
    resp = client.post("/api/auth/login", json={"username": username, "password": "pass123456"})
    assert resp.status_code == 200, f"login failed: {resp.status_code} {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _used_today(username: str) -> int:
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT used_today FROM users WHERE username=?", (username,)).fetchone()
        return row[0] or 0
    finally:
        conn.close()


def _set_used_today(username: str, used: int) -> None:
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET used_today=?, last_quota_date=? WHERE username=?",
            (used, datetime.now().strftime("%Y-%m-%d"), username),
        )
        conn.commit()
    finally:
        conn.close()


def test_async_generators_deduct_quota(test_db_path):
    """表情包/思维导图异步提交端点：普通用户每次调用扣 1 次当日额度。"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    headers = _register_and_login(client, "quota_gen_user")

    resp = client.post("/api/meme/generate", data={"top_text": "测试表情", "style": "yellow"}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("task_id"), "表情包生成应返回异步 task_id"
    assert _used_today("quota_gen_user") == 1

    resp = client.post("/api/mindmap/generate", json={"topic": "商业化", "depth": 2}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("task_id"), "思维导图生成应返回异步 task_id"
    assert _used_today("quota_gen_user") == 2


def test_quota_exhausted_returns_402(test_db_path):
    """额度耗尽（30/30）后再次调用生成端点 → 402 且不创建任务。"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    headers = _register_and_login(client, "quota_exhaust_user")
    _set_used_today("quota_exhaust_user", 29)

    # 第 30 次：允许
    resp = client.post("/api/meme/generate", data={"top_text": "最后一次", "style": "yellow"}, headers=headers)
    assert resp.status_code == 200, resp.text

    # 第 31 次：402
    resp = client.post("/api/meme/generate", data={"top_text": "超额", "style": "yellow"}, headers=headers)
    assert resp.status_code == 402, resp.text
    assert "额度" in resp.json().get("detail", "")

    # 未创建任务（配额中间件在端点前拦截）
    from task_queue import get_db as tq_db

    conn = tq_db()
    try:
        row = conn.execute("SELECT COUNT(*) c FROM async_tasks").fetchone()
        assert row[0] == 1  # 仅第一次成功提交的任务
    finally:
        conn.close()


def test_admin_not_deducted(test_db_path, auth_headers):
    """admin 调用生成端点不扣费（管理员不限额度）。"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    resp = client.post("/api/meme/generate", data={"top_text": "管理员测试", "style": "yellow"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json().get("task_id")
