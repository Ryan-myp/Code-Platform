# -*- coding: utf-8 -*-
"""音乐场景模板库：按"使用场景"封装的音乐配方（风格/情绪/声音/时长/BPM/结构/歌词示例）。

对标专业音频制作流程：每个模板 = 场景化配方（style/mood/voice/duration/bpm/乐器编配/段落结构）
+ 可直接使用的场景歌词示例（带 [Verse]/[Chorus] 段式，随模板自动填充生成表单），
让创作者选场景即可出专业级成品：电商带货卡点、短视频 BGM、直播氛围、播客片头等。

商业化：pricing free/once/day/month（积分），热度统计（生成时记录）。
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "music_scene_templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/music-scene-templates", tags=["音乐场景模板"])
from common.template_utils import load_all, load_one, get_usage, record_usage



def _tpl(tid, name, category, icon, desc, style, mood, voice, duration,
         bpm, instrument, structure, lyrics, theme, tips, pricing=None):
    return {
        "id": tid, "name": name, "category": category, "icon": icon, "desc": desc,
        "style": style, "mood": mood, "voice": voice, "duration": duration,
        "bpm": bpm, "instrument": instrument, "structure": structure,
        "lyrics_template": lyrics, "theme_suggestion": theme, "pro_tips": tips,
        "pricing": pricing or {"mode": "free", "once": 0, "day": 0, "month": 0},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _music_scene_templates():
    T = []
    # ══ 电商 4：带货钩子 / 秒杀促销 / 美妆高级 / 生活方式 ══
    T.append(_tpl(
        "ms_ecom_hook", "带货钩子开场", "电商", "🛍️",
        "短视频带货黄金 0-3 秒钩子音效 + 强节拍，情绪直接拉满，观众划不走",
        "electronic", "energetic", "female", 15, 128,
        "合成器 Pad + 鼓机 Four-on-floor + 侧链贝斯",
        "前奏 2 秒（悬念音）→ 鼓点 4 拍爆入（钩子画面）→ 副歌循环卡点（卖点快闪）→ 尾音淡出",
        "[Verse 1]\n三二一 别划走\n这个好东西今天必须有\n库存只剩最后一百件\n手慢真的拍不到\n\n[Chorus]\n买它买它就是现在\n错过今天再等一年\n直播间里最后一波\n倒计时五 四 三 二 一",
        "电商直播限时秒杀带货",
        "0-3 秒必须上鼓点；卖点词卡在正拍；结尾留强收拍衔接下一镜",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "ms_ecom_flash", "秒杀促销卡点", "电商", "⚡",
        "大促/秒杀专属 BGM：说唱节奏 + 压迫感贝斯，倒计时紧张氛围拉满",
        "rap", "energetic", "male", 30, 88,
        "808 贝斯 + 说唱鼓组 + 镲片上升音",
        "开场倒计时 4 拍 → 主歌陈述（优惠信息）→ 副歌爆发（上链接口令）→ 收尾强拍",
        "[Verse 1]\n今晚八点 准时开抢\n优惠力度 前所未有\n满减叠加 折上再折\n错过今天 就要再等一年\n\n[Chorus]\n三二一 上链接\n购物车 清空它\n今晚全场 最低价\n抢到就是 赚到啦",
        "双十一大促倒计时直播",
        "口令词与鼓点对齐；价格信息放副歌前停顿；结尾加镲片强收",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "ms_ecom_beauty", "美妆展示高级感", "电商", "💄",
        "美妆/护肤品牌质感 BGM：爵士律动 + 浪漫氛围，产品展示像广告大片",
        "jazz", "romantic", "female", 30, 108,
        "钢琴 + 爵士鼓刷 + 贝斯 Walking + 弦乐垫",
        "钢琴单音开场（产品特写）→ 律动进入（使用过程）→ 弦乐铺开（效果对比）→ 轻收尾",
        "[Verse 1]\n晨光落在梳妆台\n一抹温柔慢慢晕开\n肌肤喝饱了水光\n镜子里的自己发光\n\n[Chorus]\n每一天都值得\n被自己温柔对待\n这份美 由内而外\n像星光一样闪耀",
        "高端美妆产品宣传",
        "特写镜对钢琴单音；效果对比镜对弦乐铺开；语速放慢显高级",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_ecom_life", "生活方式轻快", "电商", "🧺",
        "家居/日用好物短视频 BGM：轻快流行，生活感与种草感平衡",
        "pop", "happy", "female", 30, 108,
        "木吉他 + 轻鼓 + 手铃 + 贝斯",
        "主歌轻快进入（使用场景）→ 副歌明亮（好物亮点）→ 桥段（小提醒）→ 收尾渐弱",
        "[Verse 1]\n清晨第一杯温水\n厨房飘着面包香\n小物件装点日常\n平凡日子也有光\n\n[Chorus]\n把生活过成想要的模样\n小小改变 大大不同\n好物藏在细节里\n每一天都更爱自己",
        "家居好物日常种草",
        "主歌配生活场景空镜；副歌配产品特写；轻快不喧宾夺主",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 短视频 4：卡点舞蹈 / Vlog / 美食 / 旅行 ══
    T.append(_tpl(
        "ms_short_dance", "卡点舞蹈", "短视频", "💃",
        "抖音/快手卡点舞专用：电子强拍 + 高频节拍点，动作卡拍零门槛",
        "electronic", "energetic", "female", 15, 122,
        "合成器主音 + 电子鼓 + 重低音",
        "4 拍预备 → 主旋律 8 拍（舞蹈动作）→ 重音段落（变装/特写）→ 循环收尾",
        "[Verse 1]\n跟我一起 举起手\n左右摇摆 不回头\n音乐一响 全场嗨\n这一刻 尽情摇摆\n\n[Chorus]\n咚哒咚哒 踩节拍\n转身跳跃 超精彩\n卡点卡点 一起来\n今晚舞池 你最帅",
        "抖音卡点舞蹈挑战",
        "动作切换点必须落在重音；变装镜对重音段落；15-30 秒为最佳完播区间",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_short_vlog", "生活 Vlog 日常", "短视频", "📷",
        "日常 Vlog 治愈 BGM：民谣木吉他 + 轻快节奏，记录感的松弛氛围",
        "folk", "calm", "female", 30, 96,
        "木吉他扫弦 + 手鼓 + 口琴点缀",
        "前奏 2 小节（环境空镜）→ 主歌（日常片段）→ 副歌轻快（高光时刻）→ 渐弱收尾",
        "[Verse 1]\n今天的阳光刚刚好\n街角的猫在打盹\n买了束花给自己\n生活要有仪式感\n\n[Chorus]\n慢一点 再慢一点\n把平凡过成诗篇\n记录每一帧温暖\n就是最好的纪念",
        "城市漫步日常记录",
        "环境音与吉他前奏交融；高光镜对副歌；字幕卡在乐句停顿处",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_short_food", "美食治愈", "短视频", "🍜",
        "美食制作/探店 BGM：轻爵士律动，食材处理的细节声与音乐自然融合",
        "jazz", "calm", "female", 20, 108,
        "钢琴 + 贝斯 + 轻刷鼓",
        "钢琴单音开场（食材特写）→ 律动进入（烹饪过程）→ 轻快段落（出锅瞬间）→ 收尾",
        "[Verse 1]\n锅里咕嘟咕嘟响\n香气飘满了厨房\n一把葱花撒下去\n人间烟火最治愈\n\n[Chorus]\n好好吃饭 好好生活\n一碗热汤 慰藉你我\n食物的温度里\n藏着最简单的快乐",
        "深夜食堂美食制作",
        "煎炸声与鼓点错开不打架；出锅镜对副歌第一拍；ASMR 感优先",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_short_travel", "旅行大片", "短视频", "🏔️",
        "旅行/风光大片 BGM：古典弦乐 + 史诗感，航拍镜头的气场全开",
        "classical", "epic", "female", 30, 78,
        "弦乐组 + 圆号 + 定音鼓 + 竖琴",
        "弦乐渐入（大远景）→ 主题进入（航拍穿云）→ 鼓点加入（徒步/冲刺）→ 辉煌收尾",
        "[Verse 1]\n翻过那座山\n穿过那片云\n世界在脚下展开\n远方在召唤\n\n[Chorus]\n去追风 去逐光\n去看没见过的远方\n每一步都算数\n每一程都滚烫",
        "川西航拍旅行大片",
        "航拍穿云对弦乐主题；画面切点对重音；结尾留白给落版字幕",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 直播/播客 3：直播氛围 / 播客片头 / 播客片尾 ══
    T.append(_tpl(
        "ms_live_room", "直播间氛围", "直播", "📺",
        "直播带货/聊天背景乐：循环友好型轻流行，不抢人声、久听不腻",
        "pop", "calm", "female", 60, 108,
        "钢琴 + 轻鼓 + 贝斯",
        "主歌循环（讲解中）→ 副歌轻起（福利时刻）→ 回到主歌（循环衔接）",
        "[Verse 1]\n欢迎来到直播间\n今天福利特别多\n喜欢的朋友点点关注\n好物马上安排\n\n[Chorus]\n热闹的夜晚 有你在\n分享好物 分享爱\n直播间里 不见不散\n快乐就是这么简单",
        "晚间直播陪聊氛围",
        "音量比讲解人声低 8-10dB；副歌只作短暂点缀；60-120 秒循环剪辑",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_podcast_intro", "播客片头", "播客", "🎙️",
        "播客/栏目开场 15 秒记忆点：电子史诗感，品牌听觉 Logo",
        "electronic", "epic", "female", 15, 122,
        "合成器 Rise + 鼓组 + 人声切片",
        "Rise 渐强 4 秒（悬念）→ 主题旋律 8 秒（节目口号）→ 强收拍（进入正片）",
        "[Verse 1]\n欢迎收听\n我们的声音宇宙\n每周与你 准时相遇\n好故事 从这里开始\n\n[Chorus]\n听见 看见 想见\n每一期都值得期待\n这里是\n不设限的谈话现场",
        "科技播客栏目片头",
        "片头控制在 12-18 秒；口号词对准主题旋律；结尾强收拍接人声",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "ms_podcast_outro", "播客片尾", "播客", "🌙",
        "播客/节目收尾 BGM：抒情钢琴渐弱，自然过渡到结束语与下期预告",
        "ballad", "calm", "female", 20, 72,
        "钢琴 + 弦乐垫",
        "钢琴主题（本期回顾）→ 弦乐铺开（下期预告）→ 渐弱淡出",
        "[Verse 1]\n感谢你的收听\n今晚的故事到这里\n如果喜欢请订阅\n我们下期再见\n\n[Chorus]\n愿每个夜晚\n都有好声音陪伴\n晚安 好梦\n下期不见不散",
        "播客节目收尾",
        "音量渐弱至 -12dB 淡出；预告词对准弦乐铺开段；20-30 秒为宜",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 品牌/场景 3：品牌广告 / 健身运动 / 睡前放松 ══
    T.append(_tpl(
        "ms_brand_ad", "品牌广告大片", "品牌", "🏆",
        "品牌 TVC/新品发布 BGM：古典史诗交响，质感与气场并重",
        "classical", "epic", "female", 30, 78,
        "交响弦乐 + 铜管 + 定音鼓 + 合唱垫",
        "弦乐渐入（品牌理念）→ 铜管主题（产品亮相）→ 定音鼓推进（价值主张）→ 辉煌收尾（Logo）",
        "[Verse 1]\n每一次突破\n都源于初心\n每一个细节\n都值得极致\n\n[Chorus]\n此刻 见证不凡\n让世界 看见我们\n以匠心 致敬时代\n与卓越 并肩同行",
        "品牌年度宣传片",
        "Logo 落版对准定音鼓强收；画面转场对乐句呼吸；30-60 秒版本通用",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "ms_gym_workout", "健身运动", "生活", "🏋️",
        "健身/运动打卡 BPM 120+：摇滚硬核节拍，训练节奏感拉满",
        "rock", "energetic", "male", 60, 126,
        "失真吉他 + 摇滚鼓 + 强贝斯",
        "强拍开场（热身）→ 主歌推进（力量训练）→ 副歌爆发（冲刺组）→ 收尾减速（拉伸）",
        "[Verse 1]\n汗水滴落 肌肉燃烧\n每一次坚持 都算数\n别停下来 再撑一秒\n你会感谢 现在的自己\n\n[Chorus]\n燃烧吧 脂肪\n突破吧 极限\n今天的汗水\n是明天的勋章",
        "健身房力量训练",
        "训练动作切换对重音；冲刺组对副歌爆发段；拉伸段用后半减速小节",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_sleep_relax", "睡前放松", "生活", "🌙",
        "冥想/助眠/读书 BGM：抒情钢琴慢板，白噪音友好型舒缓氛围",
        "ballad", "calm", "female", 120, 72,
        "钢琴单音 + 弦乐长音垫",
        "钢琴主题缓入（呼吸引导）→ 弦乐垫铺开（深度放松）→ 极简收尾（渐弱）",
        "[Verse 1]\n夜色温柔 星光低垂\n深呼吸 慢慢放松\n把今天的疲惫\n都交给夜晚\n\n[Chorus]\n放空思绪 闭上眼\n世界安静 心也安然\n晚安 好梦\n明天又是 新的一天",
        "睡前冥想助眠",
        "无强拍无鼓点；音量-15dB 以下；循环 120-300 秒剪辑",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 游戏/活动 2：游戏循环 / 年会开场 ══
    T.append(_tpl(
        "ms_game_loop", "游戏循环配乐", "游戏", "🎮",
        "小游戏/休闲游戏 BGM：电子循环友好型，8-16 秒无缝循环",
        "electronic", "energetic", "female", 30, 122,
        "合成器琶音 + 电子鼓 + 贝斯",
        "琶音循环 2 小节（场景基调）→ 加鼓（操作反馈）→ 加贝斯（关卡推进）→ 回到循环起点",
        "[Verse 1]\n出发吧 冒险家\n前方有新的关卡\n收集能量 解锁技能\n一关一关 向前冲\n\n[Chorus]\n叮咚 得分\n漂亮 通关\n再来一局 停不下来\n这就是游戏的快乐",
        "休闲小游戏背景音乐",
        "循环点必须无痕（首尾小节和弦一致）；操作音效与节拍错开",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "ms_event_open", "年会活动开场", "活动", "🎉",
        "年会/发布会/活动开场 BGM：电子史诗感，掌声与灯光的入场仪式",
        "electronic", "epic", "female", 20, 122,
        "合成器 + 鼓组 + 人声合唱垫",
        "Rise 渐强（灯光暗下）→ 鼓点爆入（嘉宾登场）→ 主题旋律（开场致辞）→ 强收拍",
        "[Verse 1]\n灯光亮起 音乐响起\n今晚属于每一个你\n过去一年 感谢有你\n新的篇章 一起开启\n\n[Chorus]\n欢呼吧 掌声响起来\n这是我们的高光时刻\n举杯吧 敬奋斗的自己\n明年还要 一起精彩",
        "公司年会开场片头",
        "嘉宾登场对鼓点爆入；开场致辞对主题旋律；20-30 秒为佳",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    return T


def init_music_scene_templates():
    """启动初始化：模板不存在才写盘（用户可自行编辑 JSON），返回全部模板。"""
    for t in _music_scene_templates():
        path = TEMPLATE_DIR / f"{t['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化音乐场景模板：{t['name']}")
    return load_all(TEMPLATE_DIR)










@router.get("/list")
async def music_scene_templates_list(category: str = "", q: str = ""):
    """音乐场景模板市场列表（分类/热度/定价）。"""
    items = []
    for t in load_all(TEMPLATE_DIR):
        pricing = t.get("pricing") or {}
        items.append({
            "id": t["id"],
            "name": t.get("name", "未命名"),
            "category": t.get("category", "通用"),
            "icon": t.get("icon", "🎵"),
            "desc": t.get("desc", ""),
            "style": t.get("style", "pop"),
            "mood": t.get("mood", "calm"),
            "voice": t.get("voice", "female"),
            "duration": t.get("duration", 30),
            "bpm": t.get("bpm", 100),
            "lyrics_template": t.get("lyrics_template", ""),
            "theme_suggestion": t.get("theme_suggestion", ""),
            "pricing": pricing,
            "pricing_label": {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
            .get(pricing.get("mode", "free"), "免费"),
            "usage": get_usage(t["id"], 'music_scene_template_usage'),
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
async def music_scene_template_detail(tid: str):
    """音乐场景模板详情（完整配方，前端填充生成表单）。"""
    t = load_one(TEMPLATE_DIR, tid, '音乐场景模板不存在')
    pricing = t.get("pricing") or {}
    data = {k: t[k] for k in ("id", "name", "category", "icon", "desc", "style", "mood",
                              "voice", "duration", "bpm", "instrument", "structure",
                              "lyrics_template", "theme_suggestion", "pro_tips", "pricing") if k in t}
    labels = {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
    data["category_label"] = data.get("category", "通用")
    data["pricing_label"] = labels.get(pricing.get("mode", "free"), "免费")
    data["usage"] = get_usage(tid, 'music_scene_template_usage')
    return data


# 启动初始化
init_music_scene_templates()
