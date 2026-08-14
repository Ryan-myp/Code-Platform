#!/usr/bin/env python3
"""LLM 调用 + 使用统计 — 单一来源。

替代 prd_engine.py 与 chat_engine.py 中重复的 call_llm 定义。

v12.0 工程化升级：
- 多轮 messages 支持（替代固定 system+user 两段，支撑真实对话上下文）
- 指数退避自动重试（429 / 5xx / 网络类异常，默认 2 次）
- 备用模型自动降级（主模型重试耗尽后切换到 fallback_models，或自动补全同源模型）
- SSE 流式输出（stream_llm_async，供聊天打字机效果）
- 对话历史组装（build_conversation_messages，多轮窗口裁剪）
"""

import asyncio
import json
import logging
import time
from datetime import datetime

import httpx
import requests
from fastapi import HTTPException

from common.config import AGNES_API_KEY, MODEL_NAME, get_model_config, get_model_list

logger = logging.getLogger(__name__)

# 可重试的 HTTP 状态码：429 限流 + 5xx 服务端瞬时故障
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# 不可重试（请求类）状态码：直接抛出，不降级不重试
_NON_RETRYABLE_STATUS = {400, 401, 403, 404, 422}
# 网络/传输类异常（连接断开、超时、EOF 等），全部可重试
_NETWORK_EXC = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.TransportError,
    httpx.RemoteProtocolError,
    requests.RequestException,
)


def _build_messages(
    system_prompt: str, user_prompt: str, messages: list[dict] | None
) -> list[dict]:
    """统一构建 messages：优先使用调用方传入的多轮 messages，否则回退 system+user 两段。"""
    if messages:
        return list(messages)
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    if user_prompt:
        msgs.append({"role": "user", "content": user_prompt})
    return msgs


def _fallback_candidates(model: str | None, fallback_models: list[str] | None) -> list[str]:
    """生成候选模型序列：主模型 → 显式备用 → 自动补全已配置模型（最多 4 个）。

    自动补全规则：模型列表中 api_key 已配置，或 base_url 留空（继承全局 key）的模型。
    """
    candidates = [model or MODEL_NAME]
    for m in fallback_models or []:
        if m and m not in candidates:
            candidates.append(m)
    for m in get_model_list():
        name = (m.get("name") or "").strip()
        if not name or name in candidates:
            continue
        has_key = bool((m.get("api_key") or "").strip())
        inherits_global = not (m.get("base_url") or "").strip() and bool(AGNES_API_KEY)
        if has_key or inherits_global:
            candidates.append(name)
    return candidates[:4]


