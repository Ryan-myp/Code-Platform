"""AI数字人/虚拟主播 — 文案→配音→口播视频合成。

- GET  /api/digital-human/avatars   内置8个虚拟形象库
- GET  /api/digital-human/voices    可选声音列表（复用配音工坊音色）
- POST /api/digital-human/generate  文案+形象+声音+背景 → 生成口播视频
- GET  /api/digital-human/records   历史生成记录
"""

import logging
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from io import BytesIO
from typing import Callable

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db, get_db_context
from common.llm import call_llm, log_usage
from task_queue import create_task, register_handler

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


# 归一化后的写真统一尺寸（4:5 竖版半身像）
PORTRAIT_NORM_SIZE = (800, 1000)


def _skin_region_metrics(img: Image.Image) -> dict | None:
    """肤色检测估计人物头部位置（无肤色返回 None，卡通/二次元形象走 fallback）。

    返回：头部中心 (cx, cy)、头部宽度 head_w。
    - HSV 色相区间过滤（橙黄肤色 vs 米黄背景：肤色更饱和、更偏红）
    - 头部搜索区限图像上部 70%；head_w 超全宽 72% 视为误检回退
    """
    import numpy as np

    a = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = np.maximum(np.maximum(R, G), B), np.minimum(np.minimum(R, G), B)
    diff = mx - mn
    is_skin = (
        (diff > 0.04) & (diff < 0.55)                     # 饱和度适中
        & (mx > 0.45) & (mx < 0.98)                       # 亮度区间（排除纯白/纯黑）
        & (R >= G) & (G >= B * 0.72) & (G <= B * 1.45)    # 橙黄主导 R>G>B
        & (R - B > 0.06) & (np.abs(R - G) > 0.03)         # 色相偏红黄
    )
    if int(is_skin.sum()) < 300:
        return None
    # 头部搜索区：上部 70% 的肤色行分布
    rows = is_skin[: int(img.height * 0.70)].sum(axis=1)
    ys = np.where(rows > rows.max() * 0.18)[0]
    if len(ys) == 0:
        return None
    top, bot = int(ys.min()), int(ys.max())
    # 头部核心区 = 肤色区上部 45%（脸，排除脖子/肩膀/手）
    sub2 = is_skin[top : top + int((bot - top) * 0.45) + 1]
    cols = sub2.sum(axis=0)
    if int(cols.sum()) < 200:
        return None
    # 列分布能量宽度：取包含 70% 肤色能量的最窄区间（抗手/肩稀疏肤色干扰）
    total = float(cols.sum())
    ccenter = int(np.argmax(cols))
    lo = hi = ccenter
    acc = float(cols[ccenter])
    while lo > 0 and acc < total * 0.70:
        lo -= 1
        acc += float(cols[lo])
    while hi < len(cols) - 1 and acc < total * 0.70:
        hi += 1
        acc += float(cols[hi])
    head_w = int((hi - lo + 1) * 0.95)
    if head_w > img.width * 0.72:  # 头部不可能占全宽：背景误检，回退
        return None
    cy = int(top + (bot - top) * 0.28)  # 头部中心（头区中上部）
    cx = int((cols * np.arange(img.width)).sum() / total)
    return {"cx": cx, "cy": cy, "head_w": head_w}


