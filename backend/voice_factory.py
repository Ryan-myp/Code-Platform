#!/usr/bin/env python3


from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping, Iterable, Awaitable, Coroutine, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio
from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
"""AI 配音工坊 — 文字转语音（TTS）。

- 调用 Agnes 中转站 OpenAI 兼容 /audio/speech（模型 tts-1，Azure Neural 音色）
- 场景预设（短视频旁白/广告口播/有声书/新闻播报/儿童故事）+ 自由音色/语速
- 长文本自动分段合成（每段 ≤ 900 字），ffmpeg 无损拼接为完整 mp3
- 产物保存到 voice_factory/ 目录并登记 artifacts 表（type=audio）
"""

import asyncio
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
from collections.abc import Callable
from datetime import datetime

import requests
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from common.artifacts import save_artifact
from common.auth import require_auth
from common.config import load_config
from common.llm import _safe_exc_msg
from task_queue import create_task, register_handler

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
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher",
        "gender": "男",
        "style": "英文男声，沉稳有力",
        "emoji": "🇬🇧",
    },
]

# ── CosyVoice 本地引擎通道（独立推理服务 voice_engine，端口 9888，MPS 加速） ──
COSYVOICE_API_BASE = os.environ.get("COSYVOICE_API_BASE", "http://127.0.0.1:9888")
_COSYVOICE_STATE = {"ok": None, "checked_at": 0.0}
_COSYVOICE_CHECK_INTERVAL = 60  # 每 60s 探活一次（引擎进程/模型加载状态）
_COSYVOICE_TIMEOUT = 180  # 长文本合成超时（秒，MPS 推理 RTF≈1-2）

# AI 克隆音色（CosyVoice 本地引擎专用，中文名音色，非 Azure Neural）
COSYVOICE_VOICES = [
    {"id": "中文女", "name": "中文女声", "gender": "女", "style": "AI 克隆音色，自然拟真（本地引擎）", "emoji": "🤖"},
    {"id": "中文男", "name": "中文男声", "gender": "男", "style": "AI 克隆音色，自然拟真（本地引擎）", "emoji": "🤖"},
    {"id": "中文童声", "name": "中文童声", "gender": "童", "style": "AI 克隆音色，活泼童真（本地引擎）", "emoji": "🤖"},
    {"id": "粤语女", "name": "粤语女声", "gender": "女", "style": "AI 克隆音色，粤语流利（本地引擎）", "emoji": "🤖"},
]
VOICES.extend(COSYVOICE_VOICES)
COSYVOICE_VOICE_IDS = {v["id"] for v in COSYVOICE_VOICES}

# 场景预设：一键套用「音色 + 语速」
SCENES = [
    {
        "id": "shortvideo",
        "name": "短视频旁白",
        "desc": "节奏明快，适合口播/知识解说",
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": 1.05,
    },
    {
        "id": "ad",
        "name": "广告口播",
        "desc": "有感染力，适合产品宣传/带货",
        "voice": "zh-CN-YunjianNeural",
        "speed": 1.0,
    },
    {
        "id": "audiobook",
        "name": "有声书",
        "desc": "娓娓道来，适合故事/小说朗读",
        "voice": "zh-CN-XiaoxiaoNeural",
        "speed": 0.95,
    },
    {
        "id": "news",
        "name": "新闻播报",
        "desc": "字正腔圆，适合资讯/播报类",
        "voice": "zh-CN-YunyangNeural",
        "speed": 1.0,
    },
    {
        "id": "story",
        "name": "儿童故事",
        "desc": "活泼童趣，适合亲子/教育内容",
        "voice": "zh-CN-XiaomoNeural",
        "speed": 0.95,
    },
    {"id": "custom", "name": "自定义", "desc": "自由选择音色与语速", "voice": "zh-CN-XiaoxiaoNeural", "speed": 1.0},
]

MAX_SEGMENT_CHARS = 400  # 单段最大字符数（edge-tts 长文本会内部限速，分段更稳）
MAX_TEXT_CHARS = 10000  # 总文本上限

