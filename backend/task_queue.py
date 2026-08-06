"""通用异步任务框架（master-worker 模式）。

- master：后台调度线程，轮询数据库中 pending 任务，抢占后分发给 worker 队列
- worker：线程池消费队列执行注册的处理器，进度/结果实时落库
- 持久化：SQLite async_tasks 表，重启后 pending 继续执行、running 标记 interrupted（可重试）
- 处理器注册：register_handler(type, fn)，任意耗时业务（视频生成/批量渲染等）一行接入
- API：创建 / 查询 / 列表 / 重试 / 取消，按用户隔离（管理员可看全部）

处理器签名：
    def handler(task_id: str, payload: dict, update: Callable[[float, str], None], ctx: dict) -> dict:
        update(30, "正在合成配音…")          # 进度(0-100) + 阶段文案
        return {"video_url": ...}            # 成功结果（存 result）
    ctx = {"username": ..., "user_id": ..., "role": ...}
    处理器内抛 HTTPException(402, "...") 会记录 error_code 供前端识别计费类错误。
"""
import asyncio
import inspect
import json
import logging
import os
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db, get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["异步任务"])

# worker 并发数（可环境变量覆盖；业务内部可再限流，如数字人渲染信号量）
MAX_WORKERS = max(1, int(os.environ.get("ASYNC_TASK_WORKERS", "3")))
# 进程重启时标记为中断的任务状态：下次启动由 recover_interrupted_tasks 处理
_INTERRUPT_MSG = "服务重启导致任务中断，可点击重试"

_handlers: dict[str, Callable] = {}
# 任务类型级用户并发限制：task_type → 同用户最多 N 个活跃任务（pending/running），0=不限制
_USER_LIMITS: dict[str, int] = {}
_task_queue: "queue.Queue[str]" = queue.Queue()
_master_running = False
_worker_pool: ThreadPoolExecutor | None = None
_master_thread: threading.Thread | None = None


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
    conn.commit()


# ══════════════════════════════════════════════════════════════
# 注册与创建（供业务模块调用）
# ══════════════════════════════════════════════════════════════

def register_handler(task_type: str, fn: Callable, user_limit: int = 0) -> None:
    """注册任务处理器：task_type → fn(task_id, payload, update, ctx) -> result dict。

    user_limit>0 时限制同一用户最多 N 个活跃任务（pending/running），
    创建时原子校验（BEGIN IMMEDIATE 串行化），超出抛 429。
    """
    if task_type in _handlers:
        raise ValueError(f"任务处理器重复注册: {task_type}")
    _handlers[task_type] = fn
    if user_limit > 0:
        _USER_LIMITS[task_type] = user_limit
    logger.info("异步任务处理器已注册: %s（用户并发限制 %s）", task_type, user_limit or "无")


