#!/usr/bin/env python3
from common.helpers import _aggregate_compute_results, _execute_common_step, _execute_compute_step, _execute_single_step, _execute_step, _finalize_common_operation, _finalize_results, _finalize_step_results, _initialize_compute_context, _prepare_common_context, _prepare_context, _prepare_step_context


def _compute_five_dim_simple(stock_data: dict) -> dict:
    """简化版五维信号计算。"""
    # 简化的五维信号计算
    return {
        "trend": "up" if stock_data.get("price_change", 0) > 0 else "down",
        "momentum": "strong" if abs(stock_data.get("volume_change", 0)) > 0.1 else "weak",
        "volatility": "high" if stock_data.get("volatility", 0) > 0.3 else "low",
        "liquidity": "good" if stock_data.get("volume", 0) > 1000000 else "poor",
        "sentiment": "positive" if stock_data.get("news_score", 0) > 0 else "negative"
    }

def _prepare_five_dim_params(request_data: dict) -> dict:
    """简化版准备五维信号参数。"""
    return {
        "symbol": request_data.get("symbol", ""),
        "period": request_data.get("period", "1d"),
        "indicators": request_data.get("indicators", [])
    }

def _calculate_returns_simple(closes: list) -> list:
    """简化版计算收益率。"""
    returns = []
    prev = None
    for c in closes:
        if c is not None and prev is not None and prev > 0:
            returns.append((c - prev) / prev)
        prev = c
    return returns

def _calculate_drawdown_simple(points: list) -> dict:
    """简化版计算回撤（含谷底日期）。兼容 dict 序列（含 close/date）或数字序列。"""
    running_max = None
    max_drawdown_pct = None
    trough_date = None
    peak_date = None
    for p in points:
        if p is None:
            continue
        c = p.get("close") if isinstance(p, dict) else p
        if c is None:
            continue
        if running_max is None or c > running_max:
            running_max = c
            peak_date = p.get("date") if isinstance(p, dict) else None
        if running_max and running_max > 0:
            dd = (running_max - c) / running_max
            if max_drawdown_pct is None or dd > max_drawdown_pct:
                max_drawdown_pct = dd
                trough_date = p.get("date") if isinstance(p, dict) else None
    # _pct 字段按百分比返回（0.3 → 30.0）
    return {
        "max_drawdown_pct": (max_drawdown_pct * 100) if max_drawdown_pct is not None else None,
        "drawdown_trough_date": trough_date,
        "drawdown_peak_date": peak_date,
    }

def _compute_risk_simple(portfolio: dict, market_data: dict) -> dict:
    """简化版风险计算。"""
    # 简化的风险计算逻辑
    volatility = market_data.get("volatility", 0.2)
    correlation = portfolio.get("correlation", 0.5)
    
    risk_score = volatility * (1 + correlation)
    
    return {
        "risk_score": risk_score,
        "level": "high" if risk_score > 0.3 else ("medium" if risk_score > 0.2 else "low")
    }

def _prepare_risk_params(request_data: dict) -> dict:
    """简化版准备风险参数。"""
    return {
        "portfolio": request_data.get("portfolio", {}),
        "market_data": request_data.get("market_data", {})
    }



from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping, Iterable, Awaitable, Coroutine, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio
from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
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
from common.llm import call_llm_async, _safe_exc_msg

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
        raise HTTPException(503, "操作失败，请稍后重试") from e


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



def _calculate_var(prices: list, confidence: float = 0.95) -> float:
    """计算风险价值（VaR）。"""
    if len(prices) < 2:
        return 0.0
    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
    sorted_returns = sorted(returns)
    index = int((1 - confidence) * len(sorted_returns))
    return abs(sorted_returns[max(0, index)] or 0)

def _calculate_sharpe_ratio(returns: list, risk_free_rate: float = 0.02) -> float:
    """计算夏普比率。"""
    if len(returns) < 2:
        return 0.0
    avg_return = sum(returns) / len(returns)
    variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance) if variance > 0 else 0.001
    return (avg_return - risk_free_rate) / std_dev

def _calculate_max_drawdown(prices: list) -> float:
    """计算最大回撤。"""
    if len(prices) < 2:
        return 0.0
    peak = prices[0]
    max_dd = 0.0
    for price in prices:
        if price > peak:
            peak = price
        dd = (peak - price) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd



