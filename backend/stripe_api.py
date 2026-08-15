#!/usr/bin/env python3
"""Stripe 自动支付集成 v2 — 月付 + 年付 + 团队席位 + A/B 实验价格。

支持：
- 个人月付/年付订阅（年付享 83 折）
- 团队席位订阅（按人按月/年）
- A/B 实验价格覆盖
- Webhook 自动开通会员
- 订单状态同步

环境变量：
  STRIPE_SECRET_KEY          — Stripe 私钥（sk_live_...）
  STRIPE_WEBHOOK_SECRET      — Webhook 签名密钥（whsec_...）
  STRIPE_PRICE_PRO           — 专业版月付价格 ID
  STRIPE_PRICE_VIP           — 至尊版月付价格 ID
  STRIPE_PRICE_PRO_YEARLY    — 专业版年付价格 ID（可选，无则用月付 × 12）
  STRIPE_PRICE_VIP_YEARLY    — 至尊版年付价格 ID（可选，无则用月付 × 12）
  STRIPE_PRICE_TEAM_PRO      — 专业版团队席位月付价格 ID
  STRIPE_PRICE_TEAM_VIP      — 至尊版团队席位月付价格 ID
"""

import logging
import os
import time
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from common.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Stripe 支付"])

# ── Stripe 配置（运行时从环境变量读取）────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_VIP = os.environ.get("STRIPE_PRICE_VIP", "").strip()
STRIPE_PRICE_PRO_YEARLY = os.environ.get("STRIPE_PRICE_PRO_YEARLY", "").strip()
STRIPE_PRICE_VIP_YEARLY = os.environ.get("STRIPE_PRICE_VIP_YEARLY", "").strip()
STRIPE_PRICE_TEAM_PRO = os.environ.get("STRIPE_PRICE_TEAM_PRO", "").strip()
STRIPE_PRICE_TEAM_VIP = os.environ.get("STRIPE_PRICE_TEAM_VIP", "").strip()

# ── 本地价格配置（兜底，单位：分）─────────────────────────────
_PRICING = {
    "pro": {
        "amount": 1990,
        "currency": "cny",
        "interval": "month",
        "name": "专业版",
        "yearly_amount": 19900,  # 年付 199 元
    },
    "vip": {
        "amount": 9900,
        "currency": "cny",
        "interval": "month",
        "name": "至尊版",
        "yearly_amount": 99000,  # 年付 990 元
    },
    "team_pro": {
        "amount": 1500,
        "currency": "cny",
        "interval": "month",
        "name": "专业版席位",
        "yearly_amount": 14400,
    },
    "team_vip": {
        "amount": 7900,
        "currency": "cny",
        "interval": "month",
        "name": "至尊版席位",
        "yearly_amount": 79000,
    },
}


def _ensure_stripe():
    """确保 stripe 库已安装并配置。"""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(400, "Stripe 未配置，请联系管理员")
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise HTTPException(503, "Stripe SDK 未安装，请运行: pip install stripe")


# ── 请求模型 ──────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str  # pro | vip | team_pro | team_vip
    interval: str = "month"  # month | yearly
    quantity: int = 1  # 团队席位数量
    success_url: str = "http://localhost:5173/membership?paid=1"
    cancel_url: str = "http://localhost:5173/membership"
    team_id: str = ""  # 团队订阅时传入


class TeamBillingRequest(BaseModel):
    team_id: str
    seats: int  # 新增席位数量
    interval: str = "month"


# ══════════════════════════════════════════════════════════════
# 支付会话
# ══════════════════════════════════════════════════════════════


