#!/usr/bin/env python3
"""智能研发平台 v8.0 — 智能研发 + Agent 工作流平台。

v8.0 升级：安全加固、Pydantic 模型验证、异步架构、WebSocket、工作流并行。
"""

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 加载 .env 文件
load_dotenv()

from chat_engine import router as chat_engine_router  # noqa: E402
from collab_engine import router as collab_engine_router  # noqa: E402
from common.auth import login_user, require_auth  # noqa: E402
from common.config import ALLOWED_ORIGINS, validate_security_config  # noqa: E402
from common.db import get_db, init_schema  # noqa: E402
from common.models import (  # noqa: E402
    AgentCreateRequest,
    AgentUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    LoginRequest,
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    SandboxProjectCreateRequest,
    SandboxPullImageRequest,
    SkillCreateRequest,
    SkillUpdateRequest,
    TeamCreateRequest,
    TeamUpdateRequest,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
)
from image_factory import router as image_factory_router  # noqa: E402
from music_factory import router as music_factory_router  # noqa: E402
from prd_engine import router as prd_engine_router  # noqa: E402
from realtime import router as realtime_router  # noqa: E402
from seed_data import seed_if_empty  # noqa: E402
from sessions import router as sessions_router  # noqa: E402
from video_factory import router as video_factory_router  # noqa: E402

# ── 日志 ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── 限流器 ────────────────────────────────────────────────────
# 测试环境下禁用限流，避免干扰测试
_is_test = os.environ.get("APP_ENV") == "test"
limiter = Limiter(key_func=get_remote_address, default_limits=[] if _is_test else ["200 per minute"])


# ── 数据库初始化（保留 init_db 名字供 conftest 调用） ─────────
def init_db():
    """委托给 common.db.init_schema（24 表 + 迁移 + admin 用户）。"""
    init_schema()


# ── 应用生命周期 ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库 + 安全校验。关闭时无特殊处理。"""
    validate_security_config()
    init_db()
    seed_if_empty()
    logger.info("Smart R&D Platform v8.0 started")
    yield
    logger.info("Smart R&D Platform v8.0 shutting down")


# ── FastAPI 应用 ──────────────────────────────────────────────
app = FastAPI(title="智能研发平台 v8.0", version="8.0.0", lifespan=lifespan)

# workflow 写入防抖（阻断旧版前端自动保存循环）
_WF_LAST_WRITE: dict[str, float] = {}
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查 ──────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "version": "8.0.0"}


# ── 认证 ──────────────────────────────────────────────────────
@app.post("/api/auth/login")
@limiter.limit("5 per minute")
async def login(request: Request, req: LoginRequest):
    return login_user(req.username, req.password)


# ── Agent 管理 ────────────────────────────────────────────────
@app.get("/api/agents")
async def list_agents(current_user: dict = require_auth()):
    """获取所有 Agent"""
    conn = get_db()
    agents = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(a) for a in agents]


@app.post("/api/agents")
async def create_agent(req: AgentCreateRequest, current_user: dict = require_auth()):
    """创建 Agent"""
    conn = get_db()
    agent_id = f"agent_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO agents (id, name, description, instructions, model, tools, knowledge_base_ids, skill_ids, mcp_server_ids, active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            agent_id,
            req.name,
            req.description,
            req.instructions,
            req.model,
            json.dumps(req.tools),
            json.dumps(req.knowledge_base_ids),
            json.dumps(req.skill_ids),
            json.dumps(req.mcp_server_ids),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": agent_id, "name": req.name}


@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest, current_user: dict = require_auth()):
    """更新 Agent"""
    conn = get_db()
    updates = []
    vals = []
    for f in ["name", "description", "instructions", "model"]:
        v = getattr(req, f, None)
        if v is not None:
            updates.append(f"{f}=?")
            vals.append(v)
    if req.active is not None:
        updates.append("active=?")
        vals.append(1 if req.active else 0)
    for f in ["tools", "knowledge_base_ids", "skill_ids", "mcp_server_ids"]:
        v = getattr(req, f, None)
        if v is not None:
            updates.append(f"{f}=?")
            vals.append(json.dumps(v))
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(agent_id)
    conn.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": agent_id}


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str, current_user: dict = require_auth()):
    """删除 Agent"""
    conn = get_db()
    conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── Workflow 管理 ──────────────────────────────────────────────
