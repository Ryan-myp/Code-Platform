"""v15 股票分析增强单测：风险提示指标（波动率/回撤/流动性）+ 端点注入。

覆盖：
- compute_risk_metrics：合成行情数据 → 年化波动率、最大回撤（含发生区间）、流动性
- 等级边界：_volatility_level / _drawdown_level / _liquidity_level
- 空数据兜底：无数据/单点数据不抛异常，warnings 有兜底提示
- get_stock 端点：行情数据返回后注入 risk_metrics
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


def make_series(closes, volumes=None, start_date="2026-01-01"):
    """构造 data_points：按收盘价数组 + 等长成交量（默认 50 万）。"""
    dates = []
    for i in range(len(closes)):
        y, m, d = 2026, 1, 1 + i
        dates.append(f"{y}-{m:02d}-{d:02d}")
    return [
        {"date": dates[i], "close": c, "volume": (volumes or [500000] * len(closes))[i]}
        for i, c in enumerate(closes)
    ]


class TestRiskMetrics:
    def test_crash_series_high_drawdown(self):
        """前 20 天缓涨、第 21 天 -30% 暴跌后回升 → 回撤 ≈30%，综合风险高。"""
        from stock_tools import compute_risk_metrics

        closes = [100 * (1 + 0.005 * i) for i in range(21)]
        closes[20] = closes[19] * 0.7  # 暴跌 30%
        closes += [closes[20] * (1 + 0.01 * i) for i in range(1, 6)]  # 缓慢回升
        data = {"data_points": make_series(closes)}

        rm = compute_risk_metrics(data)
        assert rm["volatility_pct"] is not None and rm["volatility_pct"] > 0
        assert 25 <= rm["max_drawdown_pct"] <= 31
        assert rm["drawdown_trough_date"] == "2026-01-21"
        assert rm["risk_level"] in ("中", "高")
        assert any("回撤" in w for w in rm["warnings"])

    def test_stable_series_low_risk(self):
        """每日 +0.1% 平稳上涨 → 低波动、无回撤、风险等级低。"""
        from stock_tools import compute_risk_metrics

        closes = [100 * (1 + 0.001 * i) for i in range(40)]
        rm = compute_risk_metrics({"data_points": make_series(closes, volumes=[2000000] * 40)})
        assert rm["volatility_level"] == "低"
        assert rm["max_drawdown_pct"] < 1
        assert rm["risk_level"] == "低"
        assert rm["liquidity_level"] == "活跃"

    def test_low_liquidity_warning(self):
        """日均成交量 5 万 → 流动性低迷，提示滑点成本。"""
        from stock_tools import compute_risk_metrics

        closes = [100 + i for i in range(30)]
        rm = compute_risk_metrics({"data_points": make_series(closes, volumes=[50000] * 30)})
        assert rm["avg_volume"] == 50000
        assert rm["liquidity_level"] == "低迷"
        assert any("滑点" in w for w in rm["warnings"])

    def test_empty_and_single_point(self):
        from stock_tools import compute_risk_metrics

        assert compute_risk_metrics(None)["risk_level"] == "低"
        empty = compute_risk_metrics({})
        assert empty["volatility_pct"] is None
        assert empty["max_drawdown_pct"] is None
        assert len(empty["warnings"]) >= 1

        single = compute_risk_metrics({"data_points": [{"date": "2026-01-01", "close": 100, "volume": 100}]})
        assert single["volatility_pct"] is None  # 单点无法计算波动率
        assert single["max_drawdown_pct"] == 0

    def test_none_points_skipped(self):
        """close 缺失的点跳过，不抛异常。"""
        from stock_tools import compute_risk_metrics

        points = [
            {"date": "2026-01-01", "close": 100, "volume": 100},
            {"date": "2026-01-02", "close": 110, "volume": 150},
            {"date": "2026-01-03", "close": 121, "volume": 180},
            {"date": "2026-01-04", "close": None, "volume": None},
            {"date": "2026-01-05", "close": 130, "volume": 200},
        ]
        rm = compute_risk_metrics({"data_points": points})
        assert rm["volatility_pct"] is not None  # 前 3 点连续可算波动率
        assert rm["avg_volume"] == 158  # (100+150+180+200)/4


class TestLevelBoundaries:
    def test_volatility_level(self):
        from stock_tools import _volatility_level

        assert _volatility_level(None) == "低"
        assert _volatility_level(10) == "低"
        assert _volatility_level(19.9) == "低"
        assert _volatility_level(20) == "中"
        assert _volatility_level(39.9) == "中"
        assert _volatility_level(40) == "高"
        assert _volatility_level(55) == "高"

    def test_drawdown_level(self):
        from stock_tools import _drawdown_level

        assert _drawdown_level(None) == "低"
        assert _drawdown_level(9.9) == "低"
        assert _drawdown_level(10) == "中"
        assert _drawdown_level(19.9) == "中"
        assert _drawdown_level(20) == "高"

    def test_liquidity_level(self):
        from stock_tools import _liquidity_level

        assert _liquidity_level(None) == "一般"
        assert _liquidity_level(99999) == "低迷"
        assert _liquidity_level(100000) == "一般"
        assert _liquidity_level(999999) == "一般"
        assert _liquidity_level(1000000) == "活跃"


class TestGetStockEndpoint:
    def test_endpoint_injects_risk_metrics(self, setup_test_db, monkeypatch):
        """get_stock 端点：行情返回后注入 risk_metrics（无需真实 yfinance）。"""
        import stock_tools

        fake_data = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "current_price": 150.0,
            "previous_close": 148.0,
            "indicators": {"rsi": 55.0, "macd": 1.2, "ma5": 148.0, "ma20": 145.0, "ma60": 140.0},
            "data_points": make_series([100 + i for i in range(30)], volumes=[3000000] * 30),
        }

        async def fake_get(symbol, period="3mo"):
            return fake_data

        monkeypatch.setattr(stock_tools, "get_stock_data", fake_get)

        result = asyncio.run(stock_tools.get_stock("AAPL", "3mo", current_user=USER))
        assert result["risk_metrics"]["risk_level"] == "低"
        assert result["risk_metrics"]["avg_volume"] == 3000000
        assert result["trend_analysis"]  # 原有趋势分析不回归
