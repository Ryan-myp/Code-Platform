"""Agent 运行时（v17.0）单测：绑定资源接入执行链路。

覆盖：RAG 上下文组装 / 技能注入 / 工具白名单 / 工具指令解析与清洗 / 沙箱工具真实执行 /
绑定资源损坏时的降级不阻断。
"""

import pytest
from fastapi import HTTPException


@pytest.fixture
def runtime():
    import agent_runtime

    return agent_runtime


def test_parse_tool_directives(runtime):
    text = "先用计算器算一下。\n[TOOL:code_interpreter|print(1+1)]\n[TOOL:regex-builder|检查 ^\\d+$ 匹配 12345]\n[TOOL:evil_tool|rm -rf /]"
    out = runtime.parse_tool_directives(text, {"code_interpreter", "regex-builder"})
    # 白名单过滤：evil_tool 不执行；最多 2 条
    assert [o[0] for o in out] == ["code_interpreter", "regex-builder"]
    assert out[0][1] == "print(1+1)"


def test_parse_directives_no_whitelist(runtime):
    assert runtime.parse_tool_directives("[TOOL:code_interpreter|1]", set()) == []


def test_strip_tool_directives(runtime):
    text = "答案是 2。\n[TOOL:code_interpreter|print(1+1)]"
    assert "TOOL:" not in runtime.strip_tool_directives(text)
    assert runtime.strip_tool_directives("答案是 2。").startswith("答案是")


def test_semantic_map(runtime):
    assert runtime._SEMANTIC_TOOL_MAP.get("code_interpreter") == "code_interpreter"


def test_load_agent_bundle_missing_404(runtime):
    with pytest.raises(HTTPException):
        runtime.load_agent_bundle("no_such_agent", "hi")


def test_tool_descriptions_runnable(runtime):
    lines, runnable = runtime._tool_descriptions(["code_interpreter", "regex-builder", "terminal", "weekly-report"])
    assert "code_interpreter" in runnable
    assert "regex-builder" in runnable  # compute 实算
    assert "terminal" not in runnable  # 诚实降级
    assert any("code_interpreter" in line for line in lines)


@pytest.mark.asyncio
async def test_execute_code_interpreter_runtime(runtime, monkeypatch):
    # 真实沙箱执行（不 mock：直接跑，验证受限子进程可用）
    out = await runtime.execute_tool_async("code_interpreter", "print(6*7)")
    assert "42" in out


@pytest.mark.asyncio
async def test_execute_unknown_tool_degrade(runtime):
    out = await runtime.execute_tool_async("no_such_tool_xyz", "hi")
    assert "不存在" in out or "失败" in out


def test_kb_rag_empty_query(runtime, tmp_path):
    assert runtime._kb_rag_context(["kb-x"], "") == ""
    assert runtime._kb_rag_context([], "问题") == ""


