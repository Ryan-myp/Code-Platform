#!/usr/bin/env python3
"""AI 视频 / AI 形象生成网关 — 可灵 v3 视频 + 万相文生图（阿里云百炼接入，Phase 5.5 商业化）。

能力：
- POST /api/ai-video/generate       文生视频 / 图生视频 / 口型同步数字人（异步任务 type=ai_video）
- POST /api/ai-video/avatar-image   AI 形象图生成（万相文生图 → 自动创建照片数字人形象，type=ai_avatar_image）
- GET  /api/ai-video/config         网关配置状态（是否已配置 API Key）

配置（backend/.env，缺失时接口返回配置指引）：
- DASHSCOPE_API_KEY:      阿里云百炼 API Key（https://bailian.console.aliyun.com）
- DASHSCOPE_WORKSPACE_ID: 百炼业务空间 ID（华北2 地域）

计费（复用 dh_gateway 的 users.balance 余额体系，config 表 ai_video_pricing 可覆盖）：
- ai_video: 5 元/条（720p）、10 元/条（1080p）
- ai_avatar_image: 1 元/张
任务提交时扣费，云端失败/下载失败自动退费（惰性退费，与 dh_gateway 一致）。
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from dh_gateway import _charge, _ensure_billing_tables, _refund
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai-video", tags=["AI视频网关"])

# ── 配置（.env，可被 config 表覆盖） ─────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_UPLOAD_VIDEO_DIR = os.path.join(_BASE_DIR, "uploads", "videos")
_UPLOAD_DH_AVATAR_DIR = os.path.join(_BASE_DIR, "uploads", "dh_avatars")
_VIDEO_MODEL = "kling/kling-v3-video-generation"  # 文/图生视频
_OMNI_MODEL = "kling/kling-v3-omni-video-generation"  # 口型同步（音频驱动数字人）
_IMAGE_MODEL = "wanx2.1-t2i-turbo"  # 万相文生图（AI 形象）
_POLL_INTERVAL = 15  # 云端任务轮询间隔（秒）
_POLL_DEADLINE = 30 * 60  # 视频生成最长等待

AI_VIDEO_PRICING_DEFAULT = {
    "ai_video": 5.0,  # 元/条（720p）
    "hd_1080p_extra": 5.0,  # 1080p 加价
    "ai_avatar_image": 1.0,  # 元/张
}


def _config() -> dict:
    """读取网关配置（env 优先，config 表兜底）。"""
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    ws = os.environ.get("DASHSCOPE_WORKSPACE_ID", "")
    if not api_key or not ws:
        try:
            with get_db_context() as conn:
                row = conn.execute("SELECT value FROM config WHERE key='ai_video_gateway'").fetchone()
                if row:
                    cfg = json.loads(row["value"])
                    api_key = cfg.get("api_key", api_key)
                    ws = cfg.get("workspace_id", ws)
        except Exception:  # noqa: BLE001 — 配置表读取失败不阻塞
            pass
    return {"api_key": api_key, "workspace_id": ws}


def _endpoint() -> str:
    """华北2 地域视频合成端点（WorkspaceId 内嵌）。"""
    ws = _config()["workspace_id"]
    return f"https://{ws}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"


def _image_endpoint() -> str:
    ws = _config()["workspace_id"]
    return f"https://{ws}.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"


def _task_endpoint(cloud_task_id: str) -> str:
    ws = _config()["workspace_id"]
    return f"https://{ws}.cn-beijing.maas.aliyuncs.com/api/v1/tasks/{cloud_task_id}"


def _require_gateway() -> None:
    """API Key 缺失时抛 400 + 配置指引（不消耗配额）。"""
    cfg = _config()
    if not cfg["api_key"] or not cfg["workspace_id"]:
        raise HTTPException(
            400,
            "AI 视频网关未配置：请在 backend/.env 填写 DASHSCOPE_API_KEY 与 DASHSCOPE_WORKSPACE_ID"
            "（阿里云百炼控制台开通可灵/万相模型后获取），或联系平台管理员配置后重试",
        )


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_config()['api_key']}",
        "Content-Type": "application/json",
    }


def _submit_cloud(payload: dict) -> str:
    """提交云端异步任务，返回云端 task_id。"""
    url = _image_endpoint() if payload.pop("_kind", "") == "image" else _endpoint()
    try:
        resp = httpx.post(url, headers=_headers(), json=payload, timeout=30)
    except httpx.HTTPError as e:
        raise RuntimeError(f"云端网关连接失败: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"云端网关返回 {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    tid = data.get("task_id") or data.get("output", {}).get("task_id", "")
    if not tid:
        raise RuntimeError(f"云端未返回任务 ID: {resp.text[:200]}")
    return tid


def _query_cloud(cloud_task_id: str) -> dict:
    """查询云端任务，返回 {"status", "video_url", "image_url", "error"}。"""
    try:
        resp = httpx.get(_task_endpoint(cloud_task_id), headers=_headers(), timeout=30)
    except httpx.HTTPError as e:
        raise RuntimeError(f"云端查询失败: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"云端查询返回 {resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    out = data.get("output", {}) or {}
    return {
        "status": data.get("task_status", "UNKNOWN"),
        "video_url": out.get("video_url", ""),
        "image_url": out.get("img_url", "") or out.get("image_url", ""),
        "error": data.get("message", "") or data.get("error", "") or "",
    }


def _download(url: str, dest: str) -> str:
    """下载云端产物到本地，返回本地路径。"""
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=300)
    except httpx.HTTPError as e:
        raise RuntimeError(f"云端产物下载失败: {e}") from e
    if resp.status_code != 200 or len(resp.content) < 1024:
        raise RuntimeError(f"云端产物下载异常（{resp.status_code}，{len(resp.content)} 字节）")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


def _price_for(mode: str, resolution: str) -> float:
    """AI 视频定价（config 表 ai_video_pricing 可覆盖）。"""
    pricing = dict(AI_VIDEO_PRICING_DEFAULT)
    try:
        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='ai_video_pricing'").fetchone()
            if row:
                pricing.update(json.loads(row["value"]))
    except Exception:  # noqa: BLE001 — 定价读取失败用默认
        pass
    price = float(pricing.get(mode, pricing.get("ai_video", 5.0)))
    if resolution == "1080p":
        price += float(pricing.get("hd_1080p_extra", 5.0))
    return round(price, 2)


# ── 请求模型 ───────────────────────────────────────────────────


class VideoGenerateRequest(BaseModel):
    mode: str = Field("text2video", pattern="^(text2video|image2video|lipsync)$", description="模式")
    prompt: str = Field(..., min_length=5, max_length=1000, description="视频内容描述（中文）")
    image_url: str = Field("", description="图生视频/口型同步：参考图 URL 或平台 /uploads 路径")
    audio_url: str = Field("", description="口型同步：配音音频 URL 或平台 /uploads 路径")
    duration: int = Field(5, ge=5, le=10, description="时长秒（5 或 10）")
    resolution: str = Field("720p", pattern="^(720p|1080p)$", description="分辨率")
    aspect_ratio: str = Field("16:9", pattern="^(16:9|9:16|1:1)$", description="画幅")


class AvatarImageRequest(BaseModel):
    prompt: str = Field(..., min_length=8, max_length=500, description="形象描述（正脸、职业、风格等）")
    name: str = Field("AI 形象", max_length=20, description="形象名称")


# ── 计费与任务 ─────────────────────────────────────────────────


def _to_public_url(path_or_url: str) -> str:
    """平台内 /uploads 路径原样返回（前端可直接访问），外部 URL 保持。"""
    return path_or_url if path_or_url.startswith("/uploads/") else path_or_url


def _charge_for(auth: dict, billing_id: str, price: float, task_id: str = "") -> float:
    """扣费（复用 dh_gateway 账单体系）。"""
    with get_db_context() as conn:
        _ensure_billing_tables(conn)
        row = conn.execute("SELECT balance FROM users WHERE id=?", (auth["user_id"],)).fetchone()
        balance = float(row["balance"] or 0) if row else 0.0
    if balance < price:
        raise HTTPException(402, "操作失败，请稍后重试")
    return _charge(auth, billing_id, price, task_id)


@router.post("/generate")
async def create_video_task(req: VideoGenerateRequest, current_user: dict = require_auth()):
    """提交 AI 视频生成任务（异步）。校验通过后扣费，失败自动退费。"""
    _require_gateway()
    _validate_upload_refs(req)
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    price = _price_for(req.mode, req.resolution)
    payload = req.model_dump()
    billing_id = f"billing_{uuid.uuid4().hex[:12]}"
    _charge_for(current_user, billing_id, price)
    task = create_task(
        "ai_video",
        {"billing_id": billing_id, "price": price, **payload},
        username=user,
        user_id=current_user.get("user_id", ""),
        role=current_user.get("role", ""),
    )
    return {
        "task_id": task["id"],
        "status": task["status"],
        "price": price,
        "balance": None,
        "message": "AI 视频生成任务已提交（云端生成约 1-5 分钟），可在「我的生成任务」查看",
    }


@router.post("/avatar-image")
async def create_avatar_image_task(req: AvatarImageRequest, current_user: dict = require_auth()):
    """AI 形象图生成任务：万相文生图 → 自动创建照片数字人形象（口型同步可用）。"""
    _require_gateway()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    price = _price_for("ai_avatar_image", "720p")
    billing_id = f"billing_{uuid.uuid4().hex[:12]}"
    _charge_for(current_user, billing_id, price)
    task = create_task(
        "ai_avatar_image",
        {"billing_id": billing_id, "price": price, "prompt": req.prompt, "name": req.name.strip()[:20]},
        username=user,
        user_id=current_user.get("user_id", ""),
        role=current_user.get("role", ""),
    )
    return {
        "task_id": task["id"],
        "status": task["status"],
        "price": price,
        "message": "AI 形象生成任务已提交（约 30-60 秒），完成后自动加入形象列表",
    }


@router.get("/config")
async def gateway_config(current_user: dict = require_auth()):
    """网关配置状态（前端用于展示入口可用性）。"""
    cfg = _config()
    return {
        "configured": bool(cfg["api_key"] and cfg["workspace_id"]),
        "pricing": {
            "text2video_720p": _price_for("text2video", "720p"),
            "text2video_1080p": _price_for("text2video", "1080p"),
            "avatar_image": _price_for("ai_avatar_image", "720p"),
        },
    }


# ── 云上资源引用校验 ───────────────────────────────────────────


def _resolve_local_upload(url: str) -> str:
    """平台 /uploads 路径 → 本地绝对路径（外部 http(s) URL 原样返回）。"""
    if not url:
        return url
    if url.startswith("/uploads/"):
        return os.path.join(_BASE_DIR, *url.lstrip("/").split("/"))
    return url


def _validate_upload_refs(req: VideoGenerateRequest) -> None:
    """校验图片/音频引用存在（平台内路径检查本地文件，外部 URL 仅格式校验）。"""
    for field in ("image_url", "audio_url"):
        val = getattr(req, field)
        if not val:
            continue
        if val.startswith("/uploads/"):
            local = _resolve_local_upload(val)
            if not os.path.exists(local):
                raise HTTPException(400, "引用的文件不存在")
        elif not val.startswith(("http://", "https://")):
            raise HTTPException(400, "路径格式不正确")


# ── 异步任务处理器 ─────────────────────────────────────────────


def _ai_video_handler(task_id: str, payload: dict, update: callable, ctx: dict) -> dict:  # noqa: C901
    """AI 视频任务：提交云端 → 轮询 → 下载到 uploads/videos/ → 返回结果。失败退费。"""
    billing_id = payload.pop("billing_id", "")
    payload.get("price", 0)
    try:
        _require_gateway()  # 提交时已校验，此处兜底
        mode = payload.get("mode", "text2video")
        prompt = payload.get("prompt", "")
        duration = int(payload.get("duration", 5))
        resolution = payload.get("resolution", "720p")
        aspect = payload.get("aspect_ratio", "16:9")

        # 口型同步：omni 模型 + 音频/图片引用（内部路径转绝对路径）
        if mode == "lipsync":
            body = {"model": _OMNI_MODEL, "input": {"prompt": prompt, "audio_url": _resolve_local_upload(payload.get("audio_url", ""))}}
            if payload.get("image_url"):
                body["input"]["img_url"] = _resolve_local_upload(payload["image_url"])
            body["parameters"] = {"mode": "std", "aspect_ratio": aspect, "duration": duration, "watermark": False}
        elif mode == "image2video":
            body = {"model": _VIDEO_MODEL, "input": {"prompt": prompt, "img_url": _resolve_local_upload(payload.get("image_url", ""))}}
            body["parameters"] = {"mode": "std", "aspect_ratio": aspect, "duration": duration, "audio": True, "watermark": False}
        else:
            body = {"model": _VIDEO_MODEL, "input": {"prompt": prompt}}
            body["parameters"] = {"mode": "std", "aspect_ratio": aspect, "duration": duration, "audio": True, "watermark": False}

        update(5, "正在提交云端生成任务…")
        cloud_tid = _submit_cloud(body)
        update(10, "任务已提交，云端生成中（约 1-5 分钟）…")
        deadline = time.monotonic() + _POLL_DEADLINE
        result: dict | None = None
        while time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL)
            state = _query_cloud(cloud_tid)
            if state["status"] == "SUCCEEDED":
                if not state["video_url"]:
                    raise RuntimeError("云端任务完成但未返回视频地址")
                result = state
                break
            if state["status"] in ("FAILED", "CANCELED", "UNKNOWN"):
                raise RuntimeError(f"云端生成失败（{state['status']}）: {state['error'] or '未知错误'}")
            update(min(80, 10 + int((time.monotonic() - (deadline - _POLL_DEADLINE)) / 5)), f"云端生成中（{state['status']}）…")
        if result is None:
            raise TimeoutError(f"云端生成超时（>{_POLL_DEADLINE // 60} 分钟），请稍后重试")

        update(85, "生成完成，正在下载视频…")
        filename = f"ai_{task_id.replace('task_', '')}.mp4"
        local = _download(result["video_url"], os.path.join(_UPLOAD_VIDEO_DIR, filename))
        duration_s = round(float(payload.get("duration", 0)), 1)
        return {
            "status": "done",
            "mode": mode,
            "video_url": f"/uploads/videos/{filename}",
            "local_path": local,
            "duration": duration_s,
            "resolution": resolution,
            "cloud_task_id": cloud_tid,
        }
    except Exception:  # noqa: BLE001 — 失败退费并抛出（任务框架记录 error）
        if billing_id:
            try:
                _refund(billing_id)
                logger.info("AI 视频任务失败退费: billing=%s", billing_id)
            except Exception:  # noqa: BLE001 — 退费失败不掩盖主错误
                logger.warning("AI 视频任务退费失败: billing=%s", billing_id)
        raise


def _ai_avatar_image_handler(task_id: str, payload: dict, update: callable, ctx: dict) -> dict:
    """AI 形象任务：万相文生图 → 下载 → 创建照片数字人形象。失败退费。"""
    billing_id = payload.pop("billing_id", "")
    try:
        _require_gateway()
        prompt = payload.get("prompt", "")
        name = payload.get("name", "AI 形象")
        body = {
            "model": _IMAGE_MODEL,
            "input": {"prompt": prompt},
            "parameters": {"size": "1024*1024", "n": 1, "watermark": False},
        }
        update(5, "正在提交形象生成任务…")
        cloud_tid = _submit_cloud({**body, "_kind": "image"})
        update(10, "云端生成形象中（约 30-60 秒）…")
        deadline = time.monotonic() + 10 * 60
        result: dict | None = None
        while time.monotonic() < deadline:
            time.sleep(8)
            state = _query_cloud(cloud_tid)
            if state["status"] == "SUCCEEDED":
                if not state["image_url"]:
                    raise RuntimeError("云端完成但未返回图片地址")
                result = state
                break
            if state["status"] in ("FAILED", "CANCELED", "UNKNOWN"):
                raise RuntimeError(f"云端生成失败（{state['status']}）: {state['error'] or '未知错误'}")
            update(min(60, 10 + int((time.monotonic() - (deadline - 600)) / 6)), "云端生成形象中…")
        if result is None:
            raise TimeoutError("云端形象生成超时（>10 分钟），请稍后重试")

        update(70, "下载形象图并创建形象…")
        avatar_id = f"custom_{uuid.uuid4().hex[:10]}"
        local = _download(result["image_url"], os.path.join(_UPLOAD_DH_AVATAR_DIR, f"{avatar_id}.jpg"))
        user = ctx.get("username", "") if isinstance(ctx, dict) else ""
        from common.db import get_db
        from digital_human import _ensure_tables as _dh_tables

        conn = get_db()
        try:
            _dh_tables(conn)
            conn.execute(
                "INSERT INTO digital_human_custom_avatars (id, user_id, name, style, gender, desc, emoji, image_url, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    avatar_id,
                    user,
                    name.strip()[:20],
                    "照片数字人",
                    "真人",
                    "AI 生成的形象（支持口型同步）",
                    "✨",
                    f"/uploads/dh_avatars/{avatar_id}.jpg",
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return {
            "status": "done",
            "avatar_id": avatar_id,
            "name": name.strip()[:20],
            "image_url": f"/uploads/dh_avatars/{avatar_id}.jpg",
            "local_path": local,
        }
    except Exception:  # noqa: BLE001 — 失败退费并抛出
        if billing_id:
            try:
                _refund(billing_id)
            except Exception:  # noqa: BLE001 — 退费失败不掩盖主错误
                logger.warning("AI 形象任务退费失败: billing=%s", billing_id)
        raise


register_handler("ai_video", _ai_video_handler, user_limit=2, pool="long")
register_handler("ai_avatar_image", _ai_avatar_image_handler, user_limit=2, pool="long")
