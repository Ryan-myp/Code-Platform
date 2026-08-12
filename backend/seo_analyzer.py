"""SEO关键词研究 + 内容评分 — 多维度打分 + 关键词推荐。

- POST /api/seo/analyze   内容SEO综合评分
- POST /api/seo/keywords  关键词研究（相关词/长尾词/问题型关键词）
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.llm import call_llm, log_usage, _safe_exc_msg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["SEO优化"])

# ── System Prompts ─────────────────────────────────────────

SEO_ANALYZE_SYSTEM = """你是一位拥有10年+经验的资深SEO策略顾问，精通百度/谷歌/搜狗等主流搜索引擎算法，擅长基于数据的内容优化与排名提升。

## 分析框架
对给定内容进行8维度深度SEO诊断，每个维度基于具体证据打分：

### 评分维度（满分100，权重按重要性分配）
1. **标题吸引力**（权重15）：是否包含关键词、数字/数据、悬念/痛点、长度控制（百度PC≤30字/移动≤24字）
2. **关键词覆盖**（权重20）：核心词密度（2-5%最优）、LSI相关词覆盖度、TF-IDF权重分布合理性
3. **内容深度**（权重18）：是否覆盖用户所有潜在疑问、是否有独特观点/独家数据、原创性评估
4. **可读性**（权重12）：段落长度（≤5行手机屏）、句式复杂度、Flesch可读性、图文比例
5. **结构化程度**（权重12）：H1-H3层级完整度、列表/表格使用率、首段概括质量
6. **EEAT信号**（权重10）：专业性(Expertise)、经验性(Experience)、权威性(Authoritativeness)、可信度(Trustworthiness)
7. **内链/CTA**（权重8）：相关文章推荐、行动号召明确度、转化路径清晰度
8. **移动端适配**（权重5）：短段落扫读友好、首屏关键信息呈现、加载速度考量

## 等级标准
- 90+ ═ A+ 卓越（搜索结果第1页前3名水平）
- 80-89 ═ A 优秀（第1页水平）
- 70-79 ═ B 良好（第2页水平，有优化空间）
- 60-69 ═ C 一般（需大幅改进）
- <60 ═ D 较差（建议重写）

## 输出要求
- 每个评分维度必须有具体证据支撑（引用原文具体内容或说明缺失什么）
- improvements至少3条，priority标注准确（high=影响排名/流量，medium=有明显影响，low=锦上添花）
- optimized_title_suggestions提供3种不同策略（SEO导向/点击率导向/品牌导向）
- meta_description必须包含：核心关键词 + 独特价值主张 + 行动号召，控制在150字以内

输出严格JSON：
{
  "overall_score": 75,
  "grade": "B",
  "summary": "整体评价一句话（含排名潜力预估）",
  "dimensions": [
    {"name": "标题吸引力", "score": 80, "weight": 15, "evidence": "原文标题为'XX'，包含关键词但...", "comment": "评分依据简述"}
  ],
  "keyword_analysis": {
    "primary_keyword": "核心关键词",
    "density": "1.2%",
    "appears_in_title": true,
    "appears_in_first_100": true,
    "appears_in_h2": false,
    "lsi_keywords_found": ["已覆盖的相关词"],
    "lsi_keywords_missing": ["建议补充的相关词"]
  },
  "improvements": [
    {"priority": "high|medium|low", "issue": "问题描述", "impact": "对排名/点击率/转化的预期影响", "suggestion": "具体可执行的改进方案"}
  ],
  "optimized_title_suggestions": ["SEO导向标题", "点击率导向标题", "品牌导向标题"],
  "meta_description": "含关键词+价值主张+CTA的meta描述（≤150字）"
}

只输出JSON，不要其他内容。"""

KEYWORD_SYSTEM = """你是一位拥有20年+经验的资深SEO关键词策略顾问，服务过 500+ 企业站与内容站的搜索增长，精通百度关键词规划师、5118、Ahrefs、SEMrush 等工具的分析方法，擅长从种子词出发构建完整的关键词矩阵。

