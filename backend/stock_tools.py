#!/usr/bin/env python3
"""股票分析工具 - 行情获取、趋势分析、模拟交易"""

import json
import uuid
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import httpx
import yfinance as yf
import pandas as pd
from pathlib import Path

from common.db import get_db
from common.auth import require_auth
from common.llm import call_llm

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
    price: Optional[float] = None  # 如果不指定则用市价


# ══════════════════════════════════════════════════════════════
# 股票数据获取
# ══════════════════════════════════════════════════════════════

async def get_stock_data(symbol: str, period: str = "3mo") -> Dict:
    """获取股票历史数据"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period)
        
        if hist.empty:
            # 尝试提供可能的替代建议
            suggestions = {
                "GOOGLE": "GOOGL 或 GOOG", "APPLE": "AAPL", "AMAZON": "AMZN",
                "MICROSOFT": "MSFT", "FACEBOOK": "META", "TESLA": "TSLA",
                "NETFLIX": "NFLX", "ALIBABA": "BABA", "TENCENT": "0700.HK",
                "BYD": "1211.HK", "PINGDUODUO": "PDD",
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
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        
        # 布林带
        df['BB_middle'] = df['Close'].rolling(window=20).mean()
        df['BB_upper'] = df['BB_middle'] + 2 * df['Close'].rolling(window=20).std()
        df['BB_lower'] = df['BB_middle'] - 2 * df['Close'].rolling(window=20).std()
        
        # 转换为 JSON 格式
        data_points = []
        for idx, row in df.iterrows():
            data_points.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(float(row['Open']), 2),
                "high": round(float(row['High']), 2),
                "low": round(float(row['Low']), 2),
                "close": round(float(row['Close']), 2),
                "volume": int(row['Volume']),
                "ma5": round(float(row['MA5']), 2) if pd.notna(row['MA5']) else None,
                "ma20": round(float(row['MA20']), 2) if pd.notna(row['MA20']) else None,
                "ma60": round(float(row['MA60']), 2) if pd.notna(row['MA60']) else None,
                "rsi": round(float(row['RSI']), 2) if pd.notna(row['RSI']) else None,
                "macd": round(float(row['MACD']), 4) if pd.notna(row['MACD']) else None,
                "signal": round(float(row['Signal']), 4) if pd.notna(row['Signal']) else None,
            })
        
        # 最新数据
        latest = data_points[-1] if data_points else {}
        
        return {
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
            }
        }
    except HTTPException:
        raise  # 不要吞掉 HTTPException
    except Exception as e:
        raise HTTPException(500, f"获取股票数据失败: {str(e)}")


def analyze_stock_trend(data: Dict) -> str:
    """基于技术分析给出趋势判断"""
    indicators = data.get("indicators", {})
    rsi = indicators.get("rsi")
    macd = indicators.get("macd")
    ma5 = indicators.get("ma5")
    ma20 = indicators.get("ma20")
    ma60 = indicators.get("ma60")
    current = data.get("current_price", 0)
    
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


# ══════════════════════════════════════════════════════════════
# API 端点
# ══════════════════════════════════════════════════════════════

@router.get("/api/stock/search")
async def search_stock(q: str = Query(..., min_length=1), current_user: dict = require_auth()):
    """搜索股票"""
    try:
        # 使用 yfinance 搜索
        import yfinance as yf
        ticker = yf.Ticker(q.upper())
        info = ticker.info
        
        if not info or info.get("regularMarketPrice") is None:
            return {"results": []}
        
        return {
            "results": [{
                "symbol": q.upper(),
                "name": info.get("longName", info.get("shortName", q)),
                "exchange": info.get("exchange", ""),
                "type": info.get("quoteType", ""),
            }]
        }
    except Exception as e:
        return {"results": [], "error": str(e)}


@router.get("/api/stock/{symbol}")
async def get_stock(symbol: str, period: str = "3mo", current_user: dict = require_auth()):
    """获取股票详细数据"""
    data = await get_stock_data(symbol, period)
    data["trend_analysis"] = analyze_stock_trend(data)
    return data


@router.post("/api/stock/analyze")
async def analyze_stock(req: StockAnalysisRequest, current_user: dict = require_auth()):
    """AI 股票分析"""
    data = await get_stock_data(req.symbol, req.period)
    
    # 构建分析提示
    analysis_prompts = {
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
        
        "comprehensive": """你是一个资深的股票分析师。请综合技术面和基本面，给出全面的股票分析。

