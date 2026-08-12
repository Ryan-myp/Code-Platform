"""通用异步任务框架（master-worker 模式）。

- master：后台调度线程，轮询数据库中 pending 任务，抢占后按 worker 池分发给 worker 队列
- worker：线程池消费队列执行注册的处理器，进度/结果实时落库并 WebSocket 推送
- 持久化：SQLite async_tasks 表，重启后 pending 继续执行、running 标记 interrupted（可重试）
- 处理器注册：register_handler(type, fn, pool=...) 一行接入；长任务（如视频渲染）走独立池不阻塞轻量任务
- API：创建 / 查询 / 列表 / 统计 / 重试 / 取消，按用户隔离（管理员可看全部）

处理器签名：
    def handler(task_id: str, payload: dict, update: Callable[[float, str], None], ctx: dict) -> dict:
        update(30, "正在合成配音…")          # 进度(0-100) + 阶段文案
        return {"video_url": ...}            # 成功结果（存 result）
    ctx = {"username": ..., "user_id": ..., "role": ...}
    处理器内抛 HTTPException(402, "...") 会记录 error_code 供前端识别计费类错误。

可靠性保障：
- 结果写入校验 status='running'：执行中任务被取消/重试后，迟到的结果不落库（防双跑）
- update 回调检查 cancel_requested：执行中任务被取消后业务 worker 尽早中止（省外部配额）
- 看门狗：running 超过超时阈值自动标记 failed（worker 卡死/外部 API 挂起不再永久占用）
- 历史清理：终态任务保留 30 天后自动删除（启动时与每日各扫一次）
"""

import asyncio
import inspect
import json
import logging
import os
import queue
import shutil
import sqlite3
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common.auth import consume_quota, refund_quota, require_auth
from common.db import get_db, get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["异步任务"])

# ── worker 池配置（环境变量可覆盖） ──────────────────────────
# 常规池：轻量任务（AI 生成类）；长任务池：外部轮询类（视频渲染等）
LONG_WORKERS = max(1, int(os.environ.get("ASYNC_TASK_LONG_WORKERS", "1")))
_default_workers = int(os.environ.get("ASYNC_TASK_DEFAULT_WORKERS", "2"))
if "ASYNC_TASK_DEFAULT_WORKERS" not in os.environ and os.environ.get("ASYNC_TASK_WORKERS"):
    _default_workers = max(1, int(os.environ["ASYNC_TASK_WORKERS"]) - LONG_WORKERS)
DEFAULT_WORKERS = max(1, _default_workers)
# 进程重启时标记为中断的任务状态：下次启动由 recover_interrupted_tasks 处理
_INTERRUPT_MSG = "服务重启导致任务中断，可点击重试"
# running 超时阈值（秒）：看门狗将超时任务标记为 failed。
# 默认 10800（180 分钟）：须大于业务客户端自身超时（如 SadTalker 7200s），
# 保证客户端超时抛错→引擎降级链执行完毕后仍能写回 success，不被看门狗截胡。
TASK_TIMEOUT_SECONDS = max(60, int(os.environ.get("ASYNC_TASK_TIMEOUT_SECONDS", "10800")))
# 终态任务保留天数（历史清理）
TASK_RETENTION_DAYS = max(1, int(os.environ.get("ASYNC_TASK_RETENTION_DAYS", "30")))

_handlers: dict[str, Callable] = {}
# 任务类型级用户并发限制：task_type → 同用户最多 N 个活跃任务（pending/running），0=不限制
_USER_LIMITS: dict[str, int] = {}
# 任务类型 → worker 池归属（默认常规池；长任务如视频渲染走独立池避免阻塞轻量任务）
_POOLS: dict[str, str] = {}
# 任务类型 → 自动重试次数上限（0=不自动重试；创建任务时快照到任务行）
_MAX_ATTEMPTS: dict[str, int] = {}
# 常规/长任务两个独立队列，互不争抢 worker
_task_queues: dict[str, "queue.Queue[str]"] = {"default": queue.Queue(), "long": queue.Queue()}
_master_running = False
_worker_pool: ThreadPoolExecutor | None = None
_master_thread: threading.Thread | None = None


class TaskCanceled(HTTPException):
    """任务被用户取消（执行中请求取消）：update 回调检测 cancel_requested 后抛出。

    继承 HTTPException 以便业务 worker 的 `except HTTPException: raise` 透传，
    worker 捕获后不再改写任务状态（保持 canceled）。
    """

    def __init__(self, message: str = "任务已取消"):
        super().__init__(status_code=499, detail=message)