def test_kb_rag_file(setup_test_db, tmp_path):
    """绑定 file 知识库 → 检索命中注入 rag_context（真实 DB + 真实文件）。"""
    from datetime import datetime

    import kb_api
    from common.db import get_db

    doc = tmp_path / "ad.md"
    doc.write_text("广告出价策略：智能出价支持分时段与自动调价\n仓库管理：先进先出原则", encoding="utf-8")

    # file KB 检索（内部函数，不依赖路由）
    kb_row = {"type": "file", "path": str(tmp_path), "name": "测试库", "id": "kb-x", "config": "{}"}
    res = kb_api._kb_search_file(kb_row, "广告出价策略", 3)
    assert res["count"] >= 1
    assert any("广告出价策略" in m for m in res["hits"][0]["matches"]), "强相关行应排第一"

    # 插入 KB 行到测试库 → _kb_rag_context 注入「参考知识」段
    conn = get_db()
    conn.execute(
        "INSERT INTO knowledge_bases (id, name, type, path, created_at) VALUES (?,?,?,?,?)",
        ("kb-x", "测试库", "file", str(tmp_path), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    import agent_runtime

    ctx = agent_runtime._kb_rag_context(["kb-x"], "广告出价策略")
    assert "参考知识" in ctx
    assert "广告出价策略" in ctx
    assert "测试库" in ctx


# ════════════════════════════════════════════════════════════════
# 记忆注入（P0：memories 接通执行链路）
# ════════════════════════════════════════════════════════════════
def test_attach_session_memory_injects(setup_test_db, runtime):
    """会话有记忆时：build_agent_system 注入「历史记忆」段，长期优先。"""
    from sessions import add_memory, create_session

    sid = create_session("agent-mem", "记忆测试")
    add_memory(sid, "agent-mem", "用户偏好中文回答", "long")
    add_memory(sid, "agent-mem", "用户在上海", "long")
    add_memory(sid, "agent-mem", "本轮临时任务完成", "short")

    bundle = {"id": "agent-mem"}
    runtime.attach_session_memory(bundle, sid)
    assert bundle["memory_context"], "应生成 memory_context"

    ctx = runtime.build_agent_system(bundle)
    assert "历史记忆" in ctx
    assert "用户偏好中文回答" in ctx
    # 长期/auto 记忆（60% 配额）排在短期之前
    assert ctx.index("用户偏好中文回答") < ctx.index("本轮临时任务完成")


def test_attach_session_memory_missing_session_ok(setup_test_db, runtime):
    """无会话/无记忆 → 静默跳过，system prompt 无记忆段（不阻断执行）。"""
    bundle = {"id": "agent-mem"}
    runtime.attach_session_memory(bundle, "not-exist-session")
    assert not bundle.get("memory_context")
    ctx = runtime.build_agent_system(bundle)
    assert "历史记忆" not in ctx


# ════════════════════════════════════════════════════════════════
# KB 检索 LLM 重排（P1b）
# ════════════════════════════════════════════════════════════════
def test_kb_rerank_orders_by_llm(setup_test_db, runtime, monkeypatch):
    """候选 ≥4 时调一次 LLM 重排；返回下标序 + 未选中补后。"""
    import common.llm

    calls = []

    def fake_call_llm(system, user, **kw):
        calls.append(user)
        return '{"top": [2, 0]}'

    monkeypatch.setattr(common.llm, "call_llm", fake_call_llm)
    assert runtime._kb_rerank("问题", [f"p{i}" for i in range(4)]) == [2, 0, 1, 3]
    assert len(calls) == 1, "只允许一次重排 LLM 调用（成本控制）"


def test_kb_rerank_few_candidates_no_llm(setup_test_db, runtime, monkeypatch):
    """候选 <4 不调 LLM（省成本，关键词序已够好）。"""
    import common.llm

    monkeypatch.setattr(
        common.llm, "call_llm",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("候选不足不应调用 LLM")),
    )
    assert runtime._kb_rerank("问题", ["a", "b", "c"]) == []


def test_kb_rerank_llm_failure_keeps_keyword_order(setup_test_db, runtime, monkeypatch):
    """LLM 故障 → 返回 [] 保持关键词原序（诚实降级不阻断检索）。"""
    import common.llm

    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(common.llm, "call_llm", boom)
    assert runtime._kb_rerank("问题", ["a", "b", "c", "d"]) == []


def test_kb_rag_rerank_reorders_kbs(setup_test_db, tmp_path, runtime, monkeypatch):
    """2 个 file KB × 2 命中 = 4 候选 → LLM 重排把 kb2 候选排前（跨 KB 重排生效）。"""
    from datetime import datetime

    from common.db import get_db

    d1, d2 = tmp_path / "k1", tmp_path / "k2"
    d1.mkdir()
    d2.mkdir()
    (d1 / "a.md").write_text("数据库索引策略：批量扫描优化查询", encoding="utf-8")
    (d1 / "b.md").write_text("数据库运维日常记录", encoding="utf-8")
    (d2 / "c.md").write_text("数据库备份策略与恢复演练", encoding="utf-8")
    (d2 / "d.md").write_text("数据库索引重建排期", encoding="utf-8")

    conn = get_db()
    for kid, name, p in (("k1", "库一", str(d1)), ("k2", "库二", str(d2))):
        conn.execute(
            "INSERT INTO knowledge_bases (id, name, type, path, created_at) VALUES (?,?,?,?,?)",
            (kid, name, "file", p, datetime.now().isoformat()),
        )
    conn.commit()
    conn.close()

    import common.llm

    monkeypatch.setattr(
        common.llm, "call_llm",
        lambda system, user, **kw: '{"top": [2, 3]}',
    )
    ctx = runtime._kb_rag_context(["k1", "k2"], "数据库索引策略")
    assert "参考知识" in ctx
    assert ctx.index("库二") < ctx.index("库一"), "LLM 重排后库二候选应排在库一之前"


# ════════════════════════════════════════════════════════════════
# execute_tool_loop v18 P0：多轮上下文 + 工具事件回调
# ════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_execute_loop_conversation_messages(runtime):
    """多轮上下文（conversation_messages）优先于默认 [system, prompt]。"""
    calls = []

    async def fake_llm(system, prompt, **kw):
        calls.append({"system": system, "prompt": prompt, "messages": kw.get("messages")})
        return "最终答案"

    conv = [
        {"role": "system", "content": "多轮系统"},
        {"role": "user", "content": "上一轮"},
        {"role": "assistant", "content": "上一轮回答"},
        {"role": "user", "content": "当前问题"},
    ]
    out = await runtime.execute_tool_loop(
        "应被忽略的 system", "应被忽略的 prompt", set(), llm_call=fake_llm, conversation_messages=conv
    )
    assert out["result"] == "最终答案"
    # 文本模式：首次调用带完整多轮 messages，system/prompt 参数置空
    assert calls[0]["messages"] == conv
    assert calls[0]["prompt"] == ""


@pytest.mark.asyncio
async def test_execute_loop_on_tool_use_events(runtime, monkeypatch):
    """on_tool_use 在每次真实执行前触发（流式 SSE tool 事件源）；工具真实执行并回喂。"""
    import agent_runtime as ar

    calls = []

    async def fake_llm(system, prompt, **kw):
        calls.append(prompt)
        if "工具执行结果" not in prompt:
            return "[TOOL:code_interpreter|print(1)] 先算"
        return "结果：1"

    events = []

    async def on_tool_use(kind, label, preview):
        events.append((kind, label, preview))

    out = await ar.execute_tool_loop(
        "你是助手", "算一下", {"code_interpreter"}, llm_call=fake_llm, on_tool_use=on_tool_use
    )
    assert events == [("tool", "code_interpreter", "print(1)")]
    assert out["tools_used"] == ["code_interpreter"]
    assert "结果：1" in out["result"]


# ════════════════════════════════════════════════════════════════
# P2 技能参数化：params 定义 + {{param}} 渲染
# ════════════════════════════════════════════════════════════════
def test_skills_context_renders_params(runtime):
    """技能带 params 定义时，注入段列出参数及说明（LLM 据此提取值填占位符）。"""
    rows = [
        {
            "name": "周报生成",
            "description": "按模板出周报",
            "content": "本周完成 {{topic}}，风险 {{risk}}",
            "params": '{"topic": "本周主题", "risk": "主要风险"}',
        }
    ]
    ctx = runtime._skills_context(rows)
    assert "周报生成" in ctx
    assert "topic" in ctx and "本周主题" in ctx
    assert "占位符" in ctx or "提取" in ctx


def test_render_skill_template(runtime):
    """占位符替换；未提供的参数保留原样（诚实降级不猜值）。"""
    out = runtime.render_skill_template("处理 {{svc}} 的 {{err}}", {"svc": "订单服务"})
    assert out == "处理 订单服务 的 {{err}}"
    assert runtime.render_skill_template("", {}) == ""


# ════════════════════════════════════════════════════════════════
# P1-A 记忆按查询相关性筛选（不串味）
# ════════════════════════════════════════════════════════════════
def test_attach_memory_relevance_filters(setup_test_db, runtime, monkeypatch):
    """query 提供时，只有相关记忆进提示词；无关旧话题被过滤（避免稀释预算）。"""
    import sessions

    sid = sessions.create_session("a-rel", "t")
    sessions.add_memory(sid, "a-rel", "订单服务上线失败 回滚预案", "long")
    sessions.add_memory(sid, "a-rel", "用户喜欢简洁风格的周报", "short")
    sessions.add_memory(sid, "a-rel", "数据库索引重建排期定在周三", "short")

    bundle = {"agent": {"id": "a-rel", "instructions": "x"}, "runnable_tools": set()}
    runtime.attach_session_memory(bundle, sid, query="订单服务 回滚 怎么办", limit=2)
    ctx = bundle["memory_context"]
    assert "回滚预案" in ctx, "相关记忆应被选中"
    assert "周报" not in ctx, "无关话题不应稀释预算"
    assert "索引" not in ctx


def test_attach_memory_no_relevant_falls_back_recent(setup_test_db, runtime, monkeypatch):
    """query 与所有记忆都无关 → 诚实降级回「最新 limit 条」（不丢全部上下文）。"""
    import sessions

    sid = sessions.create_session("a-rel2", "t")
    sessions.add_memory(sid, "a-rel2", "历史记忆甲", "short")
    sessions.add_memory(sid, "a-rel2", "历史记忆乙", "short")

    bundle = {"agent": {"id": "a-rel2", "instructions": "x"}, "runnable_tools": set()}
    runtime.attach_session_memory(bundle, sid, query="完全不沾边的问题 zzz")
    ctx = bundle["memory_context"]
    assert "历史记忆甲" in ctx and "历史记忆乙" in ctx, "无相关 → 回退最新 limit 条"


def test_skills_context_programmatic_prefill(setup_test_db):
    """v18 P2：pattern 命中的参数程序化预填占位符；未命中保留占位符走 LLM 提取（双轨）。"""
    import json

    import agent_runtime as runtime

    rows = [{
        "name": "发布助手",
        "description": "多平台发布",
        "content": "按 {{channel}} 渠道发布，标题 {{title}}",
        "params": json.dumps({
            "channel": {"desc": "发布渠道", "pattern": r"渠道[：:]\s*([\u4e00-\u9fff]+)"},
            "title": "标题",
        }),
    }]
    ctx = runtime._skills_context(rows, user_message="渠道：公众号，请帮我发一篇")
    assert "按 公众号 渠道发布" in ctx, f"命中参数应程序化预填：{ctx!r}"
    assert "{{title}}" in ctx, "未命中参数应保留占位符（LLM 兜底）"
    assert "公众号" not in ctx.split("按 公众号")[-1].split("\n")[0], "已填参数不重复列参数说明"

    ctx2 = runtime._skills_context(rows, user_message="帮我发一篇，标题是 X")
    assert "{{channel}}" in ctx2, "pattern 未命中 → 占位符保留"
    assert "渠道" in ctx2, "未命中参数仍列入 LLM 提取说明"

    ctx3 = runtime._skills_context(rows)  # 无用户消息
    assert "{{channel}}" in ctx3 and "{{title}}" in ctx3, "无消息时全部走 LLM 提取（行为与旧版一致）"
