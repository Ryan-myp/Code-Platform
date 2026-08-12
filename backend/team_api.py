"""团队空间API — 团队管理、成员协作。"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from common.db import get_db
from common.llm import _safe_exc_msg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/teams", tags=["团队管理"])


class TeamCreateRequest(BaseModel):
    name: str
    description: str = ""


class TeamUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class MemberAddRequest(BaseModel):
    user_id: str
    role: str = "member"  # admin | member | viewer


@router.get("")
async def list_teams(current_user: dict = require_auth()):
    """获取当前用户的所有团队。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT t.*, tm.role as member_role, tm.joined_at
               FROM teams t
               JOIN team_members tm ON t.id = tm.team_id
               WHERE tm.user_id = ?
               ORDER BY t.created_at DESC""",
            (user_id,)
        ).fetchall()
        teams = [dict(r) for r in rows]
        return {"teams": teams, "total": len(teams)}
    finally:
        conn.close()


@router.post("")
async def create_team(req: TeamCreateRequest, current_user: dict = require_auth()):
    """创建新团队。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        team_id = f"team_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO teams (id, name, description, owner_id, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (team_id, req.name, req.description, user_id, datetime.now().isoformat()),
        )
        # 创建者自动成为管理员
        conn.execute(
            """INSERT INTO team_members (id, team_id, user_id, role, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"tm_{uuid.uuid4().hex[:12]}", team_id, user_id, "admin", datetime.now().isoformat()),
        )
        conn.commit()
        return {"id": team_id, "name": req.name, "message": "团队创建成功"}
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
            """SELECT u.id, u.username, u.nickname, tm.role, tm.joined_at
               FROM team_members tm
               JOIN users u ON tm.user_id = u.id
               WHERE tm.team_id=?
               ORDER BY tm.role DESC, tm.joined_at ASC""",
            (team_id,)
        ).fetchall()
        
        return {
            "team": dict(team),
            "members": [dict(r) for r in members],
            "member_count": len(members),
        }
    finally:
        conn.close()


@router.patch("/{team_id}")
async def update_team(team_id: str, req: TeamUpdateRequest, current_user: dict = require_auth()):
    """更新团队信息（仅管理员）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        # 检查权限
        member = conn.execute(
            "SELECT role FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, user_id)
        ).fetchone()
        if not member or member["role"] != "admin":
            raise HTTPException(403, "权限不足")
        
        updates = []
        params = []
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


@router.post("/{team_id}/members")
async def add_member(team_id: str, req: MemberAddRequest, current_user: dict = require_auth()):
    """添加团队成员（仅管理员）。"""
    user_id = current_user["user_id"]
    conn = get_db()
    try:
        # 检查权限
        member = conn.execute(
            "SELECT role FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, user_id)
        ).fetchone()
        if not member or member["role"] != "admin":
            raise HTTPException(403, "权限不足")
        
        # 检查用户是否存在
        user = conn.execute("SELECT id FROM users WHERE id=?", (req.user_id,)).fetchone()
        if not user:
            raise HTTPException(404, "用户不存在")
        
        # 检查是否已在团队中
        existing = conn.execute(
            "SELECT id FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, req.user_id)
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
        # 检查权限
        member = conn.execute(
            "SELECT role FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, admin_id)
        ).fetchone()
        if not member or member["role"] != "admin":
            raise HTTPException(403, "权限不足")
        
        # 不能移除自己
        if user_id == admin_id:
            raise HTTPException(400, "不能移除自己")
        
        conn.execute(
            "DELETE FROM team_members WHERE team_id=? AND user_id=?",
            (team_id, user_id)
        )
        conn.commit()
        return {"message": "成员已移除"}
    finally:
        conn.close()


def ensure_team_tables():
    """确保团队相关表存在。"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                owner_id TEXT NOT NULL,
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_owner ON teams(id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_team ON team_members(team_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_user ON team_members(user_id)")
        conn.commit()
    finally:
        conn.close()
