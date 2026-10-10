"""工具执行 worker 身份注入测试：汇报人/作者栏应使用当前用户名，不再输出 [待补充]。"""

from unittest.mock import AsyncMock, patch

import pytest

import tool_hub


@pytest.mark.asyncio
async def test_worker_injects_username_into_system_prompt():
    captured = {}

    async def fake_llm(system, user, **kw):
        captured["system"] = system
        return "OK"

    payload = {"tool_id": "weekly-report", "input": "本周完成X", "params": {}, "username": "alice", "user_id": "u1"}
    with patch.object(tool_hub, "call_llm_async", new=AsyncMock(side_effect=fake_llm)):
        await tool_hub._run_tool_worker(payload, progress=None)

    assert "alice" in captured["system"]
    assert "不要输出 [待补充]" in captured["system"]


@pytest.mark.asyncio
async def test_worker_without_username_no_identity_line():
    captured = {}

    async def fake_llm(system, user, **kw):
        captured["system"] = system
        return "OK"

    payload = {"tool_id": "weekly-report", "input": "x", "params": {}, "username": "", "user_id": ""}
    with patch.object(tool_hub, "call_llm_async", new=AsyncMock(side_effect=fake_llm)):
        await tool_hub._run_tool_worker(payload, progress=None)

    assert "当前用户" not in captured["system"]
