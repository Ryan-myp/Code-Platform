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

from common.llm import call_llm_async
from mcp_client import (
    parse_mcp_directives,
    strip_mcp_directives,
)

logger = logging.getLogger(__name__)

_MAX_TOOL_ROUNDS = 8  # 工具调用轮次上限（v17→v21 放宽到 8，配合 token 预算控成本）
_MAX_TOOL_INPUT = 4000
_MAX_TOOL_RESULT = 3000
_MAX_TOOL_TOKEN_BUDGET = 12000  # 累计 token 预算（估算：字符数 / 4）
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


def _build_tool_schemas(runnable_tools: set[str]) -> list[dict]:
    """从 runnable_tools 生成 OpenAI function calling 工具 schema。

    每个工具的入参统一为 {"input": string}，与文本协议 [TOOL:name|input] 语义一致。
    """
    from tool_definitions import TOOL_DEFINITIONS

    schemas = []
    for tid in sorted(runnable_tools):
        meta = TOOL_DEFINITIONS.get(tid, {})
        name = meta.get("name", tid)
        desc = meta.get("description", "")
        if tid == "code_interpreter":
            desc = "执行 Python 代码（沙箱，10s CPU 限制），适合数值计算/数据处理/验证"
        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": tid,
                    "description": (desc or f"工具 {name}")[:200],
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input": {
                                "type": "string",
                                "description": "工具输入内容（代码、任务描述或 JSON 参数）",
                            }
                        },
                        "required": ["input"],
                    },
                },
            }
        )
    return schemas[:8]  # 与 _tool_descriptions 一致，上限 8 个


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

    # ── Skills：注入技能指令（v18 P2：带用户消息做确定性参数预填）──
    agent["skills_context"] = _skills_context([dict(s) for s in skills], user_message=user_message)

    # ── Tools：可执行工具说明 + 白名单 ──
    tool_lines, runnable = _tool_descriptions(_parse_list(agent.get("tools")))
    agent["tool_lines"] = tool_lines
    agent["runnable_tools"] = runnable

    # ── MCP：同步读取绑定的 Server 行（工具清单由 async attach_mcp_tools 挂接）──
    mcp_servers: list[dict] = []
    try:
        raw_mcp = _parse_list(agent.get("mcp_server_ids"))
        if raw_mcp:
            conn = get_db()
            ph = ",".join("?" * len(raw_mcp[:2]))  # 每个 Agent 最多接入 2 个 MCP Server
            rows = conn.execute(
                f"SELECT * FROM mcp_servers WHERE id IN ({ph}) AND enabled=1", raw_mcp[:2]
            ).fetchall()
            conn.close()
            mcp_servers = [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"mcp servers load failed: {e}")
        mcp_servers = []
    agent["mcp_servers"] = mcp_servers
    agent["mcp_server_ids"] = [s["id"] for s in mcp_servers]
    agent["mcp_tool_lines"] = []
    return agent


def _kb_rerank(q: str, previews: list[str]) -> list[int]:
    """LLM 重排：从 N 个关键词命中的预览中选出相关性 top3 的顺序（候选 ≥ 4 才值得调）。

    返回完整重排后的下标列表；失败/无需重排返回 []，调用方保持关键词原序（诚实降级）。
    """
    if len(previews) < 4 or not (q or "").strip():
        return []
    from common.llm import call_llm

    items = "\n".join(f"{i}. {p}" for i, p in enumerate(previews))
    try:
        out = call_llm(
            "你是搜索相关性排序器。根据用户问题对知识片段按相关性降序排列，只返回 JSON，不要其它内容。",
            f"用户问题：{q[:200]}\n候选片段：\n{items}\n返回 JSON：{{\"top\":[下标，最多 3 个，按相关性降序]}}",
            max_tokens=200,
        )
        m = re.search(r"\{.*?\}", out or "", re.S)
        data = json.loads(m.group(0)) if m else {}
        top = [int(i) for i in (data.get("top") or []) if isinstance(i, (int, str)) and str(i).lstrip("-").isdigit() and 0 <= int(i) < len(previews)]
        top = top[:3]
        seen: set[int] = set(top)
        return top + [i for i in range(len(previews)) if i not in seen]
    except Exception as e:
        logger.warning(f"kb rerank failed, keep keyword order: {e}")
        return []


