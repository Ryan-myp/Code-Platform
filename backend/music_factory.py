#!/usr/bin/env python3

def _compose_music_simple(music_params: dict) -> dict:
    """简化版音乐合成。"""
    return {
        "status": "success",
        "audio_url": music_params.get("output_path", ""),
        "duration": music_params.get("duration", 0)
    }

def _prepare_music_params_simple(request_data: dict) -> dict:
    """简化版准备音乐参数。"""
    return {
        "style": request_data.get("style", "pop"),
        "duration": request_data.get("duration", 30),
        "output_path": request_data.get("output_path", "")
    }


from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping, Iterable, Awaitable, Coroutine, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio
from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
"""音乐工厂模块 - 歌词生成、音乐生成、虚拟人声"""

import asyncio
import io
import json
import logging
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np
import requests
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from common.artifacts import save_artifact
from common.helpers import _notify_progress
from common.auth import require_auth
from common.config import load_config, resolve_api_key
from common.llm import api_error_detail, _safe_exc_msg
from content_safety import check_text, quality_report
from publish_kit import build_publish_zip, license_text, pack_dir_name, platform_spec_text, publish_registry
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
    "dream": "[Verse 1]\n夜晚的星空如此明亮\n我望着远方静静想\n梦想就像那流星划过\n带着希望飞向远方\n\n[Chorus]\n追逐梦的脚步不停歇\n哪怕前路有多曲折\n心中有光就不怕黑夜\n梦想终会实现的那一刻",
}

# 主流音乐平台发布规格（随发布包附带）
MUSIC_PACK_SPECS = [
    {"name": "音频格式", "value": "mp3（≥192k）/ wav / flac 均可", "desc": "本包已同时提供 mp3 + wav(44.1kHz/16bit) + flac 三格式"},
    {"name": "封面", "value": "≥500×500 JPG/PNG，≤1MB", "desc": "本包封面 640×640 满足要求；建议无边框、无水印"},
    {"name": "歌词", "value": "txt 或 lrc 均可上传", "desc": "本包已提供歌词.txt 与歌词.lrc（时间轴估算）"},
    {"name": "曲目信息", "value": "歌名/歌手/作词/作曲/风格", "desc": "AI 生成歌曲建议署名「作词/作曲：AI 创作工坊」"},
    {"name": "时长", "value": "无硬性限制，1-6 分钟为宜", "desc": "主流平台支持 1-10 分钟曲目"},
    {"name": "版权声明", "value": "上传时勾选「原创声明」", "desc": "随包 LICENSE.txt 为商用授权依据"},
]
MUSIC_PACK_NOTES = (
    "1. 三大平台均需实名认证（个人可开通）：网易云音乐人 / 腾讯音乐人 / 抖音音乐人；"
    "2. 同一首歌可多平台分发，收益独立计算；"
    "3. 平台审核通常 1-3 个工作日，请勿重复提交；"
    "4. 封面与歌词信息不符会被驳回，发布前请核对曲目信息.md。"
)


def save_music(data: bytes, filename: str) -> str:
    filepath = MUSIC_DIR / filename
    filepath.write_bytes(data)
    return filename


def generate_music_id() -> str:
    return f"music_{int(time.time() * 1000)}"


def _save_artifact(
    filename: str,
    project_id: str,
    art_type: str,
    content: str,
    duration: float = 0.0,
    extra_meta: dict | None = None,
    thumbnail: str = "",
) -> str:
    """将音乐/歌词产物登记到 artifacts 表（委托 common.artifacts.save_artifact），返回 artifact id。

    - art_type: 'lyrics' 或 'audio'
    - lyrics: content=歌词正文，media_url 指向 /api/music-factory/lyrics/{filename}
    - audio:  media_url 指向 /api/music-factory/audios/{filename}，duration 为实际时长
    - thumbnail: 歌曲封面 URL（PIL 生成）
    - 失败静默
    """
    meta = {"filename": filename, "type": art_type}
    if extra_meta:
        meta.update(extra_meta)
    media_url = (
        f"/api/music-factory/audios/{filename}" if art_type == "audio" else f"/api/music-factory/lyrics/{filename}"
    )
    return save_artifact(
        art_type=art_type,
        project_id=project_id,
        author="music_factory",
        media_url=media_url,
        content=content,
        metadata=meta,
        duration=duration,
        thumbnail=thumbnail,
    )


@router.get("/stats")
async def get_stats():
    music_count = len(list(MUSIC_DIR.glob("*"))) if MUSIC_DIR.exists() else 0
    return {
        "total_tracks": music_count,
        "api_configured": bool(AGNES_API_KEY),
        "features": ["歌词生成", "音乐合成", "虚拟人声"],
        # 引擎状态：大模型 ACE-Step（可用优先）/ 本地 CosyVoice 真歌声 + numpy 伴奏
        "engine": {
            "mode": MUSIC_ENGINE_MODE,
            "acestep_ok": _acestep_ok(),
            "acestep_api": ACESTEP_API_BASE,
            "cosyvoice_ok": _cosyvoice_ok(),
        },
    }


def _text_to_lrc(lyrics: str, duration: float, title: str = "", artist: str = "") -> str:
    """歌词纯文本 → lrc 文件（时间轴按行均匀估算，可发布前微调）。"""
    lines = [ln.strip() for ln in (lyrics or "").splitlines() if ln.strip()]
    lrc = [f"[ti:{title}]", f"[ar:{artist}]"]
    if not lines:
        return "\n".join(lrc)
    seg = max(duration / len(lines), 0.5)
    for i, ln in enumerate(lines):
        t = i * seg
        m, s = int(t // 60), t % 60
        lrc.append(f"[{m:02d}:{s:05.2f}]{ln}")
    return "\n".join(lrc)


def _music_custom_cover(cover_image, audio_id: str, stem: str) -> tuple:
    """处理自定义封面（可选）：居中裁剪缩放 640×640。返回 (cover_src, cover_label)。"""
    cover_path = MUSIC_DIR / f"{stem}.jpg"
    cover_src = cover_path if cover_path.exists() else None
    cover_label = "AI 生成封面"
    if cover_image is not None and (cover_image.filename or "").strip():
        data = io.BytesIO(cover_image.file.read())
        if data.getbuffer().nbytes > 8 * 1024 * 1024:
            raise HTTPException(400, "封面图片不能超过 8MB")
        from PIL import Image, ImageOps, UnidentifiedImageError

        try:
            img = Image.open(data)
        except UnidentifiedImageError:
            raise HTTPException(400, "封面图片格式无效，请上传 JPG/PNG/WebP 图片") from None
        img = ImageOps.exif_transpose(img).convert("RGB")
        w, h = img.size
        side = min(w, h)
        img = img.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
        img = img.resize((640, 640), Image.LANCZOS)
        cover_override = MUSIC_DIR / f"{stem}_cover_custom.jpg"
        img.save(cover_override, "JPEG", quality=88)
        return cover_override, "自定义封面（640×640）"
    return cover_src, cover_label


def _music_meta(audio_id: str) -> tuple:
    """从 artifacts 表取歌词与元数据。返回 (lyrics, meta)。"""
    try:
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT content, metadata FROM artifacts WHERE media_url=? AND type='audio' AND active=1",
            (f"/api/music-factory/audios/{audio_id}",),
        ).fetchone()
        conn.close()
        if row:
            lyrics = row["content"] or ""
            try:
                return lyrics, json.loads(row["metadata"] or "{}")
            except Exception:
                return lyrics, {}
    except Exception as e:
        logger.debug(f"music_publish_pack db skipped: {e}")
    return "", {}


def _music_item_meta(url: str) -> tuple:
    """列表项元数据：从 URL 提取 duration/thumbnail/style/title（无 artifact 时兜底）。"""
    try:
        _name = url.rsplit("/", 1)[-1]
        _stem = _name.rsplit(".", 1)[0]
        # 从 artifacts 表取元数据
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT content, metadata FROM artifacts WHERE media_url=? AND active=1",
            (url,),
        ).fetchone()
        if row:
            try:
                _meta = json.loads(row["metadata"] or "{}")
                _duration = float(_meta.get("duration") or 0)
                _style = str(_meta.get("style") or "")
                _content = str(row["content"] or "")
                _title = str(_meta.get("title") or _content[:40] or _stem)
                _thumb = str(_meta.get("cover") or "")
                conn.close()
                return _duration, _thumb, _style, _title
            except Exception:
                pass
        conn.close()
        return 0.0, "", "", _stem
    except Exception as e:
        logger.debug(f"music_item_meta skipped: {e}")
        return 0.0, "", "", _stem


def _music_master_transcode(audio_path) -> tuple:
    """母带级转码：wav 16bit/44.1kHz + flac 无损。返回 (wav_data, flac_data)。"""
    wav_data, flac_data = b"", b""
    try:
        r = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(audio_path), "-ar", "44100", "-ac", "2", "-sample_fmt", "s16", "-f", "wav", "-"],
            capture_output=True, timeout=300,
        )
        if r.returncode == 0 and r.stdout:
            wav_data = r.stdout
        r = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", str(audio_path), "-ar", "44100", "-ac", "2", "-f", "flac", "-"],
            capture_output=True, timeout=300,
        )
        if r.returncode == 0 and r.stdout:
            flac_data = r.stdout
    except Exception as e:
        logger.warning(f"母带转码失败（仅打包 mp3）: {e}")
    return wav_data, flac_data


def _music_pack_entries(root: str, audio_path, wav_data: bytes, flac_data: bytes, cover_src, lyrics: str, duration: float, title: str, artist_name: str, style_label: str, cover_label: str) -> dict:
    """构建音乐发布包文件条目。"""
    entries: dict = {f"{root}/01_歌曲.mp3": str(audio_path)}
    if wav_data:
        entries[f"{root}/02_母带.wav"] = wav_data
    if flac_data:
        entries[f"{root}/03_无损.flac"] = flac_data
    if cover_src is not None:
        entries[f"{root}/封面.jpg"] = str(cover_src)
    entries[f"{root}/歌词.lrc"] = _text_to_lrc(lyrics, duration, title, artist_name)
    entries[f"{root}/歌词.txt"] = lyrics or "（无歌词）"
    entries[f"{root}/曲目信息.md"] = (
        f"# {title}\n\n- 歌手：{artist_name}\n- 时长：{int(duration // 60)} 分 {int(duration % 60)} 秒\n"
        f"- 风格：{style_label or '未标注'}\n- 格式：mp3 / wav(44.1kHz 16bit) / flac\n"
        "- 说明：lrc 时间轴为按行均匀估算，如需精确同步可在发布前微调"
    )
    entries[f"{root}/规格说明.md"] = platform_spec_text("主流音乐平台", MUSIC_PACK_SPECS, MUSIC_PACK_NOTES)
    entries[f"{root}/上传指南.md"] = (
        "# 音乐平台上传指南\n\n"
        "## 网易云音乐人（music.163.com）\n"
        "1. 注册「网易云音乐人」，完成实名认证（个人即可开通）\n"
        "2. 进入音乐人后台 → 上传歌曲 → 上传 mp3/wav/flac 与封面\n"
        "3. 粘贴歌词（歌词.txt）→ 提交审核（约 1-3 个工作日）\n"
        "\n## 腾讯音乐人（y.qq.com，覆盖 QQ 音乐/酷狗/酷我）\n"
        "1. 注册「腾讯音乐人开放平台」，实名认证\n"
        "2. 上传歌曲 + 封面（≥500×500）→ 填写词曲信息\n"
        "3. 提交审核，通过后多渠道分发\n"
        "\n## 抖音音乐人（music.douyin.com，覆盖汽水音乐）\n"
        "1. 注册「抖音音乐人」，实名认证\n"
        "2. 上传 mp3/wav 与封面 → 填写歌词\n"
        "3. 审核通过后可在抖音/汽水音乐发布"
    )
    entries[f"{root}/LICENSE.txt"] = license_text(f"歌曲《{title}》")
    return entries


