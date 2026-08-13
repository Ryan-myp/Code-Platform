# -*- coding: utf-8 -*-
"""视频模板工厂：专业级短视频广告模板（TikTok/电商/社媒/节日/生活）。

架构：
- 每个模板 = JSON 定义（平台/分辨率/时长/场景序列），场景内嵌「图片模板」图层
  （复用 image_factory 渲染引擎：渐变/circle/line/真实粗体/阴影描边）。
- 渲染管线：逐场景渲染静态帧图 → ffmpeg 逐镜头做 Ken Burns 运镜（zoompan）
  → xfade 转场串联 → 电商节拍 BGM 合成 → MP4 + 封面抽帧。
- 商业化：模板定价（free/once/day/month，积分），购买授权 + 渲染校验 + 热度统计。
"""
import asyncio
import json
import logging
import math
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse

from image_factory import render_template_image

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "video_templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
RENDER_DIR = Path(__file__).parent / "video_templates" / "renders"
RENDER_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/video-templates", tags=["视频模板"])
from common.template_utils import load_all, load_one



def _ffmpeg_bin() -> str:
    """ffmpeg 选择：优先 imageio-ffmpeg 自带二进制（libass 支持），回退系统 ffmpeg。"""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return "ffmpeg"


def _has_audio(src: Path) -> bool:
    try:
        out = subprocess.run(
            [_ffmpeg_bin(), "-i", str(src), "-f", "null", "-"],
            capture_output=True, text=True, timeout=30,
        ).stderr
        return "Audio:" in out
    except Exception:  # noqa: BLE001
        return False


# ══════════════════════════════════════════════════════════════
# 模板数据：16 个专业视频模板（写盘 video_templates/*.json）
# ══════════════════════════════════════════════════════════════

