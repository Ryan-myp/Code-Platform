#!/usr/bin/env python3
"""会话管理 - 支持 Agent 对话历史"""

import json
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from common.db import get_db

router = APIRouter(tags=["会话"])


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


def add_message(session_id: str, role: str, content: str, metadata: dict = None) -> int:
    """添加消息。返回自增 id。"""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, json.dumps(metadata or {}), datetime.now().isoformat()),
    )
    conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (datetime.now().isoformat(), session_id))
    conn.commit()
    msg_id = cur.lastrowid
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


# ══════════════════════════════════════════════════════════════
# FastAPI 路由
# ══════════════════════════════════════════════════════════════


@router.get("/api/sessions")
async def api_list_sessions(agent_id: str = None):
    """获取会话列表"""
    return list_sessions(agent_id)


@router.post("/api/sessions")
async def api_create_session(req: dict):
    """创建会话"""
    agent_id = req.get("agent_id", "")
    if not agent_id:
        raise HTTPException(400, "agent_id 不能为空")
    session_id = create_session(agent_id, req.get("title", ""))
    return {"session_id": session_id, "agent_id": agent_id}


@router.get("/api/sessions/{session_id}/messages")
async def api_get_messages(session_id: str):
    """获取会话消息"""
    return get_messages(session_id)


@router.post("/api/sessions/{session_id}/messages")
async def api_add_message(session_id: str, req: dict):
    """添加消息"""
    content = req.get("content", "")
    if not content:
        raise HTTPException(400, "内容不能为空")
    msg_id = add_message(session_id, req.get("role", "user"), content, req.get("metadata"))
    return {"id": msg_id, "session_id": session_id}


@router.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str):
    """删除会话"""
    delete_session(session_id)
    return {"success": True}


@router.get("/api/sessions/{session_id}/memories")
async def api_get_memories(session_id: str, agent_id: str = None):
    """获取会话记忆"""
    return get_memories(session_id, agent_id)