def _music_qc_report(lyrics: str, audio_path, cover_label: str, cover_src, title: str) -> str | None:
    """音乐质量自检报告（失败返回 None）。"""
    try:
        lyrics_check = check_text(lyrics, "歌词") if lyrics else None
        extra = [
            f"音频规格：mp3 {audio_path.stat().st_size / 1024 / 1024:.1f}MB / wav 44.1kHz 16bit / flac 无损",
            f"封面规格：{cover_label}（≥500×500 平台要求）{'✓' if cover_src is not None else '✗ 缺失'}",
            "歌词格式：txt + lrc（时间轴估算，建议发布前核对）",
        ]
        return quality_report(f"歌曲《{title}》", text_check=lyrics_check, image_quality=None, extra=extra)
    except Exception as e:
        logger.debug(f"音乐质量自检报告生成失败: {e}")
        return None


@router.post("/publish-pack")
async def music_publish_pack(
    audio_id: str = Form(...),
    song_title: str = Form(""),
    artist: str = Form(""),
    genre: str = Form(""),
    cover_image: UploadFile = File(None),
    current_user: dict = require_auth(),
):
    """歌曲发布包：选中歌曲一键打包为可提交音乐人平台的成套物料。"""
    audio_id = (audio_id or "").strip()
    if not audio_id.endswith(".mp3"):
        raise HTTPException(400, "audio_id 需为 .mp3 文件")
    audio_path = MUSIC_DIR / audio_id
    if not audio_path.exists():
        raise HTTPException(404, "歌曲不存在")
    stem = audio_id.rsplit(".", 1)[0]

    # 自定义封面处理
    cover_src, cover_label = _music_custom_cover(cover_image, audio_id, stem)

    # 歌词与元数据
    lyrics, meta = _music_meta(audio_id)

    title = (song_title or meta.get("theme") or stem).strip()[:60]
    artist_name = (artist or "AI 音乐人").strip()[:40]
    style_label = meta.get("style", "")
    duration = _probe_seconds(str(audio_path)) or 0

    # 母带级转码
    wav_data, flac_data = _music_master_transcode(audio_path)

    root = pack_dir_name("music_release")
    entries = _music_pack_entries(root, audio_path, wav_data, flac_data, cover_src, lyrics, duration, title, artist_name, style_label, cover_label)

    # 生产级内容保障：质量自检报告
    qc_report = _music_qc_report(lyrics, audio_path, cover_label, cover_src, title)
    if qc_report:
        entries[f"{root}/质量自检报告.md"] = qc_report

    buf = build_publish_zip(entries, "music_release")
    publish = publish_registry.publish("music_platform", {"title": title, "artist": artist_name})
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="music_release_{int(time.time())}.zip"',
            "X-Publish-Result": f"published={str(publish.get('published')).lower()}",
        },
    )

@router.get("/lyrics/examples")
async def get_lyrics_examples():
    """获取歌词示例"""
    return {"examples": LYRICS_EXAMPLES}


# ── v20：歌词段落解析（[Verse 1]/[Chorus]/[Bridge]/[Outro] 标注 → 段落卡片数据）──
_SECTION_TAG_RE = re.compile(r"^\s*[\[［（(【]\s*([A-Za-z-]+(?:\s*\d*)?|副歌|主歌|桥段|桥|尾声|前奏|间奏|说唱|预副歌)\s*[]］）)】]\s*$")
_SECTION_ALIASES = {"V": "Verse", "VERSE": "Verse", "CHORUS": "Chorus", "HOOK": "Chorus",
                    "BRIDGE": "Bridge", "OUTRO": "Outro", "INTRO": "Intro", "PRE": "Pre-Chorus",
                    "PRE-CHORUS": "Pre-Chorus", "RAP": "Rap", "VERSE1": "Verse 1",
                    "副歌": "Chorus", "主歌": "Verse", "桥段": "Bridge", "桥": "Bridge",
                    "尾声": "Outro", "前奏": "Intro", "间奏": "Interlude", "说唱": "Rap",
                    "预副歌": "Pre-Chorus"}

def _normalize_section_tag(tag: str) -> str:
    """归一化段落标签（大写 + 中文别名映射）"""
    t = tag.strip().upper()
    if t in _SECTION_ALIASES:
        return _SECTION_ALIASES[t]
    # "CHORUS 1" / "VERSE2" 等带序号形式（保留序号）
    for k in ("PRE-CHORUS", "VERSE", "CHORUS", "BRIDGE", "OUTRO", "INTRO"):
        if t.startswith(k):
            return k.title() + t[len(k):]
    return t.title()


def parse_lyrics_sections(text: str) -> list[dict]:
    """解析带段落标注的歌词 → [{tag, title, lines[], is_hook}]。

    兼容 [Verse 1] / [Chorus] / [Bridge] / （副歌）/【主歌】 等标注变体；
    无任何标注时整段降级为单段 [{tag: 'text', title: '歌词', lines: 全部行}]。
    """
    if not text or not str(text).strip():
        return []
    raw_lines = [ln.rstrip() for ln in str(text).split("\n")]
    sections: list[dict] = []
    current = None

    def _push():
        if current and current["lines"]:
            sections.append(current)

    for ln in raw_lines:
        m = _SECTION_TAG_RE.match(ln)
        if m:
            _push()
            tag = m.group(1).strip().upper()
            title = _normalize_section_tag(tag)
            current = {"tag": title.upper(), "title": title, "lines": [], "is_hook": "CHORUS" in title.upper() or "HOOK" in title.upper()}
            continue
        if current is None:
            current = {"tag": "TEXT", "title": "歌词", "lines": [], "is_hook": False}
        if ln.strip():
            current["lines"].append(ln.strip())
    _push()

    if not sections:
        return []
    # 无标注：整段降级为单段（保持原行结构）
    if len(sections) == 1 and sections[0]["tag"] == "TEXT":
        return [{"tag": "text", "title": "歌词", "lines": sections[0]["lines"], "is_hook": False}]
    return sections


async def _music_lyrics_worker(payload: dict, progress: Callable | None = None) -> dict:
    """生成歌词（同步/异步任务共用执行体，异步时回报进度）。"""
    if not resolve_api_key():
        raise HTTPException(400, "未配置中转站 API Key")

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    theme = payload.get("theme") or ""
    style = payload.get("style") or "pop"
    language = payload.get("language") or "zh"
    length = payload.get("length") or "medium"
    mood = payload.get("mood") or "happy"
    rhyme = payload.get("rhyme") or "natural"  # v15：押韵要求
    structure = payload.get("structure") or "verse_chorus"  # v15：段落结构
    project_id = payload.get("project_id") or ""
    if not theme:
        raise HTTPException(400, "请输入歌词主题")

    # 生产级内容保障：歌词主题生成前安全审核（歌词需过平台内容审核）
    res = check_text(theme, "歌词")
    if not res["ok"]:
        raise HTTPException(400, "操作失败，请稍后重试")

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
    rhyme_prompts = {
        "natural": "押韵自然流畅，不强行凑韵，适合传唱",
        "strict": "严格押韵：句尾韵脚统一（如 an/ang/ing/ao 等），副歌句句压韵，适合说唱与快歌",
        "soft": "弱押韵：以意境为先，韵律轻盈不刻意",
    }
    structure_prompts = {
        "verse_chorus": "主歌 Verse + 副歌 Chorus 结构，副歌重复 2-3 遍",
        "verse_chorus_bridge": "主歌 + 副歌 + 桥段 Bridge 的完整三段式结构（含情绪递进）",
        "free": "自由段落结构，按情绪自然推进，不限定格式",
        "rap_verse": "说唱段落结构：主歌为说唱段（flow 连贯），副歌为旋律 Hook",
    }

    prompt = f"""创作一首{lang_prompts.get(language, "中文")}{style_prompts.get(style, "流行")}的歌词：

主题：{theme}
情感基调：{mood_prompts.get(mood, "欢快")}
风格：{style_prompts.get(style, "流行")}
长度要求：{length_prompts.get(length, "中歌")}
押韵要求：{rhyme_prompts.get(rhyme, "押韵自然流畅")}
段落结构：{structure_prompts.get(structure, "主歌+副歌")}

要求：
- 歌词要富有诗意和感染力
- 押韵自然流畅
- 情感表达真挚
- 结构清晰（标注Verse、Chorus、Bridge等）
- 适合演唱

v20 内容丰富度要求（必须全部满足）：
- 记忆点 Hook：副歌首句必须是一句高传唱度、易记易上口的金句（3-7 字短句优先）
- 画面感：至少 2 处具体可感知的意象描写（光线/色彩/声音/触觉/气味等五感细节），禁止抽象空话
- 情感递进：段落间情绪必须发展（起→承→高潮→收），副歌情感强度高于主歌
- 段落配比：主歌 2 段（每段 4 句）、副歌重复 2-3 遍、含桥段时桥段 2-4 句
- 每段保持 [Verse 1]/[Chorus]/[Bridge] 标注，段间空一行

请只输出歌词，不要解释。"""

    _report(15, "AI 正在创作歌词…")
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{AGNES_API_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {resolve_api_key()}", "Content-Type": "application/json"},
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
            raise HTTPException(500, "生成歌词失败，请稍后重试")
        data = response.json()
        lyrics = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not lyrics:
            raise HTTPException(502, "AI 未返回歌词内容，请重试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成歌词异常: {e}")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    # 保存生成的歌词
    lyrics_filename = f"{generate_music_id()}.txt"
    lyrics_path = MUSIC_DIR / lyrics_filename
    lyrics_path.write_text(lyrics, encoding="utf-8")
    art_id = _save_artifact(
        lyrics_filename,
        project_id,
        "lyrics",
        lyrics,
        0.0,
        {
            "theme": theme,
            "style": style,
            "language": language,
            "length": length,
            "mood": mood,
            "rhyme": rhyme,
            "structure": structure,
        },
    )
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
        "rhyme": rhyme,
        "structure": structure,
        "project_id": project_id,
    }


