#!/usr/bin/env python3
from common.helpers import (
    _sse_event,
)


def _run_workflow_simple(workflow_data: dict) -> dict:
    """简化版工作流执行。"""
    return {
        "status": "success",
        "workflow_id": workflow_data.get("workflow_id", ""),
        "result": workflow_data.get("result", {}),
    }


def _prepare_workflow_params(request_data: dict) -> dict:
    """简化版准备工作流参数。"""
    return {"workflow_id": request_data.get("workflow_id", ""), "inputs": request_data.get("inputs", {})}


import asyncio
from datetime import datetime

"""对话执行引擎 - Agent/Team/Workflow 运行 + 会话消息 + 插件市场"""

import json
import logging
import re
import sys
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

import agent_runtime
from common.auth import require_auth  # v18.2 快照/重放端点鉴权
from common.config import load_config
from common.db import get_db
from common.llm import (
    build_conversation_messages,
    call_llm_async,
    log_usage,
    parse_llm_json,
    stream_llm_async,
)

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


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


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
    """发送消息。v12.0：支持 ``stream: true`` 走 SSE 流式（打字机增量 + 自动落库 assistant）。"""
    role = req.get("role", "user")
    content = req.get("content", "")
    if not content:
        raise HTTPException(400, "内容不能为空")
    now = datetime.now().isoformat()
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO messages (conversation_id, role, content, timestamp)
           VALUES (?, ?, ?, ?) """,
        (conv_id, role, content, now),
    )
    conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))
    conn.commit()
    msg_id = cur.lastrowid

    # v12.0 流式对话：写入用户消息后，自动调用 Agent 并以 SSE 增量返回
    if req.get("stream") and role == "user":
        conn.close()  # 生成器内使用独立连接，避免跨请求复用
        system = _conversation_system_prompt(conv_id)
        messages = build_conversation_messages(conv_id, system)
        start = time.time()

        async def gen():
            try:
                full = ""
                async for delta, full in stream_llm_async(messages=messages, max_tokens=2000):  # noqa: B007 — full 为累计文本，循环结束后用于落库与 done 事件
                    yield _sse_event("delta", {"text": delta})
                # 自动落库 assistant 回复
                try:
                    c2 = get_db()
                    now2 = datetime.now().isoformat()
                    c2.execute(
                        """INSERT INTO messages (conversation_id, role, content, timestamp)
                           VALUES (?, ?, ?, ?) """,
                        (conv_id, "assistant", full, now2),
                    )
                    c2.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now2, conv_id))
                    c2.commit()
                    c2.close()
                except Exception:
                    pass
                log_usage("conversation_stream", len(content), len(full), time.time() - start)
                yield _sse_event("done", {"full": full, "elapsed": round(time.time() - start, 2)})
            except HTTPException as e:
                yield _sse_event("error", {"detail": e.detail})
            except Exception as e:
                logger.exception("conversation stream failed")
                yield _sse_event("error", {"detail": f"流式调用异常: {e}"})

        return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)

    conn.close()
    return {"id": msg_id}


def _conversation_system_prompt(conv_id: str) -> str:
    """取会话所属 Agent 的系统指令（无 Agent 时回退默认）。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT agent_id FROM conversations WHERE id=?", (conv_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row["agent_id"]:
        return "你是一个智能助手"
    try:
        return get_agent_system_prompt(row["agent_id"])
    except HTTPException:
        return "你是一个智能助手"


def get_agent_system_prompt(agent_id: str) -> str:
    """仅基础指令（兼容旧调用方）；执行链路用 agent_runtime 组装完整上下文。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id=? AND active=1", (agent_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Agent 不存在")
    instructions = row["instructions"] or "你是一个智能助手"
    return instructions


async def _assembled_agent_system(agent_id: str, message: str, session_id: str | None = None) -> tuple[str, dict]:
    """组装完整 Agent 上下文（基础指令 + 会话记忆 + 知识库 RAG + 技能 + 工具协议 + MCP 工具）。

    Agent 不存在时透传 404；资源组装失败时降级为基础指令，不阻断执行。返回 (system, bundle)。
    """
    try:
        bundle = agent_runtime.load_agent_bundle(agent_id, message)
        agent_runtime.attach_session_memory(bundle, session_id, query=message)
        await agent_runtime.attach_mcp_tools(bundle)
        return agent_runtime.build_agent_system(bundle), bundle
    except HTTPException:
        raise
    except Exception:
        logger.warning(f"agent context assembly failed for {agent_id}, fallback to base instructions")
        try:
            return get_agent_system_prompt(agent_id), {}
        except HTTPException:
            raise
        except Exception:
            return "你是一个智能助手", {}


def _record_execution(agent_id: str, user_id: str, message: str, status: str, elapsed: float, error: str = "") -> None:
    """记录 Agent 执行历史（v13.23：时间/任务/结果状态/耗时）。失败静默，不影响主流程。"""
    try:
        conn = get_db()
        conn.execute(
            """INSERT INTO agent_executions (agent_id, user_id, message, status, elapsed, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_id, user_id or "", (message or "")[:200], status, round(elapsed, 2), (error or "")[:300]),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


