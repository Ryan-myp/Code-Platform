"""增长引擎 — 批量变体生产 + 效果追踪 + AI 复盘。

阶段 2：批量变体生产流水线
- POST /api/growth/batch       主题 → LLM 生成 N 组变体（标题/正文/话题/封面风格）
- GET  /api/growth/variants     变体列表
- PUT  /api/growth/variants/{id} 编辑变体
- DELETE /api/growth/variants/{id} 删除
- POST /api/growth/batch-schedule 勾选变体 → 批量创建排期

阶段 3：发布效果追踪 + AI 复盘（同文件扩展）
- GET  /api/growth/metrics/{record_id}  拉取 / 查看效果数据
- POST /api/growth/metrics/{record_id}  手动录入兜底
- POST /api/growth/review               AI 复盘报告
"""

import json
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/growth", tags=["增长引擎"])

PLATFORM_LABELS = {"wechat": "微信公众号", "douyin": "抖音", "kuaishou": "快手"}

# ── 变体生成 prompt ──────────────────────────────────────────
VARIANT_SYSTEM = """你是顶级内容营销专家，专精于多平台内容变体创作。

你的任务：根据一个核心主题，为指定平台生成多组风格各异的「标题党」变体。
每组变体包含：
1. 标题：吸引眼球、符合平台调性、激发点击欲
2. 正文/文案：适配平台风格，自然融入关键词
3. 话题标签：3-5 个精准标签
4. 封面风格建议：颜色/构图/文字风格

要求：
- 各组之间有明显差异化（角度不同：干货型、故事型、争议型、清单型、热点借势型）
- 标题控制在 15-30 字，正文 80-200 字
- 输出严格 JSON 数组格式：[{"title":"...","content":"...","topics":["tag1","tag2"],"cover_style":"..."}, ...]
- 不要输出任何 JSON 之外的文字"""


