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

MINDMAP_SYSTEM = """你是一个专业的思维导图设计师。请根据用户提供的主题，生成一个结构清晰、逻辑严谨的思维导图JSON树。要求：

1. 根节点是核心主题
2. 展开3-4个一级分支
3. 每个分支展开2-4个二级节点
4. 适当的二级节点下可以有三级细节
5. 每个节点用简洁中文命名（2-6字）
6. 为每个一级分支分配一个主题色

输出JSON格式：
{
  "title": "思维导图根主题",
  "description": "一句话概述这个导图的内容",
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
            {"name": "三级细节", "children": []},
            {"name": "三级细节2", "children": []}
          ]}
        ]
      }
    ]
  }
}

颜色选择美观的配色（hex格式）。只输出JSON，不要其他内容。"""

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


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    """删除思维导图记录。"""
    with get_db_context() as conn:
        conn.execute("DELETE FROM mindmap_records WHERE id=?", (record_id,))
    return {"message": "已删除"}
