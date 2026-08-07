#!/usr/bin/env python3
"""表情包工坊 — 文字一键生成表情包。

- 经典模板模式（PIL 直接绘制，秒出不依赖 AI）：黄底/白底/红底/黑底/渐变 5 种风格
- AI 生成模式：文生图（Agnes）生成搞笑场景 + 自动叠加 meme 大字
- 顶部/底部双行文字，自动换行、自动缩放、白字黑描边经典风格
- 产物保存到 meme_factory/ 目录并登记 artifacts 表（type=image）
"""

import asyncio
import io
import json
import logging
import os
import time
import zipfile
from collections.abc import Callable
from datetime import datetime

import requests
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageChops, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from common.artifacts import save_artifact
from common.auth import require_auth
from common.config import load_config
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meme", tags=["表情包工坊"])

load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY  # noqa: E402

MEME_DIR = os.path.join(os.path.dirname(__file__), "meme_factory")
os.makedirs(MEME_DIR, exist_ok=True)

STYLES = [
    {"id": "yellow", "name": "经典黄底", "desc": "Doge 经典黄，大字冲击力强", "bg": "#FFD84D"},
    {"id": "white", "name": "熊猫白底", "desc": "白底黑字，极简冷幽默", "bg": "#FFFFFF"},
    {"id": "red", "name": "公告红底", "desc": "红底白字，官方通告风", "bg": "#E53935"},
    {"id": "black", "name": "暗夜黑底", "desc": "黑底白字，高冷反差", "bg": "#111111"},
    {"id": "gradient", "name": "蓝紫渐变", "desc": "渐变底色，潮流吸睛", "bg": "gradient"},
    {"id": "neon", "name": "霓虹灯管", "desc": "深紫黑底 + 霓虹青光描边", "bg": "neon"},
    {"id": "paper", "name": "报纸复古", "desc": "米白报纸底色，老照片质感", "bg": "paper"},
    {"id": "sticker", "name": "贴纸白边", "desc": "白描边黑字，微信贴纸风", "bg": "sticker"},
    {"id": "upload", "name": "上传背景", "desc": "自己的图片做底", "bg": "upload"},
    {"id": "ai", "name": "AI 生成", "desc": "文生图场景 + 自动叠字", "bg": "ai"},
]

# AI 模式画面风格（注入文生图 prompt，控制画面质感）
AI_STYLES = {
    "flat": "扁平插画风格，干净简洁的现代网络表情包场景，高饱和配色",
    "3d": "3D 渲染风格，软萌可爱的立体卡通场景，柔和光影，鲜艳配色",
    "pixel": "像素艺术风格，复古 8-bit 游戏画面质感，色彩鲜明",
    "ink": "水墨国风，飘逸的笔触与墨色晕染质感，留白得当",
    "neon": "霓虹赛博朋克风格，深色背景，霓虹灯管光效，未来感",
}

CANVAS = 1080  # 正方形画布（微信表情标准 1080×1080）
MARGIN = 80  # 文字边距
TOP_H = 240  # 顶部文字区高度
BOTTOM_H = 240  # 底部文字区高度

# 导出尺寸规格（商用场景全覆盖）
SIZE_SPECS = [
    {"size": 240, "name": "微信表情单图", "desc": "240×240 微信表情包标准"},
    {"size": 750, "name": "聊天大图", "desc": "750×750 聊天大图/社媒配图"},
    {"size": 1080, "name": "原图", "desc": "1080×1080 默认产物"},
    {"size": 2160, "name": "高清印刷", "desc": "2160×2160 印刷/大屏高清"},
]

