"""支付抽象层 — 商业闭环 P0（docs/commercialization.md）。

设计原则：
- 渠道插件化：PaymentProvider 协议（checkout / 验签 / 履约），新渠道零侵入接入
- 不做假实现：未接商户凭据的渠道显式 501（AlipayProvider.verify_webhook 抛 NotIntegrated）
- 幂等状态机：pending → paid → approved；approved 重放直接返回；rejected 不可再支付
- 金额不匹配 → 停留 paid 转人工审核（防 webhook 伪造自动开通）
- MockProvider 沙箱：HMAC 验签，测试/验收专用（APP_ENV=test/dev 默认启用）
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Protocol

from fastapi import HTTPException

MOCK_DEV_SECRET = "platform-dev-secret"  # 仅 test/dev 环境有效；生产必须 config 覆写


class NotIntegrated(Exception):
    """渠道未完成商户凭据集成，前端应展示「渠道即将支持」而非假成功。"""

    def __init__(self, provider: str, note: str = ""):
        self.provider = provider
        self.note = note
        super().__init__(f"{provider} 渠道尚未完成集成：{note}" if note else f"{provider} 渠道尚未完成集成")


class PaymentProvider(Protocol):
    """支付渠道协议。"""

    name: str

    def checkout(self, order: dict) -> dict:
        """生成支付指令（沙箱/二维码/收银台 URL）。"""
        ...

    def verify_webhook(self, payload: dict, sign: str) -> None:
        """验签；失败抛 401/400 级 HTTPException。"""
        ...


# ── 订单列迁移（旧库幂等补列）──────────────────────────────

_ORDER_EXTRA_COLS = {
    "payment_provider": "TEXT DEFAULT ''",
    "payment_ref": "TEXT DEFAULT ''",
    "paid_at": "TEXT DEFAULT ''",
}


def ensure_order_columns() -> None:
    """orders 表幂增支付列（ALTER TABLE ADD，存在则跳过）。"""
    from common.db import get_db_context

    with get_db_context() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(orders)").fetchall()}
        for col, ddl in _ORDER_EXTRA_COLS.items():
            if col not in cols:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {col} {ddl}")


# ── MockProvider（沙箱验收）────────────────────────────────


def _mock_enabled() -> bool:
    """test/dev/local（含未设 APP_ENV）默认启用沙箱渠道；生产必须 config 显式开启。"""
    from common.db import get_db_context

    env = os.environ.get("APP_ENV", "local")
    if env in ("test", "dev", "local"):
        return True
    try:
        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='payment_mock_enabled'").fetchone()
        return bool(row and row["value"] in ("1", "true"))
    except Exception:
        return False


def _mock_secret() -> str:
    from common.db import get_db_context

    try:
        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='mock_payment_secret'").fetchone()
        if row and row["value"].strip():
            return row["value"].strip()
    except Exception:
        pass
    # 生产环境拒绝默认密钥（防猜签）；test/dev 允许
    if os.environ.get("APP_ENV") == "production":
        raise HTTPException(500, "mock 支付密钥未配置（config: mock_payment_secret）")
    return MOCK_DEV_SECRET


class MockProvider:
    """沙箱渠道：HMAC-SHA256(order_id, secret) 验签，用于 E2E 验收与联调。"""

    name = "mock"

    def checkout(self, order: dict) -> dict:
        return {
            "provider": "mock",
            "order_id": order["id"],
            "amount": order.get("amount"),
            "hint": "沙箱模式：对 POST /api/orders/webhook 携带 X-Platform-Sign=HMAC(secret, order_id) 即视为付款成功",
        }

    def verify_webhook(self, payload: dict, sign: str) -> None:
        order_id = str(payload.get("order_id", ""))
        expected = hmac.new(_mock_secret().encode(), order_id.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sign or ""):
            raise HTTPException(401, "签名不匹配")


# ── AlipayProvider（契约骨架，runbook 见 docs/commercialization.md）──
#
# 待商户凭据（ALIPAY_APP_ID / ALIPAY_PRIVATE_KEY / ALIPAY_PUBLIC_KEY）到位后：
# 1) checkout: alipay.trade.face-to-face 当面付 → 返回二维码内容
# 2) verify_webhook: 支付宝异步通知 RSA2 验签（alipay_public_key 对 sign 字段）
# 3) 字段映射: out_trade_no=order_id, total_amount, trade_status=TRADE_SUCCESS
# 未到位时显式 501，不造假成功。


class AlipayProvider:
    name = "alipay"

    def checkout(self, order: dict) -> dict:
        raise NotIntegrated("alipay", "需商户 AppID + RSA2 密钥（.env），见 docs/commercialization.md Runbook")

    def verify_webhook(self, payload: dict, sign: str) -> None:
        raise NotIntegrated("alipay")


_PROVIDERS: dict[str, PaymentProvider] = {"mock": MockProvider(), "alipay": AlipayProvider()}


def get_provider(name: str) -> PaymentProvider:
    provider = _PROVIDERS.get(name)
    if not provider:
        raise HTTPException(404, f"未知支付渠道: {name}")
    if name == "mock" and not _mock_enabled():
        raise HTTPException(403, "mock 沙箱渠道未启用（config: payment_mock_enabled=1）")
    return provider


def mock_sign(order_id: str, secret: str = "") -> str:
    """对外暴露的沙箱签名工具（测试 / 运维验收用）。"""
    return hmac.new((secret or _mock_secret()).encode(), order_id.encode(), hashlib.sha256).hexdigest()


# ── 履约：mark_order_paid（幂等状态机）────────────────────


def _auto_activate() -> bool:
    """未配置时默认开启自动履约；显式 0/false 才关闭。"""
    from common.db import get_db_context

    try:
        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='payment_auto_activate'").fetchone()
        if row is None or not row["value"].strip():
            return True
        return row["value"].strip() in ("1", "true")
    except Exception:
        return True


def _expected_amount(order: dict) -> float:
    """订单应收金额：优先 original_amount-优惠券，其次 amount。"""
    amount = float(order.get("amount") or 0)
    original = order.get("original_amount")
    if order.get("coupon_code") and original:
        return amount  # amount 已是券后价
    return amount


def mark_order_paid(
    order_id: str, provider: str, ref: str, amount: float | None = None, source: str = "webhook"
) -> dict:
    """支付回调履约（幂等）：

    - approved：直接返回（重放不重复开通）
    - pending：验金额 → 匹配则自动开通（approved），不匹配停留 paid 转人工
    - paid（已提交凭证）：补支付字段，不重复开通
    - rejected：409 终态不可再支付
    """
    ensure_order_columns()
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "订单不存在")
        row = dict(row)
        if row["status"] == "approved":
            return dict(row)  # 幂等重放
        if row["status"] == "rejected":
            raise HTTPException(409, "订单已关闭，不可再支付")

        expected = _expected_amount(row)
        amount_ok = amount is None or abs(float(amount) - expected) < 0.005

        if row["status"] == "pending":
            conn.execute(
                """UPDATE orders SET status='paid', payment_provider=?, payment_ref=?, paid_at=? WHERE id=?""",
                (provider, ref, _now_iso(), order_id),
            )
            if amount_ok and _auto_activate():
                _activate_membership(conn, row, reviewer=f"auto:{provider}")
                conn.execute(
                    "UPDATE orders SET status='approved', reviewed_at=?, reviewed_by=? WHERE id=?",
                    (_now_iso(), f"auto:{provider}", order_id),
                )
            elif not amount_ok:
                # 金额不符：停留 paid 人工审核
                conn.execute(
                    "UPDATE orders SET remark=? WHERE id=?",
                    (f"[webhook:{provider}] 金额不符（应收 {expected} 实收 {amount}），转人工审核", order_id),
                )
            conn.commit()
        else:
            # paid（凭证通道在先）：仅补记支付来源，不重复开通
            conn.execute(
                """UPDATE orders SET payment_provider=?, payment_ref=?, paid_at=? WHERE id=?""",
                (provider, ref, _now_iso(), order_id),
            )
            conn.commit()
        return dict(conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    finally:
        conn.close()


def _activate_membership(conn, order_row: dict, reviewer: str) -> None:
    """开通会员（与 review_order(approve=True) 同一套 SQL，保持行为一致）。"""
    from datetime import datetime, timedelta

    from common.auth import MEMBERSHIP_PLANS

    plan = MEMBERSHIP_PLANS.get(order_row["plan"])
    if not plan:
        raise HTTPException(400, "套餐无效")
    expires = (datetime.now() + timedelta(days=plan["days"])).isoformat()
    conn.execute(
        "UPDATE users SET membership=?, membership_expires=?, daily_quota=? WHERE id=?",
        (order_row["plan"], expires, plan["daily_quota"], order_row["user_id"]),
    )


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat()
