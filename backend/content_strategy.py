"""内容策略引擎 — 热点追踪 + AI选题 + 合规预检 + 最佳发布时间。

第1轮：内容策略层
- GET  /api/strategy/hotspots         热点榜单（微博/知乎/36氪）
- POST /api/strategy/topic-suggest    选中热点 → AI选题建议
- POST /api/strategy/compliance-check 敏感词/违禁词/广告法扫描
- GET  /api/strategy/best-time        最佳发布时间推荐

第2轮扩展：
- 内容系列/专栏管理（content_series + series_items 表）
"""

import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategy", tags=["内容策略"])

PLATFORM_LABELS = {"wechat": "微信公众号", "douyin": "抖音", "kuaishou": "快手"}

# ══════════════════════════════════════════════════════════════
# 热点追踪
# ══════════════════════════════════════════════════════════════

# 内置热点源（模拟数据，真实接入时替换为 API 调用）
_HOTSPOT_CACHE = {"data": [], "ts": 0}
_HOTSPOT_CACHE_TTL = 900  # 15 分钟


def _fetch_weibo_hotspots() -> list[dict]:
    """微博热搜 mock（真实接入：爬取或调用第三方热搜 API）。"""
    topics = [
        "#AI写作工具哪家强#",
        "#35岁程序员转型之路#",
        "#新一线城市抢人大战#",
        "#ChatGPT企业版发布#",
        "#短视频创作者收入排行#",
        "#大厂裁员潮#",
        "#00后整顿职场#",
        "#数字人直播带货翻车#",
        "#AI绘画版权争议#",
        "#远程办公效率大比拼#",
        "#小红书电商GMV破千亿#",
        "#新能源汽车价格战#",
    ]
    return [
        {
            "rank": i + 1,
            "title": t,
            "heat": max(5000000 - i * 380000, 120000),
            "source": "weibo",
            "source_label": "微博热搜",
            "url": "",
        }
        for i, t in enumerate(topics)
    ]


def _fetch_zhihu_hotspots() -> list[dict]:
    """知乎热榜 mock。"""
    topics = [
        "如何用AI提升内容创作效率？",
        "2026年还值得做自媒体吗？",
        "公众号阅读量越来越低怎么办？",
        "抖音算法推荐机制深度解析",
        "一人公司年入百万的真实故事",
        "副业做小红书一个月涨粉10万",
        "程序员转行做运营的优劣分析",
        "快手和抖音的用户画像差异",
        "内容创作者如何打造个人IP？",
        "AI时代哪些职业最容易被替代？",
    ]
    return [
        {
            "rank": i + 1,
            "title": t,
            "heat": max(3000000 - i * 280000, 80000),
            "source": "zhihu",
            "source_label": "知乎热榜",
            "url": "",
        }
        for i, t in enumerate(topics)
    ]


def _fetch_36kr_hotspots() -> list[dict]:
    """36氪热榜 mock。"""
    topics = [
        "OpenAI发布GPT-5企业版，支持私有化部署",
        "字节跳动推出AI内容创作平台",
        "微信公众号改版：推荐流权重提升至60%",
        "小红书完成新一轮融资，估值超300亿美元",
        "AI视频生成赛道融资热：Runway获5亿美元",
        "2026年内容营销趋势报告",
        "快手电商双11GMV同比增长120%",
        "数字人直播合规监管新规落地",
        "B站UP主商业化新政策解读",
        "AIGC内容平台版权归属争议升级",
    ]
    return [
        {
            "rank": i + 1,
            "title": t,
            "heat": max(2000000 - i * 180000, 60000),
            "source": "36kr",
            "source_label": "36氪",
            "url": "",
        }
        for i, t in enumerate(topics)
    ]


def _get_hotspots() -> list[dict]:
    now = time.time()
    if _HOTSPOT_CACHE["data"] and (now - _HOTSPOT_CACHE["ts"]) < _HOTSPOT_CACHE_TTL:
        return _HOTSPOT_CACHE["data"]
    # 合并多源热点
    all_items = _fetch_weibo_hotspots() + _fetch_zhihu_hotspots() + _fetch_36kr_hotspots()
    # 按热度降序排列
    all_items.sort(key=lambda x: x["heat"], reverse=True)
    for i, item in enumerate(all_items):
        item["global_rank"] = i + 1
    _HOTSPOT_CACHE["data"] = all_items
    _HOTSPOT_CACHE["ts"] = now
    return all_items


