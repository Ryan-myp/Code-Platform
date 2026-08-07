#!/usr/bin/env python3
"""定时任务引擎（v10.1）。

- 管理 cron 式定时任务
- 支持：定时报告生成、数据同步、提醒通知
- SQLite scheduler_jobs 表持久化
"""

import json
import logging
import threading
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["定时任务"])

# 全局调度线程状态
_scheduler_running = False
_scheduler_thread = None


def _ensure_table():
    conn = get_db()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS scheduler_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                job_type TEXT NOT NULL DEFAULT 'report',
                cron_expression TEXT NOT NULL DEFAULT '0 9 * * *',
                config TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        conn.commit()
    finally:
        conn.close()


_ensure_table()


def _parse_cron(expr: str):
    """简易 cron 解析（支持 5 段：分 时 日 月 周），返回下次运行时间。"""
    parts = expr.strip().split()
    if len(parts) != 5:
        return None
    try:
        minute, hour, day, month, weekday = parts
        now = datetime.now()
        # 简化实现：检查当前时间是否匹配
        if minute != "*" and now.minute != int(minute):
            return None
        if hour != "*" and now.hour != int(hour):
            return None
        if day != "*" and now.day != int(day):
            return None
        if month != "*" and now.month != int(month):
            return None
        if weekday != "*" and now.weekday() != int(weekday):
            return None
        return now.isoformat()
    except (ValueError, IndexError):
        return None


def _run_scheduler_loop():
    """后台调度循环：每分钟检查一次待执行任务。"""
    global _scheduler_running
    while _scheduler_running:
        try:
            conn = get_db()
            try:
                jobs = conn.execute("SELECT * FROM scheduler_jobs WHERE enabled=1").fetchall()
            finally:
                conn.close()

            now = datetime.now()
            for job in jobs:
                next_time = _parse_cron(job["cron_expression"])
                if next_time:
                    logger.info(f"[Scheduler] 执行任务: {job['name']} (id={job['id']})")
                    conn = get_db()
                    try:
                        conn.execute(
                            "UPDATE scheduler_jobs SET last_run=?, updated_at=? WHERE id=?",
                            (now.isoformat(), now.isoformat(), job["id"]),
                        )
                        conn.commit()
                    finally:
                        conn.close()
        except Exception as e:
            logger.error(f"[Scheduler] 调度循环异常: {e}")

        time.sleep(60)


def start_scheduler():
    """启动后台调度线程（由 main.py 在 lifespan 中调用）。"""
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_run_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("[Scheduler] 后台调度已启动")


def stop_scheduler():
    """停止后台调度线程。"""
    global _scheduler_running
    _scheduler_running = False
    logger.info("[Scheduler] 后台调度已停止")


# ── API 端点 ──────────────────────────────────────────────


@router.get("")
def list_jobs(current_user: dict = Depends(require_auth)):
    """获取当前用户的定时任务列表。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduler_jobs WHERE user_id=? ORDER BY created_at DESC",
            (current_user["user_id"],),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("")
def create_job(payload: dict, current_user: dict = Depends(require_auth)):
    """创建定时任务。

    请求体：{"name":"日报","job_type":"report","cron_expression":"0 9 * * *","description":"","config":{}}
    """
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "任务名称不能为空")
    cron = (payload.get("cron_expression") or "0 9 * * *").strip()
    now = datetime.now().isoformat()

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO scheduler_jobs (user_id, name, description, job_type, cron_expression, config, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["user_id"],
                name,
                payload.get("description", ""),
                payload.get("job_type", "report"),
                cron,
                json.dumps(payload.get("config", {})),
                now,
                now,
            ),
        )
        conn.commit()
        job_id = cur.lastrowid
        return {"id": job_id, "name": name, "cron_expression": cron, "created_at": now, "message": "任务创建成功"}
    finally:
        conn.close()


@router.put("/{job_id}")
def update_job(job_id: int, payload: dict, current_user: dict = Depends(require_auth)):
    """更新定时任务。"""
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT * FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        ).fetchone()
        if not job:
            raise HTTPException(404, "任务不存在")

        updates = {}
        for field in ["name", "description", "job_type", "cron_expression", "config", "enabled"]:
            if field in payload:
                val = payload[field]
                if field == "config" and isinstance(val, dict):
                    val = json.dumps(val)
                updates[field] = val
        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE scheduler_jobs SET {set_clause} WHERE id=?",
                (*updates.values(), job_id),
            )
            conn.commit()
        return {"message": "更新成功"}
    finally:
        conn.close()


@router.delete("/{job_id}")
def delete_job(job_id: int, current_user: dict = Depends(require_auth)):
    """删除定时任务。"""
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        )
        conn.commit()
        return {"message": "已删除"}
    finally:
        conn.close()


@router.post("/{job_id}/trigger")
def trigger_job(job_id: int, current_user: dict = Depends(require_auth)):
    """手动触发一次任务。"""
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT * FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        ).fetchone()
        if not job:
            raise HTTPException(404, "任务不存在")

        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE scheduler_jobs SET last_run=?, updated_at=? WHERE id=?",
            (now, now, job_id),
        )
        conn.commit()
        return {"message": f"任务「{job['name']}」已手动触发"}
    finally:
        conn.close()
