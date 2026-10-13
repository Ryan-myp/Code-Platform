"""额度闸覆盖（v18 G）：LLM 执行路径全部计费，非 AI 路径不计费。

背景：quota_middleware 按路径名单 + 后缀扣减每日额度。历史上流式执行路径
（agent run/stream、assistant chat）不在名单内 → free 用户可绕流式接口白嫖 LLM。
本文件锁定：
- /api/agents/{id}/run/stream、/api/assistant/chat(+/stream) 均计费（超额 402）
- 非 AI 端点（技能创建等）不计费（超额也放行、used_today 不动）
"""

from datetime import datetime

from fastapi.testclient import TestClient

from common.auth import create_access_token, hash_password
from common.db import get_db


def _exhausted_user(username: str) -> str:
    """插入一个当日额度已耗尽的 free 用户（free 日限 30，used_today=30 → 耗尽），返回 JWT token。"""
    conn = get_db()
    conn.execute(
        """INSERT INTO users (id, username, password_hash, role, membership, used_today,
                              last_quota_date, total_usage, bonus_quota)
           VALUES (?, ?, ?, 'user', 'free', ?, ?, ?, 0)""",
        (
            f"u_{username}",
            username,
            hash_password("pass12345"),
            30,  # used == MEMBERSHIP_QUOTA[free] → 耗尽
            datetime.now().strftime("%Y-%m-%d"),
            30,
        ),
    )
    conn.commit()
    conn.close()
    return create_access_token(username, {"user_id": f"u_{username}", "role": "user"})


def _used_today(username: str) -> int:
    conn = get_db()
    row = conn.execute("SELECT used_today FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return row["used_today"]


def test_streaming_agent_run_charged(setup_test_db):
    """agent 流式执行路径在额度闸内：耗尽用户 → 402（中间件在端点前拦截）。"""
    from main import app

    token = _exhausted_user("q-g-stream")
    client = TestClient(app)
    res = client.post(
        "/api/agents/no-such-agent/run/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "hi"},
    )
    assert res.status_code == 402, f"耗尽用户流式执行应 402（实际 {res.status_code}）"


def test_assistant_chat_charged(setup_test_db):
    """assistant 同步/流式 chat 均在额度闸内。"""
    from main import app

    token = _exhausted_user("q-g-assist")
    client = TestClient(app)
    r1 = client.post(
        "/api/assistant/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "hi"},
    )
    assert r1.status_code == 402, f"assistant/chat 应计费（实际 {r1.status_code}）"
    r2 = client.post(
        "/api/assistant/chat/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "hi"},
    )
    assert r2.status_code == 402, f"assistant/chat/stream 应计费（实际 {r2.status_code}）"


def test_non_ai_endpoint_not_charged(setup_test_db):
    """非 AI 端点不计费：耗尽用户创建技能不 402，且 used_today 不动（无扣无退）。"""
    from main import app

    token = _exhausted_user("q-g-nonai")
    client = TestClient(app)
    res = client.post(
        "/api/skills",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "q-g-skill", "content": "test"},
    )
    assert res.status_code != 402, f"非 AI 端点不应被额度闸拦截（实际 {res.status_code}）"
    assert _used_today("q-g-nonai") == 30, "非 AI 端点既不应扣费也不应退费"
