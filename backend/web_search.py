"""AI联网搜索引擎 — 实时搜索Web → LLM整合摘要。

- POST /api/search/web     网页搜索 + AI摘要
- GET  /api/search/history  搜索历史
"""

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["联网搜索"])

# ── System Prompts ─────────────────────────────────────────

SEARCH_SUMMARY_SYSTEM = """你是一个信息整合专家。根据以下网络搜索结果，回答用户的问题。要求：

1. 综合多个来源的信息，给出全面准确的回答
2. 引用来源时标注 [来源N] 
3. 如果搜索结果信息不足，诚实说明
4. 回答要结构清晰，分点列出关键信息
5. 在回答末尾列出参考来源

搜索结果：
{search_results}

请基于以上搜索结果回答用户的问题。"""

# ── 模型 ──────────────────────────────────────────────────

class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="搜索关键词")
    num_results: int = Field(5, ge=1, le=10, description="返回结果数量")


# ── 数据库初始化 ──────────────────────────────────────────

def init_db():
    with get_db_context() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                results TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                fav_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                label TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, fav_type, target_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                label TEXT,
                last_used TEXT,
                created_at TEXT NOT NULL
            )
        """)


init_db()


# ── DuckDuckGo 搜索 ────────────────────────────────────────

def _search_ddg(query: str, num: int = 5) -> list[dict]:
    """调用 DuckDuckGo Instant Answer API（免费，无需Key）。"""
    try:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        req = urllib.request.Request(url, headers={"User-Agent": "XiaoTuanAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = []

        # Abstract / Instant Answer
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "snippet": data["AbstractText"],
                "url": data.get("AbstractURL", ""),
                "source": data.get("AbstractSource", "DuckDuckGo"),
            })

        # Related Topics
        for topic in data.get("RelatedTopics", [])[:num]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic["Text"],
                    "url": topic.get("FirstURL", ""),
                    "source": "DuckDuckGo",
                })

        return results[:num]
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return []


def _search_fallback(query: str, num: int = 5) -> list[dict]:
    """备用搜索：Wikipedia API。"""
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={num}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "XiaoTuanAI/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        results = []
        titles = data[1] if len(data) > 1 else []
        snippets = data[2] if len(data) > 2 else []
        urls = data[3] if len(data) > 3 else []

        for i in range(min(len(titles), num)):
            results.append({
                "title": titles[i],
                "snippet": snippets[i] if i < len(snippets) else "",
                "url": urls[i] if i < len(urls) else "",
                "source": "Wikipedia",
            })

        return results
    except Exception as e:
        logger.warning(f"Wikipedia search failed: {e}")
        return []


# ── API ──────────────────────────────────────────────────

@router.post("/web")
async def web_search(req: WebSearchRequest, current_user: dict = require_auth()):
    """AI联网搜索：搜索Web → LLM整合摘要。"""
    start = datetime.now()

    # 多源搜索
    results = _search_ddg(req.query, req.num_results)
    if len(results) < 2:
        wiki_results = _search_fallback(req.query, req.num_results)
        results.extend(wiki_results)

    if not results:
        # 纯LLM模式：无搜索结果时由LLM直接回答
        try:
            raw = call_llm(
                "你是一个知识渊博的助手。用户问了一个问题，但搜索引擎没有返回结果。请基于你的知识回答。如果不知道就说不知道。",
                f"问题：{req.query}",
                max_tokens=800, temperature=0.3, timeout=30,
            )
            elapsed = round((datetime.now() - start).total_seconds(), 2)
            log_usage("web_search_noresults", len(req.query), len(raw), elapsed)
            return {
                "query": req.query,
                "mode": "llm_only",
                "summary": raw.strip(),
                "sources": [],
                "related": [],
            }
        except Exception as e:
            raise HTTPException(500, f"搜索失败：{e}")

    # 构建搜索上下文
    search_context = ""
    for i, r in enumerate(results):
        search_context += f"\n[来源{i+1}] {r['title']}\n{r['snippet']}\nURL: {r['url']}\n"

    # LLM 整合摘要
    system_prompt = SEARCH_SUMMARY_SYSTEM.replace("{search_results}", search_context)

    try:
        raw = call_llm(system_prompt, req.query, max_tokens=1000, temperature=0.3, timeout=60)
        summary = raw.strip()
    except Exception as e:
        logger.exception("web search llm failed")
        raise HTTPException(500, f"AI摘要生成失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("web_search", len(req.query), len(summary), elapsed)

    # 保存搜索历史
    sid = f"sch_{int(datetime.now().timestamp()*1000)}"
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO search_history (id, query, results, created_at) VALUES (?,?,?,?)",
            (sid, req.query, json.dumps({"summary": summary, "sources": results}, ensure_ascii=False),
             datetime.now().isoformat()),
        )

    return {
        "query": req.query,
        "mode": "web_search",
        "summary": summary,
        "sources": [{"title": r["title"], "url": r["url"], "snippet": r["snippet"][:200]} for r in results],
        "related": [r["title"] for r in results[:3]],
    }


@router.get("/history")
async def search_history(current_user: dict = require_auth()):
    """获取搜索历史。"""
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, query, created_at FROM search_history ORDER BY created_at DESC LIMIT 30"
        ).fetchall()
    return [{"id": r[0], "query": r[1], "created_at": r[2]} for r in rows]
