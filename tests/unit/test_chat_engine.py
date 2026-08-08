#!/usr/bin/env python3
"""chat_engine 单元测试 — 对话 CRUD、Agent 运行、Team 运行（mock LLM）。"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def run(coro):
    """同步执行 async 函数的辅助。"""
    return asyncio.run(coro)


def _seed_agent(agent_id="agent_test", name="TestAgent", instructions="你是测试助手"):
    """在数据库中创建测试 Agent。"""
    from common.db import get_db

    conn = get_db()
    conn.execute(
        "INSERT INTO agents (id, name, instructions, model, created_at, active) VALUES (?, ?, ?, ?, ?, 1)",
        (agent_id, name, instructions, "agnes-2.0-flash", "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()


def _seed_team(team_id="team_test", members=None, instructions="团队指令"):
    """在数据库中创建测试 Team。"""
    from common.db import get_db

    conn = get_db()
    conn.execute(
        "INSERT INTO teams (id, name, members, instructions, created_at, active) VALUES (?, ?, ?, ?, ?, 1)",
        (team_id, "TestTeam", json.dumps(members or []), instructions, "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
# 对话 CRUD
# ══════════════════════════════════════════════════════════════


def test_create_conversation(test_db_path):
    """创建对话"""
    from chat_engine import create_conversation

    _seed_agent("agent_conv_1")
    result = run(create_conversation("agent_conv_1", {"title": "测试对话"}))
    assert "id" in result
    assert result["agent_id"] == "agent_conv_1"
    assert result["title"] == "测试对话"


def test_list_conversations(test_db_path):
    """列出对话"""
    from chat_engine import create_conversation, list_conversations

    _seed_agent("agent_conv_2")
    run(create_conversation("agent_conv_2", {"title": "对话1"}))
    run(create_conversation("agent_conv_2", {"title": "对话2"}))

    result = run(list_conversations("agent_conv_2"))
    assert len(result) == 2


def test_delete_conversation(test_db_path):
    """删除对话（软删除）"""
    from chat_engine import create_conversation, delete_conversation, list_conversations

    _seed_agent("agent_conv_3")
    created = run(create_conversation("agent_conv_3", {"title": "待删除"}))
    run(delete_conversation(created["id"]))

    result = run(list_conversations("agent_conv_3"))
    assert len(result) == 0


def test_get_conversation(test_db_path):
    """获取对话详情（含消息）"""
    from chat_engine import add_conversation_message, create_conversation, get_conversation

    _seed_agent("agent_conv_4")
    conv = run(create_conversation("agent_conv_4", {"title": "测试"}))
    run(add_conversation_message(conv["id"], {"role": "user", "content": "你好"}))
    run(add_conversation_message(conv["id"], {"role": "assistant", "content": "你好！"}))

    result = run(get_conversation(conv["id"]))
    assert result["conversation"]["id"] == conv["id"]
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][1]["role"] == "assistant"


def test_add_conversation_message_empty(test_db_path):
    """添加空消息应拒绝"""
    from chat_engine import add_conversation_message

    with pytest.raises(Exception) as exc_info:
        run(add_conversation_message("fake_conv", {"role": "user", "content": ""}))
    assert "400" in str(exc_info.value) or "不能为空" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# Agent 运行（mock LLM）
# ══════════════════════════════════════════════════════════════


def test_run_agent(test_db_path):
    """运行 Agent（mock LLM 返回）"""
    from chat_engine import run_agent

    _seed_agent("agent_run_1", instructions="你是助手")
    with patch("chat_engine.call_llm", return_value="LLM 模拟回复"):
        result = run_agent("agent_run_1", {"message": "你好"})

    assert result["result"] == "LLM 模拟回复"
    assert result["agent_id"] == "agent_run_1"
    assert "elapsed" in result


def test_run_agent_no_message(test_db_path):
    """运行 Agent 时消息为空应拒绝"""
    from chat_engine import run_agent

    _seed_agent("agent_run_2")
    with pytest.raises(HTTPException) as exc:
        run_agent("agent_run_2", {"message": ""})
    assert exc.value.status_code == 400


def test_run_agent_not_found(test_db_path):
    """运行不存在的 Agent 应返回 404"""
    from chat_engine import run_agent

    with pytest.raises(Exception) as exc_info:
        run_agent("nonexistent_agent", {"message": "你好"})
    assert "404" in str(exc_info.value) or "不存在" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# Team 运行（mock LLM）
# ══════════════════════════════════════════════════════════════


def test_run_team(test_db_path):
    """运行 Team（mock LLM）"""
    from chat_engine import run_team

    _seed_agent("agent_member_1", name="MemberA", instructions="你是成员A")
    _seed_team("team_run_1", members=["agent_member_1"], instructions="团队指令")

    with patch("chat_engine.call_llm_async", new_callable=AsyncMock, return_value="团队模拟回复"):
        result = run(run_team("team_run_1", {"message": "执行任务"}))

    assert result["result"] == "团队模拟回复"
    assert result["team_id"] == "team_run_1"


def test_run_team_not_found(test_db_path):
    """运行不存在的 Team 应返回 404"""
    from chat_engine import run_team

    with pytest.raises(Exception) as exc_info:
        run(run_team("nonexistent_team", {"message": "你好"}))
    assert "404" in str(exc_info.value) or "不存在" in str(exc_info.value)
