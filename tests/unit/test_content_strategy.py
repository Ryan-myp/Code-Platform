"""v15 内容策略增强单测：内容日历聚合 + 主题库标签筛选。

覆盖：
- build_calendar：月份边界（2月天数）、排期/已发布分组、跨月数据忽略、topics JSON 串兼容
- _month_bounds：非法月份回退当月
- filter_topics：标签/分类/关键词/组合筛选
- aggregate_tags：标签聚合计数与排序
- 主题库端点：创建/列表筛选/更新/删除落库断言
- calendar 端点：publish_schedules + publish_records + publish_metrics 聚合
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


# ══════════════════════════════════════════════════════════════
# build_calendar 纯函数
# ══════════════════════════════════════════════════════════════


class TestBuildCalendar:
    def test_month_bounds_feb(self):
        from content_strategy import build_calendar

        out = build_calendar("2026-02", [], [])
        assert out["month"] == "2026-02"
        assert out["day_count"] == 28  # 2026 非闰年
        assert out["first_weekday"] == 6  # 2026-02-01 是周日（周一=0）
        assert out["days"] == {}
        assert out["summary"] == {"scheduled": 0, "published": 0}

    def test_month_bounds_leap_feb(self):
        from content_strategy import build_calendar

        assert build_calendar("2024-02", [], [])["day_count"] == 29  # 闰年

    def test_group_schedules_and_records(self):
        from content_strategy import build_calendar

        schedules = [
            {"id": "s1", "title": "周三排期", "platform": "wechat", "content_type": "article",
             "status": "pending", "scheduled_at": "2026-08-05T10:30:00", "topics": '["AI"]'},
            {"id": "s2", "title": "周末排期", "platform": "douyin", "content_type": "video",
             "status": "published", "scheduled_at": "2026-08-08T20:00:00", "topics": []},
        ]
        records = [
            {"id": "r1", "title": "已发布文章", "platform": "wechat", "content_type": "article",
             "status": "success", "created_at": "2026-08-05T09:00:00", "views": 120, "likes": 8, "comments": 2},
        ]
        out = build_calendar("2026-08", schedules, records)
        assert out["summary"] == {"scheduled": 2, "published": 1}

        day05 = out["days"]["2026-08-05"]
        assert len(day05["schedules"]) == 1
        assert len(day05["records"]) == 1
        assert day05["total"] == 2
        assert day05["schedules"][0]["time"] == "10:30"
        assert day05["schedules"][0]["topics"] == ["AI"]  # JSON 串已解析
        assert day05["records"][0]["views"] == 120
        assert day05["records"][0]["kind"] == "record"

        day08 = out["days"]["2026-08-08"]
        assert day08["total"] == 1
        assert day08["schedules"][0]["status"] == "published"

    def test_out_of_month_ignored(self):
        from content_strategy import build_calendar

        schedules = [
            {"id": "s1", "scheduled_at": "2026-07-31T10:00:00"},
            {"id": "s2", "scheduled_at": "2026-08-01T10:00:00"},
            {"id": "s3", "scheduled_at": "2026-09-01T10:00:00"},
        ]
        records = [{"id": "r1", "created_at": "2026-08-15T08:00:00"}, {"id": "r2", "created_at": "bad-date"}]
        out = build_calendar("2026-08", schedules, records)
        assert out["summary"] == {"scheduled": 1, "published": 1}
        assert "2026-08-01" in out["days"]
        assert "2026-07-31" not in out["days"]
        assert "2026-09-01" not in out["days"]

    def test_invalid_month_falls_back_to_current(self):
        from datetime import datetime

        from content_strategy import build_calendar

        out = build_calendar("2026-13", [], [])
        assert out["month"] == datetime.now().strftime("%Y-%m")
        out2 = build_calendar("abc", [], [])
        assert out2["month"] == datetime.now().strftime("%Y-%m")

    def test_empty_and_none_inputs(self):
        from content_strategy import build_calendar

        out = build_calendar("2026-08", None, None)
        assert out["summary"] == {"scheduled": 0, "published": 0}
        assert out["days"] == {}


class TestFilterTopics:
    def test_tag_filter_case_insensitive(self):
        from content_strategy import filter_topics

        topics = [
            {"name": "A", "tags": ["AI", "效率"]},
            {"name": "B", "tags": ["情感"]},
        ]
        assert [t["name"] for t in filter_topics(topics, tag="ai")] == ["A"]
        assert [t["name"] for t in filter_topics(topics, tag="AI")] == ["A"]
        assert len(filter_topics(topics, tag="不存在")) == 0

    def test_category_and_keyword(self):
        from content_strategy import filter_topics

        topics = [
            {"name": "AI提效", "description": "用工具提升写作效率", "category": "干货", "tags": ["AI"]},
            {"name": "热点解读", "description": "追踪行业动态", "category": "热点", "tags": []},
        ]
        assert len(filter_topics(topics, category="干货")) == 1
        assert len(filter_topics(topics, category="热点", keyword="行业")) == 1
        assert len(filter_topics(topics, keyword="写作")) == 1  # 命中 description
        assert len(filter_topics(topics, keyword="")) == 2

    def test_combined_filters(self):
        from content_strategy import filter_topics

        topics = [
            {"name": "AI教程", "tags": ["AI", "教程"], "category": "教程"},
            {"name": "AI观点", "tags": ["AI"], "category": "观点"},
        ]
        assert len(filter_topics(topics, tag="教程")) == 1
        assert len(filter_topics(topics, tag="AI", category="观点")) == 1
        assert len(filter_topics(topics, tag="AI", category="教程", keyword="教程")) == 1
        assert len(filter_topics(topics, tag="AI", category="干货")) == 0

    def test_none_and_missing_fields(self):
        from content_strategy import filter_topics

        assert filter_topics(None) == []
        assert filter_topics([{"name": "A"}, {"tags": None}], tag="x") == []
        assert len(filter_topics([{"name": "A"}, {"tags": None}])) == 2


class TestAggregateTags:
    def test_counts_sorted_desc(self):
        from content_strategy import aggregate_tags

        topics = [
            {"tags": ["AI", "效率"]},
            {"tags": ["AI", "写作"]},
            {"tags": ["效率"]},
        ]
        out = aggregate_tags(topics)
        assert out == [{"tag": "AI", "count": 2}, {"tag": "效率", "count": 2}, {"tag": "写作", "count": 1}]

    def test_empty_and_blank_tags_skipped(self):
        from content_strategy import aggregate_tags

        assert aggregate_tags([]) == []
        assert aggregate_tags([{"tags": ["  ", None, "AI"]}]) == [{"tag": "AI", "count": 1}]


# ══════════════════════════════════════════════════════════════
# 主题库端点（落库断言）
# ══════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _init_strategy_tables(setup_test_db):
    """content_topics 表由端点惰性创建；publish 系列表由 init_db 创建，publish_metrics 此处幂等补建。"""
    from common.db import get_db

    from content_strategy import _ensure_topic_tables

    conn = get_db()
    _ensure_topic_tables(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS publish_metrics (
            id TEXT PRIMARY KEY, record_id TEXT NOT NULL, platform TEXT DEFAULT '',
            views INTEGER DEFAULT 0, likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0, followers_gained INTEGER DEFAULT 0,
            source TEXT DEFAULT 'manual', fetched_at TEXT DEFAULT '', created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()
    conn.close()


class TestTopicEndpoints:
    def test_create_and_list(self, setup_test_db):
        from content_strategy import TopicRequest, create_topic, list_topics

        req = TopicRequest(
            name="AI 提效指南",
            description="面向运营的 AI 工具清单",
            category="干货",
            tags=["AI", "效率", "工具"],
            goal="涨粉",
            priority=2,
        )
        created = asyncio.run(create_topic(req, current_user=USER))
        assert created["id"].startswith("ct_")
        assert created["tags"] == ["AI", "效率", "工具"]

        out = asyncio.run(list_topics(current_user=USER))
        assert out["total"] == 1
        assert out["items"][0]["name"] == "AI 提效指南"
        assert out["items"][0]["priority"] == 2
        # 标签聚合返回
        assert {t["tag"]: t["count"] for t in out["tags"]} == {"AI": 1, "效率": 1, "工具": 1}

    def test_list_tag_filter(self, setup_test_db):
        import asyncio

        from content_strategy import TopicRequest, create_topic, list_topics

        asyncio.run(create_topic(TopicRequest(name="AI 教程", tags=["AI", "教程"]), current_user=USER))
        asyncio.run(create_topic(TopicRequest(name="情感故事", tags=["情感"]), current_user=USER))

        out = asyncio.run(list_topics(tag="AI", current_user=USER))
        assert out["filtered"] == 1
        assert out["items"][0]["name"] == "AI 教程"

        out2 = asyncio.run(list_topics(keyword="故事", current_user=USER))
        assert out2["filtered"] == 1

        out3 = asyncio.run(list_topics(tag="AI", keyword="情感", current_user=USER))
        assert out3["filtered"] == 0

    def test_blank_tags_stripped(self, setup_test_db):
        from content_strategy import TopicRequest, create_topic, list_topics

        created = asyncio.run(
            create_topic(TopicRequest(name="T", tags=["  ", "AI", "", " 效率 "]), current_user=USER)
        )
        assert created["tags"] == ["AI", "效率"]

        out = asyncio.run(list_topics(tag="效率", current_user=USER))
        assert out["filtered"] == 1

    def test_update_topic(self, setup_test_db):
        from content_strategy import TopicRequest, create_topic, list_topics, update_topic

        created = asyncio.run(create_topic(TopicRequest(name="旧名", tags=["A"]), current_user=USER))
        asyncio.run(
            update_topic(
                req=TopicRequest(name="新名", description="改版", category="观点", tags=["B"], priority=3),
                topic_id=created["id"],
                current_user=USER,
            )
        )
        out = asyncio.run(list_topics(current_user=USER))
        item = out["items"][0]
        assert item["name"] == "新名"
        assert item["category"] == "观点"
        assert item["tags"] == ["B"]
        assert item["priority"] == 3

    def test_update_missing_topic_404(self, setup_test_db):
        from fastapi import HTTPException

        from content_strategy import TopicRequest, update_topic

        with pytest.raises(HTTPException) as exc:
            asyncio.run(update_topic(req=TopicRequest(name="x"), topic_id="nope", current_user=USER))
        assert exc.value.status_code == 404

    def test_delete_topic(self, setup_test_db):
        from content_strategy import TopicRequest, create_topic, delete_topic, list_topics

        created = asyncio.run(create_topic(TopicRequest(name="待删"), current_user=USER))
        asyncio.run(delete_topic(created["id"], current_user=USER))
        out = asyncio.run(list_topics(current_user=USER))
        assert out["total"] == 0

    def test_invalid_priority_rejected(self):
        from pydantic import ValidationError

        from content_strategy import TopicRequest

        with pytest.raises(ValidationError):
            TopicRequest(name="x", priority=5)
        with pytest.raises(ValidationError):
            TopicRequest(name="x", status="deleted")


# ══════════════════════════════════════════════════════════════
# calendar 端点（数据落库后聚合）
# ══════════════════════════════════════════════════════════════


class TestCalendarEndpoint:
    def _seed(self):
        from common.db import get_db

        conn = get_db()
        conn.execute(
            """INSERT INTO publish_schedules (id, user_id, platform, content_type, title, content,
               topics, asset_urls, account_id, scheduled_at, status, published_record_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "sched_1", "user1", "wechat", "article", "周三发布",
                "", '["AI"]', "[]", "", "2026-08-05T10:30:00", "pending", "", "2026-07-30T00:00:00",
            ),
        )
        conn.execute(
            """INSERT INTO publish_records (id, user_id, platform, content_type, title, content,
               topics, asset_urls, account_id, mode, status, platform_post_id, error, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "rec_1", "user1", "wechat", "article", "已发布文章",
                "", "[]", "[]", "", "guide", "success", "", "", "2026-08-05T09:00:00",
            ),
        )
        conn.execute(
            """INSERT INTO publish_metrics (id, record_id, platform, views, likes, comments,
               shares, followers_gained, source, fetched_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("pm_1", "rec_1", "wechat", 1250, 96, 18, 7, 3, "manual", "", "2026-08-06T00:00:00"),
        )
        # 跨月排期：不应出现在 2026-08 日历
        conn.execute(
            """INSERT INTO publish_schedules (id, user_id, platform, content_type, title, content,
               topics, asset_urls, account_id, scheduled_at, status, published_record_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "sched_2", "user1", "douyin", "video", "下月排期",
                "", "[]", "[]", "", "2026-09-01T10:00:00", "pending", "", "2026-08-01T00:00:00",
            ),
        )
        conn.commit()
        conn.close()

    def test_calendar_aggregates(self, setup_test_db):
        from content_strategy import content_calendar

        self._seed()
        out = asyncio.run(content_calendar(month="2026-08", current_user=USER))
        assert out["month"] == "2026-08"
        assert out["summary"] == {"scheduled": 1, "published": 1}

        day = out["days"]["2026-08-05"]
        assert day["total"] == 2
        assert day["schedules"][0]["title"] == "周三发布"
        assert day["schedules"][0]["topics"] == ["AI"]
        assert day["records"][0]["views"] == 1250
        assert day["records"][0]["likes"] == 96
        assert "2026-09-01" not in out["days"]

    def test_calendar_default_month(self, setup_test_db):
        from datetime import datetime

        from content_strategy import content_calendar

        self._seed()
        out = asyncio.run(content_calendar(current_user=USER))
        now = datetime.now().strftime("%Y-%m")
        assert out["month"] == now
        # 种子排期在 2026-08：若当前月恰好是 2026-08 则应聚合到 1 条
        expected = 1 if now == "2026-08" else 0
        assert out["summary"]["scheduled"] == expected

    def test_calendar_empty_month(self, setup_test_db):
        from content_strategy import content_calendar

        out = asyncio.run(content_calendar(month="2025-01", current_user=USER))
        assert out["summary"] == {"scheduled": 0, "published": 0}
        assert out["days"] == {}
        assert out["day_count"] == 31
