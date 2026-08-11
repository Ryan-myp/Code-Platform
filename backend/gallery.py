#!/usr/bin/env python3
"""作品广场 — 聚合各工厂产出的图片/视频/音频作品，支持点赞与评论。

- 作品源：artifacts 表中 type ∈ (image, video, audio) 且 active=1 的记录
- 点赞：work_likes 表（用户维度 toggle）
- 评论：复用 collab_engine 的 /api/comments（target_type='work'）
"""

import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gallery", tags=["作品广场"])

# 作品来源工厂 → 可读名称（artifacts.author 存的是模块名）
SOURCE_LABEL = {
    "image_factory": "图片工厂",
    "video_factory": "视频工厂",
    "music_factory": "音乐工厂",
    "voice_factory": "配音工坊",
    "meme_factory": "表情包工坊",
    "game_factory": "小游戏工坊",
    "miniapp": "小程序工坊",
    "publish": "发布中心",
    "short_drama": "短剧工厂",
    "digital_human": "数字人",
    "workflow": "工作流",
}
# Agent 产物的 author 形如 agent-1 / agent-2，统一展示为“AI Agent”
def _source_label(author: str) -> str:
    if not author:
        return "平台用户"
    if author.startswith("agent"):
        return "AI Agent"
    return SOURCE_LABEL.get(author, author)

# 作品类型 → 展示元信息
TYPE_META = {
    "image": {"label": "图片", "icon": "🖼️"},
    "video": {"label": "视频", "icon": "🎬"},
    "audio": {"label": "音频", "icon": "🎵"},
    "doc": {"label": "文档", "icon": "📄"},
}


def _media_file_exists(media_url: str) -> bool:
    """按 media_url 前缀定位后端目录，校验媒体文件是否真实存在（过滤历史孤儿记录）。

    未匹配已知前缀的记录视为存在（避免误伤其他来源）；文件已删除的孤儿记录不出现在广场。
    """
    if not media_url:
        return False
    base = os.path.join(os.path.dirname(__file__))
    for prefix, sub in (
        ("/api/video-factory/videos/", "video_factory"),
        ("/api/image-factory/images/", "image_factory"),
        ("/api/meme-factory/images/", "meme_factory"),
        ("/api/music-factory/", "music_factory"),
        ("/api/voice-factory/", "voice_factory"),
    ):
        if media_url.startswith(prefix):
            return os.path.exists(os.path.join(base, sub, media_url[len(prefix):]))
    return True


def _extract_prompt(content_raw: str) -> str:
    """从 content 字段提取作品描述：dict 取 prompt / 表情包文案 / filename，纯文本直接返回。"""
    if not content_raw:
        return ""
    try:
        obj = json.loads(content_raw)
        if isinstance(obj, dict):
            # 表情包：top_text + bottom_text 组合成可读标题，避免展示原始文件名
            if obj.get("top_text") or obj.get("bottom_text"):
                parts = [p for p in (obj.get("top_text"), obj.get("bottom_text")) if p]
                return " / ".join(parts)[:300]
            return obj.get("prompt") or obj.get("filename") or ""
        return str(obj)[:300]
    except Exception:
        return content_raw[:300]


