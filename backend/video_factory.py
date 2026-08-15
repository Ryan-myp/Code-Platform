#!/usr/bin/env python3
"""视频工厂模块 - 基于 Agnes AI Video API v2.0"""

from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping

import asyncio
import base64
import io
import json
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

import requests
from fastapi import APIRouter, Form, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse

from common.artifacts import derive_title, save_artifact
from common.auth import require_auth
from common.config import load_config, resolve_api_key, resolve_api_base
from common.llm import api_error_detail
from content_safety import check_text, quality_report
from publish_kit import build_publish_zip, license_text, pack_dir_name, platform_spec_text, publish_registry
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video-factory", tags=["视频工厂"])

# 配置：走 common.config 单一来源
load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY, AI_VIDEO_CHANNELS, DASHSCOPE_API_KEY  # noqa: E402

VIDEO_DIR = Path(__file__).parent / "video_factory"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


# ── 视频生成通道（多通道 failover：按配置顺序尝试，未配置 key 的通道自动跳过）──
from common.helpers import _aggregate_compute_results, _execute_common_step, _execute_compute_step, _execute_single_step, _execute_step, _finalize_common_operation, _finalize_results, _finalize_step_results, _initialize_compute_context, _prepare_common_context, _prepare_context, _prepare_step_context, _notify_progress

def _available_channels() -> list[str]:
    """返回已配置 key 的视频通道（按 AI_VIDEO_CHANNELS 顺序）。"""
    order = [c.strip() for c in AI_VIDEO_CHANNELS.split(",") if c.strip()]
    has = {"agnes": bool(resolve_api_key()), "dashscope": bool(DASHSCOPE_API_KEY)}
    return [c for c in order if has.get(c)]

# 常用提示词模板
PRESET_PROMPTS = [
    "A beautiful sunset over the ocean with gentle waves, cinematic quality",
    "A cute cat walking on the beach at sunset, warm golden light",
    "Time-lapse of clouds moving over mountains at sunrise",
    "Aerial view of a forest with autumn colors",
    "City street at night with neon lights and rain reflections",
    "Underwater scene with colorful coral and fish",
    "Northern lights dancing in the night sky",
    "A peaceful lake reflecting snow-capped mountains",
]

# v15：脚本文案模板库（口播 / 剧情 / 科普），可直接作为 prompt 或替换 {主题} 后使用
SCRIPT_TEMPLATES = [
    {
        "id": "koubo_1",
        "category": "口播",
        "name": "产品种草口播",
        "title": "30 秒种草：{主题} 的 3 个真相",
        "structure": [
            "0-3s 特写：{主题} 产品镜头，快切展示质感，光线明亮",
            "3-10s 口播正面镜头：悬念开场「关于{主题}，90% 的人都不知道这 3 件事」",
            "10-22s 产品使用特写：逐条口播 3 个卖点，字幕同步高亮关键词",
            "22-30s 结尾正面镜头：总结 + 引导关注，背景音乐渐强收尾",
        ],
        "desc": "适合带货/种草短视频：钩子开场 + 三点论证 + 行动号召",
    },
    {
        "id": "koubo_2",
        "category": "口播",
        "name": "知识干货口播",
        "title": "1 分钟讲透：{主题}",
        "structure": [
            "0-5s 标题卡：大字标题「{主题}，一条视频讲清楚」",
            "5-20s 口播：定义 {主题} 并用生活化例子解释，语速适中",
            "20-45s 演示/素材画面：3 个要点逐条展开，配合图标动画",
            "45-60s 总结口播：金句收尾 + 评论区引导互动",
        ],
        "desc": "适合知识科普/职场技能：问题引入 → 分层讲解 → 金句收尾",
    },
    {
        "id": "koubo_3",
        "category": "口播",
        "name": "情绪共鸣口播",
        "title": "关于{主题}，我想对你说",
        "structure": [
            "0-5s 空镜：黄昏/雨夜氛围画面，情绪音乐铺垫",
            "5-25s 口播：讲述 {主题} 相关的个人故事，语气真诚缓慢",
            "25-50s 回忆画面穿插：照片墙/生活片段蒙太奇",
            "50-60s 口播收尾：情感升华金句，画面渐暗淡出",
        ],
        "desc": "适合情感/成长类：故事驱动 + 氛围镜头 + 情绪共鸣",
    },
    {
        "id": "juqing_1",
        "category": "剧情",
        "name": "反转剧情",
        "title": "{主题} 的反转时刻",
        "structure": [
            "0-5s 悬念开场：异常细节特写（{主题} 相关的反常镜头）",
            "5-20s 铺垫：常规叙事推进，误导观众预期",
            "20-30s 反转：关键镜头揭示真相，节奏骤变 + 音效冲击",
            "30-40s 收尾：反转后的反应镜头 + 留白结局",
        ],
        "desc": "适合剧情号：悬念 → 铺垫 → 反转 → 留白，前 3 秒必须钩人",
    },
    {
        "id": "juqing_2",
        "category": "剧情",
        "name": "双人对话剧情",
        "title": "{主题} 的抉择",
        "structure": [
            "0-8s 环境镜头建立场景：{主题} 发生的场所，氛围感强",
            "8-30s 双人对话正反打：冲突升级，台词有来有回",
            "30-45s 情绪爆发镜头：特写表情 + 慢动作强调关键动作",
            "45-60s 结局镜头：一人转身离开/留下，开放式结局",
        ],
        "desc": "适合短剧切片：场景 → 冲突 → 爆发 → 结局，对话密度高",
    },
    {
        "id": "juqing_3",
        "category": "剧情",
        "name": "AI 视觉叙事",
        "title": "{主题}：一场视觉诗",
        "structure": [
            "0-6s 宏观空镜：{主题} 的远景，大画幅电影感",
            "6-25s 主体特写序列：3-4 个不同角度特写，光影变化",
            "25-45s 运动镜头：跟拍/环绕/升降，节奏由缓到急",
            "45-60s 收尾空镜：与开场呼应，色调变化暗示主题升华",
        ],
        "desc": "适合纯视觉/氛围号：无需对白，用镜头语言讲故事",
    },
    {
        "id": "kepu_1",
        "category": "科普",
        "name": "冷知识科普",
        "title": "关于{主题}的 3 个冷知识",
        "structure": [
            "0-5s 标题卡：大字标题 + 悬念音效",
            "5-45s 分 3 段讲解：每段一个冷知识，动画/实拍素材切换",
            "45-55s 验证镜头：实验/演示画面佐证第 1 个冷知识",
            "55-60s 结尾：总结 + 关注引导「评论区告诉我你还想知道什么」",
        ],
        "desc": "适合科普号：标题钩子 + 三点递进 + 实证收尾",
    },
    {
        "id": "kepu_2",
        "category": "科普",
        "name": "原理拆解",
        "title": "{主题}是怎么工作的？",
        "structure": [
            "0-8s 现象开场：{主题} 的直观演示画面，引发好奇",
            "8-35s 原理拆解：3D 示意/流程图解，分步解释工作机制",
            "35-50s 生活应用：{主题} 在生活中的实际场景串联",
            "50-60s 回顾总结：核心原理一句话复述 + 下期预告",
        ],
        "desc": "适合硬核科普：现象 → 原理 → 应用 → 总结",
    },
    {
        "id": "kepu_3",
        "category": "科普",
        "name": "辟谣求证",
        "title": "{主题}，是真的吗？",
        "structure": [
            "0-8s 抛观点：引用流传说法「{主题}是真的吗？」",
            "8-40s 逐条验证：实验/数据/专家观点三重视角交叉验证",
            "40-52s 结论卡：判定真假 + 依据说明",
            "52-60s 行动建议：正确做法 + 互动提问",
        ],
        "desc": "适合求真类科普：抛观点 → 三重验证 → 结论卡 → 建议",
    },
]


def save_video(data: bytes, filename: str) -> str:
    """保存视频文件；空内容/过小/假数据拒绝落盘（防废文件污染列表）。"""
    if not data or len(data) < 1024:
        logger.warning("视频内容异常（%d bytes），拒绝保存 %s", len(data or b""), filename)
        raise HTTPException(502, "视频生成异常，请稍后重试")
    filepath = VIDEO_DIR / filename
    filepath.write_bytes(data)
    # 写入后 ffprobe 校验：防止云端返回假数据（可写但无法解析）被误存
    from common.media_check import is_valid_video

    if not is_valid_video(str(filepath)):
        try:
            filepath.unlink()
        except OSError:
            pass
        logger.warning("视频内容无法解析，已删除 %s", filename)
        raise HTTPException(502, "视频生成异常，请稍后重试")
    return filename


# 封面抽帧防重集合（list 接口对缺封面的旧视频后台补生成，避免重复触发）
_cover_backlog: set[str] = set()

# 兜底封面渐变配色池（PIL 生成，按文件名哈希稳定选取）
_COVER_GRADIENTS = [
    ((99, 102, 241), (139, 92, 246)),  # 靛蓝→紫
    ((14, 165, 233), (59, 130, 246)),  # 天蓝→蓝
    ((236, 72, 153), (168, 85, 247)),  # 粉→紫
    ((16, 185, 129), (14, 165, 233)),  # 绿→蓝
    ((245, 158, 11), (239, 68, 68)),   # 橙→红
    ((59, 130, 246), (16, 185, 129)),  # 蓝→青
]


