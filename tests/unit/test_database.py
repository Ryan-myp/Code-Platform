#!/usr/bin/env python3
"""智能研发平台 — 数据库测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_init_db_creates_tables(test_db_path):
    """测试 init_db 创建所有表"""
    from database import get_db

    tables = [
        "agents", "config", "teams", "workflows", "usage_logs",
        "conversations", "messages", "knowledge_bases", "skills",
        "mcp_servers", "requirements", "projects", "tasks",
        "artifacts", "prompt_versions", "comments", "comment_likes", "users",
    ]
    with get_db() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        created_tables = [r["name"] for r in rows]
    for table in tables:
        assert table in created_tables, f"表 {table} 未创建"


def test_get_db_context_manager(test_db_path):
    """测试 get_db 上下文管理器正常工作"""
    from database import get_db

    with get_db() as conn:
        row = conn.execute("SELECT 1").fetchone()
        assert row[0] == 1


def test_reset_db(test_db_path):
    """测试 reset_db 重建数据库"""
    from database import get_db, reset_db

    # 插入一些数据
    with get_db() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?)", ("test", "value")
        )

    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM config").fetchone()[0] > 0

    # 重置
    reset_db()

    # 验证数据被清除
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM config").fetchone()[0]
        assert count == 0


def test_config_table_operations(test_db_path):
    """测试 config 表的增删改查"""
    from database import get_db

    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            ("test_key", "test_value"),
        )
        row = conn.execute(
            "SELECT value FROM config WHERE key=?", ("test_key",)
        ).fetchone()
        assert row is not None
        assert row[0] == "test_value"
