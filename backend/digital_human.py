"""AI数字人/虚拟主播 — 文案→配音→口播视频合成。

- GET  /api/digital-human/avatars   内置8个虚拟形象库
- GET  /api/digital-human/voices    可选声音列表（复用配音工坊音色）
- POST /api/digital-human/generate  文案+形象+声音+背景 → 生成口播视频
- GET  /api/digital-human/records   历史生成记录
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db, get_db_context
from common.llm import call_llm, log_usage
from common.media_check import is_valid_audio as _valid_audio, is_valid_video as _valid_video
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
    {
        "id": "en-US-ChristopherNeural",
        "name": "Christopher",
        "gender": "男",
        "style": "英文男声，沉稳有力",
        "emoji": "🇬🇧",
    },
]

# ── 背景模板 ──────────────────────────────────────────────────
BACKGROUNDS = [
    {"id": "office", "name": "现代办公室", "type": "image", "color": "#1a1a2e"},
    {"id": "studio", "name": "简约演播室", "type": "image", "color": "#16213e"},
    {"id": "nature", "name": "自然风景", "type": "image", "color": "#0f3460"},
    {
        "id": "tech",
        "name": "科技蓝幕",
        "type": "gradient",
        "color": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    },
    {
        "id": "warm",
        "name": "温馨暖调",
        "type": "gradient",
        "color": "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
    },
    {
        "id": "dark",
        "name": "暗黑质感",
        "type": "gradient",
        "color": "linear-gradient(135deg, #434343 0%, #000000 100%)",
    },
]

# ── 场景模板 ──────────────────────────────────────────────────
SCENE_TEMPLATES = [
    {
        "id": "product",
        "name": "产品介绍",
        "desc": "突出产品卖点，节奏明快",
        "voice_hint": "zh-CN-YunjianNeural",
        "speed_hint": 1.05,
    },
    {
        "id": "course",
        "name": "课程讲解",
        "desc": "结构化讲解，娓娓道来",
        "voice_hint": "zh-CN-XiaoxiaoNeural",
        "speed_hint": 0.95,
    },
    {
        "id": "news",
        "name": "新闻播报",
        "desc": "字正腔圆，专业播报",
        "voice_hint": "zh-CN-YunyangNeural",
        "speed_hint": 1.0,
    },
    {
        "id": "livestream",
        "name": "直播带货",
        "desc": "感染力强，促单话术",
        "voice_hint": "zh-CN-YunjianNeural",
        "speed_hint": 1.1,
    },
    {
        "id": "story",
        "name": "故事讲述",
        "desc": "情感丰富，引人入胜",
        "voice_hint": "zh-CN-XiaoxiaoNeural",
        "speed_hint": 0.9,
    },
]

# ── 行业模板库 ──────────────────────────────────────────────
# 每模板 = 场景背景（scene_id/background_id/voice_hint/speed_hint，供前端一键填充）
#          + 字幕样式（position: right=右侧名片下 / center=底部居中大字）
#          + 片头片尾引导语 + 推荐文案结构（脚本助手按结构生成）
INDUSTRY_TEMPLATES = [
    {
        "id": "live_shopping",
        "name": "带货种草",
        "emoji": "🛍️",
        "desc": "痛点钩子+卖点3连+促单引导，暖调背景抓眼球",
        "scene_id": "livestream",
        "background_id": "warm",
        "voice_hint": "zh-CN-YunjianNeural",
        "speed_hint": 1.1,
        "subtitle": {"position": "center", "color": "#ffb84d", "font_size": 34},
        "opening": "好物严选 · 真实测评",
        "closing": "点击关注，好物不错过",
        "script_structure": "开头痛点钩子（3秒留人）→ 产品卖点3条（每条配使用场景）→ 价格/福利对比 → 促单引导",
        "script_sample": "家人们，你们是不是也遇到过这样的问题？{产品}到手不会用、效果看不见，钱白花了还糟心！今天这款{产品}，三大优势直接拉满：第一，操作简单，三步就能上手；第二，效果肉眼可见，七天就有变化；第三，性价比超高，不到一顿饭钱。现在下单还送专属礼包，错过真的会后悔！",
    },
    {
        "id": "knowledge",
        "name": "知识口播",
        "emoji": "📚",
        "desc": "提问开场+干货3点+金句收尾，科技蓝幕显专业",
        "scene_id": "course",
        "background_id": "tech",
        "voice_hint": "zh-CN-YunxiNeural",
        "speed_hint": 1.0,
        "subtitle": {"position": "right", "color": "#4dd0e1", "font_size": 32},
        "opening": "知识干货 · 每天3分钟",
        "closing": "收藏转发，让更多人看到",
        "script_structure": "开头提问（制造好奇）→ 核心知识3点（由浅入深）→ 案例佐证 → 总结金句",
        "script_sample": "为什么你学了那么多方法，{主题}还是做不好？问题不在方法，而在顺序。第一，先定目标再找方法，方向错了努力白费；第二，小步快跑持续验证，一次吃不成胖子；第三，定期复盘迭代优化。我一个学员照这套逻辑，三个月就完成了别人一年的进度。方法很简单，难在坚持，收藏这条视频，明天就开始！",
    },
    {
        "id": "news",
        "name": "新闻播报",
        "emoji": "📰",
        "desc": "导语+事实+观点三段式，演播室背景显权威",
        "scene_id": "news",
        "background_id": "studio",
        "voice_hint": "zh-CN-YunyangNeural",
        "speed_hint": 1.0,
        "subtitle": {"position": "center", "color": "#ffd54f", "font_size": 32},
        "opening": "今日资讯 · 权威速递",
        "closing": "持续关注，第一时间掌握",
        "script_structure": "导语（一句话概括事件）→ 事件经过（时间线+关键细节）→ 背景分析 → 结尾观点",
        "script_sample": "各位观众朋友，大家好！今天是{日期}，欢迎收看本期节目。近日，{主题}引发广泛关注。据记者了解，事件发生后，相关部门第一时间启动应急预案，各项工作正在有序推进。专家分析认为，这一变化将对行业产生深远影响，未来发展趋势值得持续观察。我们将继续跟进报道，第一时间为您带来最新消息。",
    },
    {
        "id": "course",
        "name": "课程讲解",
        "emoji": "🎓",
        "desc": "概念引入+分步拆解+小结回顾，办公室背景亲和",
        "scene_id": "course",
        "background_id": "office",
        "voice_hint": "zh-CN-XiaoxiaoNeural",
        "speed_hint": 0.95,
        "subtitle": {"position": "right", "color": "#81c784", "font_size": 30},
        "opening": "系统课程 · 循序渐进",
        "closing": "点赞收藏，反复学习",
        "script_structure": "引入概念（生活化类比）→ 分步讲解（每步一个小结）→ 常见误区 → 课后小结",
        "script_sample": "同学们好，欢迎来到{课程名}。很多人觉得{主题}很难，其实它就像学做饭，掌握了步骤就不难。第一步，理解核心概念，就像先认识食材；第二步，动手练习，就像下锅翻炒，熟能生巧；第三步，总结常见误区，避免踩坑。今天我们用三个例子，把每一步都讲透。课程最后还有配套练习，记得做笔记！",
    },
    {
        "id": "brand",
        "name": "品牌介绍",
        "emoji": "🏢",
        "desc": "故事开场+优势矩阵+愿景收尾，演播室大气稳重",
        "scene_id": "story",
        "background_id": "studio",
        "voice_hint": "zh-CN-YunjianNeural",
        "speed_hint": 0.95,
        "subtitle": {"position": "center", "color": "#ffd54f", "font_size": 36},
        "opening": "品牌故事 · 匠心品质",
        "closing": "了解更多，欢迎咨询",
        "script_structure": "品牌故事（创始人初心）→ 核心优势3点（数据支撑）→ 产品/服务矩阵 → 品牌愿景口号",
        "script_sample": "五年前，我们只是一个小团队，怀着一个朴素的愿望：让{行业}变得简单一点。从第一版产品到如今服务十万家企业，我们始终坚持三件事：一是技术领先，每年研发投入占比超过百分之三十；二是客户为先，专属顾问一对一服务；三是长期主义，不做一锤子买卖。未来，我们会继续深耕{行业}，让每一个客户都能享受科技带来的效率。",
    },
    {
        "id": "vlog",
        "name": "生活记录",
        "emoji": "🏞️",
        "desc": "场景叙事+真实感受+互动结尾，自然风景背景亲和",
        "scene_id": "story",
        "background_id": "nature",
        "voice_hint": "zh-CN-XiaoxiaoNeural",
        "speed_hint": 0.95,
        "subtitle": {"position": "center", "color": "#ffffff", "font_size": 30},
        "opening": "生活记录 · 此刻分享",
        "closing": "点赞关注，和我一起记录生活",
        "script_structure": "场景引入（时间地点）→ 过程叙述（细节+感受）→ 情绪转折/感悟 → 互动结尾",
        "script_sample": "今天带大家来到{地点}，这里是我一直想来的地方。刚下车，就被眼前的风景震撼到了，风很轻，空气里有青草的味道。沿着小路走了二十分钟，路过一片开满花的山坡，忍不住停下来拍了好久。突然觉得，生活里那些忙碌的日子，都值得被这样的瞬间治愈。你们最近有没有被什么风景治愈过？评论区告诉我！",
    },
    {
        "id": "corporate",
        "name": "企业宣传",
        "emoji": "🏆",
        "desc": "实力背书+解决方案+邀约合作，暗黑质感显高端",
        "scene_id": "product",
        "background_id": "dark",
        "voice_hint": "zh-CN-YunjianNeural",
        "speed_hint": 0.95,
        "subtitle": {"position": "center", "color": "#ffd54f", "font_size": 34},
        "opening": "实力企业 · 值得信赖",
        "closing": "合作咨询，欢迎联系",
        "script_structure": "实力背书（资质/数据）→ 解决方案（针对痛点）→ 成功案例 → 邀约合作",
        "script_sample": "{企业名}，专注{行业}领域十五年，服务客户超过三千家，行业资质齐全，屡获权威认证。面对业务增长慢、管理效率低这些痛点，我们提供一站式解决方案：从{方案一}到{方案二}，全流程数字化管理，平均帮客户提升百分之四十的效率。某头部企业采用后，三个月业绩翻倍。如果您也有同样的困扰，欢迎联系我们，定制专属方案。",
    },
    {
        "id": "quote",
        "name": "情感语录",
        "emoji": "💫",
        "desc": "共情开场+故事铺陈+金句升华，暗调氛围感强",
        "scene_id": "story",
        "background_id": "dark",
        "voice_hint": "zh-CN-XiaoxiaoNeural",
        "speed_hint": 0.9,
        "subtitle": {"position": "center", "color": "#ffffff", "font_size": 36},
        "opening": "深夜电台 · 陪你说说话",
        "closing": "愿你被世界温柔以待",
        "script_structure": "共情开场（点出情绪）→ 故事铺陈（具体细节）→ 情绪转折 → 金句升华",
        "script_sample": "你有没有过这样的时刻？明明很累，却还要笑着回答没事。成年人的世界，好像连崩溃都要挑时间。那天加完班回家，看到楼下卖馄饨的大叔还在出摊，他笑着说：热乎的，来一碗？那一刻我突然释怀了。原来生活从来不会亏待认真活着的人，只是你要先学会，对自己温柔一点。晚安，愿你今夜好梦。",
    },
]


# ── AI 写真肖像生成 ─────────────────────────────────────────
from common.helpers import _aggregate_compute_results, _execute_common_step, _execute_compute_step, _execute_single_step, _execute_step, _finalize_common_operation, _finalize_results, _finalize_step_results, _initialize_compute_context, _prepare_common_context, _prepare_context, _prepare_step_context, _notify_progress

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
        (diff > 0.04)
        & (diff < 0.55)  # 饱和度适中
        & (mx > 0.45)
        & (mx < 0.98)  # 亮度区间（排除纯白/纯黑）
        & (R >= G)
        & (G >= B * 0.72)
        & (G <= B * 1.45)  # 橙黄主导 R>G>B
        & (R - B > 0.06)
        & (np.abs(R - G) > 0.03)  # 色相偏红黄
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


def _generate_portrait(avatar_id: str, uid: str = "") -> str | None:
    """调用 AI 图片生成 API 为指定数字人生成写真肖像。

    返回本地文件路径，失败返回 None。
    uid: 用户 id，用于回退用户图片模型偏好（本地版不写死模型）。
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

    from common.config import AGNES_API_BASE, AGNES_API_KEY, IMAGE_MODEL, require_model, resolve_api_key, resolve_api_base
    from common.llm import api_error_detail

    if not resolve_api_key():
        logger.warning("未配置中转站 API Key，无法生成数字人写真")
        return None

    # 竖版尺寸（4:5）更贴近半身像构图；API 不支持时降级回方形
    for size in ("1024x1280", "1024x1024"):
        try:
            import requests as _req

            url = f"{resolve_api_base()}/images/generations"
            headers = {"Authorization": f"Bearer {resolve_api_key()}", "Content-Type": "application/json"}
            from common.config import resolve_feature_model

            payload = {
                "model": require_model(resolve_feature_model(uid, "image", IMAGE_MODEL), "图片"),
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
            logger.warning(f"生成数字人写真 {avatar_id} 失败（{size}）: {api_error_detail(e)}")
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
        region = arr[y0 : y1 + 1, x0 : x1 + 1]
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
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
            timeout=15,
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
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
                timeout=15,
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
    portrait_path = avatar.get("local_image_path") or (
        _get_portrait_path(avatar["id"]) if not avatar.get("is_custom") else ""
    )
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


# ── v15 口播文案质量体检 ──────────────────────────────────────
# 面向 TTS 朗读 + 字级口型同步的文案层检查：长句无停顿 / emoji /
# 长数字 / 长英文会让 TTS 读岔、口型时间轴错位，提前发现并给出修复建议。
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_PUNCT_RE = re.compile(r"[，。！？；：、,.!?;:…—～~·\"'“”‘’（）()【】《》]")
_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F]")
_DIGIT_RE = re.compile(r"\d{3,}")
_LATIN_WORD_RE = re.compile(r"[A-Za-z]{6,}")
_CN_DIGIT_MAP = {
    "0": "零", "1": "一", "2": "二", "3": "三", "4": "四",
    "5": "五", "6": "六", "7": "七", "8": "八", "9": "九",
}


# 正则常量模块级定义（check_script_quality 与口型时间轴复用，文件头已 import re）


def _digits_to_cn(text: str) -> str:
    """数字串 → 中文数字（'399' → '三九九'，供 TTS 正确朗读）。"""
    return "".join(_CN_DIGIT_MAP.get(ch, ch) for ch in text)


