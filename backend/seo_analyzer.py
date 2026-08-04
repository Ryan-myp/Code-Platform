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
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/seo", tags=["SEO优化"])

# ── System Prompts ─────────────────────────────────────────

SEO_ANALYZE_SYSTEM = """你是一位资深SEO优化专家。请对给定的内容进行SEO多维度评分和优化建议，输出JSON格式：

{
  "overall_score": 75,
  "grade": "B",
  "summary": "整体评价一句话",
  "dimensions": [
    {"name": "标题吸引力", "score": 80, "weight": 20, "comment": "标题包含关键词但缺少数字/悬念"},
    {"name": "关键词覆盖", "score": 75, "weight": 25, "comment": "核心关键词出现3次，但缺少LSI相关词"},
    {"name": "可读性", "score": 85, "weight": 15, "comment": "段落长度适中，Flesch可读性良好"},
    {"name": "结构化程度", "score": 70, "weight": 15, "comment": "缺少H2/H3子标题和列表"},
    {"name": "情感吸引力", "score": 80, "weight": 10, "comment": "语言生动但有优化空间"},
    {"name": "字数与深度", "score": 65, "weight": 15, "comment": "内容长度不足，难以覆盖长尾关键词"}
  ],
  "keyword_analysis": {
    "primary_keyword": "核心关键词",
    "density": "1.2%",
    "appears_in_title": true,
    "appears_in_first_100": true,
    "appears_in_h2": false
  },
  "improvements": [
    {"priority": "high|medium|low", "issue": "问题描述", "suggestion": "改进建议"}
  ],
  "optimized_title_suggestions": ["优化标题建议1", "优化标题建议2", "优化标题建议3"],
  "meta_description": "建议的meta描述（150字以内）"
}

评分维度：90+=A+优秀, 80-89=A良好, 70-79=B达标, 60-69=C需改进, <60=D较差
只输出JSON，不要其他内容。"""

KEYWORD_SYSTEM = """你是一位资深SEO关键词研究专家。根据输入的主题/种子词，进行关键词拓展研究，输出JSON格式：

{
  "seed_keyword": "原始种子词",
  "related_keywords": [
    {"keyword": "相关词", "search_volume": "高|中|低", "competition": "高|中|低", "relevance": 95}
  ],
  "long_tail_keywords": [
    {"keyword": "长尾词短语", "intent": "信息型|交易型|导航型|商业型", "difficulty": "低|中|高"}
  ],
  "question_keywords": [
    {"question": "用户会问的问题", "answer_brief": "简短回答建议"}
  ],
  "topic_clusters": [
    {"cluster": "主题簇名称", "keywords": ["词1", "词2"]}
  ],
  "content_suggestions": "内容策略建议（一句话）"
}

每个列表提供5-8项。search_volume和competition用中文高/中/低。
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


# ── API ──────────────────────────────────────────────────

@router.post("/analyze")
async def analyze_seo(req: SEOAnalyzeRequest, current_user: dict = require_auth()):
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
    except json.JSONDecodeError:
        raise HTTPException(500, "SEO分析结果格式异常")
    except Exception as e:
        logger.exception("seo analyze failed")
        raise HTTPException(500, f"SEO分析失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("seo_analyze", len(req.title) + len(req.content), len(raw), elapsed)

    return {
        "title": req.title,
        "content_length": len(req.content),
        **result,
    }


@router.post("/keywords")
async def research_keywords(req: KeywordResearchRequest, current_user: dict = require_auth()):
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
    except json.JSONDecodeError:
        raise HTTPException(500, "关键词研究结果格式异常")
    except Exception as e:
        logger.exception("keyword research failed")
        raise HTTPException(500, f"关键词研究失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("seo_keywords", len(req.seed_keyword), len(raw), elapsed)

    return {
        "seed_keyword": req.seed_keyword,
        **result,
    }
