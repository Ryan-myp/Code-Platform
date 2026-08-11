#!/usr/bin/env python3
"""草稿箱 — 各工厂表单自动保存 / 恢复 / 清理。

页面在用户输入时防抖调用 save 接口落库（按 user + tool 唯一），
首页「草稿箱」聚合展示全部草稿，可恢复跳转或删除。
"""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["草稿箱"])

# 草稿所属工具的可读信息（供首页展示跳转）
TOOL_META = {
    "voice": {"label": "配音工坊", "path": "/voice-dubbing"},
    "meme": {"label": "表情包工坊", "path": "/meme"},
    "copywriting": {"label": "文案工厂", "path": "/copywriting"},
    "image": {"label": "图片工厂", "path": "/image-factory"},
    "video": {"label": "视频工厂", "path": "/video-factory"},
    "ppt": {"label": "PPT 工厂", "path": "/ppt-factory"},
    "publish": {"label": "发布中心", "path": "/publish"},
    "games": {"label": "小游戏工坊", "path": "/games"},
    "miniapp": {"label": "小程序工坊", "path": "/miniapp"},
}


class DraftSaveRequest(BaseModel):
    tool_id: str = Field(..., description="voice/meme/copywriting/…")
    title: str = Field("", max_length=200, description="草稿标题（表单摘要）")
    content: dict = Field(default_factory=dict, description="表单字段 JSON")


def _safe_load_content(raw: str) -> dict:
    """解析草稿 content 字段：脏数据（非法 JSON / 非对象）返回空 dict，避免列表接口 500。"""
    try:
        obj = json.loads(raw or "{}")
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@router.get("")
async def list_drafts(current_user: dict = require_auth()):
    """全部草稿（按更新时间倒序），附工具可读信息。"""
    user_id = current_user.get("user_id") or current_user.get("id") or "default"
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM drafts WHERE user_id=? ORDER BY updated_at DESC LIMIT 50",
        (user_id,),
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["content"] = _safe_load_content(d.get("content"))
        meta = TOOL_META.get(d["tool_id"], {})
        d["tool_label"] = meta.get("label", d["tool_id"])
        d["tool_path"] = meta.get("path", "")
        result.append(d)
    return result


@router.get("/{tool_id}")
async def get_draft(tool_id: str, current_user: dict = require_auth()):
    """获取某工具的最新草稿（无则 404）。"""
    user_id = current_user.get("user_id") or current_user.get("id") or "default"
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM drafts WHERE user_id=? AND tool_id=? ORDER BY updated_at DESC LIMIT 1",
        (user_id, tool_id),
    ).fetchone()
    conn.close()
    if not row:
        return None  # 无草稿返回 200 + null，避免前端轮询产生 404 控制台噪音
    d = dict(row)
    d["content"] = _safe_load_content(d.get("content"))
    meta = TOOL_META.get(d["tool_id"], {})
    d["tool_label"] = meta.get("label", d["tool_id"])
    d["tool_path"] = meta.get("path", "")
    return d


@router.post("/save")
async def save_draft(req: DraftSaveRequest, current_user: dict = require_auth()):
    """保存草稿（同 user+tool 覆盖更新）。"""
    user_id = current_user.get("user_id") or current_user.get("id") or "default"
    now = datetime.now().isoformat()
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM drafts WHERE user_id=? AND tool_id=?",
        (user_id, req.tool_id),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE drafts SET title=?, content=?, updated_at=? WHERE id=?",
            (req.title, json.dumps(req.content, ensure_ascii=False), now, row["id"]),
        )
        draft_id = row["id"]
    else:
        draft_id = f"draft_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO drafts (id, user_id, tool_id, title, content, updated_at) VALUES (?,?,?,?,?,?)",
            (draft_id, user_id, req.tool_id, req.title, json.dumps(req.content, ensure_ascii=False), now),
        )
    conn.commit()
    conn.close()
    return {"id": draft_id, "updated_at": now}


@router.delete("/{draft_id}")
async def delete_draft(draft_id: str, current_user: dict = require_auth()):
    user_id = current_user.get("user_id") or current_user.get("id") or "default"
    conn = get_db()
    conn.execute("DELETE FROM drafts WHERE id=? AND user_id=?", (draft_id, user_id))
    conn.commit()
    conn.close()
    return {"success": True}
