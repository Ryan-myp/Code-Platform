"""v15 底座稳定性体检抽查：realtime / sessions / backup / gallery / drafts。

覆盖：
- drafts：脏 content JSON 不 500、保存/读取/删除闭环、无草稿返回 None
- sessions：空会话、limit 收敛、不存在会话返回 None
- backup：在线快照创建/列表/非法文件名拒绝（路径穿越防护）
- realtime：无事件循环静默跳过、空频道广播安全、任务频道归属校验
- gallery：媒体存在性判定、prompt 提取（dict/纯文本/非法 JSON）
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


class TestDrafts:
    def test_list_with_corrupt_content_no_500(self, setup_test_db):
        from common.db import get_db
        from drafts import list_drafts

        conn = get_db()
        conn.execute(
            "INSERT INTO drafts (id, user_id, tool_id, title, content, updated_at) "
            "VALUES ('d1', 'u1', 'voice', '坏数据', 'not-json{{{', '2026-01-01T00:00:00')"
        )
        conn.execute(
            "INSERT INTO drafts (id, user_id, tool_id, title, content, updated_at) "
            "VALUES ('d2', 'u1', 'meme', '数组数据', '[1,2,3]', '2026-01-02T00:00:00')"
        )
        conn.commit()
        conn.close()

        result = asyncio.run(list_drafts(current_user=USER))
        assert len(result) == 2
        by_id = {d["id"]: d for d in result}
        # 非法 JSON 与非法结构都兜底为空 dict
        assert by_id["d1"]["content"] == {}
        assert by_id["d2"]["content"] == {}
        # 附工具可读信息
        assert by_id["d1"]["tool_label"] == "配音工坊"
        assert by_id["d1"]["tool_path"] == "/voice-dubbing"

    def test_save_and_get_roundtrip(self, setup_test_db):
        from common.db import get_db
        from drafts import get_draft, list_drafts, save_draft

        req = type("R", (), {"tool_id": "voice", "title": "我的配音", "content": {"text": "你好"}})()
        res = asyncio.run(save_draft(req, current_user=USER))
        assert res["id"].startswith("draft_")

        # 覆盖保存（同 user+tool 更新）
        res2 = asyncio.run(
            save_draft(type("R", (), {"tool_id": "voice", "title": "新标题", "content": {"text": "更新"}})(), current_user=USER)
        )
        assert res2["id"] == res["id"]

        draft = asyncio.run(get_draft("voice", current_user=USER))
        assert draft["title"] == "新标题"
        assert draft["content"] == {"text": "更新"}

        items = asyncio.run(list_drafts(current_user=USER))
        assert len(items) == 1

    def test_get_draft_missing_returns_none(self, setup_test_db):
        from drafts import get_draft

        result = asyncio.run(get_draft("ppt", current_user=USER))
        assert result is None


class TestSessions:
    def test_get_messages_empty(self, setup_test_db):
        from sessions import get_messages

        assert get_messages("session_none") == []

    def test_get_messages_limit_clamped(self, setup_test_db):
        from common.db import get_db
        from sessions import get_messages

        conn = get_db()
        conn.execute("INSERT INTO sessions (id, agent_id) VALUES ('s1', 'a1')")
        for i in range(5):
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES ('s1', 'user', ?, ?)",
                (f"msg{i}", f"2026-01-0{i + 1}T00:00:00"),
            )
        conn.commit()
        conn.close()

        # 非法/越界参数收敛：0 → 1，超大 → 500，非数字 → 50
        assert len(get_messages("s1", 0)) == 1
        assert len(get_messages("s1", 99999)) == 5
        assert len(get_messages("s1", "abc")) == 5

    def test_get_session_missing(self, setup_test_db):
        from sessions import get_session

        assert get_session("session_none") is None


class TestBackup:
    def test_create_and_list(self, setup_test_db, tmp_path, monkeypatch):
        import common.backup as backup_mod

        monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path)
        info = backup_mod.create_backup()
        assert info["name"].startswith("platform-")
        assert info["size"] > 0
        assert (tmp_path / info["name"]).exists()

        backups = backup_mod.list_backups()
        assert len(backups) == 1
        assert backups[0]["name"] == info["name"]

    def test_rotate_keeps_max(self, setup_test_db, tmp_path, monkeypatch):
        import common.backup as backup_mod

        monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_mod, "KEEP_MAX", 3)
        for _ in range(5):
            backup_mod.create_backup()
        backups = backup_mod.list_backups()
        assert len(backups) == 3

    def test_restore_rejects_illegal_name(self, setup_test_db):
        from common.backup import restore_backup

        with pytest.raises(ValueError):
            restore_backup("../etc/passwd.db")
        with pytest.raises(ValueError):
            restore_backup("other.db")
        with pytest.raises(ValueError):
            restore_backup("platform-unknown.db")  # 合法格式但文件不存在


class TestRealtime:
    def test_send_progress_without_loop_is_noop(self):
        from realtime import send_progress_threadsafe, set_loop

        set_loop(None)  # 测试环境未注入事件循环
        # 不应抛任何异常
        send_progress_threadsafe("task:abc", "progress", {"pct": 50})

    def test_broadcast_empty_channel_safe(self):
        from realtime import manager

        asyncio.run(manager.broadcast("empty-channel", {"event": "x"}))
        assert manager.get_connection_count() == 0
        assert manager.get_connection_count("empty-channel") == 0

    def test_task_channel_access(self, setup_test_db):
        from realtime import _check_task_channel_access

        # task:user: 仅本人/admin
        assert asyncio.run(_check_task_channel_access("task:user:alice", {"sub": "alice"})) is None
        deny = asyncio.run(_check_task_channel_access("task:user:alice", {"sub": "bob", "role": "user"}))
        assert deny and deny[0] == 4403
        assert asyncio.run(_check_task_channel_access("task:user:alice", {"sub": "bob", "role": "admin"})) is None

        # task:{id}：不存在的任务 → 4404
        deny = asyncio.run(_check_task_channel_access("task:nonexistent", {"sub": "alice", "role": "user"}))
        assert deny and deny[0] == 4404

    def test_non_task_channel_always_allowed(self, setup_test_db):
        from realtime import _check_task_channel_access

        assert asyncio.run(_check_task_channel_access("chat:a1", {"sub": "alice"})) is None


class TestGallery:
    def test_media_file_exists_unknown_prefix_true(self):
        from gallery import _media_file_exists

        assert _media_file_exists("") is False
        assert _media_file_exists("/api/some-unknown/x.png") is True

    def test_extract_prompt_variants(self):
        from gallery import _extract_prompt

        assert _extract_prompt('{"prompt": "一只猫"}') == "一只猫"
        assert _extract_prompt('{"filename": "cat.png"}') == "cat.png"
        assert _extract_prompt("纯文本描述") == "纯文本描述"
        assert _extract_prompt("not-json{{") == "not-json{{"[:300]
        assert _extract_prompt(None) == ""