# ── edge-tts 通道健康状态（v13.0：探活防抖，通道挂掉时直接走中转站） ──
_TTS_CHANNEL_STATE = {"edge_ok": True, "checked_at": 0.0}
_TTS_CHECK_INTERVAL = 600  # 每 10 分钟探活一次（合成 1s 测试音）
_TTS_EDGE_TIMEOUT = 30  # edge-tts 子进程超时（秒）
_TTS_RELAY_TIMEOUT = 30  # 中转站 API 超时（秒）


def _tts_health_check(force: bool = False) -> bool:
    """探活 edge-tts 免费通道，返回是否可用。

    - 每 _TTS_CHECK_INTERVAL 秒合成一次 1s 测试音（失败标记通道不可用）
    - force=True 强制探活（供 main.py lifespan 启动预热）
    - 探活结果影响 _tts_one 的通道优先级：edge 挂时直接走中转站，避免反复等待超时
    """
    global _TTS_CHANNEL_STATE
    now = time.time()
    if not force and now - _TTS_CHANNEL_STATE["checked_at"] < _TTS_CHECK_INTERVAL:
        return _TTS_CHANNEL_STATE["edge_ok"]
    _TTS_CHANNEL_STATE["checked_at"] = now
    try:
        _tts_edge("你好", "zh-CN-XiaoxiaoNeural", 1.0)
        _TTS_CHANNEL_STATE["edge_ok"] = True
    except Exception as e:
        _TTS_CHANNEL_STATE["edge_ok"] = False
        logger.warning(f"edge-tts 健康检查失败（标记通道不可用，后续直接走中转站）: {e}")
    return _TTS_CHANNEL_STATE["edge_ok"]


def _split_text(text: str) -> list[str]:
    """按句子边界切分长文本为多段（每段 ≤ MAX_SEGMENT_CHARS）。"""
    text = text.strip()
    if len(text) <= MAX_SEGMENT_CHARS:
        return [text]
    # 优先按句号/问号/感叹号/换行切分（括号/引号保护：不在一对括号中间断句）
    chunks, buf = [], ""
    for part in re.split(r"(?<=[。！？.!?\n])", text):
        if not part:
            continue
        # 缓冲以左括号/引号结尾时，即使超长也等待闭合配对再切，避免拼接处语气断裂
        if len(buf) + len(part) > MAX_SEGMENT_CHARS and buf and buf.rstrip().endswith(tuple("（([《“")):
            buf += part
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


def _cosyvoice_health(force: bool = False) -> bool:
    """探活 CosyVoice 本地引擎（voice_engine 服务），带 60s 防抖。"""
    now = time.time()
    if not force and now - _COSYVOICE_STATE["checked_at"] < _COSYVOICE_CHECK_INTERVAL:
        return _COSYVOICE_STATE["ok"]
    _COSYVOICE_STATE["checked_at"] = now
    try:
        r = requests.get(f"{COSYVOICE_API_BASE}/health", timeout=3)
        ok = r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        ok = False
    _COSYVOICE_STATE["ok"] = ok
    return ok


def _tts_cosyvoice(text: str, voice: str, speed: float) -> bytes:
    """CosyVoice 本地引擎合成（返回 wav 字节）。"""
    resp = requests.post(
        f"{COSYVOICE_API_BASE}/tts/sft",
        data={"text": text, "spk_id": voice, "speed": speed},
        timeout=_COSYVOICE_TIMEOUT,
    )
    if resp.status_code == 200:
        return resp.content
    raise RuntimeError(f"CosyVoice 引擎返回 {resp.status_code}: {resp.text[:200]}")


