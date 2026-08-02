#!/usr/bin/env python3
"""LLM 调用 + 使用统计 — 单一来源。

替代 prd_engine.py 与 chat_engine.py 中重复的 call_llm 定义。
"""

import logging
from datetime import datetime

import httpx
import requests
from fastapi import HTTPException

from common.config import get_llm_config

logger = logging.getLogger(__name__)


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 120,
) -> str:
    """调用 Agnes LLM（OpenAI 兼容 /chat/completions）。

    统一了旧 prd_engine(max_tokens=4000, temp=0.4) 与 chat_engine(max_tokens=2000) 两版实现。
    """
    api_key, api_base, model = get_llm_config()
    if not api_key:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

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
        logger.error(f"LLM call exception: {e}")
        raise HTTPException(500, f"LLM 调用异常: {str(e)}") from e


# 同步版本的别名（向后兼容）
call_llm_sync = call_llm


async def call_llm_async(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4000,
    temperature: float = 0.4,
    timeout: int = 120,
) -> str:
    """异步调用 Agnes LLM（使用 httpx.AsyncClient 非阻塞）。

    在 async FastAPI 端点中应使用此版本以避免阻塞事件循环。
    """
    api_key, api_base, model = get_llm_config()
    if not api_key:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

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
        logger.error(f"LLM async call exception: {e}")
        raise HTTPException(500, f"LLM 调用异常: {str(e)}") from e


def log_usage(task_type: str, input_len: int, output_len: int, elapsed: float, success: bool = True) -> None:
    """记录使用统计到 usage_logs。失败静默（不影响主流程）。"""
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            """INSERT INTO usage_logs (timestamp, task_type, input_length, output_length, response_time, success)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(), task_type, input_len, output_len, round(elapsed, 3), 1 if success else 0),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"log_usage skipped: {e}")
