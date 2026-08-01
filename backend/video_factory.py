#!/usr/bin/env python3
"""视频工厂模块 - 基于 Agnes AI Video API"""

import base64
import io
import json
import os
import time
import logging
from pathlib import Path
from typing import Any

import requests
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/video-factory", tags=["视频工厂"])

AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://api.agnes-ai.cn/v1")

VIDEO_DIR = Path(__file__).parent / "video_factory"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def save_video(data: bytes, filename: str) -> str:
    """保存视频文件"""
    filepath = VIDEO_DIR / filename
    filepath.write_bytes(data)
    return filename


def generate_video_id() -> str:
    """生成唯一视频ID"""
    return f"video_{int(time.time() * 1000)}"


@router.get("/stats")
async def get_stats():
    """获取视频统计"""
    video_count = len(list(VIDEO_DIR.glob("*.mp4"))) if VIDEO_DIR.exists() else 0
    return {
        "total_videos": video_count,
        "video_dir": str(VIDEO_DIR),
        "api_configured": bool(AGNES_API_KEY),
    }


@router.post("/generate")
async def create_video_task(
    prompt: str = Form(...),
    model: str = Form("agnes-video-v2.0"),
    width: int = Form(1152),
    height: int = Form(768),
    duration: int = Form(5),
    mode: str = Form("ti2vid"),  # ti2vid, i2vid, keyframes
    image: str = Form(""),
    frame_rate: int = Form(24),
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

    # 图生视频需要图片URL
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
            timeout=30,
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
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建视频任务异常: {e}")
        raise HTTPException(500, f"创建视频任务失败: {str(e)}")


@router.get("/result/{video_id}")
async def get_video_result(video_id: str):
    """获取视频生成结果"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    try:
        # 推荐使用 agnesapi 端点
        response = requests.get(
            f"{AGNES_API_BASE}/agnesapi",
            params={"video_id": video_id},
            headers={"Authorization": f"Bearer {AGNES_API_KEY}"},
            timeout=30,
        )

        if response.status_code != 200:
            # 尝试兼容旧版端点
            response = requests.get(
                f"{AGNES_API_BASE}/videos/{video_id}",
                headers={"Authorization": f"Bearer {AGNES_API_KEY}"},
                timeout=30,
            )

        if response.status_code not in [200, 202]:
            raise HTTPException(500, f"获取视频结果失败: {response.text}")

        data = response.json()

        # 检查状态
        status = data.get("status", "unknown")
        if status == "completed":
            video_url = data.get("output", {}).get("video_url") or data.get("url")
            if not video_url:
                raise HTTPException(500, "视频生成完成但未找到视频URL")

            # 下载视频
            video_resp = requests.get(video_url, timeout=120)
            if video_resp.status_code != 200:
                raise HTTPException(500, "下载视频失败")

            filename = f"{video_id}.mp4"
            save_video(video_resp.content, filename)

            return {
                "video_id": video_id,
                "status": "completed",
                "url": f"/api/video-factory/videos/{filename}",
                "duration": data.get("duration", 0),
            }
        elif status == "failed":
            raise HTTPException(500, f"视频生成失败: {data.get('error', 'unknown')}")
        else:
            # 还在生成中
            return {
                "video_id": video_id,
                "status": status,
                "progress": data.get("progress", 0),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取视频结果异常: {e}")
        raise HTTPException(500, f"获取视频结果失败: {str(e)}")


@router.get("/videos/{filename}")
async def get_video(filename: str):
    """获取视频文件"""
    video_path = VIDEO_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "视频不存在")
    
    return FileResponse(video_path, media_type="video/mp4")


@router.get("/list")
async def list_videos():
    """列出所有视频"""
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
    """删除视频"""
    video_path = VIDEO_DIR / filename
    if not video_path.exists():
        raise HTTPException(404, "视频不存在")
    video_path.unlink()
    return {"success": True}
