#!/usr/bin/env python3
"""全平台统一搜索端点（v10.1）。

POST /api/search/global — 跨模块搜索：需求、工具、文档、历史记录
"""

import logging

from fastapi import APIRouter, Depends

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["全平台搜索"])


@router.post("/api/search/global")
def global_search(payload: dict, current_user: dict = Depends(require_auth)):
    """统一搜索：跨需求、工具、文档、历史记录返回聚合结果。

    请求体：{"query": "关键词", "types": ["requirements","tools","docs","history"]}
    """
    query = (payload.get("query") or "").strip()
    types = payload.get("types") or ["requirements", "tools", "docs", "history"]
    if not query:
        return {"results": [], "total": 0, "query": query}

    results = []
    conn = get_db()
    try:
        like = f"%{query}%"

        if "requirements" in types:
            rows = conn.execute(
                "SELECT id, name, description, status, created_at FROM requirements WHERE name LIKE ? OR description LIKE ? ORDER BY created_at DESC LIMIT 10",
                (like, like),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "requirement",
                    "id": r["id"],
                    "title": r["name"],
                    "description": (r["description"] or "")[:120],
                    "status": r["status"],
                    "path": f"/workspace?requirement_id={r['id']}",
                    "created_at": r["created_at"],
                })

        if "tools" in types:
            rows = conn.execute(
                "SELECT id, name, description, category, icon FROM tool_hub WHERE name LIKE ? OR description LIKE ? LIMIT 10",
                (like, like),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "tool",
                    "id": r["id"],
                    "title": r["name"],
                    "description": (r["description"] or "")[:120],
                    "category": r["category"],
                    "path": f"/tool/{r['id']}",
                })

        if "docs" in types:
            rows = conn.execute(
                "SELECT id, title, content, created_at FROM knowledge_docs WHERE title LIKE ? OR content LIKE ? ORDER BY created_at DESC LIMIT 10",
                (like, like),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "document",
                    "id": r["id"],
                    "title": r["title"],
                    "description": (r["content"] or "")[:120],
                    "path": f"/knowledge-bases",
                    "created_at": r["created_at"],
                })

        if "history" in types:
            rows = conn.execute(
                "SELECT id, module, prompt, created_at FROM usage_log WHERE prompt LIKE ? ORDER BY created_at DESC LIMIT 10",
                (like,),
            ).fetchall()
            for r in rows:
                results.append({
                    "type": "history",
                    "id": r["id"],
                    "title": (r["prompt"] or "")[:80],
                    "description": f"模块：{r['module']}",
                    "module": r["module"],
                    "path": "/records",
                    "created_at": r["created_at"],
                })

    finally:
        conn.close()

    return {"results": results, "total": len(results), "query": query}
