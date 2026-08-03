#!/usr/bin/env python3
"""种子数据脚本 — 首次启动时灌入示例数据，确保每个页面都有真实内容。

使用方式：
  from seed_data import seed_if_empty
  seed_if_empty()   # 幂等：已存在则跳过
"""

import json
import logging
from datetime import datetime

from common.db import get_db

logger = logging.getLogger(__name__)

_NOW = datetime.now().isoformat()


def _row_exists(conn, table: str, row_id: str) -> bool:
    return conn.execute(
        f"SELECT 1 FROM {table} WHERE id=?", (row_id,)
    ).fetchone() is not None


def _insert_agents(conn):
    agents = [
        (
            "agent-1", "产品经理助手", "负责需求分析、PRD撰写和产品规划的智能助手",
            "你是「产品经理助手」，一个专注于产品管理的专业AI助手。重要规则：\n1. 永远不要说自己是 Agnes 或其他模型名称\n2. 当被问到身份时，只介绍自己是「产品经理助手」\n3. 你的专长是用户需求分析、产品规划和PRD文档撰写\n4. 以专业产品经理的身份回答所有问题",
            "gpt-4o", 1, 1,
            json.dumps(["web_search", "code_interpreter"]),
            json.dumps(["kb-1"]),
            json.dumps(["skill-1"]),
            json.dumps(["mcp-1"]),
            _NOW, 1,
        ),
        (
            "agent-2", "代码开发助手", "根据需求生成代码、进行代码审查和重构",
            "你是「代码开发助手」，一个专注于软件开发的专业AI助手。重要规则：\n1. 永远不要说自己是 Agnes 或其他模型名称\n2. 当被问到身份时，只介绍自己是「代码开发助手」\n3. 你是一名资深全栈工程师，精通Python、JavaScript、TypeScript等多种编程语言\n4. 以专业工程师的身份回答所有编程问题",
            "agnes-2.5-flash", 1, 1,
            json.dumps(["code_interpreter", "file_system"]),
            json.dumps(["kb-2"]),
            json.dumps(["skill-2"]),
            json.dumps(["mcp-2"]),
            _NOW, 1,
        ),
        (
            "agent-3", "测试工程师助手", "自动生成测试用例、执行测试并报告结果",
            "你是「测试工程师助手」，一个专注于软件测试的专业AI助手。重要规则：\n1. 永远不要说自己是 Agnes 或其他模型名称\n2. 当被问到身份时，只介绍自己是「测试工程师助手」\n3. 你是一名资深测试工程师，擅长设计测试用例、自动化测试和缺陷分析\n4. 以专业测试工程师的身份回答所有问题",
            "claude-3", 1, 1,
            json.dumps(["code_interpreter", "terminal"]),
            json.dumps(["kb-2"]),
            json.dumps(["skill-3"]),
            json.dumps(["mcp-2"]),
            _NOW, 1,
        ),
        (
            "agent-4", "架构设计助手", "系统架构设计、技术选型和设计模式建议",
            "你是「架构设计助手」，一个专注于系统架构的专业AI助手。重要规则：\n1. 永远不要说自己是 Agnes 或其他模型名称\n2. 当被问到身份时，只介绍自己是「架构设计助手」\n3. 你是一名资深架构师，熟悉分布式系统、微服务架构和云原生技术\n4. 以专业架构师的身份回答所有问题",
            "qwen-max", 1, 1,
            json.dumps(["web_search", "code_interpreter"]),
            json.dumps(["kb-1", "kb-3"]),
            json.dumps(["skill-1"]),
            json.dumps(["mcp-1", "mcp-3"]),
            _NOW, 1,
        ),
        (
            "agent-5", "运维工程师助手", "部署、监控、故障排查和性能优化",
            "你是「运维工程师助手」，一个专注于运维和SRE的专业AI助手。重要规则：\n1. 永远不要说自己是 Agnes 或其他模型名称\n2. 当被问到身份时，只介绍自己是「运维工程师助手」\n3. 你是一名资深SRE工程师，擅长DevOps、容器化部署和系统监控\n4. 以专业运维工程师的身份回答所有问题",
            "agnes-2.5-flash", 1, 0,
            json.dumps(["terminal", "file_system"]),
            json.dumps(["kb-3"]),
            json.dumps(["skill-2"]),
            json.dumps(["mcp-2"]),
            _NOW, 1,
        ),
    ]
    for a in agents:
        if _row_exists(conn, "agents", a[0]):
            continue
        conn.execute(
            """INSERT INTO agents (id, name, description, instructions, model,
               enable_memory, enable_reasoning, tools, knowledge_base_ids,
               skill_ids, mcp_server_ids, created_at, active)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", a,
        )
    logger.info("Agents seeded: %d rows", len(agents))


def _insert_teams(conn):
    teams = [
        (
            "team-1", "产品研发团队", "覆盖需求到上线的完整研发团队",
            "coordinate",
            json.dumps(["agent-1", "agent-2", "agent-3"]),
            "由产品经理牵头，协调开发和测试完成交付",
            0, _NOW, 1,
        ),
        (
            "team-2", "架构设计团队", "专注于系统架构和技术选型",
            "debate",
            json.dumps(["agent-4", "agent-2"]),
            "由架构师主导，与开发Agent讨论技术方案",
            0, _NOW, 1,
        ),
        (
            "team-3", "运维与交付团队", "负责部署、监控和持续运营",
            "coordinate",
            json.dumps(["agent-5", "agent-2"]),
            "由SRE牵头，协调开发完成部署",
            1, _NOW, 1,
        ),
    ]
    for t in teams:
        if _row_exists(conn, "teams", t[0]):
            continue
        conn.execute(
            """INSERT INTO teams (id, name, description, mode, members,
               instructions, respond_directly, created_at, active)
               VALUES (?,?,?,?,?,?,?,?,?)""", t,
        )
    logger.info("Teams seeded: %d rows", len(teams))


def _insert_workflows(conn):
    # 节点需要 x/y 坐标供前端画布定位；边使用 from/to 与前端一致
    wf1_nodes = [
        {"id": "n1", "type": "agent", "label": "开始", "x": 80, "y": 160, "config": {}},
        {"id": "n2", "type": "agent", "label": "需求分析", "x": 260, "y": 160, "config": {"agent_id": "agent-1"}},
        {"id": "n3", "type": "agent", "label": "代码生成", "x": 440, "y": 160, "config": {"agent_id": "agent-2"}},
        {"id": "n4", "type": "agent", "label": "测试用例", "x": 620, "y": 160, "config": {"agent_id": "agent-3"}},
        {"id": "n5", "type": "output", "label": "结束", "x": 800, "y": 160, "config": {}},
    ]
    wf1_edges = [
        {"id": "e1", "from": "n1", "to": "n2"},
        {"id": "e2", "from": "n2", "to": "n3"},
        {"id": "e3", "from": "n3", "to": "n4"},
        {"id": "e4", "from": "n4", "to": "n5"},
    ]
    wf2_nodes = [
        {"id": "n1", "type": "agent", "label": "开始", "x": 80, "y": 160, "config": {}},
        {"id": "n2", "type": "agent", "label": "架构设计", "x": 260, "y": 160, "config": {"agent_id": "agent-4"}},
        {"id": "n3", "type": "condition", "label": "方案评审", "x": 440, "y": 160, "config": {"expression": ""}},
        {"id": "n4", "type": "agent", "label": "代码实现", "x": 620, "y": 160, "config": {"agent_id": "agent-2"}},
        {"id": "n5", "type": "output", "label": "结束", "x": 800, "y": 160, "config": {}},
    ]
    wf2_edges = [
        {"id": "e1", "from": "n1", "to": "n2"},
        {"id": "e2", "from": "n2", "to": "n3"},
        {"id": "e3", "from": "n3", "to": "n4"},
        {"id": "e4", "from": "n4", "to": "n5"},
    ]
    wf3_nodes = [
        {"id": "n1", "type": "agent", "label": "开始", "x": 80, "y": 160, "config": {}},
        {"id": "n2", "type": "http", "label": "读取配置", "x": 260, "y": 160, "config": {"url": "/api/config", "method": "GET"}},
        {"id": "n3", "type": "code", "label": "生成部署脚本", "x": 440, "y": 160, "config": {"code": "print('deploy')", "language": "python"}},
        {"id": "n4", "type": "http", "label": "部署到沙箱", "x": 620, "y": 160, "config": {"url": "/api/deploy", "method": "POST"}},
        {"id": "n5", "type": "output", "label": "结束", "x": 800, "y": 160, "config": {}},
    ]
    wf3_edges = [
        {"id": "e1", "from": "n1", "to": "n2"},
        {"id": "e2", "from": "n2", "to": "n3"},
        {"id": "e3", "from": "n3", "to": "n4"},
        {"id": "e4", "from": "n4", "to": "n5"},
    ]
    workflows = [
        ("wf-1", "标准研发流程", "需求→设计→编码→测试→上线",
         json.dumps(wf1_nodes), json.dumps(wf1_edges), _NOW, 1),
        ("wf-2", "架构驱动研发", "架构设计→方案评审→代码实现",
         json.dumps(wf2_nodes), json.dumps(wf2_edges), _NOW, 1),
        ("wf-3", "自动化部署流程", "配置读取→脚本生成→沙箱部署",
         json.dumps(wf3_nodes), json.dumps(wf3_edges), _NOW, 1),
    ]
    for w in workflows:
        if _row_exists(conn, "workflows", w[0]):
            # 始终更新工作流数据，确保格式正确
            conn.execute(
                "UPDATE workflows SET steps=?, connections=? WHERE id=?",
                (w[3], w[4], w[0]),
            )
        else:
            conn.execute(
                """INSERT INTO workflows (id, name, description, steps, connections, created_at, active)
               VALUES (?,?,?,?,?,?,?)""", w,
            )
    logger.info("Workflows seeded: %d rows", len(workflows))


def _insert_requirements(conn):
    reqs = [
        (
            "req-1", "用户登录注册功能",
            "实现支持邮箱/手机号的用户注册和登录流程，包含密码重置功能",
            "completed", "P0", "proj-1", "admin",
            "# 用户登录注册 PRD\n\n## 功能需求\n1. 邮箱注册\n2. 手机号注册\n3. 密码登录\n4. 社交登录（微信/GitHub）\n5. 密码重置",
            "代码审查通过，测试覆盖率 95%",
            "技术方案：JWT + OAuth2，使用 Redis 存储登录态",
            "覆盖正常登录、异常登录、第三方登录等场景",
            json.dumps([
                {"file": "auth/login.py", "status": "approved"},
                {"file": "auth/register.py", "status": "approved"},
            ]),
            2, _NOW, _NOW, 1,
        ),
        (
            "req-2", "产品数据统计看板",
            "为产品经理提供实时数据可视化，包括用户活跃、转化漏斗、留存分析",
            "in_progress", "P1", "proj-1", "admin",
            "# 数据统计看板 PRD\n\n## 核心指标\n- DAU/MAU\n- 转化漏斗\n- 留存曲线\n- 功能使用热图",
            "",
            "技术方案：ClickHouse + Grafana 集成",
            "",
            json.dumps([
                {"file": "analytics/dashboard.py", "status": "in_progress"},
            ]),
            1, _NOW, _NOW, 1,
        ),
        (
            "req-3", "Agent 工作流编辑器",
            "可视化拖拽式编辑器，支持节点配置、连线、调试",
            "draft", "P0", "proj-2", "admin",
            "# 工作流编辑器 PRD\n\n## 功能\n1. 画布拖拽\n2. 节点属性配置\n3. 连线规则\n4. 实时调试",
            "",
            "React Flow 实现画布，WebSocket 实时通信",
            "",
            "",
            1, _NOW, _NOW, 1,
        ),
        (
            "req-4", "多团队协作管理",
            "支持多团队并行工作、任务分配、进度同步",
            "review", "P1", "proj-2", "admin",
            "# 协作管理 PRD\n\n## 功能\n- 团队创建/成员管理\n- 任务看板\n- 进度追踪",
            "需求评审通过，进入技术设计阶段",
            "",
            "",
            "",
            1, _NOW, _NOW, 1,
        ),
        (
            "req-5", "AI 代码审查助手",
            "集成到开发流程中，自动审查代码并提供改进建议",
            "planned", "P2", "proj-3", "admin",
            "# AI 代码审查 PRD\n\n## 功能\n1. PR 自动触发审查\n2. 代码质量评分\n3. 改进建议\n4. 安全漏洞检测",
            "",
            "",
            "",
            "",
            1, _NOW, _NOW, 1,
        ),
    ]
    for r in reqs:
        if _row_exists(conn, "requirements", r[0]):
            continue
        conn.execute(
            """INSERT INTO requirements (id, name, description, status, priority,
               project_id, creator, prd_text, review_report, tech_design,
               test_cases, code, version, created_at, updated_at, active)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", r,
        )
    logger.info("Requirements seeded: %d rows", len(reqs))