def _kb_rag_context(kb_ids: list, user_message: str, max_chars: int = 4000) -> str:
    """对绑定知识库做相关度检索（v2 分块打分 + LLM 重排），拼「参考知识」段。失败静默降级。

    - 每个 KB 取 top3 候选块，跨 KB 汇总后若候选 ≥ 4 个，用一次 LLM 调用按相关性重排
      （不用向量基建拿到 80% 语义收益；失败保持关键词原序）
    """
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

    # 候选：(KB名, 预览行, 详情行)；先全量收集，再统一重排取 top4
    candidates: list[tuple[str, str, list[str]]] = []
    for kb in kbs:
        try:
            cfg = json.loads(kb.get("config") or "{}") or {}
            if (kb.get("type") or "file") == "db":
                res = kb_api._kb_search_db(cfg, user_message, 4)
            else:
                res = kb_api._kb_search_file(kb, user_message, 4)
        except Exception as e:  # 单个 KB 损坏不影响其它
            logger.warning(f"kb rag failed for {kb.get('id')}: {e}")
            continue
        for h in (res.get("hits") or [])[:3]:
            kb_name = kb.get("name", kb.get("id", ""))
            if "file" in h:  # file 型：块摘录（分块后不再被截成孤行）
                matches = h.get("matches") or []
                if not matches:
                    continue
                preview = f"{h['file']}：{str(matches[0])[:150]}"
                details = [f"{h['file']}：{str(m)[:250]}" for m in matches[:2]]
            else:  # db 型：行内容摘要（排除打分离）
                summary = " | ".join(str(v)[:80] for kk, v in h.items() if v and kk not in ("score",))[:300]
                if not summary:
                    continue
                preview = summary[:150]
                details = [summary]
            candidates.append((kb_name, preview, details))
    if not candidates:
        return ""

    order = _kb_rerank(user_message, [c[1] for c in candidates])
    picked = [candidates[i] for i in (order or range(len(candidates)))][:4]

    lines = ["## 参考知识（来自你绑定的知识库，已按相关性排序；回答时优先引用）"]
    for kb_name, preview, details in picked:
        lines.append(f"- [{kb_name}] {preview}")
        for d in details[1:]:
            lines.append(f"  - {d}")
    return "\n".join(lines)[:max_chars]


def _skill_param_values(params: dict, user_message: str) -> dict:
    """确定性参数抽取（v18 P2）：params 条目支持 {"desc","pattern"}，
    pattern 命中用户消息 → 取值（group(1) 优先，其次 group(0)）；未命中 → 不填（占位符保留，LLM 兜底）。

    普通字符串条目（仅描述）不参与抽取——纯 LLM 提取路径不变。
    """
    import re

    values = {}
    msg = user_message or ""
    if not msg:
        return values
    for pname, spec in (params or {}).items():
        pattern = spec.get("pattern", "") if isinstance(spec, dict) else ""
        if not pattern:
            continue
        try:
            m = re.search(pattern, msg)
        except re.error:
            continue  # 坏 pattern 诚实跳过（不阻断技能注入）
        if m:
            values[str(pname)] = (m.group(1) if m.lastindex else m.group(0)).strip()
    return values


def _skills_context(skill_rows: list, user_message: str = "", max_chars: int = 2500) -> str:
    lines = []
    for s in skill_rows[:3]:
        body = (s.get("content") or "").strip()[:800]
        desc = (s.get("description") or "").strip()
        import json as _json

        params = {}
        try:
            params = _json.loads(s.get("params") or "{}") or {}
        except (ValueError, TypeError):
            params = {}

        # v18 P2 程序化预填：pattern 命中 → 占位符直接替换；未命中保留，由 LLM 提取（双轨诚实降级）
        filled = _skill_param_values(params, user_message)
        body_rendered = render_skill_template(body, filled) if filled else body

        block = f"### 技能「{s.get('name')}」\n{desc}\n{body_rendered}" if body_rendered else f"### 技能「{s.get('name')}」\n{desc}"
        if params:
            p_lines = []
            for k, v in params.items():
                if str(k).strip() in filled:
                    continue  # 已程序化填入的不再让 LLM 重复提取
                desc_v = v.get("desc", "") if isinstance(v, dict) else str(v).strip()
                note = f"（正则：{v.get('pattern', '')}）" if isinstance(v, dict) and v.get("pattern") else ""
                p_lines.append(f"  - {k}：{desc_v}{note}")
            if p_lines:
                block += "\n参数（回答时从用户消息中提取具体值填入占位符）：\n" + "\n".join(p_lines)
        lines.append(block)
    if not lines:
        return ""
    return "## 可用技能（按用户请求套用以下技能规范）\n\n" + "\n\n".join(lines)[:max_chars]