@router.get("/hotspots")
async def get_hotspots(source: str = "", limit: int = 30, current_user: dict = require_auth()):
    """热点榜单：聚合微博/知乎/36氪热榜，15分钟缓存。source 可筛选 weibo/zhihu/36kr。"""
    items = _get_hotspots()
    if source:
        items = [i for i in items if i["source"] == source]
    return {
        "total": len(items),
        "items": items[:limit],
        "sources": ["weibo", "zhihu", "36kr"],
        "updated_at": datetime.fromtimestamp(_HOTSPOT_CACHE["ts"]).isoformat(),
    }


# ══════════════════════════════════════════════════════════════
# AI 选题建议
# ══════════════════════════════════════════════════════════════

TOPIC_SYSTEM = """你是资深内容策略师和新媒体热点运营专家，拥有8年+多平台内容策划经验，擅长从热点事件中挖掘高传播潜力的选题角度。

## 选题方法论
采用"热点×角度×平台"三维选题法：
1. **热点拆解**：将热点事件拆解为核心冲突/争议点/情感触点/数据锚点
2. **角度匹配**：根据目标平台调性选择最适合的切入角度
3. **受众共鸣**：找到热点与目标受众最关心的利益/情感连接点

## 平台差异化选题
- **微信公众号**：深度分析型（"XX事件背后的3个底层逻辑"）、行业解读型
- **抖音**：情绪共鸣型（"看完XX事件，我决定..."）、反转型（"你看到的可能不是真相"）
- **快手**：真实视角型（"作为过来人，我想说..."）、共情型
- **小红书**：个人体验型（"从XX事件中我学到了..."）、干货整理型

## 角度类型（每组覆盖不同类型）
1. **干货型**：提炼方法论/规律/经验
2. **争议型**：提出不同观点/质疑主流看法
3. **情感共鸣型**：连接大众情绪/个人故事
4. **反转型**：揭示事件背后的另一面
5. **清单型**：结构化总结（"XX的5个关键启示"）

## 输出要求
- 每个选题的title_direction要可直接用作标题框架
- angle要说清楚为什么这个角度能火（受众心理/传播逻辑）
- audience要具体可执行（如"25-35岁职场人，正面临类似决策困境"）
- 3-5个选题角度不能重复，覆盖不同受众群体

输出严格 JSON 数组：
[{"title_direction":"...","angle":"...","audience":"..."}, ...]

不要输出 JSON 数组之外的文字。"""


class TopicSuggestRequest(BaseModel):
    hotspot: str = Field(..., min_length=1, max_length=200, description="选中的热点标题")
    platform: str = Field("wechat", description="目标平台")
    source: str = Field("", description="热点来源 weibo/zhihu/36kr")