def _normalize_portrait_image(img: Image.Image) -> Image.Image:
    """构图归一化：头部水平居中 + 垂直位置一致（消除"人物忽远忽近/忽左忽右"）。

    cover 等比缩放下人物占比是几何不变量（人物占比恒等于源图占比），
    占比统一依赖写真 prompt 的数字构图锚定；此处保证：
    - 水平：裁窗锚定头部中心 → 脸不偏不切（原固定居中裁窗在人物偏位时会切脸）
    - 垂直：头部尽量锚定到画布 25% 高度（方形源图头部上方空间不足时贴顶）
    肤色检测失败（卡通/二次元）时回退 30% 偏上 cover 裁窗。
    """
    W, H = PORTRAIT_NORM_SIZE
    k0 = max(W / img.width, H / img.height)  # cover 缩放（占比不变量）
    nw, nh = int(round(img.width * k0)), int(round(img.height * k0))
    scaled = img.resize((nw, nh), Image.LANCZOS) if (nw, nh) != img.size else img
    met = _skin_region_metrics(img)
    if not met:
        x0 = (nw - W) // 2
        y0 = max(0, min(int((nh - H) * 0.30), nh - H))
        return scaled.crop((x0, y0, x0 + W, y0 + H))
    # 水平：头部中心锚定画布中线（消除左右漂移/切脸）
    x0 = int(met["cx"] * k0 - W * 0.5)
    x0 = max(0, min(x0, nw - W))
    # 垂直：头部中心尽量锚定到画布 25% 高度（空间不足则贴顶）
    y0 = int(met["cy"] * k0 - H * 0.25)
    y0 = max(0, min(y0, nh - H))
    return scaled.crop((x0, y0, x0 + W, y0 + H))


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
    # 真实感统一后缀：微笑表情 + 数字构图锚定（消除随机构图漂移）+ 皮肤纹理去 AI 脸感
    prompt = prompt.rstrip(".") + (
        ", front-facing, eyes looking directly into camera, gentle warm smile with "
        "lips closed, slightly squinted happy eyes, soft natural rosy cheeks, "
        "waist-up half body portrait, head occupies 30 percent of frame height, "
        "chin at 55 percent of frame height, generous headroom above head, face "
        "perfectly centered horizontally, single soft key light, realistic skin "
        "pore texture, subtle natural skin imperfections, candid photography "
        "style, shallow depth of field, 8k uhd, hyper-realistic detail"
    )

    from common.config import AGNES_API_BASE, AGNES_API_KEY
    if not AGNES_API_KEY:
        logger.warning("未配置 AGNES_API_KEY，无法生成数字人写真")
        return None

    # 竖版尺寸（4:5）更贴近半身像构图；API 不支持时降级回方形
    for size in ("1024x1280", "1024x1024"):
        try:
            import requests as _req
            url = f"{AGNES_API_BASE}/images/generations"
            headers = {"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "agnes-image-2.1-flash",
                "prompt": prompt,
                "size": size,
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
                    # 构图归一化后存盘：统一头部位置/占比，保证视频人物大小一致
                    try:
                        normalized = _normalize_portrait_image(Image.open(BytesIO(img_resp.content)))
                        normalized.save(portrait_path, "JPEG", quality=92)
                    except Exception as e:
                        logger.warning(f"写真构图归一化失败，保存原图: {e}")
                        with open(portrait_path, "wb") as f:
                            f.write(img_resp.content)
                    logger.info(f"数字人写真已生成：{avatar_id} → {portrait_path} ({size})")
                    return portrait_path
            logger.warning(f"写真生成返回异常：{data}")
            return None
        except Exception as e:
            # 竖版尺寸不被 API 支持时降级重试方形；网络类错误直接失败
            logger.warning(f"生成数字人写真 {avatar_id} 失败（{size}）: {e}")
            continue
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


_VIDEO_ENCODER_CACHE: str | None = None

def _pick_video_encoder() -> str:
    """选择视频编码器，按平台/设备可用性自动探测：
    - macOS:   h264_videotoolbox（Apple 媒体引擎硬件编码）
    - Linux:   h264_nvenc（NVIDIA GPU，需 nvidia-smi；容器透传 GPU 后生效）
    - 兜底:    libx264 CPU 编码（无 GPU 的容器/CI 等环境）
    结果进程级缓存，避免每次生成视频都探测一次。"""
    global _VIDEO_ENCODER_CACHE
    if _VIDEO_ENCODER_CACHE is None:
        enc = "libx264"
        try:
            out = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=15,
            )
            lines = out.stdout.splitlines()
            if any("h264_videotoolbox" in line for line in lines):
                enc = "h264_videotoolbox"
            elif any("h264_nvenc" in line for line in lines) and shutil.which("nvidia-smi"):
                enc = "h264_nvenc"
        except Exception:
            pass
        _VIDEO_ENCODER_CACHE = enc
    return _VIDEO_ENCODER_CACHE


