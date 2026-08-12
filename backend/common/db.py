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

    v10.1: 自动 commit/rollback — 正常退出自动提交，异常退出回滚，
    彻底解决模块漏写 conn.commit() 导致数据丢失的问题。
    """
    conn = sqlite3.connect(_resolve_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
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
    # ── 结果分享（商业版：引流传播） ────────────────────────
    """CREATE TABLE IF NOT EXISTS shares (
        id TEXT PRIMARY KEY, share_code TEXT UNIQUE NOT NULL,
        user_id TEXT NOT NULL, content_type TEXT DEFAULT 'text',
        title TEXT DEFAULT '', content TEXT DEFAULT '',
        created_at TEXT, views INTEGER DEFAULT 0,
        rewarded INTEGER DEFAULT 0, reward_quota INTEGER DEFAULT 0,
        is_test INTEGER DEFAULT 0
    )""",
    # ── 会员订单（商业版：支付闭环） ────────────────────────
    """CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, plan TEXT NOT NULL,
        amount REAL DEFAULT 0, status TEXT DEFAULT 'pending',
        voucher TEXT DEFAULT '', remark TEXT DEFAULT '',
        created_at TEXT, reviewed_at TEXT, reviewed_by TEXT DEFAULT ''
    )""",
    # ── 资源可见性（v9.3：内容权限 / 灰度发布） ─────────────
    """CREATE TABLE IF NOT EXISTS resource_visibility (
        resource_type TEXT NOT NULL, resource_id TEXT NOT NULL,
        visible_to TEXT DEFAULT 'all', updated_at TEXT,
        PRIMARY KEY (resource_type, resource_id)
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
    """CREATE TABLE IF NOT EXISTS agent_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT NOT NULL, user_id TEXT DEFAULT '',
        message TEXT DEFAULT '', status TEXT DEFAULT 'done', elapsed REAL DEFAULT 0,
        error TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        code_review TEXT DEFAULT '', pipeline_status TEXT DEFAULT '{}',
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
        url TEXT DEFAULT '', auth_type TEXT DEFAULT 'none', auth_config TEXT DEFAULT '{}',
        enabled INTEGER DEFAULT 1, created_at TEXT
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
    """CREATE TABLE IF NOT EXISTS work_likes (
        id TEXT PRIMARY KEY, work_id TEXT NOT NULL, user_id TEXT DEFAULT '', created_at TEXT
    )""",
    # ── 配置与统计 ──────────────────────────────────────────
    """CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS usage_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, task_type TEXT,
        input_length INTEGER, output_length INTEGER, response_time REAL, success INTEGER,
        error TEXT DEFAULT '', api_key TEXT DEFAULT '', user_id TEXT DEFAULT '',
        feature TEXT DEFAULT '', model TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS prompt_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL, version INTEGER NOT NULL,
        instructions TEXT NOT NULL, optimized_at TEXT, created_by TEXT DEFAULT 'system'
    )""",
    # ── v9.0: 平台体验增强 ──────────────────────────────────
    # 全局任务（跨项目）
    """CREATE TABLE IF NOT EXISTS global_tasks (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT DEFAULT '',
        status TEXT DEFAULT 'todo', priority TEXT DEFAULT 'P2',
        due_date TEXT DEFAULT '', tags TEXT DEFAULT '[]',
        project_id TEXT DEFAULT '', agent_id TEXT DEFAULT '',
        created_by TEXT DEFAULT 'admin', assigned_to TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT DEFAULT '', active INTEGER DEFAULT 1
    )""",
    # 通知记录
    """CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY, type TEXT NOT NULL DEFAULT 'info',
        title TEXT NOT NULL, content TEXT DEFAULT '',
        target_type TEXT DEFAULT '', target_id TEXT DEFAULT '',
        read INTEGER DEFAULT 0, user_id TEXT DEFAULT 'all',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, read_at TEXT DEFAULT ''
    )""",
    # 优惠券/折扣码（商业版：营销）
    """CREATE TABLE IF NOT EXISTS coupons (
        id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL,
        discount_type TEXT NOT NULL DEFAULT 'fixed', value REAL NOT NULL,
        max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1, expires_at TEXT,
        created_at TEXT, created_by TEXT DEFAULT ''
    )""",
    # 分享页访问埋点（商业版：渠道分析 + 裂变奖励去重键）
    """CREATE TABLE IF NOT EXISTS share_visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT, share_id TEXT NOT NULL,
        source TEXT DEFAULT 'direct', referer TEXT DEFAULT '',
        visited_at TEXT, visitor_key TEXT DEFAULT ''
    )""",
    # 仪表盘组件配置
    """CREATE TABLE IF NOT EXISTS dashboard_widgets (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL DEFAULT 'default',
        widget_type TEXT NOT NULL, title TEXT DEFAULT '',
        config TEXT DEFAULT '{}', position INTEGER DEFAULT 0,
        size TEXT DEFAULT 'md', visible INTEGER DEFAULT 1,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # ── v9.0: Phase 2 研发增强 ──────────────────────────────
    # CI/CD 流水线
    """CREATE TABLE IF NOT EXISTS pipelines (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        type TEXT DEFAULT 'ci', config TEXT DEFAULT '{}',
        status TEXT DEFAULT 'idle', last_run TEXT DEFAULT '',
        created_by TEXT DEFAULT 'admin', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER DEFAULT 1
    )""",
    # 流水线运行记录
    """CREATE TABLE IF NOT EXISTS pipeline_runs (
        id TEXT PRIMARY KEY, pipeline_id TEXT NOT NULL, status TEXT DEFAULT 'running',
        log TEXT DEFAULT '', started_at TEXT, finished_at TEXT,
        FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
    )""",
    # 代码生成记录
    """CREATE TABLE IF NOT EXISTS code_generations (
        id TEXT PRIMARY KEY, language TEXT NOT NULL, prompt TEXT NOT NULL,
        result TEXT DEFAULT '', model TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 代码审查记录
    """CREATE TABLE IF NOT EXISTS code_reviews (
        id TEXT PRIMARY KEY, language TEXT NOT NULL, code TEXT NOT NULL,
        result TEXT DEFAULT '', model TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # ── v9.0: Phase 3 内容创作 ──────────────────────────────
    # 文案任务（user_id：商业化用户隔离）
    """CREATE TABLE IF NOT EXISTS copywriting_tasks (
        id TEXT PRIMARY KEY, type TEXT NOT NULL DEFAULT 'marketing',
        title TEXT DEFAULT '', prompt TEXT NOT NULL,
        result TEXT DEFAULT '', model TEXT DEFAULT '',
        user_id TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 翻译记录（user_id：商业化用户隔离）
    """CREATE TABLE IF NOT EXISTS translations (
        id TEXT PRIMARY KEY, source_lang TEXT NOT NULL, target_lang TEXT NOT NULL,
        source_text TEXT NOT NULL, result TEXT DEFAULT '',
        model TEXT DEFAULT '', user_id TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 翻译术语表（v15：用户自定义术语，翻译时强制应用）
    """CREATE TABLE IF NOT EXISTS translation_glossary (
        id TEXT PRIMARY KEY, user_id TEXT DEFAULT '',
        source_term TEXT NOT NULL, target_term TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # ── v9.0: Phase 4 运营分析 ──────────────────────────────
    # A/B 测试
    """CREATE TABLE IF NOT EXISTS ab_tests (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
        variant_a TEXT DEFAULT '', variant_b TEXT DEFAULT '',
        status TEXT DEFAULT 'draft', result TEXT DEFAULT '{}',
        created_by TEXT DEFAULT 'admin', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP, active INTEGER DEFAULT 1
    )""",
    # ── v9.0: 办公效率 ──────────────────────────────────────
    # PPT 生成记录（user_id：商业化用户隔离）
    """CREATE TABLE IF NOT EXISTS ppt_generations (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, outline TEXT DEFAULT '',
        slides TEXT DEFAULT '[]', result TEXT DEFAULT '',
        model TEXT DEFAULT '', user_id TEXT DEFAULT '',
        file_path TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # Excel 操作记录
    """CREATE TABLE IF NOT EXISTS excel_operations (
        id TEXT PRIMARY KEY, operation TEXT NOT NULL DEFAULT 'create',
        title TEXT DEFAULT '', data TEXT DEFAULT '{}',
        result TEXT DEFAULT '', file_path TEXT DEFAULT '',
        user_id TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 效率工具使用记录
    """CREATE TABLE IF NOT EXISTS tool_records (
        id TEXT PRIMARY KEY, tool_id TEXT NOT NULL,
        input TEXT DEFAULT '', result TEXT DEFAULT '',
        model TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 股票分析记录
    """CREATE TABLE IF NOT EXISTS stock_analyses (
        id TEXT PRIMARY KEY, symbol TEXT NOT NULL,
        analysis_type TEXT DEFAULT 'comprehensive', period TEXT DEFAULT '3mo',
        result TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 定时股票分析报告（v21：scheduler stock_report 任务产出）
    """CREATE TABLE IF NOT EXISTS stock_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
        symbol TEXT NOT NULL, period TEXT DEFAULT '3mo',
        report TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 模拟交易账户
    """CREATE TABLE IF NOT EXISTS trading_accounts (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        cash REAL DEFAULT 1000000, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 模拟交易持仓
    """CREATE TABLE IF NOT EXISTS trading_positions (
        id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
        symbol TEXT NOT NULL, quantity INTEGER DEFAULT 0,
        avg_cost REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 模拟交易历史
    """CREATE TABLE IF NOT EXISTS trading_history (
        id TEXT PRIMARY KEY, account_id TEXT NOT NULL,
        symbol TEXT NOT NULL, action TEXT NOT NULL,
        quantity INTEGER DEFAULT 0, price REAL DEFAULT 0,
        amount REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # 工具收藏
    """CREATE TABLE IF NOT EXISTS tool_favorites (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        tool_id TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, tool_id)
    )""",
    # 工具使用统计
    """CREATE TABLE IF NOT EXISTS tool_usage_stats (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        tool_id TEXT NOT NULL, use_count INTEGER DEFAULT 0,
        last_used_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, tool_id)
    )""",
    # 草稿箱（v10.0：各工厂表单自动保存草稿）
    """CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        tool_id TEXT NOT NULL,  -- voice/meme/copywriting/…
        title TEXT DEFAULT '', content TEXT DEFAULT '{}',
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    # ── 内容发布中心（公众号/抖音/快手） ──────────────────────
    # 第三方平台账号配置（自动发布用；secret 存库、读取时脱敏）
    """CREATE TABLE IF NOT EXISTS publish_accounts (
        id TEXT PRIMARY KEY, platform TEXT NOT NULL,  -- wechat/douyin/kuaishou
        name TEXT DEFAULT '', app_id TEXT DEFAULT '', app_secret TEXT DEFAULT '',
        access_token TEXT DEFAULT '', token_expires_at TEXT DEFAULT '',
        configured INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT, active INTEGER DEFAULT 1
    )""",
    # 发布记录（引导模式也记录，便于追溯）
    """CREATE TABLE IF NOT EXISTS publish_records (
        id TEXT PRIMARY KEY, user_id TEXT DEFAULT '', platform TEXT NOT NULL,
        content_type TEXT NOT NULL,  -- article/image/video
        title TEXT DEFAULT '', content TEXT DEFAULT '', topics TEXT DEFAULT '[]',
        asset_urls TEXT DEFAULT '[]', account_id TEXT DEFAULT '',
        mode TEXT DEFAULT 'guide',  -- guide=引导式 / auto=自动发布
        status TEXT DEFAULT 'pending',  -- pending/success/failed
        platform_post_id TEXT DEFAULT '', error TEXT DEFAULT '',
        created_at TEXT
    )""",
    # 发布排期（v10.0：内容运营日历）
    """CREATE TABLE IF NOT EXISTS publish_schedules (
        id TEXT PRIMARY KEY, user_id TEXT DEFAULT '', platform TEXT NOT NULL,
        content_type TEXT NOT NULL,  -- article/image/video
        title TEXT DEFAULT '', content TEXT DEFAULT '', topics TEXT DEFAULT '[]',
        asset_urls TEXT DEFAULT '[]', account_id TEXT DEFAULT '',
        scheduled_at TEXT NOT NULL,  -- 计划发布时间
        status TEXT DEFAULT 'pending',  -- pending/published/cancelled
        published_record_id TEXT DEFAULT '',  -- 关联发布记录
        created_at TEXT
    )""",
    # 小程序项目（AI 生成）
    """CREATE TABLE IF NOT EXISTS miniapp_projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, template TEXT DEFAULT 'custom',
        requirement TEXT DEFAULT '', files TEXT DEFAULT '{}',
        model TEXT DEFAULT '', created_at TEXT
    )""",
    # 小游戏项目（AI 生成，双版本 web + wx）
    """CREATE TABLE IF NOT EXISTS game_projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, template TEXT DEFAULT 'custom',
        requirement TEXT DEFAULT '', files TEXT DEFAULT '{}',
        model TEXT DEFAULT '', created_at TEXT,
        updated_at TEXT, favorite INTEGER DEFAULT 0, tags TEXT DEFAULT '[]',
        iterations INTEGER DEFAULT 0, iteration_log TEXT DEFAULT '[]'
    )""",
    # 模板市场积分（templates_market 扣减/分成，此前表缺失导致购买付费模板 500）
    """CREATE TABLE IF NOT EXISTS user_quotas (
        username TEXT PRIMARY KEY, credits INTEGER DEFAULT 0, updated_at TEXT
    )""",
    # 游戏/小程序项目可回滚历史版本（common/artifacts.py 版本快照）
    """CREATE TABLE IF NOT EXISTS project_versions (
        id TEXT PRIMARY KEY, project_type TEXT NOT NULL, project_id TEXT NOT NULL,
        version_no INTEGER DEFAULT 1, files TEXT DEFAULT '{}',
        requirement TEXT DEFAULT '', note TEXT DEFAULT '', created_at TEXT
    )""",
]

_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target_type, target_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_comment_id)",
    "CREATE INDEX IF NOT EXISTS idx_comment_likes_comment ON comment_likes(comment_id)",
    "CREATE INDEX IF NOT EXISTS idx_expert_roles_role_type ON expert_roles(role_type)",
    "CREATE INDEX IF NOT EXISTS idx_expert_roles_name ON expert_roles(name)",
    # v9.0 新索引
    "CREATE INDEX IF NOT EXISTS idx_global_tasks_status ON global_tasks(status)",
    "CREATE INDEX IF NOT EXISTS idx_global_tasks_priority ON global_tasks(priority)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_dashboard_widgets_user ON dashboard_widgets(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code)",
    "CREATE INDEX IF NOT EXISTS idx_share_visits_share ON share_visits(share_id)",
    "CREATE INDEX IF NOT EXISTS idx_share_visits_time ON share_visits(visited_at)",
]


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl_type: str) -> None:
    """安全地给已有表追加列（SQLite 不支持 IF NOT EXISTS 于 ADD COLUMN）。

    表不存在时静默跳过（由 CREATE TABLE IF NOT EXISTS 路径兜底）。
    """
    cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if not cols:
        return  # 表不存在
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
        shared = [
            c
            for c in existing_cols
            if c in ("id", "conversation_id", "role", "content", "timestamp", "session_id", "metadata", "created_at")
        ]
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
        # 流水线产物：代码审查结果留存（AI 工作台 review_code 阶段）
        _add_column_if_missing(conn, "requirements", "code_review", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "requirements", "pipeline_status", "TEXT DEFAULT '{}'")
        _add_column_if_missing(conn, "sandbox_projects", "ports", "TEXT DEFAULT '[]'")
        _add_column_if_missing(conn, "sandbox_projects", "config", "TEXT DEFAULT '{}'")
        # v10.1 游戏工坊资产化：更新/收藏/标签/迭代记录
        _add_column_if_missing(conn, "game_projects", "updated_at", "TEXT")
        _add_column_if_missing(conn, "game_projects", "favorite", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "game_projects", "tags", "TEXT DEFAULT '[]'")
        _add_column_if_missing(conn, "game_projects", "iterations", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "game_projects", "iteration_log", "TEXT DEFAULT '[]'")
        # v9.1 商业版：用户资料 / 会员 / 额度
        _add_column_if_missing(conn, "users", "avatar", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "users", "nickname", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "users", "membership", "TEXT DEFAULT 'free'")
        _add_column_if_missing(conn, "users", "membership_expires", "TEXT")
        _add_column_if_missing(conn, "users", "daily_quota", "INTEGER DEFAULT 30")
        _add_column_if_missing(conn, "users", "used_today", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "users", "last_quota_date", "TEXT")
        _add_column_if_missing(conn, "users", "total_usage", "INTEGER DEFAULT 0")
        # v9.1：工具记录归属用户（记录中心按用户隔离）
        _add_column_if_missing(conn, "tool_records", "user_id", "TEXT DEFAULT ''")
        # v9.2：邀请码分销体系
        _add_column_if_missing(conn, "users", "invite_code", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "users", "invited_by", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "users", "bonus_quota", "INTEGER DEFAULT 0")
        # v9.4 商业版：订单优惠券 / 分享转化来源
        _add_column_if_missing(conn, "orders", "coupon_code", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "orders", "original_amount", "REAL DEFAULT 0")
        _add_column_if_missing(conn, "orders", "stripe_session_id", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "users", "share_from", "TEXT DEFAULT ''")
        # v11.x 分享裂变：访问奖励（去重键 / 已发奖标记 / 已发额度）
        _add_column_if_missing(conn, "shares", "rewarded", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "shares", "reward_quota", "INTEGER DEFAULT 0")
        _add_column_if_missing(conn, "share_visits", "visitor_key", "TEXT DEFAULT ''")
        # 分享内容治理：测试/违规分享标记（案例墙过滤 + 管理员管理）
        _add_column_if_missing(conn, "shares", "is_test", "INTEGER DEFAULT 0")
        # v9.5：MCP 授权验证 / 知识库连接配置
        _add_column_if_missing(conn, "mcp_servers", "auth_type", "TEXT DEFAULT 'none'")
        # v16.0 门户系统：用户门户类型（rdm=研发管理 / media=自媒体创作 / general=通用）
        _add_column_if_missing(conn, "users", "portal_type", "TEXT DEFAULT 'general'")
        # v17.0 密码重置 + 试用机制
        _add_column_if_missing(conn, "users", "reset_token", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "users", "reset_token_expires", "TEXT")
        _add_column_if_missing(conn, "users", "trial_expires", "TEXT")
        # v17.6 邮件系统：用户邮箱（密码重置 / 试用提醒）
        _add_column_if_missing(conn, "users", "email", "TEXT DEFAULT ''")
        # v17.0 usage_logs 增强：按功能/模型/来源拆分记录
        _add_column_if_missing(conn, "usage_logs", "feature", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "usage_logs", "model", "TEXT DEFAULT ''")
        # v16.0 门户定义表
        conn.execute("""CREATE TABLE IF NOT EXISTS portals (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            nav_groups TEXT NOT NULL DEFAULT '[]',
            highlight_tools TEXT DEFAULT '[]',
            created_at TEXT,
            updated_at TEXT
        )""")
        # v16.0 门户页面映射表
        conn.execute("""CREATE TABLE IF NOT EXISTS portal_page_config (
            portal_id TEXT NOT NULL,
            page_id TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            PRIMARY KEY (portal_id, page_id),
            FOREIGN KEY (portal_id) REFERENCES portals(id) ON DELETE CASCADE
        )""")
        _add_column_if_missing(conn, "mcp_servers", "auth_config", "TEXT DEFAULT '{}'")
        _add_column_if_missing(conn, "knowledge_bases", "config", "TEXT DEFAULT '{}'")
        _add_column_if_missing(conn, "knowledge_bases", "description", "TEXT DEFAULT ''")
        _add_column_if_missing(conn, "knowledge_bases", "subtype", "TEXT DEFAULT 'general'")
        # v15：API Key 过期时间（apikey_api / auth 认证链路共用）
        _add_column_if_missing(conn, "api_keys", "expires_at", "TEXT")
        # 一句话全自动流水线：AI 工作台 AutoRun 进度记录
        conn.execute("""CREATE TABLE IF NOT EXISTS auto_runs (
            id TEXT PRIMARY KEY,
            requirement_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            language TEXT DEFAULT 'python',
            status TEXT DEFAULT 'running',
            current_stage TEXT DEFAULT '',
            stage_progress TEXT DEFAULT '{}',
            log TEXT DEFAULT '',
            pipeline_id TEXT DEFAULT '',
            port INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT,
            finished_at TEXT
        )""")
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
    # 预置门户数据（幂等，upsert）
    from portals import seed_portals
    seed_portals()
    # 预置模板市场种子数据（幂等，仅空表时插入）
    from seed_templates import seed_templates
    seed_templates()
    logger.info("Database schema initialized")
