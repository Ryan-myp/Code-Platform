"""计量中心 + 运维指标 — 商业闭环 P0（docs/commercialization.md）。

- user_billing_summary(uid)：用户侧「用量账单」（今日 / 近30日 调用、成功率、字符量、成本预估）
- ops_metrics()：管理侧运维指标（7 日延迟分位、错误率、功能分布、任务积压、DB 体积）

成本预估口径：usage_logs 记录字符量（input/output_length），按 config
`llm_cost_per_1k_chars`（JSON: {"in": 0.004, "out": 0.012}，默认平台成本估算）折算，
仅为对账参考，非最终结算金额。
"""

from __future__ import annotations

import json
import os

# 平台成本估算（元/千字符）：可在 config 表 llm_cost_per_1k_chars 覆写
DEFAULT_COST_PER_1K_CHARS = {"in": 0.004, "out": 0.012}


def _cost_cfg() -> dict:
    try:
        from common.db import get_db_context

        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='llm_cost_per_1k_chars'").fetchone()
        if row and row["value"].strip():
            return json.loads(row["value"])
    except Exception:
        pass
    return dict(DEFAULT_COST_PER_1K_CHARS)


def user_billing_summary(user_id: str) -> dict:
    """用户计量中心：今日 / 近 30 日 LLM 用量聚合。"""
    from common.db import get_db

    costs = _cost_cfg()
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT timestamp, input_length, output_length, success
               FROM usage_logs WHERE user_id=? AND timestamp >= datetime('now', '-30 days')""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    def _agg(pred) -> dict:
        sel = [r for r in rows if pred(r["timestamp"])]
        calls = len(sel)
        ok = sum(1 for r in sel if r["success"])
        in_chars = sum(r["input_length"] or 0 for r in sel)
        out_chars = sum(r["output_length"] or 0 for r in sel)
        cost = round(in_chars / 1000 * costs["in"] + out_chars / 1000 * costs["out"], 4)
        return {
            "calls": calls,
            "success_rate": round(ok / calls * 100, 1) if calls else 0.0,
            "input_chars": in_chars,
            "output_chars": out_chars,
            "cost_estimate": cost,
        }

    def _today(ts: str) -> bool:
        return ts[:10] == _today_str()

    return {"today": _agg(_today), "d30": _agg(lambda _ts: True)}


def _today_str() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d")


def ops_metrics() -> dict:
    """运维指标：7 日延迟分位 / 错误率 / 功能分布 / 任务积压 / DB 体积。"""
    from common.db import get_db

    conn = get_db()
    try:
        times = [
            r[0]
            for r in conn.execute(
                """SELECT response_time FROM usage_logs
                   WHERE response_time > 0 AND timestamp >= datetime('now', '-7 days')
                   ORDER BY response_time"""
            ).fetchall()
        ]
        d7 = {
            "total_calls": len(times),
            "p50_s": round(times[int(len(times) * 0.5)], 3) if times else 0,
            "p95_s": round(times[int(len(times) * 0.95)], 3) if times else 0,
            "errors": conn.execute(
                "SELECT COUNT(*) FROM usage_logs WHERE success=0 AND timestamp >= datetime('now', '-7 days')"
            ).fetchone()[0],
        }
        d7["error_rate"] = round(d7["errors"] / d7["total_calls"] * 100, 2) if d7["total_calls"] else 0.0
        by_feature = [
            {"feature": r["feature"] or "llm", "calls": r["calls"]}
            for r in conn.execute(
                """SELECT feature, COUNT(*) AS calls FROM usage_logs
                   WHERE timestamp >= datetime('now', '-7 days') GROUP BY feature ORDER BY calls DESC LIMIT 10"""
            ).fetchall()
        ]
        try:
            queue_backlog = conn.execute(
                "SELECT COUNT(*) FROM async_tasks WHERE status IN ('pending','running')"
            ).fetchone()[0]
        except Exception:
            queue_backlog = 0  # 测试库/新建库可能未建任务表
    finally:
        conn.close()

    db_mb = round(os.path.getsize(_db_path()) / 1024 / 1024, 2) if _db_path() and os.path.exists(_db_path()) else 0.0
    return {"d7": d7, "by_feature": by_feature, "queue_backlog": queue_backlog, "db_size_mb": db_mb}


def _db_path() -> str:
    return os.environ.get("DB_PATH", "data.db")
