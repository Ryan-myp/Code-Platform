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
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.helpers import _notify_progress
from common.db import get_db_context
from common.llm import call_llm, log_usage, parse_llm_json, _safe_exc_msg
from task_queue import create_task, register_handler

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
                user_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        # 存量库补 user_id 列（幂等，并发竞态忽略）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(forecast_records)").fetchall()]
        if "user_id" not in cols:
            try:
                conn.execute("ALTER TABLE forecast_records ADD COLUMN user_id TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()


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


# ── 预测区间规范化 / 模型选择说明（确定性纯函数）──


_METHOD_EXPLANATIONS = {
    "趋势外推": {
        "适用场景": "数据呈稳定上升/下降趋势、无明显季节波动时，用历史趋势线性外推",
        "优点": "实现简单，短期预测准确率较高",
        "缺点": "对拐点和外部冲击不敏感，长期预测偏差可能扩大",
    },
    "移动平均": {
        "适用场景": "数据波动较大、噪声明显时，通过平滑历史值降低噪声影响",
        "优点": "对短期波动平滑效果好，抗噪声",
        "缺点": "存在滞后性，难以捕捉趋势拐点",
    },
    "季节性分解": {
        "适用场景": "数据存在明显的周/月/季周期性规律（如销售旺季、流量周期）",
        "优点": "能分离趋势与季节成分，周期性预测更准",
        "缺点": "需要足够长的历史周期数据支撑，数据不足时不可靠",
    },
}


def build_method_explanation(method: str | None) -> dict:
    """生成模型选择说明：当前方法的适用场景/优缺点 + 备选方法对比。"""
    method = (method or "").strip()
    info = _METHOD_EXPLANATIONS.get(method)
    if not info:
        info = {
            "适用场景": "由 AI 结合数据特征综合判断（趋势外推/移动平均/季节性分解）",
            "优点": "自动适配数据形态",
            "缺点": "建议结合业务经验复核预测结果",
        }
    return {
        "current": method or "AI 自动选择",
        "info": info,
        "alternatives": [
            {"name": name, "适用场景": detail["适用场景"]}
            for name, detail in _METHOD_EXPLANATIONS.items()
            if name != method
        ],
    }


def _num_or_none(value):
    """尽力转 float，非数字返回 None（区间兜底用）。"""
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None



def _normalize_forecast_values(values: list) -> None:
    """规范化预测值区间：low ≤ value ≤ high，缺失补 value。"""
    for item in values:
        if not isinstance(item, dict):
            continue
        v = _num_or_none(item.get("value"))
        if v is None:
            continue
        low = _num_or_none(item.get("low"))
        high = _num_or_none(item.get("high"))
        if low is None:
            low = v
        if high is None:
            high = v
        if low > high:
            low, high = high, low
        item["value"] = v
        item["low"] = low
        item["high"] = high


def _normalize_chart_bounds(charts: dict) -> None:
    """规范化图表上下界数组长度与区间方向。"""
    labels = charts.get("labels")
    if not isinstance(labels, list) or not labels:
        return
    n = len(labels)
    upper = charts.get("upper_bound")
    lower = charts.get("lower_bound")
    if not isinstance(upper, list):
        upper = []
    if not isinstance(lower, list):
        lower = []
    norm_upper, norm_lower = [], []
    for i in range(n):
        u = _num_or_none(upper[i]) if i < len(upper) else None
        l = _num_or_none(lower[i]) if i < len(lower) else None
        if u is not None and l is not None and l > u:
            u, l = l, u
        norm_upper.append(u)
        norm_lower.append(l)
    charts["upper_bound"] = norm_upper
    charts["lower_bound"] = norm_lower

def normalize_forecast_ranges(result: dict | None) -> dict:
    """规范化预测区间：确保 low ≤ value ≤ high，charts 上下界与 labels 对齐。

    LLM 输出偶发区间倒置（low > high）、字段缺失或图表数组长度不一致，
    这里做确定性兜底，保证前端区间带渲染不越界、不破图。
    """
    result = result or {}
    predictions = result.get("predictions")
    if isinstance(predictions, dict):
        values = predictions.get("forecast_values")
        if isinstance(values, list):
            _normalize_forecast_values(values)

    charts = result.get("charts")
    if isinstance(charts, dict):
        _normalize_chart_bounds(charts)

    return result


# ── API ──────────────────────────────────────────────────


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传CSV文件，解析并返回预览数据。"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")

    content = await file.read()
    did = f"data_{int(datetime.now().timestamp() * 1000)}"
    save_path = os.path.join(UPLOAD_DIR, f"{did}.csv")

    with open(save_path, "wb") as f:
        f.write(content)

    # 解析预览
    try:
        preview = parse_csv(save_path)
    except Exception as e:
        os.remove(save_path)
        raise HTTPException(400, "服务异常，请稍后重试") from e

    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO forecast_records (id, filename, filepath, row_count, columns, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                did,
                file.filename,
                save_path,
                preview["row_count"],
                json.dumps(preview["columns"]),
                "uploaded",
                str(current_user.get("user_id", "")),
                datetime.now().isoformat(),
            ),
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


