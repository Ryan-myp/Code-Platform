"""v15 通知中心增强单测：站内信写入 / 已读管理 / 分页 / 未读角标。

覆盖：
- send_inbox_message：写入 notifications 表（type=system、read=0）
- list_notifications：分页（limit/offset/total）、unread_only 过滤
- unread-count：未读角标数
- mark_read / read-all：已读状态与 read_at 断言
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _send_many(conn, n=3, username="admin"):
    from notify_api import send_inbox_message

    ids = []
    for i in range(n):
        ids.append(send_inbox_message(username, f"消息{i}", f"内容{i}"))
    return ids


class TestSendInboxMessage:
    def test_write_with_defaults(self, setup_test_db):
        from common.db import get_db
        from notify_api import send_inbox_message

        nid = send_inbox_message("admin", "测试标题", "测试内容")

        conn = get_db()
        row = conn.execute("SELECT * FROM notifications WHERE id=?", (nid,)).fetchone()
        conn.close()
        assert row is not None
        assert row["type"] == "system"
        assert row["title"] == "测试标题"
        assert row["content"] == "测试内容"
        assert row["user_id"] == "admin"
        assert row["read"] == 0


class TestListNotifications:
    def test_pagination(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from platform_api import list_notifications

        _send_many(get_db(), n=5, username="admin")

        result = asyncio.run(list_notifications(limit=2, offset=0, current_user={"username": "admin"}))
        assert result["total"] == 5
        assert len(result["items"]) == 2

        page2 = asyncio.run(list_notifications(limit=2, offset=2, current_user={"username": "admin"}))
        assert len(page2["items"]) == 2
        # 新消息在前，两页无重叠
        ids1 = {i["id"] for i in result["items"]}
        ids2 = {i["id"] for i in page2["items"]}
        assert not (ids1 & ids2)

    def test_unread_only_filter(self, setup_test_db):
        from common.db import get_db
        from notify_api import send_inbox_message
        from platform_api import list_notifications, mark_notification_read

        nid = send_inbox_message("admin", "标题", "内容")
        asyncio.run(mark_notification_read(nid, current_user={"username": "admin"}))

        result = asyncio.run(list_notifications(unread_only=True, current_user={"username": "admin"}))
        assert result["total"] == 0


class TestUnreadCount:
    def test_count_after_read(self, setup_test_db):
        from common.db import get_db
        from notify_api import send_inbox_message
        from platform_api import mark_notification_read, unread_notification_count

        send_inbox_message("admin", "未读1", "")
        nid2 = send_inbox_message("admin", "未读2", "")
        asyncio.run(mark_notification_read(nid2, current_user={"username": "admin"}))

        result = asyncio.run(unread_notification_count(current_user={"username": "admin"}))
        assert result["count"] == 1


class TestMarkRead:
    def test_mark_one_read(self, setup_test_db):
        from common.db import get_db
        from notify_api import send_inbox_message
        from platform_api import mark_notification_read

        nid = send_inbox_message("admin", "标题", "内容")

        result = asyncio.run(mark_notification_read(nid, current_user={"username": "admin"}))
        assert result["ok"] is True

        conn = get_db()
        row = conn.execute("SELECT read, read_at FROM notifications WHERE id=?", (nid,)).fetchone()
        conn.close()
        assert row["read"] == 1
        assert row["read_at"]

    def test_mark_all_read(self, setup_test_db):
        from common.db import get_db
        from platform_api import mark_all_notifications_read, unread_notification_count

        _send_many(get_db(), n=3, username="admin")

        asyncio.run(mark_all_notifications_read(current_user={"username": "admin"}))
        result = asyncio.run(unread_notification_count(current_user={"username": "admin"}))
        assert result["count"] == 0
