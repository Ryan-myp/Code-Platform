"""团队空间 API v2 — 团队管理、席位计费、管理员仪表盘。

v2 升级：
- 按席位计费（月度/年度）
- 团队管理员仪表盘（使用量/席位/账单）
- 团队订阅生命周期管理
- 邀请链接自动生成
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import MEMBERSHIP_PLANS, TEAM_SEAT_PRICING, require_auth
from common.db import get_db
from common.llm import _safe_exc_msg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/teams", tags=["团队管理"])


# ── 请求模型 ──────────────────────────────────────────────────

class TeamCreateRequest(BaseModel):
    name: str
    description: str = ""
    plan: str = "pro"  # pro | vip
    seats: int = 1     # 初始席位数量


class TeamUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class MemberAddRequest(BaseModel):
    user_id: str
    role: str = "member"  # admin | member | viewer


class SeatPurchaseRequest(BaseModel):
    seats: int = 1
    interval: str = "month"  # month | yearly


class RenewTeamRequest(BaseModel):
    interval: str = "month"  # month | yearly


# ══════════════════════════════════════════════════════════════
# 团队 CRUD
# ══════════════════════════════════════════════════════════════


@router.get("")
async def list_teams(current_user: dict = require_auth()):
    """获取当前用户的所有团队（含订阅状态）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT t.*, tm.role as member_role, tm.joined_at,
                      u.username as owner_name
               FROM teams t
               JOIN team_members tm ON t.id = tm.team_id
               LEFT JOIN users u ON t.owner_id = u.id
               WHERE tm.user_id = ?
               ORDER BY t.created_at DESC""",
            (user_id,),
        ).fetchall()
        teams = [dict(r) for r in rows]
        # 附加订阅摘要
        for t in teams:
            t["is_subscribed"] = bool(t.get("subscription_ends_at"))
            if t.get("subscription_ends_at"):
                try:
                    ends = datetime.fromisoformat(t["subscription_ends_at"])
                    t["days_remaining"] = max(0, (ends - datetime.now()).days)
                except (ValueError, TypeError):
                    t["days_remaining"] = 0
        return {"teams": teams, "total": len(teams)}
    finally:
        conn.close()


@router.post("")
async def create_team(req: TeamCreateRequest, current_user: dict = require_auth()):
    """创建新团队（创建者自动成为管理员和首個席位）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        team_id = f"team_{uuid.uuid4().hex[:12]}"

        # 验证席位数量
        if req.seats < 1 or req.seats > 100:
            raise HTTPException(400, "席位数量须在 1-100 之间")

        conn.execute(
            """INSERT INTO teams (id, name, description, owner_id, plan, seats,
               subscription_plan, subscription_interval, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (team_id, req.name, req.description, user_id, req.plan, req.seats,
             req.plan, "month", datetime.now().isoformat()),
        )
        # 创建者自动成为管理员 + 首個席位
        conn.execute(
            """INSERT INTO team_members (id, team_id, user_id, role, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"tm_{uuid.uuid4().hex[:12]}", team_id, user_id, "admin", datetime.now().isoformat()),
        )
        conn.commit()
        return {
            "id": team_id,
            "name": req.name,
            "message": "团队创建成功",
            "seats": req.seats,
            "plan": req.plan,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, _safe_exc_msg(e))
    finally:
        conn.close()


@router.get("/{team_id}")
async def get_team(team_id: str, current_user: dict = require_auth()):
    """获取团队详情及成员列表。"""
    conn = get_db()
    try:
        team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(404, "团队不存在")

        members = conn.execute(
            """SELECT u.id, u.username, u.nickname, u.avatar, tm.role, tm.joined_at
               FROM team_members tm
               JOIN users u ON tm.user_id = u.id
               WHERE tm.team_id=?
               ORDER BY tm.role DESC, tm.joined_at ASC""",
            (team_id,),
        ).fetchall()

        # 计算用量统计
        usage_stats = _get_team_usage_stats(conn, team_id)

        return {
            "team": dict(team),
            "members": [dict(r) for r in members],
            "member_count": len(members),
            "usage_stats": usage_stats,
        }
    finally:
        conn.close()


