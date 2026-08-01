#!/usr/bin/env python3
"""音乐工厂模块 - 歌词生成、音乐生成、虚拟人声"""

import json
import logging
import os
import time
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/music-factory", tags=["音乐工厂"])

AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://api.agnes-ai.cn/v1")

MUSIC_DIR = Path(__file__).parent / "music_factory"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)


def save_music(data: bytes, filename: str) -> str:
    """保存音乐文件"""
    filepath = MUSIC_DIR / filename
    filepath.write_bytes(data)
    return filename


def generate_music_id() -> str:
    """生成唯一音乐ID"""
    return f"music_{int(time.time() * 1000)}"


@router.get("/stats")
async def get_stats():
    """获取音乐统计"""
    music_count = len(list(MUSIC_DIR.glob("*"))) if MUSIC_DIR.exists() else 0
    return {
        "total_tracks": music_count,
        "music_dir": str(MUSIC_DIR),
        "api_configured": bool(AGNES_API_KEY),
    }


@router.post("/lyrics/generate")
async def generate_lyrics(
    theme: str = ...,
    style: str = "pop",  # pop, rock, rap, ballad, jazz, classical
    language: str = "zh",  # zh, en
    length: str = "short",  # short, medium, long
):
    """生成歌词"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    style_prompts = {
        "pop": "流行歌曲",
        "rock": "摇滚歌曲",
        "rap": "说唱歌曲",
        "ballad": "抒情歌曲",
        "jazz": "爵士乐",
        "classical": "古典音乐",
    }
    lang_prompts = {
        "zh": "中文",
        "en": "英文",
    }
    length_prompts = {
        "short": "30秒到1分钟的短歌曲，包含主歌和副歌",
        "medium": "2到3分钟的完整歌曲，包含主歌、副歌和桥段",
        "long": "3到5分钟的长篇歌曲，包含多个段落和变奏",
    }

    prompt = f"""创作一首{lang_prompts.get(language, '中文')}{style_prompts.get(style, '流行')}的歌词：
主题：{theme}
风格：{style}
长度要求：{length_prompts.get(length, '短歌曲')}

要求：
- 歌词要富有诗意和感染力
- 包含主歌(Verse)、副歌(Chorus)、桥段(Bridge)结构
- 使用押韵
- 情感表达要真挚

请只输出歌词，不要解释。格式：
[Verse 1]
...
[Chorus]
...
[Verse 2]
...
[Chorus]
[Bridge]
...
[Chorus]
..."""

    try:
        response = requests.post(
            f"{AGNES_API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {AGNES_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "agnes-2.5-flash",
                "messages": [
                    {"role": "system", "content": "你是一位专业的歌词创作者，擅长创作优美动人的歌词。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2000,
            },
            timeout=60,
        )

        if response.status_code != 200:
            raise HTTPException(500, f"生成歌词失败: {response.text}")

        data = response.json()
        lyrics = data.get("choices", [{}])[0].get("message", {}).get("content", "")

        return {
            "lyrics": lyrics,
            "theme": theme,
            "style": style,
            "language": language,
            "length": length,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成歌词异常: {e}")
        raise HTTPException(500, f"生成歌词失败: {str(e)}")


@router.post("/music/generate")
async def generate_music(
    lyrics: str = ...,
    style: str = "pop",
    mood: str = "happy",  # happy, sad, energetic, calm, romantic
    duration: int = 30,
):
    """生成音乐（调用第三方API或占位）"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    # 暂时返回占位，未来可以接入 Suno/Udio API
    music_id = generate_music_id()
    
    # 模拟生成过程
    result = {
        "music_id": music_id,
        "lyrics": lyrics[:200] + "..." if len(lyrics) > 200 else lyrics,
        "style": style,
        "mood": mood,
        "duration": duration,
        "status": "pending",
        "message": "音乐生成功能正在开发中，敬请期待",
    }

    return result


@router.post("/tts/sing")
async def generate_vocal(
    lyrics: str = ...,
    voice: str = "female",  # female, male
    style: str = "pop",
):
    """生成虚拟人声（TTS）"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    # 使用 TTS API 生成人声
    voice_mapping = {
        "female": "zh-CN-XiaoxiaoNeural",
        "male": "zh-CN-YunxiNeural",
    }

    tts_voice = voice_mapping.get(voice, "zh-CN-XiaoxiaoNeural")

    try:
        # 调用 Agnes TTS API（如果支持）
        response = requests.post(
            f"{AGNES_API_BASE}/audio/speech",
            headers={
                "Authorization": f"Bearer {AGNES_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "tts-1",
                "input": lyrics,
                "voice": tts_voice,
                "speed": 1.0,
            },
            timeout=60,
        )

        if response.status_code == 200:
            filename = f"{generate_music_id()}.mp3"
            save_music(response.content, filename)
            return {
                "audio_id": filename,
                "url": f"/api/music-factory/audios/{filename}",
                "voice": voice,
                "style": style,
                "duration": len(lyrics) / 10,  # 估算时长
            }
        else:
            # TTS API 不可用，返回占位
            return {
                "status": "not_supported",
                "message": "虚拟人声功能需要 TTS API 支持",
                "lyrics": lyrics[:200],
            }

    except Exception as e:
        logger.error(f"生成人声异常: {e}")
        return {
            "status": "error",
            "message": str(e),
        }


@router.get("/audios/{filename}")
async def get_audio(filename: str):
    """获取音频文件"""
    audio_path = MUSIC_DIR / filename
    if not audio_path.exists():
        raise HTTPException(404, "音频不存在")
    
    from fastapi.responses import FileResponse
    return FileResponse(audio_path, media_type="audio/mpeg")


@router.get("/list")
async def list_audios():
    """列出所有音频"""
    audios = []
    for f in sorted(MUSIC_DIR.glob("*"), reverse=True):
        if f.is_file():
            audios.append({
                "filename": f.name,
                "url": f"/api/music-factory/audios/{f.name}",
                "size": f.stat().st_size,
            })
    return {"audios": audios}
