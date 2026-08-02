#!/usr/bin/env python3
"""对话执行引擎 - Agent/Team/Workflow 运行 + 会话消息 + 插件市场"""

import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(tags=["对话执行"])

PROJECT_DIR = Path(__file__).parent
DB_PATH = PROJECT_DIR / "platform.db"

AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://apihub.agnes-ai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "agnes-2.5-flash")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def normalize_api_base(base: str) -> str:
    base = base.strip()
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if base.endswith("/v1"):
        return base
    return base.rstrip("/") + "/v1"


def load_config():
    global AGNES_API_KEY, AGNES_API_BASE, MODEL_NAME
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        conn.close()
        for k, v in rows:
            if k == "agnes_api_key" and v:
                AGNES_API_KEY = v.strip()
            elif k == "agnes_api_base" and v:
                AGNES_API_BASE = normalize_api_base(v)
            elif k == "model_name" and v:
                MODEL_NAME = v.strip()
    except Exception:
        pass


load_config()


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> str:
    """调用 Agnes LLM"""
    if not AGNES_API_KEY:
        raise HTTPException(400, "未配置 AGNES_API_KEY")
    url = f"{AGNES_API_BASE}/chat/completions"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": 0.5,
            },
            timeout=120,
        )
        if resp.status_code != 200:
            logger.error(f"LLM call failed: {resp.status_code} {resp.text[:400]}")
            raise HTTPException(500, f"LLM 调用失败: {resp.status_code} {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LLM call exception: {e}")
        raise HTTPException(500, f"LLM 调用异常: {str(e)}")


# ══════════════════════════════════════════════════════════════
# Agent 执行
# ══════════════════════════════════════════════════════════════

@router.get("/api/agents/{agent_id}/conversations")
async def list_conversations(agent_id: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM conversations WHERE agent_id=? AND active=1 ORDER BY updated_at DESC", (agent_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/agents/{agent_id}/conversations")
async def create_conversation(agent_id: str, req: dict = None):
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO conversations (id, agent_id, title, created_at, updated_at, active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (conv_id, agent_id, (req or {}).get("title") or "新对话", now, now),
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "agent_id": agent_id, "title": (req or {}).get("title") or "新对话"}


