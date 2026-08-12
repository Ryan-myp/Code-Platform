"""用户反馈API — 收集用户反馈和建议。"""
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/feedback", tags=["用户反馈"])


class FeedbackCreateRequest(BaseModel):
    type: str = "feedback"  # feedback | bug | suggestion | praise
    title: str
    content: str
    category: str = ""  # tool | ui | performance | other
    contact: str = ""  # 可选联系方式


@router.post("")
async def submit_feedback(req: FeedbackCreateRequest, current_user: dict = require_auth()):
    """提交用户反馈。"""
    user_id = current_user.get("user_id", "")
    conn = get_db()
    try:
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO feedbacks (id, user_id, type, title, content, category, 
               contact, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (
                feedback_id, user_id, req.type, req.title, req.content,
                req.category, req.contact, datetime.now().isoformat(),
            ),
        )
        conn.commit()
        logger.info(f"Feedback submitted: {feedback_id} by {user_id}")
        return {"id": feedback_id, "message": "反馈提交成功，感谢您的建议！"}
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        raise HTTPException(500, "提交失败，请稍后重试")
    finally:
        conn.close()


@router.get("")
async def get_my_feedbacks(limit: int = 20, current_user: dict = require_auth()):
    """获取我的反馈记录。"""
    user_id = current_user.get("user_id", "")
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT * FROM feedbacks 
               WHERE user_id = ? 
               ORDER BY created_at DESC 
               LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return {"feedbacks": [dict(r) for r in rows], "total": len(rows)}
    finally:
        conn.close()


@router.get("/admin/all")
async def get_all_feedbacks(
    status: str = "",
    limit: int = 50,
    current_user: dict = require_auth(),
):
    """管理员查看所有反馈（仅管理员）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "权限不足")
    
    conn = get_db()
    try:
        where = "1=1"
        params = []
        if status:
            where += " AND status = ?"
            params.append(status)
        
        rows = conn.execute(
            f"SELECT * FROM feedbacks WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit]
        ).fetchall()
        return {"feedbacks": [dict(r) for r in rows], "total": len(rows)}
    finally:
        conn.close()


@router.patch("/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: str,
    status: str,
    current_user: dict = require_auth(),
):
    """更新反馈状态（仅管理员）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "权限不足")
    
    if status not in ("pending", "processing", "resolved", "closed"):
        raise HTTPException(400, "无效的状态值")
    
    conn = get_db()
    try:
        conn.execute(
            "UPDATE feedbacks SET status=? WHERE id=?",
            (status, feedback_id)
        )
        conn.commit()
        return {"success": True, "message": f"反馈状态已更新为: {status}"}
    finally:
        conn.close()


def ensure_feedback_table():
    """确保反馈表存在。"""
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedbacks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'feedback',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT '',
                contact TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_user ON feedbacks(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_status ON feedbacks(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedbacks_time ON feedbacks(created_at)")
        conn.commit()
    finally:
        conn.close()
    logger.info("Feedback table ensured")
