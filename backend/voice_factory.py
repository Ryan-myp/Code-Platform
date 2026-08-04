#!/usr/bin/env python3
"""AI 配音工坊 — 文字转语音（TTS）。

- 调用 Agnes 中转站 OpenAI 兼容 /audio/speech（模型 tts-1，Azure Neural 音色）
- 场景预设（短视频旁白/广告口播/有声书/新闻播报/儿童故事）+ 自由音色/语速
- 长文本自动分段合成（每段 ≤ 900 字），ffmpeg 无损拼接为完整 mp3
- 产物保存到 voice_factory/ 目录并登记 artifacts 表（type=audio）
"""

import asyncio
import logging
import os
import re
import subprocess
import tempfile
import time
import uuid
from datetime import datetime

import requests
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse

from common.config import load_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["AI配音工坊"])

load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY  # noqa: E402

VOICE_DIR = os.path.join(os.path.dirname(__file__), "voice_factory")
os.makedirs(VOICE_DIR, exist_ok=True)

# Azure Neural 音色表（与中转站 tts-1 兼容）
VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "女", "style": "温柔亲切，清晰自然", "emoji": "👩"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "女", "style": "活泼俏皮，适合生活类内容", "emoji": "👧"},
    {"id": "zh-CN-YunxiNeural", "name": "云希", "gender": "男", "style": "阳光少年感，适合解说/口播", "emoji": "👦"},
    {"id": "zh-CN-YunjianNeural", "name": "云健", "gender": "男", "style": "成熟浑厚，适合品牌/宣传", "emoji": "🧔"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬", "gender": "男", "style": "字正腔圆，新闻播报感", "emoji": "🎙️"},
    {"id": "zh-CN-XiaomoNeural", "name": "晓墨", "gender": "童", "style": "童声可爱，适合儿童/亲子内容", "emoji": "🧒"},
    {"id": "en-US-AriaNeural", "name": "Aria", "gender": "女", "style": "英文女声，自然流利", "emoji": "🇺🇸"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher", "gender": "男", "style": "英文男声，沉稳有力", "emoji": "🇬🇧"},
]

# 场景预设：一键套用「音色 + 语速」
SCENES = [
    {"id": "shortvideo", "name": "短视频旁白", "desc": "节奏明快，适合口播/知识解说", "voice": "zh-CN-XiaoxiaoNeural", "speed": 1.05},
    {"id": "ad", "name": "广告口播", "desc": "有感染力，适合产品宣传/带货", "voice": "zh-CN-YunjianNeural", "speed": 1.0},
    {"id": "audiobook", "name": "有声书", "desc": "娓娓道来，适合故事/小说朗读", "voice": "zh-CN-XiaoxiaoNeural", "speed": 0.95},
    {"id": "news", "name": "新闻播报", "desc": "字正腔圆，适合资讯/播报类", "voice": "zh-CN-YunyangNeural", "speed": 1.0},
    {"id": "story", "name": "儿童故事", "desc": "活泼童趣，适合亲子/教育内容", "voice": "zh-CN-XiaomoNeural", "speed": 0.95},
    {"id": "custom", "name": "自定义", "desc": "自由选择音色与语速", "voice": "zh-CN-XiaoxiaoNeural", "speed": 1.0},
]

MAX_SEGMENT_CHARS = 400   # 单段最大字符数（edge-tts 长文本会内部限速，分段更稳）
MAX_TEXT_CHARS = 10000   # 总文本上限


def _split_text(text: str) -> list[str]:
    """按句子边界切分长文本为多段（每段 ≤ MAX_SEGMENT_CHARS）。"""
    text = text.strip()
    if len(text) <= MAX_SEGMENT_CHARS:
        return [text]
    # 优先按句号/问号/感叹号/换行切分
    chunks, buf = [], ""
    for part in re.split(r"(?<=[。！？.!?\n])", text):
        if not part:
            continue
        if len(buf) + len(part) > MAX_SEGMENT_CHARS and buf:
            chunks.append(buf.strip())
            buf = part
        else:
            buf += part
    if buf.strip():
        chunks.append(buf.strip())
    # 兜底：仍超长的段硬切
    final = []
    for c in chunks:
        while len(c) > MAX_SEGMENT_CHARS:
            final.append(c[:MAX_SEGMENT_CHARS])
            c = c[MAX_SEGMENT_CHARS:]
        if c:
            final.append(c)
    return final


def _tts_one(text: str, voice: str, speed: float) -> bytes:
    """单段 TTS 合成，返回 mp3 字节。

    优先 edge-tts（子进程隔离，超时 45s 自动 kill，绝不阻塞主进程），
    失败回退中转站 /audio/speech（需开通 tts-1 渠道）。
    """
    try:
        return _tts_edge(text, voice, speed)
    except Exception as e:
        logger.warning(f"edge-tts 失败，回退中转站 API: {e}")
    if not AGNES_API_KEY:
        raise HTTPException(500, "TTS 通道不可用（edge-tts 与中转站均失败），请稍后重试")
    resp = requests.post(
        f"{AGNES_API_BASE}/audio/speech",
        headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
        json={"model": "tts-1", "input": text, "voice": voice, "speed": speed},
        timeout=90,
    )
    if resp.status_code != 200:
        raise HTTPException(500, f"TTS 调用失败: {resp.status_code} {resp.text[:300]}")
    return resp.content


def _tts_edge(text: str, voice: str, speed: float) -> bytes:
    """edge-tts 合成（Azure Neural 音色，免费通道，子进程隔离）。"""
    import subprocess
    import sys

    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_tts_worker.py")
    rate = f"{int(round((speed - 1) * 100)):+d}%"
    fd, tmp = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        result = subprocess.run(
            [sys.executable, worker, text, voice, rate, tmp],
            capture_output=True, timeout=45,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace")[:200] or f"exit {result.returncode}")
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _merge_mp3(seg_files: list[str], out_path: str) -> None:
    """ffmpeg concat 无损拼接多个 mp3。"""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in seg_files:
            f.write(f"file '{p}'\n")
        list_file = f.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out_path],
            capture_output=True, timeout=120,
        )
    finally:
        os.unlink(list_file)


