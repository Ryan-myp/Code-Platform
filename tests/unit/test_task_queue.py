"""通用异步任务框架（task_queue）单元测试。

覆盖：创建/查询/执行/进度/失败/402 错误码/重试/取消/重启恢复/用户隔离。
直接调用 _run_handler 同步执行（不启动 master 线程，保证测试确定性）。
"""
import time
import asyncio

import pytest
from fastapi import HTTPException

from task_queue import (
    _handlers,
    _run_handler,
    cancel_task_api,
    create_task,
    get_task,
    recover_interrupted_tasks,
    register_handler,
    retry_task_api,
)


@pytest.fixture(autouse=True)
def _clean_handlers():
    """清理测试注册的处理器，避免跨测试污染。"""
    saved = dict(_handlers)
    yield
    _handlers.clear()
    _handlers.update(saved)


def _run(coro):
    """异步 API 端点同步调用（项目统一 asyncio.run 模式）。"""
    return asyncio.run(coro)


def _register_test_handler(**opts):
    """注册一个测试处理器：默认成功返回；可配置抛错/进度序列。"""
    def handler(task_id, payload, update, ctx):
        for pct, stage in opts.get("progress", [(30, "阶段一"), (70, "阶段二")]):
            update(pct, stage)
        if opts.get("raise_http"):
            raise HTTPException(opts["raise_http"], opts.get("error", "配额不足"))
        if opts.get("raise_generic"):
            raise RuntimeError(opts["raise_generic"])
        return {"echo": payload.get("v"), "ctx_user": ctx.get("username")}
    register_handler("tq_test", handler)
    return handler


class TestCreateAndRun:
    def test_create_pending_and_run_success(self, setup_test_db):
        _register_test_handler()
        task = create_task("tq_test", {"v": 1}, username="alice", user_id="u1", role="user")
        assert task["status"] == "pending"
        assert task["progress"] == 0
        # worker 执行
        _run_handler(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "success"
        assert got["progress"] == 100
        assert got["result"] == {"echo": 1, "ctx_user": "alice"}
        assert got["finished_at"]

    def test_progress_and_stage_persisted(self, setup_test_db):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        _run_handler(task["id"])
        got = get_task(task["id"])
        assert got["progress"] == 100
        assert got["stage"] == "生成完成"

    def test_unknown_type_rejected(self, setup_test_db):
        with pytest.raises(HTTPException) as exc:
            create_task("no_such_type", {}, username="alice")
        assert exc.value.status_code == 404

    def test_unknown_handler_marks_failed(self, setup_test_db):
        # 注册后删除处理器：任务存在但无 handler → failed
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        _handlers.pop("tq_test", None)
        _run_handler(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "failed"
        assert "未注册" in got["error"]


class TestFailure:
    def test_generic_exception_marks_failed(self, setup_test_db):
        _register_test_handler(raise_generic="boom")
        task = create_task("tq_test", {}, username="alice")
        _run_handler(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "failed"
        assert "boom" in got["error"]
        assert got["error_code"] == 0

    def test_http_402_records_error_code(self, setup_test_db):
        _register_test_handler(raise_http=402, error="今日次数已用完")
        task = create_task("tq_test", {}, username="alice")
        _run_handler(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "failed"
        assert got["error_code"] == 402
        assert "今日次数已用完" in got["error"]


class TestRetry:
    def test_failed_task_retry_resets_state(self, setup_test_db):
        _register_test_handler(raise_generic="第一次失败")
        task = create_task("tq_test", {}, username="alice")
        _run_handler(task["id"])
        assert get_task(task["id"])["status"] == "failed"
        # 重试：重置为 pending，计数 +1，错误清空
        _run(retry_task_api(task["id"], {"username": "alice", "role": "user"}))
        got = get_task(task["id"])
        assert got["status"] == "pending"
        assert got["retry_count"] == 1
        assert got["error"] == ""
        assert got["progress"] == 0
        # 重试后成功（换一个成功版处理器，直接替换避免重复注册报错）
        _handlers["tq_test"] = lambda task_id, payload, update, ctx: {"ok": True}
        _run_handler(task["id"])
        assert get_task(task["id"])["status"] == "success"

    def test_retry_owner_check(self, setup_test_db):
        _register_test_handler(raise_generic="x")
        task = create_task("tq_test", {}, username="alice")
        _run_handler(task["id"])
        with pytest.raises(HTTPException) as exc:
            _run(retry_task_api(task["id"], {"username": "bob", "role": "user"}))
        assert exc.value.status_code == 403


class TestCancel:
    def test_cancel_pending(self, setup_test_db):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        _run(cancel_task_api(task["id"], {"username": "alice", "role": "user"}))
        assert get_task(task["id"])["status"] == "canceled"

    def test_cancel_running_rejected(self, setup_test_db):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        import sqlite3
        from common.db import get_db
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(HTTPException) as exc2:
            _run(cancel_task_api(task["id"], {"username": "alice", "role": "user"}))
        assert exc2.value.status_code == 400


class TestRecovery:
    def test_running_tasks_marked_interrupted(self, setup_test_db):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        from common.db import get_db
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        n = recover_interrupted_tasks()
        assert n >= 1
        got = get_task(task["id"])
        assert got["status"] == "interrupted"
        assert "重启" in got["error"]
        # 未运行中的任务不受影响
        task2 = create_task("tq_test", {}, username="alice")
        assert get_task(task2["id"])["status"] == "pending"


class TestList:
    def test_user_isolation(self, setup_test_db):
        _register_test_handler()
        create_task("tq_test", {}, username="alice")
        create_task("tq_test", {}, username="bob")
        from task_queue import list_tasks_api
        alice_tasks = _run(list_tasks_api(type="tq_test", status="", limit=20,
                                          current_user={"username": "alice", "role": "user"}))
        assert len(alice_tasks["tasks"]) == 1
        # admin 可看全部
        admin_tasks = _run(list_tasks_api(type="tq_test", status="", limit=20,
                                          current_user={"username": "root", "role": "admin"}))
        assert len(admin_tasks["tasks"]) == 2

    def test_list_order_and_status_filter(self, setup_test_db):
        _register_test_handler()
        a = create_task("tq_test", {}, username="alice")
        time.sleep(0.01)
        b = create_task("tq_test", {}, username="alice")
        from task_queue import list_tasks_api
        tasks = _run(list_tasks_api(type="tq_test", status="", limit=20,
                                    current_user={"username": "alice", "role": "user"}))["tasks"]
        assert [t["id"] for t in tasks] == [b["id"], a["id"]]
        _run_handler(b["id"])
        done = _run(list_tasks_api(type="tq_test", status="success", limit=20,
                                   current_user={"username": "alice", "role": "user"}))["tasks"]
        assert len(done) == 1
        assert done[0]["id"] == b["id"]