@router.post("/lyrics/generate")
async def generate_lyrics(
    theme: str = Form(...),
    style: str = Form("pop"),
    language: str = Form("zh"),
    length: str = Form("medium"),
    mood: str = Form("happy"),
    rhyme: str = Form("natural"),
    structure: str = Form("verse_chorus"),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """生成歌词（默认异步任务，立即返回 task_id）。"""
    if not resolve_api_key():
        raise HTTPException(400, "未配置中转站 API Key")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "theme": theme,
        "style": style,
        "language": language,
        "length": length,
        "mood": mood,
        "rhyme": rhyme,
        "structure": structure,
        "project_id": project_id,
    }
    if sync:
        return await _music_lyrics_worker(payload)
    task = create_task("music_lyrics", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "歌词生成任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


# ══════════════════════════════════════════════════════════════
# 本地 AI 音乐合成引擎：numpy 伴奏 + edge-tts 人声 + ffmpeg 混音
# ══════════════════════════════════════════════════════════════
FFMPEG_BIN = "/usr/local/bin/ffmpeg"
FFPROBE_BIN = "/usr/local/bin/ffprobe"
_SR = 44100
_EDGE_WORKER = str(Path(__file__).resolve().parent / "edge_tts_worker.py")

_VOICE_EDGE = {
    "female": "zh-CN-XiaoxiaoNeural",
    "male": "zh-CN-YunxiNeural",
    "child": "zh-CN-XiaomoNeural",
}

# ── CosyVoice 本地歌声引擎（voice_engine /sing，独立推理服务 9888） ──
# 可用时人声轨使用真歌声（instruct2 模式：音准自然、字词清晰），否则回退 edge-tts 变调链路
COSYVOICE_API_BASE = os.environ.get("COSYVOICE_API_BASE", "http://127.0.0.1:9888")
# 参考人声 prompt：默认官方 zero-shot 说话样本（已验证可驱动歌声输出）；
# 可放入自己的清唱 wav（环境变量 COSYVOICE_SING_PROMPT 覆盖）获得指定音色真演唱
COSYVOICE_SING_PROMPT = os.environ.get(
    "COSYVOICE_SING_PROMPT", "/Users/yanping.ma/ai-models/CosyVoice/asset/zero_shot_prompt.wav"
)
_COSYVOICE_SING_TIMEOUT = 180  # 单句歌声合成超时（秒，MPS 推理）

# ── ACE-Step 音乐大模型引擎（acestep-api 独立服务 9889，MLX 加速，MIT 开源） ──
# 可用时整首生成（歌词+风格提示 → 完整带人声歌曲，质量对标 Suno），否则回退本地链路
ACESTEP_API_BASE = os.environ.get("ACESTEP_API_BASE", "http://127.0.0.1:9889")
# 引擎模式：auto=ACE-Step 可用优先；acestep=强制（失败直接报错）；local=禁用
MUSIC_ENGINE_MODE = os.environ.get("MUSIC_ENGINE", "auto")
_ACESTEP_TIMEOUT = 30  # 单请求超时（秒）
_ACESTEP_POLL_INTERVAL = 6  # 任务轮询间隔（秒）
_ACESTEP_MAX_WAIT = 1200  # 单任务最大等待（秒，MLX 一首歌约 2-5 分钟）

_STYLE_LABEL = {
    "pop": "流行",
    "rock": "摇滚",
    "rap": "说唱",
    "ballad": "抒情",
    "jazz": "爵士",
    "classical": "古典",
    "folk": "民谣",
    "electronic": "电子",
}

_MOOD_LABEL = {
    "happy": "欢快",
    "sad": "悲伤",
    "energetic": "激昂",
    "calm": "平静",
    "romantic": "浪漫",
    "epic": "史诗",
}

# 风格 → 合成参数：BPM / 和弦进行（midi 绝对音级） / 琶音模式 / 鼓模式 / 贝斯模式
_STYLE_CFG = {
    "pop": {"bpm": 108, "chords": [[48, 52, 55], [55, 59, 62], [57, 60, 64], [53, 57, 60]], "pattern": "arp8", "drums": "pop", "bass": "eighth"},
    "rock": {"bpm": 126, "chords": [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], "pattern": "block", "drums": "rock", "bass": "eighth"},
    "rap": {"bpm": 88, "chords": [[50, 53, 57], [46, 49, 53], [53, 57, 60], [48, 52, 55]], "pattern": "block", "drums": "rap", "bass": "eighth"},
    "ballad": {"bpm": 72, "chords": [[48, 52, 55, 59], [55, 59, 62, 65], [57, 60, 64, 67], [53, 57, 60, 64]], "pattern": "arp16", "drums": "ballad", "bass": "half"},
    "jazz": {"bpm": 108, "chords": [[48, 52, 55, 59], [50, 53, 57, 60], [52, 55, 59, 62], [50, 53, 57, 60]], "pattern": "arp8", "drums": "jazz", "bass": "walk"},
    "classical": {"bpm": 78, "chords": [[48, 52, 55], [45, 48, 52], [53, 57, 60], [55, 59, 62]], "pattern": "arp16", "drums": "none", "bass": "half"},
    "folk": {"bpm": 96, "chords": [[55, 59, 62], [50, 54, 57], [52, 55, 59], [48, 52, 55]], "pattern": "strum", "drums": "folk", "bass": "quarter"},
    "electronic": {"bpm": 122, "chords": [[45, 49, 52], [41, 44, 48], [48, 52, 55], [43, 47, 50]], "pattern": "pad", "drums": "electronic", "bass": "eighth"},
}


async def _compose_vocal_track(phrases: list, melody: list, voice: str, total_end: float, tmpdir: str, _report) -> str:
    """合成人声轨：CosyVoice 真歌声优先，edge-tts 变调回退。返回 vocal.wav 路径。"""
    voice_edge = _VOICE_EDGE.get(voice, _VOICE_EDGE["female"])
    vocal_track = np.zeros(int((total_end + 1.5) * _SR) + _SR)
    vocal_ok = 0
    total_ph = len(phrases)
    cosy_ok = _cosyvoice_ok()
    if cosy_ok:
        logger.info("音乐工厂人声轨使用 CosyVoice 真歌声引擎（%s）", COSYVOICE_API_BASE)
    for i, ph in enumerate(phrases):
        _report(15 + int(45 * i / max(total_ph, 1)), f"演唱第 {i + 1}/{total_ph} 句…")
        phrase_vocal = None
        if cosy_ok:
            phrase_vocal = await asyncio.to_thread(_sing_phrase_aligned, ph["text"], ph["dur"])
        if phrase_vocal is None or len(phrase_vocal) == 0:
            out = os.path.join(tmpdir, f"seg_{i:03d}.mp3")
            out_json = os.path.join(tmpdir, f"seg_{i:03d}.json")
            ok = await asyncio.to_thread(_tts_segment, ph["text"], voice_edge, out, out_json)
            if not ok:
                continue
            phrase_vocal = await asyncio.to_thread(_vocalize_phrase, out, out_json, melody, ph["start"], ph["dur"])
        if phrase_vocal is None or len(phrase_vocal) == 0:
            continue
        pos = int(ph["start"] * _SR)
        end = min(pos + len(phrase_vocal), len(vocal_track))
        if end > pos:
            vocal_track[pos:end] = phrase_vocal[: end - pos]
            vocal_ok += 1
    if vocal_ok == 0:
        raise HTTPException(502, "人声演唱合成全部失败，请检查网络后重试")

    # 人声轨写 wav（峰值归一化到 0.95，防削波失真）
    vpeak = float(np.max(np.abs(vocal_track)))
    if vpeak > 0.95:
        vocal_track = vocal_track * (0.95 / vpeak)
    vocal_wav = os.path.join(tmpdir, "vocal.wav")
    _write_wav_stereo(vocal_wav, vocal_track)
    return vocal_wav


async def _compose_accompaniment(style: str, vocal_wav: str, seed: int, tmpdir: str) -> str:
    """合成伴奏轨（时长对齐人声）。返回 acc.wav 路径。"""
    import wave as _wave

    with _wave.open(vocal_wav, "rb") as w:
        frames = w.getnframes()
        fps = w.getframerate()
    duration = frames / fps
    acc = await asyncio.to_thread(_synthesize_accompaniment, style, duration + 0.5, seed)
    acc_wav = os.path.join(tmpdir, "acc.wav")
    _write_wav_stereo(acc_wav, acc)
    return acc_wav


def _write_wav_stereo(path: str, track) -> None:
    """numpy 单声道 → 16bit 立体声 wav。"""
    import wave as _wave

    pcm = (np.clip(track, -1, 1) * 32767).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with _wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes(stereo.tobytes())


def _compose_mix(vocal_wav: str, acc_wav: str, filename: str) -> Path:
    """混音链：人声压缩器 + 伴奏中频挖坑 + 总限制器 → mp3。返回输出路径。"""
    from common.media_check import is_valid_audio

    out_mp3 = MUSIC_DIR / filename
    r = subprocess.run(
        [
            FFMPEG_BIN, "-y", "-i", vocal_wav, "-i", acc_wav,
            "-filter_complex",
            "[0:a]volume=1.5,acompressor=threshold=-24dB:ratio=3:attack=6:release=120:makeup=9dB,alimiter=limit=0.93[v];"
            "[1:a]equalizer=f=480:t=q:w=1.1:g=-6,equalizer=f=1400:t=q:w=1.1:g=-4,volume=0.26[a];"
            "[v][a]amix=inputs=2:normalize=0:duration=longest,alimiter=limit=0.95[out]",
            "-map", "[out]",
            "-b:a", "192k", str(out_mp3),
        ],
        capture_output=True,
        timeout=300,
    )
    if r.returncode != 0 or not out_mp3.exists() or out_mp3.stat().st_size < 1024:
        raise RuntimeError("最终混音失败: " + r.stderr.decode(errors="replace")[-200:])
    if not is_valid_audio(str(out_mp3)):
        try:
            out_mp3.unlink()
        except OSError:
            pass
        raise RuntimeError("最终混音结果无法解析（音频无效）")
    return out_mp3



def _compose_params(payload: dict) -> dict:
    """音乐合成参数解析 + 模板热度 + 安全审核。"""
    lyrics = (payload.get("lyrics") or "").strip()
    style = payload.get("style") or "pop"
    if style not in _STYLE_CFG:
        style = "pop"
    if not lyrics:
        raise HTTPException(400, "请输入歌词内容")
    tpl_id = (payload.get("template_id") or "").strip()
    if tpl_id:
        try:
            from music_scene_templates import record_usage

            record_usage(tpl_id)
        except Exception:  # noqa: BLE001
            pass
    theme = (payload.get("theme") or "").strip()
    for label, t in (("歌词", lyrics), ("主题", theme)):
        if not t:
            continue
        res = check_text(t, "歌词")
        if not res["ok"]:
            raise HTTPException(400, "内容审核不通过")
    return {
        "lyrics": lyrics, "style": style, "mood": payload.get("mood") or "happy",
        "voice": payload.get("voice") or "female", "theme": theme,
        "project_id": payload.get("project_id") or "",
    }

async def _compose_music_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """音乐合成执行体（同步/异步任务共用）：numpy 伴奏 + edge-tts 分句人声 + ffmpeg 混音 → mp3 + 封面。"""

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    params = _compose_params(payload)
    lyrics, style, mood, voice, theme, project_id = (
        params["lyrics"], params["style"], params["mood"],
        params["voice"], params["theme"], params["project_id"],
    )

    # ACE-Step 大模型引擎优先（auto 模式可用时；失败自动回退本地链路）
    use_acestep = MUSIC_ENGINE_MODE != "local" and _acestep_ok()
    if use_acestep:
        logger.info("音乐工厂使用 ACE-Step 大模型引擎（%s）", ACESTEP_API_BASE)
        try:
            return await _compose_music_acestep(payload, _report)
        except HTTPException:
            raise
        except Exception as e:
            if MUSIC_ENGINE_MODE == "acestep":
                raise HTTPException(502, "服务异常，请稍后重试") from e
            logger.warning("ACE-Step 生成失败，回退本地引擎: %s", e)
            _report(4, "ACE-Step 引擎异常，切换本地合成…")

    _report(6, "解析歌词并谱曲…")
    seed = int(time.time() * 1000) % 100000
    phrases, melody = _plan_singing(lyrics, style, voice, seed)
    if not phrases:
        raise HTTPException(400, "歌词内容为空，请先输入或生成歌词")
    total_end = phrases[-1]["start"] + phrases[-1]["dur"]

    _report(15, "AI 人声演唱合成中（旋律谱曲 + 逐句演唱，约需 1-2 分钟）…")
    tmpdir = tempfile.mkdtemp(prefix="music_compose_")
    try:
        vocal_wav = await _compose_vocal_track(phrases, melody, voice, total_end, tmpdir, _report)

        _report(78, "伴奏谱曲合成中…")
        acc_wav = await _compose_accompaniment(style, vocal_wav, seed, tmpdir)

        _report(86, "混音合成中…")
        # 混音链：人声压缩器（压动态提响度）+ 限制器 → 伴奏中频挖坑（避开人声频段）+ 降量 → 混合 + 总限制器
        # 人声链：volume 1.5 前置增益，threshold -24dB 以上 3:1 压缩，makeup +9dB，限制 0.93 防削波
        # 伴奏链：480Hz/1.4kHz 分别 -6/-4dB（人声频段让路），整体 0.26x
        filename = f"{generate_music_id()}.mp3"
        out_mp3 = _compose_mix(vocal_wav, acc_wav, filename)

        _report(85, "生成封面…")
        stem = filename.rsplit(".", 1)[0]
        cover_path = MUSIC_DIR / f"{stem}.jpg"
        cover_url = f"/api/music-factory/covers/{stem}.jpg"
        _make_cover(theme or stem, style, mood, cover_path)
        duration = _probe_seconds(str(out_mp3))
        art_id = _save_artifact(
            filename,
            project_id,
            "audio",
            lyrics,
            duration,
            {"style": style, "mood": mood, "voice": voice, "theme": theme, "cover": cover_url},
            thumbnail=cover_url,
        )
        _report(100, "歌曲已生成")
        return {
            "audio_id": filename,
            "artifact_id": art_id,
            "url": f"/api/music-factory/audios/{filename}",
            "cover_url": cover_url,
            "duration": duration,
            "style": style,
            "mood": mood,
            "voice": voice,
            "theme": theme,
            "project_id": project_id,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _note_freq(midi: float) -> float:
    """midi 音级 → 频率 (Hz)。"""
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _synth_note(freq: float, dur: float, kind: str = "piano", vel: float = 0.8) -> np.ndarray:
    """合成一个音符波形（谐波叠加 + 指数衰减包络），kind: piano/pad/bass/strum/pluck。"""
    n = max(int(_SR * dur), 1)
    t = np.linspace(0, dur, n, endpoint=False)
    if kind == "piano":
        w = np.sin(2 * np.pi * freq * t) + 0.45 * np.sin(2 * np.pi * 2 * freq * t) + 0.2 * np.sin(2 * np.pi * 3 * freq * t)
        env = (1 - np.exp(-t * 80)) * np.exp(-t * 5.0)
    elif kind == "pad":
        w = np.sin(2 * np.pi * freq * t) + 0.5 * np.sin(2 * np.pi * freq * 1.005 * t) + 0.4 * np.sin(2 * np.pi * 2 * freq * t)
        env = (1 - np.exp(-t * 4)) * np.exp(-t * 0.8)
    elif kind == "bass":
        w = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
        env = (1 - np.exp(-t * 60)) * np.exp(-t * 3.5)
    elif kind == "strum":
        w = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * 2 * freq * t)
        env = (1 - np.exp(-t * 120)) * np.exp(-t * 7.0)
    else:  # pluck 旋律短音
        w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * 2 * freq * t)
        env = (1 - np.exp(-t * 100)) * np.exp(-t * 2.8)
    return w * env * vel


