"""v15 数据预测增强单测：预测区间（上下界）规范化 + 模型选择说明。

覆盖：
- normalize_forecast_ranges：区间倒置交换、缺失补预测值、charts 上下界与 labels 对齐
- build_method_explanation：三种方法说明 + 备选对比、未知方法回退
- worker 集成：LLM 输出含区间 → 返回规范化区间 + method_explanation，落库 done
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


@pytest.fixture(autouse=True)
def _init_forecast_tables(setup_test_db):
    """forecast_records 表由模块级 init_db 创建（可能建在旧库），测试库内幂等重建。"""
    import data_forecast

    data_forecast.init_db()


def sample_llm_json():
    """带问题的 LLM 输出：区间倒置 + 缺区间 + charts 上下界倒置。"""
    return (
        '{"overview": {"record_count": 12, "columns": ["日期", "金额"], "time_range": "2026-01 ~ 2026-12",'
        ' "data_quality": "A", "summary": "整体上升"},'
        ' "statistics": {"columns": []},'
        ' "trend_analysis": {"overall_trend": "上升", "seasonal_patterns": "无", "anomalies": [],'
        ' "correlations": [], "key_findings": ["销售额持续增长"]},'
        ' "predictions": {"method": "趋势外推",'
        ' "short_term": {"description": "继续上升", "confidence": "高"},'
        ' "medium_term": {"description": "稳步上升", "confidence": "中"},'
        ' "forecast_values": ['
        '   {"period": "2026-Q1", "value": 120, "low": 150, "high": 110},'
        '   {"period": "2026-Q2", "value": 135}'
        ' ], "risks": ["外部冲击"]},'
        ' "recommendations": [{"priority": 1, "level": "重要", "action": "加大投入",'
        ' "expected_impact": "+10%", "timeline": "Q2"}],'
        ' "charts": {"labels": ["1月", "2月", "3月"], "actual": [100, 110, 115],'
        ' "forecast": [null, null, 120], "trend_line": [100, 108, 115],'
        ' "upper_bound": [null, null, 110], "lower_bound": [null, null, 130]}}'
    )


class TestNormalizeRanges:
    def test_valid_ranges_unchanged(self):
        from data_forecast import normalize_forecast_ranges

        result = {
            "predictions": {"forecast_values": [{"period": "Q1", "value": 100, "low": 90, "high": 110}]}
        }
        out = normalize_forecast_ranges(result)
        fv = out["predictions"]["forecast_values"][0]
        assert (fv["low"], fv["value"], fv["high"]) == (90, 100, 110)

    def test_inverted_range_swapped(self):
        from data_forecast import normalize_forecast_ranges

        result = {
            "predictions": {"forecast_values": [{"period": "Q1", "value": 120, "low": 150, "high": 110}]}
        }
        fv = normalize_forecast_ranges(result)["predictions"]["forecast_values"][0]
        assert fv["low"] == 110
        assert fv["high"] == 150
        assert fv["low"] <= fv["value"] <= fv["high"]

    def test_missing_low_high_filled_with_value(self):
        from data_forecast import normalize_forecast_ranges

        result = {"predictions": {"forecast_values": [{"period": "Q1", "value": 135}]}}
        fv = normalize_forecast_ranges(result)["predictions"]["forecast_values"][0]
        assert fv["low"] == 135
        assert fv["high"] == 135

    def test_invalid_values_skipped(self):
        from data_forecast import normalize_forecast_ranges

        result = {
            "predictions": {
                "forecast_values": [
                    {"period": "Q1", "value": "abc"},
                    {"period": "Q2", "value": 10, "low": "x", "high": None},
                ]
            }
        }
        values = normalize_forecast_ranges(result)["predictions"]["forecast_values"]
        assert values[0] == {"period": "Q1", "value": "abc"}  # 非数字跳过
        assert values[1]["low"] == 10  # 非法 low 回退预测值
        assert values[1]["high"] == 10

    def test_charts_aligned_with_labels(self):
        from data_forecast import normalize_forecast_ranges

        result = {
            "charts": {
                "labels": ["1月", "2月", "3月"],
                "upper_bound": [None, None, 110],
                "lower_bound": [None, None, 130],  # 倒置 → 交换
            }
        }
        charts = normalize_forecast_ranges(result)["charts"]
        assert len(charts["upper_bound"]) == 3
        assert len(charts["lower_bound"]) == 3
        assert charts["upper_bound"][2] == 130
        assert charts["lower_bound"][2] == 110

    def test_charts_short_arrays_padded(self):
        from data_forecast import normalize_forecast_ranges

        result = {
            "charts": {
                "labels": ["1月", "2月", "3月", "4月"],
                "upper_bound": [None, None, 110],  # 短
                "lower_bound": "oops",  # 非 list
            }
        }
        charts = normalize_forecast_ranges(result)["charts"]
        assert charts["upper_bound"] == [None, None, 110, None]
        assert charts["lower_bound"] == [None, None, None, None]

    def test_none_input(self):
        from data_forecast import normalize_forecast_ranges

        assert normalize_forecast_ranges(None) == {}
        assert normalize_forecast_ranges({}) == {}


class TestMethodExplanation:
    def test_known_methods(self):
        from data_forecast import build_method_explanation

        for method in ["趋势外推", "移动平均", "季节性分解"]:
            exp = build_method_explanation(method)
            assert exp["current"] == method
            assert "适用场景" in exp["info"]
            assert "优点" in exp["info"]
            assert "缺点" in exp["info"]
            # 备选为另外两种
            assert len(exp["alternatives"]) == 2
            assert all(a["name"] != method for a in exp["alternatives"])

    def test_unknown_method_fallback(self):
        from data_forecast import build_method_explanation

        exp = build_method_explanation("神秘算法")
        assert exp["current"] == "神秘算法"
        assert "综合判断" in exp["info"]["适用场景"]
        assert len(exp["alternatives"]) == 3

    def test_empty_method(self):
        from data_forecast import build_method_explanation

        exp = build_method_explanation(None)
        assert exp["current"] == "AI 自动选择"
        assert len(exp["alternatives"]) == 3
        assert build_method_explanation("  ")["current"] == "AI 自动选择"


class TestForecastWorker:
    def test_worker_normalizes_ranges_and_explanation(self, tmp_path, monkeypatch):
        """worker：LLM 输出区间倒置/缺失 → 规范化 + 模型说明，落库 done。"""
        import data_forecast
        from common.db import get_db_context

        csv_path = tmp_path / "sales.csv"
        csv_path.write_text("日期,金额\n2026-01,100\n2026-02,110\n2026-03,115\n", encoding="utf-8")

        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO forecast_records (id, filename, filepath, row_count, columns, status, user_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    "data_test_1",
                    "sales.csv",
                    str(csv_path),
                    3,
                    '["日期", "金额"]',
                    "uploaded",
                    USER["user_id"],
                    datetime.now().isoformat(),
                ),
            )

        monkeypatch.setattr(data_forecast, "call_llm", lambda *a, **kw: sample_llm_json())
        monkeypatch.setattr(data_forecast, "log_usage", lambda *a, **kw: None)

        result = asyncio.run(
            data_forecast._forecast_analyze_worker(
                {"data_id": "data_test_1", "target_column": "金额", "forecast_periods": 3}
            )
        )

        # 模型选择说明
        assert result["method_explanation"]["current"] == "趋势外推"
        assert len(result["method_explanation"]["alternatives"]) == 2

        # 区间规范化：倒置交换、缺失补值
        fvs = result["predictions"]["forecast_values"]
        assert fvs[0]["low"] == 110 and fvs[0]["high"] == 150
        assert fvs[1]["low"] == 135 and fvs[1]["high"] == 135
        for fv in fvs:
            assert fv["low"] <= fv["value"] <= fv["high"]

        # charts 上下界与 labels 对齐（倒置交换）
        assert result["charts"]["upper_bound"] == [None, None, 130]
        assert result["charts"]["lower_bound"] == [None, None, 110]

        # 落库 done
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT status, analysis FROM forecast_records WHERE id=?", ("data_test_1",)
            ).fetchone()
        assert row[0] == "done"
        saved = json.loads(row[1])
        assert saved["predictions"]["forecast_values"][0]["low"] == 110

    def test_worker_missing_record_raises(self, monkeypatch):
        """worker：数据记录不存在 → 404（异常兜底链路）。"""
        import data_forecast

        monkeypatch.setattr(data_forecast, "call_llm", lambda *a, **kw: sample_llm_json())
        monkeypatch.setattr(data_forecast, "log_usage", lambda *a, **kw: None)

        with pytest.raises(Exception) as exc:
            asyncio.run(
                data_forecast._forecast_analyze_worker({"data_id": "no_such", "target_column": ""})
            )
        assert exc.value.status_code == 404
