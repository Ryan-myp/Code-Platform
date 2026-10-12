"""Agent 执行运行时：绑定资源（知识库 RAG / 技能 / 工具）接入执行链路。

历史短板：Agent 表单可绑定 知识库/Skills/工具/MCP，但执行引擎只用 instructions，
绑定资源全部是摆设（E2E 实锤）。本模块补齐：

1. load_agent_bundle：加载 Agent 行 + 绑定资源（KB/Skills/工具说明）
2. build_agent_system：组装系统提示词 = 基础指令 + RAG 参考知识 + 技能 + 工具清单与调用协议
3. execute_tool / execute_tool_async：真实执行绑定的工具
   - code_interpreter → common.sandbox_check.run_sandbox_python（受限子进程）
   - compute 工具     → tool_hub._run_compute_tool（本地实算，不走 LLM）
   - LLM 工具        → tool_hub._run_tool_worker（真实生成 + 落使用记录）
   - terminal / file_system → 诚实降级（需要沙箱项目环境，不假装可用）
4. strip_tool_directives：从最终答案中移除协议块，给用户干净结果

工具调用协议（LLM 侧）：
    [TOOL:工具名|输入内容]
最多 2 轮工具调用；工具执行结果回喂 LLM 生成最终答案。
"""

import json
import logging
import re

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 2
_MAX_TOOL_INPUT = 4000
_MAX_TOOL_RESULT = 3000
_TOOL_DIRECTIVE_RE = re.compile(r"\[TOOL:([^\]\|]+)\|([^\[\]]*)\]")

# 可真实执行的语义工具映射（agent.tools 里的旧种子名）
# code_interpreter → 沙箱子进程；其余名字在工具广场无同名可执行工具时诚实降级提示
_SEMANTIC_TOOL_MAP = {
    "code_interpreter": "code_interpreter",
}


def _parse_list(raw):
    try:
        v = json.loads(raw or "[]")
        return v if isinstance(v, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def load_agent_bundle(agent_id: str, user_message: str = "") -> dict:
    """加载 Agent 及其绑定资源，返回组装上下文所需的完整 bundle。

    返回 {agent, rag_context, skills_context, tool_lines, runnable_tools, user_message}。
    资源缺失/损坏时静默降级（bundle 字段为空），不阻断执行。
    """
    from common.db import get_db

    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id=?", (agent_id,)).fetchone()
    skill_ids = _parse_list(row["skill_ids"]) if row else []
    skills = []
    if row and skill_ids:
        skills = [
            dict(r)
            for r in conn.execute(
                "SELECT name, description, content FROM skills WHERE id IN ({})".format(
                    ",".join("?" * len(skill_ids))
                ),
                skill_ids,
            ).fetchall()
        ]
    conn.close()

    if not row:
        raise HTTPException(404, "Agent 不存在")
    agent = dict(row)

    # ── RAG：绑定知识库按用户消息检索 ──
    rag = _kb_rag_context(_parse_list(agent.get("knowledge_base_ids")), user_message)
    agent["rag_context"] = rag

    # ── Skills：注入技能指令 ──
    agent["skills_context"] = _skills_context([dict(s) for s in skills])

    # ── Tools：可执行工具说明 + 白名单 ──
    tool_lines, runnable = _tool_descriptions(_parse_list(agent.get("tools")))
    agent["tool_lines"] = tool_lines
    agent["runnable_tools"] = runnable
    return agent


def _kb_rag_context(kb_ids: list, user_message: str, max_chars: int = 3500) -> str:
    """对绑定知识库做相关度检索（v2 打分），拼「参考知识」段。失败静默降级。"""
    if not kb_ids or not (user_message or "").strip():
        return ""
    import kb_api
    from common.db import get_db

    conn = get_db()
    kbs = []
    for kid in kb_ids[:3]:
        r = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kid,)).fetchone()
        if r:
            kbs.append(dict(r))
    conn.close()

    sections = []
    for kb in kbs:
        try:
            cfg = json.loads(kb.get("config") or "{}") or {}
            if (kb.get("type") or "file") == "db":
                res = kb_api._kb_search_db(cfg, user_message, 4)
            else:
                res = kb_api._kb_search_file(kb, user_message, 4)
            hits = res.get("hits") or []
            if not hits:
                continue
            lines = [f"### 知识库「{kb.get('name', kb['id'])}」"]
            for h in hits[:3]:
                if "file" in h:  # file 型：文件名 + top 匹配行
                    for m in h.get("matches", [])[:2]:
                        lines.append(f"- {h['file']}：{m[:200]}")
                else:  # db 型：行内容摘要（排除打分离）
                    summary = " | ".join(str(v)[:80] for kk, v in h.items() if v and kk not in ("score",))[:300]
                    lines.append(f"- {summary}")
            sections.append("\n".join(lines))
        except Exception as e:  # 单个 KB 损坏不影响其它
            logger.warning(f"kb rag failed for {kb.get('id')}: {e}")
            continue
    if not sections:
        return ""
    text = "## 参考知识（来自你绑定的知识库，与用户问题相关；回答时优先引用）\n\n" + "\n\n".join(sections)
    return text[:max_chars]


