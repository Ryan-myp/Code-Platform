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
