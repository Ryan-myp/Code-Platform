#!/usr/bin/env python3
"""音乐工厂模块 - 歌词生成、音乐生成、虚拟人声"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Callable

import requests
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import FileResponse

from common.artifacts import save_artifact
from common.auth import require_auth
from common.config import load_config
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/music-factory", tags=["音乐工厂"])

# 配置：走 common.config 单一来源
load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY, MODEL_NAME  # noqa: E402

MUSIC_DIR = Path(__file__).parent / "music_factory"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# 示例歌词模板
LYRICS_EXAMPLES = {
    "love": "[Verse 1]\n阳光透过窗帘洒在你脸上\n你笑着问我今天怎么样\n咖啡的香气弥漫在空气\n这一刻时间仿佛静止\n\n[Chorus]\n你是我最美的遇见\n像星光照亮我的夜\n每一秒都想和你在一起\n这份爱永远不会变\n\n[Verse 2]\n手牵着手走在夕阳下\n影子被拉得好长好远\n你说我们的故事才刚开始\n未来还有很多美好要分享",
    "nature": "[Verse 1]\n山峦叠翠云雾缭绕\n溪水潺潺流淌过高桥\n鸟儿在枝头歌唱\n大自然是最美的诗行\n\n[Chorus]\n让我走进你的怀抱\n感受清风和阳光\n每一片叶每一朵花\n都在诉说着生命的魔法",
    "dream": "[Verse 1]\n夜晚的星空如此明亮\n我望着远方静静想\n梦想就像那流星划过\n带着希望飞向远方\n\n[Chorus]\n追逐梦的脚步不停歇\n哪怕前路有多曲折\n心中有光就不怕黑夜\n梦想终会实现的那一刻"
}


def save_music(data: bytes, filename: str) -> str:
    filepath = MUSIC_DIR / filename
    filepath.write_bytes(data)
    return filename


def generate_music_id() -> str:
    return f"music_{int(time.time() * 1000)}"


def _save_artifact(filename: str, project_id: str, art_type: str, content: str,
                   duration: float = 0.0, extra_meta: dict | None = None) -> str:
    """将音乐/歌词产物登记到 artifacts 表（委托 common.artifacts.save_artifact），返回 artifact id。

    - art_type: 'lyrics' 或 'audio'
    - lyrics: content=歌词正文，media_url 指向 /api/music-factory/lyrics/{filename}
    - audio:  media_url 指向 /api/music-factory/audios/{filename}，duration 为估算时长
    - 失败静默
    """
    meta = {"filename": filename, "type": art_type}
    if extra_meta:
        meta.update(extra_meta)
    media_url = (f"/api/music-factory/audios/{filename}" if art_type == "audio"
                 else f"/api/music-factory/lyrics/{filename}")
    return save_artifact(
        art_type=art_type, project_id=project_id, author="music_factory",
        media_url=media_url, content=content, metadata=meta, duration=duration,
    )


@router.get("/stats")
async def get_stats():
    music_count = len(list(MUSIC_DIR.glob("*"))) if MUSIC_DIR.exists() else 0
    return {
        "total_tracks": music_count,
        "api_configured": bool(AGNES_API_KEY),
        "features": ["歌词生成", "音乐生成(待接入)", "虚拟人声(待接入)"],
    }


@router.get("/lyrics/examples")
async def get_lyrics_examples():
    """获取歌词示例"""
    return {"examples": LYRICS_EXAMPLES}


async def _music_lyrics_worker(payload: dict, progress: Callable | None = None) -> dict:
    """生成歌词（同步/异步任务共用执行体，异步时回报进度）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    theme = payload.get("theme") or ""
    style = payload.get("style") or "pop"
    language = payload.get("language") or "zh"
    length = payload.get("length") or "medium"
    mood = payload.get("mood") or "happy"
    project_id = payload.get("project_id") or ""
    if not theme:
        raise HTTPException(400, "请输入歌词主题")

    style_prompts = {
        "pop": "流行歌曲",
        "rock": "摇滚歌曲",
        "rap": "说唱歌曲",
        "ballad": "抒情歌曲",
        "jazz": "爵士乐",
        "classical": "古典音乐",
        "folk": "民谣",
        "electronic": "电子音乐",
    }
    lang_prompts = {"zh": "中文", "en": "英文", "mixed": "中英混合"}
    mood_prompts = {
        "happy": "欢快、积极、充满希望",
        "sad": "忧伤、感伤、怀旧",
        "romantic": "浪漫、甜蜜、温柔",
        "energetic": "激昂、充满活力",
        "calm": "平静、舒缓、治愈",
        "epic": "史诗、壮阔、震撼",
    }
    length_prompts = {
        "short": "30秒到1分钟的短歌曲，包含主歌和副歌",
        "medium": "2到3分钟的完整歌曲，包含主歌、副歌和桥段",
        "long": "3到5分钟的长篇歌曲，包含多个段落和变奏",
    }

    prompt = f"""创作一首{lang_prompts.get(language, '中文')}{style_prompts.get(style, '流行')}的歌词：

主题：{theme}
情感基调：{mood_prompts.get(mood, '欢快')}
风格：{style_prompts.get(style, '流行')}
长度要求：{length_prompts.get(length, '中歌')}

要求：
- 歌词要富有诗意和感染力
- 押韵自然流畅
- 情感表达真挚
- 结构清晰（标注Verse、Chorus、Bridge等）
- 适合演唱

请只输出歌词，不要解释。"""

    _report(15, "AI 正在创作歌词…")
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{AGNES_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "你是一位专业的歌词创作者，擅长创作优美动人的歌词。"},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 2000,
                "temperature": 0.8,
            },
            timeout=90,
        )
        if response.status_code != 200:
            raise HTTPException(500, f"生成歌词失败: {response.text}")
        data = response.json()
        lyrics = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not lyrics:
            raise HTTPException(502, "AI 未返回歌词内容，请重试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成歌词异常: {e}")
        raise HTTPException(500, f"生成歌词失败: {str(e)}") from e

    # 保存生成的歌词
    lyrics_filename = f"{generate_music_id()}.txt"
    lyrics_path = MUSIC_DIR / lyrics_filename
    lyrics_path.write_text(lyrics, encoding="utf-8")
    art_id = _save_artifact(lyrics_filename, project_id, "lyrics", lyrics, 0.0,
                            {"theme": theme, "style": style, "language": language,
                             "length": length, "mood": mood})
    _report(100, "歌词已生成")
    return {
        "lyrics": lyrics,
        "lyrics_file": lyrics_filename,
        "artifact_id": art_id,
        "theme": theme,
        "style": style,
        "language": language,
        "length": length,
        "mood": mood,
        "project_id": project_id,
    }


