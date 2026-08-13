# -*- coding: utf-8 -*-
"""配音场景模板库：按"使用场景"封装的配音配方（音色/语速/音调/情绪/文案模板）。

对标专业配音工作室：每个模板 = 场景化配方（voice/speed/pitch/emotion）+ 3 组即用文案
+ 配音技巧，选场景一键填充即可出专业级配音（电商带货/知识口播/有声书/播客等），
与视频广告/短剧/音乐场景模板体系配套，覆盖内容创作全链路。

商业化：pricing free/once/day/month（积分），热度统计（生成时记录）。
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "voice_templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/voice-templates", tags=["配音场景模板"])
from common.template_utils import load_all, load_one, get_usage, record_usage



def _tpl(tid, name, category, icon, desc, voice, speed, pitch, emotion,
         texts, tips, duration=60, pricing=None):
    return {
        "id": tid, "name": name, "category": category, "icon": icon, "desc": desc,
        "voice": voice, "speed": speed, "pitch": pitch, "emotion": emotion,
        "texts": texts, "pro_tips": tips, "duration": duration,
        "pricing": pricing or {"mode": "free", "once": 0, "day": 0, "month": 0},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _voice_templates():
    T = []
    # ══ 电商 4（深度优化场景）══
    T.append(_tpl(
        "vt_ecom_sell", "电商带货口播", "电商", "🛍️",
        "直播间/短视频带货标准口播：云健浑厚音色 + 微提音调，信任感与促单力兼备",
        "zh-CN-YunjianNeural", 1.0, 5, "angry",
        [
            "家人们，今天这个价格真的是史无前例！同样的品质，外面至少要贵三倍，今天我们直播间直接给到地板价。库存只有最后 500 单，拍完立刻恢复原价，想要的姐妹现在就去下单！",
            "这款产品我用了整整一个月才敢推荐给大家。它的核心成分是 XXX，实测效果立竿见影。今天厂家直供，没有中间商赚差价，错过这波就要再等三个月！",
            "三二一，上链接！倒计时开始，五、四、三、二、一！已经拍到的家人在公屏扣个一，没拍到的不要着急，下一波马上安排！",
        ],
        "卖点前置 3 秒内讲完；价格对比用重音强调；促单口令与背景音乐重拍对齐；语速保持 1.0 不飘，信任感靠沉稳",
        45,
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "vt_ecom_flash", "秒杀倒计时", "电商", "⚡",
        "大促秒杀氛围配音：云希少年音 + 高速率，紧迫感直接拉满",
        "zh-CN-YunxiNeural", 1.12, 8, "angry",
        [
            "注意了注意了！今晚八点，双十一第一波秒杀准时开启！五千件库存，五秒钟抢完！现在先去加购物车，八点整准时开抢！",
            "最后两分钟！最后两分钟！这个价格全场只有这一次！错过了今晚，明天就是原价！还没上车的朋友抓紧时间！",
            "恭喜抢到的朋友们！没抢到的别灰心，第二波秒杀明天同一时间，我们不见不散！",
        ],
        "数字与时间词用重音（八点/五秒/两分钟）；语速 1.1 但咬字必须清晰；结尾留停顿给音效",
        30,
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "vt_ecom_life", "生活方式种草", "电商", "🧺",
        "家居/日用好物种草：晓伊活泼音色，生活感与种草欲自然平衡",
        "zh-CN-XiaoyiNeural", 1.05, 3, "happy",
        [
            "姐妹们，这个收纳神器我强烈安利！以前厨房台面乱七八糟，用了它之后，所有东西都各就各位，每天早上做早餐的心情都变好了！",
            "生活里的幸福感，往往就藏在这些小物件里。一杯好看的杯子，一盏温柔的夜灯，都能让平凡的日子闪闪发光。",
            "今天分享的这几件好物，都是我亲测回购过三次以上的。链接放在左下角，需要的姐妹自取哦！",
        ],
        "语气带笑、上扬尾音；生活场景细节描写放缓 0.1 速；种草口令轻快不油腻",
        60,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "vt_ecom_tech", "3C 数码测评", "电商", "📱",
        "数码产品测评解说：云希清晰音色 + 严肃情绪，参数讲解专业可信",
        "zh-CN-YunxiNeural", 1.0, 0, "serious",
        [
            "本期视频我们来实测这台机器的真实性能。首先看处理器，这一代芯片在跑分软件中单核提升了百分之十五，多核提升了百分之二十。",
            "续航方面，五千毫安时电池配合新一代电源管理芯片，重度使用一天一充，中度使用可以坚持一天半。这个表现，在同类产品中属于第一梯队。",
            "总结一下：如果你是重度用户，这台机器值得入手；如果只是日常使用，入门版性价比更高。参数表我放在评论区置顶。",
        ],
        "参数读法：数字与单位之间停顿 0.3 秒；对比结论加重音；语速稳定不赶，专业感靠从容",
        90,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 短视频 3 ══
    T.append(_tpl(
        "vt_short_know", "知识口播", "短视频", "📚",
        "知识科普/干货分享：晓晓温柔音色 + 轻快语速，专业但不枯燥",
        "zh-CN-XiaoxiaoNeural", 1.05, 0, "gentle",
        [
            "今天用一分钟讲清楚一个概念：什么是复利？简单说，就是利滚利。你存一万块，年化百分之十，十年后不是两万，而是两万五千九百多。",
            "很多人不知道，大脑在早晨七点到九点，记忆效率是晚上的三倍。所以重要的学习任务，建议安排在上午完成。",
            "记住这个公式：收入减去储蓄才是支出，而不是收入减去支出才是储蓄。顺序反了，你的钱包就永远存不下钱。",
        ],
        "结论句前停顿 0.5 秒；关键数字放慢 0.1 速；每 30 秒一个钩子问题",
        60,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "vt_short_travel", "旅行解说", "短视频", "🏔️",
        "旅行/风景大片旁白：晓晓舒缓音色，画面感与氛围感兼备",
        "zh-CN-XiaoxiaoNeural", 0.95, -5, "gentle",
        [
            "凌晨四点的山顶，云海像一条白色的河流，缓缓漫过群山。太阳升起的那一刻，整个世界都被染成了金色。",
            "穿过这片原始森林，就能看到海拔四千六百米的冰川湖。湖水蓝得不像真的，像一块巨大的蓝宝石，安静地躺在群山之间。",
            "旅行教会我们的事情，不是去了多远，而是带回了多少。这一路的风光，值得你用一生去回忆。",
        ],
        "景物描写放慢 0.1 速+降音调，画面感更强；情绪金句回到原速；航拍镜头前预留呼吸停顿",
        60,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "vt_short_game", "游戏解说", "短视频", "🎮",
        "游戏实况/赛事解说：云希阳光音色 + 高音调，激情与操作同步",
        "zh-CN-YunxiNeural", 1.1, 5, "angry",
        [
            "来了来了！这一波团战直接开打！打野绕后，辅助开团，一波完美的控制链，对面根本没法还手！",
            "注意看这个细节，他闪现躲掉了致命技能，反手一套连招直接带走对面核心，这个操作直接封神！",
            "兄弟们，这把真的翻盘了！从经济落后八千到一波推平基地，这就是电子竞技的魅力！",
        ],
        "团战/操作高潮段提速 0.15；关键操作名加重音；解说与画面动作差 0.5 秒预判",
        90,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 音频内容 4 ══
    T.append(_tpl(
        "vt_audio_book", "有声书朗读", "音频", "📖",
        "小说/故事朗读：晓晓低沉舒缓音色，沉浸式听觉体验",
        "zh-CN-XiaoxiaoNeural", 0.9, -8, "gentle",
        [
            "夜色渐深，街角的咖啡馆还亮着灯。她推开门，风铃清脆地响了一声，像是这座城市的叹息。",
            "他站在月台上，看着列车缓缓驶来。这些年走过的路，认识的人，都在这一刻涌上心头。",
            "多年以后，她依然记得那个夏天的午后。阳光透过梧桐叶洒下来，少年骑车经过，卷起一阵风。",
        ],
        "叙述语速 0.9 匀速；对话句区分角色音色语气；情绪转折处停顿 0.8 秒；环境描写放慢",
        600,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "vt_podcast", "播客口播", "音频", "🎙️",
        "播客节目口播：云健沉稳音色，对谈感与深度感兼备",
        "zh-CN-YunjianNeural", 0.95, -3, "gentle",
        [
            "欢迎收听本期节目，我是主播。今天我们来聊一个很多人关心的话题：如何在这个时代，保持专注力。",
            "我最近采访了三位从业超过十年的朋友，他们的共同点出人意料：都不是靠意志力硬撑，而是把环境设计成了不需要意志力的样子。",
            "节目的最后，我想把今天最重要的观点再强调一遍：专注不是天赋，是系统。感谢收听，我们下期再见。",
        ],
        "开场 15 秒内抛出话题钩子；观点句放慢加重；结尾语速放缓 0.1 收尾",
        900,
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "vt_story", "儿童故事", "音频", "🧒",
        "儿童绘本/睡前故事：晓墨童声音色，活泼生动有画面感",
        "zh-CN-XiaomoNeural", 0.9, 3, "happy",
        [
            "从前，有一只小刺猬，它的刺总是把朋友们扎得哇哇叫。小刺猬很难过，它想：要是我没有这些刺就好了。",
            "这一天，森林里来了大灰狼。小动物们都吓坏了，只有小刺猬站了出来，把身体缩成一个球，滚向了大灰狼。",
            "从此以后，小刺猬再也不觉得自己的刺是麻烦啦！每个孩子都是独一无二的，就像小刺猬的刺，总有用得到的地方。",
        ],
        "角色对话变换音调区分；拟声词（哇哇/咚咚）放慢夸张；每段结尾留 0.5 秒给翻页",
        300,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "vt_news", "新闻播报", "音频", "📰",
        "资讯/新闻播报：云扬字正腔圆音色，专业播报感",
        "zh-CN-YunyangNeural", 1.0, 0, "serious",
        [
            "今天是八月十二号，星期三。欢迎收看本台新闻。首先来看今日要闻。",
            "据最新消息，全国多地开启新一轮消费促进活动，涵盖家电、汽车、餐饮等多个领域，预计带动消费增长超过百分之十。",
            "今天的新闻就到这里，感谢您的收看。更多资讯，请关注我们的后续报道。",
        ],
        "导语与正文节奏分明；数字与百分比加重音；换行处停顿 0.5 秒",
        300,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 品牌教育 3 ══
    T.append(_tpl(
        "vt_ad_brand", "品牌广告", "品牌", "🏆",
        "品牌 TVC/宣传片旁白：云健浑厚音色 + 降音调，大气沉稳有质感",
        "zh-CN-YunjianNeural", 0.95, -3, "gentle",
        [
            "二十七年，我们只做一件事：让每一件产品，都经得起时间的检验。",
            "真正的品质，不是看得见的奢华，而是看不见的坚持。每一次打磨，都只为你的每一次使用。",
            "致敬每一个认真生活的人。从今天起，让品质，成为你的日常。",
        ],
        "品牌名加重音并放慢 0.2 速；金句之间停顿 1 秒；整体语速 0.95 显大气",
        30,
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "vt_course", "课程讲解", "教育", "🎓",
        "在线课程/教程配音：晓晓清晰音色，讲解节奏教学感强",
        "zh-CN-XiaoxiaoNeural", 0.95, 0, "serious",
        [
            "欢迎来到本节课。今天我们学习第二章的核心内容：如何搭建一个完整的工作流。",
            "请注意这个关键点：在开始之前，一定要先明确目标。没有明确目标的执行，都是在浪费时间。",
            "课后作业：请用今天学到的三个步骤，完成你自己的第一个项目。我们下节课见。",
        ],
        "知识点前说'请注意/关键点来了'引导；例题放慢 0.15 速；小节结束留 1 秒思考时间",
        600,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "vt_emotion", "情感电台", "音频", "💌",
        "情感/治愈电台：晓晓低音调温柔音色，夜晚氛围感",
        "zh-CN-XiaoxiaoNeural", 0.9, -8, "gentle",
        [
            "夜深了，你还在为白天的事情睡不着吗？有些话，白天说不出口，那就留到夜晚，说给自己听。",
            "亲爱的，你要知道，你不需要成为所有人的例外，你只需要成为自己的光。",
            "今天的节目到这里就结束了。愿你今夜好梦，我们明晚，不见不散。",
        ],
        "语速 0.9 全程匀速；'亲爱的/愿你'等词放慢加重；段落间停顿 1 秒留白",
        600,
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    return T


def init_voice_templates():
    """启动初始化：模板不存在才写盘（用户可自行编辑 JSON），返回全部模板。"""
    for t in _voice_templates():
        path = TEMPLATE_DIR / f"{t['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化配音场景模板：{t['name']}")
    return load_all(TEMPLATE_DIR)










@router.get("/list")
async def voice_templates_list(category: str = "", q: str = ""):
    """配音场景模板市场列表（分类/热度/定价，含一键填充所需全量字段）。"""
    items = []
    for t in load_all(TEMPLATE_DIR):
        pricing = t.get("pricing") or {}
        items.append({
            "id": t["id"],
            "name": t.get("name", "未命名"),
            "category": t.get("category", "通用"),
            "icon": t.get("icon", "🎙️"),
            "desc": t.get("desc", ""),
            "voice": t.get("voice", "zh-CN-XiaoxiaoNeural"),
            "speed": t.get("speed", 1.0),
            "pitch": t.get("pitch", 0),
            "emotion": t.get("emotion", ""),
            "texts": t.get("texts", []),
            "pro_tips": t.get("pro_tips", ""),
            "duration": t.get("duration", 60),
            "pricing": pricing,
            "pricing_label": {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
            .get(pricing.get("mode", "free"), "免费"),
            "usage": get_usage(t["id"], 'voice_template_usage'),
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
async def voice_template_detail(tid: str):
    """配音场景模板详情（完整配方，前端填充生成表单）。"""
    t = load_one(TEMPLATE_DIR, tid, '配音模板不存在')
    pricing = t.get("pricing") or {}
    data = {k: t[k] for k in ("id", "name", "category", "icon", "desc", "voice", "speed",
                              "pitch", "emotion", "texts", "pro_tips", "duration",
                              "pricing") if k in t}
    labels = {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
    data["category_label"] = data.get("category", "通用")
    data["pricing_label"] = labels.get(pricing.get("mode", "free"), "免费")
    data["usage"] = get_usage(tid, 'voice_template_usage')
    return data


# 启动初始化
init_voice_templates()
