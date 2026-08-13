# -*- coding: utf-8 -*-
"""短剧剧本题材模板库：专业编剧方法论结构化的爆款题材模板。

每个模板 = JSON 定义（人设/关系/冲突、起承转合结构、台词风格、开篇钩子），
生成剧本时注入 LLM 提示词（short_drama._generate_script 的 template 参数），
让 AI 按爆款题材的叙事套路产出剧本：钩子开场 → 冲突升级 → 反转 → 悬念结尾。

商业化：pricing free/once/day/month（积分），热度统计（生成时记录）。
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "drama_templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/drama-templates", tags=["短剧题材模板"])
from common.template_utils import load_all, load_one, get_usage, record_usage



def _tpl(tid, name, category, icon, desc, setup, structure, style, hook,
         pricing=None, w=(1080, 1920)):
    return {
        "id": tid, "name": name, "category": category, "icon": icon, "desc": desc,
        "setup": setup, "structure": structure, "style": style, "hook": hook,
        "pricing": pricing or {"mode": "free", "once": 0, "day": 0, "month": 0},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _drama_templates():
    T = []
    # ══ 爽文 4：都市霸总 / 逆袭战神 / 重生复仇 / 穿越系统 ══
    T.append(_tpl(
        "dt_ceo", "都市霸总", "爽文", "👑",
        "霸总追妻火葬场：冷漠总裁 × 独立女主，先虐后甜强反转，女性向流量之王",
        "核心人设：男主=身价千亿的冷漠霸总（高冷、掌控欲强、口是心非）；女主=外表柔弱内心坚韧的独立女性（拒绝依附、有底线）。关系：契约婚姻/被迫同居开局，互相误会与试探中暗生情愫。核心冲突：门第偏见 + 男配女配搅局 + 男主「追妻火葬场」式悔悟。",
        "四段式：①钩子开场（3 秒内亮冲突：离婚协议/误会撞见）；②误会升级（女主被刁难、男主冷漠误伤，观众憋屈值拉满）；③反转打脸（女主隐藏身份/能力曝光，男主追悔）；④悬念结尾（复合或新误会，留钩子）。",
        "台词金句化：霸总台词简短霸道（「我的女人，只能我欺负」）；女主台词柔中带刚（「我不需要你的施舍」）；旁白突出身份悬念与反差感。",
        "开篇钩子：第一镜必须出现强冲突画面——撕离婚协议、被泼咖啡、或是意外之吻，配合悬念旁白「三年前她签下契约，三年后他却求她别走」。",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "dt_warrior", "逆袭战神", "爽文", "⚔️",
        "废材觉醒流：被轻视的主角隐藏身份，关键时刻一鸣惊人，男频最强爽点公式",
        "核心人设：男主=表面废材/赘婿/落魄人，真实身份为隐藏大佬（战神/首富/王牌）；女主或家人=信任并守护男主的人。关系：被家族/岳家/职场轻视，暗线中积攒实力。核心冲突：当众羞辱 → 身份揭晓 → 打脸全场。",
        "四段式：①钩子开场（当众羞辱画面：退婚/下跪/扫地出门）；②隐忍蓄力（主角低调应对，观众憋屈）；③身份揭晓（最强反转：证件/召集令/黑卡亮出，全场震惊）；④打脸收尾（反派悔恨 + 主角新目标钩子）。",
        "台词反差感：被打压时忍辱负重（「我记住了」）；揭晓时一字千钧（「从现在起，这家公司我说了算」）；旁白渲染隐藏身份的悬念。",
        "开篇钩子：第一镜直接羞辱现场——婚宴退婚、董事会被逐，旁白「所有人都以为他是废物，直到那天他亮出了那个身份」。",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "dt_rebirth", "重生复仇", "爽文", "🔥",
        "重生爽文：带着前世记忆重来一次，步步为营复仇改命，情绪张力拉满",
        "核心人设：主角=前世被害惨死，重生回关键节点（含前世记忆）；反派=前世害死主角的人（亲人/闺蜜/合伙人）。关系：主角表面顺从暗中布局，反派表面友善背后捅刀。核心冲突：预知未来 → 提前截胡 → 复仇清算。",
        "四段式：①钩子开场（重生瞬间：睁眼回到过去/葬礼上醒来）；②暗线布局（提前规避灾祸、揭穿小人）；③高潮反杀（前世仇人身份揭穿、众叛亲离）；④悬念结尾（新对手出现或情感线开启）。",
        "台词宿命感：旁白承担前世今生的对比（「上一世我信错了人，这一世…」）；主角台词冷静克制带杀意（「你欠我的，该还了」）；反派前期伪善台词与后期狰狞形成反差。",
        "开篇钩子：第一镜重生瞬间——车祸后睁眼回到三年前，或葬礼上握住仇人的手，旁白「老天给了我重来一次的机会」。",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "dt_system", "穿越系统", "爽文", "🤖",
        "系统流：宿主绑定金手指系统，任务+奖励驱动，升级爽感可视化",
        "核心人设：主角=普通现代人穿越/绑定系统；系统=有性格的 AI 金手指（冷幽默/毒舌/忠犬）。关系：主角完成任务获得奖励，系统发布任务制造冲突。核心冲突：任务完不成有惩罚 + 反派上门打脸。",
        "四段式：①钩子开场（系统绑定：脑海响起提示音/完成任务瞬间反转）；②任务驱动（小任务-小奖励-小打脸循环，节奏快）；③大任务高潮（终极任务完成，大场面打脸）；④悬念结尾（系统升级/新世界开启）。",
        "台词系统化：系统提示音用特殊语气（「叮！任务完成，奖励…」）；主角与系统斗嘴增加喜剧感；反派嘲讽台词与被打脸台词形成反差。",
        "开篇钩子：第一镜系统绑定或任务倒计时——「叮！新手任务：十分钟内完成销售额十万，失败惩罚：变成一只狗」。",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 情感 3：甜宠校园 / 家庭温情 / 古风虐恋 ══
    T.append(_tpl(
        "dt_sweet", "甜宠校园", "情感", "💗",
        "校园暗恋成真：双向暗恋的糖分爆表，青春纯爱天花板",
        "核心人设：男主=校草学霸（高冷外表温柔内心）；女主=元气少女（开朗乐观小太阳）。关系：同桌/邻座/社团伙伴，互相暗恋不自知。核心冲突：误会 + 情敌 + 考试/竞赛考验，甜中带小虐。",
        "四段式：①钩子开场（校园名场面：迟到撞见/雨中共伞/图书馆偶遇）；②心动拉扯（日常甜梗密集：递水、辅导、护短）；③误会小虐（情敌登场或误会冷战）；④告白圆满（操场告白/毕业季，甜度峰值）。",
        "台词青春感：男主反差萌（嘴上冷淡「顺手而已」，动作全是偏爱）；女主直球可爱（「你耳朵红什么？」）；旁白轻快俏皮。",
        "开篇钩子：第一镜校园心动瞬间——阳光下的少年递来纸巾，或女主跑进教室撞进男主怀里，旁白「十七岁的心动，从那天开始」。",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "dt_family", "家庭温情", "情感", "🏠",
        "催泪亲情流：平凡家庭的守护与和解，主打真实细节和情绪共鸣",
        "核心人设：主角=在外打拼的子女/中年父母；家人=不善表达却默默付出的父母/懂事的孩子。关系：代际隔阂 → 意外事件 → 和解。核心冲突：子女忙于工作忽视家庭 vs 父母默默付出，一场意外让爱浮出水面。",
        "四段式：①钩子开场（生活细节切入：深夜加班电话、空荡荡的饭桌）；②隔阂累积（误会/争吵，观众共情）；③反转催泪（父母日记/旧照片/体检报告揭示沉默的爱）；④和解升华（团圆画面 + 金句收尾）。",
        "台词生活化：不说教不煽情，用细节打动（「你妈给你留的饭，在冰箱第二层」）；旁白克制留白，情绪靠画面和音乐。",
        "开篇钩子：第一镜细节催泪——父母深夜守在门口等晚归的孩子，或孩子翻到父母的旧账本，旁白「有些爱，他们从来不说」。",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "dt_ancient", "古风虐恋", "情感", "🏮",
        "古装虐恋：权谋 + 情深，先虐后甜或意难平，古风意境拉满",
        "核心人设：男主=权倾朝野的王爷/将军（冷峻多疑）；女主=将门之女/和亲公主/才女（坚韧聪慧）。关系：政治联姻/仇家之女开局，信任与背叛交织。核心冲突：家国大义 vs 儿女情长，误会与身世之谜。",
        "四段式：①钩子开场（大婚当夜冷落/赐死/和亲路上）；②权谋纠葛（朝堂斗争 + 情感拉扯）；③误会爆发（背叛/替身/生死离别大虐）；④结局（HE 重逢或 BE 意难平，留白收尾）。",
        "台词文白相间：对白古韵但不晦涩（「本王要的，从来只有你」）；旁白意境化（「那年长安的雪，下了整整一夜」）。",
        "开篇钩子：第一镜大场面——红妆十里的大婚、城楼上的决绝转身、或雪地里的血书，旁白「若早知道结局，她还会选择遇见他吗」。",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 剧情 3：悬疑推理 / 职场逆袭 / 热血创业 ══
    T.append(_tpl(
        "dt_mystery", "悬疑推理", "剧情", "🕵️",
        "单元悬疑：反转再反转的推理短剧，每集一个谜题 + 主线暗线交织",
        "核心人设：主角=天才侦探/刑警/法医（洞察力强、有执念）；搭档=菜鸟助手/记者（观众视角提问）。关系：师徒/搭档互补，各自有秘密。核心冲突：连环案件 + 主角自己的执念案件暗线。",
        "四段式：①钩子开场（案发现场/诡异线索 3 秒进入）；②线索铺陈（嫌疑人轮流登场，误导观众）；③推理反转（关键证据推翻猜想，真凶出人意料）；④悬念结尾（真凶伏法 + 主线暗线推进钩子）。",
        "台词信息密度高：线索对话留白（「他那天穿的不是这件衣服」）；旁白冷峻克制，暗示细节；真凶台词前期正常后期细思极恐。",
        "开篇钩子：第一镜直接案发现场或诡异遗言——雨夜命案、密室留言，旁白「警方赶到时，凶手刚离开三分钟」。",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "dt_office", "职场逆袭", "剧情", "💼",
        "打工人爽剧：被压榨的职场人觉醒反杀，共鸣 + 爽感双拉满",
        "核心人设：主角=老实能干的基层打工人（被抢功被甩锅）；反派=油腻领导/心机同事。关系：职场压迫 vs 隐忍觉醒。核心冲突：项目被抢/背黑锅 → 积累证据 → 公开反击。",
        "四段式：①钩子开场（职场屈辱现场：被抢功/当众甩锅/深夜加班）；②隐忍布局（记录证据、积累人脉、提升能力）；③反转爆发（公开反击：竞标现场/全体会议亮证据）；④爽感收尾（升职或被挖角，新挑战钩子）。",
        "台词职场真实感：领导画饼话术（「年轻人要多锻炼」）；主角反击台词克制有力（「这份方案，是我做的」）；旁白揭露职场潜规则。",
        "开篇钩子：第一镜屈辱瞬间——加班到深夜的办公室，领导把功劳全揽走，旁白「在职场，老实人不是没有底线，只是还没被逼到」。",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "dt_startup", "热血创业", "剧情", "🚀",
        "创业奋斗流：从一无所有到白手起家，励志燃向",
        "核心人设：主角=怀揣梦想的创业者（坚韧、敢拼）；伙伴=志同道合的朋友（各有特长）；对手=资本大佬/背叛者。关系：团队从零起步，共同面对失败与背叛。核心冲突：资金断裂/对手打压/内部背叛 → 绝地反击。",
        "四段式：①钩子开场（创业低谷：融资被拒/被扫地出门/破产边缘）；②坚持蓄力（小成功积累：拿下第一单、产品上线）；③大反转（对手打压或背叛 → 绝地反击拿下大单）；④展望收尾（公司上市/新征途，热血旁白收尾）。",
        "台词热血励志：创业口号落地（「我们没钱，但我们有脑子」）；伙伴台词重情义（「这条路我陪你走到底」）；旁白燃向收尾。",
        "开篇钩子：第一镜低谷瞬间——空荡荡的办公室、被投资人嘲讽出门，旁白「那年他 28 岁，口袋里只剩 200 块」。",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    return T


def init_drama_templates():
    """启动初始化：模板不存在才写盘（用户可自行编辑 JSON），返回全部模板。"""
    for t in _drama_templates():
        path = TEMPLATE_DIR / f"{t['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化短剧题材模板：{t['name']}")
    return load_all(TEMPLATE_DIR)






def get_template_prompt(tid: str) -> str:
    """题材模板 → 剧本提示词注入段（供 short_drama._generate_script 使用）。"""
    t = load_one(TEMPLATE_DIR, tid, '题材模板不存在')
    return (
        f"\n【题材模板：{t['name']}】\n"
        f"人设与关系：{t['setup']}\n"
        f"剧情结构：{t['structure']}\n"
        f"台词风格：{t['style']}\n"
        f"开篇钩子：{t['hook']}"
    )






@router.get("/list")
async def drama_templates_list(category: str = "", q: str = ""):
    """题材模板市场列表（分类/热度/定价）。"""
    items = []
    for t in load_all(TEMPLATE_DIR):
        pricing = t.get("pricing") or {}
        items.append({
            "id": t["id"],
            "name": t.get("name", "未命名"),
            "category": t.get("category", "通用"),
            "icon": t.get("icon", "🎬"),
            "desc": t.get("desc", ""),
            "pricing": pricing,
            "pricing_label": {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
            .get(pricing.get("mode", "free"), "免费"),
            "usage": get_usage(t["id"], 'drama_template_usage'),
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
async def drama_template_detail(tid: str):
    """题材模板详情（含完整编剧设定，前端展示）。"""
    t = load_one(TEMPLATE_DIR, tid, '题材模板不存在')
    pricing = t.get("pricing") or {}
    data = {k: t[k] for k in ("id", "name", "category", "icon", "desc", "setup",
                              "structure", "style", "hook", "pricing") if k in t}
    labels = {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
    data["category_label"] = data.get("category", "通用")
    data["pricing_label"] = labels.get(pricing.get("mode", "free"), "免费")
    data["usage"] = get_usage(tid, 'drama_template_usage')
    return data


# 启动初始化
init_drama_templates()
