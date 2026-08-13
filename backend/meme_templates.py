# -*- coding: utf-8 -*-
"""表情包模板库：按"场景/人设"封装的热门梗配方（底图风格 + AI 画面风格 + 推荐文案 + 装饰）。

对标专业表情包制作：每个模板 = 风格配方（style/ai_style）+ 3 组即用文案（顶部|底部）
+ AI 场景 prompt 建议 + 推荐 emoji 装饰，选模板一键填充即可出专业级成品，
覆盖职场/情感/搞笑/电商/节日/直播六大场景（电商营销为深度优化场景）。

商业化：pricing free/once/day/month（积分），热度统计（生成时记录）。
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "meme_templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/meme-templates", tags=["表情包模板"])
from common.template_utils import load_all, load_one, get_usage, record_usage



def _tpl(tid, name, category, icon, desc, style, ai_style, top_hint, bottom_hint,
         texts, prompt_hint="", decoration="", pricing=None):
    return {
        "id": tid, "name": name, "category": category, "icon": icon, "desc": desc,
        "style": style, "ai_style": ai_style,
        "top_hint": top_hint, "bottom_hint": bottom_hint,
        "texts": texts, "prompt_hint": prompt_hint, "decoration": decoration,
        "pricing": pricing or {"mode": "free", "once": 0, "day": 0, "month": 0},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _meme_templates():
    T = []
    # ══ 职场打工人 4 ══
    T.append(_tpl(
        "mt_monday", "周一综合症", "职场打工人", "😵",
        "周一早高峰的真实写照，打工人集体共鸣，转发率极高",
        "paper", "film",
        "周一，", "不想上班",
        ["周一，|不想上班", "又是周一|快乐是他们的", "周末去哪了|我也想知道"],
        "清晨拥挤的地铁车厢里，疲惫的上班族靠在扶手上，窗外阴雨绵绵，胶片颗粒质感",
        "☕,😮‍💨",
    ))
    T.append(_tpl(
        "mt_overtime", "加班到深夜", "职场打工人", "🌙",
        "深夜加班的社畜心声，写字楼灯光下的孤独感",
        "black", "film",
        "凌晨两点，", "还在加班",
        ["凌晨两点，|还在加班", "下班是什么|不存在的", "老板：这个需求很简单|我：好的（微笑）"],
        "深夜写字楼，空荡的办公室里只有一盏台灯亮着，窗外城市灯火，电影写实质感",
        "😴,💻",
    ))
    T.append(_tpl(
        "mt_slacking", "摸鱼快乐", "职场打工人", "🐟",
        "工位摸鱼的高光时刻，当代打工人的快乐源泉",
        "yellow", "flat",
        "工作使我快乐，", "摸鱼使我更快乐",
        ["工作使我快乐，|摸鱼使我更快乐", "偷偷摸鱼中|勿扰", "认真工作（划掉）|认真摸鱼"],
        "办公桌一角，戴着耳机的年轻人在屏幕前偷偷露出狡黠笑容，扁平插画风格，高饱和",
        "🎧,🐟",
    ))
    T.append(_tpl(
        "mt_raise", "升职加薪", "职场打工人", "💸",
        "升职加薪的荣耀时刻，红底公告风自带官宣感",
        "red", "flat",
        "恭喜！", "升职加薪",
        ["恭喜！|升职加薪", "今天起，|我是经理了", "加薪通知|请查收"],
        "金色奖杯与红包堆叠，喜庆的红金配色，扁平插画风格",
        "🎉,💰",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    # ══ 情感吐槽 4 ══
    T.append(_tpl(
        "mt_love_acid", "恋爱酸臭", "情感吐槽", "🍋",
        "被秀恩爱暴击的柠檬精现场，酸度拉满",
        "sticker", "3d",
        "你们继续，", "我吃柠檬",
        ["你们继续，|我吃柠檬", "又秀恩爱|举报了", "恋爱的酸臭味|刺鼻"],
        "一只抱着柠檬的委屈小猫，3D 软萌卡通风格，柔和光影，表情委屈",
        "🍋,😤",
    ))
    T.append(_tpl(
        "mt_single", "单身贵族", "情感吐槽", "👑",
        "单身不是可怜，是贵族！自信放光芒",
        "neon", "neon",
        "单身怎么了？", "我是贵族",
        ["单身怎么了？|我是贵族", "情人节|与我无瓜", "一个人|也很精彩"],
        "霓虹灯管组成的王冠悬浮在深色背景上，赛博朋克光效",
        "👑,✨",
    ))
    T.append(_tpl(
        "mt_dating", "相亲现场", "情感吐槽", "🤝",
        "相亲名场面：尴尬而不失礼貌的微笑",
        "white", "film",
        "阿姨介绍的对象，", "就这？",
        ["阿姨介绍的对象，|就这？", "第一次见面|已想回家", "对方家长：条件很好|我：好的好的"],
        "咖啡馆里两人尴尬对坐，气氛微妙，电影写实质感，自然光影",
        "😅,☕",
    ))
    T.append(_tpl(
        "mt_bestie", "闺蜜日常", "情感吐槽", "💅",
        "闺蜜吐槽专用，塑料姐妹花的真诚时刻",
        "gradient", "3d",
        "姐妹，", "快出来吃瓜",
        ["姐妹，|快出来吃瓜", "我有个大瓜|微信说", "塑料姐妹|在线互夸"],
        "两个可爱的闺蜜卡通形象凑在一起说悄悄话，3D 软萌风格，高饱和渐变背景",
        "💅,🍉",
    ))
    # ══ 搞笑沙雕 4 ══
    T.append(_tpl(
        "mt_schadenfreude", "幸灾乐祸", "搞笑沙雕", "🤭",
        "看别人倒霉时忍不住上扬的嘴角，损友专用",
        "yellow", "flat",
        "哈哈哈哈，", "你也有今天",
        ["哈哈哈哈，|你也有今天", "不是我干的|但我不后悔", "惨？|再惨点"],
        "一只躲在墙角偷笑的柴犬，露出半个脑袋，扁平插画风格，高饱和",
        "🤭,😂",
    ))
    T.append(_tpl(
        "mt_lying_flat", "摆烂人生", "搞笑沙雕", "🛌",
        "躺平宣言，当代年轻人的精神状态",
        "paper", "flat",
        "努力？", "我选择躺平",
        ["努力？|我选择躺平", "随便吧|就这样吧", "明天再说|后天也行"],
        "一只咸鱼躺在沙发上，身边散落零食，报纸复古质感，扁平插画",
        "🛌,🥤",
    ))
    T.append(_tpl(
        "mt_truth_bomb", "真香现场", "搞笑沙雕", "🍚",
        "嘴上说着不要，身体却很诚实——真香定律",
        "red", "3d",
        "我说了不吃！", "真香",
        ["我说了不吃！|真香", "就一口|再来一口", "减肥？|明天开始"],
        "圆滚滚的橘猫大口吃面的可爱场景，3D 软萌卡通，满足的表情，红色喜庆背景",
        "🍜,😋",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "mt_speechless", "无语凝噎", "搞笑沙雕", "🙄",
        "槽点太多不知从何吐起，高冷白底适配一切无语瞬间",
        "white", "flat",
        "……", "你说得对（并不）",
        ["……|你说得对（并不）", "我竟无言以对|你赢了", "离谱|但合理"],
        "极简白底上一只面无表情的白色猫头，扁平插画，留白得当",
        "🙄,🗯️",
    ))
    # ══ 电商营销 3（深度优化场景）══
    T.append(_tpl(
        "mt_flash_sale", "限时秒杀", "电商营销", "⚡",
        "大促秒杀氛围包：红底公告风，紧迫感与转化率拉满",
        "red", "flat",
        "限时秒杀！", "手慢无",
        ["限时秒杀！|手慢无", "最后 100 件|错过再等一年", "今晚 8 点|准时开抢"],
        "红色背景上巨大的金色闪电与倒计时数字，扁平插画风格，冲击力强",
        "⚡,🛒",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "mt_review", "好评晒单", "电商营销", "⭐",
        "买家秀好评包：晒单返现、五星好评必备",
        "gradient", "3d",
        "五星好评！", "值得回购",
        ["五星好评！|值得回购", "收到啦！|超级满意", "回购第 3 次|闭眼入"],
        "可爱的购物袋上堆满星星与爱心，3D 软萌卡通，渐变背景，喜悦氛围",
        "⭐,💖",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "mt_new_arrival", "上新预告", "电商营销", "🎁",
        "新品发布预告包：霓虹灯效果拉高期待值",
        "neon", "neon",
        "新品即将上线！", "敬请期待",
        ["新品即将上线！|敬请期待", "倒计时 3 天|抢先预定", "这次的新品|有点东西"],
        "霓虹灯管勾勒的礼物盒在深色背景上闪烁，赛博朋克光效，神秘期待感",
        "🎁,✨",
    ))
    # ══ 节日祝福 3 ══
    T.append(_tpl(
        "mt_new_year", "春节祝福", "节日祝福", "🧧",
        "新春拜年包：红底金文，恭喜发财",
        "red", "flat",
        "恭喜发财！", "红包拿来",
        ["恭喜发财！|红包拿来", "新春快乐|万事如意", "过年好！|发大财"],
        "红灯笼、金元宝与鞭炮的喜庆画面，中国红底色，扁平插画",
        "🧧,🏮",
    ))
    T.append(_tpl(
        "mt_mid_autumn", "中秋团圆", "节日祝福", "🌕",
        "中秋祝福包：月圆人团圆，温情满满",
        "paper", "ink",
        "中秋快乐！", "花好月圆",
        ["中秋快乐！|花好月圆", "人月两团圆|千里共婵娟", "月亮代表|我的心"],
        "水墨风格的圆月与桂花枝，玉兔剪影，留白得当，水墨国风",
        "🌕,🐰",
    ))
    T.append(_tpl(
        "mt_christmas", "圣诞快乐", "节日祝福", "🎄",
        "圣诞祝福包：霓虹圣诞树，节日氛围拉满",
        "neon", "neon",
        "Merry Christmas！", "圣诞快乐",
        ["Merry Christmas！|圣诞快乐", "圣诞老人|加班中", "今天 要快乐|也要收礼物"],
        "霓虹灯管勾勒的圣诞树与星星，深色背景，赛博朋克光效",
        "🎄,🎅",
    ))
    # ══ 直播互动 2 ══
    T.append(_tpl(
        "mt_live_sell", "主播带货", "直播互动", "📢",
        "直播间弹幕氛围包：3-2-1 上链接，节奏感强",
        "yellow", "flat",
        "三二一，", "上链接！",
        ["三二一，|上链接！", "家人们|拼手速了", "这个价格|史无前例"],
        "直播间的聚光灯下，麦克风与购物车图标，扁平插画，热闹氛围",
        "📢,🔥",
    ))
    T.append(_tpl(
        "mt_live_fan", "粉丝互动", "直播互动", "💬",
        "粉丝弹幕包：主播与粉丝的快乐互动",
        "sticker", "3d",
        "主播看我看我！", "已三连",
        ["主播看我看我！|已三连", "哈哈哈哈|太有才了", "新来的|求带"],
        "可爱的弹幕气泡与爱心飞向屏幕，3D 软萌卡通，贴纸质感",
        "💬,👍",
    ))
    return T


def init_meme_templates():
    """启动初始化：模板不存在才写盘（用户可自行编辑 JSON），返回全部模板。"""
    for t in _meme_templates():
        path = TEMPLATE_DIR / f"{t['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化表情包模板：{t['name']}")
    return load_all(TEMPLATE_DIR)










@router.get("/list")
async def meme_templates_list(category: str = "", q: str = ""):
    """表情包模板市场列表（分类/热度/定价）。"""
    items = []
    for t in load_all(TEMPLATE_DIR):
        pricing = t.get("pricing") or {}
        items.append({
            "id": t["id"],
            "name": t.get("name", "未命名"),
            "category": t.get("category", "通用"),
            "icon": t.get("icon", "😀"),
            "desc": t.get("desc", ""),
            "style": t.get("style", "yellow"),
            "ai_style": t.get("ai_style", "flat"),
            "texts": t.get("texts", []),
            "decoration": t.get("decoration", ""),
            "prompt_hint": t.get("prompt_hint", ""),
            "pricing": pricing,
            "pricing_label": {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
            .get(pricing.get("mode", "free"), "免费"),
            "usage": get_usage(t["id"], 'meme_template_usage'),
        })
    if q:
        ql = q.strip().lower()
        items = [i for i in items if ql in i["name"].lower() or ql in i["category"].lower() or ql in i["desc"].lower()]
    if category and category != "全部":
        items = [i for i in items if i["category"] == category]
    cats: dict = {}
    for it in items:
        cats.setdefault(it["category"], {"label": it["category"], "count": 0})
        cats[it["category"]]["count"] += 1
    return {"total": len(items), "items": items, "categories": list(cats.values())}


@router.get("/{tid}")
async def meme_template_detail(tid: str):
    """表情包模板详情（完整配方，前端填充生成表单）。"""
    t = load_one(TEMPLATE_DIR, tid, '表情包模板不存在')
    pricing = t.get("pricing") or {}
    data = {k: t[k] for k in ("id", "name", "category", "icon", "desc", "style", "ai_style",
                              "top_hint", "bottom_hint", "texts", "prompt_hint",
                              "decoration", "pricing") if k in t}
    labels = {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
    data["category_label"] = data.get("category", "通用")
    data["pricing_label"] = labels.get(pricing.get("mode", "free"), "免费")
    data["usage"] = get_usage(tid, 'meme_template_usage')
    return data


# 启动初始化
init_meme_templates()