@router.post("/api/stripe/checkout")
async def create_checkout_session(req: CheckoutRequest, current_user: dict = require_auth()):
    """创建 Stripe 支付会话（支持月付/年付/团队席位）。"""
    import stripe

    plan = req.plan
    interval = req.interval

    if plan not in _PRICING:
        raise HTTPException(400, "无效的套餐类型")

    pricing = _PRICING[plan]
    amount = pricing["yearly_amount"] if interval == "yearly" else pricing["amount"]
    currency = pricing["currency"]
    plan_name = pricing["name"]

    # A/B 实验价格覆盖
    from common.auth import get_ab_pricing_override
    ab_override = get_ab_pricing_override(plan.split("_")[0])
    if ab_override:
        amount = ab_override

    success_url = req.success_url + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = req.cancel_url
    user_id = current_user.get("user_id", "")

    # 确定 Stripe 价格 ID
    if plan == "pro":
        price_id = STRIPE_PRICE_PRO_YEARLY if interval == "yearly" else STRIPE_PRICE_PRO
    elif plan == "vip":
        price_id = STRIPE_PRICE_VIP_YEARLY if interval == "yearly" else STRIPE_PRICE_VIP
    elif plan.startswith("team_"):
        base = plan.replace("team_", "")
        yearly_var = f"STRIPE_PRICE_TEAM_{base.upper()}_YEARLY"
        monthly_var = f"STRIPE_PRICE_TEAM_{base.upper()}"
        price_id = os.environ.get(yearly_var, "").strip() or os.environ.get(monthly_var, "").strip()
    else:
        price_id = None

    if not price_id:
        # 本地兜底：使用静态价格（用于测试环境）
        price_id = f"price_test_{plan}_{interval}"

    # 创建或获取 Stripe 客户
    existing = stripe.Customer.list(email=current_user.get("email"), limit=1)
    customer_id = existing.data[0].id if existing.data else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.get("email", ""),
            metadata={"user_id": user_id, "username": current_user.get("username", "")},
        )
        customer_id = customer.id

    # 构建行项目
    line_items = [{"price": price_id, "quantity": req.quantity}]

    # 团队订阅额外元数据
    metadata = {
        "user_id": user_id,
        "plan": plan,
        "interval": interval,
        "created_at": datetime.now().isoformat(),
    }
    if req.team_id:
        metadata["team_id"] = req.team_id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=line_items,
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
    )

    # 记录订单
    from common.db import get_db
    conn = get_db()
    try:
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO orders (id, user_id, plan, amount, currency, interval,
               stripe_session_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (order_id, user_id, plan, amount, currency, interval, session.id, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "order_id": order_id,
        "plan": plan,
        "interval": interval,
        "amount": amount,
        "currency": currency,
    }


@router.get("/api/stripe/session/{session_id}")
async def get_session_status(session_id: str, current_user: dict = require_auth()):
    """查询支付会话状态。"""
    import stripe

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            "status": session.status,
            "payment_status": session.payment_status,
            "customer_id": session.customer,
            "subscription_id": getattr(session, "subscription", None),
        }
    except Exception as e:
        raise HTTPException(404, f"会话不存在: {e}")


