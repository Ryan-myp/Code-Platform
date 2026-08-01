"""Agent 模板扩展模块 — 存根实现"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/agent-templates")
async def list_templates():
    return []