@router.get("/api/agent-executions")
def agent_executions(agent_id: str = "", user_id: str = "", limit: int = 20):
    """Agent 执行历史聚合：最近 N 次执行（时间/任务/结果状态/耗时），按时间倒序（v13.23）。"""
    limit = max(1, min(limit, 100))
    conn = get_db()
    try:
        sql = "SELECT * FROM agent_executions WHERE 1=1"
        args: list = []
        if agent_id:
            sql += " AND agent_id=?"
            args.append(agent_id)
        if user_id:
            sql += " AND user_id=?"
            args.append(user_id)
        sql += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, req: dict):  # noqa: C901
    """运行 Agent - 调用 LLM（v12.0：携带 conversation_id 时使用多轮上下文；v17.0：绑定知识库 RAG + 技能 + 工具调用循环）"""
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    start = time.time()
    system, bundle = await _assembled_agent_system(agent_id, message, req.get("conversation_id") or req.get("session_id"))
    conv_id = req.get("conversation_id")
    session_id = req.get("session_id")
    user_id = req.get("user_id", "")
    runnable = bundle.get("runnable_tools") or set()
    # 多轮上下文（含当前 user 消息；无会话时 None → execute_tool_loop 默认 [system, prompt]）
    conversation_messages = None
    if conv_id:
        conversation_messages = build_conversation_messages(conversation_id=conv_id, system_prompt=system)
    elif session_id:
        conversation_messages = build_conversation_messages(session_id=session_id, system_prompt=system)
    try:
        # 统一工具循环（v18：FC 原生 + 异步 LLM，与 Team/Workflow 同源，不再双实现）
        loop = await agent_runtime.execute_tool_loop(
            system,
            message,
            runnable,
            user_id=user_id,
            max_tokens=2000,
            model=bundle.get("model") or None,  # v18 P0：agent 级模型选择生效
            mcp_servers=bundle.get("mcp_servers"),
            mcp_tools=bundle.get("mcp_tools"),
            conversation_messages=conversation_messages,
            metrics_ref=f"agent:{bundle.get('id', '')}",  # v18.2 指标归因
        )
        result = loop["result"]
        tools_used: list[str] = loop["tools_used"]
    except HTTPException as e:
        _record_execution(agent_id, user_id, message, "error", time.time() - start, str(e.detail))
        raise
    except Exception as e:
        _record_execution(agent_id, user_id, message, "error", time.time() - start, str(e))
        raise

    # 记录消息到最新会话（若有）
    if conv_id or session_id:
        try:
            conn = get_db()
            now = datetime.now().isoformat()
            if conv_id:
                conn.execute(
                    """INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)""",
                    (conv_id, "assistant", result, now),
                )
                conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conv_id))
            else:
                conn.execute(
                    """INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)""",
                    (session_id, "assistant", result, now),
                )
                conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
            conn.commit()
            conn.close()
        except Exception:
            pass

    # P1-3 闭环：对话后自动记忆提取（关键词触发才调 LLM；仅 sessions 有记忆空间，conversations 不存）
    await _maybe_extract_memory(session_id, agent_id, message, result)
    log_usage("agent_run", len(message), len(result), time.time() - start, agent_id=agent_id, model=bundle.get("model") or "")  # v18.2 归因 + v18.3 成本估算
    _record_execution(agent_id, user_id, message, "done", time.time() - start)
    return {
        "result": result,
        "agent_id": agent_id,
        "elapsed": round(time.time() - start, 2),
        # v17.0：上下文使用透明化（前端可展示「引用了知识库 X / 调用了工具 Y」）
        "tools_used": tools_used,
        "mcp_calls": list(loop["mcp_calls"]),  # v18.4：MCP 调用回执透明化（server:tool 列表）
        "used": {
            "kb": len(agent_runtime._parse_list((bundle or {}).get("knowledge_base_ids"))),
            "skills": 1 if (bundle or {}).get("skills_context") else 0,
            "tools": tools_used,
        },
    }


