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
import threading
import time
import uuid
import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db, get_db_context
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_AUDIO_DIR = os.path.join(_BASE_DIR, "uploads", "audio")
UPLOAD_VIDEO_DIR = os.path.join(_BASE_DIR, "uploads", "videos")
PORTRAIT_DIR = os.path.join(_BASE_DIR, "image_factory", "avatars")
# 自定义形象/声音（用户上传）：与 uploads 静态目录同根，URL 可直接访问
UPLOAD_DH_AVATAR_DIR = os.path.join(_BASE_DIR, "uploads", "dh_avatars")
UPLOAD_DH_VOICE_DIR = os.path.join(_BASE_DIR, "uploads", "dh_voices")
os.makedirs(UPLOAD_AUDIO_DIR, exist_ok=True)
os.makedirs(UPLOAD_VIDEO_DIR, exist_ok=True)
os.makedirs(PORTRAIT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DH_AVATAR_DIR, exist_ok=True)
os.makedirs(UPLOAD_DH_VOICE_DIR, exist_ok=True)

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
def _font_has_cjk(font) -> bool:
    """豆腐块检测：字体缺中文字形时，渲染“好”为空白或矩形边框（tofu []），
    真汉字笔画不规则、不会四边满格。用于选择能正确显示中文的字体。"""
    try:
        import numpy as np
        img = Image.new("L", (80, 80), 255)
        d = ImageDraw.Draw(img)
        d.text((20, 20), "好", fill=0, font=font)
        arr = np.array(img)
        ys, xs = np.where(arr < 128)
        if len(ys) < 30:
            return False  # 空白 = 无字形
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        region = arr[y0:y1 + 1, x0:x1 + 1]
        border = np.concatenate([region[0, :], region[-1, :], region[:, 0], region[:, -1]])
        return (border < 128).mean() <= 0.75  # 豆腐块四边几乎全暗
    except Exception:
        return False


def _load_font(size: int, candidates: list[str]) -> ImageFont.FreeTypeFont:
    """加载支持中文字形的字体；全部失败回退 load_default。

    必须验证中文字形可用：PingFang.ttc 在部分 macOS 上无法加载（cannot open
    resource），Helvetica/Arial 等西文字体渲染中文全是豆腐块（[] 方框），
    缺字校验不通过就继续尝试下一个候选。
    """
    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            if _font_has_cjk(font):
                return font
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
    """预加载并缩放写真 → (RGBA图, 圆角遮罩, 宽, 高)；无写真返回 None。

    自定义形象使用用户上传图片（local_image_path），内置形象用 AI 写真缓存。
    """
    portrait_path = avatar.get("local_image_path") or (_get_portrait_path(avatar["id"]) if not avatar.get("is_custom") else "")
    if not portrait_path or not os.path.exists(portrait_path):
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


def _clean_script_text(text: str) -> str:
    """清洗口播文案：去首尾空白、连续空行折叠为单空行（保留分段结构）。

    字幕与配音必须与用户输入一致，仅做渲染友好的空白规范化。
    """
    import re
    # 连续空行折叠为单空行（\n\n），保留分段结构；单换行保留原样
    return re.sub(r"\n{2,}", "\n\n", text or "").strip()


def _audio_energy_curve(path: str, duration: float, fps: float) -> list:
    """解码音频 → 按帧粒度 RMS 能量曲线（0~1，95 分位归一化）。

    用于驱动人物身体律动（能量高=正在说话），嘴型已升级为字级驱动。
    解码失败返回空列表（调用方回退静态呼吸）。
    """
    try:
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            capture_output=True, timeout=30,
        )
        import numpy as np
        raw = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        hop = max(int(16000 / fps), 1)
        curve = []
        for i in range(0, max(len(raw) - hop, 1), hop):
            seg = raw[i:i + hop]
            curve.append(float(np.sqrt(np.mean(seg ** 2))) if len(seg) else 0.0)
        if not curve:
            return []
        mx = max(float(np.percentile(curve, 95)), 1e-4)
        return [min(v / mx, 1.0) for v in curve]
    except Exception:
        return []


# 口型形状表：拼音韵母首音 → (开度 0~1, 圆度 0~1)
# a 大口 / o 圆嘴 / e 半开 / i 扁嘴 / u 嘟嘴 / v(ü) 扁圆 / n 闭口（声母/鼻韵）
_MOUTH_SHAPES = {
    "a": (1.0, 0.5),
    "o": (0.75, 0.95),
    "e": (0.55, 0.65),
    "i": (0.45, 0.25),
    "u": (0.55, 1.0),
    "v": (0.6, 0.8),
    "n": (0.2, 0.4),
}


def _build_script_timeline(text: str, duration: float) -> list:
    """文本 → 逐字口型时间轴 [(char, start, end, open, round)]。

    均匀时间对齐：汉字每字 1 单位时长、标点/空白 0.5 单位（闭嘴停顿），
    按总时长等比例分配。每字口型由拼音韵母首音分类（a大口/o圆嘴/e半开/
    i扁嘴/u嘟嘴），让嘴型动作真正对上朗读的每个字。
    """
    import re
    from pypinyin import Style, pinyin

    hanzi = re.compile(r"[\u4e00-\u9fff]")
    units = []
    for ch in text:
        if hanzi.match(ch):
            units.append((ch, 1.0))
        else:
            units.append((ch, 0.5))  # 标点/空白：短停顿
    total = sum(u[1] for u in units) or 1.0
    unit_dur = duration / total
    timeline = []
    cur = 0.0
    for ch, w in units:
        start, end = cur, cur + w * unit_dur
        if hanzi.match(ch):
            try:
                final = pinyin(ch, style=Style.FINALS, errors="default", heteronym=False)[0][0]
            except Exception:
                final = ""
            key = final[0] if final else "n"
            open_, round_ = _MOUTH_SHAPES.get(key, _MOUTH_SHAPES["e"])
        else:
            open_, round_ = 0.0, 0.5  # 标点：闭嘴停顿
        timeline.append((ch, start, end, open_, round_))
        cur = end
    return timeline


