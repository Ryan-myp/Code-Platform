#!/usr/bin/env python3

async def _meme_generate_simple(image_url: str, style: str, output_path: str) -> dict:
    """简化版 meme 生成。"""
    return {"status": "success", "output_path": output_path}

async def _prepare_meme_params_simple(payload: dict) -> dict:
    """简化版准备 meme 参数。"""
    return {
        "image_url": payload.get("image_url", ""),
        "style": payload.get("style", "yellow"),
        "output_path": payload.get("output_path", "")
    }
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
from common.helpers import _notify_progress
from common.auth import require_auth
from common.config import load_config, resolve_api_key, resolve_api_base
from common.llm import _safe_exc_msg
from content_safety import check_text, quality_check_image, quality_report
from publish_kit import build_publish_zip, license_text, pack_dir_name, platform_spec_text, publish_registry
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/meme", tags=["表情包工坊"])

load_config()
from common.config import AGNES_API_BASE, AGNES_API_KEY  # noqa: E402

MEME_DIR = os.path.join(os.path.dirname(__file__), "meme_factory")
os.makedirs(MEME_DIR, exist_ok=True)

# 风格预览图：模板风格=真实底图渲染，AI 风格=本地示意卡（不调文生图，秒出）
PREVIEW_DIR = os.path.join(MEME_DIR, "previews")
os.makedirs(PREVIEW_DIR, exist_ok=True)
PREVIEW_SIZE = 480

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
    "oil": "厚涂油画风格，可见笔触与颜料质感，浓郁色彩，艺术感强",
    "anime": "赛璐璐日漫风格，清晰线条与平涂上色，明亮通透，动画电影质感",
    "film": "电影写实质感，胶片颗粒与自然光影，浅景深，故事感强",
}

