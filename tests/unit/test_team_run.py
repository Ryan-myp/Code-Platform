"""团队协作执行 v2：成员以完整 Agent bundle（RAG/技能/工具循环）真实参与。

历史短板：run_team 只用 agent.instructions 调 LLM，绑定的知识库/技能/工具
全部未接入协作链路。本组测试锁定升级后的行为：
- execute_tool_loop 可复用工具循环（无工具直通 / 真实沙箱执行 / 2 轮上限）
- /api/teams/{id}/run 成员结果携带 tools_used，成员 system prompt 含工具清单
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


def _make_agent(client, headers, name, tools=None):
    r = client.post(
        "/api/agents",
        headers=headers,
        json={
            "name": name,
            "description": "",
            "instructions": "你擅长数值计算",
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
# execute_tool_loop（agent_runtime）
# ══════════════════════════════════════════════════════════════

class TestExecuteToolLoop:
    def test_no_runnable_tools_passthrough(self):
        import agent_runtime

        calls = []

        async def fake_llm(system, prompt, **kw):
            calls.append(prompt)
            return "直接答案 [TOOL:web_search|忽略我]"  # 非白名单指令必须被剥离

        out = _run(agent_runtime.execute_tool_loop("sys", "任务", set(), llm_call=fake_llm))
        assert out["result"] == "直接答案"
        assert out["tools_used"] == []
        assert len(calls) == 1  # 无可用工具 → 不会进入回喂轮

    def test_code_interpreter_round_trip(self):
        import agent_runtime

        async def fake_llm(system, prompt, **kw):
            if "工具执行结果" in prompt:
                return "最终答案：12"
            return "我来算一下 [TOOL:code_interpreter|print(6*2)]"

        out = _run(
            agent_runtime.execute_tool_loop(
                "sys",
                "算 6*2",
                {"code_interpreter"},
                llm_call=fake_llm,
            )
        )
        assert out["tools_used"] == ["code_interpreter"]
        assert "12" in out["result"]
        assert "[TOOL:" not in out["result"]
        # 沙箱真实执行痕迹：工具日志包含执行说明
        assert any("执行" in line for line in out["tool_logs"])

    def test_max_two_rounds_strips_leftover_directives(self):
        import agent_runtime

        async def fake_llm(system, prompt, **kw):
            # 每轮都发指令 → 最多执行 2 轮后必须停止且剥离残留指令
            return "再来 [TOOL:code_interpreter|print(1)]"

        out = _run(
            agent_runtime.execute_tool_loop(
                "sys",
                "任务",
                {"code_interpreter"},
                llm_call=fake_llm,
            )
        )
        assert out["tools_used"].count("code_interpreter") <= 2
        assert "[TOOL:" not in out["result"]


# ══════════════════════════════════════════════════════════════
# /api/teams/{id}/run 全链路（LLM 打桩，验证 bundle 接线）
# ══════════════════════════════════════════════════════════════

class TestRunTeamUsesAgentBundle:
    def test_member_runs_with_tools_and_reports_usage(self, auth_token, monkeypatch):
        import agent_runtime
        import chat_engine

        headers = {"Authorization": f"Bearer {auth_token}"}
        agent_id = _make_agent(client, headers, "数值专家", tools=["code_interpreter"])

        r = client.post(
            "/api/teams",
            headers=headers,
            json={"name": "工具协作测试", "plan": "pro", "seats": 2, "members": [agent_id]},
        )
        assert r.status_code == 200
        team_id = r.json()["id"]

        # 记录成员执行时的 system prompt（证明 bundle 接线：工具清单存在）
        seen_systems = []

        async def fake_member_llm(system, prompt, **kw):
            seen_systems.append(system)
            if "工具执行结果" in prompt:
                return "结论：6×2=12"
            return "先用工具算 [TOOL:code_interpreter|print(6*2)]"

        async def fake_coord_llm(system, prompt, **kw):
            return "协调汇总：团队计算完成，结果 12"

        monkeypatch.setattr(agent_runtime, "call_llm_async", fake_member_llm)
        monkeypatch.setattr(chat_engine, "call_llm_async", fake_coord_llm)

        resp = client.post(f"/api/teams/{team_id}/run", headers=headers, json={"message": "算一下 6*2"})
        assert resp.status_code == 200
        data = resp.json()

        members = data["members"]
        assert len(members) == 1
        m0 = members[0]
        assert m0["tools_used"] == ["code_interpreter"]
        assert "12" in m0["result"]
        assert "[TOOL:" not in m0["result"]
        # 协调者汇总是独立输出
        assert data["result"] == "协调汇总：团队计算完成，结果 12"

        # bundle 接线证据：成员 system prompt 含工具清单
        assert any("code_interpreter" in s for s in seen_systems)

    def test_sequential_mode_chains_member_outputs(self, auth_token, monkeypatch):
        import agent_runtime
        import chat_engine

        headers = {"Authorization": f"Bearer {auth_token}"}
        a1 = _make_agent(client, headers, "第一步")
        a2 = _make_agent(client, headers, "第二步")
        r = client.post(
            "/api/teams",
            headers=headers,
            json={"name": "顺序协作", "plan": "pro", "seats": 2, "members": [a1, a2]},
        )
        assert r.status_code == 200
        team_id = r.json()["id"]
        client.patch(f"/api/teams/{team_id}", headers=headers, json={"description": ""})

        prompts_seen = []

        async def fake_member_llm(system, prompt, **kw):
            prompts_seen.append(prompt)
            return f"成员产出：{prompt[:10]}"

        async def fake_coord_llm(system, prompt, **kw):
            return "顺序汇总完成"

        monkeypatch.setattr(agent_runtime, "call_llm_async", fake_member_llm)
        monkeypatch.setattr(chat_engine, "call_llm_async", fake_coord_llm)

        # 顺序模式跑一次即可验证链路（mode 需要置为 sequential）
        import json as _json

        from common.db import get_db

        conn = get_db()
        conn.execute("UPDATE teams SET mode='sequential' WHERE id=?", (team_id,))
        conn.commit()
        conn.close()

        resp = client.post(f"/api/teams/{team_id}/run", headers=headers, json={"message": "任务"})
        assert resp.status_code == 200
        # 第二个成员的 prompt 必须携带前序成员产出（顺序链式上下文）
        assert any("前序成员产出" in p for p in prompts_seen[1:])

    def test_team_run_without_members_still_works(self, auth_token, monkeypatch):
        import chat_engine

        headers = {"Authorization": f"Bearer {auth_token}"}
        r = client.post(
            "/api/teams",
            headers=headers,
            json={"name": "无成员测试", "plan": "pro", "seats": 1, "members": []},
        )
        assert r.status_code == 200
        team_id = r.json()["id"]

        async def fake_llm(system, prompt, **kw):
            return "团队指令直答"

        monkeypatch.setattr(chat_engine, "call_llm_async", fake_llm)
        resp = client.post(f"/api/teams/{team_id}/run", headers=headers, json={"message": "hi"})
        assert resp.status_code == 200
        assert resp.json()["result"] == "团队指令直答"