def _decorate(row: dict, user_id: str) -> dict:
    """为作品行附加点赞数 / 评论数 / 当前用户点赞态。"""
    work_id = row["id"]
    conn = get_db()
    try:
        likes = conn.execute("SELECT COUNT(*) c FROM work_likes WHERE work_id=?", (work_id,)).fetchone()["c"]
        comments = conn.execute(
            "SELECT COUNT(*) c FROM comments WHERE target_type='work' AND target_id=? AND active=1",
            (work_id,),
        ).fetchone()["c"]
        liked = (
            conn.execute(
                "SELECT 1 FROM work_likes WHERE work_id=? AND user_id=?",
                (work_id, user_id),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()
    meta = TYPE_META.get(row.get("type", ""), {})
    # 视频封面：优先 artifacts.thumbnail；无则按 video_factory 规则推断封面 URL（缺封面后台会自动补生成）
    thumbnail = row.get("thumbnail") or ""
    if not thumbnail and row.get("type") == "video":
        media_url = row.get("media_url") or ""
        if "/video-factory/videos/" in media_url:
            stem = media_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            if stem:
                thumbnail = f"/api/video-factory/covers/{stem}.jpg"
    return {
        "id": work_id,
        "type": row.get("type", ""),
        "type_label": meta.get("label", row.get("type", "")),
        "icon": meta.get("icon", "📄"),
        "media_url": row.get("media_url") or "",
        "thumbnail": thumbnail,
        "duration": float(row.get("duration") or 0),
        "prompt": _extract_prompt(row.get("content")),
        "author": _source_label(row.get("author", "") or ""),
        "created_at": row.get("created_at", ""),
        "likes": likes,
        "comments": comments,
        "liked": liked,
    }


def _uid(current_user: dict) -> str:
    return current_user.get("user_id") or current_user.get("id") or "default"


@router.get("/works")
async def list_works(
    type: str = None,
    limit: int = 60,
    offset: int = 0,
    q: str = "",
    sort: str = "newest",
    author: str = "",
    current_user: dict = require_auth(),
):
    """作品列表：type 过滤 image/video/audio，q 搜索描述/作者，sort=最新/最热，author 按工厂筛选。"""
    user_id = _uid(current_user)
    conn = get_db()
    where = ["active=1"]
    params = []
    if type:
        where.append("type=?")
        params.append(type)
    else:
        where.append("type IN ('image','video','audio')")
    if q:
        where.append("(content LIKE ? OR author LIKE ?)")
        params.append(f"%{q}%")
        params.append(f"%{q}%")
    if author:
        where.append("author=?")
        params.append(author)
    if sort == "popular":
        # 最热：按点赞数倒序（子查询关联 work_likes）
        rows = conn.execute(
            "SELECT a.*, (SELECT COUNT(*) FROM work_likes wl WHERE wl.work_id=a.id) AS like_count "
            "FROM artifacts a WHERE " + " AND ".join(where) + " "
            "ORDER BY like_count DESC, a.created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM artifacts WHERE " + " AND ".join(where) + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
    conn.close()
    # 过滤媒体文件已删除的孤儿记录（避免破损封面/黑屏视频出现在广场）
    valid = [dict(r) for r in rows if _media_file_exists(r["media_url"] or "")]
    return [_decorate(row, user_id) for row in valid]


@router.get("/works/{work_id}")
async def get_work(work_id: str, current_user: dict = require_auth()):
    """作品详情（含点赞/评论统计）。"""
    user_id = _uid(current_user)
    conn = get_db()
    row = conn.execute("SELECT * FROM artifacts WHERE id=? AND active=1", (work_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "作品不存在")
    # 媒体文件已删除的孤儿记录视为不存在
    if not _media_file_exists(row["media_url"] or ""):
        raise HTTPException(404, "作品不存在")
    return _decorate(dict(row), user_id)


@router.post("/{work_id}/like")
async def toggle_work_like(work_id: str, current_user: dict = require_auth()):
    """点赞/取消点赞作品（toggle）。"""
    user_id = _uid(current_user)
    conn = get_db()
    exists = conn.execute("SELECT 1 FROM artifacts WHERE id=? AND active=1", (work_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(404, "作品不存在")
    row = conn.execute("SELECT 1 FROM work_likes WHERE work_id=? AND user_id=?", (work_id, user_id)).fetchone()
    if row:
        conn.execute("DELETE FROM work_likes WHERE work_id=? AND user_id=?", (work_id, user_id))
        liked = False
    else:
        conn.execute(
            "INSERT INTO work_likes (id, work_id, user_id, created_at) VALUES (?,?,?,?)",
            (f"wl_{uuid.uuid4().hex[:12]}", work_id, user_id, datetime.now().isoformat()),
        )
        liked = True
    count = conn.execute("SELECT COUNT(*) c FROM work_likes WHERE work_id=?", (work_id,)).fetchone()["c"]
    conn.commit()
    conn.close()
    return {"liked": liked, "likes": count}


@router.get("/stats")
async def gallery_stats(current_user: dict = require_auth()):
    """广场统计：作品数 / 点赞数 / 评论数 / 今日新增。"""
    conn = get_db()
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        works = conn.execute(
            "SELECT COUNT(*) c FROM artifacts WHERE type IN ('image','video','audio') AND active=1"
        ).fetchone()["c"]
        works_today = conn.execute(
            "SELECT COUNT(*) c FROM artifacts WHERE type IN ('image','video','audio') AND active=1 AND substr(created_at,1,10)=?",
            (today,),
        ).fetchone()["c"]
        likes = conn.execute("SELECT COUNT(*) c FROM work_likes").fetchone()["c"]
        comments = conn.execute("SELECT COUNT(*) c FROM comments WHERE target_type='work' AND active=1").fetchone()["c"]
        by_type = {}
        for t in ("image", "video", "audio"):
            by_type[t] = conn.execute("SELECT COUNT(*) c FROM artifacts WHERE type=? AND active=1", (t,)).fetchone()[
                "c"
            ]
    finally:
        conn.close()
    return {
        "works": works,
        "works_today": works_today,
        "likes": likes,
        "comments": comments,
        "by_type": by_type,
    }
