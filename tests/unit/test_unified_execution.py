"""统一执行范式 v2：单 Agent / Team / Workflow 三层共用「提示词 + 工具」执行链路。

锁定：
- LLM 生成工具（type 为 None 的 54 个）进入 Agent 可执行白名单（上限 4 控成本）
- Workflow 新增 tool / kb 节点：编排可直接驱动平台工具广场与知识库检索
- Workflow agent 节点升级为完整 bundle（RAG/技能/工具循环），不再裸调 LLM
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture
def auth_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _make_agent(client, headers, name, tools=None, instructions="你是助手"):
    r = client.post(
        "/api/agents",
        headers=headers,
        json={
            "name": name,
            "description": "",
            "instructions": instructions,
            "model": "agnes-3.0-flash",
            "tools": tools or [],
            "knowledge_base_ids": [],
            "skill_ids": [],
            "mcp_server_ids": [],
        },
    )
    assert r.status_code == 200
    return r.json()["id"]


# ══════════════════════════════════════════════════════════════
# 白名单：LLM 生成工具可执行（上限 4）
# ══════════════════════════════════════════════════════════════

class TestToolWhitelist:
    def test_llm_tools_become_runnable_capped_at_4(self):
        import agent_runtime
        from tool_definitions import TOOL_DEFINITIONS

        llm_ids = [k for k, v in TOOL_DEFINITIONS.items() if v.get("type") is None]
        assert len(llm_ids) >= 10  # 前置：LLM 工具确实存在
        # 给 6 个 LLM 工具 → 只有前 4 个进白名单
        lines, runnable = agent_runtime._tool_descriptions(llm_ids[:6])
        llm_runnable = [t for t in llm_ids[:6] if t in runnable]
        assert len(llm_runnable) == 4
        # compute 工具不受 LLM 上限影响（8 个工具内：6 LLM + 2 compute + code_interpreter）
        compute_ids = [k for k, v in TOOL_DEFINITIONS.items() if v.get("type") == "compute"]
        _, runnable2 = agent_runtime._tool_descriptions(llm_ids[:4] + compute_ids[:3] + ["code_interpreter"])
        assert all(c in runnable2 for c in compute_ids[:3])
        assert "code_interpreter" in runnable2

    def test_agent_with_llm_tool_can_execute_it(self, auth_token, monkeypatch):
        """Agent 绑定 LLM 工具 → 工具循环内真实经工具广场执行器调用。"""
        import agent_runtime

        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = _make_agent(client, headers, "LLM 工具 Agent", tools=["meeting-notes"])

        bundle = agent_runtime.load_agent_bundle(agent_id, "整理这份会议")
        assert "meeting-notes" in (bundle.get("runnable_tools") or [])

        # 用 fake LLM 走工具循环：第一轮发指令 → 真实执行 meeting-notes（LLM 工具）
        seen = []

        async def fake_llm(system, prompt, **kw):
            seen.append(prompt)
            if "工具执行结果" in prompt:
                return "会议纪要整理完成"
            return "调用工具 [TOOL:meeting-notes|今天开会有什么结论]"

        out = _run(
            agent_runtime.execute_tool_loop(
                agent_runtime.build_agent_system(bundle),
                "整理会议",
                set(bundle["runnable_tools"]),
                llm_call=fake_llm,
            )
        )
        assert out["tools_used"] == ["meeting-notes"]
        # LLM 工具真实执行：回喂轮 prompt 含工具执行结果段
        assert any("工具执行结果" in p for p in seen)


# ══════════════════════════════════════════════════════════════
# Workflow 新节点：tool / kb
# ══════════════════════════════════════════════════════════════

class TestWorkflowNewNodes:
    def test_tool_node_runs_code_interpreter(self):
        from workflows.executor import WorkflowExecutor

        ex = WorkflowExecutor()
        out = _run(ex.execute_node("tool", {"tool_id": "code_interpreter", "input": "print(2**10)"}, {}))
        assert out["status"] == "success"
        assert "1024" in out["result"]

    def test_tool_node_requires_tool_id(self):
        from workflows.executor import WorkflowExecutor

        ex = WorkflowExecutor()
        out = _run(ex.execute_node("tool", {"input": "x"}, {}))
        assert out["status"] == "error"

    def test_kb_node_missing_config_errors(self):
        from workflows.executor import WorkflowExecutor

        ex = WorkflowExecutor()
        out = _run(ex.execute_node("kb", {"query": "x"}, {}))
        assert out["status"] == "error"
        out2 = _run(ex.execute_node("kb", {"kb_ids": ["kb_not_exist_123"], "query": "x"}, {}))
        assert out2["status"] == "success"  # KB 不存在 → 诚实空结果，不炸

    def test_kb_node_returns_hits(self, auth_token):
        """file 型知识库：上传文档 → kb 节点检索命中。"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        up = client.post(
            "/api/knowledge-bases/upload",
            headers=headers,
            files={
                "file": (
                    "wf_kb_test.md",
                    "工作流知识库节点测试条目：橙色是平台默认主题色".encode(),
                    "utf-8",
                )
            },
        )
        assert up.status_code == 200, up.text
        kb_path = up.json()["path"]

        r = client.post(
            "/api/knowledge-bases",
            headers=headers,
            json={"name": "wf-kb", "type": "file", "path": kb_path},
        )
        assert r.status_code == 200, r.text
        kb_id = r.json()["id"]

        from workflows.executor import WorkflowExecutor

        ex = WorkflowExecutor()
        out = _run(ex.execute_node("kb", {"kb_ids": [kb_id], "query": "默认主题色"}, {}))
        assert out["status"] == "success"
        assert "橙色" in out["result"]


# ══════════════════════════════════════════════════════════════
# Workflow agent 节点 = 完整 bundle
# ══════════════════════════════════════════════════════════════

class TestWorkflowAgentNodeBundle:
    def test_agent_node_uses_tools(self, auth_token, monkeypatch):

        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = _make_agent(
            client,
            headers,
            "wf 数值 Agent",
            tools=["code_interpreter"],
            instructions="你是数值计算专家",
        )

        import common.llm

        async def fake_fc(system, prompt, tools, **kw):
            msgs = kw.get("messages") or []
            # bundle 工具清单已注入（FC 模式下 system 在 messages[0]）
            if msgs:
                assert "code_interpreter" in str(msgs[0].get("content") or "")
            if any(m.get("role") == "tool" for m in msgs):
                return {"content": "答案：7", "tool_calls": None}
            return {
                "content": "",
                "tool_calls": [{"id": "c1", "name": "code_interpreter", "arguments": '{"input": "print(3+4)"}'}],
            }

        monkeypatch.setattr(common.llm, "call_llm_with_tools_async", fake_fc)

        from workflows.executor import WorkflowExecutor

        ex = WorkflowExecutor()
        out = _run(
            ex.execute_node(
                "agent",
                {"agent_id": agent_id, "message": "3+4 等于几"},
                {},
                {},
            )
        )
        assert out["status"] == "success"
        assert "7" in out["result"]
        assert out["tools_used"] == ["code_interpreter"]
        assert "[TOOL:" not in out["result"]