def render_skill_template(content: str, values: dict) -> str:
    """把技能正文里的 {{param}} 占位符替换为具体值（未提供的保留原样，诚实降级）。

    供程序化套用（如工作流技能节点）使用；LLM 注入路径由 _skills_context 提示提取。
    """
    out = content or ""
    for k, v in (values or {}).items():
        out = out.replace("{{" + str(k).strip() + "}}", str(v))
    return out


def _tool_descriptions(tool_ids: list) -> tuple[list[str], set[str]]:
    """工具清单说明行 + 可真实执行的工具白名单。

    可执行范围：code_interpreter（沙箱）+ compute 实算工具 + LLM 生成工具
    （LLM 工具经工具广场执行器真实调用，每个 Agent 上限 4 个以控成本）。
    """
    from tool_definitions import TOOL_DEFINITIONS
    lines = []
    runnable = set()
    llm_count = 0
    for tid in tool_ids[:8]:
        name = tid
        desc = ""
        meta = TOOL_DEFINITIONS.get(tid)
        if meta:
            name = meta.get("name", tid)
            desc = meta.get("description", "")
        ttype = meta.get("type") if meta else None
        if tid == "code_interpreter":
            desc = "执行 Python 代码（沙箱子进程，10 秒 CPU 限制），适合数值计算/数据处理/验证"
            runnable.add(tid)
        elif ttype == "compute":
            # compute 实算工具本地直执（快、无 LLM 额度消耗）
            runnable.add(tid)
        elif meta and (ttype is None or ttype == "llm") and llm_count < 4:
            # LLM 生成工具（tool_definitions 中无 type 字段的 54 个）也可在 Agent 内真实调用：
            # 走工具广场执行器（_run_tool_worker）真实生成 + 落使用记录，每 Agent 上限 4 个控成本
            llm_count += 1
            runnable.add(tid)
        elif tid in ("terminal", "file_system", "web_search"):
            desc = desc or "该能力暂不在 Agent 内直接执行"
        lines.append(f"- {name}：{desc or '（工具广场工具）'}")
    return lines, runnable