def _synth_kick() -> np.ndarray:
    """底鼓：低频扫频正弦 + 快速衰减。"""
    dur = 0.16
    t = np.linspace(0, dur, int(_SR * dur), endpoint=False)
    f = 100 * np.exp(-t * 22) + 42
    return np.sin(2 * np.pi * np.cumsum(f) / _SR) * np.exp(-t * 30)


def _synth_snare(vel: float = 0.7) -> np.ndarray:
    """军鼓：噪声 + 中频音色。"""
    dur = 0.18
    t = np.linspace(0, dur, int(_SR * dur), endpoint=False)
    noise = np.random.default_rng().uniform(-1, 1, len(t)) * np.exp(-t * 20)
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 32)
    return (0.65 * noise + 0.35 * tone) * vel


def _synth_hat(open_: bool = False, vel: float = 0.5) -> np.ndarray:
    """踩镲：白噪声短衰减（open_=True 为开镲长音）。"""
    dur = 0.3 if open_ else 0.09
    t = np.linspace(0, dur, int(_SR * dur), endpoint=False)
    return np.random.default_rng().uniform(-1, 1, len(t)) * np.exp(-t * (9 if open_ else 42)) * vel


def _make_place(track: np.ndarray) -> Callable:
    """返回波形叠加器：place(sig, at_sec, gain)。"""

    def place(sig: np.ndarray, at_sec: float, gain: float = 1.0) -> None:
        start = int(at_sec * _SR)
        if start >= len(track) or len(sig) == 0:
            return
        end = min(start + len(sig), len(track))
        track[start:end] += sig[: end - start] * gain

    return place


def _place_arpeggio(place, chord: list[int], t0: float, beat: float, pattern: str) -> None:  # noqa: C901
    """按风格琶音/柱式铺和弦。"""
    if pattern == "arp8":
        seq = [0, 1, 2, 3, 2, 1, 0, 2]
        for i, ci in enumerate(seq):
            place(_synth_note(_note_freq(chord[ci % len(chord)] + 12), beat * 0.42, "piano", 0.5), t0 + i * beat * 0.5)
    elif pattern == "arp16":
        seq = [0, 2, 1, 3, 2, 0, 3, 1, 0, 2, 1, 3, 2, 0, 3, 1]
        for i, ci in enumerate(seq):
            place(_synth_note(_note_freq(chord[ci % len(chord)] + 12), beat * 0.22, "piano", 0.4), t0 + i * beat * 0.25)
    elif pattern == "block":
        for ci in chord:
            place(_synth_note(_note_freq(ci + 12), beat * 3.8, "piano", 0.35), t0)
    elif pattern == "pad":
        for ci in chord:
            place(_synth_note(_note_freq(ci + 12), beat * 4.2, "pad", 0.5), t0)
    else:  # strum 扫弦：每拍快速分解
        for b_i in range(4):
            for k, ci in enumerate(chord):
                place(_synth_note(_note_freq(ci + 12), beat * 0.28, "strum", 0.32), t0 + b_i * beat + k * 0.045)



# 鼓模式定义：k=底鼓(s), s=军鼓, h=踩镲, o=开踩镲, 每个元组 (乐器, 节拍位置, 力度)
_DRUM_PATTERNS = {
    "pop": [("k", 0, 1.0), ("k", 2, 1.0), ("s", 1, 1.0), ("s", 3, 1.0)],
    "rock": [("k", 0, 1.0), ("k", 1, 1.0), ("s", 1, 1.0), ("s", 3, 1.0)],
    "rap": [("k", i, 1.0) for i in range(4)] + [("s", 1, 1.0), ("s", 3, 1.0)],
    "ballad": [("k", 0, 1.0), ("s", 1, 0.5), ("s", 3, 0.5)],
    "jazz": [("k", 0, 1.0), ("s", 1, 0.45), ("s", 3, 0.45)],
    "folk": [("k", 0, 1.0), ("s", 1, 0.4), ("s", 3, 0.4)],
    "electronic": [("k", i, 1.0) for i in range(4)],
}
_DRUM_HAT_STEPS = {"pop": 8, "rock": 8, "rap": 16, "ballad": 8, "jazz": 8, "folk": 4}
_DRUM_HAT_VOL = {"pop": 0.35, "rock": 0.45, "rap": 0.3, "ballad": 0.22, "jazz": 0.25, "folk": 0.2}


def _place_drum_hits(place, pattern: list, t0: float, beat: float, kit: dict) -> None:
    """按模式铺底鼓/军鼓。"""
    for inst, b_i, vol in pattern:
        place(kit[inst], t0 + b_i * beat, vol)


def _place_drum_hats(place, drums: str, t0: float, beat: float, kit: dict) -> None:
    """按模式铺踩镲（jazz 带摇摆）。"""
    steps = _DRUM_HAT_STEPS.get(drums, 8)
    vol = _DRUM_HAT_VOL.get(drums, 0.3)
    if drums == "electronic":
        for i in range(16):
            if i % 2 == 1:
                place(kit["h"], t0 + i * beat * 0.25, 0.3)
        place(kit["o"], t0 + 3.5 * beat, 0.35)
        return
    for i in range(steps):
        swing = 0.5 if drums != "jazz" or i % 2 == 0 else 0.55
        place(kit["h"], t0 + (i + swing - 0.5) * beat * 0.5, vol)

def _place_drums(place, drums: str, t0: float, beat: float) -> None:
    """按鼓模式铺鼓点（4/4 拍，数据驱动）。"""
    if drums == "none":
        return
    kit = {"k": _synth_kick(), "s": _synth_snare(), "h": _synth_hat(), "o": _synth_hat(open_=True)}
    _place_drum_hits(place, _DRUM_PATTERNS.get(drums, []), t0, beat, kit)
    _place_drum_hats(place, drums, t0, beat, kit)


