#!/usr/bin/env python3
"""智能研发平台 — 数据库测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_init_db_creates_tables(test_db_path):
    """测试 init_db 创建所有表（common.db.init_schema 集中管理 26 张表）"""
    from common.db import get_db

    tables = [
        "agents", "config", "teams", "workflows", "workflow_runs", "workflow_run_logs",
        "conversations", "messages", "sessions", "memories",
        "knowledge_bases", "skills", "skills_files", "mcp_servers", "expert_roles",
        "sandbox_projects",
        "requirements", "projects", "tasks", "artifacts",
        "comments", "comment_likes",
        "usage_logs", "prompt_versions", "users",
    ]
    conn = get_db()
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    created_tables = [r["name"] for r in rows]
    for table in tables:
        assert table in created_tables, f"表 {table} 未创建"


def test_get_db_returns_connection(test_db_path):
    """测试 get_db 返回带 row_factory 的连接"""
    from common.db import get_db

    conn = get_db()
    assert conn is not None
    row = conn.execute("SELECT 1 AS v").fetchone()
    assert row["v"] == 1
    conn.close()


def test_get_db_context_manager(test_db_path):
    """测试 get_db 可作为上下文管理器使用"""
    from common.db import get_db

    with get_db() as conn:
        row = conn.execute("SELECT 1").fetchone()
        assert row[0] == 1


def test_migrate_adds_artifacts_media_columns(test_db_path):
    """测试 migrate() 给 artifacts 表追加 media_url/thumbnail/duration/metadata 列"""
    from common.db import get_db, migrate

    migrate()  # 幂等
    conn = get_db()
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()}
    conn.close()
    assert "media_url" in cols, "artifacts.media_url 缺失"
    assert "thumbnail" in cols, "artifacts.thumbnail 缺失"
    assert "duration" in cols, "artifacts.duration 缺失"
    assert "metadata" in cols, "artifacts.metadata 缺失"


def test_config_table_operations(test_db_path):
    """测试 config 表的增删改查"""
    from common.db import get_db

    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("test_key", "test_value"))
    conn.commit()
    row = conn.execute("SELECT value FROM config WHERE key=?", ("test_key",)).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "test_value"
