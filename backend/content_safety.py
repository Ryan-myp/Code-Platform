#!/usr/bin/env python3
"""内容质量层（商业化发布 v14 核心）。

生产级内容保障三要素，供 6 个工厂（meme/music/image/video/game/miniapp）
在生成入口统一接入：

1. ``check_text``：文本安全审核——违规词库分类匹配（政治敏感/色情低俗/暴力血腥/
   违禁品/诈骗赌博/辱骂歧视），命中高风险直接拒绝生成（避免产出违规内容被平台驳回/封号）
2. ``quality_check_image``：图像美观度自检——分辨率/清晰度（Laplacian 方差）/
   对比度（颜色方差）/色偏（RGB 均值差），输出 0-100 评分与优化建议
3. ``quality_report``：生成"质量自检报告.md"，随发布包附带（审核结果+美观度+规格合规）

局限说明：图像/音频的深度 NSFW 检测需专用模型，本层以文本审核 + 基础图像
质量自检为主，报告中对未覆盖项明确标注，供创作者人工复核。
"""

from __future__ import annotations

import logging
from datetime import datetime

import numpy as np
from PIL import Image, ImageFilter, ImageStat

logger = logging.getLogger(__name__)

# 高危：命中即拒绝生成（平台审核红线）
HIGH_RISK_WORDS = [
    # 政治敏感
    "法轮功", "法轮大法", "台独", "藏独", "疆独", "港独", "六四", "天安门事件", "打倒", "推翻政府", "颠覆国家",
    # 色情低俗
    "裸体", "裸照", "色情", "淫秽", "嫖娼", "卖淫", "援交", "约炮", "三级片", "情色", "露点", "艳照", "性交", "口交", "做爱", "肛交",
    # 暴力血腥
    "杀人", "分尸", "碎尸", "肢解", "血腥", "砍头", "斩首", "恐怖袭击", "自杀方法", "跳楼自杀", "割腕", "枪杀",
    # 违禁品
    "冰毒", "海洛因", "大麻", "摇头丸", "可卡因", "鸦片", "罂粟", "枪支", "子弹", "炸药", "炸弹制作", "管制刀具", "假钞", "伪造证件",
    # 诈骗赌博
    "赌博", "赌场", "博彩", "六合彩", "洗钱", "诈骗", "电信诈骗", "高利贷", "传销", "裸贷", "庞氏骗局", "杀猪盘",
    # 辱骂歧视
    "傻逼", "傻b", "操你妈", "草泥马", "去死吧", "废物垃圾", "婊子", "贱人", "黑鬼", "支那", "种族歧视",
]

# 中危：命中提示整改（可在 strict=False 时仅警告）
MEDIUM_RISK_WORDS = [
    "赌博", "酒精", "香烟", "吸烟", "喝酒", "暴力", "打架", "抽烟",
]

_CONTEXT_HINTS = {
    "歌词": "请调整歌词措辞，替换或删减相关表述后再生成",
    "文案": "请修改文案，删除敏感表述后重试",
    "表情包": "表情包文字需通过平台内容审核，请改用中性、友善的表达",
    "prompt": "请修改生成描述，避免敏感内容",
}


def check_text(text: str, context: str = "") -> dict:
    """文本安全审核：命中高危词返回 ok=False（拒绝生成），中危返回警告。

    返回：``{"ok", "risk": high|medium|none, "categories", "risk_words", "suggestion"}``
    """
    text = (text or "").strip()
    categories: list[str] = []
    high_hits: list[str] = []
    medium_hits: list[str] = []
    if text:
        low = text.lower()
        for cat, words in _CATEGORY_OF.items():
            hits = [w for w in words if w in low]
            if hits:
                categories.append(cat)
                high_hits.extend(hits)
        medium_hits = [w for w in MEDIUM_RISK_WORDS if w in low and w not in high_hits]

    if high_hits:
        hint = _CONTEXT_HINTS.get(context or "", _CONTEXT_HINTS["文案"])
        return {
            "ok": False,
            "risk": "high",
            "categories": list(dict.fromkeys(categories)),
            "risk_words": high_hits,
            "suggestion": f"检测到敏感内容（{'、'.join(high_hits[:5])}）。{hint}",
        }
    if medium_hits:
        return {
            "ok": True,
            "risk": "medium",
            "categories": ["敏感表述"],
            "risk_words": medium_hits,
            "suggestion": f"检测到敏感表述（{'、'.join(medium_hits[:5])}），建议替换后再发布",
        }
    return {"ok": True, "risk": "none", "categories": [], "risk_words": [], "suggestion": ""}