def _build_portrait_src(avatar: dict):
    """预加载并缩放写真 → (RGBA图, 圆角遮罩, 宽, 高, face_meta)；无写真返回 None。

    自定义形象使用用户上传图片（local_image_path），内置形象用 AI 写真缓存。
    使用 cover 裁剪（等比缩放后居中裁切、裁窗偏上保留头部），杜绝直接拉伸
    造成的脸部变形——1:1 生成图被压扁成 0.8 比例是"AI 感"的重要来源。
    face_meta = 头部中心/宽度（画布坐标）或 None：渲染层据此动态定位眼/嘴/颊彩。
    """
    portrait_path = avatar.get("local_image_path") or (_get_portrait_path(avatar["id"]) if not avatar.get("is_custom") else "")
    if not portrait_path or not os.path.exists(portrait_path):
        return None
    try:
        portrait = Image.open(portrait_path).convert("RGB")
        # 构图归一化：无论源图是 AI 方形写真还是用户上传任意比例，
        # 统一把人物头部锚定到画布上部 1/3、头部占比一致（消除"人物忽远忽近"）
        portrait = _normalize_portrait_image(portrait)
        target_w, target_h = PORTRAIT_NORM_SIZE  # 归一化后即 800x1000，cover 缩放恒等
        # 注意：target 即画布构图基准（人物占宽 = target_w/1280），不能随意增大撑满画面；
        # 800x1000 相比 640x800 保留更多源写真信息（竖版 1024 源 → 78% vs 62.5%），1080p 下更清晰
        scale = max(target_w / portrait.width, target_h / portrait.height)
        nw, nh = int(round(portrait.width * scale)), int(round(portrait.height * scale))
        if (nw, nh) != portrait.size:
            portrait = portrait.resize((nw, nh), Image.LANCZOS)
        x0 = max(0, (nw - target_w) // 2)
        y0 = max(0, min(int((nh - target_h) * 0.30), nh - target_h))  # 裁窗偏上：半身像脸部在画面上部
        portrait = portrait.crop((x0, y0, x0 + target_w, y0 + target_h)).convert("RGBA")
        mask = Image.new("L", (target_w, target_h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, target_w, target_h], radius=48, fill=255)
        # 头部几何（画布坐标）传给渲染层做眼/嘴/颊彩动态定位
        face_meta = None
        try:
            met = _skin_region_metrics(portrait)
            if met:
                face_meta = {"cy": met["cy"], "head_w": met["head_w"]}
        except Exception:
            pass
        return portrait, mask, target_w, target_h, face_meta
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


# ── 逼真化渲染素材：嘴部/眼睑贴图模板 + 摄影棚光影 ─────────────
_MOUTH_TEMPLATES: dict = {}
_EYELID_TEMPLATES: dict = {}
_LIGHT_CACHE: dict = {}
_BLINK_PATTERN: list = []


def _build_blink_pattern(count: int = 260) -> list:
    """确定性眨眼模式：[(间隔秒, 闭眼过程秒)]，间隔 2.2~4.8s 随机（固定种子可复现）。"""
    import random
    rnd = random.Random(20260805)
    return [(rnd.uniform(2.2, 4.8), rnd.uniform(0.13, 0.20)) for _ in range(count)]


def _blink_progress(t: float) -> float:
    """t 时刻的闭眼进度 0~1（三角波 0→1→0），非闭眼期返回 0。

    替代固定 2.8s 周期的机械眨眼：间隔随机，闭眼过程 0.13~0.2s。
    """
    if not _BLINK_PATTERN:
        _BLINK_PATTERN.extend(_build_blink_pattern())
    acc = 0.0
    for gap, dur in _BLINK_PATTERN:
        if t < acc + gap:
            return 0.0
        if t < acc + gap + dur:
            p = (t - acc - gap) / dur
            return 1.0 - abs(2.0 * p - 1.0)
        acc += gap + dur
    return 0.0


def _get_mouth_template(open_idx: int, round_idx: int) -> Image.Image:
    """嘴部 RGBA 模板（128x96 基模板，按开度 6 档 x 圆度 4 档缓存）。

    真实唇形：下唇饱满渐变（上缘暗→下缘亮）+ 上唇深色 + 唇间缝 + 高光 + 嘴角阴影，
    边缘高斯羽化融入皮肤；替代原来的"椭圆+直线"贴纸式画法。
    """
    key = (open_idx, round_idx)
    if key not in _MOUTH_TEMPLATES:
        import numpy as np
        W, H = 128, 96
        open_ratio = open_idx / 5.0
        round_ratio = 0.25 + 0.75 * (round_idx / 3.0)
        mouth_w = int(36 + 28 * round_ratio)
        mouth_h = int(5 + 30 * open_ratio)
        cx, cy = W // 2, H // 2
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        arr = np.zeros((H, W, 4), dtype=np.float32)
        # 下唇：宽扁椭圆，垂直渐变（上缘暗 → 下缘亮），体现唇部体积
        dxx = (x - cx) / mouth_w
        dyy = (y - (cy + mouth_h * 0.45)) / max(mouth_h * 0.85, 1e-4)
        lower = (dxx * dxx + dyy * dyy) <= 1.0
        t = np.clip((y - (cy - mouth_h * 0.4)) / max(mouth_h * 1.6, 1e-4), 0, 1)
        lip_low = np.empty((H, W, 4), dtype=np.float32)
        lip_low[..., 0] = (108 + 62 * t) / 255.0
        lip_low[..., 1] = (56 + 44 * t) / 255.0
        lip_low[..., 2] = (66 + 46 * t) / 255.0
        lip_low[..., 3] = 1.0
        arr[lower] = lip_low[lower]
        # 上唇：位置偏上的深色椭圆，覆盖下唇上缘形成唇间暗缝
        dxxu = (x - cx) / (mouth_w * 1.04)
        dyyu = (y - (cy - mouth_h * 0.62)) / max(mouth_h * 0.60, 1e-4)
        upper = (dxxu * dxxu + dyyu * dyyu) <= 1.0
        arr[upper & ~lower, :3] = np.array([86, 44, 56], dtype=np.float32) / 255.0
        arr[upper & ~lower, 3] = 1.0
        # 唇间缝：上唇下缘的深色细线
        seam = (np.abs(y - (cy + mouth_h * 0.05)) < 1.8) & (np.abs(x - cx) <= mouth_w * 0.9)
        arr[seam, :3] = np.array([44, 24, 30], dtype=np.float32) / 255.0
        arr[seam, 3] = 1.0
        # 下唇高光：偏左的小椭圆（模拟单一主光方向）
        hx = (x - (cx + mouth_w * 0.26)) / max(mouth_w * 0.28, 1e-4)
        hy = (y - (cy + mouth_h * 0.95)) / max(mouth_h * 0.30, 1e-4)
        hl = (hx * hx + hy * hy <= 1.0) & lower
        arr[hl, :3] = arr[hl, :3] * 0.35 + 1.0 * 0.65
        arr[hl, 3] = np.maximum(arr[hl, 3], 0.80)
        # 嘴角阴影：两端加深
        for s in (-1.0, 1.0):
            ex = (x - (cx + s * mouth_w * 0.95)) / 2.2
            ey = (y - (cy + mouth_h * 0.15)) / 3.2
            corner = (ex * ex + ey * ey <= 1.0) & (lower | upper)
            arr[corner, :3] *= 0.55
            arr[corner, 3] = np.maximum(arr[corner, 3], 0.85)
        img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGBA")
        # 羽化边缘：alpha 通道高斯模糊，让唇贴图融入皮肤而非硬边
        img.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(2.2)))
        _MOUTH_TEMPLATES[key] = img
    return _MOUTH_TEMPLATES[key]


