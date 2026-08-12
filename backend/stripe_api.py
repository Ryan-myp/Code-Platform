#!/usr/bin/env python3
"""Stripe 自动支付集成。

支持：
- 创建支付会话（Payment Link）
- Webhook 处理（自动开通会员）
- 订单状态同步

环境变量：
  STRIPE_SECRET_KEY    — Stripe 私钥（sk_live_...）
  STRIPE_WEBHOOK_SECRET — Webhook 签名密钥（whsec_...）
  STRIPE_PRICE_PRO     — 专业版价格 ID（pricedata 或 price_...）
  STRIPE_PRICE_VIP     — 至尊版价格 ID
"""

import logging
import os
import time
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Query
from common.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Stripe 支付"])

# Stripe 配置（运行时从环境变量读取）
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
STRIPE_PRICE_PRO = os.environ.get("STRIPE_PRICE_PRO", "").strip()
STRIPE_PRICE_VIP = os.environ.get("STRIPE_PRICE_VIP", "").strip()

# 本地价格配置（兜底）
_PRICING = {
    "pro": {"amount": 1990, "currency": "cny", "interval": "month", "name": "专业版"},
    "vip": {"amount": 9900, "currency": "cny", "interval": "month", "name": "至尊版"},
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


# ══════════════════════════════════════════════════════════════
# 支付会话
# ══════════════════════════════════════════════════════════════


@router.post("/api/stripe/checkout")
async def create_checkout_session(req: dict, current_user: dict = require_auth()):
    """创建 Stripe 支付会话。

    请求体：
    - plan: "pro" | "vip"
    - success_url: 支付成功回调 URL
    - cancel_url: 支付取消回调 URL
    - client_reference_id: 可选，用户 ID 关联
    """
    import stripe

    plan = req.get("plan", "pro")
    if plan not in _PRICING:
        raise HTTPException(400, f"不支持的套餐: {plan}")

    success_url = req.get("success_url", "http://localhost:5173/membership?paid=1")
    cancel_url = req.get("cancel_url", "http://localhost:5173/membership")
    user_id = current_user.get("user_id", "")

    # 确定价格 ID
    price_id = (STRIPE_PRICE_PRO if plan == "pro" else STRIPE_PRICE_VIP) if plan in ("pro", "vip") else None
    if not price_id:
        raise HTTPException(400, "Stripe 价格 ID 未配置，请联系管理员")

    # 创建客户（如不存在）
    existing_customers = stripe.Customer.list(email=current_user.get("email"), limit=1)
    customer_id = existing_customers.data[0].id if existing_customers.data else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.get("email", ""),
            metadata={"user_id": user_id, "username": current_user.get("username", "")},
        )
        customer_id = customer.id

    # 创建会话
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        metadata={
            "user_id": user_id,
            "plan": plan,
            "created_at": datetime.now().isoformat(),
        },
    )

    return {"checkout_url": session.url, "session_id": session.id}


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
        }
    except stripe.error.InvalidRequestError:
        raise HTTPException(404, "会话不存在")


# ══════════════════════════════════════════════════════════════
# Webhook 处理（自动开通会员）
# ══════════════════════════════════════════════════════════════


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe Webhook — 自动开通会员。"""
    import stripe

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        raise HTTPException(400, "无效 payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(401, "签名验证失败")

    # 处理事件
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _activate_membership_from_session(session)
    elif event["type"] == "invoice.payment_succeeded":
        # 续订成功
        logger.info("Stripe 续订成功")
    elif event["type"] == "invoice.payment_failed":
        # 续订失败，通知用户
        logger.warning("Stripe 续订失败")

    return {"status": "ok"}


async def _activate_membership_from_session(session: dict) -> None:
    """从 Stripe 会话激活会员。"""
    import stripe

    user_id = session.get("metadata", {}).get("user_id", "")
    plan = session.get("metadata", {}).get("plan", "pro")
    subscription_id = session.get("subscription", "")

    if not user_id:
        logger.warning("Stripe 会话缺少 user_id，跳过激活")
        return

    # 通过 Stripe API 获取订阅详情
    try:
        sub = stripe.Subscription.retrieve(subscription_id)
        ends_at = datetime.fromtimestamp(sub.current_period_end)
    except Exception:
        # 兜底：默认 30 天
        ends_at = datetime.now() + timedelta(days=30)

    # 更新数据库
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute(
            """UPDATE users SET membership=?, membership_expires=?, stripe_subscription_id=?
               WHERE id=?""",
            (plan, ends_at.isoformat(), subscription_id, user_id),
        )
        conn.commit()
        logger.info(f"用户 {user_id} 会员已激活: {plan} 至 {ends_at.date()}")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 价格配置查询
# ══════════════════════════════════════════════════════════════


@router.get("/api/stripe/prices")
async def get_stripe_prices():
    """返回 Stripe 价格配置（前端展示用）。"""
    return {
        "pro": {
            "amount": _PRICING["pro"]["amount"],
            "currency": _PRICING["pro"]["currency"],
            "interval": _PRICING["pro"]["interval"],
            "name": _PRICING["pro"]["name"],
            "price_id": STRIPE_PRICE_PRO,
        },
        "vip": {
            "amount": _PRICING["vip"]["amount"],
            "currency": _PRICING["vip"]["currency"],
            "interval": _PRICING["vip"]["interval"],
            "name": _PRICING["vip"]["name"],
            "price_id": STRIPE_PRICE_VIP,
        },
        "configured": bool(STRIPE_PRICE_PRO and STRIPE_PRICE_VIP),
    }


# ══════════════════════════════════════════════════════════════
# 订阅管理
# ══════════════════════════════════════════════════════════════


@router.get("/api/stripe/customer-portal")
async def get_customer_portal(current_user: dict = require_auth()):
    """获取用户 Stripe 客户门户 URL（用于自助管理订阅/取消）。"""
    import stripe

    try:
        _ensure_stripe()
        user_id = current_user.get("user_id")
        # 查找该用户已有的 Stripe customer ID
        customers = stripe.Customer.list(email=None, limit=1, expand=["data.subscriptions"])
        # 通过订单关联查找 customer_id
        from common.db import get_db
        conn = get_db()
        try:
            order = conn.execute(
                "SELECT stripe_session_id FROM orders WHERE user_id=? AND status IN ('paid','approved') ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if order and order["stripe_session_id"]:
                session = stripe.checkout.Session.retrieve(order["stripe_session_id"])
                customer_id = session.customer
            else:
                return {"portal_url": None, "message": "暂无订阅记录"}
        finally:
            conn.close()
        portal = stripe.billing_portal.Session.create(customer=customer_id, return_url="http://localhost:5173/membership")
        return {"portal_url": portal.url}
    except Exception as e:
        logger.warning("customer portal creation failed: %s", e)
        return {"portal_url": None, "message": str(e)}


__all__ = ["router"]
