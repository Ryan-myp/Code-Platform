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


# ── parse_llm_json 截断修复（LLM 输出被 token 上限截断 → 抢救已完成片段）──────────────
def test_parse_llm_json_repair_truncated_object():
    """对象被截断（尾部未闭合）→ 补全闭合符，返回已完成部分。"""
    truncated = '{"meta": {"a": 1}, "slides": [{"t": 1}, {"t": 2}'
    out = llm_mod.parse_llm_json(truncated)
    assert out["slides"] == [{"t": 1}, {"t": 2}]


def test_parse_llm_json_repair_truncated_string():
    """截断在字符串中间 → 补全引号 + 闭合，仍解析成功。"""
    truncated = '{"name": "hello wo'
    out = llm_mod.parse_llm_json(truncated)
    assert out == {"name": "hello wo"}


def test_parse_llm_json_repair_trailing_comma():
    """截断在逗号后（尾逗号）→ 去悬空逗号 + 闭合。"""
    truncated = '{"a": 1, "b": 2,'
    out = llm_mod.parse_llm_json(truncated)
    assert out == {"a": 1, "b": 2}


def test_parse_llm_json_repair_array_truncated():
    """顶层数组被截断 → 补全闭合。"""
    truncated = '[1, 2, 3'
    out = llm_mod.parse_llm_json(truncated)
    assert out == [1, 2, 3]
