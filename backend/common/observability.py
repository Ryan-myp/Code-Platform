#!/usr/bin/env python3
"""全链路可观测性 — request-id 注入 / 结构化访问日志 / 运行指标。

v12.0 新增：
- RequestContextMiddleware：为每个请求注入 X-Request-ID（透传上游值，无则生成），
  记录结构化 JSON 访问日志（method/path/status/耗时/request-id），
  慢请求（>3s）与 5xx 以 WARNING 级别标记，便于 grep 定位。
- 进程级指标计数器（请求总数/错误数/慢请求/耗时累计/分路径聚合），
  供 /api/ops/stats 输出实时运行画像。
- 静态资源与健康检查请求不计入访问日志（避免噪音），但计入指标。
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("access")

# 进程启动时间（uptime 计算基准）
_START_TIME = time.time()

# ── 进程级指标（线程安全） ───────────────────────────────────
_metrics_lock = threading.Lock()
_metrics = {
    "requests_total": 0,
    "errors_total": 0,
    "slow_requests": 0,
    "latency_sum_ms": 0.0,
    "by_path": {},  # path -> {"count": n, "errors": n, "latency_sum_ms": f}
}

# 慢请求阈值（毫秒）
SLOW_REQUEST_MS = 3000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def uptime_seconds() -> float:
    """进程已运行秒数。"""
    return round(time.time() - _START_TIME, 1)


def get_metrics_snapshot() -> dict:
    """返回指标快照（含平均耗时与错误率推导，分路径 Top 聚合）。"""
    with _metrics_lock:
        total = _metrics["requests_total"]
        errors = _metrics["errors_total"]
        by_path = {
            p: {
                "count": e["count"],
                "errors": e["errors"],
                "avg_latency_ms": round(e["latency_sum_ms"] / e["count"], 1) if e["count"] else 0,
            }
            for p, e in _metrics["by_path"].items()
        }
    # 路径 Top 10（按调用量）
    top_paths = sorted(by_path.items(), key=lambda kv: kv[1]["count"], reverse=True)[:10]
    return {
        "uptime_seconds": uptime_seconds(),
        "requests_total": total,
        "errors_total": errors,
        "error_rate": round(errors / total, 4) if total else 0,
        "slow_requests": _metrics["slow_requests"],
        "avg_latency_ms": round(_metrics["latency_sum_ms"] / total, 1) if total else 0,
        "top_paths": [{"path": p, **v} for p, v in top_paths],
    }


class RequestContextMiddleware(BaseHTTPMiddleware):
    """请求上下文中间件：request-id + 结构化访问日志 + 指标计数。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id

        method = request.method
        path = request.url.path
        # 静态资源与文档页不记访问日志（噪音大），但仍计入指标
        is_noisy = (
            path.startswith(("/static/", "/assets/", "/favicon", "/uploads"))
            or path == "/api/health"
        )
        start = time.perf_counter()
        status_code = 500
        error = ""
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:  # noqa: BLE001 —— 兜底记录所有未处理异常
            error = f"{type(e).__name__}: {e}"
            raise
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            is_error = status_code >= 500 or bool(error)
            with _metrics_lock:
                _metrics["requests_total"] += 1
                _metrics["latency_sum_ms"] += latency_ms
                if is_error:
                    _metrics["errors_total"] += 1
                if latency_ms > SLOW_REQUEST_MS:
                    _metrics["slow_requests"] += 1
                entry = _metrics["by_path"].setdefault(path, {"count": 0, "errors": 0, "latency_sum_ms": 0.0})
                entry["count"] += 1
                entry["latency_sum_ms"] += latency_ms
                if is_error:
                    entry["errors"] += 1
            if not is_noisy:
                level = logging.WARNING if (is_error or latency_ms > SLOW_REQUEST_MS) else logging.INFO
                logger.log(
                    level,
                    json.dumps(
                        {
                            "ts": _now_iso(),
                            "request_id": request_id,
                            "method": method,
                            "path": path,
                            "status": status_code,
                            "latency_ms": round(latency_ms, 1),
                            "client": request.client.host if request.client else "",
                            "error": error or None,
                        },
                        ensure_ascii=False,
                    ),
                )