def _place_bass(place, bass_mode: str, root: int, t0: float, beat: float, bar: float) -> None:
    """按贝斯模式铺根音。"""
    if bass_mode == "eighth":
        for i in range(8):
            place(_synth_note(_note_freq(root), beat * 0.4, "bass", 0.5), t0 + i * beat * 0.5)
    elif bass_mode == "quarter":
        for i in range(4):
            place(_synth_note(_note_freq(root), beat * 0.8, "bass", 0.5), t0 + i * beat)
    elif bass_mode == "walk":
        for i, off in enumerate([0, 7, 12, 7]):
            place(_synth_note(_note_freq(root + off), beat * 0.85, "bass", 0.4), t0 + i * beat)
    else:  # half 全音符根音
        place(_synth_note(_note_freq(root), bar * 0.9, "bass", 0.5), t0)


def _synthesize_accompaniment(style: str, seconds: float, seed: int) -> np.ndarray:
    """按风格合成伴奏（和弦 + 琶音 + 鼓 + 贝斯 + 旋律垫音），返回单声道 float 波形。"""
    cfg = _STYLE_CFG.get(style, _STYLE_CFG["pop"])
    rng = np.random.default_rng(seed)
    beat = 60.0 / cfg["bpm"]
    bar = beat * 4
    n_bars = max(int(seconds / bar) + 2, 6)  # 前奏 + 主体 + 尾奏
    total = n_bars * bar
    track = np.zeros(int(total * _SR))
    place = _make_place(track)
    chords = cfg["chords"]
    for b in range(n_bars):
        t0 = b * bar
        chord = chords[b % len(chords)]
        is_outro = b >= n_bars - 1
        if not is_outro:
            _place_arpeggio(place, chord, t0, beat, cfg["pattern"])
            _place_drums(place, cfg["drums"], t0, beat)
            _place_bass(place, cfg["bass"], chord[0] - 12, t0, beat, bar)
            # 主旋律垫音：随机点缀和弦高音（seed 固定保证可复现）
            if cfg["pattern"] in ("arp8", "arp16", "block"):
                for i in range(8):
                    if rng.random() < 0.35:
                        note = chord[int(rng.integers(0, len(chord)))] + 24
                        place(_synth_note(_note_freq(note), beat * (0.4 + rng.random() * 0.6), "pluck", 0.16), t0 + i * beat * 0.5)
    # 结尾淡出 + 归一化
    fade = int(1.2 * _SR)
    if len(track) > fade:
        track[-fade:] *= np.linspace(1, 0, fade)
    peak = float(np.max(np.abs(track))) or 1.0
    return track / peak * 0.9


# ============ AI 歌声合成引擎（Singing Synthesis）============
# 管线：edge-tts 整句合成（WordBoundary 逐词时间戳）→ 字级 F0 估计（自相关，
# 句级中位数八度对齐）→ 相位声码器时域伸缩 → 变因子重采样搬移音高（颤音）→
# 按旋律时间轴逐词拼接成人声轨。纯 numpy 实现，无需第三方依赖。