def _get_eyelid_template(eye_w: int) -> Image.Image:
    """上眼睑下压遮罩（暗肤色渐变 + 下缘睫毛线），按宽度缓存。

    用于模拟自然闭眼：上眼睑从上往下覆盖，而非画一道"伤口线"。
    """
    key = eye_w
    if key not in _EYELID_TEMPLATES:
        import numpy as np
        w = eye_w
        h = max(8, int(w * 0.32))
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        arr = np.zeros((h, w, 4), dtype=np.float32)
        t = y / max(h - 1, 1)  # 0 顶部 → 1 底部
        edge = np.clip(1 - (x / max(w - 1, 1) - 0.5) ** 2 * 3.2, 0, 1)  # 两端收窄
        # 肤色渐变压暗（上眼睑投影），顶部最深、底部贴近睫毛
        arr[..., 0] = (96 - 34 * t) / 255.0
        arr[..., 1] = (62 - 22 * t) / 255.0
        arr[..., 2] = (70 - 26 * t) / 255.0
        arr[..., 3] = np.clip(0.95 - 0.5 * t, 0, 1) * edge
        # 下缘睫毛线：2px 深色
        lash = (y >= h - 2.5) & (np.abs(x - w / 2) <= w * 0.46)
        arr[lash, :3] = 30 / 255.0
        arr[lash, 3] = np.maximum(arr[lash, 3], 0.9)
        img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGBA")
        img.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(1.6)))
        _EYELID_TEMPLATES[key] = img
    return _EYELID_TEMPLATES[key]


def _get_studio_lighting(w: int, h: int):
    """摄影棚光影预计算（numpy，按 (w,h) 缓存）→ (主光spot, 地面反光floor, 暗角vig)。

    主光：聚焦人物站位（画面左 26%、垂直 40%）的径向聚光，营造"灯光打在人身上"的
    摄影棚关系；地面反光：底部渐亮反射带；暗角：四角压暗，电影镜头感。
    替代"均匀撒粒子"的 PPT 式背景。
    """
    key = (w, h)
    if key not in _LIGHT_CACHE:
        import numpy as np
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        spot_cx, spot_cy = w * 0.26, h * 0.40
        spot_r = max(w, h) * 0.95
        d2 = ((x - spot_cx) ** 2 + (y - spot_cy) ** 2) / (spot_r * spot_r)
        spot = np.exp(-d2 * 3.0)
        floor = np.clip((y - h * 0.74) / max(h * 0.26, 1), 0, 1) ** 1.4
        vx = np.clip(np.abs(x - w * 0.5) / max(w * 0.5, 1), 0, 1) ** 2
        vy = np.clip(np.abs(y - h * 0.5) / max(h * 0.5, 1), 0, 1) ** 2
        vig = np.clip(vx + vy, 0, 1) ** 1.5
        _LIGHT_CACHE[key] = (spot, floor, vig)
    return _LIGHT_CACHE[key]


def _apply_studio_lighting(img: Image.Image, t: float) -> Image.Image:
    """把摄影棚光影叠加到背景帧（人物叠加之前）：主光脉动 + 地面反光 + 暗角。"""
    import math
    import numpy as np
    spot, floor, vig = _get_studio_lighting(img.width, img.height)
    arr = np.asarray(img).astype(np.float32)
    light = 1.0 + 0.10 * spot * (0.92 + 0.08 * math.sin(t * 0.9))
    light = light * (1.0 + 0.05 * floor) * (1.0 - 0.20 * vig)
    # 只乘 RGB 三通道：RGBA 帧必须保留 alpha（否则半透明图层被算入光影）
    arr[..., :3] = np.clip(arr[..., :3] * light[..., None], 0, 255)
    return Image.fromarray(arr.astype(np.uint8), img.mode)


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
        base = base * (1 + 0.03 * breath)  # 呼吸幅度收敛（0.06→0.03），避免背景闪烁感
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")


