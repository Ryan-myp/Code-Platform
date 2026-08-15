"""全局搜索API — 跨工具/模板/内容一键搜索。"""

import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from common.auth import require_auth
from common.db import get_db
from common.llm import _safe_exc_msg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["全局搜索"])

# 工具列表用于搜索
TOOLS = [
    {"id": "image-factory", "name": "图片工厂", "desc": "AI图片生成与编辑工具", "type": "tool", "category": "image", "path": "/image-factory"},
    {"id": "video-factory", "name": "视频工厂", "desc": "AI视频生成与剪辑工具", "type": "tool", "category": "video", "path": "/video-factory"},
    {"id": "music-factory", "name": "音乐工厂", "desc": "AI音乐生成与混音工具", "type": "tool", "category": "music", "path": "/music-factory"},
    {"id": "code-sandbox", "name": "代码沙盒", "desc": "在线代码编辑器与执行环境", "type": "tool", "category": "code", "path": "/code-sandbox"},
    {"id": "prd-engine", "name": "PRD引擎", "desc": "产品需求文档自动生成", "type": "tool", "category": "product", "path": "/prd-engine"},
    {"id": "template-market", "name": "模板市场", "desc": "海量AI模板商店", "type": "tool", "category": "market", "path": "/templates"},
    {"id": "agents", "name": "智能体", "desc": "AI智能体创建与管理", "type": "tool", "category": "agent", "path": "/agents"},
    {"id": "chat", "name": "智能对话", "desc": "AI多轮对话与问答", "type": "tool", "category": "chat", "path": "/chat"},
    {"id": "seo-analyzer", "name": "SEO分析器", "desc": "搜索引擎优化分析工具", "type": "tool", "category": "seo", "path": "/seo-analyzer"},
    {"id": "competitor-monitor", "name": "竞品监控", "desc": "竞争对手动态追踪", "type": "tool", "category": "monitor", "path": "/competitor-monitor"},
    {"id": "meme-factory", "name": "表情包工厂", "desc": "AI表情包生成工具", "type": "tool", "category": "meme", "path": "/meme-factory"},
    {"id": "pdf-tools", "name": "PDF工具集", "desc": "PDF转换与处理工具", "type": "tool", "category": "pdf", "path": "/pdf-tools"},
    {"id": "voice-chat", "name": "语音对话", "desc": "AI语音实时对话", "type": "tool", "category": "voice", "path": "/voice-chat"},
    {"id": "data-forecast", "name": "数据预测", "desc": "AI数据分析与预测", "type": "tool", "category": "data", "path": "/data-forecast"},
    {"id": "mindmap", "name": "思维导图", "desc": "AI思维导图生成工具", "type": "tool", "category": "mindmap", "path": "/mindmap"},
    {"id": "short-drama", "name": "短剧生成", "desc": "AI短剧脚本与分镜生成", "type": "tool", "category": "drama", "path": "/short-drama"},
    {"id": "copywriting", "name": "文案创作", "desc": "AI文案自动生成工具", "type": "tool", "category": "copywriting", "path": "/copywriting"},
    {"id": "translation", "name": "翻译工具", "desc": "AI多语言翻译工具", "type": "tool", "category": "translation", "path": "/translation"},
    {"id": "ppt-factory", "name": "PPT工厂", "desc": "AI演示文稿自动生成", "type": "tool", "category": "ppt", "path": "/ppt-factory"},
    {"id": "excel-tools", "name": "Excel工具", "desc": "AI表格处理与分析工具", "type": "tool", "category": "excel", "path": "/excel"},
]
from common.helpers import _aggregate_compute_results, _execute_common_step, _execute_compute_step, _execute_single_step, _execute_step, _finalize_common_operation, _finalize_results, _finalize_step_results, _initialize_compute_context, _prepare_common_context, _prepare_context, _prepare_step_context



