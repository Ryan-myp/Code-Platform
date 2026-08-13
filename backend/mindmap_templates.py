# -*- coding: utf-8 -*-
"""思维导图模板库：按"经典思维模型"封装的专业导图结构（SWOT/OKR/金字塔/鱼骨等）。

每个模板 = 固定的一级/二级分支骨架 + 填充指引，注入 LLM 提示词后按结构展开，
保证输出是真正可用的专业模型而非自由发散。商业化 + 热度统计与其余模板库一致。
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "mindmap_templates"
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/mindmap-templates", tags=["思维导图模板"])
from common.template_utils import load_all, load_one, get_usage, record_usage



def _tpl(tid, name, category, icon, desc, style, depth, example_topic, structure, tips, pricing=None):
    """structure: [{"name": 一级分支, "hint": 分支说明, "children": [二级节点...]}]"""
    return {
        "id": tid, "name": name, "category": category, "icon": icon, "desc": desc,
        "style": style, "depth": depth, "example_topic": example_topic,
        "structure": structure, "pro_tips": tips,
        "pricing": pricing or {"mode": "free", "once": 0, "day": 0, "month": 0},
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }


def _mindmap_templates():
    T = []
    # ══ 战略管理 3 ══
    T.append(_tpl(
        "mmt_swot", "SWOT 分析", "战略管理", "⚖️",
        "经典企业/个人 SWOT 四象限：优势·劣势·机会·威胁，附带对策推演",
        "business", 3, "XX公司 2026 年度战略分析",
        [
            {"name": "优势 Strengths", "hint": "内部积极因素", "children": ["核心资源", "技术壁垒", "品牌资产", "成本优势"]},
            {"name": "劣势 Weaknesses", "hint": "内部消极因素", "children": ["资源短板", "流程瓶颈", "人才缺口", "规模限制"]},
            {"name": "机会 Opportunities", "hint": "外部利好环境", "children": ["市场增长", "政策红利", "技术变革", "竞争空窗"]},
            {"name": "威胁 Threats", "hint": "外部不利因素", "children": ["新进入者", "替代品", "客户议价", "政策风险"]},
        ],
        "每个象限按影响力排序；SWOT 后追加 SO/WT 对策分支更专业",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "mmt_okr", "OKR 目标对齐", "战略管理", "🎯",
        "目标与关键结果：O→KR→执行计划三级联动，对齐公司/团队/个人",
        "professional", 3, "2026 年 Q3 增长目标",
        [
            {"name": "公司目标 O1", "hint": "定性目标", "children": ["关键结果 KR1", "关键结果 KR2", "关键结果 KR3"]},
            {"name": "团队目标 O2", "hint": "承接拆解", "children": ["关键结果 KR1", "关键结果 KR2"]},
            {"name": "个人目标 O3", "hint": "具体到人", "children": ["关键结果 KR1", "关键结果 KR2"]},
            {"name": "执行计划", "hint": "落地动作", "children": ["里程碑", "负责人", "资源需求"]},
        ],
        "每个 KR 必须可量化（含数字指标）；O 是方向、KR 是结果、计划是动作，三层不可混淆",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "mmt_pest", "PEST 宏观分析", "战略管理", "🌐",
        "宏观环境扫描：政治·经济·社会·技术四维，辅助市场进入决策",
        "business", 3, "新能源汽车行业 PEST 分析",
        [
            {"name": "政治 Political", "hint": "政策法规", "children": ["产业政策", "税收优惠", "监管环境", "国际关系"]},
            {"name": "经济 Economic", "hint": "宏观经济", "children": ["GDP 增速", "利率汇率", "消费力", "产业链成本"]},
            {"name": "社会 Social", "hint": "社会文化", "children": ["人口结构", "消费习惯", "环保意识", "城镇化"]},
            {"name": "技术 Technological", "hint": "技术演进", "children": ["技术成熟度", "研发投入", "专利格局", "颠覆性技术"]},
        ],
        "每个维度聚焦与主题强相关的 3-4 个要素，避免泛泛而谈",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 工作方法 4 ══
    T.append(_tpl(
        "mmt_pyramid", "金字塔原理", "工作方法", "🔺",
        "麦肯锡结构化表达：结论先行→论点支撑→论据展开",
        "professional", 3, "XX产品年度汇报",
        [
            {"name": "核心结论", "hint": "一句话结论", "children": ["结论一", "结论二", "结论三"]},
            {"name": "论点支撑", "hint": "支撑结论的理由", "children": ["论据 A", "论据 B", "论据 C"]},
            {"name": "事实依据", "hint": "数据/案例", "children": ["数据指标", "客户案例", "行业对标"]},
            {"name": "行动建议", "hint": "下一步", "children": ["短期动作", "中期规划", "长期目标"]},
        ],
        "结论先行是核心：上级节点必须是下级的总结概括（MECE 互斥穷尽）",
        {"mode": "once", "once": 5, "day": 2, "month": 19},
    ))
    T.append(_tpl(
        "mmt_fishbone", "鱼骨图因果分析", "工作方法", "🐟",
        "石川图：从人机料法环测六维定位问题根因",
        "creative", 3, "订单交付延迟原因分析",
        [
            {"name": "人员 Man", "hint": "人的因素", "children": ["技能不足", "排班问题", "沟通不畅"]},
            {"name": "机器 Machine", "hint": "设备因素", "children": ["设备故障", "产能瓶颈", "维护缺失"]},
            {"name": "物料 Material", "hint": "供应因素", "children": ["到料延迟", "质量问题", "库存不足"]},
            {"name": "方法 Method", "hint": "流程因素", "children": ["流程繁琐", "标准缺失", "审批链长"]},
            {"name": "环境 Environment", "hint": "外部因素", "children": ["突发状况", "季节波动", "政策变化"]},
            {"name": "测量 Measurement", "hint": "度量因素", "children": ["指标失真", "数据缺失", "口径不一"]},
        ],
        "先发散穷举原因，再收敛到 2-3 个根因；每个原因分支给出对策建议",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "mmt_retro", "项目复盘", "工作方法", "🔄",
        "GRAI 复盘四步法：目标回顾→结果评估→原因分析→规律沉淀",
        "professional", 3, "Q2 重点项目复盘",
        [
            {"name": "目标回顾", "hint": "原定目标", "children": ["业务目标", "质量目标", "时间目标"]},
            {"name": "结果评估", "hint": "实际达成", "children": ["达标项", "差距项", "亮点项"]},
            {"name": "原因分析", "hint": "成败根因", "children": ["成功原因", "失败原因", "外部因素"]},
            {"name": "规律沉淀", "hint": "可复用经验", "children": ["流程改进", "方法固化", "风险预案"]},
            {"name": "行动清单", "hint": "落地安排", "children": ["责任人", "完成时间", "验收标准"]},
        ],
        "复盘重在归因与沉淀：每个结论都必须落到行动清单，避免复盘完就结束",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "mmt_plan", "项目规划", "工作方法", "🗂️",
        "项目全景规划：目标→里程碑→任务→风险→资源五维拆解",
        "professional", 3, "XX系统上线规划",
        [
            {"name": "项目目标", "hint": "成功定义", "children": ["业务目标", "交付范围", "验收标准"]},
            {"name": "里程碑", "hint": "阶段节点", "children": ["启动", "设计", "开发", "测试", "上线"]},
            {"name": "任务拆解", "hint": "WBS 分解", "children": ["工作包", "依赖关系", "估算工时"]},
            {"name": "风险预案", "hint": "风险应对", "children": ["进度风险", "质量风险", "人员风险"]},
            {"name": "资源计划", "hint": "资源安排", "children": ["人力", "预算", "工具"]},
        ],
        "里程碑用时间倒排；每个任务必须有唯一负责人（RACI 思想）",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    # ══ 学习成长 3 ══
    T.append(_tpl(
        "mmt_reading", "读书笔记", "学习成长", "📖",
        "深度阅读笔记：全书框架→核心观点→概念摘录→行动转化",
        "educational", 3, "《原则》读书笔记",
        [
            {"name": "全书框架", "hint": "作者结构", "children": ["核心思想", "章节脉络", "论证主线"]},
            {"name": "核心观点", "hint": "关键主张", "children": ["观点一", "观点二", "观点三"]},
            {"name": "概念摘录", "hint": "金句/定义", "children": ["重要概念", "金句摘抄", "案例故事"]},
            {"name": "批判思考", "hint": "独立评价", "children": ["认同之处", "存疑之处", "补充视角"]},
            {"name": "行动转化", "hint": "读完做什么", "children": ["立即行动", "长期习惯", "分享输出"]},
        ],
        "读书笔记的价值在于转化：行动分支必须有具体、可执行的动作",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "mmt_learn", "学习路径规划", "学习成长", "🧭",
        "从零学会一门技能：目标→知识地图→学习计划→实践检验",
        "educational", 3, "三个月学会数据分析",
        [
            {"name": "学习目标", "hint": "能力标准", "children": ["知识目标", "技能目标", "作品目标"]},
            {"name": "知识地图", "hint": "知识体系", "children": ["基础理论", "核心工具", "进阶专题"]},
            {"name": "学习计划", "hint": "分阶段", "children": ["阶段一 入门", "阶段二 进阶", "阶段三 实战"]},
            {"name": "资源清单", "hint": "学习材料", "children": ["课程", "书籍", "练习平台"]},
            {"name": "实践检验", "hint": "输出验证", "children": ["项目实战", "作品集", "考试认证"]},
        ],
        "每个阶段设置可验收的产出物（作品/项目），避免学而不练",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    T.append(_tpl(
        "mmt_brainstorm", "头脑风暴", "学习成长", "💡",
        "创意发散结构化：问题定义→自由联想→筛选收敛→行动计划",
        "creative", 3, "新产品创意头脑风暴",
        [
            {"name": "问题定义", "hint": "明确议题", "children": ["背景", "目标用户", "约束条件"]},
            {"name": "自由联想", "hint": "不做评判", "children": ["天马行空", "跨界借鉴", "逆向思考"]},
            {"name": "创意整理", "hint": "归类提炼", "children": ["可行性分类", "潜力排序", "组合创新"]},
            {"name": "筛选收敛", "hint": "评估选优", "children": ["成本评估", "价值评估", "风险提示"]},
            {"name": "行动计划", "hint": "落地验证", "children": ["原型方案", "验证步骤", "时间节点"]},
        ],
        "联想阶段禁止评判（延迟批判）；筛选阶段用成本/价值二维矩阵排序",
        {"mode": "free", "once": 0, "day": 0, "month": 0},
    ))
    return T


def init_mindmap_templates():
    """启动初始化：模板不存在才写盘（用户可编辑 JSON）。"""
    for t in _mindmap_templates():
        path = TEMPLATE_DIR / f"{t['id']}.json"
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(t, f, ensure_ascii=False, indent=2)
            logger.info(f"初始化思维导图模板：{t['name']}")
    return load_all(TEMPLATE_DIR)










def build_structure_prompt(tpl: dict) -> str:
    """把模板结构拼成注入提示词（思维导图 worker 使用）。"""
    lines = ["\n【模板结构：%s】请严格按以下分支骨架展开，可细化但不可合并分支：" % tpl.get("name", "")]
    for b in tpl.get("structure", []):
        lines.append(f"- {b['name']}（{b.get('hint', '')}）：" + "、".join(b.get("children", [])))
    return "\n".join(lines)


@router.get("/list")
async def mindmap_templates_list(category: str = "", q: str = ""):
    """思维导图模板市场列表（分类/热度/定价/结构预览）。"""
    items = []
    for t in load_all(TEMPLATE_DIR):
        pricing = t.get("pricing") or {}
        items.append({
            "id": t["id"],
            "name": t.get("name", "未命名"),
            "category": t.get("category", "通用"),
            "icon": t.get("icon", "🧠"),
            "desc": t.get("desc", ""),
            "style": t.get("style", "professional"),
            "depth": t.get("depth", 3),
            "example_topic": t.get("example_topic", ""),
            "branches": [b.get("name") for b in t.get("structure", [])],
            "pro_tips": t.get("pro_tips", ""),
            "pricing": pricing,
            "pricing_label": {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
            .get(pricing.get("mode", "free"), "免费"),
            "usage": get_usage(t["id"], 'mindmap_template_usage'),
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
async def mindmap_template_detail(tid: str):
    """思维导图模板详情（完整分支结构，供结构预览与一键填充）。"""
    t = load_one(TEMPLATE_DIR, tid, '思维导图模板不存在')
    pricing = t.get("pricing") or {}
    data = {k: t[k] for k in ("id", "name", "category", "icon", "desc", "style", "depth",
                              "example_topic", "structure", "pro_tips", "pricing") if k in t}
    labels = {"free": "免费", "once": "按次", "day": "按天", "month": "按月"}
    data["category_label"] = data.get("category", "通用")
    data["pricing_label"] = labels.get(pricing.get("mode", "free"), "免费")
    data["usage"] = get_usage(tid, 'mindmap_template_usage')
    return data


# 启动初始化
init_mindmap_templates()
