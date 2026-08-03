#!/usr/bin/env python3
"""小团智能平台 — 集成测试（API 端点）"""

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


def test_create_agent_endpoint(test_db_path, auth_headers):
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
    response = client.post("/api/agents", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["name"] == "集成测试Agent"


def test_list_agents_endpoint(test_db_path, auth_headers):
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
    client.post("/api/agents", json=payload, headers=auth_headers)

    response = client.get("/api/agents", headers=auth_headers)
    assert response.status_code == 200
    agents = response.json()
    assert isinstance(agents, list)
    assert len(agents) >= 1


def test_update_agent_endpoint(test_db_path, auth_headers):
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
    create_resp = client.post("/api/agents", json=create_payload, headers=auth_headers)
    agent_id = create_resp.json()["id"]

    # 更新
    update_payload = {"name": "已更新Agent", "instructions": "新指令"}
    response = client.put(f"/api/agents/{agent_id}", json=update_payload, headers=auth_headers)
    assert response.status_code == 200

    # 验证：通过列表找到该 Agent
    list_resp = client.get("/api/agents", headers=auth_headers)
    agents = list_resp.json()
    matched = [a for a in agents if a["id"] == agent_id]
    assert len(matched) == 1
    assert matched[0]["name"] == "已更新Agent"


def test_delete_agent_endpoint(test_db_path, auth_headers):
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
    create_resp = client.post("/api/agents", json=create_payload, headers=auth_headers)
    agent_id = create_resp.json()["id"]

    # 删除
    response = client.delete(f"/api/agents/{agent_id}", headers=auth_headers)
    assert response.status_code == 200

    # 验证：查询时不应再出现
    list_resp = client.get("/api/agents", headers=auth_headers)
    agents = list_resp.json()
    agent_ids = [a["id"] for a in agents]
    assert agent_id not in agent_ids


def test_knowledge_base_crud(test_db_path, auth_headers):
    """测试知识库 CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建（后端生成 id，需从响应取）
    kb_payload = {
        "name": "集成测试知识库",
        "type": "file",
        "path": "/tmp/test_kb",
        "top_k": 3,
    }
    response = client.post("/api/knowledge-bases", json=kb_payload, headers=auth_headers)
    assert response.status_code == 200
    kb_id = response.json()["id"]

    # 列表
    response = client.get("/api/knowledge-bases", headers=auth_headers)
    assert response.status_code == 200
    kbs = response.json()
    assert any(kb["id"] == kb_id for kb in kbs)

    # 删除
    response = client.delete(f"/api/knowledge-bases/{kb_id}", headers=auth_headers)
    assert response.status_code == 200


def test_skill_crud(test_db_path, auth_headers):
    """测试 Skill CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建（后端生成 id，需从响应取）
    skill_payload = {
        "name": "集成测试Skill",
        "description": "用于集成测试",
        "content": "# 测试技能",
    }
    response = client.post("/api/skills", json=skill_payload, headers=auth_headers)
    assert response.status_code == 200
    skill_id = response.json()["id"]

    # 列表
    response = client.get("/api/skills", headers=auth_headers)
    assert response.status_code == 200
    skills = response.json()
    assert any(s["id"] == skill_id for s in skills)

    # 删除
    response = client.delete(f"/api/skills/{skill_id}", headers=auth_headers)
    assert response.status_code == 200


def test_skill_zip_import_export(test_db_path, auth_headers):
    """Skill ZIP 导入/导出冒烟测试（标准目录结构）"""
    import io
    import zipfile

    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 构造标准 skill zip（带公共顶层目录 demo-skill/）
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "demo-skill/SKILL.md",
            "---\nname: 演示技能\ndescription: ZIP导入演示\n---\n\n# 演示技能正文",
        )
        zf.writestr("demo-skill/scripts/hello.py", "print('hello from zip')")
        zf.writestr("demo-skill/references/notes.md", "参考资料")

    # 导入
    resp = client.post(
        "/api/skills/import-zip",
        files={"file": ("demo-skill.zip", buf.getvalue(), "application/zip")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "演示技能"
    assert data["imported"] == 3
    skill_id = data["id"]
    try:
        # 目录树 + 分目录统计
        tree_resp = client.get(f"/api/skills/{skill_id}/files/tree", headers=auth_headers)
        assert tree_resp.status_code == 200
        tree = tree_resp.json()
        assert tree["file_count"] == 3
        assert tree["dir_counts"] == {"scripts": 1, "references": 1, "examples": 0, "assets": 0}

        # 读取导入的文件
        file_resp = client.get(
            f"/api/skills/{skill_id}/file", params={"path": "scripts/hello.py"}, headers=auth_headers
        )
        assert file_resp.status_code == 200
        assert file_resp.json()["content"] == "print('hello from zip')"

        # 列表接口携带 dir_counts（前端徽章）
        list_resp = client.get("/api/skills", headers=auth_headers)
        match = next((s for s in list_resp.json() if s["id"] == skill_id), None)
        assert match is not None
        assert match["dir_counts"]["scripts"] == 1

        # 导出 zip 并校验内容
        exp_resp = client.get(f"/api/skills/{skill_id}/export-zip", headers=auth_headers)
        assert exp_resp.status_code == 200
        assert exp_resp.headers.get("content-type") == "application/zip"
        with zipfile.ZipFile(io.BytesIO(exp_resp.content)) as zf:
            names = zf.namelist()
        assert any(n.endswith("SKILL.md") for n in names)
        assert any(n.endswith("scripts/hello.py") for n in names)
        assert any(n.endswith("references/notes.md") for n in names)
    finally:
        client.delete(f"/api/skills/{skill_id}", headers=auth_headers)


def test_skill_file_crud_and_path_traversal(test_db_path, auth_headers):
    """Skill 文件接口 CRUD + 路径穿越拒绝"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    create_resp = client.post(
        "/api/skills",
        json={"name": "文件接口测试", "description": "", "content": "# 测试"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 200
    skill_id = create_resp.json()["id"]
    try:
        # 新建文件（自动创建父目录）
        put_resp = client.put(
            f"/api/skills/{skill_id}/file",
            params={"path": "scripts/run.py"},
            json={"content": "print('run')"},
            headers=auth_headers,
        )
        assert put_resp.status_code == 200

        # 读取
        get_resp = client.get(
            f"/api/skills/{skill_id}/file", params={"path": "scripts/run.py"}, headers=auth_headers
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["content"] == "print('run')"

        # 删除后读取 → 404
        del_resp = client.delete(
            f"/api/skills/{skill_id}/file", params={"path": "scripts/run.py"}, headers=auth_headers
        )
        assert del_resp.status_code == 200
        get_resp2 = client.get(
            f"/api/skills/{skill_id}/file", params={"path": "scripts/run.py"}, headers=auth_headers
        )
        assert get_resp2.status_code == 404

        # 路径穿越 → 400
        for bad in ("../../etc/passwd", "..", "/etc/passwd"):
            assert client.get(
                f"/api/skills/{skill_id}/file", params={"path": bad}, headers=auth_headers
            ).status_code == 400
            assert client.put(
                f"/api/skills/{skill_id}/file", params={"path": bad},
                json={"content": "x"}, headers=auth_headers,
            ).status_code == 400
    finally:
        client.delete(f"/api/skills/{skill_id}", headers=auth_headers)


def test_config_get_endpoint(test_db_path):
    """测试获取配置端点（公开）"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "api_url" in data
    assert "model_name" in data
    assert "api_key" in data


def test_config_update_endpoint(test_db_path, auth_headers):
    """测试更新配置端点"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    payload = {
        "api_url": "https://custom-api.example.com/v1",
        "model_name": "custom-model",
    }
    response = client.post("/api/config/save", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


def test_mcp_server_crud(test_db_path, auth_headers):
    """测试 MCP Server CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    # 创建（后端生成 id，需从响应取）
    mcp_payload = {
        "name": "集成测试MCP",
        "transport_type": "stdio",
        "command": "node",
        "args": ["server.js"],
        "env": {},
    }
    response = client.post("/api/mcp-servers", json=mcp_payload, headers=auth_headers)
    assert response.status_code == 200
    server_id = response.json()["id"]

    # 列表
    response = client.get("/api/mcp-servers", headers=auth_headers)
    assert response.status_code == 200

    # 删除
    response = client.delete(f"/api/mcp-servers/{server_id}", headers=auth_headers)
    assert response.status_code == 200


def test_usage_stats_endpoint(test_db_path):
    """测试使用统计端点（公开）"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    response = client.get("/api/usage-stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "by_type" in data
    assert "avg_response_time" in data
    assert "success_rate" in data


# ══════════════════════════════════════════════════════════════
# v8.0 新增集成测试
# ══════════════════════════════════════════════════════════════

def test_workflow_crud_and_run(test_db_path, auth_headers):
    """工作流 CRUD + 执行"""
    from fastapi.testclient import TestClient
    from main import app
    from unittest.mock import patch

    client = TestClient(app)

    # 1. 创建工作流（含 delay 节点）
    nodes = [{"id": "n1", "type": "delay", "config": {"seconds": 0.01}, "name": "delay1"}]
    create_resp = client.post("/api/workflows", json={
        "name": "集成测试工作流",
        "description": "用于测试",
        "steps": nodes,
        "connections": [],
    }, headers=auth_headers)
    assert create_resp.status_code == 200
    wf_id = create_resp.json()["id"]

    # 2. 获取工作流详情
    get_resp = client.get(f"/api/workflows/{wf_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "集成测试工作流"

    # 3. 列出工作流
    list_resp = client.get("/api/workflows", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(w["id"] == wf_id for w in list_resp.json())

    # 4. 执行工作流
    run_resp = client.post(f"/api/workflows/{wf_id}/run", json={"message": "test"}, headers=auth_headers)
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["engine"] in ("executor", "simple")

    # 5. 更新工作流
    update_resp = client.put(f"/api/workflows/{wf_id}", json={"name": "已更新工作流"}, headers=auth_headers)
    assert update_resp.status_code == 200

    # 6. 验证更新
    get_resp2 = client.get(f"/api/workflows/{wf_id}", headers=auth_headers)
    assert get_resp2.json()["name"] == "已更新工作流"


def test_prd_pipeline(test_db_path, auth_headers):
    """PRD 流水线：生成 → 审查 → 技术方案（mock LLM）"""
    from fastapi.testclient import TestClient
    from main import app
    from unittest.mock import patch

    client = TestClient(app)

    with patch("prd_engine.call_llm", return_value="# PRD 文档\n## 背景\n测试PRD"):
        gen_resp = client.post("/api/prd/generate", json={"prd_text": "做一个用户系统"}, headers=auth_headers)
    assert gen_resp.status_code == 200
    prd_text = gen_resp.json()["result"]
    assert "PRD" in prd_text

    with patch("prd_engine.call_llm", return_value="审查报告：评分 90/100"):
        review_resp = client.post("/api/prd/review", json={"prd_text": prd_text}, headers=auth_headers)
    assert review_resp.status_code == 200
    assert "90" in review_resp.json()["result"]

    with patch("prd_engine.call_llm", return_value="# 技术方案\n## 架构总览"):
        td_resp = client.post("/api/prd/technical-design", json={"prd_text": prd_text}, headers=auth_headers)
    assert td_resp.status_code == 200
    assert "技术方案" in td_resp.json()["result"]


def test_prd_test_cases_and_code(test_db_path, auth_headers):
    """PRD 测试用例 + 代码生成（mock LLM）"""
    from fastapi.testclient import TestClient
    from main import app
    from unittest.mock import patch

    client = TestClient(app)

    with patch("prd_engine.call_llm", return_value="| 编号 | 步骤 | 预期结果 |"):
        tc_resp = client.post("/api/prd/test-cases", json={
            "prd_text": "# PRD\n用户注册",
            "tech_design": "# 技术方案\nREST API",
        }, headers=auth_headers)
    assert tc_resp.status_code == 200
    assert "编号" in tc_resp.json()["result"]

    with patch("prd_engine.call_llm", return_value="```python\nprint('hello')\n```"):
        code_resp = client.post("/api/prd/generate-code", json={
            "tech_design": "# 技术方案\nREST API",
            "language": "python",
        }, headers=auth_headers)
    assert code_resp.status_code == 200
    assert code_resp.json()["language"] == "python"


def test_comments_crud_and_like(test_db_path, auth_headers):
    """评论 CRUD + 点赞"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # 1. 创建评论
    create_resp = client.post("/api/comments", json={
        "content": "集成测试评论",
        "author_id": "user_int_test",
        "target_type": "requirement",
        "target_id": "req_int_test",
    }, headers=auth_headers)
    assert create_resp.status_code == 200
    comment_id = create_resp.json()["id"]

    # 2. 列出评论
    list_resp = client.get("/api/comments", params={
        "target_type": "requirement",
        "target_id": "req_int_test",
    }, headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(c["id"] == comment_id for c in list_resp.json())

    # 3. 获取评论线程
    thread_resp = client.get("/api/comments/thread", params={
        "target_type": "requirement",
        "target_id": "req_int_test",
    }, headers=auth_headers)
    assert thread_resp.status_code == 200
    assert len(thread_resp.json()) >= 1

    # 4. 点赞
    like_resp = client.post(f"/api/comments/{comment_id}/like", json={"user_id": "user_like"}, headers=auth_headers)
    assert like_resp.status_code == 200
    assert like_resp.json()["liked"] is True
    assert like_resp.json()["likes"] == 1

    # 5. 取消点赞
    unlike_resp = client.post(f"/api/comments/{comment_id}/like", json={"user_id": "user_like"}, headers=auth_headers)
    assert unlike_resp.status_code == 200
    assert unlike_resp.json()["liked"] is False

    # 6. 删除评论
    del_resp = client.delete(f"/api/comments/{comment_id}", headers=auth_headers)
    assert del_resp.status_code == 200

    # 7. 验证删除
    list_resp2 = client.get("/api/comments", params={
        "target_type": "requirement",
        "target_id": "req_int_test",
    }, headers=auth_headers)
    assert all(c["id"] != comment_id for c in list_resp2.json())


def test_sandbox_project_crud(test_db_path, auth_headers):
    """沙箱项目 CRUD（mock process_manager）"""
    from fastapi.testclient import TestClient
    from main import app
    from unittest.mock import patch, MagicMock

    client = TestClient(app)

    # mock process_manager 避免依赖 Docker
    mock_pm = MagicMock()
    mock_pm.create_container.return_value = {"status": "created", "container_id": "mock_ctr_1"}
    mock_pm.get_status.return_value = {"state": "created"}
    mock_pm.remove_container.return_value = {"success": True}

    with patch.dict("sys.modules", {"sandbox": MagicMock(process_manager=mock_pm)}):
        # 1. 创建沙箱项目
        create_resp = client.post("/api/sandbox/projects", json={
            "name": "测试沙箱",
            "image": "python:3.11-slim",
            "ports": ["8888:8888"],
            "command": "python main.py",
        }, headers=auth_headers)
        assert create_resp.status_code == 200
        project_id = create_resp.json()["id"]

        # 2. 列出沙箱项目
        list_resp = client.get("/api/sandbox/projects", headers=auth_headers)
        assert list_resp.status_code == 200
        assert any(p["id"] == project_id for p in list_resp.json())

        # 3. 获取项目状态
        get_resp = client.get(f"/api/sandbox/projects/{project_id}", headers=auth_headers)
        assert get_resp.status_code == 200

        # 4. 删除项目
        del_resp = client.delete(f"/api/sandbox/projects/{project_id}", headers=auth_headers)
        assert del_resp.status_code == 200

        # 5. 验证删除
        list_resp2 = client.get("/api/sandbox/projects", headers=auth_headers)
        assert all(p["id"] != project_id for p in list_resp2.json())


def test_team_workflow_and_conversation(test_db_path, auth_headers):
    """Team 管理 + 对话创建 + 插件列表"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # 1. 创建 Team
    team_resp = client.post("/api/teams", json={
        "name": "集成测试Team",
        "description": "用于测试",
        "members": [],
        "instructions": "团队指令",
    }, headers=auth_headers)
    assert team_resp.status_code == 200
    team_id = team_resp.json()["id"]

    # 2. 列出 Team
    list_resp = client.get("/api/teams", headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(t["id"] == team_id for t in list_resp.json())

    # 3. 获取插件列表
    plugins_resp = client.get("/api/plugins")
    assert plugins_resp.status_code == 200
    plugins_data = plugins_resp.json()
    assert "plugins" in plugins_data
    assert "categories" in plugins_data
    assert plugins_data["total"] > 0


def test_artifacts_crud(test_db_path, auth_headers):
    """成果仓库 CRUD"""
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # 1. 创建项目
    proj_resp = client.post("/api/projects", json={
        "name": "成果测试项目",
        "description": "用于测试",
    }, headers=auth_headers)
    assert proj_resp.status_code == 200
    proj_id = proj_resp.json()["id"]

    # 2. 创建成果
    art_resp = client.post("/api/artifacts", json={
        "project_id": proj_id,
        "type": "doc",
        "content": {"title": "测试成果", "body": "内容"},
    }, headers=auth_headers)
    assert art_resp.status_code == 200
    art_id = art_resp.json()["id"]

    # 3. 列出成果
    list_resp = client.get("/api/artifacts", params={"project_id": proj_id}, headers=auth_headers)
    assert list_resp.status_code == 200
    assert any(a["id"] == art_id for a in list_resp.json())

    # 4. 项目成果列表
    proj_art_resp = client.get(f"/api/projects/{proj_id}/artifacts", headers=auth_headers)
    assert proj_art_resp.status_code == 200
    assert len(proj_art_resp.json()) >= 1

    # 5. 删除成果
    del_resp = client.delete(f"/api/artifacts/{art_id}", headers=auth_headers)
    assert del_resp.status_code == 200
