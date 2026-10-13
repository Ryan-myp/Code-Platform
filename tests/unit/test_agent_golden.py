"""Agent 执行链路黄金集（v18 E）：FC/文本双模式管道行为回归门禁。

锁定行为（防未来 FC/解析/护栏重构悄悄漂移）：
- FC 多工具路由 + 工具参数解析
- 纯回答不触发工具
- 文本协议 [TOOL:] 降级路径 + 指令剥离
- 工具执行失败不阻断最终答案
- 轮次护栏：无限指令也被 _MAX_TOOL_ROUNDS 截断

LLM 与工具执行均为脚本假件（monkeypatch），零网络依赖。
"""

import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent.parent.parent / "tests" / "golden"


def _cases():
    data = json.loads((GOLDEN_DIR / "agent_golden.json").read_text(encoding="utf-8"))
    return data["cases"]


def _run_case(case: dict, monkeypatch) -> dict:
    """按 case 定义跑一次 execute_tool_loop，返回结果 dict。"""
    import agent_runtime
    import common.llm

    runnable = set(case.get("runnable_tools") or [])
    script = list(case.get("llm_script") or [])
    calls = {"llm": 0}
    tool_calls_log: list[tuple[str, str]] = []
    tool_override = case.get("tool_result_override")

    # ── 工具执行假件（记录调用；默认返回成功文本，override 返回失败文本）──
    async def fake_execute_tool(name, arg, user_id="default"):
        tool_calls_log.append((name, str(arg)))
        if tool_override:
            return tool_override
        return f"工具「{name}」执行成功（黄金集脚本结果）"

    monkeypatch.setattr(agent_runtime, "execute_tool_async", fake_execute_tool)

    llm_call = None
    if case.get("mode") == "text":
        # 文本协议：注入 llm_call 假件（脚本逐次消费；infinite 则永远给指令）
        if case.get("infinite_directives"):
            async def text_llm(system, prompt, **kw):
                return "[TOOL:kb_search|loop-{}] ".format(calls["llm"]) + "查"

            llm_call = text_llm
        else:
            def _pop():
                calls["llm"] += 1
                return script[calls["llm"] - 1] if calls["llm"] <= len(script) else script[-1]

            async def text_llm(system, prompt, **kw):
                return _pop()

            llm_call = text_llm
    else:
        # FC 模式：patch 生产入口 call_llm_with_tools_async（execute_tool_loop 函数内 import）
        def _pop_fc():
            calls["llm"] += 1
            return script[calls["llm"] - 1] if calls["llm"] <= len(script) else script[-1]

        async def fake_with_tools(system, user, tools, **kw):
            r = _pop_fc()
            return {"content": r.get("content") or "", "tool_calls": r.get("tool_calls")}

        monkeypatch.setattr(common.llm, "call_llm_with_tools_async", fake_with_tools)

    import asyncio

    return asyncio.run(
        agent_runtime.execute_tool_loop(
            "你是测试助手",
            case.get("user_message") or "hello",
            runnable,
            llm_call=llm_call,
        )
    )


def test_agent_golden_cases(setup_test_db, monkeypatch):
    for case in _cases():
        res = _run_case(case, monkeypatch)
        tools = res.get("tools_used") or []
        ans = res.get("result") or ""

        # 期望工具（按出现顺序子序列匹配）
        expected = case.get("expected_tools")
        if expected is not None:
            idx = 0
            for t in expected:
                found = False
                for j in range(idx, len(tools)):
                    if tools[j] == t:
                        idx = j + 1
                        found = True
                        break
                assert found, f"{case['name']}: 期望工具 {t} 应按序执行（实际 {tools}）"

        for t in case.get("forbidden_tools") or []:
            assert t not in tools, f"{case['name']}: 禁止工具 {t} 被调用了"

        for s in case.get("answer_contains") or []:
            assert s in ans, f"{case['name']}: 答案应含 {s!r}（实际 {ans[:80]!r}）"
        for s in case.get("answer_not_contains") or []:
            assert s not in ans, f"{case['name']}: 答案不应含 {s!r}（协议泄漏）"

        cap = case.get("expected_tools_max")
        if cap is not None:
            assert len(tools) <= cap, f"{case['name']}: 轮次护栏失守（工具次数 {len(tools)} > {cap}）"
        assert len(tools) < 100, f"{case['name']}: 疑似死循环"


def test_agent_golden_covers_five_modes(setup_test_db):
    """黄金集本身完整性：5 类行为都在（防止 case 被误删）。"""
    names = [c["name"] for c in _cases()]
    for required in ("fc_two_tools_then_answer", "fc_pure_answer_no_tools", "text_directive_fallback", "tool_error_does_not_block", "text_round_guard"):
        assert required in names, f"黄金集缺少 {required}"
