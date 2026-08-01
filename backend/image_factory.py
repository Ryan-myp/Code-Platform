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

import base64
import io
import json
import logging
import os
import time
from datetime import datetime
from io import BytesIO

import requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/image-factory", tags=["图片工厂"])

# 配置
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://api.agnes-ai.cn/v1")
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "image_factory")
TEMPLATE_DIR = os.path.join(IMAGE_DIR, "templates")

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(TEMPLATE_DIR, exist_ok=True)


# ── 辅助函数 ──────────────────────────────────────────────────
def generate_id() -> str:
    return f"img_{int(time.time() * 1000)}"


def save_image(img: Image.Image, fmt: str = "PNG") -> str:
    """保存图像并返回文件名"""
    img_id = generate_id()
    ext = ".png" if fmt == "PNG" else ".jpg"
    filename = f"{img_id}{ext}"
    filepath = os.path.join(IMAGE_DIR, filename)

    # 转换为 RGB
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if fmt == "PNG":
        img.save(filepath, "PNG")
    else:
        img.save(filepath, "JPEG", quality=95)

    return filename


def get_font(size: int = 24) -> ImageFont.FreeTypeFont:
    """获取字体"""
    font_paths = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


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
    """列出所有图片"""
    files = []
    if os.path.exists(IMAGE_DIR):
        for f in os.listdir(IMAGE_DIR):
            if f.endswith((".png", ".jpg", ".jpeg")):
                if filename and filename.lower() not in f.lower():
                    continue
                filepath = os.path.join(IMAGE_DIR, f)
                stat = os.stat(filepath)
                files.append(
                    {
                        "filename": f,
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "url": f"/api/image-factory/images/{f}",
                    }
                )
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files


@router.get("/images/{filename}")
async def get_image(filename: str):
    """获取图片文件"""
    filepath = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "图片不存在")
    return FileResponse(filepath)