def create_task(task_type: str, payload: dict, username: str = "", user_id: str = "", role: str = "") -> dict:
    """创建任务（立即返回，由 worker 异步执行）。返回任务摘要 dict。

    注册了用户级并发限制的类型：BEGIN IMMEDIATE 串行化「检查活跃数 + 插入」，
    保证并发提交下不超限（超出抛 429）。
    """
    if task_type not in _handlers:
        raise HTTPException(404, f"未注册的任务类型: {task_type}")
    limit = _USER_LIMITS.get(task_type, 0)
    conn = get_db()
    try:
        _ensure_table(conn)
        conn.commit()  # 结束隐式事务，允许显式 BEGIN IMMEDIATE
        if limit > 0 and username:
            # 写锁串行化：并发提交时第二个请求在此阻塞，之后看到第一条记录
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute(
                "SELECT COUNT(*) FROM async_tasks WHERE type=? AND created_by=? "
                "AND status IN ('pending','running')",
                (task_type, username),
            ).fetchone()[0]
            if active >= limit:
                raise HTTPException(429, "您有同类型任务正在执行中，请等待当前任务完成")
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO async_tasks
               (id, type, status, payload, created_by, user_id, role, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (task_id, task_type, "pending", json.dumps(payload, ensure_ascii=False),
             username, user_id, role, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": task_id, "type": task_type, "status": "pending", "progress": 0, "stage": "任务排队中…"}


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


def _row_to_task(row) -> dict:
    task = dict(row)
    try:
        task["payload"] = json.loads(task.get("payload") or "{}")
    except (json.JSONDecodeError, TypeError):
        task["payload"] = {}
    try:
        task["result"] = json.loads(task.get("result") or "{}") if task.get("result") else None
    except (json.JSONDecodeError, TypeError):
        task["result"] = None
    return task


def _update_progress(task_id: str, progress: float, stage: str) -> None:
    """处理器内进度回调：实时落库（SQLite WAL 短事务，高频调用安全）。"""
    try:
        with get_db_context() as conn:
            conn.execute(
                "UPDATE async_tasks SET progress=?, stage=? WHERE id=?",
                (max(0.0, min(100.0, progress)), (stage or "")[:80], task_id),
            )
    except Exception:
        logger.exception("task progress update failed %s", task_id)


def _mark_failed(task_id: str, error: str, error_code: int = 0) -> None:
    with get_db_context() as conn:
        conn.execute(
            "UPDATE async_tasks SET status='failed', error=?, error_code=?, finished_at=? WHERE id=?",
            ((error or "任务执行失败")[:500], error_code, datetime.now().isoformat(), task_id),
        )


# ══════════════════════════════════════════════════════════════
# worker：执行处理器
# ══════════════════════════════════════════════════════════════

def _run_handler(task_id: str) -> None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM async_tasks WHERE id=?", (task_id,)).fetchone()
    finally:
        conn.close()
    if not row:
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
        with get_db_context() as conn:
            conn.execute(
                "UPDATE async_tasks SET status='success', progress=100, result=?, stage='生成完成', finished_at=? WHERE id=?",
                (json.dumps(result if isinstance(result, dict) else {"result": result}, ensure_ascii=False),
                 datetime.now().isoformat(), task_id),
            )
    except HTTPException as e:
        _mark_failed(task_id, str(e.detail), e.status_code)
    except Exception as e:
        logger.exception("task handler crashed %s", task_id)
        _mark_failed(task_id, str(e)[:500])


def _worker_loop() -> None:
    """worker 消费循环：阻塞取队列任务，执行完成后继续下一单。"""
    while True:
        task_id = _task_queue.get()
        try:
            _run_handler(task_id)
        finally:
            _task_queue.task_done()


# ══════════════════════════════════════════════════════════════
# master：调度循环（扫描 pending → 原子抢占 → 分发 worker）
# ══════════════════════════════════════════════════════════════

def _master_loop() -> None:
    """master 调度：周期性扫描 pending 任务，抢占（pending→running）后入队。"""
    while _master_running:
        try:
            conn = get_db()
            try:
                rows = conn.execute(
                    "SELECT id FROM async_tasks WHERE status='pending' ORDER BY created_at LIMIT ?",
                    (MAX_WORKERS * 2,),
                ).fetchall()
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
                        _task_queue.put(r["id"])
                        claimed += 1
            time.sleep(0.5 if claimed else 1.5)
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
    """启动 master 调度线程 + worker 线程池（由 main.py lifespan 调用）。"""
    global _master_running, _worker_pool, _master_thread
    if _master_running:
        return
    _master_running = True
    _worker_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="async-task-worker")
    for _ in range(MAX_WORKERS):
        _worker_pool.submit(_worker_loop)
    _master_thread = threading.Thread(target=_master_loop, name="async-task-master", daemon=True)
    _master_thread.start()
    logger.info("异步任务框架已启动：%s 个 worker", MAX_WORKERS)


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


def _check_owner(row, current_user: dict) -> None:
    """任务归属校验：管理员可操作任意任务，普通用户仅限本人。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    if role == "admin":
        return
    if row["created_by"] != user:
        raise HTTPException(403, "无权访问该任务")


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
    task = create_task(task_type, payload, username=user, user_id=uid, role=role)
    return {"task_id": task["id"], "status": "pending", "message": "任务已提交，后台执行中", "task": task}


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
    current_user: dict = require_auth(),
):
    """任务列表（默认当前用户，按创建时间倒序）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    where, args = ["1=1"], []
    if role != "admin":
        where.append("created_by=?")
        args.append(user)
    if type.strip():
        where.append("type=?")
        args.append(type.strip())
    if status.strip():
        where.append("status=?")
        args.append(status.strip())
    conn = get_db()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            f"SELECT * FROM async_tasks WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?",
            args + [limit],
        ).fetchall()
    finally:
        conn.close()
    return {"tasks": [_row_to_task(r) for r in rows]}


@router.post("/{task_id}/retry")
async def retry_task_api(task_id: str, current_user: dict = require_auth()):
    """重试任务：failed / interrupted / canceled / success 均重置为 pending 重新执行。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _check_owner(task, current_user)
    with get_db_context() as conn:
        cur = conn.execute(
            """UPDATE async_tasks
               SET status='pending', progress=0, stage='任务已重新提交', result='', error='',
                   error_code=0, retry_count=retry_count+1, started_at='', finished_at=''
               WHERE id=? AND status IN ('pending','running')""",
            (task_id,),
        )
        # pending/running 中的任务不允许重试（避免重复执行）；其余终态可重试
        if cur.rowcount == 0:
            cur = conn.execute(
                """UPDATE async_tasks
                   SET status='pending', progress=0, stage='任务已重新提交', result='', error='',
                       error_code=0, retry_count=retry_count+1, started_at='', finished_at=''
                   WHERE id=?""",
                (task_id,),
            )
        conn.commit()
    return {"task_id": task_id, "status": "pending", "message": "任务已重新提交，后台执行中"}


@router.post("/{task_id}/cancel")
async def cancel_task_api(task_id: str, current_user: dict = require_auth()):
    """取消任务：仅排队中（pending）可取消。"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    _check_owner(task, current_user)
    with get_db_context() as conn:
        cur = conn.execute(
            "UPDATE async_tasks SET status='canceled', stage='已取消', finished_at=? WHERE id=? AND status='pending'",
            (datetime.now().isoformat(), task_id),
        )
        conn.commit()
    if not cur.rowcount:
        raise HTTPException(400, "仅排队中的任务可取消（执行中的任务请等待完成或重试）")
    return {"task_id": task_id, "status": "canceled", "message": "任务已取消"}
