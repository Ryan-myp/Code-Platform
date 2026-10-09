"""Agent / 模板 / 工作流 / 技能 管理 API — 从 main.py 拆出。"""

import io
import json
import os
import time
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

import skills_store
from common.auth import require_auth
from common.db import get_db
from common.models import (
    AgentCreateRequest,
    AgentUpdateRequest,
    SkillCreateRequest,
    SkillUpdateRequest,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
)

router = APIRouter()

# 工作流写频控（节流：2s 内同 workflow 不重复写库）
_WF_LAST_WRITE: dict[str, float] = {}


# ── Agent 管理 ────────────────────────────────────────────────
@router.get("/api/agents")
async def list_agents(current_user: dict = require_auth()):
    """获取所有 Agent（含绑定资源统计与最近运行信息）"""
    conn = get_db()
    agents = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    # 会话统计：会话数近似执行次数，最新会话时间作为 last_run
    run_stats = {}
    try:
        rows = conn.execute(
            "SELECT agent_id, COUNT(*) cnt, MAX(updated_at) last_run FROM conversations GROUP BY agent_id"
        ).fetchall()
        for r in rows:
            run_stats[r["agent_id"]] = {"execution_count": r["cnt"], "last_run": r["last_run"]}
    except Exception:
        pass
    conn.close()
    result = []
    for a in agents:
        d = dict(a)

        def _parse_list(raw):
            try:
                v = json.loads(raw or "[]")
                return v if isinstance(v, list) else []
            except (json.JSONDecodeError, TypeError):
                return []

        tools = _parse_list(d.get("tools"))
        kbs = _parse_list(d.get("knowledge_base_ids"))
        skills = _parse_list(d.get("skill_ids"))
        mcps = _parse_list(d.get("mcp_server_ids"))
        st = run_stats.get(d["id"], {})
        d["tool_count"] = len(tools)
        d["kb_count"] = len(kbs)
        d["skill_count"] = len(skills)
        d["mcp_count"] = len(mcps)
        d["execution_count"] = st.get("execution_count", 0)
        d["last_run"] = st.get("last_run")
        result.append(d)
    return result


@router.post("/api/agents")
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


@router.put("/api/agents/{agent_id}")
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


@router.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str, current_user: dict = require_auth()):
    """删除 Agent"""
    conn = get_db()
    conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── Agent 模板（agent_templates/ 标准目录）────────────────────
_AGENT_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_templates")

# 模板中文名与展示元信息（无映射时回退 frontmatter name）
_AGENT_TEMPLATE_META = {
    "architect-agent": {"name": "架构师 Agent", "tag": "analysis", "desc": "技术方案、系统架构、技术选型"},
    "dba-agent": {"name": "DBA 数据库 Agent", "tag": "analysis", "desc": "数据建模、SQL 优化、备份恢复"},
    "dev-agent": {"name": "开发工程师 Agent", "tag": "coding", "desc": "代码生成、重构、审查"},
    "pm-agent": {"name": "产品经理 Agent", "tag": "analysis", "desc": "PRD 编写、需求分析、用户故事"},
    "qa-agent": {"name": "测试工程师 Agent", "tag": "coding", "desc": "测试用例、自动化测试、质量保障"},
    "sre-agent": {"name": "SRE 运维 Agent", "tag": "service", "desc": "部署、监控、故障排查"},
    "tech-writer-agent": {"name": "技术写手 Agent", "tag": "writing", "desc": "文档生成、API 文档、用户手册"},
    "ui-designer-agent": {"name": "UI/UX 设计师 Agent", "tag": "analysis", "desc": "界面设计、交互原型、设计规范"},
}