def _ensure_table(conn) -> None:
    """任务表（含用户级并发检查所需索引）。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS async_tasks (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            progress REAL NOT NULL DEFAULT 0,
            stage TEXT DEFAULT '',
            payload TEXT DEFAULT '{}',
            result TEXT DEFAULT '',
            error TEXT DEFAULT '',
            error_code INTEGER DEFAULT 0,
            retry_count INTEGER NOT NULL DEFAULT 0,
            created_by TEXT DEFAULT '',
            user_id TEXT DEFAULT '',
            role TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            started_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT ''
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_status ON async_tasks(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_type ON async_tasks(type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_user ON async_tasks(created_by)")
    # 复合索引：列表查询（created_by + ORDER BY created_at）与统计（created_by + GROUP BY status）
    conn.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_user_created ON async_tasks(created_by, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_async_tasks_user_status ON async_tasks(created_by, status)")
    # 迁移：cancel_requested（执行中任务请求取消标志）+ priority（优先级插队）+ 自动重试
    # 并发容错：首次建表时多个线程同时 PRAGMA+ALTER，快照过期会撞 duplicate column，忽略即可
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(async_tasks)").fetchall()}
    for col, ddl in (
        ("cancel_requested", "INTEGER DEFAULT 0"),
        ("priority", "INTEGER DEFAULT 0"),
        ("max_attempts", "INTEGER DEFAULT 0"),
        ("next_retry_at", "TEXT DEFAULT ''"),
        ("quota_refunded", "INTEGER DEFAULT 0"),
    ):
        if col in cols:
            continue
        try:
            conn.execute(f"ALTER TABLE async_tasks ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    conn.commit()


# ══════════════════════════════════════════════════════════════
# 注册与创建（供业务模块调用）
# ══════════════════════════════════════════════════════════════


def register_handler(
    task_type: str, fn: Callable, user_limit: int = 0, pool: str = "default", max_attempts: int = 0
) -> None:
    """注册任务处理器：task_type → fn(task_id, payload, update, ctx) -> result dict。

    user_limit>0 时限制同一用户最多 N 个活跃任务（pending/running），
    创建时原子校验（BEGIN IMMEDIATE 串行化），超出抛 429。
    pool="long" 时任务进入长任务池（独立 worker），适合外部轮询类长耗时任务
    （如视频渲染），避免占用常规池 worker 阻塞轻量生成任务。
    max_attempts>0 时失败自动重试（指数退避，创建任务时快照），计费类错误（402）不重试。
    """
    if task_type in _handlers:
        raise ValueError(f"任务处理器重复注册: {task_type}")
    _handlers[task_type] = fn
    if user_limit > 0:
        _USER_LIMITS[task_type] = user_limit
    if pool not in ("default", "long"):
        raise ValueError(f"未知 worker 池: {pool}")
    _POOLS[task_type] = pool
    _MAX_ATTEMPTS[task_type] = max(0, int(max_attempts))
    logger.info(
        "异步任务处理器已注册: %s（用户并发限制 %s，池 %s，自动重试 %s）",
        task_type,
        user_limit or "无",
        pool,
        f"{max_attempts} 次" if max_attempts else "关",
    )


def create_task(
    task_type: str,
    payload: dict,
    username: str = "",
    user_id: str = "",
    role: str = "",
    priority: int = 0,
) -> dict:
    """创建任务（立即返回，由 worker 异步执行）。返回任务摘要 dict。

    priority 0-10（越大越先执行，默认 0）。注册了用户级并发限制的类型：
    BEGIN IMMEDIATE 串行化「检查活跃数 + 插入」，保证并发提交下不超限（超出抛 429）。
    """
    if task_type not in _handlers:
        raise HTTPException(404, "操作失败，请稍后重试")
    raw_payload = json.dumps(payload, ensure_ascii=False)
    if len(raw_payload) > 256 * 1024:
        raise HTTPException(400, "任务参数过大（>256KB），请精简参数后重试")
    priority = max(0, min(10, int(priority or 0)))
    limit = _USER_LIMITS.get(task_type, 0)
    conn = get_db()
    try:
        _ensure_table(conn)
        conn.commit()  # 结束隐式事务，允许显式 BEGIN IMMEDIATE
        if limit > 0 and username:
            # 写锁串行化：并发提交时第二个请求在此阻塞，之后看到第一条记录
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                "SELECT COUNT(*) FROM async_tasks WHERE type=? AND created_by=? AND status IN ('pending','running')",
                (task_type, username),
            ).fetchone()[0]
            if active >= limit:
                raise HTTPException(429, "您有同类型任务正在执行中，请等待当前任务完成")
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO async_tasks
               (id, type, status, payload, created_by, user_id, role, created_at, priority, max_attempts)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                task_id,
                task_type,
                "pending",
                raw_payload,
                username,
                user_id,
                role,
                datetime.now().isoformat(),
                priority,
                _MAX_ATTEMPTS.get(task_type, 0),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    _invalidate_stats(role, username)
    return {
        "id": task_id,
        "type": task_type,
        "status": "pending",
        "progress": 0,
        "stage": "任务排队中…",
        "priority": priority,
    }


def get_task(task_id: str) -> dict | None:
    """按 ID 查任务（含解析后的 payload/result）。"""
    conn = get_db()
    try:
        _ensure_table(conn)
        row = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return _row_to_task(row)


def _row_to_task(row, strip_result: bool = False) -> dict:
    task = dict(row)
    try:
        task["payload"] = json.loads(task.get("payload") or "{}")
    except (json.JSONDecodeError, TypeError):
        task["payload"] = {}
    try:
        task["result"] = json.loads(task.get("result") or "{}") if task.get("result") else None
    except (json.JSONDecodeError, TypeError):
        task["result"] = None
    # 列表场景裁剪 result 大字段（完整生成代码等几百 KB），避免列表接口读放大
    if strip_result and isinstance(task.get("result"), dict):
        stripped = {}
        for k, v in task["result"].items():
            if isinstance(v, (dict, list)):
                try:
                    size = len(json.dumps(v, ensure_ascii=False))
                except (TypeError, ValueError):
                    size = 4096
                if size > 4096:
                    continue
            elif isinstance(v, str) and len(v) > 4096:
                continue
            stripped[k] = v
        task["result"] = stripped
    return task


# 终态事件推送完整任务（含 result）；进度类事件只推轻量字段，避免 payload/result 大字段随进度读放大
_TERMINAL_EVENTS = ("task_success", "task_failed", "task_canceled", "task_retried", "task_deleted")
_PROGRESS_FIELDS = ("id", "type", "status", "progress", "stage")


def _broadcast_task(task: dict, event: str = "task_update") -> None:
    """任务状态变更 WebSocket 推送：单任务频道 + 所属用户列表频道。

    终态事件（成功/失败/取消/重试）推送完整任务；进度类事件仅推轻量字段。
    """
    try:
        from realtime import send_progress_threadsafe

        payload = task if event in _TERMINAL_EVENTS else {k: task.get(k) for k in _PROGRESS_FIELDS}
        task_id = task.get("id", "")
        send_progress_threadsafe(f"task:{task_id}", event, payload)
        username = task.get("created_by") or ""
        if username:
            send_progress_threadsafe(f"task:user:{username}", event, payload)
    except Exception:  # noqa: BLE001 广播失败不影响主流程
        logger.debug("task ws broadcast failed %s", task.get("id"))


# 进度节流：同任务 500ms 内且进度变化 <2 且阶段未变时跳过落库/推送（写放大治理）
PROGRESS_THROTTLE_SECONDS = 0.5
# task_id -> (last_ts, last_progress, last_stage)；终态/删除时清理
_progress_throttle: dict[str, tuple[float, float, str]] = {}


def _update_progress(task_id: str, progress: float, stage: str) -> None:
    """处理器内进度回调：取消检查每次都做（保证实时中止）；落库+WS 推送按节流合并。"""
    try:
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT cancel_requested, created_by, type FROM async_tasks WHERE id=?", (task_id,)
            ).fetchone()
            if row is None:
                return
            if row["cancel_requested"]:
                raise TaskCanceled()
        pct = max(0.0, min(100.0, progress))
        now = time.monotonic()
        prev = _progress_throttle.get(task_id)
        if prev and now - prev[0] < PROGRESS_THROTTLE_SECONDS and pct - prev[1] < 2 and stage == prev[2]:
            return
        with get_db_context() as conn:
            conn.execute(
                "UPDATE async_tasks SET progress=?, stage=? WHERE id=?",
                (pct, (stage or "")[:80], task_id),
            )
        _progress_throttle[task_id] = (now, pct, stage)
        _broadcast_task(
            {
                "id": task_id,
                "type": row["type"],
                "progress": pct,
                "stage": stage,
                "status": "running",
                "created_by": row["created_by"] or "",
            }
        )
    except TaskCanceled:
        raise
    except Exception:
        logger.exception("task progress update failed %s", task_id)


# 自动重试退避基数（秒）：第 n 次重试延迟 base * 2^(n-1)，封顶 10 分钟
AUTO_RETRY_BASE_DELAY = max(1, int(os.environ.get("ASYNC_TASK_RETRY_BASE_DELAY", "5")))


def _next_retry_at(attempt: int) -> str:
    """自动重试的指数退避时间（attempt 为即将执行的尝试次数，1 起）。"""
    delay = min(AUTO_RETRY_BASE_DELAY * (2 ** (attempt - 1)), 600)
    return (datetime.now() + timedelta(seconds=delay)).isoformat()


# 自动重试豁免码：计费类错误重试=重复扣费，直接失败
_RETRY_EXEMPT_CODES = (402,)


def _should_auto_retry(row, error_code: int) -> bool:
    """自动重试条件：配置了次数上限、未超限、且非计费错误。"""
    return (
        bool(row["max_attempts"]) and row["retry_count"] < row["max_attempts"] and error_code not in _RETRY_EXEMPT_CODES
    )


def _mark_failed(task_id: str, error: str, error_code: int = 0) -> None:
    """标记失败：仅当任务仍处于 running（防覆盖已取消/已重试的任务）。

    配置自动重试的任务重置为 pending（retry_count+1、指数退避），
    master 到点后重新调度；其余任务标记 failed。
    """
    with get_db_context() as conn:
        row = conn.execute("SELECT type, retry_count, max_attempts FROM async_tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return
        if _should_auto_retry(row, error_code):
            cur = conn.execute(
                "UPDATE async_tasks SET status='pending', retry_count=retry_count+1, error=?, error_code=?, "
                "finished_at='', started_at='', cancel_requested=0, next_retry_at=?, stage=? "
                "WHERE id=? AND status='running'",
                (
                    (error or "任务执行失败")[:500],
                    error_code,
                    _next_retry_at(row["retry_count"] + 1),
                    f"执行失败（第 {row['retry_count'] + 1}/{row['max_attempts']} 次尝试），自动重试排队中",
                    task_id,
                ),
            )
            if cur.rowcount:
                task = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
                if task:
                    _broadcast_task(_row_to_task(task), event="task_retried")
            return
        cur = conn.execute(
            "UPDATE async_tasks SET status='failed', error=?, error_code=?, finished_at=?, quota_refunded=1 "
            "WHERE id=? AND status='running'",
            ((error or "任务执行失败")[:500], error_code, datetime.now().isoformat(), task_id),
        )
        if cur.rowcount:
            # 失败退费（商业公平）：仅非计费错误（402 未真实扣费）；quota_refunded
            # 与状态转换同事务原子置位，保证同一任务至多退费一次（幂等）
            if error_code != 402:
                task = conn.execute("SELECT user_id FROM async_tasks WHERE id=?", (task_id,)).fetchone()
                if task and task["user_id"] and refund_quota(task["user_id"], conn=conn):
                    logger.info("任务失败退费: %s（错误码 %s）", task_id, error_code)
            task = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
            if task:
                _broadcast_task(_row_to_task(task), event="task_failed")


# ══════════════════════════════════════════════════════════════
# worker：执行处理器
# ══════════════════════════════════════════════════════════════


def _ensure_claimable(task_id: str, current_status: str) -> bool:
    """worker 启动前防护：仅 running 任务可执行（取消竞态），并刷新 started_at 排除队列等待。"""
    if current_status != "running":
        logger.info("task skipped (status=%s, canceled before worker start): %s", current_status, task_id)
        return False
    with get_db_context() as conn:
        conn.execute(
            "UPDATE async_tasks SET started_at=? WHERE id=? AND status='running'",
            (datetime.now().isoformat(), task_id),
        )
    return True


def _mark_success(task_id: str, result) -> None:
    """写入成功结果：状态校验防双跑（任务已被取消/重试时丢弃迟到结果）。"""
    with get_db_context() as conn:
        cur = conn.execute(
            "UPDATE async_tasks SET status='success', progress=100, result=?, stage='生成完成', finished_at=? "
            "WHERE id=? AND status='running'",
            (
                json.dumps(result if isinstance(result, dict) else {"result": result}, ensure_ascii=False),
                datetime.now().isoformat(),
                task_id,
            ),
        )
        if cur.rowcount:
            row = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
            if row:
                _broadcast_task(_row_to_task(row), event="task_success")


def _run_handler(task_id: str) -> None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return
    if not _ensure_claimable(task_id, row["status"]):
        return
    fn = _handlers.get(row["type"])
    if not fn:
        _mark_failed(task_id, f"未注册的任务处理器: {row['type']}")
        return
    try:
        payload = json.loads(row["payload"] or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}
    ctx = {"username": row["created_by"] or "", "user_id": row["user_id"] or "", "role": row["role"] or ""}
    try:
        result = fn(task_id, payload, lambda p, s: _update_progress(task_id, p, s), ctx)
        # async 处理器（内部 await call_llm_async 等）：worker 线程内新建事件循环执行
        if inspect.iscoroutine(result):
            result = asyncio.run(result)
        _mark_success(task_id, result)
    except TaskCanceled:
        # 任务已取消：状态保持 canceled，不覆盖、不报错
        logger.info("task canceled mid-run: %s", task_id)
    except HTTPException as e:
        if e.status_code == 499:
            logger.info("task canceled mid-run: %s", task_id)
            return
        _mark_failed(task_id, str(e.detail), e.status_code)
    except Exception as e:
        logger.exception("task handler crashed %s", task_id)
        _mark_failed(task_id, str(e)[:500])
    finally:
        _progress_throttle.pop(task_id, None)


def _worker_loop(pool: str) -> None:
    """worker 消费循环：阻塞取对应池队列任务，执行完成后继续下一单。"""
    while True:
        task_id = _task_queues[pool].get()
        try:
            _run_handler(task_id)
        finally:
            _task_queues[pool].task_done()


# ══════════════════════════════════════════════════════════════
# master：调度循环（扫描 pending → 原子抢占 → 分发 worker）
# ══════════════════════════════════════════════════════════════


def _cleanup_stale_temp_files() -> int:
    """清理残留的任务临时文件：任务创建后服务重启，worker 未消费的 file:// 文件。

    图片工厂临时文件前缀 img_task_，配音分段目录前缀 voice_seg_。
    """
    removed = 0
    for prefix in ("img_task_",):
        for name in os.listdir(tempfile.gettempdir()):
            if name.startswith(prefix):
                try:
                    os.remove(os.path.join(tempfile.gettempdir(), name))
                    removed += 1
                except OSError:
                    pass
    for name in os.listdir(tempfile.gettempdir()):
        if name.startswith("voice_seg_") and os.path.isdir(os.path.join(tempfile.gettempdir(), name)):
            try:
                shutil.rmtree(os.path.join(tempfile.gettempdir(), name), ignore_errors=True)
                removed += 1
            except OSError:
                pass
    if removed:
        logger.info("任务临时文件清理：移除 %s 个残留文件", removed)
    return removed


def _cleanup_expired_tasks() -> int:
    """历史清理：删除超过保留期的终态任务（success/failed/interrupted/canceled）。"""
    cutoff = (datetime.now() - timedelta(days=TASK_RETENTION_DAYS)).isoformat()
    with get_db_context() as conn:
        cur = conn.execute(
            "DELETE FROM async_tasks WHERE status IN ('success','failed','interrupted','canceled') "
            "AND finished_at != '' AND finished_at < ?",
            (cutoff,),
        )
    if cur.rowcount:
        logger.info("历史任务清理：删除 %s 条 %s 天前的终态任务", cur.rowcount, TASK_RETENTION_DAYS)
    return cur.rowcount


def _watchdog() -> int:
    """看门狗：running 超过超时阈值的任务标记为 failed（worker 卡死/外部 API 挂起）。"""
    cutoff = (datetime.now() - timedelta(seconds=TASK_TIMEOUT_SECONDS)).isoformat()
    rows = []
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, user_id FROM async_tasks WHERE status='running' AND started_at < ?",
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()
    for r in rows:
        with get_db_context() as conn:
            cur = conn.execute(
                "UPDATE async_tasks SET status='failed', error=?, error_code=0, finished_at=?, quota_refunded=1 "
                "WHERE id=? AND status='running'",
                (
                    f"任务执行超时（>{TASK_TIMEOUT_SECONDS // 60} 分钟），已自动终止，可点击重试",
                    datetime.now().isoformat(),
                    r["id"],
                ),
            )
            if cur.rowcount:
                # 看门狗超时失败：用户无责的服务端异常，同样退费（quota_refunded 幂等）
                if r["user_id"] and refund_quota(r["user_id"], conn=conn):
                    logger.info("看门狗超时退费: %s", r["id"])
                row = conn.execute("SELECT * FROM async_tasks WHERE id=?", (r["id"],)).fetchone()
                if row:
                    _broadcast_task(_row_to_task(row), event="task_failed")
    if rows:
        logger.warning("看门狗：%s 个任务执行超时已标记失败", len(rows))
    return len(rows)


# master 每轮扫描上限：有积压时一次多抢，避免重启后几百条 pending 恢复过慢
SCAN_BATCH = min(50, (DEFAULT_WORKERS + LONG_WORKERS) * 8)


def _fetch_pending(conn, now_iso: str):
    """取待调度任务：自动重试任务需等待退避时间；按优先级高→低、先来先服务。"""
    return conn.execute(
        "SELECT id, type FROM async_tasks WHERE status='pending' "
        "AND (next_retry_at='' OR next_retry_at <= ?) ORDER BY priority DESC, created_at LIMIT ?",
        (now_iso, SCAN_BATCH),
    ).fetchall()


def _master_loop() -> None:
    """master 调度：扫描 pending 任务 → 原子抢占 → 按 worker 池入队；
    周期性执行看门狗与历史清理。"""
    last_housekeep = 0.0
    while _master_running:
        try:
            conn = get_db()
            try:
                rows = _fetch_pending(conn, datetime.now().isoformat())
            finally:
                conn.close()
            claimed = 0
            for r in rows:
                # 原子抢占：并发多实例/重启竞争下仅一个 master 能成功
                with get_db_context() as conn:
                    cur = conn.execute(
                        "UPDATE async_tasks SET status='running', started_at=?, stage='执行中' "
                        "WHERE id=? AND status='pending'",
                        (datetime.now().isoformat(), r["id"]),
                    )
                    if cur.rowcount:
                        pool = _POOLS.get(r["type"], "default")
                        _task_queues[pool].put(r["id"])
                        claimed += 1
            # 看门狗 + 历史清理：每 60s 一次
            now = time.time()
            if now - last_housekeep >= 60:
                try:
                    _watchdog()
                    _cleanup_expired_tasks()
                except Exception:
                    logger.exception("task housekeeping failed")
                last_housekeep = now
            time.sleep(0.5 if claimed else 2.0)
        except Exception:
            logger.exception("task master loop error")
            time.sleep(2)


def recover_interrupted_tasks() -> int:
    """启动时恢复：上次进程退出时仍 running 的任务标记为 interrupted（可手动重试）。"""
    conn = get_db()
    try:
        _ensure_table(conn)
        now = datetime.now().isoformat()
        n = conn.execute(
            "UPDATE async_tasks SET status='interrupted', error=?, finished_at=? WHERE status='running'",
            (_INTERRUPT_MSG, now),
        ).rowcount
        conn.commit()
        if n:
            logger.info("异步任务恢复：%s 个运行中任务标记为已中断（可重试）", n)
        return n
    except Exception:
        logger.exception("recover interrupted tasks failed")
        return 0
    finally:
        conn.close()


def start_workers() -> None:
    """启动 master 调度线程 + 双 worker 池（常规/长任务），清理残留临时文件。"""
    global _master_running, _worker_pool, _master_thread
    if _master_running:
        return
    _cleanup_stale_temp_files()
    _master_running = True
    _worker_pool = ThreadPoolExecutor(
        max_workers=DEFAULT_WORKERS + LONG_WORKERS, thread_name_prefix="async-task-worker"
    )
    for _ in range(DEFAULT_WORKERS):
        _worker_pool.submit(_worker_loop, "default")
    for _ in range(LONG_WORKERS):
        _worker_pool.submit(_worker_loop, "long")
    _master_thread = threading.Thread(target=_master_loop, name="async-task-master", daemon=True)
    _master_thread.start()
    logger.info("异步任务框架已启动：常规池 %s worker + 长任务池 %s worker", DEFAULT_WORKERS, LONG_WORKERS)


def stop_workers() -> None:
    """停止调度（仅标记，运行中任务由重启恢复机制兜底）。"""
    global _master_running
    _master_running = False
    logger.info("异步任务框架已停止")


# ══════════════════════════════════════════════════════════════
# API：创建 / 查询 / 列表 / 重试 / 取消
# ══════════════════════════════════════════════════════════════


class CreateTaskRequest(BaseModel):
    payload: dict = Field(default_factory=dict, description="任务参数（任意 JSON，由对应处理器解析）")
    priority: int = Field(0, ge=0, le=10, description="优先级（0-10，越大越先执行，默认 0）")


def _check_owner(row, current_user: dict) -> None:
    """任务归属校验：管理员可操作任意任务，普通用户仅限本人。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    if role == "admin":
        return
    if row["created_by"] != user:
        raise HTTPException(403, "无权访问该任务")