def _ensure_variant_columns(conn) -> None:
    """幂等建表：growth_variants。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS growth_variants (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            theme TEXT DEFAULT '',
            platform TEXT DEFAULT 'wechat',
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            topics TEXT DEFAULT '[]',
            cover_style TEXT DEFAULT '',
            selected INTEGER DEFAULT 1,
            scheduled_at TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


class BatchGenerateRequest(BaseModel):
    theme: str = Field(..., min_length=1, max_length=200, description="核心主题")
    platform: str = Field("wechat", description="目标平台 wechat/douyin/kuaishou")
    count: int = Field(5, ge=1, le=10, description="生成变体数量")


class VariantUpdateRequest(BaseModel):
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=20000)
    topics: list[str] = Field(default_factory=list)
    cover_style: str = Field("", max_length=200)
    selected: bool = True


class BatchScheduleRequest(BaseModel):
    variant_ids: list[str] = Field(..., min_length=1, description="要排期的变体 ID 列表")
    interval_minutes: int = Field(60, ge=10, le=1440, description="排期间隔（分钟）")
    start_at: str = Field("", description="首条发布时间 ISO 格式，空则从现在+5分钟开始")


@router.post("/batch")
async def batch_generate(req: BatchGenerateRequest, current_user: dict = require_auth()):
    """主题 → LLM 批量生成 N 组内容变体（标题/正文/话题/封面风格）。"""
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, f"未知平台: {req.platform}")

    platform_name = PLATFORM_LABELS[req.platform]
    user_prompt = (
        f"核心主题：{req.theme}\n"
        f"目标平台：{platform_name}\n"
        f"生成数量：{req.count} 组\n"
        f"请为这个主题创作 {req.count} 组风格各异的变体，直接输出 JSON 数组。"
    )

    try:
        raw = call_llm(VARIANT_SYSTEM, user_prompt, max_tokens=4000, temperature=0.85, timeout=120)
        # 提取 JSON 数组
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        variants = json.loads(raw)
        if not isinstance(variants, list):
            raise ValueError("LLM 返回的不是数组")
    except Exception as e:
        logger.exception("batch generate LLM failed")
        raise HTTPException(502, f"变体生成失败（AI 服务可能暂时不可用）：{e}")

    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_variant_columns(conn)
    now = datetime.now().isoformat()
    saved = []
    for v in variants[: req.count]:
        vid = f"gv_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """INSERT INTO growth_variants (id, user_id, theme, platform, title, content,
               topics, cover_style, selected, created_at)
               VALUES (?,?,?,?,?,?,?,?,1,?)""",
            (
                vid, user, req.theme, req.platform,
                str(v.get("title", ""))[:200],
                str(v.get("content", ""))[:20000],
                json.dumps([str(t) for t in v.get("topics", [])], ensure_ascii=False),
                str(v.get("cover_style", ""))[:200],
                now,
            ),
        )
        saved.append({
            "id": vid, "theme": req.theme, "platform": req.platform,
            "title": v.get("title", ""), "content": v.get("content", ""),
            "topics": v.get("topics", []), "cover_style": v.get("cover_style", ""),
            "selected": True, "created_at": now,
        })
    conn.commit()
    conn.close()
    log_usage("growth_batch", len(req.theme), len(saved), 0)
    return {"generated": len(saved), "variants": saved}


@router.get("/variants")
async def list_variants(
    platform: str = "",
    theme: str = "",
    limit: int = 100,
    current_user: dict = require_auth(),
):
    """变体列表，支持按平台/主题筛选。"""
    conn = get_db()
    _ensure_variant_columns(conn)
    where, params = [], []
    if platform:
        where.append("platform=?")
        params.append(platform)
    if theme:
        where.append("theme LIKE ?")
        params.append(f"%{theme}%")
    sql = "SELECT * FROM growth_variants"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["selected"] = bool(d.get("selected"))
        result.append(d)
    return result


@router.put("/variants/{variant_id}")
async def update_variant(variant_id: str, req: VariantUpdateRequest, current_user: dict = require_auth()):
    """编辑变体内容 / 切换勾选状态。"""
    conn = get_db()
    _ensure_variant_columns(conn)
    row = conn.execute("SELECT * FROM growth_variants WHERE id=?", (variant_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "变体不存在")
    conn.execute(
        """UPDATE growth_variants SET title=?, content=?, topics=?, cover_style=?,
           selected=? WHERE id=?""",
        (
            req.title or row["title"],
            req.content or row["content"],
            json.dumps(req.topics, ensure_ascii=False) if req.topics else row["topics"],
            req.cover_style or row["cover_style"],
            1 if req.selected else 0,
            variant_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"success": True, "id": variant_id}


@router.delete("/variants/{variant_id}")
async def delete_variant(variant_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM growth_variants WHERE id=?", (variant_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/batch-schedule")
async def batch_schedule_variants(req: BatchScheduleRequest, current_user: dict = require_auth()):
    """勾选变体 → 批量创建发布排期（按间隔时间依次排开）。"""
    conn = get_db()
    _ensure_variant_columns(conn)
    placeholders = ",".join("?" for _ in req.variant_ids)
    rows = conn.execute(
        f"SELECT * FROM growth_variants WHERE id IN ({placeholders}) AND selected=1",
        req.variant_ids,
    ).fetchall()
    if not rows:
        conn.close()
        raise HTTPException(400, "没有找到勾选的变体，请先在列表中勾选要排期的变体")

    # 计算排期起始时间
    if req.start_at:
        try:
            start_dt = datetime.fromisoformat(req.start_at.replace("Z", "+00:00"))
        except ValueError:
            conn.close()
            raise HTTPException(400, "开始时间格式不正确，应为 YYYY-MM-DDTHH:MM")
    else:
        start_dt = datetime.now() + timedelta(minutes=5)

    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    scheduled_count = 0
    for i, row in enumerate(rows):
        r = dict(row)
        sched_at = (start_dt + timedelta(minutes=i * req.interval_minutes)).isoformat()
        sched_id = f"gsched_{uuid.uuid4().hex[:10]}"
        # 写入 publish_schedules 表（复用发布中心排期）
        conn.execute(
            """INSERT INTO publish_schedules (id, user_id, platform, content_type, title, content,
               topics, asset_urls, account_id, scheduled_at, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                sched_id, user, r["platform"], "article",
                r["title"], r["content"],
                r["topics"], "[]", "", sched_at, "pending",
                datetime.now().isoformat(),
            ),
        )
        # 标记变体已排期
        conn.execute(
            "UPDATE growth_variants SET scheduled_at=? WHERE id=?",
            (sched_at, r["id"]),
        )
        scheduled_count += 1

    conn.commit()
    conn.close()
    return {
        "scheduled": scheduled_count,
        "message": f"已创建 {scheduled_count} 条发布排期，间隔 {req.interval_minutes} 分钟",
    }


