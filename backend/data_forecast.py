"""AI数据预测引擎 — 上传CSV → 统计分析 + AI趋势预测 + 可视化。

- POST /api/forecast/upload   上传CSV文件 → 解析预览
- POST /api/forecast/analyze  分析数据 → 趋势 + 预测 + 建议
- GET  /api/forecast/records  历史分析记录
- DELETE /api/forecast/records/{id}
"""

import csv
import json
import logging
import os
import statistics
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/forecast", tags=["数据预测"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "data")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── System Prompts ─────────────────────────────────────────

FORECAST_SYSTEM = """你是资深商业数据分析师（10年+经验），擅长从数据中发现趋势、洞察业务机会并给出可执行的策略建议。

分析框架（按以下5个维度深度分析）：

输出JSON格式：
{
  "overview": {
    "record_count": 100,
    "columns": ["列1", "列2"],
    "time_range": "2024-01 ~ 2024-12",
    "data_quality": "A-良好|B-一般|C-较差（含缺失率）",
    "summary": "一句话概括数据全貌（涵盖关键指标、趋势方向、值得关注的点）"
  },
  "statistics": {
    "columns": [
      {
        "name": "列名",
        "mean": 平均值,
        "median": 中位数,
        "std_dev": 标准差,
        "min": 最小值,
        "max": 最大值,
        "q1": 第一四分位数,
        "q3": 第三四分位数,
        "trend_direction": "上升|下降|平稳|波动",
        "significance": "该列的业务含义一句话"
      }
    ]
  },
  "trend_analysis": {
    "overall_trend": "整体趋势详细描述（上升/下降的幅度和拐点）",
    "seasonal_patterns": "季节性规律（周/月/季/年）及置信度",
    "anomalies": [{"point": "异常点位置", "value": 异常值, "possible_reason": "可能原因"}],
    "correlations": [{"between": "列A vs 列B", "coefficient": 0.85, "interpretation": "正相关说明"}],
    "key_findings": ["发现1（数据支撑）", "发现2", "发现3", "发现4", "发现5"]
  },
  "predictions": {
    "method": "趋势外推|移动平均|季节性分解",
    "short_term": {"description": "1-3个月预测", "confidence": "高|中|低"},
    "medium_term": {"description": "3-6个月预测", "confidence": "高|中|低"},
    "forecast_values": [
      {"period": "2024-Q3", "value": 预测值, "low": 下限, "high": 上限}
    ],
    "risks": ["预测风险1", "风险2"]
  },
  "recommendations": [
    {"priority": 1, "level": "紧急|重要|建议", "action": "具体行动方案", "expected_impact": "预期效果量化", "timeline": "建议时间"}
  ],
  "charts": {
    "labels": ["1月", "2月", "3月"],
    "actual": [100, 120, 115],
    "forecast": [null, null, 125, 130, 140],
    "trend_line": [98, 110, 118, 125, 132],
    "upper_bound": [null, null, 135, 145, 158],
    "lower_bound": [null, null, 115, 115, 122]
  }
}

质量要求：
- 数值用数字类型不要加引号
- 每个发现和建议都必须有数据支撑
- 异常分析要给出可能原因，不满足于"存在异常"
- 预测要标注置信度和风险
- 建议要具体可执行，避免"加强监控"等空泛表述
- 只输出JSON，不要其他内容"""

# ── 模型 ──────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    data_id: str = Field(..., description="上传后返回的数据ID")
    target_column: str = Field("", description="目标预测列名（可选，不填自动选择数值列）")
    forecast_periods: int = Field(3, ge=1, le=12, description="预测期数")


# ── 数据库初始化 ──────────────────────────────────────────