## 研究框架
基于用户输入的种子词和行业信息，进行4层关键词拓展：

### 1. 相关关键词（related_keywords）
- 与种子词语义相近或属于同一话题域的词汇
- 标注搜索量级（高>10000/月，中1000-10000，低<1000）
- 标注竞争度（高=头部站点密集/付费竞价激烈，中=可优化争取，低=蓝海机会）
- relevance表示与种子词的相关度（95=高度相关，80=中等相关）

### 2. 长尾关键词（long_tail_keywords）
- 3个词以上的搜索短语，意图明确
- intent分类：信息型（获取知识）、交易型（购买意图）、导航型（找特定网站）、商业型（比价研究）
- difficulty标注优化难度（低=新站可做，中=需一定权重，高=需高权威站点）

### 3. 问题型关键词（question_keywords）
- 用户在搜索引擎中会以问句形式搜索的内容
- 覆盖"是什么/为什么/怎么样/多少钱/哪个好"5种问句类型
- answer_brief给出30字内的核心回答要点

### 4. 主题簇（topic_clusters）
- 将相关关键词归类为主题簇，用于内容 pillar-cluster 策略
- 每个cluster包含3-5个紧密相关的关键词

## 输出要求
- 每个列表提供6-8项（丰富度直接影响实用价值）
- search_volume/competition/difficulty用中文：高/中/低
- 关键词本身用用户指定的语言（zh/en）
- content_suggestions给出具体内容策略方向（如"围绕'XX vs XX'对比类文章建立流量入口"）

输出严格JSON：
{
  "seed_keyword": "原始种子词",
  "related_keywords": [
    {"keyword": "相关词", "search_volume": "高|中|低", "competition": "高|中|低", "relevance": 95}
  ],
  "long_tail_keywords": [
    {"keyword": "长尾词短语", "intent": "信息型|交易型|导航型|商业型", "difficulty": "低|中|高"}
  ],
  "question_keywords": [
    {"question": "用户会搜索的问题", "question_type": "是什么|为什么|怎么样|多少钱|哪个好", "answer_brief": "核心回答要点"}
  ],
  "topic_clusters": [
    {"cluster": "主题簇名称", "keywords": ["词1", "词2"]}
  ],
  "content_suggestions": "基于关键词矩阵的内容策略建议"
}

