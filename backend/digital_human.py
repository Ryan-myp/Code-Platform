"""AI数字人/虚拟主播 — 文案→配音→口播视频合成。

- GET  /api/digital-human/avatars   内置8个虚拟形象库
- GET  /api/digital-human/voices    可选声音列表（复用配音工坊音色）
- POST /api/digital-human/generate  文案+形象+声音+背景 → 生成口播视频
- GET  /api/digital-human/records   历史生成记录
"""

import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_AUDIO_DIR = os.path.join(_BASE_DIR, "uploads", "audio")
UPLOAD_VIDEO_DIR = os.path.join(_BASE_DIR, "uploads", "videos")
PORTRAIT_DIR = os.path.join(_BASE_DIR, "image_factory", "avatars")
os.makedirs(UPLOAD_AUDIO_DIR, exist_ok=True)
os.makedirs(UPLOAD_VIDEO_DIR, exist_ok=True)
os.makedirs(PORTRAIT_DIR, exist_ok=True)

router = APIRouter(prefix="/api/digital-human", tags=["AI数字人"])

# ── 数字人形象库 ──────────────────────────────────────────────
# 每个头像包含 portrait_prompt：用于 AI 生成该数字人的写真肖像
AVATARS = [
    {
        "id": "business-female",
        "name": "晓琳",
        "style": "职业女性",
        "gender": "女",
        "emoji": "👩‍💼",
        "desc": "干练知性，适合产品演示/企业培训/新闻播报",
        "bg_color": "from-blue-500 to-indigo-600",
        "portrait_prompt": "Professional beautiful Chinese female anchor, age 28, business suit, confident smile, studio lighting, portrait photography, 8K, photorealistic, half-body shot, clean background",
    },
    {
        "id": "sexy-goddess",
        "name": "魅影",
        "style": "性感女神",
        "gender": "女",
        "emoji": "💋",
        "desc": "性感魅惑，适合时尚美妆/奢侈品推广/高端直播",
        "bg_color": "from-red-500 to-pink-600",
        "portrait_prompt": "Gorgeous sexy female model, long wavy dark hair, red lipstick, elegant evening dress, glamorous makeup, soft warm lighting, high-end fashion photography, photorealistic, half-body portrait, luxury vibe",
    },
    {
        "id": "sweet-girl",
        "name": "蜜糖",
        "style": "甜美女神",
        "gender": "女",
        "emoji": "🌸",
        "desc": "甜美可人，适合美妆护肤/穿搭分享/情感电台",
        "bg_color": "from-pink-300 to-rose-500",
        "portrait_prompt": "Sweet cute Chinese young woman, age 22, natural makeup, pastel pink outfit, warm smile, soft diffused lighting, portrait photography, 8K, photorealistic, half-body shot, pastel background",
    },
    {
        "id": "cool-queen",
        "name": "冷月",
        "style": "高冷御姐",
        "gender": "女",
        "emoji": "👑",
        "desc": "冷艳霸气，适合3C数码评测/潮流解读/品牌代言",
        "bg_color": "from-purple-600 to-indigo-800",
        "portrait_prompt": "Elegant cold-temperament female model, sharp eyes, dark sleek hair, black leather jacket, urban fashion style, dramatic studio lighting, fashion editorial photography, photorealistic, half-body portrait",
    },
    {
        "id": "business-male",
        "name": "启明",
        "style": "职业男性",
        "gender": "男",
        "emoji": "👨‍💼",
        "desc": "沉稳大气，适合品牌宣传/商业演讲/课程讲解",
        "bg_color": "from-gray-700 to-slate-900",
        "portrait_prompt": "Professional handsome Chinese male anchor, age 35, navy business suit, confident expression, corporate portrait photography, clean studio lighting, photorealistic, half-body shot",
    },
    {
        "id": "casual-female",
        "name": "小悦",
        "style": "生活博主",
        "gender": "女",
        "emoji": "👩",
        "desc": "亲和自然，适合生活分享/带货口播/Vlog旁白",
        "bg_color": "from-pink-500 to-rose-600",
        "portrait_prompt": "Friendly natural Chinese female lifestyle vlogger, age 26, casual outfit, warm genuine smile, natural daylight, lifestyle photography, photorealistic, half-body shot, cozy background",
    },
    {
        "id": "casual-male",
        "name": "浩宇",
        "style": "阳光主播",
        "gender": "男",
        "emoji": "👨",
        "desc": "活力阳光，适合短视频口播/娱乐解说/直播带货",
        "bg_color": "from-amber-500 to-orange-600",
        "portrait_prompt": "Energetic young Chinese male streamer, age 24, casual streetwear, friendly smile, ring light lighting, social media portrait style, photorealistic, half-body shot",
    },
    {
        "id": "tech-female",
        "name": "灵希",
        "style": "科技主播",
        "gender": "女",
        "emoji": "👩‍💻",
        "desc": "专业前沿，适合科技评测/AI产品演示/技术分享",
        "bg_color": "from-violet-500 to-purple-600",
        "portrait_prompt": "Tech-savvy beautiful female tech reviewer, futuristic outfit, intelligent eyes, neon lighting, cyberpunk aesthetic, photorealistic, half-body portrait, tech studio background",
    },
    {
        "id": "charming-mature",
        "name": "韵姐",
        "style": "风韵熟女",
        "gender": "女",
        "emoji": "🌹",
        "desc": "成熟风情，适合情感话题/职场经验/生活智慧分享",
        "bg_color": "from-rose-600 to-amber-600",
        "portrait_prompt": "Elegant mature Chinese female host, age 35, sophisticated makeup, wine red dress, warm studio lighting, professional portrait photography, photorealistic, half-body shot, classy atmosphere",
    },
    {
        "id": "educator-male",
        "name": "博文",
        "style": "教育讲师",
        "gender": "男",
        "emoji": "👨‍🏫",
        "desc": "儒雅稳重，适合课程录制/知识科普/学术分享",
        "bg_color": "from-teal-500 to-cyan-600",
        "portrait_prompt": "Scholarly middle-aged Chinese educator, age 40, glasses, casual blazer, wise gentle smile, library background, warm natural lighting, photorealistic, half-body portrait",
    },
    {
        "id": "cartoon-cute",
        "name": "萌小团",
        "style": "卡通萌宠",
        "gender": "童",
        "emoji": "🐼",
        "desc": "可爱萌趣，适合儿童内容/趣味科普/品牌IP",
        "bg_color": "from-yellow-400 to-yellow-600",
        "portrait_prompt": "Cute 3D cartoon panda mascot character, round shape, big sparkling eyes, friendly smile, soft fur texture, bright colorful background, Pixar style render, half-body shot",
    },
    {
        "id": "anime-style",
        "name": "星野",
        "style": "二次元角色",
        "gender": "女",
        "emoji": "🎀",
        "desc": "ACG风格，适合动漫解说/游戏直播/二次元内容",
        "bg_color": "from-fuchsia-500 to-pink-600",
        "portrait_prompt": "Beautiful anime style female character, pink twin tails, big purple eyes, school uniform with ribbons, cel-shaded, vibrant colors, high quality anime art, half-body illustration",
    },
]