def check_script_quality(text: str) -> dict:
    """口播文案质量体检（纯函数，不调 LLM）。

    检查项均针对 TTS 朗读 / 字级口型同步的常见错位问题：
    - 空 / 过短：不足 10 字无法形成有效口播；
    - 长句无停顿：按标点切分的连续汉字段 > 35 字（≈9 秒 @4字/秒）
      TTS 易读岔、口型与停顿错位；> 60 字升级为 error；
    - emoji / 特殊符号：TTS 可能跳过或读出乱码，建议替换为文字；
    - 长数字串（≥3 位）：TTS 易按英文逐位朗读或读错；
    - 长英文词（≥6 字母）：中文音色下易逐字母朗读；
    - 连续空行（≥3）：渲染空白过多；
    - 全文无标点：无停顿节奏，情绪与口型无法对齐。

    返回 {ok, issues[{level,item,detail,suggest}], char_count, estimate_sec,
           fixed_text, fixed_changed}；fixed_text 为自动修复后的文案
    （去 emoji + 数字转中文 + 空行折叠），可一键应用。
    """
    raw = text or ""
    char_count = len(_CJK_RE.findall(raw))
    estimate_sec = max((char_count + 3) // 4, 1)  # 普通话语速 ≈ 4 字/秒
    fixed = raw
    issues = []

    # 1) 空文案：直接短路返回
    if not raw.strip():
        return {
            "ok": False,
            "issues": [{
                "level": "error", "item": "空文案",
                "detail": "未输入任何口播内容",
                "suggest": "请先填写文案，或点击行业模板一键填入示例文案",
            }],
            "char_count": 0,
            "estimate_sec": 1,
            "fixed_text": "",
            "fixed_changed": False,
        }

    # 2) 文案过短
    if char_count < 10:
        issues.append({
            "level": "error", "item": "文案过短",
            "detail": f"仅 {char_count} 个汉字，难以支撑完整口播",
            "suggest": "补充至 30 字以上，让数字人有充分的表达节奏",
        })

    # 3) 长句无停顿：按标点/空白切分后的连续汉字段过长
    segs = [seg for seg in re.split(r"[，。！？；：、,.!?;:…—～~·\s]+", raw) if seg]
    for seg in segs:
        n = len(_CJK_RE.findall(seg))
        if n > 60:
            issues.append({
                "level": "error", "item": "超长无停顿句",
                "detail": f"连续 {n} 个汉字无停顿（约 {n // 4} 秒一口气念完），TTS 易读岔、口型与停顿错位",
                "suggest": f"在第 18 字附近断句：『{seg[:18]}…』后加分号或句号",
            })
        elif n > 35:
            issues.append({
                "level": "warn", "item": "长句无停顿",
                "detail": f"连续 {n} 个汉字无停顿，接近一口气读完的极限",
                "suggest": f"建议在第 18 字附近断句：『{seg[:18]}…』",
            })

    # 4) emoji / 特殊符号：fixed_text 中自动移除
    emojis = sorted(set(_EMOJI_RE.findall(raw)))
    if emojis:
        issues.append({
            "level": "warn", "item": "含 emoji/特殊符号",
            "detail": f"检测到 {len(emojis)} 种符号：{' '.join(emojis[:5])}" + ("…" if len(emojis) > 5 else ""),
            "suggest": "TTS 可能跳过或读出乱码，建议改为文字（如 👍→点赞）",
        })
        fixed = _EMOJI_RE.sub("", fixed)

    # 5) 长数字串：fixed_text 中自动转中文数字
    digit_hits = _DIGIT_RE.findall(raw)
    if digit_hits:
        issues.append({
            "level": "warn", "item": "长数字串",
            "detail": f"发现 {len(digit_hits)} 处 ≥3 位数字（如 {digit_hits[0]}），TTS 易按英文逐位朗读",
            "suggest": f"建议转中文：『{_digits_to_cn(digit_hits[0])}』",
        })
        fixed = _DIGIT_RE.sub(lambda m: _digits_to_cn(m.group()), fixed)

    # 6) 长英文词
    latin_words = sorted(set(_LATIN_WORD_RE.findall(raw)))
    if latin_words:
        issues.append({
            "level": "warn", "item": "长英文词",
            "detail": f"检测到 {len(latin_words)} 个 ≥6 字母英文词（如 {latin_words[0]}），中文音色易逐字母朗读",
            "suggest": "建议拆分为中文表述（如 AI → 人工智能）",
        })

    # 7) 连续空行：fixed_text 中折叠
    if re.search(r"\n{3,}", raw):
        issues.append({
            "level": "warn", "item": "连续空行过多",
            "detail": "存在 3 行及以上连续空行，渲染会出现大段空白",
            "suggest": "合并为单个空行，保留分段结构",
        })
        fixed = re.sub(r"\n{3,}", "\n\n", fixed)

    # 8) 全文无标点（有内容且没有任何断句符号）
    if char_count >= 10 and not _PUNCT_RE.search(raw):
        issues.append({
            "level": "warn", "item": "全文无标点",
            "detail": "整段文案没有任何断句标点，朗读没有停顿节奏",
            "suggest": "按语义在每 15~20 字处添加逗号或句号",
        })

    fixed = fixed.strip()
    return {
        "ok": not issues,
        "issues": issues,
        "char_count": char_count,
        "estimate_sec": estimate_sec,
        "fixed_text": fixed,
        "fixed_changed": fixed != raw.strip(),
    }


class ScriptCheckRequest(BaseModel):
    text: str = Field(default="", max_length=5000, description="待体检口播文案（可为空，返回空文案提示）")


def _audio_energy_curve(path: str, duration: float, fps: float) -> list:
    """解码音频 → 按帧粒度 RMS 能量曲线（0~1，95 分位归一化）。

    用于驱动人物身体律动（能量高=正在说话），嘴型已升级为字级驱动。
    解码失败返回空列表（调用方回退静态呼吸）。
    """
    try:
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            capture_output=True,
            stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
            timeout=30,
        )
        import numpy as np

        raw = np.frombuffer(out.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        hop = max(int(16000 / fps), 1)
        curve = []
        for i in range(0, max(len(raw) - hop, 1), hop):
            seg = raw[i : i + hop]
            curve.append(float(np.sqrt(np.mean(seg**2))) if len(seg) else 0.0)
        if not curve:
            return []
        mx = max(float(np.percentile(curve, 95)), 1e-4)
        return [min(v / mx, 1.0) for v in curve]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# 数字人 lip-sync v2 增强：音频驱动 + 字级双源融合
# ══════════════════════════════════════════════════════════════

# 扩展版韵母口型表（v20：增加更多音标分类，覆盖常见拼音韵母）
_ENHANCED_MOUTH_SHAPES = {
    # 单韵母
    "a": (1.0, 0.5),   # 大口
    "o": (0.75, 0.95),  # 圆嘴
    "e": (0.55, 0.65),  # 半开
    "i": (0.45, 0.25),  # 扁嘴
    "u": (0.55, 1.0),   # 嘟嘴
    "v": (0.6, 0.8),    # ü 扁圆
    "er": (0.65, 0.7),  # 儿化
    # 鼻韵母
    "an": (0.8, 0.4),   # 前鼻音
    "en": (0.6, 0.5),
    "ang": (0.9, 0.3),  # 后鼻音
    "eng": (0.7, 0.4),
    "ing": (0.5, 0.3),
    "ong": (0.7, 0.85),
    "ian": (0.75, 0.35),
    "in": (0.6, 0.4),
    "ün": (0.65, 0.75),
    "ions": (0.5, 0.5),
    # 闭口音
    "n": (0.15, 0.4),   # 鼻音收尾
    "ng": (0.2, 0.45),
    # 默认
    "": (0.0, 0.5),
}


def _audio_driven_mouth(path: str, fps: float, duration: float) -> list:
    """音频驱动口型曲线：从音频能量包络中提取开合度，与字级口型融合。

    v20 增强：不仅依赖文字，还分析音频的实际能量变化，在重音处加大开合，
    静音段保持闭口，使嘴型更贴合实际语音节奏。
    """
    energy_curve = _audio_energy_curve(path, duration, fps)
    if not energy_curve:
        return []

    # 能量 → 开合度映射（非线性：低能量→小开合，高能量→大开合）
    mouth_curve = []
    for e in energy_curve:
        # 软阈值：低于 20% 能量时保持接近闭口
        if e < 0.2:
            open_val = e * 0.5  # 轻微张开
        else:
            open_val = 0.3 + 0.7 * ((e - 0.2) / 0.8)  # 线性映射到 0.3~1.0
        open_val = min(max(open_val, 0.0), 1.0)
        mouth_curve.append((open_val, 0.5))  # roundness 默认中性

    return mouth_curve


def _blend_mouth_shapes(script_curve: list, audio_curve: list, alpha: float = 0.6) -> list:
    """混合脚本驱动口型（alpha=0.6）与音频驱动口型（1-alpha=0.4）。

    alpha 越高，越依赖文字读音；越低，越跟随实际音频能量。
    """
    if not audio_curve:
        return script_curve
    if not script_curve:
        return audio_curve

    len_script = len(script_curve)
    len_audio = len(audio_curve)
    min_len = min(len_script, len_audio)
    max_len = max(len_script, len_audio)

    result = []
    for i in range(max_len):
        sc = script_curve[i] if i < len_script else (0.0, 0.5)
        ac = audio_curve[i] if i < len_audio else (0.0, 0.5)
        blended_open = alpha * sc[0] + (1 - alpha) * ac[0]
        blended_round = alpha * sc[1] + (1 - alpha) * ac[1]
        result.append((blended_open, blended_round))
    return result


def _build_script_timeline_v2(text: str, duration: float, audio_path: str = "", fps: float = 25) -> list:
    """v2 字级口型时间轴：文字读音 + 可选音频能量融合。

    比原版 _build_script_timeline 多了音频能量融合能力。
    """
    import re
    from pypinyin import Style, pinyin

    hanzi = re.compile(r"[\u4e00-\u9fff]")
    units = []
    for ch in text:
        if hanzi.match(ch):
            units.append((ch, 1.0))
        else:
            units.append((ch, 0.5))
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
            open_, round_ = _ENHANCED_MOUTH_SHAPES.get(key, _ENHANCED_MOUTH_SHAPES["e"])
        else:
            open_, round_ = 0.0, 0.5
        timeline.append((ch, start, end, open_, round_))
        cur = end

    # 如果有音频，融合音频驱动的口型
    if audio_path:
        try:
            audio_mouth = _audio_driven_mouth(audio_path, fps, duration)
            if audio_mouth:
                timeline_audio = []
                audio_idx = 0
                audio_step = len(audio_mouth) / max(len(timeline), 1)
                for ch, start, end, op, ro in timeline:
                    # 取该时间段内的平均音频口型
                    segment_end_idx = int((end / duration) * len(audio_mouth))
                    segment_start_idx = int((start / duration) * len(audio_mouth))
                    segment = audio_mouth[segment_start_idx:segment_end_idx]
                    if segment:
                        avg_open = sum(s[0] for s in segment) / len(segment)
                        avg_round = sum(s[1] for s in segment) / len(segment)
                        # 在时间段内均匀插入音频口型点
                        n_points = max(1, int((end - start) * fps))
                        for j in range(n_points):
                            t_frac = j / max(n_points - 1, 1)
                            t = start + (end - start) * t_frac
                            # 原始文字口型按包络调制
                            prog = t_frac
                            if op <= 0.01:
                                blended = (0.0, 0.5)
                            else:
                                if prog < 0.15:
                                    env = prog / 0.15
                                elif prog > 0.85:
                                    env = (1 - prog) / 0.15
                                else:
                                    env = 1.0
                                text_open = op * env
                                audio_weight = 0.35  # 音频贡献权重
                                blended = (
                                    (1 - audio_weight) * text_open + audio_weight * avg_open,
                                    (1 - audio_weight) * ro + audio_weight * avg_round,
                                )
                            timeline_audio.append((ch, t, t + 1.0 / fps, blended[0], blended[1]))
                return timeline_audio
        except Exception as e:
            logger.debug(f"音频口型融合失败，回退纯文字驱动: {e}")

    return timeline


def _mouth_shape_at_v2(timeline: list, t: float, smooth: float = 0.025) -> tuple:
    """v2 平滑口型查询：支持帧级时间轴（由 _build_script_timeline_v2 生成）。"""
    def _shape_at(t0: float) -> tuple:
        for _, _, _, open_, round_ in timeline:
            if open_ <= 0.01:
                return (0.0, 0.5)
            # 找到包含 t0 的时间段
            # 由于 v2 timeline 是帧级别的，用最近邻
        # 遍历所有帧，找最接近的
        best = (0.0, 0.5)
        best_dist = float("inf")
        for _, t_start, t_end, op, ro in timeline:
            if t_start <= t0 <= t_end:
                return (op, ro)
            dist = abs(t0 - (t_start + t_end) / 2)
            if dist < best_dist:
                best_dist = dist
                best = (op, ro)
        return best

    if smooth <= 0:
        return _shape_at(t)
    half = smooth / 2.0
    a, b, c = _shape_at(t - half), _shape_at(t), _shape_at(t + half)
    return ((a[0] + 2 * b[0] + c[0]) / 4.0, (a[1] + 2 * b[1] + c[1]) / 4.0)


def _lip_sync_quality(audio_path: str, script_text: str, duration: float, fps: int = 25) -> dict:
    """评估 lip-sync 质量（用于用户预览反馈）。

    指标：
    - energy_match: 音频能量峰值与脚本关键音节的重合度（0~1）
    - silence_gaps: 静音段数（越多说明停顿时嘴型闭合越好）
    - open_range: 开合度动态范围（越大说明嘴动越丰富）
    """
    try:
        energy = _audio_energy_curve(audio_path, duration, fps)
        if not energy:
            return {"status": "no_audio", "energy_match": 0.0, "open_range": 0.0}

        # 计算开合度范围
        open_range = max(energy) - min(energy) if energy else 0.0

        # 静音段统计（能量 < 15% 的连续段）
        silence_count = 0
        in_silence = False
        for e in energy:
            if e < 0.15:
                if not in_silence:
                    silence_count += 1
                    in_silence = True
            else:
                in_silence = False

        # 能量峰值与脚本重音匹配（简化：取能量最高的 10% 帧占比）
        peak_ratio = sum(1 for e in energy if e > 0.7) / max(len(energy), 1)

        # 综合评分
        score = 0.0
        if open_range > 0.3:
            score += 0.4  # 开合度足够
        if silence_count > 2:
            score += 0.3  # 有自然的停顿
        if 0.05 < peak_ratio < 0.3:
            score += 0.3  # 峰值比例合理

        return {
            "status": "ok",
            "score": round(score * 100),
            "open_range": round(open_range, 3),
            "silence_gaps": silence_count,
            "peak_ratio": round(peak_ratio, 3),
            "frame_count": len(energy),
            "duration_sec": round(duration, 1),
        }
    except Exception as e:
        logger.debug(f"lip-sync 质量评估失败: {e}")
        return {"status": "error", "error": str(e)}


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


def _mouth_shape_at(timeline: list, t: float, smooth: float = 0.03) -> tuple:
    """当前时刻的字级口型 → (open 0~1, round 0~1)。

    字周期内包络：前 15% 张嘴、中间 70% 维持口型、后 15% 收拢，
    形成自然说话感（每个字一次完整的开合）。
    smooth: 时间窗（秒）。帧渲染是并发无状态的，不能用全局状态做平滑，
    因此对 t 前后窗口内三点采样加权平均，消除字间开度的硬切换（"打嗝感"）。
    """

    def _shape_at(t0: float) -> tuple:
        for _, start, end, open_, round_ in timeline:
            if start <= t0 < end:
                if open_ <= 0.01:
                    return (0.0, 0.5)
                prog = (t0 - start) / max(end - start, 1e-4)
                if prog < 0.15:
                    env = prog / 0.15
                elif prog > 0.85:
                    env = (1 - prog) / 0.15
                else:
                    env = 1.0
                return (open_ * env, round_)
        return (0.0, 0.5)

    if smooth <= 0:
        return _shape_at(t)
    half = smooth / 2.0
    a, b, c = _shape_at(t - half), _shape_at(t), _shape_at(t + half)
    return ((a[0] + 2 * b[0] + c[0]) / 4.0, (a[1] + 2 * b[1] + c[1]) / 4.0)


# ── 逼真化渲染素材：嘴部/眼睑贴图模板 + 摄影棚光影 ─────────────
_MOUTH_TEMPLATES: dict = {}
_EYELID_TEMPLATES: dict = {}
_EYEBROW_TEMPLATES: dict = {}
_LIGHT_CACHE: dict = {}
_BLINK_PATTERN: list = []


# v13.24 情绪→2D 表情参数表（帧级直接查表，无状态；多线程并发帧渲染安全）
# brow: 眉形（flat 平 / rise 上挑 / droop 内八字下垂 / knit 皱眉下压）
# brow_k: 眉毛贴图不透明度系数（0 隐藏，表情越强越明显）
# squint: 恒定眯眼度（叠加在眨眼之上，0=正常睁眼）
# smile: 嘴角上翘 -1~+1（正=笑，负=哭/怒）；cheek: 腮红强度系数
# move: 动作幅度系数（欢快=大、悲伤=小）；head: 头姿偏移角（正=抬头，负=低头）
_EMOTION_FACE = {
    "neutral": {"brow": "flat", "brow_k": 0.0, "squint": 0.0, "smile": 0.0, "cheek": 1.0, "move": 1.0, "head": 0.0},
    "happy": {"brow": "rise", "brow_k": 0.55, "squint": 0.35, "smile": 0.5, "cheek": 1.35, "move": 1.15, "head": 1.0},
    "sad": {"brow": "droop", "brow_k": 0.55, "squint": 0.15, "smile": -0.5, "cheek": 0.7, "move": 0.85, "head": -2.0},
    "angry": {"brow": "knit", "brow_k": 0.6, "squint": 0.5, "smile": -0.3, "cheek": 0.9, "move": 1.1, "head": -1.0},
    "gentle": {"brow": "flat", "brow_k": 0.3, "squint": 0.2, "smile": 0.3, "cheek": 1.15, "move": 0.95, "head": 0.0},
    "serious": {"brow": "flat", "brow_k": 0.0, "squint": 0.0, "smile": 0.0, "cheek": 1.0, "move": 0.9, "head": 1.0},
}


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


def _get_mouth_template(open_idx: int, round_idx: int, smile: float = 0.0) -> Image.Image:
    """嘴部 RGBA 模板（128x96 基模板，按开度 6 档 x 圆度 4 档 x 微笑 5 档缓存）。

    真实唇形：下唇饱满渐变（上缘暗→下缘亮）+ 上唇深色 + 唇间缝 + 高光 + 嘴角阴影，
    边缘高斯羽化融入皮肤；替代原来的"椭圆+直线"贴纸式画法。
    smile（-1~+1）：嘴角上翘（笑）/下垂（哭、怒）——唇形中心线随离嘴角距离
    二次偏移，微笑时嘴角上翘而唇中部不变，形成自然的情绪嘴型。
    """
    smile_idx = int(round(max(-1.0, min(1.0, smile)) * 2))  # -2..2 五档
    key = (open_idx, round_idx, smile_idx)
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
        # 微笑/下垂：唇中心线随 |x-cx| 二次偏移（嘴角端偏移 ≈ smile*0.36*mouth_h）
        s_corr = smile_idx * 0.18 * ((np.abs(x - cx) / max(mouth_w, 1e-4)) ** 1.6)
        # 下唇：宽扁椭圆，垂直渐变（上缘暗 → 下缘亮），体现唇部体积
        dxx = (x - cx) / mouth_w
        dyy = (y - (cy + mouth_h * 0.45) - s_corr) / max(mouth_h * 0.85, 1e-4)
        lower = (dxx * dxx + dyy * dyy) <= 1.0
        t = np.clip((y - (cy - mouth_h * 0.4)) / max(mouth_h * 1.6, 1e-4), 0, 1)
        lip_low = np.empty((H, W, 4), dtype=np.float32)
        lip_low[..., 0] = (108 + 62 * t) / 255.0
        lip_low[..., 1] = (56 + 44 * t) / 255.0
        lip_low[..., 2] = (66 + 46 * t) / 255.0
        lip_low[..., 3] = 1.0
        arr[lower] = lip_low[lower]
        # 上唇：位置偏上的深色椭圆，覆盖下唇上缘形成唇间暗缝（嘴角跟随微笑偏移）
        dxxu = (x - cx) / (mouth_w * 1.04)
        dyyu = (y - (cy - mouth_h * 0.62) - s_corr * 0.6) / max(mouth_h * 0.60, 1e-4)
        upper = (dxxu * dxxu + dyyu * dyyu) <= 1.0
        arr[upper & ~lower, :3] = np.array([86, 44, 56], dtype=np.float32) / 255.0
        arr[upper & ~lower, 3] = 1.0
        # 唇间缝：上唇下缘的深色细线（随微笑曲线偏移）
        seam = (np.abs(y - (cy + mouth_h * 0.05) - s_corr * 0.8) < 1.8) & (np.abs(x - cx) <= mouth_w * 0.9)
        arr[seam, :3] = np.array([44, 24, 30], dtype=np.float32) / 255.0
        arr[seam, 3] = 1.0
        # 下唇高光：偏左的小椭圆（模拟单一主光方向）
        hx = (x - (cx + mouth_w * 0.26)) / max(mouth_w * 0.28, 1e-4)
        hy = (y - (cy + mouth_h * 0.95) - s_corr * 0.9) / max(mouth_h * 0.30, 1e-4)
        hl = (hx * hx + hy * hy <= 1.0) & lower
        arr[hl, :3] = arr[hl, :3] * 0.35 + 1.0 * 0.65
        arr[hl, 3] = np.maximum(arr[hl, 3], 0.80)
        # 嘴角阴影：两端加深（嘴角位置随微笑偏移）
        for s in (-1.0, 1.0):
            ex = (x - (cx + s * mouth_w * 0.95)) / 2.2
            ey = (y - (cy + mouth_h * 0.15) - s * s_corr) / 3.2
            corner = (ex * ex + ey * ey <= 1.0) & (lower | upper)
            arr[corner, :3] *= 0.55
            arr[corner, 3] = np.maximum(arr[corner, 3], 0.85)
        img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGBA")
        # 羽化边缘：alpha 通道高斯模糊，让唇贴图融入皮肤而非硬边
        img.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(2.2)))
        _MOUTH_TEMPLATES[key] = img
    return _MOUTH_TEMPLATES[key]