只输出JSON，不要其他内容。"""


# ── 模型 ──────────────────────────────────────────────────


class SEOAnalyzeRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=300, description="文章标题")
    content: str = Field(..., min_length=50, max_length=10000, description="文章正文")
    target_keyword: str = Field("", max_length=100, description="目标关键词（可选，不填则AI自动识别）")


class KeywordResearchRequest(BaseModel):
    seed_keyword: str = Field(..., min_length=1, max_length=200, description="种子词/主题")
    industry: str = Field("", max_length=100, description="行业/领域（可选）")
    language: str = Field("zh", max_length=10, description="语言：zh/en")


# ── 优先级矩阵（v15：确定性计算，关键词分组 + 难度分级 + 执行优先级）──

_COMPETITION_SCORE = {"高": 1, "中": 2, "低": 3}
_DIFFICULTY_SCORE = {"高": 1, "中": 2, "低": 3}
_PRIORITY_ACTIONS = {
    "P1": "立即行动：优先创作并优化该关键词内容（高相关 + 低竞争）",
    "P2": "规划执行：纳入内容规划，两周内产出内容",
    "P3": "长期布局：结合长尾词持续覆盖，等待权重提升后主攻",
}


def _priority_level(score: int) -> str:
    """总分 8-9 → P1（速赢），6-7 → P2（规划），3-5 → P3（观察）。"""
    if score >= 8:
        return "P1"
    if score >= 6:
        return "P2"
    return "P3"


def build_priority_matrix(keyword_data: dict, limit: int = 10) -> list[dict]:
    """从关键词研究结果构建优先级矩阵（确定性规则，不依赖 LLM 输出格式）。

    评分 = 相关度分 + 竞争度分 + 难度分（每项 1-3 分，总分 3-9）：
    - relevance ≥90 → 3，80-89 → 2，<80 → 1
    - competition 低/中/高 → 3/2/1
    - difficulty 低/中/高 → 3/2/1（长尾词有，相关词缺省按 2）
    返回按总分降序的 top N 矩阵条目。
    """
    keyword_data = keyword_data or {}
    matrix = []
    seen = set()

    def _add(keyword: str, relevance: int, competition: str, difficulty: str) -> None:
        key = keyword.strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        rel_score = 3 if relevance >= 90 else 2 if relevance >= 80 else 1
        comp_score = _COMPETITION_SCORE.get(competition, 2)
        diff_score = _DIFFICULTY_SCORE.get(difficulty, 2)
        total = rel_score + comp_score + diff_score
        if relevance < 80:
            total = min(total, 5)  # 相关度不足时封顶 P3，避免低相关+低竞争误判为速赢项
        matrix.append(
            {
                "keyword": keyword.strip(),
                "relevance": relevance,
                "competition": competition or "-",
                "difficulty": difficulty or "-",
                "score": total,
                "priority": _priority_level(total),
                "action": _PRIORITY_ACTIONS[_priority_level(total)],
            }
        )

    for k in keyword_data.get("related_keywords", []) or []:
        _add(
            k.get("keyword", ""),
            int(k.get("relevance", 0) or 0),
            k.get("competition", ""),
            "",  # 相关词无难度字段，缺省按 2 分
        )
    for k in keyword_data.get("long_tail_keywords", []) or []:
        _add(
            k.get("keyword", ""),
            75,  # 长尾词无相关度字段，缺省按 75（2 分）
            "",  # 长尾词无竞争度字段，缺省按 2 分
            k.get("difficulty", ""),
        )

    matrix.sort(key=lambda m: (-m["score"], m["priority"]))
    return matrix[:limit]


# ── API ──────────────────────────────────────────────────


@router.post("/analyze")
def analyze_seo(req: SEOAnalyzeRequest, current_user: dict = require_auth()):
    """内容SEO多维度评分：标题吸引力、关键词覆盖、可读性、结构化、情感、字数。"""
    start = datetime.now()

    user_prompt = f"标题：{req.title}\n\n正文：\n{req.content[:5000]}"
    if req.target_keyword:
        user_prompt += f"\n\n目标关键词：{req.target_keyword}"

    try:
        raw = call_llm(SEO_ANALYZE_SYSTEM, user_prompt, max_tokens=2000, temperature=0.3, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(500, "SEO分析结果格式异常") from e
    except Exception as e:
        logger.exception("seo analyze failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("seo_analyze", len(req.title) + len(req.content), len(raw), elapsed)

    return {
        "title": req.title,
        "content_length": len(req.content),
        **result,
    }


@router.post("/keywords")
def research_keywords(req: KeywordResearchRequest, current_user: dict = require_auth()):
    """关键词研究：相关词、长尾词、问题型关键词、主题簇。"""
    start = datetime.now()

    user_prompt = f"种子词：{req.seed_keyword}"
    if req.industry:
        user_prompt += f"\n行业/领域：{req.industry}"
    if req.language != "zh":
        user_prompt += f"\n请用{req.language}语言返回结果"

    try:
        raw = call_llm(KEYWORD_SYSTEM, user_prompt, max_tokens=2000, temperature=0.5, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(500, "关键词研究结果格式异常") from e
    except Exception as e:
        logger.exception("keyword research failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("seo_keywords", len(req.seed_keyword), len(raw), elapsed)

    # v15：优先级矩阵（关键词分组 + 难度分级 + 执行优先级，后端确定性计算兜底）
    result["priority_matrix"] = build_priority_matrix(result)

    return {
        "seed_keyword": req.seed_keyword,
        **result,
    }