# ── 声音列表（复用配音工坊 Azure Neural 音色） ────────────────
VOICES = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "女", "style": "温柔亲切，清晰自然", "emoji": "👩"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "女", "style": "活泼俏皮，适合生活类内容", "emoji": "👧"},
    {"id": "zh-CN-YunxiNeural", "name": "云希", "gender": "男", "style": "阳光少年感，适合解说/口播", "emoji": "👦"},
    {"id": "zh-CN-YunjianNeural", "name": "云健", "gender": "男", "style": "成熟浑厚，适合品牌/宣传", "emoji": "🧔"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬", "gender": "男", "style": "字正腔圆，新闻播报感", "emoji": "🎙️"},
    {"id": "zh-CN-XiaomoNeural", "name": "晓墨", "gender": "童", "style": "童声可爱，适合儿童/亲子内容", "emoji": "🧒"},
    {"id": "en-US-AriaNeural", "name": "Aria", "gender": "女", "style": "英文女声，自然流利", "emoji": "🇺🇸"},
    {"id": "en-US-ChristopherNeural", "name": "Christopher", "gender": "男", "style": "英文男声，沉稳有力", "emoji": "🇬🇧"},
]

# ── 背景模板 ──────────────────────────────────────────────────
BACKGROUNDS = [
    {"id": "office", "name": "现代办公室", "type": "image", "color": "#1a1a2e"},
    {"id": "studio", "name": "简约演播室", "type": "image", "color": "#16213e"},
    {"id": "nature", "name": "自然风景", "type": "image", "color": "#0f3460"},
    {"id": "tech", "name": "科技蓝幕", "type": "gradient", "color": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"},
    {"id": "warm", "name": "温馨暖调", "type": "gradient", "color": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)"},
    {"id": "dark", "name": "暗黑质感", "type": "gradient", "color": "linear-gradient(135deg, #434343 0%, #000000 100%)"},
]

# ── 场景模板 ──────────────────────────────────────────────────
SCENE_TEMPLATES = [
    {"id": "product", "name": "产品介绍", "desc": "突出产品卖点，节奏明快", "voice_hint": "zh-CN-YunjianNeural", "speed_hint": 1.05},
    {"id": "course", "name": "课程讲解", "desc": "结构化讲解，娓娓道来", "voice_hint": "zh-CN-XiaoxiaoNeural", "speed_hint": 0.95},
    {"id": "news", "name": "新闻播报", "desc": "字正腔圆，专业播报", "voice_hint": "zh-CN-YunyangNeural", "speed_hint": 1.0},
    {"id": "livestream", "name": "直播带货", "desc": "感染力强，促单话术", "voice_hint": "zh-CN-YunjianNeural", "speed_hint": 1.1},
    {"id": "story", "name": "故事讲述", "desc": "情感丰富，引人入胜", "voice_hint": "zh-CN-XiaoxiaoNeural", "speed_hint": 0.9},
]


# ── AI 写真肖像生成 ─────────────────────────────────────────
def _get_portrait_path(avatar_id: str) -> str:
    """返回某数字人形象写真图片的本地路径。"""
    return os.path.join(PORTRAIT_DIR, f"{avatar_id}.jpg")


def _get_portrait_url(avatar_id: str) -> str:
    """返回写真图片的访问 URL。"""
    return f"/api/image-factory/avatars/{avatar_id}.jpg"


def _generate_portrait(avatar_id: str) -> str | None:
    """调用 AI 图片生成 API 为指定数字人生成写真肖像。

    返回本地文件路径，失败返回 None。
    """
    avatar = next((a for a in AVATARS if a["id"] == avatar_id), None)
    if not avatar:
        return None

    prompt = avatar.get("portrait_prompt", "")
    if not prompt:
        # fallback：用名称+风格构造 prompt
        prompt = (
            f"Professional portrait of a {avatar['style']} named {avatar['name']}, "
            f"{avatar['gender']}, photorealistic, studio lighting, half-body shot, "
            f"8K quality, clean background"
        )

    from common.config import AGNES_API_BASE, AGNES_API_KEY
    if not AGNES_API_KEY:
        logger.warning("未配置 AGNES_API_KEY，无法生成数字人写真")
        return None

    try:
        import requests as _req
        url = f"{AGNES_API_BASE}/images/generations"
        headers = {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "agnes-image-2.1-flash",
            "prompt": prompt,
            "size": "1024x1024",
            "n": 1,
        }
        resp = _req.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if "data" in data and len(data["data"]) > 0:
            image_url = data["data"][0].get("url")
            if image_url:
                img_resp = _req.get(image_url, timeout=60)
                img_resp.raise_for_status()
                portrait_path = _get_portrait_path(avatar_id)
                with open(portrait_path, "wb") as f:
                    f.write(img_resp.content)
                logger.info(f"数字人写真已生成：{avatar_id} → {portrait_path}")
                return portrait_path
        logger.warning(f"写真生成返回异常：{data}")
        return None
    except Exception as e:
        logger.exception(f"生成数字人写真失败 {avatar_id}: {e}")
        return None


# ── 视频渲染引擎 ──────────────────────────────────────────────
def _load_font(size: int, candidates: list[str]) -> ImageFont.FreeTypeFont:
    """尝试从候选列表中加载字体，全部失败则回退 load_default。"""
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _audio_duration(path: str) -> float:
    """用 ffprobe 获取音频时长（秒）；文件无效/不可读返回 0（调用方拦截）。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=15,
        )
        duration = float(out.stdout.strip())
        return max(duration, 1.0)
    except Exception:
        return 0.0


def _build_portrait_src(avatar: dict):
    """预加载并缩放写真 → (RGBA图, 圆角遮罩, 宽, 高)；无写真返回 None。"""
    portrait_path = _get_portrait_path(avatar["id"])
    if not os.path.exists(portrait_path):
        return None
    try:
        portrait = Image.open(portrait_path).convert("RGBA")
        target_w, target_h = 520, 650
        portrait = portrait.resize((target_w, target_h), Image.LANCZOS)
        mask = Image.new("L", (target_w, target_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, target_w, target_h], radius=40, fill=255)
        return portrait, mask, target_w, target_h
    except Exception as e:
        logger.warning(f"写真加载失败，使用占位符: {e}")
        return None


def _try_load_emoji_font(size: int):
    """尝试加载系统彩色 emoji 字体；位图字体仅支持固定 strike 尺寸，
    指定尺寸失败时逐级降档（Apple Color Emoji: 160/96/64/32）。"""
    for path in [
        "/System/Library/Fonts/Apple Color Emoji.ttc",
        "/System/Library/Fonts/Apple Color Emoji.ttf",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
    ]:
        for s in (size, 160, 96, 64, 32):
            try:
                return ImageFont.truetype(path, s)
            except Exception:
                continue
    return None


def _wrap_text_lines(text: str, draw: ImageDraw.ImageDraw, font, max_width: int) -> list:
    """按像素宽度自动换行，返回行列表（兼容文案中的换行符）。"""
    lines = []
    current_line = ""
    for char in text:
        if char in "\n\r":
            if current_line:
                lines.append(current_line)
                current_line = ""
            continue
        test_line = current_line + char
        if draw.textbbox((0, 0), test_line, font=font)[2] > max_width:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test_line
    if current_line:
        lines.append(current_line)
    return lines


# ── 动态特效工具（粒子/光斑/渐变/卡拉OK字幕）─────────────────────
def _hex_to_rgb(hex_str: str) -> tuple:
    """#rrggbb → (r,g,b)。"""
    hex_str = hex_str.lstrip("#")
    return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))