def _insert_knowledge_bases(conn):
    kbs = [
        (
            "kb-1", "产品设计知识库", "file",
            "/data/knowledge/product_design",
            "https://confluence.example.com/product",
            json.dumps({"tags": ["产品", "设计"]}), 5, _NOW, 1,
        ),
        (
            "kb-2", "技术开发知识库", "file",
            "/data/knowledge/tech_dev",
            "https://confluence.example.com/tech",
            json.dumps({"tags": ["技术", "开发"]}), 5, _NOW, 1,
        ),
        (
            "kb-3", "运维部署知识库", "url",
            "",
            "https://wiki.example.com/devops",
            json.dumps({"tags": ["运维", "DevOps"]}), 3, _NOW, 1,
        ),
    ]
    for kb in kbs:
        if _row_exists(conn, "knowledge_bases", kb[0]):
            continue
        conn.execute(
            """INSERT INTO knowledge_bases (id, name, type, path, url, filter, top_k, created_at, active)
               VALUES (?,?,?,?,?,?,?,?,?)""", kb,
        )
    logger.info("Knowledge Bases seeded: %d rows", len(kbs))


def _insert_mcp_servers(conn):
    servers = [
        (
            "mcp-1", "Filesystem MCP Server", "stdio",
            "npx", json.dumps(["-y", "@modelcontextprotocol/server-filesystem"]),
            json.dumps({"NODE_ENV": "production"}),
            "", 1, _NOW,
        ),
        (
            "mcp-2", "GitHub MCP Server", "http",
            "", json.dumps([]),
            json.dumps({"GITHUB_TOKEN": "ghp_xxxx"}),
            "https://mcp.example.com/github", 1, _NOW,
        ),
        (
            "mcp-3", "Database MCP Server", "stdio",
            "python3", json.dumps(["-m", "mcp_server_db"]),
            json.dumps({"DB_HOST": "localhost", "DB_PORT": "5432"}),
            "", 1, _NOW,
        ),
    ]
    for s in servers:
        if _row_exists(conn, "mcp_servers", s[0]):
            continue
        conn.execute(
            """INSERT INTO mcp_servers (id, name, transport_type, command, args, env, url, enabled, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""", s,
        )
    logger.info("MCP Servers seeded: %d rows", len(servers))


