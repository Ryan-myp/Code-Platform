"""v15 定时任务增强单测：cron 解析边界 / 重试逻辑 / 任务执行分发 / 手动触发。

覆盖：
- _parse_cron：`*`、`*/n` 步进、`a,b` 枚举、weekday 0=周一、非法表达式、不可达日期（2月30日）
- _run_with_retry：首次成功不重试 / 失败后重试成功 / 全部失败返回聚合错误
- _execute_job：report 统计 / notify 站内信落库
- trigger_job：手动触发真正执行并落库运行历史；非法 cron 创建被拒
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


@pytest.fixture(autouse=True)
def _ensure_scheduler_tables(setup_test_db):
    """scheduler 模块可能已在旧库上建表，这里对测试库幂等补建。"""
    from scheduler import _ensure_table

    _ensure_table()


def _insert_job(conn, job_id=1, name="每日报告", job_type="report", cron="0 9 * * *", user_id=1):
    conn.execute(
        """INSERT INTO scheduler_jobs (id, user_id, name, job_type, cron_expression, next_run, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (job_id, user_id, name, job_type, cron, None, "2026-01-01T00:00:00", "2026-01-01T00:00:00"),
    )
    conn.commit()


class TestParseCron:
    def test_every_minute(self):
        from scheduler import _parse_cron

        now = datetime(2026, 8, 3, 10, 30, 15)
        res = _parse_cron("* * * * *", now=now)
        assert res == "2026-08-03T10:31:00"

    def test_step_minutes(self):
        from scheduler import _parse_cron

        now = datetime(2026, 8, 3, 10, 7, 0)
        res = _parse_cron("*/15 * * * *", now=now)
        assert res == "2026-08-03T10:15:00"

    def test_enum_minutes(self):
        from scheduler import _parse_cron

        now = datetime(2026, 8, 3, 10, 40, 0)
        res = _parse_cron("0,30 * * * *", now=now)
        assert res == "2026-08-03T11:00:00"

    def test_weekday_monday(self):
        from scheduler import _parse_cron

        now = datetime(2026, 8, 3, 10, 0, 0)  # 2026-08-03 为周一
        assert now.weekday() == 0
        # 当天 9 点已过 → 下一个周一 9:00
        res = _parse_cron("0 9 * * 1", now=now)
        assert res is not None
        nxt = datetime.fromisoformat(res)
        assert nxt.weekday() == 0 and nxt.hour == 9 and nxt.minute == 0
        assert 0 < (nxt - now).days <= 7

    def test_weekday_before_time_same_day(self):
        from scheduler import _parse_cron

        now = datetime(2026, 8, 3, 8, 0, 0)  # 周一早上 8 点，9 点未到 → 当天 9:00
        res = _parse_cron("0 9 * * 1", now=now)
        assert res == "2026-08-03T09:00:00"

    def test_invalid_expression(self):
        from scheduler import _parse_cron

        for bad in ["* * * *", "* * * * * *", "61 * * * *", "0 24 * * *", "0 9 * * 8", "abc * * * *", ""]:
            assert _parse_cron(bad) is None, bad

    def test_unreachable_day_returns_none(self):
        from scheduler import _parse_cron

        # 2 月 30 日不存在 → 400 天窗口内找不到匹配点
        now = datetime(2026, 1, 1, 0, 0, 0)
        assert _parse_cron("0 0 30 2 *", now=now) is None


class TestRunWithRetry:
    def test_success_first_try_no_sleep(self):
        from scheduler import _run_with_retry

        calls = []
        with patch("scheduler.time.sleep") as sleep:
            ok, out = _run_with_retry(lambda: (calls.append(1) or (True, "done")))
        assert ok and out == "done"
        assert len(calls) == 1
        sleep.assert_not_called()

    def test_retry_until_success(self):
        from scheduler import _run_with_retry

        calls = {"n": 0}
        with patch("scheduler.time.sleep") as sleep:
            ok, out = _run_with_retry(
                lambda: (calls.__setitem__("n", calls["n"] + 1), (True, "ok"))[1] if calls["n"] >= 2 else (
                    calls.__setitem__("n", calls["n"] + 1), (False, "boom"))[1]
            )
        assert ok
        assert calls["n"] == 3
        # 指数退避：第一次重试 sleep 2s，第二次 4s
        assert sleep.call_count == 2
        delays = [c.args[0] for c in sleep.call_args_list]
        assert delays == [2.0, 4.0]

    def test_all_fail_aggregates_error(self):
        from scheduler import _run_with_retry

        calls = {"n": 0}
        with patch("scheduler.time.sleep"):
            ok, out = _run_with_retry(lambda: (calls.__setitem__("n", calls["n"] + 1), (False, "oops"))[1])
        assert not ok
        assert calls["n"] == 3
        assert "重试 3 次仍失败" in out and "oops" in out


