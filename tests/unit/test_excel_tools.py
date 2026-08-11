"""v15 Excel 增强单测：IQR 异常值检测纯函数 + outliers 端点落库。

覆盖：
- _percentile：线性插值分位数（空/单元素/常规）
- _detect_outliers：TSV/CSV/空格分隔解析、上下界计算、异常行号定位、
  样本不足/常量列/非数值列跳过、无异常返回空
- excel_operate outliers 分支：JSON 结果 + 历史落库
"""

import json
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}

_TSV = """月份\t销售额\t成本
1月\t100\t50
2月\t120\t60
3月\t110\t55
4月\t99999\t70
5月\t130\t9999
6月\t115\t65
7月\t125\t58
8月\t105\t99999
"""


class TestPercentile:
    def test_empty(self):
        from extended_api import _percentile

        assert _percentile([], 0.5) == 0.0

    def test_single(self):
        from extended_api import _percentile

        assert _percentile([5], 0.25) == 5.0

    def test_median_and_quartiles(self):
        from extended_api import _percentile

        nums = [1, 2, 3, 4, 5]
        assert _percentile(nums, 0.5) == 3.0
        assert _percentile(nums, 0.25) == 2.0
        assert _percentile(nums, 0.75) == 4.0

    def test_interpolation(self):
        from extended_api import _percentile

        nums = [1, 2, 3, 4]
        # k = 3 * 0.5 = 1.5 → 2 + (3-2)*0.5 = 2.5
        assert _percentile(nums, 0.5) == 2.5


class TestDetectOutliers:
    def test_tsv_detects_high_and_low(self):
        from extended_api import _detect_outliers

        res = _detect_outliers(_TSV)
        assert res["success"] is True
        assert res["total_rows"] == 8
        assert res["summary"].startswith("共检测 2 个数值列")

        by_name = {c["name"]: c for c in res["columns"]}
        # 销售额：99999 为异常（偏高），其余 100-130 正常
        sales = by_name["销售额"]
        assert sales["count"] == 1
        assert sales["outliers"][0]["row"] == 5  # 表头第1行 + 数据偏移：99999 在第5行
        assert sales["outliers"][0]["value"] == 99999
        assert sales["outliers"][0]["direction"] == "偏高"
        assert sales["lower_bound"] <= 130
        assert sales["upper_bound"] < 99999
        # 成本：9999 和 99999 为异常
        assert by_name["成本"]["count"] == 2

    def test_csv_input(self):
        from extended_api import _detect_outliers

        csv_text = "id,score\n1,10\n2,12\n3,11\n4,500\n5,13\n6,9\n"
        res = _detect_outliers(csv_text)
        assert res["success"] is True
        assert res["columns"][0]["name"] == "score"
        assert res["columns"][0]["count"] == 1
        assert res["columns"][0]["outliers"][0]["value"] == 500

    def test_space_separated(self):
        from extended_api import _detect_outliers

        text = "日期  数值\n1月  10\n2月  12\n3月  11\n4月  300\n5月  13\n"
        res = _detect_outliers(text)
        assert res["success"] is True
        assert res["columns"][0]["count"] == 1

    def test_insufficient_rows(self):
        from extended_api import _detect_outliers

        res = _detect_outliers("a\tb\n1\t2\n")
        assert res["success"] is False
        assert "3 行" in res["message"]

    def test_constant_column_skipped(self):
        from extended_api import _detect_outliers

        text = "a\tb\n1\t5\n2\t5\n3\t5\n4\t5\n5\t5\n"
        res = _detect_outliers(text)
        assert res["success"] is True
        assert res["columns"] == []  # iqr=0 跳过
        assert "0 个异常值" in res["summary"]

    def test_non_numeric_column_skipped(self):
        from extended_api import _detect_outliers

        text = "名称\t值\n甲\t1\n乙\t2\n丙\t3\n丁\t4\n戊\t999\n"
        res = _detect_outliers(text)
        assert res["success"] is True
        assert len(res["columns"]) == 1
        assert res["columns"][0]["name"] == "值"

    def test_all_normal_no_outliers(self):
        from extended_api import _detect_outliers

        text = "v\n1\n2\n3\n4\n5\n6\n"
        res = _detect_outliers(text)
        assert res["success"] is True
        assert res["columns"] == []


class TestOutliersEndpoint:
    def test_endpoint_returns_json_and_records(self, setup_test_db):
        import extended_api
        from extended_api import ExcelRequest

        req = ExcelRequest(operation="outliers", title="异常检测", data={"raw": _TSV})
        resp = extended_api.excel_operate(req, current_user=USER)

        assert resp["ok"] is True
        parsed = json.loads(resp["result"])
        assert parsed["success"] is True
        assert parsed["total_rows"] == 8

        # 历史落库
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT operation, result FROM excel_operations WHERE id = ?", (resp["id"],)
        ).fetchone()
        conn.close()
        assert row["operation"] == "outliers"
        assert json.loads(row["result"])["success"] is True

    def test_endpoint_insufficient_data(self, setup_test_db):
        import extended_api
        from extended_api import ExcelRequest

        req = ExcelRequest(operation="outliers", title="t", data={"raw": "a\n1\n"})
        resp = extended_api.excel_operate(req, current_user=USER)
        assert json.loads(resp["result"])["success"] is False
