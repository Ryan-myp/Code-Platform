"""AI实时语音对话 — 语音转文字 → LLM 回复 → 语音合成。

- POST /api/voice-chat/transcribe  语音转文字（接收 Base64 音频）
- POST /api/voice-chat/respond     LLM 智能回复
- POST /api/voice-chat/tts         文字转语音
- POST /api/voice-chat/chat        一站式：文字输入 → LLM 回复（简化模式）
"""

import base64
import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice-chat", tags=["语音对话"])

# ── System Prompts ─────────────────────────────────────────

VOICE_CHAT_SYSTEM = """你是一个友好的AI语音助手，名叫"小团"。你的特点是：
1. 回复简洁自然，适合语音朗读（每次回复控制在80-150字）
2. 语气温暖亲切，像朋友聊天
3. 适当使用语气词让对话更自然
4. 如果用户问技术问题，用通俗易懂的方式解释

请直接给出回复文本，不要加任何前缀标签。"""

# ── 模型 ──────────────────────────────────────────────────

class TranscribeRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64编码的音频数据")
    format: str = Field("webm", description="音频格式: webm/wav/mp3")


class RespondRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, description="对话历史 [{\"role\":\"user/assistant\",\"content\":\"...\"}]")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="音色ID")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


# ── API ──────────────────────────────────────────────────

@router.post("/transcribe")
async def voice_to_text(req: TranscribeRequest, current_user: dict = require_auth()):
    """语音转文字：模拟STT，实际返回提示让前端使用浏览器Web Speech API。"""
    start = datetime.now()

    # 目前后端不处理真实STT（需要额外服务），引导前端使用浏览器内置Web Speech API
    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("voice_transcribe", len(req.audio_base64), 0, elapsed)

    return {
        "mode": "client_side",
        "message": "请使用浏览器内置Web Speech API进行语音识别（前端已集成）",
        "hint": "浏览器支持SpeechRecognition，无需后端处理音频",
    }


@router.post("/respond")
async def voice_respond(req: RespondRequest, current_user: dict = require_auth()):
    """LLM智能语音回复：根据用户输入生成适合语音朗读的回复。"""
    start = datetime.now()

    # 构建消息历史
    messages_text = ""
    for h in req.history[-6:]:  # 最近6轮对话
        role = "用户" if h.get("role") == "user" else "助手"
        messages_text += f"{role}：{h.get('content', '')}\n"
    messages_text += f"用户：{req.message}"

    try:
        raw = call_llm(VOICE_CHAT_SYSTEM, messages_text, max_tokens=300, temperature=0.7, timeout=30)
        reply = raw.strip()
    except Exception as e:
        logger.exception("voice respond failed")
        raise HTTPException(500, f"AI回复失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("voice_respond", len(req.message), len(reply), elapsed)

    return {
        "reply": reply,
        "input_length": len(req.message),
        "output_length": len(reply),
    }


@router.post("/tts")
async def text_to_speech(req: TTSRequest, current_user: dict = require_auth()):
    """文字转语音：代理到 voice_factory 的 TTS 引擎。"""
    start = datetime.now()

    try:
        from voice_factory import _tts_one
        audio_path = _tts_one(req.text, req.voice_id)
        audio_url = f"/api/voice-chat/audio/{os.path.basename(audio_path)}"
    except Exception as e:
        logger.warning(f"TTS via voice_factory failed: {e}, returning empty")
        audio_url = ""

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("voice_tts", len(req.text), 0, elapsed)

    return {
        "audio_url": audio_url,
        "text": req.text,
        "voice_id": req.voice_id,
    }


@router.post("/chat")
async def voice_chat(req: ChatRequest, current_user: dict = require_auth()):
    """一站式语音对话：文字 → LLM回复。前端Web Speech API处理语音部分。"""
    start = datetime.now()

    try:
        raw = call_llm(VOICE_CHAT_SYSTEM, f"用户：{req.message}", max_tokens=300, temperature=0.7, timeout=30)
        reply = raw.strip()
    except Exception as e:
        logger.exception("voice chat failed")
        raise HTTPException(500, f"AI对话失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("voice_chat", len(req.message), len(reply), elapsed)

    return {
        "reply": reply,
        "input": req.message,
    }
