"""v15 用量分析增强单测：参数化筛选（区间/模块/用户）+ user_id 埋点。

覆盖：
- log_usage 写入 user_id 列（幂等补列）
- usage-stats：days 区间影响 daily_breakdown 窗口；module 筛选收窄统计
- usage-stats：user 筛选收窄统计但模块分布保留全貌
- usage-stats/users：去重用户列表（附用户名）
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _seed_usage(conn):
    """插入 3 类任务 × 2 用户 × 跨 30 天（含今天）的记录；digital_human 最多（most_used 稳定）。"""
    now = datetime.now()
    rows = []
    for task in ("assistant_chat", "digital_human", "prd_generate"):
        for uid in ("user_a", "user_b"):
            # 15 天前 2 条（在 30 天窗口内、7 天窗口外）；digital_human 额外 +2 成为最常用
            for _ in range(2 if task != "digital_human" else 4):
                ts = (now - timedelta(days=15)).isoformat()
                rows.append((ts, task, 100, 50, 1.0, 1, uid))
            # 1 天前 1 条（两个窗口内）
            ts2 = (now - timedelta(days=1)).isoformat()
            rows.append((ts2, task, 200, 100, 2.0, 1, uid))
            # 今天 1 条（今日统计用）
            rows.append((now.isoformat(), task, 200, 100, 2.0, 1, uid))
    conn.executemany(
        "INSERT INTO usage_logs (timestamp, task_type, input_length, output_length, response_time, success, user_id) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()


def _fake_request():
    """无 Authorization 头的假 Request（usage_stats 仅读取 headers）。"""
    return type("R", (), {"headers": {}})()


class TestLogUsageUserId:
    def test_writes_user_id(self, setup_test_db):
        from common.db import get_db
        from common.llm import log_usage

        log_usage("assistant_chat", 10, 20, 0.5, user_id="user_x")

        conn = get_db()
        row = conn.execute("SELECT * FROM usage_logs ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row["user_id"] == "user_x"
        assert row["task_type"] == "assistant_chat"

    def test_legacy_calls_still_work(self, setup_test_db):
        from common.db import get_db
        from common.llm import log_usage

        # 不带 user_id 的旧式调用不报错、user_id 为空
        log_usage("prd_generate", 10, 20, 0.5)

        conn = get_db()
        row = conn.execute("SELECT * FROM usage_logs ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        assert row["user_id"] == ""


class TestUsageStatsParams:
    def test_days_window(self, setup_test_db):
        from common.db import get_db
        from prd_engine import usage_stats

        _seed_usage(get_db())

        # 总览为累计（不受 days 窗口影响）；趋势图随窗口收窄
        r7 = asyncio.run(usage_stats(_fake_request(), days=7))
        r30 = asyncio.run(usage_stats(_fake_request(), days=30))
        assert r7["total_calls"] == 28
        assert r30["total_calls"] == 28
        assert len(r7["daily_breakdown"]) == 2
        assert len(r30["daily_breakdown"]) == 3

    def test_module_filter(self, setup_test_db):
        from common.db import get_db
        from prd_engine import usage_stats

        _seed_usage(get_db())

        r = asyncio.run(usage_stats(_fake_request(), days=30, module="digital_human"))
        assert r["total_calls"] == 12  # 仅 digital_human：2 用户 × 6 条
        # 模块分布不受 module 筛选影响（保留全部模块供占比展示）
        assert len(r["module_breakdown"]) == 3
        assert r["most_used"] == "digital_human"

    def test_user_filter(self, setup_test_db):
        from common.db import get_db
        from prd_engine import usage_stats

        _seed_usage(get_db())

        r = asyncio.run(usage_stats(_fake_request(), days=30, user="user_a"))
        assert r["total_calls"] == 14  # user_a：4+6+4 条
        # 今日统计也随筛选收窄
        assert r["today_calls"] == 3
        # 模块分布仍展示 user_a 的全部模块
        assert len(r["module_breakdown"]) == 3


class TestUsageStatsUsers:
    def test_users_list(self, setup_test_db):
        from common.db import get_db
        from prd_engine import usage_stats_users

        _seed_usage(get_db())

        # 两个测试用户不在 users 表，回退显示 user_id 本身
        users = asyncio.run(usage_stats_users(current_user={"user_id": "x"}))
        assert {u["id"] for u in users} == {"user_a", "user_b"}
        assert users[0]["username"] == users[0]["id"]

    def test_empty_returns_no_users(self, setup_test_db):
        from prd_engine import usage_stats_users

        users = asyncio.run(usage_stats_users(current_user={"user_id": "x"}))
        assert users == []