def _accent_color(bg_hex: str) -> str:
    """从背景色派生高亮主题色（色相偏移 + 提亮），用于字幕当前字/进度条。"""
    import colorsys
    r, g, b = _hex_to_rgb(bg_hex)
    h, lightness, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    h2 = (h + 1 / 12) % 1.0
    l2 = min(lightness * 1.5 + 0.18, 0.92)
    s2 = max(min(s * 0.9 + 0.15, 1.0), 0.4)
    r2, g2, b2 = colorsys.hls_to_rgb(h2, l2, s2)
    return f"#{int(r2 * 255):02x}{int(g2 * 255):02x}{int(b2 * 255):02x}"


def _derive_gradient_colors(bg_hex: str) -> tuple:
    """从背景色派生渐变两端颜色 → (亮端RGB, 暗端RGB)。"""
    import colorsys
    r, g, b = _hex_to_rgb(bg_hex)
    h, lightness, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    dark = colorsys.hls_to_rgb(h, max(lightness - 0.10, 0.06), min(s + 0.05, 1.0))
    light = colorsys.hls_to_rgb(h, min(lightness + 0.22, 0.96), min(s + 0.2, 1.0))
    return (
        tuple(int(v * 255) for v in light),
        tuple(int(v * 255) for v in dark),
    )


_GRADIENT_CACHE = {}
def _get_gradient_base(w: int, h: int, bg_hex: str):
    """缓存对角渐变基座（numpy float32 数组），避免每帧重新生成。"""
    global _GRADIENT_CACHE
    key = (w, h, bg_hex)
    if key not in _GRADIENT_CACHE:
        import numpy as np
        c_light, c_dark = _derive_gradient_colors(bg_hex)
        x = np.linspace(0, 1, w, dtype=np.float32)
        y = np.linspace(0, 1, h, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)
        t = (xx * 0.62 + yy * 0.38)[..., None]
        _GRADIENT_CACHE[key] = (
            np.array(c_light, dtype=np.float32) * t
            + np.array(c_dark, dtype=np.float32) * (1 - t)
        )
    return _GRADIENT_CACHE[key]