def _mouth_shape_at(timeline: list, t: float) -> tuple:
    """当前时刻的字级口型 → (open 0~1, round 0~1)。

    字周期内包络：前 15% 张嘴、中间 70% 维持口型、后 15% 收拢，
    形成自然说话感（每个字一次完整的开合）。
    """
    for ch, start, end, open_, round_ in timeline:
        if start <= t < end:
            if open_ <= 0.01:
                return (0.0, 0.5)
            prog = (t - start) / max(end - start, 1e-4)
            if prog < 0.15:
                env = prog / 0.15
            elif prog > 0.85:
                env = (1 - prog) / 0.15
            else:
                env = 1.0
            return (open_ * env, round_)
    return (0.0, 0.5)


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
    energy: float = 0.0, mouth_shape: tuple = (0.0, 0.5),
) -> Image.Image:
    """绘制一帧：动态渐变背景 + 粒子光斑 + 人物动态（说话律动/眨眼/字级口型）+ 卡拉OK字幕。"""
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

    # 说话能量 → 驱动全身律动（能量高=说话中：幅度加大；静音：回归静态呼吸）
    talk = min(1.0, energy * 1.6)
    sway_t = math.sin(t * 1.15)
    breathe_t = math.sin(t * 1.3)
    glow_alpha = max(8, min(45, int(22 + 16 * math.sin(t * 1.9))))
    # 入场动画：前 0.8s 人物从左侧滑入（ease-out，开局明显动起来）
    enter_ease = 1 - (1 - min(1.0, t / 0.8)) ** 3

    # ── 4. 左侧人物：写真 + 动态（入场滑入/呼吸缩放/点头倾斜/眨眼/嘴型开合）──
    if portrait:
        p_base, p_mask_base, p_base_w, p_base_h = portrait
        # 呼吸缩放（幅度加大）+ 说话节奏起伏（能量驱动）
        breath_scale = 1 + 0.03 * breathe_t + 0.022 * talk * math.sin(t * 3.2)
        p_w = max(20, int(p_base_w * breath_scale * S))
        p_h = max(20, int(p_base_h * breath_scale * S))
        # 点头倾斜：绕底部中心旋转（像真人说话时身体前倾点头），幅度随能量加大
        tilt = sway_t * (1.0 + 2.4 * talk) + 1.2 * talk * math.sin(t * 2.6)
        nod_pivot = (int(p_w / 2), p_h)  # 底部中心为旋转轴
        p_img = p_base.resize((p_w, p_h), Image.LANCZOS).rotate(
            tilt, resample=Image.BILINEAR, center=nod_pivot)
        p_mask = p_mask_base.resize((p_w, p_h), Image.BILINEAR).rotate(
            tilt, resample=Image.BILINEAR, center=nod_pivot)
        # 垂直浮动 + 水平摇摆（幅度加大，说话时叠加高频起伏）
        float_offset = int((breathe_t * 11 + talk * 8 * math.sin(t * 2.8)) * S)
        sway_offset = int((sway_t * 9 + talk * 7 * math.cos(t * 2.2)) * S)
        # 入场滑入：x 从画面外（-p_w）滑到目标位
        enter_shift = int((1 - enter_ease) * (p_w + int(80 * S)))
        px = int(40 * S) + sway_offset - enter_shift
        py = int(35 * S) + float_offset
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

        # 眨眼：每 ~2.8s 闭眼一次（0.16s 内渐进闭上再睁开），闭眼线条更明显
        blink_t = t % 2.8
        if blink_t < 0.16:
            close = blink_t / 0.16  # 0→1 渐进闭眼
            eye_y = py + int(p_h * 0.335)
            eye_alpha = int(160 * close) + 80
            for ex in (px + int(p_w * 0.30), px + int(p_w * 0.58)):
                ew = int(p_w * 0.13)
                # 闭眼：在眼位画一条深色闭合线（宽度随闭眼进度变窄）
                eh = max(2, int(p_h * 0.008 * (2.2 - close)))
                draw.rounded_rectangle(
                    [ex, eye_y - eh // 2, ex + ew, eye_y + eh // 2],
                    radius=2, fill=(40, 26, 32, min(eye_alpha, 220)),
                )

        # 字级口型：open 控制开度、round 控制圆度（a 大口 / o 圆嘴 / i 扁嘴 / u 嘟嘴），
        # 由拼音时间轴驱动，嘴型动作与朗读文字逐字对齐；自定义形象按长宽比启发式启用
        mouth_open_v, roundness = mouth_shape
        aspect = p_base_w / p_base_h
        if (not avatar.get("is_custom") or 0.55 <= aspect <= 1.05) and mouth_open_v > 0.05:
            mw = max(4, int(p_w * (0.20 + 0.08 * roundness)))
            mh = max(2, int(p_h * 0.032 * mouth_open_v * (0.6 + 0.8 * roundness)))
            mx = px + int(p_w * 0.49)
            my = py + int(p_h * 0.805)
            mouth_layer = Image.new("RGBA", (mw + 10, mh + 14), (0, 0, 0, 0))
            md = ImageDraw.Draw(mouth_layer)
            # 上唇线固定 + 口型椭圆（圆度高的字更圆，扁音更扁长）
            md.rounded_rectangle([0, 0, mw, 4], radius=2, fill=(60, 32, 42, 215))
            md.ellipse([1, 5, mw - 1, 5 + mh], fill=(55, 30, 40, 200))
            img.paste(mouth_layer, (mx - mw // 2 - 5, my - 6), mouth_layer)

        # 光环脉动
        glow_layer = Image.new("RGBA", (p_w + 120, p_h + 120), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow_layer)
        gd.rounded_rectangle([60, 55, p_w + 60, p_h + 55], radius=48,
                             outline=(255, 255, 255, glow_alpha), width=6)
        img.paste(glow_layer, (px - 60, py - 55), glow_layer)
    else:
        # fallback：emoji 大头像（有真实人物感）
        float_offset = int(math.sin(t * 1.3) * 8 * S)
        sway_offset = int(math.sin(t * 0.9) * 5 * S)
        breath_scale = 1 + 0.012 * math.sin(t * 1.1)  # 呼吸缩放
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


def _render_video(text: str, avatar: dict, bg: dict, audio_path: str, output_path: str,
                  resolution: str = "720p", fps: int = 15, watermark: bool = False) -> None:
    """真实视频感多帧渲染：动态背景粒子 + 卡拉OK逐字字幕 + 镜头缓慢推近。

    相比静态图循环，加入全套时序动画呈现"直播/口播视频"观感：
    - 背景：对角渐变亮度呼吸 + 高斯柔光斑漂移 + 漂浮粒子光点
    - 人物：写真浮动呼吸 + 光环脉动 + 脚下平台光斑（直播台感）
    - 字幕：卡拉OK逐字显示，当前字主题色高亮，当前行带字幕底条
    - 镜头：整体缓慢推近（Ken Burns），开头 0.4s 淡入、结尾 0.4s 淡出
    - 商业水印：watermark=True 时右下角叠加平台半透明水印
    """
    import math
    import shutil

    OUT_W, OUT_H = (1920, 1080) if resolution == "1080p" else (1280, 720)
    # 渲染画布放大 1.10x：按进度裁剪窗口实现镜头推近 + 平移/呼吸（避免边缘露出）
    RENDER_W, RENDER_H = int(OUT_W * 1.10), int(OUT_H * 1.10)
    bg_hex = bg.get("color", "#1a1a2e")
    if bg_hex.startswith("linear-gradient"):
        import re
        m = re.search(r"#[0-9a-fA-F]{6}", bg_hex)
        bg_hex = m.group(0) if m else "#667eea"

    # 字体（优先中文 GB 字体：PingFang.ttc 在部分 macOS 无法加载，
    # Helvetica 等西文字体渲染中文为豆腐块，故候选按中文字形可用性排序）
    FONT_CANDIDATES = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",       # 中文黑体（简体全覆盖）
        "/System/Library/Fonts/STHeiti Light.ttc",          # 黑体-简
        "/System/Library/Fonts/Supplemental/Songti.ttc",    # 宋体
        "/System/Library/Fonts/PingFang.ttc",               # 部分 macOS 可加载
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux 容器
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",   # Linux 容器
        "/System/Library/Fonts/Helvetica.ttc",              # 英文兜底
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

    # 音频时长 → 帧数（分辨率/帧率由 API 参数控制）
    duration = _audio_duration(audio_path)
    if duration <= 0:
        # 空文件/损坏音频：ffprobe 读不出时长，ffmpeg 合成必然失败，提前拦截给出清晰错误
        raise RuntimeError("配音音频无效或为空，请重新生成")
    total_frames = max(int(duration * fps), 6)

    # 写真预加载（避免每帧重复 IO/缩放）
    portrait = _build_portrait_src(avatar)

    # 音频能量曲线（按帧粒度，驱动身体律动；解码失败则回退静态呼吸）
    energy_curve = _audio_energy_curve(audio_path, duration, fps)
    # 字级口型时间轴（拼音韵母分类，嘴型逐字对齐配音文字）
    script_timeline = _build_script_timeline(text, duration)

    # 文案换行（复用一帧的测量）
    probe = Image.new("RGB", (10, 10), "#000")
    probe_draw = ImageDraw.Draw(probe)
    right_w = int((OUT_W - 600 - 50) * 1.10)
    text_lines = _wrap_text_lines(text, probe_draw, fonts["body"], right_w)

    frames_dir = tempfile.mkdtemp(prefix="dh_frames_")
    try:
        for f in range(total_frames):
            t = f / fps
            progress = min(1.0, t / duration) if duration > 0 else 1.0
            energy = energy_curve[min(f, len(energy_curve) - 1)] if energy_curve else 0.0
            mouth_shape = _mouth_shape_at(script_timeline, t)
            frame = _render_frame(
                avatar=avatar, bg_hex=bg_hex, fonts=fonts,
                portrait=portrait, text_lines=text_lines,
                t=t, progress=progress, width=RENDER_W, height=RENDER_H,
                energy=energy, mouth_shape=mouth_shape,
            )
            # 镜头运动：Ken Burns 推近 + 缓慢平移 + 呼吸缩放（避免画面静止感）
            zoom = 0.05 * progress + 0.012 * math.sin(t * 0.25)
            win_w = int(RENDER_W / (1 + zoom))
            win_h = int(RENDER_H / (1 + zoom))
            pan_x = int(0.012 * RENDER_W * math.sin(t * 0.18))
            pan_y = int(0.008 * RENDER_H * math.sin(t * 0.13 + 1.0))
            x0 = (RENDER_W - win_w) // 2 + pan_x
            y0 = (RENDER_H - win_h) // 2 + pan_y
            # 越界保护：裁剪窗口不允许超出画布
            x0 = max(0, min(x0, RENDER_W - win_w))
            y0 = max(0, min(y0, RENDER_H - win_h))
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
            # 商业水印：右下角半透明（不随淡入淡出消失，全程可见）
            if watermark:
                wm_font = _load_font(int(18 * OUT_W / 1280), FONT_CANDIDATES)
                wm_text = WATERMARK_TEXT
                wm_w = wm_font.getbbox(wm_text)[2]
                wm_layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
                wm_draw = ImageDraw.Draw(wm_layer)
                wm_x, wm_y = OUT_W - wm_w - int(24 * OUT_W / 1280), OUT_H - int(34 * OUT_H / 720)
                # 深色描边提高任意背景下的可读性
                wm_draw.text((wm_x - 1, wm_y - 1), wm_text, font=wm_font, fill=(0, 0, 0, 120))
                wm_draw.text((wm_x + 1, wm_y + 1), wm_text, font=wm_font, fill=(0, 0, 0, 120))
                wm_draw.text((wm_x, wm_y), wm_text, font=wm_font, fill=(255, 255, 255, 170))
                frame.paste(wm_layer, (0, 0), wm_layer)
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
            resolution TEXT DEFAULT '720p',
            fps INTEGER DEFAULT 15,
            watermark INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        )"""
    )
    # 兼容旧库：补列
    for col, ddl in [
        ("resolution", "TEXT DEFAULT '720p'"),
        ("fps", "INTEGER DEFAULT 15"),
        ("watermark", "INTEGER DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE digital_human_records ADD COLUMN {col} {ddl}")
        except Exception:
            pass  # 已存在
    # 批量生产任务（持久化：重启可恢复/查询/重试）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS digital_human_batches (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            status TEXT DEFAULT 'running',   -- running/done/interrupted
            total INTEGER DEFAULT 0,
            success INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            skipped INTEGER DEFAULT 0,
            avatar_id TEXT DEFAULT '',
            avatar_name TEXT DEFAULT '',
            resolution TEXT DEFAULT '720p',
            fps INTEGER DEFAULT 15,
            voice_id TEXT DEFAULT '',
            background_id TEXT DEFAULT '',
            speed REAL DEFAULT 1.0,
            created_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT ''
        )"""
    )
    # 兼容旧库：补列
    for col, ddl in [
        ("voice_id", "TEXT DEFAULT ''"),
        ("background_id", "TEXT DEFAULT ''"),
        ("speed", "REAL DEFAULT 1.0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE digital_human_batches ADD COLUMN {col} {ddl}")
        except Exception:
            pass  # 已存在
    conn.execute(
        """CREATE TABLE IF NOT EXISTS digital_human_batch_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT DEFAULT '',
            idx INTEGER DEFAULT 0,
            text TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',   -- pending/running/success/failed/skipped
            error TEXT DEFAULT '',
            record_id TEXT DEFAULT '',
            audio_url TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            watermark INTEGER DEFAULT 0,
            sensitive_warning TEXT DEFAULT ''
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_items_batch ON digital_human_batch_items(batch_id)")
    # 用户自定义形象（上传头像图片）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS digital_human_custom_avatars (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            style TEXT DEFAULT '自定义形象',
            gender TEXT DEFAULT '自定义',
            desc TEXT DEFAULT '',
            emoji TEXT DEFAULT '🖼️',
            image_url TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    # 用户自定义声音（上传音频样本，生成时直接作为配音）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS digital_human_custom_voices (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            desc TEXT DEFAULT '',
            emoji TEXT DEFAULT '🎙️',
            audio_url TEXT DEFAULT '',
            duration REAL DEFAULT 0,
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


# ── 自定义形象 / 声音（用户上传）──────────────────────────────
def _load_custom_avatars(user_id: str = "") -> dict:
    """按用户加载自定义形象 → {id: avatar_dict}；avatar_dict 含本地图片路径映射。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM digital_human_custom_avatars WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    out = {}
    for r in rows:
        d = dict(r)
        d["is_custom"] = True
        # /uploads/dh_avatars/xxx.jpg → 本地绝对路径（渲染引擎用）
        url = d.get("image_url") or ""
        d["local_image_path"] = os.path.join(_BASE_DIR, *url.lstrip("/").split("/")) if url.startswith("/uploads/") else ""
        out[d["id"]] = d
    return out


def _load_custom_voices(user_id: str = "") -> dict:
    """按用户加载自定义声音 → {id: voice_dict}；含本地音频路径映射。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM digital_human_custom_voices WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    out = {}
    for r in rows:
        d = dict(r)
        d["is_custom"] = True
        url = d.get("audio_url") or ""
        d["local_audio_path"] = os.path.join(_BASE_DIR, *url.lstrip("/").split("/")) if url.startswith("/uploads/") else ""
        out[d["id"]] = d
    return out


_ALLOWED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
_ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


@router.post("/custom-avatars")
async def upload_custom_avatar(
    file: UploadFile = File(...),
    name: str = Form("我的形象"),
    desc: str = Form(""),
    current_user: dict = require_auth(),
):
    """上传自定义数字人形象（头像图片）→ 保存到 uploads/dh_avatars/ 并入表。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_IMG_EXT:
        raise HTTPException(400, f"不支持的图片格式: {ext or '未知'}（支持 jpg/png/webp）")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 10MB")
    avatar_id = f"custom_{uuid.uuid4().hex[:10]}"
    filename = f"{avatar_id}.jpg"
    path = os.path.join(UPLOAD_DH_AVATAR_DIR, filename)
    try:
        # PIL 校验并统一转 RGB JPEG（透明/异常图片兜底）
        img = Image.open(__import__("io").BytesIO(content))
        img = img.convert("RGB")
        img.thumbnail((1024, 1024), Image.LANCZOS)
        img.save(path, "JPEG", quality=92)
    except Exception as e:
        raise HTTPException(400, f"图片解析失败: {e}")
    image_url = f"/uploads/dh_avatars/{filename}"
    conn = get_db()
    try:
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO digital_human_custom_avatars (id, user_id, name, style, gender, desc, emoji, image_url, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (avatar_id, user, (name or "我的形象").strip()[:20], "自定义形象", "自定义",
             (desc or "").strip()[:100], "🖼️", image_url, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"avatar": {"id": avatar_id, "name": name.strip()[:20] or "我的形象", "image_url": image_url, "is_custom": True}}


@router.get("/custom-avatars")
async def list_custom_avatars(current_user: dict = require_auth()):
    """我的自定义数字人形象列表。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    return {"avatars": list(_load_custom_avatars(user).values())}


@router.delete("/custom-avatars/{avatar_id}")
async def delete_custom_avatar(avatar_id: str, current_user: dict = require_auth()):
    """删除自定义形象（记录 + 图片文件）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT image_url FROM digital_human_custom_avatars WHERE id=? AND user_id=?", (avatar_id, user),
        ).fetchone()
        if not row:
            raise HTTPException(404, "自定义形象不存在")
        conn.execute("DELETE FROM digital_human_custom_avatars WHERE id=? AND user_id=?", (avatar_id, user))
        conn.commit()
    finally:
        conn.close()
    url = row["image_url"] or ""
    if url.startswith("/uploads/"):
        local = os.path.join(_BASE_DIR, *url.lstrip("/").split("/"))
        if os.path.exists(local):
            os.remove(local)
    return {"success": True}


@router.post("/custom-voices")
async def upload_custom_voice(
    file: UploadFile = File(...),
    name: str = Form("我的声音"),
    desc: str = Form(""),
    current_user: dict = require_auth(),
):
    """上传自定义声音（音频样本）→ 生成视频时直接作为配音。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_AUDIO_EXT:
        raise HTTPException(400, f"不支持的音频格式: {ext or '未知'}（支持 mp3/wav/m4a/aac/ogg）")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "音频不能超过 20MB")
    voice_id = f"custom_{uuid.uuid4().hex[:10]}"
    filename = f"{voice_id}{ext}"
    path = os.path.join(UPLOAD_DH_VOICE_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    # ffprobe 校验时长（无效音频拦截，避免下游渲染失败）
    duration = _audio_duration(path)
    if duration <= 0:
        os.remove(path)
        raise HTTPException(400, "音频文件无效或无法解析，请重新上传")
    if duration > 600:
        os.remove(path)
        raise HTTPException(400, "音频不能超过 10 分钟")
    audio_url = f"/uploads/dh_voices/{filename}"
    conn = get_db()
    try:
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO digital_human_custom_voices (id, user_id, name, desc, emoji, audio_url, duration, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (voice_id, user, (name or "我的声音").strip()[:20], (desc or "").strip()[:100], "🎙️",
             audio_url, round(duration, 1), datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"voice": {"id": voice_id, "name": name.strip()[:20] or "我的声音", "audio_url": audio_url, "duration": round(duration, 1), "is_custom": True}}


@router.get("/custom-voices")
async def list_custom_voices(current_user: dict = require_auth()):
    """我的自定义声音列表。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    return {"voices": list(_load_custom_voices(user).values())}


@router.delete("/custom-voices/{voice_id}")
async def delete_custom_voice(voice_id: str, current_user: dict = require_auth()):
    """删除自定义声音（记录 + 音频文件）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT audio_url FROM digital_human_custom_voices WHERE id=? AND user_id=?", (voice_id, user),
        ).fetchone()
        if not row:
            raise HTTPException(404, "自定义声音不存在")
        conn.execute("DELETE FROM digital_human_custom_voices WHERE id=? AND user_id=?", (voice_id, user))
        conn.commit()
    finally:
        conn.close()
    url = row["audio_url"] or ""
    if url.startswith("/uploads/"):
        local = os.path.join(_BASE_DIR, *url.lstrip("/").split("/"))
        if os.path.exists(local):
            os.remove(local)
    return {"success": True}


# ── 请求模型 ──────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=5000, description="口播文案")
    avatar_id: str = Field("business-female", description="数字人形象ID")
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="声音ID")
    background_id: str = Field("tech", description="背景ID")
    scene_id: str = Field("product", description="场景模板ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    resolution: str = Field("720p", pattern="^(720p|1080p)$", description="视频分辨率")
    fps: int = Field(15, ge=10, le=30, description="帧率")
    watermark: bool | None = Field(None, description="水印：None=按会员等级（免费用户加水印）")


# 商业水印：免费用户生成视频带平台水印（会员/管理员自动去除）
WATERMARK_TEXT = "AI 数字人 · 小团智能"

# 数字人硬拦截词：行为违规（营销诱导/诈骗/赌博/违禁），命中直接拒绝生成。
# 广告法极限词（最/第一/顶级等）仅作提示不拦截——口语叙事中"第一次/最好"
# 属正常表达，硬拦截会误伤正常文案，故从硬拦截列表剔除。
_HARD_BLOCK_WORDS = [
    "点击领取", "免费领取", "立即抢购", "限时抢购", "免费送", "免费领",
    "加微信", "加QQ", "扫码加", "私信我",
    "日赚", "月入过万", "躺赚", "暴富", "发财",
    "包治", "根治", "治愈", "神药", "特效",
    "赌博", "彩票", "时时彩", "六合彩", "翻墙", "科学上网",
]


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


def _generate_one(req: GenerateRequest, user: str, uid: str, role: str = "") -> dict:
    """单条数字人视频生成流水线（供单条接口与批量任务复用）。

    流程：
    1. 文案预处理（LLM优化口播文案流畅度）
    2. TTS配音（调用配音工坊音频生成）
    3. 视频合成（数字人形象+配音+背景合成为口播视频）
    """
    start = datetime.now()

    # 0. 商业配额：生成消耗 1 次今日额度（管理员/VIP 不受限）
    from common.auth import consume_quota, get_quota_info
    quota = consume_quota(uid)
    if not quota.get("allowed"):
        raise HTTPException(
            402,
            "今日数字人生成次数已用完，升级会员获取更多额度（专业版每日 200 次，至尊版不限量）",
        )
    quota_info = get_quota_info(uid)  # 会员等级用于水印策略

    # 0.5 内容安全：硬违规词直接拒绝生成；广告法极限词/中风险词放行但提示
    try:
        from content_strategy import _scan_text
        hits = _scan_text(req.text)
    except Exception:
        hits = []
    lower_text = req.text.lower()
    hard_hits = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower_text]
    if hard_hits:
        raise HTTPException(400, f"文案含违规词（{', '.join(hard_hits[:6])}），已拦截生成，请修改后重试")
    risk_hits = list(dict.fromkeys(h["word"] for h in hits))  # 去重保序

    # 验证形象/声音/背景/场景（内置 + 用户自定义）
    avatar = next((a for a in AVATARS if a["id"] == req.avatar_id), None)
    voice = next((v for v in VOICES if v["id"] == req.voice_id), None)
    if not avatar and req.avatar_id.startswith("custom_"):
        avatar = _load_custom_avatars(user).get(req.avatar_id)
    if not voice and req.voice_id.startswith("custom_"):
        voice = _load_custom_voices(user).get(req.voice_id)
    if not avatar:
        raise HTTPException(400, f"未知数字人形象: {req.avatar_id}")
    if not voice:
        raise HTTPException(400, f"未知声音: {req.voice_id}")
    bg = next((b for b in BACKGROUNDS if b["id"] == req.background_id), None)
    if not bg:
        raise HTTPException(400, f"未知背景: {req.background_id}")

    record_id = f"dh_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    _ensure_tables(conn)

    # 水印策略：免费用户强制加水印（商业规则，不可绕过）；会员显式传 True 才加
    membership = quota_info.get("membership", "free") if isinstance(quota_info, dict) else "free"
    use_watermark = (membership == "free" and role != "admin") or bool(req.watermark)

    # 1. 文案 — 字幕与配音必须与用户输入完全一致：
    # 之前 LLM 优化环节会把原文改写为带 Markdown 标记（#、**、---）的口播脚本，
    # 导致字幕显示“乱码/不是用户输入的内容”，此处直接使用原文（仅清洗换行）。
    optimized_text = _clean_script_text(req.text)

    # 2. TTS 配音 — 内置音色走 AI 合成；自定义声音直接用上传音频作为配音
    audio_url = ""
    audio_error = ""
    audio_path = ""
    if voice.get("is_custom"):
        audio_path = voice.get("local_audio_path") or ""
        if audio_path and os.path.exists(audio_path):
            audio_url = voice["audio_url"]
        else:
            audio_error = "自定义声音文件缺失，请重新上传"
    if not audio_url:
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
    # 渲染为 CPU 密集操作，受全局并发池保护（同批次多任务串行，跨批次限并发数）
    video_url = ""
    status = "done"
    error_msg = ""
    if audio_path and os.path.exists(audio_path):
        try:
            if not _RENDER_SLOT.acquire(timeout=600):
                raise RuntimeError("当前视频渲染任务繁忙，请稍后重试")
            try:
                video_filename = f"{record_id}.mp4"
                video_path = os.path.join(UPLOAD_VIDEO_DIR, video_filename)
                _render_video(
                    text=optimized_text[:200],
                    avatar=avatar,
                    bg=bg,
                    audio_path=audio_path,
                    output_path=video_path,
                    resolution=req.resolution,
                    fps=req.fps,
                    watermark=use_watermark,
                )
            finally:
                _RENDER_SLOT.release()
            video_url = f"/uploads/videos/{video_filename}"
        except Exception as e:
            logger.exception("video generation failed %s", record_id)
            status = "audio_only"
            error_msg = f"视频合成失败（{e}），已生成配音音频"
    else:
        # 配音未生成：明确标记 failed（区别于音频成功但视频失败的 audio_only），
        # 避免前端误显“配音音频已生成，可预览音频+形象”
        status = "failed"
        error_msg = audio_error or "配音生成失败"

    # 4. 保存记录（含商业参数：分辨率/帧率/水印）
    conn.execute(
        """INSERT INTO digital_human_records
           (id, user_id, avatar_id, avatar_name, voice_id, voice_name,
            background_id, scene_id, text, text_length, status,
            audio_url, video_url, error, resolution, fps, watermark, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) """,
        (record_id, user, req.avatar_id, avatar["name"], req.voice_id, voice["name"],
         req.background_id, req.scene_id, optimized_text, len(optimized_text),
         status, audio_url, video_url, error_msg,
         req.resolution, req.fps, 1 if use_watermark else 0,
         datetime.now().isoformat()),
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
        "resolution": req.resolution,
        "fps": req.fps,
        "watermark": use_watermark,
        "quota_remaining": quota.get("remaining"),
        "sensitive_warning": (
            f"文案含风险词（{', '.join(risk_hits[:6])}），发布到平台时可能限流，建议修改"
            if risk_hits else ""
        ),
        "audio_url": audio_url,
        "video_url": video_url,
        "error": error_msg,
        "message": (
            f"口播视频已生成！{avatar['name']} + {voice['name']}，可下载 MP4 视频和 MP3 音频"
            if status == "done"
            else "配音音频已生成，视频合成失败（可预览音频+形象）"
            if status == "audio_only"
            else f"生成失败：{error_msg or '未知错误'}"
        ),
    }


@router.post("/generate")
async def generate(req: GenerateRequest, current_user: dict = require_auth()):
    """数字人口播视频生成 — 文案→配音→视频合成流水线（单条接口）。

    批量生产请使用 POST /api/digital-human/batch（多文案后台逐条生成）。
    同一用户同时仅允许 1 条生成（前端按钮已防抖，后端兜底防多标签页并发）。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    # 用户级并发限制：同用户同时最多 1 条生成中
    with _GUARD_LOCK:
        inflight = _USER_GENERATING.get(uid, 0)
        if inflight >= 1:
            raise HTTPException(429, "您有视频正在生成中，请等待当前生成完成")
        _USER_GENERATING[uid] = inflight + 1
    try:
        return _generate_one(req, user, uid, role)
    finally:
        with _GUARD_LOCK:
            _USER_GENERATING[uid] = _USER_GENERATING.get(uid, 1) - 1
            if _USER_GENERATING[uid] <= 0:
                _USER_GENERATING.pop(uid, None)


@router.get("/records")
async def list_records(
    page: int = 1, page_size: int = 20, status: str = "", q: str = "",
    current_user: dict = require_auth(),
):
    """历史记录分页查询：状态筛选（done/audio_only/failed）+ 关键词搜索（文案/形象/声音）。"""
    conn = get_db()
    _ensure_tables(conn)
    where, args = ["1=1"], []
    if status:
        where.append("status=?")
        args.append(status)
    if q.strip():
        kw = f"%{q.strip()}%"
        where.append("(text LIKE ? OR avatar_name LIKE ? OR voice_name LIKE ?)")
        args += [kw, kw, kw]
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = conn.execute(
        f"SELECT COUNT(*) FROM digital_human_records WHERE {' AND '.join(where)}", args,
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM digital_human_records WHERE {' AND '.join(where)}"
        f" ORDER BY created_at DESC LIMIT ? OFFSET ?",
        args + [page_size, (page - 1) * page_size],
    ).fetchall()
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


class BatchDeleteRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, description="记录ID列表")


def _url_to_path(url: str) -> str:
    """/uploads/audio/x.mp3 → backend/uploads/audio/x.mp3（统一 URL 到磁盘路径解析）。"""
    return os.path.join(_BASE_DIR, url.lstrip("/"))


def _delete_record_files(conn, record_id: str) -> None:
    """删除记录关联的音频/视频文件（释放磁盘空间）。"""
    row = conn.execute(
        "SELECT audio_url, video_url FROM digital_human_records WHERE id=?", (record_id,),
    ).fetchone()
    if not row:
        return
    for url in (row["audio_url"] or "", row["video_url"] or ""):
        if not url:
            continue
        p = _url_to_path(url)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


@router.post("/records/batch-delete")
async def batch_delete_records(req: BatchDeleteRequest, current_user: dict = require_auth()):
    """批量删除记录（同时清理关联的音频/视频文件）。"""
    conn = get_db()
    _ensure_tables(conn)
    deleted = 0
    for rid in req.ids:
        _delete_record_files(conn, rid)
        conn.execute("DELETE FROM digital_human_records WHERE id=?", (rid,))
        deleted += 1
    conn.commit()
    conn.close()
    return {"success": True, "deleted": deleted}


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    """删除单条记录（同时清理关联的音频/视频文件）。"""
    conn = get_db()
    _ensure_tables(conn)
    _delete_record_files(conn, record_id)
    conn.execute("DELETE FROM digital_human_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ══════════════════════════════════════════════════════════════
# 批量生产流水线：多条文案 → 后台线程逐条生成 → 进度查询 → ZIP 打包
# ══════════════════════════════════════════════════════════════

class BatchGenerateRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=50, description="文案列表（1-50 条）")
    avatar_id: str = Field("business-female", description="数字人形象ID")
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="声音ID")
    background_id: str = Field("tech", description="背景ID")
    scene_id: str = Field("product", description="场景模板ID")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    resolution: str = Field("720p", pattern="^(720p|1080p)$", description="视频分辨率")
    fps: int = Field(15, ge=10, le=30, description="帧率")
    watermark: bool | None = Field(None, description="水印：None=按会员等级（免费用户加水印）")


# 批量任务缓存：batch_id → 任务（DB 为持久真相，内存仅加速轮询；重启后自动从 DB 恢复）
_BATCH_TASKS: dict[str, dict] = {}
_BATCH_LOCK = threading.Lock()

# 全局渲染并发池：视频渲染为 CPU 密集操作，跨用户/批次统一限制并发数
_RENDER_SLOT = threading.BoundedSemaphore(2)
# 单条生成用户级并发限制：同用户同时最多 1 条生成中（防多标签页并发）
_USER_GENERATING: dict[str, int] = {}
_GUARD_LOCK = threading.Lock()

# 视频保留策略：默认 30 天（0 或负值 = 不自动清理）
DH_RETENTION_DAYS = int(os.environ.get("DH_RETENTION_DAYS", "30"))


def _load_batch_from_db(batch_id: str) -> dict | None:
    """从数据库恢复批量任务完整结构（重启后轮询/下载/重试兜底）。"""
    conn = get_db()
    try:
        _ensure_tables(conn)
        conn.commit()
        row = conn.execute("SELECT * FROM digital_human_batches WHERE id=?", (batch_id,)).fetchone()
        if not row:
            return None
        items = conn.execute(
            "SELECT * FROM digital_human_batch_items WHERE batch_id=? ORDER BY idx", (batch_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "id": row["id"], "user": row["user_id"], "status": row["status"],
        "total": row["total"],
        "done": row["success"] + row["failed"] + row["skipped"],
        "success": row["success"], "failed": row["failed"], "skipped": row["skipped"],
        "avatar_id": row["avatar_id"], "avatar_name": row["avatar_name"],
        "resolution": row["resolution"], "fps": row["fps"],
        "voice_id": row["voice_id"], "background_id": row["background_id"],
        "speed": row["speed"],
        "created_at": row["created_at"], "finished_at": row["finished_at"],
        "items": [
            {"index": r["idx"], "text_preview": r["text"][:40], "status": r["status"],
             "error": r["error"], "record_id": r["record_id"],
             "audio_url": r["audio_url"], "video_url": r["video_url"],
             "watermark": bool(r["watermark"]), "sensitive_warning": r["sensitive_warning"]}
            for r in items
        ],
    }


def _batch_worker(batch_id: str, texts: list[str], req: BatchGenerateRequest,
                  user: str, uid: str, role: str, indexes: list[int] | None = None) -> None:
    """后台批量生成：逐条走完整流水线；违规词/超短文案直接失败（不浪费配额）。

    indexes 非空时表示部分重试（只处理指定下标）；每条结果实时落库，进程重启可从 DB 恢复。
    """
    task = _BATCH_TASKS[batch_id]
    try:
        for i in (indexes if indexes is not None else range(len(texts))):
            item = task["items"][i]
            text = texts[i].strip()
            if len(text) < 5:
                item["status"] = "failed"
                item["error"] = "文案太短（至少 5 字）"
            elif any(w.lower() in text.lower() for w in _HARD_BLOCK_WORDS):
                item["status"] = "failed"
                item["error"] = "文案含违规词，已拦截"
            else:
                try:
                    sub = GenerateRequest(
                        text=text, avatar_id=req.avatar_id, voice_id=req.voice_id,
                        background_id=req.background_id, scene_id=req.scene_id,
                        speed=req.speed, resolution=req.resolution,
                        fps=req.fps, watermark=req.watermark,
                    )
                    res = _generate_one(sub, user, uid, role)
                    if res["status"] == "done":
                        item.update(
                            status="success",
                            record_id=res["record_id"],
                            audio_url=res["audio_url"],
                            video_url=res["video_url"],
                            watermark=res["watermark"],
                            sensitive_warning=res.get("sensitive_warning", ""),
                        )
                    else:
                        # audio_only/failed：未产出视频一律算失败（可重试）
                        item["status"] = "failed"
                        item["error"] = (res.get("error") or "生成失败")[:120]
                except HTTPException as e:
                    item["status"] = "skipped" if e.status_code == 402 else "failed"
                    item["error"] = str(e.detail)[:120]
                except Exception as e:
                    logger.exception("batch item failed %s", batch_id)
                    item["status"] = "failed"
                    item["error"] = str(e)[:120]
            task["done"] += 1
            task[item["status"]] += 1
            # 逐条落库：重启后可恢复进度/结果
            with get_db_context() as conn:
                conn.execute(
                    """UPDATE digital_human_batch_items
                       SET status=?, error=?, record_id=?, audio_url=?, video_url=?,
                           watermark=?, sensitive_warning=?
                       WHERE batch_id=? AND idx=?""",
                    (item["status"], item["error"], item.get("record_id", ""),
                     item.get("audio_url", ""), item.get("video_url", ""),
                     1 if item.get("watermark") else 0,
                     item.get("sensitive_warning", ""), batch_id, i),
                )
    except Exception:
        logger.exception("batch worker crashed %s", batch_id)
        with get_db_context() as conn:
            conn.execute(
                "UPDATE digital_human_batches SET status='interrupted', finished_at=? WHERE id=?",
                (datetime.now().isoformat(), batch_id),
            )
        task["status"] = "interrupted"
        return
    task["status"] = "done"
    task["finished_at"] = datetime.now().isoformat()
    with get_db_context() as conn:
        conn.execute(
            """UPDATE digital_human_batches
               SET status=?, success=?, failed=?, skipped=?, finished_at=?
               WHERE id=?""",
            (task["status"], task["success"], task["failed"], task["skipped"],
             task["finished_at"], batch_id),
        )


def recover_interrupted_batches() -> None:
    """启动时恢复：上次进程退出时仍在 running 的批量任务标记为 interrupted（可手动重试失败项）。"""
    try:
        with get_db_context() as conn:
            _ensure_tables(conn)
            now = datetime.now().isoformat()
            n = conn.execute(
                "UPDATE digital_human_batches SET status='interrupted', finished_at=? WHERE status='running'",
                (now,),
            ).rowcount
            if n:
                logger.info("数字人批量任务恢复：%s 个运行中任务标记为已中断", n)
    except Exception:
        logger.exception("recover interrupted batches failed")


@router.post("/batch")
async def create_batch(req: BatchGenerateRequest, current_user: dict = require_auth()):
    """批量生成：多条文案 → 后台线程逐条生产 → 返回 batch_id 供进度轮询。

    配额逐条扣减（每条 1 次）；违规词文案不消耗配额；额度不足的条目标记 skipped。
    任务持久化落库：重启后可查询进度/打包下载/重试失败项。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    texts = [t.strip() for t in req.texts if t and t.strip()]
    if not texts:
        raise HTTPException(400, "文案列表为空，请输入至少一条文案")
    if len(texts) > 50:
        raise HTTPException(400, "单次最多 50 条文案")
    # 预检配额：今日剩余为 0 直接拒绝（避免空跑任务）
    from common.auth import get_quota_info
    qi = get_quota_info(uid) or {}
    remaining = qi.get("remaining_today")
    if remaining is not None and remaining <= 0:
        raise HTTPException(402, "今日生成次数已用完，升级会员获取更多额度")
    # 形象名校验（zip 打包文件名使用）
    avatar = next((a for a in AVATARS if a["id"] == req.avatar_id), None)
    avatar_name = avatar["name"] if avatar else req.avatar_id
    batch_id = f"dhb_{uuid.uuid4().hex[:10]}"
    items = [
        {"index": i, "text_preview": t[:40], "status": "pending", "error": "",
         "record_id": "", "audio_url": "", "video_url": "",
         "watermark": False, "sensitive_warning": ""}
        for i, t in enumerate(texts)
    ]
    # 持久化落库 + 运行中任务数限制（同用户最多 2 个，防止堆积打爆资源）
    with get_db_context() as conn:
        _ensure_tables(conn)
        running_cnt = conn.execute(
            "SELECT COUNT(*) FROM digital_human_batches WHERE user_id=? AND status='running'",
            (user,),
        ).fetchone()[0]
        if running_cnt >= 2:
            raise HTTPException(400, "您已有批量任务在运行（最多同时 2 个），请等待完成后再创建")
        conn.execute(
            """INSERT INTO digital_human_batches
               (id, user_id, status, total, success, failed, skipped,
                avatar_id, avatar_name, resolution, fps, voice_id, background_id, speed,
                created_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (batch_id, user, "running", len(texts), 0, 0, 0,
             req.avatar_id, avatar_name, req.resolution, req.fps,
             req.voice_id, req.background_id, req.speed,
             datetime.now().isoformat(), ""),
        )
        for i, t in enumerate(texts):
            conn.execute(
                "INSERT INTO digital_human_batch_items (batch_id, idx, text, status) VALUES (?,?,?,?)",
                (batch_id, i, t, "pending"),
            )
    task = {
        "id": batch_id, "user": user, "status": "running",
        "total": len(texts), "done": 0, "success": 0, "failed": 0, "skipped": 0,
        "avatar_id": req.avatar_id, "avatar_name": avatar_name,
        "resolution": req.resolution, "fps": req.fps,
        "voice_id": req.voice_id, "background_id": req.background_id, "speed": req.speed,
        "created_at": datetime.now().isoformat(), "finished_at": "",
        "items": items,
    }
    with _BATCH_LOCK:
        _BATCH_TASKS[batch_id] = task
        # 内存任务上限 100：清理最旧的已完成任务（DB 仍有完整记录，可兜底恢复）
        if len(_BATCH_TASKS) > 100:
            done_ids = [k for k, v in _BATCH_TASKS.items() if v["status"] == "done"]
            for k in done_ids[: len(_BATCH_TASKS) - 100]:
                del _BATCH_TASKS[k]
    threading.Thread(target=_batch_worker, args=(batch_id, texts, req, user, uid, role), daemon=True).start()
    return {
        "batch_id": batch_id, "total": len(texts), "status": "running",
        "avatar_name": avatar_name, "resolution": req.resolution, "fps": req.fps,
    }


@router.get("/batch/{batch_id}")
async def get_batch(batch_id: str, current_user: dict = require_auth()):
    """批量任务进度查询（仅创建者可见）。内存缓存未命中时从 DB 恢复（重启后仍可查询）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    task = _BATCH_TASKS.get(batch_id) or _load_batch_from_db(batch_id)
    if not task or task["user"] != user:
        raise HTTPException(404, "批量任务不存在")
    return task


@router.get("/batch/{batch_id}/download")
async def download_batch(batch_id: str, current_user: dict = require_auth()):
    """打包下载批量任务的全部成功视频（ZIP，文件名含序号+形象+记录ID）。"""
    import io
    import zipfile
    from fastapi.responses import StreamingResponse
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    task = _BATCH_TASKS.get(batch_id) or _load_batch_from_db(batch_id)
    if not task or task["user"] != user:
        raise HTTPException(404, "批量任务不存在")
    if task["status"] != "done":
        raise HTTPException(400, "任务尚未完成，请稍后再下载")
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in task["items"]:
            if item["status"] != "success" or not item.get("video_url"):
                continue
            p = _url_to_path(item["video_url"])
            if os.path.exists(p):
                zf.write(p, f"{item['index'] + 1:02d}_{task['avatar_name']}_{item['record_id']}.mp4")
                count += 1
    if count == 0:
        raise HTTPException(400, "没有可下载的视频（任务无成功产物）")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="digital-human-batch-{batch_id}.zip"'},
    )


@router.post("/batch/{batch_id}/retry-failed")
async def retry_batch_failed(batch_id: str, current_user: dict = require_auth()):
    """重试批量任务的失败项：仅重跑非内容性问题项（违规词/文案太短重试必然再失败，跳过）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    task = _load_batch_from_db(batch_id)
    if not task or task["user"] != user:
        raise HTTPException(404, "批量任务不存在")
    if task["status"] not in ("done", "interrupted"):
        raise HTTPException(400, "任务仍在运行中，请等待完成后再重试")
    if task["failed"] == 0:
        raise HTTPException(400, "没有失败项需要重试")
    retry_indexes = [
        item["index"] for item in task["items"]
        if item["status"] == "failed" and "违规词" not in item["error"]
        and "文案太短" not in item["error"]
    ]
    if not retry_indexes:
        raise HTTPException(400, "失败项均为内容问题（违规词/文案过短），无需重试")
    # 完整文案从 DB 读取（text_preview 被截断，重试必须用原文）
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT idx, text FROM digital_human_batch_items WHERE batch_id=? ORDER BY idx", (batch_id,),
        ).fetchall()
    full_texts = [r["text"] for r in rows]
    req = BatchGenerateRequest(
        texts=full_texts,
        avatar_id=task["avatar_id"], voice_id=task["voice_id"],
        background_id=task["background_id"], scene_id="product",
        speed=task["speed"], resolution=task["resolution"], fps=task["fps"],
        watermark=None,
    )
    # 重建任务（失败项重置为 pending，其余保持原结果）
    new_items = [dict(item) for item in task["items"]]
    for i in retry_indexes:
        new_items[i].update(status="pending", error="", record_id="", audio_url="",
                            video_url="", watermark=False, sensitive_warning="")
    new_task = {
        "id": batch_id, "user": user, "status": "running",
        "total": task["total"], "done": task["total"] - len(retry_indexes),
        "success": task["success"], "failed": task["failed"] - len(retry_indexes),
        "skipped": task["skipped"],
        "avatar_id": task["avatar_id"], "avatar_name": task["avatar_name"],
        "resolution": task["resolution"], "fps": task["fps"],
        "voice_id": task["voice_id"], "background_id": task["background_id"],
        "speed": task["speed"],
        "created_at": task["created_at"], "finished_at": "",
        "items": new_items,
    }
    with _BATCH_LOCK:
        _BATCH_TASKS[batch_id] = new_task
    with get_db_context() as conn:
        conn.execute(
            "UPDATE digital_human_batches SET status='running', finished_at='' WHERE id=?", (batch_id,),
        )
        for i in retry_indexes:
            conn.execute(
                """UPDATE digital_human_batch_items SET status='pending', error='',
                   record_id='', audio_url='', video_url='', watermark=0, sensitive_warning=''
                   WHERE batch_id=? AND idx=?""",
                (batch_id, i),
            )
    threading.Thread(
        target=_batch_worker,
        args=(batch_id, full_texts, req, user, uid, role, retry_indexes),
        daemon=True,
    ).start()
    return {"batch_id": batch_id, "retrying": len(retry_indexes), "status": "running"}


# ══════════════════════════════════════════════════════════════
# 内容生产提效：AI 口播文案助手 + 文案合规预检
# ══════════════════════════════════════════════════════════════

class ScriptAssistRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=100, description="口播主题")
    scene_id: str = Field("product", description="场景模板ID（影响文案风格）")
    platform: str = Field("douyin", max_length=20, description="目标平台 douyin/kuaishou/wechat/bilibili")
    tone: str = Field("专业", max_length=20, description="文案风格：专业/亲切/活泼/煽情")


