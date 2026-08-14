"""AI联网搜索引擎 — 实时搜索Web → LLM整合摘要。

- POST /api/search/web     网页搜索 + AI摘要
- GET  /api/search/history  搜索历史
"""

import json
import logging
import re
import time
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.helpers import _notify_progress
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

## 时效要求
{time_constraint}

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
    time_range: Literal["", "24h", "7d", "30d"] = Field("", description="时间筛选：近24小时/7天/30天，空=不限")
    domain_filter: str = Field("", max_length=500, description="来源域白名单（逗号分隔，如 wikipedia.org,github.com），空=不过滤")


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
                expires_at TEXT,
                created_at TEXT NOT NULL
            )
        """)


init_db()


# ── 搜索结果内存缓存（v16）：同词重复搜索秒回，省一次外部搜索 + LLM 调用 ──


_SEARCH_CACHE: dict[str, tuple[float, dict]] = {}
_SEARCH_CACHE_TTL = 600  # 10 分钟
_SEARCH_CACHE_MAX = 200  # 上限防内存膨胀


def _cache_key(query: str, time_range: str = "", domain_filter: str = "") -> str:
    """缓存键：小写关键词 + 筛选条件（不同筛选条件结果不同，分开缓存）。"""
    return f"{time_range}|{domain_filter}|{query.strip().lower()}"


def _cache_get(key: str) -> dict | None:
    """读取缓存：过期即失效并清理。"""
    item = _SEARCH_CACHE.get(key)
    if item and time.time() - item[0] < _SEARCH_CACHE_TTL:
        return item[1]
    _SEARCH_CACHE.pop(key, None)
    return None


def _cache_set(key: str, value: dict) -> None:
    """写入缓存：超上限时淘汰最旧一条（简单 FIFO 近似，足够）。"""
    if len(_SEARCH_CACHE) >= _SEARCH_CACHE_MAX:
        try:
            oldest = min(_SEARCH_CACHE, key=lambda k: _SEARCH_CACHE[k][0])
            _SEARCH_CACHE.pop(oldest, None)
        except ValueError:
            pass
    _SEARCH_CACHE[key] = (time.time(), value)


def _cache_clear() -> None:
    """清空缓存（测试用）。"""
    _SEARCH_CACHE.clear()


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


# ── 时间筛选 / 来源域过滤（v15，纯函数便于单测）──

TIME_RANGE_LABELS = {"": "不限", "24h": "近24小时", "7d": "近7天", "30d": "近30天"}
TIME_RANGE_DELTAS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}

# 日期提取模式（顺序匹配，命中即返回）：
# 1) 2025-03-01 / 2025/3/1  2) 2025年3月1日  3) 英文相对时间 3 days ago
# 4) 中文相对时间 3天前/3小时前  5) 裸年份 2025（保守：仅当目标跨度 ≥ 1 年才判过期）
_DATE_ABS = re.compile(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})")
_DATE_ABS_CN = re.compile(r"(20\d{2})年(\d{1,2})月(\d{1,2})日?")
_DATE_REL_EN = re.compile(r"(\d{1,2})\s+(hour|hours|day|days|week|weeks|month|months)\s+ago", re.IGNORECASE)
_DATE_REL_CN = re.compile(r"(\d{1,2})\s*(小时|天|周|个月)\s*前")
_DATE_YEAR = re.compile(r"(20\d{2})")
_REL_UNITS = {
    "hour": "hours", "hours": "hours", "小时": "hours",
    "day": "days", "days": "days", "天": "days",
    "week": "weeks", "weeks": "weeks", "周": "weeks",
    "month": "months", "months": "months", "个月": "months",
}
_REL_DELTAS = {"hours": timedelta(hours=1), "days": timedelta(days=1), "weeks": timedelta(weeks=1), "months": timedelta(days=30)}


def _extract_date(text: str, now: datetime | None = None) -> datetime | None:
    """从文本中提取日期（绝对日期/相对时间/裸年份），提取不到返回 None。"""
    now = now or datetime.now()
    m = _DATE_ABS.search(text) or _DATE_ABS_CN.search(text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = _DATE_REL_EN.search(text) or _DATE_REL_CN.search(text)
    if m:
        unit = _REL_UNITS.get(m.group(2).lower(), "days")
        return now - int(m.group(1)) * _REL_DELTAS[unit]
    m = _DATE_YEAR.search(text)
    if m:
        return datetime(int(m.group(1)), 12, 31)  # 年末近似：仅用于「超过1年」判定
    return None


def _filter_results_by_time(results: list[dict], time_range: str, now: datetime | None = None) -> list[dict]:
    """按时间筛选结果：提取到的日期超出范围则剔除；无日期信息的结果保留（宁多勿少）。"""
    delta = TIME_RANGE_DELTAS.get(time_range)
    if not delta or not results:
        return results
    now = now or datetime.now()
    filtered = []
    for r in results:
        date = _extract_date(f"{r.get('title', '')} {r.get('snippet', '')}", now)
        if date is None or (now - date) <= delta:
            filtered.append(r)
    return filtered


def _filter_results_by_domain(results: list[dict], domains: list[str]) -> list[dict]:
    """按来源域白名单过滤：URL 域名是任一白名单域或其子域则保留（如 wikipedia.org 匹配 en.wikipedia.org）。"""
    allowed = [d.lower().strip() for d in domains if d and d.strip()]
    if not allowed or not results:
        return results
    filtered = []
    for r in results:
        host = (urlparse(r.get("url", "")).netloc or "").split(":")[0].lower()
        if any(host == d or host.endswith("." + d) for d in allowed):
            filtered.append(r)
    return filtered


# ── API ──────────────────────────────────────────────────

# ── 异步任务：联网搜索（进度/自动重试/并发控制）──


async def _web_search_worker(payload: dict, progress: Callable | None = None) -> dict:
    """联网搜索 worker：多源搜索 → LLM 整合摘要 → 历史入库（带用户归属）。"""

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    query = payload.get("query", "")
    num_results = int(payload.get("num_results", 5))
    time_range = payload.get("time_range", "")
    domain_filter = payload.get("domain_filter", "")

    # v16 缓存命中：10 分钟内同词同条件直接返回，秒回且不重复消耗 LLM 额度
    ckey = _cache_key(query, time_range, domain_filter)
    cached = _cache_get(ckey)
    if cached:
        _report(100, "完成")
        return cached

    _report(15, "多源搜索中")
    results = _search_ddg(query, num_results)
    if len(results) < 2:
        wiki_results = _search_fallback(query, num_results)
        results.extend(wiki_results)

    # v15：来源域过滤 + 时间筛选（先过滤再进 LLM 上下文，避免脏源干扰摘要）
    if domain_filter:
        results = _filter_results_by_domain(results, [d.strip() for d in domain_filter.split(",") if d.strip()])
    if time_range:
        results = _filter_results_by_time(results, time_range)

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
        result = {"query": query, "mode": "llm_only", "summary": summary, "sources": [], "related": related}
        _cache_set(ckey, result)
        return result

    search_context = ""
    for i, r in enumerate(results):
        search_context += f"\n[来源{i + 1}] {r['title']}\n{r['snippet']}\nURL: {r['url']}\n"

    _report(45, "AI 整合摘要中")
    time_constraint = TIME_RANGE_LABELS.get(time_range, "")
    if time_constraint:
        time_constraint = f"仅优先采用{time_constraint}内的信息；对超过时效的内容明确标注「时效性提醒」，不要作为主要结论依据。"
    else:
        time_constraint = "无特殊时效要求，正常标注各信息时间。"
    system_prompt = SEARCH_SUMMARY_SYSTEM.replace("{search_results}", search_context).replace(
        "{time_constraint}", time_constraint
    )
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
    result = {
        "query": query,
        "mode": "web_search",
        "summary": summary,
        "time_range": time_range,
        "domain_filter": domain_filter,
        "sources": [{"title": r["title"], "url": r["url"], "snippet": r["snippet"][:200]} for r in results],
        "related": [r["title"] for r in results[:3]],
    }
    _cache_set(ckey, result)
    return result


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