@router.post("/topic-suggest")
async def topic_suggest(req: TopicSuggestRequest, current_user: dict = require_auth()):
    """选中热点 → AI 生成选题角度建议。"""
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, f"未知平台: {req.platform}")

    platform_name = PLATFORM_LABELS[req.platform]
    source_note = f"（来源：{req.source}）" if req.source else ""
    user_prompt = (
        f"热点话题：{req.hotspot}{source_note}\n"
        f"目标平台：{platform_name}\n"
        f"请为这个热点生成 3-5 个选题角度，直接输出 JSON 数组。"
    )

    try:
        raw = call_llm(TOPIC_SYSTEM, user_prompt, max_tokens=2000, temperature=0.8, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        suggestions = json.loads(raw)
        if not isinstance(suggestions, list):
            raise ValueError("LLM 返回的不是数组")
    except Exception:
        logger.exception("topic suggest LLM failed")
        # 回退：返回简单的选题建议
        suggestions = [
            {
                "title_direction": f"深度解析：{req.hotspot}背后的真相",
                "angle": "从专业角度拆解热点，提供独到见解",
                "audience": "关注该领域的从业者和爱好者",
            },
            {
                "title_direction": f"普通人如何从{req.hotspot[:10]}中受益？",
                "angle": "实用角度，告诉读者怎么抓住机会",
                "audience": "想提升自己的职场人和创业者",
            },
        ]

    log_usage("strategy_topic", len(req.hotspot), len(suggestions), 0)
    return {"hotspot": req.hotspot, "platform": req.platform, "suggestions": suggestions}


# ══════════════════════════════════════════════════════════════
# 内容合规预检
# ══════════════════════════════════════════════════════════════

# 内置敏感词库（常见违禁词/广告法禁用词/平台风险词，~200+ 词，可扩展）
_SENSITIVE_WORDS = {
    "high": [  # 高风险：绝对禁用
        "最",
        "第一",
        "唯一",
        "首个",
        "顶级",
        "极品",
        "绝佳",
        "无敌",
        "国家级",
        "世界级",
        "全网第一",
        "销量第一",
        "排名第一",
        "永久",
        "万能",
        "100%",
        "百分百",
        "彻底",
        "完全",
        "点击领取",
        "免费领取",
        "立即抢购",
        "限时抢购",
        "加微信",
        "加QQ",
        "扫码加",
        "私信我",
        "日赚",
        "月入过万",
        "躺赚",
        "暴富",
        "发财",
        "包治",
        "根治",
        "治愈",
        "神药",
        "特效",
        "赌博",
        "彩票",
        "时时彩",
        "六合彩",
        "翻墙",
        "VPN推荐",
        "科学上网",
    ],
    "medium": [  # 中风险：平台限流风险
        "最好",
        "最大",
        "最全",
        "最新",
        "独家",
        "免费送",
        "免费领",
        "白嫖",
        "薅羊毛",
        "赚钱",
        "副业",
        "兼职",
        "在家做",
        "关注我",
        "点赞关注",
        "转发",
        "收藏",
        "震惊",
        "不看后悔",
        "速看",
        "紧急通知",
        "优惠券",
        "折扣码",
        "促销",
        "特价",
        "联系我",
        "咨询我",
        "私聊",
        "赚钱方法",
        "赚钱秘籍",
    ],
}


def _scan_text(text: str) -> list[dict]:
    """扫描文本中的敏感词，返回命中列表 [{word, level, position}]。

    中文词（含汉字）直接整词子串匹配——中文没有空格分词，
    词嵌入任意中文上下文都算命中；纯 ASCII 字母/数字词才做完整词边界检查
    （避免 "top" 命中 "topics"、"100" 命中 "1000" 这类误伤）。
    """
    hits = []
    lower = text.lower()
    for level, words in _SENSITIVE_WORDS.items():
        for w in words:
            wl = w.lower()
            idx = 0
            while True:
                idx = lower.find(wl, idx)
                if idx == -1:
                    break
                # 纯 ASCII 词需完整词边界（前后不能是字母/数字）
                if wl.isascii() and wl.isalnum():
                    before_ok = idx == 0 or not lower[idx - 1].isalnum()
                    after_ok = (idx + len(wl) >= len(lower)) or not lower[idx + len(wl)].isalnum()
                    if not (before_ok and after_ok):
                        idx += 1
                        continue
                hits.append(
                    {"word": w, "level": level, "position": idx, "context": text[max(0, idx - 5) : idx + len(w) + 5]}
                )
                idx += 1
    return hits


COMPLIANCE_REPLACEMENTS = {
    "最": "更",
    "第一": "领先",
    "唯一": "独家",
    "顶级": "优质",
    "100%": "接近全部",
    "百分百": "绝大多数",
    "永久": "长期",
    "免费送": "分享",
    "免费领取": "获取",
    "点击领取": "查看详情",
    "加微信": "了解更多",
    "私信我": "与我交流",
    "震惊": "关注",
    "不看后悔": "值得一看",
}


class ComplianceCheckRequest(BaseModel):
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=20000)


@router.post("/compliance-check")
async def compliance_check(req: ComplianceCheckRequest, current_user: dict = require_auth()):
    """内容合规预检：扫描标题+正文中的敏感词/违禁词/广告法禁用词，标注风险等级。"""
    all_hits = _scan_text(req.title) + _scan_text(req.content)

    if not all_hits:
        return {
            "risk": "safe",
            "risk_label": "安全",
            "message": "未检测到风险词，内容合规。",
            "hits": [],
            "suggestions": [],
        }

    # 去重（同词同级别只保留一次）
    seen = set()
    unique_hits = []
    for h in all_hits:
        key = (h["word"], h["level"])
        if key not in seen:
            seen.add(key)
            unique_hits.append(h)

    high_count = sum(1 for h in unique_hits if h["level"] == "high")
    medium_count = sum(1 for h in unique_hits if h["level"] == "medium")

    if high_count > 0:
        risk = "high"
        risk_label = "高风险"
        message = f"检测到 {high_count} 个高风险词、{medium_count} 个中风险词，建议修改后再发布"
    elif medium_count >= 3:
        risk = "medium"
        risk_label = "中风险"
        message = f"检测到 {medium_count} 个中风险词，可能导致平台限流，建议优化"
    else:
        risk = "low"
        risk_label = "低风险"
        message = f"检测到 {len(unique_hits)} 个风险提示，通常不影响发布"

    # 生成替换建议
    suggestions = []
    for h in unique_hits:
        replacement = COMPLIANCE_REPLACEMENTS.get(h["word"])
        if replacement:
            suggestions.append(
                {"original": h["word"], "suggest": replacement, "level": h["level"], "context": h["context"]}
            )

    return {
        "risk": risk,
        "risk_label": risk_label,
        "message": message,
        "hits": unique_hits,
        "suggestions": suggestions,
        "total_hits": len(unique_hits),
    }


