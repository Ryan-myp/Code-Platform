#!/usr/bin/env python3
"""OpenAI 兼容开放网关 — 对外开发者 API。

v12.0 新增（兑现 apikey_api.API_DOCS 中已宣传的能力）：
- GET  /v1/models               模型列表（OpenAI 格式）
- POST /v1/chat/completions     LLM 对话补全（Bearer xt- API Key 认证）
- POST /api/chat/completions    兼容别名（旧文档路径）

特性：
- 鉴权：Authorization: Bearer xt-xxx → _auth_by_api_key（sha256 比对 api_keys 表）
- 多轮 messages 透传（OpenAI 格式），任意已配置模型名可路由（缺省用全局默认）
- stream: true → SSE 流式（OpenAI chunk 格式 + [DONE] 结束）
- 配额随绑定用户走（额度扣减由 quota_middleware 对 /api 路径生效）
"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from common.auth import _auth_by_api_key
from common.config import MODEL_NAME, get_model_list
from common.llm import call_llm_async, log_usage, stream_llm_async

logger = logging.getLogger(__name__)
router = APIRouter(tags=["开放API"])

_GATEWAY_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _auth(request: Request):
    """Bearer API Key 认证。失败返回 OpenAI 风格错误响应。"""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": "缺少 API Key（Authorization: Bearer xt-xxx）",
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )
    token = auth[7:].strip()
    try:
        return _auth_by_api_key(token)
    except HTTPException as e:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "message": str(e.detail),
                    "type": "invalid_request_error",
                    "code": "invalid_api_key",
                }
            },
        )


def _estimate_tokens(messages: list, content: str) -> dict:
    """粗略 Token 估算（字符数口径，中文约 1 token/字）。"""
    prompt_tokens = sum(len(str(m.get("content") or "")) for m in messages)
    completion_tokens = len(content or "")
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


def _chat_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex[:16]}"


def _resolve_model(name: str) -> str:
    if not name or name in ("xiaotuan-default", "default"):
        return MODEL_NAME
    return name


# ── 模型列表 ──────────────────────────────────────────────────


@router.get("/v1/models")
@router.get("/api/models")
async def list_models():
    """返回平台可用模型列表（OpenAI 格式）。"""
    models = get_model_list()
    return {
        "object": "list",
        "data": [{"id": m["name"], "object": "model", "created": 0, "owned_by": "xiaotuan"} for m in models],
    }


# ── 对话补全 ──────────────────────────────────────────────────


@router.post("/v1/chat/completions")
@router.post("/api/chat/completions")
async def chat_completions(request: Request, body: dict):  # noqa: C901
    """LLM 对话补全（OpenAI 兼容）。支持多轮 messages 与 stream 流式。"""
    auth = _auth(request)
    if isinstance(auth, JSONResponse):
        return auth

    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "messages 不能为空", "type": "invalid_request_error"}},
        )
    for m in messages:
        if not isinstance(m, dict) or not m.get("role") or m.get("content") is None:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": "messages 每一项需包含 role 与 content 字段",
                        "type": "invalid_request_error",
                    }
                },
            )

    model_name = _resolve_model(str(body.get("model") or "").strip())
    try:
        max_tokens = int(body.get("max_tokens") or 2000)
        temperature = float(body.get("temperature") if body.get("temperature") is not None else 0.4)
    except (TypeError, ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "max_tokens / temperature 必须为数字", "type": "invalid_request_error"}},
        )
    stream = bool(body.get("stream"))
    start = time.time()

    # 流式：OpenAI chunk 格式
    if stream:
        async def gen():
            try:
                full = ""
                async for delta, full in stream_llm_async(  # noqa: B007 — full 为累计文本，循环结束后用于 usage/done 事件
                    messages=messages, model=model_name, max_tokens=max_tokens, temperature=temperature
                ):
                    chunk = {
                        "id": _chat_id(),
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": model_name,
                        "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                    }
                    yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                # 收尾 chunk：finish_reason + usage
                final_chunk = {
                    "id": _chat_id(),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model_name,
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    "usage": _estimate_tokens(messages, full),
                }
                yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                log_usage("openai_gateway_stream", len(json.dumps(messages, ensure_ascii=False)), len(full), time.time() - start)
            except HTTPException as e:
                yield f"data: {json.dumps({'error': {'message': str(e.detail), 'type': 'server_error'}}, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.exception("gateway stream failed")
                yield f"data: {json.dumps({'error': {'message': f'内部错误: {e}', 'type': 'server_error'}}, ensure_ascii=False)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers=_GATEWAY_HEADERS)

    # 非流式
    try:
        content = await call_llm_async(
            "", "", model=model_name, messages=messages, max_tokens=max_tokens, temperature=temperature
        )
    except HTTPException as e:
        status = e.status_code if e.status_code < 500 else 502
        return JSONResponse(
            status_code=status,
            content={"error": {"message": str(e.detail), "type": "server_error"}},
        )
    log_usage("openai_gateway", len(json.dumps(messages, ensure_ascii=False)), len(content), time.time() - start)
    return {
        "id": _chat_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model_name,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": _estimate_tokens(messages, content),
    }
