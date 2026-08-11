#!/usr/bin/env python3
"""图片工厂模块 - 完整版本

功能：
1. 文生图（调用 Agnes AI API）
2. 图生图
3. 智能抠图（基于颜色阈值）
4. 剪裁缩放
5. 模板合成
6. 批量生成
7. 图片管理（下载、预览、删除）
"""

import asyncio
import base64
import io
import json
import logging
import os
import re
import tempfile
import time
from collections.abc import Callable
from datetime import datetime
from io import BytesIO

import numpy as np
import requests
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from common.artifacts import derive_title, save_artifact
from common.auth import require_auth
from common.config import load_config
from content_safety import check_text, quality_check_image, quality_report
from publish_kit import build_publish_zip, license_text, pack_dir_name, platform_spec_text, publish_registry
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image-factory", tags=["图片工厂"])

# 配置：走 common.config 单一来源（运行时可被 config 表覆盖）
load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY  # noqa: E402

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "image_factory")
TEMPLATE_DIR = os.path.join(IMAGE_DIR, "templates")

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)

# v15：批量生成资源上限（防滥用）与缩略图规格
MAX_BATCH_SIZE = 4  # 单任务最大批次数
MAX_N = 4  # 单批最大张数
MAX_TOTAL_IMAGES = 16  # 单任务总张数上限（batch × n）
DEFAULT_IMAGE_SIZE = "1024x1024"
MIN_IMAGE_SIDE = 256
MAX_IMAGE_SIDE = 4096
THUMB_SIZE = 256  # 历史缩略图长边像素

# 平台发布规格预设（商业化发布包：按平台规格输出成品）
PLATFORM_PRESETS = [
    {"id": "xiaohongshu", "name": "小红书封面", "w": 1242, "h": 1660, "ratio": "3:4",
     "desc": "图文笔记封面（3:4 竖版），兼容抖音图文/微信公众号推文"},
    {"id": "douyin", "name": "抖音/快手头图", "w": 1080, "h": 1920, "ratio": "9:16",
     "desc": "短视频平台头图/视频封面（9:16 竖版）"},
    {"id": "taobao", "name": "淘宝/电商主图", "w": 800, "h": 800, "ratio": "1:1",
     "desc": "电商主图 800×800（满足淘宝/拼多多/京东主图要求）"},
    {"id": "wechat", "name": "公众号头图", "w": 900, "h": 383, "ratio": "2.35:1",
     "desc": "微信公众号头图 900×383（适配 2.35:1 展示）"},
]

# 各平台发布规格说明（随发布包附带的规格说明.md）
_PLATFORM_SPECS = {
    "xiaohongshu": [
        {"name": "封面尺寸", "value": "1242×1660（3:4）", "desc": "图文笔记首图，信息量大的图建议左侧留安全区"},
        {"name": "格式", "value": "JPG/PNG，≤20MB", "desc": "JPG 压缩率建议 85-95，兼顾清晰与加载速度"},
        {"name": "标签", "value": "每篇最多 10 个话题标签", "desc": "建议 3-5 个精准标签，覆盖热门话题"},
    ],
    "douyin": [
        {"name": "头图尺寸", "value": "1080×1920（9:16）", "desc": "视频封面/图文头图；主体居中，避免文字遮挡关键信息"},
        {"name": "格式", "value": "JPG/PNG，≤20MB", "desc": "封面文字建议 ≤3 行，字号足够大"},
        {"name": "标签", "value": "最多 5 个话题标签", "desc": "建议组合：大热话题 + 垂类话题"},
    ],
    "taobao": [
        {"name": "主图尺寸", "value": "800×800（1:1）", "desc": "5 张主图 + 1 张视频主图；首图建议纯色背景突出商品"},
        {"name": "格式", "value": "JPG，≤3MB", "desc": "白底图可参与部分行业活动，建议保留一张白底版"},
        {"name": "规范", "value": "不得含水印/logo/联系方式", "desc": "主图文字占比 ≤1/3，避免牛皮癣式堆叠"},
    ],
    "wechat": [
        {"name": "头图尺寸", "value": "900×383（2.35:1）", "desc": "公众号头条头图；次条 300×300"},
        {"name": "格式", "value": "JPG/PNG，≤10MB", "desc": "文字居中偏左，右侧避免放重要信息（会被折叠）"},
        {"name": "规范", "value": "不得含二维码/诱导关注信息", "desc": "封面图需与文章内容强相关"},
    ],
}

# 各平台上架文案标签建议
_PLATFORM_TAGS = {
    "xiaohongshu": ["#AI绘画", "#插画分享", "#壁纸", "#每日一图", "#设计灵感"],
    "douyin": ["#AI绘画", "#壁纸", "#插画", "#涨知识", "#创意"],
    "taobao": ["#主图", "#电商设计", "#商品图", "#白底图"],
    "wechat": ["#AI生成", "#封面图", "#插画", "#设计"],
}


def _save_artifact(filename: str, project_id: str, prompt: str, extra_meta: dict | None = None) -> str:
    """将生成的图片产物登记到 artifacts 表（委托 common.artifacts.save_artifact）。

    - type=image，media_url 指向 /api/image-factory/images/{filename} 的相对路径
    - metadata 含 prompt + 额外字段（size/model 等）；title 为语义化标题（v13.26）
    - 失败静默（不影响主流程）
    """
    meta = {"prompt": prompt, "filename": filename}
    if extra_meta:
        meta.update(extra_meta)
    meta.setdefault("title", derive_title("image", {"prompt": prompt}, meta))
    return save_artifact(
        art_type="image",
        project_id=project_id,
        author="image_factory",
        media_url=f"/api/image-factory/images/{filename}",
        content={"filename": filename, "prompt": prompt},
        metadata=meta,
    )


# ── 辅助函数 ──────────────────────────────────────────────────
def generate_id() -> str:
    return f"img_{int(time.time() * 1000)}"


def save_image(img: Image.Image, fmt: str = "PNG", keep_alpha: bool = False) -> str:
    """保存图像并返回文件名

    keep_alpha=True 时保留 RGBA 透明通道（抠图/分割等透明输出场景，PNG 格式）。
    """
    img_id = generate_id()
    ext = ".png" if (fmt == "PNG" or keep_alpha) else ".jpg"
    filename = f"{img_id}{ext}"
    filepath = os.path.join(IMAGE_DIR, filename)

    # 转换为 RGB（keep_alpha 时保留透明通道）
    if img.mode in ("RGBA", "P"):
        if keep_alpha and img.mode == "RGBA":
            pass  # 原样保存，透明背景保留
        else:
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if fmt == "PNG" or keep_alpha:
        img.save(filepath, "PNG")
    else:
        img.save(filepath, "JPEG", quality=95)

    return filename


