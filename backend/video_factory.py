#!/usr/bin/env python3
"""视频工厂模块 - 基于 Agnes AI Video API v2.0"""

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

import requests
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import FileResponse

from common.artifacts import save_artifact
from common.auth import require_auth
from common.config import load_config
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video-factory", tags=["视频工厂"])

# 配置：走 common.config 单一来源
load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY  # noqa: E402

VIDEO_DIR = Path(__file__).parent / "video_factory"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

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


def save_video(data: bytes, filename: str) -> str:
    filepath = VIDEO_DIR / filename
    filepath.write_bytes(data)
    return filename


def generate_video_id() -> str:
    return f"video_{int(time.time() * 1000)}"


def _save_artifact(filename: str, project_id: str, prompt: str, duration: float,
                   extra_meta: dict | None = None) -> str:
    """将视频产物登记到 artifacts 表（委托 common.artifacts.save_artifact），返回 artifact id。

    - type=video，media_url 指向 /api/video-factory/videos/{filename}
    - metadata 含 prompt / video_id / 尺寸等
    - 失败静默
    """
    meta = {"prompt": prompt, "filename": filename}
    if extra_meta:
        meta.update(extra_meta)
    return save_artifact(
        art_type="video", project_id=project_id, author="video_factory",
        media_url=f"/api/video-factory/videos/{filename}",
        content={"filename": filename, "prompt": prompt}, metadata=meta, duration=duration,
    )


@router.get("/stats")
async def get_stats():
    video_count = len(list(VIDEO_DIR.glob("*.mp4"))) if VIDEO_DIR.exists() else 0
    return {
        "total_videos": video_count,
        "api_configured": bool(AGNES_API_KEY),
        "model": "agnes-video-v2.0",
        "price": "免费",
    }


def _parse_video_params(payload: dict) -> dict:
    """解析视频生成参数：校验 prompt，按 8n+1 规则计算帧数（最大 441 帧）。"""
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "请输入画面描述")
    model = payload.get("model") or "agnes-video-v2.0"
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


async def _create_video_task(api_payload: dict, report: Callable) -> str:
    """创建外部视频渲染任务，返回 video_id。"""
    report(10, "正在创建视频生成任务…")
    try:
        response = await asyncio.to_thread(
            requests.post,
            f"{AGNES_API_BASE}/videos",
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json=api_payload,
            timeout=60,
        )
        if response.status_code != 200:
            logger.error(f"创建视频任务失败: {response.text}")
            raise HTTPException(500, f"创建视频任务失败: {response.text}")
        data = response.json()
        video_id = data.get("video_id") or data.get("task_id")
        if not video_id:
            raise HTTPException(500, f"未获取到视频ID: {data}")
        return video_id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建视频任务异常: {e}")
        raise HTTPException(500, f"创建视频任务失败: {str(e)}") from e


async def _poll_video_result(video_id: str, report: Callable) -> dict:
    """轮询外部渲染结果：间隔 5s，最长约 15 分钟（超时由任务框架标记失败可重试）。"""
    report(20, "视频任务已创建，等待云端渲染…")
    for _ in range(180):
        await asyncio.sleep(5)
        try:
            resp = await asyncio.to_thread(
                requests.get,
                f"{AGNES_API_BASE}/agnesapi",
                params={"video_id": video_id},
                headers={"Authorization": f"Bearer {AGNES_API_KEY}"},
                timeout=30,
            )
            if resp.status_code not in [200, 202]:
                raise HTTPException(500, f"获取视频结果失败: {resp.text}")
            d = resp.json()
            status = d.get("status", "unknown")
            if status == "completed":
                return d
            if status == "failed":
                raise HTTPException(500, f"视频生成失败: {d.get('error', 'unknown')}")
            ext_progress = float(d.get("progress") or 0)
            report(min(90, 20 + int(ext_progress * 70 / 100)), d.get("message") or "云端渲染中…")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取视频结果异常: {e}")
            raise HTTPException(500, f"获取视频结果失败: {str(e)}") from e
    raise HTTPException(504, "视频渲染超时（>15 分钟），请稍后在任务中心重试")


