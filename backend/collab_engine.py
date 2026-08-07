#!/usr/bin/env python3
"""协作评论 + Skills 文件管理 API"""

import logging
import mimetypes
import uuid
from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

import skills_store
from common.db import get_db
from common.models import CommentCreateRequest, CommentLikeRequest, SkillFileWriteRequest

logger = logging.getLogger(__name__)
router = APIRouter(tags=["协作评论"])


# ══════════════════════════════════════════════════════════════
# 评论系统
# ══════════════════════════════════════════════════════════════


@router.get("/api/comments/thread")
async def get_comment_thread(target_type: str, target_id: str, user_id: str = ""):
    """获取评论线程（含回复树 + 点赞统计）"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM comments WHERE target_type=? AND target_id=? AND active=1 ORDER BY created_at ASC",
        (target_type, target_id),
    ).fetchall()
    comments = [dict(r) for r in rows]
    # 附加点赞统计
    for c in comments:
        cnt = conn.execute("SELECT COUNT(*) c FROM comment_likes WHERE comment_id=?", (c["id"],)).fetchone()["c"]
        c["likes"] = cnt
        c["liked"] = (
            bool(
                conn.execute(
                    "SELECT 1 FROM comment_likes WHERE comment_id=? AND user_id=?", (c["id"], user_id)
                ).fetchone()
            )
            if user_id
            else False
        )
    conn.close()
    # 构建树结构
    by_id = {}
    roots = []
    for c in comments:
        c["replies"] = []
        by_id[c["id"]] = c
    for c in comments:
        parent = c.get("parent_comment_id")
        if parent and parent in by_id:
            by_id[parent]["replies"].append(c)
        else:
            roots.append(c)
    return roots


@router.get("/api/comments")
async def list_comments(target_type: str = None, target_id: str = None, user_id: str = ""):
    """获取评论列表（平铺 + 点赞统计）"""
    conn = get_db()
    if target_type and target_id:
        rows = conn.execute(
            "SELECT * FROM comments WHERE target_type=? AND target_id=? AND active=1 ORDER BY created_at DESC",
            (target_type, target_id),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM comments WHERE active=1 ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        c = dict(r)
        c["likes"] = conn.execute("SELECT COUNT(*) c FROM comment_likes WHERE comment_id=?", (c["id"],)).fetchone()["c"]
        c["liked"] = (
            bool(
                conn.execute(
                    "SELECT 1 FROM comment_likes WHERE comment_id=? AND user_id=?", (c["id"], user_id)
                ).fetchone()
            )
            if user_id
            else False
        )
        result.append(c)
    conn.close()
    return result


@router.post("/api/comments")
async def create_comment(req: CommentCreateRequest):
    """创建评论"""
    if not req.content:
        raise HTTPException(400, "评论内容不能为空")
    if not req.target_type or not req.target_id:
        raise HTTPException(400, "target_type 和 target_id 不能为空")

    comment_id = f"cmt_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO comments (id, content, author_id, parent_comment_id, target_type, target_id, created_at, updated_at, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
        (comment_id, req.content, req.author_id, req.parent_comment_id, req.target_type, req.target_id, now, now),
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
async def like_comment(comment_id: str, req: CommentLikeRequest = None):
    """点赞评论"""
    user_id = (req or CommentLikeRequest()).user_id
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
# Skills 文件管理（标准目录结构：SKILL.md + scripts/references/examples/assets）
# ══════════════════════════════════════════════════════════════
# Skills 文件接口（文件系统语义）
# ══════════════════════════════════════════════════════════════


def _normalize_rel(raw: str) -> str:
    """规范化相对路径：拒绝绝对路径（/ 开头），交给 resolve_path 做防穿越校验。"""
    rel = (raw or "").strip().replace("\\", "/")
    if rel.startswith("/"):
        raise HTTPException(400, "path 不能是绝对路径")
    rel = rel.strip("/")
    if not rel or rel == ".":
        raise HTTPException(400, "path 不能为空")
    return rel


@router.get("/api/skills/{skill_id}/files/tree")
async def get_skill_file_tree(skill_id: str):
    """获取 Skill 目录树（递归）+ 分目录统计。"""
    try:
        return skills_store.list_tree(skill_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/skills/{skill_id}/file")
async def read_skill_file(skill_id: str, path: str = ""):
    """读取 Skill 文件内容（文本文件返回 content，二进制返回 is_text=False）。"""
    try:
        return skills_store.read_file(skill_id, path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/skills/{skill_id}/file/raw")
async def read_skill_file_raw(skill_id: str, path: str = ""):
    """读取原始文件字节流（图片/二进制预览）。"""
    try:
        target = skills_store.resolve_path(skill_id, path)
        if not target.is_file():
            raise HTTPException(404, f"文件不存在: {path}")
        data = target.read_bytes()
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    media_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)


@router.put("/api/skills/{skill_id}/file")
async def write_skill_file(skill_id: str, path: str, req: SkillFileWriteRequest):
    """新建/更新 Skill 文件（自动创建父目录）。编辑 SKILL.md 时同步 DB 元数据。"""
    rel = _normalize_rel(path)
    if rel.lower() == "skill.md":
        if not req.content.strip():
            raise HTTPException(400, "SKILL.md 内容不能为空")
        try:
            result = skills_store.write_file(skill_id, rel, req.content)
            skills_store.sync_db_from_skill_md(skill_id, req.content)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {**result, "synced_db": True}
    try:
        return skills_store.write_file(skill_id, rel, req.content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/api/skills/{skill_id}/file")
async def delete_skill_file(skill_id: str, path: str = ""):
    """删除 Skill 文件或目录（递归）。"""
    rel = _normalize_rel(path)
    try:
        skills_store.delete_path(skill_id, rel)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"success": True}


@router.post("/api/skills/{skill_id}/folder")
async def create_skill_folder(skill_id: str, path: str = ""):
    """创建目录（幂等）。"""
    rel = _normalize_rel(path)
    try:
        skills_store.mkdir(skill_id, rel)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"success": True}


@router.post("/api/skills/{skill_id}/upload")
async def upload_skill_file(
    skill_id: str,
    file: UploadFile = File(...),
    folder: str = Form(""),
):
    """上传单个文件到 Skill 指定目录（folder 如 scripts / references）。"""
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not filename:
        raise HTTPException(400, "文件名不能为空")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "文件不能超过 10MB")
    folder_raw = (folder or "").strip()
    if folder_raw.startswith("/"):
        raise HTTPException(400, "folder 不能是绝对路径")
    folder_clean = folder_raw.strip("/")
    rel = _normalize_rel(f"{folder_clean}/{filename}" if folder_clean else filename)
    try:
        return skills_store.write_file(skill_id, rel, content)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