def get_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """获取字体（macOS PingFang → Linux 文泉驿/Noto CJK → 默认）"""
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux：文泉驿（简体）
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux：Noto CJK
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ── v20：AI 提示词润色（免费辅助能力；LLM 失败静默回退原 prompt，不阻塞主链路）──
_DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, watermark, text, deformed, extra limbs, bad anatomy, "
    "cropped, jpeg artifacts"
)


@router.post("/enhance-prompt")
async def enhance_prompt(prompt: str = Form(...), current_user: dict = require_auth()):
    """AI 润色文生图提示词：简单描述 → 专业提示词（主体/构图/光线/风格/质量词）+ 自动负面词建议。"""
    from common.llm import call_llm_async

    original = (prompt or "").strip()
    if not original:
        raise HTTPException(400, "请输入图片描述")
    if len(original) > 500:
        raise HTTPException(400, "描述过长（500 字以内），请精简后重试")
    system = (
        "你是一位专业 AI 绘画提示词工程师。把用户的简要描述扩写为高质量中文绘图提示词，"
        "必须覆盖以下维度：主体（内容/数量/动作表情）、环境（场景/背景）、构图（视角/景别/布局）、"
        "光线（时间/氛围/光源）、风格（艺术流派/画风）、材质与细节、质量词（高清/细腻/光影自然等）。"
        "控制在 150 字以内，只输出润色后的提示词本身，不要解释。"
    )
    enhanced = original
    try:
        out = await call_llm_async(system, f"【原始描述】\n{original}", max_tokens=500, temperature=0.7)
        out = (out or "").strip().strip('\"\'`')
        if len(out) >= 4:
            enhanced = out
    except Exception:
        logger.warning("[image_factory.enhance_prompt] LLM 调用失败，静默回退原 prompt", exc_info=True)
    return {"ok": True, "original": original, "enhanced": enhanced, "negative_auto": _DEFAULT_NEGATIVE_PROMPT}


# ── 统计 API ──────────────────────────────────────────────────
@router.get("/stats")
async def get_stats():
    """获取图片工厂统计"""
    files = []
    if os.path.exists(IMAGE_DIR):
        files = [f for f in os.listdir(IMAGE_DIR) if f.endswith((".png", ".jpg", ".jpeg"))]
    templates = []
    if os.path.exists(TEMPLATE_DIR):
        templates = [f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".json")]
    return {
        "total_images": len(files),
        "total_templates": len(templates),
        "image_dir": IMAGE_DIR,
        "api_configured": bool(AGNES_API_KEY),
    }


# ── 图片管理 API ──────────────────────────────────────────────
@router.get("/images")
async def list_images(filename: str | None = None):
    """列出所有图片（v13.26：从 artifacts 合并 prompt/title，展示语义化标题而非随机 ID）。"""
    meta = _artifact_meta()
    files = []
    if os.path.exists(IMAGE_DIR):
        for f in os.listdir(IMAGE_DIR):
            if f.endswith((".png", ".jpg", ".jpeg")):
                if filename and filename.lower() not in f.lower():
                    continue
                filepath = os.path.join(IMAGE_DIR, f)
                stat = os.stat(filepath)
                m = meta.get(f, {})
                prompt = m.get("prompt", "")
                files.append(
                    {
                        "filename": f,
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "url": f"/api/image-factory/images/{f}",
                        "thumb_url": f"/api/image-factory/images/{f}/thumb",
                        "prompt": prompt,
                        "title": m.get("title") or derive_title("image", {"prompt": prompt}, m) or _fallback_title(f),
                    }
                )
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files


def _fallback_title(filename: str) -> str:
    """存量旧图语义化兜底（v13.26）：img_时间戳 → 「图片 · 月-日 时:分」，避免裸 ID 展示。"""
    m = re.match(r"^img_(\d{13})\.(?:png|jpe?g)$", filename)
    if m:
        ts = int(m.group(1)) / 1000
        return "图片 · " + datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    return os.path.splitext(filename)[0]


def _artifact_meta() -> dict:
    """读取 artifacts 表图片产物元数据（filename → {prompt, title, …}）。"""
    meta: dict = {}
    try:
        from common.db import get_db

        conn = get_db()
        rows = conn.execute(
            "SELECT content, media_url, metadata FROM artifacts "
            "WHERE type='image' AND author='image_factory' AND active=1"
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
        logger.warning(f"读取图片元数据失败: {e}")
    return meta


@router.get("/images/{filename}")
async def get_image(filename: str):
    """获取图片文件"""
    filepath = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "图片不存在")
    return FileResponse(filepath)


@router.get("/images/{filename}/thumb")
async def get_image_thumb(filename: str):
    """图片缩略图（≤256px JPEG，内存生成，历史缩略图墙加载提速；失败回退原图）。"""
    filepath = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "图片不存在")
    try:
        img = Image.open(filepath)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82)
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception as e:
        logger.warning(f"缩略图生成失败，回退原图: {e}")
        return FileResponse(filepath)


@router.delete("/images/{filename}")
async def delete_image(filename: str):
    """删除图片"""
    filepath = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return {"success": True}


# ── 异步任务文件参数辅助 ─────────────────────────────────────
_TMP_PREFIX = "file://"


def _read_file_field(payload: dict, key: str) -> bytes | None:
    """读取 payload 中的文件字段：sync 模式为 base64，async 模式为 file:// 临时路径。"""
    val = payload.get(key)
    if not val:
        return None
    if isinstance(val, str) and val.startswith(_TMP_PREFIX):
        path = val[len(_TMP_PREFIX) :]
        try:
            with open(path, "rb") as f:
                return f.read()
        finally:
            # 任务文件一次性使用：读完即删（临时目录），避免残留
            try:
                os.remove(path)
            except OSError:
                pass
    return base64.b64decode(val) if isinstance(val, str) else None


async def _write_file_field(content: bytes) -> str:
    """异步任务模式：文件写入临时目录，payload 存 file:// 路径。"""
    tmp = tempfile.NamedTemporaryFile(prefix="img_task_", suffix=".png", delete=False)
    tmp.write(content)
    tmp.close()
    return f"{_TMP_PREFIX}{tmp.name}"


# ── 文生图 API ────────────────────────────────────────────────
def normalize_batch_params(batch_size: int | None, n: int | None) -> tuple[int, int]:
    """批量生成参数规范化：各自截断到 1..MAX，且总张数不超过 MAX_TOTAL_IMAGES。

    返回 (batch_size, n)，纯函数可单测。
    """
    b = max(1, min(MAX_BATCH_SIZE, int(batch_size or 1)))
    nn = max(1, min(MAX_N, int(n or 1)))
    while b * nn > MAX_TOTAL_IMAGES:
        if b >= nn:
            b -= 1
        else:
            nn -= 1
    return b, nn


def normalize_size(size: str | None) -> str:
    """尺寸参数规范化：WxH 且每边在 MIN..MAX_IMAGE_SIDE，非法回退默认尺寸。"""
    raw = (size or "").strip().lower()
    try:
        w, h = (int(x) for x in raw.split("x"))
    except Exception:
        return DEFAULT_IMAGE_SIZE
    if not (MIN_IMAGE_SIDE <= w <= MAX_IMAGE_SIDE and MIN_IMAGE_SIDE <= h <= MAX_IMAGE_SIDE):
        return DEFAULT_IMAGE_SIZE
    return f"{w}x{h}"