def _insert_skills(conn):
    skills = [
        (
            "skill-1", "PRD 撰写技能",
            "结构化撰写产品需求文档，包含用户故事、验收标准、排期建议",
            "你是一名PRD撰写专家。请根据以下输入生成一份完整的PRD文档，包括：\n1. 产品概述\n2. 用户故事\n3. 功能需求\n4. 非功能需求\n5. 验收标准\n6. 排期建议",
            json.dumps({}), json.dumps([]),
            json.dumps([]), json.dumps([]),
            _NOW, 1,
        ),
        (
            "skill-2", "代码审查技能",
            "对代码进行静态分析、风格检查和最佳实践建议",
            "你是一名代码审查专家。请审查以下代码，关注：\n1. 代码风格\n2. 潜在Bug\n3. 性能问题\n4. 安全性\n5. 可维护性",
            json.dumps({}), json.dumps([]),
            json.dumps([]), json.dumps([]),
            _NOW, 1,
        ),
        (
            "skill-3", "测试用例设计技能",
            "基于需求自动生成测试用例，覆盖功能/边界/异常场景",
            "你是一名测试专家。请根据以下需求描述生成测试用例，包含：\n1. 正向用例\n2. 边界用例\n3. 异常用例\n4. 性能用例\n请使用表格格式输出。",
            json.dumps({}), json.dumps([]),
            json.dumps([]), json.dumps([]),
            _NOW, 1,
        ),
    ]
    for s in skills:
        if _row_exists(conn, "skills", s[0]):
            continue
        conn.execute(
            """INSERT INTO skills (id, name, description, content, `references`, templates, scripts, assets, created_at, active)
               VALUES (?,?,?,?,?,?,?,?,?,?)""", s,
        )
    logger.info("Skills seeded: %d rows", len(skills))


