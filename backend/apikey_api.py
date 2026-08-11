"""对外API密钥管理 — 用户创建/管理自己的API Key。

- POST /api/api-keys       创建API Key
- GET  /api/api-keys       列表
- DELETE /api/api-keys/{id} 吊销
- GET  /api/open/docs      API文档概览
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["API密钥"])

# ── 模型 ──────────────────────────────────────────────────


class ApiKeyCreateRequest(BaseModel):
    label: str = Field("", max_length=100, description="备注标签（可选）")
    expire_days: int = Field(0, ge=0, le=3650, description="有效期天数（0=永不过期）")


# 可用有效期档位（前端下拉展示）
EXPIRE_PRESETS = [
    {"days": 0, "label": "永不过期"},
    {"days": 7, "label": "7 天"},
    {"days": 30, "label": "30 天"},
    {"days": 90, "label": "90 天"},
    {"days": 365, "label": "1 年"},
]


def _calc_expires_at(expire_days: int) -> str:
    """按有效天数计算过期时间（0=永不过期返回空串）。"""
    if not expire_days:
        return ""
    return (datetime.now() + timedelta(days=expire_days)).isoformat()


def _key_status(expires_at: str) -> str:
    """密钥状态：expired=已过期 / active=生效中（永不过期也视为 active）。"""
    if expires_at and expires_at <= datetime.now().isoformat():
        return "expired"
    return "active"

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

    kid = f"apikey_{int(datetime.now().timestamp() * 1000)}"
    expires_at = _calc_expires_at(req.expire_days)
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, label, created_at, expires_at) VALUES (?,?,?,?,?,?,?)",
            (kid, user_id, key_hash, key_prefix, req.label or "", datetime.now().isoformat(), expires_at),
        )

    return {
        "id": kid,
        "api_key": raw_key,
        "prefix": key_prefix,
        "label": req.label,
        "expire_days": req.expire_days,
        "expires_at": expires_at,
        "message": "API Key 创建成功！请立即复制保存，后续无法再次查看完整Key。",
    }


@router.get("/api-keys")
async def list_api_keys(current_user: dict = require_auth()):
    """列出我的API Keys（含过期时间 / 状态 / 累计用量统计）。"""
    user_id = current_user.get("user_id")
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, key_prefix, label, last_used, expires_at, created_at FROM api_keys WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        key_ids = [r["id"] for r in rows]
        # 单次聚合所有 Key 的用量（与 /api-keys/usage 口径一致）
        usage_map = {}
        if key_ids:
            ph = ",".join("?" * len(key_ids))
            for r in conn.execute(
                f"""SELECT api_key, COUNT(*) requests, SUM(success) ok,
                            SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) err,
                            COALESCE(SUM(input_length+output_length),0) tokens
                    FROM usage_logs WHERE api_key IN ({ph}) AND api_key != ''
                    GROUP BY api_key""",
                key_ids,
            ).fetchall():
                usage_map[r["api_key"]] = {
                    "requests": r["requests"],
                    "ok": r["ok"],
                    "err": r["err"],
                    "tokens": r["tokens"],
                }

    result = []
    for r in rows:
        result.append(
            {
                "id": r["id"],
                "prefix": r["key_prefix"],
                "label": r["label"],
                "last_used": r["last_used"],
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
                "status": _key_status(r["expires_at"] or ""),
                "usage": usage_map.get(r["id"], {"requests": 0, "ok": 0, "err": 0, "tokens": 0}),
            }
        )
    return result


@router.get("/api-keys/usage")
async def api_key_usage(current_user: dict = require_auth()):
    """API Key 使用报表：按天聚合请求数/成功数/错误数/LLM token 消耗（v13.23）。

    数据来自 openai_gateway 调用时写入 usage_logs 的 api_key 标记。
    """
    user_id = current_user.get("user_id")
    with get_db_context() as conn:
        key_rows = conn.execute(
            "SELECT id, key_prefix, label, last_used FROM api_keys WHERE user_id=?", (user_id,)
        ).fetchall()
        key_ids = [r["id"] for r in key_rows]
        if not key_ids:
            return {"daily": [], "per_key": [], "total": {"requests": 0, "ok": 0, "err": 0, "tokens": 0}}
        ph = ",".join("?" * len(key_ids))
        daily = conn.execute(
            f"""SELECT substr(timestamp,1,10) day, COUNT(*) requests,
                        SUM(success) ok, SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) err,
                        COALESCE(SUM(input_length+output_length),0) tokens
                FROM usage_logs WHERE api_key IN ({ph}) AND api_key != ''
                GROUP BY day ORDER BY day DESC LIMIT 30""",
            key_ids,
        ).fetchall()
        per_key = conn.execute(
            f"""SELECT api_key, COUNT(*) requests, SUM(success) ok,
                        SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) err,
                        COALESCE(SUM(input_length+output_length),0) tokens
                FROM usage_logs WHERE api_key IN ({ph}) AND api_key != ''
                GROUP BY api_key ORDER BY requests DESC""",
            key_ids,
        ).fetchall()
        total = conn.execute(
            f"""SELECT COUNT(*) requests, COALESCE(SUM(success),0) ok,
                        COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0) err,
                        COALESCE(SUM(input_length+output_length),0) tokens
                FROM usage_logs WHERE api_key IN ({ph}) AND api_key != ''""",
            key_ids,
        ).fetchone()
    key_meta = {r["id"]: dict(r) for r in key_rows}
    return {
        "daily": [dict(r) for r in daily],
        "per_key": [
            {
                "id": r["api_key"],
                "prefix": key_meta.get(r["api_key"], {}).get("key_prefix", ""),
                "label": key_meta.get(r["api_key"], {}).get("label", ""),
                "requests": r["requests"],
                "ok": r["ok"],
                "err": r["err"],
                "tokens": r["tokens"],
            }
            for r in per_key
        ],
        "total": dict(total) if total else {"requests": 0, "ok": 0, "err": 0, "tokens": 0},
    }


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
