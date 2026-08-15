"""统一异常兜底设施（v15 全面进化）。

- ``safe_api``：装饰器，捕获未预期异常 → 记录完整堆栈 → 转 500 友好错误，
  避免 500 裸抛 / 堆栈泄漏；HTTPException 原样透传（业务异常语义不变）
- ``safe_sync``：同步函数版（供非 async 路由/线程任务使用）

用法::

    @router.get("/x")
    @safe_api
    async def get_x(...):
        ...

各工厂/底座模块统一接入后，前端 toast 可拿到稳定格式的错误消息。
"""

from __future__ import annotations

import functools
import inspect
import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _wrap(fn):
    @functools.wraps(fn)
    async def awrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("接口异常: %s.%s", fn.__module__, fn.__name__)
            # v22.2：详情附带原始异常信息（截断防泄漏），便于前端定位与用户反馈
            detail = str(e) or e.__class__.__name__
            if len(detail) > 200:
                detail = detail[:200] + "…"
            raise HTTPException(500, f"服务异常，请稍后重试（{detail}）") from e

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("接口异常: %s.%s", fn.__module__, fn.__name__)
            detail = str(e) or e.__class__.__name__
            if len(detail) > 200:
                detail = detail[:200] + "…"
            raise HTTPException(500, f"服务异常，请稍后重试（{detail}）") from e

    return awrapper if inspect.iscoroutinefunction(fn) else wrapper


def safe_api(fn):
    """统一异常兜底装饰器（自动识别 async/同步）。"""
    return _wrap(fn)


def safe_sync(fn):
    """同步函数版兜底（供线程任务等非路由场景复用）。"""
    return _wrap(fn)


__all__ = ["safe_api", "safe_sync"]