# 分类词库：category → 词表（与 HIGH_RISK_WORDS 同源，仅用于报告分类）
_CATEGORY_OF: dict[str, list[str]] = {
    "政治敏感": ["法轮功", "法轮大法", "台独", "藏独", "疆独", "港独", "六四", "天安门事件", "打倒", "推翻政府", "颠覆国家"],
    "色情低俗": ["裸体", "裸照", "色情", "淫秽", "嫖娼", "卖淫", "援交", "约炮", "三级片", "情色", "露点", "艳照", "性交", "口交", "做爱", "肛交"],
    "暴力血腥": ["杀人", "分尸", "碎尸", "肢解", "血腥", "砍头", "斩首", "恐怖袭击", "自杀方法", "跳楼自杀", "割腕", "枪杀"],
    "违禁品": ["冰毒", "海洛因", "大麻", "摇头丸", "可卡因", "鸦片", "罂粟", "枪支", "子弹", "炸药", "炸弹制作", "管制刀具", "假钞", "伪造证件"],
    "诈骗赌博": ["赌博", "赌场", "博彩", "六合彩", "洗钱", "诈骗", "电信诈骗", "高利贷", "传销", "裸贷", "庞氏骗局", "杀猪盘"],
    "辱骂歧视": ["傻逼", "傻b", "操你妈", "草泥马", "去死吧", "废物垃圾", "婊子", "贱人", "黑鬼", "支那", "种族歧视"],
}



def _check_resolution(img: Image.Image, checks: list, suggestions: list) -> int:
    """分辨率检查（30 分）。"""
    w, h = img.size
    min_side = min(w, h)
    score = 30 if min_side >= 1080 else (22 if min_side >= 720 else (12 if min_side >= 480 else 5))
    if min_side < 720:
        suggestions.append(f"分辨率偏低（{w}×{h}），建议 ≥1080px 以获得平台高清展示")
    checks.append({"name": "分辨率", "ok": min_side >= 720, "score": score, "detail": f"{w}×{h}"})
    return score


