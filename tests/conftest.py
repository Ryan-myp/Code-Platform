#!/usr/bin/env python3
"""智能研发平台 — 测试配置 fixtures"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# 添加 backend 到路径
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def setup_test_db():
    """为每个测试创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    original_db_path = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = db_path
    # 重置 Config 模块缓存
    if "config" in sys.modules:
        del sys.modules["config"]
    if "database" in sys.modules:
        del sys.modules["database"]
    from database import init_db
    init_db()
    yield db_path
    # Cleanup
    if original_db_path:
        os.environ["DB_PATH"] = original_db_path
    elif "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture
def test_db_path(setup_test_db):
    """返回临时数据库路径"""
    return setup_test_db


@pytest.fixture
def sample_agent_data():
    """示例 Agent 数据"""
    return {
        "id": "agent_test_001",
        "name": "测试Agent",
        "description": "用于单元测试的Agent",
        "instructions": "你是一个测试助手",
        "model": "agnes-2.0-flash",
        "enable_memory": False,
        "enable_reasoning": False,
        "tools": [],
        "knowledge_base_ids": [],
        "skill_ids": [],
        "mcp_server_ids": [],
    }


@pytest.fixture
def sample_knowledge_base_data():
    """示例知识库数据"""
    return {
        "id": "kb_test_001",
        "name": "测试知识库",
        "type": "file",
        "path": "/tmp/test_kb",
        "top_k": 3,
    }


@pytest.fixture
def sample_skill_data():
    """示例 Skill 数据"""
    return {
        "id": "skill_test_001",
        "name": "测试Skill",
        "description": "用于单元测试的Skill",
        "content": "# 技能说明\n这是一个测试技能",
    }


@pytest.fixture
def sample_mcp_server_data():
    """示例 MCP Server 数据"""
    return {
        "id": "mcp_test_001",
        "name": "测试MCP",
        "transport_type": "stdio",
        "command": "node",
        "args": ["server.js"],
        "env": {},
    }


@pytest.fixture
def sample_project_data():
    """示例项目数据"""
    return {
        "id": "proj_test_001",
        "name": "测试项目",
        "description": "用于单元测试的项目",
        "status": "planning",
        "team_id": "",
    }


@pytest.fixture
def sample_requirement_data():
    """示例需求数据"""
    return {
        "id": "req_test_001",
        "name": "测试需求",
        "description": "用于单元测试的需求",
        "status": "draft",
        "priority": "P1",
        "project_id": "proj_test_001",
        "creator": "tester",
    }


@pytest.fixture
def sample_task_data():
    """示例任务数据"""
    return {
        "id": "task_test_001",
        "project_id": "proj_test_001",
        "title": "测试任务",
        "description": "用于单元测试的任务",
        "type": "prd",
        "assignee": "dev1",
        "status": "todo",
        "priority": "P1",
    }
