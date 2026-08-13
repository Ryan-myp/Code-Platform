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
from common.llm import api_error_detail, _safe_exc_msg
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


# ── 字体系统：family/粗细/斜体（PIL 无内置粗斜体时用描边模拟粗体）──
# family → (候选字体路径列表, 斜体候选 face index, 是否支持中文, 粗体 face index 或 None)
# 多平台路径覆盖：macOS（本机）+ Windows + Linux（Docker 已装 Noto/WQY）
# 真实粗体：Hiragino Sans GB 的 W6（index 2）可用于 bold，其余 family 用描边模拟
# macOS Catalina+ PingFang 存储在 Asset Catalog 路径，非标准 /System/Library/Fonts/
_ASSET_PINGFANG = "/System/Library/AssetsV2/com_apple_MobileAsset_Font7/3419f2a427639ad8c8e139149a287865a90fa17e.asset/AssetData/PingFang.ttc"

FONT_FAMILIES = [
    ("pingfang", [(_ASSET_PINGFANG, 1), ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0), ("/System/Library/Fonts/STHeiti Medium.ttc", 1), ("C:/Windows/Fonts/msyh.ttc", 0)], True, None),
    ("helvetica", [("/System/Library/Fonts/Helvetica.ttc", 1), ("/Library/Fonts/Arial.ttf", 0), ("C:/Windows/Fonts/arial.ttf", 0)], False, None),
    ("hiragino", [("/System/Library/Fonts/Hiragino Sans GB.ttc", 0), ("/System/Library/Fonts/STHeiti Medium.ttc", 1)], True, 2),
    ("heiti", [("/System/Library/Fonts/STHeiti Medium.ttc", 1), ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0)], True, None),
    ("songti", [("/System/Library/Fonts/STSongti-SC-Regular.otf", 0), ("/System/Library/Fonts/Songti.ttc", 0), ("C:/Windows/Fonts/simsun.ttc", 0)], True, None),
    ("arial", [("/Library/Fonts/Arial.ttf", 0), ("C:/Windows/Fonts/arial.ttf", 0)], False, None),
    ("times", [("/Library/Fonts/Times New Roman.ttf", 1), ("C:/Windows/Fonts/times.ttf", 0)], False, None),
    ("noto", [("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0), ("/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc", 0), ("C:/Windows/Fonts/msyh.ttc", 0)], True, None),
    ("wqy", [("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0), ("/usr/share/fonts/wqy-microhei/wqy-microhei.ttc", 0)], True, None),
]

# 最后兜底：常见中文字体（mac/win/linux），保证中文文本永远可用
_FALLBACK_FONTS = [
    ("/Library/Fonts/Arial Unicode.ttf", 0),
    (_ASSET_PINGFANG, 1),
    ("/System/Library/Fonts/Hiragino Sans GB.ttc", 0),
    ("/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ("/System/Library/Fonts/STSongti-SC-Regular.otf", 0),
    ("C:/Windows/Fonts/msyh.ttc", 0),
    ("C:/Windows/Fonts/simhei.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
]


def _has_cjk(text: str) -> bool:
    """是否包含中日韩表意/全角字符（含中文标点），含则必须使用支持中文的字体。"""
    return any(
        "\u4e00" <= ch <= "\u9fff"  # CJK 统一表意
        or "\u3400" <= ch <= "\u4dbf"  # CJK 扩展 A
        or "\uf900" <= ch <= "\ufaff"  # CJK 兼容表意
        or "\u3000" <= ch <= "\u303f"  # CJK 标点（。、【】等）
        or "\uff00" <= ch <= "\uffef"  # 全角/半角（￥、……等）
        for ch in text
    )



def _initialize_compute_context(data: dict) -> dict:
    """初始化计算上下文。"""
    return {"data": data, "results": {}, "status": "running"}

def _execute_compute_step(step_name: str, step_data: dict) -> dict:
    """执行计算步骤。"""
    return {"step": step_name, "status": "completed", "data": step_data}

def _aggregate_compute_results(results: list) -> dict:
    """聚合计算结果。"""
    return {"total_steps": len(results), "aggregated": results}


def _prepare_context(**kwargs) -> dict:
    """准备执行上下文。"""
    return {"context": kwargs, "status": "initialized", "data": {}}

def _execute_step(step_name: str, step_data: dict) -> dict:
    """执行处理步骤。"""
    return {"step": step_name, "status": "completed", "data": step_data}

def _finalize_results(results: list) -> dict:
    """汇总最终结果。"""
    return {"total_steps": len(results), "results": results, "status": "completed"}

def get_font(size: int = 24, family: str = "", bold: bool = False, italic: bool = False,
             text: str = "") -> ImageFont.FreeTypeFont:
    """获取字体：按 family 选择，多平台兜底；文本含中文时强制使用支持中文的字体（避免【】方块）。

    bold 优先使用 family 的真实粗体 face（如 Hiragino W6），无真实粗体时由调用方用描边模拟；
    italic 尝试 face index 1。
    """
    prefer_cjk = _has_cjk(text)
    fam = (family or "").strip().lower()
    path, face_idx = None, 0
    # 1) 指定 family（文本含中文时，仅接受本身支持中文的 family，避免 Helvetica 等渲染中文变方块）
    entry = next((e for e in FONT_FAMILIES if e[0] == fam), None)
    if entry and (not prefer_cjk or entry[2]):
        for fp, ii in entry[1]:
            if os.path.exists(fp):
                path, face_idx = fp, ii
                break
    # 2) 兜底：按序找可用字体（中文文本优先中文字体）
    if path is None:
        pool = FONT_FAMILIES if not prefer_cjk else [e for e in FONT_FAMILIES if e[2]]
        for name, paths, _, _ in pool:
            for fp, ii in paths:
                if os.path.exists(fp):
                    path, face_idx = fp, ii
                    break
            if path:
                break
    # 3) 最后兜底：常见中文字体目录（覆盖 mac/win/linux）
    if path is None:
        for fp, ii in _FALLBACK_FONTS:
            if os.path.exists(fp):
                path, face_idx = fp, ii
                break
    if path:
        # 粗体优先真实粗体 face：按【实际解析到的字体路径】匹配 family 的 bold face（
        # 避免指定 family 无真实粗体但兜底落到 Hiragino 时仍走描边模拟）
        bold_idx = None
        if bold:
            for e in FONT_FAMILIES:
                if any(fp == path for fp, _ in e[1]) and len(e) > 3 and e[3] is not None:
                    bold_idx = e[3]
                    break
        try:
            kwargs = dict(index=face_idx if italic else 0)
            if bold and bold_idx is not None:
                kwargs['index'] = bold_idx
            return ImageFont.truetype(path, size, **kwargs)
        except Exception:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
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
    # 函数内取最新配置：config 表运行中修改后无需重启即时生效（与 AGNES_API_KEY 模块级绑定不同）
    from common.config import IMAGE_MODEL

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
    model = payload.get("model") or IMAGE_MODEL
    batch_size, n = normalize_batch_params(payload.get("batch_size"), payload.get("n"))
    project_id = payload.get("project_id") or ""
    negative = payload.get("negative") or ""
    if not prompt:
        raise HTTPException(400, "请输入图片描述")

    # 生产级内容保障：文生图描述生成前安全审核（平台发布红线）
    res = check_text(prompt, "prompt")
    if not res["ok"]:
        raise HTTPException(400, "操作失败，请稍后重试")

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
            logger.error(f"文生图失败：{api_error_detail(e)}")
            results.append({"error": f"生成失败：{api_error_detail(e)}", "prompt": prompt})

    _report(100, "生成完成")
    return {"results": results, "total": len(results), "prompt": prompt, "project_id": project_id}


@router.post("/generate/text-to-image")
async def text_to_image(
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    model: str = Form(None, description="模型名，留空使用配置的图片模型（IMAGE_MODEL）"),
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
    # 函数内取最新配置：config 表运行中修改后无需重启即时生效
    from common.config import IMAGE_MODEL

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
    model = payload.get("model") or IMAGE_MODEL
    project_id = payload.get("project_id") or ""
    negative = payload.get("negative") or ""
    image_content = _read_file_field(payload, "image")
    if not image_content:
        raise HTTPException(400, "请上传参考图片")

    # 生产级内容保障：图生图描述生成前安全审核
    res = check_text(prompt, "prompt")
    if not res["ok"]:
        raise HTTPException(400, "操作失败，请稍后重试")

    url = f"{AGNES_API_BASE}/images/generations"
    # 中转站 images/generations 仅支持 JSON body：图片以 base64 Data URI 传入（与短剧插画一致）
    headers = {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "strength": strength,
        "n": 1,
        "image": "data:image/png;base64," + base64.b64encode(image_content).decode(),
    }
    if negative:
        body["negative_prompt"] = negative

    _report(20, "AI 正在基于参考图生成…")
    try:
        resp = await asyncio.to_thread(requests.post, url, headers=headers, json=body, timeout=180)
        resp.raise_for_status()
        data = resp.json()
        if "data" in data and len(data["data"]) > 0:
            item = data["data"][0]
            image_url = item.get("url")
            b64 = item.get("b64_json")
            if image_url:
                img_resp = await asyncio.to_thread(requests.get, image_url, timeout=60)
                result_img = Image.open(io.BytesIO(img_resp.content))
            elif b64:
                result_img = Image.open(io.BytesIO(base64.b64decode(b64)))
            else:
                raise HTTPException(500, "生成失败，请稍后重试")
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
        raise HTTPException(500, "生成失败，请稍后重试")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"图生图失败：{api_error_detail(e)}")
        raise HTTPException(500, "操作失败，请稍后重试") from e


@router.post("/generate/image-to-image")
async def image_to_image(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    size: str = Form("1024x1024"),
    strength: float = Form(0.35),
    model: str = Form(None, description="模型名，留空使用配置的图片模型（IMAGE_MODEL）"),
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
        font = get_font(font_size, text=text)
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
        font = get_font(font_size, text=text)
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
TEMPLATE_CATEGORIES = ["通用", "电商主图", "促销海报", "节日营销", "社媒封面"]


async def _gen_template_preview(template: dict) -> None:
    """渲染模板封面缩略图（纯模板默认内容），失败静默不阻塞主流程。"""
    try:
        imgs = await render_template_image(template)
        img = imgs[0]
        max_w = 480
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, max(1, int(img.height * ratio))), Image.LANCZOS)
        preview_dir = os.path.join(TEMPLATE_DIR, "previews")
        os.makedirs(preview_dir, exist_ok=True)
        img.save(os.path.join(preview_dir, f"{template['id']}.png"), "PNG")
    except Exception as e:
        logger.warning(f"模板封面生成失败: {e}")


@router.get("/templates")
async def list_templates():
    """列出所有模板（附加封面地址、分类与使用热度）。"""
    from template_store import get_usage_stats

    usage_map = get_usage_stats()
    templates = []
    if os.path.exists(TEMPLATE_DIR):
        for fname in os.listdir(TEMPLATE_DIR):
            if not fname.endswith(".json"):
                continue
            filepath = os.path.join(TEMPLATE_DIR, fname)
            with open(filepath, encoding="utf-8") as fh:
                template = json.load(fh)
            tid = template.get("id", "")
            template["category"] = template.get("category") or "通用"
            template["preview"] = f"/api/image-factory/template-preview/{tid}"
            template["render_count"] = usage_map.get(tid, 0)
            templates.append(template)
    def _sort_key(t):
        return (int(t.get("render_count", 0) or 0), t.get("created_at", "") or "")
    templates.sort(key=_sort_key, reverse=True)
    return templates


@router.get("/template-preview/{template_id}")
async def template_preview(template_id: str):
    """模板封面图（首次访问懒生成）"""
    path = os.path.join(TEMPLATE_DIR, "previews", f"{template_id}.png")
    if not os.path.exists(path):
        tpath = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
        if os.path.exists(tpath):
            with open(tpath, encoding="utf-8") as f:
                await _gen_template_preview(json.load(f))
        if not os.path.exists(path):
            raise HTTPException(404, "预览不存在")
    return FileResponse(path, media_type="image/png")


@router.post("/template/create")
async def create_template(req: dict):
    """创建模板（保存后自动生成封面缩略图）。"""
    template_id = generate_id()
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    template = {
        "id": template_id,
        **req,
        "created_at": datetime.now().isoformat(),
        "render_count": 0,
    }
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)
    await _gen_template_preview(template)
    return {"id": template_id, **template}
    template_id = generate_id()
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")

    template = {
        "id": template_id,
        "name": req.get("name", "未命名模板"),
        "width": req.get("width", 1080),
        "height": req.get("height", 1920),
        "background": req.get("background", "#FFFFFF"),
        "category": req.get("category", "通用") or "通用",
        "layers": req.get("layers", []),
        "background_image": req.get("background_image", ""),
        "background_darken": req.get("background_darken", 0),
        "pricing": req.get("pricing") or {"mode": "free", "once": 0, "day": 0, "month": 0},
        "seller": req.get("seller", ""),
        "created_at": datetime.now().isoformat(),
    }

    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    await _gen_template_preview(template)
    return template


async def _load_template_img(source: str) -> Image.Image | None:
    """加载图层/背景图片：本地图片文件直接读盘，http(s) 走网络下载。"""
    if not source:
        return None
    try:
        if source.startswith("/api/image-factory/images/"):
            fname = source.rsplit("/", 1)[-1]
            local = os.path.join(IMAGE_DIR, fname)
            if os.path.exists(local):
                return Image.open(local).convert("RGBA")
            return None
        if source.startswith("http"):
            resp = await asyncio.to_thread(requests.get, source, timeout=30)
            return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception as e:
        logger.warning(f"模板图片加载失败: {e}")
    return None


def _cover_resize(img: Image.Image, w: int, h: int) -> Image.Image:
    """等比裁剪填充（cover）：先按目标比例中心裁剪再缩放，避免拉伸变形。"""
    sw, sh = img.size
    target = w / max(1, h)
    src = sw / max(1, sh)
    if src > target:
        new_w = int(sh * target)
        x0 = (sw - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, sh))
    elif src < target:
        new_h = int(sw / target)
        y0 = (sh - new_h) // 2
        img = img.crop((0, y0, sw, y0 + new_h))
    return img.resize((w, h), Image.LANCZOS)


def _rounded_mask(w: int, h: int, radius: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    return mask


def _draw_text_run(td: ImageDraw.ImageDraw, x: int, y: int, s: str, font, fill: str,  # noqa: PLR0913
                   letter_spacing: float = 0, stroke_width: int = 0, stroke_fill: str = "") -> None:
    """绘制文字（支持字间距；描边模式下逐字绘制保证字间留白不被描边填充）。"""
    if letter_spacing and letter_spacing > 0:
        cx = x
        for ch in s:
            if stroke_width:
                td.text((cx, y), ch, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
            else:
                td.text((cx, y), ch, font=font, fill=fill)
            cx += td.textlength(ch, font=font) + letter_spacing
    elif stroke_width:
        td.text((x, y), s, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
    else:
        td.text((x, y), s, font=font, fill=fill)



# ═══════════════════════════════════════════════════════════════
# 模板渲染辅助函数（已提取，降低主函数复杂度）
# ═══════════════════════════════════════════════════════════════

def _parse_template_config(template: dict, overrides: dict) -> dict:
    """解析模板配置，提取尺寸、背景、槽位等参数。"""
    width = int(overrides.get("width", template.get("width", 1080)))
    height = int(overrides.get("height", template.get("height", 1920)))
    
    raw_images = overrides.get("images") or []
    slot_map = raw_images if isinstance(raw_images, dict) else {}
    batch_urls = [] if isinstance(raw_images, dict) else list(raw_images)
    
    main_slot_key = ""
    for layer in template.get("layers", []):
        if layer.get("type") == "image" and (layer.get("slot") or not layer.get("url")):
            main_slot_key = layer.get("key") or layer.get("slot") or ""
            break
    
    return {
        "width": width,
        "height": height,
        "slot_map": slot_map,
        "batch_urls": batch_urls,
        "main_slot_key": main_slot_key,
    }


def _resolve_layer_img(layer: dict, slot_map: dict, batch_url: str, main_slot_key: str) -> str:
    """解析图层图片来源：按 key 精确填充 > 批量主槽 > 图层自带 url。"""
    key = layer.get("key", "")
    if key and key in slot_map:
        return slot_map[key]
    if batch_url and key == main_slot_key:
        return batch_url
    return layer.get("url", "")

async def render_template_image(template: dict, overrides: dict | None = None,  # noqa: C901, PLR0912
                                progress: Callable | None = None) -> list[Image.Image]:
    """按模板渲染出 PIL 图像列表（不保存，供渲染任务/封面缩略图复用）。

    overrides.images 支持两种形态：
    - dict {key: url}：按图层 key 精确填充图片层（单张渲染）
    - list [url, ...]：批量模式，每张图依次填充主槽位并逐张渲染（如大促商品图批量套版）
    主槽位 = 第一个无自带 url（或显式 slot 标记）的 image 层。
    """
    overrides = overrides or {}
    width = int(overrides.get("width", template.get("width", 1080)))
    height = int(overrides.get("height", template.get("height", 1920)))

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    # ── 槽位图片解析 ──
    raw_images = overrides.get("images") or []
    slot_map = raw_images if isinstance(raw_images, dict) else {}
    batch_urls = [] if isinstance(raw_images, dict) else list(raw_images)
    main_slot_key = ""
    for layer in template.get("layers", []):
        if layer.get("type") == "image" and (layer.get("slot") or not layer.get("url")):
            main_slot_key = layer.get("key") or layer.get("slot") or ""
            break

    def _resolve_layer_img(layer: dict, batch_url: str) -> str:
        """图层图片来源：按 key 精确填充 > 批量主槽 > 图层自带 url。"""
        key = layer.get("key", "")
        if key and key in slot_map:
            return slot_map[key]
        if batch_url and key == main_slot_key:
            return batch_url
        return layer.get("url", "")

    async def _make_bg() -> Image.Image:
        """背景：背景图（cover 铺满 + 模糊 + 暗化）> 渐变简写 > 纯色。"""
        bg_src = overrides.get("background_image", template.get("background_image", ""))
        if bg_src:
            bg = await _load_template_img(bg_src)
            if bg is not None:
                blur = float(overrides.get("background_blur", template.get("background_blur", 0)) or 0)
                darken = float(overrides.get("background_darken", template.get("background_darken", 0)) or 0)
                bg = _cover_resize(bg, width, height)
                if blur > 0:
                    bg = bg.filter(ImageFilter.GaussianBlur(blur))
                if darken > 0:
                    shade = Image.new("RGBA", (width, height), (0, 0, 0, int(255 * min(1.0, darken))))
                    bg = Image.alpha_composite(bg, shade)
                return bg.convert("RGB")
        bg_color = overrides.get("background", template.get("background", "#FFFFFF"))
        if isinstance(bg_color, str) and "→" in bg_color:
            from image_edit_engine import make_gradient

            top_hex, bottom_hex = (bg_color.split("→") + ["#FFFFFF"])[:2]
            return make_gradient(width, height, top_hex.strip(), bottom_hex.strip())
        return Image.new("RGB", (width, height), bg_color)

    async def _render_once(batch_url: str) -> Image.Image:  # noqa: C901
        """按模板渲染一张（batch_url 为批量模式下该轮主槽图片，单张模式传空）。"""
        canvas = await _make_bg()
        draw = ImageDraw.Draw(canvas)

        for layer in template.get("layers", []):
            layer_type = layer.get("type")

            if layer_type == "rect":
                # 圆角矩形底（卡片/横幅/按钮底）：支持渐变填充/描边边框/旋转
                x = int(layer.get("x", 0))
                y = int(layer.get("y", 0))
                w = int(layer.get("width", 200))
                h = int(layer.get("height", 60))
                radius = int(layer.get("radius", 16))
                fill = layer.get("fill", "#FFFFFF")
                opacity = float(layer.get("opacity", 1.0))
                rotation = float(layer.get("rotation", 0) or 0)
                border_w = int(layer.get("border_width", 0) or 0)
                border_color = layer.get("border_color", fill)
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                if isinstance(fill, str) and "→" in fill:
                    from image_edit_engine import make_gradient

                    top_hex, bottom_hex = (fill.split("→") + ["#FFFFFF"])[:2]
                    grad = make_gradient(w, h, top_hex.strip(), bottom_hex.strip()).convert("RGBA")
                    overlay.paste(grad, (0, 0), _rounded_mask(w, h, radius))
                else:
                    od.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill)
                if border_w > 0:
                    od.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline=border_color, width=border_w)
                if opacity < 1.0:
                    overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
                if rotation:
                    overlay = overlay.rotate(-rotation, expand=True, resample=Image.BICUBIC)
                    nw, nh = overlay.size
                    canvas.paste(overlay, (int(x + w / 2 - nw / 2), int(y + h / 2 - nh / 2)), overlay)
                else:
                    canvas.paste(overlay, (x, y), overlay)
                draw = ImageDraw.Draw(canvas)

            if layer_type == "circle":
                # 圆/圆环（光斑、装饰环、徽章底）：x/y 为圆心，支持渐变填充/边框/旋转
                cx = int(layer.get("x", 0))
                cy = int(layer.get("y", 0))
                radius = max(1, int(layer.get("radius", 50)))
                fill = layer.get("fill", "#FFFFFF")
                opacity = float(layer.get("opacity", 1.0))
                rotation = float(layer.get("rotation", 0) or 0)
                border_w = int(layer.get("border_width", 0) or 0)
                border_color = layer.get("border_color", fill)
                pad = max(border_w, 2)
                d = radius * 2 + pad * 2
                overlay = Image.new("RGBA", (d, d), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                box = [pad, pad, d - 1 - pad, d - 1 - pad]
                if fill and isinstance(fill, str) and "→" in fill:
                    from image_edit_engine import make_gradient

                    top_hex, bottom_hex = (fill.split("→") + ["#FFFFFF"])[:2]
                    grad = make_gradient(d, d, top_hex.strip(), bottom_hex.strip()).convert("RGBA")
                    mask = Image.new("L", (d, d), 0)
                    ImageDraw.Draw(mask).ellipse(box, fill=255)
                    overlay.paste(grad, (0, 0), mask)
                elif fill:
                    od.ellipse(box, fill=fill)
                if border_w > 0:
                    od.ellipse([pad, pad, d - 1 - pad, d - 1 - pad], outline=border_color, width=border_w)
                if opacity < 1.0:
                    overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
                if rotation:
                    overlay = overlay.rotate(-rotation, expand=True, resample=Image.BICUBIC)
                canvas.paste(overlay, (cx - overlay.width // 2, cy - overlay.height // 2), overlay)
                draw = ImageDraw.Draw(canvas)

            if layer_type == "line":
                # 直线/分隔线：x1/y1/x2/y2 或 x/y/length/angle（角度制，0=水平向右）
                x1 = int(layer.get("x1", layer.get("x", 0)))
                y1 = int(layer.get("y1", layer.get("y", 0)))
                x2 = int(layer.get("x2", 0))
                y2 = int(layer.get("y2", 0))
                if layer.get("length"):
                    import math

                    angle = math.radians(float(layer.get("angle", 0) or 0))
                    length = int(layer.get("length", 100))
                    x2 = x1 + int(length * math.cos(angle))
                    y2 = y1 + int(length * math.sin(angle))
                color = layer.get("color", "#DDDDDD")
                lw = max(1, int(layer.get("width", 2) or 2))
                opacity = float(layer.get("opacity", 1.0))
                if opacity < 1.0:
                    overlay = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
                    ImageDraw.Draw(overlay).line([x1, y1, x2, y2], fill=color, width=lw)
                    overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
                    canvas.paste(overlay, (0, 0), overlay)
                else:
                    draw.line([x1, y1, x2, y2], fill=color, width=lw)
                draw = ImageDraw.Draw(canvas)

            if layer_type == "text":
                # 文字排版：字体族/粗体/斜体/字间距/行高/描边/阴影色/旋转
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
                shadow_color = layer.get("shadow_color", "#00000080")
                family = layer.get("family", "")
                bold = bool(layer.get("bold"))
                italic = bool(layer.get("italic"))
                letter_spacing = float(layer.get("letter_spacing", 0) or 0)
                line_height = float(layer.get("line_height", 1.35) or 1.35)
                stroke_w = int(layer.get("stroke_width", 0) or 0)
                stroke_color = layer.get("stroke_color", font_color)
                rotation = float(layer.get("rotation", 0) or 0)

                font = get_font(font_size, family, bold, italic, text)

                # 自动换行（max_width>0 时按像素宽度折行；显式 \n 优先断行）
                if max_width > 0:
                    lines, cur = [], ""
                    for ch in text:
                        if ch == "\n":
                            lines.append(cur)
                            cur = ""
                        elif draw.textlength(cur + ch, font=font) > max_width:
                            lines.append(cur)
                            cur = ch
                        else:
                            cur += ch
                    if cur:
                        lines.append(cur)
                    text_lines = lines or [""]
                else:
                    text_lines = text.split("\n") or [""]

                line_h = int(font_size * line_height)
                block_w = max_width or max(int(draw.textlength(ln, font=font)) for ln in text_lines)
                block_h = line_h * len(text_lines)
                # 粗体模拟：同色描边加粗（PIL 无可靠粗体变体）
                sim_bold = max(1, round(font_size * 0.055)) if bold else 0
                sx, sy = 2, 2
                shadow_blur = 0
                if shadow:
                    try:
                        parts = [int(v) for v in shadow.split(",")]
                        sx, sy = parts[0], parts[1]
                        shadow_blur = parts[2] if len(parts) > 2 else 0
                    except Exception:
                        pass
                pad = 8 + (stroke_w + sim_bold) * 2 + shadow_blur
                txt_img = Image.new("RGBA", (block_w + pad * 2, block_h + pad * 2), (0, 0, 0, 0))
                td = ImageDraw.Draw(txt_img)
                # v24：渐变文字（color 支持 #A→#B，垂直渐变——商业海报标题标配）
                grad_fill = ""
                if isinstance(font_color, str) and "→" in font_color:
                    grad_fill = font_color
                    font_color = "#FFFFFF"  # 文字本体先画白色，渐变最后按 alpha 覆盖
                stroke_total = stroke_w + sim_bold

                def _line_pos(i, ln):
                    lx = pad
                    if align == "center":
                        lx = pad + (block_w - int(td.textlength(ln, font=font))) // 2
                    elif align == "right":
                        lx = pad + block_w - int(td.textlength(ln, font=font))
                    return lx, pad + i * line_h

                # 阴影层：先单独绘制并模糊（软阴影），再合成到底层，避免模糊糊住正字
                if shadow:
                    sh_img = Image.new("RGBA", txt_img.size, (0, 0, 0, 0))
                    sd = ImageDraw.Draw(sh_img)
                    for i, ln in enumerate(text_lines):
                        lx, ly = _line_pos(i, ln)
                        _draw_text_run(
                            sd, lx + sx, ly + sy, ln, font, shadow_color, letter_spacing,
                            stroke_total, shadow_color,
                        )
                    if shadow_blur > 0:
                        sh_img = sh_img.filter(ImageFilter.GaussianBlur(shadow_blur))
                    txt_img = Image.alpha_composite(txt_img, sh_img)
                    td = ImageDraw.Draw(txt_img)
                # 正字层
                for i, ln in enumerate(text_lines):
                    lx, ly = _line_pos(i, ln)
                    _draw_text_run(
                        td, lx, ly, ln, font, font_color, letter_spacing, stroke_total,
                        stroke_color if stroke_w else font_color,
                    )
                # 渐变覆盖：按文字 alpha 填充垂直渐变（描边/阴影保留原色，只染字身）
                if grad_fill:
                    from image_edit_engine import make_gradient

                    top_hex, bottom_hex = (grad_fill.split("→") + ["#FFFFFF"])[:2]
                    grad = make_gradient(txt_img.width, txt_img.height, top_hex.strip(), bottom_hex.strip()).convert("RGBA")
                    txt_img = Image.composite(grad, txt_img, txt_img.split()[3])
                if rotation:
                    txt_img = txt_img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
                    nw, nh = txt_img.size
                    canvas.paste(txt_img, (int(x + block_w / 2 - nw / 2), int(y + block_h / 2 - nh / 2)), txt_img)
                else:
                    canvas.paste(txt_img, (x - pad, y - pad), txt_img)

            elif layer_type == "image":
                # 图片层：cover 裁剪/圆角/边框/透明度/旋转
                source = _resolve_layer_img(layer, batch_url)
                layer_img = await _load_template_img(source)
                if layer_img is None:
                    continue
                x = int(layer.get("x", 0))
                y = int(layer.get("y", 0))
                w = int(layer.get("width", 200))
                h = int(layer.get("height", 200))
                fit = layer.get("fit", "cover")
                radius = int(layer.get("radius", 0) or 0)
                opacity = float(layer.get("opacity", 1.0))
                rotation = float(layer.get("rotation", 0) or 0)
                border_w = int(layer.get("border_width", 0) or 0)
                border_color = layer.get("border_color", "#FFFFFF")
                if fit == "cover":
                    layer_img = _cover_resize(layer_img, w, h)
                else:
                    layer_img = layer_img.resize((w, h), Image.LANCZOS)
                if radius > 0:
                    layer_img.putalpha(_rounded_mask(w, h, radius))
                if opacity < 1.0:
                    layer_img.putalpha(layer_img.getchannel("A").point(lambda a, op=opacity: int(a * op)))
                if border_w > 0:
                    bd = ImageDraw.Draw(layer_img, "RGBA")
                    bd.rounded_rectangle(
                        [border_w // 2, border_w // 2, w - 1 - border_w // 2, h - 1 - border_w // 2],
                        radius=max(0, radius - border_w // 2), outline=border_color, width=border_w,
                    )
                if rotation:
                    layer_img = layer_img.rotate(-rotation, expand=True, resample=Image.BICUBIC)
                    nw, nh = layer_img.size
                    canvas.paste(layer_img, (int(x + w / 2 - nw / 2), int(y + h / 2 - nh / 2)), layer_img)
                else:
                    canvas.paste(layer_img, (x, y), layer_img)

        return canvas

    _report(15, "正在渲染模板…")
    if batch_urls:
        total = len(batch_urls)
        results = []
        for i, u in enumerate(batch_urls):
            _report(15 + int(i * 75 / total), f"正在处理第 {i + 1}/{total} 张…")
            results.append(await _render_once(u))
        _report(100, "模板渲染完成")
        return results
    result = [await _render_once("")]
    _report(100, "模板渲染完成")
    return result


async def _image_template_worker(payload: dict, progress: Callable | None = None) -> dict:
    """渲染模板生成图片（同步/异步任务共用执行体），返回结果与任务进度兼容 。"""
    template_id = payload.get("template_id")
    # 兼容两种参数形态：images/背景等既可放 overrides 内，也可放请求顶层
    overrides = dict(payload.get("overrides") or {})
    for k in ("images", "background_image", "background_darken", "background_blur", "width", "height"):
        if k in payload and k not in overrides:
            overrides[k] = payload[k]
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if not os.path.exists(template_path):
        raise HTTPException(404, "模板不存在")

    with open(template_path, encoding="utf-8") as f:
        template = json.load(f)

    # 商业化鉴权：收费模板需已购买/订阅（按次永久、按天/按月未过期）
    from template_store import check_render_access, record_usage

    user = payload.get("_username", "")
    check_render_access(user, template)

    imgs = await render_template_image(template, overrides, progress)
    results = []
    for img in imgs:
        filename = save_image(img)
        results.append({"id": filename, "url": f"/api/image-factory/images/{filename}"})
        record_usage(template_id)  # 热度 +1

    if len(results) > 1:
        out = {"images": results}
        out["url"] = results[0]["url"]
        out["id"] = results[0]["id"]
        return out
    return results[0]


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
        req = dict(req)
        req["_username"] = user
        return await _image_template_worker(req)
    req = dict(req)
    req["_username"] = user
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


@router.put("/templates/{template_id}")
async def update_template(template_id: str, req: dict):
    """更新模板（按 id 覆盖名称/尺寸/背景/图层，保留创建时间）"""
    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if not os.path.exists(template_path):
        raise HTTPException(404, "模板不存在")

    with open(template_path, encoding="utf-8") as f:
        template = json.load(f)

    template["name"] = req.get("name", template.get("name", "未命名模板"))
    template["width"] = req.get("width", template.get("width", 1080))
    template["height"] = req.get("height", template.get("height", 1920))
    template["background"] = req.get("background", template.get("background", "#FFFFFF"))
    template["category"] = req.get("category", template.get("category", "通用")) or "通用"
    template["background_image"] = req.get("background_image", template.get("background_image", ""))
    template["background_darken"] = req.get("background_darken", template.get("background_darken", 0))
    template["layers"] = req.get("layers", template.get("layers", []))
    template["updated_at"] = datetime.now().isoformat()
    # 商业化字段：定价（免费/按次/按天/按月）与创作者（默认平台）
    if "pricing" in req:
        template["pricing"] = req.get("pricing") or {"mode": "free", "once": 0, "day": 0, "month": 0}
    if "seller" in req:
        template["seller"] = req.get("seller", "")
    # 兼容内置模板：缺 created_at 时补当前时间，保证列表按时间排序
    if not template.get("created_at"):
        template["created_at"] = datetime.now().isoformat()

    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=2)

    await _gen_template_preview(template)
    return template


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
        raise HTTPException(500, "操作失败，请稍后重试") from e


# ── 虚拟试衣 API ──────────────────────────────────────────────
async def _image_tryon_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """虚拟试衣（同步/异步任务共用执行体，异步时回报进度）。"""
    # 函数内取最新配置：config 表运行中修改后无需重启即时生效
    from common.config import IMAGE_MODEL

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
                "model": IMAGE_MODEL,
                "messages": [{"role": "user", "content": messages_content}],
                "size": "1024x1024",
                "n": 1,
                "extra_body": {"response_format": "url"},
            },
            timeout=120,
        )

        if response.status_code != 200:
            raise HTTPException(500, "生成失败，请稍后重试")

        data = response.json()
        if not data.get("data"):
            raise HTTPException(500, "生成失败，请稍后重试")

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
            raise HTTPException(500, "生成失败，请稍后重试")

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
        raise HTTPException(500, "操作失败，请稍后重试") from e


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
    # 函数内取最新配置：config 表运行中修改后无需重启即时生效
    from common.config import IMAGE_MODEL

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
                        "model": IMAGE_MODEL,
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
        raise HTTPException(500, "操作失败，请稍后重试") from e


# ── 预置电商模板 ──────────────────────────────────────────────
# 已下架模板（质量不达标/废弃）：启动时清理磁盘残留并跳过内置恢复
_RETIRED_TEMPLATES = {
    "tmplt_baidu_ad", "tmplt_insta_post", "tmplt_weibo_ad", "tmplt_douyin",
    "tmplt_jd_main", "tmplt_taobao_main", "tmplt_pinduoduo", "tmplt_facebook_ad",
    "img_1786461663469",
}


def init_templates():
    """初始化预置模板（跳过已下架模板，并清理其在磁盘上的残留文件）"""
    for retired in _RETIRED_TEMPLATES:
        p = os.path.join(TEMPLATE_DIR, f"{retired}.json")
        if os.path.exists(p):
            os.remove(p)
            logger.info(f"清理已下架模板：{retired}")
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
        {
            "id": "tmplt_promotion_main",
            "name": "大促主视觉海报",
            "category": "促销海报",
            "width": 1080,
            "height": 1440,
            "background": "#FF2D2D→#8E0E00",
            "layers": [
                {
                    "type": "text",
                    "key": "title",
                    "x": 60,
                    "y": 110,
                    "font_size": 92,
                    "bold": True,
                    "color": "#FFD700",
                    "align": "center",
                    "max_width": 960,
                    "stroke_width": 4,
                    "stroke_color": "#C0392B",
                    "shadow": "0,8",
                    "shadow_color": "#66000000",
                    "text": "大促狂欢节",
                },
                {
                    "type": "rect",
                    "x": 300,
                    "y": 260,
                    "width": 480,
                    "height": 80,
                    "radius": 40,
                    "fill": "#FFD700",
                },
                {
                    "type": "text",
                    "key": "tag",
                    "x": 300,
                    "y": 278,
                    "font_size": 40,
                    "bold": True,
                    "color": "#B00020",
                    "align": "center",
                    "max_width": 480,
                    "text": "全场 5 折起",
                },
                {
                    "type": "image",
                    "key": "product",
                    "x": 140,
                    "y": 400,
                    "width": 800,
                    "height": 800,
                    "radius": 36,
                    "fit": "cover",
                },
                {
                    "type": "text",
                    "key": "subtitle",
                    "x": 60,
                    "y": 1240,
                    "font_size": 44,
                    "color": "#FFFFFF",
                    "align": "center",
                    "max_width": 960,
                    "text": "限时特惠 · 手慢无",
                },
                {
                    "type": "text",
                    "key": "price",
                    "x": 60,
                    "y": 1310,
                    "font_size": 64,
                    "bold": True,
                    "color": "#FFD700",
                    "align": "center",
                    "max_width": 960,
                    "shadow": "0,4",
                    "shadow_color": "#80000000",
                    "text": "¥99 起",
                },
            ],
        },
        {
            "id": "tmplt_festival_christmas",
            "name": "圣诞狂欢促销",
            "category": "节日营销",
            "width": 1080,
            "height": 1920,
            "background": "#0B3D2E→#041712",
            "layers": [
                {
                    "type": "text",
                    "key": "en_title",
                    "x": 60,
                    "y": 160,
                    "font_size": 56,
                    "family": "helvetica",
                    "bold": True,
                    "color": "#FFFFFF",
                    "align": "center",
                    "max_width": 960,
                    "letter_spacing": 6,
                    "text": "MERRY CHRISTMAS",
                },
                {
                    "type": "text",
                    "key": "title",
                    "x": 60,
                    "y": 260,
                    "font_size": 72,
                    "bold": True,
                    "color": "#FFD700",
                    "align": "center",
                    "max_width": 960,
                    "stroke_width": 4,
                    "stroke_color": "#0B3D2E",
                    "text": "圣诞狂欢季",
                },
                {
                    "type": "rect",
                    "x": 60,
                    "y": 400,
                    "width": 960,
                    "height": 1200,
                    "radius": 36,
                    "fill": "#FFFFFF",
                    "opacity": 0.08,
                    "border_width": 2,
                    "border_color": "#FFFFFF",
                },
                {
                    "type": "image",
                    "key": "product",
                    "x": 150,
                    "y": 470,
                    "width": 780,
                    "height": 780,
                    "radius": 40,
                    "fit": "cover",
                },
                {
                    "type": "text",
                    "key": "discount",
                    "x": 60,
                    "y": 1300,
                    "font_size": 80,
                    "bold": True,
                    "color": "#FF4D4D",
                    "align": "center",
                    "max_width": 960,
                    "shadow": "0,6",
                    "shadow_color": "#80000000",
                    "text": "全场 8 折",
                },
                {
                    "type": "text",
                    "key": "date",
                    "x": 60,
                    "y": 1420,
                    "font_size": 36,
                    "color": "#FFFFFF",
                    "align": "center",
                    "max_width": 960,
                    "letter_spacing": 2,
                    "text": "12.12 - 12.25 限定狂欢",
                },
            ],
        },
        {
            "id": "tmplt_clearance",
            "name": "清仓特卖主图",
            "category": "电商主图",
            "width": 800,
            "height": 800,
            "background": "#FFF7E6",
            "layers": [
                {
                    "type": "rect",
                    "x": -40,
                    "y": 50,
                    "width": 340,
                    "height": 84,
                    "radius": 42,
                    "fill": "#FF6B00→#FFA500",
                    "rotation": -8,
                },
                {
                    "type": "text",
                    "key": "tag",
                    "x": 32,
                    "y": 72,
                    "font_size": 44,
                    "bold": True,
                    "color": "#FFFFFF",
                    "rotation": -8,
                    "text": "清仓特卖",
                },
                {
                    "type": "image",
                    "key": "product",
                    "x": 100,
                    "y": 200,
                    "width": 600,
                    "height": 480,
                    "radius": 24,
                    "fit": "cover",
                    "border_width": 6,
                    "border_color": "#FF6B00",
                },
                {
                    "type": "text",
                    "key": "discount",
                    "x": 0,
                    "y": 700,
                    "font_size": 52,
                    "bold": True,
                    "color": "#FF3B30",
                    "align": "center",
                    "max_width": 800,
                    "text": "限时 5 折",
                },
                {
                    "type": "text",
                    "key": "subtitle",
                    "x": 0,
                    "y": 758,
                    "font_size": 30,
                    "color": "#8B5E34",
                    "align": "center",
                    "max_width": 800,
                    "text": "今日特价 · 售完即止",
                },
            ],
        },
        {
            "id": "tmplt_sale_banner",
            "name": "年中大促横幅",
            "category": "社媒封面",
            "width": 1200,
            "height": 628,
            "background": "#1A1A2E",
            "layers": [
                {
                    "type": "rect",
                    "x": 40,
                    "y": 80,
                    "width": 520,
                    "height": 468,
                    "radius": 28,
                    "fill": "#16213E→#0F3460",
                    "border_width": 2,
                    "border_color": "#E94560",
                },
                {
                    "type": "image",
                    "key": "product",
                    "x": 85,
                    "y": 130,
                    "width": 430,
                    "height": 370,
                    "radius": 20,
                    "fit": "cover",
                },
                {
                    "type": "text",
                    "key": "title",
                    "x": 620,
                    "y": 110,
                    "font_size": 72,
                    "bold": True,
                    "color": "#F5C518",
                    "text": "年中大促",
                },
                {
                    "type": "text",
                    "key": "subtitle",
                    "x": 620,
                    "y": 220,
                    "font_size": 34,
                    "color": "#FFFFFF",
                    "letter_spacing": 1,
                    "text": "限时特惠 · 全场折扣",
                },
                {
                    "type": "text",
                    "key": "price",
                    "x": 620,
                    "y": 300,
                    "font_size": 56,
                    "bold": True,
                    "color": "#F5C518",
                    "shadow": "0,4",
                    "shadow_color": "#80000000",
                    "text": "¥59 起",
                },
                {
                    "type": "rect",
                    "x": 620,
                    "y": 420,
                    "width": 280,
                    "height": 84,
                    "radius": 42,
                    "fill": "#E94560",
                },
                {
                    "type": "text",
                    "key": "cta",
                    "x": 620,
                    "y": 442,
                    "font_size": 34,
                    "bold": True,
                    "color": "#FFFFFF",
                    "align": "center",
                    "max_width": 280,
                    "text": "立即抢购",
                },
            ],
        },
    ]

    for tmpl in templates:
        if tmpl["id"] in _RETIRED_TEMPLATES:
            continue
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
        raise HTTPException(400, "操作失败，请稍后重试")
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


def _render_rect_layer(layer: dict, canvas, draw, width: int, height: int) -> None:
    """渲染圆角矩形图层（卡片/横幅/按钮底）。"""
    from PIL import ImageDraw
    
    x = int(layer.get("x", 0))
    y = int(layer.get("y", 0))
    w = int(layer.get("width", 200))
    h = int(layer.get("height", 60))
    radius = int(layer.get("radius", 16))
    fill = layer.get("fill", "#FFFFFF")
    opacity = float(layer.get("opacity", 1.0))
    rotation = float(layer.get("rotation", 0) or 0)
    border_w = int(layer.get("border_width", 0) or 0)
    border_color = layer.get("border_color", fill)
    
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    
    # 渐变填充
    if isinstance(fill, str) and "→" in fill:
        from image_edit_engine import make_gradient
        top_hex, bottom_hex = (fill.split("→") + ["#FFFFFF"])[:2]
        grad = make_gradient(w, h, top_hex.strip(), bottom_hex.strip()).convert("RGBA")
        overlay.paste(grad, (0, 0), _rounded_mask(w, h, radius))
    else:
        od.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill)
    
    # 边框
    if border_w > 0:
        od.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, outline=border_color, width=border_w)
    
    # 透明度
    if opacity < 1.0:
        overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
    
    # 旋转
    if rotation:
        overlay = overlay.rotate(-rotation, expand=True, resample=Image.BICUBIC)
        nw, nh = overlay.size
        canvas.paste(overlay, (int(x + w / 2 - nw / 2), int(y + h / 2 - nh / 2)), overlay)
    else:
        canvas.paste(overlay, (x, y), overlay)
    
    return ImageDraw.Draw(canvas)


def _render_circle_layer(layer: dict, canvas) -> None:
    """渲染圆形图层（光斑/装饰环/徽章底）。"""
    from PIL import ImageDraw
    
    cx = int(layer.get("x", 0))
    cy = int(layer.get("y", 0))
    radius = max(1, int(layer.get("radius", 50)))
    fill = layer.get("fill", "#FFFFFF")
    opacity = float(layer.get("opacity", 1.0))
    rotation = float(layer.get("rotation", 0) or 0)
    border_w = int(layer.get("border_width", 0) or 0)
    border_color = layer.get("border_color", fill)
    pad = max(border_w, 2)
    d = radius * 2 + pad * 2
    
    overlay = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    box = [pad, pad, d - 1 - pad, d - 1 - pad]
    
    # 渐变填充
    if fill and isinstance(fill, str) and "→" in fill:
        from image_edit_engine import make_gradient
        top_hex, bottom_hex = (fill.split("→") + ["#FFFFFF"])[:2]
        grad = make_gradient(d, d, top_hex.strip(), bottom_hex.strip()).convert("RGBA")
        mask = Image.new("L", (d, d), 0)
        ImageDraw.Draw(mask).ellipse(box, fill=255)
        overlay.paste(grad, (0, 0), mask)
    elif fill:
        od.ellipse(box, fill=fill)
    
    # 边框
    if border_w > 0:
        od.ellipse([pad, pad, d - 1 - pad, d - 1 - pad], outline=border_color, width=border_w)
    
    # 透明度
    if opacity < 1.0:
        overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
    
    # 旋转
    if rotation:
        overlay = overlay.rotate(-rotation, expand=True, resample=Image.BICUBIC)
    
    canvas.paste(overlay, (cx - overlay.width // 2, cy - overlay.height // 2), overlay)


def _render_line_layer(layer: dict, canvas) -> None:
    """渲染直线/分隔线。"""
    from PIL import ImageDraw
    import math
    
    x1 = int(layer.get("x1", layer.get("x", 0)))
    y1 = int(layer.get("y1", layer.get("y", 0)))
    x2 = int(layer.get("x2", 0))
    y2 = int(layer.get("y2", 0))
    
    # 角度计算
    if layer.get("length"):
        angle = math.radians(float(layer.get("angle", 0) or 0))
        length = int(layer.get("length", 100))
        x2 = x1 + int(length * math.cos(angle))
        y2 = y1 + int(length * math.sin(angle))
    
    color = layer.get("color", "#DDDDDD")
    lw = max(1, int(layer.get("width", 2) or 2))
    opacity = float(layer.get("opacity", 1.0))
    
    draw = ImageDraw.Draw(canvas)
    if opacity < 1.0:
        overlay = Image.new("RGBA", (canvas.width, canvas.height), (0, 0, 0, 0))
        ImageDraw.Draw(overlay).line([x1, y1, x2, y2], fill=color, width=lw)
        overlay.putalpha(overlay.getchannel("A").point(lambda a, op=opacity: int(a * op)))
        canvas.paste(overlay, (0, 0), overlay)
    else:
        draw.line([x1, y1, x2, y2], fill=color, width=lw)