def _audio_duration(path: str) -> float:
    """ffprobe 读取音频真实时长（秒）。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30,
        )
        return round(float(out.stdout.strip()), 1)
    except Exception:
        return 0.0


def _save_artifact(filename: str, text: str, extra: dict) -> str:
    """登记 artifacts 表（type=audio），失败静默。"""
    art_id = f"art_{uuid.uuid4().hex[:12]}"
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            """INSERT INTO artifacts
               (id, project_id, type, content, version, author, created_at, active, media_url, duration, metadata)
               VALUES (?, ?, 'audio', ?, 'v1', 'voice_factory', ?, 1, ?, ?, ?)""",
            (art_id, "", text[:500],
             datetime.now().isoformat(), f"/api/voice/audios/{filename}",
             0.0, __import__("json").dumps(extra, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"_save_artifact skipped: {e}")
    return art_id


@router.post("/generate")
async def generate_voice(
    text: str = Form(...),
    scene: str = Form("shortvideo"),
    voice: str = Form(""),
    speed: float = Form(1.0),
    project_id: str = Form(""),
):
    """文字转语音：场景预设或自由音色，长文本自动分段拼接。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY（系统配置-模型配置中设置）")
    text = (text or "").strip()
    if not text:
        raise HTTPException(400, "请输入要配音的文本")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(400, f"文本过长（{MAX_TEXT_CHARS} 字以内），请分段生成")

    scene_cfg = next((s for s in SCENES if s["id"] == scene), None)
    if scene and scene != "custom" and not scene_cfg:
        raise HTTPException(400, f"未知场景: {scene}")
    tts_voice = voice or (scene_cfg["voice"] if scene_cfg else "zh-CN-XiaoxiaoNeural")
    tts_speed = speed if scene == "custom" else (scene_cfg["speed"] if scene_cfg else speed)
    tts_speed = max(0.5, min(2.0, float(tts_speed)))

    start = time.time()
    segments = _split_text(text)
    if not segments:
        raise HTTPException(400, "文本为空")

    try:
        tmp_dir = tempfile.mkdtemp(prefix="voice_seg_")
        seg_files = []
        for i, seg in enumerate(segments):
            data = await asyncio.to_thread(_tts_one, seg, tts_voice, tts_speed)
            seg_path = os.path.join(tmp_dir, f"seg_{i}.mp3")
            with open(seg_path, "wb") as f:
                f.write(data)
            seg_files.append(seg_path)

        filename = f"voice_{int(time.time() * 1000)}.mp3"
        out_path = os.path.join(VOICE_DIR, filename)
        if len(seg_files) == 1:
            with open(out_path, "wb") as f:
                f.write(open(seg_files[0], "rb").read())
        else:
            _merge_mp3(seg_files, out_path)
        duration = _audio_duration(out_path) or round(len(text) / 4.5, 1)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 生成失败: {e}")
        raise HTTPException(500, f"配音生成失败: {str(e)}") from e
    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)

    art_id = _save_artifact(filename, text,
                            {"voice": tts_voice, "scene": scene, "speed": tts_speed, "segments": len(segments)})
    elapsed = round(time.time() - start, 2)
    from common.llm import log_usage

    log_usage("voice_generate", len(text), 0, elapsed)
    return {
        "id": filename,
        "artifact_id": art_id,
        "url": f"/api/voice/audios/{filename}",
        "voice": tts_voice,
        "scene": scene,
        "speed": tts_speed,
        "duration": duration,
        "segments": len(segments),
        "text": text[:200],
    }


@router.get("/audios/{filename}")
async def get_audio(filename: str):
    path = os.path.join(VOICE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "配音不存在")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/list")
async def list_voices():
    items = []
    if os.path.exists(VOICE_DIR):
        for f in sorted(os.listdir(VOICE_DIR), reverse=True):
            if not f.endswith(".mp3"):
                continue
            filepath = os.path.join(VOICE_DIR, f)
            stat = os.stat(filepath)
            items.append({
                "id": f,
                "url": f"/api/voice/audios/{f}",
                "size": stat.st_size,
                "duration": _audio_duration(filepath),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return items


@router.delete("/{filename}")
async def delete_voice(filename: str):
    path = os.path.join(VOICE_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return {"success": True}