# ══════════════════════════════════════════════════════════════
# 阶段 3：发布效果追踪 + AI 复盘
# ══════════════════════════════════════════════════════════════

def _ensure_metrics_columns(conn) -> None:
    """幂等建表 + 补列：publish_metrics。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS publish_metrics (
            id TEXT PRIMARY KEY,
            record_id TEXT NOT NULL,
            platform TEXT DEFAULT '',
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            followers_gained INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual',
            fetched_at TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


class MetricsUpsertRequest(BaseModel):
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    followers_gained: int = 0


@router.get("/metrics/{record_id}")
async def get_metrics(record_id: str, current_user: dict = require_auth()):
    """获取某条发布记录的效果数据（自动拉取尽力而为 + 手动录入兜底）。"""
    conn = get_db()
    _ensure_metrics_columns(conn)
    row = conn.execute(
        "SELECT * FROM publish_metrics WHERE record_id=? ORDER BY created_at DESC LIMIT 1",
        (record_id,),
    ).fetchone()
    conn.close()
    if not row:
        return {"record_id": record_id, "views": 0, "likes": 0, "comments": 0,
                "shares": 0, "followers_gained": 0, "source": "none",
                "note": "暂无效果数据，可手动录入或等待平台 API 自动拉取"}
    return dict(row)


@router.post("/metrics/{record_id}")
async def upsert_metrics(record_id: str, req: MetricsUpsertRequest, current_user: dict = require_auth()):
    """手动录入 / 更新发布效果数据。"""
    conn = get_db()
    _ensure_metrics_columns(conn)
    now = datetime.now().isoformat()
    # 查发布记录获取 platform
    pub_row = conn.execute("SELECT platform FROM publish_records WHERE id=?", (record_id,)).fetchone()
    platform = pub_row["platform"] if pub_row else ""

    existing = conn.execute(
        "SELECT id FROM publish_metrics WHERE record_id=? ORDER BY created_at DESC LIMIT 1",
        (record_id,),
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE publish_metrics SET views=?, likes=?, comments=?, shares=?,
               followers_gained=?, fetched_at=?, source='manual'
               WHERE id=?""",
            (req.views, req.likes, req.comments, req.shares,
             req.followers_gained, now, existing["id"]),
        )
    else:
        mid = f"pm_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """INSERT INTO publish_metrics (id, record_id, platform, views, likes,
               comments, shares, followers_gained, source, fetched_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (mid, record_id, platform, req.views, req.likes, req.comments,
             req.shares, req.followers_gained, "manual", now, now),
        )
    conn.commit()
    conn.close()
    return {"success": True, "record_id": record_id,
            "views": req.views, "likes": req.likes, "comments": req.comments}


