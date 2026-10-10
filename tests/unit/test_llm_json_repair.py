"""LLM JSON 自修复工具测试：call_llm_json / call_llm_json_async。

覆盖：一次成功 / 首次坏 JSON 触发修复重试 / 类型不符触发修复 / 双败抛错。
"""

from unittest.mock import AsyncMock, patch

import pytest

from common import llm as llm_mod


def test_json_first_try_ok():
    with patch.object(llm_mod, "call_llm", return_value='{"a": 1}'):
        assert llm_mod.call_llm_json("sys", "user") == {"a": 1}


def test_json_repair_on_broken_first():
    """首次返回带说明文字 + 单引号（解析失败）→ 修复重试携带【修复指令】→ 成功。"""
    calls = []

    def fake_call_llm(system, user, **kw):
        calls.append(user)
        if "修复指令" in user:
            return '[{"title_direction": "x"}]'
        return "好的，这是结果：'a': 1"  # 非 JSON

    with patch.object(llm_mod, "call_llm", side_effect=fake_call_llm):
        out = llm_mod.call_llm_json("sys", "user", expect="array")
    assert out == [{"title_direction": "x"}]
    assert len(calls) == 2 and "修复指令" in calls[1]


def test_json_type_mismatch_triggers_repair():
    """要 array 却给 object → 触发修复重试。"""

    def fake_call_llm(system, user, **kw):
        if "修复指令" in user:
            return "[]"
        return '{"not": "list"}'

    with patch.object(llm_mod, "call_llm", side_effect=fake_call_llm):
        assert llm_mod.call_llm_json("sys", "user", expect="array") == []


def test_json_double_failure_raises():
    def fake_call_llm(system, user, **kw):
        return "完全不是 JSON"

    with patch.object(llm_mod, "call_llm", side_effect=fake_call_llm):
        with pytest.raises(ValueError):
            llm_mod.call_llm_json("sys", "user")


@pytest.mark.asyncio
async def test_json_async_repair():
    async def fake_call_llm_async(system, user, **kw):
        if "修复指令" in user:
            return '{"ok": 1}'
        return "说明文字 ```json\n{broken"

    with patch.object(llm_mod, "call_llm_async", new=AsyncMock(side_effect=fake_call_llm_async)):
        assert await llm_mod.call_llm_json_async("sys", "user") == {"ok": 1}