def _skills_context(skill_rows: list, max_chars: int = 2500) -> str:
    lines = []
    for s in skill_rows[:3]:
        body = (s.get("content") or "").strip()[:800]
        desc = (s.get("description") or "").strip()
        lines.append(f"### 技能「{s.get('name')}」\n{desc}\n{body}" if body else f"### 技能「{s.get('name')}」\n{desc}")
    if not lines:
        return ""
    return "## 可用技能（按用户请求套用以下技能规范）\n\n" + "\n\n".join(lines)[:max_chars]


def _tool_descriptions(tool_ids: list) -> tuple[list[str], set[str]]:
    """工具清单说明行 + 可真实执行的工具白名单。"""
    from tool_definitions import TOOL_DEFINITIONS
    lines = []
    runnable = set()
    for tid in tool_ids[:8]:
        name = tid
        desc = ""
        meta = TOOL_DEFINITIONS.get(tid)
        if meta:
            name = meta.get("name", tid)
            desc = meta.get("description", "")
        if tid == "code_interpreter":
            desc = "执行 Python 代码（沙箱子进程，10 秒 CPU 限制），适合数值计算/数据处理/验证"
            runnable.add(tid)
        elif tid in TOOL_DEFINITIONS and TOOL_DEFINITIONS[tid].get("type") == "compute":
            # 仅 compute 实算工具可真实执行（快、无 LLM 额度消耗）；LLM 生成类工具走工具广场页面
            runnable.add(tid)
        elif tid in ("terminal", "file_system", "web_search"):
            desc = desc or "该能力暂不在 Agent 内直接执行"
        lines.append(f"- {name}：{desc or '（工具广场工具，可在左侧工具广场使用）'}")
    return lines, runnable


def build_agent_system(agent: dict, base_instructions: str | None = None) -> str:
    """组装 Agent 系统提示词：基础指令 + RAG + 技能 + 工具协议。"""
    parts = [base_instructions or agent.get("instructions") or "你是一个智能助手"]
    if agent.get("rag_context"):
        parts.append(agent["rag_context"])
    if agent.get("skills_context"):
        parts.append(agent["skills_context"])
    if agent.get("tool_lines"):
        parts.append("## 可用工具\n" + "\n".join(agent["tool_lines"]))
    if agent.get("runnable_tools"):
        parts.append(
            "如果任务需要用到「可用工具」中列出的 code_interpreter 或工具广场工具，"
            "请在回复末尾追加调用指令（一行一个，最多 2 个）：[TOOL:工具名|输入内容]\n"
            "代码类输入直接写完整可运行代码；工具执行结果随后会单独提供，届时再给出最终答案。"
        )
    return "\n\n".join(p for p in parts if p)


def parse_tool_directives(text: str, runnable_tools: set[str]) -> list[tuple[str, str]]:
    """从 LLM 回复中解析工具调用指令；只保留白名单内工具。"""
    out = []
    for m in _TOOL_DIRECTIVE_RE.finditer(text or ""):
        name = m.group(1).strip()
        arg = m.group(2).strip()
        mapped = _SEMANTIC_TOOL_MAP.get(name, name)
        if mapped in runnable_tools:
            out.append((mapped, arg[:_MAX_TOOL_INPUT]))
    return out[:_MAX_TOOL_ROUNDS]


def strip_tool_directives(text: str) -> str:
    """移除协议块，给用户干净答案。"""
    return _TOOL_DIRECTIVE_RE.sub("", text or "").strip()


async def execute_tool_async(tool_id: str, tool_input: str, user_id: str = "default") -> str:
    """真实执行工具，返回给 LLM 回喂的结果文本。失败返回降级说明而非抛异常。"""
    if tool_id == "code_interpreter":
        from common.sandbox_check import run_sandbox_python

        try:
            r = run_sandbox_python(tool_input, timeout=30)
            output = (r.get("output") or "").strip()
            error = (r.get("error") or "").strip()
            if r.get("exit_code") == 0 and not error:
                return f"代码执行成功（{r.get('duration')}s）\n输出：{output[:_MAX_TOOL_RESULT] or '（无输出）'}"
            return f"代码执行失败（exit {r.get('exit_code')}）\n错误：{(error or output)[:_MAX_TOOL_RESULT]}"
        except Exception as e:
            return f"code_interpreter 执行异常：{str(e)[:300]}"

    # 工具广场工具（compute 实算 / LLM 生成）
    from tool_definitions import TOOL_DEFINITIONS
    from tool_hub import _run_tool_worker

    meta = TOOL_DEFINITIONS.get(tool_id)
    if not meta:
        return f"工具「{tool_id}」不存在或未接入执行链路，请基于自身知识直接回答。"
    if meta.get("type") == "app":
        return f"工具「{meta.get('name', tool_id)}」需要专属页面操作，请在左侧工具广场打开使用。"
    try:
        res = await _run_tool_worker({"tool_id": tool_id, "input": tool_input, "user_id": user_id})
        text = res.get("result") or ""
        return f"工具「{meta.get('name', tool_id)}」执行结果：\n{str(text)[:_MAX_TOOL_RESULT]}"
    except HTTPException as e:
        return f"工具「{tool_id}」执行失败：{e.detail}"
    except Exception as e:
        return f"工具「{tool_id}」执行异常：{str(e)[:300]}"
