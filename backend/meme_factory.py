#!/usr/bin/env python3
"""表情包工坊 — 文字一键生成表情包。

- 经典模板模式（PIL 直接绘制，秒出不依赖 AI）：黄底/白底/红底/黑底/渐变 5 种风格
- AI 生成模式：文生图（Agnes）生成搞笑场景 + 自动叠加 meme 大字
- 顶部/底部双行文字，自动换行、自动缩放、白字黑描边经典风格
- 产物保存到 meme_factory/ 目录并登记 artifacts 表（type=image）
"""

import io
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Optional

import requests
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont

from common.config import load_config

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
    {"id": "ai", "name": "AI 生成", "desc": "文生图场景 + 自动叠字", "bg": "ai"},
]

CANVAS = 1080  # 正方形画布（微信表情标准 1080×1080）
MARGIN = 80    # 文字边距
TOP_H = 240    # 顶部文字区高度
BOTTOM_H = 240  # 底部文字区高度


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取中文字体（macOS PingFang），失败回退默认。"""
    for fp in ["/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/STHeiti Medium.ttc"]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_meme_text(draw: ImageDraw.ImageDraw, text: str, box_top: int, box_bottom: int,
                    fill: str = "#FFFFFF", stroke: str = "#000000", font_size: int = 96) -> None:
    """在指定区域居中绘制 meme 文字：自动换行、自动缩放、白字黑描边。"""
    if not text:
        return
    text = text.strip()
    if not text:
        return
    font = get_font(font_size)
    max_w = CANVAS - MARGIN * 2
    max_h = box_bottom - box_top

    # 自动缩放字号直到能放下（最多 2 行）
    while font_size > 30:
        font = get_font(font_size)
        # 按字符数估算换行
        lines = [text]
        if draw.textlength(text, font=font) > max_w:
            half = max(1, len(text) // 2)
            lines = [text[:half], text[half:]]
        line_w = max(draw.textlength(l, font=font) for l in lines)
        total_h = len(lines) * font_size * 1.2
        if line_w <= max_w and total_h <= max_h:
            break
        font_size -= 6

    # 换行逻辑（按最大宽度精确切分）
    def wrap(t: str) -> list[str]:
        if draw.textlength(t, font=font) <= max_w:
            return [t]
        # 逐字符累积
        lines, cur = [], ""
        for ch in t:
            if draw.textlength(cur + ch, font=font) > max_w and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines[:2]  # meme 文字最多 2 行

    lines = wrap(text)
    line_h = int(font_size * 1.2)
    total_h = len(lines) * line_h
    y = box_top + (max_h - total_h) // 2
    for l in lines:
        w = draw.textlength(l, font=font)
        x = (CANVAS - w) // 2
        draw.text((x, y), l, font=font, fill=fill, stroke_width=max(3, font_size // 24), stroke_fill=stroke)
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
    """按风格生成底图。"""
    if style == "gradient":
        return _gradient_bg((99, 102, 241), (168, 85, 247))
    if style == "black":
        return Image.new("RGB", (CANVAS, CANVAS), (17, 17, 17))
    if style == "red":
        return Image.new("RGB", (CANVAS, CANVAS), (229, 57, 53))
    if style == "white":
        return Image.new("RGB", (CANVAS, CANVAS), (255, 255, 255))
    return Image.new("RGB", (CANVAS, CANVAS), (255, 216, 77))  # yellow 默认


def _text_color(style: str) -> str:
    """按风格取文字/描边色。"""
    if style in ("yellow", "white"):
        return "#FFFFFF", "#000000"   # 白字黑边（经典）
    if style == "black":
        return "#FFFFFF", "#000000"
    return "#FFFFFF", "#B71C1C" if style == "red" else "#1E1B4B"  # red/渐变用深描边


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

        return Image.open(io.BytesIO(base64.b64decode(item["b64_json"]))).convert("RGB").resize((CANVAS, CANVAS), Image.LANCZOS)
    raise HTTPException(500, f"文生图返回异常: {data}")


def _save_artifact(filename: str, prompt: str) -> str:
    """登记 artifacts 表（type=image），失败静默。"""
    art_id = f"art_{uuid.uuid4().hex[:12]}"
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            """INSERT INTO artifacts
               (id, project_id, type, content, version, author, created_at, active, media_url, metadata)
               VALUES (?, ?, 'image', ?, 'v1', 'meme_factory', ?, 1, ?, ?)""",
            (art_id, "", __import__("json").dumps({"filename": filename, "prompt": prompt}, ensure_ascii=False),
             datetime.now().isoformat(), f"/api/meme/images/{filename}",
             __import__("json").dumps({"filename": filename, "prompt": prompt}, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"_save_artifact skipped: {e}")
    return art_id


@router.post("/generate")
async def generate_meme(
    top_text: str = Form(""),
    bottom_text: str = Form(""),
    style: str = Form("yellow"),
    ai_prompt: str = Form(""),
):
    """文字一键生成表情包：经典模板（PIL 绘制）或 AI 文生图 + 叠字。"""
    top_text = (top_text or "").strip()
    bottom_text = (bottom_text or "").strip()
    if not top_text and not bottom_text:
        raise HTTPException(400, "请输入至少一行文字（顶部或底部）")
    if style not in {s["id"] for s in STYLES}:
        raise HTTPException(400, f"未知风格: {style}")

    # 背景
    if style == "ai":
        full_prompt = ai_prompt.strip() or f"{top_text}，{bottom_text}"
        scene = "搞笑夸张的卡通插画场景，网络表情包风格，色彩鲜艳，画面留出上下空间放文字"
        img = _ai_bg(f"{full_prompt}。{scene}")
        top_fill, top_stroke = "#FFFFFF", "#000000"
        bottom_fill, bottom_stroke = "#FFFFFF", "#000000"
    else:
        img = _style_bg(style)
        top_fill, top_stroke = _text_color(style)
        bottom_fill, bottom_stroke = _text_color(style)

    draw = ImageDraw.Draw(img)
    # 顶部文字
    _draw_meme_text(draw, top_text, MARGIN, TOP_H, fill=top_fill, stroke=top_stroke, font_size=96)
    # 底部文字（AI 模式加半透明底条提升可读性）
    if style == "ai" and bottom_text:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle([0, CANVAS - BOTTOM_H, CANVAS, CANVAS], fill=(0, 0, 0, 120))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
    _draw_meme_text(draw, bottom_text, CANVAS - BOTTOM_H, CANVAS - MARGIN, fill=bottom_fill, stroke=bottom_stroke, font_size=96)

    filename = f"meme_{int(time.time() * 1000)}.png"
    img.save(os.path.join(MEME_DIR, filename), "PNG")
    art_id = _save_artifact(filename, f"{top_text} / {bottom_text}")
    return {
        "id": filename,
        "artifact_id": art_id,
        "url": f"/api/meme/images/{filename}",
        "style": style,
        "top_text": top_text,
        "bottom_text": bottom_text,
    }


@router.get("/images/{filename}")
async def get_image(filename: str):
    path = os.path.join(MEME_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "表情包不存在")
    return FileResponse(path, media_type="image/png")


@router.get("/list")
async def list_memes():
    items = []
    if os.path.exists(MEME_DIR):
        for f in sorted(os.listdir(MEME_DIR), reverse=True):
            if not f.endswith(".png"):
                continue
            filepath = os.path.join(MEME_DIR, f)
            stat = os.stat(filepath)
            items.append({
                "id": f,
                "url": f"/api/meme/images/{f}",
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return items


@router.delete("/{filename}")
async def delete_meme(filename: str):
    path = os.path.join(MEME_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return {"success": True}
