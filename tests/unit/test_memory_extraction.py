"""P1-3 记忆自动提取闭环：对话后关键词触发 → LLM 提取 → 写入 memories → 下轮注入。

锁定行为：
- 非触发关键词不调 LLM（成本控制，每轮至多 1 次小调用）
- 触发且提取成功 → memories 表新增 auto 型记忆
- LLM 故障 → 静默不阻断对话主流程
"""

import asyncio


def test_trigger_miss_no_llm_call(setup_test_db, monkeypatch):
    """普通对话不触发提取（零 LLM 成本）。"""
    import chat_engine
    from sessions import add_memory, create_session

    sid = create_session("agent-x", "t")
    add_memory(sid, "agent-x", "基线记忆", "long")
    called = []
    monkeypatch.setattr("sessions.auto_extract_memory", lambda *a, **k: called.append(1))

    asyncio.new_event_loop().run_until_complete(
        chat_engine._maybe_extract_memory(sid, "agent-x", "帮我写一段介绍文案", "好的")
    )
    assert not called, "非触发关键词不应调提取"


def test_trigger_hit_writes_memory(setup_test_db, monkeypatch):
    """'记住' 触发 → auto_extract_memory 被调用（真实 LLM 在测试环境不可用时静默 0 写入，仅验证链路）。"""
    import chat_engine
    from sessions import create_session

    sid = create_session("agent-x", "t")
    calls = []

    async def fake_extract(session_id, agent_id, user, reply):
        calls.append((session_id, agent_id))
        return 0

    monkeypatch.setattr("sessions.auto_extract_memory", fake_extract)
    asyncio.new_event_loop().run_until_complete(
        chat_engine._maybe_extract_memory(sid, "agent-x", "记住：我偏好中文回答", "好的")
    )
    assert calls == [(sid, "agent-x")], "应把 session/agent 传给提取器"

    # 无会话空间（session_id=None）时绝不提取
    calls.clear()
    asyncio.new_event_loop().run_until_complete(chat_engine._maybe_extract_memory(None, "agent-x", "记住：x", "y"))
    assert not calls


def test_trigger_failure_silent(setup_test_db, monkeypatch):
    """提取器故障（如 LLM 不可用）→ 不抛异常，不阻断对话主流程。"""
    import chat_engine

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr("sessions.auto_extract_memory", boom)

    async def run():
        await chat_engine._maybe_extract_memory("sid", "agent-x", "记住：x", "y")

    asyncio.new_event_loop().run_until_complete(run())  # 不抛 = 通过


def test_schedule_extraction_fires_background_task(setup_test_db, monkeypatch):
    """流式路径 fire-and-forget：任务真实执行且不阻塞调用方。"""
    import chat_engine

    done = []

    async def fake_extract(session_id, agent_id, user, reply):
        done.append(session_id)
        return 1

    monkeypatch.setattr("sessions.auto_extract_memory", fake_extract)

    async def run():
        # 模拟 generator 内部（运行中的循环）调用 fire-and-forget
        chat_engine._schedule_memory_extraction("s1", "agent-x", "记住我的偏好是深色", "好的")
        await asyncio.sleep(0.05)

    asyncio.new_event_loop().run_until_complete(run())
    assert "s1" in done, "后台提取任务应真实执行"


# ════════════════════════════════════════════════════════════════
# P1 记忆治理：去重 + 上限裁剪（防无界增长）
# ════════════════════════════════════════════════════════════════
def test_add_memory_dedup_same_content(setup_test_db):
    """同 session 同内容不重复写（返回已有 id）。"""
    from sessions import add_memory, create_session

    sid = create_session("agent-gov", "治理测试")
    id1 = add_memory(sid, "agent-gov", "用户偏好：使用中文", "long")
    id2 = add_memory(sid, "agent-gov", "用户偏好：使用中文", "long")
    assert id1 == id2

    from common.db import get_db

    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE session_id=?", (sid,)).fetchone()["c"]
    conn.close()
    assert n == 1


def test_memory_prune_caps_session_total(setup_test_db):
    """session 总量超 100 → 裁到 100（先裁非 long）。"""
    from sessions import add_memory, create_session, get_memories

    sid = create_session("agent-gov2", "裁剪测试")
    for i in range(110):
        add_memory(sid, "agent-gov2", f"短期记忆 {i}", "short")
    assert len(get_memories(sid)) == 100


def test_memory_prune_caps_auto_type(setup_test_db):
    """auto 记忆最多保留最近 30 条。"""
    from common.db import get_db
    from sessions import create_session

    sid = create_session("agent-gov3", "auto 裁剪")
    conn = get_db()
    for i in range(40):
        conn.execute(
            "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?,?,?,?,?)",
            (f"auto_{i}", sid, "agent-gov3", "auto", f"auto 记忆 {i}"),
        )
    conn.commit()
    from sessions import _prune_session_memories

    _prune_session_memories(conn, sid)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE session_id=? AND memory_type='auto'", (sid,)).fetchone()["c"]
    conn.close()
    assert n == 30
