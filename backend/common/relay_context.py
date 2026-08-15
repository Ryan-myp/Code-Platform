#!/usr/bin/env python3
"""用户级中转站配置上下文（模式 B：用户自带中转站 API Key）。

通过 ContextVar 在请求作用域内传递「当前用户的中转站 key/base_url」，
所有 AI 调用（LLM/图片/视频/配音）在 get_model_config 时自动读取，
实现：用户使用 AI 功能时只走用户自己的中转站 token（平台从中转站卖 token 盈利）。

用法（一般无需直接调用，中间件自动注入）：
    from common.relay_context import get_relay_context
    ctx = get_relay_context()  # {"api_key": ..., "api_base": ...} 或 None
"""

import contextvars
from typing import Optional

# 当前请求的用户中转站配置：{"api_key": str, "api_base": str} 或 None
_relay_context: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "relay_context", default=None
)


def set_relay_context(relay: Optional[dict]) -> None:
    """设置当前请求的用户中转站配置（中间件在请求开始时调用）。"""
    _relay_context.set(relay)


def get_relay_context() -> Optional[dict]:
    """读取当前请求的用户中转站配置（无则 None）。"""
    return _relay_context.get()


def clear_relay_context() -> None:
    """清理当前请求上下文（中间件在请求结束时调用，防串号）。"""
    _relay_context.set(None)


def has_user_relay() -> bool:
    """当前请求是否已注入用户自有中转站 key。"""
    ctx = _relay_context.get()
    return bool(ctx and ctx.get("api_key"))
