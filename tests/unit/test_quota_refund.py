"""失败退费机制（商业公平：失败不扣费）单元测试。

覆盖：
- refund_quota 边界：正常退 / 0 下限 / admin / vip / 跨天 / total_usage 下限
- consume_quota 的 charged 标记（未真实扣费不触发退费）
- 任务最终失败退费（_mark_failed 路径）+ quota_refunded 幂等
- 402 失败不退费（未真实扣费）
- 手动重试计费：failed 重试重新扣费；interrupted/canceled 续跑不重复扣费
- 中间件失败响应退费（4xx 不消耗额度）
- 数字人扣费时序：参数/内容校验失败发生在扣费之前
"""

import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException

from common.auth import consume_quota, refund_quota
from common.db import get_db
from task_queue import _handlers, create_task, get_task, register_handler, retry_task_api


def _run(coro):
    """异步 API 端点同步调用（项目统一 asyncio.run 模式）。"""
    return asyncio.run(coro)


def _insert_user(username: str, role: str = "user", membership: str = "free", used: int = 0) -> str:
    """直接插入测试用户（绕过注册接口），返回 user_id。"""
    import uuid

    from common.auth import hash_password

    uid = f"u_{uuid.uuid4().hex[:8]}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, membership, used_today,
                                  last_quota_date, total_usage, bonus_quota)
               VALUES (?,?,?,?,?,?,?,?,0)""",
            (
                uid,
                username,
                hash_password("pass123456"),
                role,
                membership,
                used,
                datetime.now().strftime("%Y-%m-%d"),
                used,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return uid


def _used_today(uid: str) -> int:
    conn = get_db()
    try:
        row = conn.execute("SELECT used_today FROM users WHERE id=?", (uid,)).fetchone()
        return row[0] or 0
    finally:
        conn.close()


def _total_usage(uid: str) -> int:
    conn = get_db()
    try:
        row = conn.execute("SELECT total_usage FROM users WHERE id=?", (uid,)).fetchone()
        return row[0] or 0
    finally:
        conn.close()


def _register_failing_handler(task_type: str = "refund_test", error: Exception | None = None):
    """注册一个必然失败的处理器（可指定异常类型）。"""

    def handler(task_id, payload, update, ctx):
        if error is not None:
            raise error
        raise RuntimeError("boom")

    register_handler(task_type, handler)
    return handler


@pytest.fixture(autouse=True)
def _clean_handlers():
    """清理测试注册的处理器，避免跨测试污染。"""
    saved = dict(_handlers)
    yield
    _handlers.clear()
    _handlers.update(saved)


# ══════════════════════════════════════════════════════════════
# refund_quota 边界
# ══════════════════════════════════════════════════════════════


class TestRefundQuota:
    def test_normal_refund(self, setup_test_db):
        uid = _insert_user("refund_normal", used=3)
        assert refund_quota(uid) is True
        assert _used_today(uid) == 2
        assert _total_usage(uid) == 2

    def test_zero_used_no_refund(self, setup_test_db):
        uid = _insert_user("refund_zero", used=0)
        assert refund_quota(uid) is False
        assert _used_today(uid) == 0

    def test_admin_no_refund(self, setup_test_db):
        uid = _insert_user("refund_admin", role="admin", used=5)
        assert refund_quota(uid) is False
        assert _used_today(uid) == 5  # admin 本来就不扣，退费应无操作

    def test_vip_no_refund(self, setup_test_db):
        uid = _insert_user("refund_vip", membership="vip", used=8)
        assert refund_quota(uid) is False
        assert _used_today(uid) == 8

    def test_cross_day_no_refund(self, setup_test_db):
        """跨天后当日计数已重置，退费无法定位到具体某次扣减，不操作。"""
        uid = _insert_user("refund_crossday", used=3)
        conn = get_db()
        try:
            conn.execute("UPDATE users SET last_quota_date='2000-01-01' WHERE id=?", (uid,))
            conn.commit()
        finally:
            conn.close()
        assert refund_quota(uid) is False
        assert _used_today(uid) == 3

    def test_total_usage_floor(self, setup_test_db):
        """total_usage 不为负：与 used_today 联动时下限 0。"""
        uid = _insert_user("refund_floor", used=1)
        conn = get_db()
        try:
            conn.execute("UPDATE users SET total_usage=0 WHERE id=?", (uid,))
            conn.commit()
        finally:
            conn.close()
        assert refund_quota(uid) is True
        assert _total_usage(uid) == 0

    def test_missing_user_no_refund(self, setup_test_db):
        assert refund_quota("no_such_user") is False


class TestConsumeChargedFlag:
    def test_charged_flag_reflects_real_deduction(self, setup_test_db):
        """charged=False 的路径（admin/vip/额度不足）不触发退费。"""
        uid = _insert_user("charged_free", used=0)
        assert consume_quota(uid)["charged"] is True

        admin = _insert_user("charged_admin", role="admin", used=0)
        assert consume_quota(admin)["charged"] is False

        vip = _insert_user("charged_vip", membership="vip", used=0)
        assert consume_quota(vip)["charged"] is False

        # 额度耗尽：未扣费
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET used_today=30, last_quota_date=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d"), uid),
            )
            conn.commit()
        finally:
            conn.close()
        res = consume_quota(uid)
        assert res["allowed"] is False
        assert res["charged"] is False


# ══════════════════════════════════════════════════════════════
# 任务失败退费（task_queue 路径）
# ══════════════════════════════════════════════════════════════


class TestTaskFailureRefund:
    def _make_task(self, uid: str, task_type: str = "refund_test"):
        """创建任务并模拟 master 抢占为 running。"""
        _register_failing_handler(task_type)
        task = create_task(task_type, {}, username="alice", user_id=uid, role="user")
        conn = get_db()
        try:
            conn.execute(
                "UPDATE async_tasks SET status='running' WHERE id=?",
                (task["id"],),
            )
            conn.commit()
        finally:
            conn.close()
        return task

    def test_task_failure_refunds_quota(self, setup_test_db, claim_and_run):
        """提交时扣费 → 任务失败 → 当日额度回退 1 次。"""
        uid = _insert_user("taskfail_user", used=1)  # 模拟提交时中间件已扣 1 次
        task = self._make_task(uid)
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "failed"
        assert _used_today(uid) == 0
        assert _total_usage(uid) == 0

    def test_refund_idempotent_single_task(self, setup_test_db):
        """同一任务至多退费一次：quota_refunded 与状态转换原子置位。"""
        uid = _insert_user("taskfail_idem", used=1)
        task = self._make_task(uid)
        # 模拟 _run_handler 中的失败路径（等价于 claim_and_run 的执行结果）
        from task_queue import _mark_failed

        _mark_failed(task["id"], "boom", 0)
        assert _used_today(uid) == 0
        # 重复失败事件（如看门狗与 worker 竞态）：状态已非 running，不再退
        _mark_failed(task["id"], "boom again", 0)
        assert _used_today(uid) == 0

    def test_402_failure_no_refund(self, setup_test_db):
        """402 计费类错误：额度未真实扣减（consume 拒绝即返回），不退费。"""
        uid = _insert_user("taskfail_402", used=0)
        _register_failing_handler("refund_402", error=HTTPException(402, "额度不足"))
        task = create_task("refund_402", {}, username="alice", user_id=uid, role="user")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        from task_queue import _run_handler

        _run_handler(task["id"])
        assert get_task(task["id"])["error_code"] == 402
        assert _used_today(uid) == 0

    def test_failed_retry_charges_again(self, setup_test_db):
        """failed 任务重试 = 新一次执行：失败已退费，重试需重新扣费。"""
        uid = _insert_user("retry_charge", used=1)
        task = self._make_task(uid)
        from task_queue import _run_handler

        _run_handler(task["id"])
        assert _used_today(uid) == 0  # 失败已退费
        _run(retry_task_api(task["id"], {"username": "alice", "user_id": uid, "role": "user"}))
        assert get_task(task["id"])["status"] == "pending"
        assert _used_today(uid) == 1  # 重试重新扣费
        assert get_task(task["id"])["quota_refunded"] == 0  # 幂等标记已重置

    def test_retry_402_rejected(self, setup_test_db):
        """额度不足时重试被 402 拒绝，任务保持 failed。

        用 402 失败构造：计费类失败不退费，额度保持耗尽状态。
        """
        uid = _insert_user("retry_402", used=30)
        _register_failing_handler("refund_402_retry", error=HTTPException(402, "额度不足"))
        task = create_task("refund_402_retry", {}, username="alice", user_id=uid, role="user")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        from task_queue import _run_handler

        _run_handler(task["id"])
        assert get_task(task["id"])["status"] == "failed"
        assert _used_today(uid) == 30  # 402 未退费
        with pytest.raises(HTTPException) as exc:
            _run(retry_task_api(task["id"], {"username": "alice", "user_id": uid, "role": "user"}))
        assert exc.value.status_code == 402
        assert get_task(task["id"])["status"] == "failed"

    def test_interrupted_retry_no_charge(self, setup_test_db):
        """interrupted 重试 = 续跑（提交时已扣且未退费），不重复扣费。"""
        uid = _insert_user("retry_interrupted", used=1)
        _register_failing_handler("refund_interrupted")
        task = create_task("refund_interrupted", {}, username="alice", user_id=uid, role="user")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='interrupted' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        _run(retry_task_api(task["id"], {"username": "alice", "user_id": uid, "role": "user"}))
        assert get_task(task["id"])["status"] == "pending"
        assert _used_today(uid) == 1  # 不重复扣费

    def test_success_retry_charges_again(self, setup_test_db):
        """success 重试 = 再次生成新产物：重新扣费。"""
        uid = _insert_user("retry_success", used=1)

        def ok_handler(task_id, payload, update, ctx):
            return {"ok": True}

        register_handler("refund_success", ok_handler)
        task = create_task("refund_success", {}, username="alice", user_id=uid, role="user")
        conn = get_db()
        try:
            conn.execute("UPDATE async_tasks SET status='running' WHERE id=?", (task["id"],))
            conn.commit()
        finally:
            conn.close()
        from task_queue import _run_handler

        _run_handler(task["id"])
        assert get_task(task["id"])["status"] == "success"
        _run(retry_task_api(task["id"], {"username": "alice", "user_id": uid, "role": "user"}))
        assert _used_today(uid) == 2  # 成功重试重新扣费


# ══════════════════════════════════════════════════════════════
# 中间件失败响应退费（集成）
# ══════════════════════════════════════════════════════════════


class TestMiddlewareRefund:
    def test_4xx_response_refunds(self, test_db_path):
        """请求失败（参数校验 422）不消耗额度：提交即扣，失败即退。"""
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        resp = client.post("/api/auth/register", json={"username": "mid_refund", "password": "pass123456"})
        assert resp.status_code in (200, 201), resp.text
        resp = client.post("/api/auth/login", json={"username": "mid_refund", "password": "pass123456"})
        headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        # 成功请求扣 1 次
        resp = client.post("/api/meme/generate", data={"top_text": "正常", "style": "yellow"}, headers=headers)
        assert resp.status_code == 200, resp.text
        conn = get_db()
        try:
            row = conn.execute("SELECT id FROM users WHERE username='mid_refund'").fetchone()
            uid = row[0]
        finally:
            conn.close()
        assert _used_today(uid) == 1

        # 缺参数 → 422：中间件自动退费
        resp = client.post("/api/meme/generate", data={}, headers=headers)
        assert resp.status_code >= 400, resp.text
        assert _used_today(uid) == 1  # 退费后回到 1（失败请求未消耗）

    def test_admin_failure_no_refund_impact(self, test_db_path, auth_headers):
        """admin 不扣费，失败响应也不会误触发退费（charged=False）。"""
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        resp = client.post("/api/meme/generate", data={}, headers=auth_headers)
        assert resp.status_code >= 400, resp.text
        conn = get_db()
        try:
            row = conn.execute("SELECT used_today FROM users WHERE username='admin'").fetchone()
            assert row[0] == 0
        finally:
            conn.close()


# ══════════════════════════════════════════════════════════════
# 数字人扣费时序
# ══════════════════════════════════════════════════════════════


class TestDigitalHumanTiming:
    def test_invalid_avatar_not_charged(self, setup_test_db):
        """参数校验失败发生在扣费之前：未知形象 400 不消耗额度。"""
        from digital_human import _generate_one

        uid = _insert_user("dh_timing", used=0)

        class Req:
            text = "正常文案"
            avatar_id = "no_such_avatar"
            voice_id = "voice_1"
            background_id = "bg_1"
            speed = 1.0
            watermark = False

        with pytest.raises(HTTPException) as exc:
            _generate_one(Req(), user="alice", uid=uid, role="user")
        assert exc.value.status_code == 400
        assert _used_today(uid) == 0  # 未扣费

    def test_hard_block_word_not_charged(self, setup_test_db):
        """内容安全拦截发生在扣费之前：违规词 400 不消耗额度。"""
        from digital_human import _generate_one

        uid = _insert_user("dh_blockword", used=0)

        class Req:
            text = "免费领取"  # 广告法极限词/硬违规词
            avatar_id = "avatar_1"
            voice_id = "voice_1"
            background_id = "bg_1"
            speed = 1.0
            watermark = False

        with pytest.raises(HTTPException) as exc:
            _generate_one(Req(), user="alice", uid=uid, role="user")
        assert exc.value.status_code == 400
        assert _used_today(uid) == 0  # 未扣费