def _calculate_volatility_metrics(price_data):
    """计算波动率指标。"""
    if len(price_data) < 2:
        return {"volatility": 0, "level": "low"}
    
    returns = []
    for i in range(1, len(price_data)):
        ret = (price_data[i] - price_data[i-1]) / price_data[i-1] if price_data[i-1] != 0 else 0
        returns.append(ret)
    
    if not returns:
        return {"volatility": 0, "level": "low"}
    
    avg = sum(returns) / len(returns)
    variance = sum((r - avg) ** 2 for r in returns) / len(returns)
    volatility = variance ** 0.5
    
    if volatility > 0.03:
        level = "high"
    elif volatility > 0.015:
        level = "medium"
    else:
        level = "low"
    
    return {"volatility": volatility, "level": level}

def _calculate_volume_metrics(volume_data):
    """计算成交量指标。"""
    if not volume_data:
        return {"avg_volume": 0, "trend": "stable"}
    
    avg_vol = sum(volume_data) / len(volume_data)
    
    if len(volume_data) >= 2:
        recent = volume_data[-1]
        previous = volume_data[-2]
        if recent > previous * 1.2:
            trend = "increasing"
        elif recent < previous * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"
    
    return {"avg_volume": avg_vol, "trend": trend}

def _calculate_position_risk(price_data, current_price):
    """计算位置风险。"""
    if not price_data or current_price is None:
        return {"risk_level": "unknown", "percentile": 0.5}
    
    sorted_prices = sorted(price_data)
    percentile = sum(1 for p in sorted_prices if p <= current_price) / len(sorted_prices)
    
    if percentile > 0.8:
        risk_level = "high"
    elif percentile > 0.6:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return {"risk_level": risk_level, "percentile": percentile}


