"""统一错误分类 + 重试原语（v18 P2）。

LLM 与 MCP 此前各自零散处理（LLM 有退避、MCP 零重试、标准不一）。
本模块给两条链路同一套分类口径与退避函数，薄封装不引框架依赖。

分类口径（对外只有这 5 类，便于前端/监控按类展示）：
- transient  瞬时故障（429/408/5xx/连接断/超时/EOF）→ 可重试
- auth       凭据问题（401/403）→ 不重试，提示更新密钥/授权
- content    内容策略（400 且命中受限内容特征）→ 重试无意义
- invalid    其它 4xx（参数/缺列等）→ 不重试
- unknown    无法归类 → 不重试（保守）

重试策略（低并发纪律）：默认"至多重试 1 次 + 指数退避带上限"，避免放大
对上游（LLM 中转站 / MCP server）的压力；需要更多次数的调用方显式传 attempts。
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

TRANSIENT = "transient"
AUTH = "auth"
CONTENT = "content"
INVALID = "invalid"
UNKNOWN = "unknown"

RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
AUTH_STATUS = frozenset({401, 403})

# 网络/传输类异常（可重试）——LLM/MCP 共用
try:  # httpx 优先（MCP 用），requests 兜底（LLM 同步路径用）
    import httpx as _httpx

    NETWORK_EXC = tuple(getattr(_httpx, n) for n in (
        "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout",
        "RemoteProtocolError", "TimeoutException", "PoolTimeout",
    ) if hasattr(_httpx, n))
except ImportError:  # pragma: no cover
    NETWORK_EXC = ()
try:
    import requests as _requests

    NETWORK_EXC = NETWORK_EXC + (
        _requests.exceptions.ConnectionError,
        _requests.exceptions.Timeout,
        _requests.exceptions.ChunkedEncodingError,
    )
except ImportError:  # pragma: no cover
    pass


def classify_http_status(status: int, body: str = "") -> str:
    """HTTP 状态码 → 分类。429/5xx/408 瞬时可重试；401/403 凭据；
    400 且 body 命中内容策略特征 → content；其余 4xx → invalid。"""
    if status in RETRYABLE_STATUS:
        return TRANSIENT
    if status in AUTH_STATUS:
        return AUTH
    if status == 400:
        low = (body or "").lower()
        if any(k in low for k in ("content policy", "safety", "restricted", "内容策略", "受限")):
            return CONTENT
        return INVALID
    if 400 <= status < 500:
        return INVALID
    return UNKNOWN


def classify_exception(exc: BaseException) -> str:
    """异常 → 分类：网络/传输类 → transient；HTTP 异常（带 status_code）走状态码口径；
    其余 → unknown（保守不重试）。"""
    sc = getattr(exc, "status_code", None)
    if isinstance(sc, int):
        return classify_http_status(sc, getattr(exc, "detail", "") or "")
    if NETWORK_EXC and isinstance(exc, NETWORK_EXC):
        return TRANSIENT
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)) and not isinstance(exc, (ValueError, TypeError)):
        return TRANSIENT
    return UNKNOWN


def should_retry(cls: str) -> bool:
    return cls == TRANSIENT


def backoff_delay(attempt: int, base: float = 0.6, cap: float = 8.0, jitter: bool = True) -> float:
    """指数退避带上限 + 可选抖动（防多客户端同步重试放大上游压力）。"""
    d = min(cap, base * (2 ** max(0, attempt - 1)))
    if jitter:
        d = d * (0.7 + random.random() * 0.3)
    return d


def run_with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 2,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, BaseException], None] | None = None,
    classify: Callable[[BaseException], str] | None = None,
) -> T:
    """同步通用重试：至多重试 attempts-1 次，仅 transient 可重试，退避 base=0.6s。

    attempts=1 → 单次执行不重试（默认 2 = 首试 + 1 次重试，低并发纪律）。
    on_retry(attempt, exc) 回调供日志；classify 可注入（默认 classify_exception）。
    重试耗尽后抛出最后一次异常（由调用方决定如何降级，本函数不吞异常）。
    """

    def _cls(e: BaseException) -> str:
        return (classify or classify_exception)(e)

    n = max(1, attempts)
    for i in range(n):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 分类后决定是否重试，不吞（重试耗尽仍 raise）
            if i >= n - 1 or not should_retry(_cls(e)):
                raise
            if on_retry:
                on_retry(i + 1, e)
            sleep(backoff_delay(i + 1, jitter=(n > 2)))
    raise RuntimeError("unreachable")  # pragma: no cover


async def run_with_retry_async(
    fn: Callable[[], T],
    *,
    attempts: int = 2,
    sleep: Callable[[float], None] | None = None,
    on_retry: Callable[[int, BaseException], None] | None = None,
    classify: Callable[[BaseException], str] | None = None,
) -> T:
    """run_with_retry 的 async 版（fn 返回协程；sleep 缺省用 asyncio.sleep）。"""
    import asyncio

    do_sleep = sleep or (lambda d: asyncio.sleep(d))
    n = max(1, attempts)

    def _cls(e: BaseException) -> str:
        return (classify or classify_exception)(e)

    for i in range(n):
        try:
            r = fn()
            if hasattr(r, "__await__"):
                return await r
            return r
        except Exception as e:  # noqa: BLE001 - 同上，不吞异常
            if i >= n - 1 or not should_retry(_cls(e)):
                raise
            if on_retry:
                on_retry(i + 1, e)
            do_sleep(backoff_delay(i + 1, jitter=(n > 2)))
    raise RuntimeError("unreachable")  # pragma: no cover
