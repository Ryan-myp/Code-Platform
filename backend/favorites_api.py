"""收藏系统 — 收藏工具/记录/模板/作品，一键直达。

- POST   /api/favorites          添加收藏
- GET    /api/favorites          收藏列表（支持按类型筛选）
- DELETE /api/favorites/{id}     取消收藏
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/favorites", tags=["收藏"])

# 注意：favorites 表由 web_search.py init_db() 创建
# CREATE TABLE IF NOT EXISTS favorites (
#     id TEXT PRIMARY KEY,
#     user_id TEXT NOT NULL,
#     fav_type TEXT NOT NULL,
#     target_id TEXT NOT NULL,
#     label TEXT,
#     created_at TEXT NOT NULL,
#     UNIQUE(user_id, fav_type, target_id)
# )

# ── 模型 ──────────────────────────────────────────────────


class FavoriteRequest(BaseModel):
    fav_type: str = Field(..., description="收藏类型: tool/record/template/gallery")
    target_id: str = Field(..., description="目标ID")
    label: str = Field("", description="显示标签（可选）")


# ── API ──────────────────────────────────────────────────


@router.post("")
async def add_favorite(req: FavoriteRequest, current_user: dict = require_auth()):
    """添加收藏。"""
    user_id = current_user.get("user_id")
    fid = f"fav_{int(datetime.now().timestamp() * 1000)}"

    with get_db_context() as conn:
        try:
            conn.execute(
                "INSERT INTO favorites (id, user_id, fav_type, target_id, label, created_at) VALUES (?,?,?,?,?,?)",
                (fid, user_id, req.fav_type, req.target_id, req.label or "", datetime.now().isoformat()),
            )
        except Exception as e:
            raise HTTPException(400, "已收藏，请勿重复操作") from e

    return {"id": fid, "message": "收藏成功"}


@router.get("")
async def list_favorites(
    fav_type: str = Query("", description="筛选类型: tool/record/template/gallery"),
    current_user: dict = require_auth(),
):
    """收藏列表。"""
    user_id = current_user.get("user_id")
    with get_db_context() as conn:
        if fav_type:
            rows = conn.execute(
                "SELECT id, fav_type, target_id, label, created_at FROM favorites WHERE user_id=? AND fav_type=? ORDER BY created_at DESC LIMIT 100",
                (user_id, fav_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, fav_type, target_id, label, created_at FROM favorites WHERE user_id=? ORDER BY created_at DESC LIMIT 100",
                (user_id,),
            ).fetchall()

    return [{"id": r[0], "fav_type": r[1], "target_id": r[2], "label": r[3], "created_at": r[4]} for r in rows]


@router.delete("/{fav_id}")
async def remove_favorite(fav_id: str, current_user: dict = require_auth()):
    """取消收藏。"""
    user_id = current_user.get("user_id")
    with get_db_context() as conn:
        row = conn.execute("SELECT id FROM favorites WHERE id=? AND user_id=?", (fav_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, "收藏不存在或无权操作")
        conn.execute("DELETE FROM favorites WHERE id=?", (fav_id,))
    return {"message": "已取消收藏"}