def _extract_content(resp_json) -> str:
    """从 OpenAI 兼容响应中提取文本内容（兼容非标准返回结构 / SSE 流式文本）。"""
    # SSE 格式：omniroute 等网关即使请求非流式也返回 data: {...} 块
    if isinstance(resp_json, str):
        text = resp_json
        if "data: " in text:
            chunks = []
            for line in text.split("\n"):
                line = line.strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        delta = (
                            (chunk.get("choices") or [{}])[0].get("delta") or {}
                        )
                        content = delta.get("content") or ""
                        if content:
                            chunks.append(content)
                    except (ValueError, TypeError):
                        continue
            if chunks:
                return "".join(chunks)
        # 尝试直接 JSON
        try:
            resp_json = json.loads(text)
        except (ValueError, TypeError):
            return text or ""
    try:
        return resp_json["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        pass
    if isinstance(resp_json.get("content"), str):
        return resp_json["content"]
    raise HTTPException(502, "操作失败，请稍后重试")


def _retry_delay(attempt: int) -> float:
    """指数退避：1s → 2s → 4s …（attempt 从 1 开始）。"""
    return 2 ** attempt


def _readable_error(exc: Exception) -> str:
    """连接类异常 str 常为空，兜底为可读文案，避免用户看到空白错误。"""
    return str(exc) or f"{type(exc).__name__}（连接异常），请稍后重试"


def _safe_exc_msg(exc: Exception) -> str:
    """从异常中提取安全错误消息，过滤路径、IP、敏感词，防止信息泄露。"""
    import re as _re
    msg = str(exc)[:200]
    msg = _re.sub(r"/[^\s,;]{6,}", "<path>", msg)
    msg = _re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<ip>", msg)
    msg = _re.sub(r"(?:password|secret|token|key)\s*[:=]\s*\S+", "<cred>", msg, flags=_re.IGNORECASE)
    return msg or "操作失败，请稍后重试"


def api_error_detail(exc: Exception) -> str:
    """提取外部 API 调用异常的供应商错误详情（兼容 requests/httpx），替代无信息量的 "400 Client Error"。

    识别 OpenAI 兼容错误结构 {error: {message, code}}；内容策略违规（content_policy_violation）
    额外附加中文提示，帮助用户/调用方理解失败原因。
    """
    resp = getattr(exc, "response", None)
    if resp is None:
        return _readable_error(exc)
    detail, code = "", ""
    try:
        data = resp.json()
        err = data.get("error") or {}
        detail = str(err.get("message") or data.get("message") or "")
        code = str(err.get("code") or "")
    except Exception:
        detail = str(getattr(resp, "text", "") or "")
    body = detail or code or _readable_error(exc)
    msg = f"HTTP {resp.status_code}: {body[:300]}"
    if code and code not in body:
        msg += f"（{code}）"
    if code == "content_policy_violation" or "content policy" in detail.lower():
        msg += "；提示词可能包含平台受限内容，请调整个别描述词后重试"
    return msg


# ══════════════════════════════════════════════════════════════
# 同步版（向后兼容：签名不变，新增可选参数）
# ══════════════════════════════════════════════════════════════


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 300,
    model: str | None = None,
    messages: list[dict] | None = None,
    retries: int = 2,
    fallback_models: list[str] | None = None,
) -> str:
    """同步调用 LLM（OpenAI 兼容 /chat/completions），按模型路由到对应供应商。

    v12.0：支持多轮 messages、指数退避重试（默认 2 次）、备用模型降级。
    """
    msgs = _build_messages(system_prompt, user_prompt, messages)
    if not msgs:
        raise HTTPException(400, "prompt 不能为空")

    candidates = _fallback_candidates(model, fallback_models)
    last_error: Exception | None = None
    for idx, mname in enumerate(candidates):
        cfg = get_model_config(mname)
        if not cfg["api_key"]:
            continue
        try:
            return _call_one_sync(cfg, msgs, max_tokens, temperature, timeout, retries)
        except HTTPException as e:
            if e.status_code in _NON_RETRYABLE_STATUS:
                raise
            last_error = e
            if idx < len(candidates) - 1:
                logger.warning(f"LLM model {mname} failed, fallback to next: {e.detail}")
        except Exception as e:
            last_error = e
            if idx < len(candidates) - 1:
                logger.warning(f"LLM model {mname} exception, fallback to next: {e}")

    if isinstance(last_error, HTTPException):
        raise last_error
    raise HTTPException(502, "操作失败，请稍后重试")


def _call_one_sync(cfg: dict, msgs: list[dict], max_tokens: int, temperature: float, timeout: int, retries: int) -> str:
    """单模型同步调用，内置指数退避重试。"""
    url = f"{cfg['api_base']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    attempt = 0
    while True:
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                body = resp.text[:400]
                if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                    attempt += 1
                    time.sleep(_retry_delay(attempt))
                    continue
                logger.error(f"LLM call failed: {resp.status_code} {body}")
                raise HTTPException(502, "操作失败，请稍后重试")
            try:
                return _extract_content(resp.json())
            except (ValueError, TypeError):
                # omniroute 等网关返回 SSE 文本而非标准 JSON
                return _extract_content(resp.text)
        except HTTPException:
            raise
        except Exception as e:
            if isinstance(e, _NETWORK_EXC) and attempt < retries:
                attempt += 1
                time.sleep(_retry_delay(attempt))
                continue
            logger.error(f"LLM call exception: {e}", exc_info=True)
            raise HTTPException(502, "操作失败，请稍后重试") from e


# 同步版本的别名（向后兼容）
call_llm_sync = call_llm


# ══════════════════════════════════════════════════════════════
# 异步版（FastAPI async 端点应使用此版本，避免阻塞事件循环）
# ══════════════════════════════════════════════════════════════


async def call_llm_async(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 300,
    model: str | None = None,
    messages: list[dict] | None = None,
    retries: int = 2,
    fallback_models: list[str] | None = None,
) -> str:
    """异步调用 LLM（httpx.AsyncClient 非阻塞）。

    v12.0：支持多轮 messages、指数退避重试（默认 2 次）、备用模型降级。
    """
    msgs = _build_messages(system_prompt, user_prompt, messages)
    if not msgs:
        raise HTTPException(400, "prompt 不能为空")

    candidates = _fallback_candidates(model, fallback_models)
    last_error: Exception | None = None
    for idx, mname in enumerate(candidates):
        cfg = get_model_config(mname)
        if not cfg["api_key"]:
            continue
        try:
            return await _call_one_async(cfg, msgs, max_tokens, temperature, timeout, retries)
        except HTTPException as e:
            if e.status_code in _NON_RETRYABLE_STATUS:
                raise
            last_error = e
            if idx < len(candidates) - 1:
                logger.warning(f"LLM model {mname} failed, fallback to next: {e.detail}")
        except Exception as e:
            last_error = e
            if idx < len(candidates) - 1:
                logger.warning(f"LLM model {mname} exception, fallback to next: {e}")

    if isinstance(last_error, HTTPException):
        raise last_error
    raise HTTPException(502, "操作失败，请稍后重试")