@router.get("/metrics-dashboard")
async def metrics_dashboard(
    platform: str = "",
    days: int = 30,
    current_user: dict = require_auth(),
):
    """效果数据看板：聚合总阅读/总涨粉/平台分布/各篇效果排行。"""
    conn = get_db()
    _ensure_metrics_columns(conn)

    where = ""
    params = []
    if platform:
        where = "WHERE m.platform=?"
        params = [platform]

    total_views = conn.execute(
        f"SELECT COALESCE(SUM(views),0) AS n FROM publish_metrics m {where}", params
    ).fetchone()["n"]
    total_likes = conn.execute(
        f"SELECT COALESCE(SUM(likes),0) AS n FROM publish_metrics m {where}", params
    ).fetchone()["n"]
    total_comments = conn.execute(
        f"SELECT COALESCE(SUM(comments),0) AS n FROM publish_metrics m {where}", params
    ).fetchone()["n"]
    total_shares = conn.execute(
        f"SELECT COALESCE(SUM(shares),0) AS n FROM publish_metrics m {where}", params
    ).fetchone()["n"]
    total_followers = conn.execute(
        f"SELECT COALESCE(SUM(followers_gained),0) AS n FROM publish_metrics m {where}", params
    ).fetchone()["n"]

    # 平台分布
    by_platform = {}
    for r in conn.execute(
        "SELECT m.platform, COALESCE(SUM(m.views),0) AS v FROM publish_metrics m "
        + (where.replace("m.", "m.") if where else "").replace("WHERE", "WHERE" if not where else "AND"),
        params,
    ).fetchall():
        by_platform[r["platform"]] = {"views": r["v"]}

    # 各篇排行（关联发布记录取标题）
    top_items = []
    sql_top = (
        "SELECT m.record_id, m.views, m.likes, m.comments, m.shares, m.followers_gained, "
        "r.title, r.platform "
        "FROM publish_metrics m LEFT JOIN publish_records r ON m.record_id=r.id "
        + (where.replace("m.", "m.").replace("WHERE", "WHERE" if not where else "AND")
           if where else "")
        + " ORDER BY m.views DESC LIMIT 20"
    )
    for r in conn.execute(sql_top, params).fetchall():
        top_items.append(dict(r))

    conn.close()
    return {
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "total_followers": total_followers,
        "by_platform": by_platform,
        "top_items": top_items,
    }


REVIEW_SYSTEM = """你是资深内容运营分析师，擅长基于数据做内容复盘。

请根据提供的发布效果数据，生成一份简明的 AI 复盘报告。报告结构：
1. **整体概览**：总阅读/互动/涨粉情况一句话总结
2. **爆款分析**：数据最好的 1-2 篇为什么好（标题/话题/发布时间角度）
3. **问题诊断**：数据不好的内容可能的问题
4. **下期建议**：选题方向、标题策略、发布时间建议

报告要具体、可执行，不要泛泛而谈。控制在 500 字以内。"""


@router.post("/review")
async def ai_review(
    platform: str = "",
    days: int = 30,
    current_user: dict = require_auth(),
):
    """AI 复盘报告：基于最近 N 天的效果数据 + 内容标题，LLM 生成运营建议。"""
    # 先拉数据
    conn = get_db()
    _ensure_metrics_columns(conn)

    where = "WHERE m.created_at >= datetime('now', ?)"
    params = [f"-{days} days"]
    if platform:
        where += " AND m.platform=?"
        params.append(platform)

    rows = conn.execute(
        f"SELECT m.*, r.title, r.content, r.platform, r.created_at as pub_at "
        f"FROM publish_metrics m LEFT JOIN publish_records r ON m.record_id=r.id "
        f"{where} ORDER BY m.views DESC LIMIT 30",
        params,
    ).fetchall()
    conn.close()

    if not rows:
        return {"report": f"最近 {days} 天暂无效果数据，请先录入发布数据后再生成复盘报告。", "data_points": 0}

    # 组装数据摘要给 LLM
    data_lines = [f"近 {days} 天共有 {len(rows)} 条有效数据：\n"]
    for r in rows:
        data_lines.append(
            f"- [{r.get('platform', '')}]《{r.get('title', '无标题')[:40]}》"
            f" 阅读:{r.get('views', 0)} 点赞:{r.get('likes', 0)} "
            f"评论:{r.get('comments', 0)} 涨粉:{r.get('followers_gained', 0)}"
        )

    total_v = sum(r.get("views", 0) for r in rows)
    total_l = sum(r.get("likes", 0) for r in rows)
    total_f = sum(r.get("followers_gained", 0) for r in rows)
    summary = f"\n汇总：总阅读 {total_v}，总点赞 {total_l}，总涨粉 {total_f}"

    user_prompt = "\n".join(data_lines) + summary + "\n\n请基于以上数据生成复盘报告。"

    try:
        report = call_llm(REVIEW_SYSTEM, user_prompt, max_tokens=1500, temperature=0.55, timeout=90)
    except Exception as e:
        logger.exception("ai review LLM failed")
        report = f"AI 复盘生成失败（{e}），请稍后重试。以下是原始数据摘要：\n\n{user_prompt}"

    log_usage("growth_review", len(user_prompt), len(report), 0)
    return {"report": report, "data_points": len(rows),
            "total_views": total_v, "total_likes": total_l, "total_followers": total_f}


