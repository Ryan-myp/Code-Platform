"""智能数据分析看板 — 自然语言 → 图表（ECharts 配置） + 数据源管理。

- POST /api/dashboard/nl-query   自然语言→自动SQL/聚合→ECharts图表配置JSON
- GET  /api/dashboard/saved      已保存的看板列表
- POST /api/dashboard/save       保存看板布局（图表卡片排列）
- POST /api/dashboard/upload-csv 上传CSV作为数据源
"""

import csv
import io
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage, _safe_exc_msg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["智能看板"])

# ── NL→图表 System Prompt ─────────────────────────────────
CHART_SYSTEM = """你是一位资深数据可视化分析师，精通ECharts图表配置和商业数据洞察呈现，擅长将复杂数据转化为一目了然的可视化图表。

## 图表类型决策树
- **比较/排名** → bar（柱状图）：横向对比多类别数据
- **趋势/变化** → line（折线图）：展示时间序列变化
- **占比/构成** → pie（饼图）：显示各部分占整体的比例（≤8个分类）
- **相关性/分布** → scatter（散点图）：展示两变量间的关系
- **多维度对比** → radar（雷达图）：展示多指标的综合对比
- **流程/漏斗** → funnel（漏斗图）：展示转化递减过程

## 可视化设计原则
1. **降噪原则**：只展示关键数据，删除无关元素（chart junk）
2. **颜色语义**：
   - 增长/正面 → 蓝色系(#4A90D9)或绿色系(#38A169)
   - 下降/负面 → 红色系(#E53E3E)或橙色系(#DD6B20)
   - 中性/对比 → 灰色系(#718096)
   - 多系列用差异化配色（避免相近色导致混淆）
3. **数据标注**：关键数据点加label标注具体数值
4. **响应式标题**：标题简洁有信息量（≤15字），不重复axis标签信息

## 数据洞察要求
- insight包含：最显著的趋势/对比/异常 + 可能的业务含义
- 示例："Q3销售额环比增长23%，主要受新品上市拉动；华东区贡献超40%"
- 如果用户提供了CSV数据，基于真实数据生成图表，不要构造模拟数据
- 如果无数据，构造5-8行合理美观的示例数据

输出严格JSON：
{
  "chart_type": "bar|line|pie|scatter|radar|funnel",
  "title": "图表标题（≤15字）",
  "insight": "一句话数据洞察（含关键数据和业务含义）",
  "option": {
    "tooltip": {"trigger": "axis|item"},
    "legend": {"data": ["系列名"]},
    "xAxis": {"type": "category", "data": ["类别"]},
    "yAxis": {"type": "value"},
    "series": [{"name": "系列名", "type": "bar|line|pie", "data": [数值]}]
  }
}

只输出JSON，不要任何额外说明。"""


def _ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS dashboard_dashboards (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            cards TEXT DEFAULT '[]',
            csv_data TEXT DEFAULT '',
            csv_filename TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


# ── 模型 ──────────────────────────────────────────────────


class NLQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="自然语言数据查询")
    csv_data: str = Field("", description="可选：CSV数据源（行文本）")
    csv_filename: str = Field("", description="可选：CSV文件名")


class SaveDashboardRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("")
    cards: list[dict] = Field(default_factory=list, description="图表卡片数组")
    csv_data: str = Field("")
    csv_filename: str = Field("")


# ── API ──────────────────────────────────────────────────


@router.post("/nl-query")
def nl_query(req: NLQueryRequest, current_user: dict = require_auth()):
    """自然语言 → ECharts图表配置。

    示例查询：
    - "过去7天每天的内容发布量趋势"
    - "各类型内容的占比"
    - "本周互动量TOP5的文章"
    - "发布量与互动率的散点关系"

    如果提供了CSV数据，LLM会基于CSV内容生成图表。
    """
    start = datetime.now()

    # 如果有CSV数据，附加到prompt
    user_prompt = req.query
    if req.csv_data:
        user_prompt = (
            f"数据来源（CSV内容）：\n{req.csv_data[:3000]}\n\n"
            f"用户查询：{req.query}\n"
            f"请基于CSV数据中的字段和数值，生成最合适的图表。"
        )

    try:
        raw = call_llm(CHART_SYSTEM, user_prompt, max_tokens=2000, temperature=0.3, timeout=60)
        # 提取JSON
        raw = raw.strip()
        if raw.startswith("```"):
            # 移除markdown代码块
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(500, "LLM返回格式异常，无法解析为JSON") from e
    except Exception as e:
        logger.exception("nl-query failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("dashboard_nl_query", len(req.query), len(raw), elapsed)

    return {
        **result,
        "query": req.query,
    }


@router.get("/saved")
async def list_dashboards(current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute("SELECT * FROM dashboard_dashboards ORDER BY updated_at DESC LIMIT 100").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["cards"] = json.loads(d.get("cards", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["cards"] = []
        result.append(d)
    return result


@router.post("/save")
async def save_dashboard(req: SaveDashboardRequest, current_user: dict = require_auth()):
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    dash_id = f"db_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    now = datetime.now().isoformat()
    conn.execute(
        """INSERT INTO dashboard_dashboards
           (id, user_id, title, description, cards, csv_data, csv_filename, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            dash_id,
            user,
            req.title,
            req.description,
            json.dumps(req.cards, ensure_ascii=False),
            req.csv_data[:50000] if req.csv_data else "",
            req.csv_filename,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": dash_id, "title": req.title, "created_at": now}


@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传CSV文件作为看板数据源。返回解析后的字段列表和样例数据。"""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "仅支持 .csv 文件")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # 处理 BOM
    except UnicodeDecodeError:
        try:
            text = content.decode("gbk")
        except Exception as e:
            raise HTTPException(400, "无法解析文件编码，请使用UTF-8或GBK编码") from e

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(400, "CSV文件为空或无表头")

    rows = list(reader)
    sample = rows[:10]
    columns = [{"name": f, "type": _guess_type([r.get(f, "") for r in sample])} for f in reader.fieldnames]

    return {
        "filename": file.filename,
        "columns": columns,
        "row_count": len(rows),
        "sample": [dict(r) for r in sample],
        "csv_data": text[:50000],  # 保留原始数据给后续查询
    }


def _guess_type(values: list[str]) -> str:
    """推测列的数据类型：number / date / text"""
    numeric = 0
    for v in values:
        if not v or v.strip() == "":
            continue
        try:
            float(v.replace(",", "").replace("%", ""))
            numeric += 1
        except ValueError:
            pass
    if numeric >= len(values) * 0.7:
        return "number"
    # 简单日期检测
    date_samples = [v for v in values if v and ("-" in v or "/" in v)]
    if len(date_samples) >= len(values) * 0.5:
        return "date"
    return "text"


@router.delete("/saved/{dash_id}")
async def delete_dashboard(dash_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM dashboard_dashboards WHERE id=?", (dash_id,))
    conn.commit()
    conn.close()
    return {"success": True}