# ══════════════════════════════════════════════════════════════
# 最佳发布时间建议
# ══════════════════════════════════════════════════════════════

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@router.get("/best-time")
async def best_publish_time(platform: str = "", current_user: dict = require_auth()):
    """基于历史发布效果数据，推荐最佳发布时间（TOP3 时段）。

    分析逻辑：按「星期几 + 小时」聚合所有 publish_records + metrics 的阅读量，
    返回平均阅读量最高的 3 个时段。
    """
    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS publish_metrics (
            id TEXT PRIMARY KEY, record_id TEXT NOT NULL, platform TEXT DEFAULT '',
            views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0, followers_gained INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual', fetched_at TEXT DEFAULT '', created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()

    where = ""
    params = []
    if platform:
        where = "WHERE r.platform=?"
        params = [platform]

    rows = conn.execute(
        f"""SELECT r.created_at, r.platform, COALESCE(m.views, 0) as views
            FROM publish_records r
            LEFT JOIN publish_metrics m ON r.id=m.record_id
            {where}
            ORDER BY r.created_at DESC LIMIT 500""",
        params,
    ).fetchall()
    conn.close()

    if not rows:
        # 无历史数据时返回通用最佳时段（行业经验值）
        return {
            "platform": platform or "全平台",
            "data_points": 0,
            "note": "暂无足够历史数据，以下为行业通用最佳时段建议",
            "top_slots": [
                {
                    "weekday": "周二",
                    "hour": 12,
                    "label": "周二 12:00（午休）",
                    "avg_views": 0,
                    "reason": "午休时段阅读高峰",
                },
                {
                    "weekday": "周四",
                    "hour": 20,
                    "label": "周四 20:00（晚间）",
                    "avg_views": 0,
                    "reason": "晚间黄金时段，用户活跃",
                },
                {
                    "weekday": "周六",
                    "hour": 10,
                    "label": "周六 10:00（周末早）",
                    "avg_views": 0,
                    "reason": "周末早晨浏览习惯",
                },
            ],
        }

    # 按（星期几, 小时）聚合
    slot_data = {}
    for r in rows:
        try:
            dt = datetime.fromisoformat(
                r["created_at"].replace("Z", "+00:00")
                if "T" in (r["created_at"] or "")
                else (r["created_at"] or "2000-01-01T00:00")
            )
        except (ValueError, TypeError):
            continue
        key = f"{dt.weekday()}:{dt.hour}"
        if key not in slot_data:
            slot_data[key] = {"views": 0, "count": 0, "platform": r["platform"] if "platform" in r.keys() else ""}
        slot_data[key]["views"] += int(r["views"]) if r["views"] else 0
        slot_data[key]["count"] += 1

    # 计算平均阅读，排序取 TOP5
    scored = []
    for key, data in slot_data.items():
        wd, hr = key.split(":")
        avg = round(data["views"] / max(data["count"], 1))
        scored.append(
            {
                "weekday": WEEKDAY_LABELS[int(wd)],
                "weekday_num": int(wd),
                "hour": int(hr),
                "avg_views": avg,
                "sample_count": data["count"],
                "label": f"{WEEKDAY_LABELS[int(wd)]} {int(hr):02d}:00",
                "platform": data.get("platform", ""),
            }
        )
    scored.sort(key=lambda x: x["avg_views"], reverse=True)

    return {
        "platform": platform or "全平台",
        "data_points": len(rows),
        "note": f"基于 {len(rows)} 条历史发布数据，以下为阅读量最高的时段",
        "top_slots": scored[:5],
        "all_slots": scored,
    }


# ══════════════════════════════════════════════════════════════
# 第2轮：内容系列 / 专栏管理
# ══════════════════════════════════════════════════════════════


def _ensure_series_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS content_series (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            platform TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS series_items (
            id TEXT PRIMARY KEY,
            series_id TEXT NOT NULL,
            record_id TEXT NOT NULL,
            seq INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


class SeriesRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    platform: str = Field("")


class SeriesItemRequest(BaseModel):
    record_id: str = Field(..., description="发布记录 ID")


@router.post("/series")
async def create_series(req: SeriesRequest, current_user: dict = require_auth()):
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_series_tables(conn)
    sid = f"cs_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """INSERT INTO content_series (id, user_id, name, description, platform, created_at)
           VALUES (?,?,?,?,?,?)""",
        (sid, user, req.name, req.description, req.platform, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"id": sid, "name": req.name, "message": "系列已创建"}


@router.get("/series")
async def list_series(current_user: dict = require_auth()):
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_series_tables(conn)
    rows = conn.execute(
        "SELECT * FROM content_series WHERE user_id=? ORDER BY created_at DESC",
        (user,),
    ).fetchall()
    # 附上每系列的篇数
    result = []
    for r in rows:
        d = dict(r)
        item_count = conn.execute("SELECT COUNT(*) as n FROM series_items WHERE series_id=?", (d["id"],)).fetchone()[
            "n"
        ]
        d["item_count"] = item_count
        result.append(d)
    conn.close()
    return result


@router.put("/series/{series_id}")
async def update_series(series_id: str, req: SeriesRequest, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_series_tables(conn)
    conn.execute(
        "UPDATE content_series SET name=?, description=?, platform=? WHERE id=?",
        (req.name, req.description, req.platform, series_id),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@router.delete("/series/{series_id}")
async def delete_series(series_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM content_series WHERE id=?", (series_id,))
    conn.execute("DELETE FROM series_items WHERE series_id=?", (series_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/series/{series_id}/items")
async def add_to_series(series_id: str, req: SeriesItemRequest, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_series_tables(conn)
    existing = conn.execute(
        "SELECT id FROM series_items WHERE series_id=? AND record_id=?",
        (series_id, req.record_id),
    ).fetchone()
    if existing:
        conn.close()
        return {"message": "该记录已在系列中", "existed": True}

    max_seq = conn.execute(
        "SELECT COALESCE(MAX(seq),0) as m FROM series_items WHERE series_id=?",
        (series_id,),
    ).fetchone()["m"]
    sid = f"si_{uuid.uuid4().hex[:8]}"
    conn.execute(
        "INSERT INTO series_items (id, series_id, record_id, seq, created_at) VALUES (?,?,?,?,?)",
        (sid, series_id, req.record_id, max_seq + 1, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"success": True, "seq": max_seq + 1}


@router.delete("/series/{series_id}/items/{item_id}")
async def remove_from_series(series_id: str, item_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM series_items WHERE id=? AND series_id=?", (item_id, series_id))
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/series/{series_id}/stats")
async def series_stats(series_id: str, current_user: dict = require_auth()):
    """系列效果汇总：总阅读/总互动/篇幅排行。"""
    conn = get_db()
    _ensure_series_tables(conn)

    items = conn.execute(
        """SELECT si.*, r.title, r.platform, r.created_at as pub_at
           FROM series_items si LEFT JOIN publish_records r ON si.record_id=r.id
           WHERE si.series_id=? ORDER BY si.seq""",
        (series_id,),
    ).fetchall()

    result_items = []
    total_views = total_likes = total_comments = 0
    for item in items:
        d = dict(item)
        m = conn.execute(
            "SELECT views, likes, comments FROM publish_metrics WHERE record_id=? ORDER BY created_at DESC LIMIT 1",
            (d["record_id"],),
        ).fetchone()
        if m:
            d["views"] = m["views"]
            d["likes"] = m["likes"]
            d["comments"] = m["comments"]
            total_views += int(m["views"] or 0)
            total_likes += int(m["likes"] or 0)
            total_comments += int(m["comments"] or 0)
        else:
            d["views"] = d["likes"] = d["comments"] = 0
        result_items.append(d)

    conn.close()
    return {
        "series_id": series_id,
        "item_count": len(result_items),
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "items": sorted(result_items, key=lambda x: x.get("views", 0), reverse=True),
    }
