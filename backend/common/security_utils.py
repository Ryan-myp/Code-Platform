"""安全工具函数 — 统一错误处理和鉴权。"""
import logging
import os
import functools
from typing import Callable

logger = logging.getLogger(__name__)

# 用户可见的错误消息映射
USER_FRIENDLY_ERRORS = {
    400: "请求参数错误，请检查后重试",
    401: "登录已过期，请重新登录",
    403: "您没有权限执行此操作",
    404: "请求的资源不存在",
    429: "请求过于频繁，请稍后再试",
    500: "服务器内部错误，请稍后重试",
    502: "服务暂时不可用，请稍后重试",
    503: "服务暂时不可用，请稍后重试",
}


def safe_http_error(status_code: int, message: str = None) -> str:
    """返回用户友好的错误消息。"""
    if message and len(message) < 100:
        return message
    return USER_FRIENDLY_ERRORS.get(status_code, f"操作失败 (错误码: {status_code})")


def require_api_key(func: Callable) -> Callable:
    """API Key鉴权装饰器。"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        from fastapi import Header, HTTPException
        api_key = kwargs.get('api_key') or Header(None)
        if not api_key:
            raise HTTPException(401, safe_http_error(401))
        # 验证API Key
        from common.db import get_db
        conn = get_db()
        try:
            row = conn.execute(
                "SELECT id, user_id, name FROM api_keys WHERE key=? AND active=1",
                (api_key,)
            ).fetchone()
            if not row:
                raise HTTPException(401, safe_http_error(401))
            kwargs['current_user'] = {"user_id": row["user_id"], "role": "api"}
        finally:
            conn.close()
        return await func(*args, **kwargs)
    return wrapper


def optional_auth(func: Callable) -> Callable:
    """可选鉴权 — 有token就验证，没有也放行（用于公开+私有混合端点）。"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        from fastapi import Request
        request = kwargs.get('request')
        if request:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                from common.auth import decode_access_token
                try:
                    user = decode_access_token(auth_header[7:])
                    kwargs['current_user'] = user
                except:
                    pass
        return await func(*args, **kwargs)
    return wrapper