# ══════════════════════════════════════════════════════════════
# 阶段 3 补充：评论互动聚合 + AI 回复
# ══════════════════════════════════════════════════════════════

def _ensure_comments_table(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS publish_comments (
            id TEXT PRIMARY KEY,
            record_id TEXT NOT NULL,
            platform TEXT DEFAULT '',
            author TEXT DEFAULT '',
            content TEXT DEFAULT '',
            likes INTEGER DEFAULT 0,
            replied INTEGER DEFAULT 0,
            reply_content TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


class CommentAddRequest(BaseModel):
    record_id: str = Field(..., description="发布记录 ID")
    author: str = Field("匿名用户", max_length=100)
    content: str = Field(..., min_length=1, max_length=2000)
    platform: str = Field("")
    likes: int = Field(0)


@router.get("/comments")
async def list_comments(record_id: str = "", platform: str = "", limit: int = 50, current_user: dict = require_auth()):
    """评论列表：按发布记录筛选，未指定 record_id 时返回最近评论。"""
    conn = get_db()
    _ensure_comments_table(conn)
    where, params = [], []
    if record_id:
        where.append("record_id=?")
        params.append(record_id)
    if platform:
        where.append("platform=?")
        params.append(platform)
    sql = "SELECT * FROM publish_comments"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/comments")
async def add_comment(req: CommentAddRequest, current_user: dict = require_auth()):
    """手动添加评论（平台 API 不可用时兜底录入）。"""
    conn = get_db()
    _ensure_comments_table(conn)
    # 自动获取发布记录的 platform
    platform = req.platform
    if not platform:
        pub = conn.execute("SELECT platform FROM publish_records WHERE id=?", (req.record_id,)).fetchone()
        if pub:
            platform = pub["platform"]
    cid = f"cmt_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """INSERT INTO publish_comments (id, record_id, platform, author, content,
           likes, replied, source, created_at) VALUES (?,?,?,?,?,?,0,?,?)""",
        (cid, req.record_id, platform, req.author, req.content,
         req.likes, "manual", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"id": cid, "message": "评论已录入"}


REPLY_SYSTEM = """你是专业的内容运营，负责回复读者评论。

要求：
- 语气亲切自然，像真人回复而非机器
- 根据评论内容个性化回复（赞同/感谢/解答/引导讨论）
- 控制在 50 字以内
- 不要用"亲爱的用户"等模板化开头
- 直接给出回复内容，不要多余说明"""


@router.post("/comments/{comment_id}/reply")
async def ai_reply_suggest(comment_id: str, current_user: dict = require_auth()):
    """AI 生成评论回复建议（不自动发送，用户确认后手动粘贴回复）。"""
    conn = get_db()
    _ensure_comments_table(conn)
    row = conn.execute("SELECT * FROM publish_comments WHERE id=?", (comment_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "评论不存在")
    comment = dict(row)
    conn.close()

    user_prompt = f"读者评论：{comment['content']}\n作者：{comment.get('author', '匿名')}\n请生成一条亲切自然的回复。"
    try:
        reply = call_llm(REPLY_SYSTEM, user_prompt, max_tokens=200, temperature=0.7, timeout=30)
    except Exception as e:
        logger.exception("ai reply failed")
        reply = f"感谢你的留言！（AI回复生成失败：{e}）"

    # 保存回复到数据库
    conn = get_db()
    conn.execute(
        "UPDATE publish_comments SET reply_content=?, replied=1 WHERE id=?",
        (reply, comment_id),
    )
    conn.commit()
    conn.close()
    log_usage("growth_reply", len(comment["content"]), len(reply), 0)
    return {"comment_id": comment_id, "reply": reply, "author": comment.get("author", "")}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM publish_comments WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()
    return {"success": True}