def _insert_projects(conn):
    projects = [
        (
            "proj-1", "小团智能平台",
            "AI 赋能各行业的智能平台，覆盖创作、翻译、分析、办公等全场景工具",
            "active", "team-1", _NOW, _NOW, 1,
        ),
        (
            "proj-2", "Agent 工作流系统",
            "可编排的 Agent 工作流引擎，支持多 Agent 协作完成复杂任务",
            "active", "team-2", _NOW, _NOW, 1,
        ),
        (
            "proj-3", "AI 代码审查系统",
            "集成 AI 的自动化代码审查系统，提升代码质量",
            "planning", "team-3", _NOW, _NOW, 1,
        ),
    ]
    for p in projects:
        if _row_exists(conn, "projects", p[0]):
            continue
        conn.execute(
            """INSERT INTO projects (id, name, description, status, team_id, created_at, updated_at, active)
               VALUES (?,?,?,?,?,?,?,?)""", p,
        )
    logger.info("Projects seeded: %d rows", len(projects))


def _insert_sandbox_projects(conn):
    sandboxes = [
        (
            "sp-1", "Hello World API",
            "一个简单的 REST API 示例项目",
            "python3 main.py", None, "running", 8080,
            _NOW, _NOW, "/sandbox/sp-1",
        ),
        (
            "sp-2", "数据处理管道",
            "演示 ETL 数据处理流程的示例项目",
            "python3 pipeline.py", None, "ready", 8081,
            _NOW, _NOW, "/sandbox/sp-2",
        ),
        (
            "sp-3", "Web 前端项目",
            "React 前端示例项目，包含路由和状态管理",
            "npm start", None, "stopped", 3000,
            _NOW, _NOW, "/sandbox/sp-3",
        ),
    ]
    for sp in sandboxes:
        if _row_exists(conn, "sandbox_projects", sp[0]):
            continue
        conn.execute(
            """INSERT INTO sandbox_projects (id, name, description, command, skill_id, status, port, created_at, updated_at, project_dir)
               VALUES (?,?,?,?,?,?,?,?,?,?)""", sp,
        )
    logger.info("Sandbox Projects seeded: %d rows", len(sandboxes))