@router.post("/api/agents/{agent_id}/run/stream")
async def run_agent_stream(agent_id: str, req: dict):  # noqa: C901
    """运行 Agent（SSE 流式）— v17.0：绑定知识库 RAG + 技能 + 工具调用循环。

    事件流：``tool``（工具调用，0-2 个）→ ``delta``（增量文本）→ ``done``（完整结果）或 ``error``。
    中间轮（可能含工具指令）非流式；最终答案分块流式输出（打字机兼容）。
    """
    message = (req.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    conv_id = req.get("conversation_id")
    session_id = req.get("session_id")
    user_id = req.get("user_id", "")
    system, bundle = await _assembled_agent_system(agent_id, message, conv_id or session_id)
    runnable = bundle.get("runnable_tools") or set()
    # 多轮上下文（含当前 user 消息；无会话时 None → 默认 [system, prompt]）
    conversation_messages = None
    if conv_id:
        conversation_messages = build_conversation_messages(conversation_id=conv_id, system_prompt=system)
    elif session_id:
        conversation_messages = build_conversation_messages(session_id=session_id, system_prompt=system)
    start = time.time()

    async def gen():
        tool_events: list[dict] = []

        # 工具事件实时转发：execute_tool_loop 在真实执行前推事件，gen 消费后发 SSE
        async def on_tool_use(kind: str, label: str, preview: str) -> None:
            tool_events.append({"tool": label, "input": preview})

        # 后台跑统一工具循环（FC 原生，与 Team/Workflow 同源），事件随产随发
        loop_task = asyncio.create_task(
            agent_runtime.execute_tool_loop(
                system,
                message,
                runnable,
                user_id=user_id,
                max_tokens=2000,
                model=bundle.get("model") or None,  # v18 P0
                mcp_servers=bundle.get("mcp_servers"),
                mcp_tools=bundle.get("mcp_tools"),
                conversation_messages=conversation_messages,
                on_tool_use=on_tool_use,
                metrics_ref=f"agent:{bundle.get('id', '')}",  # v18.2 指标归因
            )
        )
        emitted = 0
        while not loop_task.done():
            while emitted < len(tool_events):
                yield _sse_event("tool", tool_events[emitted])
                emitted += 1
            await asyncio.sleep(0.02)
        while emitted < len(tool_events):
            yield _sse_event("tool", tool_events[emitted])
            emitted += 1
        try:
            loop = await loop_task
        except HTTPException as e:
            _record_execution(agent_id, user_id, message, "error", time.time() - start, str(e.detail))
            yield _sse_event("error", {"detail": e.detail})
            return
        except Exception as e:
            _record_execution(agent_id, user_id, message, "error", time.time() - start, str(e)[:300])
            logger.exception("agent stream failed")
            yield _sse_event("error", {"detail": f"流式调用异常: {e}"})
            return

        final_answer = loop["result"]
        tools_used = loop["tools_used"]

        # 最终答案分块流式输出（打字机兼容；与 v17 行为一致）
        full = ""
        chunk = 24
        for i in range(0, len(final_answer), chunk):
            part = final_answer[i : i + chunk]
            full += part
            yield _sse_event("delta", {"text": part})

        # 落库 assistant 回复（若有会话）
        if conv_id or session_id:
            try:
                c2 = get_db()
                now2 = datetime.now().isoformat()
                if conv_id:
                    c2.execute(
                        """INSERT INTO messages (conversation_id, role, content, timestamp)
                           VALUES (?, ?, ?, ?) """,
                        (conv_id, "assistant", full, now2),
                    )
                    c2.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now2, conv_id))
                else:
                    c2.execute(
                        """INSERT INTO messages (session_id, role, content, timestamp)
                           VALUES (?, ?, ?, ?) """,
                        (session_id, "assistant", full, now2),
                    )
                    c2.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now2, session_id))
                c2.commit()
                c2.close()
            except Exception:
                pass
        log_usage("agent_run_stream", len(message), len(full), time.time() - start, agent_id=agent_id, model=bundle.get("model") or "")  # v18.2 归因 + v18.3 成本估算
        _record_execution(agent_id, user_id, message, "done", time.time() - start)
        _schedule_memory_extraction(session_id, agent_id, message, full)
        yield _sse_event("done", {"full": full, "elapsed": round(time.time() - start, 2), "tools_used": tools_used})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_SSE_HEADERS)