@router.post("/cleanup")
async def cleanup_tasks_api(current_user: dict = require_auth()):
    """清空终态任务（success/failed/interrupted/canceled），执行中的任务不受影响。

    注意：必须注册在 /{task_type} 之前避免被通配路由拦截。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    terminal = "('success','failed','interrupted','canceled')"
    with get_db_context() as conn:
        if role == "admin":
            cur = conn.execute(f"DELETE FROM async_tasks WHERE status IN {terminal}")
        else:
            cur = conn.execute(f"DELETE FROM async_tasks WHERE status IN {terminal} AND created_by=?", (user,))
    deleted = cur.rowcount
    _progress_throttle.clear()
    _invalidate_stats(role, user)
    if deleted:
        logger.info("任务清空：%s 删除 %s 条终态任务", user or role, deleted)
    return {"deleted": deleted, "message": f"已清理 {deleted} 条历史任务"}


@router.post("/{task_type}")
async def create_task_api(
    task_type: str,
    req: CreateTaskRequest | None = None,
    current_user: dict = require_auth(),
):
    """创建异步任务：立即返回 task_id，后台 worker 执行。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = (req.payload if req else {}) or {}
    priority = (req.priority if req else 0) or 0
    task = create_task(task_type, payload, username=user, user_id=uid, role=role, priority=priority)
    return {"task_id": task["id"], "status": "pending", "message": "任务已提交，后台执行中", "task": task}