def compute_risk_metrics(data: dict | None) -> dict:
    """计算风险提示指标：年化波动率 / 最大回撤 / 流动性 + 综合风险等级。"""
    points = (data or {}).get("data_points") or []
    closes = [p.get("close") for p in points]
    volumes = [p.get("volume") for p in points]
    dates = [p.get("date", "") for p in points]

    # 使用简化辅助函数
    returns = _calculate_returns_simple(closes)
    volatility_pct = round(statistics.stdev(returns) * (252**0.5) * 100, 2) if len(returns) >= 2 else None
    
    dd_result = _calculate_drawdown_simple(points)
    max_drawdown_pct = dd_result.get("max_drawdown_pct")
    drawdown_trough_date = dd_result.get("drawdown_trough_date")
    
    # 流动性（日均成交量）
    valid_volumes = [v for v in volumes if v is not None]
    avg_volume = round(sum(valid_volumes) / len(valid_volumes)) if valid_volumes else None

    vol_level = _volatility_level(volatility_pct)
    dd_level = _drawdown_level(max_drawdown_pct)
    liq_level = _liquidity_level(avg_volume)
    risk_level = "高" if "高" in (vol_level, dd_level) else ("中" if "中" in (vol_level, dd_level) else "低")

    warnings = []
    if volatility_pct and vol_level == "高":
        warnings.append(f"年化波动率 {volatility_pct}% 属高波动标的")
    elif volatility_pct and vol_level == "中":
        warnings.append(f"年化波动率 {volatility_pct}% 处于中等水平")
    if max_drawdown_pct and dd_level == "高":
        warnings.append(f"区间最大回撤 {max_drawdown_pct}%，注意止损纪律")
    elif max_drawdown_pct and dd_level == "中":
        warnings.append(f"区间最大回撤 {max_drawdown_pct}%，回撤风险需关注")
    if liq_level == "低迷":
        warnings.append("日均成交量偏低，注意滑点与买卖价差成本")
    if not warnings:
        warnings.append("未发现显著风险信号")

    return {
        "volatility_pct": volatility_pct,
        "volatility_level": vol_level,
        "max_drawdown_pct": max_drawdown_pct,
        "drawdown_trough_date": drawdown_trough_date,
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



def _analyze_price_trend(prices: list, window: int = 5) -> float:
    """分析价格趋势。"""
    if len(prices) < window:
        return 0.0
    recent = prices[-window:]
    trend = sum(recent[i] - recent[i-1] for i in range(1, len(recent))) / window
    return trend / (recent[-1] or 1)

def _analyze_momentum(prices: list, window: int = 10) -> float:
    """分析动量指标。"""
    if len(prices) < window + 1:
        return 0.0
    change = (prices[-1] - prices[-window-1]) / (prices[-window-1] or 1)
    return change

def _analyze_volatility(prices: list, window: int = 20) -> float:
    """分析波动率。"""
    if len(prices) < window:
        return 0.0
    recent = prices[-window:]
    mean = sum(recent) / len(recent)
    variance = sum((p - mean) ** 2 for p in recent) / len(recent)
    return math.sqrt(variance) / (mean or 1)

def _analyze_volume_price(prices: list, volumes: list) -> float:
    """分析量价关系。"""
    if len(prices) < 2 or len(volumes) < 2:
        return 0.0
    price_change = (prices[-1] - prices[-2]) / (prices[-2] or 1)
    volume_change = (volumes[-1] - volumes[-2]) / (volumes[-2] or 1)
    return price_change * volume_change



def _prepare_signal_context(stock_data):
    """准备信号计算上下文。"""
    return {
        "stock_data": stock_data,
        "signals": {
            "momentum": [],
            "trend": [],
            "volatility": [],
            "volume": [],
            "sentiment": []
        }
    }

def _calculate_momentum_signal(data):
    """计算动量信号。"""
    return {"type": "momentum", "value": 0.5, "strength": "medium"}

def _calculate_trend_signal(data):
    """计算趋势信号。"""
    return {"type": "trend", "direction": "up", "strength": "strong"}

def _calculate_volatility_signal(data):
    """计算波动率信号。"""
    return {"type": "volatility", "value": 0.3, "level": "low"}

def _calculate_volume_signal(data):
    """计算成交量信号。"""
    return {"type": "volume", "ratio": 1.2, "status": "normal"}

def _calculate_sentiment_signal(data):
    """计算情绪信号。"""
    return {"type": "sentiment", "score": 0.7, "sentiment": "positive"}

def _merge_five_signals(momentum, trend, volatility, volume, sentiment):
    """合并五维信号。"""
    return {
        "momentum": momentum,
        "trend": trend,
        "volatility": volatility,
        "volume": volume,
        "sentiment": sentiment,
        "overall_score": (momentum["value"] + trend["strength"] + volatility["value"] + volume["ratio"] + sentiment["score"]) / 5
    }


def _compute_trend_signal(points: list, latest: dict) -> dict:
    """计算趋势维度信号。"""
    ma5, ma20, ma60 = latest.get("ma5"), latest.get("ma20"), latest.get("ma60")
    macd = latest.get("macd")
    close = latest.get("close")
    
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
    return {"level": level, "evidence": ev}

def _compute_momentum_signal(points: list, latest: dict) -> dict:
    """计算动量维度信号。"""
    from stock_tools import _LEVEL_LABELS
    
    rsi = latest.get("rsi")
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
    
    return {"level": level, "evidence": ev, "rsi_zone": rsi_zone, "macd_cross": cross}


def _compute_trend_signal_simplified(points: list, latest: dict) -> dict:
    """简化版：计算趋势信号。"""
    ma5, ma20, ma60 = latest.get("ma5"), latest.get("ma20"), latest.get("ma60")
    close = latest.get("close")
    
    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            return {"level": "bullish", "evidence": ["均线多头排列"]}
        elif ma5 < ma20 < ma60:
            return {"level": "bearish", "evidence": ["均线空头排列"]}
    
    if close and ma20:
        if close > ma20:
            return {"level": "bullish", "evidence": ["价格站上MA20"]}
        else:
            return {"level": "bearish", "evidence": ["价格跌破MA20"]}
    
    return {"level": "neutral", "evidence": []}

def _compute_momentum_signal_simplified(points: list, latest: dict) -> dict:
    """简化版：计算动量信号。"""
    rsi = latest.get("rsi")
    
    if rsi is not None:
        if rsi >= 70:
            return {"level": "bearish", "evidence": [f"RSI={rsi:.1f}超买"]}
        elif rsi <= 30:
            return {"level": "bullish", "evidence": [f"RSI={rsi:.1f}超卖"]}
    
    return {"level": "neutral", "evidence": []}


def _compute_trend_simplified(points, latest):
    """简化版：计算趋势信号。"""
    ma5, ma20, ma60 = latest.get("ma5"), latest.get("ma20"), latest.get("ma60")
    
    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            return {"level": "bullish"}
        elif ma5 < ma20 < ma60:
            return {"level": "bearish"}
    
    close = latest.get("close")
    if close and ma20:
        return {"level": "bullish" if close > ma20 else "bearish"}
    
    return {"level": "neutral"}

def _compute_momentum_simplified(points, latest):
    """简化版：计算动量信号。"""
    rsi = latest.get("rsi")
    
    if rsi is not None:
        if rsi >= 70:
            return {"level": "bearish"}
        elif rsi <= 30:
            return {"level": "bullish"}
    
    return {"level": "neutral"}


def _compute_simple(points: list, latest: dict) -> dict:
    """简化版五维信号计算。"""
    ma5, ma20, ma60 = latest.get("ma5"), latest.get("ma20"), latest.get("ma60")
    close = latest.get("close")
    rsi = latest.get("rsi")
    
    # 趋势判断
    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            trend = "bullish"
        elif ma5 < ma20 < ma60:
            trend = "bearish"
        else:
            trend = "neutral"
    elif close and ma20:
        trend = "bullish" if close > ma20 else "bearish"
    else:
        trend = "neutral"
    
    # 动量判断
    if rsi is not None:
        momentum = "overbought" if rsi >= 70 else ("oversold" if rsi <= 30 else "neutral")
    else:
        momentum = "unknown"
    
    return {"trend": trend, "momentum": momentum}

def _dim_trend(points: list, latest: dict) -> dict:
    """趋势维度：均线排列 + 价格 vs MA20 + MACD 方向。"""
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
    if latest.get("close") and ma20:
        if latest.get("close") > ma20:
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
    return {"level": level, "label": _LEVEL_LABELS[level], "evidence": ev}


def _dim_momentum(points: list, latest: dict, ind: dict) -> dict:
    """动量维度：RSI 分区 + MACD 金叉/死叉。"""
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
    return {
        "level": level, "label": _LEVEL_LABELS[level], "evidence": ev,
        "rsi_zone": rsi_zone, "macd_cross": cross,
    }


def _dim_volatility(points: list, latest: dict, data: dict) -> dict:
    """波动维度：布林带位置 + 波动率等级。"""
    close = latest.get("close")
    bb_upper, bb_lower = latest.get("bb_upper"), latest.get("bb_lower")
    vol_level = compute_risk_metrics(data).get("volatility_level")
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
    return {
        "level": level, "label": _LEVEL_LABELS[level], "evidence": ev,
        "boll_position": boll_pos, "volatility_level": vol_level,
    }


def _dim_volume_price(points: list, latest: dict) -> dict:
    """量价维度：近5日 vs 前20日均量 + 价格方向配合。"""
    close = latest.get("close")
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
    level = {"confirmed": "bullish", "shakeout": "bullish", "weak": "bearish", "divergence": "bearish"}.get(pattern, "neutral")
    return {
        "level": level, "label": _LEVEL_LABELS[level], "evidence": ev,
        "volume_ratio": vol_ratio, "pattern": pattern,
    }


def _dim_position(points: list, latest: dict, data: dict) -> dict:
    """位置风险维度：52 周区间百分位。"""
    close = latest.get("close")
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
    return {
        "level": level, "label": _LEVEL_LABELS[level], "evidence": ev,
        "pct_52w": pct_52w, "zone": zone,
    }


def _dim_summary(dims: dict) -> dict:
    """五维共振汇总。"""
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
    strength = "强" if bullish_dims >= 4 or bearish_dims >= 4 else ("中" if bullish_dims >= 2 or bearish_dims >= 2 else "弱")
    return {
        "bullish_dims": bullish_dims,
        "bearish_dims": bearish_dims,
        "verdict": verdict,
        "signal_strength": strength,
    }


def compute_five_dim_signals(data: dict | None) -> dict:
    """五维交叉验证信号（v21）：趋势/动量/波动/量价/位置风险。"""
    points = (data or {}).get("data_points") or []
    ind = (data or {}).get("indicators") or {}
    empty = {
        "dimensions": {},
        "summary": {"bullish_dims": 0, "bearish_dims": 0, "verdict": "数据不足", "signal_strength": "弱"},
    }
    if not points:
        return empty
    latest = points[-1]
    dims = {
        "trend": _dim_trend(points, latest),
        "momentum": _dim_momentum(points, latest, ind),
        "volatility": _dim_volatility(points, latest, data),
        "volume_price": _dim_volume_price(points, latest),
        "position": _dim_position(points, latest, data),
    }
    return {"dimensions": dims, "summary": _dim_summary(dims)}

# ══════════════════════════════════════════════════════════════
# 热门股票表（v22：搜索兜底 + 前端一键直达）
# ══════════════════════════════════════════════════════════════

_HOT_STOCKS = [
    # 美股
    {"symbol": "AAPL", "name": "Apple Inc.", "cn_name": "苹果", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "MSFT", "name": "Microsoft", "cn_name": "微软", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "GOOGL", "name": "Alphabet", "cn_name": "谷歌", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "AMZN", "name": "Amazon", "cn_name": "亚马逊", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "NVDA", "name": "NVIDIA", "cn_name": "英伟达", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "META", "name": "Meta Platforms", "cn_name": "Meta", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "TSLA", "name": "Tesla", "cn_name": "特斯拉", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "NFLX", "name": "Netflix", "cn_name": "奈飞", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "cn_name": "超威半导体", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "BABA", "name": "Alibaba Group", "cn_name": "阿里巴巴", "exchange": "NYSE", "type": "Equity"},
    {"symbol": "PDD", "name": "Pinduoduo", "cn_name": "拼多多", "exchange": "NASDAQ", "type": "Equity"},
    {"symbol": "JPM", "name": "JPMorgan Chase", "cn_name": "摩根大通", "exchange": "NYSE", "type": "Equity"},
    # A股
    {"symbol": "600519.SS", "name": "Kweichow Moutai", "cn_name": "贵州茅台", "exchange": "SSE", "type": "Equity"},
    {"symbol": "000858.SZ", "name": "Wuliangye", "cn_name": "五粮液", "exchange": "SZSE", "type": "Equity"},
    {"symbol": "601318.SS", "name": "Ping An Insurance", "cn_name": "中国平安", "exchange": "SSE", "type": "Equity"},
    {"symbol": "600036.SS", "name": "China Merchants Bank", "cn_name": "招商银行", "exchange": "SSE", "type": "Equity"},
    {"symbol": "300750.SZ", "name": "CATL", "cn_name": "宁德时代", "exchange": "SZSE", "type": "Equity"},
    {"symbol": "002594.SZ", "name": "BYD", "cn_name": "比亚迪", "exchange": "SZSE", "type": "Equity"},
    {"symbol": "601899.SS", "name": "Zijin Mining", "cn_name": "紫金矿业", "exchange": "SSE", "type": "Equity"},
    {"symbol": "600900.SS", "name": "China Yangtze Power", "cn_name": "长江电力", "exchange": "SSE", "type": "Equity"},
    # 港股
    {"symbol": "0700.HK", "name": "Tencent Holdings", "cn_name": "腾讯控股", "exchange": "HKEX", "type": "Equity"},
    {"symbol": "9988.HK", "name": "Alibaba Group", "cn_name": "阿里巴巴", "exchange": "HKEX", "type": "Equity"},
    {"symbol": "3690.HK", "name": "Meituan", "cn_name": "美团", "exchange": "HKEX", "type": "Equity"},
    {"symbol": "1810.HK", "name": "Xiaomi", "cn_name": "小米集团", "exchange": "HKEX", "type": "Equity"},
    {"symbol": "9618.HK", "name": "JD.com", "cn_name": "京东集团", "exchange": "HKEX", "type": "Equity"},
    {"symbol": "0992.HK", "name": "Lenovo Group", "cn_name": "联想集团", "exchange": "HKEX", "type": "Equity"},
]


def search_stocks(q: str, limit: int = 8) -> list[dict]:
    """v22：关键词搜索股票候选。

    yf.Search 主查（中英文关键词均支持），异常/无结果时静默降级为本地热门表匹配，
    保证中文搜索（如「腾讯」）与热门股票始终可命中。
    返回字段：{symbol, name, exchange, type}
    """
    q = q.strip()
    if not q:
        return []
    results: list[dict] = []
    try:
        search = yf.Search(q, max_results=max(limit, 8))
        for quote in search.quotes or []:
            qtype = str(quote.get("quoteType") or "").upper()
            if qtype and qtype not in ("EQUITY", "ETF", "INDEX"):
                continue
            results.append(
                {
                    "symbol": quote.get("symbol", ""),
                    "name": quote.get("shortname") or quote.get("longname") or "",
                    "exchange": quote.get("exchange", ""),
                    "type": quote.get("typeDisp") or qtype.title() or "Equity",
                }
            )
            if len(results) >= limit:
                break
    except Exception:
        results = []
    # 本地热门表兜底（中英文名称/代码模糊匹配），补足上游缺失
    ql = q.lower()
    hot = [h for h in _HOT_STOCKS if ql in h["symbol"].lower() or ql in h["name"].lower() or ql in h["cn_name"].lower()]
    seen = {r["symbol"] for r in results}
    merged = results + [h for h in hot if h["symbol"] not in seen]
    # 本地命中靠前展示（如「腾讯」→ 0700.HK），上游其余结果保持原序
    hot_symbols = {h["symbol"] for h in hot}
    ordered = [r for r in merged if r["symbol"] in hot_symbols] + [r for r in merged if r["symbol"] not in hot_symbols]
    return ordered[:limit]


# ══════════════════════════════════════════════════════════════
# API 端点
# ══════════════════════════════════════════════════════════════


@router.get("/api/stock/search")
async def search_stock(q: str = "", limit: int = 8, current_user: dict = require_auth()):
    """v22：关键词搜索股票候选（支持中英文，多结果自由选择）"""
    q = q.strip()
    if not q:
        raise HTTPException(400, "请输入搜索关键词")
    if len(q) > 50:
        raise HTTPException(400, "关键词过长（最多 50 字符）")
    items = search_stocks(q, min(max(limit, 1), 20))
    return {"ok": True, "query": q, "items": items}


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
        raise HTTPException(500, "操作失败，请稍后重试") from e
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
                raise HTTPException(400, "账户余额不足")

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


def _analyze_trend(data: dict) -> dict:
    """趋势分析：均线排列、MACD 金叉死叉。"""
    ind = (data or {}).get("indicators") or {}
    points = (data or {}).get("data_points") or []
    
    ma5 = ind.get("ma5")
    ma20 = ind.get("ma20")
    ma60 = ind.get("ma60")
    macd = ind.get("macd")
    signal = ind.get("signal")
    
    # 均线排列
    if ma5 and ma20 and ma60:
        if ma5 > ma20 > ma60:
            trend_level = "bullish"
            trend_label = "多头排列"
        elif ma5 < ma20 < ma60:
            trend_level = "bearish"
            trend_label = "空头排列"
        else:
            trend_level = "neutral"
            trend_label = "均线纠缠"
    else:
        trend_level = "neutral"
        trend_label = "数据不足"
    
    # MACD
    if macd and signal:
        if macd > signal and macd > 0:
            macd_signal = "金叉看涨"
        elif macd < signal and macd < 0:
            macd_signal = "死叉看跌"
        else:
            macd_signal = "震荡"
    else:
        macd_signal = "数据不足"
    
    evidence = [f"MA5={ma5:.2f}" if ma5 else "MA5=N/A", 
                f"MA20={ma20:.2f}" if ma20 else "MA20=N/A",
                f"MA60={ma60:.2f}" if ma60 else "MA60=N/A",
                f"MACD={macd:.4f}" if macd else "MACD=N/A"]
    
    return {
        "level": trend_level,
        "label": trend_label,
        "evidence": evidence,
        "macd_signal": macd_signal
    }


def _analyze_momentum(data: dict) -> dict:
    """动量分析：RSI 超买超卖、KDJ。"""
    ind = (data or {}).get("indicators") or {}
    
    rsi = ind.get("rsi")
    
    if rsi is not None:
        if rsi >= 70:
            momentum_level = "bearish"
            momentum_label = f"RSI={rsi:.1f} 超买"
        elif rsi <= 30:
            momentum_level = "bullish"
            momentum_label = f"RSI={rsi:.1f} 超卖"
        else:
            momentum_level = "neutral"
            momentum_label = f"RSI={rsi:.1f} 中性"
    else:
        momentum_level = "neutral"
        momentum_label = "RSI 数据不足"
    
    return {
        "level": momentum_level,
        "label": momentum_label,
        "evidence": [f"RSI={rsi:.1f}" if rsi else "RSI=N/A"],
        "rsi": rsi
    }


def _analyze_volatility(data: dict) -> dict:
    """波动分析：ATR、标准差。"""
    points = (data or {}).get("data_points") or []
    
    if not points:
        return {"level": "neutral", "label": "数据不足", "evidence": []}
    
    closes = [p.get("close") for p in points if p.get("close")]
    if len(closes) < 2:
        return {"level": "neutral", "label": "数据不足", "evidence": []}
    
    # 计算日收益率标准差
    returns = []
    for i in range(1, len(closes)):
        if closes[i-1] > 0:
            returns.append((closes[i] - closes[i-1]) / closes[i-1])
    
    if returns:
        import statistics
        vol_std = statistics.stdev(returns) * 100
        if vol_std > 3:
            vol_level = "high"
            vol_label = f"高波动 ({vol_std:.2f}%)"
        elif vol_std > 1.5:
            vol_level = "medium"
            vol_label = f"中波动 ({vol_std:.2f}%)"
        else:
            vol_level = "low"
            vol_label = f"低波动 ({vol_std:.2f}%)"
    else:
        vol_level = "neutral"
        vol_label = "波动率计算失败"
    
    return {
        "level": vol_level,
        "label": vol_label,
        "evidence": [f"日波动率={vol_std:.2f}%" if returns else "波动率=N/A"],
        "vol_std": round(vol_std, 2) if returns else None
    }


def _analyze_volume_price(data: dict) -> dict:
    """量价分析：成交量变化、资金流向。"""
    points = (data or {}).get("data_points") or []
    
    if not points:
        return {"level": "neutral", "label": "数据不足", "evidence": []}
    
    # 最近5日均量 vs 前5日均量
    recent_vols = [p.get("volume", 0) for p in points[-5:] if p.get("volume")]
    prev_vols = [p.get("volume", 0) for p in points[-10:-5] if p.get("volume")]
    
    if recent_vols and prev_vols:
        avg_recent = sum(recent_vols) / len(recent_vols)
        avg_prev = sum(prev_vols) / len(prev_vols)
        
        if avg_prev > 0:
            vol_change = (avg_recent - avg_prev) / avg_prev * 100
            if vol_change > 20:
                vol_level = "increasing"
                vol_label = f"量能放大 {vol_change:.1f}%"
            elif vol_change < -20:
                vol_level = "decreasing"
                vol_label = f"量能萎缩 {abs(vol_change):.1f}%"
            else:
                vol_level = "stable"
                vol_label = f"量能稳定 ({vol_change:.1f}%)"
        else:
            vol_level = "neutral"
            vol_label = "量能比较失败"
    else:
        vol_level = "neutral"
        vol_label = "量能数据不足"
    
    # 价格趋势
    recent_closes = [p.get("close") for p in points[-5:] if p.get("close")]
    if len(recent_closes) >= 2:
        price_change = (recent_closes[-1] - recent_closes[0]) / recent_closes[0] * 100
        price_trend = "上涨" if price_change > 0 else "下跌"
    else:
        price_change = 0
        price_trend = "持平"
    
    return {
        "level": vol_level,
        "label": vol_label,
        "evidence": [f"量能变化={vol_change:.1f}%" if recent_vols and prev_vols else "量能=N/A",
                     f"价格趋势={price_trend} ({price_change:+.2f}%)"],
        "vol_change": round(vol_change, 2) if recent_vols and prev_vols else None,
        "price_change": round(price_change, 2)
    }