async def _image_t2i_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """文生图（同步/异步任务共用执行体，异步时回报进度）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    prompt = payload.get("prompt") or ""
    size = payload.get("size") or DEFAULT_IMAGE_SIZE
    model = payload.get("model") or "agnes-image-2.1-flash"
    batch_size, n = normalize_batch_params(payload.get("batch_size"), payload.get("n"))
    project_id = payload.get("project_id") or ""
    negative = payload.get("negative") or ""
    if not prompt:
        raise HTTPException(400, "请输入图片描述")

    # 生产级内容保障：文生图描述生成前安全审核（平台发布红线）
    res = check_text(prompt, "prompt")
    if not res["ok"]:
        raise HTTPException(400, f"图片描述：{res['suggestion']}")

    url = f"{AGNES_API_BASE}/images/generations"
    headers = {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}

    size_str = normalize_size(size)

    results = []
    _report(10, f"开始生成（共 {batch_size} 批）…")
    for i in range(batch_size):
        _report(20 + int(i * 60 / batch_size), f"第 {i + 1}/{batch_size} 批生成中…")
        api_payload = {
            "model": model,
            "prompt": prompt,
            "size": size_str,
            "n": n,
        }
        if negative:
            api_payload["negative_prompt"] = negative
        try:
            resp = await asyncio.to_thread(requests.post, url, headers=headers, json=api_payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()
            if "data" in data and len(data["data"]) > 0:
                for item in data["data"]:
                    image_url = item.get("url")
                    if image_url:
                        img_resp = await asyncio.to_thread(requests.get, image_url, timeout=60)
                        img = Image.open(io.BytesIO(img_resp.content))
                        filename = save_image(img)
                        art_id = _save_artifact(filename, project_id, prompt, {"size": size_str, "model": model})
                        results.append(
                            {
                                "id": filename,
                                "artifact_id": art_id,
                                "url": f"/api/image-factory/images/{filename}",
                                "prompt": prompt,
                            }
                        )
            else:
                results.append({"error": f"生成失败：{data}", "prompt": prompt})
        except Exception as e:
            logger.error(f"文生图失败：{e}")
            results.append({"error": f"生成失败：{str(e)}", "prompt": prompt})

    _report(100, "生成完成")
    return {"results": results, "total": len(results), "prompt": prompt, "project_id": project_id}


@router.post("/generate/text-to-image")
async def text_to_image(
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    model: str = Form("agnes-image-2.1-flash"),
    batch_size: int = Form(1),
    n: int = Form(1),
    project_id: str = Form(""),
    negative: str = Form("", description="负面提示词（不想要的元素，如 low quality, blurry）"),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """
    文生图 - 支持批量生成（默认异步任务，立即返回 task_id）

    参数:
    - prompt: 图片描述
    - size: 尺寸 (1024x1024, 800x600, 1280x720 等)
    - model: 模型名称
    - batch_size: 批量生成数量 (1-4)
    - n: 每批次生成数量
    - project_id: 关联项目 ID（可选，写入 artifacts 表用于项目空间聚合）
    - negative: 负面提示词（可选，排除不想要的元素）
    """
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "prompt": prompt,
        "size": size,
        "model": model,
        "batch_size": batch_size,
        "n": n,
        "project_id": project_id,
        "negative": negative,
    }
    if sync:
        return await _image_t2i_worker(payload)
    task = create_task("image_t2i", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "文生图任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


# ── 图生图 API ────────────────────────────────────────────────
async def _image_i2i_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """图生图（同步/异步任务共用执行体，异步时回报进度）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    prompt = payload.get("prompt") or ""
    size = payload.get("size") or "1024x1024"
    strength = float(payload.get("strength") or 0.35)
    model = payload.get("model") or "agnes-image-2.1-flash"
    project_id = payload.get("project_id") or ""
    negative = payload.get("negative") or ""
    image_content = _read_file_field(payload, "image")
    if not image_content:
        raise HTTPException(400, "请上传参考图片")

    # 生产级内容保障：图生图描述生成前安全审核
    res = check_text(prompt, "prompt")
    if not res["ok"]:
        raise HTTPException(400, f"图片描述：{res['suggestion']}")

    url = f"{AGNES_API_BASE}/images/generations"
    headers = {"Authorization": f"Bearer {AGNES_API_KEY}"}
    files = {"image": ("input.png", image_content, "image/png")}
    data = {"model": model, "prompt": prompt, "size": size, "strength": strength, "n": 1}
    if negative:
        data["negative_prompt"] = negative

    _report(20, "AI 正在基于参考图生成…")
    try:
        resp = await asyncio.to_thread(requests.post, url, headers=headers, data=data, files=files, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        if "data" in data and len(data["data"]) > 0:
            image_url = data["data"][0].get("url")
            if image_url:
                img_resp = await asyncio.to_thread(requests.get, image_url, timeout=60)
                result_img = Image.open(io.BytesIO(img_resp.content))
                filename = save_image(result_img)
                art_id = _save_artifact(
                    filename, project_id, prompt, {"size": size, "model": model, "strength": strength}
                )
                _report(100, "生成完成")
                return {
                    "id": filename,
                    "artifact_id": art_id,
                    "url": f"/api/image-factory/images/{filename}",
                    "prompt": prompt,
                    "project_id": project_id,
                }
        raise HTTPException(500, f"生成失败: {data}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"图生图失败：{e}")
        raise HTTPException(500, f"生成失败：{str(e)}") from e


@router.post("/generate/image-to-image")
async def image_to_image(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    size: str = Form("1024x1024"),
    strength: float = Form(0.35),
    model: str = Form("agnes-image-2.1-flash"),
    project_id: str = Form(""),
    negative: str = Form("", description="负面提示词（不想要的元素）"),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """图生图 - 基于输入图片生成新图片（默认异步任务；异步时文件暂存临时路径）。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")
    image_content = await image.read()
    if not image_content:
        raise HTTPException(400, "参考图片为空")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {"prompt": prompt, "size": size, "strength": strength, "model": model, "project_id": project_id, "negative": negative}
    if sync:
        payload["image"] = base64.b64encode(image_content).decode()
        return await _image_i2i_worker(payload)
    payload["image"] = await _write_file_field(image_content)
    task = create_task("image_i2i", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "图生图任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


# ── 编辑 API ──────────────────────────────────────────────────
@router.post("/edit/crop")
async def crop_image(
    image: UploadFile = File(...), x1: int = Form(0), y1: int = Form(0), x2: int = Form(100), y2: int = Form(100)
):
    """剪裁图片（百分比坐标）"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))

    w, h = img.size
    crop_box = (int(x1 * w / 100), int(y1 * h / 100), int(x2 * w / 100), int(y2 * h / 100))

    cropped = img.crop(crop_box)
    filename = await asyncio.to_thread(save_image, cropped)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}", "size": cropped.size}


@router.post("/edit/resize")
async def resize_image(
    image: UploadFile = File(...), width: int = Form(1024), height: int = Form(1024), maintain_aspect: bool = Form(True)
):
    """调整大小"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))

    if maintain_aspect:
        img.thumbnail((width, height), Image.LANCZOS)
    else:
        img = img.resize((width, height), Image.LANCZOS)

    filename = await asyncio.to_thread(save_image, img)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}", "size": img.size}


@router.post("/edit/background-remove")
async def remove_background(image: UploadFile = File(...)):
    """简单抠图：基于颜色阈值"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content)).convert("RGBA")

    w, h = img.size
    # 检测背景色
    corner_colors = [
        img.getpixel((0, 0)),
        img.getpixel((w - 1, 0)),
        img.getpixel((0, h - 1)),
        img.getpixel((w - 1, h - 1)),
    ]

    from collections import Counter

    bg_color = Counter(corner_colors).most_common(1)[0][0]

    # 创建掩码（numpy 向量化，O(1) 通道级运算替代逐像素循环）
    arr = np.asarray(img.convert("RGB"))
    bg_arr = np.array(bg_color[:3], dtype=arr.dtype)
    # 与原逻辑等价：每个通道差都 < 30（取最大通道差 < 30）
    distance = np.abs(arr.astype(np.int16) - bg_arr).max(axis=2)
    mask_arr = np.where(distance < 30, 0, 255).astype(np.uint8)
    mask = Image.fromarray(mask_arr, "L")

    result = img.copy()
    result.putalpha(mask)

    # 透明抠图输出：保留 alpha 通道（save_image 默认白底合成，keep_alpha 跳过）
    filename = await asyncio.to_thread(save_image, result, "PNG", True)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/blur")
async def blur_image(image: UploadFile = File(...), radius: int = Form(5)):
    """高斯模糊"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))

    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    filename = await asyncio.to_thread(save_image, blurred)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/text-overlay")
async def text_overlay(
    image: UploadFile = File(...),
    text: str = Form("Hello World"),
    font_size: int = Form(48),
    color: str = Form("#FFFFFF"),
    x: int = Form(50),
    y: int = Form(50),
):
    """文字叠加"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content)).convert("RGBA")

    # 创建透明图层
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = get_font(font_size)
    except Exception:
        font = ImageFont.load_default()

    # 解析颜色
    r = int(color[1:3], 16) if color.startswith("#") and len(color) == 7 else 255
    g = int(color[3:5], 16) if color.startswith("#") and len(color) == 7 else 255
    b = int(color[5:7], 16) if color.startswith("#") and len(color) == 7 else 255

    draw.text((x, y), text, fill=(r, g, b, 255), font=font)

    # 合成
    result = Image.alpha_composite(img, overlay)
    filename = await asyncio.to_thread(save_image, result)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/batch-resize")
async def batch_resize(images: list[UploadFile] = File(...), width: int = Form(800), height: int = Form(800)):
    """批量调整大小"""
    results = []
    for image in images:
        content = await image.read()
        img = Image.open(io.BytesIO(content))
        img = img.resize((width, height), Image.LANCZOS)
        filename = await asyncio.to_thread(save_image, img)
        results.append({"filename": filename, "url": f"/api/image-factory/images/{filename}"})
    return {"results": results, "total": len(results)}


@router.post("/edit/rotate")
async def rotate_image(image: UploadFile = File(...), angle: int = Form(0)):
    """旋转图片"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))
    rotated = img.rotate(angle, expand=True)
    filename = await asyncio.to_thread(save_image, rotated)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}", "angle": angle}


@router.post("/edit/flip")
async def flip_image(image: UploadFile = File(...), direction: str = Form("horizontal")):
    """翻转图片"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))
    if direction == "horizontal":
        flipped = img.transpose(Image.FLIP_LEFT_RIGHT)
    else:
        flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
    filename = await asyncio.to_thread(save_image, flipped)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/filter")
async def apply_filter(
    image: UploadFile = File(...),
    filter_type: str = Form("none"),
    intensity: float = Form(0.5),
):
    """应用滤镜"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))

    if filter_type == "grayscale":
        result = img.convert("L").convert("RGB")
    elif filter_type == "sepia":
        result = img.filter(ImageFilter.FIND_EDGES)
        result = result.filter(ImageFilter.EMBOSS)
    elif filter_type == "blur":
        radius = int(intensity * 20)
        result = img.filter(ImageFilter.GaussianBlur(radius=radius))
    elif filter_type == "sharpen":
        result = img.filter(ImageFilter.SHARPEN)
    elif filter_type == "emboss":
        result = img.filter(ImageFilter.EMBOSS)
    elif filter_type == "contour":
        result = img.filter(ImageFilter.FIND_EDGES)
    else:
        result = img

    filename = await asyncio.to_thread(save_image, result)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}", "filter": filter_type}


@router.post("/edit/adjust")
async def adjust_image(
    image: UploadFile = File(...),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
):
    """调整图片参数"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content)).convert("RGB")

    # 调整亮度
    from PIL import ImageEnhance

    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness)

    # 调整对比度
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(contrast)

    # 调整饱和度
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(saturation)

    filename = await asyncio.to_thread(save_image, img)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/watermark")
async def add_watermark(
    image: UploadFile = File(...),
    text: str = Form(" watermark"),
    position: str = Form("bottom-right"),
    opacity: float = Form(0.5),
    font_size: int = Form(24),
):
    """添加水印"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content)).convert("RGBA")

    # 创建水印图层
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = get_font(font_size)
    except Exception:
        font = ImageFont.load_default()

    # 计算水印位置
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    if position == "bottom-right":
        x = img.size[0] - text_width - 20
        y = img.size[1] - text_height - 20
    elif position == "bottom-left":
        x = 20
        y = img.size[1] - text_height - 20
    elif position == "top-right":
        x = img.size[0] - text_width - 20
        y = 20
    elif position == "top-left":
        x = 20
        y = 20
    else:  # center
        x = (img.size[0] - text_width) // 2
        y = (img.size[1] - text_height) // 2

    # 绘制水印（半透明）
    alpha = int(255 * opacity)
    draw.text((x, y), text, fill=(255, 255, 255, alpha), font=font)

    # 合成
    result = Image.alpha_composite(img, overlay)
    filename = await asyncio.to_thread(save_image, result)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


# ── 模板管理 API ──────────────────────────────────────────────
@router.get("/templates")
async def list_templates():
    """列出所有模板"""
    templates = []
    if os.path.exists(TEMPLATE_DIR):
        for f in os.listdir(TEMPLATE_DIR):
            if f.endswith(".json"):
                filepath = os.path.join(TEMPLATE_DIR, f)
                with open(filepath, encoding="utf-8") as fh:
                    template = json.load(fh)
                    templates.append(template)
    templates.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return templates


@router.post("/template/create")
async def create_template(req: dict):
    """创建模板"""
    template_id = generate_id()
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")

    template = {
        "id": template_id,
        "name": req.get("name", "未命名模板"),
        "width": req.get("width", 1080),
        "height": req.get("height", 1920),
        "background": req.get("background", "#FFFFFF"),
        "layers": req.get("layers", []),
        "created_at": datetime.now().isoformat(),
    }

    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return template


async def _image_template_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """渲染模板生成图片（同步/异步任务共用执行体）。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    template_id = payload.get("template_id")
    overrides = payload.get("overrides") or {}
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if not os.path.exists(template_path):
        raise HTTPException(404, "模板不存在")

    with open(template_path, encoding="utf-8") as f:
        template = json.load(f)

    width = overrides.get("width", template.get("width", 1080))
    height = overrides.get("height", template.get("height", 1920))
    bg_color = overrides.get("background", template.get("background", "#FFFFFF"))

    _report(30, "正在渲染模板…")
    # 背景：支持渐变简写 "#A→#B"（自上而下），否则纯色
    if isinstance(bg_color, str) and "→" in bg_color:
        from image_edit_engine import make_gradient

        top_hex, bottom_hex = (bg_color.split("→") + ["#FFFFFF"])[:2]
        img = make_gradient(width, height, top_hex.strip(), bottom_hex.strip())
    else:
        img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    for layer in template.get("layers", []):
        layer_type = layer.get("type")

        if layer_type == "rect":
            # 圆角矩形底（卡片/横幅/按钮底）
            x = int(layer.get("x", 0))
            y = int(layer.get("y", 0))
            w = int(layer.get("width", 200))
            h = int(layer.get("height", 60))
            radius = int(layer.get("radius", 16))
            fill = layer.get("fill", "#FFFFFF")
            opacity = float(layer.get("opacity", 1.0))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            od = ImageDraw.Draw(overlay)
            od.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill)
            if opacity < 1.0:
                overlay = overlay.filter(ImageFilter.GaussianBlur(0))
                overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
            img.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(img)

        if layer_type == "text":
            x = int(layer.get("x", 0))
            y = int(layer.get("y", 0))
            key = layer.get("key", "")
            default_text = layer.get("text", "")
            text = str(overrides.get(key, default_text) or "")
            font_size = int(layer.get("font_size", 24))
            font_color = layer.get("color", "#000000")
            align = layer.get("align", "left")
            max_width = int(layer.get("max_width", 0) or 0)
            shadow = layer.get("shadow", "")

            try:
                font = get_font(font_size)
            except Exception:
                font = ImageFont.load_default()

            # 自动换行（max_width>0 时按像素宽度折行）
            if max_width > 0:
                lines, cur = [], ""
                for ch in text:
                    if draw.textlength(cur + ch, font=font) > max_width:
                        lines.append(cur)
                        cur = ch
                    else:
                        cur += ch
                if cur:
                    lines.append(cur)
                text_lines = lines or [""]
            else:
                text_lines = text.split("\n") or [""]

            line_h = int(font_size * 1.35)
            for i, line in enumerate(text_lines):
                lx = x
                if align == "center":
                    lx = x + (max_width - int(draw.textlength(line, font=font))) // 2
                elif align == "right":
                    lx = x + max_width - int(draw.textlength(line, font=font))
                ly = y + i * line_h
                if shadow:
                    try:
                        sx, sy = (int(v) for v in shadow.split(","))
                        draw.text((lx + sx, ly + sy), line, fill="#00000080", font=font)
                    except Exception:
                        draw.text((lx + 2, ly + 2), line, fill="#00000080", font=font)
                draw.text((lx, ly), line, fill=font_color, font=font)

        elif layer_type == "image":
            image_url = layer.get("url", "")
            if image_url and image_url.startswith("http"):
                try:
                    resp = await asyncio.to_thread(requests.get, image_url, timeout=30)
                    layer_img = Image.open(io.BytesIO(resp.content))
                    layer_img = layer_img.convert("RGBA")

                    x = layer.get("x", 0)
                    y = layer.get("y", 0)
                    w = layer.get("width", 200)
                    h = layer.get("height", 200)
                    layer_img = layer_img.resize((w, h), Image.LANCZOS)

                    img.paste(layer_img, (x, y), layer_img)
                except Exception as e:
                    logger.warning(f"Layer image error: {e}")

    filename = save_image(img)
    _report(100, "模板渲染完成")
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/template/render")
async def render_template(
    req: dict,
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """渲染模板（默认异步任务，立即返回 task_id）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    if sync:
        return await _image_template_worker(req)
    task = create_task("image_template", req, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "模板渲染任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


@router.post("/template/upload")
async def upload_template(file: UploadFile = File(...), name: str = Form(None)):
    """上传模板"""
    content = await file.read()

    try:
        template = json.loads(content)
    except Exception as e:
        raise HTTPException(400, "无效的模板格式") from e

    template_id = generate_id()
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")

    template["id"] = template_id
    template["name"] = name or template.get("name", "上传模板")
    template["created_at"] = datetime.now().isoformat()

    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    return {"id": template_id, "name": template["name"]}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """删除模板"""
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if os.path.exists(template_path):
        os.remove(template_path)
    return {"success": True}


# ── 人像分割 API ─────────────────────────────────────────────
@router.post("/edit/personal-segmentation")
async def person_segmentation(
    image: UploadFile = File(...),
    feather: int = Form(0, description="边缘羽化半径（0-8，发丝/毛边场景建议 2）"),
):
    """人像分割 - 将人物从背景中分离（rembg 语义分割，失败回退旧椭圆近似）。"""
    try:
        content = await image.read()
        img = Image.open(BytesIO(content))
        try:
            from image_edit_engine import remove_background

            result = await asyncio.to_thread(remove_background, img, max(0, min(8, int(feather))))
        except Exception as e:  # noqa: BLE001 — rembg 不可用时降级旧椭圆近似
            logger.warning(f"rembg 分割不可用，回退椭圆近似: {e}")
            mask = Image.new("L", img.size, 0)
            draw = ImageDraw.Draw(mask)
            w, h = img.size
            draw.ellipse([w * 0.2, h * 0.05, w * 0.8, h * 0.95], fill=255)
            result = img.convert("RGBA")
            result.putalpha(mask)

        filename = await asyncio.to_thread(save_image, result, "PNG", True)
        return {"id": filename, "url": f"/api/image-factory/images/{filename}"}

    except Exception as e:
        raise HTTPException(500, f"人像分割失败: {str(e)}") from e


# ── 虚拟试衣 API ──────────────────────────────────────────────
async def _image_tryon_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """虚拟试衣（同步/异步任务共用执行体，异步时回报进度）。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    person_content = _read_file_field(payload, "person_image")
    clothing_content = _read_file_field(payload, "clothing_image")
    if not person_content or not clothing_content:
        raise HTTPException(400, "请上传人物照片与衣物照片")
    description = payload.get("description") or ""
    style = payload.get("style") or "casual"
    background = payload.get("background") or "beach"
    project_id = payload.get("project_id") or ""

    try:
        _report(10, "正在识别衣物特征…")
        _img = Image.open(BytesIO(clothing_content))

        # 生成描述性提示词
        style_prompts = {
            "casual": "casual outfit, relaxed fit, everyday wear",
            "formal": "formal attire, elegant, business suit, professional",
            "sporty": "athletic wear, sporty outfit, active lifestyle",
            "fashion": "high fashion, designer clothing, runway style",
        }

        background_prompts = {
            "beach": "sandy beach, ocean waves, palm trees, sunset, tropical paradise",
            "city": "urban city street, modern buildings, street lights, busy atmosphere",
            "space": "futuristic space station, stars, nebula, sci-fi background",
            "studio": "professional photography studio, neutral background, soft lighting",
            "forest": "lush forest, sunlight filtering through trees, nature path",
            "snow": "snowy mountain landscape, winter wonderland, snow-capped peaks",
        }

        # 用多模态文本模型自动识别衣物特征（颜色/款式/面料/图案）
        clothing_description = description
        try:
            from common.config import MODEL_NAME

            clothing_data_uri_desc = f"data:image/png;base64,{base64.b64encode(clothing_content).decode('utf-8')}"
            analyze_payload = {
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {"url": clothing_data_uri_desc},
                            },
                            {
                                "type": "text",
                                "text": (
                                    "Describe this garment in detail for a virtual try-on system. "
                                    "Include: exact color(s), clothing type, fabric/material, pattern, "
                                    "length, sleeves, style details. Reply in English, one concise paragraph."
                                ),
                            },
                        ],
                    }
                ],
                "max_tokens": 200,
            }
            analyze_resp = await asyncio.to_thread(
                requests.post,
                f"{AGNES_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
                json=analyze_payload,
                timeout=60,
            )
            if analyze_resp.status_code == 200:
                ad = analyze_resp.json()
                auto_desc = ad.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if auto_desc:
                    clothing_description = auto_desc
        except Exception as e:
            logger.warning(f"衣物识别失败，使用用户描述: {e}")

        _report(30, "正在生成试穿效果…")
        prompt = f"{description} {style_prompts.get(style, style_prompts['casual'])}, high quality fashion photography, professional lighting"
        bg_prompt = background_prompts.get(background, background_prompts["beach"])

        # 将图像转换为 Data URI Base64
        person_data_uri = f"data:image/png;base64,{base64.b64encode(person_content).decode('utf-8')}"
        clothing_data_uri = f"data:image/png;base64,{base64.b64encode(clothing_content).decode('utf-8')}"

        # 强化提示词：保持人物特征不变，只更换衣服
        # 第一张图 = 人物本人，第二张图 = 要穿的衣物
        style_prompt = style_prompts.get(style, style_prompts["casual"])
        bg_prompt = background_prompts.get(background, background_prompts["beach"])

        # 调用 Agnes AI 多图合成 API（messages 多模态格式，理解更准确）
        messages_content = [
            {
                "type": "image_url",
                "image_url": {"url": person_data_uri},
            },
            {
                "type": "text",
                "text": (
                    "This is the person. IMPORTANT: keep this exact same person — "
                    "same face, body, hair, skin, pose, and identity. Do NOT change the person."
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": clothing_data_uri},
            },
            {
                "type": "text",
                "text": (
                    f"This is the garment to wear ({style_prompt}). "
                    f"Exact garment details: {clothing_description}. "
                    f"Dress the person from the first image in exactly this garment from the second image "
                    f"(match the described color, type and pattern precisely). "
                    f"New background: {bg_prompt}. "
                    "Photorealistic, high resolution, the person looks natural wearing the garment."
                ),
            },
        ]

        response = await asyncio.to_thread(
            requests.post,
            f"{AGNES_API_BASE}/images/generations",
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "agnes-image-2.1-flash",
                "messages": [{"role": "user", "content": messages_content}],
                "size": "1024x1024",
                "n": 1,
                "extra_body": {"response_format": "url"},
            },
            timeout=120,
        )

        if response.status_code != 200:
            raise HTTPException(500, f"生成失败: {response.text}")

        data = response.json()
        if not data.get("data"):
            raise HTTPException(500, f"生成失败: {data}")

        # API 返回 url 或 b64_json，两种都要兼容
        first_item = data["data"][0]
        image_url = first_item.get("url")
        if image_url:
            img_resp = await asyncio.to_thread(requests.get, image_url, timeout=60)
            img_resp.raise_for_status()
            result_img = Image.open(BytesIO(img_resp.content))
        elif first_item.get("b64_json"):
            img_data = base64.b64decode(first_item["b64_json"])
            result_img = Image.open(BytesIO(img_data))
        else:
            raise HTTPException(500, f"生成失败: {data}")

        filename = save_image(result_img)
        art_id = _save_artifact(
            filename, project_id, prompt, {"style": style, "background": background, "feature": "try-on"}
        )
        _report(100, "试穿效果已生成")
        return {
            "id": filename,
            "artifact_id": art_id,
            "url": f"/api/image-factory/images/{filename}",
            "prompt": prompt,
            "style": style,
            "background": background,
            "project_id": project_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"虚拟试衣失败: {str(e)}") from e


