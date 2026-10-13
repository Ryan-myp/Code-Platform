"""P1-3 记忆自动提取闭环：对话后关键词触发 → LLM 提取 → 写入 memories → 下轮注入。

锁定行为：
- 非触发关键词不调 LLM（成本控制，每轮至多 1 次小调用）
- 触发且提取成功 → memories 表新增 auto 型记忆
- LLM 故障 → 静默不阻断对话主流程
"""

import asyncio

import pytest


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


def test_prune_creates_lossy_summary(setup_test_db):
    """单次裁剪 ≥5 条 → 合并为一条 long 摘要记忆（不静默丢信息，纯规则零 LLM）。"""
    import sessions

    sid = sessions.create_session("a1", "t")
    conn = sessions.get_db()
    for i in range(40):
        conn.execute(
            "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, 'auto', ?)",
            (f"m{i}", sid, "a1", f"旧记忆 {i}"),
        )
    conn.commit()
    conn.close()

    sessions.add_memory(sid, "a1", "新记忆", "short")

    conn = sessions.get_db()
    auto_n = conn.execute(
        "SELECT COUNT(*) AS c FROM memories WHERE session_id=? AND memory_type='auto'", (sid,)
    ).fetchone()["c"]
    summaries = conn.execute(
        "SELECT content FROM memories WHERE session_id=? AND memory_type='long'", (sid,)
    ).fetchall()
    conn.close()
    assert auto_n == 30, "auto 裁到上限 30"
    assert len(summaries) == 1
    text = summaries[0]["content"]
    assert sessions.SUMMARY_PREFIX in text
    assert "旧记忆" in text, "被裁要点保留在摘要里"


def test_prune_summary_upsert_not_duplicate(setup_test_db):
    """摘要记忆重复裁剪时原地更新，不重复插入。"""
    import sessions

    sid = sessions.create_session("a1", "t")
    conn = sessions.get_db()
    for i in range(35):
        conn.execute(
            "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, 'auto', ?)",
            (f"a{i}", sid, "a1", f"条目 {i}"),
        )
    conn.commit()
    conn.close()

    sessions.add_memory(sid, "a1", "触发裁剪A", "short")
    sessions.add_memory(sid, "a1", "触发裁剪B", "short")

    conn = sessions.get_db()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM memories WHERE session_id=? AND content LIKE ?",
        (sid, sessions.SUMMARY_PREFIX + "%"),
    ).fetchone()["c"]
    conn.close()
    assert n == 1, "摘要只应有一条（upsert 不重插）"


def test_auto_extract_semantic_dedup(setup_test_db, monkeypatch):
    """LLM 提取出措辞不同但语义相近的两条 → 只入一条（语义去重只在提取路径生效）。"""
    import common.llm
    import sessions

    sid = sessions.create_session("a-ss", "t")
    sessions.add_memory(sid, "a-ss", "用户喜欢简洁风格的输出", "short")

    async def fake_llm(system, user, **kw):
        return '{"memories": ["用户偏好简洁的输出风格", "部署前必须跑全量回归"]}'

    monkeypatch.setattr(common.llm, "call_llm_async", fake_llm)
    import asyncio

    written = asyncio.run(sessions.auto_extract_memory(sid, "a-ss", "帮我记一下", "好的"))
    assert written == 1, "近义条目被去重，只写入不重复的那条"

    conn = sessions.get_db()
    rows = conn.execute("SELECT content FROM memories WHERE session_id=?", (sid,)).fetchall()
    conn.close()
    contents = [r["content"] for r in rows]
    assert any("简洁" in c for c in contents), "已有条目保留"
    assert sum(1 for c in contents if "简洁" in c or "简练" in c) == 1, "不重复存近义条目"
    assert any("回归" in c for c in contents), "不相关的正常写入"


def test_add_memory_different_content_kept(setup_test_db):
    """语义无关的条目正常入库（add_memory 不做语义去重，模板化内容不误杀）。"""
    import sessions

    sid = sessions.create_session("a-ss2", "t")
    a = sessions.add_memory(sid, "a-ss2", "用户喜欢简洁风格的输出", "short")
    b = sessions.add_memory(sid, "a-ss2", "数据库连接池大小设为 20", "short")
    assert a != b

    conn = sessions.get_db()
    n = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE session_id=?", (sid,)).fetchone()["c"]
    conn.close()
    assert n == 2


@pytest.mark.asyncio
async def test_compress_memory_summary_llm(setup_test_db, monkeypatch):
    """LLM 语义压缩：规则摘要被替换为 ≤3 条真要点；LLM 失败保持规则摘要（诚实降级）。"""
    import sessions

    sid = sessions.create_session("a-comp", "t")
    # 造一条规则摘要记忆
    conn = sessions.get_db()
    conn.execute(
        "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, 'long', ?)",
        ("mem_sum_1", sid, "a-comp", sessions.SUMMARY_PREFIX + "（10 条）\n- 旧记忆 0\n- 旧记忆 1"),
    )
    conn.commit()
    conn.close()

    # LLM 成功 → 原地升级为语义要点
    async def fake_llm(system, user, **kw):
        return "- 用户偏好简洁\n- 索引重建在周三\n- 订单服务回滚预案"

    import common.llm

    monkeypatch.setattr(common.llm, "call_llm_async", fake_llm)
    ok = await sessions.compress_memory_summary(sid, "a-comp")
    assert ok is True
    conn = sessions.get_db()
    row = conn.execute("SELECT content FROM memories WHERE id='mem_sum_1'").fetchone()
    conn.close()
    assert "用户偏好简洁" in row["content"]
    assert "LLM 语义压缩" in row["content"]

    # LLM 失败 → 保持（内容不回滚为旧值，但也不崩）
    async def fail_llm(system, user, **kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr(common.llm, "call_llm_async", fail_llm)
    ok2 = await sessions.compress_memory_summary(sid, "a-comp")
    assert ok2 is False