def _tts_one(text: str, voice: str, speed: float, pitch: int = 0, emotion: str = "") -> bytes:  # noqa: C901 — 多通道降级逻辑，复杂度可控
    """单段 TTS 合成，返回 mp3/wav 字节。

    AI 克隆音色（中文名）优先走 CosyVoice 本地引擎（高质量自然音色，不依赖外网）；
    Azure Neural 音色走 edge-tts（子进程隔离，超时 45s 自动 kill，绝不阻塞主进程），
    子进程偶发崩溃/空输出时带间隔重试，仍失败回退中转站 /audio/speech（需开通 tts-1 渠道）；
    中转站也不可用时再回试 edge-tts（免费通道网络抖动可能已自愈）。
    pitch 为音调百分比（-20~+20）。
    emotion 为 Azure 情绪风格名（v13.24：happy/sad/angry/gentle/serious 等），
    空串=无风格；CosyVoice 通道不支持风格时忽略该参数。
    """

    if voice in COSYVOICE_VOICE_IDS:
        # CosyVoice 音色专属通道：引擎不可用时明确报错（音色名非 Azure 格式，不能静默换通道）
        if _cosyvoice_health():
            try:
                return _tts_cosyvoice(text, voice, speed)
            except Exception as e:
                logger.warning(f"CosyVoice 合成失败: {e}")
        else:
            logger.warning("CosyVoice 引擎不可用（voice_engine 服务未启动）")
        raise HTTPException(500, "请先启动语音引擎服务")

    def _edge_with_retry(rounds: int = 2) -> bytes:
        """带 1s 间隔的 edge-tts 重试；全部失败抛最后一个异常。

        情绪风格（SSML express-as）失败时降级为无风格再试：部分音色不支持风格，
        重复同风格无意义；无风格通道更稳定。
        """
        last = None
        for attempt in range(rounds):
            try:
                return _tts_edge(text, voice, speed, pitch, emotion)
            except Exception as e:
                last = e
                logger.warning(f"edge-tts 失败: {e}")
                if attempt < rounds - 1:
                    time.sleep(1)  # 网络抖动短暂等待后可自愈
        if emotion:
            logger.warning(f"edge-tts 情绪风格({emotion})失败，降级无风格重试: {last}")
            for attempt in range(2):
                try:
                    return _tts_edge(text, voice, speed, pitch, "")
                except Exception as e:
                    last = e
                    if attempt < 1:
                        time.sleep(1)
        raise last

    try:
        if _tts_health_check():
            return _edge_with_retry(3)
        logger.warning("edge-tts 健康检查不通过，直接走中转站通道")
    except Exception:
        logger.warning("edge-tts 全部失败，回退中转站 API")
    if not AGNES_API_KEY:
        raise HTTPException(500, "TTS 通道不可用（edge-tts 与中转站均失败），请稍后重试")
    try:
        resp = requests.post(
            f"{AGNES_API_BASE}/audio/speech",
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json={"model": "tts-1", "input": text, "voice": voice, "speed": speed},
            timeout=_TTS_RELAY_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.content
        raise HTTPException(500, "TTS 调用失败，请稍后重试")
    except Exception:
        # 中转站不可用：免费通道可能已恢复，最后再回试一次
        logger.warning("中转站 TTS 失败，回试 edge-tts")
        try:
            return _edge_with_retry(2)
        except Exception as e:
            raise HTTPException(500, "操作失败，请稍后重试")


def _tts_edge(text: str, voice: str, speed: float, pitch: int = 0, emotion: str = "") -> bytes:
    """edge-tts 合成（Azure Neural 音色，免费通道，子进程隔离）。

    v13.28 情绪改音调表达：SSML express-as 实测强制 ~0.6 字/s 极慢语速（rate/prosody
    均无法修正），全局将 emotion 映射为 pitch 叠加（happy 高亢 / sad 低沉 / angry 激昂 /
    gentle 柔和），语速恢复正常，情绪通过音调区分。
    """
    import subprocess
    import sys

    if emotion:
        # cheerful 为 happy 的 Azure 风格别名（数字人/短剧调用方映射），一并映射高亢
        pitch = pitch + {"happy": 15, "cheerful": 15, "sad": -15, "angry": 12, "gentle": -5, "serious": 0}.get(emotion, 0)
        emotion = ""  # v13.28 不再使用 SSML style（语速黑洞）
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edge_tts_worker.py")
    rate = f"{int(round((speed - 1) * 100)):+d}%"
    fd, tmp = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        args = [sys.executable, worker, text, voice, rate, tmp]
        if pitch:
            args.append(f"{pitch:+d}Hz")
        else:
            args.append("")
        args.append("")
        if emotion:
            args.append(emotion)
        # stdin=DEVNULL：nohup 后台环境下父进程 fd 0 可能无效，子进程继承后
        # Python 3.13 初始化标准流崩溃（Fatal Python error: init_sys_streams）
        result = subprocess.run(args, capture_output=True, stdin=subprocess.DEVNULL, timeout=_TTS_EDGE_TIMEOUT)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode(errors="replace")[:200] or f"exit {result.returncode}")
        with open(tmp, "rb") as f:
            content = f.read()
        if not content:
            # edge-tts 偶发静默失败：进程正常退出但产出 0 字节文件，必须拦截，
            # 否则下游拿到空音频（ffmpeg 合成必然报错）
            raise RuntimeError("edge-tts 返回空音频（0 字节）")
        return content
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
            capture_output=True,
            stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
            timeout=120,
        )
    finally:
        os.unlink(list_file)


