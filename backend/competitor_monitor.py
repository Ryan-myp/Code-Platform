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
from common.llm import call_llm, log_usage, _safe_exc_msg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitor", tags=["竞品监控"])

# ── System Prompt ─────────────────────────────────────────

ANALYSIS_SYSTEM = """你是一位拥有10年+经验的竞争情报分析师和内容策略专家，曾为多个行业头部品牌提供竞品追踪和差异化策略咨询。

## 分析框架（SWOT+内容矩阵）
从以下6个维度对竞品内容进行系统性分析：

### 1. 内容策略定位
- 竞品的内容定位和品牌人设是什么
- 目标受众画像和内容-受众匹配度
- 差异化定位（相比同赛道其他竞品的独特之处）

### 2. 内容矩阵分析
- 内容类型分布（干货/情感/促销/互动/热点借势）及各类型占比
- 各类型内容的效果表现差异
- 有无定期栏目/IP化内容

### 3. 爆款规律提炼
- 近期的爆款内容（前20%阅读量/互动量的内容）有什么共同特征
- 标题模式、封面风格、开头节奏是否有可复用的公式
- 爆款内容的生命周期（多久进入衰退期）

### 4. 发布策略
- 发布频率和节奏（日更/周更/不定期）
- 最佳发布时间窗口
- 多平台分发策略和平台间差异化程度

### 5. 互动与增长
- 互动率水平（点赞/评论/分享/收藏）及趋势
- 评论区运营策略（是否积极回复、是否有引导话术）
- 粉丝增长质量和活跃度

### 6. 可攻击的弱点
- 竞品内容中缺失或薄弱的环节
- 用户评论中反映的未被满足的需求
- 可能存在的合规风险或品牌危机

## 输出要求
- 每个结论基于可观察的证据，不凭空推测
- hot_patterns提炼3条可复用的爆款规律
- competitive_advantages/weaknesses客观公正
- recommendations提供3-5条具体的差异化切入策略

输出严格JSON：
{
  "overview": "竞品整体评价（一句话定位+市场地位判断）",
  "content_categories": [
    {"name": "分类名", "percentage": 30, "effectiveness": "high|medium|low", "typical_example": "代表作品简述"}
  ],
  "hot_patterns": ["可复用的爆款规律1", "规律2", "规律3"],
  "publishing_habits": {
    "frequency": "发布频率描述",
    "best_times": ["最佳时段1", "最佳时段2"],
    "platform_focus": "主要平台",
    "multi_platform_strategy": "多平台分发策略简述"
  },
  "engagement_analysis": {
    "avg_likes": 0,
    "avg_comments": 0,
    "avg_shares": 0,
    "engagement_rate": "互动率估算",
    "trend": "up|stable|down"
  },
  "competitive_advantages": ["优势1", "优势2"],
  "competitive_weaknesses": ["劣势1", "劣势2"],
  "recommendations": ["具体的差异化切入策略1", "策略2", "策略3"]
}

只输出JSON，不要其他内容。"""