def _tpl(tid, name, category, platform, scenes, pricing, w=1080, h=1920, fps=30, desc=""):
    return {
        "id": tid, "name": name, "category": category, "platform": platform,
        "width": w, "height": h, "fps": fps, "scenes": scenes,
        "pricing": pricing, "desc": desc,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _scene(bg, seconds, layers, motion="zoom_in"):
    return {"background": bg, "seconds": seconds, "layers": layers, "motion": motion}


def _rect(x, y, w, h, fill, radius=16, opacity=1.0, border=0, border_color="#FFFFFF", rot=0):
    d = {"type": "rect", "x": x, "y": y, "width": w, "height": h, "radius": radius, "fill": fill}
    if opacity < 1:
        d["opacity"] = opacity
    if border:
        d["border_width"] = border
        d["border_color"] = border_color
    if rot:
        d["rotation"] = rot
    return d


def _dot(x, y, r, fill, opacity=1.0, border=0, border_color="#FFFFFF"):
    d = {"type": "circle", "x": x, "y": y, "radius": r, "fill": fill}
    if opacity < 1:
        d["opacity"] = opacity
    if border:
        d["border_width"] = border
        d["border_color"] = border_color
    return d


def _line(x, y, length, angle, color, width=2, opacity=1.0):
    d = {"type": "line", "x": x, "y": y, "length": length, "angle": angle, "color": color, "width": width}
    if opacity < 1:
        d["opacity"] = opacity
    return d


def _txt(key, x, y, text, fs, color, bold=False, align="left", mw=0, family="hiragino",
         shadow="", sc="#00000055", lh=1.35, sp=0):
    d = {"type": "text", "key": key, "x": x, "y": y, "text": text, "font_size": fs,
         "color": color, "align": align, "max_width": mw, "bold": bold, "family": family}
    if shadow:
        d["shadow"] = shadow
        d["shadow_color"] = sc
    if lh != 1.35:
        d["line_height"] = lh
    if sp:
        d["letter_spacing"] = sp
    return d


def _img(key, x, y, w, h, radius=0, border=0, border_color="#FFFFFF"):
    d = {"type": "image", "key": key, "x": x, "y": y, "width": w, "height": h, "radius": radius, "fit": "cover"}
    if border:
        d["border_width"] = border
        d["border_color"] = border_color
    return d


# ── 场景工厂：钩子开场 / 卖点轮播 / 价格行动 / 结尾引导 ──
def _hook(bg, tag, title, subtitle, accent, accent2, seconds=3.2, motion="zoom_in"):
    return _scene(
        bg, seconds,
        [
            _dot(540, 320, 280, accent, opacity=0.35),
            _rect(300, 130, 480, 78, "#FFFFFF", radius=39, opacity=0.12, border=2, border_color=accent2),
            _txt("tag", 300, 150, tag, 26, accent2, bold=True, align="center", mw=480),
            _txt("title", 80, 260, title, 92, "#FFFFFF", bold=True, align="center", mw=920, lh=1.25,
                 shadow="0,8", sc="#00000066"),
            _txt("subtitle", 80, 560, subtitle, 32, "#DDDDDD", align="center", mw=920),
            _line(280, 640, 520, 0, "#FFFFFF33", width=2),
            _img("product", 140, 1240, 800, 520, radius=28, border=6, border_color="#FFFFFF22"),
        ],
        motion,
    )


def _feat(bg, num, point, desc, accent, accent2, product=True, seconds=2.8, motion="zoom_out"):
    layers = [
        _dot(540, 240, 230, accent, opacity=0.22),
        _dot(200, 320, 66, accent2),
        _txt(f"num{num}", 200, 294, f"{num:02d}", 52, "#FFFFFF" if accent2 != "#FFFFFF" else "#1A1A1A",
             bold=True, align="center", mw=132),
        _txt(f"point{num}", 80, 480, point, 76, "#FFFFFF", bold=True, align="center", mw=920, lh=1.3,
             shadow="0,6", sc="#00000066"),
        _txt(f"desc{num}", 80, 760, desc, 30, "#CCCCCC", align="center", mw=920),
    ]
    if product:
        layers.append(_img("product", 140, 900, 800, 620, radius=32, border=6, border_color="#FFFFFF22"))
    return _scene(bg, seconds, layers, motion)


def _price(bg, price, old, cta, accent, accent2, sub="", seconds=2.8, motion="zoom_in"):
    return _scene(
        bg, seconds,
        [
            _dot(540, 380, 170, "#FFFFFF", opacity=0.1),
            _dot(540, 380, 150, "", border=8, border_color="#FFFFFF44"),
            _txt("price", 80, 230, price, 120, "#FFFFFF", bold=True, align="center", mw=920, lh=1.15,
                 shadow="0,10", sc="#00000055"),
            _txt("old", 80, 430, f"原价 {old}", 36, "#FFFFFF99", align="center", mw=920),
            _txt("flash", 80, 520, sub, 42, accent2, bold=True, align="center", mw=920),
            _line(240, 620, 600, 0, "#FFFFFF33", width=2),
            _img("product", 170, 700, 740, 620, radius=32, border=6, border_color="#FFFFFF22"),
            _rect(240, 1420, 600, 130, accent2, radius=65),
            _txt("cta", 240, 1458, cta, 44, "#1A1A1A", bold=True, align="center", mw=600),
        ],
        motion,
    )


def _outro(bg, brand, slogan, accent, accent2, seconds=2.0, motion="zoom_out"):
    return _scene(
        bg, seconds,
        [
            _dot(540, 560, 120, "", border=8, border_color=accent),
            _dot(540, 560, 92, "", border=6, border_color=accent2),
            _dot(540, 560, 10, accent2),
            _txt("brand", 80, 800, brand, 76, "#FFFFFF", bold=True, align="center", mw=920, lh=1.25),
            _txt("slogan", 80, 960, slogan, 34, "#CCCCCC", align="center", mw=920),
            _txt("follow", 80, 1420, "FOLLOW US", 28, accent, family="helvetica", align="center", mw=920, sp=8),
        ],
        motion,
    )


def _category_for(tid: str) -> str:
    """模板分类：由模板 id 前缀推导（电商/社媒/节日/生活）。"""
    if any(k in tid for k in ("tiktok", "flash", "new", "bundle", "food", "beauty", "fashion", "tech")):
        return "电商"
    if any(k in tid for k in ("douyin", "kuaishou", "youtube", "xhs")):
        return "社媒"
    if any(k in tid for k in ("xmas", "double11")):
        return "节日"
    return "生活"


def _build(tid, name, platform, hook, feats, price, outro, pricing, desc="",
           hseconds=3.2, fseconds=2.8, pseconds=2.8, oseconds=2.0, w=1080, h=1920):
    scenes = [hook]
    scenes += feats
    scenes += [price, outro]
    total = round(hseconds + fseconds * len(feats) + pseconds + oseconds, 2)
    return _tpl(tid, name, _category_for(tid), platform, scenes, pricing, w=w, h=h, desc=desc), total


def _video_templates():
    T = []
    # ══ 电商 8：TikTok Shop / 秒杀 / 新品 / 套装 / 美食 / 美妆 / 服饰 / 3C ══
    t, _ = _build(
        "vt_tiktok_shop", "TikTok Shop 跨境带货", "tiktok",
        _hook("#1A1A1A→#FF2E4D", "TikTok Shop", "3 秒心动\n好物推荐", "海外爆款 · 今日直降", "#FF2E4D", "#00F2EA"),
        [
            _feat("#1A1A1A→#2D2D2D", 1, "跨境直邮\n3 天到手", "欧美仓直发 · 全程物流可查", "#00F2EA", "#00F2EA"),
            _feat("#1A1A1A→#2D2D2D", 2, "好评 10 万+", "真实买家秀 · 复购率 40%", "#00F2EA", "#00F2EA"),
            _feat("#1A1A1A→#2D2D2D", 3, "今日直降 50%", "仅限今天 · 售完恢复原价", "#FF2E4D", "#00F2EA"),
        ],
        _price("#FF2E4D→#C2185B", "$19.9", "$39.9", "点击购物车下单", "#FFFFFF", "#00F2EA", "限时 5 折"),
        _outro("#1A1A1A", "小团优选", "关注我 · 更多海外好物", "#00F2EA", "#FF2E4D"),
        {"mode": "once", "once": 20, "day": 8, "month": 79},
        desc="TikTok 带货黄金结构：钩子大字 + 三卖点 + 价格逼单 + 关注引导",
    )
    T.append(t)
    t, _ = _build(
        "vt_flash_sale", "限时秒杀", "通用",
        _hook("#0F2027→#203A43", "FLASH SALE", "限时秒杀\n整点开抢", "库存仅 50 件 · 抢完即止", "#FFC107", "#FFC107"),
        [
            _feat("#0F2027→#203A43", 1, "限量 50 件", "每人限购 2 件 · 手慢无", "#FFC107", "#FFC107"),
            _feat("#0F2027→#203A43", 2, "先到先得", "下单立减 · 超时恢复原价", "#FFC107", "#FFC107"),
        ],
        _price("#0F2027→#203A43", "¥99", "¥199", "立即抢购", "#FFC107", "#FFC107", "立省 ¥100"),
        _outro("#0F2027→#203A43", "秒杀专场", "关注不迷路 · 下次开抢提醒", "#FFC107", "#FFC107"),
        {"mode": "once", "once": 15, "day": 6, "month": 59},
        desc="秒杀氛围：深蓝底 + 电光黄，倒计时紧迫感 + 价格对比逼单",
    )
    T.append(t)
    t, _ = _build(
        "vt_new_arrival", "新品首发", "通用",
        _hook("#F0F4FF→#DBEAFE", "NEW ARRIVAL", "新品首发\n抢先体验", "全新升级 · 首批限定", "#3B82F6", "#7C3AED"),
        [
            _feat("#F0F4FF→#DBEAFE", 1, "首发 7 折", "新品上市专属优惠", "#3B82F6", "#7C3AED"),
            _feat("#F0F4FF→#DBEAFE", 2, "前 100 名赠礼", "价值 ¥99 精美礼盒", "#3B82F6", "#7C3AED"),
        ],
        _price("#3B82F6→#7C3AED", "¥699", "¥999", "立即预订", "#FFFFFF", "#FFD93D", "首发立省 ¥300"),
        _outro("#1E3A8A→#312E81", "新品季", "每周上新 · 敬请期待", "#FFD93D", "#7C3AED"),
        {"mode": "once", "once": 10, "day": 5, "month": 49},
        desc="新品发布：清爽蓝紫渐变 + 新品徽章 + 首发福利",
    )
    T.append(t)
    t, _ = _build(
        "vt_bundle", "超值套装", "通用",
        _hook("#FFF7E6→#FFE9C4", "BUNDLE DEAL", "超值套装\n一次买齐", "组合装 · 更划算", "#FF8A00", "#FF5C00"),
        [
            _feat("#FFF7E6→#FFE9C4", 1, "买 2 送 1", "多买多送 · 上不封顶", "#FF8A00", "#FF5C00"),
            _feat("#FFF7E6→#FFE9C4", 2, "组合立省 40%", "三件套打包价更优", "#FF8A00", "#FF5C00"),
        ],
        _price("#FF8A00→#FF5C00", "¥129", "¥215", "立即下单", "#FFFFFF", "#FFD93D", "3 件套 · 立省 ¥86"),
        _outro("#5D2E00→#3A1C00", "小团优选", "更多超值套装 · 关注解锁", "#FFD93D", "#FF8A00"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="套装促销：暖橙渐变 + 打包价对比，适合组合装/礼盒装",
    )
    T.append(t)
    t, _ = _build(
        "vt_food", "美食诱惑", "通用",
        _hook("#FFF1E6→#FFD9B8", "FOOD TIME", "深夜食堂\n治愈上线", "现点现做 · 暖胃更暖心", "#E65100", "#FF6B00"),
        [
            _feat("#FFF1E6→#FFD9B8", 1, "现点现做", "明档厨房 · 新鲜看得见", "#E65100", "#FF6B00"),
            _feat("#FFF1E6→#FFD9B8", 2, "30 分钟达", "热乎到家 · 口感不打折", "#E65100", "#FF6B00"),
        ],
        _price("#E65100→#FF6B00", "¥19.9", "¥35", "立即下单", "#FFFFFF", "#FFD93D", "新客立减 ¥5"),
        _outro("#5D2E00→#3A1C00", "深夜食堂", "关注 · 每天一道招牌菜", "#FFD93D", "#FF6B00"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="美食带货：暖米色食欲感 + 番茄橙点缀，适合餐饮/生鲜",
    )
    T.append(t)
    t, _ = _build(
        "vt_beauty", "美妆焕颜", "通用",
        _hook("#FFF0F5→#FFD6E8", "BEAUTY DROP", "素颜也敢拍\n水光肌养成", "28 天焕亮 · 告别暗沉", "#FF6B9D", "#E75A8D"),
        [
            _feat("#FFF0F5→#FFD6E8", 1, "28 天焕亮", "烟酰胺 + 玻尿酸双效", "#FF6B9D", "#E75A8D"),
            _feat("#FFF0F5→#FFD6E8", 2, "敏感肌可用", "0 酒精 · 0 色素 · 0 香精", "#FF6B9D", "#E75A8D"),
        ],
        _price("#FF6B9D→#E75A8D", "¥299", "¥399", "立即抢购", "#FFFFFF", "#FFD93D", "买一送一"),
        _outro("#7A2545→#4A2545", "小团美妆", "关注 · 更多变美干货", "#FFD93D", "#FF6B9D"),
        {"mode": "once", "once": 10, "day": 5, "month": 49},
        desc="美妆种草：粉金少女感 + 玫红 CTA，适合护肤/彩妆",
    )
    T.append(t)
    t, _ = _build(
        "vt_fashion", "穿搭展示", "通用",
        _hook("#FAFAFA→#E8E8E8", "FASHION DROP", "秋冬新品\n极简廓形", "质感面料 · 高级剪裁", "#111111", "#111111"),
        [
            _feat("#FAFAFA→#E8E8E8", 1, "质感面料", "羊毛混纺 · 亲肤保暖", "#111111", "#111111"),
            _feat("#FAFAFA→#E8E8E8", 2, "限量配色", "三色可选 · 售完即止", "#111111", "#111111"),
        ],
        _price("#111111→#333333", "¥399", "¥599", "立即选购", "#FFFFFF", "#E53935", "限时 6 折"),
        _outro("#111111", "FASHION WEEK", "每周上新 · 关注不错过", "#FFFFFF", "#E53935"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="服饰极简：黑白高级感 + 大留白，适合服装/鞋包",
    )
    T.append(t)
    t, _ = _build(
        "vt_tech", "3C 酷玩", "通用",
        _hook("#0A0F1E→#1B2A4A", "TECH LAUNCH", "硬核科技\n旗舰登场", "性能拉满 · 全系顶配", "#00E5FF", "#7C4DFF"),
        [
            _feat("#0A0F1E→#1B2A4A", 1, "旗舰芯片", "新一代旗舰芯 · 能效飙升", "#00E5FF", "#7C4DFF"),
            _feat("#0A0F1E→#1B2A4A", 2, "百瓦闪充", "10 分钟回血 50%", "#00E5FF", "#7C4DFF"),
        ],
        _price("#0A0F1E→#1B2A4A", "¥3999", "¥4599", "立即预订", "#00E5FF", "#00E5FF", "12 期免息"),
        _outro("#0A0F1E→#0F0F23", "TECH LAB", "关注 · 数码资讯抢先看", "#00E5FF", "#7C4DFF"),
        {"mode": "once", "once": 10, "day": 5, "month": 49},
        desc="3C 数码：深空蓝 + 霓虹青，科技感拉满",
    )
    T.append(t)
    # ══ 社媒 4：抖音信息流 / 快手直播 / YouTube 片头 / 小红书 ══
    t, _ = _build(
        "vt_douyin_feed", "抖音信息流广告", "douyin",
        _hook("#1A1A1A→#2D2D2D", "DOUYIN FEED", "全网爆款\n刷到就是赚到", "10W+ 人已下单", "#FE2C55", "#25F4EE"),
        [
            _feat("#1A1A1A→#2D2D2D", 1, "全网热销 10W+", "口碑爆棚 · 复购不断", "#25F4EE", "#FE2C55"),
            _feat("#1A1A1A→#2D2D2D", 2, "好评如潮", "4.9 分 · 万人真实评价", "#25F4EE", "#FE2C55"),
        ],
        _price("#FE2C55→#B0153A", "¥59.9", "¥89.9", "点击下方链接", "#FFFFFF", "#25F4EE", "抖音专属价"),
        _outro("#1A1A1A", "抖音好物", "关注 · 天天有好物", "#25F4EE", "#FE2C55"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="抖音信息流：红青撞色 + 大字钩子，前 3 秒抓注意力",
    )
    T.append(t)
    t, _ = _build(
        "vt_kuaishou_live", "快手直播预告", "kuaishou",
        _hook("#FF4D00→#FF9A00", "LIVE TONIGHT", "今晚 8 点\n直播见", "秒杀福利 · 红包雨", "#FF4D00", "#FFD93D"),
        [
            _feat("#FF4D00→#FF9A00", 1, "秒杀福利", "整点秒杀 · 1 元起", "#FF4D00", "#FFD93D"),
            _feat("#FF4D00→#FF9A00", 2, "红包雨", "直播间红包不断", "#FF4D00", "#FFD93D"),
        ],
        _price("#FF4D00→#C22E00", "今晚 8:00", "开播提醒", "预约直播", "#FFFFFF", "#FFD93D", "预约抽好礼"),
        _outro("#5D1A00→#3A0F00", "老铁直播间", "关注 · 开播不迷路", "#FFD93D", "#FF4D00"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="快手直播：橙红热情风 + 直播倒计时，适合直播预热",
    )
    T.append(t)
    t, _ = _build(
        "vt_youtube_intro", "YouTube 频道片头", "youtube",
        _hook("#0F0F0F→#2D0000", "SUBSCRIBE", "欢迎来到\n我的频道", "每周更新 · 干货不断", "#FF0000", "#FF0000",
              seconds=4.0, motion="zoom_out"),
        [_feat("#0F0F0F→#2D0000", 1, "频道亮点", "科技 + 生活双领域", "#FF0000", "#FF0000", seconds=3.0)],
        _price("#0F0F0F→#2D0000", "免费订阅", "月更 8 期", "立即订阅", "#FFFFFF", "#FF0000", "打开小铃铛", seconds=3.0),
        _outro("#0F0F0F", "MY CHANNEL", "订阅 + 点赞 + 转发", "#FF0000", "#FF0000", seconds=2.0),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="YouTube 片头：黑红经典 + 订阅引导，适合频道主",
    )
    T.append(t)
    t, _ = _build(
        "vt_xhs_plant", "小红书种草视频", "xiaohongshu",
        _hook("#FFF9F2→#FFE8E8", "好物分享", "自用 30 天\n真心推荐", "无广测评 · 真实体验", "#FF2442", "#FF2442"),
        [
            _feat("#FFF9F2→#FFE8E8", 1, "自用 30 天", "每天记录 · 效果看得见", "#FF2442", "#FF2442"),
            _feat("#FFF9F2→#FFE8E8", 2, "真实测评", "优点缺点都说清", "#FF2442", "#FF2442"),
        ],
        _price("#FF2442→#C2183B", "¥89", "¥129", "点击收藏", "#FFFFFF", "#FFD93D", "笔记同款"),
        _outro("#FFF9F2→#FFE8E8", "小团种草日记", "关注 · 每周一篇测评", "#FF2442", "#FF2442"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="小红书种草：米白温柔风 + 种草红，适合笔记种草",
    )
    T.append(t)
    # ══ 节日 2：双11 / 圣诞 ══
    t, _ = _build(
        "vt_double11", "双 11 大促", "通用",
        _hook("#8B0000→#C8102E", "11.11 SALE", "双 11 狂欢\n全年最低", "全场 5 折起 · 满减叠加", "#FFD700", "#FFD700"),
        [
            _feat("#8B0000→#C8102E", 1, "全场 5 折", "大牌云集 · 一价到底", "#FFD700", "#FFD700"),
            _feat("#8B0000→#C8102E", 2, "满减叠加", "满 ¥500 减 ¥100", "#FFD700", "#FFD700"),
        ],
        _price("#C8102E→#8B0000", "¥999", "¥1999", "马上抢购", "#FFD700", "#FFD700", "狂欢 48 小时"),
        _outro("#3D0000→#1A0000", "双 11 盛典", "错过再等一年", "#FFD700", "#FFD700"),
        {"mode": "once", "once": 20, "day": 8, "month": 79},
        desc="双11 大促：红金大气风 + 满减规则，适合平台级大促",
    )
    T.append(t)
    t, _ = _build(
        "vt_xmas", "圣诞狂欢促销", "通用",
        _hook("#0B3D2E→#041712", "MERRY XMAS", "圣诞狂欢季\n礼盒直降", "限定礼盒 · 赠精美包装", "#FFD700", "#FF4D4D"),
        [
            _feat("#0B3D2E→#041712", 1, "礼盒直降", "圣诞限定 · 送人倍有面", "#FFD700", "#FF4D4D"),
            _feat("#0B3D2E→#041712", 2, "限量发售", "售完不补 · 先到先得", "#FFD700", "#FF4D4D"),
        ],
        _price("#0B3D2E→#041712", "¥199", "¥299", "立即购买", "#FFD700", "#FF4D4D", "圣诞特惠"),
        _outro("#041712→#02200E", "圣诞市集", "Merry Christmas 🎄", "#FFD700", "#FF4D4D"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="圣诞促销：墨绿 + 金红圣诞配色，适合节日礼盒",
    )
    T.append(t)
    # ══ 生活 2：健身 / 旅行 ══
    t, _ = _build(
        "vt_fitness", "健身挑战打卡", "通用",
        _hook("#0F1F14→#1A2E22", "30 DAY CHALLENGE", "30 天挑战\n遇见更好的自己", "每天 10 分钟 · 无需器械", "#39FF88", "#39FF88"),
        [
            _feat("#0F1F14→#1A2E22", 1, "燃脂计划", "HIIT + 拉伸科学搭配", "#39FF88", "#39FF88"),
            _feat("#0F1F14→#1A2E22", 2, "无需器械", "在家就能练 · 0 门槛", "#39FF88", "#39FF88"),
        ],
        _price("#0F1F14→#1A2E22", "¥0", "原价 ¥99", "免费加入", "#39FF88", "#39FF88", "限时 0 元"),
        _outro("#0F1F14→#0A120C", "燃脂计划", "打卡 30 天 · 赢好礼", "#39FF88", "#39FF88"),
        {"mode": "free", "once": 0, "day": 0, "month": 0},
        desc="健身打卡：深绿 + 荧光绿能量风，适合健身/打卡社群",
    )
    T.append(t)
    t, _ = _build(
        "vt_travel", "旅行 Vlog", "通用",
        _hook("#1E3A8A→#0F172A", "TRAVEL VLOG", "说走就走\n去看更大的世界", "小众秘境 · 省钱攻略", "#FDE68A", "#FDE68A"),
        [
            _feat("#1E3A8A→#0F172A", 1, "小众秘境", "人少景美 · 超出片", "#FDE68A", "#FDE68A"),
            _feat("#1E3A8A→#0F172A", 2, "省钱攻略", "机票酒店这样订最划算", "#FDE68A", "#FDE68A"),
        ],
        _price("#1E3A8A→#0F172A", "¥2999", "¥3999", "收藏攻略", "#FDE68A", "#FDE68A", "6 日 5 晚"),
        _outro("#0F172A→#0A0F1E", "小团旅行", "关注 · 每周一条线路", "#FDE68A", "#FDE68A"),
        {"mode": "once", "once": 8, "day": 4, "month": 39},
        desc="旅行 Vlog：夜空蓝 + 月亮金，适合旅行博主/旅行社",
    )
    T.append(t)
    return T


def init_video_templates():
    """启动初始化：模板不存在才写盘（用户可自行编辑 JSON），返回全部模板。"""
    for t in _video_templates():
        path = TEMPLATE_DIR / f"{t['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化视频模板：{t['name']}")
    return load_all(TEMPLATE_DIR)






# ══════════════════════════════════════════════════════════════
# 商业化：购买授权 + 渲染校验 + 热度
# ══════════════════════════════════════════════════════════════

def _get_db():
    from common.db import get_db

    return get_db()


def _ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS video_template_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, template_id TEXT, access_type TEXT, expires_at TEXT,
            purchased_at TEXT, UNIQUE(user_id, template_id))"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS video_template_usage (
            template_id TEXT PRIMARY KEY, usage_count INTEGER DEFAULT 0)"""
    )
    conn.commit()


def _get_usage(tid: str) -> int:
    try:
        conn = _get_db()
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT usage_count FROM video_template_usage WHERE template_id=?", (tid,)
        ).fetchone()
        conn.close()
        return int(row["usage_count"]) if row else 0
    except Exception:  # noqa: BLE001
        return 0


def _record_usage(tid: str) -> None:
    try:
        conn = _get_db()
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO video_template_usage(template_id, usage_count) VALUES(?,1) "
            "ON CONFLICT(template_id) DO UPDATE SET usage_count=usage_count+1",
            (tid,),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        pass


def _check_render_access(user: str, template: dict) -> None:
    """收费模板校验：once 永久 / day / month 未过期，无权限 402 引导购买。"""
    pricing = template.get("pricing") or {}
    if pricing.get("mode", "free") == "free":
        return
    if not user:
        raise HTTPException(402, "该模板为付费模板，请先登录后购买")
    conn = _get_db()
    _ensure_tables(conn)
    row = conn.execute(
        "SELECT * FROM video_template_access WHERE user_id=? AND template_id=?",
        (user, template.get("id", "")),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(402, "该模板为付费模板，请先购买（积分可用）")
    a = dict(row)
    if a["access_type"] == "once":
        return
    try:
        if a["expires_at"] and datetime.fromisoformat(a["expires_at"]) > datetime.now():
            return
    except ValueError:
        pass
    raise HTTPException(402, "订阅已过期，请重新购买")


# ══════════════════════════════════════════════════════════════
# 渲染引擎：镜头帧 → zoompan 运镜 → xfade 转场 → BGM 合成
# ══════════════════════════════════════════════════════════════

def _scene_motion_filter(motion: str, w: int, h: int, fps: int, secs: float) -> str:
    """Ken Burns 运镜（zoompan 用 on 输出帧计数，预放大 2x 防抖动）。"""
    total = max(1, int(secs * fps))
    step = 0.9 / total
    if motion == "zoom_out":
        z = f"max(1.15-{step:.6f}*on,1.0)"
    else:  # zoom_in 默认
        z = f"min(1+{step:.6f}*on,1.15)"
    x = "iw/2-(iw/zoom/2)"
    y = "ih/2-(ih/zoom/2)"
    if motion == "pan_up":
        z = "1.12"
        y = f"(ih-ih/zoom)*(1-on/{total})"
    elif motion == "pan_down":
        z = "1.12"
        y = f"(ih-ih/zoom)*on/{total}"
    elif motion == "pan_left":
        z = "1.12"
        x = f"(iw-iw/zoom)*(1-on/{total})"
    elif motion == "pan_right":
        z = "1.12"
        x = f"(iw-iw/zoom)*on/{total}"
    elif motion == "none":
        z = "1"
        x = "0"
        y = "0"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={total}:s={w}x{h}:fps={fps}"


def _render_shot(frame_path: Path, out_path: Path, motion: str, w: int, h: int, fps: int,
                 secs: float) -> bool:
    """单镜头：静态帧 + Ken Burns 运镜 → mp4（无音频，供 xfade 串联）。"""
    ffmpeg = _ffmpeg_bin()
    vf = (
        f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
        f"crop={w * 2}:{h * 2},"
        + _scene_motion_filter(motion, w, h, fps, secs)
    )
    cmd = [
        ffmpeg, "-nostdin", "-y", "-loop", "1", "-i", str(frame_path),
        "-t", f"{secs:.2f}",
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(out_path),
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 4096:
        logger.warning(f"镜头渲染失败: {r.stderr.decode(errors='replace')[-300:]}")
        return False
    return True


def _make_bgm(total_secs: float, out_path: Path) -> None:
    """电商节拍 BGM：低频 pad 三和弦 + 440Hz 音头脉冲 + 2s 低音强调。"""
    ffmpeg = _ffmpeg_bin()
    d = f"{total_secs:.2f}"
    cmd = [
        ffmpeg, "-nostdin", "-y",
        "-f", "lavfi", "-i",
        f"aevalsrc='0.09*sin(2*PI*110*t)+0.06*sin(2*PI*165*t)+0.04*sin(2*PI*220*t)':d={d}:s=44100",
        "-f", "lavfi", "-i",
        f"aevalsrc='0.16*sin(2*PI*440*t)*exp(-4*mod(t,0.4))+0.12*sin(2*PI*220*t)*exp(-3*mod(t,2))':d={d}:s=44100",
        "-filter_complex",
        f"[0][1]amix=inputs=2:normalize=0,afade=t=in:d=0.4,afade=t=out:st={max(0.5, total_secs - 1.2):.2f}:d=1.2",
        "-c:a", "pcm_s16le",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"BGM 生成失败: {e}")


def _xfade_concat(shot_paths: list[Path], secs_list: list[float], out_path: Path,
                  bgm: Path | None, fps: int) -> bool:
    """xfade 转场串联 + 混入 BGM → 最终 MP4。"""
    fade = 0.4
    n = len(shot_paths)
    ffmpeg = _ffmpeg_bin()
    inputs = []
    for p in shot_paths:
        inputs += ["-i", str(p)]
    fc, prev, offsets = [], "[0:v]", []
    acc = 0.0
    for i in range(1, n):
        acc += secs_list[i - 1] - fade
        offsets.append(round(acc, 3))
    for i in range(1, n):
        label = f"[x{i}]" if i < n - 1 else "[vout]"
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration={fade}:offset={offsets[i - 1]}{label}")
        prev = label
    cmd = [ffmpeg, "-nostdin", "-y"] + inputs + ["-filter_complex", ";".join(fc)]
    if bgm and bgm.exists():
        cmd += ["-i", str(bgm), "-map", "[vout]", "-map", f"{n}:a"]
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    else:
        cmd += ["-map", "[vout]", "-an"]
    cmd += ["-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-movflags", "+faststart", str(out_path)]
    r = subprocess.run(cmd, capture_output=True, timeout=600)
    if r.returncode != 0 or not out_path.exists() or out_path.stat().st_size < 8192:
        logger.warning(f"转场合成失败: {r.stderr.decode(errors='replace')[-400:]}")
        return False
    return True


def _extract_cover(video_path: Path, cover_path: Path) -> None:
    try:
        subprocess.run(
            [_ffmpeg_bin(), "-nostdin", "-y", "-ss", "0.6", "-i", str(video_path),
             "-frames:v", "1", "-q:v", "3", str(cover_path)],
            capture_output=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"封面抽帧失败: {e}")


async def render_video_template(template: dict, overrides: dict | None = None,
                                images: list | None = None) -> dict:
    """渲染视频模板：逐场景帧图 → 运镜镜头 → 转场合成 → BGM → MP4 + 封面。"""
    overrides = dict(overrides or {})
    if images:
        overrides["images"] = images
    w = int(template.get("width", 1080))
    h = int(template.get("height", 1920))
    fps = int(template.get("fps", 30))
    scenes = template.get("scenes", [])
    if not scenes:
        raise HTTPException(400, "模板没有场景")

    with tempfile.TemporaryDirectory(prefix="vtpl_") as tmp:
        tmpd = Path(tmp)
        frame_paths, secs_list = [], []
        for i, scene in enumerate(scenes):
            frame_tpl = {
                "width": w, "height": h,
                "background": scene.get("background", "#000000"),
                "background_image": scene.get("background_image", ""),
                "background_darken": scene.get("background_darken", 0),
                "layers": scene.get("layers", []),
            }
            imgs = await render_template_image(frame_tpl, overrides, None)
            frame_path = tmpd / f"frame_{i}.png"
            imgs[0].save(frame_path)
            frame_paths.append(frame_path)
            secs_list.append(max(1.0, float(scene.get("seconds", 2.5))))

        shot_paths = []
        for i, (fp, secs) in enumerate(zip(frame_paths, secs_list, strict=False)):
            shot = tmpd / f"shot_{i}.mp4"
            motion = scenes[i].get("motion", "zoom_in")
            if not _render_shot(fp, shot, motion, w, h, fps, secs):
                raise HTTPException(500, "操作失败，请稍后重试")
            shot_paths.append(shot)

        total_secs = sum(secs_list) - 0.4 * (len(secs_list) - 1)
        bgm = tmpd / "bgm.wav"
        _make_bgm(total_secs, bgm)

        filename = f"{template['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        out_path = RENDER_DIR / filename
        if not _xfade_concat(shot_paths, secs_list, out_path, bgm if bgm.exists() else None, fps):
            raise HTTPException(500, "视频合成失败")
        cover_name = filename.replace(".mp4", "_cover.jpg")
        _extract_cover(out_path, RENDER_DIR / cover_name)
        _record_usage(template["id"])
        return {
            "filename": filename,
            "url": f"/api/video-templates/videos/{filename}",
            "cover": f"/api/video-templates/videos/{cover_name}",
            "duration": round(total_secs, 1),
            "width": w, "height": h,
        }


# ══════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════

@router.get("/list")
async def video_templates_list(category: str = "", q: str = "", sort: str = "hot"):
    """视频模板市场列表（含预览图/定价/热度/分类）。"""
    items = []
    for t in load_all(TEMPLATE_DIR):
        pricing = t.get("pricing") or {}
        mode = pricing.get("mode", "free")
        item = {
            "id": t["id"],
            "name": t.get("name", "未命名"),
            "category": t.get("category", "通用"),
            "platform": t.get("platform", "通用"),
            "width": t.get("width", 1080),
            "height": t.get("height", 1920),
            "duration": round(sum(s.get("seconds", 2.5) for s in t.get("scenes", []))
                              - 0.4 * max(0, len(t.get("scenes", [])) - 1), 1),
            "preview": f"/api/video-templates/preview/{t['id']}",
            "pricing": pricing,
            "pricing_label": {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}.get(mode, "免费"),
            "usage": _get_usage(t["id"]),
            "desc": t.get("desc", ""),
            "created_at": t.get("created_at", ""),
        }
        items.append(item)
    if q:
        ql = q.strip().lower()
        items = [i for i in items if ql in i["name"].lower() or ql in i["category"].lower() or ql in i["platform"].lower()]
    if category and category != "全部":
        items = [i for i in items if i["category"] == category]
    if sort == "new":
        items.sort(key=lambda i: i.get("created_at", ""), reverse=True)
    elif sort == "price":
        items.sort(key=lambda i: (0 if i["pricing"].get("mode") == "free" else 1, i["pricing"].get("once", 0)))
    else:
        items.sort(key=lambda i: (i["usage"], i.get("created_at", "")), reverse=True)
    cats: dict = {}
    for it in items:
        cats.setdefault(it["category"], {"label": it["category"], "count": 0})
        cats[it["category"]]["count"] += 1
    return {"total": len(items), "items": items, "categories": list(cats.values())}


@router.get("/{tid}")
async def video_template_detail(tid: str):
    """模板详情（渲染参数变量说明）。"""
    t = load_one(TEMPLATE_DIR, tid, '视频模板不存在')
    keys = []
    for scene in t.get("scenes", []):
        for layer in scene.get("layers", []):
            if layer.get("key"):
                keys.append({"key": layer["key"], "type": layer["type"], "text": layer.get("text", "")})
    return {"template": {k: t[k] for k in ("id", "name", "category", "platform", "width", "height",
                                           "fps", "desc", "pricing") if k in t}, "vars": keys}


@router.get("/preview/{tid}")
async def video_template_preview(tid: str):
    """模板封面：首场景帧渲染（PNG，公开 CORS 供市场卡片展示）。"""
    t = load_one(TEMPLATE_DIR, tid, '视频模板不存在')
    scene = t["scenes"][0]
    frame_tpl = {
        "width": t["width"], "height": t["height"],
        "background": scene.get("background", "#000000"),
        "layers": scene.get("layers", []),
    }
    imgs = await render_template_image(frame_tpl, {}, None)
    import io

    from fastapi.responses import Response

    buf = io.BytesIO()
    imgs[0].save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=86400"})


@router.post("/purchase")
async def purchase_video_template(template_id: str = Form(...), access_type: str = Form("once"),
                                  current_user: dict = __import__("common.auth", fromlist=["require_auth"]).require_auth()):
    """购买视频模板（积分）：once 永久 / day / month 订阅。"""
    from common.auth import require_auth  # noqa: F401 — 签名已用

    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    t = _load_one(template_id)
    pricing = t.get("pricing") or {}
    if pricing.get("mode", "free") == "free":
        return {"ok": True, "message": "免费模板无需购买", "mode": "free"}
    amounts = {"once": pricing.get("once", 0), "day": pricing.get("day", 0), "month": pricing.get("month", 0)}
    amount = int(amounts.get(access_type, amounts["once"]) or 0)
    conn = _get_db()
    _ensure_tables(conn)
    quota = conn.execute("SELECT credits FROM user_quotas WHERE username=?", (user,)).fetchone()
    balance = int(quota["credits"]) if quota else 0
    if balance < amount:
        conn.close()
        raise HTTPException(402, "余额不足，请先充值")
    conn.execute("UPDATE user_quotas SET credits=credits-? WHERE username=?", (amount, user))
    expires = ""
    if access_type in ("day", "month"):
        import datetime as _dt

        days = {"day": 1, "month": 30}[access_type]
        expires = (_dt.datetime.now() + _dt.timedelta(days=days)).isoformat()
    conn.execute(
        "INSERT INTO video_template_access(user_id, template_id, access_type, expires_at, purchased_at) "
        "VALUES(?,?,?,?,?) ON CONFLICT(user_id, template_id) DO UPDATE SET "
        "access_type=excluded.access_type, expires_at=excluded.expires_at, purchased_at=excluded.purchased_at",
        (user, template_id, access_type, expires, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"购买成功，扣除 {amount} 积分", "credits": balance - amount}


@router.post("/render")
async def render_video_template_api(template_id: str = Form(...),
                                    overrides: str = Form("{}"),
                                    images: str = Form("[]"),
                                    current_user: dict = __import__("common.auth", fromlist=["require_auth"]).require_auth()):
    """渲染视频模板（同步，耗时 30-90s）：overrides=JSON 文本变量，images=JSON 图片槽。"""
    from common.auth import require_auth  # noqa: F401

    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    t = _load_one(template_id)
    _check_render_access(user, t)
    try:
        ov = json.loads(overrides or "{}")
        imgs = json.loads(images or "[]")
    except json.JSONDecodeError as e:
        raise HTTPException(400, "服务异常，请稍后重试") from e
    if not isinstance(ov, dict) or not (isinstance(imgs, dict) or isinstance(imgs, list)):
        raise HTTPException(400, "overrides 需为 JSON 对象，images 需为 JSON 对象（按图层 key）或数组（批量）")
    result = await render_video_template(t, ov, imgs)
    return result


@router.get("/videos/{filename}")
async def video_template_asset(filename: str):
    """渲染产物（mp4 / 封面 jpg），公开展示 CORS。"""
    safe = os.path.basename(filename.replace("\\", "/"))
    path = RENDER_DIR / safe
    if not path.exists():
        raise HTTPException(404, "文件不存在")
    media = "video/mp4" if safe.endswith(".mp4") else "image/jpeg"
    return FileResponse(path, media_type=media, headers={"Access-Control-Allow-Origin": "*"})


# 启动初始化
init_video_templates()
