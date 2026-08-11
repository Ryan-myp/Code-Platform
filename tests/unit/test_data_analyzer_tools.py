"""v15 数据分析增强单测：三段式结论解析（洞察/异常/建议）。

覆盖：
- parse_conclusion：完整三段解析、编号前缀去除、无标记回退洞察
- 空输出、异常段无内容、标记在文本中间（非行首）兼容
- 端点：analyze 返回 conclusion_sections + overview（拦截 LLM 与沙箱）
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


class TestParseConclusion:
    def test_full_three_sections(self):
        from data_analyzer import parse_conclusion

        output = (
            "[洞察] 1. 华东区销售额居首，占 28%\n"
            "2. 2 月整体环比下滑 12%\n"
            "[异常] 1. 3 月 6 日销量骤降至均值 1/4\n"
            "[建议] 1. 对华南品类补货并加大促销"
        )
        sections = parse_conclusion(output)
        assert len(sections["insights"]) == 2
        assert sections["insights"][0] == "华东区销售额居首，占 28%"
        assert sections["insights"][1] == "2 月整体环比下滑 12%"
        assert sections["anomalies"] == ["3 月 6 日销量骤降至均值 1/4"]
        assert sections["suggestions"] == ["对华南品类补货并加大促销"]

    def test_no_marker_falls_back_to_insights(self):
        from data_analyzer import parse_conclusion

        sections = parse_conclusion("整体平稳增长\n利润率 12%")
        assert sections["insights"] == ["整体平稳增长", "利润率 12%"]
        assert sections["anomalies"] == []
        assert sections["suggestions"] == []

    def test_empty_and_none(self):
        from data_analyzer import parse_conclusion

        assert parse_conclusion("") == {"insights": [], "anomalies": [], "suggestions": []}
        assert parse_conclusion(None) == {"insights": [], "anomalies": [], "suggestions": []}

    def test_marker_in_middle_of_line(self):
        from data_analyzer import parse_conclusion

        # 标记不出现在行首时不做切段（保持容错）
        output = "结论如下 [洞察] 1. 发现一"
        sections = parse_conclusion(output)
        assert sections["insights"] == ["结论如下 [洞察] 1. 发现一"]

    def test_no_anomaly_section(self):
        from data_analyzer import parse_conclusion

        output = "[洞察] 1. 增长 10%\n[建议] 1. 继续投入"
        sections = parse_conclusion(output)
        assert sections["insights"] == ["增长 10%"]
        assert sections["anomalies"] == []
        assert sections["suggestions"] == ["继续投入"]

    def test_cn_numbering_styles(self):
        from data_analyzer import _strip_number

        assert _strip_number("1. 内容") == "内容"
        assert _strip_number("2、内容") == "内容"
        assert _strip_number("3．内容") == "内容"
        assert _strip_number("无编号") == "无编号"


class TestAnalyzeEndpoint:
    def test_returns_sections_and_overview(self, setup_test_db, monkeypatch):
        """analyze 端点：沙箱输出三段式 → 返回 conclusion_sections + overview。"""
        import data_analyzer
        from data_analyzer import data_analyzer_analyze

        async def fake_llm(_system, _user, **_kw):
            return "```python\nimport pandas as pd\ndf = pd.read_csv('data.csv')\nprint('x')\n```"

        monkeypatch.setattr(data_analyzer, "call_llm_async", fake_llm)
        monkeypatch.setattr(
            data_analyzer,
            "run_sandbox_python",
            lambda code, **kw: {
                "output": "[洞察] 1. 销售额 100 万\n[异常] 1. 3 月异常\n[建议] 1. 优化库存",
                "error": "",
                "duration": 0.1,
                "exit_code": 0,
                "files": {},
            },
        )
        monkeypatch.setattr(data_analyzer, "log_usage", lambda *a, **kw: None)

        result = asyncio.run(
            data_analyzer_analyze(
                {"question": "分析销售", "data": "日期,金额\n2026-01-01,100\n2026-01-02,200"},
                current_user=USER,
            )
        )
        assert result["overview"]["columns"] == ["日期", "金额"]
        assert result["overview"]["rows"] == 2
        assert result["conclusion_sections"]["insights"] == ["销售额 100 万"]
        assert result["conclusion_sections"]["anomalies"] == ["3 月异常"]
        assert result["conclusion_sections"]["suggestions"] == ["优化库存"]
