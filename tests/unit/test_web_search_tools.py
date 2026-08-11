"""v15 Web 搜索增强单测：时间筛选（近24h/7d/30d）+ 来源域过滤。

覆盖：
- _extract_date：绝对日期/中文日期/英文相对时间/中文相对时间/裸年份/无日期
- _filter_results_by_time：过期剔除、无日期保留、未来日期保留、空 time_range 原样
- _filter_results_by_domain：白名单精确/子域匹配、不匹配剔除、空白名单原样
- Prompt 时效约束注入：SEARCH_SUMMARY_SYSTEM 含 {time_constraint} 占位且被替换
- WebSearchRequest 参数校验：非法 time_range 拒绝、domain_filter 上限
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}

NOW = datetime(2025, 6, 1, 12, 0, 0)


@pytest.fixture(autouse=True)
def _init_web_search_tables(setup_test_db):
    """在临时库中重建 search_history 表（init_db 仅在首次 import 时执行一次）。"""
    import web_search

    web_search.init_db()


def sample_results():
    return [
        {"title": "最新发布", "snippet": "2025-05-30 更新内容", "url": "https://a.example.com/x", "source": "t"},
        {"title": "旧闻", "snippet": "发布于 2024-01-15", "url": "https://b.example.org/y", "source": "t"},
        {"title": "无日期", "snippet": "这是一篇没有时间信息的文章", "url": "https://c.example.net/z", "source": "t"},
    ]


class TestExtractDate:
    def test_absolute_date(self):
        from web_search import _extract_date

        assert _extract_date("2025-05-30", NOW) == datetime(2025, 5, 30)
        assert _extract_date("2025/5/3", NOW) == datetime(2025, 5, 3)
        assert _extract_date("2025年5月30日", NOW) == datetime(2025, 5, 30)

    def test_relative_time(self):
        from web_search import _extract_date

        assert _extract_date("3 days ago", NOW) == NOW - timedelta(days=3)
        assert _extract_date("5小时前", NOW) == NOW - timedelta(hours=5)
        assert _extract_date("2 weeks ago", NOW) == NOW - timedelta(weeks=2)

    def test_bare_year_and_none(self):
        from web_search import _extract_date

        assert _extract_date("2024 年度报告", NOW) == datetime(2024, 12, 31)
        assert _extract_date("无任何时间信息", NOW) is None


class TestFilterResultsByTime:
    def test_expired_removed_unknown_kept(self):
        from web_search import _filter_results_by_time

        out = _filter_results_by_time(sample_results(), "7d", now=NOW)
        titles = [r["title"] for r in out]
        assert "旧闻" not in titles  # 2024-01-15 超 7 天剔除
        assert "最新发布" in titles  # 2025-05-30 在 7 天内
        assert "无日期" in titles  # 无日期信息保留（宁多勿少）

    def test_future_date_kept(self):
        from web_search import _filter_results_by_time

        out = _filter_results_by_time([{"title": "t", "snippet": "2026-01-01", "url": "u"}], "24h", now=NOW)
        assert len(out) == 1

    def test_empty_range_returns_as_is(self):
        from web_search import _filter_results_by_time

        assert _filter_results_by_time(sample_results(), "", now=NOW) == sample_results()
        assert _filter_results_by_time([], "7d", now=NOW) == []

    def test_24h_stricter(self):
        from web_search import _filter_results_by_time

        # 3 天前的在 7d 保留、24h 剔除
        seven = _filter_results_by_time(
            [{"title": "t", "snippet": "3 days ago", "url": "u"}], "7d", now=NOW
        )
        assert len(seven) == 1
        day = _filter_results_by_time(
            [{"title": "t", "snippet": "3 days ago", "url": "u"}], "24h", now=NOW
        )
        assert day == []


class TestFilterResultsByDomain:
    def test_exact_and_subdomain_match(self):
        from web_search import _filter_results_by_domain

        out = _filter_results_by_domain(sample_results(), ["example.com", "example.net"])
        urls = [r["url"] for r in out]
        assert "https://a.example.com/x" in urls  # 子域匹配 example.com
        assert "https://c.example.net/z" in urls  # 精确匹配 example.net
        assert "https://b.example.org/y" not in urls

    def test_case_and_whitespace_insensitive(self):
        from web_search import _filter_results_by_domain

        out = _filter_results_by_domain(
            [{"title": "t", "url": "https://En.Example.Org/x", "snippet": "s"}], ["  example.org "]
        )
        assert len(out) == 1

    def test_empty_domains_no_filter(self):
        from web_search import _filter_results_by_domain

        assert _filter_results_by_domain(sample_results(), []) == sample_results()
        assert _filter_results_by_domain(sample_results(), ["  "]) == sample_results()
        assert _filter_results_by_domain([], ["example.com"]) == []

    def test_no_match_returns_empty(self):
        from web_search import _filter_results_by_domain

        out = _filter_results_by_domain(sample_results(), ["github.com"])
        assert out == []


class TestPromptTimeConstraint:
    def test_placeholder_present(self):
        import web_search

        assert "{time_constraint}" in web_search.SEARCH_SUMMARY_SYSTEM

    def test_constraint_injected(self):
        from web_search import SEARCH_SUMMARY_SYSTEM

        prompt = SEARCH_SUMMARY_SYSTEM.replace("{search_results}", "[来源1] x\n").replace(
            "{time_constraint}", "仅优先采用近24小时内的信息"
        )
        assert "仅优先采用近24小时内的信息" in prompt
        assert "{time_constraint}" not in prompt
        assert "[来源1] x" in prompt


class TestWebSearchRequest:
    def test_valid_time_range_accepted(self):
        from web_search import WebSearchRequest

        req = WebSearchRequest(query="q", time_range="7d", domain_filter="wikipedia.org")
        assert req.time_range == "7d"
        assert req.domain_filter == "wikipedia.org"

    def test_invalid_time_range_rejected(self):
        from pydantic import ValidationError

        from web_search import WebSearchRequest

        with pytest.raises(ValidationError):
            WebSearchRequest(query="q", time_range="1y")

    def test_domain_filter_max_length(self):
        from pydantic import ValidationError

        from web_search import WebSearchRequest

        with pytest.raises(ValidationError):
            WebSearchRequest(query="q", domain_filter="a" * 501)


class TestWorkerIntegration:
    def test_worker_applies_filters(self, setup_test_db, monkeypatch):
        """worker 集成：过滤后结果进 LLM 上下文 + 返回结果携带筛选字段（拦截网络与 LLM）。"""
        from web_search import _web_search_worker

        monkeypatch.setattr(
            "web_search._search_ddg",
            lambda q, n: [
                {"title": "匹配源", "snippet": "2 days ago 更新", "url": "https://news.example.com/a", "source": "ddg"},
                {"title": "过期源", "snippet": "2 months ago 发布", "url": "https://news.other.org/b", "source": "ddg"},
            ],
        )
        monkeypatch.setattr("web_search._search_fallback", lambda q, n: [])
        captured = {}

        async def fake_llm(system, user, **_kw):
            captured["system"] = system
            return "摘要内容"

        monkeypatch.setattr("web_search.call_llm_async", fake_llm)
        monkeypatch.setattr("web_search.log_usage", lambda *a, **kw: None)

        result = asyncio.run(
            _web_search_worker(
                {"query": "测试", "num_results": 5, "time_range": "7d", "domain_filter": "example.com"},
                progress=lambda p, s: None,
            )
        )
        assert result["time_range"] == "7d"
        assert result["domain_filter"] == "example.com"
        # 来源只剩「匹配域 + 未过期」的一条
        assert len(result["sources"]) == 1
        assert "example.com" in result["sources"][0]["url"]
        # LLM 上下文只含过滤后结果，提示词已注入时效约束
        assert "仅优先采用近7天内的信息" in captured["system"]
        assert "过期源" not in captured["system"]