def _master_audio(in_path: str, out_path: str, fmt: str = "mp3") -> None:
    """商用级母带处理：响度标准化（-14 LUFS，短视频平台标准）+ 淡入淡出。

    - loudnorm 单遍动态模式统一整体响度，消除分段拼接处响度落差
    - 时长 ≥0.6s 时加 150ms 淡入 + 300ms 淡出，避免首尾爆音
    - fmt=mp3 输出 256kbps/44.1kHz 高音质；fmt=wav 输出 PCM 16bit 无损
    """
    duration = _audio_duration(in_path)
    af = "loudnorm=I=-14:TP=-1.5:LRA=11"
    if duration and duration > 0.6:
        fade_out_start = max(0.0, duration - 0.3)
        af += f",afade=t=in:st=0:d=0.15,afade=t=out:st={fade_out_start:.2f}:d=0.3"
    cmd = ["ffmpeg", "-y", "-i", in_path, "-af", af]
    if fmt == "wav":
        cmd += ["-codec:a", "pcm_s16le", "-ar", "44100", out_path]
    else:
        cmd += ["-codec:a", "libmp3lame", "-b:a", "256k", "-ar", "44100", out_path]
    subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=180, check=True)


def _make_srt(segs: list[str], durations: list[float], out_path: str) -> None:
    """生成标准 SRT 字幕：按分段文本与真实时长累计时间戳（商用配音包必备）。"""

    def ts(sec: float) -> str:
        sec = max(0.0, sec)
        h, rem = int(sec // 3600), sec % 3600
        m, s = int(rem // 60), rem % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"

    lines, cursor = [], 0.0
    for i, (seg_text, dur) in enumerate(zip(segs, durations, strict=False), 1):
        start, cursor = cursor, cursor + max(dur, 0.5)
        lines.append(f"{i}\n{ts(start)} --> {ts(cursor)}\n{seg_text.strip()}\n")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ffprobe 结果缓存（path → (mtime, duration)）：列表接口每个文件一次子进程开销大，
# 文件未变更时直接命中缓存
_duration_cache: dict[str, tuple[float, float]] = {}


def _audio_duration(path: str) -> float:
    """ffprobe 读取音频真实时长（秒），带 mtime 缓存。"""
    try:
        mtime = os.path.getmtime(path)
        cached = _duration_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True,
            stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
            text=True,
            timeout=30,
        )
        dur = round(float(out.stdout.strip()), 1)
        _duration_cache[path] = (mtime, dur)
        return dur
    except Exception:
        return 0.0


def _save_artifact(filename: str, text: str, extra: dict) -> str:
    """登记 artifacts 表（type=audio，委托 common.artifacts.save_artifact），失败静默。"""
    return save_artifact(
        art_type="audio",
        author="voice_factory",
        media_url=f"/api/voice/audios/{filename}",
        content=text[:500],
        metadata=extra,
        duration=0.0,
    )


def _artifact_meta() -> dict:
    """读取 artifacts 表中配音产物的元数据（filename → {text, scene, voice, speed, segments}）。"""
    meta: dict = {}
    try:
        from common.db import get_db

        conn = get_db()
        rows = conn.execute(
            "SELECT content, media_url, metadata FROM artifacts "
            "WHERE type='audio' AND author='voice_factory' AND active=1"
        ).fetchall()
        conn.close()
        for r in rows:
            fname = (r["media_url"] or "").rsplit("/", 1)[-1]
            if not fname:
                continue
            md = {}
            try:
                md = json.loads(r["metadata"] or "{}")
            except Exception:
                pass
            meta[fname] = {
                "text": r["content"] or "",
                "scene": md.get("scene", ""),
                "voice": md.get("voice", ""),
                "speed": md.get("speed", 1.0),
                "pitch": md.get("pitch", 0),
                "format": md.get("format", "mp3"),
                "segments": md.get("segments", 1),
                "title": md.get("title", ""),
            }
    except Exception as e:
        logger.debug(f"_artifact_meta skipped: {e}")
    return meta


async def _voice_generate_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """文字转语音全流程（同步/异步任务共用执行体，异步时回报进度）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY（系统配置-模型配置中设置）")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    text = (payload.get("text") or "").strip()
    scene = payload.get("scene") or "shortvideo"
    voice = payload.get("voice") or ""
    speed = float(payload.get("speed") or 1.0)
    pitch = int(payload.get("pitch") or 0)
    format = payload.get("format") or "mp3"
    emotion = payload.get("emotion") or ""
    # v23 配音场景模板热度：按模板生成时记录（失败静默）
    tpl_id = (payload.get("template_id") or "").strip()
    if tpl_id:
        try:
            from voice_templates import record_usage
            record_usage(tpl_id)
        except Exception:  # noqa: BLE001
            pass
    if not text:
        raise HTTPException(400, "请输入要配音的文本")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(400, "操作失败，请稍后重试")
    if format not in ("mp3", "wav"):
        raise HTTPException(400, "format 仅支持 mp3 / wav")
    pitch = max(-20, min(20, pitch))
    scene_cfg = next((s for s in SCENES if s["id"] == scene), None)
    if scene and scene != "custom" and not scene_cfg:
        raise HTTPException(400, "操作失败，请稍后重试")
    tts_voice = voice or (scene_cfg["voice"] if scene_cfg else "zh-CN-XiaoxiaoNeural")
    tts_speed = speed if scene == "custom" else (scene_cfg["speed"] if scene_cfg else speed)
    tts_speed = max(0.5, min(2.0, float(tts_speed)))

    start = time.time()
    segments = _split_text(text)
    if not segments:
        raise HTTPException(400, "文本为空")

    try:
        tmp_dir = tempfile.mkdtemp(prefix="voice_seg_")
        seg_files, seg_durations = [], []
        for i, seg in enumerate(segments):
            _report(10 + int(i * 70 / len(segments)), f"正在合成第 {i + 1}/{len(segments)} 段…")
            data = await asyncio.to_thread(_tts_one, seg, tts_voice, tts_speed, pitch, emotion)
            seg_path = os.path.join(tmp_dir, f"seg_{i}.mp3")
            with open(seg_path, "wb") as f:
                f.write(data)
            seg_files.append(seg_path)
            seg_durations.append(_audio_duration(seg_path))

        # 拼接 → 母带处理（响度标准化 + 淡入淡出）→ 输出产物
        _report(85, "正在拼接与母带处理…")
        stem = f"voice_{int(time.time() * 1000)}"
        raw_path = os.path.join(tmp_dir, "merged.mp3")
        if len(seg_files) == 1:
            shutil.copyfile(seg_files[0], raw_path)
        else:
            _merge_mp3(seg_files, raw_path)
        filename = f"{stem}.{'wav' if format == 'wav' else 'mp3'}"
        out_path = os.path.join(VOICE_DIR, filename)
        _master_audio(raw_path, out_path, format)
        duration = _audio_duration(out_path) or round(len(text) / 4.5, 1)
        # 字幕：分段文本 + 分段真实时长，时间戳与最终音频对齐
        srt_path = os.path.join(VOICE_DIR, f"{stem}.srt")
        _make_srt(segments, seg_durations, srt_path)
        has_srt = os.path.exists(srt_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS 生成失败: {e}")
        raise HTTPException(500, "操作失败，请稍后重试") from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    art_id = _save_artifact(
        filename,
        text,
        {
            "voice": tts_voice,
            "scene": scene,
            "speed": tts_speed,
            "pitch": pitch,
            "format": format,
            "has_srt": has_srt,
            "segments": len(segments),
        },
    )
    elapsed = round(time.time() - start, 2)
    from common.llm import log_usage

    log_usage("voice_generate", len(text), 0, elapsed)
    _report(100, "配音已生成")
    return {
        "id": filename,
        "artifact_id": art_id,
        "url": f"/api/voice/audios/{filename}",
        "voice": tts_voice,
        "scene": scene,
        "speed": tts_speed,
        "pitch": pitch,
        "format": format,
        "has_srt": has_srt,
        "duration": duration,
        "segments": len(segments),
        "text": text[:200],
    }


@router.post("/generate")
async def generate_voice(
    text: str = Form(...),
    scene: str = Form("shortvideo"),
    voice: str = Form(""),
    speed: float = Form(1.0),
    pitch: int = Form(0),
    format: str = Form("mp3"),
    emotion: str = Form("", description="情绪风格（happy/sad/angry/gentle/serious，空=无）"),
    template_id: str = Form("", description="配音场景模板 ID（voice-templates，如 vt_ecom_sell）"),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """文字转语音（默认异步任务，立即返回 task_id）。

    - 场景预设或自由音色，长文本自动分段 + 商用级母带处理
    - 母带：响度标准化 -14 LUFS + 淡入淡出（短视频/自媒体平台标准）
    - 自动生成同名字幕 .srt（分段时间戳对齐，批量下载随包附送）
    - format: mp3（256k 高音质，默认）/ wav（PCM 无损）
    - pitch: -20 ~ +20 音调百分比（0 为原声，正为明亮/负为低沉）
    """
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY（系统配置-模型配置中设置）")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "text": text,
        "scene": scene,
        "voice": voice,
        "speed": speed,
        "pitch": pitch,
        "format": format,
        "emotion": emotion,
        "template_id": template_id,
        "project_id": project_id,
    }
    if sync:
        return await _voice_generate_worker(payload)
    task = create_task("voice_generate", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "配音任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


@router.get("/audios/{filename}")
async def get_audio(filename: str):
    path = os.path.join(VOICE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "配音不存在")
    media = "audio/wav" if filename.endswith(".wav") else "audio/mpeg"
    return FileResponse(path, media_type=media)


@router.post("/preview")
async def preview_voice(voice: str = Form(...), text: str = Form("")):
    """音色试听：合成短示例片段（≤80 字），快速对比不同音色的商用效果。"""
    if voice not in {v["id"] for v in VOICES}:
        raise HTTPException(400, "操作失败，请稍后重试")
    sample = (text or "").strip()[:80]
    if not sample:
        sample = "你好，这是智能语音试听，可以用来挑选喜欢的音色。"
    data = await asyncio.to_thread(_tts_one, sample, voice, 1.0, 0)
    return Response(content=data, media_type="audio/mpeg")


@router.get("/list")
async def list_voices(
    q: str = "",
    scene: str = "",
    voice: str = "",
    sort: str = "newest",
    current_user: dict = require_auth(),
):
    """配音列表：从 artifacts 合并文本/场景/音色元数据，支持搜索与筛选。

    - q: 按文件名或文本内容搜索
    - scene: 场景 ID 筛选（shortvideo/ad/news/…）
    - voice: 音色 ID 筛选（zh-CN-XiaoxiaoNeural/…）
    - sort: newest / oldest / duration
    """
    meta = _artifact_meta()
    items = []
    if os.path.exists(VOICE_DIR):
        files = [f for f in sorted(os.listdir(VOICE_DIR), reverse=True) if f.endswith((".mp3", ".wav"))]
        # 时长探测（ffprobe 子进程）在独立线程并发执行，避免逐文件阻塞事件循环；
        # mtime 缓存保证二次访问零子进程开销
        durations = await asyncio.gather(
            *(asyncio.to_thread(_audio_duration, os.path.join(VOICE_DIR, f)) for f in files)
        )
        for f, duration in zip(files, durations, strict=False):
            filepath = os.path.join(VOICE_DIR, f)
            stat = os.stat(filepath)
            m = meta.get(f, {})
            scene_cfg = next((s for s in SCENES if s["id"] == m.get("scene")), None)
            voice_cfg = next((v for v in VOICES if v["id"] == m.get("voice")), None)
            text = m.get("text", "")
            item = {
                "id": f,
                "url": f"/api/voice/audios/{f}",
                "size": stat.st_size,
                "duration": duration,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "title": m.get("title") or (text[:30] + ("…" if len(text) > 30 else "")) or f,
                "text": text,
                "scene": m.get("scene", ""),
                "scene_label": scene_cfg["name"] if scene_cfg else "",
                "voice": m.get("voice", ""),
                "voice_name": voice_cfg["name"] if voice_cfg else "",
                "speed": m.get("speed", 1.0),
                "pitch": m.get("pitch", 0),
                "format": m.get("format", "mp3"),
                "has_srt": os.path.exists(os.path.join(VOICE_DIR, f"{os.path.splitext(f)[0]}.srt")),
                "segments": m.get("segments", 1),
            }
            items.append(item)

    # 搜索与筛选
    q_lower = (q or "").strip().lower()
    if q_lower:
        items = [i for i in items if q_lower in i["id"].lower() or q_lower in (i["text"] or "").lower()]
    if scene:
        items = [i for i in items if i["scene"] == scene]
    if voice:
        items = [i for i in items if i["voice"] == voice]
    if sort == "oldest":
        items.reverse()
    elif sort == "duration":
        items.sort(key=lambda x: x["duration"], reverse=True)
    return items


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80, description="新标题")


@router.put("/{filename}/rename")
async def rename_voice(filename: str, req: RenameRequest, current_user: dict = require_auth()):
    """重命名配音：标题写入 artifacts.metadata.title。"""
    path = os.path.join(VOICE_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "配音不存在")
    try:
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT metadata FROM artifacts WHERE media_url=? AND active=1",
            (f"/api/voice/audios/{filename}",),
        ).fetchone()
        if row:
            md = {}
            try:
                md = json.loads(row["metadata"] or "{}")
            except Exception:
                pass
            md["title"] = req.title.strip()
            conn.execute(
                "UPDATE artifacts SET metadata=? WHERE media_url=? AND active=1",
                (json.dumps(md, ensure_ascii=False), f"/api/voice/audios/{filename}"),
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"rename_voice db skipped: {e}")
    return {"success": True, "title": req.title.strip()}


@router.post("/batch-download")
async def batch_download_voices(ids: list[str] = Form(...), current_user: dict = require_auth()):
    """批量下载多个配音为 ZIP 包。"""
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ids:
            path = os.path.join(VOICE_DIR, fname)
            if os.path.exists(path) and fname.endswith((".mp3", ".wav")):
                zf.write(path, fname)
                # 商用配音包标准：同名字幕随包附送
                stem = os.path.splitext(fname)[0]
                srt_path = os.path.join(VOICE_DIR, f"{stem}.srt")
                if os.path.exists(srt_path):
                    zf.write(srt_path, f"{stem}.srt")
                count += 1
    if count == 0:
        raise HTTPException(400, "没有可下载的文件")
    data = buf.getvalue()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="voices_{int(time.time())}.zip"'},
    )


@router.get("/stats")
async def voice_stats(current_user: dict = require_auth()):
    """配音工坊统计：总数 / 总时长 / 场景分布 / 音色分布。"""
    items = await list_voices(current_user=current_user)
    total = len(items)
    total_duration = round(sum(i["duration"] for i in items), 1)
    total_size = sum(i["size"] for i in items)
    scene_dist = {}
    voice_dist = {}
    for i in items:
        s = i["scene_label"] or "未标记"
        scene_dist[s] = scene_dist.get(s, 0) + 1
        v = i["voice_name"] or "未知"
        voice_dist[v] = voice_dist.get(v, 0) + 1
    return {
        "total": total,
        "total_duration": total_duration,
        "total_size": total_size,
        "scene_dist": scene_dist,
        "voice_dist": voice_dist,
    }


@router.delete("/{filename}")
async def delete_voice(filename: str, current_user: dict = require_auth()):
    path = os.path.join(VOICE_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    # 同步删除同名字幕文件
    srt_path = os.path.join(VOICE_DIR, f"{os.path.splitext(filename)[0]}.srt")
    if os.path.exists(srt_path):
        os.remove(srt_path)
    # 同步注销 artifacts 记录（软删，保留历史计数口径）
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            "UPDATE artifacts SET active=0 WHERE media_url=? AND type='audio'",
            (f"/api/voice/audios/{filename}",),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"delete_voice artifact skipped: {e}")
    return {"success": True}


async def _voice_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装配音生成全流程，回报进度。"""
    return await _voice_generate_worker(payload, progress=update)


register_handler("voice_generate", _voice_generate_handler, user_limit=2, max_attempts=2)