@router.patch("/{team_id}")
async def update_team(team_id: str, req: TeamUpdateRequest, current_user: dict = require_auth()):
    """更新团队信息（仅管理员）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, user_id):
            raise HTTPException(403, "权限不足")

        updates, params = [], []
        if req.name is not None:
            updates.append("name=?")
            params.append(req.name)
        if req.description is not None:
            updates.append("description=?")
            params.append(req.description)

        if updates:
            params.append(team_id)
            conn.execute(f"UPDATE teams SET {', '.join(updates)} WHERE id=?", params)
            conn.commit()

        return {"message": "更新成功"}
    finally:
        conn.close()


@router.delete("/{team_id}")
async def delete_team(team_id: str, current_user: dict = require_auth()):
    """删除团队（仅管理员，不可恢复）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, user_id):
            raise HTTPException(403, "权限不足")

        conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
        conn.commit()
        return {"message": "团队已删除"}
    finally:
        conn.close()


# ── 成员管理 ───────────────────────────────────────────────────

@router.post("/{team_id}/members")
async def add_member(team_id: str, req: MemberAddRequest, current_user: dict = require_auth()):
    """添加团队成员（仅管理员，受席位限制）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, user_id):
            raise HTTPException(403, "权限不足")

        # 检查席位上限
        team = conn.execute("SELECT seats FROM teams WHERE id=?", (team_id,)).fetchone()
        if team:
            current_members = conn.execute(
                "SELECT COUNT(*) as cnt FROM team_members WHERE team_id=?", (team_id,)
            ).fetchone()
            if current_members["cnt"] >= team["seats"]:
                raise HTTPException(400, f"席位已满（{team['seats']} 人），请先扩容")

        user = conn.execute("SELECT id FROM users WHERE id=?", (req.user_id,)).fetchone()
        if not user:
            raise HTTPException(404, "用户不存在")

        existing = conn.execute(
            "SELECT id FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, req.user_id),
        ).fetchone()
        if existing:
            raise HTTPException(400, "该用户已在团队中")

        conn.execute(
            """INSERT INTO team_members (id, team_id, user_id, role, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"tm_{uuid.uuid4().hex[:12]}", team_id, req.user_id, req.role, datetime.now().isoformat()),
        )
        conn.commit()
        return {"message": "成员添加成功"}
    finally:
        conn.close()


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(team_id: str, user_id: str, current_user: dict = require_auth()):
    """移除团队成员（仅管理员）。"""
    admin_id = current_user["user_id"]
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, admin_id):
            raise HTTPException(403, "权限不足")
        if user_id == admin_id:
            raise HTTPException(400, "不能移除自己")

        conn.execute("DELETE FROM team_members WHERE team_id=? AND user_id=?", (team_id, user_id))
        conn.commit()
        return {"message": "成员已移除"}
    finally:
        conn.close()


# ── 席位管理 ───────────────────────────────────────────────────

