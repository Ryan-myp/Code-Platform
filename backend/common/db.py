#!/usr/bin/env python3
"""数据库连接 + 集中式 schema 管理。

- get_db(): 单一连接工厂，DB_PATH 可由环境变量覆盖（测试需要）
- init_schema(): 集中创建全部 26 张表，替代散落各处的 init_db()
- migrate(): 对已存在表追加新列（SQLite ALTER ADD COLUMN），安全幂等
"""

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/ 目录（common/db.py 的上两级）
PROJECT_DIR = Path(__file__).resolve().parent.parent

# 默认数据库路径；可被环境变量 DB_PATH 覆盖（供单元测试使用）
_DEFAULT_DB_PATH = PROJECT_DIR / "platform.db"

# 线程级连接复用池 — 同一线程内复用连接，减少频繁创建/关闭开销
_thread_local = threading.local()


def _resolve_db_path() -> str:
    return os.environ.get("DB_PATH") or str(_DEFAULT_DB_PATH)


def get_db() -> sqlite3.Connection:
    """获取数据库连接。row_factory=Row，启用 WAL 与 busy_timeout。

    v8.0: 使用线程级连接复用，同一线程内复用已有连接，避免频繁创建/关闭。
    在测试环境中每次创建新连接以确保隔离性。
    """
    db_path = _resolve_db_path()
    # 测试环境每次新建连接确保隔离
    if os.environ.get("APP_ENV") == "test":
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    # 生产/开发环境：线程级连接复用
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except sqlite3.Error:
            try:
                conn.close()
            except Exception:
                pass
            _thread_local.conn = None
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _thread_local.conn = conn
    return conn