def build_agent_system(agent: dict, base_instructions: str | None = None) -> str:
    """组装 Agent 系统提示词：基础指令 + RAG + 技能 + 工具协议。"""
    parts = [base_instructions or agent.get("instructions") or "你是一个智能助手"]
    if agent.get("memory_context"):
        parts.append(agent["memory_context"])
    if agent.get("rag_context"):
        parts.append(agent["rag_context"])
    if agent.get("skills_context"):
        parts.append(agent["skills_context"])
    if agent.get("tool_lines"):
        parts.append("## 可用工具\n" + "\n".join(agent["tool_lines"]))
    if agent.get("mcp_tool_lines"):
        parts.append(
            "## MCP 工具（外部 MCP Server 提供的能力）\n" + "\n".join(agent["mcp_tool_lines"])
            + "\n调用时在回复末尾追加（一行一个，最多 2 个）：[MCP:工具名|JSON参数]，参数直接写工具名即可。"
        )
    if agent.get("runnable_tools") or agent.get("mcp_tool_lines"):
        parts.append(
            "如果任务需要用到「可用工具」或 MCP 工具，"
            "请在回复末尾追加调用指令（一行一个，各最多 2 个）：[TOOL:工具名|输入内容] 或 [MCP:工具名|JSON参数]\n"
            "代码类输入直接写完整可运行代码；LLM 生成类工具输入写任务描述；"
            "工具执行结果随后会单独提供，届时再给出最终答案。"
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
    """移除 [TOOL:] 与 [MCP:] 协议块，给用户干净答案。"""
    return strip_mcp_directives(_TOOL_DIRECTIVE_RE.sub("", text or "")).strip()


def _mem_relevance(content: str, query: str) -> int:
    """轻量相关性打分（CJK 双字重叠×2 + ASCII 词重叠，零依赖；与 KB 关键词口径一致）。"""
    import re

    qc = (query or "").strip()
    if not qc:
        return 0

    def toks(t: str) -> tuple[set[str], set[str]]:
        t = (t or "").lower()
        words = set(re.findall(r"[a-z0-9_]{2,}", t))
        cjk = re.findall(r"[\u4e00-\u9fff]", t)
        bigrams = {"".join(p) for p in zip(cjk, cjk[1:], strict=False)}
        return words, bigrams

    cq_words, cq_big = toks(content)
    qq_words, qq_big = toks(qc)
    return 2 * len(cq_big & qq_big) + len(cq_words & qq_words)


def attach_session_memory(bundle: dict, session_id: str | None = None, limit: int = 10, query: str = "") -> dict:
    """把会话记忆挂进 bundle：long 型优先，各截 200 字，总预算 2000 字。

    提供 query 时按与当前问题的相关性选 top-k（避免无关旧话题稀释提示词预算）；
    无相关记忆时回退「最新 limit 条」（诚实降级：不丢全部上下文）。无记忆/失败时 memory_context 为空。
    """
    agent = bundle.get("agent") or bundle
    sid = (session_id or "").strip()
    if not sid:
        bundle["memory_context"] = ""
        return bundle
    try:
        from sessions import get_memories

        rows = get_memories(sid, agent.get("id") or None)
    except Exception as e:
        logger.warning(f"session memory load failed: {e}")
        bundle["memory_context"] = ""
        return bundle

    long_rows = [r for r in rows if r.get("memory_type") in ("long", "auto")]
    short_rows = [r for r in rows if r.get("memory_type") not in ("long", "auto")]

    if (query or "").strip():
        # 按与当前问题的相关性选 top-k：长型保底 1 席（若相关），其余按分取
        scored: list[tuple[int, int, dict]] = []
        for idx, r in enumerate(long_rows + short_rows):
            s = _mem_relevance(str(r.get("content") or ""), query)
            if s > 0:
                scored.append((s, -idx, r))  # 分降序，同分取新（idx 大 = 新）
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        picked = [r for _, _, r in scored[: int(limit)]]
        # 无相关记忆 → 诚实降级回最新 limit 条（不丢全部上下文）
        if not picked:
            picked = (long_rows[: int(limit * 0.6)] + short_rows[: max(limit - int(limit * 0.6), 0)])
    else:
        picked = long_rows[: int(limit * 0.6)] + short_rows[: max(limit - int(limit * 0.6), 0)]

    long_ids = {id(r) for r in long_rows}
    lines: list[str] = []
    for r in picked:
        c = str(r.get("content") or "").strip()[:200]
        if c:
            lines.append(f"- {'[长期] ' if id(r) in long_ids else ''}{c}")
    if not lines:
        bundle["memory_context"] = ""
        return bundle
    text = ("## 历史记忆（本会话中用户明确让你记住的内容；与当前任务相关时参考）\n" + "\n".join(lines))[:2000]
    bundle["memory_context"] = text
    return bundle


async def attach_mcp_tools(bundle: dict) -> dict:
    """在 bundle 上挂接 MCP 工具清单（async，调用真实 tools/list）。

    单个 Server 不可达时跳过并保留其它；全部失败时 mcp_tool_lines 为空，
    系统提示词自动省略 MCP 段（诚实降级）。
    """
    import mcp_client

    servers = bundle.get("mcp_servers") or []
    lines: list[str] = []
    tool_map: dict[str, str] = {}
    for srv in servers:
        try:
            tools = await mcp_client.mcp_list_tools(srv)
        except Exception as e:
            logger.warning(f"mcp list_tools failed for {srv.get('id')}: {e}")
            tools = []
        for t in tools[:6]:
            lines.append(f"- [MCP] {srv.get('name')}：{t.get('name')} — {str(t.get('description') or '')[:120]}")
            tool_map[t.get("name")] = srv["id"]
    bundle["mcp_tool_lines"] = lines
    bundle["mcp_tools"] = tool_map
    return bundle


def _parse_tool_args(raw_args: str) -> str:
    """解析 function calling arguments JSON，提取 input 字段。非 JSON 原样返回。"""
    try:
        data = json.loads(raw_args)
        if isinstance(data, dict):
            return str(data.get("input", raw_args))
        return str(data)
    except (json.JSONDecodeError, TypeError):
        return raw_args


async def execute_tool_loop(
    system: str,
    prompt: str,
    runnable_tools: set[str],
    *,
    user_id: str = "default",
    max_tokens: int = 2000,
    model: str | None = None,
    fallback_models: list[str] | None = None,
    llm_call=None,
    mcp_servers: list[dict] | None = None,
    mcp_tools: dict[str, str] | None = None,
    mcp_executor=None,
    conversation_messages: list[dict] | None = None,
    on_tool_use=None,
) -> dict:
    """可复用的工具调用循环（双模式：function calling + 文本协议兼容）。

    双模式路由：
    - 生产模式（llm_call 未注入）+ 有工具 → call_llm_with_tools_async（OpenAI tools API）
    - 测试模式（llm_call 注入）或 LLM 不支持 tools → 文本协议 [TOOL:name|input]（兼容）

    参数：
    - model/fallback_models：agent 级模型选择透传（v18）；None = 全局/中转站默认。
      仅生产/文本层按传入与否注入，保持测试 fake llm_call 的旧签名兼容。

    参数：
    - conversation_messages：多轮上下文（含 system + 历史，含当前 user 消息）；
      传入时优先于默认 [system, prompt]，支持会话/Session 双轨。
    - on_tool_use：async 回调 (kind, label, preview) → None，kind∈{"tool","mcp"}，
      每次真实执行前触发；供流式路径发 SSE tool 事件（不传则静默）。

    同时支持 MCP 指令 [MCP:server_id|tool|json] / [MCP:tool|json]。
    返回 {result（已剥离协议指令）, tools_used, mcp_calls, tool_logs}。

    轮次上限 _MAX_TOOL_ROUNDS + 累计 token 预算 _MAX_TOOL_TOKEN_BUDGET 双闸控成本。
    """
    import mcp_client

    def _est_tokens(text: str) -> int:
        """粗略 token 估算：中英混合 ~ 4 char/token，纯 CJK 约 1.5 char/token。"""
        if not text:
            return 0
        import re as _re

        cjk = len(_re.findall(r"[\u4e00-\u9fff]", text))
        ratio = cjk / max(len(text), 1)
        token_per_char = 1 / (4 - 2.5 * ratio)
        return max(1, int(len(text) * token_per_char))

    llm = llm_call if llm_call is not None else call_llm_async
    mcp_call = mcp_executor if mcp_executor is not None else mcp_client.mcp_call_tool
    mcp_by_id = {s.get("id"): s for s in (mcp_servers or [])}
    mcp_ids = set(mcp_by_id)
    tools_used: list[str] = []
    mcp_calls: list[str] = []
    tool_logs: list[str] = []
    token_budget = _MAX_TOOL_TOKEN_BUDGET

    # ── 双模式：function calling 或文本协议 ──
    tool_schemas = _build_tool_schemas(runnable_tools) if runnable_tools else []
    use_fc = bool(tool_schemas) and llm_call is None  # 仅生产模式启用 FC

    base_messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    first_messages: list[dict] = list(conversation_messages) if conversation_messages else list(base_messages)
    conv_messages: list[dict] = list(first_messages)  # 可累积的对话上下文

    if conversation_messages:
        token_spent = sum(_est_tokens(str(m.get("content") or "")) for m in conversation_messages)
    else:
        token_spent = _est_tokens(system) + _est_tokens(prompt)

    # 文本协议层的 LLM 附加 kwarg：agent 级模型选择仅在配置时注入（保持旧版 fake llm_call 签名兼容）
    text_llm_kwargs = {"model": model} if model else {}

    # 首次调用
    tool_calls: list | None = None
    if use_fc:
        from common.llm import call_llm_with_tools_async

        resp = await call_llm_with_tools_async(
            "", "", tool_schemas, max_tokens=max_tokens, model=model,
            fallback_models=fallback_models, messages=conv_messages,
        )
        text = resp["content"]
        tool_calls = resp["tool_calls"]
    else:
        if conversation_messages:
            text = await llm("", "", max_tokens=max_tokens, messages=first_messages, **text_llm_kwargs)
        else:
            text = await llm(system, prompt, max_tokens=max_tokens, **text_llm_kwargs)
    token_spent += _est_tokens(text)

    for _round_idx in range(_MAX_TOOL_ROUNDS):
        # 双模式指令解析
        if tool_calls:
            # function calling 模式：从 tool_calls 提取 (name, args)
            directives = [(tc["name"], _parse_tool_args(tc["arguments"])) for tc in tool_calls if tc["name"] in runnable_tools]
        else:
            # 文本协议模式：解析 [TOOL:name|input]
            directives = parse_tool_directives(text, runnable_tools)
        mcp_directives = parse_mcp_directives(text, mcp_ids, mcp_tools)
        if not directives and not mcp_directives:
            break

        # 执行工具
        exec_results: list[str] = []
        tool_result_msgs: list[dict] = []  # FC 模式的 tool 结果消息
        round_tokens = 0
        for name, arg in directives:
            tools_used.append(name)
            if on_tool_use is not None:
                await on_tool_use("tool", name, str(arg)[:200])
            out = await execute_tool_async(name, arg, user_id)
            exec_results.append(f"[工具 {name} 执行结果]\n{out}")
            tool_logs.append(f"{name}: {out[:300]}")
            round_tokens += _est_tokens(out)
            if tool_calls:
                tc_id = next((tc["id"] for tc in tool_calls if tc["name"] == name), "")
                tool_result_msgs.append({"role": "tool", "tool_call_id": tc_id, "content": out[:_MAX_TOOL_RESULT]})
        for sid, mtool, args in mcp_directives:
            mcp_calls.append(f"{sid}:{mtool}")
            if on_tool_use is not None:
                await on_tool_use("mcp", f"MCP:{mtool}", json.dumps(args, ensure_ascii=False)[:200])
            srv = mcp_by_id.get(sid) or {}
            out = await mcp_call(srv, mtool, args)
            exec_results.append(f"[MCP {mtool} 执行结果]\n{out}")
            tool_logs.append(f"MCP {mtool}: {out[:300]}")
            round_tokens += _est_tokens(out)
        token_spent += round_tokens
        if token_spent > token_budget:
            logger.info(f"agent tool loop stop: token budget {token_spent}>{token_budget}")
            break

        # 后续调用
        if use_fc and tool_calls:
            # FC 模式：assistant + tool results → 再调用
            assistant_msg = {
                "role": "assistant",
                "content": text,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in tool_calls
                ],
            }
            conv_messages = conv_messages + [assistant_msg] + tool_result_msgs
            if exec_results:
                conv_messages.append(
                    {"role": "user", "content": "\n\n".join(exec_results[len(tool_result_msgs):]) + "\n\n请基于以上工具执行结果，直接给出最终答案。"}
                )
            resp = await call_llm_with_tools_async(
                "", "", tool_schemas, max_tokens=max_tokens, model=model,
                fallback_models=fallback_models, messages=conv_messages,
            )
            text = resp["content"]
            tool_calls = resp["tool_calls"]
        else:
            # 文本协议模式（或 FC 降级后）
            follow_up = (
                f"{prompt}\n\n" + "\n\n".join(exec_results)
                + "\n\n请基于以上工具执行结果，直接给出最终答案（不要再输出 [TOOL:] / [MCP:] 指令）。"
            )
            if conversation_messages:
                follow_msgs = first_messages + [{"role": "assistant", "content": text}, {"role": "user", "content": follow_up}]
                text = await llm("", "", max_tokens=max_tokens, messages=follow_msgs, **text_llm_kwargs)
            else:
                text = await llm(system, follow_up, max_tokens=max_tokens, **text_llm_kwargs)
            tool_calls = None
        token_spent += _est_tokens(text)
        if token_spent > token_budget:
            logger.info(f"agent tool loop stop post-call: {token_spent}>{token_budget}")
            break
    return {
        "result": strip_tool_directives(text),
        "tools_used": tools_used,
        "mcp_calls": mcp_calls,
        "tool_logs": tool_logs,
    }


# 工具执行降级标记（结果文本由本模块控制，前缀匹配稳定）
_TOOL_DEGRADED_MARKERS = (
    "代码执行失败", "执行异常", "执行失败", "不存在或未接入",
)


async def execute_tool_async(tool_id: str, tool_input: str, user_id: str = "default") -> str:
    """真实执行工具，返回给 LLM 回喂的结果文本。失败返回降级说明而非抛异常。

    包一层做可靠性指标记录（kind=tool，ok/degraded），实现与监控解耦。
    """
    import time

    import common.metrics as metrics

    t0 = time.time()
    out = await _execute_tool_impl(tool_id, tool_input, user_id)
    degraded = any(m in out for m in _TOOL_DEGRADED_MARKERS)
    metrics.record("tool", "degraded" if degraded else "ok", (time.time() - t0) * 1000, detail=f"tool={tool_id}")
    return out


async def _execute_tool_impl(tool_id: str, tool_input: str, user_id: str = "default") -> str:
    """工具执行本体（原 execute_tool_async 实现）。"""
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
