"""
企业级优化器集成
将优化器注册到定时任务系统，并提供API端点查看状态。
"""

import asyncio
import json
import logging
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends

logger = logging.getLogger("optimizer_integration")

from common.auth import require_auth
from common.db import get_db
from enterprise_optimizer import (
    get_latest_report,
    get_optimizer_status,
    run_enterprise_optimizer,
)

router = APIRouter(prefix="/api/optimizer", tags=["企业级优化器"])

# 调度器状态
_optimizer_thread = None
_optimizer_lock = threading.Lock()


def _start_optimizer_scheduler():
    """启动优化器后台调度线程（每小时20分运行）。"""
    global _optimizer_thread
    
    with _optimizer_lock:
        if _optimizer_thread and _optimizer_thread.is_alive():
            return
        
        def _run_loop():
            from optimizer_scheduler import EnterpriseOptimizerScheduler
            scheduler = EnterpriseOptimizerScheduler(callback=run_enterprise_optimizer)
            scheduler.start(background=True)
        
        _optimizer_thread = threading.Thread(target=_run_loop, daemon=True)
        _optimizer_thread.start()
        logger.info("🕐 企业级优化调度器已启动（每小时20分运行）")


@router.get("/status")
def get_optimizer_status_endpoint(current_user: dict = Depends(require_auth)):
    """获取优化器当前状态。"""
    status = get_optimizer_status()
    return {
        "last_run": status.get("last_run"),
        "enterprise_readiness": status.get("enterprise_readiness"),
        "ready": status.get("ready", False),
        "scheduler_active": _optimizer_thread and _optimizer_thread.is_alive(),
    }


@router.get("/report")
def get_optimizer_report(current_user: dict = Depends(require_auth)):
    """获取最新优化报告。"""
    report = get_latest_report()
    if not report:
        return {"message": "暂无优化报告", "report": None}
    return report


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


def init_optimizer_system():
    """初始化优化器系统（启动调度器）。"""
    # 确保表结构存在
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS optimizer_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cron_expression TEXT NOT NULL DEFAULT '20 * * * *',
                enabled INTEGER DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # 插入默认任务（每小时20分）
        conn.execute("""
            INSERT OR IGNORE INTO optimizer_jobs (name, cron_expression, enabled)
            VALUES ('企业级智能优化', '20 * * * *', 1)
        """)
        conn.commit()
    finally:
        conn.close()
    
    # 启动调度器
    _start_optimizer_scheduler()
    logger.info("✅ 企业级优化器系统初始化完成")


def get_optimizer_db():
    """获取优化器数据库连接。"""
    conn = get_db()
    return conn