def init_db():
    with get_db_context() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forecast_records (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                row_count INTEGER,
                columns TEXT,
                analysis TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
        """)


init_db()

# ── 辅助函数 ──────────────────────────────────────────────

def parse_csv(filepath: str) -> dict:
    """解析CSV文件，返回列名、行数、数值列的统计信息。"""
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {"columns": [], "rows": [], "row_count": 0, "sample": []}

    columns = list(rows[0].keys())
    sample = rows[:10]

    # 数值列基础统计
    stats = {}
    for col in columns:
        try:
            vals = [float(r[col]) for r in rows if r[col] and r[col].strip()]
            if vals:
                stats[col] = {
                    "mean": round(statistics.mean(vals), 2),
                    "median": round(statistics.median(vals), 2),
                    "min": round(min(vals), 2),
                    "max": round(max(vals), 2),
                    "count": len(vals),
                }
                if len(vals) >= 2:
                    stats[col]["std_dev"] = round(statistics.stdev(vals), 2)
        except (ValueError, statistics.StatisticsError):
            pass

    return {
        "columns": columns,
        "row_count": len(rows),
        "stats": stats,
        "sample": sample,
    }


# ── API ──────────────────────────────────────────────────

@router.post("/upload")
async def upload_csv(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传CSV文件，解析并返回预览数据。"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")

    content = await file.read()
    did = f"data_{int(datetime.now().timestamp()*1000)}"
    save_path = os.path.join(UPLOAD_DIR, f"{did}.csv")

    with open(save_path, "wb") as f:
        f.write(content)

    # 解析预览
    try:
        preview = parse_csv(save_path)
    except Exception as e:
        os.remove(save_path)
        raise HTTPException(400, f"CSV解析失败：{e}")

    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO forecast_records (id, filename, filepath, row_count, columns, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (did, file.filename, save_path, preview["row_count"], json.dumps(preview["columns"]), "uploaded", datetime.now().isoformat()),
        )

    return {
        "data_id": did,
        "filename": file.filename,
        "row_count": preview["row_count"],
        "columns": preview["columns"],
        "numeric_columns": list(preview["stats"].keys()),
        "statistics": preview["stats"],
        "sample": preview["sample"],
    }


@router.post("/analyze")
async def analyze_data(req: AnalyzeRequest, current_user: dict = require_auth()):
    """分析数据：AI趋势分析 + 统计 + 预测。"""
    start = datetime.now()

    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM forecast_records WHERE id=?", (req.data_id,)).fetchone()
        if not row:
            raise HTTPException(404, "数据记录不存在")

        filepath = row[2]
        filename = row[1]

    # 解析数据摘要
    preview = parse_csv(filepath)
    data_summary = {
        "filename": filename,
        "row_count": preview["row_count"],
        "columns": preview["columns"],
        "statistics": preview["stats"],
        "sample": preview["sample"][:5] if preview["sample"] else [],
    }

    user_prompt = json.dumps(data_summary, ensure_ascii=False, indent=2)
    if req.target_column:
        user_prompt += f"\n\n重点分析列：{req.target_column}"

    try:
        raw = call_llm(FORECAST_SYSTEM, user_prompt, max_tokens=3000, temperature=0.3, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("forecast json parse failed")
        raise HTTPException(500, "数据预测结果格式异常，请重试")
    except Exception as e:
        logger.exception("forecast analyze failed")
        raise HTTPException(500, f"数据预测失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("data_forecast", len(user_prompt), len(raw), elapsed)

    with get_db_context() as conn:
        conn.execute(
            "UPDATE forecast_records SET analysis=?, status=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), "done", req.data_id),
        )

    return {
        "data_id": req.data_id,
        "filename": filename,
        **result,
    }


@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    """获取历史数据预测记录。"""
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, filename, row_count, status, created_at FROM forecast_records ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    return [{"id": r[0], "filename": r[1], "row_count": r[2], "status": r[3], "created_at": r[4]} for r in rows]


@router.get("/records/{record_id}")
async def get_record(record_id: str, current_user: dict = require_auth()):
    """获取单条数据预测详情（含分析结果）。"""
    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM forecast_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")

    return {
        "id": row[0],
        "filename": row[1],
        "row_count": row[3],
        "columns": json.loads(row[4]) if row[4] else [],
        "analysis": json.loads(row[5]) if row[5] else None,
        "status": row[6],
        "created_at": row[7],
    }


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    """删除数据预测记录。"""
    with get_db_context() as conn:
        row = conn.execute("SELECT filepath FROM forecast_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")
        try:
            os.remove(row[0])
        except OSError:
            pass
        conn.execute("DELETE FROM forecast_records WHERE id=?", (record_id,))
    return {"message": "已删除"}