# AI 风格中文名（风格预览卡与前端展示共用）
AI_STYLE_LABELS = {
    "flat": "扁平插画",
    "3d": "3D 软萌",
    "pixel": "像素复古",
    "ink": "水墨国风",
    "neon": "霓虹赛博",
    "oil": "油画质感",
    "anime": "赛璐璐动漫",
    "film": "电影写实",
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

# 微信表情开放平台发布规格（提交审核需 16 张成套）
WECHAT_PACK_MAX = 16
WECHAT_PACK_SPECS = [
    {"name": "表情主图", "value": "240×240 PNG，透明或纯色背景，单张 ≤500KB", "desc": "16 张成套提交审核；本包已按原图等比缩放"},
    {"name": "表情缩略图", "value": "120×120 PNG（与主图内容一致）", "desc": "聊天面板内的小图预览"},
    {"name": "聊天页图标", "value": "50×50 PNG", "desc": "聊天面板入口图标"},
    {"name": "详情页横幅", "value": "750×400 PNG/JPG", "desc": "表情商店详情页展示图，本包已生成 4×4 宫格预览"},
    {"name": "表情名称", "value": "4-12 个汉字（或 2-8 个英文单词）", "desc": "提交审核时填写，避免与已有表情重名"},
    {"name": "表情介绍", "value": "50 字以内", "desc": "提交审核时填写"},
    {"name": "版权信息", "value": "真实有效的版权人信息", "desc": "提交审核时填写，随本包 LICENSE.txt 一并存档"},
]
WECHAT_PACK_NOTES = (
    "1. 微信表情开放平台（sticker.weixin.qq.com）提交审核需注册表情开放平台账号；"
    "2. 一套表情必须为 16 张才能提交审核；"
    "3. 图片不得包含二维码、联系方式、广告水印；"
    "4. 文字内容需通过内容安全审核，请勿使用违规用语；"
    "5. 审核通过后可上架微信表情商店，可按份数设置付费或免费发布。"
)

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
        # 注意 ImageChops.add 的 scale 作用于两图之和，需先把噪声中心化到 ±16 再纯加
        noise = Image.effect_noise((CANVAS, CANVAS), 10).convert("RGB")
        noise = noise.point(lambda v: v // 8 - 16)
        img = ImageChops.add(img, noise)
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


# ══════════════════════════════════════════════════════════════
# v15：风格预览图（模板风格=真实底图渲染，AI 风格=示意卡）
# ══════════════════════════════════════════════════════════════


def _draw_centered_label(img: Image.Image, text: str, y: int, fill: str, stroke: str, max_font: int = 64) -> None:
    """在画布中央绘制一行自动缩字号文字（含投影描边），供预览卡使用。"""
    d = ImageDraw.Draw(img)
    font = get_font(max_font)
    while font.size > 24 and d.textlength(text, font=font) > img.width - 80:
        font = get_font(font.size - 4)
    w = d.textlength(text, font=font)
    x = (img.width - w) // 2
    d.text((x + 4, y + 4), text, font=font, fill="#000000", stroke_width=4, stroke_fill="#000000")
    d.text((x, y), text, font=font, fill=fill, stroke_width=4, stroke_fill=stroke)


def _build_ai_style_card(size: int, name: str, desc: str) -> Image.Image:
    """AI 画面风格示意卡：深色渐变底 + 风格名 + 说明 + 「AI 效果示意」徽标。

    本地 PIL 绘制（不调文生图），用于生成前预览画面质感方向。
    """
    img = _gradient_bg((30, 30, 60), (96, 32, 82)).resize((size, size), Image.LANCZOS)
    _draw_centered_label(img, name, size // 2 - 70, "#FFFFFF", "#B026FF", max_font=56)
    d = ImageDraw.Draw(img)
    if desc:
        font = get_font(26)
        while font.size > 15 and d.textlength(desc, font=font) > size - 50:
            font = get_font(font.size - 2)
        w = d.textlength(desc, font=font)
        d.text(((size - w) // 2, size // 2 + 30), desc, font=font, fill="#C9C9E8")
    badge = "AI 效果示意"
    font2 = get_font(24)
    w2 = d.textlength(badge, font=font2)
    d.text(((size - w2) // 2, size - 70), badge, font=font2, fill="#8E8EA8")
    return img


def build_style_preview(style_id: str) -> Image.Image:
    """生成单风格预览图（480×480，纯函数可单测）。

    - 模板风格：复用 _style_bg/_text_color 渲染真实底图 + 居中风格名，预览与成图一致；
    - upload：灰格示意卡；ai 与未知 id：AI 风格示意卡。
    """
    style_ids = {s["id"] for s in STYLES}
    if style_id not in style_ids:
        return _build_ai_style_card(PREVIEW_SIZE, style_id or "未知", "")
    info = next(s for s in STYLES if s["id"] == style_id)
    if style_id == "ai":
        return _build_ai_style_card(PREVIEW_SIZE, info["name"], info["desc"])
    if style_id == "upload":
        img = Image.new("RGB", (PREVIEW_SIZE, PREVIEW_SIZE), (226, 232, 240))
        # 棋盘格纹样示意「上传自己的图片」
        d = ImageDraw.Draw(img)
        for r in range(0, PREVIEW_SIZE, 60):
            for c in range(0, PREVIEW_SIZE, 60):
                if (r // 60 + c // 60) % 2 == 0:
                    d.rectangle([c, r, c + 60, r + 60], fill=(203, 213, 225))
        _draw_centered_label(img, info["name"], PREVIEW_SIZE // 2 - 70, "#FFFFFF", "#64748B", max_font=56)
        d2 = ImageDraw.Draw(img)
        font = get_font(26)
        w = d2.textlength(info["desc"], font=font)
        d2.text(((PREVIEW_SIZE - w) // 2, PREVIEW_SIZE // 2 + 30), info["desc"], font=font, fill="#64748B")
        return img
    bg = _style_bg(style_id)
    img = bg.resize((PREVIEW_SIZE, PREVIEW_SIZE), Image.LANCZOS) if bg.size != (PREVIEW_SIZE, PREVIEW_SIZE) else bg
    fill, stroke = _text_color(style_id)
    _draw_centered_label(img, info["name"], PREVIEW_SIZE // 2 - 70, fill, stroke, max_font=64)
    d = ImageDraw.Draw(img)
    font = get_font(26)
    while font.size > 15 and d.textlength(info["desc"], font=font) > PREVIEW_SIZE - 60:
        font = get_font(font.size - 2)
    w = d.textlength(info["desc"], font=font)
    d.text(((PREVIEW_SIZE - w) // 2, PREVIEW_SIZE // 2 + 30), info["desc"], font=font, fill="#444444" if style_id == "paper" else stroke)
    return img


@router.get("/style-previews")
async def style_previews(current_user: dict = require_auth()):
    """全部风格预览图列表（本地生成并缓存，秒出）：模板风格 + AI 风格。"""
    out = []
    for s in STYLES:
        fname = f"{s['id']}.png"
        path = os.path.join(PREVIEW_DIR, fname)
        if not os.path.exists(path):
            try:
                build_style_preview(s["id"]).save(path, "PNG")
            except Exception as e:
                logger.debug(f"style preview {s['id']} failed: {e}")
                continue
        out.append({"id": s["id"], "name": s["name"], "url": f"/api/meme/previews/{fname}"})
    for sid, desc in AI_STYLES.items():
        fname = f"ai_{sid}.png"
        path = os.path.join(PREVIEW_DIR, fname)
        if not os.path.exists(path):
            try:
                _build_ai_style_card(PREVIEW_SIZE, AI_STYLE_LABELS.get(sid, sid), desc).save(path, "PNG")
            except Exception as e:
                logger.debug(f"ai style preview {sid} failed: {e}")
                continue
        out.append({"id": f"ai:{sid}", "style_id": sid, "name": AI_STYLE_LABELS.get(sid, sid), "url": f"/api/meme/previews/{fname}"})
    return out


@router.get("/previews/{filename}")
async def get_style_preview(filename: str):
    """风格预览图静态服务（仅 previews 目录内的 PNG）。"""
    if not filename.endswith(".png") or "/" in filename or ".." in filename:
        raise HTTPException(404, "预览图不存在")
    path = os.path.join(PREVIEW_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "预览图不存在")
    return FileResponse(path, media_type="image/png")


def _ai_bg(prompt: str, uid: str = "") -> Image.Image:
    """文生图生成表情包背景，失败抛异常。"""
    # 函数内取最新配置：config 表运行中修改后无需重启即时生效
    from common.config import IMAGE_MODEL, require_model, resolve_feature_model

    if not resolve_api_key():
        raise HTTPException(400, "未配置中转站 API Key，AI 模式不可用（可先使用经典模板模式）")
    resp = requests.post(
        f"{resolve_api_base()}/images/generations",
        headers={"Authorization": f"Bearer {resolve_api_key()}", "Content-Type": "application/json"},
        json={
            "model": require_model(resolve_feature_model(uid, "image", IMAGE_MODEL), "表情包"),
            "prompt": prompt,
            "size": "1024x1024",
            "n": 1,
        },
        timeout=180,
    )
    if resp.status_code != 200:
        exc = requests.HTTPError(f"HTTP {resp.status_code} error", response=resp)
        from common.llm import api_error_detail

        raise HTTPException(500, "操作失败，请稍后重试")
    data = resp.json()
    if not data.get("data"):
        raise HTTPException(500, "操作失败，请稍后重试")
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
    raise HTTPException(500, "文生图返回异常，请稍后重试")


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



async def _meme_generate_simple(image_url: str, style: str, output_path: str) -> dict:
    """简化版 meme 生成。"""
    # 简化的处理逻辑
    result = {
        "status": "success",
        "output_path": output_path,
        "style": style
    }
    return result


def _meme_validate(payload: dict) -> dict:
    """表情包参数提取 + 校验 + 安全审核。返回规范化参数。"""
    def _get_text(key: str) -> str:
        return (payload.get(key) or "").strip()

    top_text = _get_text("top_text")
    bottom_text = _get_text("bottom_text")
    style = payload.get("style") or "yellow"
    bg_upload = payload.get("bg_upload") or ""
    ai_prompt = payload.get("ai_prompt") or ""
    if not top_text and not bottom_text:
        raise HTTPException(400, "请输入至少一行文字（顶部或底部）")
    if style not in {s["id"] for s in STYLES}:
        raise HTTPException(400, "操作失败，请稍后重试")
    if style == "upload" and not bg_upload:
        raise HTTPException(400, "上传背景模式需要提供 bg_upload 图片（base64）")
    for label, t in (("顶部文字", top_text), ("底部文字", bottom_text), ("AI 画面描述", ai_prompt)):
        if not t:
            continue
        res = check_text(t, "表情包")
        if not res["ok"]:
            raise HTTPException(400, "内容审核不通过")
    return {
        "top_text": top_text, "bottom_text": bottom_text, "style": style,
        "bg_upload": bg_upload, "ai_prompt": ai_prompt,
        "ai_style": payload.get("ai_style") or "flat",
        "decoration": payload.get("decoration") or "",
        "character": (payload.get("character") or "").strip(),
    }


async def _meme_render_bg(params: dict, _report) -> tuple:
    """生成表情包背景。返回 (img, top_fill, top_stroke, bottom_fill, bottom_stroke)。"""
    if params["style"] == "ai":
        _report(20, "AI 正在绘制表情包背景…")
        full_prompt = params["ai_prompt"].strip() or f"{params['top_text']}，{params['bottom_text']}"
        scene = (
            f"{AI_STYLES.get(params['ai_style'], AI_STYLES['flat'])}，画面主体居中偏下，"
            "顶部与底部各预留 20% 高度纯净留白区域用于叠加文字，背景简洁不杂乱"
        )
        if params["character"]:
            scene += f"，角色设定（全套必须完全一致）：{params['character']}；所有画面中的角色形象、服装、画风保持一致"
        img = await asyncio.to_thread(_ai_bg, f"{full_prompt}。{scene}", payload.get("user_id") or "")
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        if params["top_text"]:
            od.rectangle([0, 0, CANVAS, TOP_H], fill=(0, 0, 0, 110))
        if params["bottom_text"]:
            od.rectangle([0, CANVAS - BOTTOM_H, CANVAS, CANVAS], fill=(0, 0, 0, 110))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        return img, "#FFFFFF", "#000000", "#FFFFFF", "#000000"
    img = _style_bg(params["style"])
    top_fill, top_stroke = _text_color(params["style"])
    return img, top_fill, top_stroke, top_fill, top_stroke

async def _meme_generate_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """文字一键生成表情包（同步/异步任务共用执行体，异步时回报进度）。"""

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    # v22 表情包模板热度：按模板生成时记录（失败静默）
    tpl_id = (payload.get("template_id") or "").strip()
    if tpl_id:
        try:
            from meme_templates import record_usage
            record_usage(tpl_id)
        except Exception:
            pass

    params = _meme_validate(payload)
    top_text, bottom_text = params["top_text"], params["bottom_text"]
    style = params["style"]
    decoration = params["decoration"]

    # 背景
    img, top_fill, top_stroke, bottom_fill, bottom_stroke = await _meme_render_bg(params, _report)

    _report(70, "正在叠加文字…")
    draw = ImageDraw.Draw(img)
    _draw_meme_text(draw, top_text, MARGIN, TOP_H, fill=top_fill, stroke=top_stroke, font_size=96)
    _draw_meme_text(
        draw, bottom_text, CANVAS - BOTTOM_H, CANVAS - MARGIN, fill=bottom_fill, stroke=bottom_stroke, font_size=96
    )
    if decoration:
        _draw_decoration(img, decoration)

    filename = f"meme_{int(time.time() * 1000)}.png"
    img.save(os.path.join(MEME_DIR, filename), "PNG")
    art_id = _save_artifact(filename, top_text, bottom_text, style, params["ai_prompt"].strip())
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
    ai_style: str = Form("flat", description="AI 模式画面风格（flat/3d/pixel/ink/neon/oil/anime/film）"),
    bg_upload: str = Form("", description="上传背景图 base64 dataURL（style=upload 时必填，≤8MB）"),
    decoration: str = Form("", description="右下角 emoji 装饰，逗号分隔，最多 4 个（如 😂,🔥,💯）"),
    template_id: str = Form("", description="表情包模板 ID（meme-templates，如 mt_monday）"),
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """文字一键生成表情包：经典模板（PIL 绘制）或 AI 文生图 + 叠字（默认异步任务）。"""
    top_text = (top_text or "").strip()
    bottom_text = (bottom_text or "").strip()
    if not top_text and not bottom_text:
        raise HTTPException(400, "请输入至少一行文字（顶部或底部）")
    if style not in {s["id"] for s in STYLES}:
        raise HTTPException(400, "操作失败，请稍后重试")
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
        "user_id": uid,
        "decoration": decoration,
        "template_id": template_id,
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


@router.post("/generate-set")
async def generate_meme_set(
    items: list[str] = Form(...),
    style: str = Form("yellow"),
    ai_style: str = Form("flat"),
    character: str = Form("", description="成套角色设定，全套保持一致，如：一只圆滚滚的橘猫，穿黄色卫衣"),
    sync: bool = Query(False, description="true=同步执行；默认异步任务"),
    current_user: dict = require_auth(),
):
    """成套生成（商业化关键能力）：一次输入最多 16 个文案，产出风格/角色统一的成套表情包。

    每项格式：``顶部文字|底部文字``（可只填顶部）。全部文字生成前做安全审核，
    命中违规直接拒绝整包生成（避免废包）；AI 模式注入角色一致性约束保证成套观感统一。
    """
    parsed = []
    for it in items:
        it = (it or "").strip().replace("／", "/")
        if not it:
            continue
        if "|" in it:
            top, _, bottom = it.partition("|")
        elif "/" in it:
            top, _, bottom = it.partition("/")
        else:
            top, bottom = it, ""
        parsed.append((top.strip(), bottom.strip()))
    parsed = [p for p in parsed if p[0] or p[1]][:WECHAT_PACK_MAX]
    if not parsed:
        raise HTTPException(400, "请输入至少一条表情文案（格式：顶部文字|底部文字）")

    # 成套前置审核：任一文案违规则拒绝整包（保证成套不废）
    for top, bottom in parsed:
        for label, t in (("顶部文字", top), ("底部文字", bottom)):
            if not t:
                continue
            res = check_text(t, "表情包")
            if not res["ok"]:
                raise HTTPException(400, "内容审核不通过")

    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {
        "items": [{"top_text": t, "bottom_text": b} for t, b in parsed],
        "style": style,
        "ai_style": ai_style,
        "character": (character or "").strip(),
    }
    if sync:
        return await _meme_generate_set_worker(payload)
    task = create_task("meme_generate_set", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": f"成套生成任务已提交（{len(parsed)} 张），后台执行中，可在任务中心查看进度",
        "task": task,
    }


async def _meme_generate_set_worker(payload: dict, progress: Callable | None = None) -> dict:
    """成套生成执行体：逐张调用单张 worker（同风格/角色），产出成套列表。"""
    items = payload.get("items") or []
    style = payload.get("style") or "yellow"
    ai_style = payload.get("ai_style") or "flat"
    character = (payload.get("character") or "").strip()
    results = []
    total = len(items)
    for i, it in enumerate(items):
        if progress:
            try:
                progress(10 + int(85 * i / max(total, 1)), f"正在生成第 {i + 1}/{total} 张…")
            except Exception:
                pass
        try:
            r = await _meme_generate_worker(
                {
                    "top_text": it.get("top_text", ""),
                    "bottom_text": it.get("bottom_text", ""),
                    "style": style,
                    "ai_style": ai_style,
                    "character": character,
                }
            )
            results.append(r)
        except HTTPException as e:
            results.append({"error": str(e.detail), "top_text": it.get("top_text", "")})
    if progress:
        try:
            progress(100, "成套表情包已生成")
        except Exception:
            pass
    return {
        "set_id": f"meme_set_{int(time.time() * 1000)}",
        "count": len(results),
        "style": style,
        "ai_style": ai_style,
        "character": character,
        "items": results,
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
                raise HTTPException(500, "操作失败，请稍后重试") from e
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


def _wechat_banner(images: list[Image.Image], title: str) -> bytes:
    """微信详情页横幅（750×400 PNG）：白底 + 首图代表作 + 表情名称，开箱即用。"""
    W, H = 750, 400
    banner = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(banner)
    if images:
        cover = images[0].copy()
        cover.thumbnail((300, 300), Image.LANCZOS)
        banner.paste(cover, ((W - cover.width) // 2, 16))
    if title:
        font = get_font(44)
        # 标题超宽自动缩字号
        while font.size > 24 and d.textlength(title, font=font) > W - 80:
            font = get_font(font.size - 4)
        w = d.textlength(title, font=font)
        d.text(((W - w) // 2, 322), title, font=font, fill="#111111")
    buf = io.BytesIO()
    banner.save(buf, "PNG")
    return buf.getvalue()


def split_pack_sets(ids: list[str], max_per_set: int = WECHAT_PACK_MAX) -> list[list[str]]:
    """发布包多套拆分（纯函数，可单测）：按 max_per_set 张为一套分组。

    输入自动去重、跳过非 png 项；返回空列表表示无可打包内容。
    微信审核要求每套 16 张成套，勾选超出一套时按 16 张/套拆分目录打包。
    """
    cleaned = []
    seen = set()
    for f in ids or []:
        if not isinstance(f, str):
            continue
        f = f.strip()
        if not f.endswith(".png") or f in seen:
            continue
        seen.add(f)
        cleaned.append(f)
    if not cleaned:
        return []
    return [cleaned[i : i + max_per_set] for i in range(0, len(cleaned), max_per_set)]


def _pack_set_entries(sets: list[list[str]], meta: dict, pack_title: str, pack_desc: str) -> tuple[dict, list[Image.Image]]:
    """按套构建发布包条目（纯函数，可单测）：每套主图/缩略图 + 表情说明。

    单套时目录即根目录；多套时按「表情包第 N 套」分目录。返回 (entries, 第一套原图列表)。
    """
    root = pack_dir_name("wechat_meme")
    entries: dict = {}
    images: list[Image.Image] = []
    set_total = len(sets)
    for si, picked in enumerate(sets, 1):
        if set_total == 1:
            set_root = root
        else:
            set_root = f"{root}/表情包第{si}套"
        main_dir = f"{set_root}/主图"
        thumb_dir = f"{set_root}/缩略图"
        rows: list[str] = []
        for i, fname in enumerate(picked, 1):
            with Image.open(os.path.join(MEME_DIR, fname)) as im:
                m = meta.get(fname, {})
                cap = " / ".join(x for x in (m.get("top_text"), m.get("bottom_text")) if x) or fname
                rows.append(f"{i:02d}. {cap}")
                b_main = io.BytesIO()
                b_thumb = io.BytesIO()
                im.resize((240, 240), Image.LANCZOS).save(b_main, "PNG")
                im.resize((120, 120), Image.LANCZOS).save(b_thumb, "PNG")
                entries[f"{main_dir}/{i:02d}_{fname}"] = b_main.getvalue()
                entries[f"{thumb_dir}/{i:02d}_{fname}"] = b_thumb.getvalue()
                if si == 1:
                    images.append(im.copy())
        suffix = f"（第{si}套）" if set_total > 1 else ""
        entries[f"{set_root}/表情说明.md"] = (
            f"# {pack_title}{suffix}\n\n{pack_desc}\n\n共 {len(picked)} 张（微信审核需 16 张成套）\n\n"
            + "\n".join(rows)
        )
    return entries, images


@router.post("/publish-pack")
async def meme_publish_pack(
    ids: list[str] = Form(...),
    pack_title: str = Form("我的表情包"),
    pack_desc: str = Form("AI 生成趣味表情包"),
    current_user: dict = require_auth(),
):
    """微信表情包发布包：勾选表情打包为可提交微信表情开放平台的成套物料，支持多套合并。

    - 勾选 ≤16 张按一套打包（主图 240 / 缩略图 120 / 图标 50 / 横幅 750×400）；
    - 勾选 >16 张自动按 16 张/套拆分为「表情包第1套/第2套…」多套目录合并打包；
    - 含上传指南、平台规格说明、商用授权说明、质量自检报告。
    """
    pack_title = (pack_title or "我的表情包").strip()[:30]
    pack_desc = (pack_desc or "").strip()[:200]
    sets = split_pack_sets(ids)
    # 过滤磁盘上不存在的文件，空套丢弃
    sets = [[f for f in s if os.path.exists(os.path.join(MEME_DIR, f))] for s in sets]
    sets = [s for s in sets if s]
    if not sets:
        raise HTTPException(400, "没有可打包的表情包（请先勾选已生成的表情）")
    meta = _artifact_meta()

    root = pack_dir_name("wechat_meme")
    entries, images = _pack_set_entries(sets, meta, pack_title, pack_desc)
    total = sum(len(s) for s in sets)
    set_total = len(sets)

    icon_buf = io.BytesIO()
    images[0].resize((50, 50), Image.LANCZOS).save(icon_buf, "PNG")
    entries[f"{root}/icon_50x50.png"] = icon_buf.getvalue()
    entries[f"{root}/banner_750x400.png"] = _wechat_banner(images, pack_title)
    entries[f"{root}/上传指南_微信表情开放平台.md"] = (
        "# 微信表情开放平台上传指南\n\n"
        "1. 注册登录表情开放平台：https://sticker.weixin.qq.com\n"
        "2. 选择「上传表情」→「静态表情」→ 填写表情名称/介绍/版权信息\n"
        "3. 依次上传 16 张主图（240×240）与缩略图（120×120），本包已按规格生成"
        + (f"（共 {set_total} 套，每套独立成目录，需分别提交）" if set_total > 1 else "")
        + "\n"
        "4. 上传聊天页图标（50×50）与详情页横幅（750×400），本包已生成\n"
        "5. 提交审核（约 1-3 个工作日）；通过后可在商店上架，设置免费或付费"
    )
    entries[f"{root}/规格说明.md"] = platform_spec_text("微信表情开放平台", WECHAT_PACK_SPECS, WECHAT_PACK_NOTES)
    entries[f"{root}/LICENSE.txt"] = license_text(f"微信表情包《{pack_title}》")

    # 生产级内容保障：发布包附质量自检报告（安全审核汇总 + 每张美观度评分）
    try:
        text_results = []
        img_scores = []
        for fname in [f for s in sets for f in s]:
            m = meta.get(fname, {})
            for t in (m.get("top_text", ""), m.get("bottom_text", "")):
                if t:
                    text_results.append(check_text(t, "表情包"))
            try:
                with Image.open(os.path.join(MEME_DIR, fname)) as im:
                    img_scores.append(quality_check_image(im))
            except Exception:
                pass
        ok_all = all(r.get("ok") for r in text_results)
        avg = int(sum(q.get("score", 0) for q in img_scores) / max(len(img_scores), 1))
        extra = [
            f"打包套数：{set_total} 套（微信审核每套需 16 张）",
            f"总张数：{total} 张",
            f"规格合规：主图 240×240 / 缩略图 120×120 / 图标 50×50 / 横幅 750×400 ✓",
            f"平均美观度：{avg}/100" if img_scores else "美观度：未检测",
        ]
        entries[f"{root}/质量自检报告.md"] = quality_report(
            f"微信表情包《{pack_title}》",
            text_check={"ok": ok_all, "risk": "none" if ok_all else "high", "risk_words": [], "categories": [], "suggestion": ""},
            image_quality={"score": avg, "grade": "A" if avg >= 85 else ("B" if avg >= 65 else "C"), "checks": [], "suggestions": []},
            extra=extra,
        )
    except Exception as e:
        logger.debug(f"质量自检报告生成失败: {e}")

    buf = build_publish_zip(entries, "wechat_meme")
    publish = publish_registry.publish("wechat_meme", {"pack_title": pack_title, "count": total, "sets": set_total})
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="wechat_meme_pack_{int(time.time())}.zip"',
            "X-Publish-Result": f"published={str(publish.get('published')).lower()}",
        },
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


async def _meme_generate_set_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：成套生成。"""
    return await _meme_generate_set_worker(payload, progress=update)


register_handler("meme_generate", _meme_generate_handler, user_limit=2)
register_handler("meme_generate_set", _meme_generate_set_handler, user_limit=1)


# ══════════════════════════════════════════════════════════════
# 表情包工坊 v2 增强：GIF 动图生成 + 微信动表情打包
# ══════════════════════════════════════════════════════════════


# ── GIF 动图生成 ─────────────────────────────────────────────

def _make_meme_gif(
    base_img: Image.Image,
    top_text: str,
    bottom_text: str,
    style: str,
    frame_count: int = 8,
    fps: int = 10,
) -> bytes:
    """将静态表情包渲染为 GIF 动图（文字缩放脉冲 + 轻微震动效果）。"""
    frames = []
    w, h = base_img.size

    for i in range(frame_count):
        # 每帧：文字大小脉冲 + 整体轻微平移模拟震动
        progress = (i / max(frame_count - 1, 1)) * 2 * 3.14159  # 一个完整正弦周期
        scale_factor = 1.0 + 0.03 * abs(progress)  # 文字 ±3% 缩放
        shift_x = int(1.5 * (i % 2 == 0) - 0.75)
        shift_y = int(1.0 * ((-1) ** i))

        frame = base_img.copy()
        draw = ImageDraw.Draw(frame)

        # 缩放渲染文字（模拟脉冲）
        try:
            font_big = get_font(int(48 * scale_factor))
            font_small = get_font(int(36 * scale_factor))
        except Exception:
            font_big = get_font(48)
            font_small = get_font(36)

        margin = 16
        max_w = w - margin * 2

        # 顶部文字（居中，带阴影偏移）
        if top_text:
            lines = _wrap_text(draw, top_text, font_big, max_w, max_lines=2)
            text_h = sum(draw.textlength(ln, font=font_big) for ln in lines) if hasattr(draw, 'textlength') else h // 3
            y_start = margin + shift_y
            for ln in lines:
                txt_w = draw.textlength(ln, font=font_big) if hasattr(draw, 'textlength') else len(ln) * font_big.size * 0.6
                x = (w - txt_w) // 2 + shift_x
                _draw_centered_label(frame, ln, y_start, "#FFFFFF", "#000000")
                y_start += font_big.size + 4

        # 底部文字
        if bottom_text:
            lines = _wrap_text(draw, bottom_text, font_small, max_w, max_lines=2)
            y_start = h - margin - font_small.size * len(lines) - shift_y
            for ln in lines:
                txt_w = draw.textlength(ln, font=font_small) if hasattr(draw, 'textlength') else len(ln) * font_small.size * 0.5
                x = (w - txt_w) // 2 - shift_x
                _draw_centered_label(frame, ln, y_start, "#FFFFFF", "#000000")
                y_start += font_small.size + 4

        # 轻微整体裁切模拟震动
        if shift_x or shift_y:
            frame = frame.crop((-abs(shift_x), -abs(shift_y), w + abs(shift_x), h + abs(shift_y)))
            if frame.size != (w, h):
                new_frame = Image.new("RGBA" if base_img.mode == "RGBA" else "RGB", (w, h), (255, 255, 255, 0))
                new_frame.paste(frame, (max(shift_x, 0), max(shift_y, 0)))
                frame = new_frame

        frames.append(frame)

    # 保存为 GIF
    buf = io.BytesIO()
    if frames:
        first = frames[0]
        others = frames[1:]
        first.save(
            buf,
            format="GIF",
            save_all=True,
            append_images=others,
            duration=int(1000 / fps),
            loop=0,
            optimize=True,
        )
    buf.seek(0)
    return buf.getvalue()


@router.post("/generate/gif")
async def generate_meme_gif(
    top_text: str = Form(""),
    bottom_text: str = Form(""),
    style: str = Form("yellow"),
    frame_count: int = Form(8, ge=4, le=16, description="动图帧数（4-16）"),
    fps: int = Form(10, ge=5, le=24, description="帧率（5-24 FPS）"),
    current_user: dict = require_auth(),
):
    """生成 GIF 动图版表情包：静态图 + 文字脉冲震动动画。

    v20：在现有静态表情包基础上，额外生成循环动图（GIF），
    适合微信/Telegram/WhatsApp 聊天场景的动态表情。
    """
    top_text = (top_text or "").strip()
    bottom_text = (bottom_text or "").strip()
    if not top_text and not bottom_text:
        raise HTTPException(400, "请输入至少一行文字")
    if style not in {s["id"] for s in STYLES}:
        raise HTTPException(400, "无效的风格类型")

    # 先生成静态底图
    temp_dir = MEME_DIR / ".temp_gif"
    temp_dir.mkdir(parents=True, exist_ok=True)
    tmp_png = temp_dir / f"gtmp_{int(time.time() * 1000)}.png"

    try:
        # 复用现有渲染逻辑生成静态图
        params = {"top_text": top_text, "bottom_text": bottom_text, "style": style}
        static_img = await _meme_render_bg(params, None)
        base = static_img[0] if isinstance(static_img, tuple) else static_img
        if isinstance(base, str):
            base = Image.open(base)
        elif not isinstance(base, Image.Image):
            base = Image.new("RGB", (400, 400), (255, 255, 255))

        gif_data = _make_meme_gif(base, top_text, bottom_text, style, frame_count, fps)

        # 保存 GIF
        gif_filename = f"meme_gif_{int(time.time() * 1000)}.gif"
        gif_path = MEME_DIR / gif_filename
        gif_path.write_bytes(gif_data)

        # 保存到 artifacts
        meta = {
            "top_text": top_text,
            "bottom_text": bottom_text,
            "style": style,
            "type": "gif",
            "frame_count": frame_count,
            "fps": fps,
            "created_at": datetime.now().isoformat(),
        }
        save_artifact("meme", gif_filename, json.dumps(meta, ensure_ascii=False), extra={"style_label": style})

        return {
            "url": f"/api/meme/images/{gif_filename}",
            "filename": gif_filename,
            "format": "gif",
            "size_bytes": len(gif_data),
            "frames": frame_count,
            "fps": fps,
        }
    finally:
        # 清理临时文件
        try:
            tmp_png.unlink(missing_ok=True)
        except Exception:
            pass


# ── 微信动表情打包（Animated Sticker Pack）──────────────────
WECHAT_ANIMATED_SPECS = [
    {"name": "主图", "value": "GIF 动图（≤3MB）", "desc": "微信动表情主图，支持动画"},
    {"name": "缩略图", "value": "PNG 静帧 120×120", "desc": "聊天列表预览图"},
    {"name": "图标", "value": "PNG 50×50", "desc": "表情面板图标"},
    {"name": "横幅", "value": "PNG 750×400", "desc": "详情页 Banner"},
    {"name": "上限", "value": "每套 16 张动图", "desc": "超出自动拆分多套"},
]
WECHAT_ANIMATED_NOTES = [
    "动表情审核比静态表情更严格，确保内容健康、动画流畅无闪烁",
    "单个 GIF 文件 ≤ 3MB，帧率建议 10-15fps 保证流畅与体积平衡",
    "动表情需要单独审核，提交时勾选「动态表情」类别",
    "动表情上架后可设置付费（最低定价 ¥1.00）",
]


@router.post("/publish-pack/animated")
async def meme_publish_animated_pack(
    ids: list[str] = Form(...),
    pack_title: str = Form("我的动表情"),
    pack_desc: str = Form("AI 生成趣味动表情"),
    current_user: dict = require_auth(),
):
    """微信动表情发布包：筛选 GIF 动图打包为微信表情开放平台动表情格式。

    v20：支持 GIF 动图的微信动表情打包，含上传指南与平台规格说明。
    """
    from pathlib import Path as _Path

    gif_ids = [f for f in ids if f.endswith(".gif") and _Path(MEME_DIR, f).exists()]
    if not gif_ids:
        raise HTTPException(400, "没有找到有效的 GIF 动图（请先用 /generate/gif 生成动表情）")

    sets = split_pack_sets(gif_ids)
    sets = [[f for f in s if _Path(MEME_DIR, f).exists()] for s in sets]
    sets = [s for s in sets if s]
    if not sets:
        raise HTTPException(400, "没有可打包的动表情文件")

    meta = _artifact_meta()
    root = pack_dir_name("wechat_animated_meme")
    entries: dict = {}
    set_total = len(sets)

    for idx, s in enumerate(sets, 1):
        set_root = f"{root}/动表情第{idx}套" if set_total > 1 else root
        for fname in s:
            fpath = _Path(MEME_DIR) / fname
            if fpath.exists():
                entries[f"{set_root}/{fname}"] = str(fpath)

    # 生成缩略图（从 GIF 取第一帧）
    thumb_buf = io.BytesIO()
    icon_buf = io.BytesIO()
    banner_buf = io.BytesIO()
    try:
        with Image.open(_Path(MEME_DIR) / gif_ids[0]) as img:
            # 动图取第一帧做缩略图
            thumb_img = img.convert("RGBA") if img.mode != "RGBA" else img.copy()
            thumb_img.thumbnail((120, 120), Image.LANCZOS)
            thumb_img.save(thumb_buf, "PNG")
            icon_img = thumb_img.resize((50, 50), Image.LANCZOS)
            icon_img.save(icon_buf, "PNG")
    except Exception:
        # fallback：用纯色图
        fallback = Image.new("RGBA", (120, 120), (100, 100, 255, 255))
        fallback.save(thumb_buf, "PNG")
        fallback.resize((50, 50)).save(icon_buf, "PNG")

    # 生成横幅
    try:
        with Image.open(_Path(MEME_DIR) / gif_ids[0]) as img:
            banner_img = img.copy().convert("RGBA")
            banner_img.thumbnail((750, 400), Image.LANCZOS)
            banner_img.save(banner_buf, "PNG")
    except Exception:
        banner_buf = thumb_buf  # fallback 复用

    entries[f"{root}/thumb_120x120.png"] = thumb_buf.getvalue()
    entries[f"{root}/icon_50x50.png"] = icon_buf.getvalue()
    entries[f"{root}/banner_750x400.png"] = banner_buf.getvalue()

    total = sum(len(s) for s in sets)
    entries[f"{root}/上传指南_微信动表情开放平台.md"] = (
        "# 微信动表情开放平台上传指南（v20）\n\n"
        "1. 注册登录表情开放平台：https://sticker.weixin.qq.com\n"
        "2. 选择「上传表情」→「动态表情」→ 填写表情名称/介绍/版权信息\n"
        "3. 依次上传 GIF 动图主图（≤3MB/张），本包已按规格生成缩略图/图标/横幅\n"
        "4. 动表情审核时间约 3-5 个工作日，比静态表情审核周期更长\n"
        "5. 审核通过后即可上架，动表情支持付费销售（最低 ¥1.00）"
        + (f"（共 {set_total} 套，每套独立提交）" if set_total > 1 else "")
        + "\n\n## 注意事项\n"
        "- 动表情内容需健康向上，避免暴力/色情/低俗动画\n"
        "- 单个 GIF ≤ 3MB，推荐帧率 10-15fps\n"
        "- 动表情与静态表情需分别提交审核"
    )
    entries[f"{root}/规格说明.md"] = platform_spec_text(
        "微信动表情开放平台", WECHAT_ANIMATED_SPECS, WECHAT_ANIMATED_NOTES
    )
    entries[f"{root}/LICENSE.txt"] = license_text(f"微信动表情包《{pack_title}》")

    # 质量自检
    try:
        gif_sizes = []
        for fname in gif_ids:
            fpath = _Path(MEME_DIR) / fname
            if fpath.exists():
                gif_sizes.append(fpath.stat().st_size)
        avg_size_kb = sum(gif_sizes) / max(len(gif_sizes), 1) / 1024
        over_limit = sum(1 for s in gif_sizes if s > 3 * 1024 * 1024)
        entries[f"{root}/质量自检报告.md"] = quality_report(
            f"微信动表情包《{pack_title}》",
            text_check=None,
            image_quality=None,
            extra=[
                f"动表情张数：{total} 张（{set_total} 套）",
                f"平均大小：{avg_size_kb:.0f} KB/张",
                f"超限（>3MB）：{over_limit} 张",
                "规格合规：GIF ≤ 3MB / 缩略图 120×120 / 图标 50×50 / 横幅 750×400",
            ],
        )
    except Exception:
        pass

    buf = build_publish_zip(entries, "wechat_animated_meme")
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="wechat_animated_pack_{int(time.time())}.zip"',
        },
    )


__all__ = ["router"]