async def _video_generate_worker(payload: dict, progress: Callable | None = None) -> dict:
    """视频生成全流程：创建外部任务 → 轮询 → 下载保存（同步/异步任务共用执行体）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    api_payload = _parse_video_params(payload)
    project_id = payload.get("project_id") or ""
    video_id = await _create_video_task(api_payload, _report)
    d = await _poll_video_result(video_id, _report)

    _report(92, "渲染完成，正在下载视频…")
    video_url = d.get("output", {}).get("video_url") or d.get("url")
    if not video_url:
        raise HTTPException(500, "视频生成完成但未找到视频URL")
    video_resp = await asyncio.to_thread(requests.get, video_url, timeout=120)
    if video_resp.status_code != 200:
        raise HTTPException(500, "下载视频失败")

    filename = f"{video_id}.mp4"
    save_video(video_resp.content, filename)
    vid_duration = float(d.get("duration", 0) or 0)
    art_id = _save_artifact(filename, project_id, d.get("prompt", ""), vid_duration,
                            {"video_id": video_id, "width": d.get("width", 0), "height": d.get("height", 0)})
    _report(100, "视频已保存")
    return {
        "video_id": video_id,
        "status": "completed",
        "artifact_id": art_id,
        "url": f"/api/video-factory/videos/{filename}",
        "prompt": d.get("prompt", ""),
        "duration": vid_duration,
        "width": d.get("width", 0),
        "height": d.get("height", 0),
        "created_at": d.get("created_at", int(time.time())),
        "project_id": project_id,
        "filename": filename,
    }


@router.post("/generate")
async def create_video_task(
    prompt: str = Form(...),
    model: str = Form("agnes-video-v2.0"),
    width: int = Form(1152),
    height: int = Form(768),
    duration: int = Form(5),
    mode: str = Form("ti2vid"),
    image: str = Form(""),
    frame_rate: int = Form(24),
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """创建视频生成任务（默认异步任务，worker 内创建外部任务并轮询到完成）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "prompt": prompt, "model": model, "width": width, "height": height,
        "duration": duration, "mode": mode, "image": image,
        "frame_rate": frame_rate, "project_id": project_id,
    }
    if sync:
        return await _video_generate_worker(payload)
    task = create_task("video_generate", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"], "status": "pending",
        "message": "视频生成任务已提交，后台执行中，可在任务中心查看进度", "task": task,
    }


@router.get("/result/{video_id}")
async def get_video_result(video_id: str, project_id: str = ""):
    """获取视频生成结果。

    project_id 作为 query 参数传入；视频生成完成时写入 artifacts 表关联到项目。
    """
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    try:
        response = requests.get(
            f"{AGNES_API_BASE}/agnesapi",
            params={"video_id": video_id},
            headers={"Authorization": f"Bearer {AGNES_API_KEY}"},
            timeout=30,
        )

        if response.status_code not in [200, 202]:
            raise HTTPException(500, f"获取视频结果失败: {response.text}")

        data = response.json()
        status = data.get("status", "unknown")

        if status == "completed":
            video_url = data.get("output", {}).get("video_url") or data.get("url")
            if not video_url:
                raise HTTPException(500, "视频生成完成但未找到视频URL")

            video_resp = requests.get(video_url, timeout=120)
            if video_resp.status_code != 200:
                raise HTTPException(500, "下载视频失败")

            filename = f"{video_id}.mp4"
            save_video(video_resp.content, filename)
            vid_duration = float(data.get("duration", 0) or 0)
            art_id = _save_artifact(filename, project_id, data.get("prompt", ""), vid_duration,
                                    {"video_id": video_id, "width": data.get("width", 0),
                                     "height": data.get("height", 0)})

            return {
                "video_id": video_id,
                "status": "completed",
                "artifact_id": art_id,
                "url": f"/api/video-factory/videos/{filename}",
                "prompt": data.get("prompt", ""),
                "duration": vid_duration,
                "width": data.get("width", 0),
                "height": data.get("height", 0),
                "created_at": data.get("created_at", int(time.time())),
                "project_id": project_id,
            }
        elif status == "failed":
            raise HTTPException(500, f"视频生成失败: {data.get('error', 'unknown')}")
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
        raise HTTPException(500, f"获取视频结果失败: {str(e)}") from e


@router.get("/videos/{filename}")
async def get_video(filename: str):
    video_path = VIDEO_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "视频不存在")
    return FileResponse(video_path, media_type="video/mp4")


@router.get("/list")
async def list_videos():
    videos = []
    for f in sorted(VIDEO_DIR.glob("*.mp4"), reverse=True):
        videos.append({
            "filename": f.name,
            "url": f"/api/video-factory/videos/{f.name}",
            "size": f.stat().st_size,
        })
    return {"videos": videos}


@router.delete("/delete/{filename}")
async def delete_video(filename: str):
    video_path = VIDEO_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "视频不存在")
    video_path.unlink()
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
