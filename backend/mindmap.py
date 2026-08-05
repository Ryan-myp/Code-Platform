"""AI思维导图生成器 — 输入主题 → AI生成结构化思维导图。

- POST /api/mindmap/generate  生成思维导图
- GET  /api/mindmap/records   历史记录
- DELETE /api/mindmap/records/{id}
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mindmap", tags=["思维导图"])

# ── System Prompts ─────────────────────────────────────────

MINDMAP_SYSTEM = """你是一位资深知识架构师和思维导图设计专家，拥有10年以上信息可视化经验。

你的核心能力：
- 将复杂主题解构为逻辑清晰、层次分明的知识树
- 运用MECE原则（相互独立、完全穷尽）确保分支不重叠、不遗漏
- 根据风格要求灵活调整节点命名策略和展开深度

## 风格指导
根据用户指定的风格调整思维导图特征：

**professional（专业严谨）**：
- 分支按学科/方法论/流程阶段等逻辑维度展开
- 节点命名偏学术化、术语化（如"SWOT分析"而非"分析一下"）
- 层级结构严格，二级节点按重要性排序
- 配色：深蓝/藏青/灰色系，体现专业感

**creative（创意发散）**：
- 分支按灵感/场景/联想等非线性维度展开
- 节点命名有趣味性、画面感（如"爆款密码"而非"爆款因素"）
- 可包含跨界联想的节点（如"像Netflix一样做内容推荐"）
- 配色：亮橙/活力紫/渐变暖色，体现创意感

**educational（教学讲解）**：
- 分支按概念→原理→应用→案例的认知递进展开
- 节点命名清晰直白，新手友好（如"什么是XX"、"为什么要XX"）
- 每个概念节点下附简短解释性子节点
- 配色：绿色/蓝色系，体现知识感

**business（商业分析）**：
- 分支按市场/竞争/财务/执行等商业维度展开
- 节点命名偏商业术语（如"TAM分析"、"单位经济学"、"增长飞轮"）
- 关键指标作为二级节点（如"CAC<LTV"、"NPS>50"）
- 配色：深蓝/金色点缀，体现商业感

## 输出规范
1. 根节点是核心主题（精准概括，≤8字）
2. 展开3-5个一级分支（覆盖主题的主要维度）
3. 每个分支展开2-4个二级节点，关键分支可到三级
4. 节点命名：2-8字，简洁有力，避免冗长描述
5. 为每个一级分支分配符合风格的主题色（hex格式）
6. 每个一级分支的二级节点数量尽量均衡（2-4个）

## 配色参考
- professional: #1a365d, #2b6cb0, #3182ce, #63b3ed, #90cdf4
- creative: #e53e3e, #dd6b20, #d69e2e, #805ad5, #d53f8c
- educational: #276749, #2f855a, #38a169, #68d391, #9ae6b4
- business: #1a365d, #2d3748, #4a5568, #c59b27, #e2b93b

## 质量要求
- 一级分支之间无概念重叠（MECE原则）
- 每个一级分支下的内容有明确的区分度
- 层级深度不超过3层（避免过度嵌套导致阅读困难）
- description字段：一句话概括导图覆盖范围和适用场景

输出严格JSON格式：
{
  "title": "思维导图根主题",
  "description": "一句话概述这个导图的内容和适用场景",
  "root": {
    "name": "中心主题",
    "color": "#667eea",
    "children": [
      {
        "name": "一级分支",
        "color": "#4A90D9",
        "children": [
          {"name": "二级节点", "children": []},
          {"name": "二级节点2", "children": [
            {"name": "三级细节", "children": []}
          ]}
        ]
      }
    ]
  }
}

只输出JSON，不要任何其他文字。"""

# ── 模型 ──────────────────────────────────────────────────

class MindMapRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200, description="思维导图主题")
    depth: int = Field(3, ge=2, le=4, description="展开深度（2-4层）")
    style: str = Field("professional", description="风格：professional/creative/educational/business")


# ── 数据库初始化 ──────────────────────────────────────────

def init_db():
    with get_db_context() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mindmap_records (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                depth INTEGER,
                style TEXT,
                result TEXT,
                created_at TEXT NOT NULL
            )
        """)


init_db()

# ── API ──────────────────────────────────────────────────

@router.post("/generate")
async def generate_mindmap(req: MindMapRequest, current_user: dict = require_auth()):
    """生成思维导图：输入主题 → AI生成树形结构。"""
    start = datetime.now()

    user_prompt = f"主题：{req.topic}\n展开深度：{req.depth}层\n风格：{req.style}"

    try:
        raw = call_llm(MINDMAP_SYSTEM, user_prompt, max_tokens=2000, temperature=0.5, timeout=60)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"mindmap json parse failed, raw: {raw[:500]}")
        raise HTTPException(500, "思维导图生成结果格式异常，请重试")
    except Exception as e:
        logger.exception("mindmap generate failed")
        raise HTTPException(500, f"思维导图生成失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("mindmap_generate", len(req.topic), len(raw), elapsed)

    # 保存记录
    rid = f"mm_{int(datetime.now().timestamp()*1000)}"
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO mindmap_records (id, topic, depth, style, result, created_at) VALUES (?,?,?,?,?,?)",
            (rid, req.topic, req.depth, req.style, json.dumps(result, ensure_ascii=False), datetime.now().isoformat()),
        )

    return {
        "id": rid,
        "topic": req.topic,
        **result,
    }


@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    """获取历史思维导图记录。"""
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, topic, depth, style, created_at FROM mindmap_records ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    return [{"id": r[0], "topic": r[1], "depth": r[2], "style": r[3], "created_at": r[4]} for r in rows]


@router.get("/records/{record_id}")
async def get_record(record_id: str, current_user: dict = require_auth()):
    """获取单条思维导图详情（含完整树结构）。"""
    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM mindmap_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")

    result = json.loads(row[4]) if row[4] else {}
    return {
        "id": row[0],
        "topic": row[1],
        "depth": row[2],
        "style": row[3],
        "title": result.get("title"),
        "root": result.get("root"),
        "description": result.get("description"),
        "created_at": row[5],
    }


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    """删除思维导图记录。"""
    with get_db_context() as conn:
        conn.execute("DELETE FROM mindmap_records WHERE id=?", (record_id,))
    return {"message": "已删除"}