def _get_eyebrow_template(eye_w: int, pose: str = "flat") -> Image.Image:
    """眉毛 RGBA 贴图（按宽度 x 眉形缓存），v13.24 情绪表情层。

    pose: flat 平眉 / rise 上挑（欢快）/ droop 内八字下垂（悲伤）/ knit 下压皱眉（愤怒）。
    眉形用中心线（内端→外端的高度轮廓）+ 半厚渐变生成，半透明深棕（alpha≈0.6）
    叠加在写真眉骨位置，改变/增强眉形以传达情绪。
    """
    key = (eye_w, pose)
    if key not in _EYEBROW_TEMPLATES:
        import numpy as np

        w = max(8, int(eye_w * 1.15))
        h = max(10, int(w * 0.34))
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        t = x / max(w - 1, 1)  # 0 内端 → 1 外端
        if pose == "rise":  # 上挑眉：内端低、外端高（欢快/惊讶）
            cy = h * (0.62 - 0.32 * t)
        elif pose == "droop":  # 八字眉：内端高、外端低（悲伤）
            cy = h * (0.30 + 0.32 * t)
        elif pose == "knit":  # 皱眉：内端下压 + 眉峰内移（愤怒/专注）
            cy = h * (0.42 + 0.30 * np.clip(1 - t, 0, 1) ** 1.3)
        else:  # flat：轻微平弧（眉峰微高）
            cy = h * (0.44 - 0.08 * np.abs(t - 0.45))
        half = h * (0.15 + 0.10 * np.abs(t - 0.45))  # 眉峰处略厚
        dist = np.abs(y - cy) / np.maximum(half, 1e-4)
        alpha = np.clip(1 - dist, 0, 1) ** 1.5
        # 眉色深棕，两端自然收窄（乘端部衰减）
        end_fade = np.clip(1 - np.abs(t - 0.5) * 1.6, 0, 1)
        arr = np.zeros((h, w, 4), dtype=np.float32)
        arr[..., 0] = 0.30
        arr[..., 1] = 0.19
        arr[..., 2] = 0.16
        arr[..., 3] = alpha * (0.55 + 0.20 * end_fade)
        img = Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), "RGBA")
        img.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(1.3)))
        _EYEBROW_TEMPLATES[key] = img
    return _EYEBROW_TEMPLATES[key]


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
    return tuple(int(hex_str[i : i + 2], 16) for i in (0, 2, 4))


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
        _GRADIENT_CACHE[key] = np.array(c_light, dtype=np.float32) * t + np.array(c_dark, dtype=np.float32) * (1 - t)
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

_TEXT_WIDTH_CACHE: dict = {}


def _text_width(text: str, font) -> float:
    """文本宽度（按 字体+文本 缓存）：卡拉OK逐字绘制每帧高频调用 textlength。"""
    key = (font, text)
    w = _TEXT_WIDTH_CACHE.get(key)
    if w is None:
        w = float(font.getlength(text))
        if len(_TEXT_WIDTH_CACHE) > 10000:  # 上限防无限增长（文本行数有限，正常远低于此）
            _TEXT_WIDTH_CACHE.clear()
        _TEXT_WIDTH_CACHE[key] = w
    return w


def _karaoke_cur_idx(lines: list, progress: float) -> int:
    """卡拉OK进度 → 当前行下标（与 _draw_karaoke 逐字逻辑一致，供字幕层缓存签名使用）。"""
    total_chars = sum(len(ln) for ln in lines)
    if total_chars == 0:
        return 0
    chars_done = min(int(progress * total_chars), total_chars - 1)
    acc = 0
    for i, ln in enumerate(lines):
        if acc + len(ln) > chars_done:
            return i
        acc += len(ln)
    return max(0, len(lines) - 1)


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


def _draw_karaoke(  # noqa: C901 — 卡拉OK逐字绘制（right/center 双布局），复杂度可控
    draw,
    lines: list,
    progress: float,
    font,
    x: int,
    y0: int,
    line_h: int,
    accent: str,
    max_rows: int = 12,
    center: bool = False,
    canvas_w: int = 0,
) -> None:
    """卡拉OK逐字字幕：已读行整行半透明白，当前行逐字显示且当前字主题色高亮。

    center=True 时按底部全宽居中绘制，窗口跟随进度滑动（短视频字幕观感），
    x 为每行中心点；canvas_w 用于居中时行宽超限的截断提示。
    """
    if not lines:
        return
    total_chars = sum(len(ln) for ln in lines)
    if total_chars == 0:
        return
    chars_done = min(int(progress * total_chars), total_chars - 1)
    # 定位当前行（窗口起点字符数：center 模式下当前行内进度需相对窗口计算）
    cur_idx = _karaoke_cur_idx(lines, progress)
    acc = sum(len(ln) for ln in lines[:cur_idx])
    if center:
        # 窗口 = 当前行及之前 max_rows-1 行（底部字幕随进度上滚）
        start = max(0, cur_idx - max_rows + 1)
        display = lines[start : cur_idx + 1]
        if cur_idx < len(lines) - 1:
            display = display + [lines[cur_idx + 1]]  # 预显示下一行开头，提示后续内容
        display = display[:max_rows]
        # 重新累计窗口起点前的字符数（当前行内进度需相对窗口计算）
        acc = sum(len(ln) for ln in lines[:start])
    else:
        display = lines[:max_rows]
    # 已读行（center 模式下窗口内当前行之前的行；right 模式为开头所有已读行）
    for i in range(len(display)):
        if center and i >= len(display) - 1:
            break
        if not center and i >= cur_idx:
            break
        ln = display[i]
        tx = x - _text_width(ln, font) / 2 if center else x
        draw.text((tx, y0 + i * line_h), ln, fill="#ffffffb3", font=font)
    # 当前行：字幕底条 + 逐字着色（已读白 / 当前字主题色 / 未读灰）
    cur_disp = cur_idx - (start if center else 0)
    line = display[cur_disp]
    in_done = chars_done - acc
    y_cur = y0 + cur_disp * line_h
    line_w = _text_width(line, font)
    if center:
        half = line_w / 2
        lx = x - half - 8
        rx = x + half + 8
    else:
        lx = x - 8
        rx = x + line_w + 8
    draw.rounded_rectangle(
        [lx, y_cur - 3, rx, y_cur + line_h - 5],
        radius=7,
        fill="#0000003a",
    )
    cur_x = x - line_w / 2 if center else x
    for j, ch in enumerate(line):
        if j < in_done:
            fill = "#ffffff"
        elif j == in_done:
            fill = accent
        else:
            fill = "#ffffff59"
        draw.text((cur_x, y_cur), ch, fill=fill, font=font)
        cur_x += _text_width(ch, font)



def _create_ui_layer(width: int, height: int):
    """创建 UI 图层。"""
    from PIL import Image, ImageDraw
    ui = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    return ui, ImageDraw.Draw(ui)