@router.post("/{team_id}/seats/purchase")
async def purchase_seats(team_id: str, req: SeatPurchaseRequest, current_user: dict = require_auth()):
    """购买额外席位（管理员操作）。"""
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, current_user["user_id"]):
            raise HTTPException(403, "权限不足")

        team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(404, "团队不存在")
        team = dict(team)

        pricing = TEAM_SEAT_PRICING.get(team["subscription_plan"] or "pro", TEAM_SEAT_PRICING["pro"])
        if req.interval == "yearly":
            unit_price = pricing["yearly"]
        else:
            unit_price = pricing["monthly"]

        total = unit_price * req.seats

        # 更新席位数
        new_seats = (team.get("seats") or 0) + req.seats
        conn.execute("UPDATE teams SET seats=? WHERE id=?", (new_seats, team_id))

        # 记录订单
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO orders (id, user_id, plan, amount, interval,
               status, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)""",
            (order_id, current_user["user_id"], f"team_seat_{team['subscription_plan']}",
             int(total * 100), req.interval,
             f'{{"team_id": "{team_id}", "seats": {req.seats}, "unit_price": {unit_price}}}',
             datetime.now().isoformat()),
        )
        conn.commit()

        return {
            "order_id": order_id,
            "new_seats": new_seats,
            "total_cents": int(total * 100),
            "currency": "cny",
            "message": "席位购买订单已创建，请在支付中心完成付款",
        }
    finally:
        conn.close()


@router.post("/{team_id}/seats/renew")
async def renew_team_subscription(team_id: str, req: RenewTeamRequest, current_user: dict = require_auth()):
    """续费团队订阅（延长到期时间）。"""
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, current_user["user_id"]):
            raise HTTPException(403, "权限不足")

        team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
        if not team:
            raise HTTPException(404, "团队不存在")
        team = dict(team)

        # 计算新的到期时间
        current_end = team.get("subscription_ends_at")
        if current_end:
            try:
                end_dt = datetime.fromisoformat(current_end)
                if end_dt > datetime.now():
                    # 未到期：在现有基础上延长
                    new_end = end_dt + (timedelta(days=365 if req.interval == "yearly" else 30))
                else:
                    new_end = datetime.now() + timedelta(days=365 if req.interval == "yearly" else 30)
            except (ValueError, TypeError):
                new_end = datetime.now() + timedelta(days=365 if req.interval == "yearly" else 30)
        else:
            new_end = datetime.now() + timedelta(days=365 if req.interval == "yearly" else 30)

        conn.execute(
            "UPDATE teams SET subscription_ends_at=?, subscription_interval=? WHERE id=?",
            (new_end.isoformat(), req.interval, team_id),
        )
        conn.commit()

        return {
            "message": "续费成功",
            "new_ends_at": new_end.isoformat(),
            "interval": req.interval,
        }
    finally:
        conn.close()


# ── 管理员仪表盘 ───────────────────────────────────────────────

@router.get("/{team_id}/dashboard")
async def get_team_dashboard(team_id: str, current_user: dict = require_auth()):
    """团队管理员仪表盘（使用量/席位/账单/成员活跃）。"""
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, current_user["user_id"]):
            raise HTTPException(403, "权限不足")

        usage = _get_team_usage_stats(conn, team_id)

        # 成员活跃统计
        members = conn.execute(
            """SELECT tm.role, COUNT(*) as cnt
               FROM team_members tm
               GROUP BY tm.role"""
        ).fetchall()
        role_stats = {r["role"]: r["cnt"] for r in members}

        # 近期账单
        now = datetime.now()
        month_start = now.replace(day=1).isoformat()
        bills = conn.execute(
            """SELECT * FROM orders
               WHERE metadata LIKE ? AND status IN ('paid','approved')
               ORDER BY created_at DESC LIMIT 10""",
            (f'%"team_id": "{team_id}"%',),
        ).fetchall()

        # 订阅状态
        team_row = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
        team = dict(team_row) if team_row else None
        sub_status = "active"
        if team and team.get("subscription_ends_at"):
            try:
                if datetime.fromisoformat(team["subscription_ends_at"]) < now:
                    sub_status = "expired"
            except (ValueError, TypeError):
                pass

        return {
            "team": dict(team) if team else {},
            "subscription_status": sub_status,
            "seats": {
                "total": team.get("seats", 0) if team else 0,
                "used": role_stats.get("member", 0) + role_stats.get("admin", 0),
                "available": (team.get("seats", 0) or 0) - sum(role_stats.values()),
            },
            "usage": usage,
            "role_stats": role_stats,
            "recent_bills": [dict(b) for b in bills],
        }
    finally:
        conn.close()


@router.get("/{team_id}/invite-link")
async def get_invite_link(team_id: str, current_user: dict = require_auth()):
    """生成团队邀请链接（管理员可用）。"""
    conn = get_db()
    try:
        if not _is_team_admin(conn, team_id, current_user["user_id"]):
            raise HTTPException(403, "权限不足")

        invite_code = f"TEAM_{team_id}_{uuid.uuid4().hex[:6].upper()}"
        conn.execute(
            "UPDATE teams SET invite_code=? WHERE id=?",
            (invite_code, team_id),
        )
        conn.commit()

        from common.config import is_production
        base_url = "https://xiaotuan.ai" if is_production() else "http://localhost:5173"
        return {
            "invite_code": invite_code,
            "invite_url": f"{base_url}/join-team/{invite_code}",
            "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════

def _is_team_admin(conn, team_id: str, user_id: str) -> bool:
    """检查用户是否为团队管理员。"""
    member = conn.execute(
        "SELECT role FROM team_members WHERE team_id=? AND user_id=?",
        (team_id, user_id),
    ).fetchone()
    return member and member["role"] in ("admin", "owner")


def _get_team_usage_stats(conn, team_id: str) -> dict:
    """获取团队使用量统计。"""
    try:
        # 今日总用量
        today = datetime.now().strftime("%Y-%m-%d")
        usage_row = conn.execute(
            """SELECT COALESCE(SUM(u.used_today), 0) as total_used
               FROM users u
               JOIN team_members tm ON u.id = tm.user_id
               WHERE tm.team_id=?""",
            (team_id,),
        ).fetchone()
        total_used = usage_row["total_used"] if usage_row else 0

        # 本月总用量
        month_start = datetime.now().replace(day=1).strftime("%Y-%m-%d")
        month_row = conn.execute(
            """SELECT COALESCE(SUM(u.total_usage), 0) as total
               FROM users u
               JOIN team_members tm ON u.id = tm.user_id
               WHERE tm.team_id=? AND u.created_at >= ?""",
            (team_id, month_start),
        ).fetchone()
        month_used = month_row["total"] if month_row else 0

        return {
            "today_used": total_used,
            "month_used": month_used,
            "avg_daily": round(month_used / max(1, datetime.now().day), 1),
        }
    except Exception:
        return {"today_used": 0, "month_used": 0, "avg_daily": 0}


def ensure_team_tables():
    """确保团队相关表存在（含新字段）。"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                owner_id TEXT NOT NULL,
                plan TEXT DEFAULT 'pro',
                seats INTEGER DEFAULT 1,
                subscription_plan TEXT DEFAULT 'pro',
                subscription_interval TEXT DEFAULT 'month',
                subscription_ends_at TEXT,
                subscription_id TEXT,
                invite_code TEXT,
                created_at TEXT,
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                team_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT DEFAULT 'member',
                joined_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                UNIQUE(team_id, user_id)
            )
        """)
        # 迁移：为新字段添加默认值（兼容旧数据库）
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN owner_id TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN plan TEXT DEFAULT 'pro'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN subscription_plan TEXT DEFAULT 'pro'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN subscription_interval TEXT DEFAULT 'month'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN seats INTEGER DEFAULT 1")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN subscription_ends_at TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE teams ADD COLUMN invite_code TEXT")
        except Exception:
            pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_owner ON teams(owner_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_id ON teams(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id)")
        # orders 表兼容迁移：补 interval/metadata 列（团队席位订单 & 支付模块共用）
        try:
            conn.execute("ALTER TABLE orders ADD COLUMN interval TEXT DEFAULT 'month'")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE orders ADD COLUMN metadata TEXT DEFAULT ''")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


# ── 公开接口：通过邀请码加入团队 ──────────────────────────────

@router.get("/join/{invite_code}")
async def join_team_by_code(invite_code: str, current_user: dict = require_auth()):
    """通过邀请码加入团队。"""
    conn = get_db()
    try:
        team = conn.execute(
            "SELECT * FROM teams WHERE invite_code=?", (invite_code,)
        ).fetchone()
        if not team:
            raise HTTPException(404, "邀请码无效")
        team = dict(team)

        # 检查是否已在团队中
        existing = conn.execute(
            "SELECT id FROM team_members WHERE team_id=? AND user_id=?",
            (team["id"], current_user["user_id"]),
        ).fetchone()
        if existing:
            raise HTTPException(400, "您已是该团队成员")

        # 检查席位
        current_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM team_members WHERE team_id=?", (team["id"],)
        ).fetchone()
        if current_count["cnt"] >= (team.get("seats") or 0):
            raise HTTPException(400, "团队席位已满")

        conn.execute(
            """INSERT INTO team_members (id, team_id, user_id, role, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"tm_{uuid.uuid4().hex[:12]}", team["id"], current_user["user_id"],
             "member", datetime.now().isoformat()),
        )
        # 清除已使用的邀请码
        conn.execute("UPDATE teams SET invite_code=NULL WHERE id=?", (team["id"],))
        conn.commit()

        return {"message": f"已成功加入团队「{team['name']}」", "team_id": team["id"]}
    finally:
        conn.close()