_SCENE_STYLES = {
    "product": "产品介绍，突出卖点与使用场景",
    "course": "课程讲解，结构化输出知识点",
    "news": "新闻播报，字正腔圆、客观中立",
    "livestream": "直播带货，强互动、营造紧迫感",
    "story": "故事讲述，情感丰富、有画面感",
}


@router.post("/script-assist")
async def script_assist(req: ScriptAssistRequest, current_user: dict = require_auth()):
    """AI 口播文案助手：按主题/场景/平台生成 3 版口播脚本（LLM 失败自动回退模板）。"""
    scene_style = _SCENE_STYLES.get(req.scene_id, "产品介绍")
    platform_labels = {"douyin": "抖音", "kuaishou": "快手", "wechat": "公众号", "bilibili": "B站"}
    platform_name = platform_labels.get(req.platform, req.platform)
    system = (
        "你是资深短视频口播文案专家。根据要求生成3版口播文案，直接输出JSON数组，"
        "每版是1个字符串对象，120字以内，必须包含：开头钩子、核心内容、结尾引导。"
        "要求：口语化、无Markdown标记、无违禁词（不能出现点击领取/加微信/日赚等），不要用'最'等广告法极限词。"
    )
    user_prompt = (
        f"主题：{req.topic}；场景：{scene_style}；平台：{platform_name}；风格：{req.tone}。"
        "请生成3版不同切入角度的口播文案。"
    )
    scripts = []
    ok = False
    try:
        raw = call_llm(system, user_prompt, max_tokens=1500, temperature=0.9, timeout=60)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            if raw.endswith("```"):
                raw = raw[:-3]
        data = json.loads(raw)
        if isinstance(data, list) and data:
            scripts = [str(s).strip() for s in data if str(s).strip()][:3]
            ok = True
    except Exception:
        logger.exception("script assist LLM failed")
    if not scripts:
        # 回退模板：保证功能在 LLM 不可用时仍可用
        scripts = [
            f"大家好，今天和大家聊聊「{req.topic}」。这件事和每个人都有关，看完一定会有收获。",
            f"你敢信吗？{req.topic}还能这么玩。今天3分钟带你彻底搞明白。",
            f"最近后台收到很多朋友问{req.topic}，今天就一次说清楚，记得点赞收藏。",
        ]
    log_usage("digital_human_script", len(req.topic), sum(len(s) for s in scripts), 0)
    return {"scripts": scripts, "source": "ai" if ok else "fallback"}


class ComplianceCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="待检查文案")


@router.post("/compliance-check")
async def compliance_check(req: ComplianceCheckRequest, current_user: dict = require_auth()):
    """文案合规预检：硬违规词（红色拦截）+ 广告法极限词/风险词（橙色提示）。"""
    lower = req.text.lower()
    hard_hits = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower]
    risk_hits = []
    try:
        from content_strategy import _scan_text
        risk_hits = list(dict.fromkeys(h["word"] for h in _scan_text(req.text)))
    except Exception:
        pass
    return {"allowed": not hard_hits, "hard_hits": hard_hits, "risk_hits": risk_hits}


# ══════════════════════════════════════════════════════════════
# 生产运营：磁盘治理（保留期清理）+ 存储统计 + 管理员专项报表
# ══════════════════════════════════════════════════════════════

def _cleanup_expired_records() -> int:
    """删除超过保留期的历史记录及其文件（DH_RETENTION_DAYS 天，默认 30；<=0 不清理）。"""
    if DH_RETENTION_DAYS <= 0:
        return 0
    cutoff = (datetime.now() - timedelta(days=DH_RETENTION_DAYS)).isoformat()
    with get_db_context() as conn:
        _ensure_tables(conn)
        rows = conn.execute(
            "SELECT id FROM digital_human_records WHERE created_at < ?", (cutoff,),
        ).fetchall()
        for row in rows:
            _delete_record_files(conn, row["id"])
            conn.execute("DELETE FROM digital_human_records WHERE id=?", (row["id"],))
    if rows:
        logger.info("存储清理：删除 %s 条超过 %s 天的过期记录", len(rows), DH_RETENTION_DAYS)
    return len(rows)


