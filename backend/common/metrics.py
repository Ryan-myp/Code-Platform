"""平台可靠性指标：轻量事件表 + 记录/聚合（可观测性层 F）。

设计（诚实降级 + 低并发纪律）：
- 事件表 metrics_events：kind（llm/tool/mcp/workflow）× outcome（ok/error/degraded）
  + err_class（errors.py 五类）+ latency_ms + detail（已脱敏截断，只含模型名/工具 id 等
  非机密字段，绝不落凭据）
- record() 失败静默：指标永不阻断主流程
- 30 天滚动保留：每次 record 顺带清旧行（低量级下无额外成本）
- summarize()：按 kind/outcome 计数、err_class 分布、延迟 avg/min/max/p50/p95
  （分位数在 Python 算，抓 5000 行封顶——低并发场景足够）

挂载点（调用方）：
- common/llm.py：LLM 调用成功/失败（含 4xx 状态分类）
- agent_runtime.execute_tool_async：工具执行 ok/降级
- mcp_client.mcp_call_tool：MCP 调用成功/失败
"""

from __future__ import annotations

import contextvars
import logging
import time

logger = logging.getLogger(__name__)

_RETENTION_DAYS = 30
_DETAIL_MAX = 300
_KINDS = ("llm", "tool", "mcp", "workflow")
_OUTCOMES = ("ok", "error", "degraded")
_CLASSES = ("transient", "auth", "content", "invalid", "unknown", "")


def _conn():
    from common.db import get_db

    return get_db()


def _ensure_table(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS metrics_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,
            outcome TEXT NOT NULL,
            err_class TEXT DEFAULT '',
            latency_ms REAL,
            detail TEXT DEFAULT '',
            ref TEXT DEFAULT ''
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_events_ts ON metrics_events(ts)")
    # 幂等补列：老库无 ref（v18.2 agent 归因）
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(metrics_events)").fetchall()}
    if "ref" not in cols:
        conn.execute("ALTER TABLE metrics_events ADD COLUMN ref TEXT DEFAULT ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics_events_ref ON metrics_events(ref)")


# v18.2 agent 归因：执行链路入口 set_ref("agent:<id>")，该任务内所有 record 自动带上
_ctx_ref: contextvars.ContextVar = contextvars.ContextVar("metrics_ref", default="")


def set_ref(ref: str):
    """设置当前执行上下文的归因标签（如 'agent:a_123' / 'workflow:run_x'）。

    asyncio task / to_thread 均继承 contextvars → 子调用自动携带，无需逐层透传。
    返回 token（需要恢复时可 reset）。"""
    return _ctx_ref.set(ref or "")


def record(kind: str, outcome: str, latency_ms: float | None = None, err_class: str = "", detail: str = "") -> None:
    """写一条指标事件（幂等降级：任何失败静默，不影响主流程）。"""
    try:
        conn = _conn()
        _ensure_table(conn)
        ts = time.time()
        conn.execute(
            "INSERT INTO metrics_events (ts, kind, outcome, err_class, latency_ms, detail, ref) VALUES (?,?,?,?,?,?,?)",
            (
                ts,
                kind if kind in _KINDS else "workflow",
                outcome if outcome in _OUTCOMES else "degraded",
                err_class if err_class in _CLASSES else "unknown",
                round(float(latency_ms)) if latency_ms is not None else None,
                (str(detail) or "")[:_DETAIL_MAX],
                (_ctx_ref.get() or "")[:80],
            ),
        )
        # 滚动保留（低量级下每次顺手清旧行，无单独清理任务）
        cutoff = ts - _RETENTION_DAYS * 86400
        conn.execute("DELETE FROM metrics_events WHERE ts < ?", (cutoff,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"metrics record failed (ignored): {e}")


def summarize(days: int = 7) -> dict:
    """聚合窗口内指标（管理端只读；不暴露敏感详情）。"""
    conn = _conn()
    _ensure_table(conn)
    cutoff = time.time() - max(1, min(days, 30)) * 86400
    rows = conn.execute(
        "SELECT kind, outcome, err_class, latency_ms, detail FROM metrics_events WHERE ts>=?", (cutoff,)
    ).fetchall()
    conn.close()

    by_kind: dict[str, dict[str, int]] = {}
    err_classes: dict[str, int] = {}
    lat_by_kind: dict[str, list[float]] = {}
    total = 0
    for r in rows:
        total += 1
        k = by_kind.setdefault(r["kind"], {"ok": 0, "error": 0, "degraded": 0})
        k[r["outcome"]] = k.get(r["outcome"], 0) + 1
        ec = (r["err_class"] or "").strip()
        if ec:
            err_classes[ec] = err_classes.get(ec, 0) + 1
        if r["latency_ms"] is not None and r["outcome"] != "error":
            lat_by_kind.setdefault(r["kind"], []).append(float(r["latency_ms"]))

    def _pct(vals: list[float], p: float) -> float | None:
        if not vals:
            return None
        s = sorted(vals)
        return round(s[min(len(s) - 1, int(len(s) * p))], 1)

    latency = {}
    for kind, vals in lat_by_kind.items():
        latency[kind] = {
            "avg_ms": round(sum(vals) / len(vals), 1),
            "min_ms": round(min(vals), 1),
            "max_ms": round(max(vals), 1),
            "p50_ms": _pct(vals, 0.5),
            "p95_ms": _pct(vals, 0.95),
        }

    # 最近 20 条错误（按时间倒序，供管理端排查）
    conn = _conn()
    recent = [
        {"err_class": r["err_class"] or "unknown", "kind": r["kind"], "detail": (r["detail"] or "")[:200]}
        for r in conn.execute(
            "SELECT kind, err_class, detail FROM metrics_events WHERE ts>=? AND outcome='error' "
            "ORDER BY ts DESC LIMIT 20",
            (cutoff,),
        ).fetchall()
    ]
    conn.close()

    return {
        "window_days": days,
        "total_events": total,
        "by_kind": by_kind,
        "error_classes": dict(sorted(err_classes.items(), key=lambda x: -x[1])),
        "latency": latency,
        "recent_errors": recent,
    }
