#!/usr/bin/env python3
"""LLM 调用 + 使用统计 — 单一来源。

替代 prd_engine.py 与 chat_engine.py 中重复的 call_llm 定义。
"""

import logging
from datetime import datetime

import httpx
import requests
from fastapi import HTTPException

from common.config import get_model_config

logger = logging.getLogger(__name__)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 300,
    model: str | None = None,
) -> str:
    """调用 LLM（OpenAI 兼容 /chat/completions），按模型路由到对应供应商。

    model 参数可覆盖全局模型（None 时使用全局配置）。
    每个模型可在模型列表配置独立的 base_url / api_key（多供应商接入）。
    统一了旧 prd_engine(max_tokens=4000, temp=0.4) 与 chat_engine(max_tokens=2000) 两版实现。
    """
    cfg = get_model_config(model)
    api_key, api_base, model = cfg["api_key"], cfg["api_base"], cfg["model"]
    if not api_key:
        raise HTTPException(400, f"未配置模型 {model} 的 API Key（可在系统配置-模型列表中设置）")

    url = f"{api_base}/chat/completions"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.error(f"LLM call failed: {resp.status_code} {resp.text[:400]}")
            raise HTTPException(500, f"LLM 调用失败: {resp.status_code} {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM call exception: {e}", exc_info=True)
        # 连接类异常（EOFError/ConnectionResetError 等）str 常为空，兜底为可读文案，避免用户看到空白错误
        detail = str(e) or f"{type(e).__name__}（连接异常），请稍后重试"
        raise HTTPException(500, f"LLM 调用异常: {detail}") from e


# 同步版本的别名（向后兼容）
call_llm_sync = call_llm


async def call_llm_async(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 300,
    model: str | None = None,
) -> str:
    """异步调用 LLM（使用 httpx.AsyncClient 非阻塞），按模型路由到对应供应商。

    model 参数可覆盖全局模型（None 时使用全局配置）。
    在 async FastAPI 端点中应使用此版本以避免阻塞事件循环。
    """
    cfg = get_model_config(model)
    api_key, api_base, model = cfg["api_key"], cfg["api_base"], cfg["model"]
    if not api_key:
        raise HTTPException(400, f"未配置模型 {model} 的 API Key（可在系统配置-模型列表中设置）")

    url = f"{api_base}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if resp.status_code != 200:
                logger.error(f"LLM async call failed: {resp.status_code} {resp.text[:400]}")
                raise HTTPException(500, f"LLM 调用失败: {resp.status_code} {resp.text[:300]}")
            return resp.json()["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except Exception as e:
        # exc_info 打印完整 traceback：连接类异常（EOFError/ConnectionResetError 等）str 常为空，
        # 只记消息会导致线上无法定位根因；同时给用户可读的兜底文案而非空白
        logger.error(f"LLM async call exception: {e}", exc_info=True)
        detail = str(e) or f"{type(e).__name__}（连接异常），请稍后重试"
        raise HTTPException(500, f"LLM 调用异常: {detail}") from e


def log_usage(task_type: str, input_len: int, output_len: int, elapsed: float, success: bool = True) -> None:
    """记录使用统计到 usage_logs。失败静默（不影响主流程）。"""
    try:
        from common.db import get_db_context

        with get_db_context() as conn:
            conn.execute(
                """INSERT INTO usage_logs (timestamp, task_type, input_length, output_length, response_time, success)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), task_type, input_len, output_len, round(elapsed, 3), 1 if success else 0),
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
    import json
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
