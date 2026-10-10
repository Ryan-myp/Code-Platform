"""游戏工坊重构回归：POST /api/games/generate 提交端点 + _extract_json 多级容错。

背景：提交端点在重构中丢失，前端 GameFactoryPage 调用 404（工厂验收发现）。
"""

import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import game_factory  # noqa: E402


def test_generate_endpoint_exists():
    """端点必须存在（防止再次回归丢失）。"""
    assert hasattr(game_factory, "generate_game")
    assert hasattr(game_factory, "GenerateRequest")


def test_extract_json_accepts_fenced_and_noisy():
    """旧解析器弱项：代码块 + 前后噪音 + 单引号，多级容错后应可解析。"""
    noisy = "好的，这是结果：\n```json\n{'name': 'x', 'files': {}}\n```\n希望有帮助"
    out = game_factory._extract_json(noisy)
    assert out["name"] == "x"


def test_extract_json_truncation_repair_still_works():
    """截断 JSON（尾部未闭合）→ 抢救已完成部分（含被截断前的所有键）。"""
    truncated = '{"outer": {"inner": 1}, "more": "text'
    out = game_factory._extract_json(truncated)
    assert out == {"outer": {"inner": 1}, "more": "text"}


def test_repair_truncated_json_helper_direct():
    """游戏自有截断修复助手（_extract_json 的兜底路径）独立验证。"""
    raw = '{"a": 1, "b": "xy'
    out = game_factory._repair_truncated_json(raw, len(raw))
    assert out == {"a": 1, "b": "xy"}