def start_storage_cleaner() -> None:
    """启动存储清理守护线程：启动时执行一次，之后每 24h 执行（保留 DH_RETENTION_DAYS 天）。"""
    if DH_RETENTION_DAYS <= 0:
        logger.info("数字人存储清理已禁用（DH_RETENTION_DAYS=%s）", DH_RETENTION_DAYS)
        return

    def _loop():
        while True:
            try:
                _cleanup_expired_records()
            except Exception:
                logger.exception("storage cleaner failed")
            time.sleep(24 * 3600)

    threading.Thread(target=_loop, daemon=True, name="dh-storage-cleaner").start()
    logger.info("数字人存储清理守护线程已启动（保留 %s 天）", DH_RETENTION_DAYS)


def _compute_storage_bytes() -> dict:
    """统计音频/视频目录磁盘占用（MB）。"""
    total = audio_bytes = video_bytes = 0
    audio_count = video_count = 0
    for root, is_audio in ((UPLOAD_AUDIO_DIR, True), (UPLOAD_VIDEO_DIR, False)):
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for fn in names:
            p = os.path.join(root, fn)
            try:
                if os.path.isfile(p):
                    sz = os.path.getsize(p)
                    total += sz
                    if is_audio:
                        audio_bytes += sz; audio_count += 1
                    else:
                        video_bytes += sz; video_count += 1
            except OSError:
                pass
    return {
        "total_mb": round(total / 1048576, 1),
        "audio_mb": round(audio_bytes / 1048576, 1),
        "video_mb": round(video_bytes / 1048576, 1),
        "audio_count": audio_count, "video_count": video_count,
    }


