#!/usr/bin/env python3
"""智能研发平台 — 后端入口"""

import sys
from pathlib import Path

# 添加 biz-delivery 到 path
biz_delivery_path = Path('/Users/yanping.ma/biz-delivery/scripts')
sys.path.insert(0, str(biz_delivery_path))

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
    try:
        # TODO: 调用 biz-delivery review_engine
        report = "PRD 审查报告

## 总体评价
[需修订] — PRD 缺少异常处理

## 问题清单

### P0 — 阻塞
- **[P0] 缺少异常处理** — PRD 未描述网络超时、数据校验失败等异常情况
- 建议：补充异常处理流程

### P1 — 重要
- **[P1] 缺少权限控制** — PRD 未明确操作者权限要求
- 建议：补充权限说明

### P2 — 一般
- **[P2] 缺少数据迁移方案** — 如果是新功能，未说明旧数据处理
- 建议：补充数据迁移方案

## 风险评估
- **实现难度**: 中 — 需要新增异常处理逻辑
- **依赖风险**: 无
- **兼容性风险**: 低

## 结论与建议
建议补充异常处理、权限控制、数据迁移方案后再进入下一阶段。"
        return ReviewResponse(status="success", report=report, issues=[])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
