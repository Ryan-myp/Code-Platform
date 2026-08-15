#!/usr/bin/env python3
"""API Key 独立计费系统。

为使用 API Key 调用的用户建立独立的配额和计费体系，与个人订阅配额隔离。

核心功能：
- API Key 创建/管理（支持按量付费和包月套餐）
- 独立配额扣减（不消耗个人订阅额度）
- 用量统计与账单
- 用量告警（低于阈值自动提醒）

环境变量：
  API_KEY_DEFAULT_RATE    — 按量付费单价（分/次，默认 5 分）
  API_KEY_PLAN_PRO_MONTHLY — 专业版 API 包月次数（默认 5000）
  API_KEY_PLAN_VIP_MONTHLY — 至尊版 API 包月次数（默认 50000）
"""

import logging
import os
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/api-key-billing", tags=["API Key 计费"])

# ── 配置 ──────────────────────────────────────────────────────
DEFAULT_RATE_PER_CALL = int(os.environ.get("API_KEY_DEFAULT_RATE", "5"))          # 5 分/次
PLAN_PRO_MONTHLY_CALLS = int(os.environ.get("API_KEY_PLAN_PRO_MONTHLY", "5000"))  # 5000 次/月
PLAN_VIP_MONTHLY_CALLS = int(os.environ.get("API_KEY_PLAN_VIP_MONTHLY", "50000")) # 50000 次/月
ALERT_THRESHOLD_PERCENT = int(os.environ.get("API_KEY_ALERT_THRESHOLD", "20"))    # 剩余 20% 时告警


class APIKeyCreateRequest(BaseModel):
    name: str
    plan: str = "pay_as_you_go"  # pay_as_you_go | pro | vip
    monthly_limit: int = 0       # 自定义月度限额（仅自定义计划）


class APIKeyUpdateRequest(BaseModel):
    name: str | None = None
    plan: str | None = None
    monthly_limit: int | None = None


# ══════════════════════════════════════════════════════════════
# Key 管理
# ══════════════════════════════════════════════════════════════


@router.get("")
async def list_keys(current_user: dict = require_auth()):
    """列出当前用户的所有 API Key。"""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT k.*, u.username as owner_name
               FROM api_key_billing k
               LEFT JOIN users u ON k.user_id = u.id
               WHERE k.user_id=?
               ORDER BY k.created_at DESC""",
            (current_user["user_id"],),
        ).fetchall()
        keys = [dict(r) for r in rows]
        # 附加本月用量
        now = datetime.now()
        month_start = now.replace(day=1).strftime("%Y-%m-%d %H:%M:%S")
        for k in keys:
            usage = conn.execute(
                """SELECT COALESCE(SUM(amount), 0) as total
                   FROM api_usage WHERE key_id=? AND created_at >= ?""",
                (k["id"], month_start),
            ).fetchone()
            k["usage_this_month"] = usage["total"] if usage else 0
        return {"keys": keys}
    finally:
        conn.close()


@router.post("")
async def create_key(req: APIKeyCreateRequest, current_user: dict = require_auth()):
    """创建新的 API Key。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        # 检查 Key 数量限制
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM api_key_billing WHERE user_id=? AND active=1", (user_id,)
        ).fetchone()
        if count["cnt"] >= 5:
            raise HTTPException(400, "最多创建 5 个 API Key")

        key_id = f"xt_{uuid.uuid4().hex[:20]}"
        plan = req.plan
        monthly_limit = req.monthly_limit or (PLAN_PRO_MONTHLY_CALLS if plan == "pro" else PLAN_VIP_MONTHLY_CALLS if plan == "vip" else 0)

        billing_id = f"key_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO api_key_billing (id, user_id, name, key_prefix, plan,
               monthly_limit, rate_per_call, remaining, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (billing_id, user_id, req.name, key_id[:8], plan,
             monthly_limit, DEFAULT_RATE_PER_CALL, monthly_limit, datetime.now().isoformat()),
        )
        conn.commit()

        return {
            "id": billing_id,
            "key": key_id,  # 仅创建时返回完整 key
            "name": req.name,
            "plan": plan,
            "monthly_limit": monthly_limit,
            "rate_per_call": DEFAULT_RATE_PER_CALL,
            "message": "API Key 创建成功，请妥善保管（仅显示一次）",
        }
    finally:
        conn.close()