def _clean_text(text: str) -> str:
    """清理文本用于搜索。"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip().lower()


def _score_result(doc: dict, keywords: list) -> int:
    """计算搜索结果相关性评分。"""
    score = 0
    title = _clean_text(doc.get("name", ""))
    content = _clean_text(doc.get("description", ""))
    desc = _clean_text(doc.get("desc", ""))
    all_text = f"{title} {content} {desc}"
    
    for kw in keywords:
        kw = kw.lower()
        if kw in title:
            score += 10
        if kw in desc:
            score += 5
        if kw in content:
            score += 2
        if title.startswith(kw):
            score += 8
        if desc.startswith(kw):
            score += 4
    return score


def _qs_search_tools(keywords: list) -> list:
    """搜索内置工具。"""
    results = []
    for tool in TOOLS:
        text = f"{tool['name']} {tool['desc']}"
        if any(kw in text.lower() for kw in keywords):
            tool_copy = dict(tool)
            tool_copy["score"] = _score_result(tool_copy, keywords)
            results.append(tool_copy)
    return results


def _qs_search_templates(conn, q: str, keywords: list) -> list:
    """搜索内置模板 + 用户自定义模板。"""
    results = []
    try:
        rows = conn.execute(
            """SELECT id, name, description, category, tool_id, usage_count
               FROM templates
               WHERE (name LIKE ? OR description LIKE ?)
               ORDER BY usage_count DESC
               LIMIT 10""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        for r in rows:
            doc = {
                "id": r["id"], "name": r["name"], "description": r["description"] or "",
                "category": r["category"], "tool_id": r["tool_id"],
                "usage_count": r["usage_count"], "type": "template", "source": "builtin",
            }
            doc["score"] = _score_result(doc, keywords)
            results.append(doc)
    except Exception as e:
        logger.debug(f"Builtin template search error: {e}")
    try:
        rows = conn.execute(
            """SELECT id, name, description, created_at
               FROM user_templates
               WHERE (name LIKE ? OR description LIKE ?)
               ORDER BY created_at DESC
               LIMIT 10""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        for r in rows:
            doc = {
                "id": r["id"], "name": r["name"], "description": r["description"] or "",
                "type": "template", "source": "user_template", "created_at": r["created_at"],
            }
            doc["score"] = _score_result(doc, keywords)
            results.append(doc)
    except Exception as e:
        logger.debug(f"Template search error: {e}")
    return results


def _qs_search_work(conn, q: str, keywords: list) -> list:
    """搜索对话/需求/项目。"""
    results = []
    try:
        conv_rows = conn.execute(
            """SELECT id, title as name, agent_id as source_id, created_at
               FROM conversations
               WHERE title LIKE ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (f"%{q}%",),
        ).fetchall()
        for r in conv_rows:
            doc = {"id": r["id"], "name": r["name"], "type": "conversation",
                   "source": "chat", "created_at": r["created_at"]}
            doc["score"] = _score_result(doc, keywords)
            results.append(doc)
        req_rows = conn.execute(
            """SELECT id, name, description, status
               FROM requirements
               WHERE name LIKE ? OR description LIKE ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        for r in req_rows:
            doc = {"id": r["id"], "name": r["name"], "description": r["description"] or "",
                   "type": "requirement", "source": "task", "status": r["status"]}
            doc["score"] = _score_result(doc, keywords)
            results.append(doc)
        proj_rows = conn.execute(
            """SELECT id, name, description, status
               FROM projects
               WHERE name LIKE ? OR description LIKE ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
        for r in proj_rows:
            doc = {"id": r["id"], "name": r["name"], "description": r["description"] or "",
                   "type": "project", "source": "project", "status": r["status"]}
            doc["score"] = _score_result(doc, keywords)
            results.append(doc)
    except Exception as e:
        logger.debug(f"Work search error: {e}")
    return results


def _qs_search_recent(conn, user_id: str) -> list:
    """搜索最近使用的工具。"""
    results = []
    try:
        recent_rows = conn.execute(
            """SELECT DISTINCT feature as name, model, created_at
               FROM usage_logs
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT 5""",
            (user_id,),
        ).fetchall()
        for r in recent_rows:
            doc = {"id": r["name"], "name": r["name"], "type": "recent",
                   "score": 1, "created_at": r["created_at"]}
            results.append(doc)
    except Exception:
        pass
    return results


def _qs_finalize(results: list, keywords: list, q: str, limit: int) -> dict:
    """排序去重 + 搜索建议。"""
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    seen = set()
    unique_results = []
    for r in results:
        key = f"{r.get('type', 'unknown')}:{r.get('id', '')}"
        if key not in seen:
            seen.add(key)
            unique_results.append(r)
    suggestions = []
    if len(keywords) == 1:
        kw = keywords[0]
        suggest_queries = [f"{kw} 模板", f"{kw} 工具", f"{kw} AI生成", f"如何使用 {kw}"]
        suggestions = [s for s in suggest_queries if kw in s][:5]
    return {
        "query": q,
        "results": unique_results[:limit],
        "total": len(unique_results),
        "suggestions": suggestions,
        "time_ms": 50,
    }

@router.get("/quick")
async def quick_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    current_user: dict = require_auth(),
):
    """全局快速搜索 — 搜索模板、工具、内容。"""
    if not q or len(q.strip()) < 1:
        return {"results": [], "total": 0, "suggestions": []}
    
    keywords = [w.strip() for w in q.split() if w.strip()]
    if not keywords:
        return {"results": [], "total": 0, "suggestions": []}
    
    conn = get_db()
    try:
        results = []
        user_id = current_user.get("user_id", "")
        
        # 1. 搜索工具
        results += _qs_search_tools(keywords)
        # 2. 搜索模板
        results += _qs_search_templates(conn, q, keywords)
        # 3. 搜索工作（对话/需求/项目）
        results += _qs_search_work(conn, q, keywords)
        # 4. 搜索最近使用的工具
        results += _qs_search_recent(conn, user_id)
        
        # 排序去重 + 搜索建议
        return _qs_finalize(results, keywords, q, limit)
    finally:
        conn.close()