@router.post("/try-on/generate")
async def virtual_try_on(
    person_image: UploadFile = File(...),
    clothing_image: UploadFile = File(...),
    description: str = Form(""),
    style: str = Form("casual"),  # casual, formal, sporty, fashion
    background: str = Form("beach"),  # beach, city, space, studio, etc.
    project_id: str = Form(""),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """
    虚拟试衣功能（默认异步任务；异步时图片暂存临时路径）
    - 上传人物照片
    - 上传衣物照片
    - AI 生成试穿效果
    - 可选择背景场景
    """
    person_content = await person_image.read()
    clothing_content = await clothing_image.read()
    if not person_content or not clothing_content:
        raise HTTPException(400, "请上传人物照片与衣物照片")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {"description": description, "style": style, "background": background, "project_id": project_id}
    if sync:
        payload["person_image"] = base64.b64encode(person_content).decode()
        payload["clothing_image"] = base64.b64encode(clothing_content).decode()
        return await _image_tryon_worker(payload)
    payload["person_image"] = await _write_file_field(person_content)
    payload["clothing_image"] = await _write_file_field(clothing_content)
    task = create_task("image_tryon", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "虚拟试衣任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


# ── 背景替换 API ──────────────────────────────────────────────
@router.post("/edit/replace-background")
async def replace_background(
    image: UploadFile = File(...),
    background: str = Form("beach"),
    force_color: str = Form(""),  # 可选：强制使用指定颜色
    ai_background: str = Form("", description="AI 背景描述（非空时调用文生图生成真实场景背景，失败回退场景渐变）"),
):
    """背景替换 - rembg 语义分割人物 + 新背景合成（场景渐变 / 纯色 / AI 生成）。"""
    try:
        content = await image.read()
        img = Image.open(BytesIO(content))
        img = img.convert("RGBA")
        w, h = img.size

        # 1. 背景底图：AI 描述 > 纯色 > 场景渐变
        bg_img = None
        if ai_background.strip():
            try:
                bg_resp = await asyncio.to_thread(
                    requests.post,
                    f"{AGNES_API_BASE}/images/generations",
                    headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "agnes-image-2.1-flash",
                        "prompt": f"{ai_background.strip()}, wide background, no people, no text, soft lighting",
                        "size": f"{w}x{h}",
                        "n": 1,
                    },
                    timeout=120,
                )
                if bg_resp.status_code == 200 and (bg_resp.json().get("data") or []):
                    first = bg_resp.json()["data"][0]
                    bg_url = first.get("url")
                    if bg_url:
                        bg_raw = await asyncio.to_thread(requests.get, bg_url, timeout=60)
                        bg_img = Image.open(BytesIO(bg_raw.content)).convert("RGB").resize((w, h), Image.LANCZOS)
            except Exception as e:  # noqa: BLE001 — AI 背景失败静默回退场景渐变
                logger.warning(f"AI 背景生成失败，回退场景渐变: {e}")
        if bg_img is None and force_color:
            try:
                r, g, b = tuple(int(force_color[i : i + 2], 16) for i in (1, 3, 5))
                bg_img = Image.new("RGB", (w, h), (r, g, b))
            except Exception:
                pass
        if bg_img is None:
            from image_edit_engine import make_scene_background

            bg_img = make_scene_background(w, h, background or "studio")

        # 2. 分割前景：rembg 语义分割，失败回退（整图透明化兜底）
        try:
            from image_edit_engine import compose_foreground, remove_background

            fg = await asyncio.to_thread(remove_background, img)
            result = await asyncio.to_thread(compose_foreground, fg, bg_img)
        except Exception as e:  # noqa: BLE001 — rembg 不可用时降级：整图贴底
            logger.warning(f"rembg 分割不可用，降级整图合成: {e}")
            result = bg_img.convert("RGBA")
            result.paste(img, (0, 0), img.split()[3] if img.mode == "RGBA" else None)

        filename = await asyncio.to_thread(save_image, result)
        return {
            "id": filename,
            "url": f"/api/image-factory/images/{filename}",
            "background": background,
            "ai_background": ai_background.strip() or None,
        }

    except Exception as e:
        raise HTTPException(500, f"背景替换失败: {str(e)}") from e


# ── 预置电商模板 ──────────────────────────────────────────────
def init_templates():
    """初始化预置模板"""
    templates = [
        {
            "id": "tmplt_taobao_main",
            "name": "淘宝主图模板",
            "width": 800,
            "height": 800,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "product_image", "x": 100, "y": 100, "width": 600, "height": 600},
                {
                    "type": "text",
                    "key": "title",
                    "x": 50,
                    "y": 720,
                    "font_size": 28,
                    "color": "#333333",
                    "text": "商品标题",
                },
                {
                    "type": "text",
                    "key": "price",
                    "x": 50,
                    "y": 760,
                    "font_size": 24,
                    "color": "#FF4400",
                    "text": "¥199",
                },
            ],
        },
        {
            "id": "tmplt_xiaohongshu",
            "name": "小红书封面模板",
            "width": 1080,
            "height": 1440,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "cover_image", "x": 0, "y": 0, "width": 1080, "height": 900},
                {
                    "type": "text",
                    "key": "title",
                    "x": 50,
                    "y": 950,
                    "font_size": 40,
                    "color": "#000000",
                    "text": "标题文字",
                },
                {
                    "type": "text",
                    "key": "subtitle",
                    "x": 50,
                    "y": 1000,
                    "font_size": 28,
                    "color": "#666666",
                    "text": "副标题",
                },
            ],
        },
        {
            "id": "tmplt_douyin",
            "name": "抖音封面模板",
            "width": 1080,
            "height": 1920,
            "background": "#000000",
            "layers": [
                {"type": "image", "key": "cover_image", "x": 0, "y": 0, "width": 1080, "height": 1920},
                {
                    "type": "text",
                    "key": "title",
                    "x": 50,
                    "y": 1700,
                    "font_size": 48,
                    "color": "#FFFFFF",
                    "text": "视频标题",
                },
            ],
        },
        {
            "id": "tmplt_jd_main",
            "name": "京东主图模板",
            "width": 800,
            "height": 800,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "product_image", "x": 100, "y": 100, "width": 600, "height": 600},
                {
                    "type": "text",
                    "key": "title",
                    "x": 50,
                    "y": 720,
                    "font_size": 28,
                    "color": "#333333",
                    "text": "商品标题",
                },
                {
                    "type": "text",
                    "key": "price",
                    "x": 50,
                    "y": 760,
                    "font_size": 24,
                    "color": "#FF0000",
                    "text": "¥199",
                },
            ],
        },
        {
            "id": "tmplt_pinduoduo",
            "name": "拼多多主图模板",
            "width": 800,
            "height": 800,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "product_image", "x": 100, "y": 100, "width": 600, "height": 500},
                {
                    "type": "text",
                    "key": "discount",
                    "x": 100,
                    "y": 650,
                    "font_size": 32,
                    "color": "#FF4400",
                    "text": "限时特惠",
                },
                {
                    "type": "text",
                    "key": "price",
                    "x": 100,
                    "y": 700,
                    "font_size": 28,
                    "color": "#333333",
                    "text": "¥99",
                },
            ],
        },
        # 新增商用模板
        {
            "id": "tmplt_insta_post",
            "name": "Instagram 帖子",
            "width": 1080,
            "height": 1080,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "cover_image", "x": 0, "y": 0, "width": 1080, "height": 1080},
            ],
        },
        {
            "id": "tmplt_facebook_ad",
            "name": "Facebook 广告",
            "width": 1200,
            "height": 628,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "cover_image", "x": 0, "y": 0, "width": 1200, "height": 628},
                {
                    "type": "text",
                    "key": "cta",
                    "x": 50,
                    "y": 550,
                    "font_size": 36,
                    "color": "#1877F2",
                    "text": "立即购买",
                },
            ],
        },
        {
            "id": "tmplt_weibo_ad",
            "name": "微博广告",
            "width": 1080,
            "height": 608,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "cover_image", "x": 0, "y": 0, "width": 1080, "height": 608},
            ],
        },
        {
            "id": "tmplt_baidu_ad",
            "name": "百度推广",
            "width": 340,
            "height": 260,
            "background": "#FFFFFF",
            "layers": [
                {"type": "image", "key": "cover_image", "x": 20, "y": 20, "width": 300, "height": 200},
                {
                    "type": "text",
                    "key": "title",
                    "x": 20,
                    "y": 230,
                    "font_size": 16,
                    "color": "#000000",
                    "text": "推广标题",
                },
            ],
        },
        {
            "id": "tmplt_coupon",
            "name": "优惠券模板",
            "width": 800,
            "height": 400,
            "background": "#FF4444",
            "layers": [
                {"type": "image", "key": "logo", "x": 30, "y": 30, "width": 100, "height": 100},
                {
                    "type": "text",
                    "key": "discount",
                    "x": 150,
                    "y": 120,
                    "font_size": 48,
                    "color": "#FFFFFF",
                    "text": "¥50",
                },
                {
                    "type": "text",
                    "key": "title",
                    "x": 150,
                    "y": 180,
                    "font_size": 24,
                    "color": "#FFFFFF",
                    "text": "限时优惠券",
                },
            ],
        },
    ]

    for tmpl in templates:
        tmpl_path = os.path.join(TEMPLATE_DIR, f"{tmpl['id']}.json")
        if not os.path.exists(tmpl_path):
            with open(tmpl_path, "w", encoding="utf-8") as f:
                json.dump(tmpl, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化模板：{tmpl['name']}")


# 启动时初始化模板
init_templates()


async def _image_t2i_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：文生图。"""
    return await _image_t2i_worker(payload, progress=update)


async def _image_i2i_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：图生图。"""
    return await _image_i2i_worker(payload, progress=update)


async def _image_template_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：模板渲染。"""
    return await _image_template_worker(payload, progress=update)


async def _image_tryon_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：虚拟试衣。"""
    return await _image_tryon_worker(payload, progress=update)


def _cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
    """cover 模式适配目标规格：等比放大至覆盖目标尺寸后居中裁剪（不变形）。"""
    ratio = max(w / img.width, h / img.height)
    new_w, new_h = round(img.width * ratio), round(img.height * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _upscale2x(img: Image.Image) -> Image.Image:
    """2 倍保真放大（lanczos）+ 轻度锐化，适合平台高清展示与印刷。"""
    img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=3))


