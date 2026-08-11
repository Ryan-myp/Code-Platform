#!/usr/bin/env python3
"""CosyVoice2 独立推理服务（voice_engine）

独立进程 + 独立 venv（/Users/yanping.ma/ai-models/cv-venv），通过 HTTP 与平台解耦：
- GET  /health            服务状态、设备、内置音色
- POST /tts/sft           内置音色合成（text + spk_id）
- POST /tts/zero_shot     零样本克隆（text + prompt_text + prompt_wav）
- POST /sing              歌声合成（lyrics + instruct + prompt_wav，instruct2 模式）

推理在后台线程串行执行（MPS 并发不稳定），接口为 async 避免阻塞事件循环。
"""
import asyncio
import io
import logging
import os
import sys
import threading
import time

import torch
import torchaudio
import uvicorn
from fastapi import FastAPI, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from patch_audio import patch_audio

patch_audio()

MODEL_DIR = os.environ.get(
    "COSYVOICE_MODEL_DIR", "/Users/yanping.ma/ai-models/CosyVoice2-0.5B"
)
SAMPLE_RATE = 22050

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger("voice_engine")

app = FastAPI(title="Voice Engine (CosyVoice2)", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_infer_lock = threading.Lock()
cosyvoice = None


def load_model():
    """懒加载模型（首次请求或启动时）"""
    global cosyvoice
    if cosyvoice is not None:
        return
    sys.path.insert(0, "/Users/yanping.ma/ai-models/CosyVoice")
    sys.path.insert(0, "/Users/yanping.ma/ai-models/CosyVoice/third_party/Matcha-TTS")
    from cosyvoice.cli.cosyvoice import CosyVoice2

    logger.info("loading CosyVoice2 from %s ...", MODEL_DIR)
    t0 = time.time()
    cosyvoice = CosyVoice2(MODEL_DIR)
    logger.info(
        "model loaded in %.1fs, device=%s, spks=%s",
        time.time() - t0,
        cosyvoice.model.device,
        cosyvoice.list_available_spks(),
    )


def _consume(generator):
    """在锁内消费生成器（inference_* 均为惰性生成器，必须整体包在锁里）"""
    with _infer_lock:
        return list(generator)


def _load_prompt_wav(file: UploadFile) -> torch.Tensor:
    """读取上传的参考音频并重采样到 22050Hz"""
    data = file.file.read()
    wav, sr = torchaudio.load(io.BytesIO(data), backend="soundfile")
    if sr != SAMPLE_RATE:
        wav = torchaudio.functional.resample(wav, sr, SAMPLE_RATE)
    return wav


def _wav_bytes(wav: torch.Tensor) -> bytes:
    buf = io.BytesIO()
    torchaudio.save(buf, wav, SAMPLE_RATE, format="wav")
    return buf.getvalue()


@app.on_event("startup")
def startup():
    load_model()


@app.get("/health")
def health():
    if torch.cuda.is_available():
        dev = "cuda"
    elif torch.backends.mps.is_available():
        dev = "mps"
    else:
        dev = "cpu"
    return {
        "status": "ok" if cosyvoice is not None else "loading",
        "engine": "cosyvoice2",
        "device": dev,
        "sample_rate": SAMPLE_RATE,
        "spk_ids": cosyvoice.list_available_spks() if cosyvoice else [],
    }


@app.post("/tts/sft")
async def tts_sft(text: str = Form(...), spk_id: str = Form("中文女"), speed: float = Form(1.0)):
    """内置音色合成"""
    load_model()

    def work():
        t0 = time.time()
        chunks = []
        for out in _consume(cosyvoice.inference_sft(text, spk_id, speed=speed)):
            chunks.append(out["tts_speech"])
        wav = torch.cat(chunks, dim=1)
        logger.info(
            "sft %.1fs -> %.1fs audio (spk=%s)", time.time() - t0, wav.shape[1] / SAMPLE_RATE, spk_id
        )
        return _wav_bytes(wav)

    return Response(content=await asyncio.to_thread(work), media_type="audio/wav")


@app.post("/tts/zero_shot")
async def tts_zero_shot(
    text: str = Form(...),
    prompt_text: str = Form(...),
    prompt_wav: UploadFile = None,
    speed: float = Form(1.0),
):
    """零样本音色克隆：上传 3-10s 参考音频 + 对应文本，克隆其音色合成新文本"""
    load_model()
    if prompt_wav is None:
        return Response(content="prompt_wav required", status_code=400)

    prompt = _load_prompt_wav(prompt_wav)

    def work():
        t0 = time.time()
        chunks = []
        for out in _consume(
            cosyvoice.inference_zero_shot(text, prompt_text, prompt, speed=speed)
        ):
            chunks.append(out["tts_speech"])
        wav = torch.cat(chunks, dim=1)
        logger.info(
            "zero_shot %.1fs -> %.1fs audio", time.time() - t0, wav.shape[1] / SAMPLE_RATE
        )
        return _wav_bytes(wav)

    return Response(content=await asyncio.to_thread(work), media_type="audio/wav")


@app.post("/sing")
async def sing(
    lyrics: str = Form(...),
    instruct: str = Form("请用中文演唱下面的歌词，注意音准和节奏<|endofprompt|>"),
    prompt_wav: UploadFile = None,
    speed: float = Form(1.0),
):
    """歌声合成（instruct2 模式）：提供一段参考人声（说话或唱歌均可），
    instruct 描述演唱方式，lyrics 为歌词。"""
    load_model()
    if prompt_wav is None:
        return Response(content="prompt_wav required", status_code=400)

    prompt = _load_prompt_wav(prompt_wav)

    def work():
        t0 = time.time()
        chunks = []
        for out in _consume(
            cosyvoice.inference_instruct2(lyrics, instruct, prompt, speed=speed)
        ):
            chunks.append(out["tts_speech"])
        wav = torch.cat(chunks, dim=1)
        logger.info(
            "sing %.1fs -> %.1fs audio", time.time() - t0, wav.shape[1] / SAMPLE_RATE
        )
        return _wav_bytes(wav)

    return Response(content=await asyncio.to_thread(work), media_type="audio/wav")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9888, log_level="info")