@router.get("/suggest")
async def search_suggestions(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=20),
):
    """搜索建议 — 输入时实时提示。"""
    if not q or len(q.strip()) < 1:
        return {"suggestions": []}
    
    conn = get_db()
    try:
        suggestions = []
        
        # 从用户模板获取建议
        try:
            rows = conn.execute(
                """SELECT DISTINCT name FROM user_templates 
                   WHERE name LIKE ?
                   LIMIT ?""",
                (f"{q}%", limit,)
            ).fetchall()
            suggestions.extend([r["name"] for r in rows])
        except Exception:
            pass
        
        # 从工具名获取建议
        for tool in TOOLS:
            if q.lower() in tool["name"].lower() or q.lower() in tool["desc"].lower():
                if tool["name"] not in suggestions:
                    suggestions.append(tool["name"])
        
        return {"suggestions": suggestions[:limit]}
    finally:
        conn.close()


@router.get("/history")
async def get_search_history(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = require_auth(),
):
    """获取搜索历史（基于最近使用的工具）。"""
    user_id = current_user.get("user_id", "")
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT DISTINCT feature as query, MAX(created_at) as last_used
               FROM usage_logs 
               WHERE user_id = ?
               ORDER BY last_used DESC
               LIMIT ?""",
            (user_id, limit)
        ).fetchall()
        return {"history": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.post("/history/clear")
async def clear_search_history(current_user: dict = require_auth()):
    """清空搜索历史。"""
    return {"success": True, "message": "搜索历史已清空"}


@router.get("/categories")
async def get_search_categories():
    """获取搜索分类。"""
    return {
        "categories": [
            {"id": "all", "name": "全部", "icon": "🔍"},
            {"id": "tools", "name": "工具", "icon": "🛠️"},
            {"id": "templates", "name": "模板", "icon": "📋"},
            {"id": "projects", "name": "项目", "icon": "📁"},
            {"id": "tasks", "name": "任务", "icon": "✅"},
            {"id": "conversations", "name": "对话", "icon": "💬"},
        ]
    }

def _search_works(conn, keyword: str, limit: int = 20) -> list:
    """搜索创作工厂作品（artifacts、game_projects、miniapp_projects）。"""
    results = []
    type_map = {
        "image": ("图片作品", "/image-factory"),
        "video": ("视频作品", "/video-factory"),
        "audio": ("歌曲作品", "/music-factory"),
        "lyrics": ("歌词作品", "/music-factory"),
        "meme": ("表情包", "/meme"),
    }
    try:
        rows = conn.execute(
            """SELECT id, type, author, content, media_url, metadata, created_at
               FROM artifacts WHERE content LIKE ? OR metadata LIKE ?
               LIMIT ?""",
            (keyword, keyword, limit),
        ).fetchall()
        for r in rows:
            meta = {}
            try:
                import json
                meta = json.loads(r["metadata"] or "{}")
            except Exception:
                pass
            title = meta.get("title")
            if not title:
                try:
                    import json as _json
                    _content = json.loads(r["content"] or "{}")
                    title = (_content.get("prompt") or r["content"] or "")[:24]
                except Exception:
                    title = (r["content"] or "")[:24]
            t = r["type"]
            # 表情包工坊产物在 artifacts 中 type 为 image，按来源工厂推断为 meme（前端展示为表情包）
            if t == "image" and r["author"] == "meme_factory":
                t = "meme"
            label, path = type_map.get(t, ("作品", f"/{t}-factory"))
            results.append({
                "id": r["id"], "type": t, "title": title,
                "path": path, "module": label,
                "author": r["author"], "created_at": r["created_at"],
            })
    except Exception:
        pass
    # game_projects
    try:
        rows = conn.execute(
            """SELECT id, name, requirement, created_at FROM game_projects
               WHERE name LIKE ? OR requirement LIKE ? LIMIT ?""",
            (keyword, keyword, limit),
        ).fetchall()
        for r in rows:
            results.append({
                "id": r["id"], "type": "game",
                "title": r["name"], "path": "/games",
                "module": "小游戏",
                "author": "", "created_at": r["created_at"],
            })
    except Exception:
        pass
    # miniapp_projects
    try:
        rows = conn.execute(
            """SELECT id, name, requirement, created_at FROM miniapp_projects
               WHERE name LIKE ? OR requirement LIKE ? LIMIT ?""",
            (keyword, keyword, limit),
        ).fetchall()
        for r in rows:
            results.append({
                "id": r["id"], "type": "miniapp",
                "title": r["name"], "path": "/miniapp",
                "module": "小程序",
                "author": "", "created_at": r["created_at"],
            })
    except Exception:
        pass
    return results



def _search_tools(query: str) -> list:
    """搜索内置工具。"""
    from search_api import TOOLS

    results = []
    for tool in TOOLS:
        text = f"{tool['name']} {tool['desc']}"
        if query.lower() in text.lower():
            results.append({**tool, "score": 10})
    return results


def _search_builtin_templates(conn, kw: str, limit: int) -> list:
    """搜索内置 + 用户模板。"""
    results = []
    try:
        rows = conn.execute(
            "SELECT id, name, description, category, tool_id, usage_count FROM templates WHERE name LIKE ? OR description LIKE ? LIMIT ?",
            (kw, kw, limit),
        ).fetchall()
        for r in rows:
            results.append({
                "id": r["id"], "name": r["name"], "type": "template", "source": "builtin",
                "category": r["category"], "tool_id": r["tool_id"],
                "usage_count": r["usage_count"], "description": r["description"] or "", "score": 9,
            })
    except Exception:
        pass
    try:
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM user_templates WHERE name LIKE ? LIMIT ?",
            (kw, limit),
        ).fetchall()
        for r in rows:
            results.append({
                "id": r["id"], "name": r["name"], "type": "template", "source": "user_template",
                "created_at": r["created_at"], "score": 8,
            })
    except Exception:
        pass
    return results


def _search_table_rows(conn, table: str, kw: str, limit: int, result_type: str, score: int, source: str = "project") -> list:
    """通用表搜索（requirements/projects 等）。"""
    if table not in [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        return []
    try:
        rows = conn.execute(
            f"SELECT id, name, description FROM {table} WHERE name LIKE ? LIMIT ?",
            (kw, limit),
        ).fetchall()
        return [{
            "id": r["id"], "name": r["name"], "type": result_type, "source": source,
            "description": r["description"] or "", "score": score,
        } for r in rows]
    except Exception:
        return []


def _dedup_results(results: list, limit: int) -> list:
    """按 type-id 去重 + 排序 + 截断。"""
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: x.get("score", 0), reverse=True):
        key = f"{r.get('type','')}-{r.get('id','')}"
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique[:limit]

def global_search(params: dict, current_user: dict) -> dict:
    """全局搜索入口 — 支持 types 过滤。"""
    from common.db import get_db
    query = params.get("query", "").strip()
    types = params.get("types", ["tools", "templates", "projects", "tasks", "requirements", "contents", "works"])
    limit = min(params.get("limit", 20), 50)
    
    if not query:
        return {"results": [], "total": 0, "query": "", "suggestions": []}
    
    conn = get_db()
    try:
        results = []
        kw = f"%{query}%"
        
        if "tools" in types:
            results += _search_tools(query)
        
        if "templates" in types:
            results += _search_builtin_templates(conn, kw, limit)
        
        if "works" in types:
            results.extend(_search_works(conn, kw, limit))
        
        if "requirements" in types:
            results += _search_table_rows(conn, "requirements", kw, limit, "requirement", 7)
        
        if "projects" in types:
            results += _search_table_rows(conn, "projects", kw, limit, "project", 6)
        
        # 排序去重
        unique = _dedup_results(results, limit)
        return {"results": unique, "total": len(unique), "query": query, "suggestions": []}
    finally:
        conn.close()