@router.post("/lyrics/generate")
async def generate_lyrics(
    theme: str = Form(...),
    style: str = Form("pop"),
    language: str = Form("zh"),
    length: str = Form("medium"),
    mood: str = Form("happy"),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """生成歌词（默认异步任务，立即返回 task_id）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {"theme": theme, "style": style, "language": language,
               "length": length, "mood": mood, "project_id": project_id}
    if sync:
        return await _music_lyrics_worker(payload)
    task = create_task("music_lyrics", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"], "status": "pending",
        "message": "歌词生成任务已提交，后台执行中，可在任务中心查看进度", "task": task,
    }


@router.post("/music/generate")
async def generate_music(
    lyrics: str = Form(...),
    style: str = Form("pop"),
    mood: str = Form("happy"),
    duration: int = Form(30),
):
    """生成音乐（占位，待接入 Suno/Udio API）"""
    music_id = generate_music_id()

    result = {
        "music_id": music_id,
        "lyrics": lyrics[:200] + "..." if len(lyrics) > 200 else lyrics,
        "style": style,
        "mood": mood,
        "duration": duration,
        "status": "pending",
        "message": "音乐生成功能正在开发中，敬请期待",
        "note": "当前仅支持歌词生成，音乐生成需要接入第三方API（如Suno、Udio）",
    }

    return result


@router.delete("/delete/{filename}")
async def delete_item(filename: str):
    """删除文件"""
    file_path = MUSIC_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    file_path.unlink()
    return {"success": True}


async def _music_sing_worker(payload: dict, progress: Callable | None = None) -> dict:
    """生成虚拟人声 TTS（同步/异步任务共用执行体，异步时回报进度）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    lyrics = payload.get("lyrics") or ""
    voice = payload.get("voice") or "female"
    style = payload.get("style") or "pop"
    project_id = payload.get("project_id") or ""
    if not (lyrics or "").strip():
        raise HTTPException(400, "请输入歌词文本")

    voice_mapping = {
        "female": "zh-CN-XiaoxiaoNeural",
        "male": "zh-CN-YunxiNeural",
        "child": "zh-CN-XiaomoNeural",
    }
    tts_voice = voice_mapping.get(voice, "zh-CN-XiaoxiaoNeural")

    _report(20, "AI 正在合成人声…")
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{AGNES_API_BASE}/audio/speech",
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json={"model": "tts-1", "input": lyrics[:500], "voice": tts_voice, "speed": 1.0},
            timeout=60,
        )

        if response.status_code == 200:
            filename = f"{generate_music_id()}.mp3"
            save_music(response.content, filename)
            duration = len(lyrics) / 15
            art_id = _save_artifact(filename, project_id, "audio", lyrics[:500], duration,
                                    {"voice": voice, "style": style, "tts_voice": tts_voice})
            _report(100, "人声已生成")
            return {
                "audio_id": filename,
                "artifact_id": art_id,
                "url": f"/api/music-factory/audios/{filename}",
                "voice": voice,
                "style": style,
                "duration": duration,
                "project_id": project_id,
            }
        raise HTTPException(502, "虚拟人声功能需要 TTS API 支持（当前服务商暂未开通）")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成人声异常: {e}")
        raise HTTPException(500, f"生成人声失败: {str(e)}") from e


