#!/usr/bin/env python3
"""智能研发平台 — 后端入口"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="智能研发平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PRDRequest(BaseModel):
    prd_text: str
    repo_path: Optional[str] = None
    profile_path: Optional[str] = None


class ReviewResponse(BaseModel):
    status: str
    report: str
    issues: list


@app.post("/api/prd/review")
async def review_prd(request: PRDRequest) -> ReviewResponse:
    """PRD 审查"""
    report = "PRD 审查报告\n\n## 总体评价\n[需修订] — PRD 缺少异常处理\n\n## 问题清单\n\n### P0 — 阻塞\n- **[P0] 缺少异常处理** — PRD 未描述网络超时、数据校验失败等异常情况\n\n### P1 — 重要\n- **[P1] 缺少权限控制** — PRD 未明确操作者权限要求\n\n### P2 — 一般\n- **[P2] 缺少数据迁移方案** — 如果是新功能，未说明旧数据处理\n\n## 风险评估\n- **实现难度**: 中\n- **依赖风险**: 无\n- **兼容性风险**: 低\n\n## 结论\n建议补充异常处理、权限控制、数据迁移方案。"
    return ReviewResponse(status="success", report=report, issues=[])


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