class TestExecuteJob:
    def test_report_job_returns_summary(self, setup_test_db):
        from common.db import get_db
        from scheduler import _execute_job

        conn = get_db()
        _insert_job(conn)
        conn.close()

        ok, out = _execute_job({"job_type": "report", "name": "每日报告", "user_id": 1})
        assert ok
        assert "调度自检报告" in out and "1 个任务" in out

    def test_notify_job_writes_inbox(self, setup_test_db):
        from common.db import get_db
        from scheduler import _execute_job

        conn = get_db()
        # admin 用户由 init_db seed，notifications.user_id 存 username
        admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        _insert_job(conn, job_type="notify", user_id=admin["id"])
        conn.close()

        ok, out = _execute_job({"job_type": "notify", "name": "提醒", "user_id": admin["id"]})
        assert ok and out == "站内信已发送"

        conn = get_db()
        row = conn.execute("SELECT * FROM notifications ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        assert row is not None
        assert row["type"] == "system" and row["user_id"] == "admin"
        assert row["read"] == 0
        assert "提醒" in row["title"]

    def test_notify_job_unknown_user_falls_back_all(self, setup_test_db):
        from common.db import get_db
        from scheduler import _execute_job

        ok, out = _execute_job({"job_type": "notify", "name": "x", "user_id": 999})
        assert ok

        conn = get_db()
        row = conn.execute("SELECT * FROM notifications ORDER BY rowid DESC LIMIT 1").fetchone()
        conn.close()
        assert row["user_id"] == "all"

    def test_unknown_job_type_falls_back_to_report(self, setup_test_db):
        from scheduler import _execute_job

        ok, out = _execute_job({"job_type": "sync", "name": "x", "user_id": 1})
        assert ok and "调度自检报告" in out


class TestTriggerJob:
    def test_trigger_executes_and_records_history(self, setup_test_db):
        from common.db import get_db
        from scheduler import trigger_job

        conn = get_db()
        _insert_job(conn)
        conn.close()

        result = trigger_job(1, current_user={"user_id": 1})
        assert result["status"] == "success"
        assert "执行成功" in result["message"]
        assert "调度自检报告" in result["output"]

        conn = get_db()
        row = conn.execute("SELECT * FROM scheduler_runs WHERE job_id=1").fetchone()
        job = conn.execute("SELECT last_status, last_run FROM scheduler_jobs WHERE id=1").fetchone()
        conn.close()
        assert row is not None and row["status"] == "success"
        assert job["last_status"] == "success" and job["last_run"]

    def test_trigger_not_found(self, setup_test_db):
        from scheduler import trigger_job

        with pytest.raises(HTTPException) as ei:
            trigger_job(999, current_user={"user_id": 1})
        assert ei.value.status_code == 404

    def test_list_runs_returns_history(self, setup_test_db):
        from common.db import get_db
        from scheduler import list_job_runs, trigger_job

        conn = get_db()
        _insert_job(conn)
        conn.close()
        trigger_job(1, current_user={"user_id": 1})

        runs = list_job_runs(1, current_user={"user_id": 1})
        assert len(runs) == 1
        assert runs[0]["status"] == "success"

    def test_list_runs_not_found(self, setup_test_db):
        from scheduler import list_job_runs

        with pytest.raises(HTTPException) as ei:
            list_job_runs(999, current_user={"user_id": 1})
        assert ei.value.status_code == 404

    def test_create_job_rejects_invalid_cron(self, setup_test_db):
        from scheduler import create_job

        with pytest.raises(HTTPException) as ei:
            create_job({"name": "bad", "cron_expression": "99 9 * * *"}, current_user={"user_id": 1})
        assert ei.value.status_code == 400
        assert "非法" in ei.value.detail

    def test_create_job_sets_next_run(self, setup_test_db):
        from scheduler import create_job

        result = create_job({"name": "ok", "cron_expression": "0 9 * * *"}, current_user={"user_id": 1})
        assert result["next_run"]
        nxt = datetime.fromisoformat(result["next_run"])
        assert nxt.hour == 9 and nxt.minute == 0