# ══════════════════════════════════════════════════════════════
# Team / Workflow 执行
# ══════════════════════════════════════════════════════════

# 记忆自动提取（P1-3 闭环）：关键词预触发才调 LLM，控制成本；每轮至多 1 次小调用
_MEMORY_TRIGGER_RE = re.compile(
    r"记住|记一下|帮我记|别忘了|以後都|以後請|以後不要|不要再|我偏好|我的偏好|我习惯|我喜欢|我負責|我负责"
)
_BG_TASKS: set = set()


async def _maybe_extract_memory(session_id: str | None, agent_id: str, user_msg: str, assistant_msg: str) -> None:
    """对话后自动提取记忆：关键词命中才调 LLM 判断并写入 memories；失败静默不阻断。"""
    if not session_id or not _MEMORY_TRIGGER_RE.search(user_msg or ""):
        return
    try:
        from sessions import auto_extract_memory, compress_memory_summary

        await auto_extract_memory(session_id, agent_id, user_msg, assistant_msg)
        await compress_memory_summary(session_id, agent_id)  # v18 D：规则摘要→LLM 语义压缩（best-effort）
    except Exception as e:
        logger.debug(f"memory extraction failed: {e}")


def _schedule_memory_extraction(session_id: str | None, agent_id: str, user_msg: str, assistant_msg: str) -> None:
    """流式版：响应完成后 fire-and-forget 提取（保持强引用防 GC）；触发条件同上。"""
    if not session_id or not _MEMORY_TRIGGER_RE.search(user_msg or ""):
        return

    async def _task() -> None:
        try:
            from sessions import auto_extract_memory, compress_memory_summary

            await auto_extract_memory(session_id, agent_id, user_msg, assistant_msg)
            await compress_memory_summary(session_id, agent_id)  # 同上，best-effort
        except Exception as e:
            logger.debug(f"memory extraction task failed: {e}")

    task = asyncio.create_task(_task())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)


# Team 并行成员执行并发上限（控制资源压力；不无限堆并发）
_TEAM_MEMBER_CONCURRENCY = 2
_MAX_TEAM_SUBTASKS = 4


async def _gather_capped(items: list, runner) -> list:
    """按并发上限（_TEAM_MEMBER_CONCURRENCY）并行执行 runner(item)；不无限堆并发。"""
    sem = asyncio.Semaphore(_TEAM_MEMBER_CONCURRENCY)

    async def _one(item):
        async with sem:
            return await runner(item)

    return await asyncio.gather(*[_one(i) for i in items])


async def _team_plan_subtasks(message: str, team_instructions: str, agents: list[dict]) -> list[dict] | None:
    """coordinate 模式 planner（P1-5）：LLM 把大任务拆成子任务并按成员专长分配。

    失败/返回空 → None，调用方降级为「所有成员拿原始消息」旧行为（诚实降级不阻断）。
    单次小 LLM 调用（max_tokens=500），子任务上限 _MAX_TEAM_SUBTASKS 控成本。
    """
    if len(agents) < 2:
        return None
    roster = "\n".join(f"- {a['name']}：{str((a.get('instructions') or '').strip()[:60]) or '无说明'}" for a in agents)
    try:
        out = await call_llm_async(
            "你是团队任务规划器。把任务拆成子任务并分配给最合适的成员。只返回 JSON，不要其它内容。",
            (
                f"团队协作规则：{(team_instructions or '')[:300]}\n团队成员：\n{roster}\n任务：{message[:500]}\n"
                f'返回 JSON：{{"subtasks":[{{"assignee":"成员名","task":"子任务描述"}}, ...]}}，最多 {_MAX_TEAM_SUBTASKS} 条；'
                "任务简单时可只拆 1 条。"
            ),
            max_tokens=500,
        )
    except Exception as e:
        logger.warning(f"team planner failed, fallback to raw task: {e}")
        return None
    data = parse_llm_json(out)
    name_map = {a["name"]: a for a in agents}
    subs = []
    for s in (data.get("subtasks") or [])[:_MAX_TEAM_SUBTASKS]:
        if not isinstance(s, dict):
            continue
        who = str(s.get("assignee") or "").strip()
        task = str(s.get("task") or "").strip()
        if who in name_map and task:
            subs.append({"agent": name_map[who], "task": task})
    return subs or None


