#!/usr/bin/env python3
"""表情包工坊 — 文字一键生成表情包。

- 经典模板模式（PIL 直接绘制，秒出不依赖 AI）：黄底/白底/红底/黑底/渐变 5 种风格
- AI 生成模式：文生图（Agnes）生成搞笑场景 + 自动叠加 meme 大字
- 顶部/底部双行文字，自动换行、自动缩放、白字黑描边经典风格
- 产物保存到 meme_factory/ 目录并登记 artifacts 表（type=image）
"""

import io
import json
import logging
import os
import time
import zipfile
from datetime import datetime

import requests
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image, ImageChops, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from common.artifacts import save_artifact
from common.auth import require_auth
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

# 导出尺寸规格（商用场景全覆盖）
SIZE_SPECS = [
    {"size": 240, "name": "微信表情单图", "desc": "240×240 微信表情包标准"},
    {"size": 750, "name": "聊天大图", "desc": "750×750 聊天大图/社媒配图"},
    {"size": 1080, "name": "原图", "desc": "1080×1080 默认产物"},
    {"size": 2160, "name": "高清印刷", "desc": "2160×2160 印刷/大屏高清"},
]

_BREAK_CHARS = "，。！？、；：,.!?;: "  # 智能换行优先断点（标点/空格）


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 2) -> list[str]:
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
    for l in lines:
        while len(final) < max_lines and draw.textlength(l, font=font) > max_w:
            cut = 1
            for i in range(2, len(l) + 1):
                if draw.textlength(l[:i], font=font) > max_w:
                    cut = i - 1
                    break
            final.append(l[:cut])
            l = l[cut:]
        if l:
            final.append(l)
    return final[:max_lines]


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
        line_w = max(draw.textlength(l, font=font) for l in lines)
        total_h = len(lines) * int(font_size * 1.2)
        if line_w <= max_w and total_h <= max_h:
            break
        font_size -= 6

    lines = _wrap_text(draw, text, font, max_w)
    line_h = int(font_size * 1.2)
    total_h = len(lines) * line_h
    y = box_top + (max_h - total_h) // 2
    sw = max(3, font_size // 24)
    for l in lines:
        w = draw.textlength(l, font=font)
        x = (CANVAS - w) // 2
        # 投影层：右下偏移黑色实心描边，增强立体感与浅色背景可读性（商用 meme 标准）
        draw.text((x + 4, y + 4), l, font=font, fill="#000000", stroke_width=sw, stroke_fill="#000000")
        draw.text((x, y), l, font=font, fill=fill, stroke_width=sw, stroke_fill=stroke)
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


def _save_artifact(filename: str, top_text: str, bottom_text: str, style: str, ai_prompt: str) -> str:
    """登记 artifacts 表（type=image，委托 common.artifacts.save_artifact），失败静默。"""
    meta = {"filename": filename, "top_text": top_text, "bottom_text": bottom_text,
            "style": style, "ai_prompt": ai_prompt}
    return save_artifact(
        art_type="image", author="meme_factory",
        media_url=f"/api/meme/images/{filename}", content=meta, metadata=meta,
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
        scene = ("扁平插画风格，干净简洁的现代网络表情包场景，高饱和配色，画面主体居中偏下，"
                 "顶部与底部各预留 20% 高度纯净留白区域用于叠加文字，背景简洁不杂乱")
        img = _ai_bg(f"{full_prompt}。{scene}")
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

    draw = ImageDraw.Draw(img)
    # 顶部文字
    _draw_meme_text(draw, top_text, MARGIN, TOP_H, fill=top_fill, stroke=top_stroke, font_size=96)
    # 底部文字
    _draw_meme_text(draw, bottom_text, CANVAS - BOTTOM_H, CANVAS - MARGIN, fill=bottom_fill, stroke=bottom_stroke, font_size=96)

    filename = f"meme_{int(time.time() * 1000)}.png"
    img.save(os.path.join(MEME_DIR, filename), "PNG")
    art_id = _save_artifact(filename, top_text, bottom_text, style, ai_prompt.strip())
    return {
        "id": filename,
        "artifact_id": art_id,
        "url": f"/api/meme/images/{filename}",
        "style": style,
        "top_text": top_text,
        "bottom_text": bottom_text,
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
                raise HTTPException(500, f"尺寸导出失败: {e}")
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
            items.append({
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
            })

    # 搜索与筛选
    q_lower = (q or "").strip().lower()
    if q_lower:
        items = [i for i in items if q_lower in i["id"].lower()
                 or q_lower in i["top_text"].lower() or q_lower in i["bottom_text"].lower()]
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