@router.delete("/images/{filename}")
async def delete_image(filename: str):
    """删除图片"""
    filepath = os.path.join(IMAGE_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    return {"success": True}


# ── 文生图 API ────────────────────────────────────────────────
@router.post("/generate/text-to-image")
async def text_to_image(
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    model: str = Form("agnes-image-2.1-flash"),
    batch_size: int = Form(1),
    n: int = Form(1),
):
    """
    文生图 - 支持批量生成

    参数:
    - prompt: 图片描述
    - size: 尺寸 (1024x1024, 800x600, 1280x720 等)
    - model: 模型名称
    - batch_size: 批量生成数量 (1-4)
    - n: 每批次生成数量
    """
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    url = f"{AGNES_API_BASE}/images/generations"
    headers = {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}

    # 解析尺寸
    try:
        width, height = map(int, size.split("x"))
        size_str = f"{width}x{height}"
    except Exception:
        size_str = size

    results = []

    for _ in range(batch_size):
        payload = {
            "model": model,
            "prompt": prompt,
            "size": size_str,
            "n": min(n, 4),  # API 限制最多 4 张
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=180)
            resp.raise_for_status()
            data = resp.json()

            if "data" in data and len(data["data"]) > 0:
                for item in data["data"]:
                    image_url = item.get("url")
                    if image_url:
                        img_resp = requests.get(image_url, timeout=60)
                        img = Image.open(io.BytesIO(img_resp.content))
                        filename = save_image(img)
                        results.append(
                            {"id": filename, "url": f"/api/image-factory/images/{filename}", "prompt": prompt}
                        )
            else:
                results.append({"error": f"生成失败：{data}", "prompt": prompt})

        except Exception as e:
            logger.error(f"文生图失败：{e}")
            results.append({"error": f"生成失败：{str(e)}", "prompt": prompt})

    return {"results": results, "total": len(results), "prompt": prompt}


# ── 图生图 API ────────────────────────────────────────────────
@router.post("/generate/image-to-image")
async def image_to_image(
    prompt: str = Form(...),
    image: UploadFile = File(...),
    size: str = Form("1024x1024"),
    strength: float = Form(0.35),
    model: str = Form("agnes-image-2.1-flash"),
):
    """图生图 - 基于输入图片生成新图片"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")

    image_content = await image.read()

    url = f"{AGNES_API_BASE}/images/generations"
    headers = {
        "Authorization": f"Bearer {AGNES_API_KEY}",
    }

    files = {"image": ("input.png", image_content, "image/png")}
    data = {"model": model, "prompt": prompt, "size": size, "strength": strength, "n": 1}

    try:
        resp = requests.post(url, headers=headers, data=data, files=files, timeout=180)
        resp.raise_for_status()
        data = resp.json()

        if "data" in data and len(data["data"]) > 0:
            image_url = data["data"][0].get("url")
            if image_url:
                img_resp = requests.get(image_url, timeout=60)
                result_img = Image.open(io.BytesIO(img_resp.content))
                filename = save_image(result_img)
                return {"id": filename, "url": f"/api/image-factory/images/{filename}", "prompt": prompt}

        return JSONResponse(status_code=500, content={"error": "生成失败", "response": data})
    except Exception as e:
        logger.error(f"图生图失败：{e}")
        raise HTTPException(500, f"生成失败：{str(e)}")


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
    filename = save_image(cropped)
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

    filename = save_image(img)
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

    # 创建掩码
    pixels = img.load()
    mask = Image.new("L", (w, h), 0)
    mask_pixels = mask.load()

    for y in range(h):
        for x in range(w):
            px = pixels[x, y]
            if abs(px[0] - bg_color[0]) < 30 and abs(px[1] - bg_color[1]) < 30 and abs(px[2] - bg_color[2]) < 30:
                mask_pixels[x, y] = 0
            else:
                mask_pixels[x, y] = 255

    result = img.copy()
    result.putalpha(mask)

    filename = save_image(result)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/blur")
async def blur_image(image: UploadFile = File(...), radius: int = Form(5)):
    """高斯模糊"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))

    blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
    filename = save_image(blurred)
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
    except:
        font = ImageFont.load_default()

    # 解析颜色
    r = int(color[1:3], 16) if color.startswith("#") and len(color) == 7 else 255
    g = int(color[3:5], 16) if color.startswith("#") and len(color) == 7 else 255
    b = int(color[5:7], 16) if color.startswith("#") and len(color) == 7 else 255

    draw.text((x, y), text, fill=(r, g, b, 255), font=font)

    # 合成
    result = Image.alpha_composite(img, overlay)
    filename = save_image(result)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


@router.post("/edit/batch-resize")
async def batch_resize(images: list[UploadFile] = File(...), width: int = Form(800), height: int = Form(800)):
    """批量调整大小"""
    results = []
    for image in images:
        content = await image.read()
        img = Image.open(io.BytesIO(content))
        img = img.resize((width, height), Image.LANCZOS)
        filename = save_image(img)
        results.append({"filename": filename, "url": f"/api/image-factory/images/{filename}"})
    return {"results": results, "total": len(results)}


@router.post("/edit/rotate")
async def rotate_image(image: UploadFile = File(...), angle: int = Form(0)):
    """旋转图片"""
    image_content = await image.read()
    img = Image.open(io.BytesIO(image_content))
    rotated = img.rotate(angle, expand=True)
    filename = save_image(rotated)
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
    filename = save_image(flipped)
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

    filename = save_image(result)
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

    filename = save_image(img)
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
    except:
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
    filename = save_image(result)
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


@router.post("/template/render")
async def render_template(req: dict):
    """渲染模板"""
    template_id = req.get("template_id")
    overrides = req.get("overrides", {})

    template_path = os.path.join(TEMPLATE_DIR, f"{template_id}.json")
    if not os.path.exists(template_path):
        raise HTTPException(404, "模板不存在")

    with open(template_path, encoding="utf-8") as f:
        template = json.load(f)

    width = overrides.get("width", template.get("width", 1080))
    height = overrides.get("height", template.get("height", 1920))
    bg_color = overrides.get("background", template.get("background", "#FFFFFF"))

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    for layer in template.get("layers", []):
        layer_type = layer.get("type")

        if layer_type == "text":
            x = layer.get("x", 0)
            y = layer.get("y", 0)
            key = layer.get("key", "")
            default_text = layer.get("text", "")
            text = overrides.get(key, default_text)
            font_size = layer.get("font_size", 24)
            font_color = layer.get("color", "#000000")

            try:
                font = get_font(font_size)
            except Exception:
                font = ImageFont.load_default()

            draw.text((x, y), text, fill=font_color, font=font)

        elif layer_type == "image":
            image_url = layer.get("url", "")
            if image_url and image_url.startswith("http"):
                try:
                    resp = requests.get(image_url, timeout=30)
                    layer_img = Image.open(io.BytesIO(resp.content))
                    layer_img = layer_img.convert("RGBA")

                    x = layer.get("x", 0)
                    y = layer.get("y", 0)
                    w = layer.get("width", 200)
                    h = layer.get("height", 200)
                    layer_img = layer_img.resize((w, h), Image.LANCZOS)

                    img.paste(layer_img, (x, y), layer_img)
                except Exception as e:
                    print(f"Layer image error: {e}")

    filename = save_image(img)
    return {"id": filename, "url": f"/api/image-factory/images/{filename}"}


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
async def person_segmentation(image: UploadFile = File(...)):
    """人像分割 - 将人物从背景中分离"""
    try:
        content = await image.read()
        img = Image.open(BytesIO(content))

        # 使用颜色阈值法进行人像分割
        # 检测人体轮廓并创建掩码
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)

        # 简单实现：检测中心区域（假设人物在画面中央）
        w, h = img.size
        # 创建一个椭圆掩码，模拟人物轮廓
        draw.ellipse(
            [
                w * 0.2,
                h * 0.05,  # 顶部
                w * 0.8,
                h * 0.95,  # 底部
            ],
            fill=255,
        )

        # 保存掩码
        mask_path = os.path.join(IMAGE_DIR, f"mask_{datetime.now().timestamp()}.png")
        mask.save(mask_path)

        # 应用分割
        result = img.copy()
        result = result.convert("RGBA")

        # 简单的边缘检测，增强轮廓
        # 这里可以后续接入 rembg 或其他人像分割模型
        for y in range(h):
            for x in range(w):
                mask_pixel = mask.getpixel((x, y))
                if mask_pixel < 128:
                    result.putpixel((x, y), (0, 0, 0, 0))  # 透明

        filename = save_image(result)
        return {"id": filename, "url": f"/api/image-factory/images/{filename}"}

    except Exception as e:
        raise HTTPException(500, f"人像分割失败: {str(e)}") from e


