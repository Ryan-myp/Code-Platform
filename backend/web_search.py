"""AI联网搜索引擎 — 实时搜索Web → LLM整合摘要。

- POST /api/search/web     网页搜索 + AI摘要
- GET  /api/search/history  搜索历史
"""

import json
import logging
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm_async, log_usage
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["联网搜索"])

# ── System Prompts ─────────────────────────────────────────

SEARCH_SUMMARY_SYSTEM = """你是资深信息研究分析师，拥有10年+跨领域研究经验，擅长从多源信息中交叉验证、提炼准确答案、洞察深层趋势。

## 研究方法论
1. **三角验证**：关键事实至少从2个独立来源确认，单一来源的信息标注"待核实"
2. **时效加权**：优先采纳最新信息，超过2年的数据标注"时效性提醒"
3. **权威分级**：官方/学术来源 > 知名媒体 > 个人博客/论坛，低权威来源的信息降低引用权重
4. **冲突处理**：当来源信息矛盾时，呈现双方说法并分析可能原因（方法论差异/利益立场/时效不同）

## 回答框架

### 直接回答（1-3句）
用最简洁的语言直接回答核心问题，让用户5秒内获取答案。

### 深度分析
- 从2-4个维度展开，每维度独立一段
- 引用搜索结果时标注 [来源N]
- 区分"事实"（可验证的客观陈述）与"观点"（专家判断/推测），明确标注
- 对争议话题呈现多方立场，不预设立场

### 关键数据速览
| 指标 | 数据 | 来源 | 时效 | 可信度 |
|------|------|------|------|--------|
| ... | ... | [来源N] | 2024年 | 高/中/低 |

### 延伸洞察
- 相关趋势或背景（帮助用户理解Why而不只是What）
- 常见误区澄清
- 进一步深挖的方向建议

## 质量标准
1. **事实优先**：有数据用数据，没数据说明不确定性程度
2. **时效透明**：所有信息标注时间，过时信息加⚠️警告
3. **客观中立**：不夹带个人立场，涉及利益相关方时主动披露
4. **诚实边界**：信息不足时明确说明"目前可确认的信息有限，以下是已知部分..."
5. **安全红线**：不提供医疗诊断、法律意见、投资建议等需资质的专业判断

## 参考来源
[来源1] 标题 — URL
[来源2] 标题 — URL

---
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
                user_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        # 存量库补 user_id 列（幂等，并发竞态忽略）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(search_history)").fetchall()]
        if "user_id" not in cols:
            try:
                conn.execute("ALTER TABLE search_history ADD COLUMN user_id TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()
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
            results.append(
                {
                    "title": data.get("Heading", query),
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL", ""),
                    "source": data.get("AbstractSource", "DuckDuckGo"),
                }
            )

        # Related Topics
        for topic in data.get("RelatedTopics", [])[:num]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append(
                    {
                        "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                        "snippet": topic["Text"],
                        "url": topic.get("FirstURL", ""),
                        "source": "DuckDuckGo",
                    }
                )

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
            results.append(
                {
                    "title": titles[i],
                    "snippet": snippets[i] if i < len(snippets) else "",
                    "url": urls[i] if i < len(urls) else "",
                    "source": "Wikipedia",
                }
            )

        return results
    except Exception as e:
        logger.warning(f"Wikipedia search failed: {e}")
        return []


# ── API ──────────────────────────────────────────────────

# ── 异步任务：联网搜索（进度/自动重试/并发控制）──


async def _web_search_worker(payload: dict, progress: Callable | None = None) -> dict:
    """联网搜索 worker：多源搜索 → LLM 整合摘要 → 历史入库（带用户归属）。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            progress(pct, stage)

    query = payload.get("query", "")
    num_results = int(payload.get("num_results", 5))

    _report(15, "多源搜索中")
    results = _search_ddg(query, num_results)
    if len(results) < 2:
        wiki_results = _search_fallback(query, num_results)
        results.extend(wiki_results)

    if not results:
        # 纯LLM模式：无搜索结果时由LLM直接回答（同样写入历史，保证记录闭环）
        _report(40, "AI 整合回答")
        raw = await call_llm_async(
            "你是一个知识渊博的助手。用户问了一个问题，但搜索引擎没有返回结果。请基于你的知识回答。如果不知道就说不知道。",
            f"问题：{query}",
            max_tokens=800,
            temperature=0.3,
            timeout=30,
        )
        log_usage("web_search_noresults", len(query), len(raw), 0)
        summary = raw.strip()
        # 无搜索结果时补充相关搜索推荐（中文查询也可获得推荐词）
        related = []
        try:
            raw_related = await call_llm_async(
                "你是搜索推荐引擎。为用户的搜索词推荐 3 个相关搜索词，每行一个，只输出词本身，不要序号和多余文字。",
                f"搜索词：{query}",
                max_tokens=60,
                temperature=0.5,
                timeout=15,
            )
            related = [line.strip() for line in raw_related.strip().splitlines() if line.strip()][:3]
        except Exception:  # noqa: BLE001 — 推荐词失败不影响主流程
            related = []
        sid = f"sch_{uuid.uuid4().hex[:12]}"
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO search_history (id, query, results, user_id, created_at) VALUES (?,?,?,?,?)",
                (
                    sid,
                    query,
                    json.dumps({"summary": summary, "sources": []}, ensure_ascii=False),
                    payload.get("user_id", ""),
                    datetime.now().isoformat(),
                ),
            )
        _report(100, "完成")
        return {"query": query, "mode": "llm_only", "summary": summary, "sources": [], "related": related}

    search_context = ""
    for i, r in enumerate(results):
        search_context += f"\n[来源{i + 1}] {r['title']}\n{r['snippet']}\nURL: {r['url']}\n"

    _report(45, "AI 整合摘要中")
    system_prompt = SEARCH_SUMMARY_SYSTEM.replace("{search_results}", search_context)
    raw = await call_llm_async(system_prompt, query, max_tokens=1000, temperature=0.3, timeout=60)
    summary = raw.strip()
    log_usage("web_search", len(query), len(summary), 0)

    _report(85, "保存搜索历史")
    sid = f"sch_{uuid.uuid4().hex[:12]}"
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO search_history (id, query, results, user_id, created_at) VALUES (?,?,?,?,?)",
            (
                sid,
                query,
                json.dumps({"summary": summary, "sources": results}, ensure_ascii=False),
                payload.get("user_id", ""),
                datetime.now().isoformat(),
            ),
        )
    _report(100, "完成")
    return {
        "query": query,
        "mode": "web_search",
        "summary": summary,
        "sources": [{"title": r["title"], "url": r["url"], "snippet": r["snippet"][:200]} for r in results],
        "related": [r["title"] for r in results[:3]],
    }


async def _web_search_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装联网搜索，回报进度。"""
    return await _web_search_worker(payload, progress=update)


@router.post("/web")
async def web_search(req: WebSearchRequest, current_user: dict = require_auth()):
    """AI联网搜索（异步任务：进度跟踪 / 失败自动重试 / 并发控制）"""
    payload = {
        **req.model_dump(),
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    task = create_task(
        "web_search_query",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"]}


@router.get("/history")
async def search_history(current_user: dict = require_auth()):
    """获取搜索历史（用户隔离：admin 全量，普通用户仅自己的）。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    with get_db_context() as conn:
        if role in ("admin", "super_admin"):
            rows = conn.execute(
                "SELECT id, query, created_at FROM search_history ORDER BY created_at DESC LIMIT 30"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, query, created_at FROM search_history WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
                (uid,),
            ).fetchall()
    return [{"id": r[0], "query": r[1], "created_at": r[2]} for r in rows]


# ── 异步任务处理器注册（进度/自动重试/并发控制）──
register_handler("web_search_query", _web_search_handler, user_limit=1, max_attempts=1)
