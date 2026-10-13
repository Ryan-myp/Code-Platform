"""统一错误分类 + 重试原语（v18 P2）单测。"""

import httpx
import pytest


# ── 分类口径 ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "status,expected",
    [
        (429, "transient"),
        (500, "transient"),
        (503, "transient"),
        (408, "transient"),
        (401, "auth"),
        (403, "auth"),
        (400, "invalid"),
        (404, "invalid"),
        (422, "invalid"),
    ],
)
def test_classify_http_status(status, expected):
    from common.errors import classify_http_status

    assert classify_http_status(status) == expected


def test_classify_content_policy_body():
    """400 + 内容策略特征 → content（重试无意义，区别于普通 400）。"""
    from common.errors import classify_http_status

    assert classify_http_status(400, "Your request was rejected by content policy") == "content"
    assert classify_http_status(400, "field x missing") == "invalid"


def test_classify_exception_network_transient():
    from common.errors import classify_exception

    assert classify_exception(httpx.ConnectError("boom")) == "transient"
    assert classify_exception(httpx.ReadTimeout("t")) == "transient"
    assert classify_exception(TimeoutError()) == "transient"
    assert classify_exception(ValueError("bad")) == "unknown"


def test_classify_exception_http_status():
    """带 status_code 的异常（如 HTTPException）走状态码口径。"""
    from fastapi import HTTPException

    from common.errors import classify_exception

    assert classify_exception(HTTPException(401, "no")) == "auth"
    assert classify_exception(HTTPException(502, "bad gateway")) == "transient"


def test_should_retry_only_transient():
    from common.errors import should_retry

    assert should_retry("transient") is True
    assert should_retry("auth") is False
    assert should_retry("content") is False


# ── 退避 ──────────────────────────────────────────────
def test_backoff_delay_grows_and_caps():
    from common.errors import backoff_delay

    assert backoff_delay(1, jitter=False) == 0.6
    assert backoff_delay(2, jitter=False) == 1.2
    assert backoff_delay(3, jitter=False) == 2.4
    assert backoff_delay(10, jitter=False) <= 8.0  # cap


# ── 同步重试原语 ──────────────────────────────────────
def test_run_with_retry_retries_transient_then_succeeds():
    from common import errors

    calls = {"n": 0}
    sleeps = []

    def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("flaky")
        return "ok"

    out = errors.run_with_retry(fn, attempts=2, sleep=sleeps.append)
    assert out == "ok"
    assert calls["n"] == 2
    assert len(sleeps) == 1, "首试失败 → 1 次退避重试"


def test_run_with_retry_no_retry_non_transient():
    """非 transient（auth）立即 raise，不浪费时间重试。"""
    from fastapi import HTTPException

    from common import errors

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise HTTPException(401, "bad key")

    with pytest.raises(HTTPException):
        errors.run_with_retry(fn, attempts=3, sleep=lambda d: None)
    assert calls["n"] == 1, "auth 类不重试"


def test_run_with_retry_exhausts_and_raises():
    """瞬时可重试但耗尽次数 → 抛出最后一次异常（不吞）。"""
    from common import errors

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise httpx.ConnectError("down")

    with pytest.raises(httpx.ConnectError):
        errors.run_with_retry(fn, attempts=2, sleep=lambda d: None)
    assert calls["n"] == 2


def test_run_with_retry_attempts_one_is_single_shot():
    """attempts=1 → 单次不重试（MCP 默认纪律）。"""
    from common import errors

    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise httpx.ConnectError("x")

    with pytest.raises(httpx.ConnectError):
        errors.run_with_retry(fn, attempts=1, sleep=lambda d: None)
    assert calls["n"] == 1


# ── 异步重试原语 ──────────────────────────────────────
@pytest.mark.asyncio
async def test_run_with_retry_async_transient():

    from common import errors

    calls = {"n": 0}

    async def fn():
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("flaky")
        return 42

    out = await errors.run_with_retry_async(fn, attempts=2, sleep=lambda d: None)
    assert out == 42
    assert calls["n"] == 2


@pytest.mark.asyncio
async def test_run_with_retry_async_supports_coroutine_factory():
    """fn 返回协程对象（lambda 包 async 函数）也正确 await（mcp 调用点形态）。"""
    from common import errors

    calls = {"n": 0}

    async def inner():
        calls["n"] += 1
        return "r"

    out = await errors.run_with_retry_async(lambda: inner(), attempts=2, sleep=lambda d: None)
    assert out == "r"
    assert calls["n"] == 1