@router.put("/{key_id}")
async def update_key(key_id: str, req: APIKeyUpdateRequest, current_user: dict = require_auth()):
    """更新 API Key 配置。"""
    conn = get_db()
    try:
        key = conn.execute("SELECT * FROM api_key_billing WHERE id=? AND user_id=?", (key_id, current_user["user_id"])).fetchone()
        key = dict(key) if key else None
        if not key:
            raise HTTPException(404, "Key 不存在")

        sets, params = [], []
        if req.name is not None:
            sets.append("name=?"); params.append(req.name)
        if req.plan is not None:
            sets.append("plan=?"); params.append(req.plan)
            # 切换套餐时重置月度限额
            if req.plan in ("pro", "vip"):
                new_limit = PLAN_PRO_MONTHLY_CALLS if req.plan == "pro" else PLAN_VIP_MONTHLY_CALLS
                sets.append("monthly_limit=?"); params.append(new_limit)
                sets.append("remaining=?"); params.append(new_limit)
        if req.monthly_limit is not None:
            sets.append("monthly_limit=?"); params.append(req.monthly_limit)

        if sets:
            params.append(key_id)
            conn.execute(f"UPDATE api_key_billing SET {', '.join(sets)} WHERE id=?", params)
            conn.commit()

        return {"message": "更新成功"}
    finally:
        conn.close()