def _draw_glow_spots(img, ui, width, height, t, S):
    """绘制高斯柔光斑。"""
    for i, (gx, gy, scale) in enumerate([
        (0.82, 0.20, 1.6),
        (0.12, 0.72, 1.3),
        (0.58, 0.92, 1.9),
    ]):
        layer = _get_glow_template(150, scale)
        cx = int(width * gx + __import__('math').sin(t * 0.3 + i * 2.1) * 40 * S)
        cy = int(height * gy + __import__('math').cos(t * 0.25 + i * 1.7) * 30 * S)
        img.paste(layer, (cx - layer.width // 2, cy - layer.height // 2), layer)

def _apply_talk_motion(t, energy, emotion, S):
    """应用说话律动。"""
    import math
    emo = _EMOTION_FACE.get(emotion, _EMOTION_FACE["neutral"])
    talk = min(1.0, energy * 1.6) * emo["move"]
    sway_t = math.sin(t * 1.15)
    breathe_t = math.sin(t * 1.3)
    glow_alpha = max(8, min(45, int(22 + 16 * math.sin(t * 1.9))))
    enter_ease = 1 - (1 - min(1.0, t / 0.8)) ** 3
    return talk, sway_t, breathe_t, glow_alpha, enter_ease, emo

def _draw_portrait_region(img, draw, portrait, t, energy, S, width, height, talk, sway_t, breathe_t, glow_alpha, enter_ease, emo, mouth_shape, avatar) -> None:
    """绘制人物区（写真动态 + 眨眼/嘴型 + 光环）——完整迁移。"""
    import math
    p_base, p_mask_base, p_base_w, p_base_h, face_meta = portrait
    # 头部几何（归一化画布 800x1000 坐标）→ 眼/嘴/颊彩动态定位，
    # 适配不同写真构图差异（固定比例在构图漂移时会贴错位）
    bx = p_base_w / 800.0
    by = p_base_h / 1000.0
    if face_meta:
        cy_c = face_meta["cy"]
        head_h_c = face_meta["head_w"] * 1.30  # 头高估计（检测带宽含肩，按唇色实测校准）
        eye_y_c = cy_c - 12  # 眼 ≈ 肤色区上界（眉骨附近）
        mouth_y_c = cy_c + head_h_c * 0.15  # 唇：实测校准（唇-头中心差 ≈ 0.15 x 头高）
        cheek_y_c = cy_c + head_h_c * 0.08  # 颊：眼唇之间
        cheek_dx_c = face_meta["head_w"] * 0.32
    else:
        eye_y_c, mouth_y_c, cheek_y_c, cheek_dx_c = 240, 340, 290, 140
        head_h_c = 320  # 默认头高（无检测时，眉毛按固定比例定位）
    # 呼吸缩放（真人幅度 ~1.2%，收敛气球感）+ 说话节奏起伏
    breath_scale = 1 + 0.012 * breathe_t + 0.010 * talk * math.sin(t * 3.2)
    p_w = max(20, int(p_base_w * breath_scale * S))
    p_h = max(20, int(p_base_h * breath_scale * S))
    # 点头倾斜：小角度 + 高频微颤（真人肌肉松弛感，避免纸片式大摆）
    # v13.24 情绪头姿：欢快/严肃微抬头，悲伤低头，愤怒微前倾
    tilt = (
        0.9 * sway_t * (1.0 + 0.9 * talk)
        + 0.45 * talk * math.sin(t * 2.9)
        + 0.22 * math.sin(t * 5.1)
        + emo["head"]
    )
    nod_pivot = (int(p_w / 2), p_h)  # 底部中心为旋转轴
    p_img = p_base.resize((p_w, p_h), Image.LANCZOS).rotate(tilt, resample=Image.BILINEAR, center=nod_pivot)
    p_mask = p_mask_base.resize((p_w, p_h), Image.BILINEAR).rotate(tilt, resample=Image.BILINEAR, center=nod_pivot)
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
        [10, 10, p_w + 10, p_h + 10],
        radius=40,
        fill=(0, 0, 0, 50),
    )
    img.paste(shadow, (px - 5, py - 5), shadow)
    img.paste(p_img, (px, py), p_mask)

    # 自然眨眼：随机间隔（2.2~4.8s）+ 上眼睑渐变遮罩下压（替代"画线"）
    # v13.24 情绪眯眼：happy/gentle 微眯（笑眼）、angry 眯视，叠加在眨眼之上
    close = max(_blink_progress(t), emo["squint"])
    if close > 0.03:
        eye_w = max(6, int(p_w * 0.135))
        eye_y = py + int(eye_y_c * by * breath_scale)
        lid = _get_eyelid_template(eye_w)
        lid_h = max(2, int(lid.height * min(close * 1.25, 1.0)))
        lid_use = lid.crop((0, 0, lid.width, lid_h)) if lid_h < lid.height else lid
        for ex in (px + int(p_w * 0.30), px + int(p_w * 0.58)):
            img.paste(lid_use, (ex - lid_use.width // 2, eye_y - lid_h), lid_use)

    # v13.24 情绪眉毛：半透明眉形贴图（上挑/下垂/皱眉）叠加在眉骨位置，
    # 传达欢快/悲伤/愤怒；轻微情绪（gentle）整体降透明度
    if emo["brow_k"] > 0.05:
        brow_img = _get_eyebrow_template(max(6, int(p_w * 0.15)), emo["brow"])
        if emo["brow_k"] < 0.5:
            brow_a = brow_img.getchannel("A").point(lambda v: int(v * (emo["brow_k"] / 0.5)))
            brow_img = brow_img.copy()
            brow_img.putalpha(brow_a)
        brow_y = py + int((eye_y_c - head_h_c * 0.10) * by * breath_scale) - brow_img.height // 2
        for ex in (px + int(p_w * 0.30), px + int(p_w * 0.58)):
            img.paste(brow_img, (ex - brow_img.width // 2, brow_y), brow_img)

    # 颊彩表情层：柔和粉彩脸颊（说话时随能量微亮），提升生气感
    # v13.24 情绪腮红：欢快/温柔加深（笑出红晕），悲伤减淡
    cheek_alpha = int((22 + 14 * talk) * emo["cheek"])
    cheek_w = max(8, int(p_w * 0.17))
    cheek_h = max(4, int(cheek_w * 0.55))
    cheek_y = py + int(cheek_y_c * by * breath_scale)
    cheek = Image.new("RGBA", (cheek_w * 2 + 4, cheek_h * 2 + 4), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cheek)
    for s in (-1.0, 1.0):
        cex = cheek_w + 2 + int(s * cheek_dx_c * bx * breath_scale)
        cd.ellipse([cex - cheek_w, 2, cex + cheek_w, 2 + cheek_h * 2], fill=(240, 120, 130, cheek_alpha))
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
        # v13.24 情绪嘴型：smile 驱动嘴角上翘/下垂（笑/哭/怒）
        mouth_layer = _get_mouth_template(open_idx, round_idx, emo["smile"]).resize(
            (mw, mh),
            Image.LANCZOS,
        )
        mx = px + int(p_w * 0.49)
        my = py + int(mouth_y_c * by * breath_scale)
        img.paste(mouth_layer, (mx - mw // 2, my - mh // 2), mouth_layer)

    # 光环脉动
    glow_layer = Image.new("RGBA", (p_w + 120, p_h + 120), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    gd.rounded_rectangle([60, 55, p_w + 60, p_h + 55], radius=48, outline=(255, 255, 255, glow_alpha), width=6)
    img.paste(glow_layer, (px - 60, py - 55), glow_layer)


def _draw_portrait_region_fallback(img, draw, portrait, t, S, width, height, avatar, fonts) -> None:
    """无人物时的兜底画面（云朵/光斑/表情）。"""
    import math
    glow_alpha = max(8, min(45, int(22 + 16 * math.sin(t * 1.9))))  # 呼吸光晕透明度（与主画像函数一致）
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
        outline=(255, 255, 255, glow_alpha),
        width=6,
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


def _draw_bottom_bar(draw, width: int, height: int, S: float, fonts: dict, avatar: dict, accent, progress: float) -> None:
    """底部栏：品牌信息 + 主题色进度条。"""
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
    draw.rounded_rectangle([int(30 * S), bar_y, int(30 * S) + bar_w, bar_y + int(6 * S)], radius=3, fill="#ffffff20")
    fill_w = int(bar_w * progress)
    if fill_w > 4:
        draw.rounded_rectangle([int(30 * S), bar_y, int(30 * S) + fill_w, bar_y + int(6 * S)], radius=3, fill=accent)

def _render_frame(  # noqa: C901
    avatar: dict,
    bg_hex: str,
    fonts: dict,
    portrait,
    text_lines: list,
    t: float,
    progress: float,
    width: int,
    height: int,
    energy: float = 0.0,
    mouth_shape: tuple = (0.0, 0.5),
    bg_img: Image.Image | None = None,
    subtitle_style: dict | None = None,
    sub_font=None,
    sub_cache: dict | None = None,
    emotion: str = "neutral",
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
    ui, draw = _create_ui_layer(width, height)
    _draw_glow_spots(img, ui, width, height, t, S)

    # ── 3. 漂浮粒子（像直播间的氛围光点，画在 UI 图层参与 alpha 合成）──
    _draw_particles(ui, t)

    # ── 3.5 摄影棚光影：主光聚焦人物 + 地面反光 + 暗角（背景上、人物下）──
    img = _apply_studio_lighting(img, t)

    # 说话能量 → 驱动全身律动
    talk, sway_t, breathe_t, glow_alpha, enter_ease, emo = _apply_talk_motion(t, energy, emotion, S)

    # ── 4. 左侧人物：写真 + 动态（入场滑入/呼吸缩放/点头倾斜/眨眼/嘴型开合）──
    if portrait:
        _draw_portrait_region(
            img, draw, portrait, t, energy, S, width, height,
            talk, sway_t, breathe_t, glow_alpha, enter_ease, emo, mouth_shape, avatar,
        )
    else:
        _draw_portrait_region_fallback(
            img, draw, portrait, t, S, width, height, avatar, fonts,
        )

    # ── 5. 人物名片（右上）+ 卡拉OK逐字字幕（right=名片下 / center=底部居中大字）──
    right_x = int(600 * S)
    right_w = int((1280 - 600 - 50) * S)

    name_text = avatar.get("name", "AI数字人")
    draw.text((right_x, int(60 * S)), name_text, fill="#ffffff", font=fonts["title"])

    style_text = avatar.get("style", "")
    if style_text:
        tag_w = draw.textbbox((0, 0), style_text, font=fonts["tag"])[2] + 20
        draw.rounded_rectangle(
            [right_x, int(108 * S), right_x + tag_w, int(134 * S)],
            radius=12,
            fill="#ffffff20",
            outline="#ffffff30",
            width=1,
        )
        draw.text((right_x + 10, int(110 * S)), style_text, fill="#ffffffcc", font=fonts["tag"])

    draw.line([right_x, int(155 * S), right_x + right_w, int(155 * S)], fill="#ffffff15", width=1)

    accent = _accent_color(bg_hex)
    sub_style = subtitle_style or {}
    sub_color = sub_style.get("color") or accent
    sub_font_size = int(sub_style.get("font_size") or 32)
    sub_font = sub_font or fonts["body"]
    # 字幕静态帧跳过重绘：进度（当前行）未变化时复用上一帧字幕层，跳过逐字绘制
    # （句间停顿/慢语速间隙命中率高；缓存随视频实例隔离，无跨视频串扰）
    if sub_style.get("position") == "center":
        k_max_rows = 4
        k_line_h = int(sub_font_size * S)
        k_y0 = height - int(64 * S) - int(20 * S) - k_max_rows * k_line_h
        sub_x, sub_y, sub_w = 0, k_y0, width
        sub_h = height - int(64 * S) - k_y0 + 4
    else:
        k_max_rows = 12
        k_line_h = int(sub_font_size * S)
        k_y0 = int(175 * S)
        sub_x, sub_y = right_x - 10, k_y0 - 10
        sub_w = right_w + 20
        sub_h = (k_max_rows + 1) * k_line_h + int(40 * S)
    sub_sig = (
        hash("".join(text_lines)),
        _karaoke_cur_idx(text_lines, progress),
        sub_style.get("position"),
        sub_color,
        sub_font_size,
        width,
        height,
    )
    cached_layer = None
    if sub_cache is not None:
        with sub_cache["lock"]:
            if sub_cache.get("sig") == sub_sig and sub_cache.get("layer") is not None:
                cached_layer = sub_cache["layer"]
    if cached_layer is not None:
        ui.paste(cached_layer, (sub_x, sub_y))
    else:
        sub_layer = Image.new("RGBA", (sub_w, sub_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sub_layer)
        if sub_style.get("position") == "center":
            # 底部居中大字（短视频字幕观感）：窗口跟随进度上滚，最多 4 行
            _draw_karaoke(
                sd,
                text_lines,
                progress,
                sub_font,
                width // 2,
                k_y0 - sub_y,
                k_line_h,
                sub_color,
                max_rows=k_max_rows,
                center=True,
                canvas_w=width,
            )
            if len(text_lines) > k_max_rows + 1:
                sd.text(
                    (width - int(40 * S), (k_y0 - sub_y) + (k_max_rows - 1) * k_line_h),
                    f"...共{sum(len(ln) for ln in text_lines)}字",
                    fill="#ffffff55",
                    font=fonts["tag"],
                )
        else:
            _draw_karaoke(
                sd,
                text_lines,
                progress,
                sub_font,
                right_x,
                k_y0 - sub_y,
                k_line_h,
                sub_color,
            )
            if len(text_lines) > 12:
                sd.text(
                    (right_x, (k_y0 - sub_y) + 12 * k_line_h),
                    f"...共{sum(len(ln) for ln in text_lines)}字",
                    fill="#ffffff55",
                    font=fonts["tag"],
                )
        ui.paste(sub_layer, (sub_x, sub_y))
        if sub_cache is not None:
            with sub_cache["lock"]:
                sub_cache["sig"] = sub_sig
                sub_cache["layer"] = sub_layer

    # ── 6. 底部：品牌信息 + 主题色进度条 ──
    _draw_bottom_bar(draw, width, height, S, fonts, avatar, accent, progress)

    return Image.alpha_composite(img.convert("RGBA"), ui).convert("RGB")


def _render_video_frame(
    f: int, fps: int, duration: float, energy_curve, script_timeline, avatar, bg_hex, fonts,
    portrait, text_lines, RENDER_W: int, RENDER_H: int, bg_img, subtitle_style, sub_font,
    sub_cache, emotion, OUT_W: int, OUT_H: int, opening: str, closing: str, watermark: bool,
    wm_font, frames_dir: str,
) -> None:
    """渲染单帧：人物帧 + Ken Burns 运镜 + 淡入淡出 + 片头片尾 + 水印 → JPG。"""
    import math

    t = f / fps
    progress = min(1.0, t / duration) if duration > 0 else 1.0
    energy = energy_curve[min(f, len(energy_curve) - 1)] if energy_curve else 0.0
    mouth_shape = _mouth_shape_at(script_timeline, t)
    frame = _render_frame(
        avatar=avatar, bg_hex=bg_hex, fonts=fonts, portrait=portrait, text_lines=text_lines,
        t=t, progress=progress, width=RENDER_W, height=RENDER_H, energy=energy,
        mouth_shape=mouth_shape, bg_img=bg_img, subtitle_style=subtitle_style,
        sub_font=sub_font, sub_cache=sub_cache, emotion=emotion,
    )
    # 镜头运动：Ken Burns 推近 + 缓慢平移 + 呼吸缩放
    zoom = 0.05 * progress + 0.012 * math.sin(t * 0.25)
    win_w = int(RENDER_W / (1 + zoom))
    win_h = int(RENDER_H / (1 + zoom))
    pan_x = int(0.012 * RENDER_W * math.sin(t * 0.18))
    pan_y = int(0.008 * RENDER_H * math.sin(t * 0.13 + 1.0))
    x0 = max(0, min((RENDER_W - win_w) // 2 + pan_x, RENDER_W - win_w))
    y0 = max(0, min((RENDER_H - win_h) // 2 + pan_y, RENDER_H - win_h))
    frame = frame.crop((x0, y0, x0 + win_w, y0 + win_h)).resize((OUT_W, OUT_H), Image.LANCZOS)
    # 开头淡入 / 结尾淡出
    fade = 1.0
    if t < 0.4:
        fade = t / 0.4
    elif t > duration - 0.4:
        fade = max(0.0, (duration - t) / 0.4)
    if fade < 1.0:
        black = Image.new("RGB", (OUT_W, OUT_H), (0, 0, 0))
        frame = Image.blend(black, frame, fade)
    # 行业模板片头/片尾
    if (opening and t < 1.2) or (closing and t > duration - 1.2):
        frame = _overlay_script_text(frame, opening if t < 1.2 else closing, t, duration, fonts["title"], OUT_W, OUT_H)
    # 商业水印
    if watermark:
        frame = _overlay_watermark(frame, wm_font, OUT_W, OUT_H)
    frame.save(os.path.join(frames_dir, f"{f:04d}.jpg"), quality=95)


def _overlay_script_text(frame, ov_text: str, t: float, duration: float, ov_font, OUT_W: int, OUT_H: int):
    """片头/片尾文字叠加（渐显渐隐）。"""
    if t < 1.2:
        fade_o = min(1.0, t / 0.3) * min(1.0, (1.2 - t) / 0.4)
    else:
        fade_o = min(1.0, (t - (duration - 1.2)) / 0.3) * min(1.0, (duration - t) / 0.4)
    if fade_o <= 0.02:
        return frame
    ov_layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(ov_layer)
    ov_w = ov_draw.textlength(ov_text, font=ov_font)
    ov_h = ov_font.getbbox(ov_text)[3]
    a = int(255 * fade_o * 0.92)
    ov_x = (OUT_W - ov_w) / 2
    ov_y = OUT_H * 0.20 - ov_h / 2
    ov_draw.text((ov_x + 2, ov_y + 2), ov_text, font=ov_font, fill=(0, 0, 0, a))
    ov_draw.text((ov_x, ov_y), ov_text, font=ov_font, fill=(255, 255, 255, a))
    frame.paste(ov_layer, (0, 0), ov_layer)
    return frame


def _overlay_watermark(frame, wm_font, OUT_W: int, OUT_H: int):
    """右下角半透明水印（深色描边提高可读性）。"""
    wm_text = WATERMARK_TEXT
    wm_w = wm_font.getbbox(wm_text)[2]
    wm_layer = Image.new("RGBA", (OUT_W, OUT_H), (0, 0, 0, 0))
    wm_draw = ImageDraw.Draw(wm_layer)
    wm_x, wm_y = OUT_W - wm_w - int(24 * OUT_W / 1280), OUT_H - int(34 * OUT_H / 720)
    wm_draw.text((wm_x - 1, wm_y - 1), wm_text, font=wm_font, fill=(0, 0, 0, 120))
    wm_draw.text((wm_x + 1, wm_y + 1), wm_text, font=wm_font, fill=(0, 0, 0, 120))
    wm_draw.text((wm_x, wm_y), wm_text, font=wm_font, fill=(255, 255, 255, 170))
    frame.paste(wm_layer, (0, 0), wm_layer)
    return frame


def _encode_with_fallback(frames_dir: str, audio_path: str, output_path: str, resolution: str, fps: int, total_frames: int, duration: float) -> None:
    """ffmpeg 编码：1080p 失败自动降级 720p 重试。"""
    encode_attempts = [resolution, "720p"] if resolution == "1080p" else [resolution]
    encode_err: Exception | None = None
    for enc_res in encode_attempts:
        try:
            _ffmpeg_encode(frames_dir, audio_path, output_path, enc_res, fps)
            encode_err = None
            logger.info(f"视频编码成功：{enc_res} {total_frames}帧 @{fps}fps, {duration:.1f}s")
            return
        except Exception as e:  # noqa: BLE001 — 编码失败尝试降级
            encode_err = e
            logger.warning(f"视频编码失败（{enc_res}），准备降级重试: {e}")
    raise encode_err


def _render_video(  # noqa: C901 — 多阶段渲染管线（帧/编码/降级），复杂度可控
    text: str,
    avatar: dict,
    bg: dict,
    audio_path: str,
    output_path: str,
    resolution: str = "720p",
    fps: int = 15,
    watermark: bool = False,
    subtitle_style: dict | None = None,
    opening: str = "",
    closing: str = "",
    emotion: str = "neutral",
) -> None:
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
        "/System/Library/Fonts/Hiragino Sans GB.ttc",  # 中文黑体（简体全覆盖）
        "/System/Library/Fonts/STHeiti Light.ttc",  # 黑体-简
        "/System/Library/Fonts/Supplemental/Songti.ttc",  # 宋体
        "/System/Library/Fonts/PingFang.ttc",  # 部分 macOS 可加载
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux 容器：文泉驿（简体字型，优先于 Noto JP 变体）
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux 容器：Noto CJK
        "/System/Library/Fonts/Helvetica.ttc",  # 英文兜底
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
    # 字幕专用字体：行业模板可指定字号（1280 基准坐标系），未指定时沿用 body
    sub_style = subtitle_style or {}
    sub_font = _load_font(int(sub_style.get("font_size") or 20), FONT_CANDIDATES) if sub_style else fonts["body"]

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

    # 文案换行（复用一帧的测量）：center 字幕按底部全宽排版，right 沿用右侧栏宽
    probe = Image.new("RGB", (10, 10), "#000")
    probe_draw = ImageDraw.Draw(probe)
    right_w = int((OUT_W - 600 - 50) * 1.10)
    if sub_style.get("position") == "center":
        wrap_w = int((OUT_W - 120) * 1.10)
    else:
        wrap_w = right_w
    text_lines = _wrap_text_lines(text, probe_draw, sub_font, wrap_w)

    frames_dir = tempfile.mkdtemp(prefix="dh_frames_")
    # 水印字体只加载一次（原实现每帧重复加载字体文件）
    wm_font = _load_font(int(18 * OUT_W / 1280), FONT_CANDIDATES) if watermark else None
    # 字幕静态帧缓存：进度未变化时复用字幕层（仅本次视频内共享，线程锁保护并发帧）
    sub_cache = {"sig": None, "layer": None, "lock": threading.Lock()}

    def _render_one(f: int) -> None:
        frame = _render_video_frame(
            f, fps, duration, energy_curve, script_timeline, avatar, bg_hex, fonts,
            portrait, text_lines, RENDER_W, RENDER_H, bg_img, subtitle_style, sub_font,
            sub_cache, emotion, OUT_W, OUT_H, opening, closing, watermark, wm_font, frames_dir,
        )

    try:
        # 帧渲染并行化：PIL/numpy 的 C 层操作释放 GIL，线程池可吃满多核（帧间无依赖）
        # v13.0 看门狗：单帧无进展超时 + 总时长超限即中断，绝不僵死白等
        # v14.0 线程池按分辨率调优：720p 默认档吃满核（8 worker）；
        # 1080p 单帧内存/耗时翻倍，降并发防内存压力（4 worker 封顶）
        # v14.1 修复：as_completed 的 timeout 是"总预算"（长视频必然误杀），
        # 改用手动 wait(FIRST_COMPLETED, 15s) 实现真正的"无进展看门狗"
        cpu_n = os.cpu_count() or 4
        render_workers = min(cpu_n, 8) if resolution == "720p" else max(2, min(cpu_n // 2, 4))
        deadline = max(total_frames * 0.5, 300)  # 经验单帧预算 0.5s，下限 300s
        frame_start = time.monotonic()
        with ThreadPoolExecutor(max_workers=render_workers) as pool:
            pending = {pool.submit(_render_one, f) for f in range(total_frames)}
            done = 0
            while pending:
                # 15s 内无任何新完成帧 → 视为渲染停滞（worker 卡死/内存压力），立即中断
                finished, pending = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
                if not finished:
                    raise TimeoutError(f"帧渲染停滞：>15s 无新完成帧（已完成 {done}/{total_frames} 帧）")
                for fut in finished:
                    fut.result()  # 帧渲染异常向上抛
                    done += 1
                if time.monotonic() - frame_start > deadline:
                    raise TimeoutError(f"帧渲染总时长超限（>{deadline:.0f}s，已完成 {done}/{total_frames} 帧）")
        logger.info(f"帧渲染完成：{total_frames}帧 耗时{time.monotonic() - frame_start:.1f}s")

        # ffmpeg：帧序列 + 音频 → MP4（1080p 失败自动降级 720p）
        _encode_with_fallback(frames_dir, audio_path, output_path, resolution, fps, total_frames, duration)
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


def _ffmpeg_encode(frames_dir: str, audio_path: str, output_path: str, resolution: str, fps: int) -> None:
    """ffmpeg 帧序列+音频合成 MP4（分辨率由参数控制，供降级重试复用）。"""
    OUT_W, OUT_H = (1920, 1080) if resolution == "1080p" else (1280, 720)
    try:
        enc = _pick_video_encoder()
        # 画质滤镜链：锐化（unsharp）+ 对比度/饱和度分级（eq），
        # 去除 JPG 帧软糊感；硬件编码器（videotoolbox/nvenc）不支持 qscale
        # （ffmpeg 8.x 报错）改用目标码率模式，libx264 用 crf 18
        # v14.0 码率按分辨率分级：720p 短视频 5M 已满足观感（编码更快），1080p 保持 6M 画质
        if enc != "libx264":
            quality_args = [
                "-b:v", "6M" if resolution == "1080p" else "5M",
                "-maxrate", "8M" if resolution == "1080p" else "7M",
                "-bufsize", "12M" if resolution == "1080p" else "10M",
            ]
        else:
            quality_args = ["-crf", "18"]
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                os.path.join(frames_dir, "%04d.jpg"),
                "-i",
                audio_path,
                "-vf",
                f"scale={OUT_W}:{OUT_H}:flags=lanczos,unsharp=5:5:0.6:5:5:0.0,eq=contrast=1.06:saturation=1.10",
                "-c:v",
                enc,
                "-pix_fmt",
                "yuv420p",
                *quality_args,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-shortest",
                "-movflags",
                "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
            stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
            timeout=900,
        )
    except subprocess.CalledProcessError as e:
        # 把 ffmpeg stderr 带进错误信息，否则用户只能看到 exit code，无法诊断
        detail = e.stderr.decode(errors="replace")[-500:].strip() if e.stderr else "未知错误"
        raise RuntimeError(f"视频编码失败（ffmpeg exit {e.returncode}）：{detail}") from e


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
        ("engine", "TEXT DEFAULT '2d'"),
        ("template_id", "TEXT DEFAULT ''"),
        ("emotion", "TEXT DEFAULT 'auto'"),
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
        ("engine", "TEXT DEFAULT '2d'"),
        ("emotion", "TEXT DEFAULT 'auto'"),
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
    # v14.0 音频缓存：同文案+同音色+同速度复用 TTS 结果（key=hash(text|voice|speed|pitch)）
    conn.execute(
        """CREATE TABLE IF NOT EXISTS digital_human_tts_cache (
            cache_key TEXT PRIMARY KEY,
            text TEXT DEFAULT '',
            voice TEXT DEFAULT '',
            speed REAL DEFAULT 1.0,
            pitch INTEGER DEFAULT 0,
            audio_url TEXT DEFAULT '',
            hits INTEGER DEFAULT 0,
            created_at TEXT DEFAULT '',
            last_hit TEXT DEFAULT ''
        )"""
    )
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
    # 声音克隆（v1 参数近似克隆：edge-tts 音色池 + 基频匹配 + 音调补偿；
    # engine 预留 cosyvoice 升级路径）。吊销后 status='revoked'，生成链路不再可用。
    conn.execute(
        """CREATE TABLE IF NOT EXISTS voice_clones (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            voice_name TEXT DEFAULT '',
            sample_path TEXT DEFAULT '',
            sample_duration REAL DEFAULT 0,
            f0_mean REAL DEFAULT 0,
            gender TEXT DEFAULT '',
            edge_voice TEXT DEFAULT '',
            pitch_hz INTEGER DEFAULT 0,
            speed REAL DEFAULT 1.0,
            status TEXT DEFAULT 'active',       -- active/revoked
            declare_authorized INTEGER DEFAULT 0,
            engine TEXT DEFAULT 'pitch_fit',    -- v1: 参数近似克隆；预留 cosyvoice
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
        d["local_image_path"] = (
            os.path.join(_BASE_DIR, *url.lstrip("/").split("/")) if url.startswith("/uploads/") else ""
        )
        out[d["id"]] = d
    return out


def _lookup_voice(user_id: str = "", voice_id: str = "") -> dict | None:
    """声音统一查找：内置音色 / 自定义上传（custom_）/ 克隆声音（clone_）。"""
    v = next((x for x in VOICES if x["id"] == voice_id), None)
    if not v and (voice_id.startswith("custom_") or voice_id.startswith("clone_")):
        v = _load_custom_voices(user_id).get(voice_id)
    return v


def _load_custom_voices(user_id: str = "") -> dict:
    """按用户加载自定义声音 → {id: voice_dict}；含本地音频路径映射。

    合并两类声音：
    - custom_：用户上传的音频样本（生成时直接用样本作为配音）
    - clone_：声音克隆（生成时用匹配音色 + 音调补偿合成，样本仅作分析，不直接使用）
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM digital_human_custom_voices WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        clone_rows = conn.execute(
            "SELECT * FROM voice_clones WHERE user_id=? AND status='active' ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    out = {}
    for r in rows:
        d = dict(r)
        d["is_custom"] = True
        url = d.get("audio_url") or ""
        d["local_audio_path"] = (
            os.path.join(_BASE_DIR, *url.lstrip("/").split("/")) if url.startswith("/uploads/") else ""
        )
        out[d["id"]] = d
    for r in clone_rows:
        d = dict(r)
        d["is_custom"] = True
        d["is_clone"] = True
        d["name"] = d.get("voice_name") or "克隆声音"
        d["desc"] = f"声音克隆 · {d.get('gender') or '未知'}声 · 基频 {d.get('f0_mean') or 0}Hz"
        d["emoji"] = "🔊"
        d["local_audio_path"] = d.get("sample_path") or ""
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
        raise HTTPException(400, "操作失败，请稍后重试")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 10MB")
    avatar_id = f"custom_{uuid.uuid4().hex[:10]}"
    filename = f"{avatar_id}.jpg"
    path = os.path.join(UPLOAD_DH_AVATAR_DIR, filename)
    try:
        # PIL 校验并统一转 RGB JPEG（透明/异常图片兜底）
        # 图像解码/编码耗时操作放入线程池，避免阻塞事件循环
        def _process_avatar() -> None:
            img = Image.open(__import__("io").BytesIO(content))
            img = img.convert("RGB")
            img.thumbnail((1024, 1024), Image.LANCZOS)
            img.save(path, "JPEG", quality=92)

        await asyncio.to_thread(_process_avatar)
    except Exception as e:
        raise HTTPException(400, "服务异常，请稍后重试") from e
    image_url = f"/uploads/dh_avatars/{filename}"
    conn = get_db()
    try:
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO digital_human_custom_avatars (id, user_id, name, style, gender, desc, emoji, image_url, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                avatar_id,
                user,
                (name or "我的形象").strip()[:20],
                "自定义形象",
                "自定义",
                (desc or "").strip()[:100],
                "🖼️",
                image_url,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "avatar": {"id": avatar_id, "name": name.strip()[:20] or "我的形象", "image_url": image_url, "is_custom": True}
    }


@router.post("/photo-avatar")
async def upload_photo_avatar(
    file: UploadFile = File(...),
    name: str = Form("我的照片形象"),
    current_user: dict = require_auth(),
):
    """照片数字人形象上传：校验正脸（mediapipe）+ 分辨率 ≥ 512px → 存入自定义形象。

    照片原图即推理素材（LivePortrait/Wav2Lip 引擎在生成时做检测/裁剪/对齐），
    前端缩略图直接展示原图。校验失败返回 400（不消耗配额）。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_IMG_EXT:
        raise HTTPException(400, "操作失败，请稍后重试")
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "照片不能超过 15MB")
    avatar_id = f"custom_{uuid.uuid4().hex[:10]}"
    filename = f"{avatar_id}.jpg"
    path = os.path.join(UPLOAD_DH_AVATAR_DIR, filename)
    try:
        def _process_photo() -> None:
            img = Image.open(BytesIO(content))
            img.load()
            w, h = img.size
            if min(w, h) < 512:
                raise HTTPException(400, "照片分辨率不足，请上传至少 512x512 的清晰正脸照片")
            if w / h > 3 or h / w > 3:
                raise HTTPException(400, "照片比例异常，请上传正常的人像照片")
            # 正脸检测：mediapipe 检测不到人脸/关键点 → 视为非真实正脸（漫画/截图/无人像）
            import cv2
            import numpy as np

            from live_portrait_engine import _face_align_params

            bgr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
            try:
                _face_align_params(bgr)
            except Exception as e:  # noqa: BLE001 — 检测失败统一转为友好提示
                raise HTTPException(400, "人像检测失败，请上传正面免冠清晰照片") from e
            img.convert("RGB").save(path, "JPEG", quality=92)

        await asyncio.to_thread(_process_photo)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, "服务异常，请稍后重试") from e
    image_url = f"/uploads/dh_avatars/{filename}"
    conn = get_db()
    try:
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO digital_human_custom_avatars (id, user_id, name, style, gender, desc, emoji, image_url, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                avatar_id,
                user,
                (name or "我的照片形象").strip()[:20],
                "照片数字人",
                "真人",
                "上传照片生成的数字人形象（支持口型同步）",
                "📷",
                image_url,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "avatar": {
            "id": avatar_id,
            "name": (name or "我的照片形象").strip()[:20],
            "image_url": image_url,
            "is_custom": True,
            "engine": "live_portrait",
        }
    }


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
            "SELECT image_url FROM digital_human_custom_avatars WHERE id=? AND user_id=?",
            (avatar_id, user),
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
        raise HTTPException(400, "操作失败，请稍后重试")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "音频不能超过 20MB")
    voice_id = f"custom_{uuid.uuid4().hex[:10]}"
    filename = f"{voice_id}{ext}"
    path = os.path.join(UPLOAD_DH_VOICE_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    # ffprobe 校验时长（无效音频拦截，避免下游渲染失败）
    # 子进程调用放入线程池，避免阻塞事件循环
    duration = await asyncio.to_thread(_audio_duration, path)
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
            (
                voice_id,
                user,
                (name or "我的声音").strip()[:20],
                (desc or "").strip()[:100],
                "🎙️",
                audio_url,
                round(duration, 1),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "voice": {
            "id": voice_id,
            "name": name.strip()[:20] or "我的声音",
            "audio_url": audio_url,
            "duration": round(duration, 1),
            "is_custom": True,
        }
    }


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
            "SELECT audio_url FROM digital_human_custom_voices WHERE id=? AND user_id=?",
            (voice_id, user),
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


# ── 声音克隆（v1 参数近似克隆：上传样本 → 基频分析 → 音色匹配 + 音调补偿） ──
@router.post("/voice-clone")
async def create_voice_clone(
    file: UploadFile = File(...),
    voice_name: str = Form(...),
    declare_authorized: str = Form(""),
    current_user: dict = require_auth(),
):
    """上传 10-60s 干净人声样本 → 克隆专属声音（异步任务分析匹配音色）。

    合规必选：declare_authorized 必须为 true（本人声音或已获授权），否则拒绝克隆。
    返回 task_id：轮询 GET /api/tasks/{task_id}，完成后在 GET /voice-clones 查看。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    if declare_authorized.strip().lower() not in ("true", "1", "yes"):
        raise HTTPException(400, "请先声明「本人声音或已获授权」后再进行声音克隆（合规必选）")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_AUDIO_EXT:
        raise HTTPException(400, "操作失败，请稍后重试")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "样本音频不能超过 20MB")
    clone_id = f"clone_{uuid.uuid4().hex[:10]}"
    filename = f"{clone_id}{ext}"
    path = os.path.join(UPLOAD_DH_VOICE_DIR, filename)
    with open(path, "wb") as f:
        f.write(content)
    # ffprobe 快速校验：无效音频 / 时长不在 10-60s 直接拦截（避免无效分析任务）
    duration = await asyncio.to_thread(_audio_duration, path)
    if duration <= 0:
        os.remove(path)
        raise HTTPException(400, "音频文件无效或无法解析，请重新上传")
    from voice_clone import MAX_SAMPLE_SECONDS, MIN_SAMPLE_SECONDS

    if duration < MIN_SAMPLE_SECONDS or duration > MAX_SAMPLE_SECONDS:
        os.remove(path)
        raise HTTPException(
            400, f"样本时长需在 {MIN_SAMPLE_SECONDS:.0f}-{MAX_SAMPLE_SECONDS:.0f} 秒之间（当前 {duration:.0f}s）"
        )
    task = create_task(
        "dh_voice_clone",
        {"clone_id": clone_id, "sample_path": path, "voice_name": (voice_name or "").strip()[:20]},
        username=user,
        user_id=uid,
    )
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "声音克隆任务已提交，分析完成自动入库，稍后刷新声音列表",
        "task": task,
    }


@router.get("/voice-clones")
async def list_voice_clones(current_user: dict = require_auth()):
    """我的克隆声音列表（含已吊销，供前端展示状态与吊销入口）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        _ensure_tables(conn)
        rows = conn.execute(
            "SELECT * FROM voice_clones WHERE user_id=? ORDER BY created_at DESC",
            (user,),
        ).fetchall()
    finally:
        conn.close()
    return {"voices": [dict(r) for r in rows]}


@router.post("/voice-clones/{clone_id}/revoke")
async def revoke_voice_clone(clone_id: str, current_user: dict = require_auth()):
    """吊销克隆音色（本人或管理员）：状态置 revoked 并删除样本文件，立即不可再用于生成。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT user_id, sample_path FROM voice_clones WHERE id=?", (clone_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "克隆声音不存在")
        if row["user_id"] != user and role != "admin":
            raise HTTPException(403, "无权吊销该克隆音色")
        conn.execute("UPDATE voice_clones SET status='revoked' WHERE id=?", (clone_id,))
        conn.commit()
    finally:
        conn.close()
    sample = row["sample_path"] or ""
    if sample and os.path.exists(sample):
        os.remove(sample)
    return {"success": True, "message": "克隆音色已吊销，不可再用于生成"}


# ── 请求模型 ──────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=5, max_length=5000, description="口播文案")
    avatar_id: str = Field("business-female", description="数字人形象ID")
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="声音ID")
    background_id: str = Field("tech", description="背景ID")
    scene_id: str = Field("product", description="场景模板ID")
    template_id: str = Field("", max_length=40, description="行业模板ID（可选，空=不套模板）")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    resolution: str = Field("720p", pattern="^(720p|1080p)$", description="视频分辨率")
    fps: int = Field(15, ge=10, le=30, description="帧率")
    watermark: bool | None = Field(None, description="水印：本地版由用户开关自由控制")
    engine: str = Field("2d", pattern="^(2d|live_portrait|sadtalker)$", description="引擎：2d=基础卡通渲染，live_portrait=照片数字人（需先创建照片形象），sadtalker=照片数字人高级版（3D 头部运动）")
    emotion: str = Field("auto", pattern="^(auto|neutral|happy|sad|angry|gentle|serious)$", description="情绪（v13.24）：auto=LLM自动判断，或 neutral/happy/sad/angry/gentle/serious 手动指定")


# 本地免费版：水印由用户开关控制
WATERMARK_TEXT = "AI 星火 · 数字人"

# 数字人硬拦截词：行为违规（营销诱导/诈骗/赌博/违禁），命中直接拒绝生成。
# 广告法极限词（最/第一/顶级等）仅作提示不拦截——口语叙事中"第一次/最好"
# 属正常表达，硬拦截会误伤正常文案，故从硬拦截列表剔除。
_HARD_BLOCK_WORDS = [
    "点击领取",
    "免费领取",
    "立即抢购",
    "限时抢购",
    "免费送",
    "免费领",
    "加微信",
    "加QQ",
    "扫码加",
    "私信我",
    "日赚",
    "月入过万",
    "躺赚",
    "暴富",
    "发财",
    "包治",
    "根治",
    "治愈",
    "神药",
    "特效",
    "赌博",
    "彩票",
    "时时彩",
    "六合彩",
    "翻墙",
    "科学上网",
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


@router.get("/templates")
async def list_templates():
    """行业模板库：带货种草/知识口播/新闻播报/课程讲解/品牌介绍。

    每模板含场景背景一键填充（scene/background/voice/speed）、
    字幕样式（位置/配色/字号）、片头片尾引导语、推荐文案结构。
    """
    return {"templates": INDUSTRY_TEMPLATES}


@router.post("/script-check")
async def script_check(req: ScriptCheckRequest, current_user: dict = require_auth()):
    """v15 口播文案质量体检：面向 TTS 朗读与口型同步的文案层检查。

    长句无停顿 / emoji / 长数字 / 长英文等会直接导致口型时间轴与
    配音错位；返回问题清单 + 自动修复版文案（可一键应用）。
    """
    return check_script_quality(req.text)


# ── v14.0 音频缓存：同文案+同音色+同速度复用 TTS 结果（省通道调用/网络等待） ──
_TTS_KEY_LOCKS: dict[str, threading.Lock] = {}
_TTS_KEY_LOCKS_GUARD = threading.Lock()
_TTS_CACHE_MAX_ROWS = 500  # 缓存行数上限（超出按最后命中时间清理最旧的 100 条）


def _tts_cache_filename(cache_key: str) -> str:
    """缓存音频文件路径（uploads/audio/tts_cache/{key}.mp3）。"""
    return os.path.join(UPLOAD_AUDIO_DIR, "tts_cache", f"{cache_key}.mp3")


def _tts_cache_key(text: str, voice: str, speed: float, pitch: int, emotion: str = "") -> str:
    import hashlib

    # v13.28 前缀 v28：情绪改 pitch 表达后旧 style 缓存音频失效（语速差异 5 倍）
    return hashlib.sha256(f"v28|{text}|{voice}|{speed}|{pitch}|{emotion}".encode()).hexdigest()[:16]


def _tts_key_lock(cache_key: str) -> threading.Lock:
    """进程内 per-key 锁：批量预热与单条生成并发时同一 key 只合成一次。"""
    with _TTS_KEY_LOCKS_GUARD:
        lock = _TTS_KEY_LOCKS.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _TTS_KEY_LOCKS[cache_key] = lock
        return lock


def _tts_cached(text: str, voice: str, speed: float, pitch: int = 0, emotion: str = "") -> tuple[str, str]:
    """带缓存的 TTS 合成，返回 (audio_path, audio_url)。

    - key = hash(text|voice|speed|pitch|emotion)：同文案同音色同语速同情绪直接复用
      （跨用户共享，TTS 通道有成本与限速，命中零等待；批量任务 TTS 预热即依赖此机制）
    - 未命中：合成后落缓存（文件 + 表），行数超限按最后命中时间清理最旧 100 条
    """
    cache_key = _tts_cache_key(text, voice, speed, pitch, emotion)
    lock = _tts_key_lock(cache_key)
    with lock:
        path = _tts_cache_filename(cache_key)
        url = f"/uploads/audio/tts_cache/{cache_key}.mp3"
        with get_db_context() as conn:
            _ensure_tables(conn)
            row = conn.execute(
                "SELECT audio_url FROM digital_human_tts_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        if row and os.path.exists(path) and _valid_audio(path):
            with get_db_context() as conn:
                conn.execute(
                    "UPDATE digital_human_tts_cache SET hits=hits+1, last_hit=? WHERE cache_key=?",
                    (datetime.now().isoformat(), cache_key),
                )
            return path, row["audio_url"]
        from voice_factory import _tts_one

        audio_bytes = _tts_one(text, voice, speed, pitch, emotion)
        if not audio_bytes or len(audio_bytes) < 512:
            raise RuntimeError("TTS 生成的音频无效（文件过小）")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(audio_bytes)
        # 写入后再完整校验（ffprobe 可解析），防假数据落盘
        if not _valid_audio(path):
            try:
                os.remove(path)
            except OSError:
                pass
            raise RuntimeError("TTS 生成的音频无效（无法解析）")
        now = datetime.now().isoformat()
        with get_db_context() as conn:
            _ensure_tables(conn)
            conn.execute(
                """INSERT OR REPLACE INTO digital_human_tts_cache
                   (cache_key, text, voice, speed, pitch, audio_url, hits, created_at, last_hit)
                   VALUES (?,?,?,?,?,?,1,?,?)""",
                (cache_key, text[:200], voice, speed, pitch, url, now, now),
            )
            # 行数超限：按最后命中时间清理最旧 100 条（连同文件，防磁盘膨胀）
            over = conn.execute("SELECT COUNT(*) AS c FROM digital_human_tts_cache").fetchone()["c"]
            over -= _TTS_CACHE_MAX_ROWS
            if over > 0:
                stale = conn.execute(
                    """SELECT cache_key FROM digital_human_tts_cache
                       ORDER BY COALESCE(last_hit, created_at) ASC LIMIT ?""",
                    (over,),
                ).fetchall()
                for r in stale:
                    conn.execute("DELETE FROM digital_human_tts_cache WHERE cache_key=?", (r["cache_key"],))
                    fp = _tts_cache_filename(r["cache_key"])
                    if os.path.exists(fp):
                        try:
                            os.remove(fp)
                        except OSError:
                            pass
        return path, url


# ── 写真肖像 API ────────────────────────────────────────────


@router.get("/portraits")
async def list_portraits():
    """列出所有已缓存的数字人写真肖像。"""
    portraits = []
    for avatar in AVATARS:
        portrait_path = _get_portrait_path(avatar["id"])
        exists = os.path.exists(portrait_path)
        portraits.append(
            {
                "avatar_id": avatar["id"],
                "avatar_name": avatar["name"],
                "avatar_emoji": avatar["emoji"],
                "exists": exists,
                "url": _get_portrait_url(avatar["id"]) if exists else None,
            }
        )
    return {"portraits": portraits, "total": len(portraits), "cached": sum(1 for p in portraits if p["exists"])}


@router.post("/generate-portrait/{avatar_id}")
async def generate_portrait(avatar_id: str, current_user: dict = require_auth()):
    """为指定数字人形象生成 AI 写真肖像（如已存在则跳过）。

    返回写真图片的访问 URL。
    """
    avatar = next((a for a in AVATARS if a["id"] == avatar_id), None)
    if not avatar:
        raise HTTPException(404, "操作失败，请稍后重试")

    portrait_path = _get_portrait_path(avatar_id)
    if os.path.exists(portrait_path):
        return {
            "avatar_id": avatar_id,
            "avatar_name": avatar["name"],
            "url": _get_portrait_url(avatar_id),
            "cached": True,
            "message": f"{avatar['name']} 写真已存在，直接使用缓存",
        }

    _uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    result = await asyncio.to_thread(_generate_portrait, avatar_id, _uid)
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
            results.append(
                {
                    "avatar_id": avatar["id"],
                    "avatar_name": avatar["name"],
                    "success": True,
                    "cached": True,
                }
            )
            continue
        _uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
        path = await asyncio.to_thread(_generate_portrait, avatar["id"], _uid)
        results.append(
            {
                "avatar_id": avatar["id"],
                "avatar_name": avatar["name"],
                "success": path is not None,
                "cached": False,
            }
        )
    return {
        "results": results,
        "total": len(results),
        "generated": sum(1 for r in results if r["success"] and not r["cached"]),
        "cached": sum(1 for r in results if r["cached"]),
        "failed": sum(1 for r in results if not r["success"]),
    }



def _dh_render_with_chain(
    req, avatar, bg, audio_path, video_path, optimized_text, use_watermark, subtitle_style,
    opening_text, closing_text, emotion, progress, record_id,
) -> tuple:
    """引擎选择链渲染（sadtalker → live_portrait → 2d），返回 (engine_used, render_size)。"""
    sadtalker_render_size: int | None = None
    engine_chain = {
        "sadtalker": ["sadtalker", "live_portrait", "2d"],
        "live_portrait": ["live_portrait", "2d"],
        "2d": ["2d"],
    }[req.engine]
    render_err: Exception | None = None
    for eng in engine_chain:
        try:
            if eng == "sadtalker":
                from digital_human_sadtalker import generate_with_sadtalker

                sad_result = generate_with_sadtalker(
                    photo_path=avatar["local_image_path"],
                    audio_path=audio_path,
                    output_path=video_path,
                    resolution=req.resolution,
                    watermark=use_watermark,
                    progress=progress,
                    emotion=emotion,
                )
                sadtalker_render_size = sad_result.get("render_size")
            elif eng == "live_portrait":
                from live_portrait_engine import generate_from_photo

                generate_from_photo(
                    photo_path=avatar["local_image_path"],
                    audio_path=audio_path,
                    output_path=video_path,
                    resolution=req.resolution,
                    watermark=use_watermark,
                    progress=progress,
                )
            else:
                _render_video(
                    text=optimized_text[:200],
                    avatar=avatar,
                    bg=bg,
                    audio_path=audio_path,
                    output_path=video_path,
                    resolution=req.resolution,
                    fps=req.fps,
                    watermark=use_watermark,
                    subtitle_style=subtitle_style,
                    opening=opening_text,
                    closing=closing_text,
                    emotion=emotion,
                )
            render_err = None
            return eng, sadtalker_render_size
        except Exception as e:  # noqa: BLE001 — 引擎失败尝试降级
            render_err = e
            logger.warning(f"数字人渲染失败（engine={eng}），准备降级: {e}")
    raise render_err if render_err else RuntimeError("渲染失败")


def _dh_save_record(conn, record_id: str, user: str, req, avatar, voice, bg, optimized_text: str, status: str, audio_url: str, video_url: str, error_msg: str, use_watermark: bool, engine_used: str, emotion: str) -> None:
    """保存数字人生成记录。"""
    conn.execute(
        """INSERT INTO digital_human_records
           (id, user_id, avatar_id, avatar_name, voice_id, voice_name,
            background_id, scene_id, template_id, text, text_length, status,
            audio_url, video_url, error, resolution, fps, watermark, engine, emotion, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) """,
        (
            record_id,
            user,
            req.avatar_id,
            avatar["name"],
            req.voice_id,
            voice["name"],
            req.background_id,
            req.scene_id,
            req.template_id,
            optimized_text,
            len(optimized_text),
            status,
            audio_url,
            video_url,
            error_msg,
            req.resolution,
            req.fps,
            1 if use_watermark else 0,
            engine_used,
            emotion,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()



def _dh_content_scan(text: str) -> list:
    """内容安全扫描：返回风险词列表（硬违规词直接抛 400）。"""
    try:
        from content_strategy import _scan_text

        hits = _scan_text(text)
    except Exception:
        hits = []
    lower_text = text.lower()
    hard_hits = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower_text]
    if hard_hits:
        raise HTTPException(400, "操作失败，请稍后重试")
    return list(dict.fromkeys(h["word"] for h in hits))


def _dh_validate_resources(req, user: str) -> tuple:
    """验证形象/声音/背景/场景（内置 + 用户自定义 + 克隆）+ 行业模板。"""
    avatar = next((a for a in AVATARS if a["id"] == req.avatar_id), None)
    voice = _lookup_voice(user, req.voice_id)
    if not avatar and req.avatar_id.startswith("custom_"):
        avatar = _load_custom_avatars(user).get(req.avatar_id)
    if not avatar:
        raise HTTPException(400, f"数字人形象不存在（{req.avatar_id}），请重新选择")
    if not voice:
        raise HTTPException(400, f"配音音色不存在（{req.voice_id}），请重新选择")
    bg = next((b for b in BACKGROUNDS if b["id"] == req.background_id), None)
    if not bg:
        raise HTTPException(400, f"背景场景不存在（{req.background_id}），请重新选择")
    if req.engine in ("live_portrait", "sadtalker"):
        if not (avatar.get("is_custom") and avatar.get("local_image_path") and os.path.exists(avatar["local_image_path"])):
            raise HTTPException(400, "照片数字人引擎需要先上传照片形象（请先在「照片数字人」上传正脸照片）")
    template = next((t for t in INDUSTRY_TEMPLATES if t["id"] == req.template_id), None)
    if req.template_id and not template:
        raise HTTPException(400, f"未知行业模板（{req.template_id}），请重新选择")
    return avatar, voice, bg, template


def _dh_generate_audio(voice: dict, req, optimized_text: str, emotion: str, _report) -> tuple:
    """TTS 配音：自定义声音直接用上传音频；克隆/内置走 AI 合成。返回 (audio_path, audio_url)。"""
    audio_path, audio_url = "", ""
    if voice.get("is_custom") and not voice.get("is_clone"):
        audio_path = voice.get("local_audio_path") or ""
        if audio_path and os.path.exists(audio_path):
            audio_url = voice["audio_url"]
        else:
            raise RuntimeError("自定义声音文件缺失，请重新上传")
    if not audio_url:
        _report(20, "正在合成配音…")
        tts_voice = req.voice_id
        tts_pitch = 0
        if voice.get("is_clone"):
            tts_voice = voice.get("edge_voice") or req.voice_id
            tts_pitch = int(voice.get("pitch_hz") or 0)
        tts_emotion = EMOTION_TTS_STYLE.get(emotion, "")
        audio_path, audio_url = _tts_cached(optimized_text, tts_voice, req.speed, tts_pitch, tts_emotion)
        if not audio_path or not os.path.exists(audio_path) or os.path.getsize(audio_path) < 512:
            audio_path = ""
            raise RuntimeError("TTS 生成的音频无效（文件过小）")
    return audio_path, audio_url


def _dh_quota_setup(uid: str, req, role: str) -> tuple:
    """额度扣费 + 记录ID + 水印策略。返回 (quota, record_id, conn, use_watermark)。"""
    from common.auth import consume_quota, get_quota_info

    quota = consume_quota(uid)
    if not quota.get("allowed"):
        raise HTTPException(
            402,
            "今日数字人生成次数已用完，可在次日 0 点自动恢复",
        )
    quota_info = get_quota_info(uid)
    record_id = f"dh_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    _ensure_tables(conn)
    # 本地免费版：水印完全由用户开关控制（无会员水印策略）
    use_watermark = bool(req.watermark)
    return quota, record_id, conn, use_watermark


def _dh_final_failure(stage: str, audio_path: str, audio_error: str) -> tuple:
    """最终失败分类：audio_only（音频成功、视频失败）vs failed（配音未生成）。"""
    if stage == "render" and audio_path and os.path.exists(audio_path):
        return "audio_only", f"{audio_error}，已生成配音音频"
    return "failed", audio_error or "配音生成失败"


def _dh_validate_video(video_path: str) -> None:
    """校验渲染视频有效（非 0KB/损坏），无效删除并抛错。"""
    if not os.path.exists(video_path) or not _valid_video(video_path):
        try:
            os.remove(video_path)
        except OSError:
            pass
        raise RuntimeError("视频渲染结果无效（文件缺失或损坏）")

def _generate_one(  # noqa: C901
    req: GenerateRequest,
    user: str,
    uid: str,
    role: str = "",
    progress: Callable[[float, str], None] | None = None,
) -> dict:
    """单条数字人视频生成流水线（供单条接口与批量任务复用）。

    流程：
    1. 文案预处理（LLM优化口播文案流畅度）
    2. TTS配音（调用配音工坊音频生成）
    3. 视频合成（数字人形象+配音+背景合成为口播视频）

    progress: 可选进度回调 (percent 0-100, stage 文案)，异步任务模式实时回报进度。
    """
    start = datetime.now()
    sadtalker_render_size: int | None = None  # v13.23 真实推理分辨率（512/256），TTS 失败等路径下保持 None
    # v13.24 情绪：auto=LLM 判断主导情绪（失败回退 neutral）；手动直接使用
    # getattr 兼容旧调用方（测试/脚本直接传无 emotion 字段的请求对象）
    emotion = getattr(req, "emotion", "auto")
    if emotion == "auto":
        emotion = _detect_emotion(req.text)

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    # 0.5 内容安全：硬违规词直接拒绝生成；广告法极限词/中风险词放行但提示
    risk_hits = _dh_content_scan(req.text)
    # 验证形象/声音/背景/场景 + 行业模板
    avatar, voice, bg, template = _dh_validate_resources(req, user)
    subtitle_style = template.get("subtitle") if template else None
    opening_text = template.get("opening", "") if template else ""
    closing_text = template.get("closing", "") if template else ""

    # 0. 商业配额 + 记录ID + 水印策略
    quota, record_id, conn, use_watermark = _dh_quota_setup(uid, req, role)

    # 1. 文案 — 字幕与配音必须与用户输入完全一致：
    # 之前 LLM 优化环节会把原文改写为带 Markdown 标记（#、**、---）的口播脚本，
    # 导致字幕显示“乱码/不是用户输入的内容”，此处直接使用原文（仅清洗换行）。
    optimized_text = _clean_script_text(req.text)
    _report(15, "文案已就绪，正在合成配音…")

    # 2+3. 配音与视频合成（v13.0：失败自动重试 1 次；配额已在上方只扣一次，重试不重复扣费）
    # stage 埋点：失败原因带 [stage:tts]/[stage:render] 前缀，便于诊断与前端提示
    audio_url, audio_path, audio_error = "", "", ""
    video_url = ""
    status = "failed"
    error_msg = ""
    engine_used = req.engine  # 记录实际使用的引擎（降级后为 2d）
    for attempt in (1, 2):
        stage = "tts"
        try:
            # 2. TTS 配音 — 内置音色走 AI 合成；自定义声音直接用上传音频；克隆声音用匹配音色
            audio_path, audio_url = _dh_generate_audio(voice, req, optimized_text, emotion, _report)

            # 3. 视频合成 — ffmpeg 将背景图+音频合成为 MP4
            # 渲染为 CPU 密集操作，受全局并发池保护（同批次多任务串行，跨批次限并发数）
            stage = "render"
            _report(55, "配音完成，正在渲染数字人视频…")
            if audio_path and os.path.exists(audio_path):
                if not _RENDER_SLOT.acquire(timeout=600):
                    raise RuntimeError("当前视频渲染任务繁忙，请稍后重试")
                try:
                    video_filename = f"{record_id}.mp4"
                    video_path = os.path.join(UPLOAD_VIDEO_DIR, video_filename)
                    engine_used, sadtalker_render_size = _dh_render_with_chain(
                        req, avatar, bg, audio_path, video_path, optimized_text,
                        use_watermark, subtitle_style, opening_text, closing_text,
                        emotion, progress, record_id,
                    )
                finally:
                    _RENDER_SLOT.release()
                # 视频有效性校验：防止渲染引擎产出 0KB/损坏文件被误标记成功
                _dh_validate_video(video_path)
                video_url = f"/uploads/videos/{video_filename}"
                _report(85, "视频渲染完成，正在保存记录…")
            status = "done"
            break
        except HTTPException:
            raise  # 4xx/配额类错误不重试
        except Exception as e:
            logger.warning(f"数字人生成第 {attempt} 次失败（stage={stage}）: {e}")
            audio_error = f"[stage:{stage}] {e}"
            if attempt < 2:
                continue
            status, error_msg = _dh_final_failure(stage, audio_path, audio_error)

    # 4. 保存记录（含商业参数：分辨率/帧率/水印/引擎/行业模板/情绪）
    _dh_save_record(conn, record_id, user, req, avatar, voice, bg, optimized_text,
                    status, audio_url, video_url, error_msg, use_watermark, engine_used, emotion)
    conn.close()
    _report(95, "记录已保存")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("digital_human", len(req.text), len(optimized_text), elapsed, success=not error_msg, error=error_msg or "", user_id=str(user or ""))
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
        "engine": engine_used,
        "render_size": sadtalker_render_size,
        "emotion": emotion,
        "quota_remaining": quota.get("remaining"),
        "sensitive_warning": (
            f"文案含风险词（{', '.join(risk_hits[:6])}），发布到平台时可能限流，建议修改" if risk_hits else ""
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


# v13.24 数字人情绪系统：统一情绪枚举 + TTS 风格映射
# happy→cheerful、sad→sad、angry→angry、gentle→gentle、serious→serious、neutral→无风格
EMOTION_OPTIONS = ("neutral", "happy", "sad", "angry", "gentle", "serious")
EMOTION_TTS_STYLE = {
    "neutral": "",
    "happy": "cheerful",
    "sad": "sad",
    "angry": "angry",
    "gentle": "gentle",
    "serious": "serious",
}
_EMOTION_ALIAS = {
    "欢快": "happy", "开心": "happy", "高兴": "happy", "快乐": "happy", "兴奋": "happy",
    "悲伤": "sad", "难过": "sad", "伤心": "sad", "忧伤": "sad", "失落": "sad",
    "激昂": "angry", "愤怒": "angry", "激动": "angry", "生气": "angry", "激情": "angry",
    "温柔": "gentle", "平和": "gentle", "舒缓": "gentle", "亲切": "gentle",
    "严肃": "serious", "认真": "serious", "郑重": "serious", "正式": "serious",
    "自然": "neutral", "中性": "neutral", "平静": "neutral", "平淡": "neutral",
}


def _detect_emotion(text: str) -> str:
    """LLM 判断文案主导情绪（v13.24）；失败/非法输出回退 neutral，绝不阻塞生成。"""
    try:
        from common.llm import call_llm

        raw = call_llm(
            "你是情绪分析师。判断一段口播文案的主导情绪，只输出一个英文单词："
            + "neutral / happy / sad / angry / gentle / serious。",
            f"文案：\n{text[:1500]}",
            max_tokens=16,
            temperature=0.3,
            timeout=30,
        )
    except Exception as e:
        logger.warning(f"情绪标注 LLM 失败，回退 neutral: {e}")
        return "neutral"
    emo = (raw or "").strip().lower().strip('\"\'。，,. ')
    if emo in EMOTION_OPTIONS:
        return emo
    # LLM 可能输出中文标签或带说明：模糊匹配别名
    lower = (raw or "").lower()
    for k, v in _EMOTION_ALIAS.items():
        if k in lower:
            return v
    logger.warning(f"情绪标注结果非法（{raw!r}），回退 neutral")
    return "neutral"


def _precheck_generate(req: GenerateRequest, uid: str, user: str) -> None:  # noqa: C901 — 多条件校验，逐项分支保持可读
    """异步提交前快速失败预检：违规词 / 今日额度 / 素材参数（不消耗配额，执行时再扣）。"""
    try:
        from content_strategy import _scan_text

        _scan_text(req.text)  # 触发内容策略扫描（软校验，结果不阻断预检）
    except Exception:
        pass
    lower_text = req.text.lower()
    hard_hits = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower_text]
    if hard_hits:
        raise HTTPException(400, "操作失败，请稍后重试")
    from common.auth import get_quota_info

    qi = get_quota_info(uid) or {}
    remaining = qi.get("remaining_today")
    if remaining is not None and remaining <= 0:
        raise HTTPException(402, "今日数字人生成次数已用完，可在次日 0 点自动恢复")
    avatar = next((a for a in AVATARS if a["id"] == req.avatar_id), None)
    voice = _lookup_voice(user, req.voice_id)
    if not avatar and req.avatar_id.startswith("custom_"):
        avatar = _load_custom_avatars(user).get(req.avatar_id)
    if not avatar:
        raise HTTPException(400, f"数字人形象不存在（{req.avatar_id}），请重新选择")
    if not voice:
        raise HTTPException(400, f"未知声音（{req.voice_id}），请重新选择")
    if not next((b for b in BACKGROUNDS if b["id"] == req.background_id), None):
        raise HTTPException(400, f"背景场景不存在（{req.background_id}），请重新选择")
    # 照片数字人引擎：必须使用照片形象（photo-avatar 创建，带本地原图）
    if req.engine == "live_portrait":
        if not (avatar.get("is_custom") and avatar.get("local_image_path")):
            raise HTTPException(400, "照片数字人引擎需要先上传照片形象（请先在「照片数字人」上传正脸照片）")
        if not os.path.exists(avatar["local_image_path"]):
            raise HTTPException(400, "照片形象文件缺失，请重新上传")


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
    page: int = 1,
    page_size: int = 20,
    status: str = "",
    q: str = "",
    current_user: dict = require_auth(),
):
    """历史生成记录（分页 / 按状态筛选 / 关键词搜索）。

    text 字段防御性清洗：兼容历史脏数据（误存 Python dict 字面量），
    解析出真实文案后再返回，避免前端直接渲染数据结构。
    """
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
        f"SELECT COUNT(*) FROM digital_human_records WHERE {' AND '.join(where)}",
        args,
    ).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM digital_human_records WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        args + [page_size, (page - 1) * page_size],
    ).fetchall()
    conn.close()
    items = []
    for r in rows:
        item = dict(r)
        item["text"] = _clean_record_text(item.get("text") or "")
        items.append(item)
    return {"total": total, "page": page, "page_size": page_size, "items": items}


def _clean_record_text(raw: str) -> str:
    """兼容历史脏数据：若 text 被误存为 Python dict 字面量（如 {"text": "..."}），安全解析出真实文案。"""
    if not raw or not raw.lstrip().startswith("{"):
        return raw
    try:
        import ast

        parsed = ast.literal_eval(raw)
        if isinstance(parsed, dict) and parsed.get("text"):
            return str(parsed["text"])
    except (ValueError, SyntaxError):
        pass
    return raw


class BatchDeleteRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, description="记录ID列表")


def _url_to_path(url: str) -> str:
    """/uploads/audio/x.mp3 → backend/uploads/audio/x.mp3（统一 URL 到磁盘路径解析）。"""
    return os.path.join(_BASE_DIR, url.lstrip("/"))


def _delete_record_files(conn, record_id: str) -> None:
    """删除记录关联的音频/视频文件（释放磁盘空间）。"""
    row = conn.execute(
        "SELECT audio_url, video_url FROM digital_human_records WHERE id=?",
        (record_id,),
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
    template_id: str = Field("", max_length=40, description="行业模板ID（可选）")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    resolution: str = Field("720p", pattern="^(720p|1080p)$", description="视频分辨率")
    fps: int = Field(15, ge=10, le=30, description="帧率")
    watermark: bool | None = Field(None, description="水印：本地版由用户开关自由控制")
    engine: str = Field("2d", pattern="^(2d|live_portrait|sadtalker)$", description="引擎：2d=基础卡通渲染，live_portrait=照片数字人（需先创建照片形象），sadtalker=照片数字人高级版（3D 头部运动）")
    emotion: str = Field("auto", pattern="^(auto|neutral|happy|sad|angry|gentle|serious)$", description="情绪（v13.24）：auto=LLM自动判断，或手动指定")


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
            "SELECT * FROM digital_human_batch_items WHERE batch_id=? ORDER BY idx",
            (batch_id,),
        ).fetchall()
    finally:
        conn.close()
    return {
        "id": row["id"],
        "user": row["user_id"],
        "status": row["status"],
        "total": row["total"],
        "done": row["success"] + row["failed"] + row["skipped"],
        "success": row["success"],
        "failed": row["failed"],
        "skipped": row["skipped"],
        "avatar_id": row["avatar_id"],
        "avatar_name": row["avatar_name"],
        "resolution": row["resolution"],
        "fps": row["fps"],
        "voice_id": row["voice_id"],
        "background_id": row["background_id"],
        "speed": row["speed"],
        "engine": row["engine"] if "engine" in row.keys() else "2d",
        "emotion": row["emotion"] if "emotion" in row.keys() else "auto",
        "created_at": row["created_at"],
        "finished_at": row["finished_at"],
        "items": [
            {
                "index": r["idx"],
                "text_preview": r["text"][:40],
                "status": r["status"],
                "error": r["error"],
                "record_id": r["record_id"],
                "audio_url": r["audio_url"],
                "video_url": r["video_url"],
                "watermark": bool(r["watermark"]),
                "sensitive_warning": r["sensitive_warning"],
            }
            for r in items
        ],
    }



def _batch_process_one(batch_id: str, i: int, text: str, req, user: str, uid: str, role: str, task: dict, item: dict) -> None:
    """批量单条处理：校验 → 生成 → 落库。"""
    if len(text) < 5:
        item["status"] = "failed"
        item["error"] = "文案太短（至少 5 字）"
    elif any(w.lower() in text.lower() for w in _HARD_BLOCK_WORDS):
        item["status"] = "failed"
        item["error"] = "文案含违规词，已拦截"
    else:
        try:
            sub = GenerateRequest(
                text=text,
                avatar_id=req.avatar_id,
                voice_id=req.voice_id,
                background_id=req.background_id,
                scene_id=req.scene_id,
                template_id=req.template_id,
                speed=req.speed,
                resolution=req.resolution,
                fps=req.fps,
                watermark=req.watermark,
                engine=req.engine,
                emotion=req.emotion,
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
                item["status"] = "failed"
                item["error"] = (res.get("error") or "生成失败")[:120]
                from common.auth import refund_quota

                refund_quota(uid)
        except HTTPException as e:
            item["status"] = "skipped" if e.status_code == 402 else "failed"
            item["error"] = str(e.detail)[:120]
        except Exception as e:
            logger.exception("batch item failed %s", batch_id)
            item["status"] = "failed"
            item["error"] = str(e)[:120]
            from common.auth import refund_quota

            refund_quota(uid)
    task["done"] += 1
    task[item["status"]] += 1
    with get_db_context() as conn:
        conn.execute(
            """UPDATE digital_human_batch_items
               SET status=?, error=?, record_id=?, audio_url=?, video_url=?,
                   watermark=?, sensitive_warning=?
               WHERE batch_id=? AND idx=?""",
            (
                item["status"],
                item["error"],
                item.get("record_id", ""),
                item.get("audio_url", ""),
                item.get("video_url", ""),
                1 if item.get("watermark") else 0,
                item.get("sensitive_warning", ""),
                batch_id,
                i,
            ),
        )


def _prefetch_tts(texts: list, indexes: list | None, req, user: str) -> None:
    """并行 TTS 预热：合法文案写入音频缓存，供主循环渲染时命中。"""
    try:
        voice_info = _lookup_voice(user, req.voice_id)
    except Exception:  # noqa: BLE001 — 预热失败不影响主流程
        return
    if not voice_info:
        return
    if voice_info.get("is_custom") and not voice_info.get("is_clone"):
        return
    tts_voice = voice_info.get("edge_voice") or req.voice_id if voice_info.get("is_clone") else req.voice_id
    tts_pitch = int(voice_info.get("pitch_hz") or 0) if voice_info.get("is_clone") else 0
    warm = [
        i
        for i in (indexes if indexes is not None else range(len(texts)))
        if 5 <= len(texts[i].strip()) <= 10000
        and not any(w.lower() in texts[i].lower() for w in _HARD_BLOCK_WORDS)
    ]
    if not warm:
        return

    def _warm(i: int) -> None:
        try:
            emo = req.emotion if req.emotion != "auto" else _detect_emotion(texts[i].strip())
            _tts_cached(texts[i].strip(), tts_voice, req.speed, tts_pitch, EMOTION_TTS_STYLE.get(emo, ""))
        except Exception as e:  # noqa: BLE001 — 预热失败仅告警，主流程会再合成
            logger.warning(f"批量 TTS 预热失败 idx={i}: {e}")

    with ThreadPoolExecutor(max_workers=min(4, len(warm))) as pool:
        list(pool.map(_warm, warm))

def _batch_worker(  # noqa: C901 — 批量主循环含预检/TTS预热/重试多分支，逐段可读
    batch_id: str,
    texts: list[str],
    req: BatchGenerateRequest,
    user: str,
    uid: str,
    role: str,
    indexes: list[int] | None = None,
) -> None:
    """后台批量生成：逐条走完整流水线；违规词/超短文案直接失败（不浪费配额）。

    indexes 非空时表示部分重试（只处理指定下标）；每条结果实时落库，进程重启可从 DB 恢复。
    v14.0 并行流水线：渲染前先并行预热全部文案配音（写音频缓存），逐条渲染时
    TTS 缓存命中直接跳过合成阶段，TTS 总耗时从串行 n 条降到 ≈n/4 条。
    """
    task = _BATCH_TASKS[batch_id]

    prefetch = threading.Thread(target=_prefetch_tts, args=(texts, indexes, req, user), daemon=True)
    prefetch.start()
    try:
        for i in indexes if indexes is not None else range(len(texts)):
            item = task["items"][i]
            text = texts[i].strip()
            _batch_process_one(batch_id, i, text, req, user, uid, role, task, item)
    except Exception:
        logger.exception("batch worker crashed %s", batch_id)
        with get_db_context() as conn:
            conn.execute(
                "UPDATE digital_human_batches SET status='interrupted', finished_at=? WHERE id=?",
                (datetime.now().isoformat(), batch_id),
            )
        task["status"] = "interrupted"
        prefetch.join(timeout=30)
        return
    prefetch.join(timeout=120)  # 等待 TTS 预热收尾（渲染期间应已全部完成）
    task["status"] = "done"
    task["finished_at"] = datetime.now().isoformat()
    with get_db_context() as conn:
        conn.execute(
            """UPDATE digital_human_batches
               SET status=?, success=?, failed=?, skipped=?, finished_at=?
               WHERE id=?""",
            (task["status"], task["success"], task["failed"], task["skipped"], task["finished_at"], batch_id),
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
        raise HTTPException(402, "今日生成次数已用完，可在次日 0 点自动恢复")
    # 形象名校验（zip 打包文件名使用）
    avatar = next((a for a in AVATARS if a["id"] == req.avatar_id), None)
    avatar_name = avatar["name"] if avatar else req.avatar_id
    batch_id = f"dhb_{uuid.uuid4().hex[:10]}"
    items = [
        {
            "index": i,
            "text_preview": t[:40],
            "status": "pending",
            "error": "",
            "record_id": "",
            "audio_url": "",
            "video_url": "",
            "watermark": False,
            "sensitive_warning": "",
        }
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
                avatar_id, avatar_name, resolution, fps, voice_id, background_id, speed, engine, emotion,
                created_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) """,
            (
                batch_id,
                user,
                "running",
                len(texts),
                0,
                0,
                0,
                req.avatar_id,
                avatar_name,
                req.resolution,
                req.fps,
                req.voice_id,
                req.background_id,
                req.speed,
                req.engine,
                req.emotion,
                datetime.now().isoformat(),
                "",
            ),
        )
        for i, t in enumerate(texts):
            conn.execute(
                "INSERT INTO digital_human_batch_items (batch_id, idx, text, status) VALUES (?,?,?,?)",
                (batch_id, i, t, "pending"),
            )
    task = {
        "id": batch_id,
        "user": user,
        "status": "running",
        "total": len(texts),
        "done": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "avatar_id": req.avatar_id,
        "avatar_name": avatar_name,
        "resolution": req.resolution,
        "fps": req.fps,
        "voice_id": req.voice_id,
        "background_id": req.background_id,
        "speed": req.speed,
        "engine": req.engine,
        "emotion": req.emotion,
        "created_at": datetime.now().isoformat(),
        "finished_at": "",
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
        "batch_id": batch_id,
        "total": len(texts),
        "status": "running",
        "avatar_name": avatar_name,
        "resolution": req.resolution,
        "fps": req.fps,
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
        item["index"]
        for item in task["items"]
        if item["status"] == "failed" and "违规词" not in item["error"] and "文案太短" not in item["error"]
    ]
    if not retry_indexes:
        raise HTTPException(400, "失败项均为内容问题（违规词/文案过短），无需重试")
    # 完整文案从 DB 读取（text_preview 被截断，重试必须用原文）
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT idx, text FROM digital_human_batch_items WHERE batch_id=? ORDER BY idx",
            (batch_id,),
        ).fetchall()
    full_texts = [r["text"] for r in rows]
    req = BatchGenerateRequest(
        texts=full_texts,
        avatar_id=task["avatar_id"],
        voice_id=task["voice_id"],
        background_id=task["background_id"],
        scene_id="product",
        speed=task["speed"],
        resolution=task["resolution"],
        fps=task["fps"],
        watermark=None,
        engine=task.get("engine", "2d"),
        emotion=task.get("emotion", "auto"),  # v13.24 重试保持原情绪，避免回落 auto 重新 LLM 判断
    )
    # 重建任务（失败项重置为 pending，其余保持原结果）
    new_items = [dict(item) for item in task["items"]]
    for i in retry_indexes:
        new_items[i].update(
            status="pending", error="", record_id="", audio_url="", video_url="", watermark=False, sensitive_warning=""
        )
    new_task = {
        "id": batch_id,
        "user": user,
        "status": "running",
        "total": task["total"],
        "done": task["total"] - len(retry_indexes),
        "success": task["success"],
        "failed": task["failed"] - len(retry_indexes),
        "skipped": task["skipped"],
        "avatar_id": task["avatar_id"],
        "avatar_name": task["avatar_name"],
        "resolution": task["resolution"],
        "fps": task["fps"],
        "voice_id": task["voice_id"],
        "background_id": task["background_id"],
        "speed": task["speed"],
        "engine": task.get("engine", "2d"),
        "created_at": task["created_at"],
        "finished_at": "",
        "items": new_items,
    }
    with _BATCH_LOCK:
        _BATCH_TASKS[batch_id] = new_task
    with get_db_context() as conn:
        conn.execute(
            "UPDATE digital_human_batches SET status='running', finished_at='' WHERE id=?",
            (batch_id,),
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
    template_id: str = Field("", max_length=40, description="行业模板ID（可选，按模板推荐结构生成）")
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
def script_assist(req: ScriptAssistRequest, current_user: dict = require_auth()):
    """AI 口播文案助手：按主题/场景/平台生成 3 版口播脚本（LLM 失败自动回退模板）。"""
    scene_style = _SCENE_STYLES.get(req.scene_id, "产品介绍")
    # 行业模板：按模板推荐的文案结构生成（选模板后脚本结构与成片字幕风格一致）
    template = next((t for t in INDUSTRY_TEMPLATES if t["id"] == req.template_id), None)
    structure = f"；文案结构：{template['script_structure']}" if template else ""
    platform_labels = {"douyin": "抖音", "kuaishou": "快手", "wechat": "公众号", "bilibili": "B站"}
    platform_name = platform_labels.get(req.platform, req.platform)
    system = (
        "你是资深短视频口播文案专家。根据要求生成3版口播文案，直接输出JSON数组，"
        "每版是1个字符串对象，120字以内，必须包含：开头钩子、核心内容、结尾引导。"
        "要求：口语化、无Markdown标记、无违禁词（不能出现点击领取/加微信/日赚等），不要用'最'等广告法极限词。"
    )
    user_prompt = (
        f"主题：{req.topic}；场景：{scene_style}{structure}；平台：{platform_name}；风格：{req.tone}。"
        "请生成3版不同切入角度的口播文案。"
    )
    from common.config import resolve_feature_model

    _uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    scripts = []
    ok = False
    try:
        raw = call_llm(
            system, user_prompt, max_tokens=1500, temperature=0.9, timeout=60,
            model=resolve_feature_model(_uid, "dh", ""),
        )
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
            "SELECT id FROM digital_human_records WHERE created_at < ?",
            (cutoff,),
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
                        audio_bytes += sz
                        audio_count += 1
                    else:
                        video_bytes += sz
                        video_count += 1
            except OSError:
                pass
    return {
        "total_mb": round(total / 1048576, 1),
        "audio_mb": round(audio_bytes / 1048576, 1),
        "video_mb": round(video_bytes / 1048576, 1),
        "audio_count": audio_count,
        "video_count": video_count,
    }


@router.get("/storage")
async def my_storage(current_user: dict = require_auth()):
    """我的存储用量：记录数 / 音频视频数 / 磁盘占用 / 保留策略。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT audio_url, video_url FROM digital_human_records WHERE user_id=?",
            (user,),
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
        total_records = conn.execute("SELECT COUNT(*) FROM digital_human_records").fetchone()[0]
        today_prefix = datetime.now().strftime("%Y-%m-%d")
        today_records = conn.execute(
            "SELECT COUNT(*) FROM digital_human_records WHERE created_at LIKE ?",
            (today_prefix + "%",),
        ).fetchone()[0]
        status_dist = {
            r["status"]: r["c"]
            for r in conn.execute("SELECT status, COUNT(*) c FROM digital_human_records GROUP BY status").fetchall()
        }
        res_dist = {
            r["resolution"]: r["c"]
            for r in conn.execute(
                "SELECT resolution, COUNT(*) c FROM digital_human_records GROUP BY resolution"
            ).fetchall()
        }
        user_top = [
            dict(r)
            for r in conn.execute(
                "SELECT user_id, COUNT(*) c FROM digital_human_records GROUP BY user_id ORDER BY c DESC LIMIT 5"
            ).fetchall()
        ]
        trend_7d = []
        for i in range(6, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            c = conn.execute(
                "SELECT COUNT(*) FROM digital_human_records WHERE created_at LIKE ?",
                (d + "%",),
            ).fetchone()[0]
            trend_7d.append({"date": d, "count": c})
        recent_failures = [
            dict(r)
            for r in conn.execute(
                "SELECT text, error, created_at FROM digital_human_records WHERE status='failed'"
                " AND error != '' ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        ]
        usage = conn.execute(
            "SELECT COUNT(*) c, AVG(response_time) avg_sec, SUM(success) ok"
            " FROM usage_logs WHERE task_type='digital_human'"
        ).fetchone()
        batch_row = conn.execute(
            "SELECT COUNT(*) c,"
            " SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) done_cnt,"
            " SUM(CASE WHEN status='interrupted' THEN 1 ELSE 0 END) interrupted_cnt"
            " FROM digital_human_batches"
        ).fetchone()
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
            _uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
            if await asyncio.to_thread(_generate_portrait, avatar["id"], _uid):
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


register_handler("dh_generate", _dh_generate_handler, user_limit=1, max_attempts=2)


def _dh_voice_clone_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """声音克隆异步任务：pyin 基频分析 → 音色池匹配 + 音调补偿 → 入库（active）。

    v1 参数近似克隆（engine='pitch_fit'）：样本仅作分析，不直接用于配音；
    失败自动清理样本文件，任务重试需重新上传。
    """
    from voice_clone import analyze_sample, fit_voice

    clone_id = payload.get("clone_id") or ""
    sample_path = payload.get("sample_path") or ""
    voice_name = (payload.get("voice_name") or "我的克隆声音").strip()[:20]
    # 与 digital_human_records / custom_voices 一致：user_id 列存 username（生成链路按 username 查询）
    user = ctx.get("username", "")
    update(10, "正在分析人声样本…")
    try:
        if not sample_path or not os.path.exists(sample_path):
            raise RuntimeError("样本文件缺失，请重新上传")
        analysis = analyze_sample(sample_path)  # {duration, f0_mean, voiced_ratio, gender}
        update(60, "正在匹配音色…")
        fit = fit_voice(analysis["f0_mean"])
        conn = get_db()
        try:
            _ensure_tables(conn)
            conn.execute(
                "INSERT INTO voice_clones (id, user_id, voice_name, sample_path, sample_duration,"
                " f0_mean, gender, edge_voice, pitch_hz, speed, status, declare_authorized, engine, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    clone_id,
                    user,
                    voice_name,
                    sample_path,
                    analysis["duration"],
                    analysis["f0_mean"],
                    analysis["gender"],
                    fit["edge_voice"],
                    fit["pitch_hz"],
                    fit["speed"],
                    "active",
                    1,
                    "pitch_fit",
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        update(100, "声音克隆完成，可在声音列表中使用")
        return {
            "clone_id": clone_id,
            "voice_id": clone_id,
            "voice_name": voice_name,
            "edge_voice": fit["edge_voice"],
            "pitch_hz": fit["pitch_hz"],
            "gender": analysis["gender"],
            "f0_mean": analysis["f0_mean"],
            "sample_duration": analysis["duration"],
        }
    except Exception:
        # 分析失败：清理样本文件（避免垃圾留存），任务失败可重试（需重新上传）
        if sample_path and os.path.exists(sample_path):
            os.remove(sample_path)
        raise


register_handler("dh_voice_clone", _dh_voice_clone_handler, user_limit=1)


# ══════════════════════════════════════════════════════════════
# 数字人 lip-sync v2 端点：质量评估 + 口型曲线预览
# ══════════════════════════════════════════════════════════════

@router.post("/lip-sync/quality")
async def check_lip_sync_quality(
    audio_path: str = Form(..., description="音频文件路径（相对于 DIGITAL_HUMAN_DIR）"),
    script_text: str = Form("", description="口播文案（可选，用于文字驱动口型对比）"),
    fps: int = Form(25, ge=15, le=30),
    current_user: dict = require_auth(),
):
    """评估数字人 lip-sync 质量：音频能量与脚本文字的口型匹配度。

    v20：支持文本+音频双源融合评估，返回各项质量指标。
    """
    import os as _os
    from pathlib import Path
    logger.warning(f"[lip-sync-debug] audio_path={audio_path!r} file={__file__}")

    # 支持三种路径：绝对路径 / uploads 相对路径（audio_url） / digital_human 目录相对路径
    audio_path = (audio_path or "").strip()
    candidates = []
    if audio_path.startswith("/uploads/"):
        # 平台内 /uploads 路径 → 映射到实际存储目录（注意：isabs 会误判为绝对路径，须先判断）
        candidates.append(Path(__file__).parent / audio_path.lstrip("/"))
    elif _os.path.isabs(audio_path):
        candidates.append(Path(audio_path))
    else:
        dh_dir = Path(__file__).parent / "digital_human"
        candidates.append(dh_dir / audio_path)
        candidates.append(Path(__file__).parent / "uploads" / "audio" / audio_path)
    full_audio = next((p for p in candidates if p.exists()), None)
    if full_audio is None:
        logger.warning(f"lip-sync quality 音频不存在，candidates: {[str(c) for c in candidates]}")
        raise HTTPException(404, "音频文件不存在")

    # 获取音频时长
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(full_audio)],
            capture_output=True, text=True, timeout=15,
        )
        duration = float(probe.stdout.strip()) if probe.stdout.strip() else 5.0
    except Exception:
        duration = 5.0

    result = _lip_sync_quality(str(full_audio), script_text, duration, fps)
    return result


@router.post("/lip-sync/curve")
async def get_mouth_curve(
    audio_path: str = Form(...),
    script_text: str = Form(""),
    fps: int = Form(25, ge=15, le=30),
    blend_alpha: float = Form(0.6, ge=0.0, le=1.0, description="文字驱动权重（0=纯音频，1=纯文字）"),
    current_user: dict = require_auth(),
):
    """获取融合口型曲线（用于前端可视化预览）。

    返回帧级 (open, round) 数据，前端可绘制为波形图。
    """
    import os as _os
    from pathlib import Path
    logger.warning(f"[lip-sync-debug] audio_path={audio_path!r} file={__file__}")

    # 支持三种路径：绝对路径 / uploads 相对路径（audio_url） / digital_human 目录相对路径
    audio_path = (audio_path or "").strip()
    candidates = []
    if audio_path.startswith("/uploads/"):
        # 平台内 /uploads 路径 → 映射到实际存储目录（注意：isabs 会误判为绝对路径，须先判断）
        candidates.append(Path(__file__).parent / audio_path.lstrip("/"))
    elif _os.path.isabs(audio_path):
        candidates.append(Path(audio_path))
    else:
        dh_dir = Path(__file__).parent / "digital_human"
        candidates.append(dh_dir / audio_path)
        candidates.append(Path(__file__).parent / "uploads" / "audio" / audio_path)
    full_audio = next((p for p in candidates if p.exists()), None)
    if full_audio is None:
        logger.warning(f"lip-sync quality 音频不存在，candidates: {[str(c) for c in candidates]}")
        raise HTTPException(404, "音频文件不存在")

    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(full_audio)],
            capture_output=True, text=True, timeout=15,
        )
        duration = float(probe.stdout.strip()) if probe.stdout.strip() else 5.0
    except Exception:
        duration = 5.0

    # 生成文字驱动时间轴
    script_timeline = _build_script_timeline_v2(script_text, duration, str(full_audio), fps)
    # 生成音频驱动曲线
    audio_curve = _audio_driven_mouth(str(full_audio), fps, duration)
    # 融合
    blended = _blend_mouth_shapes(script_timeline, audio_curve, alpha=blend_alpha)

    # 下采样：每 2 帧取 1 个点，最多 500 点（避免响应过大）
    step = max(1, len(blended) // 500)
    sampled = blended[::step]

    return {
        "frames": len(blended),
        "sampled_frames": len(sampled),
        "fps": fps,
        "duration_sec": round(duration, 2),
        "alpha": blend_alpha,
        "curve": sampled,
    }
