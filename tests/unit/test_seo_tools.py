"""v15 SEO 分析增强单测：关键词优先级矩阵（分组 + 难度分级 + 执行优先级）。

覆盖：
- build_priority_matrix：相关词/长尾词合并去重、评分规则（relevance/competition/difficulty）
- 优先级分级：P1（高分速赢）/ P2 / P3 边界
- 空输入、非法字段兜底、limit 截断、排序
- keywords 端点：结果包含 priority_matrix（LLM 结果 mock）
"""

import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


def sample_keyword_data():
    return {
        "related_keywords": [
            {"keyword": "AI写作工具", "search_volume": "高", "competition": "低", "relevance": 95},
            {"keyword": "AI写作", "search_volume": "高", "competition": "高", "relevance": 92},
            {"keyword": "写作助手", "search_volume": "中", "competition": "中", "relevance": 82},
            {"keyword": "相关词重复", "search_volume": "低", "competition": "低", "relevance": 60},
        ],
        "long_tail_keywords": [
            {"keyword": "AI写作工具哪个好", "intent": "商业型", "difficulty": "低"},
            {"keyword": "AI写论文怎么用", "intent": "信息型", "difficulty": "高"},
            {"keyword": "相关词重复", "intent": "信息型", "difficulty": "低"},  # 与相关词重复 → 去重
        ],
    }


class TestPriorityMatrix:
    def test_p1_high_relevance_low_competition(self):
        from seo_analyzer import build_priority_matrix

        matrix = build_priority_matrix(sample_keyword_data())
        by_keyword = {m["keyword"]: m for m in matrix}
        assert by_keyword["AI写作工具"]["priority"] == "P1"
        assert by_keyword["AI写作工具"]["score"] == 8  # 相关3 + 竞争3 + 难度缺省2

    def test_p2_mid_relevance_mid_competition(self):
        from seo_analyzer import build_priority_matrix

        matrix = build_priority_matrix(sample_keyword_data())
        by_keyword = {m["keyword"]: m for m in matrix}
        assert by_keyword["写作助手"]["priority"] == "P2"

    def test_p3_low_relevance(self):
        from seo_analyzer import build_priority_matrix

        matrix = build_priority_matrix(sample_keyword_data())
        by_keyword = {m["keyword"]: m for m in matrix}
        assert by_keyword["相关词重复"]["priority"] == "P3"

    def test_merge_dedupe_and_sort(self):
        from seo_analyzer import build_priority_matrix

        matrix = build_priority_matrix(sample_keyword_data())
        keywords = [m["keyword"] for m in matrix]
        assert len(keywords) == len(set(keywords))  # 去重
        # 按 score 降序
        scores = [m["score"] for m in matrix]
        assert scores == sorted(scores, reverse=True)
        # P1 排最前
        assert matrix[0]["priority"] == "P1"

    def test_priority_boundaries(self):
        from seo_analyzer import _priority_level

        assert _priority_level(9) == "P1"
        assert _priority_level(8) == "P1"
        assert _priority_level(7) == "P2"
        assert _priority_level(6) == "P2"
        assert _priority_level(5) == "P3"
        assert _priority_level(3) == "P3"

    def test_empty_and_missing_fields(self):
        from seo_analyzer import build_priority_matrix

        assert build_priority_matrix({}) == []
        assert build_priority_matrix(None) == []
        # 字段缺失/None 兜底不抛异常
        matrix = build_priority_matrix(
            {"related_keywords": [{"keyword": "词", "relevance": None, "competition": None}]}
        )
        assert matrix[0]["priority"] == "P3"
        assert matrix[0]["competition"] == "-"

    def test_limit(self):
        from seo_analyzer import build_priority_matrix

        matrix = build_priority_matrix(sample_keyword_data(), limit=2)
        assert len(matrix) == 2

    def test_action_mapping(self):
        from seo_analyzer import build_priority_matrix

        matrix = build_priority_matrix(sample_keyword_data())
        by_keyword = {m["keyword"]: m for m in matrix}
        assert "优先创作" in by_keyword["AI写作工具"]["action"]
        assert "长期布局" in by_keyword["相关词重复"]["action"]


class TestKeywordsEndpoint:
    def test_result_contains_priority_matrix(self, setup_test_db, monkeypatch):
        """keywords 端点：LLM 返回分组数据后，后端注入优先级矩阵。"""
        import seo_analyzer
        from seo_analyzer import KeywordResearchRequest, research_keywords

        raw_json = (
            '{"related_keywords": [{"keyword": "AI写作", "search_volume": "高", "competition": "低", "relevance": 95}],'
            ' "long_tail_keywords": [{"keyword": "AI写作工具", "intent": "信息型", "difficulty": "低"}],'
            ' "question_keywords": [], "topic_clusters": [], "content_suggestions": "建议"}'
        )
        monkeypatch.setattr(seo_analyzer, "call_llm", lambda *a, **kw: raw_json)
        monkeypatch.setattr(seo_analyzer, "log_usage", lambda *a, **kw: None)

        req = KeywordResearchRequest(seed_keyword="AI写作")
        result = research_keywords(req, current_user=USER)
        assert result["seed_keyword"] == "AI写作"
        assert isinstance(result["priority_matrix"], list)
        assert result["priority_matrix"][0]["keyword"] == "AI写作"
        assert result["priority_matrix"][0]["priority"] == "P1"

    def test_analyze_prompt_20y_expert(self):
        """分析/关键词 prompt 已按 20 年行业专家角色重写。"""
        import seo_analyzer

        assert "20年+" in seo_analyzer.KEYWORD_SYSTEM
        assert "10年+" in seo_analyzer.SEO_ANALYZE_SYSTEM
