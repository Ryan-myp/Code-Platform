"""
企业级优化器集成（API端点）
提供REST API查看优化状态和手动触发优化。
调度由 backend/scheduler.py 统一处理（每小时20分自动运行）。
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from common.auth import require_auth
from common.db import get_db
from enterprise_optimizer import (
    get_latest_report,
    get_optimizer_status,
    run_enterprise_optimizer,
)

router = APIRouter(prefix="/api/optimizer", tags=["企业级优化器"])

logger = logging.getLogger("optimizer_integration")


@router.get("/status")
def get_optimizer_status_endpoint(current_user: dict = Depends(require_auth)):
    """获取优化器当前状态。"""
    status = get_optimizer_status()
    return {
        "last_run": status.get("last_run"),
        "enterprise_readiness": status.get("enterprise_readiness"),
        "ready": status.get("ready", False),
        "scheduler_active": True,  # 由 scheduler.py 统一管理
    }


@router.get("/report")
def get_optimizer_report(current_user: dict = Depends(require_auth)):
    """获取最新优化报告。"""
    report = get_latest_report()
    if not report:
        return {"message": "暂无优化报告", "report": None}
    return report


@router.get("/metrics")
def get_optimizer_metrics(current_user: dict = Depends(require_auth)):
    """获取优化指标摘要。"""
    report = get_latest_report()
    if not report:
        return {"message": "暂无数据"}
    
    summary = report.get("summary", {})
    readiness = report.get("enterprise_readiness", {})
    
    return {
        "total_score": readiness.get("score", 0),
        "grade": readiness.get("grade", "N/A"),
        "code_quality": summary.get("code", {}).get("complexity_score", 0),
        "test_passed": summary.get("tests", {}).get("passed", 0),
        "test_total": summary.get("tests", {}).get("total", 0),
        "api_healthy": summary.get("api", {}).get("healthy", 0),
        "api_checked": summary.get("api", {}).get("checked", 0),
        "security_passed": summary.get("security", {}).get("checks_passed", 0),
        "security_failed": summary.get("security", {}).get("checks_failed", 0),
        "deps_outdated": summary.get("deps", {}).get("outdated", 0),
        "deps_vulnerable": summary.get("deps", {}).get("vulnerable", 0),
        "space_freed_mb": summary.get("data", {}).get("space_freed_mb", 0),
    }


@router.post("/run-now")
def run_optimizer_now(current_user: dict = Depends(require_auth)):
    """立即运行一次优化。"""
    try:
        result = run_enterprise_optimizer()
        return {
            "message": "优化完成",
            "report_path": result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"优化失败: {e}")
        raise


@router.get("/schedule")
def get_optimizer_schedule(current_user: dict = Depends(require_auth)):
    """获取优化器调度信息。"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, job_type, cron_expression, enabled, last_run, next_run, last_status "
            "FROM scheduler_jobs WHERE name='企业级智能优化' LIMIT 1"
        ).fetchone()
        if row:
            return dict(row)
        return {"message": "未配置优化器任务"}
    finally:
        conn.close()


def init_optimizer_system():
    """初始化优化器系统。"""
    # 确保 API 路由已注册（在 main.py 中完成）
    logger.info("✅ 企业级优化器API系统就绪（调度由 scheduler.py 管理）")
