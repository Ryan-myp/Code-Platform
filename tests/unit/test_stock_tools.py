"""v15 股票分析增强单测：风险提示指标（波动率/回撤/流动性）+ 端点注入。

覆盖：
- compute_risk_metrics：合成行情数据 → 年化波动率、最大回撤（含发生区间）、流动性
- 等级边界：_volatility_level / _drawdown_level / _liquidity_level
- 空数据兜底：无数据/单点数据不抛异常，warnings 有兜底提示
- get_stock 端点：行情数据返回后注入 risk_metrics
- v21：compute_five_dim_signals 五维交叉验证纯函数 + 专业投研 prompt + 定时报告接口
"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

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


# ══════════════════════════════════════════════════════════════
# v21：五维交叉验证信号（compute_five_dim_signals 纯函数）
# ══════════════════════════════════════════════════════════════


def _five_dim_data(rsi=55.0, volumes=None, latest_ma=(190, 170, 150), bb=(210, 180, 150), hi52=220, lo52=90):
    """构造五维信号样本：30 天缓涨（100→216）+ 默认多头均线 + 布林带 + 52 周区间。"""
    closes = [100 + 4 * i for i in range(30)]
    points = []
    for i, c in enumerate(closes):
        points.append({"date": f"2026-01-{i + 1:02d}", "close": c, "volume": (volumes or [500000] * 30)[i]})
    points[-1].update({
        "ma5": latest_ma[0], "ma20": latest_ma[1], "ma60": latest_ma[2],
        "macd": 2.0, "signal": 1.0,
        "bb_upper": bb[0], "bb_middle": bb[1], "bb_lower": bb[2],
    })
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "data_points": points,
        "indicators": {"rsi": rsi, "macd": 2.0, "ma5": latest_ma[0], "ma20": latest_ma[1], "ma60": latest_ma[2]},
        "52w_high": hi52, "52w_low": lo52,
    }


class TestFiveDimSignals:
    def test_trend_bullish_with_bullish_alignment(self):
        """多头排列 + 价格站上 MA20 + MACD 正 → 趋势看多。"""
        from stock_tools import compute_five_dim_signals

        sig = compute_five_dim_signals(_five_dim_data())
        trend = sig["dimensions"]["trend"]
        assert trend["level"] == "bullish"
        assert any("多头排列" in e for e in trend["evidence"])

    def test_trend_bearish_with_bearish_alignment(self):
        from stock_tools import compute_five_dim_signals

        data = _five_dim_data(latest_ma=(140, 160, 180), bb=(200, 180, 160))
        data["indicators"]["macd"] = -2.0
        data["data_points"][-1]["macd"] = -2.0
        sig = compute_five_dim_signals(data)
        assert sig["dimensions"]["trend"]["level"] == "bearish"
        assert any("空头排列" in e for e in sig["dimensions"]["trend"]["evidence"])

    def test_rsi_overbought_bearish_momentum(self):
        """RSI>=70 → 动量超买看空（回调风险）。"""
        from stock_tools import compute_five_dim_signals

        sig = compute_five_dim_signals(_five_dim_data(rsi=80))
        m = sig["dimensions"]["momentum"]
        assert m["rsi_zone"] == "overbought"
        assert m["level"] == "bearish"

    def test_rsi_oversold_bullish_momentum(self):
        from stock_tools import compute_five_dim_signals

        sig = compute_five_dim_signals(_five_dim_data(rsi=25))
        m = sig["dimensions"]["momentum"]
        assert m["rsi_zone"] == "oversold"
        assert m["level"] == "bullish"

    def test_boll_upper_bearish_volatility(self):
        """价格触及布林上轨 → 强势但短期过热。"""
        from stock_tools import compute_five_dim_signals

        # 最新价 216 >= 上轨 210
        sig = compute_five_dim_signals(_five_dim_data(bb=(210, 180, 150)))
        v = sig["dimensions"]["volatility"]
        assert v["boll_position"] == "upper"
        assert v["level"] == "bearish"

    def test_boll_lower_bullish_volatility(self):
        from stock_tools import compute_five_dim_signals

        # 最新价 216 <= 下轨 220
        sig = compute_five_dim_signals(_five_dim_data(bb=(260, 240, 220)))
        assert sig["dimensions"]["volatility"]["boll_position"] == "lower"
        assert sig["dimensions"]["volatility"]["level"] == "bullish"

    def test_volume_price_confirmed_bullish(self):
        """放量上涨（近5日 ≥1.2x 前20日）→ 量价配合。"""
        from stock_tools import compute_five_dim_signals

        volumes = [100000] * 25 + [300000] * 5
        sig = compute_five_dim_signals(_five_dim_data(volumes=volumes))
        vp = sig["dimensions"]["volume_price"]
        assert vp["pattern"] == "confirmed"
        assert vp["level"] == "bullish"
        assert vp["volume_ratio"] == 3.0

    def test_volume_price_divergence_bearish(self):
        """放量下跌 → 量价背离。"""
        from stock_tools import compute_five_dim_signals

        data = _five_dim_data(volumes=[100000] * 25 + [300000] * 5)
        closes = data["data_points"]
        # 最后 5 天改为下跌：末价 116 < 6 天前 120
        closes[-5]["close"] = 120
        closes[-4]["close"] = 118
        closes[-3]["close"] = 117
        closes[-2]["close"] = 116.5
        closes[-1]["close"] = 116
        sig = compute_five_dim_signals(data)
        vp = sig["dimensions"]["volume_price"]
        assert vp["pattern"] == "divergence"
        assert vp["level"] == "bearish"

    def test_position_high_zone_bearish(self):
        """52 周区间高分位（>=80%）→ 位置风险看空。"""
        from stock_tools import compute_five_dim_signals

        # close=216, hi=220, lo=90 → 分位 96.9%
        sig = compute_five_dim_signals(_five_dim_data())
        pos = sig["dimensions"]["position"]
        assert pos["zone"] == "high"
        assert pos["level"] == "bearish"
        assert pos["pct_52w"] == 96.9

    def test_position_low_zone_bullish(self):
        from stock_tools import compute_five_dim_signals

        # close=216, hi=230, lo=213 → 分位 17.6%
        sig = compute_five_dim_signals(_five_dim_data(hi52=230, lo52=213))
        assert sig["dimensions"]["position"]["zone"] == "low"
        assert sig["dimensions"]["position"]["level"] == "bullish"

    def test_summary_verdict_dissonance(self):
        """默认样本：趋势多 + 波动空 + 位置空 → 信号分歧。"""
        from stock_tools import compute_five_dim_signals

        sig = compute_five_dim_signals(_five_dim_data())
        s = sig["summary"]
        assert s["bullish_dims"] == 1 and s["bearish_dims"] == 2
        assert s["verdict"] == "信号分歧，方向待确认"
        assert s["signal_strength"] == "中"

    def test_summary_verdict_five_bullish(self):
        """五维全看多构造 → 共振看多、强度强。"""
        from stock_tools import compute_five_dim_signals

        data = _five_dim_data(
            rsi=25,  # 超卖 → 动量多
            volumes=[100000] * 25 + [300000] * 5,  # 放量上涨 → 量价多
            bb=(260, 240, 220),  # close 216 <= 下轨 → 波动多
            hi52=230, lo52=213,  # 分位 17.6% → 位置多
        )
        sig = compute_five_dim_signals(data)
        s = sig["summary"]
        assert s["bullish_dims"] == 5 and s["bearish_dims"] == 0
        assert s["verdict"] == "五维共振看多"
        assert s["signal_strength"] == "强"

    def test_empty_data_fallback(self):
        from stock_tools import compute_five_dim_signals

        sig = compute_five_dim_signals({})
        assert sig["dimensions"] == {}
        assert sig["summary"]["verdict"] == "数据不足"


class TestAnalysisPrompt:
    def _prompt(self, analysis_type="comprehensive"):
        from stock_tools import (
            _build_analysis_prompt,
            compute_five_dim_signals,
            compute_risk_metrics,
            compute_support_resistance,
        )

        data = _five_dim_data()
        return _build_analysis_prompt(
            data,
            compute_risk_metrics(data),
            compute_five_dim_signals(data),
            compute_support_resistance(data),
            analysis_type,
        )

    def test_comprehensive_pro_structure(self):
        """v21：专业投研结构——核心观点/五维验证/关键点位/情景推演/风险/策略。"""
        prompt = self._prompt()
        for kw in ["核心观点", "五维交叉验证", "关键点位", "情景推演", "风险提示", "操作策略"]:
            assert kw in prompt, kw
        # 五维信号与关键点位注入
        for kw in ["趋势维度", "动量维度", "波动维度", "量价维度", "位置风险", "支撑位", "压力位", "均线多头排列"]:
            assert kw in prompt, kw
        assert "禁止编造" in prompt

    def test_technical_keeps_lightweight(self):
        prompt = self._prompt("technical")
        assert "技术分析" in prompt
        assert "五维交叉验证" not in prompt


class TestStockReports:
    def _insert(self, user="u1", symbol="AAPL", report="# 每日报告\n\n测试内容"):
        from common.db import get_db

        conn = get_db()
        conn.execute(
            "INSERT INTO stock_reports (user_id, symbol, period, report, created_at) VALUES (?,?,?,?,?)",
            (user, symbol, "3mo", report, "2026-01-01T09:00:00"),
        )
        conn.commit()
        conn.close()

    def test_list_get_delete_own_report(self, setup_test_db):
        from stock_tools import delete_stock_report, get_stock_report, list_stock_reports

        self._insert()
        items = asyncio.run(list_stock_reports(current_user=USER))["items"]
        assert len(items) == 1
        assert items[0]["symbol"] == "AAPL"
        assert items[0]["period"] == "3mo"

        rid = items[0]["id"]
        detail = asyncio.run(get_stock_report(rid, current_user=USER))
        assert "每日报告" in detail["report"]

        res = asyncio.run(delete_stock_report(rid, current_user=USER))
        assert res["ok"] is True
        assert asyncio.run(list_stock_reports(current_user=USER))["items"] == []

    def test_get_other_user_report_404(self, setup_test_db):
        from stock_tools import get_stock_report, list_stock_reports

        self._insert()
        rid = asyncio.run(list_stock_reports(current_user=USER))["items"][0]["id"]
        other = {"user_id": "u2", "username": "b", "role": "user"}
        with pytest.raises(HTTPException) as ei:
            asyncio.run(get_stock_report(rid, current_user=other))
        assert ei.value.status_code == 404

    def test_delete_other_user_report_404(self, setup_test_db):
        from stock_tools import delete_stock_report, list_stock_reports

        self._insert()
        rid = asyncio.run(list_stock_reports(current_user=USER))["items"][0]["id"]
        other = {"user_id": "u2", "username": "b", "role": "user"}
        with pytest.raises(HTTPException) as ei:
            asyncio.run(delete_stock_report(rid, current_user=other))
        assert ei.value.status_code == 404