async def _call_one_async(cfg: dict, msgs: list[dict], max_tokens: int, temperature: float, timeout: int, retries: int) -> str:
    """单模型异步调用，内置指数退避重试。"""
    url = f"{cfg['api_base']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    attempt = 0
    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            try:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    body = resp.text[:400]
                    if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                        attempt += 1
                        await asyncio.sleep(_retry_delay(attempt))
                        continue
                    logger.error(f"LLM async call failed: {resp.status_code} {body}")
                    raise HTTPException(502, "操作失败，请稍后重试")
                try:
                    return _extract_content(resp.json())
                except (ValueError, TypeError):
                    # omniroute 等网关返回 SSE 文本而非标准 JSON
                    return _extract_content(resp.text)
            except HTTPException:
                raise
            except Exception as e:
                if isinstance(e, _NETWORK_EXC) and attempt < retries:
                    attempt += 1
                    await asyncio.sleep(_retry_delay(attempt))
                    continue
                logger.error(f"LLM async call exception: {e}", exc_info=True)
                raise HTTPException(502, "操作失败，请稍后重试") from e


# ══════════════════════════════════════════════════════════════
# 流式版（SSE / Server-Sent Events）
# ══════════════════════════════════════════════════════════════


async def stream_llm_async(  # noqa: C901
    system_prompt: str = "",
    user_prompt: str = "",
    messages: list[dict] | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 300,
    model: str | None = None,
    retries: int = 2,
    fallback_models: list[str] | None = None,
):
    """SSE 流式调用 LLM，异步生成器逐块产出 ``(delta_text, accumulated_text)``。

    - 支持多轮 messages / 重试 / 备用模型降级（与 call_llm_async 一致）
    - 调用方：``async for delta, full in stream_llm_async(...):``
    - 中断/降级发生时通过异常向上抛出，由端点层决定 SSE error 事件
    """
    msgs = _build_messages(system_prompt, user_prompt, messages)
    if not msgs:
        raise HTTPException(400, "prompt 不能为空")

    candidates = _fallback_candidates(model, fallback_models)
    last_error: Exception | None = None
    for idx, mname in enumerate(candidates):
        cfg = get_model_config(mname)
        if not cfg["api_key"]:
            continue
        try:
            async for item in _stream_one(cfg, msgs, max_tokens, temperature, timeout, retries):
                yield item
            return  # 流式成功结束
        except HTTPException as e:
            if e.status_code in _NON_RETRYABLE_STATUS:
                raise
            last_error = e
            if idx < len(candidates) - 1:
                logger.warning(f"LLM stream model {mname} failed, fallback to next: {e.detail}")
        except Exception as e:
            last_error = e
            if idx < len(candidates) - 1:
                logger.warning(f"LLM stream model {mname} exception, fallback to next: {e}")

    if isinstance(last_error, HTTPException):
        raise last_error
    raise HTTPException(502, "操作失败，请稍后重试")


async def _stream_one(cfg: dict, msgs: list[dict], max_tokens: int, temperature: float, timeout: int, retries: int):  # noqa: C901
    """单模型流式调用，内置指数退避重试。产出 (delta, full)。"""
    url = f"{cfg['api_base']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": msgs,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    attempt = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "replace")[:400]
                        if resp.status_code in _RETRYABLE_STATUS and attempt < retries:
                            attempt += 1
                            await asyncio.sleep(_retry_delay(attempt))
                            continue
                        raise HTTPException(502, "操作失败，请稍后重试")
                    full_parts: list[str] = []
                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                            delta = obj["choices"][0]["delta"]
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue
                        if not isinstance(delta, dict):
                            continue
                        piece = delta.get("content") or delta.get("reasoning_content") or ""
                        if piece:
                            full_parts.append(piece)
                            yield piece, "".join(full_parts)
                    return
        except HTTPException:
            raise
        except Exception as e:
            if isinstance(e, _NETWORK_EXC) and attempt < retries:
                attempt += 1
                await asyncio.sleep(_retry_delay(attempt))
                continue
            raise


# ══════════════════════════════════════════════════════════════
# 对话历史组装
# ══════════════════════════════════════════════════════════════


