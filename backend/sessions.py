#!/usr/bin/env python3
"""会话管理 - 支持 Agent 对话历史"""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "platform.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化会话表"""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            agent_id TEXT,
            memory_type TEXT DEFAULT 'short',
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()


def create_session(agent_id: str, title: str = "") -> str:
    """创建新会话"""
    session_id = f"session_{int(time.time() * 1000)}"
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (id, agent_id, title) VALUES (?, ?, ?)",
        (session_id, agent_id, title or f"会话 {datetime.now().strftime('%H:%M')}"),
    )
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id: str) -> dict:
    """获取会话"""
    conn = get_db()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_sessions(agent_id: str = None) -> list:
    """列出会话"""
    conn = get_db()
    if agent_id:
        rows = conn.execute("SELECT * FROM sessions WHERE agent_id=? ORDER BY updated_at DESC", (agent_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_message(session_id: str, role: str, content: str, metadata: dict = None) -> str:
    """添加消息"""
    msg_id = f"msg_{int(time.time() * 1000)}"
    conn = get_db()
    conn.execute(
        "INSERT INTO messages (id, session_id, role, content, metadata) VALUES (?, ?, ?, ?, ?)",
        (msg_id, session_id, role, content, json.dumps(metadata or {})),
    )
    conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (datetime.now().isoformat(), session_id))
    conn.commit()
    conn.close()
    return msg_id


def get_messages(session_id: str, limit: int = 50) -> list:
    """获取消息历史"""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id=? ORDER BY created_at DESC LIMIT ?", (session_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows][::-1]


def delete_session(session_id: str) -> bool:
    """删除会话"""
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    conn.commit()
    conn.close()
    return True


def add_memory(session_id: str, agent_id: str, content: str, memory_type: str = "short") -> str:
    """添加记忆"""
    mem_id = f"mem_{int(time.time() * 1000)}"
    conn = get_db()
    conn.execute(
        "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, ?, ?)",
        (mem_id, session_id, agent_id, memory_type, content),
    )
    conn.commit()
    conn.close()
    return mem_id


def get_memories(session_id: str, agent_id: str = None) -> list:
    """获取记忆"""
    conn = get_db()
    if agent_id:
        rows = conn.execute(
            "SELECT * FROM memories WHERE session_id=? AND agent_id=? ORDER BY created_at DESC", (session_id, agent_id)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE session_id=? ORDER BY created_at DESC", (session_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# 初始化
init_db()
