#!/usr/bin/env python3
"""股票分析工具 - 行情获取、趋势分析、模拟交易"""

import statistics
import time
import uuid
from datetime import datetime

import pandas as pd
import yfinance as yf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm_async

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════════


class StockSearchRequest(BaseModel):
    symbol: str


class StockAnalysisRequest(BaseModel):
    symbol: str
    analysis_type: str = "comprehensive"  # technical, fundamental, comprehensive
    period: str = "3mo"  # 1mo, 3mo, 6mo, 1y, 2y


class TradeRequest(BaseModel):
    symbol: str
    action: str  # buy, sell
    quantity: int
    price: float | None = None  # 如果不指定则用市价


# ══════════════════════════════════════════════════════════════
# 股票数据获取
# ══════════════════════════════════════════════════════════════

# 行情数据内存缓存（15 分钟 TTL，降低上游请求频率）
_STOCK_CACHE: dict[str, tuple] = {}
_STOCK_CACHE_TTL = 900


async def get_stock_data(symbol: str, period: str = "3mo") -> dict:
    """获取股票历史数据（带 15 分钟内存缓存；上游不可用时降级为 503 友好提示）。"""
    cache_key = f"{symbol.upper()}:{period}"
    now = time.time()
    hit = _STOCK_CACHE.get(cache_key)
    if hit and now - hit[0] < _STOCK_CACHE_TTL:
        return hit[1]
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)

        if hist.empty:
            # 尝试提供可能的替代建议
            suggestions = {
                "GOOGLE": "GOOGL 或 GOOG",
                "APPLE": "AAPL",
                "AMAZON": "AMZN",
                "MICROSOFT": "MSFT",
                "FACEBOOK": "META",
                "TESLA": "TSLA",
                "NETFLIX": "NFLX",
                "ALIBABA": "BABA",
                "TENCENT": "0700.HK",
                "BYD": "1211.HK",
                "PINGDUODUO": "PDD",
            }
            hint = suggestions.get(symbol.upper(), "")
            msg = f"找不到股票数据: {symbol}"
            if hint:
                msg += f"，请尝试使用正确的代码：{hint}"
            else:
                msg += "，请检查股票代码是否正确（如：AAPL, GOOGL, MSFT, TSLA）"
            raise HTTPException(404, msg)

        # 获取基本信息
        info = ticker.info

        # 计算技术指标
        df = hist.copy()
        df["MA5"] = df["Close"].rolling(window=5).mean()
        df["MA20"] = df["Close"].rolling(window=20).mean()
        df["MA60"] = df["Close"].rolling(window=60).mean()

        # RSI
        delta = df["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["RSI"] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = df["Close"].ewm(span=12, adjust=False).mean()
        exp2 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = exp1 - exp2
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

        # 布林带
        df["BB_middle"] = df["Close"].rolling(window=20).mean()
        df["BB_upper"] = df["BB_middle"] + 2 * df["Close"].rolling(window=20).std()
        df["BB_lower"] = df["BB_middle"] - 2 * df["Close"].rolling(window=20).std()

        # 转换为 JSON 格式
        data_points = []
        for idx, row in df.iterrows():
            data_points.append(
                {
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 2),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2),
                    "volume": int(row["Volume"]),
                    "ma5": round(float(row["MA5"]), 2) if pd.notna(row["MA5"]) else None,
                    "ma20": round(float(row["MA20"]), 2) if pd.notna(row["MA20"]) else None,
                    "ma60": round(float(row["MA60"]), 2) if pd.notna(row["MA60"]) else None,
                    "rsi": round(float(row["RSI"]), 2) if pd.notna(row["RSI"]) else None,
                    "macd": round(float(row["MACD"]), 4) if pd.notna(row["MACD"]) else None,
                    "signal": round(float(row["Signal"]), 4) if pd.notna(row["Signal"]) else None,
                }
            )

        # 最新数据
        latest = data_points[-1] if data_points else {}

        result = {
            "symbol": symbol.upper(),
            "name": info.get("longName", info.get("shortName", symbol)),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "current_price": latest.get("close", 0),
            "previous_close": info.get("previousClose", 0),
            "open": latest.get("open", 0),
            "day_high": latest.get("high", 0),
            "day_low": latest.get("low", 0),
            "volume": latest.get("volume", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "eps": info.get("trailingEps", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "52w_high": info.get("fiftyTwoWeekHigh", 0),
            "52w_low": info.get("fiftyTwoWeekLow", 0),
            "data_points": data_points,
            "indicators": {
                "rsi": latest.get("rsi"),
                "macd": latest.get("macd"),
                "ma5": latest.get("ma5"),
                "ma20": latest.get("ma20"),
                "ma60": latest.get("ma60"),
            },
        }
        _STOCK_CACHE[cache_key] = (time.time(), result)
        return result
    except HTTPException:
        raise  # 不要吞掉 HTTPException
    except Exception as e:
        raise HTTPException(503, f"行情数据服务暂时不可用（网络或上游限制），请稍后重试。详情: {str(e)[:150]}") from e


# ── 风险指标计算（确定性纯函数，可单测）──


def _volatility_level(vol_pct: float | None) -> str:
    """年化波动率等级：<20% 低 / 20-40% 中 / >40% 高。"""
    if vol_pct is None:
        return "低"
    if vol_pct >= 40:
        return "高"
    if vol_pct >= 20:
        return "中"
    return "低"


def _drawdown_level(dd_pct: float | None) -> str:
    """最大回撤等级：<10% 低 / 10-20% 中 / >20% 高。"""
    if dd_pct is None:
        return "低"
    if dd_pct >= 20:
        return "高"
    if dd_pct >= 10:
        return "中"
    return "低"


def _liquidity_level(avg_volume: float | None) -> str:
    """流动性等级：日均成交 ≥1M 活跃 / ≥100K 一般 / <100K 低迷。"""
    if avg_volume is None:
        return "一般"
    if avg_volume >= 1_000_000:
        return "活跃"
    if avg_volume >= 100_000:
        return "一般"
    return "低迷"


def compute_risk_metrics(data: dict | None) -> dict:
    """计算风险提示指标：年化波动率 / 最大回撤 / 流动性 + 综合风险等级。

    纯函数（输入 get_stock_data 的输出），确定性可单测：
    - volatility_pct：日收益率标准差年化（×√252）
    - max_drawdown_pct：区间内从峰值到谷底的最大回撤（含发生区间）
    - avg_volume：日均成交量 + 流动性等级
    - risk_level：取波动率与回撤中更高者（保守原则）
    - warnings：按阈值给出可读风险提示
    """
    points = (data or {}).get("data_points") or []
    closes = [p.get("close") for p in points]
    volumes = [p.get("volume") for p in points]
    dates = [p.get("date", "") for p in points]

    # 年化波动率（日收益率 → ×√252）
    volatility_pct = None
    returns = []
    prev = None
    for c in closes:
        if c is None:
            prev = None
            continue
        if prev is not None and prev > 0:
            returns.append(c / prev - 1)
        prev = c
    if len(returns) >= 2:
        volatility_pct = round(statistics.stdev(returns) * (252**0.5) * 100, 2)

    # 最大回撤（含峰值/谷底日期）
    max_drawdown_pct = None
    peak_date = ""
    trough_date = ""
    running_max = None
    for i, c in enumerate(closes):
        if c is None:
            continue
        if running_max is None or c > running_max:
            running_max = c
            peak_date = dates[i] if i < len(dates) else ""
        if running_max and running_max > 0:
            dd = (c - running_max) / running_max * 100
            if max_drawdown_pct is None or dd < max_drawdown_pct:
                max_drawdown_pct = round(dd, 2)
                trough_date = dates[i] if i < len(dates) else ""
    if max_drawdown_pct is not None:
        max_drawdown_pct = abs(max_drawdown_pct)

    # 流动性（日均成交量）
    valid_volumes = [v for v in volumes if v is not None]
    avg_volume = round(sum(valid_volumes) / len(valid_volumes)) if valid_volumes else None

    vol_level = _volatility_level(volatility_pct)
    dd_level = _drawdown_level(max_drawdown_pct)
    liq_level = _liquidity_level(avg_volume)
    risk_level = (
        "高"
        if "高" in (vol_level, dd_level)
        else ("中" if "中" in (vol_level, dd_level) else "低")
    )

    warnings = []
    if volatility_pct is not None and vol_level == "高":
        warnings.append(f"年化波动率 {volatility_pct}% 属高波动标的，价格短期波动剧烈")
    elif volatility_pct is not None and vol_level == "中":
        warnings.append(f"年化波动率 {volatility_pct}% 处于中等水平，注意仓位控制")
    if max_drawdown_pct is not None and dd_level == "高":
        warnings.append(
            f"区间最大回撤 {max_drawdown_pct}%（{peak_date} → {trough_date}），注意止损纪律"
        )
    elif max_drawdown_pct is not None and dd_level == "中":
        warnings.append(f"区间最大回撤 {max_drawdown_pct}%，回撤风险需关注")
    if liq_level == "低迷":
        warnings.append("日均成交量偏低，注意买卖价差与滑点成本")
    if not warnings:
        warnings.append("未发现显著风险信号，仍请关注市场系统性风险")

    return {
        "volatility_pct": volatility_pct,
        "volatility_level": vol_level,
        "max_drawdown_pct": max_drawdown_pct,
        "drawdown_peak_date": peak_date,
        "drawdown_trough_date": trough_date,
        "avg_volume": avg_volume,
        "liquidity_level": liq_level,
        "risk_level": risk_level,
        "warnings": warnings,
    }


def analyze_stock_trend(data: dict) -> str:
    """基于技术分析给出趋势判断"""
    indicators = data.get("indicators", {})
    rsi = indicators.get("rsi")
    macd = indicators.get("macd")
    ma5 = indicators.get("ma5")
    ma20 = indicators.get("ma20")
    ma60 = indicators.get("ma60")

    signals = []

    # RSI 分析
    if rsi:
        if rsi > 70:
            signals.append("RSI 超买区域，可能回调")
        elif rsi < 30:
            signals.append("RSI 超卖区域，可能反弹")
        else:
            signals.append("RSI 处于正常区间")

    # 均线分析
    if ma5 and ma20:
        if ma5 > ma20:
            signals.append("短期均线在长期均线上方，短期趋势向上")
        else:
            signals.append("短期均线在长期均线下方，短期趋势向下")

    if ma20 and ma60:
        if ma20 > ma60:
            signals.append("中期趋势向上")
        else:
            signals.append("中期趋势向下")

    # MACD 分析
    if macd:
        if macd > 0:
            signals.append("MACD 正值，多头力量较强")
        else:
            signals.append("MACD 负值，空头力量较强")

    return "\n".join(signals)


# ── 五维交叉验证信号（v21：参考开源技术分析 SKILL「规则计算在前，模型解读在后」）──


_LEVEL_LABELS = {"bullish": "看多", "bearish": "看空", "neutral": "中性"}


def compute_support_resistance(data: dict | None) -> dict:
    """程序化支撑/压力位（规则计算在前，避免 LLM 臆造点位）。

    - S1：近 20 日最低点；S2：近 60 日最低点（数据不足时取 MA60）
    - R1：近 20 日最高点；R2：52 周最高（缺失时取近 60 日最高点）
    纯函数，确定性可单测。
    """
    points = (data or {}).get("data_points") or []
    if not points:
        return {"support": [], "resistance": []}
    close = points[-1].get("close")
    lows20 = [p.get("low") for p in points[-20:] if p.get("low") is not None]
    highs20 = [p.get("high") for p in points[-20:] if p.get("high") is not None]
    lows60 = [p.get("low") for p in points[-60:] if p.get("low") is not None]
    highs60 = [p.get("high") for p in points[-60:] if p.get("high") is not None]
    ma60 = points[-1].get("ma60")
    hi52 = (data or {}).get("52w_high")

    support = []
    if lows20:
        support.append({"level": round(min(lows20), 2), "tag": "S1（近20日低点）"})
    if len(lows60) > 20:
        support.append({"level": round(min(lows60), 2), "tag": "S2（近60日低点）"})
    elif ma60 and close and ma60 < close:
        support.append({"level": round(ma60, 2), "tag": "S2（MA60）"})

    resistance = []
    if highs20:
        resistance.append({"level": round(max(highs20), 2), "tag": "R1（近20日高点）"})
    if hi52:
        resistance.append({"level": round(hi52, 2), "tag": "R2（52周高点）"})
    elif len(highs60) > 20:
        resistance.append({"level": round(max(highs60), 2), "tag": "R2（近60日高点）"})
    return {"support": support, "resistance": resistance}


def compute_five_dim_signals(data: dict | None) -> dict:
    """五维交叉验证信号（v21，参考开源技术分析 SKILL）。

    五个维度：趋势 / 动量 / 波动 / 量价 / 位置风险，每维输出
    level（bullish/bearish/neutral）+ label + evidence 证据列表；
    summary 汇总共振情况（看多/看空维度数、信号强度、总判定）。
    纯函数（输入 get_stock_data 输出），确定性可单测。
    """
    points = (data or {}).get("data_points") or []
    ind = (data or {}).get("indicators") or {}
    empty = {
        "dimensions": {},
        "summary": {"bullish_dims": 0, "bearish_dims": 0, "verdict": "数据不足", "signal_strength": "弱"},
    }
    if not points:
        return empty
    latest = points[-1]
    close = latest.get("close")
    dims: dict = {}

    # ── 趋势维度：均线排列 + 价格 vs MA20 + MACD 方向 ──
    ma5, ma20, ma60 = latest.get("ma5"), latest.get("ma20"), latest.get("ma60")
    macd = latest.get("macd")
    ev, pos, neg = [], 0, 0
    if None not in (ma5, ma20, ma60):
        if ma5 > ma20 > ma60:
            ev.append("均线多头排列（MA5>MA20>MA60）")
            pos += 1
        elif ma5 < ma20 < ma60:
            ev.append("均线空头排列（MA5<MA20<MA60）")
            neg += 1
        else:
            ev.append("均线交织，方向不明")
    if close and ma20:
        if close > ma20:
            ev.append("价格站上 MA20")
            pos += 1
        else:
            ev.append("价格跌破 MA20")
            neg += 1
    if macd is not None:
        if macd > 0:
            ev.append("MACD 为正（多头动能）")
            pos += 1
        else:
            ev.append("MACD 为负（空头动能）")
            neg += 1
    level = "bullish" if pos >= 2 else ("bearish" if neg >= 2 else "neutral")
    dims["trend"] = {"level": level, "label": _LEVEL_LABELS[level], "evidence": ev}

    # ── 动量维度：RSI 分区 + MACD 金叉/死叉 ──
    rsi = ind.get("rsi")
    ev = []
    rsi_zone = "unknown"
    if rsi is not None:
        if rsi >= 70:
            rsi_zone = "overbought"
            ev.append(f"RSI={rsi:.1f} 超买过热（回调风险）")
        elif rsi <= 30:
            rsi_zone = "oversold"
            ev.append(f"RSI={rsi:.1f} 超卖弱势（修复可能）")
        else:
            rsi_zone = "neutral"
            ev.append(f"RSI={rsi:.1f} 中性区间")
    cross = "none"
    if len(points) >= 2:
        p2 = points[-2]
        m1, s1 = latest.get("macd"), latest.get("signal")
        m0, s0 = p2.get("macd"), p2.get("signal")
        if None not in (m1, s1, m0, s0):
            if m0 <= s0 and m1 > s1:
                cross = "golden"
                ev.append("MACD 金叉（DIF 上穿 DEA）")
            elif m0 >= s0 and m1 < s1:
                cross = "death"
                ev.append("MACD 死叉（DIF 下穿 DEA）")
    if cross == "golden" or rsi_zone == "oversold":
        level = "bullish"
    elif cross == "death" or rsi_zone == "overbought":
        level = "bearish"
    else:
        level = "neutral"
    dims["momentum"] = {
        "level": level,
        "label": _LEVEL_LABELS[level],
        "evidence": ev,
        "rsi_zone": rsi_zone,
        "macd_cross": cross,
    }

    # ── 波动维度：布林带位置 + 波动率等级 ──
    bb_upper, bb_lower = latest.get("bb_upper"), latest.get("bb_lower")
    rm = compute_risk_metrics(data)
    vol_level = rm.get("volatility_level")
    ev = []
    boll_pos = "middle"
    if close and bb_upper is not None and bb_lower is not None:
        if close >= bb_upper:
            boll_pos = "upper"
            ev.append("价格触及布林上轨（强势但短期过热）")
        elif close <= bb_lower:
            boll_pos = "lower"
            ev.append("价格触及布林下轨（超跌，支撑区）")
        else:
            ev.append("价格位于布林通道中轨附近")
    if vol_level:
        ev.append(f"年化波动率等级：{vol_level}")
    level = "bullish" if boll_pos == "lower" else ("bearish" if boll_pos == "upper" else "neutral")
    dims["volatility"] = {
        "level": level,
        "label": _LEVEL_LABELS[level],
        "evidence": ev,
        "boll_position": boll_pos,
        "volatility_level": vol_level,
    }

    # ── 量价维度：近5日 vs 前20日均量 + 价格方向配合 ──
    volumes = [p.get("volume") or 0 for p in points]
    recent5 = volumes[-5:]
    prev20 = volumes[-25:-5]
    avg5 = round(sum(recent5) / len(recent5)) if recent5 else 0
    avg20 = round(sum(prev20) / len(prev20)) if prev20 else 0
    vol_ratio = round(avg5 / avg20, 2) if avg20 else None
    ev = []
    pattern = "neutral"
    if len(points) >= 6 and close and points[-6].get("close"):
        price_up = close >= points[-6]["close"]
        if vol_ratio is not None:
            ev.append(f"近5日均量 {avg5:,} vs 前20日均量 {avg20:,}（{vol_ratio}x）")
            if price_up and vol_ratio >= 1.2:
                pattern = "confirmed"
                ev.append("放量上涨，量价配合（突破可信度高）")
            elif price_up and vol_ratio < 0.8:
                pattern = "weak"
                ev.append("缩量上涨，上攻动能不足")
            elif not price_up and vol_ratio >= 1.2:
                pattern = "divergence"
                ev.append("放量下跌，抛压明显（量价背离）")
            elif not price_up and vol_ratio < 0.8:
                pattern = "shakeout"
                ev.append("缩量回调，抛压有限（健康整理）")
        else:
            ev.append("量能数据不足")
    level = {
        "confirmed": "bullish",
        "shakeout": "bullish",
        "weak": "bearish",
        "divergence": "bearish",
    }.get(pattern, "neutral")
    dims["volume_price"] = {
        "level": level,
        "label": _LEVEL_LABELS[level],
        "evidence": ev,
        "volume_ratio": vol_ratio,
        "pattern": pattern,
    }

    # ── 位置风险维度：52 周区间百分位 ──
    hi52, lo52 = (data or {}).get("52w_high"), (data or {}).get("52w_low")
    pct_52w = None
    zone = "unknown"
    ev = []
    if close and hi52 and lo52 and hi52 > lo52:
        pct_52w = round((close - lo52) / (hi52 - lo52) * 100, 1)
        if pct_52w >= 80:
            zone = "high"
            ev.append(f"价格处于 52 周区间 {pct_52w}% 分位（历史高位区，追涨风险）")
        elif pct_52w <= 20:
            zone = "low"
            ev.append(f"价格处于 52 周区间 {pct_52w}% 分位（历史低位区，下行空间有限）")
        else:
            zone = "middle"
            ev.append(f"价格处于 52 周区间 {pct_52w}% 分位")
    level = {"high": "bearish", "low": "bullish"}.get(zone, "neutral")
    dims["position"] = {
        "level": level,
        "label": _LEVEL_LABELS[level],
        "evidence": ev,
        "pct_52w": pct_52w,
        "zone": zone,
    }

    # ── 汇总：共振判定 ──
    bullish_dims = sum(1 for d in dims.values() if d["level"] == "bullish")
    bearish_dims = sum(1 for d in dims.values() if d["level"] == "bearish")
    if bullish_dims >= 4:
        verdict = "五维共振看多"
    elif bearish_dims >= 4:
        verdict = "五维共振看空"
    elif bullish_dims >= 3 and bearish_dims <= 1:
        verdict = "多方占优"
    elif bearish_dims >= 3 and bullish_dims <= 1:
        verdict = "空方占优"
    elif bullish_dims == bearish_dims:
        verdict = "多空分歧"
    else:
        verdict = "信号分歧，方向待确认"
    strength = (
        "强"
        if bullish_dims >= 4 or bearish_dims >= 4
        else ("中" if bullish_dims >= 2 or bearish_dims >= 2 else "弱")
    )
    return {
        "dimensions": dims,
        "summary": {
            "bullish_dims": bullish_dims,
            "bearish_dims": bearish_dims,
            "verdict": verdict,
            "signal_strength": strength,
        },
    }


# ══════════════════════════════════════════════════════════════
# API 端点
# ══════════════════════════════════════════════════════════════


@router.get("/api/stock/{symbol}")
async def get_stock(symbol: str, period: str = "3mo", current_user: dict = require_auth()):
    """获取股票详细数据"""
    data = await get_stock_data(symbol, period)
    data["trend_analysis"] = analyze_stock_trend(data)
    data["risk_metrics"] = compute_risk_metrics(data)
    return data


@router.post("/api/stock/analyze")
async def analyze_stock(req: StockAnalysisRequest, current_user: dict = require_auth()):
    """AI 股票分析（v21：五维交叉验证 + 专业投研结构）"""
    return await run_stock_analysis(req.symbol, req.period, req.analysis_type)


# ══════════════════════════════════════════════════════════════
# AI 专业分析（v21：规则计算在前、模型解读在后）
# ══════════════════════════════════════════════════════════════

_ANALYST_ROLE = (
    "你是一位拥有 15 年经验的资深股票分析师（CFA 持证级别）。"
    "请基于给定的程序化计算信号与行情数据，输出专业、严谨、结构化的投研分析报告（Markdown 格式）。"
    "你的判断必须忠实于给定数据，禁止编造任何数据。"
)


# 基础分析 prompt（technical / fundamental 保持轻量，comprehensive 为专业投研结构）
_ANALYSIS_PROMPTS = {
    "technical": """你是一个专业的股票技术分析师。请根据以下股票数据和技术指标，给出详细的技术分析。

## 股票信息
- 股票代码：{symbol}
- 当前价格：{current_price}
- 52周最高：{52w_high}
- 52周最低：{52w_low}

## 技术指标
- RSI: {rsi}
- MACD: {macd}
- MA5: {ma5}
- MA20: {ma20}
- MA60: {ma60}

## 请分析
1. 当前趋势判断（上涨/下跌/震荡）
2. 支撑位和压力位
3. 技术指标信号解读
4. 短期走势预判
5. 操作建议（买入/持有/卖出/观望）

注意：仅供参考，不构成投资建议。""",
    "fundamental": """你是一个专业的股票基本面分析师。请根据以下公司信息，给出基本面分析。

## 公司信息
- 股票代码：{symbol}
- 公司名称：{name}
- 行业：{sector} / {industry}
- 市值：{market_cap}
- 市盈率：{pe_ratio}
- 每股收益：{eps}
- 股息率：{dividend_yield}

## 请分析
1. 公司基本面评估
2. 估值分析（是否合理）
3. 行业地位与竞争力
4. 财务健康度
5. 长期投资价值评估

注意：仅供参考，不构成投资建议。""",
}


# v21：综合专业投研报告结构（参考开源技术分析 SKILL：核心观点→五维验证→关键点位→情景推演→风险提示）
_COMPREHENSIVE_PROMPT = """## 行情数据
- 代码：{symbol}（{name}）· 当前价格：${current_price}
- 52周区间：${52w_low} ~ ${52w_high} · 市值：{market_cap} · 市盈率：{pe_ratio}
- 每股收益：{eps} · 股息率：{dividend_yield}% · 行业：{sector} / {industry}

## 技术指标（最新值）
- RSI(14)：{rsi} · MACD：{macd} · Signal：{signal}
- MA5：{ma5} · MA20：{ma20} · MA60：{ma60}
- 布林带：上轨 {bb_upper} / 中轨 {bb_middle} / 下轨 {bb_lower}

## 风险指标（程序化计算）
- 综合风险等级：{risk_level} · 年化波动率：{volatility_pct}%（{volatility_level}）
- 区间最大回撤：{max_drawdown_pct}%（{peak_date} → {trough_date}）· 流动性：{liquidity_level}
- 风险警告：{warnings}

## 五维交叉验证信号（程序化计算，事实依据，禁止修改）
- 趋势维度（{trend_label}）：{trend_evidence}
- 动量维度（{momentum_label}）：{momentum_evidence}
- 波动维度（{volatility_label}）：{volatility_evidence}
- 量价维度（{volume_price_label}）：{volume_price_evidence}
- 位置风险（{position_label}）：{position_evidence}
- 汇总：{verdict}（看多 {bullish_dims} 维 / 看空 {bearish_dims} 维，信号强度{signal_strength}）

## 关键点位（程序化计算）
- 支撑位：{support}
- 压力位：{resistance}

## 输出要求（严格按此 Markdown 结构）
### 核心观点
1-2 句总括判断（附置信度：高/中/低），明确短期（1周）与中期（1-3月）方向。

### 五维交叉验证
对五个维度逐一给出「证据 → 判断」；指出哪些维度共振、哪些分歧，并说明对结论强度的影响（共振增强 / 分歧降级）。

### 关键点位
引用程序化计算的支撑/压力位，说明跌破/突破后的意义。

### 情景推演
- 乐观情景：触发条件 + 目标位
- 中性情景：运行区间
- 谨慎情景：触发条件 + 风险位

### 风险提示
结合波动/回撤/位置/量价背离给出具体风险因素。

### 操作策略
条件化操作建议（若……则……），明确止损位与仓位建议（轻仓/半仓/标准仓）。

要求：
1. 所有结论必须基于给定数据，禁止编造；缺失数据标注 N/A
2. 量化优先：每个结论尽量带具体数字
3. 五维分歧时用条件化表达，禁止绝对化断言
4. 报告直接输出 Markdown，可读性优先

⚠️ 免责声明：本报告仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"""


def _fmt_num(v, digits=2) -> str:
    """数值格式化：None/0 显示 N/A，大数避免科学计数法。"""
    if v is None:
        return "N/A"
    try:
        return f"{round(float(v), digits):,}"
    except (TypeError, ValueError):
        return "N/A"


# technical / fundamental 模板占位符字段（与旧实现一致的注入字段）
_BASE_FIELDS = (
    "symbol", "name", "current_price", "52w_high", "52w_low",
    "rsi", "macd", "ma5", "ma20", "ma60",
    "market_cap", "pe_ratio", "eps", "dividend_yield", "sector", "industry",
)


def _build_analysis_prompt(data: dict, risk_metrics: dict, signals: dict, levels: dict, analysis_type: str) -> str:
    """构建分析 prompt：comprehensive 用五维投研结构，其余走基础模板。"""
    ind = data.get("indicators") or {}
    if analysis_type in _ANALYSIS_PROMPTS:
        return _ANALYSIS_PROMPTS[analysis_type].format(
            symbol=data["symbol"],
            name=data.get("name", ""),
            current_price=_fmt_num(data.get("current_price")),
            **{"52w_high": _fmt_num(data.get("52w_high"))},
            **{"52w_low": _fmt_num(data.get("52w_low"))},
            rsi=_fmt_num(ind.get("rsi")),
            macd=_fmt_num(ind.get("macd"), 4),
            ma5=_fmt_num(ind.get("ma5")),
            ma20=_fmt_num(ind.get("ma20")),
            ma60=_fmt_num(ind.get("ma60")),
            market_cap=_fmt_num(data.get("market_cap"), 0),
            pe_ratio=_fmt_num(data.get("pe_ratio")),
            eps=_fmt_num(data.get("eps")),
            dividend_yield=_fmt_num(data.get("dividend_yield")),
            sector=data.get("sector", ""),
            industry=data.get("industry", ""),
        )

    latest = data.get("data_points") or [{}]
    latest = latest[-1]
    dims = signals.get("dimensions") or {}
    summary = signals.get("summary") or {}
    warnings = "；".join(risk_metrics.get("warnings") or [])

    def _join_evidence(key: str) -> str:
        d = dims.get(key)
        if not d:
            return "N/A"
        text = "；".join(d.get("evidence") or []) or "N/A"
        return f"{d.get('label', '中性')}：{text}"

    def _fmt_levels(items: list) -> str:
        return "；".join(f"{it['tag']} ${it['level']}" for it in items) or "N/A"

    return _COMPREHENSIVE_PROMPT.format(
        symbol=data["symbol"],
        name=data.get("name", ""),
        current_price=_fmt_num(data.get("current_price")),
        **{"52w_high": _fmt_num(data.get("52w_high"))},
        **{"52w_low": _fmt_num(data.get("52w_low"))},
        market_cap=_fmt_num(data.get("market_cap"), 0),
        pe_ratio=_fmt_num(data.get("pe_ratio")),
        eps=_fmt_num(data.get("eps")),
        dividend_yield=_fmt_num(data.get("dividend_yield")),
        sector=data.get("sector", ""),
        industry=data.get("industry", ""),
        rsi=_fmt_num(ind.get("rsi")),
        macd=_fmt_num(ind.get("macd"), 4),
        signal=_fmt_num(latest.get("signal"), 4),
        ma5=_fmt_num(ind.get("ma5")),
        ma20=_fmt_num(ind.get("ma20")),
        ma60=_fmt_num(ind.get("ma60")),
        bb_upper=_fmt_num(latest.get("bb_upper")),
        bb_middle=_fmt_num(latest.get("bb_middle")),
        bb_lower=_fmt_num(latest.get("bb_lower")),
        risk_level=risk_metrics.get("risk_level", "N/A"),
        volatility_pct=risk_metrics.get("volatility_pct") if risk_metrics.get("volatility_pct") is not None else "N/A",
        volatility_level=risk_metrics.get("volatility_level", "N/A"),
        max_drawdown_pct=risk_metrics.get("max_drawdown_pct") if risk_metrics.get("max_drawdown_pct") is not None else "N/A",
        peak_date=risk_metrics.get("drawdown_peak_date") or "N/A",
        trough_date=risk_metrics.get("drawdown_trough_date") or "N/A",
        liquidity_level=risk_metrics.get("liquidity_level", "N/A"),
        warnings=warnings or "无",
        trend_label=dims.get("trend", {}).get("label", "中性"),
        trend_evidence=_join_evidence("trend"),
        momentum_label=dims.get("momentum", {}).get("label", "中性"),
        momentum_evidence=_join_evidence("momentum"),
        volatility_label=dims.get("volatility", {}).get("label", "中性"),
        volatility_evidence=_join_evidence("volatility"),
        volume_price_label=dims.get("volume_price", {}).get("label", "中性"),
        volume_price_evidence=_join_evidence("volume_price"),
        position_label=dims.get("position", {}).get("label", "中性"),
        position_evidence=_join_evidence("position"),
        verdict=summary.get("verdict", "数据不足"),
        bullish_dims=summary.get("bullish_dims", 0),
        bearish_dims=summary.get("bearish_dims", 0),
        signal_strength=summary.get("signal_strength", "弱"),
        support=_fmt_levels(levels.get("support") or []),
        resistance=_fmt_levels(levels.get("resistance") or []),
    )


async def run_stock_analysis(symbol: str, period: str = "3mo", analysis_type: str = "comprehensive") -> dict:
    """抓取行情 → 五维信号/关键点位程序化计算 → LLM 专业投研分析 → 入库。

    API handler 与定时任务（scheduler stock_report）共用执行体。
    返回 {ok, id, symbol, name, analysis_type, result, data_summary}。
    """
    data = await get_stock_data(symbol, period)
    rm = compute_risk_metrics(data)
    signals = compute_five_dim_signals(data)
    levels = compute_support_resistance(data)
    prompt = _build_analysis_prompt(data, rm, signals, levels, analysis_type)

    try:
        result = await call_llm_async(_ANALYST_ROLE, prompt)
    except Exception as e:
        raise HTTPException(500, f"分析失败: {str(e)}") from e
    if not result or not str(result).strip():
        raise HTTPException(502, "AI 未返回分析内容，请重试")
    result = str(result)

    # 保存分析记录
    record_id = f"stock_analysis_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO stock_analyses (id, symbol, analysis_type, period, result, created_at)
               VALUES (?,?,?,?,?,?)""",
            (record_id, data["symbol"], analysis_type, period, result, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ok": True,
        "id": record_id,
        "symbol": data["symbol"],
        "name": data.get("name", ""),
        "analysis_type": analysis_type,
        "result": result,
        "data_summary": {
            "current_price": data.get("current_price"),
            "trend_analysis": analyze_stock_trend(data),
            "risk_metrics": rm,
            "five_dim_signals": signals,
            "support_resistance": levels,
        },
    }


@router.get("/api/stock/reports")
async def list_stock_reports(limit: int = 20, current_user: dict = require_auth()):
    """v21：当前用户定时股票分析报告列表（按时间倒序）。"""
    uid = str(current_user.get("user_id", ""))
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, symbol, period, report, created_at FROM stock_reports "
            "WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (uid, min(max(limit, 1), 100)),
        ).fetchall()
        return {"items": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.get("/api/stock/reports/{report_id}")
async def get_stock_report(report_id: int, current_user: dict = require_auth()):
    """v21：单条定时股票报告详情（校验归属）。"""
    uid = str(current_user.get("user_id", ""))
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, symbol, period, report, created_at FROM stock_reports WHERE id=? AND user_id=?",
            (report_id, uid),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "报告不存在")
    return dict(row)


@router.delete("/api/stock/reports/{report_id}")
async def delete_stock_report(report_id: int, current_user: dict = require_auth()):
    """v21：删除单条定时股票报告（校验归属）。"""
    uid = str(current_user.get("user_id", ""))
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM stock_reports WHERE id=? AND user_id=?", (report_id, uid))
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "报告不存在")
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
# 模拟交易
# ══════════════════════════════════════════════════════════════


@router.get("/api/trading/portfolio")
async def get_portfolio(current_user: dict = require_auth()):
    """获取模拟交易投资组合"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        # 获取账户信息
        account = conn.execute("SELECT * FROM trading_accounts WHERE user_id=?", (user_id,)).fetchone()

        if not account:
            # 创建默认账户
            account_id = f"acc_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO trading_accounts (id, user_id, cash, created_at)
                   VALUES (?,?,1000000,?)""",
                (account_id, user_id, datetime.now().isoformat()),
            )
            conn.commit()
            account = {"id": account_id, "cash": 1000000, "total_value": 1000000}
        else:
            account = dict(account)

        # 获取持仓
        positions = []
        for row in conn.execute("SELECT * FROM trading_positions WHERE account_id=?", (account["id"],)).fetchall():
            pos = dict(row)
            # 获取当前价格
            try:
                data = await get_stock_data(pos["symbol"], "1d")
                pos["current_price"] = data.get("current_price", 0)
                pos["market_value"] = pos["current_price"] * pos["quantity"]
                pos["profit_loss"] = (pos["current_price"] - pos["avg_cost"]) * pos["quantity"]
                pos["profit_loss_pct"] = (
                    ((pos["current_price"] - pos["avg_cost"]) / pos["avg_cost"] * 100) if pos["avg_cost"] > 0 else 0
                )
            except Exception:
                pos["current_price"] = pos["avg_cost"]
                pos["market_value"] = pos["avg_cost"] * pos["quantity"]
                pos["profit_loss"] = 0
                pos["profit_loss_pct"] = 0
            positions.append(pos)

        # 获取交易历史
        trades = []
        for row in conn.execute(
            "SELECT * FROM trading_history WHERE account_id=? ORDER BY created_at DESC LIMIT 50", (account["id"],)
        ).fetchall():
            trades.append(dict(row))

        # 计算总资产
        total_market_value = sum(p["market_value"] for p in positions)
        account["total_value"] = account["cash"] + total_market_value
        account["positions"] = positions
        account["trades"] = trades

        return account
    finally:
        conn.close()


@router.post("/api/trading/trade")
async def execute_trade(req: TradeRequest, current_user: dict = require_auth()):
    """执行模拟交易"""
    user_id = current_user["user_id"]

    # 获取当前价格
    data = await get_stock_data(req.symbol, "1d")
    price = req.price or data.get("current_price", 0)

    if price <= 0:
        raise HTTPException(400, "无法获取股票价格")

    conn = get_db()
    try:
        # 获取账户
        account = conn.execute("SELECT * FROM trading_accounts WHERE user_id=?", (user_id,)).fetchone()

        if not account:
            raise HTTPException(400, "请先创建交易账户")

        account = dict(account)
        trade_amount = price * req.quantity

        if req.action == "buy":
            # 买入检查
            if account["cash"] < trade_amount:
                raise HTTPException(400, f"现金不足，需要 {trade_amount}，当前 {account['cash']}")

            # 更新现金
            conn.execute(
                "UPDATE trading_accounts SET cash=? WHERE id=?", (account["cash"] - trade_amount, account["id"])
            )

            # 更新或创建持仓
            existing = conn.execute(
                "SELECT * FROM trading_positions WHERE account_id=? AND symbol=?", (account["id"], req.symbol)
            ).fetchone()

            if existing:
                existing = dict(existing)
                new_qty = existing["quantity"] + req.quantity
                new_avg = (existing["avg_cost"] * existing["quantity"] + price * req.quantity) / new_qty
                conn.execute(
                    "UPDATE trading_positions SET quantity=?, avg_cost=? WHERE id=?", (new_qty, new_avg, existing["id"])
                )
            else:
                pos_id = f"pos_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """INSERT INTO trading_positions (id, account_id, symbol, quantity, avg_cost, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (pos_id, account["id"], req.symbol, req.quantity, price, datetime.now().isoformat()),
                )

        elif req.action == "sell":
            # 卖出检查
            existing = conn.execute(
                "SELECT * FROM trading_positions WHERE account_id=? AND symbol=?", (account["id"], req.symbol)
            ).fetchone()

            if not existing or existing["quantity"] < req.quantity:
                raise HTTPException(400, "持仓不足")

            existing = dict(existing)

            # 更新现金
            conn.execute(
                "UPDATE trading_accounts SET cash=? WHERE id=?", (account["cash"] + trade_amount, account["id"])
            )

            # 更新持仓
            new_qty = existing["quantity"] - req.quantity
            if new_qty > 0:
                conn.execute("UPDATE trading_positions SET quantity=? WHERE id=?", (new_qty, existing["id"]))
            else:
                conn.execute("DELETE FROM trading_positions WHERE id=?", (existing["id"],))

        # 记录交易
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO trading_history (id, account_id, symbol, action, quantity, price, amount, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                trade_id,
                account["id"],
                req.symbol,
                req.action,
                req.quantity,
                price,
                trade_amount,
                datetime.now().isoformat(),
            ),
        )

        conn.commit()

        return {
            "ok": True,
            "trade_id": trade_id,
            "symbol": req.symbol,
            "action": req.action,
            "quantity": req.quantity,
            "price": price,
            "amount": trade_amount,
        }
    finally:
        conn.close()


@router.post("/api/trading/reset")
async def reset_portfolio(current_user: dict = require_auth()):
    """重置模拟交易账户"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        # 删除旧账户和关联数据
        account = conn.execute("SELECT id FROM trading_accounts WHERE user_id=?", (user_id,)).fetchone()

        if account:
            conn.execute("DELETE FROM trading_positions WHERE account_id=?", (account["id"],))
            conn.execute("DELETE FROM trading_history WHERE account_id=?", (account["id"],))
            conn.execute("DELETE FROM trading_accounts WHERE id=?", (account["id"],))

        # 创建新账户
        account_id = f"acc_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO trading_accounts (id, user_id, cash, created_at)
               VALUES (?,?,1000000,?)""",
            (account_id, user_id, datetime.now().isoformat()),
        )
        conn.commit()

        return {"ok": True, "message": "账户已重置，初始资金 100 万"}
    finally:
        conn.close()
