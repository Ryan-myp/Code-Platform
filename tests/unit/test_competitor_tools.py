"""v15 竞品监控增强单测：变化摘要 diff + 监控频率。

覆盖：
- diff_reports：首次分析无基准、列表字段 added/removed、标量字段 modified、无变化
- add_competitor：监控频率落库与返回
- list_competitors：按频率筛选
- analyze_competitors：二次分析产出 changes（monkeypatch LLM）
"""

import json
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


def prev_analysis():
    return {
        "overview": "竞品A 处于行业头部，内容稳定",
        "hot_patterns": ["悬念标题", "场景化开头", "热点借势"],
        "competitive_advantages": ["内容质量高", "更新频率高"],
        "competitive_weaknesses": ["互动运营弱"],
        "recommendations": ["加强评论区运营", "增加直播场次"],
        "publishing_habits": {"frequency": "日更"},
        "engagement_analysis": {"trend": "up"},
    }


def curr_analysis():
    return {
        "overview": "竞品A 处于行业头部，内容稳定，粉丝增速放缓",
        "hot_patterns": ["悬念标题", "场景化开头", "用户共创"],
        "competitive_advantages": ["内容质量高", "更新频率高"],
        "competitive_weaknesses": ["互动运营弱", "选题同质化"],
        "recommendations": ["加强评论区运营", "增加直播场次", "尝试短剧植入"],
        "publishing_habits": {"frequency": "日更"},
        "engagement_analysis": {"trend": "stable"},
    }


class TestDiffReports:
    def test_first_analysis_no_baseline(self):
        from competitor_monitor import diff_reports

        out = diff_reports(None, curr_analysis())
        assert out["total_changed"] == 0
        assert "首次分析" in out["summary"]
        assert out["changed"] == []

    def test_list_field_added_removed(self):
        from competitor_monitor import diff_reports

        out = diff_reports(prev_analysis(), curr_analysis())
        hot = next(c for c in out["changed"] if c["field"] == "hot_patterns")
        assert "用户共创" in hot["added"]
        assert "热点借势" in hot["removed"]

        weak = next(c for c in out["changed"] if c["field"] == "competitive_weaknesses")
        assert "选题同质化" in weak["added"]

        adv = next((c for c in out["changed"] if c["field"] == "competitive_advantages"), None)
        assert adv is None  # 无变化字段不进 changed

    def test_scalar_field_modified(self):
        from competitor_monitor import diff_reports

        out = diff_reports(prev_analysis(), curr_analysis())
        trend = next(c for c in out["changed"] if c["field"] == "engagement_analysis.trend")
        assert trend["modified"] == [{"prev": "up", "curr": "stable"}]

        overview = next(c for c in out["changed"] if c["field"] == "overview")
        assert overview["modified"][0]["curr"].startswith("竞品A")

    def test_no_change(self):
        from competitor_monitor import diff_reports

        out = diff_reports(prev_analysis(), prev_analysis())
        assert out["total_changed"] == 0
        assert "无显著变化" in out["summary"]

    def test_summary_counts(self):
        from competitor_monitor import diff_reports

        out = diff_reports(prev_analysis(), curr_analysis())
        # hot_patterns + weaknesses + recommendations + trend + overview = 5 处
        assert out["total_changed"] == 5
        assert str(out["total_changed"]) in out["summary"]

    def test_empty_inputs(self):
        from competitor_monitor import diff_reports

        assert diff_reports({}, {})["total_changed"] == 0
        assert diff_reports(None, None)["total_changed"] == 0


class TestCompetitorEndpoints:
    @pytest.fixture(autouse=True)
    def _init_competitor_tables(self, setup_test_db):
        """competitors/competitor_reports 表由端点惰性创建，先确保存在。"""
        from common.db import get_db

        from competitor_monitor import _ensure_tables

        conn = get_db()
        _ensure_tables(conn)
        conn.close()

    def test_add_competitor_with_frequency(self, setup_test_db):
        from competitor_monitor import add_competitor
        from competitor_monitor import CompetitorAddRequest

        import asyncio

        req = CompetitorAddRequest(
            name="竞品A", platform="抖音", description="测试", monitor_frequency="daily"
        )
        result = asyncio.run(add_competitor(req, current_user=USER))
        assert result["monitor_frequency"] == "daily"

        from common.db import get_db

        conn = get_db()
        row = conn.execute("SELECT monitor_frequency FROM competitors WHERE id=?", (result["id"],)).fetchone()
        conn.close()
        assert row[0] == "daily"

    def test_add_invalid_frequency_rejected(self):
        from pydantic import ValidationError

        from competitor_monitor import CompetitorAddRequest

        with pytest.raises(ValidationError):
            CompetitorAddRequest(name="竞品B", platform="B站", monitor_frequency="every-minute")

    def test_list_by_frequency(self, setup_test_db):
        import asyncio

        from competitor_monitor import CompetitorAddRequest, add_competitor, list_competitors

        for freq in ("daily", "weekly"):
            asyncio.run(
                add_competitor(
                    CompetitorAddRequest(name=f"竞品{freq}", platform="抖音", monitor_frequency=freq),
                    current_user=USER,
                )
            )
        daily = asyncio.run(list_competitors(frequency="daily", current_user=USER))
        assert len(daily) == 1
        assert daily[0]["monitor_frequency"] == "daily"
        all_rows = asyncio.run(list_competitors(current_user=USER))
        assert len(all_rows) == 2

    def test_analyze_twice_produces_changes(self, setup_test_db, monkeypatch):
        """两次分析：第二次返回 changes（diff 上次报告）。"""
        import asyncio

        from common.db import get_db

        import competitor_monitor
        from competitor_monitor import AnalyzeRequest, add_competitor, analyze_competitors
        from competitor_monitor import CompetitorAddRequest

        id_a = asyncio.run(
            add_competitor(
                CompetitorAddRequest(name="竞品A", platform="抖音", description="头部账号"),
                current_user=USER,
            )
        )["id"]

        def fake_llm(system, user_prompt, **_kw):
            if "雷达" in system or "radar" in system:
                return json.dumps(
                    {"chart_type": "radar", "title": "竞品对比", "option": {"radar": {"indicator": []}, "series": []}},
                    ensure_ascii=False,
                )
            # 第一次返回 prev_analysis 内容，第二次返回 curr_analysis 内容
            if fake_llm.calls == 0:
                fake_llm.calls += 1
                return json.dumps(prev_analysis(), ensure_ascii=False)
            return json.dumps(curr_analysis(), ensure_ascii=False)

        fake_llm.calls = 0
        monkeypatch.setattr(competitor_monitor, "call_llm", fake_llm)
        monkeypatch.setattr(competitor_monitor, "log_usage", lambda *a, **kw: None)

        req = AnalyzeRequest(competitor_ids=[id_a])
        first = analyze_competitors(req, current_user=USER)
        assert first["changes"] is None  # 首次无基准
        assert first["competitors"][0]["monitor_frequency"] == "weekly"

        second = analyze_competitors(req, current_user=USER)
        assert second["changes"] is not None
        assert second["changes"]["total_changed"] > 0
        fields = [c["field"] for c in second["changes"]["changed"]]
        assert "hot_patterns" in fields
        assert "engagement_analysis.trend" in fields

        # 报告已落库
        conn = get_db()
        n = conn.execute("SELECT COUNT(*) FROM competitor_reports").fetchone()[0]
        conn.close()
        assert n == 2
