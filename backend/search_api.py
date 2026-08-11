#!/usr/bin/env python3
"""全平台统一搜索端点（v10.3 收尾）。

POST /api/search/global — 跨模块搜索：需求、工具、知识库、历史对话
v10.2：修复 v10.1 引用了不存在的表（tool_hub/knowledge_docs/usage_log），
       改为内存工具目录 + 真实存在的表（knowledge_bases/conversations/messages/usage_logs）。
v10.3：支持 limit 参数（前端已传但此前被忽略）；agents/workflows 直达详情页；
       修复 tools 搜索因全局结果数已达 30 而提前中断的问题。
"""

import json
import logging

from fastapi import APIRouter, Depends

from common.auth import require_auth
from common.db import get_db
from tool_hub import TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["全平台搜索"])


# ── 各类型搜索（按类型拆分，避免 global_search 复杂度过高）──────────────────


def _search_requirements(conn, like: str, limit: int) -> list:
    """需求：名称/描述 LIKE 匹配。"""
    results = []
    try:
        rows = conn.execute(
            f"SELECT id, name, description, status, created_at FROM requirements WHERE name LIKE ? OR description LIKE ? ORDER BY created_at DESC LIMIT {limit}",
            (like, like),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        results.append(
            {
                "type": "requirement",
                "id": r["id"],
                "title": r["name"],
                "description": (r["description"] or "")[:120],
                "status": r["status"],
                "path": f"/workspace?requirement_id={r['id']}",
                "created_at": r["created_at"],
            }
        )
    return results


def _search_tools(q: str, limit: int) -> list:
    """工具：目录在内存中（tool_hub.TOOL_DEFINITIONS），非数据库表。"""
    results = []
    hits = 0
    for tid, tdef in TOOL_DEFINITIONS.items():
        if hits >= limit:
            break
        name = tdef.get("name", tid)
        desc = tdef.get("description", "")
        category = tdef.get("category", "通用")
        if q in name.lower() or q in desc.lower() or q in tid.lower():
            results.append(
                {
                    "type": "tool",
                    "id": tid,
                    "title": name,
                    "description": desc[:120],
                    "category": category,
                    "path": f"/tool/{tid}",
                }
            )
            hits += 1
    return results


def _search_typed_table(conn, _type: str, _table: str, _label: str, path_tpl: str, like: str, limit: int) -> list:
    """Agent / Skill / 工作流：同一 name/description + active 模式，仅表与路径模板不同。"""
    results = []
    try:
        rows = conn.execute(
            f"SELECT id, name, description, created_at FROM {_table} "
            f"WHERE (name LIKE ? OR description LIKE ?) AND active=1 ORDER BY created_at DESC LIMIT {limit}",
            (like, like),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        results.append(
            {
                "type": _type,
                "id": r["id"],
                "title": r["name"],
                "description": (r["description"] or "")[:120],
                "module": _label,
                "path": path_tpl.format(id=r["id"]),
                "created_at": r["created_at"],
            }
        )
    return results


def _search_docs(conn, like: str, limit: int) -> list:
    """知识库：名称/描述 LIKE 匹配。"""
    results = []
    try:
        rows = conn.execute(
            f"SELECT id, name, description, created_at FROM knowledge_bases WHERE name LIKE ? OR description LIKE ? ORDER BY created_at DESC LIMIT {limit}",
            (like, like),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        results.append(
            {
                "type": "document",
                "id": r["id"],
                "title": r["name"],
                "description": (r["description"] or "")[:120],
                "path": "/knowledge-bases",
                "created_at": r["created_at"],
            }
        )
    return results


def _search_history(conn, like: str, limit: int) -> list:
    """历史对话：会话标题 + 消息内容。"""
    results = []
    try:
        rows = conn.execute(
            f"SELECT id, title, created_at FROM conversations WHERE title LIKE ? ORDER BY updated_at DESC LIMIT {limit}",
            (like,),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        results.append(
            {
                "type": "history",
                "id": r["id"],
                "title": (r["title"] or "")[:80],
                "description": "会话",
                "module": "会话",
                "path": "/chat",
                "created_at": r["created_at"],
            }
        )
    try:
        rows = conn.execute(
            f"SELECT id, conversation_id, content, created_at FROM messages WHERE content LIKE ? ORDER BY created_at DESC LIMIT {limit}",
            (like,),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        results.append(
            {
                "type": "history",
                "id": r["id"],
                "title": (r["content"] or "")[:80],
                "description": "消息",
                "module": "会话",
                "path": "/chat",
                "created_at": r["created_at"],
            }
        )
    return results


def _like_patterns(like: str) -> list:
    """LIKE 模式集合：原词 + JSON 转义形式。

    metadata/content 的 JSON 文本由 json.dumps 默认 ensure_ascii=True 写入，
    中文会存为 \\uXXXX 转义序列，直接 LIKE 中文字面无法命中，需追加转义模式。
    """
    pats = [like]
    try:
        inner = json.dumps(like, ensure_ascii=True)
        if inner.startswith('"') and inner.endswith('"') and "\\u" in inner:
            pats.append(f"%{inner[1:-1]}%")
    except Exception:
        pass
    return pats


def _search_works(conn, like: str, limit: int) -> list:
    """创作工厂作品（v22.1 补齐统一搜索缺口）。

    - artifacts 表：图片（image_factory / meme_factory）、视频、歌词、歌曲
      （metadata/content 为 JSON 文本，LIKE 可模糊匹配 prompt/标题，含 \\u 转义形式）
    - 小游戏 / 小程序：game_projects / miniapp_projects 表（名称/需求描述匹配）
    表缺失或查询异常时静默跳过，不影响主链路。
    """
    results = []
    pats = _like_patterns(like)
    try:
        rows = conn.execute(
            "SELECT id, type, author, content, media_url, metadata, created_at FROM artifacts "
            "WHERE active=1 AND type IN ('image','video','lyrics','audio') "
            "AND (metadata LIKE ? OR content LIKE ? OR metadata LIKE ? OR content LIKE ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (pats[0], pats[0], *pats[1:], *pats[1:], limit),
        ).fetchall()
    except Exception:
        rows = []
    for r in rows:
        md = {}
        try:
            md = json.loads(r["metadata"] or "{}")
        except (TypeError, json.JSONDecodeError):
            pass
        is_meme = r["type"] == "image" and r["author"] == "meme_factory"
        if is_meme:
            label, path, type_ = "表情包", "/meme", "meme"
        elif r["type"] == "image":
            label, path, type_ = "图片作品", "/image-factory", "image"
        elif r["type"] == "video":
            label, path, type_ = "视频作品", "/video-factory", "video"
        elif r["type"] == "audio":
            label, path, type_ = "歌曲作品", "/music-factory", "audio"
        else:
            label, path, type_ = "歌词作品", "/music-factory", "lyrics"
        prompt = md.get("prompt") or ""
        if not prompt:
            try:
                content = json.loads(r["content"] or "{}")
                prompt = content.get("prompt", "") if isinstance(content, dict) else str(content)[:60]
            except (TypeError, json.JSONDecodeError):
                prompt = str(r["content"] or "")[:60]
        title = md.get("title") or prompt[:24] or f"{label} · {(r['created_at'] or '')[:16]}"
        results.append(
            {
                "type": type_,
                "id": r["id"],
                "title": title[:60],
                "description": (prompt or "")[:120],
                "module": label,
                "path": path,
                "created_at": r["created_at"],
            }
        )
    # 小游戏 / 小程序（表可能存在也可能为空，查询失败静默跳过）
    for table, label, path, type_ in (
        ("game_projects", "小游戏", "/games", "game"),
        ("miniapp_projects", "小程序", "/miniapp", "miniapp"),
    ):
        try:
            rows2 = conn.execute(
                f"SELECT id, name, requirement, created_at FROM {table} "
                f"WHERE name LIKE ? OR requirement LIKE ? ORDER BY created_at DESC LIMIT {limit}",
                (like, like),
            ).fetchall()
        except Exception:
            rows2 = []
        for r2 in rows2:
            results.append(
                {
                    "type": type_,
                    "id": r2["id"],
                    "title": (r2["name"] or "")[:60],
                    "description": (r2["requirement"] or "")[:120],
                    "module": label,
                    "path": path,
                    "created_at": r2["created_at"],
                }
            )
    return results[:limit]


# ── 统一入口 ────────────────────────────────────────────────────────────────


@router.post("/api/search/global")
def global_search(payload: dict, current_user: dict = Depends(require_auth)):
    """统一搜索：跨需求、工具、知识库、Agent、Skill、工作流、历史对话返回聚合结果。

    请求体：{"query": "关键词", "types": ["requirements","tools","docs","agents","skills","workflows","history"], "limit": 5}
    """
    query = (payload.get("query") or "").strip()
    types = payload.get("types") or ["requirements", "tools", "docs", "history"]
    # 每类型返回上限：前端传 limit（如 5），默认 10，上限 20
    limit = min(int(payload.get("limit") or 10), 20)
    if not query:
        return {"results": [], "total": 0, "query": query}

    results = []
    conn = get_db()
    try:
        like = f"%{query}%"
        q = query.lower()

        if "requirements" in types:
            results.extend(_search_requirements(conn, like, limit))

        if "tools" in types:
            results.extend(_search_tools(q, limit))

        # agents/skills/workflows 同一模式；agents/workflows 直达详情页（路由已存在）
        for _type, _table, _label, _path in (
            ("agents", "agents", "Agent", "/agents/{id}"),
            ("skills", "skills", "Skill", "/skills"),
            ("workflows", "workflows", "工作流", "/workflows/{id}"),
        ):
            if _type in types:
                results.extend(_search_typed_table(conn, _type, _table, _label, _path, like, limit))

        if "docs" in types:
            results.extend(_search_docs(conn, like, limit))

        if "history" in types:
            results.extend(_search_history(conn, like, limit))

        # v22.1：创作工厂作品（图片/视频/音乐/表情包/小游戏/小程序）
        if "works" in types:
            results.extend(_search_works(conn, like, limit))

    finally:
        conn.close()

    return {"results": results, "total": len(results), "query": query}