@router.get("/stats")
async def task_stats_api(current_user: dict = require_auth()):
    """任务统计：总量 / 状态分布 / 类型分布 / 今日 / 成功率 / 平均时长。

    注意：必须注册在 /{task_id} 之前避免路径冲突。
    """
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    cache_key = f"{role}:{user}"
    cached = _stats_cache.get(cache_key)
    if cached and time.time() - cached[0] < STATS_CACHE_TTL:
        return cached[1]
    where, args = ["1=1"], []
    if role != "admin":
        where.append("created_by=?")
        args.append(user)
    where_sql = " AND ".join(where)
    conn = get_db()
    try:
        _ensure_table(conn)
        total = conn.execute(f"SELECT COUNT(*) FROM async_tasks WHERE {where_sql}", args).fetchone()[0]
        by_status = dict(
            conn.execute(f"SELECT status, COUNT(*) FROM async_tasks WHERE {where_sql} GROUP BY status", args).fetchall()
        )
        by_type = dict(
            conn.execute(f"SELECT type, COUNT(*) FROM async_tasks WHERE {where_sql} GROUP BY type", args).fetchall()
        )
        today = datetime.now().strftime("%Y-%m-%d")
        today_created = conn.execute(
            f"SELECT COUNT(*) FROM async_tasks WHERE {where_sql} AND created_at LIKE ?",
            args + [f"{today}%"],
        ).fetchone()[0]
        today_finished = conn.execute(
            f"SELECT COUNT(*) FROM async_tasks WHERE {where_sql} AND status='success' AND finished_at LIKE ?",
            args + [f"{today}%"],
        ).fetchone()[0]
        row = conn.execute(
            f"SELECT AVG((julianday(finished_at) - julianday(started_at)) * 86400) AS avg_sec, "
            f"SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS ok, COUNT(*) AS done "
            f"FROM async_tasks WHERE {where_sql} AND status IN ('success','failed','interrupted','canceled') "
            f"AND started_at != '' AND finished_at != ''",
            args,
        ).fetchone()
        done = row["done"] or 0
        success_rate = round((row["ok"] or 0) * 100 / done, 1) if done else 0.0
        avg_duration = round(row["avg_sec"] or 0, 1)
    finally:
        conn.close()
    result = {
        "total": total,
        "by_status": by_status,
        "by_type": by_type,
        "today_created": today_created,
        "today_finished": today_finished,
        "success_rate": success_rate,
        "avg_duration_seconds": avg_duration,
        "active": by_status.get("pending", 0) + by_status.get("running", 0),
    }
    # 缓存防膨胀：用户键过多时整体清空重建
    if len(_stats_cache) > 500:
        _stats_cache.clear()
    _stats_cache[cache_key] = (time.time(), result)
    return result


