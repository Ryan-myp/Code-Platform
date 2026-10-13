"""E2E：UI 视角的 agent 对话 × 工具一致性验证（v18 能力验收）。

场景（模拟前端用户操作）：
1. POST /api/agents 创建 agent（选工具 weekly-report / viral-title）
2. POST /api/agents/{id}/run 把「工具场景的 prompt」直接当对话消息传入
3. agent FC 路由 → 调用工具广场对应工具 → 最终答案携带工具产出
4. 基线：同一 prompt 直接走工具执行路径（tool_hub._run_tool_worker）

验收点：agent 路径的工具产出 == 工具直接执行产出（同一 fake LLM 下逐字一致），
证明「界面创建的 agent 对话能力」与「工厂/工具能力」同源一致，路由无丢字、无改写。

零网络：LLM 三层全部 fake（FC 层 common.llm、工具内部 tool_hub、
文本协议 agent_runtime），确定性输出。
"""

import json

import pytest


def _tool_llm_fake():
    """工具广场内部 LLM：确定性回声，锁定「工具产出」内容。"""
    async def fake(system_prompt: str, user_prompt: str, **kwargs) -> str:
        return f"E2E-GEN｜{user_prompt.strip()[:60]}"
    return fake


def _text_llm_fake():
    """无工具时的文本协议 LLM（agent 纯直答路径），确定性输出。"""
    async def fake(system_prompt: str, user_prompt: str, **kwargs) -> str:
        return f"E2E-ANSWER：{user_prompt.strip()[:60]}"
    return fake


def _fc_fake():
    """agent FC 层：关键词路由（周报→weekly-report，标题→viral-title），第二轮回传工具结果。"""
    async def fake(system, prompt, tools, **kw):
        messages = kw.get("messages") or []
        if any(m.get("role") == "tool" for m in messages):
            last_tool = next(m["content"] for m in reversed(messages) if m.get("role") == "tool")
            return {"content": f"E2E-FINAL：{last_tool.strip()[:200]}", "tool_calls": []}
        user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
        if "周报" in user_msg:
            return {"content": "", "tool_calls": [
                {"id": "c1", "name": "weekly-report", "arguments": json.dumps({"input": user_msg})}]}
        if "标题" in user_msg:
            return {"content": "", "tool_calls": [
                {"id": "c1", "name": "viral-title", "arguments": json.dumps({"input": user_msg})}]}
        return {"content": f"E2E-ANSWER：{user_msg[:60]}", "tool_calls": []}
    return fake


@pytest.fixture(autouse=True)
def fake_llms(monkeypatch):
    """三层 fake：FC 路由 + 工具内部生成 + 文本协议（确定性，无网络）。"""
    import agent_runtime
    import common.llm
    import tool_hub

    monkeypatch.setattr(common.llm, "call_llm_with_tools_async", _fc_fake())
    monkeypatch.setattr(tool_hub, "call_llm_async", _tool_llm_fake())
    monkeypatch.setattr(agent_runtime, "call_llm_async", _text_llm_fake())


def _create_agent(client, auth_headers, tools: list[str]) -> str:
    res = client.post(
        "/api/agents",
        headers=auth_headers,
        json={"name": "e2e-agent", "description": "E2E 工具一致性验证", "tools": tools},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _direct_tool_run(tool_id: str, msg: str, user_id: str = "u_e2e") -> str:
    """基线：prompt 直接走工具执行路径（工具广场同款 worker）。"""
    import asyncio

    import tool_hub

    res = asyncio.run(tool_hub._run_tool_worker(
        {"tool_id": tool_id, "input": msg, "user_id": user_id, "username": "e2e"}))
    return res["result"]


def test_agent_weekly_report_matches_direct_tool(setup_test_db, auth_headers):
    """agent 对话「写周报」→ FC 路由 weekly-report → 产出与工具直接执行逐字一致。"""
    from fastapi.testclient import TestClient

    from main import app

    msg = "本周完成了 agent 工具循环改造、修复了知识库检索空召回，帮我写一份周报"
    aid = _create_agent(TestClient(app), auth_headers, ["weekly-report"])

    direct = _direct_tool_run("weekly-report", msg)
    assert "E2E-GEN" in direct, f"基线工具产出异常：{direct!r}"

    client = TestClient(app)
    res = client.post(
        f"/api/agents/{aid}/run",
        headers=auth_headers,
        json={"message": msg, "user_id": "u_e2e"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "weekly-report" in body["tools_used"], f"FC 未路由到 weekly-report：{body['tools_used']}"
    assert direct in body["result"], "agent 最终答案应原样携带工具产出（与直接执行一致）"


def test_agent_viral_title_matches_direct_tool(setup_test_db, auth_headers):
    """第二工具（爆款标题）路由 + 一致性。"""
    from fastapi.testclient import TestClient

    from main import app

    msg = "为智能助手产品写个爆款标题，突出 3 分钟出稿的卖点"
    aid = _create_agent(TestClient(app), auth_headers, ["viral-title"])

    direct = _direct_tool_run("viral-title", msg)
    assert "E2E-GEN" in direct

    client = TestClient(app)
    res = client.post(f"/api/agents/{aid}/run", headers=auth_headers, json={"message": msg})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "viral-title" in body["tools_used"], f"FC 未路由到 viral-title：{body['tools_used']}"
    assert direct in body["result"], "agent 最终答案应原样携带工具产出"


def test_agent_no_tools_pure_answer(setup_test_db, auth_headers):
    """未挂工具的 agent：纯 LLM 直答，tools_used 为空（不误触发工具路径）。"""
    from fastapi.testclient import TestClient

    from main import app

    msg = "帮我总结：这周干了啥来着？"
    aid = _create_agent(TestClient(app), auth_headers, [])

    client = TestClient(app)
    res = client.post(f"/api/agents/{aid}/run", headers=auth_headers, json={"message": msg})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tools_used"] == [], f"无工具 agent 不应调用工具：{body['tools_used']}"
    assert body["result"].startswith("E2E-ANSWER"), f"应为 LLM 直答：{body['result']!r}"


def test_agent_model_selection_takes_effect(setup_test_db, auth_headers, monkeypatch):
    """v18 P0：agent 行上的 model 字段必须透传到 LLM 层（此前 UI 可选但实际无效）。"""
    import common.llm

    captured: list[str] = []
    orig_fc = _fc_fake()

    async def recording_fc(system, prompt, tools, **kw):
        captured.append(kw.get("model") or "")
        return await orig_fc(system, prompt, tools, **kw)

    monkeypatch.setattr(common.llm, "call_llm_with_tools_async", recording_fc)

    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    res = client.post(
        "/api/agents",
        headers=auth_headers,
        json={"name": "e2e-model", "model": "e2e-custom-model", "tools": ["weekly-report"]},
    )
    assert res.status_code == 200, res.text
    aid = res.json()["id"]

    run = client.post(
        f"/api/agents/{aid}/run",
        headers=auth_headers,
        json={"message": "帮我写一份周报"},
    )
    assert run.status_code == 200, run.text
    assert captured, "FC 调用应发生"
    assert "e2e-custom-model" in captured, f"agent 模型未透传到 LLM 层：{captured}"
