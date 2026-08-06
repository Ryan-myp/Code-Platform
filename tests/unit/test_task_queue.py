"""通用异步任务框架（task_queue）单元测试。

覆盖：创建/查询/执行/进度/失败/402 错误码/重试/取消/重启恢复/用户隔离/分页。
使用 claim_and_run 模拟 master 抢占（pending→running）后由 worker 执行，保证测试确定性。
"""

import asyncio
import time

import pytest
from fastapi import HTTPException

from common.db import get_db
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
    """清理测试注册的处理器与进度节流缓存，避免跨测试污染。"""
    from task_queue import _progress_throttle

    saved = dict(_handlers)
    _progress_throttle.clear()
    yield
    _handlers.clear()
    _handlers.update(saved)
    _progress_throttle.clear()


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
    def test_create_pending_and_run_success(self, setup_test_db, claim_and_run):
        _register_test_handler()
        task = create_task("tq_test", {"v": 1}, username="alice", user_id="u1", role="user")
        assert task["status"] == "pending"
        assert task["progress"] == 0
        # worker 执行（模拟 master 抢占后运行）
        claim_and_run(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "success"
        assert got["progress"] == 100
        assert got["result"] == {"echo": 1, "ctx_user": "alice"}
        assert got["finished_at"]

    def test_progress_and_stage_persisted(self, setup_test_db, claim_and_run):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
        got = get_task(task["id"])
        assert got["progress"] == 100
        assert got["stage"] == "生成完成"

    def test_unknown_type_rejected(self, setup_test_db):
        with pytest.raises(HTTPException) as exc:
            create_task("no_such_type", {}, username="alice")
        assert exc.value.status_code == 404

    def test_unknown_handler_marks_failed(self, setup_test_db, claim_and_run):
        # 注册后删除处理器：任务存在但无 handler → failed
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        _handlers.pop("tq_test", None)
        claim_and_run(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "failed"
        assert "未注册" in got["error"]

    def test_started_at_refreshed_on_worker_start(self, setup_test_db, claim_and_run):
        """看门狗精准化：worker 真正开始执行时刷新 started_at（队列等待不计入超时）。"""
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        conn = get_db()
        try:
            # 模拟抢占时写入旧 started_at（内存队列等待）
            conn.execute(
                "UPDATE async_tasks SET status='running', started_at=? WHERE id=?",
                ("2020-01-01T00:00:00", task["id"]),
            )
            conn.commit()
        finally:
            conn.close()
        claim_and_run(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "success"
        assert got["started_at"] > "2020-01-01T00:00:00"


class TestFailure:
    def test_generic_exception_marks_failed(self, setup_test_db, claim_and_run):
        _register_test_handler(raise_generic="boom")
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "failed"
        assert "boom" in got["error"]
        assert got["error_code"] == 0

    def test_http_402_records_error_code(self, setup_test_db, claim_and_run):
        _register_test_handler(raise_http=402, error="今日次数已用完")
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
        got = get_task(task["id"])
        assert got["status"] == "failed"
        assert got["error_code"] == 402
        assert "今日次数已用完" in got["error"]


class TestRetry:
    def test_failed_task_retry_resets_state(self, setup_test_db, claim_and_run):
        _register_test_handler(raise_generic="第一次失败")
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
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
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"

    def test_retry_owner_check(self, setup_test_db, claim_and_run):
        _register_test_handler(raise_generic="x")
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
        with pytest.raises(HTTPException) as exc:
            _run(retry_task_api(task["id"], {"username": "bob", "role": "user"}))
        assert exc.value.status_code == 403


class TestCancel:
    def test_cancel_pending(self, setup_test_db):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        _run(cancel_task_api(task["id"], {"username": "alice", "role": "user"}))
        assert get_task(task["id"])["status"] == "canceled"

    def test_cancel_running_sets_cancel_requested(self, setup_test_db):
        """执行中任务可请求取消：置 cancel_requested 标志，worker 下次进度回调自检中止。"""
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        _run(cancel_task_api(task["id"], {"username": "alice", "role": "user"}))
        got = get_task(task["id"])
        assert got["status"] == "canceled"
        assert got["cancel_requested"] == 1

    def test_retry_running_rejected(self, setup_test_db):
        """执行中任务禁止重试：重置为 pending 会与新 worker 双跑。"""
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(HTTPException) as exc:
            _run(retry_task_api(task["id"], {"username": "alice", "role": "user"}))
        assert exc.value.status_code == 400

    def test_cancel_before_worker_start_skips_handler(self, setup_test_db):
        """取消竞态：master 抢占后、worker 启动前取消，worker 不执行 handler（防消耗配额）。"""
        calls = {"n": 0}

        def handler(task_id, payload, update, ctx):
            calls["n"] += 1
            return {"ok": True}

        register_handler("tq_test", handler)
        task = create_task("tq_test", {}, username="alice")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        # 抢占后用户取消（status→canceled + cancel_requested=1）
        _run(cancel_task_api(task["id"], {"username": "alice", "role": "user"}))
        _run_handler(task["id"])
        assert calls["n"] == 0
        assert get_task(task["id"])["status"] == "canceled"


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

        alice_tasks = _run(
            list_tasks_api(
                type="tq_test", status="", limit=20, offset=0, current_user={"username": "alice", "role": "user"}
            )
        )
        assert len(alice_tasks["tasks"]) == 1
        # admin 可看全部
        admin_tasks = _run(
            list_tasks_api(
                type="tq_test", status="", limit=20, offset=0, current_user={"username": "root", "role": "admin"}
            )
        )
        assert len(admin_tasks["tasks"]) == 2

    def test_list_order_and_status_filter(self, setup_test_db, claim_and_run):
        _register_test_handler()
        a = create_task("tq_test", {}, username="alice")
        time.sleep(0.01)
        b = create_task("tq_test", {}, username="alice")
        from task_queue import list_tasks_api

        tasks = _run(
            list_tasks_api(
                type="tq_test", status="", limit=20, offset=0, current_user={"username": "alice", "role": "user"}
            )
        )["tasks"]
        assert [t["id"] for t in tasks] == [b["id"], a["id"]]
        claim_and_run(b["id"])
        done = _run(
            list_tasks_api(
                type="tq_test", status="success", limit=20, offset=0, current_user={"username": "alice", "role": "user"}
            )
        )["tasks"]
        assert len(done) == 1
        assert done[0]["id"] == b["id"]

    def test_list_pagination(self, setup_test_db):
        """分页：返回 total 总数，offset 翻页无重复。"""
        _register_test_handler()
        for i in range(3):
            create_task("tq_test", {"i": i}, username="alice")
        from task_queue import list_tasks_api

        page1 = _run(
            list_tasks_api(type="", status="", limit=2, offset=0, current_user={"username": "alice", "role": "user"})
        )
        assert page1["total"] == 3
        assert len(page1["tasks"]) == 2
        page2 = _run(
            list_tasks_api(type="", status="", limit=2, offset=2, current_user={"username": "alice", "role": "user"})
        )
        assert page2["total"] == 3
        assert len(page2["tasks"]) == 1
        ids = [t["id"] for t in page1["tasks"]] + [t["id"] for t in page2["tasks"]]
        assert len(set(ids)) == 3


class TestDelete:
    def test_delete_terminal_task(self, setup_test_db, claim_and_run):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"
        from task_queue import delete_task_api

        resp = _run(delete_task_api(task["id"], {"username": "alice", "role": "user"}))
        assert resp["task_id"] == task["id"]
        assert get_task(task["id"]) is None

    def test_delete_running_rejected(self, setup_test_db):
        """执行中任务禁止删除：先取消或等待完成（防止删除后 worker 迟到结果落库异常）。"""
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        from task_queue import delete_task_api

        with pytest.raises(HTTPException) as exc:
            _run(delete_task_api(task["id"], {"username": "alice", "role": "user"}))
        assert exc.value.status_code == 400
        assert get_task(task["id"])["status"] == "running"

    def test_delete_owner_check(self, setup_test_db, claim_and_run):
        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        claim_and_run(task["id"])
        from task_queue import delete_task_api

        with pytest.raises(HTTPException) as exc:
            _run(delete_task_api(task["id"], {"username": "bob", "role": "user"}))
        assert exc.value.status_code == 403

    def test_cleanup_only_terminal(self, setup_test_db):
        """清空只删终态：pending/running 保留，且按用户隔离。"""
        _register_test_handler()
        pending = create_task("tq_test", {}, username="alice")
        done = create_task("tq_test", {}, username="alice")
        bob_done = create_task("tq_test", {}, username="bob")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='success' WHERE id IN (?,?)", (done["id"], bob_done["id"]))
            conn.commit()
        finally:
            conn.close()
        from task_queue import cleanup_tasks_api

        resp = _run(cleanup_tasks_api({"username": "alice", "role": "user"}))
        assert resp["deleted"] == 1  # 只删 alice 自己的终态任务
        assert get_task(done["id"]) is None
        assert get_task(pending["id"])["status"] == "pending"  # 排队中保留
        assert get_task(bob_done["id"])["status"] == "success"  # 他人任务不受影响


class TestPayloadLimit:
    def test_payload_too_large_rejected(self, setup_test_db):
        """任务参数序列化后超过 256KB 拒绝创建（防恶意大字段入库）。"""
        _register_test_handler()
        with pytest.raises(HTTPException) as exc:
            create_task("tq_test", {"big": "x" * (256 * 1024)}, username="alice")
        assert exc.value.status_code == 400
        # 边界内正常创建
        task = create_task("tq_test", {"v": "ok"}, username="alice")
        assert get_task(task["id"])["status"] == "pending"


class TestStatsCache:
    def test_stats_route_not_shadowed_by_task_id(self, setup_test_db, auth_headers):
        """HTTP 层回归：GET /api/tasks/stats 不能被 /{task_id} 通配路由吞掉（浏览器验证暴露）。"""
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        resp = client.get("/api/tasks/stats", headers=auth_headers)
        assert resp.status_code == 200, f"stats route shadowed: {resp.status_code} {resp.text}"
        body = resp.json()
        assert "total" in body and "active" in body

    def test_stats_cached_within_ttl(self, setup_test_db):
        """stats 30s TTL 缓存：窗口内不重算，清缓存后恢复实时。"""
        from task_queue import _stats_cache, task_stats_api

        _register_test_handler()
        create_task("tq_test", {}, username="alice")
        _stats_cache.clear()
        first = _run(task_stats_api(current_user={"username": "alice", "role": "user"}))
        assert first["total"] == 1
        # 缓存窗口内新增任务：统计仍返回缓存旧值
        create_task("tq_test", {}, username="alice")
        second = _run(task_stats_api(current_user={"username": "alice", "role": "user"}))
        assert second["total"] == 1
        # 清缓存后重新统计
        _stats_cache.clear()
        third = _run(task_stats_api(current_user={"username": "alice", "role": "user"}))
        assert third["total"] == 2


class TestProgressThrottle:
    def _make_running(self, task_id):
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task_id,))
            conn.commit()
        finally:
            conn.close()

    def test_redundant_updates_skipped(self, setup_test_db):
        """进度节流：500ms 内且变化 <2 且阶段未变时跳过落库；变化 ≥2 立即落库。"""
        from task_queue import _update_progress

        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        self._make_running(task["id"])
        _update_progress(task["id"], 10, "阶段A")
        _update_progress(task["id"], 11, "阶段A")  # 节流跳过
        assert get_task(task["id"])["progress"] == 10
        _update_progress(task["id"], 15, "阶段A")  # 变化 ≥2 → 落库
        assert get_task(task["id"])["progress"] == 15

    def test_stage_change_flushes_immediately(self, setup_test_db):
        """阶段文案变化立即落库（用户可感知的阶段跳变不延迟）。"""
        from task_queue import _update_progress

        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        self._make_running(task["id"])
        _update_progress(task["id"], 30, "阶段A")
        _update_progress(task["id"], 31, "阶段B")  # stage 变化 → 立即落库
        got = get_task(task["id"])
        assert got["progress"] == 31
        assert got["stage"] == "阶段B"

    def test_cancel_check_not_throttled(self, setup_test_db):
        """节流不削弱取消检测：取消后即使节流窗口内，进度回调也立即抛 TaskCanceled。"""
        from task_queue import TaskCanceled, _update_progress

        _register_test_handler()
        task = create_task("tq_test", {}, username="alice")
        self._make_running(task["id"])
        _update_progress(task["id"], 40, "阶段A")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='canceled', cancel_requested=1 WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        with pytest.raises(TaskCanceled):
            _update_progress(task["id"], 41, "阶段A")
