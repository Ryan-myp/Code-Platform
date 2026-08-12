"""AI实时语音对话 — 语音转文字 → LLM 回复 → 语音合成。

- POST /api/voice-chat/respond     LLM 智能回复
- POST /api/voice-chat/tts         文字转语音
"""

import asyncio
import logging
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.llm import call_llm, log_usage, _safe_exc_msg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice-chat", tags=["语音对话"])

# ── System Prompts ─────────────────────────────────────────

VOICE_CHAT_SYSTEM = """你是「小团智能平台」的AI语音助手，名叫"小团"，一位声音甜美、反应敏捷、善解人意的智能伙伴。

## 角色特质
- 像一位懂技术的朋友：专业但不装，亲切但不油腻
- 善于倾听：先完整理解用户说什么，再针对性回应
- 有幽默感：适当场合可以轻松调侃（如用户说"好无聊"时回"那我给你讲个AI冷笑话？"）

## 回复规范（语音场景专用）
1. **短句优先**：每句话15-25字，一句一意，方便语音合成自然停顿
2. **先确认再展开**：用1-2句确认理解（"嗯，你是想问...对吧？"），再给核心信息
3. **结论先行**：先说答案，再说原因/步骤/建议，不绕弯子
4. **信息分层**：单次回复50-120字（约15-30秒朗读），复杂话题引导用户追问"需要我说详细点吗？"
5. **技术翻译**：专业术语用生活化比喻（"API就像餐厅服务员帮你向后厨传话"），不用缩写

## 话题策略
- **平台功能咨询**：功能名+一句话价值+访问路径（"这个在左边的创作工厂里，叫XX工坊，点进去就能用"）
- **操作指导**：用"你先...然后...最后..."的叙事顺序，不用编号
- **技术探讨**：通俗解释+1个生活例子+"想深入了解的话我还可以说更多"
- **闲聊问候**：友好回应+自然引导到平台能帮什么（"今天想用我帮你做点啥？写文案？做PPT？还是分析数据？"）
- **超出能力**：诚实说明+给出替代方案（"这个我暂时帮不上，不过你可以试试平台的XX功能，也许能解决"）

## 禁止事项
- 不用列表序号（1. 2. 3.），改用"首先其次最后"
- 不生成URL链接（语音无法点击，说"在左边菜单找XX"即可）
- 单次回复不超过150字（超过则主动问"需要我展开说吗？"）
- 不评价竞品或做横向对比
- 不承诺平台做不到的事情

直接返回对话文本，不要加任何前缀标签。"""

# ── 模型 ──────────────────────────────────────────────────


class TranscribeRequest(BaseModel):
    audio_base64: str = Field(..., description="Base64编码的音频数据")
    format: str = Field("webm", description="音频格式: webm/wav/mp3")


class RespondRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] = Field(
        default_factory=list, description='对话历史 [{"role":"user/assistant","content":"..."}]'
    )


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="音色ID")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


# ── API ──────────────────────────────────────────────────


@router.post("/respond")
def voice_respond(req: RespondRequest, current_user: dict = require_auth()):
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
        raise HTTPException(500, "操作失败，请稍后重试") from e

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("voice_respond", len(req.message), len(reply), elapsed)

    return {
        "reply": reply,
        "input_length": len(req.message),
        "output_length": len(reply),
    }


@router.post("/tts")
async def text_to_speech(req: TTSRequest, current_user: dict = require_auth()):
    """文字转语音：调用 voice_factory TTS 引擎，保存为 mp3 文件并返回 URL。"""
    start = datetime.now()

    tts_dir = os.path.join(os.path.dirname(__file__), "uploads", "tts")
    os.makedirs(tts_dir, exist_ok=True)

    try:
        from voice_factory import _tts_one

        # 同步 TTS（网络请求 30-120s）在独立线程执行，避免阻塞事件循环
        audio_bytes = await asyncio.to_thread(_tts_one, req.text, req.voice_id, 1.0)
        filename = f"tts_{int(datetime.now().timestamp() * 1000)}.mp3"
        filepath = os.path.join(tts_dir, filename)
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        audio_url = f"/uploads/tts/{filename}"
    except Exception as e:
        logger.warning(f"TTS failed: {e}")
        audio_url = ""

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("voice_tts", len(req.text), 0, elapsed)

    return {
        "audio_url": audio_url,
        "text": req.text,
        "voice_id": req.voice_id,
    }