# ── 异步任务：数据预测（进度/自动重试/并发控制）──


async def _forecast_analyze_worker(payload: dict, progress: Callable | None = None) -> dict:
    """数据预测 worker：解析数据摘要 → AI 趋势分析+预测 → 记录落库。"""

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    data_id = payload.get("data_id", "")
    target_column = payload.get("target_column", "")

    _report(10, "读取数据文件")
    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM forecast_records WHERE id=?", (data_id,)).fetchone()
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
    if target_column:
        user_prompt += f"\n\n重点分析列：{target_column}"

    _report(30, "AI 统计分析中")
    # 解析失败自动重试一次（LLM 长输出偶发非法 JSON，实测首轮失败率高）；
    # 重试时追加严格格式约束，仍失败才报错（用户无需手动重跑）
    raw = ""
    for attempt in range(2):
        try:
            raw = call_llm(FORECAST_SYSTEM, user_prompt, max_tokens=3000, temperature=0.3, timeout=90)
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            result = parse_llm_json(raw)
            result = normalize_forecast_ranges(result)
            break
        except Exception as e:
            if attempt == 0:
                logger.warning("forecast LLM 输出解析失败，自动重试: %s", str(e)[:150])
                user_prompt += (
                    "\n\n（注意：上次返回的内容无法解析为 JSON。请严格只输出一个合法的 JSON 对象："
                    "不要 ``` 代码块围栏、不要注释、不要尾逗号、不要省略号，键和字符串统一使用双引号。）"
                )
            else:
                logger.exception("forecast analyze failed")
                raise HTTPException(500, "操作失败，请稍后重试") from e

    _report(70, "生成预测图表")
    log_usage("data_forecast", len(user_prompt), len(raw), 0)

    _report(90, "保存分析结果")
    with get_db_context() as conn:
        conn.execute(
            "UPDATE forecast_records SET analysis=?, status=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), "done", data_id),
        )

    _report(100, "完成")
    return {
        "data_id": data_id,
        "filename": filename,
        **result,
        "method_explanation": build_method_explanation(
            (result.get("predictions") or {}).get("method")
        ),
    }


async def _forecast_analyze_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装数据预测，回报进度。"""
    return await _forecast_analyze_worker(payload, progress=update)


@router.post("/analyze")
async def analyze_data(req: AnalyzeRequest, current_user: dict = require_auth()):
    """分析数据（异步任务：进度跟踪 / 失败自动重试 / 并发控制）"""
    payload = {
        **req.model_dump(),
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    task = create_task(
        "forecast_analyze",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"]}


@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    """获取历史数据预测记录（用户隔离：admin 全量，普通用户仅自己的）。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    with get_db_context() as conn:
        if role in ("admin", "super_admin"):
            rows = conn.execute(
                "SELECT id, filename, row_count, status, created_at FROM forecast_records ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, filename, row_count, status, created_at FROM forecast_records WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (uid,),
            ).fetchall()

    return [{"id": r[0], "filename": r[1], "row_count": r[2], "status": r[3], "created_at": r[4]} for r in rows]


def _can_access(conn, record_id: str, current_user: dict) -> bool:
    """记录归属校验：admin 可访问全部；普通用户仅自己的记录。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    if role in ("admin", "super_admin"):
        return True
    row = conn.execute("SELECT user_id FROM forecast_records WHERE id=?", (record_id,)).fetchone()
    return bool(row) and str(row[0] or "") == uid


@router.get("/records/{record_id}")
async def get_record(record_id: str, current_user: dict = require_auth()):
    """获取单条数据预测详情（含分析结果，归属校验）。"""
    with get_db_context() as conn:
        if not _can_access(conn, record_id, current_user):
            raise HTTPException(404, "记录不存在")
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
    """删除数据预测记录（归属校验）。"""
    with get_db_context() as conn:
        if not _can_access(conn, record_id, current_user):
            raise HTTPException(404, "记录不存在")
        row = conn.execute("SELECT filepath FROM forecast_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")
        try:
            os.remove(row[0])
        except OSError:
            pass
        conn.execute("DELETE FROM forecast_records WHERE id=?", (record_id,))
    return {"message": "已删除"}


# ── 异步任务处理器注册（进度/自动重试/并发控制）──
register_handler("forecast_analyze", _forecast_analyze_handler, user_limit=1, max_attempts=1)