@contextmanager
def get_db_context():
    """上下文管理器形式的数据库连接获取。确保使用后关闭（用于非复用场景）。

    用法::
        with get_db_context() as conn:
            conn.execute("...")
    """
    conn = sqlite3.connect(_resolve_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 集中式表定义（CREATE TABLE IF NOT EXISTS）
# ══════════════════════════════════════════════════════════════

_SCHEMA_STATEMENTS = [
    # ── 用户与鉴权 ──────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user', created_at TEXT, active INTEGER DEFAULT 1
    )""",

    # ── Agent / Team / Workflow ─────────────────────────────
    """CREATE TABLE IF NOT EXISTS agents (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        instructions TEXT DEFAULT '', model TEXT DEFAULT 'agnes-2.0-flash',
        enable_memory INTEGER DEFAULT 0, enable_reasoning INTEGER DEFAULT 0,
        tools TEXT DEFAULT '[]', knowledge_base_ids TEXT DEFAULT '[]',
        skill_ids TEXT DEFAULT '[]', mcp_server_ids TEXT DEFAULT '[]',
        created_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS teams (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        mode TEXT DEFAULT 'coordinate', members TEXT DEFAULT '[]',
        instructions TEXT DEFAULT '', respond_directly INTEGER DEFAULT 0,
        created_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        steps TEXT DEFAULT '[]', connections TEXT DEFAULT '[]',
        created_at TEXT, active INTEGER DEFAULT 1
    )""",
    # workflow_runs / workflow_run_logs: workflows/executor.py 执行记录
    """CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL, status TEXT DEFAULT 'running',
        input_data TEXT DEFAULT '{}', output_data TEXT DEFAULT '{}',
        started_at TEXT, completed_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS workflow_run_logs (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, node_id TEXT, status TEXT,
        output_data TEXT DEFAULT '{}', completed_at TEXT,
        FOREIGN KEY (run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
    )""",

    # ── 会话 / 消息 / 记忆 ──────────────────────────────────
    # conversations + messages 是 chat_engine 使用的对话模型
    """CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, title TEXT DEFAULT '',
        created_at TEXT, updated_at TEXT, active INTEGER DEFAULT 1
    )""",
    # messages 同时服务 chat_engine(conversation_id) 与 sessions.py(session_id)
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT,
        role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, title TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY, session_id TEXT NOT NULL, agent_id TEXT,
        memory_type TEXT DEFAULT 'short', content TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )""",

    # ── 研发流程 ────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        status TEXT DEFAULT 'planning', team_id TEXT DEFAULT '',
        created_at TEXT, updated_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS requirements (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        status TEXT DEFAULT 'draft', priority TEXT DEFAULT 'P2',
        project_id TEXT DEFAULT '', creator TEXT DEFAULT '',
        prd_text TEXT DEFAULT '', review_report TEXT DEFAULT '',
        tech_design TEXT DEFAULT '', test_cases TEXT DEFAULT '', code TEXT DEFAULT '',
        version INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
        description TEXT DEFAULT '', type TEXT DEFAULT 'prd',
        assignee TEXT DEFAULT '', status TEXT DEFAULT 'todo',
        priority TEXT DEFAULT 'P2', parent_task_id TEXT DEFAULT '',
        created_at TEXT, completed_at TEXT, active INTEGER DEFAULT 1
    )""",
    # artifacts: 统一成果仓库，承载研发产物 + 创作产物（图片/视频/音频）
    """CREATE TABLE IF NOT EXISTS artifacts (
        id TEXT PRIMARY KEY, project_id TEXT DEFAULT '', requirement_id TEXT DEFAULT '',
        type TEXT NOT NULL, content TEXT DEFAULT '', version INTEGER DEFAULT 1,
        author TEXT DEFAULT '', created_at TEXT, active INTEGER DEFAULT 1
    )""",

    # ── 能力扩展 ────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS knowledge_bases (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT DEFAULT 'file',
        path TEXT DEFAULT '', url TEXT DEFAULT '', filter TEXT DEFAULT '',
        top_k INTEGER DEFAULT 5, created_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS skills (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        content TEXT DEFAULT '', `references` TEXT DEFAULT '', templates TEXT DEFAULT '',
        scripts TEXT DEFAULT '', assets TEXT DEFAULT '',
        created_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS skills_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT, skill_id TEXT NOT NULL, folder TEXT NOT NULL,
        filename TEXT NOT NULL, content TEXT DEFAULT '', created_at TEXT, updated_at TEXT,
        FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS mcp_servers (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, transport_type TEXT DEFAULT 'stdio',
        command TEXT DEFAULT '', args TEXT DEFAULT '[]', env TEXT DEFAULT '{}',
        url TEXT DEFAULT '', enabled INTEGER DEFAULT 1, created_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS expert_roles (
        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE,
        role_type TEXT NOT NULL CHECK(role_type IN ('dev','qa','pm','ui','architect','project_manager','dba','sre')),
        description TEXT NOT NULL, skills TEXT NOT NULL, responsibilities TEXT NOT NULL,
        deliverables TEXT NOT NULL, tool_stack TEXT NOT NULL,
        experience_years INTEGER DEFAULT 5, proficiency_level TEXT DEFAULT 'expert',
        created_at TEXT, active INTEGER DEFAULT 1
    )""",

    # ── 沙箱 ────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS sandbox_projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
        command TEXT DEFAULT 'python3 main.py', skill_id TEXT, status TEXT DEFAULT 'ready',
        port INTEGER, created_at TEXT, updated_at TEXT, project_dir TEXT
    )""",

    # ── 协作 ────────────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY, content TEXT NOT NULL, author_id TEXT DEFAULT 'system',
        parent_comment_id TEXT DEFAULT '', target_type TEXT NOT NULL, target_id TEXT NOT NULL,
        created_at TEXT, updated_at TEXT, active INTEGER DEFAULT 1
    )""",
    """CREATE TABLE IF NOT EXISTS comment_likes (
        id TEXT PRIMARY KEY, comment_id TEXT NOT NULL, user_id TEXT DEFAULT '', created_at TEXT
    )""",

    # ── 配置与统计 ──────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, task_type TEXT,
        input_length INTEGER, output_length INTEGER, response_time REAL, success INTEGER
    )""",
    """CREATE TABLE IF NOT EXISTS prompt_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, version INTEGER NOT NULL,
        instructions TEXT NOT NULL, optimized_at TEXT, created_by TEXT DEFAULT 'system'
    )""",
]

_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target_type, target_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id)",
    "CREATE INDEX IF NOT EXISTS idx_comment_likes_comment ON comment_likes(comment_id)",
    "CREATE INDEX IF NOT EXISTS idx_expert_roles_role_type ON expert_roles(role_type)",
    "CREATE INDEX IF NOT EXISTS idx_expert_roles_name ON expert_roles(name)",
]


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    """安全地给已有表追加列（SQLite 不支持 IF NOT EXISTS 于 ADD COLUMN）。"""
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
        logger.info(f"migrate: {table}.{column} added")


def _rebuild_messages_if_needed(conn: sqlite3.Connection) -> None:
    """如果 messages.conversation_id 是 NOT NULL（旧 schema），重建表让它可空。

    sessions.py 用 session_id 写消息（无 conversation_id），需要此列为可空。
    保留所有现有行 + 旧库已追加的 session_id/metadata/created_at 列。
    """
    cols = conn.execute("PRAGMA table_info(messages)").fetchall()
    if not cols:
        return  # 表不存在，由 init_schema 创建
    conv_col = next((c for c in cols if c["name"] == "conversation_id"), None)
    if not conv_col or conv_col["notnull"] == 0:
        return  # 已可空，无需重建

    existing_cols = [c["name"] for c in cols]
    # 重建期间关闭 FK（旧库可能有 orphan messages 指向已删除的 conversation）
    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        conn.execute("ALTER TABLE messages RENAME TO messages_old")
        conn.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT,
                role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """)
        # 重建后追加新列（与旧库 migrate 顺序一致）
        for col, ddl in [("session_id", "TEXT"), ("metadata", "TEXT DEFAULT '{}'"), ("created_at", "TEXT")]:
            if col in existing_cols:
                conn.execute(f"ALTER TABLE messages ADD COLUMN {col} {ddl}")
        # 复制数据（仅保留两表共有的列）
        shared = [c for c in existing_cols if c in ("id", "conversation_id", "role", "content", "timestamp", "session_id", "metadata", "created_at")]
        col_list = ", ".join(shared)
        conn.execute(f"INSERT INTO messages ({col_list}) SELECT {col_list} FROM messages_old")
        conn.execute("DROP TABLE messages_old")
        conn.commit()
        logger.info("migrate: messages table rebuilt (conversation_id now nullable)")
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def migrate() -> None:
    """对已存在的表追加新列（向前兼容旧库）。

    - messages: 重建以让 conversation_id 可空；为 sessions.py 补 session_id/metadata/created_at
    - artifacts: 为创作产物补 media_url / thumbnail / duration / metadata 列
    """
    conn = get_db()
    try:
        _rebuild_messages_if_needed(conn)
        _add_column_if_missing(conn, "messages", "session_id", "TEXT")
        _add_column_if_missing(conn, "messages", "metadata", "TEXT DEFAULT '{}'")
        _add_column_if_missing(conn, "messages", "created_at", "TEXT")
        _add_column_if_missing(conn, "artifacts", "media_url", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "artifacts", "thumbnail", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "artifacts", "duration", "REAL DEFAULT 0")
        _add_column_if_missing(conn, "artifacts", "metadata", "TEXT DEFAULT '{}'")
        _add_column_if_missing(conn, "sandbox_projects", "image", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "sandbox_projects", "ports", "TEXT DEFAULT '[]'")
        _add_column_if_missing(conn, "sandbox_projects", "config", "TEXT DEFAULT '{}'")
        conn.commit()
    finally:
        conn.close()


def init_schema() -> None:
    """创建全部表（IF NOT EXISTS）+ 迁移新列 + 预置 admin 用户。"""
    conn = get_db()
    try:
        for stmt in _SCHEMA_STATEMENTS:
            conn.execute(stmt)
        for stmt in _INDEX_STATEMENTS:
            conn.execute(stmt)
        conn.commit()
    finally:
        conn.close()

    # 对旧库追加新列
    migrate()

    # 预置 admin 用户（仅在不存在时）
    from common.auth import ensure_admin_user
    ensure_admin_user()
    logger.info("Database schema initialized")