def _make_gradient(w: int, h: int, bg_hex: str, breath: float = 0.0) -> Image.Image:
    """从缓存基座生成渐变帧；breath 为亮度呼吸系数（向量化乘法，~6ms）。"""
    import numpy as np
    base = _get_gradient_base(w, h, bg_hex)
    if breath:
        base = base * (1 + 0.06 * breath)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")


_GLOW_CACHE = {}
def _get_glow_template(radius: int = 150, scale: float = 1.0):
    """高斯柔光斑 RGBA 模板（按 (radius, scale) 缓存，避免每帧重复计算/resize）。"""
    global _GLOW_CACHE
    key = (radius, scale)
    if key not in _GLOW_CACHE:
        import numpy as np
        r = radius
        y, x = np.ogrid[-r:r, -r:r]
        d2 = x.astype(np.float32) ** 2 + y.astype(np.float32) ** 2
        mask = d2 <= r * r
        vals = np.zeros((2 * r, 2 * r), dtype=np.float32)
        vals[mask] = np.exp(-d2[mask] / (2 * (r / 2.6) ** 2))
        alpha = (vals * 255).astype(np.uint8)
        arr = np.zeros((2 * r, 2 * r, 4), dtype=np.uint8)
        arr[..., 0] = arr[..., 1] = arr[..., 2] = 255
        arr[..., 3] = alpha
        base = Image.fromarray(arr, "RGBA")
        if scale != 1.0:
            gw = max(1, int(base.width * scale))
            base = base.resize((gw, gw), Image.LANCZOS)
        _GLOW_CACHE[key] = base
    return _GLOW_CACHE[key]


_PARTICLES_CACHE = None
def _get_particles(count: int = 42) -> list:
    """确定性粒子系统（固定种子，按时间纯函数式计算，无随机状态）。"""
    global _PARTICLES_CACHE
    if _PARTICLES_CACHE is None:
        import random
        rnd = random.Random(2026)
        _PARTICLES_CACHE = [
            {
                "x": rnd.uniform(0.03, 0.97),
                "y": rnd.uniform(0.0, 1.0),
                "r": rnd.uniform(1.0, 3.0),
                "speed": rnd.uniform(14, 34),
                "phase": rnd.uniform(0, 6.283),
                "bright": rnd.uniform(0.22, 0.6),
            }
            for _ in range(count)
        ]
    return _PARTICLES_CACHE


def _draw_particles(img: Image.Image, t: float) -> None:
    """绘制漂浮粒子：缓慢上升 + 左右摆动 + 明暗闪烁。"""
    import math
    w, h = img.size
    d = ImageDraw.Draw(img)
    for p in _get_particles():
        px = p["x"] * w + math.sin(t * 0.55 + p["phase"]) * 14
        py = (p["y"] * h - t * p["speed"]) % h
        alpha = int(p["bright"] * 255 * (0.65 + 0.35 * math.sin(t * 1.4 + p["phase"] * 2)))
        alpha = max(8, min(170, alpha))
        r = p["r"]
        d.ellipse([px - r, py - r, px + r, py + r], fill=f"#ffffff{alpha:02x}")


def _draw_karaoke(draw, lines: list, progress: float, font, x: int, y0: int,
                  line_h: int, accent: str, max_rows: int = 12) -> None:
    """卡拉OK逐字字幕：已读行整行半透明白，当前行逐字显示且当前字主题色高亮。"""
    if not lines:
        return
    display = lines[:max_rows]
    total_chars = sum(len(ln) for ln in display)
    if total_chars == 0:
        return
    chars_done = min(int(progress * total_chars), total_chars - 1)
    # 定位当前行
    acc = 0
    cur_idx = 0
    for i, ln in enumerate(display):
        if acc + len(ln) > chars_done:
            cur_idx = i
            break
        acc += len(ln)
    # 已读行：整行半透明白
    for i in range(cur_idx):
        draw.text((x, y0 + i * line_h), display[i], fill="#ffffffb3", font=font)
    # 当前行：字幕底条 + 逐字着色（已读白 / 当前字主题色 / 未读灰）
    line = display[cur_idx]
    in_done = chars_done - acc
    y_cur = y0 + cur_idx * line_h
    line_w = draw.textlength(line, font=font)
    draw.rounded_rectangle(
        [x - 8, y_cur - 3, x + line_w + 8, y_cur + line_h - 5],
        radius=7, fill="#0000003a",
    )
    cur_x = x
    for j, ch in enumerate(line):
        if j < in_done:
            fill = "#ffffff"
        elif j == in_done:
            fill = accent
        else:
            fill = "#ffffff59"
        draw.text((cur_x, y_cur), ch, fill=fill, font=font)
        cur_x += draw.textlength(ch, font=font)