@app.get("/api/workflows")
async def list_workflows(current_user: dict = require_auth()):
    """获取工作流列表"""
    conn = get_db()
    workflows = conn.execute("SELECT * FROM workflows ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for w in workflows:
        d = dict(w)
        d["status"] = "active" if d.get("active") else "inactive"
        try:
            d["nodes"] = json.loads(d.get("steps") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["nodes"] = []
        result.append(d)
    return result


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, current_user: dict = require_auth()):
    """获取工作流详情"""
    conn = get_db()
    row = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "工作流不存在")
    d = dict(row)
    d["status"] = "active" if d.get("active") else "inactive"
    try:
        nodes = json.loads(d.get("steps") or "[]")
    except (json.JSONDecodeError, TypeError):
        nodes = []
    try:
        edges = json.loads(d.get("connections") or "[]")
        if not isinstance(edges, list):
            edges = []
    except (json.JSONDecodeError, TypeError):
        edges = []
    d["nodes"] = nodes
    d["definition"] = {"nodes": nodes, "edges": edges}
    return d


@app.post("/api/workflows")
async def create_workflow(req: WorkflowCreateRequest, current_user: dict = require_auth()):
    """创建工作流"""
    import uuid

    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    # 处理 definition 字段（前端编辑器可能发送 WorkflowDefinition 对象或 JSON 字符串）
    steps = req.steps
    connections = req.connections
    if req.definition is not None:
        defn = req.definition
        if isinstance(defn, str):
            try:
                defn = json.loads(defn)
            except json.JSONDecodeError:
                defn = {}
        if hasattr(defn, "nodes"):
            steps = steps or defn.nodes
            connections = connections or defn.edges
        elif isinstance(defn, dict):
            steps = steps or defn.get("nodes", [])
            connections = connections or defn.get("edges", [])
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, description, steps, connections, created_at, active)
           VALUES (?, ?, ?, ?, ?, ?, 1)""",
        (
            workflow_id,
            req.name,
            req.description,
            json.dumps(steps or []),
            json.dumps(connections or []),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": workflow_id, "name": req.name}


@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, req: WorkflowUpdateRequest, current_user: dict = require_auth()):  # noqa: C901
    """更新工作流"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    if req.description is not None:
        updates.append("description=?")
        vals.append(req.description)
    if req.steps is not None:
        updates.append("steps=?")
        vals.append(json.dumps(req.steps))
    if req.connections is not None:
        updates.append("connections=?")
        vals.append(json.dumps(req.connections))
    # 前端编辑器发送 definition 字段（JSON 字符串或对象），含 nodes 和 edges
    if req.definition is not None:
        defn = req.definition
        if isinstance(defn, str):
            try:
                defn = json.loads(defn)
            except json.JSONDecodeError:
                defn = {}
        if hasattr(defn, "nodes"):
            updates.append("steps=?")
            vals.append(json.dumps(defn.nodes))
            updates.append("connections=?")
            vals.append(json.dumps(defn.edges))
        elif isinstance(defn, dict):
            updates.append("steps=?")
            vals.append(json.dumps(defn.get("nodes", [])))
            updates.append("connections=?")
            vals.append(json.dumps(defn.get("edges", [])))
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(workflow_id)

    # 防抖保护：1.5s 内同一 workflow 的重复写入直接跳过（阻断旧页面循环）
    import time as _time

    now = _time.time()
    key = f"wf_write:{workflow_id}"
    last = _WF_LAST_WRITE.get(key, 0)
    if now - last < 1.5:
        conn.close()
        return {"success": True, "id": workflow_id, "deduped": True}
    _WF_LAST_WRITE[key] = now

    conn.execute(f"UPDATE workflows SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": workflow_id}


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, current_user: dict = require_auth()):
    """删除工作流"""
    conn = get_db()
    conn.execute("DELETE FROM workflows WHERE id=?", (workflow_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── 会话管理 ──────────────────────────────────────────────────
# 会话/消息/记忆 API 已迁移至 sessions.py router（/api/sessions/*）

# ── Team 管理 ───────────────────────────────────────────────────
@app.get("/api/teams")
async def list_teams(current_user: dict = require_auth()):
    """获取所有 Teams"""
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(t) for t in teams]


@app.post("/api/teams")
async def create_team(req: TeamCreateRequest, current_user: dict = require_auth()):
    """创建 Team"""
    conn = get_db()
    team_id = f"team_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO teams (id, name, description, mode, members, instructions, respond_directly, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            team_id,
            req.name,
            req.description,
            req.mode,
            json.dumps(req.members),
            req.instructions,
            1 if req.respond_directly else 0,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": team_id, "name": req.name}


@app.put("/api/teams/{team_id}")
async def update_team(team_id: str, req: TeamUpdateRequest, current_user: dict = require_auth()):
    """更新 Team"""
    conn = get_db()
    conn.execute(
        """UPDATE teams SET name=?, description=?, mode=?, members=?, instructions=?, respond_directly=?
           WHERE id=?""",
        (
            req.name or "",
            req.description or "",
            req.mode or "coordinate",
            json.dumps(req.members or []),
            req.instructions or "",
            1 if req.respond_directly else 0,
            team_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": team_id, "name": req.name or ""}


@app.delete("/api/teams/{team_id}")
async def delete_team(team_id: str, current_user: dict = require_auth()):
    """删除 Team"""
    conn = get_db()
    conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── Skills 管理 ─────────────────────────────────────────────────
@app.get("/api/skills")
async def list_skills(current_user: dict = require_auth()):
    """获取所有 Skills"""
    conn = get_db()
    skills = conn.execute("SELECT * FROM skills ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(s) for s in skills]


@app.post("/api/skills")
async def create_skill(req: SkillCreateRequest, current_user: dict = require_auth()):
    """创建 Skill"""
    conn = get_db()
    skill_id = f"skill_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO skills (id, name, description, content, `references`, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            skill_id,
            req.name,
            req.description,
            req.content,
            req.references,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": skill_id, "name": req.name}


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, req: SkillUpdateRequest, current_user: dict = require_auth()):
    """更新 Skill"""
    conn = get_db()
    updates = []
    values = []
    for field in ["name", "description", "content", "references"]:
        v = getattr(req, field, None)
        if v is not None:
            updates.append(f"{field}=?")
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            values.append(v)
    if not updates:
        raise HTTPException(400, "没有需要更新的字段")
    values.append(skill_id)
    conn.execute(f"UPDATE skills SET {','.join(updates)} WHERE id=?", values)
    conn.commit()
    conn.close()
    return {"success": True, "id": skill_id}


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str, current_user: dict = require_auth()):
    """删除 Skill"""
    conn = get_db()
    conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── 知识库管理 ──────────────────────────────────────────────────
@app.get("/api/knowledge-bases")
async def list_knowledge_bases(current_user: dict = require_auth()):
    """获取所有知识库"""
    conn = get_db()
    kbs = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(kb) for kb in kbs]


@app.post("/api/knowledge-bases")
async def create_knowledge_base(req: KnowledgeBaseCreateRequest, current_user: dict = require_auth()):
    """创建知识库"""
    conn = get_db()
    kb_id = f"kb_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO knowledge_bases (id, name, type, path, url, filter, top_k, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            kb_id,
            req.name,
            req.type or req.source_type or "file",
            req.path or req.source_path or "",
            req.url,
            json.dumps(req.filter),
            req.top_k,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": kb_id, "name": req.name}


@app.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str, current_user: dict = require_auth()):
    """删除知识库"""
    conn = get_db()
    conn.execute("DELETE FROM knowledge_bases WHERE id=?", (kb_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.put("/api/knowledge-bases/{kb_id}")
async def update_knowledge_base(kb_id: str, req: KnowledgeBaseUpdateRequest, current_user: dict = require_auth()):
    """更新知识库"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    # type 和 source_type 都映射到数据库的 type 列
    db_type = req.type or req.source_type
    if db_type is not None:
        updates.append("type=?")
        vals.append(db_type)
    # path 和 source_path 都映射到数据库的 path 列
    db_path = req.path or req.source_path
    if db_path is not None:
        updates.append("path=?")
        vals.append(db_path)
    if req.url is not None:
        updates.append("url=?")
        vals.append(req.url)
    if req.top_k is not None:
        updates.append("top_k=?")
        vals.append(req.top_k)
    if not updates:
        raise HTTPException(400, "无更新字段")
    updates.append("created_at=created_at")
    vals.append(kb_id)
    conn.execute(f"UPDATE knowledge_bases SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": kb_id}


# ── MCP Servers 管理 ───────────────────────────────────────────
@app.get("/api/mcp-servers")
async def list_mcp_servers(current_user: dict = require_auth()):
    """获取所有 MCP Servers"""
    conn = get_db()
    servers = conn.execute("SELECT * FROM mcp_servers ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for s in servers:
        d = dict(s)
        d["status"] = "active" if d.get("enabled") else "inactive"
        d["transport"] = d.get("transport_type") or "stdio"
        result.append(d)
    return result


@app.post("/api/mcp-servers")
async def create_mcp_server(req: MCPServerCreateRequest, current_user: dict = require_auth()):
    """创建 MCP Server"""
    conn = get_db()
    server_id = f"mcp_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO mcp_servers (id, name, transport_type, command, args, env, url, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            server_id,
            req.name,
            req.transport_type,
            req.command,
            json.dumps(req.args),
            json.dumps(req.env),
            req.url,
            1 if req.enabled else 0,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": server_id, "name": req.name}


@app.put("/api/mcp-servers/{server_id}")
async def update_mcp_server(server_id: str, req: MCPServerUpdateRequest, current_user: dict = require_auth()):
    """更新 MCP Server"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    if req.command is not None:
        updates.append("command=?")
        vals.append(req.command)
    if req.url is not None:
        updates.append("url=?")
        vals.append(req.url)
    if req.env is not None:
        updates.append("env=?")
        vals.append(json.dumps(req.env))
    if req.transport is not None or req.transport_type is not None:
        updates.append("transport_type=?")
        vals.append(req.transport_type or req.transport)
    if req.args is not None:
        updates.append("args=?")
        vals.append(json.dumps(req.args))
    if req.enabled is not None:
        updates.append("enabled=?")
        vals.append(1 if req.enabled else 0)
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(server_id)
    conn.execute(f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": server_id}


@app.post("/api/mcp-servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, current_user: dict = require_auth()):
    """切换 MCP Server 启用状态"""
    conn = get_db()
    row = conn.execute("SELECT enabled FROM mcp_servers WHERE id=?", (server_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "MCP 服务器不存在")
    new_val = 0 if row["enabled"] else 1
    conn.execute("UPDATE mcp_servers SET enabled=? WHERE id=?", (new_val, server_id))
    conn.commit()
    conn.close()
    return {"success": True, "enabled": bool(new_val), "status": "active" if new_val else "inactive"}


@app.delete("/api/mcp-servers/{server_id}")
async def delete_mcp_server(server_id: str, current_user: dict = require_auth()):
    """删除 MCP Server"""
    conn = get_db()
    conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── 沙箱管理 ───────────────────────────────────────────────────
@app.get("/api/sandbox/images")
async def sandbox_list_images(current_user: dict = require_auth()):
    """列出沙箱镜像"""
    from sandbox import process_manager

    return {"images": process_manager.list_images()}


@app.post("/api/sandbox/images/pull")
async def sandbox_pull_image(req: SandboxPullImageRequest, current_user: dict = require_auth()):
    """拉取镜像"""
    from sandbox import process_manager

    return process_manager.pull_image(req.image)


@app.get("/api/sandbox/services")
async def sandbox_services(current_user: dict = require_auth()):
    """获取预置服务模板"""
    from sandbox import SERVICE_TEMPLATES

    return {"services": SERVICE_TEMPLATES}


@app.get("/api/sandbox/projects")
async def sandbox_list_projects(current_user: dict = require_auth()):
    """列出沙箱项目"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM sandbox_projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/sandbox/projects")
async def sandbox_create_project(req: SandboxProjectCreateRequest, current_user: dict = require_auth()):
    """创建沙箱项目"""
    from sandbox import process_manager

    project_id = f"proj_{int(time.time() * 1000)}"
    # 前端可能传字符串或列表，统一转为列表
    raw_ports = req.ports
    if isinstance(raw_ports, str):
        ports = [p.strip() for p in raw_ports.split(",") if p.strip()]
    else:
        ports = raw_ports or []
    raw_env = req.env
    if isinstance(raw_env, str):
        env = [e.strip() for e in raw_env.split(",") if e.strip()]
    else:
        env = raw_env or []
    config = {
        "image": req.image,
        "ports": ports,
        "env": env,
        "command": req.command,
    }
    result = process_manager.create_container(project_id, config)
    conn = get_db()
    conn.execute(
        """INSERT INTO sandbox_projects (id, name, image, status, ports, config, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (project_id, req.name, config["image"], result.get("status", "created"),
         json.dumps(config.get("ports", [])), json.dumps(config), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"id": project_id, **result}


@app.get("/api/sandbox/projects/{project_id}")
async def sandbox_get_project(project_id: str, current_user: dict = require_auth()):
    """获取沙箱项目状态"""
    from sandbox import process_manager

    status = process_manager.get_status(project_id)
    return {"id": project_id, "status": status or {"state": "unknown"}}


@app.post("/api/sandbox/projects/{project_id}/start")
async def sandbox_start_project(project_id: str, current_user: dict = require_auth()):
    """启动沙箱项目"""
    from sandbox import process_manager

    return process_manager.start_container(project_id)


@app.post("/api/sandbox/projects/{project_id}/stop")
async def sandbox_stop_project(project_id: str, current_user: dict = require_auth()):
    """停止沙箱项目"""
    from sandbox import process_manager

    return process_manager.stop_container(project_id)


@app.delete("/api/sandbox/projects/{project_id}")
async def sandbox_delete_project(project_id: str, current_user: dict = require_auth()):
    """删除沙箱项目"""
    from sandbox import process_manager

    result = process_manager.remove_container(project_id)
    conn = get_db()
    conn.execute("DELETE FROM sandbox_projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return result


app.include_router(image_factory_router)
app.include_router(video_factory_router)
app.include_router(music_factory_router)
app.include_router(prd_engine_router)
app.include_router(chat_engine_router)
app.include_router(sessions_router)
app.include_router(collab_engine_router)
app.include_router(realtime_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8888)