## 股票信息
- 代码：{symbol}
- 名称：{name}
- 当前价格：{current_price}
- 市值：{market_cap}
- 市盈率：{pe_ratio}

## 技术指标
- RSI: {rsi}
- MACD: {macd}
- 均线系统：MA5={ma5}, MA20={ma20}, MA60={ma60}

## 请给出综合分析
1. 整体趋势判断
2. 技术面分析
3. 基本面亮点与风险
4. 短期（1周）走势预判
5. 中期（1-3月）走势预判
6. 操作策略建议
7. 风险提示

⚠️ 免责声明：本分析仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。"""
    }
    
    prompt_template = analysis_prompts.get(req.analysis_type, analysis_prompts["comprehensive"])
    
    prompt = prompt_template.format(
        symbol=data["symbol"],
        name=data.get("name", ""),
        current_price=data.get("current_price", 0),
        **{"52w_high": data.get("52w_high", 0)},
        **{"52w_low": data.get("52w_low", 0)},
        rsi=data["indicators"].get("rsi", "N/A"),
        macd=data["indicators"].get("macd", "N/A"),
        ma5=data["indicators"].get("ma5", "N/A"),
        ma20=data["indicators"].get("ma20", "N/A"),
        ma60=data["indicators"].get("ma60", "N/A"),
        market_cap=data.get("market_cap", 0),
        pe_ratio=data.get("pe_ratio", 0),
        eps=data.get("eps", 0),
        dividend_yield=data.get("dividend_yield", 0),
        sector=data.get("sector", ""),
        industry=data.get("industry", ""),
    )
    
    try:
        result = call_llm(
            "你是一个专业的股票分析师，请基于数据给出客观、专业的分析。",
            prompt
        )
        
        # 保存分析记录
        conn = get_db()
        try:
            record_id = f"stock_analysis_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO stock_analyses (id, symbol, analysis_type, period, result, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (record_id, req.symbol, req.analysis_type, req.period, result, datetime.now().isoformat())
            )
            conn.commit()
        finally:
            conn.close()
        
        return {
            "ok": True,
            "id": record_id,
            "symbol": req.symbol,
            "analysis_type": req.analysis_type,
            "result": result,
            "data_summary": {
                "current_price": data.get("current_price"),
                "trend_analysis": data.get("trend_analysis"),
            }
        }
    except Exception as e:
        raise HTTPException(500, f"分析失败: {str(e)}")


@router.get("/api/stock/{symbol}/history")
async def get_stock_history(symbol: str, days: int = 30, current_user: dict = require_auth()):
    """获取股票历史数据（简化版）"""
    data = await get_stock_data(symbol, f"{days}d")
    return {
        "symbol": symbol,
        "data_points": data["data_points"],
    }


# ══════════════════════════════════════════════════════════════
# 模拟交易
# ══════════════════════════════════════════════════════════════

@router.get("/api/trading/portfolio")
async def get_portfolio(current_user: dict = require_auth()):
    """获取模拟交易投资组合"""
    user_id = current_user["id"]
    conn = get_db()
    try:
        # 获取账户信息
        account = conn.execute(
            "SELECT * FROM trading_accounts WHERE user_id=?", (user_id,)
        ).fetchone()
        
        if not account:
            # 创建默认账户
            account_id = f"acc_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO trading_accounts (id, user_id, cash, created_at)
                   VALUES (?,?,1000000,?)""",
                (account_id, user_id, datetime.now().isoformat())
            )
            conn.commit()
            account = {"id": account_id, "cash": 1000000, "total_value": 1000000}
        else:
            account = dict(account)
        
        # 获取持仓
        positions = []
        for row in conn.execute(
            "SELECT * FROM trading_positions WHERE account_id=?", (account["id"],)
        ).fetchall():
            pos = dict(row)
            # 获取当前价格
            try:
                data = await get_stock_data(pos["symbol"], "1d")
                pos["current_price"] = data.get("current_price", 0)
                pos["market_value"] = pos["current_price"] * pos["quantity"]
                pos["profit_loss"] = (pos["current_price"] - pos["avg_cost"]) * pos["quantity"]
                pos["profit_loss_pct"] = ((pos["current_price"] - pos["avg_cost"]) / pos["avg_cost"] * 100) if pos["avg_cost"] > 0 else 0
            except:
                pos["current_price"] = pos["avg_cost"]
                pos["market_value"] = pos["avg_cost"] * pos["quantity"]
                pos["profit_loss"] = 0
                pos["profit_loss_pct"] = 0
            positions.append(pos)
        
        # 获取交易历史
        trades = []
        for row in conn.execute(
            "SELECT * FROM trading_history WHERE account_id=? ORDER BY created_at DESC LIMIT 50",
            (account["id"],)
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
    user_id = current_user["id"]
    
    # 获取当前价格
    data = await get_stock_data(req.symbol, "1d")
    price = req.price or data.get("current_price", 0)
    
    if price <= 0:
        raise HTTPException(400, "无法获取股票价格")
    
    conn = get_db()
    try:
        # 获取账户
        account = conn.execute(
            "SELECT * FROM trading_accounts WHERE user_id=?", (user_id,)
        ).fetchone()
        
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
                "UPDATE trading_accounts SET cash=? WHERE id=?",
                (account["cash"] - trade_amount, account["id"])
            )
            
            # 更新或创建持仓
            existing = conn.execute(
                "SELECT * FROM trading_positions WHERE account_id=? AND symbol=?",
                (account["id"], req.symbol)
            ).fetchone()
            
            if existing:
                existing = dict(existing)
                new_qty = existing["quantity"] + req.quantity
                new_avg = (existing["avg_cost"] * existing["quantity"] + price * req.quantity) / new_qty
                conn.execute(
                    "UPDATE trading_positions SET quantity=?, avg_cost=? WHERE id=?",
                    (new_qty, new_avg, existing["id"])
                )
            else:
                pos_id = f"pos_{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """INSERT INTO trading_positions (id, account_id, symbol, quantity, avg_cost, created_at)
                       VALUES (?,?,?,?,?,?)""",
                    (pos_id, account["id"], req.symbol, req.quantity, price, datetime.now().isoformat())
                )
        
        elif req.action == "sell":
            # 卖出检查
            existing = conn.execute(
                "SELECT * FROM trading_positions WHERE account_id=? AND symbol=?",
                (account["id"], req.symbol)
            ).fetchone()
            
            if not existing or existing["quantity"] < req.quantity:
                raise HTTPException(400, "持仓不足")
            
            existing = dict(existing)
            
            # 更新现金
            conn.execute(
                "UPDATE trading_accounts SET cash=? WHERE id=?",
                (account["cash"] + trade_amount, account["id"])
            )
            
            # 更新持仓
            new_qty = existing["quantity"] - req.quantity
            if new_qty > 0:
                conn.execute(
                    "UPDATE trading_positions SET quantity=? WHERE id=?",
                    (new_qty, existing["id"])
                )
            else:
                conn.execute(
                    "DELETE FROM trading_positions WHERE id=?",
                    (existing["id"],)
                )
        
        # 记录交易
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO trading_history (id, account_id, symbol, action, quantity, price, amount, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (trade_id, account["id"], req.symbol, req.action, req.quantity, price, trade_amount, datetime.now().isoformat())
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
    user_id = current_user["id"]
    conn = get_db()
    try:
        # 删除旧账户和关联数据
        account = conn.execute(
            "SELECT id FROM trading_accounts WHERE user_id=?", (user_id,)
        ).fetchone()
        
        if account:
            conn.execute("DELETE FROM trading_positions WHERE account_id=?", (account["id"],))
            conn.execute("DELETE FROM trading_history WHERE account_id=?", (account["id"],))
            conn.execute("DELETE FROM trading_accounts WHERE id=?", (account["id"],))
        
        # 创建新账户
        account_id = f"acc_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO trading_accounts (id, user_id, cash, created_at)
               VALUES (?,?,1000000,?)""",
            (account_id, user_id, datetime.now().isoformat())
        )
        conn.commit()
        
        return {"ok": True, "message": "账户已重置，初始资金 100 万"}
    finally:
        conn.close()
