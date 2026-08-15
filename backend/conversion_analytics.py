#!/usr/bin/env python3
"""转化漏斗 & 商业化数据分析。

提供：
- 注册→付费转化率（Free → Pro → VIP）
- 试用到期流失分析
- 渠道归因（邀请码/分享链接来源）
- 月度 MRR/ARR 估算
- 用户留存 cohort 分析
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from common.auth import require_auth
from admin_api import _check_admin
from common.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["商业化分析"])


class FunnelSnapshot(BaseModel):
    registered_30d: int = 0
    trial_started_30d: int = 0
    paid_30d: int = 0
    pro_users: int = 0
    vip_users: int = 0
    free_users: int = 0
    churned_30d: int = 0


# ══════════════════════════════════════════════════════════════
# 转化漏斗
# ══════════════════════════════════════════════════════════════


@router.get("/api/analytics/funnel")
async def get_conversion_funnel(current_user: dict = require_auth()):
    """获取转化漏斗数据（仅管理员可见）。"""

    _check_admin(current_user)

    conn = get_db()
    try:
        now = datetime.now()
        thirty_days_ago = (now - timedelta(days=30)).isoformat()
        ninety_days_ago = (now - timedelta(days=90)).isoformat()

        # 注册数
        reg_30d = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE created_at >= ?", (thirty_days_ago,)
        ).fetchone()["cnt"]

        # 试用启动数（trial_expires 非空）
        trial_30d = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE trial_expires IS NOT NULL AND trial_expires != '' AND created_at >= ?",
            (thirty_days_ago,),
        ).fetchone()["cnt"]

        # 付费用户数
        paid_30d = conn.execute(
            """SELECT COUNT(*) as cnt FROM users
               WHERE (membership IN ('pro','vip') OR membership_expires IS NOT NULL)
               AND (membership_expires IS NULL OR membership_expires >= ?)""",
            (now.isoformat(),),
        ).fetchone()["cnt"]

        # 各层级用户分布
        tiers = conn.execute(
            """SELECT membership, COUNT(*) as cnt FROM users
               WHERE membership IS NOT NULL AND membership != ''
               GROUP BY membership"""
        ).fetchall()
        tier_map = {t["membership"]: t["cnt"] for t in tiers}

        # 近 30 天流失（曾为 pro/vip 现已 free）
        churned = conn.execute(
            """SELECT COUNT(*) as cnt FROM users
               WHERE membership='free' AND trial_expires IS NOT NULL
               AND trial_expires < ?""",
            (now.isoformat(),),
        ).fetchone()["cnt"]

        # 月度 MRR 估算（按实际订阅计算）
        pro_monthly = (tier_map.get("pro") or 0) * 1990 / 100  # 元
        vip_monthly = (tier_map.get("vip") or 0) * 9900 / 100
        mrr = pro_monthly + vip_monthly

        return {
            "snapshot": {
                "period": "last_30_days",
                "registered": reg_30d,
                "trial_started": trial_30d,
                "converted_to_paid": paid_30d,
                "churned": churned,
            },
            "tiers": {
                "free": tier_map.get("free", 0),
                "pro": tier_map.get("pro", 0),
                "vip": tier_map.get("vip", 0),
            },
            "conversion_rates": {
                "register_to_trial": round(trial_30d / max(reg_30d, 1) * 100, 1),
                "trial_to_paid": round(paid_30d / max(trial_30d, 1) * 100, 1),
                "register_to_paid": round(paid_30d / max(reg_30d, 1) * 100, 1),
            },
            "mrr_cny": round(mrr, 2),
            "arr_cny": round(mrr * 12, 2),
            "generated_at": now.isoformat(),
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 渠道归因
# ══════════════════════════════════════════════════════════════


@router.get("/api/analytics/channels")
async def get_channel_attribution(current_user: dict = require_auth()):
    """各获客渠道的用户分布和转化效果。"""

    _check_admin(current_user)

    conn = get_db()
    try:
        # 按邀请来源统计
        invite_stats = conn.execute(
            """SELECT
                  CASE WHEN invited_by IS NOT NULL AND invited_by != '' THEN 'invite'
                       WHEN share_from IS NOT NULL AND share_from != '' THEN 'share'
                       ELSE 'organic' END as channel,
                  COUNT(*) as registered,
                  COUNT(CASE WHEN membership IN ('pro','vip') THEN 1 END) as paid
               FROM users
               WHERE created_at >= date('now', '-90 days')
               GROUP BY channel"""
        ).fetchall()

        # 按分享来源统计（top 10）
        share_sources = conn.execute(
            """SELECT share_from, COUNT(*) as cnt
               FROM users
               WHERE share_from IS NOT NULL AND share_from != ''
               GROUP BY share_from ORDER BY cnt DESC LIMIT 10"""
        ).fetchall()

        return {
            "channels": [dict(r) for r in invite_stats],
            "top_share_sources": [dict(r) for r in share_sources],
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 留存 Cohort 分析
# ══════════════════════════════════════════════════════════════


@router.get("/api/analytics/retention")
async def get_retention_cohorts(current_user: dict = require_auth()):
    """按注册周计算的活跃留存率。"""

    _check_admin(current_user)

    conn = get_db()
    try:
        # 最近 8 周的 cohort
        cohorts = conn.execute(
            """SELECT
                  strftime('%Y-W%W', created_at) as week,
                  COUNT(*) as total,
                  COUNT(CASE WHEN last_active >= datetime('now', '-7 days') THEN 1 END) as active_7d,
                  COUNT(CASE WHEN last_active >= datetime('now', '-30 days') THEN 1 END) as active_30d
               FROM users
               WHERE created_at >= datetime('now', '-56 days')
               GROUP BY strftime('%Y-W%W', created_at)
               ORDER BY week DESC
               LIMIT 8"""
        ).fetchall()

        result = []
        for c in cohorts:
            total = c["total"] or 1
            result.append({
                "week": c["week"],
                "cohort_size": c["total"],
                "retention_7d": round(c["active_7d"] / total * 100, 1),
                "retention_30d": round(c["active_30d"] / total * 100, 1),
            })

        return {"cohorts": result}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 试用到期漏斗
# ══════════════════════════════════════════════════════════════


@router.get("/api/analytics/trial-expiry")
async def get_trial_expiry_pipeline(current_user: dict = require_auth()):
    """试用到期管道：即将到期 / 已到期 / 已转化的试用用户。"""

    _check_admin(current_user)

    conn = get_db()
    try:
        now = datetime.now()

        # 7 天内到期
        soon = conn.execute(
            """SELECT COUNT(*) as cnt FROM users
               WHERE membership='pro' AND trial_expires IS NOT NULL
               AND trial_expires BETWEEN ? AND ?""",
            (now.isoformat(), (now + timedelta(days=7)).isoformat()),
        ).fetchone()["cnt"]

        # 已到期未续费
        expired = conn.execute(
            """SELECT COUNT(*) as cnt FROM users
               WHERE (membership='free' OR membership_expires IS NULL OR membership_expires < ?)
               AND trial_expires IS NOT NULL AND trial_expires < ?""",
            (now.isoformat(), now.isoformat()),
        ).fetchone()["cnt"]

        # 已转化（试用后转为付费）
        converted = conn.execute(
            """SELECT COUNT(*) as cnt FROM users
               WHERE membership IN ('pro','vip') AND membership_expires > ?
               AND trial_expires IS NOT NULL
               AND trial_expires <= membership_expires""",
            (now.isoformat(),),
        ).fetchone()["cnt"]

        return {
            "expiring_in_7d": soon,
            "already_expired": expired,
            "converted_to_paid": converted,
            "conversion_rate": round(converted / max(converted + expired, 1) * 100, 1),
        }
    finally:
        conn.close()


def ensure_analytics_tables():
    """确保分析相关表存在（扩展 users 表以支持留存分析）。"""
    conn = get_db()
    try:
        # 为 users 表添加 last_active 字段（如果不存在）
        try:
            conn.execute("ALTER TABLE users ADD COLUMN last_active TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN share_from TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN ab_test_group TEXT")
        except Exception:
            pass
        # 模式 B：用户级中转站 key（用户自带 token，平台卖 token 盈利）
        try:
            conn.execute("ALTER TABLE users ADD COLUMN relay_api_key TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN relay_api_base TEXT DEFAULT ''")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


__all__ = ["router"]
