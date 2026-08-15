#!/usr/bin/env python3
"""企业定制服务 API。

为 B 端客户提供：
- 私有化部署方案
- 定制开发服务
- 企业级功能（SSO、审计日志、SLA）
- 报价和合同管理
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from admin_api import _check_admin
from common.db import get_db
from common.auth import MEMBERSHIP_PLANS, ENTERPRISE_PRICING

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enterprise", tags=["企业服务"])


class EnterpriseInquiryRequest(BaseModel):
    company_name: str
    contact_name: str
    contact_email: str
    contact_phone: str = ""
    team_size: int  # 团队人数
    plan_tier: str = "standard"  # basic | standard | premium
    requirements: str = ""  # 需求描述
    expected_start: str = ""  # 期望启动时间


class EnterpriseInquiryResponse(BaseModel):
    inquiry_id: str
    estimated_setup_fee: int
    estimated_yearly_service: int
    estimated_total: int
    response_time: str  # 预计响应时间


# ══════════════════════════════════════════════════════════════
# 企业服务询价
# ══════════════════════════════════════════════════════════════


@router.post("/inquiry")
async def submit_inquiry(req: EnterpriseInquiryRequest, current_user: dict = require_auth()):
    """提交企业定制询价（管理员后续跟进）。"""
    conn = get_db()
    try:
        pricing = ENTERPRISE_PRICING.get(req.plan_tier, ENTERPRISE_PRICING["standard"])
        # 根据团队规模调整报价
        size_multiplier = max(1.0, req.team_size / 50.0)
        setup_fee = int(pricing["setup_fee"] * size_multiplier)
        yearly_service = int(pricing["yearly_service"] * size_multiplier)

        inquiry_id = f"ent_{uuid.uuid4().hex[:10]}"

        conn.execute(
            """INSERT INTO enterprise_inquiries (id, user_id, company_name, contact_name,
               contact_email, contact_phone, team_size, plan_tier, requirements,
               estimated_setup_fee, estimated_yearly_service, estimated_total,
               status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (inquiry_id, current_user["user_id"], req.company_name, req.contact_name,
             req.contact_email, req.contact_phone or "", req.team_size, req.plan_tier,
             req.requirements, setup_fee, yearly_service, setup_fee + yearly_service,
             datetime.now().isoformat()),
        )
        conn.commit()

        logger.info("企业询价提交: %s (%s) 团队 %d 人, 预计 ¥%d",
                     inquiry_id, req.company_name, req.team_size, setup_fee + yearly_service)

        return EnterpriseInquiryResponse(
            inquiry_id=inquiry_id,
            estimated_setup_fee=setup_fee,
            estimated_yearly_service=yearly_service,
            estimated_total=setup_fee + yearly_service,
            response_time="1-2 个工作日内",
        )
    finally:
        conn.close()


@router.get("/inquiries")
async def list_inquiries(current_user: dict = require_auth()):
    """列出所有企业询价（仅管理员）。"""
    from common.auth import _check_admin
    _check_admin(current_user)

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM enterprise_inquiries ORDER BY created_at DESC LIMIT 50"""
        ).fetchall()
        return {"inquiries": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.patch("/inquiries/{inquiry_id}")
async def update_inquiry_status(inquiry_id: str, status: str, current_user: dict = require_auth()):
    """更新询价状态（仅管理员）。"""
    from common.auth import _check_admin
    _check_admin(current_user)

    if status not in ("pending", "contacted", "quoted", "won", "lost"):
        raise HTTPException(400, "无效状态")

    conn = get_db()
    try:
        conn.execute(
            "UPDATE enterprise_inquiries SET status=? WHERE id=?",
            (status, inquiry_id),
        )
        conn.commit()
        return {"message": "状态已更新"}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 企业功能开关
# ══════════════════════════════════════════════════════════════


@router.get("/features")
async def get_enterprise_features(current_user: dict = require_auth()):
    """返回企业级功能清单及定价。"""
    return {
        "features": [
            {"id": "sso", "name": "SSO 单点登录", "description": "支持 SAML 2.0 / OAuth 2.0 企业认证", "available": True},
            {"id": "audit_log", "name": "审计日志", "description": "完整操作审计，保留 365 天", "available": True},
            {"id": "sla", "name": "SLA 保障", "description": "99.9% 可用性承诺，优先技术支持", "available": True},
            {"id": "private_deploy", "name": "私有化部署", "description": "全量代码部署至客户自有服务器", "available": True},
            {"id": "custom_branding", "name": "品牌定制", "description": "Logo/域名/界面白标", "available": True},
            {"id": "data_export", "name": "数据导出 API", "description": "批量导出业务数据", "available": True},
            {"id": "dedicated_support", "name": "专属技术支持", "description": "7×24 专属技术对接人", "available": True},
        ],
        "pricing_tiers": {
            tier: {"setup_fee": info["setup_fee"], "yearly_service": info["yearly_service"], "name": info["name"]}
            for tier, info in ENTERPRISE_PRICING.items()
        },
    }


def ensure_enterprise_tables():
    """确保企业服务相关表存在。"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS enterprise_inquiries (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                company_name TEXT NOT NULL,
                contact_name TEXT NOT NULL,
                contact_email TEXT NOT NULL,
                contact_phone TEXT DEFAULT '',
                team_size INTEGER DEFAULT 1,
                plan_tier TEXT DEFAULT 'standard',
                requirements TEXT DEFAULT '',
                estimated_setup_fee INTEGER,
                estimated_yearly_service INTEGER,
                estimated_total INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_enterprise_inquiries_status ON enterprise_inquiries(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_enterprise_inquiries_user ON enterprise_inquiries(user_id)")
        conn.commit()
    finally:
        conn.close()


__all__ = ["router"]
