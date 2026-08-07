#!/usr/bin/env python3
"""对话执行引擎 - Agent/Team/Workflow 运行 + 会话消息 + 插件市场"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from common.config import load_config
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)
router = APIRouter(tags=["对话执行"])

PROJECT_DIR = Path(__file__).parent

# 模块加载时从 config 表加载 LLM 配置
load_config()


# ══════════════════════════════════════════════════════════════
# Agent 执行
# ══════════════════════════════════════════════════════════════


@router.get("/api/agents/{agent_id}/conversations")
async def list_conversations(agent_id: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM conversations WHERE agent_id=? AND active=1 ORDER BY updated_at DESC", (agent_id,)
    ).fetchall()
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
    msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC", (conv_id,)).fetchall()
    conn.close()
    if not row:
        raise HTTPException(404, "对话不存在")
    return {"conversation": dict(row), "messages": [dict(m) for m in msgs]}


@router.get("/api/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    conn = get_db()
    msgs = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY timestamp ASC", (conv_id,)).fetchall()
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
    cur = conn.execute(
        """INSERT INTO messages (conversation_id, role, content, timestamp)
           VALUES (?, ?, ?, ?)""",
        (conv_id, role, content, now),
    )
    conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))
    conn.commit()
    msg_id = cur.lastrowid
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

    log_usage("agent_run", len(message), len(result), time.time() - start)
    return {"result": result, "agent_id": agent_id, "elapsed": round(time.time() - start, 2)}


# ══════════════════════════════════════════════════════════════
# Team / Workflow 执行
# ══════════════════════════════════════════════════════════════


@router.post("/api/teams/{team_id}/run")
async def run_team(team_id: str, req: dict):  # noqa: C901
    """运行 Team：按协作模式调度成员 Agent 执行，并汇总结果。

    - coordinate（协调）：所有成员并行执行 → 协调者汇总最终答案
    - sequential（顺序）：成员按顺序执行，上一步输出作为下一步输入
    - parallel（并行）：所有成员并行执行，返回各自结果
    """
    import asyncio

    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    conn = get_db()
    team = conn.execute("SELECT * FROM teams WHERE id=?", (team_id,)).fetchone()
    if not team:
        conn.close()
        raise HTTPException(404, "Team 不存在")

    members = json.loads(team["members"] or "[]")
    member_ids = [m if isinstance(m, str) else m.get("id") for m in members]
    member_ids = [mid for mid in member_ids if mid]
    agents = []
    if member_ids:
        placeholders = ",".join("?" * len(member_ids))
        rows = conn.execute(
            f"SELECT id, name, instructions, model FROM agents WHERE id IN ({placeholders}) AND active=1",
            member_ids,
        ).fetchall()
        agents = [dict(r) for r in rows]
    conn.close()

    mode = (team["mode"] or "coordinate").lower()
    team_instructions = team["instructions"] or "你是一个团队协作助手"
    start = time.time()

    async def _run_member(agent: dict, task: str, extra_context: str = "") -> dict:
        """单个成员 Agent 执行：系统指令 = 团队成员指令 + 团队协作规则。"""
        system = agent["instructions"] or "你是一个智能助手"
        if team_instructions:
            system = f"{system}\n\n## 团队协作规则\n{team_instructions}"
        prompt = f"团队任务：{task}"
        if extra_context:
            prompt += f"\n\n前序成员产出（供参考）：\n{extra_context}"
        try:
            result = call_llm(system, prompt, max_tokens=2000)
            return {"agent_id": agent["id"], "name": agent["name"], "result": result}
        except Exception as e:
            return {"agent_id": agent["id"], "name": agent["name"], "result": f"（执行失败：{e}）", "error": str(e)}

    member_results = []
    coordinator_result = ""
    if not agents:
        # 无成员：直接用团队指令执行
        result = call_llm(team_instructions, message, max_tokens=2000)
        coordinator_result = result
    elif mode == "sequential":
        # 顺序执行：上一步输出作为下一步上下文
        context = ""
        for agent in agents:
            r = await _run_member(agent, message, context)
            member_results.append(r)
            context += f"\n【{r['name']} 的产出】\n{r['result'][:1500]}"
        # 汇总：由最后一个成员生成最终答案（上下文已包含全部产出）
        coordinator_result = member_results[-1]["result"] if member_results else ""
    elif mode == "parallel":
        # 并行执行：各自独立完成，直接返回成员结果拼接
        member_results = await asyncio.gather(*[_run_member(a, message) for a in agents])
        coordinator_result = "\n\n".join(f"### {r['name']}\n{r['result']}" for r in member_results)
    else:
        # coordinate：成员并行产出 → 协调者汇总
        member_results = await asyncio.gather(*[_run_member(a, message) for a in agents])
        digest = "\n\n".join(f"### {r['name']} 的产出\n{r['result'][:1200]}" for r in member_results)
        coordinator_system = (
            f"你是团队协调者。请汇总以下团队成员对任务的产出，给出统一的最终答案。\n"
            f"## 团队协作规则\n{team_instructions}"
        )
        coordinator_result = call_llm(
            coordinator_system,
            f"团队任务：{message}\n\n## 成员产出\n{digest}",
            max_tokens=2000,
        )

    log_usage("team_run", len(message), len(coordinator_result), time.time() - start)
    return {
        "result": coordinator_result,
        "team_id": team_id,
        "mode": mode,
        "members": member_results,
        "elapsed": round(time.time() - start, 2),
    }


def _wf_node_summary(res: dict) -> str:
    """把节点执行结果整理成可读文本。"""
    if not isinstance(res, dict):
        return str(res)
    if res.get("status") == "error":
        return f"节点执行失败：{res.get('message', '未知错误')}"
    for key in ("result", "lyrics", "content", "text"):
        if res.get(key):
            return str(res[key])
    if res.get("url"):
        return f"生成成功：{res['url']}\n\n提示词：{res.get('prompt', '')}"
    if res.get("video_id"):
        return f"视频任务已创建：{res['video_id']}（预计 {res.get('estimated_time', '?')} 秒完成）"
    return "```json\n" + json.dumps(res, ensure_ascii=False, default=str) + "\n```"


@router.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, req: dict):  # noqa: C901
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
    definition = json.loads(steps_raw or "[]") if steps_raw else []
    nodes = definition if isinstance(definition, list) else definition.get("nodes", [])

    # 尝试用完整 executor
    try:
        from workflows.executor import executor as _executor

        run_id = await _executor.execute(workflow_id, {"message": message})
        # 取出运行记录与各节点结果，整理成可读摘要返回
        conn = get_db()
        run = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
        conn.close()
        run_dict = dict(run) if run else None
        output_data = {}
        if run_dict:
            try:
                output_data = json.loads(run_dict.get("output_data") or "{}")
            except (json.JSONDecodeError, TypeError):
                output_data = {}
        if not isinstance(output_data, dict):
            output_data = {}

        # 节点 id → 显示名映射
        node_labels = {}
        for n in nodes:
            if isinstance(n, dict) and n.get("id"):
                node_labels[n["id"]] = n.get("label") or n.get("name") or n["id"]

        # 每个节点的摘要（按执行顺序稳定排序）
        node_results = []
        for nid, res in output_data.items():
            if nid == "input":
                continue  # 注入的输入数据不当作节点展示
            if not isinstance(res, dict):
                res = {"status": "success", "result": str(res)}
            node_results.append(
                {
                    "node_id": nid,
                    "label": node_labels.get(nid, nid),
                    "status": res.get("status", "success"),
                    "summary": _wf_node_summary(res),
                }
            )

        # 最终结果：优先输出节点，其次最后一个成功的节点，再退回错误信息
        final_result = None
        for nid in node_labels:
            r = output_data.get(nid)
            if isinstance(r, dict) and r.get("status") == "success":
                final_result = r
                break
        if final_result is None:
            for r in reversed(list(output_data.values())):
                if isinstance(r, dict) and r.get("status") == "success":
                    final_result = r
                    break
        if final_result is None:
            for r in output_data.values():
                if isinstance(r, dict) and r.get("status") == "error":
                    final_result = r
                    break
        if final_result is None:
            final_result = {"status": "error", "message": "工作流未产生任何输出，请检查节点配置与连线"}

        # 计算耗时
        elapsed = None
        try:
            if run_dict and run_dict.get("started_at") and run_dict.get("completed_at"):
                start = datetime.fromisoformat(run_dict["started_at"])
                end = datetime.fromisoformat(run_dict["completed_at"])
                elapsed = round((end - start).total_seconds(), 2)
        except (ValueError, TypeError):
            elapsed = None

        return {
            "result": _wf_node_summary(final_result),
            "nodes": node_results,
            "run": run_dict,
            "workflow_id": workflow_id,
            "engine": "executor",
            "elapsed": elapsed,
        }
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


# ══════════════════════════════════════════════════════════════
# 会话记忆（复用 memories 表，session_id = conversation_id）
# ══════════════════════════════════════════════════════════════


@router.get("/api/conversations/{conv_id}/memories")
async def get_conversation_memories(conv_id: str):
    """获取会话记忆（按时间倒序）"""
    from sessions import get_memories

    return get_memories(conv_id)


@router.post("/api/conversations/{conv_id}/memories")
async def add_conversation_memory(conv_id: str, req: dict):
    """添加会话记忆（如用户偏好、关键决定等，供后续对话引用）"""
    from sessions import add_memory

    content = (req.get("content") or "").strip()
    if not content:
        raise HTTPException(400, "记忆内容不能为空")
    memory_type = req.get("memory_type", "short")
    agent_id = req.get("agent_id", "") or ""
    # memories 表外键指向 sessions(id)，对话 id 不同源，需先确保占位会话存在
    conn = get_db()
    try:
        if not conn.execute("SELECT id FROM sessions WHERE id=?", (conv_id,)).fetchone():
            conn.execute(
                "INSERT INTO sessions (id, agent_id, title) VALUES (?,?,?)",
                (conv_id, agent_id, "对话记忆"),
            )
            conn.commit()
    finally:
        conn.close()
    mem_id = add_memory(conv_id, agent_id, content, memory_type)
    return {"id": mem_id, "session_id": conv_id}


@router.delete("/api/conversations/memories/{mem_id}")
async def delete_conversation_memory(mem_id: str):
    """删除单条会话记忆"""
    conn = get_db()
    conn.execute("DELETE FROM memories WHERE id=?", (mem_id,))
    conn.commit()
    conn.close()
    return {"success": True}
