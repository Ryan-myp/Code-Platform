#!/usr/bin/env python3
"""协作评论 + Skills 文件管理 API"""

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["协作评论"])

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "platform.db"


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ══════════════════════════════════════════════════════════════
# 评论系统
# ══════════════════════════════════════════════════════════════

@router.get("/api/comments/thread")
async def get_comment_thread(target_type: str, target_id: str):
    """获取评论线程（含回复树）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM comments WHERE target_type=? AND target_id=? AND active=1 ORDER BY created_at ASC",
        (target_type, target_id),
    ).fetchall()
    conn.close()

    comments = [dict(r) for r in rows]
    # 构建树结构
    by_id = {}
    roots = []
    for c in comments:
        c["replies"] = []
        c["likes"] = 0
        by_id[c["id"]] = c
    for c in comments:
        parent = c.get("parent_comment_id")
        if parent and parent in by_id:
            by_id[parent]["replies"].append(c)
        else:
            roots.append(c)
    return roots


@router.get("/api/comments")
async def list_comments(target_type: str = None, target_id: str = None):
    """获取评论列表（平铺）"""
    conn = get_db()
    if target_type and target_id:
        rows = conn.execute(
            "SELECT * FROM comments WHERE target_type=? AND target_id=? AND active=1 ORDER BY created_at DESC",
            (target_type, target_id),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM comments WHERE active=1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/comments")
async def create_comment(req: dict):
    """创建评论"""
    content = (req.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "评论内容不能为空")
    target_type = req.get("target_type", "")
    target_id = req.get("target_id", "")
    if not target_type or not target_id:
        raise HTTPException(400, "target_type 和 target_id 不能为空")

    comment_id = f"cmt_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO comments (id, content, author_id, parent_comment_id, target_type, target_id, created_at, updated_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (comment_id, content, req.get("author_id", "admin"), req.get("parent_comment_id"),
         target_type, target_id, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": comment_id, "created_at": now}


@router.delete("/api/comments/{comment_id}")
async def delete_comment(comment_id: str):
    """删除评论"""
    conn = get_db()
    conn.execute("UPDATE comments SET active=0 WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/api/comments/{comment_id}/like")
async def like_comment(comment_id: str, req: dict = None):
    """点赞评论"""
    user_id = (req or {}).get("user_id", "admin")
    like_id = f"lk_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    existing = conn.execute(
        "SELECT * FROM comment_likes WHERE comment_id=? AND user_id=?", (comment_id, user_id)
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM comment_likes WHERE comment_id=? AND user_id=?", (comment_id, user_id))
        liked = False
    else:
        conn.execute(
            "INSERT INTO comment_likes (id, comment_id, user_id, created_at) VALUES (?, ?, ?, ?)",
            (like_id, comment_id, user_id, datetime.now().isoformat()),
        )
        liked = True
    count = conn.execute("SELECT COUNT(*) c FROM comment_likes WHERE comment_id=?", (comment_id,)).fetchone()["c"]
    conn.commit()
    conn.close()
    return {"liked": liked, "likes": count}


# ══════════════════════════════════════════════════════════════
# Skills 文件管理
# ══════════════════════════════════════════════════════════════

@router.get("/api/skills/{skill_id}/files")
async def list_skill_files(skill_id: str):
    """列出 Skill 的文件"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM skills_files WHERE skill_id=? ORDER BY folder, filename", (skill_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/skills/{skill_id}/files")
async def create_skill_file(skill_id: str, req: dict):
    """创建 Skill 文件"""
    filename = (req.get("filename") or "").strip()
    if not filename:
        raise HTTPException(400, "文件名不能为空")
    file_id = f"sf_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO skills_files (id, skill_id, folder, filename, content, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (file_id, skill_id, req.get("folder", "references"), filename, req.get("content", ""), now, now),
    )
    conn.commit()
    conn.close()
    return {"id": file_id, "filename": filename}


@router.put("/api/skills/{skill_id}/files/{file_id}")
async def update_skill_file(skill_id: str, file_id: str, req: dict):
    """更新 Skill 文件"""
    conn = get_db()
    conn.execute(
        "UPDATE skills_files SET content=?, updated_at=? WHERE id=? AND skill_id=?",
        (req.get("content", ""), datetime.now().isoformat(), file_id, skill_id),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@router.delete("/api/skills/{skill_id}/files/{file_id}")
async def delete_skill_file(skill_id: str, file_id: str):
    """删除 Skill 文件"""
    conn = get_db()
    conn.execute("DELETE FROM skills_files WHERE id=? AND skill_id=?", (file_id, skill_id))
    conn.commit()
    conn.close()
    return {"success": True}


@router.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, req: dict):
    """更新 Skill"""
    conn = get_db()
    fields = ["name", "description", "content", "references", "templates", "scripts", "assets"]
    updates = []
    vals = []
    for f in fields:
        if f in req:
            updates.append(f"{f}=?")
            v = req[f]
            vals.append(json.dumps(v) if isinstance(v, (list, dict)) else v)
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(skill_id)
    conn.execute(f"UPDATE skills SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": skill_id}
