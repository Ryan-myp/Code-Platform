#!/usr/bin/env python3
"""管理后台 API（v9.1 商业版）。

提供用户管理、使用统计、TOP 工具排行、活跃度曲线。
仅 admin 角色可访问（403 兜底）。
"""

import json
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import expire_stale_orders, require_auth, review_order
from common.db import get_db
from permissions import (
    PAGES,
    VISIBLE_TO_VALUES,
    build_permission_matrix,
    get_all_visibility,
    get_visibility_map,
    load_user_ctx,
    matrix_summary,
    set_visibility,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


def _check_admin(current_user: dict) -> None:
    """非 admin 角色一律拒绝。"""
    if (current_user.get("role") or "viewer") != "admin":
        raise HTTPException(403, "仅管理员可访问")


class AdminUserUpdateRequest(BaseModel):
    """管理员修改用户状态：会员等级 / 每日额度 / 启用状态 / 角色。"""

    membership: str | None = None
    daily_quota: int | None = None
    active: bool | None = None
    role: str | None = None


class ShareTestMarkRequest(BaseModel):
    """分享测试标记：is_test=True 隐藏（案例墙过滤），False 恢复。"""

    is_test: bool = True


@router.get("/stats")
async def admin_stats(current_user: dict = require_auth()):
    """总体统计：用户 / 调用 / 工具 / 分享。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        today_users = conn.execute(
            "SELECT COUNT(*) AS c FROM users WHERE substr(created_at, 1, 10)=?", (today,)
        ).fetchone()["c"]
        total_calls = conn.execute("SELECT COUNT(*) AS c FROM usage_logs").fetchone()["c"]
        today_calls = conn.execute(
            "SELECT COUNT(*) AS c FROM usage_logs WHERE substr(timestamp, 1, 10)=?", (today,)
        ).fetchone()["c"]
        # 今日活跃用户（usage_logs 有记录或今日有消耗额度）
        today_active = conn.execute(
            "SELECT COUNT(DISTINCT user_id) AS c FROM tool_usage_stats WHERE substr(last_used_at, 1, 10)=?",
            (today,),
        ).fetchone()["c"]
        total_shares = conn.execute("SELECT COUNT(*) AS c FROM shares").fetchone()["c"]
        total_views = conn.execute("SELECT COALESCE(SUM(views), 0) AS c FROM shares").fetchone()["c"]
        # 工具总数（tool_hub 定义）
        try:
            from tool_hub import TOOL_DEFINITIONS

            total_tools = len(TOOL_DEFINITIONS)
        except Exception:
            total_tools = 0
        # 会员分布
        membership_rows = conn.execute("SELECT membership, COUNT(*) AS c FROM users GROUP BY membership").fetchall()
        membership_dist = {r["membership"] or "free": r["c"] for r in membership_rows}
        return {
            "total_users": total_users,
            "today_users": today_users,
            "total_calls": total_calls,
            "today_calls": today_calls,
            "today_active": today_active,
            "total_shares": total_shares,
            "total_views": total_views,
            "total_tools": total_tools,
            "membership_dist": membership_dist,
        }
    finally:
        conn.close()


@router.get("/users")
async def admin_users(
    search: str = "",
    limit: int = 50,
    current_user: dict = require_auth(),
):
    """用户列表（支持关键词搜索 + 分页）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        sql = "SELECT * FROM users"
        params = []
        if search:
            sql += " WHERE username LIKE ? OR nickname LIKE ?"
            params = [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(min(limit, 200))
        rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d.pop("password_hash", None)  # 绝不返回密码哈希
            result.append(d)
        return result
    finally:
        conn.close()


@router.put("/users/{user_id}")
async def admin_update_user(  # noqa: C901
    user_id: str,
    req: AdminUserUpdateRequest,
    current_user: dict = require_auth(),
):
    """管理员调整用户会员等级 / 额度 / 启用状态 / 角色。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, "用户不存在")
        # 自我保护：不能修改自己的角色（防止误操作锁死系统）
        if req.role is not None and str(user_id) == str(current_user.get("user_id")):
            raise HTTPException(400, "不能修改自己的角色")
        sets, params = [], []
        if req.membership is not None:
            if req.membership not in ("free", "pro", "vip"):
                raise HTTPException(400, "无效会员等级")
            sets.append("membership=?")
            params.append(req.membership)
        if req.daily_quota is not None:
            if req.daily_quota < 0 or req.daily_quota > 100000:
                raise HTTPException(400, "额度范围无效")
            sets.append("daily_quota=?")
            params.append(req.daily_quota)
        if req.active is not None:
            sets.append("active=?")
            params.append(1 if req.active else 0)
        if req.role is not None:
            if req.role not in ("admin", "user", "viewer"):
                raise HTTPException(400, "无效角色")
            sets.append("role=?")
            params.append(req.role)
        if not sets:
            raise HTTPException(400, "无更新字段")
        params.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", params)
        conn.commit()
        return {"message": "用户已更新", "user_id": user_id}
    finally:
        conn.close()


@router.get("/visibility")
async def admin_visibility(
    type: str = "tool",
    current_user: dict = require_auth(),
):
    """内容可见性列表：工具或页面 + 当前可见范围。"""
    _check_admin(current_user)
    if type == "tool":
        try:
            from tool_hub import TOOL_DEFINITIONS

            items = [
                {"resource_id": tid, "name": t.get("name", tid), "category": t.get("category", "")}
                for tid, t in TOOL_DEFINITIONS.items()
            ]
        except Exception:
            items = []
    elif type == "page":
        items = [{"resource_id": p["id"], "name": p["label"], "category": p["path"]} for p in PAGES]
    else:
        raise HTTPException(400, "type 仅支持 tool / page")
    conf = get_all_visibility(type, [i["resource_id"] for i in items])
    conf_map = {c["resource_id"]: c["visible_to"] for c in conf}
    for i in items:
        i["visible_to"] = conf_map.get(i["resource_id"], "all")
    return items


class VisibilityUpdateRequest(BaseModel):
    """修改资源可见范围。"""

    resource_type: str
    resource_id: str
    visible_to: str


@router.put("/visibility")
async def admin_set_visibility(
    req: VisibilityUpdateRequest,
    current_user: dict = require_auth(),
):
    """设置工具/页面可见范围（灰度发布 / 上下线）。"""
    _check_admin(current_user)
    if req.resource_type not in ("tool", "page"):
        raise HTTPException(400, "resource_type 仅支持 tool / page")
    if req.visible_to not in VISIBLE_TO_VALUES:
        raise HTTPException(400, "无效的可见范围")
    set_visibility(req.resource_type, req.resource_id, req.visible_to)
    return {"message": "可见范围已更新", "resource_type": req.resource_type, "resource_id": req.resource_id}


@router.get("/permissions/matrix")
async def admin_permission_matrix(
    type: str = "page",
    user_id: str = "",
    current_user: dict = require_auth(),
):
    """角色-权限矩阵（v15）：查看指定用户视角下各资源的可见状态与权限来源。

    - type: page（独立页面）/ tool（效率工具）
    - user_id: 可选，不传则按当前管理员视角；传了则模拟该用户（用于排查会员权益）
    每项标注 source：role=管理员角色 / membership=会员等级 / config=后台配置 / default=默认公开
    """
    _check_admin(current_user)
    if type not in ("tool", "page"):
        raise HTTPException(400, "type 仅支持 tool / page")

    conn = get_db()
    try:
        if user_id:
            row = conn.execute("SELECT id, role, membership, membership_expires FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                raise HTTPException(404, "用户不存在")
            user_ctx = {
                "user_id": row["id"],
                "role": row["role"] or "viewer",
                "membership": row["membership"] or "free",
            }
            # 会员过期降级（与 load_user_ctx 一致）
            exp = row["membership_expires"]
            if user_ctx["membership"] != "free" and exp and exp <= datetime.now().isoformat():
                user_ctx["membership"] = "free"
        else:
            user_ctx = load_user_ctx(current_user)
    finally:
        conn.close()

    if type == "page":
        resources = PAGES
    else:
        try:
            from tool_hub import TOOL_DEFINITIONS

            resources = [{"id": t.get("id", tid), "label": t.get("name", tid), "category": t.get("category", "")} for tid, t in TOOL_DEFINITIONS.items()]
        except Exception:
            resources = []

    vis_map = get_visibility_map(type)
    items = build_permission_matrix(user_ctx, resources, vis_map)
    return {
        "user": user_ctx,
        "type": type,
        "items": items,
        "summary": matrix_summary(items),
        "legend": {
            "role": "管理员角色：全量放行",
            "membership": "会员等级：pro/vip 权益或锁定引导",
            "config": "后台显式配置的可见范围",
            "default": "未配置，默认公开",
            "hidden": "全站下线 / admin 专属",
        },
    }


@router.get("/top-tools")
async def admin_top_tools(
    days: int = 30,
    limit: int = 10,
    current_user: dict = require_auth(),
):
    """TOP 工具排行（按使用次数）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT tool_id, SUM(use_count) AS total, MAX(last_used_at) AS last_used
               FROM tool_usage_stats
               WHERE last_used_at >= ?
               GROUP BY tool_id ORDER BY total DESC LIMIT ?""",
            ((datetime.now() - timedelta(days=days)).isoformat(), min(limit, 50)),
        ).fetchall()
        # 关联工具名称
        names = {}
        try:
            from tool_hub import TOOL_DEFINITIONS

            names = {tid: t.get("name", tid) for tid, t in TOOL_DEFINITIONS.items()}
        except Exception:
            pass
        result = []
        for r in rows:
            result.append(
                {
                    "tool_id": r["tool_id"],
                    "name": names.get(r["tool_id"], r["tool_id"]),
                    "count": r["total"],
                    "last_used": r["last_used"],
                }
            )
        return result
    finally:
        conn.close()


@router.get("/orders")
async def admin_orders(status: str = "", current_user: dict = require_auth()):
    """订单列表（可按状态筛选），关联用户名。"""
    _check_admin(current_user)
    expire_stale_orders()  # 惰性关闭超时订单
    conn = get_db()
    try:
        sql = "SELECT o.*, u.username FROM orders o LEFT JOIN users u ON o.user_id = u.id"
        params: list = []
        if status:
            sql += " WHERE o.status=?"
            params.append(status)
        sql += " ORDER BY o.created_at DESC LIMIT 200"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class OrderReviewRequest(BaseModel):
    """订单审核：approve=True 开通会员，False 拒绝。"""

    approve: bool


@router.post("/orders/{order_id}/review")
async def admin_review_order(order_id: str, req: OrderReviewRequest, current_user: dict = require_auth()):
    """审核订单：通过自动开通对应会员（30 天）。"""
    _check_admin(current_user)
    return review_order(order_id, current_user.get("user_id") or "admin", req.approve)


@router.get("/activity")
async def admin_activity(
    days: int = 7,
    current_user: dict = require_auth(),
):
    """最近 N 天调用活跃度（按天聚合）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        since = (datetime.now() - timedelta(days=max(1, days) - 1)).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS calls
               FROM usage_logs WHERE timestamp >= ? GROUP BY day ORDER BY day""",
            (since,),
        ).fetchall()
        by_day = {r["day"]: r["calls"] for r in rows}
        # 补全无记录日期
        result = []
        for i in range(max(1, days)):
            d = (datetime.now() - timedelta(days=max(1, days) - 1 - i)).strftime("%Y-%m-%d")
            result.append({"day": d, "calls": by_day.get(d, 0)})
        return result
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 优惠券 / 折扣码管理（v9.4 营销）
# ══════════════════════════════════════════════════════════════

import uuid as _uuid  # noqa: E402


class CouponCreateRequest(BaseModel):
    """创建优惠券：固定金额或百分比折扣。"""

    code: str = ""  # 留空自动生成
    discount_type: str = "fixed"  # fixed / percent
    value: float = 10
    max_uses: int = 100
    expires_days: int = 0  # 0 = 永不过期
    active: bool = True


@router.get("/coupons")
async def admin_coupons(current_user: dict = require_auth()):
    """优惠券列表（含使用情况）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM coupons ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/coupons")
async def admin_create_coupon(req: CouponCreateRequest, current_user: dict = require_auth()):
    """创建优惠券；code 留空时自动生成（COUPON + 8 位随机大写）。"""
    _check_admin(current_user)
    if req.discount_type not in ("fixed", "percent"):
        raise HTTPException(400, "discount_type 仅支持 fixed / percent")
    if req.value <= 0 or (req.discount_type == "percent" and req.value >= 100):
        raise HTTPException(400, "折扣值无效：固定金额需 >0，百分比需在 0-100 之间")
    if req.max_uses <= 0:
        raise HTTPException(400, "使用次数需 >0")
    code = req.code.strip().upper() or f"COUPON{_uuid.uuid4().hex[:8].upper()}"
    expires_at = ""
    if req.expires_days > 0:
        expires_at = (datetime.now() + timedelta(days=req.expires_days)).isoformat()
    conn = get_db()
    try:
        dup = conn.execute("SELECT id FROM coupons WHERE code=?", (code,)).fetchone()
        if dup:
            raise HTTPException(400, "操作失败，请稍后重试")
        cid = f"coupon_{_uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO coupons (id, code, discount_type, value, max_uses, active, expires_at, created_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                cid,
                code,
                req.discount_type,
                req.value,
                req.max_uses,
                1 if req.active else 0,
                expires_at,
                datetime.now().isoformat(),
                current_user.get("username") or "admin",
            ),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM coupons WHERE id=?", (cid,)).fetchone())
    finally:
        conn.close()


@router.post("/coupons/{coupon_id}/toggle")
async def admin_toggle_coupon(coupon_id: str, current_user: dict = require_auth()):
    """启用 / 停用优惠券。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM coupons WHERE id=?", (coupon_id,)).fetchone()
        if not row:
            raise HTTPException(404, "优惠券不存在")
        new_active = 0 if row["active"] else 1
        conn.execute("UPDATE coupons SET active=? WHERE id=?", (new_active, coupon_id))
        conn.commit()
        return {"ok": True, "active": new_active}
    finally:
        conn.close()


@router.delete("/coupons/{coupon_id}")
async def admin_delete_coupon(coupon_id: str, current_user: dict = require_auth()):
    """删除优惠券。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM coupons WHERE id=?", (coupon_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "优惠券不存在")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 分享埋点统计（v9.4 渠道分析）
# ══════════════════════════════════════════════════════════════


@router.get("/share-stats")
async def admin_share_stats(current_user: dict = require_auth()):
    """每个分享的打开数 / 访问来源分布 / 注册转化率。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        shares = conn.execute(
            "SELECT id, share_code, title, content_type, views, created_at FROM shares ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for s in shares:
            sid = s["id"]
            visits = conn.execute("SELECT COUNT(*) AS c FROM share_visits WHERE share_id=?", (sid,)).fetchone()["c"]
            sources = conn.execute(
                """SELECT source, COUNT(*) AS c FROM share_visits WHERE share_id=?
                   GROUP BY source ORDER BY c DESC""",
                (sid,),
            ).fetchall()
            conversions = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE share_from=?", (s["share_code"],)
            ).fetchone()["c"]
            result.append(
                {
                    "id": sid,
                    "share_code": s["share_code"],
                    "title": s["title"] or f"{s['content_type']} 分享",
                    "views": s["views"],
                    "visits": visits,
                    "sources": [{"source": r["source"], "count": r["c"]} for r in sources],
                    "conversions": conversions,
                    "conversion_rate": round(conversions / visits * 100, 1) if visits else 0.0,
                    "created_at": s["created_at"],
                }
            )
        # 全局汇总
        total_visits = conn.execute("SELECT COUNT(*) AS c FROM share_visits").fetchone()["c"]
        total_conversions = conn.execute("SELECT COUNT(*) AS c FROM users WHERE share_from != ''").fetchone()["c"]
        return {
            "shares": result,
            "totals": {
                "visits": total_visits,
                "conversions": total_conversions,
                "conversion_rate": round(total_conversions / total_visits * 100, 1) if total_visits else 0.0,
            },
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 订单统计报表（v9.4 营收分析）
# ══════════════════════════════════════════════════════════════


@router.get("/order-stats")
async def admin_order_stats(days: int = 30, current_user: dict = require_auth()):
    """营收 / 转化率 / 客单价 + 按天营收趋势 + 套餐分布。"""
    _check_admin(current_user)
    expire_stale_orders()
    conn = get_db()
    try:
        approved = conn.execute("SELECT * FROM orders WHERE status='approved'").fetchall()
        revenue = round(sum(float(r["amount"] or 0) for r in approved), 2)
        discount = round(
            sum(float(r["original_amount"] or r["amount"] or 0) - float(r["amount"] or 0) for r in approved), 2
        )
        total_orders = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
        status_counts = {
            r["status"]: r["c"]
            for r in conn.execute("SELECT status, COUNT(*) AS c FROM orders GROUP BY status").fetchall()
        }
        # 转化率 = 已开通 / 总订单；客单价 = 已开通订单平均金额
        conversion_rate = round(len(approved) / total_orders * 100, 1) if total_orders else 0.0
        avg_order = round(revenue / len(approved), 2) if approved else 0.0
        # 近 N 天营收趋势（approved 订单按天聚合）
        since = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        trend_rows = conn.execute(
            """SELECT substr(reviewed_at, 1, 10) AS day, COUNT(*) AS orders, SUM(amount) AS revenue
               FROM orders WHERE status='approved' AND reviewed_at >= ? GROUP BY day""",
            (since,),
        ).fetchall()
        trend_map = {r["day"]: r for r in trend_rows}
        trend = []
        for i in range(days):
            d = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            r = trend_map.get(d)
            trend.append(
                {
                    "day": d,
                    "orders": r["orders"] if r else 0,
                    "revenue": round(float(r["revenue"] or 0), 2) if r else 0.0,
                }
            )
        # 套餐分布
        plan_dist = [
            {"plan": r["plan"], "orders": r["c"], "revenue": round(float(r["rev"] or 0), 2)}
            for r in conn.execute(
                """SELECT plan, COUNT(*) AS c, SUM(amount) AS rev FROM orders
                   WHERE status='approved' GROUP BY plan ORDER BY rev DESC"""
            ).fetchall()
        ]
        coupon_usage = conn.execute(
            "SELECT COUNT(*) AS c FROM orders WHERE coupon_code != '' AND status='approved'"
        ).fetchone()["c"]
        return {
            "revenue": revenue,
            "discount_total": discount,
            "total_orders": total_orders,
            "status_counts": status_counts,
            "conversion_rate": conversion_rate,
            "avg_order": avg_order,
            "trend": trend,
            "plan_dist": plan_dist,
            "coupon_orders": coupon_usage,
        }
    finally:
        conn.close()


@router.get("/shares")
async def admin_shares(
    search: str = "",
    limit: int = 50,
    current_user: dict = require_auth(),
):
    """分享内容治理列表（含测试标记，按浏览量倒序）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        sql = """SELECT s.id, s.share_code, s.title, s.content_type, s.views, s.is_test, s.created_at, u.username
                 FROM shares s JOIN users u ON u.id = s.user_id"""
        params: list = []
        if search:
            sql += " WHERE s.title LIKE ? OR u.username LIKE ?"
            params = [f"%{search}%", f"%{search}%"]
        sql += " ORDER BY s.views DESC, s.created_at DESC LIMIT ?"
        params.append(min(limit, 200))
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/shares/{share_id}/mark-test")
async def admin_mark_share_test(share_id: str, req: ShareTestMarkRequest, current_user: dict = require_auth()):
    """标记分享为测试内容（is_test=1，从案例墙隐藏）或恢复（is_test=0）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM shares WHERE id=?", (share_id,)).fetchone()
        if not row:
            raise HTTPException(404, "分享不存在")
        conn.execute("UPDATE shares SET is_test=? WHERE id=?", (1 if req.is_test else 0, share_id))
        conn.commit()
        return {"success": True, "id": share_id, "is_test": req.is_test}
    finally:
        conn.close()


@router.delete("/shares/{share_id}")
async def admin_delete_share(share_id: str, current_user: dict = require_auth()):
    """删除违规/测试分享（级联清理访问埋点）。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM shares WHERE id=?", (share_id,)).fetchone()
        if not row:
            raise HTTPException(404, "分享不存在")
        conn.execute("DELETE FROM shares WHERE id=?", (share_id,))
        conn.execute("DELETE FROM share_visits WHERE share_id=?", (share_id,))
        conn.commit()
        return {"success": True, "id": share_id}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 门户管理 API（v16.0）
# ══════════════════════════════════════════════════════════════

class AdminPortalUserUpdateRequest(BaseModel):
    """管理员批量设置用户门户类型。"""

    portal_type: str = Field(..., description="门户类型: rdm / media / general")
    user_ids: list[str] = Field(..., description="目标用户 ID 列表")


@router.get("/portals")
async def admin_list_portals(current_user: dict = require_auth()):
    """获取所有门户定义（管理后台用）。"""
    _check_admin(current_user)
    from portals import get_all_portals, PORTAL_DEFS

    db_portals = {p["id"]: p for p in get_all_portals()}
    result = []
    for pid, defn in PORTAL_DEFS.items():
        db = db_portals.get(pid, {})
        result.append({**defn, "db_updated_at": db.get("updated_at"), "db_created_at": db.get("created_at")})
    return {"portals": result}


@router.put("/portals/{portal_type}/pages")
async def admin_update_portal_pages(
    portal_type: str,
    page_ids: list[str],
    current_user: dict = require_auth(),
):
    """管理员修改门户的页面配置（启用/禁用特定页面）。"""
    _check_admin(current_user)
    from portals import PORTAL_DEFS

    if portal_type not in PORTAL_DEFS:
        raise HTTPException(404, "门户不存在")
    conn = get_db()
    try:
        # 先删除旧配置
        conn.execute("DELETE FROM portal_page_config WHERE portal_id=?", (portal_type,))
        # 写入新配置
        for page_id in page_ids:
            conn.execute(
                "INSERT INTO portal_page_config (portal_id, page_id, enabled) VALUES (?, ?, 1)",
                (portal_type, page_id),
            )
        # 同步更新数据库的 nav_groups 和 highlight_tools
        defn = PORTAL_DEFS[portal_type]
        conn.execute(
            "UPDATE portals SET nav_groups=?, highlight_tools=?, updated_at=? WHERE id=?",
            (
                json.dumps(defn["nav_groups"], ensure_ascii=False),
                json.dumps(defn["highlight_tools"], ensure_ascii=False),
                datetime.now().isoformat(),
                portal_type,
            ),
        )
        conn.commit()
        return {"message": f"门户 {portal_type} 页面配置已更新，共 {len(page_ids)} 个页面"}
    finally:
        conn.close()


@router.post("/users/portal-batch")
async def admin_batch_set_portal(
    req: AdminPortalUserUpdateRequest,
    current_user: dict = require_auth(),
):
    """批量设置用户门户类型。"""
    _check_admin(current_user)
    from portals import set_user_portal_type

    if req.portal_type not in ("rdm", "media", "general"):
        raise HTTPException(400, "无效门户类型")
    if not req.user_ids:
        raise HTTPException(400, "user_ids 不能为空")
    conn = get_db()
    try:
        updated = 0
        for uid in req.user_ids:
            try:
                row = conn.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone()
                if not row:
                    continue
                set_user_portal_type(uid, req.portal_type)
                updated += 1
            except Exception:
                continue
        conn.commit()
        return {"message": f"已更新 {updated} 个用户的门户类型", "updated": updated}
    finally:
        conn.close()


@router.get("/portals/stats")
async def admin_portal_stats(current_user: dict = require_auth()):
    """门户分布统计。"""
    _check_admin(current_user)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT portal_type, COUNT(*) AS cnt FROM users WHERE portal_type IS NOT NULL GROUP BY portal_type"
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()["cnt"]
        distribution = {r["portal_type"] or "general": r["cnt"] for r in rows}
        return {"total_users": total, "distribution": distribution}
    finally:
        conn.close()