@router.get("/storage")
async def my_storage(current_user: dict = require_auth()):
    """我的存储用量：记录数 / 音频视频数 / 磁盘占用 / 保留策略。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT audio_url, video_url FROM digital_human_records WHERE user_id=?", (user,),
        ).fetchall()
    finally:
        conn.close()
    total = 0
    audio_count = video_count = 0
    for row in rows:
        for url in (row["audio_url"], row["video_url"]):
            if not url:
                continue
            p = _url_to_path(url)
            try:
                if os.path.isfile(p):
                    total += os.path.getsize(p)
                    if url.endswith(".mp4"):
                        video_count += 1
                    else:
                        audio_count += 1
            except OSError:
                pass
    return {
        "records": len(rows),
        "audio_count": audio_count,
        "video_count": video_count,
        "size_mb": round(total / 1048576, 1),
        "retention_days": DH_RETENTION_DAYS,
    }


@router.get("/admin/stats")
async def admin_dh_stats(current_user: dict = require_auth()):
    """数字人专项运营报表（管理员）：总量/成功率/耗时/失败原因/用户TOP/趋势/存储/批量任务。"""
    from admin_api import _check_admin
    _check_admin(current_user)
    conn = get_db()
    try:
        total_records = conn.execute(
            "SELECT COUNT(*) FROM digital_human_records").fetchone()[0]
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        today_records = conn.execute(
            "SELECT COUNT(*) FROM digital_human_records WHERE created_at LIKE ?",
            (today_prefix + "%",),
        ).fetchone()[0]
        status_dist = {r["status"]: r["c"] for r in conn.execute(
            "SELECT status, COUNT(*) c FROM digital_human_records GROUP BY status").fetchall()}
        res_dist = {r["resolution"]: r["c"] for r in conn.execute(
            "SELECT resolution, COUNT(*) c FROM digital_human_records GROUP BY resolution").fetchall()}
        user_top = [dict(r) for r in conn.execute(
            "SELECT user_id, COUNT(*) c FROM digital_human_records GROUP BY user_id ORDER BY c DESC LIMIT 5").fetchall()]
        trend_7d = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            c = conn.execute(
                "SELECT COUNT(*) FROM digital_human_records WHERE created_at LIKE ?", (d + "%",),
            ).fetchone()[0]
            trend_7d.append({"date": d, "count": c})
        recent_failures = [dict(r) for r in conn.execute(
            "SELECT text, error, created_at FROM digital_human_records WHERE status='failed'"
            " AND error != '' ORDER BY created_at DESC LIMIT 10").fetchall()]
        usage = conn.execute(
            "SELECT COUNT(*) c, AVG(response_time) avg_sec, SUM(success) ok"
            " FROM usage_logs WHERE task_type='digital_human'").fetchone()
        batch_row = conn.execute(
            "SELECT COUNT(*) c,"
            " SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done_cnt,"
            " SUM(CASE WHEN status='interrupted' THEN 1 ELSE 0 END) interrupted_cnt"
            " FROM digital_human_batches").fetchone()
    finally:
        conn.close()
    ok = usage["ok"] or 0
    usage_cnt = usage["c"] or 0
    return {
        "totals": {"records": total_records, "today": today_records},
        "status_dist": status_dist,
        "res_dist": res_dist,
        "user_top": user_top,
        "trend_7d": trend_7d,
        "recent_failures": recent_failures,
        "usage": {
            "total": usage_cnt,
            "success": ok,
            "success_rate": round(ok / usage_cnt, 3) if usage_cnt else 0,
            "avg_seconds": round(usage["avg_sec"] or 0, 1),
        },
        "storage": _compute_storage_bytes(),
        "batches": {
            "total": batch_row["c"] or 0,
            "done": batch_row["done_cnt"] or 0,
            "interrupted": batch_row["interrupted_cnt"] or 0,
        },
    }