# image 类型背景：程序化"拟摄影"底图（低分辨率模糊色块 + 纵向光感 + 噪点纹理）
_SCENE_BG_CACHE: dict = {}


def _make_scene_background(bg_id: str, w: int, h: int) -> Image.Image:
    """程序化拟摄影背景：多层模糊色块模拟真实场景光感（办公室/演播室/自然）。

    image 类型背景不再退化为纯色渐变——按场景调色板绘制大半径模糊椭圆色块
    （模拟窗户光/聚光灯/树影），叠加纵向明暗与微弱噪点，获得"照片级"质感。
    低分辨率绘制 + 放大，模糊成本可控；结果按 (bg_id, w, h) 缓存、固定种子可复现。
    """
    import random
    import numpy as np
    palettes = {
        # 场景 → 基色 + [(色块颜色, 数量权重), ...]（权重高 = 色块更多更明显）
        "office": [("#f5f0e6", 1.0), ("#e2d9c8", 0.8), ("#cbb99f", 0.5), ("#ffffff", 0.7)],
        "studio": [("#17243f", 1.0), ("#2b4068", 0.7), ("#0e1728", 0.6), ("#5a7ec2", 0.35)],
        "nature": [("#2d4b39", 1.0), ("#416f52", 0.7), ("#1c3025", 0.6), ("#e8f0d8", 0.4)],
    }
    colors = palettes.get(bg_id, palettes["studio"])
    sw, sh = max(8, w // 4), max(8, h // 4)
    rnd = random.Random(2026 + len(bg_id))
    base = Image.new("RGB", (sw, sh), colors[0][0])
    d = ImageDraw.Draw(base)
    for color, weight in colors[1:]:
        for _ in range(int(2 + 3 * weight)):
            cw = rnd.uniform(0.25, 0.9) * sw
            ch = rnd.uniform(0.2, 0.7) * sh
            cx = rnd.uniform(-0.1, 1.1) * sw
            cy = rnd.uniform(-0.1, 1.1) * sh
            d.ellipse([cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2], fill=color)
    base = base.filter(ImageFilter.GaussianBlur(max(sw, sh) // 6)).resize((w, h), Image.LANCZOS)
    # 纵向光感：上方亮（天光/顶光）、下方压暗（地面层次）；弱噪点消除色带
    arr = np.asarray(base).astype(np.float32)
    yy = np.linspace(1.0, 0.78, h, dtype=np.float32)[:, None, None]
    arr = np.clip(arr * yy, 0, 255)
    arr += np.random.default_rng(42 + len(bg_id)).normal(0, 6, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _build_bg_src(bg: dict, w: int, h: int) -> Image.Image | None:
    """image 类型背景 → 拟摄影底图（按 (bg_id, w, h) 缓存）；渐变背景返回 None。"""
    if not bg or bg.get("type") != "image":
        return None
    key = f"{bg.get('id')}:{w}x{h}"
    if key not in _SCENE_BG_CACHE:
        _SCENE_BG_CACHE[key] = _make_scene_background(bg.get("id", ""), w, h)
    return _SCENE_BG_CACHE[key]


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
def _get_particles(count: int = 24) -> list:
    """确定性粒子系统（固定种子，按时间纯函数式计算，无随机状态）。

    数量/亮度/速度收敛（42→24、亮度减半、速度变慢），避免"光污染"盖过人物。
    """
    global _PARTICLES_CACHE
    if _PARTICLES_CACHE is None:
        import random
        rnd = random.Random(2026)
        _PARTICLES_CACHE = [
            {
                "x": rnd.uniform(0.03, 0.97),
                "y": rnd.uniform(0.0, 1.0),
                "r": rnd.uniform(1.0, 2.4),
                "speed": rnd.uniform(10, 22),
                "phase": rnd.uniform(0, 6.283),
                "bright": rnd.uniform(0.15, 0.35),
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
    bg_img: Image.Image | None = None,
) -> Image.Image:
    """绘制一帧：拟摄影/动态渐变背景 + 粒子光斑 + 人物动态（说话律动/眨眼/字级口型）+ 卡拉OK字幕。"""
    import math
    S = width / 1280.0  # 渲染缩放系数（Ken Burns 放大画布时保持坐标比例）

    # ── 1. 背景底图：image 类型用拟摄影底图（静态，动态感由光斑/光影承担），
    #      渐变类型保持动态亮度呼吸 ──
    if bg_img is not None:
        img = bg_img.copy()
    else:
        breath = 0.5 + 0.5 * math.sin(t * 0.8)
        img = _make_gradient(width, height, bg_hex, breath)
    # 半透明 UI 元素（粒子/名片/字幕/底条/进度条）画到独立 RGBA 图层：
    # ImageDraw 无 alpha 合成能力（RGBA 图上直接覆盖 RGB+写 alpha），
    # 画到底图会把半透明色覆盖成纯色（曾致底部 bar 纯黑盖住嘴部贴图）
    ui = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ui)

    # ── 2. 高斯柔光斑（缓慢漂移，营造摄影棚光效）──
    for i, (gx, gy, scale) in enumerate([
        (0.82, 0.20, 1.6), (0.12, 0.72, 1.3), (0.58, 0.92, 1.9),
    ]):
        layer = _get_glow_template(150, scale)
        cx = int(width * gx + math.sin(t * 0.3 + i * 2.1) * 40 * S)
        cy = int(height * gy + math.cos(t * 0.25 + i * 1.7) * 30 * S)
        img.paste(layer, (cx - layer.width // 2, cy - layer.height // 2), layer)

    # ── 3. 漂浮粒子（像直播间的氛围光点，画在 UI 图层参与 alpha 合成）──
    _draw_particles(ui, t)

    # ── 3.5 摄影棚光影：主光聚焦人物 + 地面反光 + 暗角（背景上、人物下）──
    img = _apply_studio_lighting(img, t)

    # 说话能量 → 驱动全身律动（能量高=说话中：幅度加大；静音：回归静态呼吸）
    talk = min(1.0, energy * 1.6)
    sway_t = math.sin(t * 1.15)
    breathe_t = math.sin(t * 1.3)
    glow_alpha = max(8, min(45, int(22 + 16 * math.sin(t * 1.9))))
    # 入场动画：前 0.8s 人物从左侧滑入（ease-out，开局明显动起来）
    enter_ease = 1 - (1 - min(1.0, t / 0.8)) ** 3

    # ── 4. 左侧人物：写真 + 动态（入场滑入/呼吸缩放/点头倾斜/眨眼/嘴型开合）──
    if portrait:
        p_base, p_mask_base, p_base_w, p_base_h, face_meta = portrait
        # 头部几何（归一化画布 800x1000 坐标）→ 眼/嘴/颊彩动态定位，
        # 适配不同写真构图差异（固定比例在构图漂移时会贴错位）
        bx = p_base_w / 800.0
        by = p_base_h / 1000.0
        if face_meta:
            cy_c = face_meta["cy"]
            head_h_c = face_meta["head_w"] * 1.30  # 头高估计（检测带宽含肩，按唇色实测校准）
            eye_y_c = cy_c - 12            # 眼 ≈ 肤色区上界（眉骨附近）
            mouth_y_c = cy_c + head_h_c * 0.15   # 唇：实测校准（唇-头中心差 ≈ 0.15 x 头高）
            cheek_y_c = cy_c + head_h_c * 0.08   # 颊：眼唇之间
            cheek_dx_c = face_meta["head_w"] * 0.32
        else:
            eye_y_c, mouth_y_c, cheek_y_c, cheek_dx_c = 240, 340, 290, 140
        # 呼吸缩放（真人幅度 ~1.2%，收敛气球感）+ 说话节奏起伏
        breath_scale = 1 + 0.012 * breathe_t + 0.010 * talk * math.sin(t * 3.2)
        p_w = max(20, int(p_base_w * breath_scale * S))
        p_h = max(20, int(p_base_h * breath_scale * S))
        # 点头倾斜：小角度 + 高频微颤（真人肌肉松弛感，避免纸片式大摆）
        tilt = 0.9 * sway_t * (1.0 + 0.9 * talk) + 0.45 * talk * math.sin(t * 2.9) + 0.22 * math.sin(t * 5.1)
        nod_pivot = (int(p_w / 2), p_h)  # 底部中心为旋转轴
        p_img = p_base.resize((p_w, p_h), Image.LANCZOS).rotate(
            tilt, resample=Image.BILINEAR, center=nod_pivot)
        p_mask = p_mask_base.resize((p_w, p_h), Image.BILINEAR).rotate(
            tilt, resample=Image.BILINEAR, center=nod_pivot)
        # 垂直浮动 + 水平摇摆（幅度收敛，说话时叠加轻微起伏）
        float_offset = int((breathe_t * 6 + talk * 4 * math.sin(t * 2.8)) * S)
        sway_offset = int((sway_t * 5 + talk * 4 * math.cos(t * 2.2)) * S)
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

        # 自然眨眼：随机间隔（2.2~4.8s）+ 上眼睑渐变遮罩下压（替代"画线"）
        close = _blink_progress(t)
        if close > 0.03:
            eye_w = max(6, int(p_w * 0.135))
            eye_y = py + int(eye_y_c * by * breath_scale)
            lid = _get_eyelid_template(eye_w)
            lid_h = max(2, int(lid.height * min(close * 1.25, 1.0)))
            lid_use = lid.crop((0, 0, lid.width, lid_h)) if lid_h < lid.height else lid
            for ex in (px + int(p_w * 0.30), px + int(p_w * 0.58)):
                img.paste(lid_use, (ex - lid_use.width // 2, eye_y - lid_h), lid_use)

        # 颊彩表情层：柔和粉彩脸颊（说话时随能量微亮），提升生气感
        cheek_alpha = int(22 + 14 * talk)
        cheek_w = max(8, int(p_w * 0.17))
        cheek_h = max(4, int(cheek_w * 0.55))
        cheek_y = py + int(cheek_y_c * by * breath_scale)
        cheek = Image.new("RGBA", (cheek_w * 2 + 4, cheek_h * 2 + 4), (0, 0, 0, 0))
        cd = ImageDraw.Draw(cheek)
        for s in (-1.0, 1.0):
            cex = cheek_w + 2 + int(s * cheek_dx_c * bx * breath_scale)
            cd.ellipse([cex - cheek_w, 2, cex + cheek_w, 2 + cheek_h * 2],
                       fill=(240, 120, 130, cheek_alpha))
        cheek = cheek.filter(ImageFilter.GaussianBlur(cheek_w * 0.55))
        img.paste(cheek, (px + int(p_w * 0.5) - cheek.width // 2, cheek_y - cheek.height // 2), cheek)

        # 逼真口型：量化嘴部模板（开度 6 档 x 圆度 4 档），羽化贴图融入皮肤；
        # open 控制开度、round 控制圆度，仍由拼音时间轴逐字驱动；
        # 位置由头部几何动态定位（原固定 0.805 在构图漂移时贴到颈部/胸口）
        mouth_open_v, roundness = mouth_shape
        aspect = p_base_w / p_base_h
        if (not avatar.get("is_custom") or 0.55 <= aspect <= 1.05) and mouth_open_v > 0.05:
            open_idx = min(5, int(round(mouth_open_v * 5)))
            round_idx = min(3, int(round(roundness * 3)))
            mw = max(6, int(p_w * (0.20 + 0.08 * roundness)))
            mh = max(3, int(p_h * 0.032 * mouth_open_v * (0.6 + 0.8 * roundness)))
            mouth_layer = _get_mouth_template(open_idx, round_idx).resize(
                (mw, mh), Image.LANCZOS,
            )
            mx = px + int(p_w * 0.49)
            my = py + int(mouth_y_c * by * breath_scale)
            img.paste(mouth_layer, (mx - mw // 2, my - mh // 2), mouth_layer)

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

    return Image.alpha_composite(img.convert("RGBA"), ui).convert("RGB")


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
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",   # Linux 容器：文泉驿（简体字型，优先于 Noto JP 变体）
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux 容器：Noto CJK
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

    # 写真预加载（避免每帧重复 IO/缩放）；image 类型背景预构建拟摄影底图
    portrait = _build_portrait_src(avatar)
    bg_img = _build_bg_src(bg, RENDER_W, RENDER_H)

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
    # 水印字体只加载一次（原实现每帧重复加载字体文件）
    wm_font = _load_font(int(18 * OUT_W / 1280), FONT_CANDIDATES) if watermark else None

    def _render_one(f: int) -> None:
        t = f / fps
        progress = min(1.0, t / duration) if duration > 0 else 1.0
        energy = energy_curve[min(f, len(energy_curve) - 1)] if energy_curve else 0.0
        mouth_shape = _mouth_shape_at(script_timeline, t)
        frame = _render_frame(
            avatar=avatar, bg_hex=bg_hex, fonts=fonts,
            portrait=portrait, text_lines=text_lines,
            t=t, progress=progress, width=RENDER_W, height=RENDER_H,
            energy=energy, mouth_shape=mouth_shape, bg_img=bg_img,
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

    try:
        # 帧渲染并行化：PIL/numpy 的 C 层操作释放 GIL，线程池可吃满多核（帧间无依赖）
        render_workers = min(os.cpu_count() or 4, 8)
        with ThreadPoolExecutor(max_workers=render_workers) as pool:
            for _ in pool.map(_render_one, range(total_frames)):
                pass

        # ffmpeg：帧序列 + 音频 → MP4
        # 编码器自动选择：Apple 芯片用 VideoToolbox 硬件编码（快 5~10 倍），
        # Linux 容器等无硬件编码器环境自动回退 libx264 CPU 编码
        try:
            enc = _pick_video_encoder()
            # 画质滤镜链：锐化（unsharp）+ 对比度/饱和度分级（eq），
            # 去除 JPG 帧软糊感；硬件编码器（videotoolbox/nvenc）不支持 qscale
            # （ffmpeg 8.x 报错）改用目标码率模式，libx264 用 crf 18
            quality_args = (["-b:v", "6M", "-maxrate", "8M", "-bufsize", "12M"]
                            if enc != "libx264" else ["-crf", "18"])
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", os.path.join(frames_dir, "%04d.jpg"),
                    "-i", audio_path,
                    "-c:v", enc, "-pix_fmt", "yuv420p",
                    "-vf", "unsharp=5:5:0.6:5:5:0.0,eq=contrast=1.06:saturation=1.10",
                    *quality_args,
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


def _generate_one(req: GenerateRequest, user: str, uid: str, role: str = "",
                  progress: Callable[[float, str], None] | None = None) -> dict:
    """单条数字人视频生成流水线（供单条接口与批量任务复用）。

    流程：
    1. 文案预处理（LLM优化口播文案流畅度）
    2. TTS配音（调用配音工坊音频生成）
    3. 视频合成（数字人形象+配音+背景合成为口播视频）

    progress: 可选进度回调 (percent 0-100, stage 文案)，异步任务模式实时回报进度。
    """
    start = datetime.now()

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

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
    _report(15, "文案已就绪，正在合成配音…")

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
        _report(20, "正在合成配音…")
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
    _report(55, "配音完成，正在渲染数字人视频…")
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
            _report(85, "视频渲染完成，正在保存记录…")
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
    _report(95, "记录已保存")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("digital_human", len(req.text), len(optimized_text), elapsed,
              success=not error_msg)
    _report(100, "生成完成")

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


def _precheck_generate(req: GenerateRequest, uid: str, user: str) -> None:
    """异步提交前快速失败预检：违规词 / 今日额度 / 素材参数（不消耗配额，执行时再扣）。"""
    try:
        from content_strategy import _scan_text
        hits = _scan_text(req.text)
    except Exception:
        hits = []
    lower_text = req.text.lower()
    hard_hits = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower_text]
    if hard_hits:
        raise HTTPException(400, f"文案含违规词（{', '.join(hard_hits[:6])}），已拦截生成，请修改后重试")
    from common.auth import get_quota_info
    qi = get_quota_info(uid) or {}
    remaining = qi.get("remaining_today")
    if remaining is not None and remaining <= 0:
        raise HTTPException(402, "今日数字人生成次数已用完，升级会员获取更多额度（专业版每日 200 次，至尊版不限量）")
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
    if not next((b for b in BACKGROUNDS if b["id"] == req.background_id), None):
        raise HTTPException(400, f"未知背景: {req.background_id}")


@router.post("/generate")
async def generate(
    req: GenerateRequest,
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务模式"),
    current_user: dict = require_auth(),
):
    """数字人口播视频生成 — 文案→配音→视频合成流水线。

    默认异步任务模式：立即返回 task_id，后台 worker 执行（GET /api/tasks/{task_id}
    查进度/结果，GET /api/tasks?type=dh_generate 看任务列表，POST /api/tasks/{id}/retry
    重试），页面可关闭无需等待；sync=true 时同步执行（兼容旧客户端/脚本）。
    批量生产请使用 POST /api/digital-human/batch（多文案后台逐条生成）。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    # 快速失败预检：违规词 / 额度 / 素材参数，无效请求不进入任务队列
    _precheck_generate(req, uid, user)
    if sync:
        # 同步模式：保留原用户级并发限制（同用户同时仅 1 条生成中）
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
    # 异步任务模式：同用户并发限制由任务框架原子校验（register_handler user_limit=1）
    task = create_task("dh_generate", req.model_dump(), username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "生成任务已提交，可关闭页面，完成后在「我的生成任务」查看",
        "task": task,
    }


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


@router.post("/portraits/regenerate")
async def regenerate_portraits(current_user: dict = require_auth()):
    """管理员：按升级后的真实感提示词重新生成全部内置数字人写真。

    逐形象串行调用（避免同时打爆图片 API），返回成功/失败清单。
    """
    from admin_api import _check_admin
    _check_admin(current_user)
    ok, failed = [], []
    for avatar in AVATARS:
        try:
            if _generate_portrait(avatar["id"]):
                ok.append(avatar["id"])
            else:
                failed.append(avatar["id"])
        except Exception:
            logger.exception(f"重新生成写真失败 {avatar['id']}")
            failed.append(avatar["id"])
    return {"ok": ok, "failed": failed}


# ══════════════════════════════════════════════════════════════
# 通用异步任务框架接入：单条生成为后台任务（默认异步，页面可关闭）
# ══════════════════════════════════════════════════════════════

def _dh_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：接收 GenerateRequest 参数，走完整生成流水线并实时回报进度。

    失败/配额不足时抛 HTTPException，由框架捕获记录 error / error_code（402 → 前端引导升级）。
    """
    req = GenerateRequest(**payload)
    update(5, "任务已受理，正在校验参数…")
    return _generate_one(
        req,
        ctx.get("username", ""),
        ctx.get("user_id", ""),
        ctx.get("role", ""),
        progress=update,
    )


register_handler("dh_generate", _dh_generate_handler, user_limit=1)
