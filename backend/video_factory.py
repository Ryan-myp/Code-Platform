#!/usr/bin/env python3
"""视频工厂模块 - 基于 Agnes AI Video API v2.0"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse

from common.config import load_config
from common.db import get_db

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
    """将视频产物登记到 artifacts 表，返回 artifact id。

    - type=video，media_url 指向 /api/video-factory/videos/{filename}
    - metadata 含 prompt / video_id / 尺寸等
    - 失败静默
    """
    art_id = f"art_{uuid.uuid4().hex[:12]}"
    meta = {"prompt": prompt, "filename": filename}
    if extra_meta:
        meta.update(extra_meta)
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO artifacts
               (id, project_id, type, content, version, author, created_at, active, media_url, duration, metadata)
               VALUES (?, ?, 'video', ?, 'v1', 'video_factory', ?, 1, ?, ?, ?)""",
            (art_id, project_id or "", json.dumps({"filename": filename, "prompt": prompt}, ensure_ascii=False),
             datetime.now().isoformat(), f"/api/video-factory/videos/{filename}",
             float(duration or 0), json.dumps(meta, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"_save_artifact skipped: {e}")
    return art_id


@router.get("/stats")
async def get_stats():
    video_count = len(list(VIDEO_DIR.glob("*.mp4"))) if VIDEO_DIR.exists() else 0
    return {
        "total_videos": video_count,
        "api_configured": bool(AGNES_API_KEY),
        "model": "agnes-video-v2.0",
        "price": "免费",
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
):
    """创建视频生成任务"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    # 计算帧数 (8n+1 规则，最大 441 帧)
    num_frames = min(duration * frame_rate, 441)
    if (num_frames - 1) % 8 != 0:
        num_frames = ((num_frames - 1) // 8) * 8 + 1

    payload = {
        "model": model,
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": num_frames,
        "frame_rate": frame_rate,
        "mode": mode,
    }

    if image and mode == "i2vid":
        payload["image"] = image

    try:
        response = requests.post(
            f"{AGNES_API_BASE}/videos",
            headers={
                "Authorization": f"Bearer {AGNES_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(f"创建视频任务失败: {response.text}")
            raise HTTPException(500, f"创建视频任务失败: {response.text}")

        data = response.json()
        video_id = data.get("video_id") or data.get("task_id")
        if not video_id:
            raise HTTPException(500, f"未获取到视频ID: {data}")

        return {
            "video_id": video_id,
            "status": "pending",
            "prompt": prompt,
            "model": model,
            "width": width,
            "height": height,
            "duration": duration,
            "mode": mode,
            "project_id": project_id,
            "estimated_time": duration * 10,  # 估算时间
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建视频任务异常: {e}")
        raise HTTPException(500, f"创建视频任务失败: {str(e)}") from e


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