def _parse_agent_template_file(skill_path: str) -> dict | None:
    """解析 SKILL.md：提取 frontmatter（name/description）+ Instructions 正文。"""
    try:
        with open(skill_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    fm = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            body = parts[2]
    raw_name = fm.get("name", "").strip()
    if not raw_name:
        return None
    # Instructions：取 `## Instructions` 标题后的正文（截取到下一个二级标题）
    instructions = ""
    idx = body.find("## Instructions")
    if idx >= 0:
        rest = body[idx + len("## Instructions") :]
        next_h2 = rest.find("\n## ")
        instructions = rest[:next_h2].strip() if next_h2 >= 0 else rest.strip()
    if not instructions:
        instructions = body.strip()[:2000]
    meta = _AGENT_TEMPLATE_META.get(raw_name, {})
    return {
        "name": raw_name,
        "label": meta.get("name") or fm.get("label") or raw_name.replace("-", " ").title(),
        "description": fm.get("description", ""),
        "tag": meta.get("tag", "general"),
        "instructions": instructions,
        "title": (body.strip().splitlines() or [""])[0].lstrip("# ").strip(),
    }


@router.get("/api/agent-templates")
async def list_agent_templates(current_user: dict = require_auth()):
    """获取 Agent 模板列表（来自 agent_templates/ 标准目录）。"""
    templates = []
    if not os.path.isdir(_AGENT_TEMPLATES_DIR):
        return []
    for sub in sorted(os.listdir(_AGENT_TEMPLATES_DIR)):
        skill_path = os.path.join(_AGENT_TEMPLATES_DIR, sub, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        tpl = _parse_agent_template_file(skill_path)
        if tpl:
            templates.append(tpl)
    return templates


@router.post("/api/agent-templates/{template_name}/create")
async def create_agent_from_template(template_name: str, current_user: dict = require_auth()):
    """从模板一键创建 Agent：解析 SKILL.md 的 Instructions 作为系统指令。"""
    if not template_name or "/" in template_name or ".." in template_name:
        raise HTTPException(400, "模板名不合法")
    skill_path = None
    if os.path.isdir(_AGENT_TEMPLATES_DIR):
        for sub in os.listdir(_AGENT_TEMPLATES_DIR):
            candidate = os.path.join(_AGENT_TEMPLATES_DIR, sub, "SKILL.md")
            if os.path.isfile(candidate):
                tpl = _parse_agent_template_file(candidate)
                if tpl and tpl["name"] == template_name:
                    skill_path = candidate
                    break
    if not skill_path:
        raise HTTPException(404, "操作失败，请稍后重试")
    tpl = _parse_agent_template_file(skill_path)
    if not tpl:
        raise HTTPException(400, "模板解析失败")

    conn = get_db()
    agent_id = f"agent_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO agents (id, name, description, instructions, model, tools, knowledge_base_ids, skill_ids, mcp_server_ids, active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            agent_id,
            tpl["label"],
            tpl["description"] or tpl["title"],
            tpl["instructions"],
            "agnes-2.5-flash",
            "[]",
            "[]",
            "[]",
            "[]",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": agent_id, "name": tpl["label"], "template": template_name}


# ── Workflow 管理 ──────────────────────────────────────────────
@router.get("/api/workflows")
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


_WF_VALID_TYPES = {"agent", "http", "condition", "parallel", "code", "delay", "output"}
_WF_TYPE_MAP = {"start": "agent", "end": "output", "llm": "agent", "http": "http", "condition": "condition"}


def _normalize_wf_nodes(nodes: list) -> list:
    """规范化工作流节点：映射旧类型、补 x/y/config 字段。"""
    normalized = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        raw_type = n.get("type", "agent")
        n["type"] = _WF_TYPE_MAP.get(raw_type, raw_type) if raw_type not in _WF_VALID_TYPES else raw_type
        if "x" not in n:
            n["x"] = 80 + len(normalized) * 180
        if "y" not in n:
            n["y"] = 160
        if "config" not in n:
            n["config"] = {}
        normalized.append(n)
    return normalized


def _normalize_wf_edges(edges: list) -> list:
    """规范化工作流边：统一 from/to 格式。"""
    normalized = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        edge_from = e.get("from") or e.get("source")
        edge_to = e.get("to") or e.get("target")
        if edge_from and edge_to:
            normalized.append(
                {
                    "id": e.get("id") or f"edge_{edge_from}_{edge_to}",
                    "from": edge_from,
                    "to": edge_to,
                }
            )
    return normalized


@router.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, current_user: dict = require_auth()):  # noqa: C901
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

    # 规范化节点/边格式
    normalized_nodes = _normalize_wf_nodes(nodes)
    normalized_edges = _normalize_wf_edges(edges)
    d["nodes"] = normalized_nodes
    d["definition"] = {"nodes": normalized_nodes, "edges": normalized_edges}
    return d


@router.post("/api/workflows")
async def create_workflow(req: WorkflowCreateRequest, current_user: dict = require_auth()):
    """创建工作流"""

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


@router.put("/api/workflows/{workflow_id}")
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


@router.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, current_user: dict = require_auth()):
    """删除工作流"""
    conn = get_db()
    conn.execute("DELETE FROM workflows WHERE id=?", (workflow_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── 会话管理 ──────────────────────────────────────────────────
# 会话/消息/记忆 API 已迁移至 sessions.py router（/api/sessions/*）


# ── Skills 管理（标准 Agent Skills 目录结构）───────────────────
@router.get("/api/skills")
async def list_skills(current_user: dict = require_auth()):
    """获取所有 Skills（含文件系统统计）"""
    conn = get_db()
    skills = conn.execute("SELECT * FROM skills ORDER BY created_at DESC").fetchall()
    conn.close()
    stats = skills_store.scan_stats()
    result = []
    for s in skills:
        d = dict(s)
        st = stats.get(d["id"], {"file_count": 0, "dir_counts": {}})
        d["file_count"] = st["file_count"]
        d["dir_counts"] = st.get("dir_counts", {})
        result.append(d)
    return result


@router.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str, current_user: dict = require_auth()):
    """获取单个 Skill 详情（含文件统计）"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    d = dict(row)
    try:
        tree = skills_store.list_tree(skill_id)
        d["file_count"] = tree["file_count"]
        d["dir_counts"] = tree["dir_counts"]
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
    return d


@router.post("/api/skills")
async def create_skill(req: SkillCreateRequest, current_user: dict = require_auth()):
    """创建 Skill（落库 + 初始化标准目录结构）"""
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
    try:
        # 标准目录结构：SKILL.md + scripts/references/examples/assets
        skills_store.ensure_standard_dirs(skill_id)
        skills_store.write_file(
            skill_id,
            "SKILL.md",
            skills_store.render_skill_markdown(
                {
                    "name": req.name,
                    "description": req.description,
                    "content": req.content,
                }
            ),
        )
    except (ValueError, OSError) as e:
        raise HTTPException(500, "操作失败，请稍后重试") from e
    return {"id": skill_id, "name": req.name}


def _sync_skill_meta_to_fs(skill_id: str, skill: dict, fields_updated: set) -> None:
    """将 DB 元数据同步到标准目录：SKILL.md 与 references/references.md。

    - name/description 更新：重写 frontmatter，保留磁盘正文（文件浏览器可能更新过）
    - content 更新：整体重写 SKILL.md（以 DB 为准）
    - references 更新：同步 references/references.md（空值删除）
    """
    if fields_updated & {"name", "description", "content"}:
        existing = skills_store.read_skill_md(skill_id)
        if "content" in fields_updated:
            body = skill.get("content") or ""
        else:
            body = skills_store.parse_skill_markdown(existing)["content"] if existing else (skill.get("content") or "")
        md = skills_store.render_skill_markdown(
            {
                "name": skill["name"],
                "description": skill["description"],
                "content": body,
            }
        )
        skills_store.write_file(skill_id, "SKILL.md", md)
    if "references" in fields_updated:
        refs = (skill.get("references") or "").strip()
        if refs:
            skills_store.write_file(skill_id, "references/references.md", refs)
        else:
            try:
                skills_store.delete_path(skill_id, "references/references.md")
            except FileNotFoundError:
                pass


@router.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, req: SkillUpdateRequest, current_user: dict = require_auth()):
    """更新 Skill（元数据 + 同步标准目录文件）"""
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
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    try:
        _sync_skill_meta_to_fs(
            skill_id, dict(row), {u for u in updates if u in ("name", "description", "content", "references")}
        )
    except (ValueError, OSError) as e:
        raise HTTPException(500, "操作失败，请稍后重试") from e
    return {"success": True, "id": skill_id}


@router.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str, current_user: dict = require_auth()):
    """删除 Skill（含标准目录）"""
    conn = get_db()
    conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
    conn.commit()
    conn.close()
    try:
        skills_store.delete_path(skill_id, "")
    except (ValueError, FileNotFoundError):
        pass
    return {"success": True}


# ── 标准 SKILL.md 支持（导入 / 导出 / ZIP 打包）────────────────
@router.post("/api/skills/import")
async def import_skill(req: dict, current_user: dict = require_auth()):
    """导入标准 SKILL.md 文本：自动解析 frontmatter 创建 Skill 并落盘。"""
    markdown = (req.get("markdown") or "").strip()
    if not markdown:
        raise HTTPException(400, "SKILL.md 内容不能为空")
    parsed = skills_store.parse_skill_markdown(markdown)
    name = (parsed["name"] or req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "无法识别 Skill 名称（请在 frontmatter 中提供 name）")
    conn = get_db()
    skill_id = f"skill_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO skills (id, name, description, content, `references`, created_at)
           VALUES (?, ?, ?, ?, '', ?)""",
        (skill_id, name, parsed["description"], parsed["content"], datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    skills_store.ensure_standard_dirs(skill_id)
    skills_store.write_file(skill_id, "SKILL.md", markdown)
    return {"id": skill_id, "name": name, "description": parsed["description"]}


@router.post("/api/skills/import-zip")
async def import_skill_zip(file: UploadFile = File(...), current_user: dict = require_auth()):
    """导入标准 Skill 目录 zip 包（SKILL.md + scripts/references/examples/assets 等）。"""
    content = await file.read()
    if not content:
        raise HTTPException(400, "ZIP 文件为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "ZIP 包不能超过 20MB")
    try:
        parsed = skills_store.parse_skill_zip(content)
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
    name = (parsed["name"] or "").strip()
    if not name:
        raise HTTPException(400, "SKILL.md 缺少 frontmatter name，无法识别技能名称")
    conn = get_db()
    skill_id = f"skill_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO skills (id, name, description, content, `references`, created_at)
           VALUES (?, ?, ?, '', '', ?)""",
        (skill_id, name, parsed["description"], datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    skills_store.ensure_standard_dirs(skill_id)
    imported = skills_store.extract_zip_to(skill_id, content)
    return {"id": skill_id, "name": imported["name"], "imported": imported["imported"]}


@router.get("/api/skills/{skill_id}/export")
async def export_skill(skill_id: str, current_user: dict = require_auth()):
    """导出为标准 SKILL.md 文本（优先读取磁盘，兼容任意 Agent 工具）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    disk = skills_store.read_skill_md(skill_id)
    if disk is not None:
        return {"filename": f"{row['name']}/SKILL.md", "content": disk}
    return {
        "filename": f"{row['name']}/SKILL.md",
        "content": skills_store.render_skill_markdown(dict(row)),
    }


@router.get("/api/skills/{skill_id}/export-zip")
async def export_skill_zip(skill_id: str, current_user: dict = require_auth()):
    """导出整个 Skill 目录为 zip 包（标准结构，可直接用于其他 Agent 工具）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    try:
        data, filename = skills_store.export_zip(skill_id, row["name"])
    except FileNotFoundError as e:
        raise HTTPException(400, "请求参数错误") from e
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
    # Content-Disposition 需 latin-1 安全：中文名走 RFC 5987 filename* 编码
    try:
        filename.encode("latin-1")
        ascii_name = filename
    except UnicodeEncodeError:
        ascii_name = "skill.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": (f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}")},
    )