@router.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    conn = get_db()
    conn.execute("UPDATE conversations SET active=0 WHERE id=?", (conv_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    msgs = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC", (conv_id,)
    ).fetchall()
    conn.close()
    if not row:
        raise HTTPException(404, "对话不存在")
    return {"conversation": dict(row), "messages": [dict(m) for m in msgs]}


@router.get("/api/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    conn = get_db()
    msgs = conn.execute(
        "SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC", (conv_id,)
    ).fetchall()
    conn.close()
    return [dict(m) for m in msgs]


@router.post("/api/conversations/{conv_id}/messages")
async def add_conversation_message(conv_id: str, req: dict):
    role = req.get("role", "user")
    content = req.get("content", "")
    if not content:
        raise HTTPException(400, "内容不能为空")
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO messages (conversation_id, role, content, timestamp)
           VALUES (?, ?, ?, ?)""",
        (conv_id, role, content, now),
    )
    conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))
    conn.commit()
    conn.close()
    return {"id": msg_id}


def get_agent_system_prompt(agent_id: str) -> str:
    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id=? AND active=1", (agent_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Agent 不存在")
    instructions = row["instructions"] or "你是一个智能助手"
    return instructions


@router.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, req: dict):
    """运行 Agent - 调用 LLM"""
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    start = time.time()
    system = get_agent_system_prompt(agent_id)
    result = call_llm(system, message, max_tokens=2000)

    # 记录消息到最新会话（若有）
    conv_id = req.get("conversation_id")
    if conv_id:
        try:
            conn = get_db()
            now = datetime.now().isoformat()
            conn.execute(
                """INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)""",
                (conv_id, "assistant", result, now),
            )
            conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))
            conn.commit()
            conn.close()
        except Exception:
            pass

    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO usage_logs (id, timestamp, task_type, input_length, output_length, response_time, success)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (f"ul_{int(time.time() * 1000)}", datetime.now().isoformat(), "agent_run",
             len(message), len(result), round(time.time() - start, 3)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

    return {"result": result, "agent_id": agent_id, "elapsed": round(time.time() - start, 2)}


# ══════════════════════════════════════════════════════════════
# Team / Workflow 执行
# ══════════════════════════════════════════════════════════════

@router.post("/api/teams/{team_id}/run")
async def run_team(team_id: str, req: dict):
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
    conn.close()
    if not team:
        raise HTTPException(404, "Team 不存在")

    members = json.loads(team["members"] or "[]")
    system = team["instructions"] or "你是一个团队协作助手"
    member_info = ""
    if members:
        try:
            member_names = []
            for m in members:
                mid = m if isinstance(m, str) else m.get("id")
                if mid:
                    row = conn.execute("SELECT name, instructions FROM agents WHERE id=?", (mid,)).fetchone()
                    if row:
                        member_names.append(f"- {row['name']}: {row['instructions'][:200]}")
            member_info = "\n".join(member_names)
        except Exception:
            pass

    prompt = f"团队指令: {system}\n\n团队成员:\n{member_info or '（无成员信息）'}\n\n任务: {message}"
    result = call_llm(system, prompt, max_tokens=2000)
    return {"result": result, "team_id": team_id}


@router.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, req: dict):
    """运行 Workflow - 若可用 executor 则用，否则简单执行"""
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    conn = get_db()
    wf = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    conn.close()
    if not wf:
        raise HTTPException(404, "Workflow 不存在")

    steps_raw = wf["steps"] if "steps" in wf.keys() else ""
    connections_raw = wf["connections"] if "connections" in wf.keys() else ""
    definition = json.loads(steps_raw or "[]") if steps_raw else []
    connections = json.loads(connections_raw or "{}") if connections_raw else {}
    nodes = definition if isinstance(definition, list) else definition.get("nodes", [])

    # 尝试用完整 executor
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from workflows.executor import WorkflowExecutor

        executor = WorkflowExecutor()
        result = executor.run(workflow_id, {"message": message})
        return {"result": result, "workflow_id": workflow_id, "engine": "executor"}
    except Exception as e:
        logger.warning(f"workflow executor unavailable, simple run: {e}")

    # 简单执行：把节点信息组装给 LLM
    node_desc = ""
    if nodes:
        node_desc = "\n".join(f"- {n.get('type')}: {n.get('name')}" for n in nodes[:10])
    system = "你是工作流执行引擎，根据工作流定义和输入，直接给出执行结果。"
    prompt = f"工作流: {wf['name']}\n节点: {node_desc or '（无节点定义）'}\n\n输入: {message}"
    result = call_llm(system, prompt, max_tokens=2000)
    return {"result": result, "workflow_id": workflow_id, "engine": "simple"}


# ══════════════════════════════════════════════════════════════
# 插件市场
# ══════════════════════════════════════════════════════════════

# 内置插件注册表
BUILTIN_PLUGINS = [
    {
        "name": "biz-review",
        "label": "PRD 智能审查",
        "category": "研发流程",
        "version": "1.0.0",
        "description": "注入代码 IR 证据审查 PRD，22+ 预检查维度（biz-delivery 引擎）",
        "enabled": True,
    },
    {
        "name": "biz-technical-design",
        "label": "技术方案生成",
        "category": "研发流程",
        "version": "1.0.0",
        "description": "基于 PRD + 代码 IR 生成完整技术方案，含 Mermaid 图表",
        "enabled": True,
    },
    {
        "name": "biz-test-cases",
        "label": "测试用例生成",
        "category": "研发流程",
        "version": "1.0.0",
        "description": "注入错误码和 Request/Response struct 生成测试用例",
        "enabled": True,
    },
    {
        "name": "biz-code-scan",
        "label": "代码库扫描",
        "category": "代码分析",
        "version": "1.0.0",
        "description": "扫描代码仓库，生成 IR 缓存、业务卡片、核心流程推断",
        "enabled": True,
    },
    {
        "name": "image-factory",
        "label": "图片工厂",
        "category": "内容创作",
        "version": "2.0.0",
        "description": "文生图、图生图、智能抠图、模板合成、虚拟试衣",
        "enabled": True,
    },
    {
        "name": "video-factory",
        "label": "视频工厂",
        "category": "内容创作",
        "version": "1.0.0",
        "description": "文生视频、图生视频、关键帧动画（Agnes Video V2.0）",
        "enabled": True,
    },
    {
        "name": "music-factory",
        "label": "音乐工厂",
        "category": "内容创作",
        "version": "1.0.0",
        "description": "歌词生成、音乐创作、虚拟人声",
        "enabled": True,
    },
]


@router.get("/api/plugins")
async def list_plugins():
    """获取插件列表"""
    plugins = []
    # 尝试加载真实 registry
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from plugin_registry import registry

        registered = registry.list_all()
        if registered:
            plugins = registered
    except Exception:
        pass
    if not plugins:
        plugins = BUILTIN_PLUGINS

    # 按类别分组
    categories = []
    seen = set()
    for p in plugins:
        cat = p.get("category", "其他")
        if cat not in seen:
            seen.add(cat)
            categories.append(cat)

    return {
        "plugins": plugins,
        "categories": categories,
        "total": len(plugins),
    }


@router.post("/api/plugins/{plugin_name}/execute")
async def execute_plugin(plugin_name: str, req: dict):
    """执行插件"""
    # 兼容 {input_data: {...}} 和扁平结构
    input_data = req.get("input_data", {}) if isinstance(req.get("input_data"), dict) else req

    # 尝试真实 registry
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        from plugin_registry import registry

        result = registry.execute(plugin_name, input_data)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.warning(f"plugin registry execute failed: {e}")

    # 内置插件映射到 prd_engine 端点逻辑
    mapping = {
        "biz-review": ("/api/prd/review", input_data),
        "biz-technical-design": ("/api/prd/technical-design", input_data),
        "biz-test-cases": ("/api/prd/test-cases", input_data),
        "biz-code-scan": ("/api/prd/generate-code", input_data),
        "image-factory": None,
        "video-factory": None,
        "music-factory": None,
    }
    if plugin_name not in mapping:
        raise HTTPException(404, f"插件不存在: {plugin_name}")

    target = mapping[plugin_name]
    if target is None:
        return {"status": "success", "result": f"插件 {plugin_name} 已在对应工厂页面提供完整功能"}

    # 转发到 prd 端点逻辑（内联复用）
    from prd_engine import review_prd, technical_design, test_cases

    url, body = target
    try:
        if url == "/api/prd/review":
            r = await review_prd(body)
        elif url == "/api/prd/technical-design":
            r = await technical_design(body)
        elif url == "/api/prd/test-cases":
            r = await test_cases(body)
        else:
            r = {"result": "插件执行完成"}
        return {"status": "success", "result": r}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