def _insert_artifacts(conn):
    artifacts = [
        (
            "art-1", "proj-1", "req-1", "code",
            json.dumps({"file": "auth_service.py", "language": "python", "lines": 245}),
            1, "agent-2", _NOW, 1,
            "", "", 0, json.dumps({"coverage": 0.95}),
        ),
        (
            "art-2", "proj-1", "req-2", "code",
            json.dumps({"file": "dashboard.vue", "language": "vue", "lines": 180}),
            1, "agent-2", _NOW, 1,
            "", "", 0, json.dumps({"components": 12}),
        ),
        (
            "art-3", "proj-2", "req-3", "design",
            json.dumps({"file": "workflow_editor.fig", "tool": "Figma", "pages": 8}),
            1, "agent-4", _NOW, 1,
            "", "", 0, json.dumps({"frame_count": 45}),
        ),
        (
            "art-4", "proj-2", "req-4", "document",
            json.dumps({"file": "collab_spec.md", "type": "markdown", "words": 3200}),
            2, "agent-1", _NOW, 1,
            "", "", 0, json.dumps({"status": "approved"}),
        ),
        (
            "art-5", "proj-3", "req-5", "code",
            json.dumps({"file": "code_reviewer.py", "language": "python", "lines": 320}),
            1, "agent-2", _NOW, 1,
            "", "", 0, json.dumps({"framework": "AST"}),
        ),
    ]
    for a in artifacts:
        if _row_exists(conn, "artifacts", a[0]):
            continue
        conn.execute(
            """INSERT INTO artifacts (id, project_id, requirement_id, type, content, version, author, created_at, active, media_url, thumbnail, duration, metadata)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", a,
        )
    logger.info("Artifacts seeded: %d rows", len(artifacts))


def _insert_notifications(conn):
    notifications = [
        ("notif_welcome", "info", "欢迎使用小团智能平台 v9.0", "平台已升级到 v9.0，新增了工作台、任务中心和通知中心等功能", "", "", "all", _NOW, 0, ""),
    ]
    for n in notifications:
        if _row_exists(conn, "notifications", n[0]):
            continue
        conn.execute(
            """INSERT INTO notifications (id, type, title, content, target_type, target_id, user_id, created_at, read, read_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""", n,
        )
    logger.info("Notifications seeded: %d rows", len(notifications))


def seed_if_empty():
    """向空数据库灌入种子数据。幂等——已存在的记录不会重复插入。"""
    conn = get_db()
    try:
        _insert_agents(conn)
        _insert_teams(conn)
        _insert_workflows(conn)
        _insert_requirements(conn)
        _insert_knowledge_bases(conn)
        _insert_mcp_servers(conn)
        _insert_skills(conn)
        _insert_projects(conn)
        _insert_sandbox_projects(conn)
        _insert_artifacts(conn)
        _insert_notifications(conn)
        conn.commit()
        logger.info("Seed data inserted successfully")
    finally:
        conn.close()
