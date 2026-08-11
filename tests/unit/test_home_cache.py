"""v17-F 首页热接口短 TTL 缓存单测：命中 / 过期失效 / SQL 执行次数。

覆盖：
- _home_cache_get/_home_cache_set 基本读写与 TTL 过期
- /api/home/stats：TTL 内第二次调用不再执行 SQL（8 个 COUNT 只跑一次）
- /api/home/recent：真实库下正常返回结构与缓存复用
"""

import asyncio
import sys
import time as real_time
from pathlib import Path
from types import SimpleNamespace

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import platform_api  # noqa: E402


def _reset_cache():
    platform_api._HOME_CACHE.clear()


class FakeRow:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return (self.value,)

    def keys(self):
        return []


class FakeConn:
    """记录 execute 调用次数的假连接（stats 接口只用 fetchone）。"""

    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append(sql)
        return FakeRow(1)

    def close(self):
        pass


def _fake_db(log_conn):
    def factory():
        return log_conn

    return factory


class TestHomeCacheUnit:
    def test_set_then_get_hits(self):
        _reset_cache()
        platform_api._home_cache_set("stats", {"agents": 3})
        assert platform_api._home_cache_get("stats") == {"agents": 3}

    def test_missing_key_returns_none(self):
        _reset_cache()
        assert platform_api._home_cache_get("nope") is None

    def test_expired_entry_misses(self, monkeypatch):
        _reset_cache()
        platform_api._home_cache_set("stats", {"agents": 3})
        # 替换 platform_api 模块的 time 引用为拨快的时钟（不触碰全局 time 模块）
        monkeypatch.setattr(platform_api, "time", SimpleNamespace(time=lambda: real_time.time() + 60))
        assert platform_api._home_cache_get("stats") is None


class TestHomeStatsCache:
    def test_first_call_runs_sql_second_hits_cache(self, monkeypatch):
        _reset_cache()
        conn = FakeConn()
        monkeypatch.setattr(platform_api, "get_db", _fake_db(conn))

        first = asyncio.run(platform_api.get_home_stats(current_user={"user_id": "u1"}))
        assert len(conn.calls) == 8  # 8 个 COUNT
        assert first["agents"] == 1

        second = asyncio.run(platform_api.get_home_stats(current_user={"user_id": "u1"}))
        assert second == first  # 缓存命中返回同一结果
        assert len(conn.calls) == 8  # 未再执行 SQL

    def test_cache_expiry_re_runs_sql(self, monkeypatch):
        _reset_cache()
        conn = FakeConn()
        monkeypatch.setattr(platform_api, "get_db", _fake_db(conn))

        asyncio.run(platform_api.get_home_stats(current_user={"user_id": "u1"}))
        monkeypatch.setattr(platform_api, "time", SimpleNamespace(time=lambda: real_time.time() + 60))
        asyncio.run(platform_api.get_home_stats(current_user={"user_id": "u1"}))
        assert len(conn.calls) == 16  # 过期后重新执行


class TestHomeRecentCache:
    def test_returns_expected_structure_and_reuses_cache(self, setup_test_db):
        _reset_cache()
        first = asyncio.run(platform_api.get_home_recent(current_user={"user_id": "u1"}))
        assert set(first.keys()) == {"tasks", "projects", "notifications", "requirements", "pipelines"}

        second = asyncio.run(platform_api.get_home_recent(current_user={"user_id": "u1"}))
        assert second == first  # 缓存命中，结构一致