@router.post("/api/teams/{team_id}/run")
async def run_team(team_id: str, req: dict):  # noqa: C901
    """运行 Team：按协作模式调度成员 Agent 执行，并汇总结果。

    - coordinate（协调）：planner 拆分子任务分配成员（失败降级为全员拿原始消息）→ 并发上限内并行执行 → 协调者汇总最终答案
    - sequential（顺序）：成员按顺序执行，上一步输出作为下一步输入
    - parallel（并行）：所有成员在并发上限内执行，返回各自结果
    """

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
    team_session = req.get("conversation_id") or req.get("session_id")
    start = time.time()

    async def _run_member(agent: dict, task: str, extra_context: str = "") -> dict:
        """单个成员 Agent 执行：完整 bundle（指令 + RAG + 技能 + 工具循环）。

        成员以自身绑定的知识库/技能/工具真实参与协作；工具可执行时走 ≤2 轮调用循环。
        Agent 行缺失时降级为纯文本指令路径，不阻断团队执行。
        """
        prompt = f"团队任务：{task}"
        if extra_context:
            prompt += f"\n\n前序成员产出（供参考）：\n{extra_context}"
        base = agent["instructions"] or "你是一个智能助手"
        system = f"{base}\n\n## 团队协作规则\n{team_instructions}" if team_instructions else base
        runnable: set[str] = set()
        try:
            bundle = agent_runtime.load_agent_bundle(agent["id"], prompt)
            agent_runtime.attach_session_memory(bundle, team_session, query=prompt)
            await agent_runtime.attach_mcp_tools(bundle)
            system = agent_runtime.build_agent_system(bundle)
            if team_instructions:
                system += f"\n\n## 团队协作规则\n{team_instructions}"
            runnable = set(bundle.get("runnable_tools") or [])
            loop = await agent_runtime.execute_tool_loop(
                system,
                prompt,
                runnable,
                user_id="team",
                model=bundle.get("model") or None,  # v18 P0：成员 agent 各自模型
                mcp_servers=bundle.get("mcp_servers"),
                mcp_tools=bundle.get("mcp_tools"),
                metrics_ref=f"agent:{bundle.get('id', '')}",  # v18.2 指标归因（成员 agent）
            )
            return {
                "agent_id": agent["id"],
                "name": agent["name"],
                "result": loop["result"],
                "tools_used": loop["tools_used"],
                "mcp_calls": loop["mcp_calls"],
            }
        except HTTPException:
            pass  # Agent 行缺失 → 降级为纯文本指令
        except Exception as e:
            return {"agent_id": agent["id"], "name": agent["name"], "result": f"（执行失败：{e}）", "error": str(e), "tools_used": []}
        try:
            result = await call_llm_async(system, prompt, max_tokens=2000)
            return {"agent_id": agent["id"], "name": agent["name"], "result": result, "tools_used": []}
        except Exception as e:
            return {"agent_id": agent["id"], "name": agent["name"], "result": f"（执行失败：{e}）", "error": str(e), "tools_used": []}

    member_results = []
    coordinator_result = ""
    if not agents:
        # 无成员：直接用团队指令执行
        result = await call_llm_async(team_instructions, message, max_tokens=2000)
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
        # 并行执行：各自独立完成，直接返回成员结果拼接（并发上限 2）
        member_results = await _gather_capped(agents, lambda a: _run_member(a, message))
        coordinator_result = "\n\n".join(f"### {r['name']}\n{r['result']}" for r in member_results)
    else:
        # coordinate：planner 拆分分配 → 并发上限内执行 → 协调者汇总
        subtasks = await _team_plan_subtasks(message, team_instructions, agents)
        if subtasks:
            # planner 拆分后按分配执行（同并发上限）
            member_results = await _gather_capped(subtasks, lambda st: _run_member(st["agent"], st["task"]))
        else:
            member_results = await _gather_capped(agents, lambda a: _run_member(a, message))
        digest = "\n\n".join(f"### {r['name']} 的产出\n{r['result'][:1200]}" for r in member_results)
        coordinator_system = (
            f"你是团队协调者。请汇总以下团队成员对任务的产出，给出统一的最终答案。\n"
            f"## 团队协作规则\n{team_instructions}"
        )
        coordinator_result = await call_llm_async(
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


def _load_workflow_config(workflow_id: str) -> dict:
    """加载工作流配置。"""
    # 简化的工作流加载
    return {"id": workflow_id, "steps": [], "config": {}}


def _validate_workflow_steps(workflow: dict) -> list:
    """验证工作流步骤。"""
    steps = workflow.get("steps", [])
    valid_steps = []
    for step in steps:
        if step.get("type") in ["llm", "tool", "condition"]:
            valid_steps.append(step)
    return valid_steps


def _format_workflow_output(execution_results: list) -> dict:
    """格式化工作流输出。"""
    return {"status": "completed", "results": execution_results, "total_steps": len(execution_results)}


async def _run_executor_workflow(workflow_id: str, input_data: dict, nodes: list) -> dict:
    """用完整 executor 执行工作流并整理结果摘要。"""
    from workflows.executor import executor as _executor

    run_id = await _executor.execute(workflow_id, input_data or {})
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

    node_labels = {}
    for n in nodes:
        if isinstance(n, dict) and n.get("id"):
            node_labels[n["id"]] = n.get("label") or n.get("name") or n["id"]

    node_results = []
    for nid, res in output_data.items():
        if nid == "input":
            continue
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

    final_result = _wf_final_result(output_data, node_labels, nodes)
    elapsed = _wf_elapsed(run_dict)

    return {
        "result": _wf_node_summary(final_result),
        "nodes": node_results,
        "run": run_dict,
        "workflow_id": workflow_id,
        "engine": "executor",
        "elapsed": elapsed,
    }


def _wf_final_result(output_data: dict, node_labels: dict, nodes: list = None) -> dict:
    """挑选最终结果：优先结束(output)节点 → 定义顺序最后一个成功节点 → 任意成功 → 错误信息。"""
    node_types = {}
    for n in nodes or []:
        if isinstance(n, dict) and n.get("id"):
            node_types[n["id"]] = n.get("type", "")
    # 1) 结束节点（output）
    for nid, t in node_types.items():
        if t == "output":
            r = output_data.get(nid)
            if isinstance(r, dict) and r.get("status") == "success":
                return r
    # 2) 定义顺序最后一个成功节点（排除开始节点自身，避免把入参当最终输出）
    for nid in reversed(list(node_labels)):
        if node_types.get(nid) == "start":
            continue
        r = output_data.get(nid)
        if isinstance(r, dict) and r.get("status") == "success":
            return r
    # 3) 任意成功 → 错误信息
    for r in reversed(list(output_data.values())):
        if isinstance(r, dict) and r.get("status") == "success":
            return r
    for r in output_data.values():
        if isinstance(r, dict) and r.get("status") == "error":
            return r
    return {"status": "error", "message": "工作流未产生任何输出，请检查节点配置与连线"}


def _wf_elapsed(run_dict: dict | None) -> float | None:
    """计算工作流运行耗时（秒）。"""
    try:
        if run_dict and run_dict.get("started_at") and run_dict.get("completed_at"):
            start = datetime.fromisoformat(run_dict["started_at"])
            end = datetime.fromisoformat(run_dict["completed_at"])
            return round((end - start).total_seconds(), 2)
    except (ValueError, TypeError):
        pass
    return None


@router.post("/api/workflows/runs/{run_id}/resume")
async def workflow_run_resume(run_id: str, reset_node: list = Query(default=None), current_user: dict = require_auth()):
    """v18.3 断点续跑：以旧 run 的成功节点快照为起点重跑（节点不重执行）。

    reset_node（可多个）：单节点回滚——清除该节点快照，重跑它及其下游。
    诚实边界：快照源是 workflow_run_logs 的 success 行；工作流结构变更后层序可能不一致，
    返回 resumed_nodes 供审计。
    """
    conn = get_db()
    run = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not run:
        raise HTTPException(404, "运行记录不存在")
    wf_id = run["workflow_id"]
    if not wf_id:
        raise HTTPException(400, "该运行无 workflow_id，无法续跑")
    try:
        wf_input = json.loads(run["input_data"] or "{}")
    except (json.JSONDecodeError, TypeError):
        wf_input = {}

    from workflows.executor import executor as _executor

    seeded = _executor._load_resume_snapshots(run_id, reset_node)
    new_run_id = await _executor.execute(wf_id, wf_input, resume_run_id=run_id, reset_nodes=reset_node)
    conn = get_db()
    new_run = conn.execute("SELECT id, status FROM workflow_runs WHERE id=?", (new_run_id,)).fetchone()
    conn.close()
    return {
        "source_run": run_id,
        "new_run": new_run["id"] if new_run else new_run_id,
        "status": new_run["status"] if new_run else "unknown",
        "resumed_nodes": sorted(seeded.keys()),
        "reset_nodes": reset_node or [],
    }


@router.get("/api/workflows/runs/{run_id}/snapshots")
async def workflow_run_snapshots(run_id: str, current_user: dict = require_auth()):
    """v18.2 运行快照：节点级 input/output/status 时间线（工作流可观测性的地基）。"""
    conn = get_db()
    run = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    logs = conn.execute(
        "SELECT node_id, status, output_data, completed_at, "
        "COALESCE(input_data, '') AS input_data FROM workflow_run_logs WHERE run_id=? ORDER BY completed_at",
        (run_id,),
    ).fetchall()
    conn.close()
    if not run:
        raise HTTPException(404, "运行记录不存在")
    return {
        "run_id": run_id,
        "workflow_id": run["workflow_id"],
        "status": run["status"],
        "workflow_input": run["input_data"] or "{}",
        "nodes": [dict(r) for r in logs],
    }


@router.post("/api/workflows/runs/{run_id}/replay")
async def workflow_run_replay(run_id: str, current_user: dict = require_auth()):
    """v18.2 重放：用原运行保存的 input_data 重新跑同工作流（快照 → 可重跑）。

    诚实边界：v1 是输入重放（新 run_id，不篡改历史 run）；节点级断点续跑/回滚为 v2。
    """
    conn = get_db()
    run = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not run:
        raise HTTPException(404, "运行记录不存在")
    wf_id = run["workflow_id"]
    if not wf_id:
        raise HTTPException(400, "该运行无 workflow_id（兼容旧数据），无法重放")
    try:
        wf_input = json.loads(run["input_data"] or "{}")
    except (json.JSONDecodeError, TypeError):
        wf_input = {}
    from workflows.executor import executor as _executor

    new_run_id = await _executor.execute(wf_id, wf_input)
    conn = get_db()
    new_run = conn.execute("SELECT id, status FROM workflow_runs WHERE id=?", (new_run_id,)).fetchone()
    conn.close()
    return {
        "source_run": run_id,
        "new_run": new_run["id"] if new_run else new_run_id,
        "status": new_run["status"] if new_run else "unknown",
    }


@router.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, req: dict):  # noqa: C901
    """运行 Workflow - 若可用 executor 则用，否则简单执行"""
    message = (req.get("message") or "").strip()
    # 开始节点字段：除 message 外的其它键作为工作流入参（供 ${start.result.<key>} 引用）
    input_data = {k: v for k, v in req.items() if k != "message"}
    full_input = {**input_data, "message": message}
    if not message and not input_data:
        raise HTTPException(400, "消息或开始节点输入不能为空")

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
        return await _run_executor_workflow(workflow_id, full_input, nodes)
    except Exception as e:
        logger.warning(f"workflow executor unavailable, simple run: {e}")

    # 简单执行：把节点信息组装给 LLM
    node_desc = ""
    if nodes:
        node_desc = "\n".join(f"- {n.get('type')}: {n.get('name')}" for n in nodes[:10])
    system = "你是工作流执行引擎，根据工作流定义和输入，直接给出执行结果。"
    prompt = f"工作流: {wf['name']}\n节点: {node_desc or '（无节点定义）'}\n\n输入: {message}"
    result = await call_llm_async(system, prompt, max_tokens=2000)
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
        raise HTTPException(404, "操作失败，请稍后重试")

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