@router.post("/publish-pack")
async def image_publish_pack(
    ids: list[str] = Form(...),
    platform: str = Form("xiaohongshu"),
    pack_title: str = Form("AI 原创插画集"),
    upscale: bool = Form(True, description="是否附带 2 倍高清版"),
    current_user: dict = require_auth(),
):
    """图片发布包：选中图片按平台规格输出成品 + 高清版 + 上架文案 + 质量报告，一键下载。"""
    preset = next((p for p in PLATFORM_PRESETS if p["id"] == platform), None)
    if not preset:
        raise HTTPException(400, f"未知平台规格: {platform}")
    pack_title = (pack_title or "AI 原创插画集").strip()[:60]
    picked = [f for f in ids if os.path.exists(os.path.join(IMAGE_DIR, f))][:50]
    if not picked:
        raise HTTPException(400, "没有可打包的图片（请先勾选已生成的图片）")

    w, h = preset["w"], preset["h"]
    root = pack_dir_name("image_release")
    entries: dict = {}
    img_checks = []
    for i, fname in enumerate(picked, 1):
        with Image.open(os.path.join(IMAGE_DIR, fname)) as im:
            img_checks.append(quality_check_image(im))
            out = _cover_fit(im.convert("RGB"), w, h)
            b = io.BytesIO()
            out.save(b, "JPEG", quality=95)
            stem = f"{i:02d}_{os.path.splitext(fname)[0]}"
            entries[f"{root}/成品/{stem}.jpg"] = b.getvalue()
            if upscale:
                hi = _upscale2x(out)
                b2 = io.BytesIO()
                hi.save(b2, "JPEG", quality=95)
                entries[f"{root}/高清版/{stem}@2x.jpg"] = b2.getvalue()

    # 上架文案：标题/描述/标签（模板 + 平台建议标签，可直接复制发布）
    tags = " ".join(_PLATFORM_TAGS.get(platform, []))
    entries[f"{root}/上架文案.md"] = (
        f"# {pack_title}\n\n## 标题\n{pack_title}\n\n"
        f"## 描述\n{pack_title}，AI 原创数字插画，可用于壁纸/头像/自媒体配图/电商主图等场景。\n"
        f"## 标签\n{tags}\n\n## 使用建议\n"
        "- 发布后 1 小时内回复评论可提升流量；\n"
        "- 同一组图可拆分为多篇笔记/图文发布，增加曝光；\n"
        f"- 本包共 {len(picked)} 张，规格 {preset['ratio']}（{w}×{h}）。"
    )
    entries[f"{root}/规格说明.md"] = platform_spec_text(preset["name"], _PLATFORM_SPECS.get(platform, []))
    entries[f"{root}/LICENSE.txt"] = license_text(f"图片发布包《{pack_title}》")

    # 生产级内容保障：质量自检报告（规格合规 + 美观度评分）
    try:
        avg = int(sum(q.get("score", 0) for q in img_checks) / max(len(img_checks), 1))
        prompts = []
        try:
            from common.db import get_db

            conn = get_db()
            for fname in picked:
                row = conn.execute(
                    "SELECT metadata FROM artifacts WHERE media_url=? AND active=1",
                    (f"/api/image-factory/images/{fname}",),
                ).fetchone()
                if row:
                    try:
                        prompts.append(json.loads(row["metadata"] or "{}").get("prompt", ""))
                    except Exception:
                        pass
            conn.close()
        except Exception:
            pass
        text_check = None
        for p in prompts:
            if p:
                rc = check_text(p, "prompt")
                if not rc["ok"]:
                    text_check = rc
                    break
        extra = [
            f"规格合规：{w}×{h}（{preset['ratio']}）{'✓' if img_checks else '✗'}",
            f"高清版：{'已附带 2× 高清版' if upscale else '未附带'}",
            f"平均美观度：{avg}/100",
        ]
        entries[f"{root}/质量自检报告.md"] = quality_report(
            f"图片发布包《{pack_title}》",
            text_check=text_check,
            image_quality={
                "score": avg,
                "grade": "A" if avg >= 85 else ("B" if avg >= 65 else "C"),
                "checks": [],
                "suggestions": [],
            },
            extra=extra,
        )
    except Exception as e:
        logger.debug(f"图片质量自检报告生成失败: {e}")

    buf = build_publish_zip(entries, "image_release")
    publish = publish_registry.publish("image_platform", {"platform": platform, "count": len(picked)})
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="image_release_{int(time.time())}.zip"',
            "X-Publish-Result": f"published={str(publish.get('published')).lower()}",
        },
    )


register_handler("image_t2i", _image_t2i_handler, user_limit=2)
register_handler("image_i2i", _image_i2i_handler, user_limit=2)
register_handler("image_template", _image_template_handler, user_limit=2)
register_handler("image_tryon", _image_tryon_handler, user_limit=2)
