#!/usr/bin/env python3
"""智能研发平台 — 集成测试（API 端点）"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_health_endpoint(test_db_path):
    """测试健康检查端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_create_agent_endpoint(test_db_path):
    """测试创建 Agent 端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    payload = {
        "name": "集成测试Agent",
        "description": "用于集成测试",
        "instructions": "你是一个测试助手",
        "model": "agnes-2.0-flash",
        "enable_memory": False,
        "enable_reasoning": False,
        "tools": [],
        "knowledge_base_ids": [],
        "skill_ids": [],
        "mcp_server_ids": [],
    }
    response = client.post("/api/agents", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["message"] == "Agent created successfully"


def test_list_agents_endpoint(test_db_path):
    """测试列出 Agent 端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 先创建一个
    payload = {
        "name": "列表测试Agent",
        "description": "",
        "instructions": "",
        "model": "agnes-2.0-flash",
        "enable_memory": False,
        "enable_reasoning": False,
        "tools": [],
        "knowledge_base_ids": [],
        "skill_ids": [],
        "mcp_server_ids": [],
    }
    client.post("/api/agents", json=payload)

    response = client.get("/api/agents")
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) >= 1


def test_get_agent_not_found(test_db_path):
    """测试获取不存在的 Agent"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/api/agents/nonexistent")
    assert response.status_code == 404


def test_update_agent_endpoint(test_db_path):
    """测试更新 Agent 端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建
    create_payload = {
        "name": "待更新Agent",
        "description": "",
        "instructions": "原始指令",
        "model": "agnes-2.0-flash",
        "enable_memory": False,
        "enable_reasoning": False,
        "tools": [],
        "knowledge_base_ids": [],
        "skill_ids": [],
        "mcp_server_ids": [],
    }
    create_resp = client.post("/api/agents", json=create_payload)
    agent_id = create_resp.json()["id"]

    # 更新
    update_payload = {"name": "已更新Agent", "instructions": "新指令"}
    response = client.put(f"/api/agents/{agent_id}", json=update_payload)
    assert response.status_code == 200

    # 验证
    get_resp = client.get(f"/api/agents/{agent_id}")
    data = get_resp.json()
    assert data["name"] == "已更新Agent"


def test_delete_agent_endpoint(test_db_path):
    """测试删除 Agent 端点（软删除）"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建
    create_payload = {
        "name": "待删除Agent",
        "description": "",
        "instructions": "",
        "model": "agnes-2.0-flash",
        "enable_memory": False,
        "enable_reasoning": False,
        "tools": [],
        "knowledge_base_ids": [],
        "skill_ids": [],
        "mcp_server_ids": [],
    }
    create_resp = client.post("/api/agents", json=create_payload)
    agent_id = create_resp.json()["id"]

    # 删除
    response = client.delete(f"/api/agents/{agent_id}")
    assert response.status_code == 200

    # 验证：查询时不应再出现
    list_resp = client.get("/api/agents")
    agents = list_resp.json()
    agent_ids = [a["id"] for a in agents]
    assert agent_id not in agent_ids


def test_knowledge_base_crud(test_db_path):
    """测试知识库 CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建
    kb_payload = {
        "id": "kb_integration_001",
        "name": "集成测试知识库",
        "type": "file",
        "path": "/tmp/test_kb",
        "top_k": 3,
    }
    response = client.post("/api/knowledge-bases", json=kb_payload)
    assert response.status_code == 200

    # 列表
    response = client.get("/api/knowledge-bases")
    assert response.status_code == 200
    kbs = response.json()
    assert any(kb["id"] == "kb_integration_001" for kb in kbs)

    # 删除
    response = client.delete("/api/knowledge-bases/kb_integration_001")
    assert response.status_code == 200


def test_skill_crud(test_db_path):
    """测试 Skill CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建
    skill_payload = {
        "id": "skill_integration_001",
        "name": "集成测试Skill",
        "description": "用于集成测试",
        "content": "# 测试技能",
    }
    response = client.post("/api/skills", json=skill_payload)
    assert response.status_code == 200

    # 列表
    response = client.get("/api/skills")
    assert response.status_code == 200
    skills = response.json()
    assert any(s["id"] == "skill_integration_001" for s in skills)

    # 删除
    response = client.delete("/api/skills/skill_integration_001")
    assert response.status_code == 200


def test_config_get_endpoint(test_db_path):
    """测试获取配置端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "api_url" in data
    assert "model_name" in data
    assert "has_api_key" in data


def test_config_update_endpoint(test_db_path):
    """测试更新配置端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    payload = {
        "api_url": "https://custom-api.example.com/v1",
        "model_name": "custom-model",
    }
    response = client.post("/api/config", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


def test_mcp_server_crud(test_db_path):
    """测试 MCP Server CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建
    mcp_payload = {
        "id": "mcp_integration_001",
        "name": "集成测试MCP",
        "transport_type": "stdio",
        "command": "node",
        "args": ["server.js"],
        "env": {},
    }
    response = client.post("/api/mcp-servers", json=mcp_payload)
    assert response.status_code == 200

    # 列表
    response = client.get("/api/mcp-servers")
    assert response.status_code == 200

    # 删除
    response = client.delete("/api/mcp-servers/mcp_integration_001")
    assert response.status_code == 200


def test_usage_stats_endpoint(test_db_path):
    """测试使用统计端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/api/usage-stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_requests" in data
    assert "by_task_type" in data
    assert "avg_response_time" in data
    assert "error_rate" in data