def _check_clarity(img: Image.Image, checks: list, suggestions: list) -> int:
    """清晰度检查（30 分，Laplacian 方差）。"""
    try:
        w, h = img.size
        gray = img.convert("L").resize((min(w, 320), min(h, 320)))
        lap = np.array(gray.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        if lap.size > 9:
            lap = lap[1:-1, 1:-1]
        lap_var = float(lap.var())
        clarity = 30 if lap_var >= 100 else (20 if lap_var >= 40 else (10 if lap_var >= 12 else 4))
        if lap_var < 40:
            suggestions.append("画面偏模糊，建议使用高清源图或放大后再导出")
        checks.append({"name": "清晰度", "ok": lap_var >= 40, "score": clarity, "detail": f"边缘方差 {lap_var:.1f}"})
    except Exception:
        clarity = 20
        checks.append({"name": "清晰度", "ok": True, "score": clarity, "detail": "检测跳过"})
    return clarity


def _check_contrast(img: Image.Image, checks: list, suggestions: list) -> int:
    """对比度检查（20 分，颜色方差）。"""
    try:
        stat = ImageStat.Stat(img.convert("RGB").resize((128, 128)))
        var = sum(stat.var) / 3.0
        contrast = 20 if var >= 600 else (13 if var >= 250 else 6)
        if var < 250:
            suggestions.append("色彩对比度不足（画面偏平），建议提升明暗层次或更换底色")
        checks.append({"name": "对比度", "ok": var >= 250, "score": contrast, "detail": f"颜色方差 {var:.0f}"})
    except Exception:
        contrast = 13
        checks.append({"name": "对比度", "ok": True, "score": contrast, "detail": "检测跳过"})
    return contrast


def _check_color_drift(img: Image.Image, checks: list, suggestions: list) -> int:
    """色偏检查（20 分，RGB 通道均值差）。"""
    try:
        stat = ImageStat.Stat(img.convert("RGB").resize((128, 128)))
        means = list(stat.mean)
        drift = max(means) - min(means)
        color = 20 if drift <= 40 else (13 if drift <= 80 else 6)
        if drift > 80:
            suggestions.append("存在明显色偏，建议检查白平衡或滤镜")
        checks.append({"name": "色偏", "ok": drift <= 80, "score": color, "detail": f"通道偏差 {drift:.0f}"})
    except Exception:
        color = 13
        checks.append({"name": "色偏", "ok": True, "score": color, "detail": "检测跳过"})
    return color

def quality_check_image(img: Image.Image) -> dict:
    """图像美观度自检：分辨率/清晰度/对比度/色偏 → 0-100 分与建议。

    返回：``{"score", "grade": A|B|C, "checks": [{name, ok, score, detail}], "suggestions"}``
    """
    if img is None:
        return {"score": 0, "grade": "C", "checks": [], "suggestions": ["图像无效"]}
    checks: list[dict] = []
    suggestions: list[str] = []
    total = 0

    total += _check_resolution(img, checks, suggestions)
    total += _check_clarity(img, checks, suggestions)
    total += _check_contrast(img, checks, suggestions)
    total += _check_color_drift(img, checks, suggestions)

    grade = "A" if total >= 85 else ("B" if total >= 65 else "C")
    return {"score": total, "grade": grade, "checks": checks, "suggestions": suggestions}


def quality_report(product: str, text_check: dict | None = None, image_quality: dict | None = None, extra: list[str] | None = None) -> str:
    """生成"质量自检报告.md"文本（随发布包附带）。"""
    lines = [
        f"# {product} 质量自检报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- 说明：本报告由 AI 创作工坊自动生成，供发布前人工复核参考",
        "",
    ]
    lines.append("## 一、内容安全审核")
    if text_check is None:
        lines.append("- 未执行文本审核（本产物不涉及用户文本）")
    elif text_check.get("ok"):
        lines.append(f"- 结果：通过（{text_check.get('risk', 'none')} 风险）")
        if text_check.get("risk_words"):
            lines.append(f"- 提示：含敏感表述 {'、'.join(text_check['risk_words'][:5])}，建议发布前确认")
    else:
        lines.append("- 结果：**未通过**，请修改后重新生成")
        lines.append(f"- 命中类别：{'、'.join(text_check.get('categories', []) or ['未知'])}")
        lines.append(f"- 命中词：{'、'.join(text_check.get('risk_words', [])[:10])}")
        lines.append(f"- 建议：{text_check.get('suggestion', '')}")
    lines.append("")

    lines.append("## 二、图像美观度自检")
    if image_quality is None:
        lines.append("- 本产物不涉及图像（或图像检测跳过）")
    else:
        lines.append(f"- 综合评分：**{image_quality.get('score', 0)}/100（{image_quality.get('grade', 'C')} 级）**")
        for c in image_quality.get("checks", []):
            mark = "✓" if c.get("ok") else "✗"
            lines.append(f"- {mark} {c.get('name', '')}：{c.get('detail', '')}（{c.get('score', 0)} 分）")
        for s in image_quality.get("suggestions", []):
            lines.append(f"- 建议：{s}")
    lines.append("")

    if extra:
        lines.append("## 三、其他检查项")
        for e in extra:
            lines.append(f"- {e}")
        lines.append("")

    lines.append(
        "## 局限说明\n"
        "- 本工具基于规则词库与基础图像指标，深度违规内容（如图像裸体、音频涉政）"
        "需平台审核兜底；发布前请人工复核一遍，遵守目标平台内容规范。"
    )
    return "\n".join(lines)