@router.delete("/{key_id}")
async def delete_key(key_id: str, current_user: dict = require_auth()):
    """删除 API Key（软删除，active=0）。"""
    conn = get_db()
    try:
        result = conn.execute(
            "UPDATE api_key_billing SET active=0 WHERE id=? AND user_id=?",
            (key_id, current_user["user_id"]),
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Key 不存在")
        conn.commit()
        return {"message": "Key 已删除"}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 用量查询
# ══════════════════════════════════════════════════════════════


@router.get("/{key_id}/usage")
async def get_key_usage(key_id: str, current_user: dict = require_auth(), days: int = 30):
    """查询 API Key 用量详情。"""
    conn = get_db()
    try:
        key = conn.execute(
            "SELECT * FROM api_key_billing WHERE id=? AND user_id=?", (key_id, current_user["user_id"])
        ).fetchone()
        if not key:
            raise HTTPException(404, "Key 不存在")
        key = dict(key)

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        usage_rows = conn.execute(
            """SELECT DATE(created_at) as date, COALESCE(SUM(amount), 0) as calls
               FROM api_usage WHERE key_id=? AND created_at >= ?
               GROUP BY DATE(created_at) ORDER BY date DESC LIMIT ?""",
            (key_id, cutoff, days),
        ).fetchall()

        total_calls = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM api_usage WHERE key_id=?", (key_id,)
        ).fetchone()

        # 今日用量
        today = datetime.now().strftime("%Y-%m-%d")
        today_row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) as total FROM api_usage
               WHERE key_id=? AND created_at LIKE ?""",
            (key_id, f"{today}%"),
        ).fetchone()

        return {
            "key_name": key["name"],
            "plan": key["plan"],
            "monthly_limit": key["monthly_limit"],
            "remaining": key["remaining"],
            "usage_today": today_row["total"] if today_row else 0,
            "usage_this_month": total_calls["total"] if total_calls else 0,
            "daily_history": [dict(r) for r in usage_rows],
        }
    finally:
        conn.close()


@router.get("/{key_id}/billing")
async def get_key_billing(key_id: str, current_user: dict = require_auth(), months: int = 12):
    """查询 API Key 账单历史。"""
    conn = get_db()
    try:
        key = conn.execute(
            "SELECT * FROM api_key_billing WHERE id=? AND user_id=?", (key_id, current_user["user_id"])
        ).fetchone()
        if not key:
            raise HTTPException(404, "Key 不存在")
        key = dict(key)

        # 按月聚合账单
        bills = conn.execute(
            """SELECT strftime('%Y-%m', created_at) as month,
                      COALESCE(SUM(amount), 0) as total_calls,
                      COALESCE(SUM(amount) * rate_per_call / 100.0, 0) as estimated_cost
               FROM api_usage WHERE key_id=?
               GROUP BY strftime('%Y-%m', created_at)
               ORDER BY month DESC LIMIT ?""",
            (key_id, months),
        ).fetchall()

        return {
            "key_name": key["name"],
            "plan": key["plan"],
            "bills": [dict(r) for r in bills],
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 额度充值
# ══════════════════════════════════════════════════════════════


class TopUpRequest(BaseModel):
    amount: int  # 充值次数


@router.post("/{key_id}/topup")
async def topup_key(key_id: str, req: TopUpRequest, current_user: dict = require_auth()):
    """为 API Key 充值额度。"""
    conn = get_db()
    try:
        key = conn.execute(
            "SELECT * FROM api_key_billing WHERE id=? AND user_id=?", (key_id, current_user["user_id"])
        ).fetchone()
        if not key:
            raise HTTPException(404, "Key 不存在")
        key = dict(key)

        new_remaining = (key.get("remaining") or 0) + req.amount
        conn.execute(
            "UPDATE api_key_billing SET remaining=? WHERE id=?",
            (new_remaining, key_id),
        )
        conn.commit()

        return {"message": f"充值成功，新增 {req.amount} 次额度", "new_remaining": new_remaining}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 计费中间件钩子（供 task_queue 和 quota_middleware 调用）
# ══════════════════════════════════════════════════════════════


def consume_api_key_quota(key_id: str, amount: int = 1) -> dict:
    """从 API Key 扣减配额，返回结果。

    返回：{"allowed": bool, "remaining": int, "key_id": str}
    """
    conn = get_db()
    try:
        key = conn.execute("SELECT * FROM api_key_billing WHERE id=? AND active=1", (key_id,)).fetchone()
        key = dict(key) if key else None
        if not key:
            return {"allowed": False, "reason": "key_not_found", "key_id": key_id}

        # 包月计划：检查月度剩余
        if key["plan"] in ("pro", "vip") and key.get("monthly_limit"):
            now = datetime.now()
            month_start = now.replace(day=1).strftime("%Y-%m-%d %H:%M:%S")
            used_this_month = conn.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM api_usage WHERE key_id=? AND created_at >= ?",
                (key_id, month_start),
            ).fetchone()["total"]
            available = key["monthly_limit"] - used_this_month
            if available < amount:
                return {"allowed": False, "reason": "monthly_limit_exceeded", "key_id": key_id}
            remaining = available - amount
        else:
            # 按量付费：检查 key 级别剩余
            if (key.get("remaining") or 0) < amount:
                return {"allowed": False, "reason": "insufficient_balance", "key_id": key_id}
            remaining = (key.get("remaining") or 0) - amount

        # 扣减
        conn.execute(
            "UPDATE api_key_billing SET remaining=max(0, remaining-?) WHERE id=?",
            (amount, key_id),
        )
        # 记录 usage
        conn.execute(
            """INSERT INTO api_usage (id, key_id, amount, created_at)
               VALUES (?, ?, ?, ?)""",
            (f"au_{uuid.uuid4().hex[:12]}", key_id, amount, datetime.now().isoformat()),
        )
        conn.commit()

        # 检查告警阈值
        limit = key.get("monthly_limit") or 999999
        if limit > 0 and remaining / limit < ALERT_THRESHOLD_PERCENT / 100:
            logger.info("API Key %s 用量告警：剩余 %.1f%%", key_id, remaining / limit * 100)

        return {"allowed": True, "remaining": remaining, "key_id": key_id}
    except Exception as e:
        logger.error("consume_api_key_quota failed: %s", e)
        return {"allowed": False, "reason": "error", "key_id": key_id}
    finally:
        conn.close()


def refund_api_key_quota(key_id: str, amount: int = 1) -> bool:
    """API Key 退费（请求失败时回退）。"""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE api_key_billing SET remaining=remaining+? WHERE id=?", (amount, key_id)
        )
        # 删除最新的 api_usage 记录
        conn.execute(
            "DELETE FROM api_usage WHERE key_id=? ORDER BY created_at DESC LIMIT ?",
            (key_id, amount),
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def ensure_api_keys_tables():
    """确保 API Key 相关表存在。"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_key_billing (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                plan TEXT DEFAULT 'pay_as_you_go',
                monthly_limit INTEGER DEFAULT 0,
                rate_per_call INTEGER DEFAULT 5,
                remaining INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id TEXT PRIMARY KEY,
                key_id TEXT NOT NULL,
                amount INTEGER NOT NULL DEFAULT 1,
                endpoint TEXT,
                created_at TEXT,
                FOREIGN KEY (key_id) REFERENCES api_key_billing(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_billing_user ON api_key_billing(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_billing_active ON api_key_billing(active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_key ON api_usage(key_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_usage_time ON api_usage(created_at)")
        conn.commit()
    finally:
        conn.close()


__all__ = ["router", "consume_api_key_quota", "refund_api_key_quota", "ensure_api_keys_tables"]