@router.get("/{task_id}")
async def get_task_api(task_id: str, current_user: dict = require_auth()):
    """查询任务详情：状态 / 进度 / 阶段文案 / 结果 / 错误。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _check_owner(task, current_user)
    return task


@router.get("")
async def list_tasks_api(
    type: str = Query("", description="按任务类型过滤"),
    status: str = Query("", description="按状态过滤"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0, description="分页偏移"),
    current_user: dict = require_auth(),
):
    """任务列表（默认当前用户，按创建时间倒序；result 大字段已裁剪为摘要）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    where, args = ["1=1"], []
    if role != "admin":
        where.append("created_by=?")
        args.append(user)
    if type.strip():
        types = [t.strip() for t in type.split(",") if t.strip()]
        if len(types) > 1:
            where.append(f"type IN ({','.join('?' * len(types))})")
            args.extend(types)
        else:
            where.append("type=?")
            args.append(types[0])
    if status.strip():
        where.append("status=?")
        args.append(status.strip())
    where_sql = " AND ".join(where)
    conn = get_db()
    try:
        _ensure_table(conn)
        total = conn.execute(f"SELECT COUNT(*) FROM async_tasks WHERE {where_sql}", args).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM async_tasks WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            args + [limit, offset],
        ).fetchall()
    finally:
        conn.close()
    return {
        "tasks": [_row_to_task(r, strip_result=True) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# 统计缓存：stats 接口多次 COUNT/GROUP BY 全表扫描，TTL 内直接复用结果
_stats_cache: dict[str, tuple[float, dict]] = {}
STATS_CACHE_TTL = 30.0


def _invalidate_stats(role: str, username: str) -> None:
    """任务变更后失效对应统计缓存（管理员/用户键分开，不影响他人）。

    直接调用 create_task 时 role 常为空：按普通用户视角失效（API 层必传真实角色）。
    """
    if not username:
        return
    _stats_cache.pop(f"{role or 'user'}:{username}", None)


@router.post("/{task_id}/retry")
async def retry_task_api(task_id: str, current_user: dict = require_auth()):
    """重试任务：仅终态（failed / interrupted / canceled / success）可重试。

    排队中/执行中的任务禁止重试——running 任务被重置会与新 worker 双跑，
    造成结果互相覆盖并重复消耗外部 API 配额。
    """
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _check_owner(task, current_user)
    if task["status"] in ("pending", "running"):
        raise HTTPException(400, "任务正在排队/执行中，无法重试，请等待完成")
    # 重试计费：failed/success 重试 = 新一次执行（失败已退费 / 成功是新增需求），重新扣费；
    # interrupted/canceled 重试 = 续跑（提交时已扣且未退费），不重复扣费；402 拒绝重试
    if task["status"] in ("failed", "success"):
        uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
        quota = consume_quota(uid)
        if not quota.get("allowed"):
            raise HTTPException(402, "今日免费额度已用完，升级会员可继续使用（剩余 0 次）")
    with get_db_context() as conn:
        conn.execute(
            """UPDATE async_tasks
               SET status='pending', progress=0, stage='任务已重新提交', result='', error='',
                   error_code=0, retry_count=retry_count+1, started_at='', finished_at='',
                   cancel_requested=0, next_retry_at='', quota_refunded=0
               WHERE id=?""",
            (task_id,),
        )
        row = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
        conn.commit()
    if row:
        _broadcast_task(_row_to_task(row), event="task_retried")
    _invalidate_stats(current_user.get("role", ""), current_user.get("username", ""))
    return {"task_id": task_id, "status": "pending", "message": "任务已重新提交，后台执行中"}


@router.post("/{task_id}/cancel")
async def cancel_task_api(task_id: str, current_user: dict = require_auth()):
    """取消任务：排队中直接取消；执行中置 cancel_requested 标志，
    worker 下次进度回调时自检中止（迟到的结果不落库）。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _check_owner(task, current_user)
    with get_db_context() as conn:
        cur = conn.execute(
            "UPDATE async_tasks SET status='canceled', cancel_requested=1, stage='已取消', finished_at=? "
            "WHERE id=? AND status IN ('pending','running')",
            (datetime.now().isoformat(), task_id),
        )
        conn.commit()
    if not cur.rowcount:
        raise HTTPException(400, "仅排队中/执行中的任务可取消（已完成的任务无需取消）")
    _broadcast_task(get_task(task_id), event="task_canceled")
    _invalidate_stats(current_user.get("role", ""), current_user.get("username", ""))
    return {"task_id": task_id, "status": "canceled", "message": "任务已取消"}


@router.delete("/{task_id}")
async def delete_task_api(task_id: str, current_user: dict = require_auth()):
    """删除任务记录：执行中的任务禁止删除（先取消或等待完成），其余状态均可删。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _check_owner(task, current_user)
    if task["status"] == "running":
        raise HTTPException(400, "任务执行中，请先取消或等待完成后再删除")
    with get_db_context() as conn:
        cur = conn.execute("DELETE FROM async_tasks WHERE id=?", (task_id,))
    if not cur.rowcount:
        raise HTTPException(404, "任务不存在")
    _progress_throttle.pop(task_id, None)
    _broadcast_task(task, event="task_deleted")
    _invalidate_stats(current_user.get("role", ""), current_user.get("username", ""))
    return {"task_id": task_id, "message": "任务已删除"}
