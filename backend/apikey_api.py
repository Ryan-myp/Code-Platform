"""对外API密钥管理 — 用户创建/管理自己的API Key。

- POST /api/api-keys       创建API Key
- GET  /api/api-keys       列表
- DELETE /api/api-keys/{id} 吊销
- GET  /api/open/docs      API文档概览
"""

import hashlib
import secrets
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["API密钥"])

# ── 模型 ──────────────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    label: str = Field("", max_length=100, description="备注标签（可选）")

# ── API文档定义 ─────────────────────────────────────────────
# 注意：web_search.py/batch_api.py/favorites_api.py 的 init_db() 已初始化 api_keys 表

API_DOCS = {
    "title": "小团智能平台 Open API",
    "version": "v1.0",
    "base_url": "https://platform.xiaotuan.ai/api",
    "auth": "Bearer Token (API Key)",
    "endpoints": [
        {
            "method": "POST",
            "path": "/api/chat/completions",
            "description": "LLM对话补全（兼容OpenAI格式）",
            "body": {"model": "xiaotuan-default", "messages": [{"role": "user", "content": "你好"}]},
        },
        {
            "method": "POST",
            "path": "/api/search/web",
            "description": "AI联网搜索",
            "body": {"query": "最新AI新闻"},
        },
        {
            "method": "POST",
            "path": "/api/batch/translate",
            "description": "批量翻译",
            "body": {"texts": ["Hello", "World"], "target_lang": "zh"},
        },
        {
            "method": "POST",
            "path": "/api/mindmap/generate",
            "description": "AI思维导图生成",
            "body": {"topic": "新能源汽车市场分析", "depth": 3},
        },
        {
            "method": "POST",
            "path": "/api/forecast/analyze",
            "description": "AI数据预测",
            "body": {"data_id": "data_xxx"},
        },
        {
            "method": "POST",
            "path": "/api/doc-qa/ask",
            "description": "文档智能问答",
            "body": {"doc_id": "doc_xxx", "question": "核心观点是什么？"},
        },
    ],
    "rate_limit": "1000 请求/天（会员5000/天）",
}


# ── API ──────────────────────────────────────────────────

@router.post("/api-keys")
async def create_api_key(req: ApiKeyCreateRequest, current_user: dict = require_auth()):
    """创建个人API Key（完整Key仅返回一次，请妥善保存）。"""
    user_id = current_user.get("user_id")
    raw_key = f"xt-{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    kid = f"apikey_{int(datetime.now().timestamp()*1000)}"
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, label, created_at) VALUES (?,?,?,?,?,?)",
            (kid, user_id, key_hash, key_prefix, req.label or "", datetime.now().isoformat()),
        )

    return {
        "id": kid,
        "api_key": raw_key,
        "prefix": key_prefix,
        "label": req.label,
        "message": "API Key 创建成功！请立即复制保存，后续无法再次查看完整Key。",
    }


@router.get("/api-keys")
async def list_api_keys(current_user: dict = require_auth()):
    """列出我的API Keys。"""
    user_id = current_user.get("user_id")
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, key_prefix, label, last_used, created_at FROM api_keys WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()

    return [{"id": r[0], "prefix": r[1], "label": r[2], "last_used": r[3], "created_at": r[4]} for r in rows]


@router.delete("/api-keys/{key_id}")
async def delete_api_key(key_id: str, current_user: dict = require_auth()):
    """吊销API Key。"""
    user_id = current_user.get("user_id")
    with get_db_context() as conn:
        row = conn.execute("SELECT id FROM api_keys WHERE id=? AND user_id=?", (key_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, "API Key不存在或无权操作")
        conn.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
    return {"message": "API Key已吊销"}


@router.get("/open/docs")
async def api_docs(current_user: dict = require_auth()):
    """获取API文档概览。"""
    return API_DOCS