@router.post("/tts/sing")
async def generate_vocal(
    lyrics: str = Form(...),
    voice: str = Form("female"),
    style: str = Form("pop"),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """生成虚拟人声 TTS（默认异步任务，立即返回 task_id）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {"lyrics": lyrics, "voice": voice, "style": style, "project_id": project_id}
    if sync:
        return await _music_sing_worker(payload)
    task = create_task("music_sing", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"], "status": "pending",
        "message": "人声合成任务已提交，后台执行中，可在任务中心查看进度", "task": task,
    }


async def _music_lyrics_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装歌词生成，回报进度。"""
    return await _music_lyrics_worker(payload, progress=update)


async def _music_sing_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装人声合成，回报进度。"""
    return await _music_sing_worker(payload, progress=update)


register_handler("music_lyrics", _music_lyrics_handler, user_limit=2)
register_handler("music_sing", _music_sing_handler, user_limit=2)


@router.get("/audios/{filename}")
async def get_audio(filename: str):
    audio_path = MUSIC_DIR / filename
    if not audio_path.exists():
        raise HTTPException(404, "音频不存在")
    return FileResponse(audio_path, media_type="audio/mpeg")


@router.get("/list")
async def list_audios():
    """列出所有音频和歌词文件"""
    items = []
    for f in sorted(MUSIC_DIR.glob("*"), reverse=True):
        if f.is_file():
            ext = f.suffix.lower()
            item_type = "audio" if ext in [".mp3", ".wav", ".ogg"] else "lyrics"
            items.append({
                "filename": f.name,
                "url": f"/api/music-factory/audios/{f.name}" if ext in [".mp3", ".wav", ".ogg"] else f"/api/music-factory/lyrics/{f.name}",
                "size": f.stat().st_size,
                "type": item_type,
                "ext": ext,
            })
    return {"items": items, "count": len(items)}


@router.get("/lyrics/{filename}")
async def get_lyrics_file(filename: str):
    """获取歌词文件"""
    lyrics_path = MUSIC_DIR / filename
    if not lyrics_path.exists():
        raise HTTPException(404, "歌词文件不存在")
    content = lyrics_path.read_text(encoding="utf-8")
    return {"filename": filename, "content": content}


@router.delete("/delete/{filename}")
async def delete_item(filename: str):
    """删除文件"""
    file_path = MUSIC_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    file_path.unlink()
    return {"success": True}