_BREAK_CHARS = "，。！？、；：,.!?;: "  # 智能换行优先断点（标点/空格）


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 2) -> list[str]:  # noqa: C901
    """智能换行：优先在标点/空格后断行，避免词语被硬切；超宽段兜底逐字符切。"""
    if draw.textlength(text, font=font) <= max_w:
        return [text]
    # 1) 按标点切成小段（标点保留在段尾，语气不断裂）
    segs, buf = [], ""
    for ch in text:
        buf += ch
        if ch in _BREAK_CHARS:
            segs.append(buf)
            buf = ""
    if buf:
        segs.append(buf)
    # 2) 贪心组行
    lines, cur = [], ""
    for s in segs:
        if cur and draw.textlength(cur + s, font=font) > max_w:
            lines.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        lines.append(cur)
    # 3) 仍超宽的段兜底逐字符切
    final = []
    for line in lines:
        while len(final) < max_lines and draw.textlength(line, font=font) > max_w:
            cut = 1
            for i in range(2, len(line) + 1):
                if draw.textlength(line[:i], font=font) > max_w:
                    cut = i - 1
                    break
            final.append(line[:cut])
            line = line[cut:]
        if line:
            final.append(line)
    return final[:max_lines]


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取中文字体（macOS PingFang → Linux 文泉驿/Noto CJK），失败回退默认。"""
    for fp in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux：文泉驿（简体）
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux：Noto CJK
    ]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_meme_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box_top: int,
    box_bottom: int,
    fill: str = "#FFFFFF",
    stroke: str = "#000000",
    font_size: int = 96,
) -> None:
    """在指定区域居中绘制 meme 文字：智能换行、自动缩放、白字黑描边 + 投影。"""
    if not text:
        return
    text = text.strip()
    if not text:
        return
    font = get_font(font_size)
    max_w = CANVAS - MARGIN * 2
    max_h = box_bottom - box_top

    # 自动缩放字号直到 2 行以内能放下（智能换行按真实行宽计算）
    while font_size > 30:
        font = get_font(font_size)
        lines = _wrap_text(draw, text, font, max_w)
        line_w = max(draw.textlength(line, font=font) for line in lines)
        total_h = len(lines) * int(font_size * 1.2)
        if line_w <= max_w and total_h <= max_h:
            break
        font_size -= 6

    lines = _wrap_text(draw, text, font, max_w)
    line_h = int(font_size * 1.2)
    total_h = len(lines) * line_h
    y = box_top + (max_h - total_h) // 2
    sw = max(3, font_size // 24)
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (CANVAS - w) // 2
        # 投影层：右下偏移黑色实心描边，增强立体感与浅色背景可读性（商用 meme 标准）
        draw.text((x + 4, y + 4), line, font=font, fill="#000000", stroke_width=sw, stroke_fill="#000000")
        draw.text((x, y), line, font=font, fill=fill, stroke_width=sw, stroke_fill=stroke)
        y += line_h


def _gradient_bg(draw_color1: tuple, draw_color2: tuple) -> Image.Image:
    """生成垂直渐变底图。"""
    img = Image.new("RGB", (CANVAS, CANVAS))
    for y in range(CANVAS):
        t = y / CANVAS
        color = tuple(int(draw_color1[i] + (draw_color2[i] - draw_color1[i]) * t) for i in range(3))
        for x in range(0, CANVAS, 4):
            img.paste(color, (x, y, x + 4, y + 1))
    return img


def _style_bg(style: str) -> Image.Image:
    """按风格生成底图（黄/白底附加高斯噪点颗粒，消除纯色廉价感）。"""
    if style == "gradient":
        return _gradient_bg((99, 102, 241), (168, 85, 247))
    if style == "neon":
        return _gradient_bg((17, 8, 38), (45, 12, 66))  # 深紫黑渐变（霓虹灯管氛围）
    if style == "paper":
        return Image.new("RGB", (CANVAS, CANVAS), (247, 243, 232))  # 米白报纸底
    if style == "sticker":
        return Image.new("RGB", (CANVAS, CANVAS), (255, 255, 255))  # 贴纸白底
    if style == "black":
        return Image.new("RGB", (CANVAS, CANVAS), (17, 17, 17))
    if style == "red":
        return Image.new("RGB", (CANVAS, CANVAS), (229, 57, 53))
    if style == "white":
        img = Image.new("RGB", (CANVAS, CANVAS), (255, 255, 255))
    else:
        img = Image.new("RGB", (CANVAS, CANVAS), (255, 216, 77))  # yellow 默认
    if style in ("yellow", "white"):
        # 高斯噪点叠加：±16 亮度颗粒，纸张质感，避免大面积纯色（商用质感）
        noise = Image.effect_noise((CANVAS, CANVAS), 10).convert("RGB")
        img = ImageChops.add(img, noise, scale=8, offset=-16)
    return img


def _text_color(style: str) -> tuple:
    """按风格取文字/描边色。"""
    if style in ("yellow", "white"):
        return "#FFFFFF", "#000000"  # 白字黑边（经典）
    if style == "black":
        return "#FFFFFF", "#000000"
    if style == "neon":
        return "#FFFFFF", "#22D3EE"  # 白字青描边（霓虹灯管感）
    if style == "paper":
        return "#111111", "#D6CFC0"  # 深灰字 + 米色描边（报纸铅字感）
    if style == "sticker":
        return "#000000", "#FFFFFF"  # 黑字白描边（贴纸风）
    return "#FFFFFF", "#B71C1C"  # red/渐变用深描边


def _upload_bg(b64: str) -> Image.Image:
    """用户上传背景图：等比缩放至 1080 画布居中，黑边填充（不变形）。"""
    import base64 as _b64

    if "," in b64:
        b64 = b64.split(",", 1)[1]
    try:
        raw = _b64.b64decode(b64)
    except Exception as e:
        raise HTTPException(400, "背景图 base64 解码失败") from e
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(400, "背景图过大（≤8MB）")
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:
        raise HTTPException(400, "背景图格式不支持（请用 JPG/PNG）") from e
    im.thumbnail((CANVAS, CANVAS), Image.LANCZOS)
    canvas = Image.new("RGB", (CANVAS, CANVAS), (17, 17, 17))
    canvas.paste(im, ((CANVAS - im.width) // 2, (CANVAS - im.height) // 2))
    return canvas


def _load_emoji_font(size: int) -> ImageFont.FreeTypeFont | None:
    """加载彩色 emoji 字体（macOS Apple → Linux Noto），失败返回 None。"""
    for fp in (
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    ):
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return None


def _draw_decoration(img: Image.Image, decoration: str) -> None:
    """右下角横排 emoji 装饰（微信表情常用点缀，最多 4 个）。"""
    import re as _re

    emojis = [e for e in _re.split(r"[\s,，、]+", (decoration or "").strip()) if e]
    if not emojis:
        return
    emojis = emojis[:4]
    font = _load_emoji_font(96)
    if font is None:
        return
    d = ImageDraw.Draw(img, "RGBA")
    gap = 36
    total = sum(d.textlength(e, font=font) for e in emojis) + gap * (len(emojis) - 1)
    x = CANVAS - MARGIN - total
    y = CANVAS - MARGIN - 150
    for e in emojis:
        d.text((x, y), e, font=font)
        x += d.textlength(e, font=font) + gap


def _overlay_text_bars(img: Image.Image, top_text: str, bottom_text: str) -> Image.Image:
    """顶部/底部半透明底条，保证大字在复杂背景上可读（商用标准）。"""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if top_text:
        od.rectangle([0, 0, CANVAS, TOP_H], fill=(0, 0, 0, 110))
    if bottom_text:
        od.rectangle([0, CANVAS - BOTTOM_H, CANVAS, CANVAS], fill=(0, 0, 0, 110))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _ai_bg(prompt: str) -> Image.Image:
    """文生图生成表情包背景，失败抛异常。"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY，AI 模式不可用（可先使用经典模板模式）")
    resp = requests.post(
        f"{AGNES_API_BASE}/images/generations",
        headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "agnes-image-2.1-flash",
            "prompt": prompt,
            "size": "1024x1024",
            "n": 1,
        },
        timeout=180,
    )
    if resp.status_code != 200:
        raise HTTPException(500, f"文生图失败: {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    if not data.get("data"):
        raise HTTPException(500, f"文生图失败: {data}")
    item = data["data"][0]
    url = item.get("url")
    if url:
        img_resp = requests.get(url, timeout=60)
        return Image.open(io.BytesIO(img_resp.content)).convert("RGB").resize((CANVAS, CANVAS), Image.LANCZOS)
    if item.get("b64_json"):
        import base64

        return (
            Image.open(io.BytesIO(base64.b64decode(item["b64_json"])))
            .convert("RGB")
            .resize((CANVAS, CANVAS), Image.LANCZOS)
        )
    raise HTTPException(500, f"文生图返回异常: {data}")


def _save_artifact(filename: str, top_text: str, bottom_text: str, style: str, ai_prompt: str) -> str:
    """登记 artifacts 表（type=image，委托 common.artifacts.save_artifact），失败静默。"""
    meta = {
        "filename": filename,
        "top_text": top_text,
        "bottom_text": bottom_text,
        "style": style,
        "ai_prompt": ai_prompt,
    }
    return save_artifact(
        art_type="image",
        author="meme_factory",
        media_url=f"/api/meme/images/{filename}",
        content=meta,
        metadata=meta,
    )


def _artifact_meta() -> dict:
    """读取 artifacts 表中表情包产物的元数据（filename → {top_text, bottom_text, style}）。"""
    meta: dict = {}
    try:
        from common.db import get_db

        conn = get_db()
        rows = conn.execute(
            "SELECT content, media_url, metadata FROM artifacts "
            "WHERE type='image' AND author='meme_factory' AND active=1"
        ).fetchall()
        conn.close()
        for r in rows:
            fname = (r["media_url"] or "").rsplit("/", 1)[-1]
            if not fname:
                continue
            md = {}
            raw = r["metadata"] or r["content"] or ""
            try:
                md = json.loads(raw)
            except Exception:
                pass
            top = md.get("top_text", "") or ""
            bottom = md.get("bottom_text", "") or ""
            # 兼容旧数据：metadata 为 {filename, prompt}，prompt 格式 "top / bottom"
            if not top and not bottom and isinstance(md, dict) and md.get("prompt"):
                parts = str(md["prompt"]).split("/", 1)
                top, bottom = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
            # 兼容更旧数据：content 为 "top / bottom" 纯文本
            if not top and not bottom and isinstance(raw, str) and "/" in raw and not raw.startswith("{"):
                parts = raw.split("/", 1)
                top, bottom = parts[0].strip(), parts[1].strip()
            meta[fname] = {
                "top_text": top,
                "bottom_text": bottom,
                "style": md.get("style", ""),
                "title": md.get("title", ""),
                "ai_prompt": md.get("ai_prompt", ""),
            }
    except Exception as e:
        logger.debug(f"_artifact_meta skipped: {e}")
    return meta


async def _meme_generate_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """文字一键生成表情包（同步/异步任务共用执行体，异步时回报进度）。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    top_text = (payload.get("top_text") or "").strip()
    bottom_text = (payload.get("bottom_text") or "").strip()
    style = payload.get("style") or "yellow"
    ai_style = payload.get("ai_style") or "flat"
    bg_upload = payload.get("bg_upload") or ""
    decoration = payload.get("decoration") or ""
    ai_prompt = payload.get("ai_prompt") or ""
    if not top_text and not bottom_text:
        raise HTTPException(400, "请输入至少一行文字（顶部或底部）")
    if style not in {s["id"] for s in STYLES}:
        raise HTTPException(400, f"未知风格: {style}")
    if style == "upload" and not bg_upload:
        raise HTTPException(400, "上传背景模式需要提供 bg_upload 图片（base64）")

    # 背景
    if style == "ai":
        _report(20, "AI 正在绘制表情包背景…")
        full_prompt = ai_prompt.strip() or f"{top_text}，{bottom_text}"
        scene = (
            f"{AI_STYLES.get(ai_style, AI_STYLES['flat'])}，画面主体居中偏下，"
            "顶部与底部各预留 20% 高度纯净留白区域用于叠加文字，背景简洁不杂乱"
        )
        img = await asyncio.to_thread(_ai_bg, f"{full_prompt}。{scene}")
        # 顶部 + 底部半透明底条，保证大字在任何画面上都可读（商用标准）
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        if top_text:
            od.rectangle([0, 0, CANVAS, TOP_H], fill=(0, 0, 0, 110))
        if bottom_text:
            od.rectangle([0, CANVAS - BOTTOM_H, CANVAS, CANVAS], fill=(0, 0, 0, 110))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        top_fill, top_stroke = "#FFFFFF", "#000000"
        bottom_fill, bottom_stroke = "#FFFFFF", "#000000"
    else:
        img = _style_bg(style)
        top_fill, top_stroke = _text_color(style)
        bottom_fill, bottom_stroke = _text_color(style)

    _report(70, "正在叠加文字…")
    draw = ImageDraw.Draw(img)
    # 顶部文字
    _draw_meme_text(draw, top_text, MARGIN, TOP_H, fill=top_fill, stroke=top_stroke, font_size=96)
    # 底部文字
    _draw_meme_text(
        draw, bottom_text, CANVAS - BOTTOM_H, CANVAS - MARGIN, fill=bottom_fill, stroke=bottom_stroke, font_size=96
    )
    # 右下角 emoji 装饰（微信表情常见点缀）
    if decoration:
        _draw_decoration(img, decoration)

    filename = f"meme_{int(time.time() * 1000)}.png"
    img.save(os.path.join(MEME_DIR, filename), "PNG")
    art_id = _save_artifact(filename, top_text, bottom_text, style, ai_prompt.strip())
    _report(100, "表情包已生成")
    return {
        "id": filename,
        "artifact_id": art_id,
        "url": f"/api/meme/images/{filename}",
        "style": style,
        "top_text": top_text,
        "bottom_text": bottom_text,
    }


@router.post("/generate")
async def generate_meme(
    top_text: str = Form(""),
    bottom_text: str = Form(""),
    style: str = Form("yellow"),
    ai_prompt: str = Form(""),
    ai_style: str = Form("flat", description="AI 模式画面风格（flat/3d/pixel/ink/neon）"),
    bg_upload: str = Form("", description="上传背景图 base64 dataURL（style=upload 时必填，≤8MB）"),
    decoration: str = Form("", description="右下角 emoji 装饰，逗号分隔，最多 4 个（如 😂,🔥,💯）"),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """文字一键生成表情包：经典模板（PIL 绘制）或 AI 文生图 + 叠字（默认异步任务）。"""
    top_text = (top_text or "").strip()
    bottom_text = (bottom_text or "").strip()
    if not top_text and not bottom_text:
        raise HTTPException(400, "请输入至少一行文字（顶部或底部）")
    if style not in {s["id"] for s in STYLES}:
        raise HTTPException(400, f"未知风格: {style}")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "top_text": top_text,
        "bottom_text": bottom_text,
        "style": style,
        "ai_prompt": ai_prompt,
        "ai_style": ai_style,
        "bg_upload": bg_upload,
        "decoration": decoration,
    }
    if sync:
        return await _meme_generate_worker(payload)
    task = create_task("meme_generate", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "表情包生成任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


@router.get("/images/{filename}")
async def get_image(filename: str, size: int = 1080):
    """表情包图片：默认返回 1080 原图；size=240/750/2160 时动态导出对应商用尺寸（磁盘缓存）。"""
    path = os.path.join(MEME_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "表情包不存在")
    if size in (240, 750, 2160):
        cache_dir = os.path.join(MEME_DIR, "exports")
        os.makedirs(cache_dir, exist_ok=True)
        stem = os.path.splitext(filename)[0]
        cached = os.path.join(cache_dir, f"{stem}_{size}.png")
        if not os.path.exists(cached):
            try:
                with Image.open(path) as im:
                    im.resize((size, size), Image.LANCZOS).save(cached, "PNG")
            except Exception as e:
                raise HTTPException(500, f"尺寸导出失败: {e}") from e
        return FileResponse(cached, media_type="image/png")
    return FileResponse(path, media_type="image/png")


@router.get("/list")
async def list_memes(
    q: str = "",
    style: str = "",
    sort: str = "newest",
    current_user: dict = require_auth(),
):
    """表情包列表：从 artifacts 合并文案/风格元数据，支持搜索与筛选。"""
    meta = _artifact_meta()
    items = []
    if os.path.exists(MEME_DIR):
        for f in sorted(os.listdir(MEME_DIR), reverse=True):
            if not f.endswith(".png"):
                continue
            filepath = os.path.join(MEME_DIR, f)
            stat = os.stat(filepath)
            m = meta.get(f, {})
            top, bottom = m.get("top_text", ""), m.get("bottom_text", "")
            style_cfg = next((s for s in STYLES if s["id"] == m.get("style")), None)
            title = m.get("title") or f"{top} / {bottom}".strip(" /")
            items.append(
                {
                    "id": f,
                    "url": f"/api/meme/images/{f}",
                    "size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "title": title[:60] or f,
                    "top_text": top,
                    "bottom_text": bottom,
                    "style": m.get("style", ""),
                    "style_label": style_cfg["name"] if style_cfg else "",
                    "ai_prompt": m.get("ai_prompt", ""),
                    "sizes": [s["size"] for s in SIZE_SPECS],
                }
            )

    # 搜索与筛选
    q_lower = (q or "").strip().lower()
    if q_lower:
        items = [
            i
            for i in items
            if q_lower in i["id"].lower() or q_lower in i["top_text"].lower() or q_lower in i["bottom_text"].lower()
        ]
    if style:
        items = [i for i in items if i["style"] == style]
    if sort == "oldest":
        items.reverse()
    return items


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=80, description="新标题")


@router.put("/{filename}/rename")
async def rename_meme(filename: str, req: RenameRequest, current_user: dict = require_auth()):
    """重命名表情包：标题写入 artifacts.metadata.title。"""
    path = os.path.join(MEME_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "表情包不存在")
    try:
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            "SELECT metadata FROM artifacts WHERE media_url=? AND active=1",
            (f"/api/meme/images/{filename}",),
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
                (json.dumps(md, ensure_ascii=False), f"/api/meme/images/{filename}"),
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"rename_meme db skipped: {e}")
    return {"success": True, "title": req.title.strip()}


@router.post("/batch-download")
async def batch_download_memes(ids: list[str] = Form(...), current_user: dict = require_auth()):
    """批量下载多个表情包为 ZIP 包。"""
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ids:
            path = os.path.join(MEME_DIR, fname)
            if os.path.exists(path) and fname.endswith(".png"):
                zf.write(path, fname)
                count += 1
    if count == 0:
        raise HTTPException(400, "没有可下载的文件")
    data = buf.getvalue()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="memes_{int(time.time())}.zip"'},
    )


@router.get("/stats")
async def meme_stats(current_user: dict = require_auth()):
    """表情包工坊统计：总数 / 风格分布 / AI 占比。"""
    items = await list_memes(current_user=current_user)
    total = len(items)
    style_dist = {}
    ai_count = 0
    for i in items:
        s = i["style_label"] or "未标记"
        style_dist[s] = style_dist.get(s, 0) + 1
        if i["style"] == "ai":
            ai_count += 1
    return {
        "total": total,
        "ai_count": ai_count,
        "style_dist": style_dist,
    }


@router.delete("/{filename}")
async def delete_meme(filename: str, current_user: dict = require_auth()):
    path = os.path.join(MEME_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    # 清理尺寸导出缓存
    stem = os.path.splitext(filename)[0]
    for s in (240, 750, 2160):
        cached = os.path.join(MEME_DIR, "exports", f"{stem}_{s}.png")
        if os.path.exists(cached):
            os.remove(cached)
    # 同步注销 artifacts 记录
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            "UPDATE artifacts SET active=0 WHERE media_url=? AND type='image'",
            (f"/api/meme/images/{filename}",),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"delete_meme artifact skipped: {e}")
    return {"success": True}


async def _meme_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装表情包生成，回报进度。"""
    return await _meme_generate_worker(payload, progress=update)


register_handler("meme_generate", _meme_generate_handler, user_limit=2)