def build_conversation_messages(
    conversation_id: str = "",
    session_id: str = "",
    system_prompt: str = "",
    max_rounds: int = 12,
    max_chars: int = 24000,
) -> list[dict]:
    """从 messages 表加载对话历史，组装多轮 messages（供真实上下文对话）。

    - conversation_id（聊天页）与 session_id（Agent 执行页）双轨兼容，二选一
    - 仅保留 user/assistant 轮次（忽略内部消息）
    - 窗口裁剪：最多 max_rounds 轮；总字符超 max_chars 时从最早丢弃
    - system_prompt 恒置最前
    """
    from common.db import get_db

    turns: list[dict] = []
    if conversation_id or session_id:
        conn = get_db()
        try:
            if conversation_id:
                rows = conn.execute(
                    "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC",
                    (conversation_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT role, content FROM messages WHERE session_id=? ORDER BY id ASC",
                    (session_id,),
                ).fetchall()
        finally:
            conn.close()
        turns = [
            dict(r) for r in rows if r["role"] in ("user", "assistant") and str(r["content"] or "").strip()
        ]
    turns = turns[-max_rounds:]
    while turns and sum(len(t["content"]) for t in turns) > max_chars:
        turns.pop(0)
    msgs: list[dict] = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.extend(turns)
    return msgs


# ══════════════════════════════════════════════════════════════
# 使用统计与 JSON 容错解析（v12.0 保留）
# ══════════════════════════════════════════════════════════════


def log_usage(task_type: str, input_len: int, output_len: int, elapsed: float, success: bool = True, error: str = "", api_key: str = "", user_id: str = "") -> None:
    """记录使用统计到 usage_logs。失败静默（不影响主流程）。

    error 为失败原因摘要（阶段标记 [stage:xxx] 等），供运营诊断失败率。
    api_key 为开放网关调用来源（api_keys.id），用于 API Key 使用报表（v13.23）。
    user_id 为平台用户（users.id），用于用量分析按用户筛选（v15）。
    """
    try:
        from common.db import get_db_context

        with get_db_context() as conn:
            # 幂等补列：老库无 error 列（v13.1 诊断埋点）/ 无 api_key 列（v13.23 报表）/ 无 user_id 列（v15 按用户筛选）
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(usage_logs)").fetchall()]
            if "error" not in cols:
                conn.execute("ALTER TABLE usage_logs ADD COLUMN error TEXT DEFAULT ''")
            if "api_key" not in cols:
                conn.execute("ALTER TABLE usage_logs ADD COLUMN api_key TEXT DEFAULT ''")
            if "user_id" not in cols:
                conn.execute("ALTER TABLE usage_logs ADD COLUMN user_id TEXT DEFAULT ''")
            conn.commit()
            conn.execute(
                """INSERT INTO usage_logs (timestamp, task_type, input_length, output_length, response_time, success, error, api_key, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    task_type,
                    input_len,
                    output_len,
                    round(elapsed, 3),
                    1 if success else 0,
                    (error or "")[:500],
                    (api_key or "")[:64],
                    (user_id or "")[:64],
                ),
            )
    except Exception as e:
        logger.debug(f"log_usage skipped: {e}")


def parse_llm_json(raw: str) -> dict:
    """解析 LLM 返回的 JSON（多级容错，保证生产可用性）。

    LLM 输出经常带 ```json 围栏、前后说明文字、尾逗号、单引号、注释等，
    长文本场景下直接 json.loads 失败率高，这里按序降级重试：
    1. 去代码块围栏 → 2. 提取首个 { 至最后一个 } 片段 → 3. 剥离注释 → 4. 修复尾逗号 → 5. 修复单引号。
    全部失败时抛出带原始内容摘要的异常，便于定位。
    """
    import re

    text = (raw or "").strip()
    if not text:
        raise ValueError("LLM 返回内容为空，无法解析 JSON")

    candidates = [text]
    # 1. 剥离 markdown 代码块围栏
    fence = re.match(r"^```(?:json)?\s*\n(.*?)\n```\s*$", text, re.S)
    if fence:
        candidates.append(fence.group(1).strip())
    # 2. 提取首个 { 到最后一个 } 的 JSON 片段
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        for fix in (
            lambda s: s,  # 原样
            lambda s: _strip_json_comments(s),  # 剥离 // 与 /* */ 注释（字符串内不受影响）
            lambda s: _strip_json_comments(re.sub(r",(\s*[}\]])", r"\1", s)),  # 注释 + 尾逗号
            lambda s: re.sub(r"'([^']*)'\s*:", r'"\1":', s),  # 单引号 key
            lambda s: re.sub(r"'([^']*)'", r'"\1"', s),  # 单引号字符串
        ):
            try:
                return json.loads(fix(candidate))
            except Exception:
                continue

    snippet = text[:120].replace("\n", " ")
    raise ValueError(f"LLM 返回无法解析为 JSON（内容开头：{snippet}…）")


def _strip_json_comments(s: str) -> str:
    """安全剥离 JSON 中的 // 行注释与 /* */ 块注释（跳过字符串字面量内部，避免误伤 URL 等）。"""
    out = []
    i, n = 0, len(s)
    in_str = False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)