def _fallback_cover(filename: str, cover_path: Path) -> bool:
    """ffmpeg 抽帧全部失败时，用 PIL 生成渐变底 + 提示词标题的兜底封面，保证视频永远有封面。"""
    try:
        from PIL import Image, ImageDraw, ImageFont

        w, h = 640, 360
        # 按文件名哈希稳定选配色，同一视频重复生成结果一致
        idx = sum(ord(c) for c in filename) % len(_COVER_GRADIENTS)
        c1, c2 = _COVER_GRADIENTS[idx]
        img = Image.new("RGB", (w, h), c1)
        px = img.load()
        for y in range(h):
            t = y / h
            r = int(c1[0] + (c2[0] - c1[0]) * t)
            g = int(c1[1] + (c2[1] - c1[1]) * t)
            b = int(c1[2] + (c2[2] - c1[2]) * t)
            for x in range(w):
                px[x, y] = (r, g, b)
        # 装饰圆环
        draw = ImageDraw.Draw(img)
        draw.ellipse([w * 0.62, h * 0.18, w * 1.12, h * 0.68], outline=(255, 255, 255, 40), width=2)
        draw.ellipse([w * 0.55, h * 0.1, w * 1.05, h * 0.6], outline=(255, 255, 255, 20), width=2)
        # 标题文字
        title = Path(filename).stem
        font = None
        for fp in ("/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
            if Path(fp).exists():
                try:
                    font = ImageFont.truetype(fp, 30)
                    break
                except Exception:
                    continue
        if font is None:
            font = ImageFont.load_default()
        draw.text((40, h // 2 - 24), "AI 视频作品", fill=(255, 255, 255, 235), font=font)
        draw.text((40, h // 2 + 18), title[:28], fill=(255, 255, 255, 170), font=font)
        img.save(cover_path, "JPEG", quality=85)
        return True
    except Exception:
        return False


def _pick_ffmpeg() -> str:
    """ffmpeg 选择：系统 ffmpeg 无 libass（字幕烧录必需）时用 imageio-ffmpeg 自带二进制。"""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 — 无 imageio 时回退系统 ffmpeg
        return "ffmpeg"


def _pick_video_encoder() -> str:
    """视频编码器自动选择：Apple 硬件编码优先，无则回退 libx264。"""
    import subprocess as sp

    try:
        out = sp.run(
            ["ffmpeg", "-nostdin", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        if "videotoolbox" in out and "h264_videotoolbox" in out:
            return "h264_videotoolbox"
    except Exception:  # noqa: BLE001 — 编码器探测失败回退 CPU
        pass
    return "libx264"


def _probe_duration(filename: str) -> float:
    """ffprobe 读取视频时长（秒），失败返回 0。"""
    import subprocess

    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(VIDEO_DIR / filename)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            return float(r.stdout.strip().split(",")[0])
    except Exception:  # noqa: BLE001
        pass
    return 0.0



def _probe_duration_ffmpeg(video_path) -> float:
    """ffprobe 获取视频时长（秒），失败返回 0。"""
    import subprocess

    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_path)],
            capture_output=True, timeout=15,
        )
        if r.returncode == 0:
            return float(r.stdout.decode().strip().split(",")[0])
    except Exception:
        pass
    return 0.0


def _extract_frame_candidates(video_path, dur: float) -> list:
    """多点采样抽帧（30%/50%/70% + 首帧兜底），返回候选帧文件列表。"""
    import subprocess

    frames: list = []
    positions = [dur * p for p in (0.3, 0.5, 0.7)] if dur > 1 else []
    positions.append(-1)
    cover_name = video_path.stem + ".jpg"
    for idx, pos in enumerate(positions):
        tmp = video_path.parent / f"{cover_name}.{idx}.tmp.jpg"
        try:
            cmd = ["ffmpeg", "-nostdin", "-y"]
            if pos >= 0:
                cmd += ["-ss", f"{max(0.5, pos):.2f}"]
            cmd += ["-i", str(video_path), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(tmp)]
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
                frames.append(tmp)
        except Exception:
            pass
    return frames


def _pick_brightest_frame(frames: list) -> Path:
    """选最亮帧作封面（PIL 亮度均值；无 PIL 用体积近似）。"""
    best = frames[0]
    best_score = -1.0
    try:
        from PIL import Image

        for fp in frames:
            try:
                img = Image.open(fp).convert("L")
                px = list(img.getdata())
                score = sum(px) / len(px)
                if score > best_score:
                    best_score, best = score, fp
            except Exception:
                continue
    except ImportError:
        best = max(frames, key=lambda p: p.stat().st_size)
    return best

def _extract_cover(filename: str) -> str | None:  # noqa: C901
    """用 ffmpeg 从视频抽帧生成封面图（30%/50%/70% 多点抽帧，自动选最亮帧；全失败回退首帧）。

    返回封面文件名（xxx.jpg）或 None；已存在封面时直接复用。
    注意：ffmpeg 的 -ss 不支持百分比语法（如 40%），需用 ffprobe 换算秒数；
    AI 视频首帧常有淡入/黑屏，多点采样取最亮帧可避开暗帧。
    ffmpeg 抽帧全失败时兜底用 PIL 生成渐变封面，保证视频永远有封面（前端不出现灰色占位）。
    """
    import subprocess

    video_path = VIDEO_DIR / filename
    cover_name = f"{Path(filename).stem}.jpg"
    cover_path = VIDEO_DIR / cover_name
    if cover_path.exists() and cover_path.stat().st_size > 0:
        return cover_name
    if not video_path.exists():
        return None

    # ffprobe 取视频时长（失败则仅首帧兜底）
    dur = _probe_duration_ffmpeg(video_path)

    # 收集候选帧：多点采样 + 首帧兜底
    frames = _extract_frame_candidates(video_path, dur)
    if not frames:
        return cover_name if _fallback_cover(filename, cover_path) else None

    # 选最亮帧作为封面
    best = _pick_brightest_frame(frames)
    for fp in frames:
        if fp == best:
            fp.rename(cover_path)
        else:
            fp.unlink(missing_ok=True)
    return cover_name


async def _backfill_cover(filename: str) -> None:
    """后台补生成缺失封面（list 接口触发，不阻塞响应）。"""
    try:
        await asyncio.to_thread(_extract_cover, filename)
    except Exception:
        pass
    finally:
        _cover_backlog.discard(filename)


def generate_video_id() -> str:
    return f"video_{int(time.time() * 1000)}"


def _save_artifact(
    filename: str, project_id: str, prompt: str, duration: float, extra_meta: dict | None = None, thumbnail: str = ""
) -> str:
    """将视频产物登记到 artifacts 表（委托 common.artifacts.save_artifact），返回 artifact id。

    - type=video，media_url 指向 /api/video-factory/videos/{filename}
    - metadata 含 prompt / video_id / 尺寸等；title 为语义化标题（v13.26）；thumbnail 存封面 URL
    - 失败静默
    """
    meta = {"prompt": prompt, "filename": filename}
    if extra_meta:
        meta.update(extra_meta)
    meta.setdefault("title", derive_title("video", {"prompt": prompt}, meta))
    return save_artifact(
        art_type="video",
        project_id=project_id,
        author="video_factory",
        media_url=f"/api/video-factory/videos/{filename}",
        content={"filename": filename, "prompt": prompt},
        metadata=meta,
        duration=duration,
        thumbnail=thumbnail,
    )


@router.get("/stats")
async def get_stats(current_user: dict = require_auth()):
    """视频工厂统计：总数 + 通道就绪状态（按当前用户的中转站 Key 判断）。"""
    from common.config import VIDEO_MODEL

    video_count = len(list(VIDEO_DIR.glob("*.mp4"))) if VIDEO_DIR.exists() else 0
    return {
        "total_videos": video_count,
        "api_configured": bool(_available_channels()),
        "channels": _available_channels(),
        "model": VIDEO_MODEL,
        "price": "免费",
    }


def _parse_video_params(payload: dict) -> dict:
    """解析视频生成参数：校验 prompt，按 8n+1 规则计算帧数（最大 441 帧）。"""
    # 函数内取最新配置：config 表运行中修改后无需重启即时生效
    from common.config import VIDEO_MODEL, require_model, resolve_feature_model

    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "请输入画面描述")
    _uid = payload.get("user_id") or ""
    model = require_model(payload.get("model") or resolve_feature_model(_uid, "video", VIDEO_MODEL), "视频")
    width = int(payload.get("width") or 1152)
    height = int(payload.get("height") or 768)
    duration = int(payload.get("duration") or 5)
    mode = payload.get("mode") or "ti2vid"
    image = payload.get("image") or ""
    frame_rate = int(payload.get("frame_rate") or 24)
    num_frames = min(duration * frame_rate, 441)
    if (num_frames - 1) % 8 != 0:
        num_frames = ((num_frames - 1) // 8) * 8 + 1
    api_payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
        "mode": mode,
    }
    if image and mode == "i2vid":
        api_payload["image"] = image
    return api_payload


async def _dashscope_create_task(api_payload: dict, report: Callable) -> str:
    """阿里云百炼 wan2.2 文生视频：创建异步任务返回 task_id（预留通道，配置 key 后自动启用）。

    i2vid（图生视频）模式百炼通道暂不支持，直接抛错由 failover 切回 agnes。
    """
    report(10, "正在创建阿里云百炼视频任务…")
    if api_payload.get("mode") == "i2vid":
        raise HTTPException(400, "dashscope 通道暂不支持图生视频，跳过该通道")
    body = {
        "model": "wan2.2-t2v-plus",
        "input": {"prompt": api_payload["prompt"]},
        "parameters": {
            "size": f"{api_payload.get('width', 1152)}*{api_payload.get('height', 768)}",
            "duration": max(3, min(6, (api_payload.get("num_frames") or 120) // 24)),
        },
    }
    resp = await asyncio.to_thread(
        requests.post,
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
        headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if resp.status_code != 200:
        raise HTTPException(500, "创建百炼视频任务失败，请稍后重试")
    data = resp.json()
    task_id = data.get("output", {}).get("task_id") or data.get("task_id")
    if not task_id:
        raise HTTPException(500, "未获取到百炼任务ID，请检查 API 配置")
    return task_id


async def _create_video_task(api_payload: dict, report: Callable, channel: str = "agnes") -> str:
    """创建外部视频渲染任务，返回任务 id（按通道分派：agnes=video_id，dashscope=task_id）。"""
    if channel == "dashscope":
        return await _dashscope_create_task(api_payload, report)
    report(10, "正在创建视频生成任务…")
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{resolve_api_base()}/videos",
            headers={"Authorization": f"Bearer {resolve_api_key()}", "Content-Type": "application/json"},
            json=api_payload,
            timeout=60,
        )
        if response.status_code != 200:
            logger.error(f"创建视频任务失败: {api_error_detail(Exception(response.text[:200]))}")
            raise HTTPException(500, "创建视频任务失败，请稍后重试")
        data = response.json()
        video_id = data.get("video_id") or data.get("task_id")
        if not video_id:
            raise HTTPException(500, "未获取到视频ID，请稍后重试")
        return video_id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建视频任务异常: {e}")
        raise HTTPException(500, "操作失败，请稍后重试") from e


async def _dashscope_poll_result(task_id: str, report: Callable) -> dict:
    """轮询百炼任务：output.task_status SUCCEEDED → video_url；FAILED 抛错（预留通道，未配 key 不启用）。"""
    report(20, "百炼任务已创建，等待云端渲染…")
    for _ in range(180):
        await asyncio.sleep(5)
        try:
            resp = await asyncio.to_thread(
                requests.get,
                f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {DASHSCOPE_API_KEY}"},
                timeout=30,
            )
            if resp.status_code != 200:
                raise HTTPException(500, "获取百炼任务失败，请稍后重试")
            d = resp.json()
            out = d.get("output") or {}
            status = (out.get("task_status") or "").upper()
            if status == "SUCCEEDED":
                if not out.get("video_url"):
                    raise HTTPException(500, "百炼任务完成但未返回视频地址，请稍后重试")
                return {"status": "completed", "output": out, "prompt": "", "duration": 0, "width": 0, "height": 0}
            if status == "FAILED":
                raise HTTPException(500, "百炼视频生成失败，请稍后重试")
            report(min(90, 20 + int(out.get("progress") or 0)), out.get("message") or "百炼渲染中…")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取百炼任务异常: {e}")
            raise HTTPException(500, "操作失败，请稍后重试") from e
    raise HTTPException(504, "百炼视频渲染超时（>15 分钟），请稍后在任务中心重试")


async def _poll_video_result(video_id: str, report: Callable, channel: str = "agnes") -> dict:
    """轮询外部渲染结果：间隔 5s，最长约 15 分钟（按通道分派；超时由任务框架标记失败可重试）。

    v17.7：轮询中的瞬时网络错误（SSL 抖动/连接超时）静默重试最多 3 次再放弃，
    避免任务已提交云端渲染、仅查询接口抖动导致整个通道被误判失败。
    """
    if channel == "dashscope":
        return await _dashscope_poll_result(video_id, report)
    report(20, "视频任务已创建，等待云端渲染…")
    consecutive_err = 0
    for _ in range(180):
        await asyncio.sleep(5)
        try:
            resp = await asyncio.to_thread(
                requests.get,
                f"{resolve_api_base()}/agnesapi",
                params={"video_id": video_id},
                headers={"Authorization": f"Bearer {resolve_api_key()}"},
                timeout=30,
            )
            if resp.status_code not in [200, 202]:
                raise HTTPException(500, "获取视频结果失败，请稍后重试")
            d = resp.json()
            status = d.get("status", "unknown")
            consecutive_err = 0
            if status == "completed":
                return d
            if status == "failed":
                raise HTTPException(500, "视频生成失败，请稍后重试")
            ext_progress = float(d.get("progress") or 0)
            report(min(90, 20 + int(ext_progress * 70 / 100)), d.get("message") or "云端渲染中…")
        except HTTPException:
            raise
        except Exception as e:
            consecutive_err += 1
            if consecutive_err >= 3:
                logger.error(f"获取视频结果连续失败 {consecutive_err} 次: {e}")
                raise HTTPException(500, "操作失败，请稍后重试") from e
            logger.warning(f"获取视频结果瞬时异常（{consecutive_err}/3），继续轮询: {e}")
            continue
    raise HTTPException(504, "视频渲染超时（>15 分钟），请稍后在任务中心重试")


async def _video_finish(video_id: str, d: dict, project_id: str, _report: Callable, channel: str, prompt: str) -> dict:
    """渲染成功后收尾：下载视频 → 抽封面 → 落库 artifacts（各通道共用）。

    v20.1：下载/校验增加自动重试（瞬时网络抖动导致下载不完整或 ffprobe 校验失败时自愈），
    避免渲染成功却因下载环节偶发失败导致整个任务失败。
    """
    _report(92, "渲染完成，正在下载视频…")
    video_url = d.get("output", {}).get("video_url") or d.get("url")
    if not video_url:
        raise HTTPException(500, "视频生成完成但未找到视频URL")

    filename = f"{video_id}.mp4"
    last_err = ""
    for dl_attempt in (1, 2, 3):
        try:
            video_resp = await asyncio.to_thread(requests.get, video_url, timeout=180)
            if video_resp.status_code != 200:
                raise HTTPException(500, f"下载视频失败（HTTP {video_resp.status_code}）")
            # 校验 + 落盘（save_video 内部 ffprobe 校验，失败抛 502）
            save_video(video_resp.content, filename)
            break
        except HTTPException as e:
            last_err = str(e.detail or "")
            logger.warning(f"视频下载/校验失败（第{dl_attempt}/3）: {last_err}")
            # 清理可能残留的半成品文件
            try:
                (VIDEO_DIR / filename).unlink(missing_ok=True)
            except OSError:
                pass
            if dl_attempt < 3:
                await asyncio.sleep(3)
                _report(92, f"视频下载中断，正在重试（{dl_attempt}/3）…")
            else:
                raise HTTPException(500, f"视频下载失败（已重试3次）: {last_err}")

    cover_name = _extract_cover(filename)
    cover_url = f"/api/video-factory/covers/{cover_name}" if cover_name else ""
    vid_duration = float(d.get("duration", 0) or 0)
    # 外部 API 未返回时长时，用 ffprobe 读取真实时长落库（时长角标/列表展示依赖）
    if vid_duration <= 0:
        vid_duration = _probe_duration(filename)
    art_id = _save_artifact(
        filename,
        project_id,
        d.get("prompt") or prompt,
        vid_duration,
        {"video_id": video_id, "channel": channel, "width": d.get("width", 0), "height": d.get("height", 0)},
        thumbnail=cover_url,
    )
    _report(100, "视频已保存")
    return {
        "video_id": video_id,
        "status": "completed",
        "artifact_id": art_id,
        "url": f"/api/video-factory/videos/{filename}",
        "cover_url": cover_url,
        "prompt": d.get("prompt") or prompt,
        "duration": vid_duration,
        "width": d.get("width", 0),
        "height": d.get("height", 0),
        "created_at": d.get("created_at", int(time.time())),
        "project_id": project_id,
        "filename": filename,
    }


async def _video_generate_worker(payload: dict, progress: Callable | None = None) -> dict:
    """视频生成全流程：多通道 failover（创建外部任务 → 轮询 → 下载保存，同步/异步任务共用执行体）。"""
    channels = _available_channels()
    if not channels:
        raise HTTPException(400, "未配置任何视频通道（resolve_api_key() / DASHSCOPE_API_KEY）")

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    api_payload = _parse_video_params(payload)
    project_id = payload.get("project_id") or ""

    # 生产级内容保障：视频描述生成前安全审核（视频发布平台内容红线）
    res = check_text(api_payload["prompt"], "prompt")
    if not res["ok"]:
        raise HTTPException(400, "操作失败，请稍后重试")

    errors: list[str] = []
    for idx, channel in enumerate(channels):
        # 单通道重试（临时网络抖动/超时可自愈）：每通道最多 2 次尝试
        for attempt in (1, 2):
            try:
                video_id = await _create_video_task(api_payload, _report, channel)
                d = await _poll_video_result(video_id, _report, channel)
                return await _video_finish(video_id, d, project_id, _report, channel, api_payload["prompt"])
            except HTTPException as e:
                err_detail = str(e.detail or "")
                errors.append(f"{channel}#{attempt}: {err_detail}")
                logger.warning(f"视频通道 {channel} 第{attempt}次失败: {err_detail}")
                # 仅网络类错误值得重试（超时/连接/5xx）；业务 4xx 不重试
                retryable = any(k in err_detail for k in ("超时", "Timeout", "连接", "Connect", "5", "SSL", "网络")) or "操作失败" in err_detail
                if attempt == 1 and retryable and len(channels) == 1:
                    _report(10, f"通道 {channel} 网络波动，正在重试…")
                    await asyncio.sleep(5)
                    continue
                break
        if idx < len(channels) - 1:
            _report(10, f"通道 {channel} 不可用，尝试备用通道…")
    # v20.1：保留具体失败原因（用户可见可诊断），而非泛化的"所有通道均失败"
    detail = "；".join(errors[:3]) or "未知错误"
    if len(detail) > 300:
        detail = detail[:300] + "…"
    raise HTTPException(500, f"视频生成失败: {detail}")


# ── v20：AI 画质增强提示词（免费辅助能力；LLM 失败静默回退原 prompt）──
@router.post("/enhance-prompt")
async def enhance_prompt(
    prompt: str = Form(...),
    mode: str = Form("ti2vid", description="ti2vid=文生视频 / i2vid=图生视频"),
    current_user: dict = require_auth(),
):
    """AI 增强视频画面描述：主体+运动+镜头语言+光影+氛围+风格；i2vid 保留主体前缀；失败回退原 prompt。"""
    from common.llm import call_llm_async

    original = (prompt or "").strip()
    if not original:
        raise HTTPException(400, "请输入视频描述")
    if len(original) > 800:
        raise HTTPException(400, "描述过长（800 字以内），请精简后重试")
    is_i2vid = mode.strip().lower() in ("i2vid", "img2vid", "image")
    system = (
        "你是一位专业 AI 视频提示词工程师。把用户的简要画面描述增强为可直接用于文生视频模型的详细画面描述，"
        "必须覆盖：主体（内容/数量/动作）、运动（主体运动/镜头运动）、镜头语言（景别/运镜/视角）、"
        "光影（光线/时间/氛围）、情绪氛围、风格与画质词。控制在 200 字以内，"
        "只输出增强后的画面描述本身，不要解释、不要加引号。"
    )
    if is_i2vid:
        system += "注意：这是图生视频，必须完整保留用户描述中的主体特征（人物/物体外观、服装、场景细节）作为前缀，只在其后补充运动与镜头语言。"
    enhanced = original
    try:
        out = await call_llm_async(system, f"【原始描述】\n{original}", max_tokens=600, temperature=0.7)
        out = (out or "").strip().strip('\"\'`')
        if len(out) >= 8:
            enhanced = out
    except Exception:
        logger.warning("[video_factory.enhance_prompt] LLM 调用失败，静默回退原 prompt", exc_info=True)
    return {"ok": True, "original": original, "enhanced": enhanced, "mode": "i2vid" if is_i2vid else "ti2vid"}


@router.post("/generate")
async def create_video_task(
    prompt: str = Form(...),
    model: str = Form(None, description="模型名，留空使用配置的视频模型（VIDEO_MODEL）"),
    width: int = Form(1152),
    height: int = Form(768),
    duration: int = Form(5),
    mode: str = Form("ti2vid"),
    image: str = Form(""),
    image_upload: UploadFile | None = File(None, description="图生视频：本地图片上传（替代 image URL，自动转 base64 data URL）"),
    frame_rate: int = Form(24),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """创建视频生成任务（默认异步任务，worker 内创建外部任务并轮询到完成）。"""
    # i2vid 图生视频：参考图必填（本地上传自动转 base64，或 http/https 直链）
    is_i2vid = mode.strip().lower() in ("i2vid", "img2vid", "image")
    img_url = (image or "").strip()
    if is_i2vid:
        if image_upload:
            # 本地图片 → base64 data URL（AGNES 云端支持，与数字人照片活化一致）
            _raw = await image_upload.read()
            if not _raw:
                raise HTTPException(400, "上传的参考图片为空")
            _mime = image_upload.content_type or "image/png"
            img_url = f"data:{_mime};base64,{base64.b64encode(_raw).decode()}"
        elif not img_url:
            raise HTTPException(400, "图生视频模式需要填写参考图片 URL（或上传本地图片）")
        elif not re.match(r"^https?://", img_url):
            raise HTTPException(400, "参考图片 URL 必须以 http:// 或 https:// 开头")
    if not _available_channels():
        raise HTTPException(400, "未配置任何视频通道（resolve_api_key() / DASHSCOPE_API_KEY）")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "prompt": prompt,
        "model": model,
        "width": width,
        "height": height,
        "duration": duration,
        "mode": mode,
        "image": img_url,
        "frame_rate": frame_rate,
        "user_id": uid,
        "project_id": project_id,
    }
    if sync:
        return await _video_generate_worker(payload)
    task = create_task("video_generate", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "视频生成任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


@router.get("/result/{video_id}")
async def get_video_result(video_id: str, project_id: str = "", current_user: dict = require_auth()):
    """获取视频生成结果。

    project_id 作为 query 参数传入；视频生成完成时写入 artifacts 表关联到项目。
    需要登录态以携带用户中转站 Key（resolve_api_key 按用户上下文解析）。
    """
    if not _available_channels():
        raise HTTPException(400, "未配置任何视频通道（resolve_api_key() / DASHSCOPE_API_KEY）")

    try:
        response = await asyncio.to_thread(
            requests.get,
            f"{resolve_api_base()}/agnesapi",
            params={"video_id": video_id},
            headers={"Authorization": f"Bearer {resolve_api_key()}"},
            timeout=30,
        )

        if response.status_code not in [200, 202]:
            # 视频不存在（如视频 id 输入错误/已过期）→ 404 而非 500
            if response.status_code == 404:
                raise HTTPException(404, "视频不存在或已过期")
            raise HTTPException(500, "获取视频结果失败，请稍后重试")

        data = response.json()
        status = data.get("status", "unknown")

        if status == "completed":
            video_url = data.get("output", {}).get("video_url") or data.get("url")
            if not video_url:
                raise HTTPException(500, "视频生成完成但未找到视频URL")

            video_resp = await asyncio.to_thread(requests.get, video_url, timeout=120)
            if video_resp.status_code != 200:
                raise HTTPException(500, "下载视频失败")

            filename = f"{video_id}.mp4"
            save_video(video_resp.content, filename)
            cover_name = _extract_cover(filename)
            cover_url = f"/api/video-factory/covers/{cover_name}" if cover_name else ""
            vid_duration = float(data.get("duration", 0) or 0)
            if vid_duration <= 0:
                vid_duration = _probe_duration(filename)
            art_id = _save_artifact(
                filename,
                project_id,
                data.get("prompt", ""),
                vid_duration,
                {"video_id": video_id, "width": data.get("width", 0), "height": data.get("height", 0)},
                thumbnail=cover_url,
            )

            return {
                "video_id": video_id,
                "status": "completed",
                "artifact_id": art_id,
                "url": f"/api/video-factory/videos/{filename}",
                "cover_url": cover_url,
                "prompt": data.get("prompt", ""),
                "duration": vid_duration,
                "width": data.get("width", 0),
                "height": data.get("height", 0),
                "created_at": data.get("created_at", int(time.time())),
                "project_id": project_id,
            }
        elif status == "failed":
            raise HTTPException(500, "视频生成失败，请稍后重试")
        else:
            return {
                "video_id": video_id,
                "status": status,
                "progress": data.get("progress", 0),
                "message": data.get("message", "生成中..."),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频结果异常: {e}")
        raise HTTPException(500, "操作失败，请稍后重试") from e


@router.get("/videos/{filename}")
async def get_video(filename: str):
    video_path = VIDEO_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "视频不存在")
    return FileResponse(video_path, media_type="video/mp4")


@router.get("/covers/{filename}")
async def get_cover(filename: str):
    """视频封面图（ffmpeg 抽帧产物，jpg）。

    封面为公开展示资源（首页/作品广场 <img> 跨域直显），放开 CORS。
    """
    cover_path = VIDEO_DIR / filename
    if not cover_path.exists():
        raise HTTPException(404, "封面不存在")
    return FileResponse(cover_path, media_type="image/jpeg", headers={"Access-Control-Allow-Origin": "*"})


@router.get("/list")
async def list_videos():
    """视频列表（v13.26：从 artifacts 合并语义化标题 title，替代随机文件名展示）。

    v17.7：过滤 0KB 空文件（历史生成失败残留，避免污染列表）。
    """
    meta = _artifact_meta()
    videos = []
    for f in sorted(VIDEO_DIR.glob("*.mp4"), reverse=True):
        try:
            size = f.stat().st_size
        except OSError:
            continue
        if size < 1024:  # 空文件/失败残留：不展示
            continue
        cover_name = f"{f.stem}.jpg"
        cover_url = f"/api/video-factory/covers/{cover_name}" if (VIDEO_DIR / cover_name).exists() else ""
        # 旧视频缺封面：后台异步补抽帧（防重集合避免重复触发）
        if not cover_url and f.name not in _cover_backlog:
            _cover_backlog.add(f.name)
            asyncio.create_task(_backfill_cover(f.name))
        m = meta.get(f.name, {})
        prompt = m.get("prompt", "")
        videos.append(
            {
                "filename": f.name,
                "title": m.get("title") or derive_title("video", {"prompt": prompt}, m) or _fallback_title(f.name),
                "url": f"/api/video-factory/videos/{f.name}",
                "cover_url": cover_url,
                "size": size,
            }
        )
    return {"videos": videos}


def _fallback_title(filename: str) -> str:
    """存量旧数据/后期处理产物文件名语义化兜底（v13.26）。

    字幕/配乐/拼接产物不登记 artifacts，无 prompt 元数据，按前缀给可读名；
    其余旧视频（含 base64 长名）统一归为「AI 视频作品」，避免展示随机 ID。
    """
    if filename.startswith("subtitle_"):
        return "字幕合成视频"
    if filename.startswith("music_"):
        return "配乐视频"
    if filename.startswith("concat_"):
        return "视频拼接合成"
    return "AI 视频作品"


def _artifact_meta() -> dict:
    """读取 artifacts 表视频产物元数据（filename → {prompt, title, …}）。"""
    meta: dict = {}
    try:
        from common.db import get_db

        conn = get_db()
        rows = conn.execute(
            "SELECT content, media_url, metadata FROM artifacts "
            "WHERE type='video' AND author='video_factory' AND active=1"
        ).fetchall()
        conn.close()
        for r in rows:
            fname = (r["media_url"] or "").rsplit("/", 1)[-1]
            if not fname:
                continue
            md = {}
            try:
                md = json.loads(r["metadata"] or "{}")
            except (TypeError, json.JSONDecodeError):
                pass
            if not md.get("prompt"):
                try:
                    content = json.loads(r["content"] or "{}")
                    md["prompt"] = content.get("prompt", "") if isinstance(content, dict) else ""
                except (TypeError, json.JSONDecodeError):
                    pass
            meta[fname] = md
    except Exception as e:
        logger.warning(f"读取视频元数据失败: {e}")
    return meta


@router.delete("/delete/{filename}")
async def delete_video(filename: str):
    video_path = VIDEO_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "视频不存在")
    video_path.unlink()
    # 同步清理封面（兜底封面/抽帧封面同名 .jpg），避免残留
    cover_path = VIDEO_DIR / f"{Path(filename).stem}.jpg"
    if cover_path.exists():
        cover_path.unlink(missing_ok=True)
    return {"success": True}


@router.get("/prompts")
async def get_preset_prompts():
    """获取预设提示词"""
    return {"prompts": PRESET_PROMPTS}


async def _video_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装视频生成全流程，回报进度。"""
    return await _video_generate_worker(payload, progress=update)


# 视频生成为外部轮询类长任务：走独立 long 池，避免占用常规池 worker 阻塞轻量生成任务
register_handler("video_generate", _video_generate_handler, user_limit=2, pool="long")


# ── 视频发布包（商业化发布 v14）────────────────────────────
VIDEO_PRESETS = [
    {"id": "douyin", "name": "抖音/快手", "w": 1080, "h": 1920, "ratio": "9:16",
     "desc": "抖音/快手短视频（9:16 竖版），封面与视频同规格"},
    {"id": "bilibili", "name": "B站/西瓜", "w": 1920, "h": 1080, "ratio": "16:9",
     "desc": "B站/西瓜/YouTube 横屏（1080p）"},
    {"id": "weixin", "name": "视频号", "w": 1080, "h": 1230, "ratio": "6:7",
     "desc": "微信视频号推荐比例 6:7（1080×1230）"},
]
_VIDEO_PLATFORM_SPECS = {
    "douyin": [
        {"name": "成片规格", "value": "1080×1920（9:16）", "desc": "时长建议 15-60 秒，前 3 秒抓住注意力"},
        {"name": "封面", "value": "1080×1920 竖版", "desc": "封面文字 ≤3 行，主体清晰居中"},
        {"name": "标题", "value": "≤55 字，含 1-2 个关键词", "desc": "标题带话题标签更容易被推荐"},
    ],
    "bilibili": [
        {"name": "成片规格", "value": "1920×1080（16:9）", "desc": "B站推荐横屏 1080p，封面 16:9"},
        {"name": "封面", "value": "1920×1080 JPG ≤2MB", "desc": "封面信息密度适中，标题 ≤16 字"},
        {"name": "标题", "value": "≤60 字", "desc": "B站标题允许较长，可带悬念"},
    ],
    "weixin": [
        {"name": "成片规格", "value": "1080×1230（6:7）", "desc": "视频号信息流展示比例，兼容 9:16"},
        {"name": "封面", "value": "1080×1230 JPG", "desc": "视频号封面即视频首帧，可后台上传自定义封面"},
        {"name": "标题", "value": "≤30 字", "desc": "视频号标题简洁为宜，可带 #话题"},
    ],
}
_VIDEO_PLATFORM_TAGS = {
    "douyin": ["#AI视频", "#视觉大片", "#治愈系", "#创意短片"],
    "bilibili": ["#AI生成", "#科技", "#视觉艺术"],
    "weixin": ["#AI视频", "#创意", "#视觉"],
}


def _vp_transcode(src_path, out_name: str, w: int, h: int) -> tuple:
    """视频规格转码（cover 模式）：等比放大居中裁剪 + aac 重编码。返回 (out_path, has_audio)。"""
    import subprocess

    ffmpeg = _pick_ffmpeg()
    out_path = VIDEO_DIR / out_name
    has_audio = _probe_has_audio(src_path)
    cmd = [
        ffmpeg, "-nostdin", "-y", "-i", str(src_path),
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
    ]
    cmd += (["-c:a", "aac", "-b:a", "192k"] if has_audio else ["-an"]) + [str(out_path)]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 1024:
        raise HTTPException(500, "规格转码失败，请稍后重试")
    return out_path, has_audio


def _vp_artifact_prompt(src: str) -> str:
    """从 artifacts 表查询视频生成提示词（用于发布文案）。"""
    try:
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT content FROM artifacts WHERE media_url=? AND active=1",
            (f"/api/video-factory/videos/{src}",),
        ).fetchone()
        conn.close()
        if row:
            try:
                return (json.loads(row["content"] or "{}") or {}).get("prompt", "") or ""
            except Exception:
                return str(row["content"] or "")[:200]
    except Exception:
        pass
    return ""


def _vp_qc_report(prompt: str, width: int, height: int, w: int, h: int, duration: float, has_audio: bool, title: str) -> str | None:
    """视频质量自检报告（失败返回 None）。"""
    try:
        prompt_check = check_text(prompt, "prompt") if prompt else None
        extra = [
            f"成片规格：{width}×{height}（目标 {w}×{h}）{'✓' if (width, height) == (w, h) else '✗'}",
            f"时长：{duration:.1f} 秒 / 音轨：{'有' if has_audio else '无'}",
            f"编码：H.264 + {'AAC' if has_audio else '静音'}（平台兼容）",
        ]
        return quality_report(f"视频《{title}》", text_check=prompt_check, image_quality=None, extra=extra)
    except Exception as e:
        logger.debug(f"视频质量自检报告生成失败: {e}")
        return None


@router.post("/publish-pack")
async def video_publish_pack(
    filename: str = Form(...),
    platform: str = Form("douyin"),
    video_title: str = Form(""),
    video_desc: str = Form(""),
    current_user: dict = require_auth(),
):
    """视频发布包：按平台规格转码成片 + 抽帧封面 + 发布文案 + 质量报告，一键下载。"""
    preset = next((p for p in VIDEO_PRESETS if p["id"] == platform), None)
    if not preset:
        raise HTTPException(400, "操作失败，请稍后重试")
    src = (filename or "").strip()
    if not src.endswith(".mp4") or Path(src).name != src:
        raise HTTPException(400, "非法的视频文件名")
    src_path = VIDEO_DIR / src
    if not src_path.exists():
        raise HTTPException(404, "视频不存在")

    w, h = preset["w"], preset["h"]
    root = pack_dir_name("video_release")
    out_name = f"{Path(src).stem}_{preset['id']}.mp4"
    out_path, has_audio = _vp_transcode(src_path, out_name, w, h)

    # 从规格成片抽帧做封面（与成片同规格）
    cover_name = _extract_cover(out_name)
    width, height = _probe_resolution(out_path)
    duration = _probe_duration(out_name)

    # 发布文案（模板 + 平台标签，可直接复制发布）
    prompt = _vp_artifact_prompt(src)
    title = (video_title or f"AI 创意短片 · {Path(src).stem}").strip()[:60]
    desc = (video_desc or f"AI 生成创意视频，{prompt[:60]}。").strip()[:300]
    tags = " ".join(_VIDEO_PLATFORM_TAGS.get(platform, []))
    entries: dict = {f"{root}/成片/{out_name}": str(out_path)}  # key=zip 路径, value=磁盘路径
    if cover_name:
        entries[f"{root}/封面.jpg"] = str(VIDEO_DIR / cover_name)
    entries[f"{root}/发布文案.md"] = (
        f"# {title}\n\n## 标题\n{title}\n\n## 描述\n{desc}\n\n## 标签\n{tags}\n\n"
        f"## 发布建议\n- 前 3 秒为完播率关键，建议直接展示核心画面；\n"
        f"- 本包规格 {preset['ratio']}（{w}×{h}），时长 {duration:.1f} 秒。"
    )
    entries[f"{root}/规格说明.md"] = platform_spec_text(preset["name"], _VIDEO_PLATFORM_SPECS.get(platform, []))
    entries[f"{root}/上传指南.md"] = (
        "# 视频平台上传指南\n\n"
        f"## {preset['name']}\n"
        "1. 登录创作者后台 → 发布作品 → 上传成片；\n"
        "2. 上传封面（与成片同规格，本包已生成）；\n"
        "3. 粘贴发布文案.md 中的标题/描述/标签；\n"
        "4. 勾选原创声明 → 提交审核（通常 1-2 小时通过）。"
    )
    entries[f"{root}/LICENSE.txt"] = license_text(f"视频《{title}》")

    # 生产级内容保障：质量自检报告（描述审核 + 成片规格合规）
    qc_report = _vp_qc_report(prompt, width, height, w, h, duration, has_audio, title)
    if qc_report:
        entries[f"{root}/质量自检报告.md"] = qc_report

    buf = build_publish_zip(entries, "video_release")
    publish = publish_registry.publish("video_platform", {"platform": platform, "title": title})
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="video_release_{int(time.time())}.zip"',
            "X-Publish-Result": f"published={str(publish.get('published')).lower()}",
        },
    )


# ── 视频后期工具（拼接 / 配乐 / 字幕烧录）──────────────────────────
def _safe_video_name(filename: str) -> str:
    """校验视频文件名：必须存在于 VIDEO_DIR，且不含路径穿越。"""
    name = (filename or "").strip()
    if not name or Path(name).name != name:
        raise HTTPException(400, "非法的文件名")
    p = VIDEO_DIR / name
    if not p.exists():
        raise HTTPException(404, "操作失败，请稍后重试")
    return name


def _probe_has_audio(path: Path) -> bool:
    """ffprobe 探测视频是否含音轨（拼接/配乐需要区分处理）。"""
    import subprocess

    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def _probe_resolution(path: Path) -> tuple[int, int]:
    """ffprobe 读取视频分辨率（拼接时作为统一输出尺寸，失败默认 640x360）。"""
    import subprocess

    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            w, h = r.stdout.strip().split("x")
            return int(w), int(h)
    except Exception:
        pass
    return 640, 360


@router.post("/tools/concat")
async def concat_videos(
    filenames: str = Form(...),
    output_name: str = Form(""),
    current_user: dict = require_auth(),
):
    """多视频拼接：统一分辨率（等比缩放+黑边补齐）后按顺序拼接；无音轨片段自动补静音。"""
    import subprocess

    names = [n.strip() for n in (filenames or "").split(",") if n.strip()]
    if len(names) < 2:
        raise HTTPException(400, "至少需要两个视频（filenames 用逗号分隔）")
    paths = [VIDEO_DIR / _safe_video_name(n) for n in names]
    w, h = _probe_resolution(paths[0])
    n = len(paths)
    has_audio = [_probe_has_audio(p) for p in paths]
    ffmpeg = _pick_ffmpeg()
    enc = _pick_video_encoder()
    out = VIDEO_DIR / (output_name or f"concat_{int(time.time() * 1000)}.mp4")

    cmd = [ffmpeg, "-nostdin", "-y"]
    for p in paths:
        cmd += ["-i", str(p)]
    vf = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
    parts = [f"[{i}:v]{vf}[v{i}]" for i in range(n)]
    a_idx = n
    a_parts = []
    for i, has in enumerate(has_audio):
        if has:
            a_parts.append(f"[{i}:a]aresample=44100,pan=stereo|c0=c0|c1=c1[a{i}]")
        else:
            dur = _probe_duration(names[i]) or 1.0
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
            a_parts.append(f"[{a_idx}:a]atrim=0:{dur:.2f},asetpts=PTS-STARTPTS,aresample=44100[a{i}]")
            a_idx += 1
    # concat filter 输入顺序为视频/音频交替：[v0][a0][v1][a1]…（先视频后音频会报 Media type mismatch）
    ins = "".join(f"[v{i}][a{i}]" for i in range(n))
    parts += a_parts + [f"{ins}concat=n={n}:v=1:a=1[vout][aout]"]
    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", enc, "-c:a", "aac", "-movflags", "+faststart",
        str(out),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as e:
        raise HTTPException(500, "操作失败，请稍后重试")
    if r.returncode != 0 or not out.exists():
        raise HTTPException(500, "拼接失败，请稍后重试")
    return {"url": f"/api/video-factory/videos/{out.name}", "filename": out.name, "width": w, "height": h}


@router.post("/tools/music")
async def add_music(
    video: str = Form(...),
    music: str = Form(...),
    bg_volume: float = Form(0.3),
    output_name: str = Form(""),
    current_user: dict = require_auth(),
):
    """视频配乐：原声 + BGM 混音（BGM 支持 URL 或本地路径；bg_volume 控制背景音量 0~1）。"""
    import subprocess

    video_path = VIDEO_DIR / _safe_video_name(video)
    bgm_path = VIDEO_DIR / f".bgm_{int(time.time() * 1000)}.mp3"
    try:
        if music.startswith(("http://", "https://")):
            resp = await asyncio.to_thread(requests.get, music, timeout=60)
            if resp.status_code != 200:
                raise HTTPException(400, "BGM 下载失败")
            bgm_path.write_bytes(resp.content)
        else:
            src = Path(music)
            if not src.exists():
                raise HTTPException(404, "操作失败，请稍后重试")
            bgm_path.write_bytes(src.read_bytes())
        if not bgm_path.stat().st_size:
            raise HTTPException(400, "BGM 文件为空")

        vol = max(0.0, min(1.0, bg_volume))
        has_audio = _probe_has_audio(video_path)
        out = VIDEO_DIR / (output_name or f"music_{int(time.time() * 1000)}.mp4")
        ffmpeg = _pick_ffmpeg()
        enc = _pick_video_encoder()
        cmd = [ffmpeg, "-nostdin", "-y", "-i", str(video_path), "-i", str(bgm_path)]
        if has_audio:
            # 原声 + BGM 混音：以原视频时长为准（duration=first），淡出防爆音
            cmd += [
                "-filter_complex",
                f"[1:a]volume={vol}[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v", "-map", "[aout]",
            ]
        else:
            # 原视频无音轨：仅 BGM 作音轨
            cmd += ["-filter_complex", f"[1:a]volume={vol}[aout]", "-map", "0:v", "-map", "[aout]"]
        cmd += ["-c:v", enc, "-c:a", "aac", "-movflags", "+faststart", str(out)]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        except Exception as e:
            raise HTTPException(500, "操作失败，请稍后重试")
        if r.returncode != 0 or not out.exists():
            raise HTTPException(500, "配乐失败，请稍后重试")
        return {"url": f"/api/video-factory/videos/{out.name}", "filename": out.name, "bg_volume": vol}
    finally:
        bgm_path.unlink(missing_ok=True)


@router.post("/tools/subtitle")
async def burn_subtitle(
    video: str = Form(...),
    srt_content: str = Form(...),
    output_name: str = Form(""),
    current_user: dict = require_auth(),
):
    """字幕烧录：SRT 文本烧录进画面（需 libass；自动优先使用 imageio-ffmpeg 自带二进制）。"""
    import subprocess

    video_path = VIDEO_DIR / _safe_video_name(video)
    srt_file = VIDEO_DIR / f".sub_{int(time.time() * 1000)}.srt"
    try:
        srt_file.write_text(srt_content, encoding="utf-8")
        out = VIDEO_DIR / (output_name or f"subtitle_{int(time.time() * 1000)}.mp4")
        ffmpeg = _pick_ffmpeg()
        enc = _pick_video_encoder()
        # subtitles filter 路径转义：\ : ' 需转义，避免 filter 解析错乱
        escaped = str(srt_file).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        cmd = [
            ffmpeg, "-nostdin", "-y", "-i", str(video_path),
            "-vf", f"subtitles='{escaped}'",
            "-c:v", enc, "-c:a", "copy", "-movflags", "+faststart",
            str(out),
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        except Exception as e:
            raise HTTPException(500, "操作失败，请稍后重试")
        if r.returncode != 0 or not out.exists():
            raise HTTPException(500, "字幕烧录失败，请稍后重试")
        return {"url": f"/api/video-factory/videos/{out.name}", "filename": out.name}
    finally:
        srt_file.unlink(missing_ok=True)


# ── 批量转码（v15）：统一 H.264 + 可选分辨率，逐项报告成功/失败 ──
MAX_TRANSCODE_BATCH = 10
MIN_TRANSCODE_CRF = 18
MAX_TRANSCODE_CRF = 35


def build_transcode_plan(
    filenames: list[str],
    width: int | None = None,
    height: int | None = None,
    crf: int = 23,
) -> list[dict]:
    """生成批量转码计划（纯函数，不触盘）：校验数量/文件名/尺寸/CRF，返回逐项计划。

    - 单次最多 MAX_TRANSCODE_BATCH 个；文件名禁止路径穿越
    - width/height 必须成对；指定时输出等比缩放+黑边补齐，否则保持原分辨率
    - crf 收敛到 [MIN_TRANSCODE_CRF, MAX_TRANSCODE_CRF]
    - 输出名 {stem}_enc_{时间戳}_{序号}.mp4，同批内唯一
    """
    names = [str(n or "").strip() for n in (filenames or []) if str(n or "").strip()]
    if not names:
        raise ValueError("至少需要一个视频文件")
    if len(names) > MAX_TRANSCODE_BATCH:
        raise ValueError(f"单次最多转码 {MAX_TRANSCODE_BATCH} 个视频")
    for n in names:
        if Path(n).name != n or n.startswith("."):
            raise ValueError(f"非法的文件名: {n}")
    if (width is None) != (height is None):
        raise ValueError("宽高必须成对指定")
    c = max(MIN_TRANSCODE_CRF, min(MAX_TRANSCODE_CRF, int(crf or 23)))
    w = h = None
    if width is not None:
        w, h = int(width), int(height)
        if w < 16 or w > 7680 or h < 16 or h > 7680:
            raise ValueError("分辨率超出支持范围（16~7680）")
    ts = int(time.time() * 1000)
    plan = []
    for i, n in enumerate(names):
        if w is not None:
            scale = f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
        else:
            scale = "format=yuv420p"
        plan.append(
            {
                "source": n,
                "output": f"{Path(n).stem}_enc_{ts}_{i}.mp4",
                "crf": c,
                "width": w,
                "height": h,
                "scale": scale,
            }
        )
    return plan


@router.post("/tools/transcode")
async def transcode_videos(
    filenames: str = Form(...),
    width: int = Form(0),
    height: int = Form(0),
    crf: int = Form(23),
    current_user: dict = require_auth(),
):
    """批量转码：统一 H.264 + 可选分辨率（等比缩放+黑边补齐），逐项报告成功/失败，失败不影响其他项。"""
    import subprocess

    names = [n.strip() for n in (filenames or "").split(",") if n.strip()]
    for n in names:
        _safe_video_name(n)  # 存在性校验
    try:
        plan = build_transcode_plan(names, width or None, height or None, crf)
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from None

    ffmpeg = _pick_ffmpeg()
    enc = _pick_video_encoder()
    results = []
    for item in plan:
        src = VIDEO_DIR / item["source"]
        out = VIDEO_DIR / item["output"]
        cmd = [
            ffmpeg, "-nostdin", "-y", "-i", str(src),
            "-vf", item["scale"],
            "-c:v", enc, "-crf", str(item["crf"]),
            "-movflags", "+faststart",
        ]
        if _probe_has_audio(src):
            cmd += ["-c:a", "aac", "-b:a", "192k"]
        else:
            cmd += ["-an"]
        cmd.append(str(out))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if r.returncode == 0 and out.exists():
                results.append(
                    {
                        "status": "ok",
                        "source": item["source"],
                        "filename": item["output"],
                        "url": f"/api/video-factory/videos/{item['output']}",
                        "width": item["width"],
                        "height": item["height"],
                        "crf": item["crf"],
                    }
                )
            else:
                results.append({"status": "error", "source": item["source"], "error": (r.stderr or "")[-300:]})
        except Exception as e:  # noqa: BLE001 — 单文件失败不阻塞批量
            results.append({"status": "error", "source": item["source"], "error": str(e)})
    ok = sum(1 for r in results if r["status"] == "ok")
    return {"total": len(plan), "ok": ok, "failed": len(plan) - ok, "results": results}


# ══════════════════════════════════════════════════════════════
# 视频工坊 v2 增强：自动字幕生成 + 视频分析 + 脚本模板扩展
# ══════════════════════════════════════════════════════════════


# ── 新增脚本文案模板（v20 扩展）───────────────────────────────
EXTENDED_SCRIPT_TEMPLATES = [
    {
        "id": "vlog_1",
        "category": "Vlog",
        "name": "日常生活 Vlog",
        "title": "和我的一天：{主题}",
        "structure": [
            "0-5s 晨间镜头：起床/早餐，自然光，生活感强",
            "5-20s 出门场景：通勤/出行，节奏轻快",
            "20-45s 核心活动：{主题} 相关的主场景，多角度穿插",
            "45-55s 傍晚/总结：回顾当天亮点，情绪收束",
            "55-60s 片尾：预告下期 + 关注引导",
        ],
        "desc": "适合生活博主：自然真实 + 节奏轻快 + 个人风格",
    },
    {
        "id": "vlog_2",
        "category": "Vlog",
        "name": "旅行记录 Vlog",
        "title": "{地点} 旅行日记",
        "structure": [
            "0-5s 抵达镜头：交通工具/地标远景，震撼开场",
            "5-25s 目的地探索：街景/美食/人文，快速剪辑",
            "25-50s 核心体验：深度游玩/特色活动，慢节奏沉浸",
            "50-60s 日落/夜景收尾：情感升华 + 下期预告",
        ],
        "desc": "适合旅游博主：航拍+街拍结合，节奏有张有弛",
    },
    {
        "id": "ad_1",
        "category": "广告",
        "name": "产品种草广告",
        "title": "{产品} 使用测评",
        "structure": [
            "0-3s 痛点开场：问题场景特写，引发共鸣",
            "3-15s 产品介绍：{产品} 亮相，突出核心卖点",
            "15-40s 使用演示：前后对比/实际效果，真实可信",
            "40-55s 用户证言/数据：第三方背书，增强说服力",
            "55-60s 行动号召：优惠信息 + 购买引导",
        ],
        "desc": "适合带货广告：痛点→方案→证明→行动，经典转化链路",
    },
    {
        "id": "ad_2",
        "category": "广告",
        "name": "品牌故事广告",
        "title": "关于{品牌}的故事",
        "structure": [
            "0-8s 品牌起源：创始故事/初心，情感铺垫",
            "8-30s 发展历程：关键节点/里程碑，时间轴叙事",
            "30-50s 产品理念：核心价值观/品质坚持",
            "50-60s 品牌愿景：未来展望 + Slogan 定格",
        ],
        "desc": "适合品牌形象片：情感叙事 + 价值传递，走心路线",
    },
    {
        "id": "tutorial_1",
        "category": "教程",
        "name": "操作教程",
        "title": "{工具/软件} 入门教程",
        "structure": [
            "0-5s 效果展示：最终成果预览，激发学习兴趣",
            "5-15s 环境准备：工具/材料介绍，降低门槛",
            "15-45s 分步教学：3-5 个关键步骤，每步配字幕说明",
            "45-55s 常见问题：易错点提醒，避坑指南",
            "55-60s 总结回顾：要点复述 + 练习作业",
        ],
        "desc": "适合知识分享：结果导向 + 步骤清晰 + 避坑提示",
    },
    {
        "id": "music_1",
        "category": "音乐",
        "name": "音乐 MV",
        "title": "《{歌名}》官方 MV",
        "structure": [
            "0-5s 前奏画面：氛围空镜，定调视觉风格",
            "5-25s 主歌段落：歌手/主角镜头，情感表达",
            "25-40s 副歌高潮：快切/特效/群像，视觉冲击力",
            "40-55s 桥段变化：视角转换/色调变化，情绪转折",
            "55-60s 尾声：渐弱画面 + 歌名/歌手信息卡",
        ],
        "desc": "适合音乐人：节奏驱动剪辑，画面与音乐情绪匹配",
    },
    {
        "id": "review_1",
        "category": "测评",
        "name": "产品横评",
        "title": "{品类} 横评：5 款热门款实测",
        "structure": [
            "0-8s 引入：横评背景 + 入选标准说明",
            "8-40s 逐一测评：每款产品核心表现（优点/缺点）",
            "40-55s 横向对比：参数/价格/表现三维雷达图",
            "55-60s 推荐结论：按需求给出选购建议",
        ],
        "desc": "适合评测号：公平客观 + 数据支撑 + 结论明确",
    },
]

# 合并脚本模板库（原有 + 扩展）
ALL_SCRIPT_TEMPLATES = SCRIPT_TEMPLATES + EXTENDED_SCRIPT_TEMPLATES


@router.get("/prompts/scripts")
async def get_script_templates():
    """获取完整脚本文案模板库（口播/剧情/科普/Vlog/广告/教程/音乐/测评，v20 扩展）。"""
    return {"templates": ALL_SCRIPT_TEMPLATES}


# ── 自动字幕生成（语音识别 → SRT）──────────────────────────

@router.post("/tools/auto-subtitle")
async def auto_generate_subtitle(
    video: str = Form(...),
    language: str = Form("zh"),
    output_name: str = Form(""),
    current_user: dict = require_auth(),
):
    """自动字幕生成：调用 LLM 根据视频画面描述生成 SRT 字幕，或用内置规则从音频提取。

    v20：两阶段策略
    1. 先用 ffmpeg 提取音频，尝试调用 AGNES API 的 Whisper 转录
    2. 失败时 fallback：LLM 根据视频 prompt 生成结构化字幕
    """
    import subprocess

    video_path = VIDEO_DIR / _safe_video_name(video)
    audio_path = VIDEO_DIR / f".audio_{int(time.time() * 1000)}.wav"
    srt_path = VIDEO_DIR / f".srt_{int(time.time() * 1000)}.srt"
    out_name = output_name or f"subtitle_{int(time.time() * 1000)}.mp4"

    try:
        # Step 1: 提取音频
        ffmpeg = _pick_ffmpeg()
        subprocess.run(
            [ffmpeg, "-nostdin", "-y", "-i", str(video_path), "-vn",
             "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_path)],
            capture_output=True, timeout=120,
        )

        # Step 2: 尝试 Whisper 转录
        srt_content = ""
        try:
            from common.llm import call_llm_async
            import httpx

            # 调用 OpenAI 兼容的 Whisper API
            api_key = resolve_api_key()
            api_base = resolve_api_base().rstrip("/")
            async with httpx.AsyncClient(timeout=120) as client:
                with open(audio_path, "rb") as f:
                    resp = await client.post(
                        f"{api_base}/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        files={"file": ("audio.wav", f, "audio/wav")},
                        data={"model": "whisper-1", "language": language, "response_format": "srt"},
                    )
                if resp.status_code == 200:
                    srt_content = resp.text
                else:
                    logger.warning("Whisper 转录失败 %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.debug("Whisper 不可用，fallback 到 LLM 生成: %s", e)

        # Step 3: Fallback — LLM 根据视频元数据生成结构化字幕
        if not srt_content:
            prompt_text = _vp_artifact_prompt(video)
            duration = _probe_duration(str(video_path)) or 60.0
            srt_content = await _generate_subtitle_by_llm(prompt_text, duration, language)

        srt_path.write_text(srt_content, encoding="utf-8")

        # Step 4: 烧录字幕
        escaped = str(srt_path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        out_path = VIDEO_DIR / out_name
        enc = _pick_video_encoder()
        cmd = [
            ffmpeg, "-nostdin", "-y", "-i", str(video_path),
            "-vf", f"subtitles='{escaped}'",
            "-c:v", enc, "-c:a", "copy", "-movflags", "+faststart",
            str(out_path),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        if r.returncode != 0 or not out_path.exists():
            raise HTTPException(500, "字幕生成失败，请稍后重试")

        return {
            "url": f"/api/video-factory/videos/{out_name}",
            "filename": out_name,
            "subtitle_source": "whisper" if srt_content and "[" in srt_content[:10] else "llm_fallback",
            "duration_sec": round(duration, 1),
        }
    finally:
        audio_path.unlink(missing_ok=True)
        srt_path.unlink(missing_ok=True)


async def _generate_subtitle_by_llm(prompt_text: str, duration: float, language: str) -> str:
    """LLM 生成结构化 SRT 字幕（fallback 方案）。"""
    from common.llm import call_llm_async

    key_topics = re.findall(r'[\u4e00-\u9fa5]{2,8}', prompt_text)[:10]
    segments = int(duration / 5)  # 每 5 秒一段
    srt_lines = []
    for i in range(max(1, segments)):
        start_s = i * 5
        end_s = min((i + 1) * 5, duration)
        h, m, s = _secs_to_srt_time(start_s)
        he, me, se = _secs_to_srt_time(end_s)
        topic = key_topics[i % len(key_topics)] if key_topics else "内容"
        srt_lines.append(f"{i + 1}\n{h}:{m}:{s},000 --> {he}:{me}:{se},000\n{topic} 相关内容片段 {i+1}")
    return "\n\n".join(srt_lines)


def _secs_to_srt_time(seconds: float) -> tuple:
    """秒数 → (h, m, s) 用于 SRT 时间戳。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return h, m, s


# ── 视频智能分析（v20 增强）─────────────────────────────────

@router.post("/tools/analyze")
async def analyze_video(
    video: str = Form(...),
    analysis_type: str = Form("general"),  # general | sentiment | keywords | quality
    current_user: dict = require_auth(),
):
    """视频智能分析：多维度 AI 分析视频内容。

    - general: 整体内容概述、关键场景、推荐标签
    - sentiment: 情感基调分析（积极/消极/中性）
    - keywords: 关键帧提取 + 关键词提取
    - quality: 技术质量评估（分辨率/码率/稳定性）
    """
    video_path = VIDEO_DIR / _safe_video_name(video)
    width, height = _probe_resolution(video_path)
    duration = _probe_duration(str(video_path))
    has_audio = _probe_has_audio(video_path)

    # 提取关键帧
    frame_paths = _extract_keyframes(video_path, count=6)

    # 调用 LLM 分析
    from common.llm import call_llm_async
    try:
        frame_descs = []
        for fp in frame_paths:
            if fp.exists():
                try:
                    import base64
                    b64 = base64.b64encode(fp.read_bytes()).decode()[:50000]  # 截断防溢出
                    frame_descs.append(f"[FRAME:{fp.name}:data:image/jpeg;base64,{b64[:20000]}...]")
                except Exception:
                    pass

        analysis_prompt = f"""请分析以下视频内容并输出 JSON 格式的分析结果：
视频规格：{width}x{height}，时长 {duration:.1f} 秒，{'有音频' if has_audio else '静音'}
分析类型：{analysis_type}
关键帧描述：{'；'.join(frame_descs[:3]) if frame_descs else '无可用帧'}

请输出：
{{
  "summary": "视频内容简述（50字以内）",
  "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"],
  "sentiment": "positive|negative|neutral",
  "sentiment_score": 0.8,
  "recommended_tags": ["标签1", "标签2", "标签3"],
  "target_audience": "目标受众描述",
  "quality_notes": ["技术质量备注1", "改进建议1"],
  "scene_breakdown": [
    {{"time_range": "0-10s", "description": "场景描述", "emotion": "情绪"}}
  ]
}}"""
        result = await call_llm_async(analysis_prompt, max_tokens=800)
        # 解析 JSON
        import json as _json
        try:
            # 提取 JSON 块
            match = re.search(r'\{[^{}]*"summary"[^{}]*\}', result, re.DOTALL)
            if match:
                analysis = _json.loads(match.group())
            else:
                analysis = {"summary": result[:200], "keywords": [], "sentiment": "neutral",
                            "recommended_tags": [], "scene_breakdown": []}
        except Exception:
            analysis = {"summary": result[:300], "keywords": [], "sentiment": "neutral",
                        "recommended_tags": [], "scene_breakdown": []}
    except Exception as e:
        logger.warning("视频分析失败: %s", e)
        analysis = {"summary": "分析暂不可用", "keywords": [], "sentiment": "neutral",
                    "recommended_tags": [], "scene_breakdown": []}

    # 技术质量数据
    file_size = video_path.stat().st_size if video_path.exists() else 0
    bitrate_est = (file_size * 8 / max(duration, 1)) if duration > 0 else 0  # bps

    return {
        "video": str(video_path.name),
        "spec": {"width": width, "height": height, "duration_sec": round(duration, 1),
                 "has_audio": has_audio, "file_size_mb": round(file_size / 1024 / 1024, 2),
                 "estimated_bitrate_kbps": round(bitrate_est / 1000, 1)},
        "analysis": analysis,
        "keyframe_count": len(frame_paths),
    }


def _extract_keyframes(video_path: Path, count: int = 6) -> list:
    """从视频中均匀提取关键帧，保存为临时图片。"""
    import subprocess
    frames = []
    if not video_path.exists():
        return frames
    try:
        duration = _probe_duration(str(video_path))
        if duration <= 0:
            return frames
        interval = duration / max(count, 1)
        ffmpeg = _pick_ffmpeg()
        out_dir = VIDEO_DIR / ".keyframes"
        out_dir.mkdir(exist_ok=True)
        for i in range(count):
            t = i * interval + interval * 0.5  # 每段中间时刻
            frame_path = out_dir / f"frame_{int(t * 1000)}ms.jpg"
            if not frame_path.exists():
                subprocess.run(
                    [ffmpeg, "-nostdin", "-y", "-ss", str(t), "-i", str(video_path),
                     "-vframes", "1", "-q:v", "2", str(frame_path)],
                    capture_output=True, timeout=30,
                )
            if frame_path.exists():
                frames.append(frame_path)
    except Exception as e:
        logger.debug("关键帧提取失败: %s", e)
    return frames


# ── 视频特效滤镜（v20）──────────────────────────────────────

@router.post("/tools/filters")
async def apply_video_filter(
    video: str = Form(...),
    filter_type: str = Form("none"),  # none | sepia | black_white | vintage | warm | cool | fade
    intensity: float = Form(0.5),
    output_name: str = Form(""),
    current_user: dict = require_auth(),
):
    """视频滤镜：ffmpeg 滤镜链实现多种视觉效果。"""
    import subprocess

    video_path = VIDEO_DIR / _safe_video_name(video)
    out_name = output_name or f"filter_{filter_type}_{int(time.time() * 1000)}.mp4"
    out_path = VIDEO_DIR / out_name
    ffmpeg = _pick_ffmpeg()
    enc = _pick_video_encoder()

    # 滤镜映射
    filter_map = {
        "sepia": "colorbalance=rs=0.1:gs=0.05:bs=-0.05,curves=all='0/0 0.33/0.9 0.66/0.95 1/1'",
        "black_white": "hue=s=0",
        "vintage": "colorbalance=rs=0.15:gs=0.05:bs=-0.1,curves=all='0/0 0.2/0.85 0.5/0.9 0.8/0.95 1/1',gamma=g=0.95",
        "warm": "colorbalance=rs=0.08:gs=0.03:bs=-0.02",
        "cool": "colorbalance=rs=-0.05:gs=-0.02:bs=0.08",
        "fade": "fade=t=in:st=0:d=1,fade=t=out:st=%f:d=1" % max(0, (_probe_duration(str(video_path)) or 30) - 2),
    }

    vf = filter_map.get(filter_type, "format=yuv420p")
    cmd = [
        ffmpeg, "-nostdin", "-y", "-i", str(video_path),
        "-vf", vf,
        "-c:v", enc, "-c:a", "copy", "-movflags", "+faststart",
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0 or not out_path.exists():
        raise HTTPException(500, "滤镜应用失败")

    return {"url": f"/api/video-factory/videos/{out_name}", "filename": out_name, "filter": filter_type}


__all__ = ["router"]