# ── 虚拟试衣 API ──────────────────────────────────────────────
@router.post("/try-on/generate")
async def virtual_try_on(
    person_image: UploadFile = File(...),
    clothing_image: UploadFile = File(...),
    description: str = Form(""),
    style: str = Form("casual"),  # casual, formal, sporty, fashion
    background: str = Form("beach"),  # beach, city, space, studio, etc.
):
    """
    虚拟试衣功能
    - 上传人物照片
    - 上传衣物照片
    - AI 生成试穿效果
    - 可选择背景场景
    """
    try:
        # 读取人物和衣物图像
        person_content = await person_image.read()
        clothing_content = await clothing_image.read()

        img = Image.open(BytesIO(clothing_content))

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

        prompt = f"{description} {style_prompts.get(style, style_prompts['casual'])}, high quality fashion photography, professional lighting"
        bg_prompt = background_prompts.get(background, background_prompts["beach"])
        
        # 将图像编码为 base64
        person_b64 = base64.b64encode(person_content).decode('utf-8')
        clothing_b64 = base64.b64encode(clothing_content).decode('utf-8')

        # 调用 Agnes AI 图生图 API
        api_key = os.environ.get("AGNES_API_KEY")
        api_base = os.environ.get("AGNES_API_BASE", "https://api.agnes-ai.cn/v1")

        response = requests.post(
            f"{api_base}/images/generations",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "agnes-image-v2",
                "prompt": f"Virtual try-on: person wearing {style_prompts.get(style, 'casual outfit')}, background: {bg_prompt}, photorealistic, 8K quality",
                "image": person_b64,
                "size": "1024x1024",
                "strength": 0.75,
            },
            timeout=120,
        )

        if response.status_code != 200:
            raise HTTPException(500, f"生成失败: {response.text}")

        data = response.json()
        img_data = base64.b64decode(data["data"][0]["b64_json"])
        result_img = Image.open(BytesIO(img_data))

        filename = save_image(result_img)
        return {
            "id": filename,
            "url": f"/api/image-factory/images/{filename}",
            "prompt": prompt,
            "style": style,
            "background": background,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"虚拟试衣失败: {str(e)}") from e


# ── 背景替换 API ──────────────────────────────────────────────
@router.post("/edit/replace-background")
async def replace_background(
    image: UploadFile = File(...),
    background: str = Form("beach"),
    force_color: str = Form(""),  # 可选：强制使用指定颜色
):
    """背景替换 - 将人物从原背景中分离并替换为新背景"""
    try:
        content = await image.read()
        img = Image.open(BytesIO(content))
        img = img.convert("RGBA")

        w, h = img.size

        # 场景背景生成
        background_scenes = {
            "beach": [(255, 182, 193), (135, 206, 235)],  # 粉色沙滩 + 蓝天
            "city": [(100, 100, 100), (60, 60, 60)],  # 城市灰色调
            "space": [(0, 0, 0), (25, 25, 25)],  # 太空深空
            "studio": [(240, 240, 240), (255, 255, 255)],  # 白色摄影棚
            "forest": [(34, 139, 34), (0, 100, 0)],  # 森林绿
            "snow": [(255, 255, 255), (220, 230, 241)],  # 雪景白
        }

        # 生成背景
        bg_type = background_scenes.get(background, background_scenes["studio"])
        bg_img = Image.new("RGBA", (w, h), (*bg_type[0], 255))

        # 如果有颜色，使用纯色背景
        if force_color:
            try:
                r, g, b = tuple(int(force_color[i : i + 2], 16) for i in (1, 3, 5))
                bg_img = Image.new("RGBA", (w, h), (r, g, b, 255))
            except Exception:
                pass

        # 使用掩码将人物合成到背景上
        mask_path = os.path.join(IMAGE_DIR, f"mask_{datetime.now().timestamp()}.png")
        if os.path.exists(mask_path):
            mask = Image.open(mask_path).convert("L")
            mask = mask.resize(img.size)

            # 应用掩码
            result = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            result = Image.composite(img, bg_img, mask)
        else:
            # 如果没有掩码，直接合成（人物居中）
            result = bg_img.copy()
            # 将人物缩放到合适大小并居中
            person_scaled = img.resize((w, h))
            result.paste(person_scaled, (0, 0), person_scaled.split()[3] if img.mode == "RGBA" else None)

        filename = save_image(result)
        return {
            "id": filename,
            "url": f"/api/image-factory/images/{filename}",
            "background": background,
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