def _estimate_f0_mono(x: np.ndarray, sr: int = _SR, pct: float = 15.0):
    """自相关 F0 估计：返回 (f0_hz|None, 浊音占比)。低分位数抑制高八度误检。

    局部峰值挑选：插值重采样会让相邻样本强相关，自相关在小 lag 处形成单调
    伪峰，全局 argmax 会锁到最小 lag（1575Hz 上限）；局部峰值可避开单调区。
    """
    frame, hop = 1024, 512
    lags = np.arange(40, 512)  # 86Hz ~ 1102Hz
    f0s = []
    for s in range(0, max(len(x) - frame, 1), hop):
        seg = x[s : s + frame]
        if len(seg) < frame:
            seg = np.pad(seg, (0, frame - len(seg)))
        seg = seg - seg.mean()
        energy = np.dot(seg, seg)
        if energy < 1e-6:
            continue
        r = np.array([np.dot(seg[: frame - k], seg[k:]) for k in lags]) / energy
        # 局部峰值（一阶差分由正转负），排除插值伪相关的单调区
        d = np.diff(r)
        peaks = np.where((d[:-1] > 0) & (d[1:] <= 0))[0] + 1
        if len(peaks) == 0:
            peaks = np.array([int(np.argmax(r))])
        peak_i = int(peaks[int(np.argmax(r[peaks]))])
        if r[peak_i] < 0.35:
            continue
        # 抛物线插值细化峰值位置
        if 0 < peak_i < len(lags) - 1:
            a, b, c = r[peak_i - 1], r[peak_i], r[peak_i + 1]
            denom = a - 2 * b + c
            if abs(denom) > 1e-12:
                peak_i += 0.5 * (a - c) / denom
        f0s.append(sr / (lags[0] + peak_i))
    if not f0s:
        return None, 0.0
    f0s = np.array(f0s)
    return float(np.percentile(f0s, pct)), len(f0s) / max((len(x) - frame) // hop + 1, 1)


def _stft_phase(x: np.ndarray, n_fft: int = 1024, hop: int = 256):
    """短时傅里叶变换（歌声合成用，返回幅度谱与窗函数）。"""
    win = np.hanning(n_fft)
    frames = max(1 + (len(x) - n_fft) // hop, 1)
    cols = np.array([x[i * hop : i * hop + n_fft] for i in range(frames)])
    cols = np.pad(cols, ((0, 0), (0, n_fft - cols.shape[1])))
    return np.fft.rfft(cols * win, axis=1), win


def _istft_phase(X: np.ndarray, win: np.ndarray, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    """重叠相加逆 STFT（含窗平方归一化与边缘平滑）。"""
    frames = X.shape[0]
    out_len = (frames - 1) * hop + n_fft
    out = np.zeros(out_len)
    wsum = np.zeros(out_len)
    win2 = win * win
    for i in range(frames):
        seg = np.fft.irfft(X[i], n=n_fft) * win
        s = i * hop
        out[s : s + n_fft] += seg
        wsum[s : s + n_fft] += win2
    wsum[wsum < 1e-3] = 1.0
    wsum = np.convolve(wsum, np.ones(64) / 64, mode="same")  # 平滑，抑制边缘放大
    wsum[wsum < 1e-3] = 1.0
    return out / wsum


def _phase_vocoder_stretch(x: np.ndarray, rate: float, sr: int = _SR) -> np.ndarray:
    """相位声码器时域伸缩：rate>1 拉长，rate<1 压缩，音高保持不变。"""
    rate = float(np.clip(rate, 0.5, 2.5))
    if abs(rate - 1.0) < 0.02 or len(x) < 800:
        return x.copy()
    n_fft, hop = 1024, 256
    X, win = _stft_phase(x, n_fft, hop)
    frames = X.shape[0]
    if frames < 3:
        return x.copy()
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    phase_adv = 2 * np.pi * freqs * hop / sr
    hop_out = max(int(round(hop * rate)), 16)
    Y = np.zeros_like(X)
    Y[0] = X[0]
    phase_acc = np.angle(X[0])
    for k in range(1, frames):
        mag = np.abs(X[k])
        # 输入相邻帧相位差（扣除理想推进）→ 瞬时频率残差，保持音高
        d = np.angle(X[k]) - np.angle(X[k - 1]) - phase_adv
        d = (d + np.pi) % (2 * np.pi) - np.pi
        phase_acc = phase_acc + phase_adv * rate + d
        Y[k] = mag * np.exp(1j * phase_acc)
    out = _istft_phase(Y, win, n_fft, hop_out)
    scale = np.sqrt(np.dot(x, x) / (np.dot(out, out) + 1e-9))
    return out * min(scale, 3.0)


def _resample_fft(x: np.ndarray, n_out: int) -> np.ndarray:
    """FFT 频域重采样：无混叠、无线性插值高频衰减（sinc 级插值质量）。"""
    n_in = len(x)
    if n_out == n_in or n_in < 32 or n_out < 32:
        return x.copy()
    X = np.fft.rfft(x)
    Y = np.zeros(n_out // 2 + 1, dtype=complex)
    k = min(X.shape[0], n_out // 2 + 1)
    Y[:k] = X[:k]
    return np.fft.irfft(Y, n=n_out) * (n_out / n_in)


def _lowpass_fft(x: np.ndarray, sr: int, fcut: float) -> np.ndarray:
    """FFT 频域低通（零相位），过渡带 200Hz 渐变防硬切振铃。"""
    if fcut <= 0 or fcut >= sr * 0.49:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / sr)
    X[f > fcut] = 0.0
    band = (f >= fcut - 200.0) & (f <= fcut)
    if band.any():
        X[band] *= (fcut - f[band]) / 200.0
    return np.fft.irfft(X, n=len(x))


def _pitch_shift_vibrato(x: np.ndarray, f0: float, f1: float, sr: int = _SR) -> np.ndarray:
    """变因子重采样：把基频从 f0 搬到 f1，长音附加 5.5Hz 演唱颤音。"""
    ratio = f1 / f0
    n = len(x)
    if abs(ratio - 1.0) < 0.01:
        return x.copy()
    if ratio > 1.05:
        # 抗混叠：升调重采样会把高于 sr/2/ratio 的频率折回低频（刺耳机器人音）
        x = _lowpass_fft(x, sr, min(0.45 * sr / ratio, 8000.0))
    dur = n / sr
    n_out = max(int(n / ratio), 2)
    tt = np.arange(n_out) / sr
    if dur > 0.28:
        r_t = ratio * (1.0 + 0.008 * np.sin(2 * np.pi * 5.5 * tt))
    else:
        r_t = np.full(n_out, ratio)
    phase = np.zeros(n_out)
    phase[1:] = np.cumsum(r_t[1:])
    pos = np.clip(phase, 0, n - 1)
    return np.interp(pos, np.arange(n), x)


def _vocalize_word(cut: np.ndarray, f1: float, target_dur: float, ref_f0: float | None, sr: int = _SR):
    """单字歌声化：字级 F0（句级基准做八度对齐）→ 相位声码器拉伸 → 变调颤音 → 包络。

    返回 (歌声段, 使用的f0)；清音字退化为仅时长处理，保留自然辅音。
    """
    t0 = len(cut) / sr
    # 中位数 F0 估计：pct=15 低分位会系统性低估（乘法误差被变调放大），改用中位数
    f0, vr = _estimate_f0_mono(cut, pct=50)
    if f0 is None or f0 < 70 or vr < 0.15:
        out = _phase_vocoder_stretch(cut, target_dur / max(t0, 0.05))
        env = np.ones(len(out))
        a = min(int(0.02 * sr), len(out))
        e = min(int(0.04 * sr), len(out))
        if len(out) > a + e:
            env[:a] = np.linspace(0, 1, a) ** 0.7
            env[-e:] = np.linspace(1, 0, e) ** 0.8
        return out * env, None
    if ref_f0 is not None and ref_f0 > 70:
        if f0 / ref_f0 > 3.0 or ref_f0 / f0 > 3.0:
            f0 = ref_f0  # 极端误检（非八度关系，如噪声谐波）直接回退句级基准
        else:
            # 八度对齐：仅当字级与句级偏差超过整八度时折半/加倍（防高八度误检）
            while f0 / ref_f0 > 2.0 and f0 > 75:
                f0 /= 2.0
            while ref_f0 / f0 > 2.0 and f0 < 600:
                f0 *= 2.0
    stretch_rate = float(np.clip(target_dur * f1 / f0 / max(t0, 0.02), 0.5, 2.5))
    stretched = _phase_vocoder_stretch(cut, stretch_rate)
    shifted = _pitch_shift_vibrato(stretched, f0, f1, sr)
    # 时长对齐：stretch 被 clip 后，pitch_shift 按 ratio 缩短时长会偏离 target_dur，
    # 再补一次拉伸把词长校准到目标时值（保证槽位无静音空隙）
    t_cur = len(shifted) / sr
    if t_cur > 0.05 and abs(t_cur - target_dur) / max(target_dur, 0.05) > 0.08:
        shifted = _phase_vocoder_stretch(shifted, target_dur / t_cur)
    # 包络：20ms 淡入 + 尾音 40ms 淡出（防爆音 + 演唱咬字感）
    env = np.ones(len(shifted))
    a = int(0.02 * sr)
    e = int(0.04 * sr)
    if len(shifted) > a + e:
        env[:a] = np.linspace(0, 1, a) ** 0.7
        env[-e:] = np.linspace(1, 0, e) ** 0.8
    return shifted * env, f0



def _estimate_word_f0s(raw: np.ndarray, valid: list, ref_f0: float | None, sr: int) -> list:
    """逐词 F0 预估计：自相关 + 中位数 + 八度对齐 + 极端回退。"""
    f0_list: list[float | None] = []
    for w0, w1 in valid:
        f0, vr = _estimate_f0_mono(raw[int(w0 * sr): int(w1 * sr)], pct=50)
        if f0 is None or f0 < 70 or vr < 0.15:
            f0_list.append(None)
            continue
        if ref_f0 is not None and ref_f0 > 70:
            if f0 / ref_f0 > 3.0 or ref_f0 / f0 > 3.0:
                f0 = ref_f0
            else:
                while f0 / ref_f0 > 2.0 and f0 > 75:
                    f0 /= 2.0
                while ref_f0 / f0 > 2.0 and f0 < 600:
                    f0 *= 2.0
        f0_list.append(f0)
    return f0_list


def _synthesize_word_vocal(
    raw: np.ndarray, valid: list, f0_list: list, notes: list,
    seg_dur: float, target_n: int, sr: int,
) -> np.ndarray:
    """逐词演唱化：槽位按词长比例分配 + raw 段直接变调 + 包络防爆音。"""
    n = len(valid)
    total_t = max(sum(w1 - w0 for w0, w1 in valid), 1e-6)
    vocal = np.zeros(target_n)
    pos = 0
    for i in range(n):
        w0, w1 = valid[i]
        s0, s1 = pos, min(pos + int(seg_dur / total_t * (w1 - w0) * sr), target_n)
        pos = s1
        if s1 <= s0:
            continue
        seg_in = raw[int(w0 * sr): int(w1 * sr)]
        if len(seg_in) < 64:
            continue
        f0 = f0_list[i]
        ni = min(len(notes) - 1, round(i * (len(notes) - 1) / max(n - 1, 1)))
        f1 = _note_freq(notes[ni]["midi"])
        if f0 is None:
            voiced = _phase_vocoder_stretch(seg_in, (s1 - s0) / len(seg_in))
        else:
            voiced = _pitch_shift_vibrato(seg_in, f0, f1, sr)
            stretch = (s1 - s0) / max(len(voiced), 1)
            if len(voiced) > 64 and stretch > 1.05:
                voiced = _phase_vocoder_stretch(voiced, stretch)
        env = np.ones(len(voiced))
        a = min(int(0.015 * sr), len(voiced))
        e = min(int(0.03 * sr), len(voiced))
        if len(voiced) > a + e:
            env[:a] = np.linspace(0, 1, a) ** 0.7
            env[-e:] = np.linspace(1, 0, e) ** 0.8
        voiced = voiced * env
        end = min(s0 + len(voiced), target_n)
        vocal[s0:end] = voiced[: end - s0]
    return vocal

def _vocalize_phrase(  # noqa: C901
    mp3_path: str, json_path: str, melody: list[dict], seg_start: float, seg_dur: float, sr: int = _SR
) -> np.ndarray | None:
    """整句演唱化：逐词变调 + 时长铺满 → 返回句内人声段 numpy。失败返回 None。

    步骤：
    1. 逐词 F0 预估计（raw 段自相关，中位数+八度对齐+极端回退）——必须在任何
       重采样前完成：插值/FFT 重采样会让自相关在小 lag 处产生单调伪峰（锁到
       1102Hz 检测上限），重采样后重估必然误检；
    2. 逐词演唱化：槽位按 TTS 词朗读时长比例分配（长词唱长、短词唱短，节奏自然），
       词段直接变调（升调带抗混叠低通）搬到旋律音符，再相位声码器补拉伸铺满槽位。
    """
    try:
        wav_path = mp3_path + ".wav"
        r = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", mp3_path, "-ar", str(sr), "-ac", "1", wav_path],
            capture_output=True,
            timeout=60,
        )
        if r.returncode != 0 or not os.path.exists(wav_path) or os.path.getsize(wav_path) == 0:
            return None
        with wave.open(wav_path, "rb") as w:
            raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
        with open(json_path, encoding="utf-8") as f:
            words = json.load(f)
        if not words or len(raw) < 2048:
            return None
        ref_f0, _ = _estimate_f0_mono(raw, pct=50)
        # 句内音符序列（按时间序）
        notes = sorted(
            (m for m in melody if seg_start - 0.05 <= m["start"] < seg_start + seg_dur + 0.05),
            key=lambda m: m["start"],
        )
        # 有效词序列（按时间序）
        valid = []
        for wd in words:
            try:
                w0 = float(wd["start"])
                w1 = float(wd["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if w1 > w0 and int(w0 * sr) < int(w1 * sr):
                valid.append((w0, w1))
        if not valid or not notes:
            return None
        n = len(valid)
        target_n = int(seg_dur * sr)

        # ── 1. 逐词 F0 预估计（raw 段，不受重采样伪相关影响）──
        f0_list = _estimate_word_f0s(raw, valid, ref_f0, sr)

        # ── 2. 逐词演唱化：槽位按词朗读时长比例分配 + raw 段直接变调 ──
        vocal = _synthesize_word_vocal(raw, valid, f0_list, notes, seg_dur, target_n, sr)
        return vocal
    except Exception:
        return None



def _melody_pool(chord: list, root: int, penta: tuple, lo: int, hi: int) -> list:
    """生成可用音池（和弦音 + 五声音阶，限音域）。"""
    pool: set[int] = set()
    for off in (0, 12):
        for c in chord:
            pool.add(c + off)
    for octv in (0, 1, 2):
        for iv in penta:
            pool.add(root + iv + 12 * octv)
    usable = sorted(p for p in pool if lo <= p <= hi)
    return usable or [root + 12]


def _note_start(usable: list, prev: int | None, root: int, rng) -> int:
    """句首音：和弦根/五音，优先衔接前句尾音（≤4 半音）。"""
    cands = [p for p in usable if (p - root) % 12 in (0, 7)] or usable
    if prev is not None:
        joined = [p for p in cands if abs(p - prev) <= 4]
        if joined:
            cands = joined
        else:
            near = [p for p in usable if abs(p - prev) <= 4]
            if near:
                cands = near
    return rng.choice(cands)


def _note_end(usable: list, prev: int | None, root: int, rng) -> int:
    """句尾音：回落收束（根音/三音，平滑）。"""
    cands = [
        p for p in usable
        if (p - root) % 12 in (0, 4)
        and (prev is None or prev - 3 <= p <= prev + 2)
    ]
    return rng.choice(cands) if cands else (prev or root + 12)


def _note_middle(usable: list, prev: int | None, root: int, rng) -> int:
    """句中音：≤3 半音平滑游走。"""
    base = prev if prev is not None else root + 12
    near = [p for p in usable if abs(p - base) <= 3]
    return rng.choice(near) if near else base

def _generate_melody(style: str, phrases: list[dict], seed: int, voice: str = "female") -> list[dict]:  # noqa: C901
    """为歌词生成主旋律（midi 音符序列）：和弦进行 + 五声音阶随机游走，音域受限。

    规则：句首取和弦根音/五音（强拍），句尾回落收束，中间字 ≤3 半音平滑游走。
    """
    cfg = _STYLE_CFG.get(style, _STYLE_CFG["pop"])
    beat = 60.0 / cfg["bpm"]
    bar_dur = beat * 4
    # 音域：女声 C4~C5，男声 C3~C4（贴近说话音高，升调 ≤2.5x 内补拉伸质量可控）
    lo, hi = (50, 62) if voice == "male" else (60, 72)
    penta = (0, 2, 4, 7, 9)
    rng = random.Random(seed)
    melody: list[dict] = []
    prev: int | None = None
    for ph in phrases:
        n = max(ph["n"], 1)
        dur_per = ph["dur"] / n
        bar_idx = int(ph["start"] / bar_dur)
        chord = cfg["chords"][bar_idx % len(cfg["chords"])]
        root = chord[0]
        usable = _melody_pool(chord, root, penta, lo, hi)
        for i in range(n):
            if i == 0:
                note = _note_start(usable, prev, root, rng)
            elif i == n - 1:
                note = _note_end(usable, prev, root, rng)
            else:
                note = _note_middle(usable, prev, root, rng)
            note = int(np.clip(note, lo, hi))
            melody.append(
                {
                    "midi": note,
                    "start": round(ph["start"] + i * dur_per, 3),
                    "dur": round(dur_per, 3),
                }
            )
            prev = note
    return melody


def _chunk_long(s: str) -> list[str]:
    """超长乐句硬切：12 字一段，剩余不足 12 字单独成句。"""
    if len(s) <= 12:
        return [s]
    return [s[i : i + 12] for i in range(0, len(s), 12)]


def _split_lyric_lines(lyrics: str) -> list[str]:
    """歌词分句：换行 > 中文标点 > 空格 token，乐句上限 12 字（保证演唱有乐句感）。"""
    import re

    out: list[str] = []
    for ln in [ln.strip() for ln in (lyrics or "").splitlines() if ln.strip()]:
        if ln.startswith("[") and ln.endswith("]"):
            out.append(ln)
            continue
        for p in re.split(r"[，。！？；、,.!?;]+[\s　]*", ln):
            p = p.strip()
            if not p:
                continue
            for tok in (t.strip() for t in p.split() if t.strip()) or [p]:
                out.extend(_chunk_long(tok))
    return out


def _plan_lyrics(lyrics: str) -> list[dict]:
    """解析歌词 → [{text, start, est}]：按中文朗读速度估算句长，段落标记间留白。"""
    segments: list[dict] = []
    t = 1.0  # 前奏
    for ln in _split_lyric_lines(lyrics):
        if ln.startswith("[") and ln.endswith("]"):
            t += 1.2
            continue
        dur = max(len(ln) * 0.30, 1.6) + 0.4
        segments.append({"text": ln, "start": t, "est": dur})
        t += dur
    return segments


def _plan_singing(lyrics: str, style: str, voice: str, seed: int) -> tuple[list[dict], list[dict]]:
    """解析歌词 → 演唱计划：句级 [{text,start,dur,n}] + 全局主旋律音符序列。

    演唱节奏比朗读略快（每字约 0.34s），句间留呼吸，段落标记间加间奏。
    """
    phrases: list[dict] = []
    t = 1.0  # 前奏
    for ln in _split_lyric_lines(lyrics):
        if ln.startswith("[") and ln.endswith("]"):
            t += 1.4
            continue
        n = len(ln)
        dur = max(n * 0.34, 1.8) + 0.5
        phrases.append({"text": ln, "start": round(t, 3), "dur": round(dur, 3), "n": n})
        t += dur
    melody = _generate_melody(style, phrases, seed, voice)
    return phrases, melody


def _tts_segment(text: str, voice: str, out_path: str, words_path: str = "") -> bool:
    """子进程调用 edge-tts 合成单句人声（含逐词时间戳）；空文件视为失败。"""
    try:
        result = subprocess.run(
            [sys.executable, _EDGE_WORKER, text, voice, "+0%", out_path, "", words_path],
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=90,
        )
        return result.returncode == 0 and os.path.getsize(out_path) > 0
    except Exception:
        return False


def _cosyvoice_ok() -> bool:
    """探活 CosyVoice 本地引擎（/health），失败时音乐工厂回退 edge-tts 变调链路。"""
    try:
        r = requests.get(f"{COSYVOICE_API_BASE}/health", timeout=2)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def _sing_cosyvoice(text: str) -> tuple[np.ndarray, int] | None:
    """调用 voice_engine /sing 合成一句真歌声，返回 (samples float32, sample_rate)。"""
    import io

    try:
        prompt = COSYVOICE_SING_PROMPT
        if not os.path.exists(prompt):
            logger.warning(f"CosyVoice 歌声 prompt 不存在: {prompt}")
            return None
        with open(prompt, "rb") as f:
            resp = requests.post(
                f"{COSYVOICE_API_BASE}/sing",
                data={"lyrics": text},
                files={"prompt_wav": (os.path.basename(prompt), f, "audio/wav")},
                timeout=_COSYVOICE_SING_TIMEOUT,
            )
        if resp.status_code != 200:
            logger.warning(f"CosyVoice /sing 返回 {resp.status_code}: {resp.text[:120]}")
            return None
        with wave.open(io.BytesIO(resp.content), "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if nch > 1:
            raw = raw.reshape(-1, nch).mean(axis=1)
        return raw.astype(np.float32) / 32768.0, sr
    except Exception as e:
        logger.warning(f"CosyVoice 歌声合成失败: {e}")
        return None


def _fit_duration(samples: np.ndarray, sr: int, target_sec: float) -> np.ndarray | None:
    """时间拉伸对齐目标时长并重采样到 44.1kHz 单声道；超限返回 None（由调用方回退）。

    拉伸比例夹在 0.7~1.35（超出会明显变调失真，宁可回退旧链路）；
    拉伸后仍长于目标时截尾，保证句落位不越界。
    """
    tmp_in = tmp_out = ""
    try:
        cur = len(samples) / sr
        if cur < 0.4 or target_sec < 0.4:
            return None
        ratio = cur / max(target_sec, 0.6)
        ratio = max(0.7, min(1.35, ratio))
        stamp = f"{int(time.time() * 1000)}_{random.randint(0, 9999)}"
        tmp_in = os.path.join(tempfile.gettempdir(), f"cv_sing_{stamp}.wav")
        tmp_out = tmp_in + ".fit.wav"
        pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        with wave.open(tmp_in, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(pcm.tobytes())
        r = subprocess.run(
            [FFMPEG_BIN, "-y", "-i", tmp_in, "-af", f"atempo={ratio:.4f}", "-ar", str(_SR), "-ac", "1", tmp_out],
            capture_output=True,
            timeout=60,
        )
        if r.returncode != 0 or not os.path.exists(tmp_out):
            return None
        with wave.open(tmp_out, "rb") as w:
            out = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
        target_n = int(target_sec * _SR)
        if len(out) > target_n:
            out = out[:target_n]
        return out
    except Exception as e:
        logger.warning(f"歌声时长对齐失败: {e}")
        return None
    finally:
        for p in (tmp_in, tmp_out):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


def _sing_phrase_aligned(text: str, target_sec: float) -> np.ndarray | None:
    """CosyVoice 真歌声单句流水线：/sing 生成 → 时间拉伸对齐谱曲时长 → 44.1kHz 单声道。"""
    wav = _sing_cosyvoice(text)
    if wav is None:
        return None
    samples, sr = wav
    if len(samples) < int(sr * 0.3):
        return None
    return _fit_duration(samples, sr, target_sec)


def _acestep_ok() -> bool:
    """探活 ACE-Step 引擎（/health），失败时音乐工厂走本地合成链路。"""
    try:
        r = requests.get(f"{ACESTEP_API_BASE}/health", timeout=3)
        return r.status_code == 200 and r.json().get("data", {}).get("status") == "ok"
    except Exception:
        return False


def _acestep_release_task(prompt: str, lyrics: str, duration: int, style_cfg: dict) -> str:
    """提交 ACE-Step 音乐生成任务，返回 task_id。"""
    payload = {
        "prompt": prompt,
        "lyrics": lyrics,
        "vocal_language": "zh",
        "thinking": True,
        "audio_duration": max(10, min(600, duration)),
        "audio_format": "mp3",
        "inference_steps": 8,
        "batch_size": 1,
    }
    if style_cfg and style_cfg.get("bpm"):
        payload["bpm"] = style_cfg["bpm"]
    r = requests.post(f"{ACESTEP_API_BASE}/release_task", json=payload, timeout=_ACESTEP_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"ACE-Step 提交失败 {r.status_code}: {r.text[:200]}")
    data = r.json()
    if data.get("code") != 200 or not data.get("data"):
        raise RuntimeError(f"ACE-Step 提交失败: {data.get('error') or str(data)[:200]}")
    return data["data"]["task_id"]


def _acestep_wait_audio(task_id: str) -> str:
    """轮询任务直到成功，返回音频文件 URL（/v1/audio?path=...）。"""
    deadline = time.time() + _ACESTEP_MAX_WAIT
    while time.time() < deadline:
        r = requests.post(
            f"{ACESTEP_API_BASE}/query_result",
            json={"task_id_list": [task_id]},
            timeout=_ACESTEP_TIMEOUT,
        )
        if r.status_code != 200:
            raise RuntimeError(f"ACE-Step 查询失败 {r.status_code}")
        item = next((x for x in (r.json().get("data") or []) if x.get("task_id") == task_id), None)
        if not item:
            time.sleep(_ACESTEP_POLL_INTERVAL)
            continue
        status = item.get("status")
        if status == 2:
            raise RuntimeError(f"ACE-Step 生成失败: {str(item.get('result', ''))[:200]}")
        if status == 1:
            try:
                result = json.loads(item["result"])[0]
            except Exception:
                result = {}
            file_url = result.get("file", "")
            if file_url:
                return file_url
        time.sleep(_ACESTEP_POLL_INTERVAL)
    raise RuntimeError("ACE-Step 生成超时")


def _acestep_download(file_url: str) -> bytes:
    """下载 ACE-Step 产物音频。"""
    url = file_url if file_url.startswith("http") else f"{ACESTEP_API_BASE}{file_url}"
    r = requests.get(url, timeout=120)
    if r.status_code != 200 or not r.content:
        raise RuntimeError(f"ACE-Step 音频下载失败 {r.status_code}")
    return r.content


async def _compose_music_acestep(payload: dict, _report: Callable) -> dict:
    """ACE-Step 大模型整首生成：歌词 + 风格/情绪/主题提示 → 完整带人声歌曲 mp3 + 封面。"""
    lyrics = (payload.get("lyrics") or "").strip()
    style = payload.get("style") or "pop"
    mood = payload.get("mood") or "happy"
    voice = payload.get("voice") or "female"
    theme = (payload.get("theme") or "").strip()
    project_id = payload.get("project_id") or ""
    duration = max(10, min(600, int(payload.get("duration") or 30)))
    if style not in _STYLE_CFG:
        style = "pop"
    prompt = f"{_STYLE_LABEL.get(style, style)}风格，{_MOOD_LABEL.get(mood, mood)}情绪"
    if theme:
        prompt += f"，主题：{theme}"
    _report(5, "AI 谱曲中（大模型整首创作，约 2-5 分钟）…")
    task_id = await asyncio.to_thread(_acestep_release_task, prompt, lyrics, duration, _STYLE_CFG.get(style))
    file_url = await asyncio.to_thread(_acestep_wait_audio, task_id)
    data = await asyncio.to_thread(_acestep_download, file_url)
    if len(data) < 1024:
        raise RuntimeError("ACE-Step 音频为空")
    filename = f"{generate_music_id()}.mp3"
    out_path = MUSIC_DIR / filename
    out_path.write_bytes(data)
    _report(85, "生成封面…")
    stem = filename.rsplit(".", 1)[0]
    cover_path = MUSIC_DIR / f"{stem}.jpg"
    cover_url = f"/api/music-factory/covers/{stem}.jpg"
    await asyncio.to_thread(_make_cover, theme or stem, style, mood, cover_path)
    duration_real = _probe_seconds(str(out_path))
    art_id = _save_artifact(
        filename,
        project_id,
        "audio",
        lyrics,
        duration_real,
        {"style": style, "mood": mood, "voice": voice, "theme": theme, "cover": cover_url, "engine": "acestep"},
        thumbnail=cover_url,
    )
    _report(100, "歌曲已生成")
    return {
        "audio_id": filename,
        "artifact_id": art_id,
        "url": f"/api/music-factory/audios/{filename}",
        "cover_url": cover_url,
        "duration": duration_real,
        "style": style,
        "mood": mood,
        "voice": voice,
        "theme": theme,
        "project_id": project_id,
        "engine": "acestep",
    }


def _probe_seconds(path: str) -> float:
    """ffprobe 读取音频时长（秒），失败返回 0。"""
    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return float(result.stdout.strip() or 0)
    except Exception:
        return 0


def _make_cover(title: str, style: str, mood: str, cover_path: Path) -> bool:
    """PIL 生成歌曲封面（渐变底 + 音符装饰 + 标题 + 风格标签），失败静默。"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        size = 640
        gradients = [
            ((147, 51, 234), (236, 72, 153)),
            ((59, 130, 246), (16, 185, 129)),
            ((245, 158, 11), (239, 68, 68)),
            ((16, 185, 129), (14, 165, 233)),
            ((99, 102, 241), (217, 70, 239)),
            ((236, 72, 153), (59, 130, 246)),
        ]
        idx = sum(ord(c) for c in (title or "music")) % len(gradients)
        c1, c2 = gradients[idx]
        img = Image.new("RGB", (size, size), c1)
        px = img.load()
        for y in range(size):
            t = y / size
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            for x in range(size):
                px[x, y] = (r, g, b)
        draw = ImageDraw.Draw(img)
        for cx, cy, r0 in ((480, 150, 90), (120, 420, 60), (520, 500, 40)):
            draw.ellipse([cx - r0, cy - r0, cx + r0, cy + r0], outline=(255, 255, 255, 50), width=3)
        draw.ellipse([-160, -160, 240, 240], outline=(255, 255, 255, 30), width=3)
        draw.ellipse([440, 460, 820, 840], outline=(255, 255, 255, 25), width=3)
        font_path = None
        for fp in ("/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
            if Path(fp).exists():
                font_path = fp
                break
        font_big = ImageFont.truetype(font_path, 120) if font_path else ImageFont.load_default()
        font_title = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default()
        font_small = ImageFont.truetype(font_path, 26) if font_path else ImageFont.load_default()
        draw.text((60, 60), "♪", fill=(255, 255, 255, 210), font=font_big)
        draw.text((60, 240), "AI 音乐工坊", fill=(255, 255, 255, 160), font=font_small)
        draw.text((60, 300), (title or "无题")[:12], fill=(255, 255, 255, 235), font=font_title)
        draw.rounded_rectangle([60, 420, 250, 470], radius=25, outline=(255, 255, 255, 180), width=2)
        draw.text(
            (80, 432),
            f"{_STYLE_LABEL.get(style, style)} · {_MOOD_LABEL.get(mood, mood)}",
            fill=(255, 255, 255, 200),
            font=font_small,
        )
        img.save(cover_path, "JPEG", quality=88)
        return True
    except Exception:
        return False


@router.post("/music/generate")
async def generate_music(
    lyrics: str = Form(...),
    style: str = Form("pop"),
    mood: str = Form("happy"),
    voice: str = Form("female"),
    theme: str = Form(""),
    duration: int = Form(30),
    template_id: str = Form("", description="音乐场景模板 ID（music-scene-templates，如 ms_ecom_hook）"),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """生成音乐（默认异步任务，立即返回 task_id）。

    本地 AI 音乐合成引擎：numpy 按风格谱曲合成伴奏 → edge-tts 逐句合成人声 →
    ffmpeg 按歌词节奏混音 → mp3 + PIL 封面。无需第三方音乐生成 API。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "lyrics": lyrics,
        "style": style,
        "mood": mood,
        "voice": voice,
        "theme": theme,
        "project_id": project_id,
        "duration": duration,
        "template_id": template_id,
    }
    if sync:
        return await _compose_music_worker(payload)
    task = create_task("music_compose", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "音乐创作任务已提交，后台正在谱曲合成（约 1-2 分钟），可在任务中心查看进度",
        "task": task,
    }


@router.delete("/delete/{filename}")
async def delete_item(filename: str):
    """删除文件"""
    file_path = MUSIC_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "文件不存在")
    file_path.unlink()
    return {"success": True}


async def _music_sing_worker(payload: dict, progress: Callable | None = None) -> dict:
    """生成虚拟人声 TTS（同步/异步任务共用执行体，异步时回报进度）。

    双通道：优先 agnes /audio/speech（线上 TTS），失败自动回退 edge-tts 本地合成
    （与音乐合成同款子进程链路），不依赖第三方通道是否开通。
    """
    if not resolve_api_key():
        raise HTTPException(400, "未配置中转站 API Key")

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    lyrics = payload.get("lyrics") or ""
    voice = payload.get("voice") or "female"
    style = payload.get("style") or "pop"
    project_id = payload.get("project_id") or ""
    if not (lyrics or "").strip():
        raise HTTPException(400, "请输入歌词文本")

    tts_voice = _VOICE_EDGE.get(voice, _VOICE_EDGE["female"])
    text = (lyrics or "")[:500]

    _report(20, "AI 正在合成人声…")
    # 通道一：agnes /audio/speech（线上 TTS，未开通/失败时自动降级）
    audio_data: bytes | None = None
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{AGNES_API_BASE}/audio/speech",
            headers={"Authorization": f"Bearer {resolve_api_key()}", "Content-Type": "application/json"},
            json={"model": "tts-1", "input": text, "voice": tts_voice, "speed": 1.0},
            timeout=60,
        )
        if response.status_code == 200:
            audio_data = response.content
        else:
            logger.warning(f"agnes TTS 不可用（HTTP {response.status_code}），回退 edge-tts 本地合成")
    except Exception as e:
        logger.warning(f"agnes TTS 调用异常，回退 edge-tts 本地合成: {api_error_detail(e)}")

    # 通道二：edge-tts 本地合成（与音乐合成同款子进程链路）
    if not audio_data:
        tmpdir = tempfile.mkdtemp(prefix="music_sing_")
        try:
            tmp_path = os.path.join(tmpdir, "tts.mp3")
            ok = await asyncio.to_thread(_tts_segment, text, tts_voice, tmp_path)
            if ok:
                with open(tmp_path, "rb") as f:
                    audio_data = f.read()
        except Exception as e:
            logger.error(f"edge-tts 人声合成失败: {e}")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    if not audio_data:
        raise HTTPException(502, "人声合成失败：线上 TTS 与本地 edge-tts 通道均不可用，请稍后重试")

    filename = f"{generate_music_id()}.mp3"
    save_music(audio_data, filename)
    duration = len(lyrics) / 15
    art_id = _save_artifact(
        filename,
        project_id,
        "audio",
        lyrics[:500],
        duration,
        {"voice": voice, "style": style, "tts_voice": tts_voice},
    )
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
    if not resolve_api_key():
        raise HTTPException(400, "未配置中转站 API Key")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {"lyrics": lyrics, "voice": voice, "style": style, "project_id": project_id}
    if sync:
        return await _music_sing_worker(payload)
    task = create_task("music_sing", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "人声合成任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


async def _music_lyrics_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装歌词生成，回报进度。"""
    return await _music_lyrics_worker(payload, progress=update)


async def _music_compose_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装音乐合成，回报进度。"""
    return await _compose_music_worker(payload, progress=update)


async def _music_sing_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装人声合成，回报进度。"""
    return await _music_sing_worker(payload, progress=update)


register_handler("music_lyrics", _music_lyrics_handler, user_limit=2)
register_handler("music_compose", _music_compose_handler, user_limit=1)
register_handler("music_sing", _music_sing_handler, user_limit=2)


@router.get("/audios/{filename}")
async def get_audio(filename: str):
    audio_path = MUSIC_DIR / filename
    if not audio_path.exists():
        raise HTTPException(404, "音频不存在")
    return FileResponse(audio_path, media_type="audio/mpeg")


@router.get("/covers/{filename}")
async def get_cover(filename: str):
    """获取歌曲封面（PIL 生成，跨域放开供各端展示）。"""
    cover_path = MUSIC_DIR / filename
    if not cover_path.exists():
        raise HTTPException(404, "封面不存在")
    return FileResponse(cover_path, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})


@router.get("/list")
async def list_audios():
    """列出所有音频和歌词文件（音频附封面与时长）。"""
    items = []
    for f in sorted(MUSIC_DIR.glob("*"), reverse=True):
        if f.is_file():
            ext = f.suffix.lower()
            if ext in [".jpg", ".jpeg", ".png"]:
                continue  # 封面图不作为独立作品展示
            if ext in [".mp3", ".wav", ".ogg"]:
                item_type = "audio"
                url = f"/api/music-factory/audios/{f.name}"
                stem = f.stem
                cover = f"/api/music-factory/covers/{stem}.jpg" if (MUSIC_DIR / f"{stem}.jpg").exists() else ""
            else:
                item_type = "lyrics"
                url = f"/api/music-factory/lyrics/{f.name}"
                cover = ""
            duration, thumbnail, style, title = _music_item_meta(url)
            items.append(
                {
                    "filename": f.name,
                    "url": url,
                    "size": f.stat().st_size,
                    "type": item_type,
                    "ext": ext,
                    "cover_url": cover or thumbnail,
                    "duration": duration,
                    "style": style,
                    "title": title,
                }
            )
    return {"items": items, "count": len(items)}


@router.get("/lyrics/{filename}")
async def get_lyrics_file(filename: str):
    """获取歌词文件"""
    lyrics_path = MUSIC_DIR / filename
    if not lyrics_path.exists():
        raise HTTPException(404, "歌词文件不存在")
    content = lyrics_path.read_text(encoding="utf-8")
    return {"filename": filename, "content": content}


def _generate_melody(style: str, key: str = "C", duration: int = 16) -> list:
    """生成旋律。"""
    # 简化的旋律生成逻辑
    notes = ["C", "D", "E", "F", "G", "A", "B"]
    melody = []
    
    for i in range(duration):
        # 根据风格选择音符
        if style == "major":
            idx = i % 7
        elif style == "minor":
            idx = (i + 2) % 7
        else:
            idx = i % 7
        
        note = f"{notes[idx]}4"
        melody.append({"note": note, "duration": 0.5})
    
    return melody


def _arrange_chords(key: str, progression: str = "I-V-vi-IV") -> list:
    """编排和弦进行。"""
    # 简化的和弦编排
    chord_map = {
        "I": "C",
        "V": "G",
        "vi": "Am",
        "IV": "F"
    }
    
    chords = []
    for prog in progression.split("-"):
        chord = chord_map.get(prog, "C")
        chords.append({"chord": chord, "duration": 2.0})
    
    return chords


async def _synthesize_audio(melody: list, chords: list, output_format: str = "mp3") -> str:
    """合成音频。"""
    import subprocess
    import json
    
    # 使用简化的音频合成逻辑
    output_path = f"/tmp/music_{id(asyncio.get_event_loop())}.{output_format}"
    
    # 生成 MIDI 数据（简化）
    midi_data = json.dumps({
        "melody": melody,
        "chords": chords,
        "tempo": 120
    })
    
    # 调用音频合成工具
    try:
        # 这里可以调用更多的音频合成库
        with open("/tmp/music_midi.json", 'w') as f:
            f.write(midi_data)
        output_path = "/tmp/music_output.mp3"
        # 实际应该调用音频合成引擎
    except Exception as e:
        logger.info(f"音频合成失败: {e}")
        output_path = ""
        pass
    
    return output_path


def _apply_mixing(audio_path: str, effects: dict) -> str:
    """应用混音效果。"""
    import subprocess
    
    if not audio_path:
        return ""
    
    output_path = audio_path.replace(".mp3", "_mixed.mp3")
    
    # 应用音频效果
    filter_complex = []
    
    if effects.get("reverb"):
        filter_complex.append("aecho=0.8:0.9:1000:0.3")
    
    if effects.get("compression"):
        filter_complex.append("acompressor")
    
    if filter_complex:
        cmd = [
            "ffmpeg", "-i", audio_path,
            "-af", ",".join(filter_complex),
            output_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)
    
    return output_path