RADAR_SYSTEM = """你是竞品分析与数据可视化专家，擅长将多维度竞品数据转化为直观的雷达对比图。

## 雷达图设计原则
1. **维度选择**：6-8个维度覆盖竞品评估的核心面（过多拥挤、过少不够全面）
2. **评分客观**：基于实际数据而非感觉，每个维度有评分依据
3. **配色区分**：不同竞品使用有区分度的颜色，我方使用突出色
4. **max值合理**：根据维度特性设置合理的max值（百分比维度max=100，绝对数值维度max取实际最大值*1.2）

## 推荐评估维度（6-8个中选择）
- 内容质量：原创性、深度、信息密度
- 更新频率：内容产出速度
- 互动率：平均点赞+评论+分享/阅读
- 粉丝增长：月均新增粉丝
- 品牌声量：行业提及率、搜索指数
- 差异化程度：内容独特性和不可替代性
- 商业变现：带货/广告/知识付费能力
- 用户粘性：复访率、收藏率

输出ECharts雷达图配置JSON：
{
  "chart_type": "radar",
  "title": "竞品对比雷达图",
  "insight": "一句话雷达图解读（我方强项/弱项/机会点）",
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
            monitor_frequency TEXT DEFAULT 'weekly',
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
    # 存量库补 monitor_frequency 列（幂等，并发竞态忽略）
    cols = [r[1] for r in conn.execute("PRAGMA table_info(competitors)").fetchall()]
    if "monitor_frequency" not in cols:
        try:
            conn.execute("ALTER TABLE competitors ADD COLUMN monitor_frequency TEXT DEFAULT 'weekly'")
        except Exception:
            pass
    conn.commit()


# ── 变化摘要（确定性纯函数，可单测）──

# 需要对比的列表型字段 → 中文标签
_LIST_FIELDS = [
    ("hot_patterns", "爆款规律"),
    ("competitive_advantages", "竞争优势"),
    ("competitive_weaknesses", "竞争劣势"),
    ("recommendations", "策略建议"),
]

# 需要对比的标量型字段 → 中文标签（(字段路径, 标签)）
_SCALAR_FIELDS = [
    ("overview", "整体评价"),
    ("publishing_habits.frequency", "发布频率"),
    ("engagement_analysis.trend", "互动趋势"),
]


def _dig(obj: dict, path: str):
    """按 a.b.c 路径取值，缺失返回 None。"""
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def diff_reports(prev: dict | None, curr: dict) -> dict:
    """对比上次与本次分析，产出变化摘要（新增/移除/变更）。

    - 列表字段：集合差 → added / removed
    - 标量字段：值不同 → modified
    - summary：一句话概括变化规模，供前端 diff 高亮展示
    """
    curr = curr or {}
    if not prev:
        return {
            "summary": "首次分析，无历史对比基准",
            "changed": [],
            "total_changed": 0,
        }

    changed = []
    for field, label in _LIST_FIELDS:
        p_items = [str(x).strip() for x in (prev.get(field) or []) if str(x).strip()]
        c_items = [str(x).strip() for x in (curr.get(field) or []) if str(x).strip()]
        added = [x for x in c_items if x not in p_items]
        removed = [x for x in p_items if x not in c_items]
        if added or removed:
            changed.append({"field": field, "label": label, "added": added, "removed": removed})

    for path, label in _SCALAR_FIELDS:
        pv = _dig(prev, path)
        cv = _dig(curr, path)
        if pv is not None and cv is not None and pv != cv:
            changed.append(
                {"field": path, "label": label, "added": [], "removed": [], "modified": [{"prev": str(pv), "curr": str(cv)}]}
            )

    total = len(changed)
    if total == 0:
        summary = "与上次分析相比无显著变化"
    else:
        summary = f"发现 {total} 处变化：{('、'.join(c['label'] for c in changed))}"
    return {"summary": summary, "changed": changed, "total_changed": total}


# ── 模型 ──────────────────────────────────────────────────


class CompetitorAddRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="竞品名称")
    platform: str = Field(..., max_length=50, description="平台（如 抖音/小红书/B站/公众号）")
    account_id: str = Field("", max_length=200, description="账号ID/主页链接")
    description: str = Field("", max_length=500, description="竞品描述")
    profile_url: str = Field("", max_length=500, description="主页URL")
    monitor_frequency: str = Field("weekly", pattern="^(daily|weekly|monthly|manual)$", description="监控频率：daily/weekly/monthly/manual")


class AnalyzeRequest(BaseModel):
    competitor_ids: list[str] = Field(..., min_length=1, max_length=10, description="要分析的竞品ID列表")
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
           description, profile_url, monitor_frequency, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?) """,
        (comp_id, user, req.name, req.platform, req.account_id, req.description, req.profile_url, req.monitor_frequency, now, now),
    )
    conn.commit()
    conn.close()
    return {
        "id": comp_id,
        "name": req.name,
        "platform": req.platform,
        "monitor_frequency": req.monitor_frequency,
        "created_at": now,
    }


@router.get("/competitors")
async def list_competitors(frequency: str = "", current_user: dict = require_auth()):
    """竞品列表（支持按监控频率筛选）。"""
    conn = get_db()
    _ensure_tables(conn)
    if frequency in ("daily", "weekly", "monthly", "manual"):
        rows = conn.execute(
            "SELECT * FROM competitors WHERE monitor_frequency=? ORDER BY updated_at DESC LIMIT 100",
            (frequency,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM competitors ORDER BY updated_at DESC LIMIT 100").fetchall()
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
def analyze_competitors(req: AnalyzeRequest, current_user: dict = require_auth()):
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
    comp_desc = "\n".join(f"- {c['name']}（{c['platform']}）: {c['description']}" for c in competitors)

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
    except json.JSONDecodeError as e:
        raise HTTPException(500, "AI分析结果格式异常") from e
    except Exception as e:
        logger.exception("competitor analysis failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    # 2. 雷达图
    try:
        radar_raw = call_llm(
            RADAR_SYSTEM, f"分析以下竞品并生成雷达图：\n{comp_desc}", max_tokens=1500, temperature=0.3, timeout=60
        )
        radar_raw = radar_raw.strip()
        if radar_raw.startswith("```"):
            lines = radar_raw.split("\n")
            radar_raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        radar = json.loads(radar_raw)
    except Exception:
        radar = {"chart_type": "radar", "title": "竞品对比", "option": {}}

    # 3. 变化摘要：对比该批竞品最近一次报告
    changes = None
    conn = get_db()
    _ensure_tables(conn)
    try:
        prev_row = conn.execute(
            "SELECT analysis_data FROM competitor_reports WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user,),
        ).fetchone()
        if prev_row and prev_row[0]:
            prev_analysis = json.loads(prev_row[0]) if isinstance(prev_row[0], str) else prev_row[0]
            changes = diff_reports(prev_analysis, analysis)
    except (json.JSONDecodeError, TypeError):
        changes = None
    finally:
        conn.close()

    # 保存报告
    report_id = f"rpt_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO competitor_reports
           (id, user_id, competitor_ids, analysis_data, radar_data, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            report_id,
            user,
            json.dumps(req.competitor_ids),
            json.dumps(analysis, ensure_ascii=False),
            json.dumps(radar, ensure_ascii=False),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("competitor_analysis", len(user_prompt), len(raw), elapsed)

    return {
        "report_id": report_id,
        "competitors": [
            {"id": c["id"], "name": c["name"], "platform": c["platform"], "monitor_frequency": c.get("monitor_frequency", "weekly")}
            for c in competitors
        ],
        "analysis": analysis,
        "radar": radar,
        "changes": changes,
    }


@router.get("/report/{report_id}")
async def get_report(report_id: str, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    row = conn.execute("SELECT * FROM competitor_reports WHERE id=?", (report_id,)).fetchone()
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
    rows = conn.execute("SELECT * FROM competitor_reports ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
