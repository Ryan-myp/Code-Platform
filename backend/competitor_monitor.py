"""竞品监控与舆情分析 — 竞品追踪 + AI策略分析 + 对比雷达图。

- POST /api/monitor/competitors   添加竞品
- GET  /api/monitor/competitors   竞品列表
- POST /api/monitor/analyze       AI分析竞品内容策略
- GET  /api/monitor/report/{id}   竞品对比雷达图
"""

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitor", tags=["竞品监控"])

# ── System Prompt ─────────────────────────────────────────

ANALYSIS_SYSTEM = """你是一位专业的内容策略分析师。请分析竞品的内容策略，输出JSON格式：

{
  "overview": "竞品整体评价（一句话）",
  "content_categories": [
    {"name": "分类名", "percentage": 30, "effectiveness": "high|medium|low"}
  ],
  "hot_patterns": ["爆款规律1", "爆款规律2", "爆款规律3"],
  "publishing_habits": {
    "frequency": "发布频率描述",
    "best_times": ["最佳时段1", "最佳时段2"],
    "platform_focus": "主要平台"
  },
  "engagement_analysis": {
    "avg_likes": 数字,
    "avg_comments": 数字,
    "avg_shares": 数字,
    "trend": "up|stable|down"
  },
  "competitive_advantages": ["优势1", "优势2"],
  "competitive_weaknesses": ["劣势1", "劣势2"],
  "recommendations": ["差异化建议1", "差异化建议2", "差异化建议3"]
}

只输出JSON，不要其他内容。"""

RADAR_SYSTEM = """你是竞品分析专家。基于竞品的表现数据，生成一个对比雷达图配置，输出JSON格式：

{
  "chart_type": "radar",
  "title": "竞品对比雷达图",
  "option": {
    "radar": {
      "indicator": [
        {"name": "维度1", "max": 100},
        {"name": "维度2", "max": 100}
      ]
    },
    "series": [{
      "name": "竞品名称",
      "type": "radar",
      "data": [{"name": "竞品名称", "value": [80, 75, 90]}]
    }]
  }
}

比较维度建议：内容质量、更新频率、互动率、粉丝增长、品牌声量、差异化程度
只输出JSON，不要其他内容。"""

# ── 数据库 ──────────────────────────────────────────────────
def _ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS competitors (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            platform TEXT DEFAULT '',
            account_id TEXT DEFAULT '',
            description TEXT DEFAULT '',
            profile_url TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS competitor_reports (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            competitor_ids TEXT DEFAULT '',
            analysis_data TEXT DEFAULT '',
            radar_data TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


# ── 模型 ──────────────────────────────────────────────────

class CompetitorAddRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="竞品名称")
    platform: str = Field(..., max_length=50, description="平台（如 抖音/小红书/B站/公众号）")
    account_id: str = Field("", max_length=200, description="账号ID/主页链接")
    description: str = Field("", max_length=500, description="竞品描述")
    profile_url: str = Field("", max_length=500, description="主页URL")


class AnalyzeRequest(BaseModel):
    competitor_ids: list[str] = Field(..., min_length=1, max_length=10,
                                       description="要分析的竞品ID列表")
    query: str = Field("", max_length=500, description="可选：分析重点（如：聚焦选题策略）")


# ── API ──────────────────────────────────────────────────

@router.post("/competitors")
async def add_competitor(req: CompetitorAddRequest, current_user: dict = require_auth()):
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    comp_id = f"comp_{uuid.uuid4().hex[:10]}"
    now = datetime.now().isoformat()
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO competitors (id, user_id, name, platform, account_id,
           description, profile_url, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (comp_id, user, req.name, req.platform, req.account_id,
         req.description, req.profile_url, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": comp_id, "name": req.name, "platform": req.platform, "created_at": now}


@router.get("/competitors")
async def list_competitors(current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM competitors ORDER BY updated_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.delete("/competitors/{comp_id}")
async def delete_competitor(comp_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM competitors WHERE id=?", (comp_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/analyze")
async def analyze_competitors(req: AnalyzeRequest, current_user: dict = require_auth()):
    """AI分析竞品内容策略 + 生成对比雷达图。"""
    start = datetime.now()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    # 获取竞品信息
    conn = get_db()
    _ensure_tables(conn)
    placeholders = ",".join("?" * len(req.competitor_ids))
    rows = conn.execute(
        f"SELECT * FROM competitors WHERE id IN ({placeholders})",
        req.competitor_ids,
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(404, "未找到指定竞品")

    competitors = [dict(r) for r in rows]
    comp_desc = "\n".join(
        f"- {c['name']}（{c['platform']}）: {c['description']}"
        for c in competitors
    )

    user_prompt = f"竞品列表：\n{comp_desc}"
    if req.query:
        user_prompt += f"\n\n分析重点：{req.query}"

    # 1. 策略分析
    try:
        raw = call_llm(ANALYSIS_SYSTEM, user_prompt, max_tokens=2000, temperature=0.4, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        analysis = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, "AI分析结果格式异常")
    except Exception as e:
        logger.exception("competitor analysis failed")
        raise HTTPException(500, f"竞品分析失败：{e}")

    # 2. 雷达图
    try:
        radar_raw = call_llm(RADAR_SYSTEM, f"分析以下竞品并生成雷达图：\n{comp_desc}",
                             max_tokens=1500, temperature=0.3, timeout=60)
        radar_raw = radar_raw.strip()
        if radar_raw.startswith("```"):
            lines = radar_raw.split("\n")
            radar_raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        radar = json.loads(radar_raw)
    except Exception:
        radar = {"chart_type": "radar", "title": "竞品对比", "option": {}}

    # 保存报告
    report_id = f"rpt_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO competitor_reports
           (id, user_id, competitor_ids, analysis_data, radar_data, created_at)
           VALUES (?,?,?,?,?,?)""",
        (report_id, user, json.dumps(req.competitor_ids),
         json.dumps(analysis, ensure_ascii=False),
         json.dumps(radar, ensure_ascii=False),
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("competitor_analysis", len(user_prompt), len(raw), elapsed)

    return {
        "report_id": report_id,
        "competitors": [{"id": c["id"], "name": c["name"], "platform": c["platform"]} for c in competitors],
        "analysis": analysis,
        "radar": radar,
    }


@router.get("/report/{report_id}")
async def get_report(report_id: str, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM competitor_reports WHERE id=?", (report_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "报告不存在")
    r = dict(row)
    try:
        r["competitor_ids"] = json.loads(r.get("competitor_ids", "[]"))
        r["analysis_data"] = json.loads(r.get("analysis_data", "{}"))
        r["radar_data"] = json.loads(r.get("radar_data", "{}"))
    except (json.JSONDecodeError, TypeError):
        pass
    return r


@router.get("/reports")
async def list_reports(limit: int = 50, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM competitor_reports ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
