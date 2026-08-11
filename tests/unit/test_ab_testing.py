"""v15 AB 测试增强单测：运行/结果路由逻辑（LLM 以 mock 替代）。

覆盖：
- run：LLM 返回完整 JSON → 结果落库、winner/confidence/scores 正确组装
- run：LLM 未返回 scores → 兜底为空分结构
- run：A/B 方案为空 → 400
- run：实验不存在 → 404
- results：未运行时返回 status=pending；运行后返回完整结果
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _insert_test(conn, tid="ab_test_001", a="标题A：限时5折", b="标题B：全场清仓", status="draft"):
    conn.execute(
        "INSERT INTO ab_tests (id, name, description, variant_a, variant_b, status, result) VALUES (?,?,?,?,?,?,?)",
        (tid, "首页标题对比", "验证点击", a, b, status, "{}"),
    )
    conn.commit()


class TestRunABTest:
    def test_run_success_persists_result(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import run_ab_test

        conn = get_db()
        _insert_test(conn)
        conn.close()

        fake = {
            "generated_a": "A 完整文案…",
            "generated_b": "B 完整文案…",
            "scores": [
                {"dimension": "吸引力", "a": 90, "b": 70},
                {"dimension": "清晰度", "a": 80, "b": 85},
                {"dimension": "转化力", "a": 88, "b": 60},
                {"dimension": "专业度", "a": 75, "b": 82},
                {"dimension": "记忆点", "a": 92, "b": 65},
            ],
            "winner": "A",
            "confidence": 78,
            "conclusion": "方案A整体占优，建议采用",
        }
        with patch("extended_api.call_llm_async", new=AsyncMock(return_value=json.dumps(fake, ensure_ascii=False))):
            result = asyncio.run(run_ab_test("ab_test_001", data=type("R", (), {"objective": "点击转化率"})(), current_user={"username": "t"}))

        assert result["status"] == "completed"
        assert result["winner"] == "A"
        assert result["confidence"] == 78
        assert len(result["scores"]) == 5
        assert result["objective"] == "点击转化率"
        assert result["generated_a"].startswith("A 完整")

        conn = get_db()
        row = conn.execute("SELECT status, result FROM ab_tests WHERE id='ab_test_001'").fetchone()
        conn.close()
        assert row["status"] == "completed"
        assert json.loads(row["result"])["winner"] == "A"

    def test_run_missing_scores_falls_back(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import run_ab_test

        conn = get_db()
        _insert_test(conn)
        conn.close()

        fake = {"generated_a": "x", "generated_b": "y", "winner": "B", "confidence": 60, "conclusion": ""}
        with patch("extended_api.call_llm_async", new=AsyncMock(return_value=json.dumps(fake))):
            result = asyncio.run(run_ab_test("ab_test_001", data=type("R", (), {"objective": "整体效果"})(), current_user={"username": "t"}))

        # 兜底：五个维度空分结构
        assert len(result["scores"]) == 5
        assert all(s["a"] == 0 and s["b"] == 0 for s in result["scores"])

    def test_run_empty_variants_rejected(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import run_ab_test

        conn = get_db()
        _insert_test(conn, a="", b="")
        conn.close()

        with pytest.raises(HTTPException) as ei:
            asyncio.run(run_ab_test("ab_test_001", data=type("R", (), {"objective": "整体效果"})(), current_user={"username": "t"}))
        assert ei.value.status_code == 400

    def test_run_not_found(self, setup_test_db):
        import asyncio

        from extended_api import run_ab_test

        with pytest.raises(HTTPException) as ei:
            asyncio.run(run_ab_test("no_such", data=type("R", (), {"objective": "整体效果"})(), current_user={"username": "t"}))
        assert ei.value.status_code == 404


class TestGetABResults:
    def test_pending_when_never_run(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import get_ab_test_results

        conn = get_db()
        _insert_test(conn)
        conn.close()

        result = asyncio.run(get_ab_test_results("ab_test_001", current_user={"username": "t"}))
        assert result["status"] == "pending"

    def test_completed_returns_result(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import get_ab_test_results

        conn = get_db()
        _insert_test(conn, status="completed", )
        stored = {"status": "completed", "winner": "B", "confidence": 66, "scores": [], "generated_a": "a", "generated_b": "b"}
        conn.execute("UPDATE ab_tests SET result=? WHERE id='ab_test_001'", (json.dumps(stored, ensure_ascii=False),))
        conn.commit()
        conn.close()

        result = asyncio.run(get_ab_test_results("ab_test_001", current_user={"username": "t"}))
        assert result["status"] == "completed"
        assert result["winner"] == "B"


# ══════════════════════════════════════════════════════════════
# v15-8 分析输出升级：结构化兜底 + 报告导出
# ══════════════════════════════════════════════════════════════


def full_parsed():
    return {
        "generated_a": "A 终稿",
        "generated_b": "B 终稿",
        "scores": [
            {"dimension": "吸引力", "a": 90, "b": 70},
            {"dimension": "清晰度", "a": 80, "b": 85},
            {"dimension": "转化力", "a": 88, "b": 60},
            {"dimension": "专业度", "a": 75, "b": 82},
            {"dimension": "记忆点", "a": 92, "b": 65},
        ],
        "winner": "A",
        "confidence": 78,
        "conclusion": "建议采用方案A",
        "analysis": {
            "winner_reason": "A 在转化力维度领先明显",
            "risks": ["A 文案较长可能影响移动端展示"],
            "next_steps": ["小流量验证 3 天", "观察转化率变化"],
        },
    }


class TestNormalizeABResult:
    def test_full_analysis_kept(self):
        from extended_api import normalize_ab_result

        out = normalize_ab_result(full_parsed(), objective="点击转化率")
        assert out["status"] == "completed"
        assert out["winner"] == "A"
        assert out["confidence"] == 78
        assert out["objective"] == "点击转化率"
        assert out["analysis"]["winner_reason"] == "A 在转化力维度领先明显"
        assert out["analysis"]["risks"] == ["A 文案较长可能影响移动端展示"]
        assert len(out["analysis"]["next_steps"]) == 2
        assert len(out["scores"]) == 5

    def test_missing_analysis_derived(self):
        """无 analysis → 按最大分差维度派生胜出原因。"""
        from extended_api import normalize_ab_result

        parsed = full_parsed()
        parsed.pop("analysis")
        out = normalize_ab_result(parsed)
        # 分差最大为 转化力（88-60=28）
        assert "转化力" in out["analysis"]["winner_reason"]
        assert "28 分" in out["analysis"]["winner_reason"]
        assert out["analysis"]["risks"] == []
        assert out["analysis"]["next_steps"] == []

    def test_missing_scores_filled_and_extra_kept(self):
        from extended_api import normalize_ab_result

        parsed = full_parsed()
        parsed["scores"] = [{"dimension": "吸引力", "a": 80, "b": 60}, {"dimension": "额外维度", "a": 50, "b": 40}]
        out = normalize_ab_result(parsed)
        dims = [s["dimension"] for s in out["scores"]]
        assert dims[:5] == ["吸引力", "清晰度", "转化力", "专业度", "记忆点"]
        assert "额外维度" in dims  # LLM 额外维度保留
        missing = [s for s in out["scores"] if s["dimension"] != "吸引力" and s["dimension"] != "额外维度"]
        assert all(s["a"] == 0 and s["b"] == 0 for s in missing)

    def test_score_clamped_and_invalid_winner_inferred(self):
        from extended_api import normalize_ab_result

        parsed = full_parsed()
        parsed["scores"] = [{"dimension": d, "a": 120, "b": -5} for d in ["吸引力", "清晰度", "转化力", "专业度", "记忆点"]]
        parsed["winner"] = "C"  # 非法胜出方
        out = normalize_ab_result(parsed)
        assert all(s["a"] == 100 and s["b"] == 0 for s in out["scores"])
        assert out["winner"] == "A"  # 总分推断

    def test_confidence_derived_when_zero(self):
        from extended_api import normalize_ab_result

        parsed = full_parsed()
        parsed["confidence"] = "abc"  # 非法
        out = normalize_ab_result(parsed)
        # 按相对分差推断（63/425≈14.8%，低于下限时保底 50）
        assert 50 <= out["confidence"] <= 90
        assert out["confidence"] == 50

    def test_empty_input(self):
        from extended_api import normalize_ab_result

        out = normalize_ab_result({})
        assert out["status"] == "completed"
        assert out["winner"] == "A"  # 总分 0:0 → A
        assert len(out["scores"]) == 5
        assert "胜出" in out["analysis"]["winner_reason"]


class TestBuildABReportMd:
    def test_full_report(self):
        from extended_api import build_ab_report_md, normalize_ab_result

        result = normalize_ab_result(full_parsed(), objective="点击转化率")
        test = {"name": "首页标题对比", "description": "验证点击", "variant_a": "标题A", "variant_b": "标题B"}
        md = build_ab_report_md(test, result)
        assert "# A/B 测试分析报告" in md
        assert "首页标题对比" in md
        assert "| 维度 | 方案A | 方案B |" in md and "| 吸引力 | 90 | 70 |" in md
        assert "胜出方：方案 A" in md and "置信度：78%" in md
        assert "## 胜出原因" in md and "转化力" in md
        assert "## 风险提示" in md
        assert "## 下一步行动" in md
        assert "## AI 扩写终稿" in md and "A 终稿" in md

    def test_minimal_report(self):
        from extended_api import build_ab_report_md

        md = build_ab_report_md({"name": "x"}, {"status": "completed", "winner": "B", "confidence": 60})
        assert "# A/B 测试分析报告" in md
        assert "胜出方：方案 B" in md
        assert "由小团智能平台 AI A/B 测试生成" in md


class TestABReportEndpoint:
    def test_report_export(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import get_ab_test_report, normalize_ab_result

        conn = get_db()
        _insert_test(conn, tid="ab_r1", status="completed")
        stored = normalize_ab_result(full_parsed(), objective="点击转化率")
        conn.execute(
            "UPDATE ab_tests SET result=? WHERE id='ab_r1'",
            (json.dumps(stored, ensure_ascii=False),),
        )
        conn.commit()
        conn.close()

        out = asyncio.run(get_ab_test_report("ab_r1", current_user={"username": "t"}))
        assert out["filename"] == "首页标题对比-AB实验报告.md"
        assert "## 胜出原因" in out["content"]
        assert "| 吸引力 | 90 | 70 |" in out["content"]

    def test_report_not_run_404(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from extended_api import get_ab_test_report

        conn = get_db()
        _insert_test(conn, tid="ab_r2")
        conn.close()

        with pytest.raises(HTTPException) as ei:
            asyncio.run(get_ab_test_report("ab_r2", current_user={"username": "t"}))
        assert ei.value.status_code == 404
        assert "尚未运行" in ei.value.detail

    def test_report_not_found_404(self, setup_test_db):
        import asyncio

        from extended_api import get_ab_test_report

        with pytest.raises(HTTPException) as ei:
            asyncio.run(get_ab_test_report("no_such", current_user={"username": "t"}))
        assert ei.value.status_code == 404