# ══════════════════════════════════════════════════════════════
# Webhook 处理（自动开通会员）
# ══════════════════════════════════════════════════════════════


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe Webhook — 自动开通会员 / 团队订阅。"""
    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(400, "无效 payload")
    except Exception:
        raise HTTPException(401, "签名验证失败")

    # 处理事件
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _activate_membership_from_session(session)
    elif event["type"] == "invoice.payment_succeeded":
        logger.info("Stripe 订阅续订成功")
    elif event["type"] == "invoice.payment_failed":
        logger.warning("Stripe 订阅续订失败，将触发降级流程")
        # TODO: 触发降级通知
    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        user_id = sub.get("metadata", {}).get("user_id", "")
        if user_id:
            await _deactivate_membership(user_id)

    return {"status": "ok"}


async def _activate_membership_from_session(session: dict) -> None:
    """从 Stripe 会话激活会员（个人 + 团队）。"""
    import stripe

    metadata = session.get("metadata", {})
    user_id = metadata.get("user_id", "")
    plan = metadata.get("plan", "pro")
    interval = metadata.get("interval", "month")
    subscription_id = session.get("subscription", "")
    team_id = metadata.get("team_id", "")

    if not user_id:
        logger.warning("Stripe 会话缺少 user_id，跳过激活")
        return

    # 计算到期时间
    try:
        days = 365 if interval == "yearly" else 30
        ends_at = datetime.now() + timedelta(days=days)
    except Exception:
        ends_at = datetime.now() + timedelta(days=30)

    from common.db import get_db

    conn = get_db()
    try:
        if team_id:
            # 团队订阅：更新团队席位数和到期时间
            conn.execute(
                """UPDATE teams SET subscription_id=?, subscription_plan=?,
                   subscription_interval=?, subscription_ends_at=? WHERE id=?""",
                (subscription_id, plan, interval, ends_at.isoformat(), team_id),
            )
            # 给团队所有者提升个人会员等级（团队订阅者享有对应个人权益）
            conn.execute(
                """UPDATE users SET membership=?, membership_expires=?, stripe_subscription_id=?
                   WHERE id=?""",
                (plan.replace("team_", ""), ends_at.isoformat(), subscription_id, user_id),
            )
        else:
            # 个人订阅
            conn.execute(
                """UPDATE users SET membership=?, membership_expires=?, stripe_subscription_id=?,
                   daily_quota=? WHERE id=?""",
                (plan, ends_at.isoformat(), subscription_id,
                 9999 if plan == "vip" else 200, user_id),
            )
        conn.commit()
        logger.info("用户 %s 会员已激活: %s (%s) 至 %s", user_id, plan, interval, ends_at.date())
    finally:
        conn.close()

    # 更新订单状态
    try:
        conn = get_db()
        conn.execute(
            "UPDATE orders SET status='paid', paid_at=? WHERE stripe_session_id=? AND status='pending'",
            (datetime.now().isoformat(), session.get("id", "")),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        if conn:
            conn.close()


async def _deactivate_membership(user_id: str) -> None:
    """订阅取消时降级用户。"""
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET membership='free', membership_expires=NULL, daily_quota=NULL WHERE id=?",
            (user_id,),
        )
        conn.commit()
        logger.info("用户 %s 会员已降级（订阅取消）", user_id)
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 价格配置查询（含 A/B 实验值）
# ══════════════════════════════════════════════════════════════


@router.get("/api/stripe/prices")
async def get_stripe_prices():
    """返回所有价格配置（前端展示用，含 A/B 实验覆盖）。"""
    from common.auth import AB_TEST_ENABLED, get_ab_pricing_override

    result = {}
    for key, pricing in _PRICING.items():
        base_plan = key.replace("team_", "")
        ab_override = get_ab_pricing_override(base_plan) if not key.startswith("team_") else None

        monthly_amount = ab_override if ab_override else pricing["amount"]
        yearly_amount = int(pricing["yearly_amount"] * 0.85)  # 年付额外 15% 折扣展示

        result[key] = {
            "amount": monthly_amount,
            "yearly_amount": yearly_amount,
            "currency": pricing["currency"],
            "interval": pricing["interval"],
            "name": pricing["name"],
            "price_id_monthly": _get_price_id(key, "month"),
            "price_id_yearly": _get_price_id(key, "yearly"),
            "save_percent": 17 if key.startswith("team_") else 17,
        }

    return {
        "plans": result,
        "ab_test_enabled": AB_TEST_ENABLED,
        "configured": bool(STRIPE_PRICE_PRO and STRIPE_PRICE_VIP),
    }


def _get_price_id(plan: str, interval: str) -> str:
    """根据 plan 和 interval 返回对应的 Stripe 价格 ID。"""
    if plan == "pro":
        return STRIPE_PRICE_PRO_YEARLY if interval == "yearly" else STRIPE_PRICE_PRO
    if plan == "vip":
        return STRIPE_PRICE_VIP_YEARLY if interval == "yearly" else STRIPE_PRICE_VIP
    if plan == "team_pro":
        return STRIPE_PRICE_TEAM_PRO  # 暂不支持团队年付价格 ID
    if plan == "team_vip":
        return STRIPE_PRICE_TEAM_VIP
    return ""


# ══════════════════════════════════════════════════════════════
# 订阅管理
# ══════════════════════════════════════════════════════════════


@router.get("/api/stripe/customer-portal")
async def get_customer_portal(current_user: dict = require_auth()):
    """获取用户 Stripe 客户门户 URL（自助管理订阅/取消）。"""
    import stripe

    try:
        _ensure_stripe()
        user_id = current_user.get("user_id")

        from common.db import get_db
        conn = get_db()
        try:
            order = conn.execute(
                "SELECT stripe_session_id FROM orders WHERE user_id=? AND status IN ('paid','approved') ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if not order or not order["stripe_session_id"]:
                return {"portal_url": None, "message": "暂无订阅记录"}
            session = stripe.checkout.Session.retrieve(order["stripe_session_id"])
            customer_id = session.customer
        finally:
            conn.close()

        portal = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url="http://localhost:5173/membership",
        )
        return {"portal_url": portal.url}
    except Exception as e:
        logger.warning("customer portal creation failed: %s", e)
        return {"portal_url": None, "message": str(e)}


# ══════════════════════════════════════════════════════════════
# 团队计费
# ══════════════════════════════════════════════════════════════


@router.post("/api/stripe/team-checkout")
async def create_team_checkout(req: TeamBillingRequest, current_user: dict = require_auth()):
    """创建团队席位支付会话。"""
    import stripe

    # 验证团队权限
    from common.db import get_db
    conn = get_db()
    try:
        member = conn.execute(
            "SELECT role FROM team_members WHERE team_id=? AND user_id=?",
            (req.team_id, current_user["user_id"]),
        ).fetchone()
        if not member or member["role"] not in ("admin", "owner"):
            raise HTTPException(403, "仅团队管理员可操作计费")

        team = conn.execute("SELECT * FROM teams WHERE id=?", (req.team_id,)).fetchone()
        if not team:
            raise HTTPException(404, "团队不存在")

        # 确定套餐
        plan = team.get("subscription_plan", "pro")
        pricing = _PRICING.get(f"team_{plan}", _PRICING["team_pro"])
        amount = pricing["yearly_amount"] if req.interval == "yearly" else pricing["amount"]
        amount *= req.seats  # 按席位数量计算

        # Stripe 价格 ID
        base = plan
        price_id = os.environ.get(f"STRIPE_PRICE_TEAM_{base.upper()}", "").strip()
        if not price_id:
            price_id = _get_price_id(f"team_{plan}", req.interval)

        if not price_id:
            raise HTTPException(400, "Stripe 团队价格 ID 未配置")

        # 创建/获取客户
        existing = stripe.Customer.list(email=current_user.get("email"), limit=1)
        customer_id = existing.data[0].id if existing.data else None
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.get("email", ""),
                metadata={"team_id": req.team_id, "admin_id": current_user["user_id"]},
            )
            customer_id = customer.id

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": req.seats}],
            mode="subscription",
            success_url=f"{req.success_url if hasattr(req, 'success_url') else 'http://localhost:5173/teams'}/?paid=1",
            cancel_url="http://localhost:5173/teams",
            metadata={
                "team_id": req.team_id,
                "plan": f"team_{plan}",
                "interval": req.interval,
                "seats": req.seats,
                "admin_id": current_user["user_id"],
                "created_at": datetime.now().isoformat(),
            },
        )

        # 记录订单
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO orders (id, user_id, plan, amount, currency, interval,
               stripe_session_id, status, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (order_id, current_user["user_id"], f"team_{plan}", amount,
             pricing["currency"], req.interval, session.id,
             f'{{"team_id": "{req.team_id}", "seats": {req.seats}}}',
             datetime.now().isoformat()),
        )
        conn.commit()
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "order_id": order_id,
            "amount": amount,
            "seats": req.seats,
        }
    finally:
        conn.close()


@router.get("/api/stripe/team-billing/{team_id}")
async def get_team_billing(team_id: str, current_user: dict = require_auth()):
    """获取团队计费信息（当前席位、到期时间、账单历史）。"""
    from common.db import get_db

    conn = get_db()
    try:
        # 验证成员权限
        member = conn.execute(
            "SELECT role FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, current_user["user_id"]),
        ).fetchone()
        if not member:
            raise HTTPException(403, "无权访问该团队")

        team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(404, "团队不存在")

        # 账单历史
        orders = conn.execute(
            """SELECT * FROM orders WHERE metadata LIKE ? AND status IN ('paid','approved')
               ORDER BY created_at DESC LIMIT 20""",
            (f'%"team_id": "{team_id}"%',),
        ).fetchall()

        return {
            "team": dict(team),
            "current_seats": team.get("seats", 0),
            "subscription_plan": team.get("subscription_plan", "pro"),
            "subscription_interval": team.get("subscription_interval", "month"),
            "subscription_ends_at": team.get("subscription_ends_at"),
            "billing_history": [dict(o) for o in orders],
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 促销码 & 优惠券
# ══════════════════════════════════════════════════════════════


@router.get("/api/stripe/coupon")
async def get_active_coupon():
    """返回当前 A/B 实验促销码（如有）。"""
    from common.auth import get_ab_discount_code

    code = get_ab_discount_code()
    if code:
        return {"code": code, "discount_percent": 20, "description": "限时促销优惠码"}
    return {"code": "", "discount_percent": 0, "description": ""}


__all__ = ["router"]