def _render_frame(
    avatar: dict, bg_hex: str, fonts: dict,
    portrait, text_lines: list,
    t: float, progress: float, width: int, height: int,
) -> Image.Image:
    """绘制一帧：动态渐变背景 + 粒子光斑 + 写真浮动 + 卡拉OK字幕。"""
    import math
    S = width / 1280.0  # 渲染缩放系数（Ken Burns 放大画布时保持坐标比例）

    # ── 1. 动态渐变背景（亮度呼吸，模拟真实灯光变化）──
    breath = 0.5 + 0.5 * math.sin(t * 0.8)
    img = _make_gradient(width, height, bg_hex, breath)
    draw = ImageDraw.Draw(img)

    # ── 2. 高斯柔光斑（缓慢漂移，营造摄影棚光效）──
    for i, (gx, gy, scale) in enumerate([
        (0.82, 0.20, 1.6), (0.12, 0.72, 1.3), (0.58, 0.92, 1.9),
    ]):
        layer = _get_glow_template(150, scale)
        cx = int(width * gx + math.sin(t * 0.3 + i * 2.1) * 40 * S)
        cy = int(height * gy + math.cos(t * 0.25 + i * 1.7) * 30 * S)
        img.paste(layer, (cx - layer.width // 2, cy - layer.height // 2), layer)

    # ── 3. 漂浮粒子（像直播间的氛围光点）──
    _draw_particles(img, t)

    # 人物浮动偏移 + 光环脉动（垂直呼吸浮动 + 水平轻微摇摆，像真人站立微动）
    float_offset = int(math.sin(t * 1.3) * 8 * S)
    sway_offset = int(math.sin(t * 0.9) * 5 * S)
    breath_scale = 1 + 0.012 * math.sin(t * 1.1)  # 呼吸缩放
    glow_alpha = max(8, min(45, int(22 + 16 * math.sin(t * 1.9))))

    # ── 4. 左侧人物：写真/emoji + 底部平台光斑 ──
    if portrait:
        p_base, p_mask_base, p_base_w, p_base_h = portrait
        # 呼吸缩放：每帧从基准写真重新缩放（轻微放大缩小，像活人呼吸）
        p_w = max(20, int(p_base_w * breath_scale * S))
        p_h = max(20, int(p_base_h * breath_scale * S))
        p_img = p_base.resize((p_w, p_h), Image.LANCZOS)
        p_mask = p_mask_base.resize((p_w, p_h), Image.BILINEAR)
        px, py = int(40 * S) + sway_offset, int(35 * S) + float_offset
        # 人物脚下平台光斑（小尺寸 RGBA 图层，像直播台灯光）
        plat_w, plat_h = int(560 * S), int(110 * S)
        plat = Image.new("RGBA", (plat_w, plat_h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(plat)
        pd.ellipse([0, 0, plat_w, plat_h], fill=(255, 255, 255, 26 + int(14 * math.sin(t * 1.2))))
        img.paste(plat, (int(60 * S), py + p_h - int(50 * S)), plat)
        # 阴影 + 写真
        shadow = Image.new("RGBA", (p_w + 20, p_h + 20), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            [10, 10, p_w + 10, p_h + 10], radius=40, fill=(0, 0, 0, 50),
        )
        img.paste(shadow, (px - 5, py - 5), shadow)
        img.paste(p_img, (px, py), p_mask)
        # 光环脉动
        glow_layer = Image.new("RGBA", (p_w + 120, p_h + 120), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.rounded_rectangle([60, 55, p_w + 60, p_h + 55], radius=48,
                             outline=(255, 255, 255, glow_alpha), width=6)
        img.paste(glow_layer, (px - 60, py - 55), glow_layer)
    else:
        # fallback：emoji 大头像（有真实人物感）
        cx = int(300 * S) + sway_offset
        cy = height // 2 + float_offset
        r = max(20, int(170 * S * breath_scale))
        # 平台光斑（小尺寸 RGBA 图层）
        plat_w, plat_h = int(460 * S), int(90 * S)
        plat = Image.new("RGBA", (plat_w, plat_h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(plat)
        pd.ellipse([0, 0, plat_w, plat_h], fill=(255, 255, 255, 26 + int(14 * math.sin(t * 1.2))))
        img.paste(plat, (int(cx - plat_w / 2), cy + r - int(20 * S)), plat)
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse(
            [cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18],
            outline=(255, 255, 255, glow_alpha), width=6,
        )
        img.paste(glow, (0, 0), glow)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#ffffff12", outline="#ffffff30", width=4)
        # 彩色 emoji 头像（位图字体渲染后放大，RGBA 图层合成保留颜色）
        emoji = avatar.get("emoji", "👩‍💼")
        emoji_font = _try_load_emoji_font(160)
        if emoji_font:
            layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            bbox = ld.textbbox((0, 0), emoji, font=emoji_font)
            ew = bbox[2] - bbox[0]
            eh = bbox[3] - bbox[1]
            target = int(r * 1.9)
            scale = target / max(ew, 1)
            if scale > 1.6:
                small = Image.new("RGBA", (ew + 40, eh + 40), (0, 0, 0, 0))
                sd = ImageDraw.Draw(small)
                sd.text((20 - bbox[0], 20 - bbox[1]), emoji, font=emoji_font, embedded_color=True)
                big = small.resize((int((ew + 40) * scale), int((eh + 40) * scale)), Image.LANCZOS)
                layer.paste(big, (int(cx - big.width / 2), int(cy - big.height / 2)), big)
            else:
                ld.text((cx - ew / 2 - bbox[0], cy - eh / 2 - bbox[1]), emoji, font=emoji_font, embedded_color=True)
            img.paste(layer, (0, 0), layer)
        else:
            name_text = avatar.get("name", "AI数字人")
            bbox = draw.textbbox((0, 0), name_text, font=fonts["title"])
            tw = bbox[2] - bbox[0]
            draw.text((cx - tw // 2, cy - 18), name_text, fill="#ffffff88", font=fonts["title"])
        style_text = avatar.get("style", "")
        if style_text:
            bbox = draw.textbbox((0, 0), style_text, font=fonts["body"])
            sw = bbox[2] - bbox[0]
            draw.text((cx - sw // 2, cy + r + 22), style_text, fill="#ffffff55", font=fonts["body"])

    # ── 5. 右侧：人物名片 + 卡拉OK逐字字幕 ──
    right_x = int(600 * S)
    right_w = int((1280 - 600 - 50) * S)

    name_text = avatar.get("name", "AI数字人")
    draw.text((right_x, int(60 * S)), name_text, fill="#ffffff", font=fonts["title"])

    style_text = avatar.get("style", "")
    if style_text:
        tag_w = draw.textbbox((0, 0), style_text, font=fonts["tag"])[2] + 20
        draw.rounded_rectangle(
            [right_x, int(108 * S), right_x + tag_w, int(134 * S)], radius=12,
            fill="#ffffff20", outline="#ffffff30", width=1,
        )
        draw.text((right_x + 10, int(110 * S)), style_text, fill="#ffffffcc", font=fonts["tag"])

    draw.line([right_x, int(155 * S), right_x + right_w, int(155 * S)], fill="#ffffff15", width=1)

    accent = _accent_color(bg_hex)
    _draw_karaoke(
        draw, text_lines, progress, fonts["body"],
        right_x, int(175 * S), int(32 * S), accent,
    )
    if len(text_lines) > 12:
        draw.text(
            (right_x, int(175 * S) + 12 * int(32 * S)),
            f"...共{sum(len(ln) for ln in text_lines)}字", fill="#ffffff55", font=fonts["tag"],
        )

    # ── 6. 底部：品牌信息 + 主题色进度条 ──
    bar_h = int(64 * S)
    draw.rectangle([0, height - bar_h, width, height], fill="#00000055")
    brand = "AI 数字人 · 智能口播视频"
    draw.text((int(30 * S), height - int(48 * S)), brand, fill="#ffffff88", font=fonts["tag"])
    voice_hint = avatar.get("desc", "")[:25]
    if voice_hint:
        bbox = draw.textbbox((0, 0), voice_hint, font=fonts["tag"])
        dw = bbox[2] - bbox[0]
        draw.text((width - dw - int(30 * S), height - int(48 * S)), voice_hint, fill="#ffffff55", font=fonts["tag"])

    bar_y = height - int(14 * S)
    bar_w = width - int(60 * S)
    draw.rounded_rectangle(
        [int(30 * S), bar_y, int(30 * S) + bar_w, bar_y + int(6 * S)],
        radius=3, fill="#ffffff20",
    )
    fill_w = int(bar_w * progress)
    if fill_w > 4:
        draw.rounded_rectangle(
            [int(30 * S), bar_y, int(30 * S) + fill_w, bar_y + int(6 * S)],
            radius=3, fill=accent,
        )

    return img


def _render_video(text: str, avatar: dict, bg: dict, audio_path: str, output_path: str) -> None:
    """真实视频感多帧渲染：动态背景粒子 + 卡拉OK逐字字幕 + 镜头缓慢推近。

    相比静态图循环，加入全套时序动画呈现"直播/口播视频"观感：
    - 背景：对角渐变亮度呼吸 + 高斯柔光斑漂移 + 漂浮粒子光点
    - 人物：写真浮动呼吸 + 光环脉动 + 脚下平台光斑（直播台感）
    - 字幕：卡拉OK逐字显示，当前字主题色高亮，当前行带字幕底条
    - 镜头：整体缓慢推近（Ken Burns），开头 0.4s 淡入、结尾 0.4s 淡出
    """
    import shutil

    OUT_W, OUT_H = 1280, 720
    # 渲染画布放大 1.05x，按进度裁剪窗口实现镜头推近（避免边缘露出）
    RENDER_W, RENDER_H = int(OUT_W * 1.05), int(OUT_H * 1.05)
    bg_hex = bg.get("color", "#1a1a2e")
    if bg_hex.startswith("linear-gradient"):
        import re
        m = re.search(r"#[0-9a-fA-F]{6}", bg_hex)
        bg_hex = m.group(0) if m else "#667eea"

    # 字体
    FONT_CANDIDATES = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/ArialHB.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    fonts = {
        "title": _load_font(36, FONT_CANDIDATES),
        "name": _load_font(28, FONT_CANDIDATES),
        "body": _load_font(20, FONT_CANDIDATES),
        "tag": _load_font(18, FONT_CANDIDATES),
    }

    # 音频时长 → 帧率/帧数（动态效果更丰富，帧率相应提高）
    duration = _audio_duration(audio_path)
    if duration <= 0:
        # 空文件/损坏音频：ffprobe 读不出时长，ffmpeg 合成必然失败，提前拦截给出清晰错误
        raise RuntimeError("配音音频无效或为空，请重新生成")
    fps = 12 if duration <= 30 else (10 if duration <= 60 else 8)
    total_frames = max(int(duration * fps), 6)

    # 写真预加载（避免每帧重复 IO/缩放）
    portrait = _build_portrait_src(avatar)

    # 文案换行（复用一帧的测量）
    probe = Image.new("RGB", (10, 10), "#000")
    probe_draw = ImageDraw.Draw(probe)
    right_w = int((1280 - 600 - 50) * 1.05)
    text_lines = _wrap_text_lines(text, probe_draw, fonts["body"], right_w)

    frames_dir = tempfile.mkdtemp(prefix="dh_frames_")
    try:
        for f in range(total_frames):
            t = f / fps
            progress = min(1.0, t / duration) if duration > 0 else 1.0
            frame = _render_frame(
                avatar=avatar, bg_hex=bg_hex, fonts=fonts,
                portrait=portrait, text_lines=text_lines,
                t=t, progress=progress, width=RENDER_W, height=RENDER_H,
            )
            # 镜头缓慢推近：裁剪窗口随进度缩小，再缩放回输出尺寸
            zoom = 0.035 * progress
            win_w = int(RENDER_W / (1 + zoom))
            win_h = int(RENDER_H / (1 + zoom))
            x0 = (RENDER_W - win_w) // 2
            y0 = (RENDER_H - win_h) // 2
            frame = frame.crop((x0, y0, x0 + win_w, y0 + win_h)).resize(
                (OUT_W, OUT_H), Image.LANCZOS,
            )
            # 开头淡入 / 结尾淡出
            fade = 1.0
            if t < 0.4:
                fade = t / 0.4
            elif t > duration - 0.4:
                fade = max(0.0, (duration - t) / 0.4)
            if fade < 1.0:
                black = Image.new("RGB", (OUT_W, OUT_H), (0, 0, 0))
                frame = Image.blend(black, frame, fade)
            # JPG 帧序列（quality=95 视觉无损，比 PNG 快 10 倍+）
            frame.save(os.path.join(frames_dir, f"{f:04d}.jpg"), quality=95)

        # ffmpeg：帧序列 + 音频 → MP4
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", os.path.join(frames_dir, "%04d.jpg"),
                    "-i", audio_path,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k",
                    "-shortest", "-movflags", "+faststart",
                    output_path,
                ],
                check=True, capture_output=True, timeout=900,
            )
        except subprocess.CalledProcessError as e:
            # 把 ffmpeg stderr 带进错误信息，否则用户只能看到 exit code，无法诊断
            detail = e.stderr.decode(errors="replace")[-500:].strip() if e.stderr else "未知错误"
            raise RuntimeError(f"视频编码失败（ffmpeg exit {e.returncode}）：{detail}") from e
        logger.info(f"动态视频生成成功：{output_path} ({total_frames}帧 @{fps}fps, {duration:.1f}s)")
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


# ── 数据库 ──────────────────────────────────────────────────
def _ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS digital_human_records (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            avatar_id TEXT DEFAULT '',
            avatar_name TEXT DEFAULT '',
            voice_id TEXT DEFAULT '',
            voice_name TEXT DEFAULT '',
            background_id TEXT DEFAULT '',
            scene_id TEXT DEFAULT '',
            text TEXT DEFAULT '',
            text_length INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            audio_url TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            error TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


# ── 请求模型 ──────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=5000, description="口播文案")
    avatar_id: str = Field("business-female", description="数字人形象ID")
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="声音ID")
    background_id: str = Field("tech", description="背景ID")
    scene_id: str = Field("product", description="场景模板ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")


# ── API ──────────────────────────────────────────────────────

@router.get("/avatars")
async def list_avatars():
    """内置12个数字人形象库（含性感女神/甜美女神/高冷御姐/风韵熟女等）。"""
    result = []
    for a in AVATARS:
        portrait_path = _get_portrait_path(a["id"])
        a_copy = dict(a)
        a_copy["has_portrait"] = os.path.exists(portrait_path)
        a_copy["portrait_url"] = _get_portrait_url(a["id"]) if a_copy["has_portrait"] else None
        result.append(a_copy)
    return {"avatars": result}


@router.get("/voices")
async def list_voices():
    """可选声音列表（复用配音工坊 Azure Neural 音色表）。"""
    return {"voices": VOICES}


@router.get("/backgrounds")
async def list_backgrounds():
    """虚拟背景模板。"""
    return {"backgrounds": BACKGROUNDS}


@router.get("/scenes")
async def list_scenes():
    """场景预设模板（产品介绍/课程讲解/新闻播报/直播带货/故事讲述）。"""
    return {"scenes": SCENE_TEMPLATES}


# ── 写真肖像 API ────────────────────────────────────────────

@router.get("/portraits")
async def list_portraits():
    """列出所有已缓存的数字人写真肖像。"""
    portraits = []
    for avatar in AVATARS:
        portrait_path = _get_portrait_path(avatar["id"])
        exists = os.path.exists(portrait_path)
        portraits.append({
            "avatar_id": avatar["id"],
            "avatar_name": avatar["name"],
            "avatar_emoji": avatar["emoji"],
            "exists": exists,
            "url": _get_portrait_url(avatar["id"]) if exists else None,
        })
    return {"portraits": portraits, "total": len(portraits), "cached": sum(1 for p in portraits if p["exists"])}


@router.post("/generate-portrait/{avatar_id}")
async def generate_portrait(avatar_id: str, current_user: dict = require_auth()):
    """为指定数字人形象生成 AI 写真肖像（如已存在则跳过）。

    返回写真图片的访问 URL。
    """
    avatar = next((a for a in AVATARS if a["id"] == avatar_id), None)
    if not avatar:
        raise HTTPException(404, f"未知数字人形象: {avatar_id}")

    portrait_path = _get_portrait_path(avatar_id)
    if os.path.exists(portrait_path):
        return {
            "avatar_id": avatar_id,
            "avatar_name": avatar["name"],
            "url": _get_portrait_url(avatar_id),
            "cached": True,
            "message": f"{avatar['name']} 写真已存在，直接使用缓存",
        }

    result = _generate_portrait(avatar_id)
    if result:
        return {
            "avatar_id": avatar_id,
            "avatar_name": avatar["name"],
            "url": _get_portrait_url(avatar_id),
            "cached": False,
            "message": f"{avatar['name']} 写真已生成",
        }
    else:
        raise HTTPException(500, "写真生成失败，请检查 API Key 配置或稍后重试")


@router.post("/generate-all-portraits")
async def generate_all_portraits(current_user: dict = require_auth()):
    """批量为所有数字人形象生成写真肖像（已有缓存的跳过）。"""
    results = []
    for avatar in AVATARS:
        portrait_path = _get_portrait_path(avatar["id"])
        if os.path.exists(portrait_path):
            results.append({
                "avatar_id": avatar["id"],
                "avatar_name": avatar["name"],
                "success": True,
                "cached": True,
            })
            continue
        path = _generate_portrait(avatar["id"])
        results.append({
            "avatar_id": avatar["id"],
            "avatar_name": avatar["name"],
            "success": path is not None,
            "cached": False,
        })
    return {
        "results": results,
        "total": len(results),
        "generated": sum(1 for r in results if r["success"] and not r["cached"]),
        "cached": sum(1 for r in results if r["cached"]),
        "failed": sum(1 for r in results if not r["success"]),
    }


@router.post("/generate")
async def generate(req: GenerateRequest, current_user: dict = require_auth()):
    """数字人口播视频生成 — 文案→配音→视频合成流水线。

    流程：
    1. 文案预处理（LLM优化口播文案流畅度）
    2. TTS配音（调用配音工坊音频生成）
    3. 视频合成（数字人形象+配音+背景合成为口播视频）
    """
    start = datetime.now()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    # 验证形象/声音/背景/场景
    avatar = next((a for a in AVATARS if a["id"] == req.avatar_id), None)
    if not avatar:
        raise HTTPException(400, f"未知数字人形象: {req.avatar_id}")
    voice = next((v for v in VOICES if v["id"] == req.voice_id), None)
    if not voice:
        raise HTTPException(400, f"未知声音: {req.voice_id}")
    bg = next((b for b in BACKGROUNDS if b["id"] == req.background_id), None)
    if not bg:
        raise HTTPException(400, f"未知背景: {req.background_id}")

    record_id = f"dh_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    _ensure_tables(conn)

    # 1. 文案优化（LLM让口播更流畅自然）
    optimized_text = req.text
    try:
        SCRIPT_SYSTEM = (
            f"你是专业口播脚本优化师。将以下文案优化为适合{avatar['style']}风格的数字人口播脚本。"
            "要求：口语化、自然流畅、保留原意、适合听觉（非阅读）、每句不超过25字。直接输出优化后文案，不要任何说明。"
        )
        optimized_text = call_llm(SCRIPT_SYSTEM, req.text, max_tokens=1000, temperature=0.5, timeout=30)
    except Exception as e:
        logger.warning("script optimization failed, using original: %s", e)

    # 2. TTS 配音 — 保存到 uploads/audio/
    audio_url = ""
    audio_error = ""
    audio_path = ""
    try:
        from voice_factory import _tts_one
        audio_bytes = _tts_one(optimized_text, req.voice_id, req.speed)
        if not audio_bytes:
            raise RuntimeError("TTS 返回空音频")
        audio_filename = f"{record_id}.mp3"
        audio_path = os.path.join(UPLOAD_AUDIO_DIR, audio_filename)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        # 极小/空文件视为生成失败：避免前端误显"音频已生成"、下游 ffmpeg 报错
        if os.path.getsize(audio_path) < 512:
            os.remove(audio_path)
            audio_path = ""
            raise RuntimeError("TTS 生成的音频无效（文件过小）")
        audio_url = f"/uploads/audio/{audio_filename}"
    except Exception as e:
        logger.exception("TTS failed for digital human %s", record_id)
        audio_error = str(e)

    # 3. 视频合成 — ffmpeg 将背景图+音频合成为 MP4
    video_url = ""
    status = "done"
    error_msg = ""
    if audio_path and os.path.exists(audio_path):
        try:
            video_filename = f"{record_id}.mp4"
            video_path = os.path.join(UPLOAD_VIDEO_DIR, video_filename)
            _render_video(
                text=optimized_text[:200],
                avatar=avatar,
                bg=bg,
                audio_path=audio_path,
                output_path=video_path,
            )
            video_url = f"/uploads/videos/{video_filename}"
        except Exception as e:
            logger.exception("video generation failed %s", record_id)
            status = "audio_only"
            error_msg = f"视频合成失败（{e}），已生成配音音频"
    else:
        status = "audio_only"
        error_msg = audio_error or "配音生成失败"

    # 4. 保存记录
    conn.execute(
        """INSERT INTO digital_human_records
           (id, user_id, avatar_id, avatar_name, voice_id, voice_name,
            background_id, scene_id, text, text_length, status,
            audio_url, video_url, error, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (record_id, user, req.avatar_id, avatar["name"], req.voice_id, voice["name"],
         req.background_id, req.scene_id, optimized_text, len(optimized_text),
         status, audio_url, video_url, error_msg, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("digital_human", len(req.text), len(optimized_text), elapsed,
              success=not error_msg)

    return {
        "record_id": record_id,
        "status": status,
        "avatar": {"id": avatar["id"], "name": avatar["name"], "emoji": avatar["emoji"]},
        "voice": {"id": voice["id"], "name": voice["name"]},
        "background": {"id": bg["id"], "name": bg["name"]},
        "text_length": len(optimized_text),
        "audio_url": audio_url,
        "video_url": video_url,
        "error": error_msg,
        "message": (
            f"口播视频已生成！{avatar['name']} + {voice['name']}，可下载 MP4 视频和 MP3 音频"
            if status == "done"
            else "配音音频已生成，视频合成失败（可预览音频+形象）"
            if status == "audio_only"
            else "生成失败"
        ),
    }


@router.get("/records")
async def list_records(limit: int = 50, current_user: dict = require_auth()):
    """历史数字人视频生成记录。"""
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM digital_human_records ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM digital_human_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return {"success": True}
