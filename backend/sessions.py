#!/usr/bin/env python3
"""会话管理 - 支持 Agent 对话历史"""

import json
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from common.db import get_db

router = APIRouter(tags=["会话"])


def create_session(agent_id: str, title: str = "") -> str:
    """创建新会话"""
    session_id = f"session_{int(time.time() * 1000)}"
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (id, agent_id, title) VALUES (?, ?, ?)",
        (session_id, agent_id, title or f"会话 {datetime.now().strftime('%H:%M')}"),
    )
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id: str) -> dict:
    """获取会话"""
    conn = get_db()
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_sessions(agent_id: str = None) -> list:
    """列出会话"""
    conn = get_db()
    if agent_id:
        rows = conn.execute("SELECT * FROM sessions WHERE agent_id=? ORDER BY updated_at DESC", (agent_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM sessions ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_message(session_id: str, role: str, content: str, metadata: dict = None) -> int:
    """添加消息。返回自增 id。"""
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO messages (session_id, role, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, json.dumps(metadata or {}), datetime.now().isoformat()),
    )
    conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (datetime.now().isoformat(), session_id))
    conn.commit()
    msg_id = cur.lastrowid
    conn.close()
    return msg_id


def get_messages(session_id: str, limit: int = 50) -> list:
    """获取消息历史（limit 收敛到 1-500，防脏参数拖垮查询）。"""
    try:
        limit = int(limit) if limit is not None else 50
        limit = max(1, min(limit, 500))
    except (TypeError, ValueError):
        limit = 50
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM messages WHERE session_id=? ORDER BY created_at DESC LIMIT ?", (session_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows][::-1]


def delete_session(session_id: str) -> bool:
    """删除会话"""
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
    conn.commit()
    conn.close()
    return True


# 记忆治理上限：防无界增长（auto 最弱先裁；session 总量硬上限）
_MAX_SESSION_MEMORIES = 100
_MAX_AUTO_MEMORIES = 30
# 单次裁剪丢弃 ≥ 该条数时，合并为一条 lossy 摘要记忆（避免静默丢信息；纯规则零 API 成本）
_PRUNE_SUMMARIZE_MIN = 5
_SUMMARY_KEEP = 20  # 摘要最多保留最近多少条要点
SUMMARY_PREFIX = "记忆摘要（自动压缩旧条目）："


def _prune_session_memories(conn, session_id: str, agent_id: str = "") -> None:
    """裁剪会话记忆到上限：先裁最老的 auto（最弱），再裁最老非 long，总量超限时最后才裁 long。

    单次丢弃 ≥ _PRUNE_SUMMARIZE_MIN 条时，把被裁内容合并为一条 lossy 摘要
    （long 型；已存在则原地更新，不重复插入）——不丢关键信息，且纯规则零 LLM 成本。
    调用方持有 conn 并负责 commit。"""
    pruned: list[str] = []
    rows = conn.execute(
        "SELECT id, content FROM memories WHERE session_id=? AND memory_type='auto' ORDER BY created_at ASC, id ASC",
        (session_id,),
    ).fetchall()
    excess = len(rows) - _MAX_AUTO_MEMORIES
    if excess > 0:
        victims = rows[:excess]
        pruned.extend(r["content"] for r in victims)
        conn.executemany("DELETE FROM memories WHERE id=?", [(r["id"],) for r in victims])
    total = conn.execute("SELECT COUNT(*) AS c FROM memories WHERE session_id=?", (session_id,)).fetchone()["c"]
    over = total - _MAX_SESSION_MEMORIES
    while over > 0:
        victim = conn.execute(
            "SELECT id, content FROM memories WHERE session_id=? AND memory_type!='long' ORDER BY created_at ASC LIMIT 1",
            (session_id,),
        ).fetchone()
        if not victim:
            victim = conn.execute(
                "SELECT id, content FROM memories WHERE session_id=? ORDER BY created_at ASC LIMIT 1", (session_id,)
            ).fetchone()
        if not victim:
            break
        pruned.append(victim["content"])
        conn.execute("DELETE FROM memories WHERE id=?", (victim["id"],))
        over -= 1
    if len(pruned) >= _PRUNE_SUMMARIZE_MIN:
        _upsert_memory_summary(conn, session_id, agent_id, pruned)


def _upsert_memory_summary(conn, session_id: str, agent_id: str, pruned: list[str]) -> None:
    """被裁条目 → 一条 lossy 摘要（最近 _SUMMARY_KEEP 条，每条截 60 字）；存在则更新不重插。"""
    keep = [p[:60] for p in pruned[-_SUMMARY_KEEP:] if p]
    if not keep:
        return
    body = "\n".join(f"- {c}" for c in keep)
    text = f"{SUMMARY_PREFIX}（{len(pruned)} 条，列最近 {len(keep)}）\n{body}"
    existing = conn.execute(
        "SELECT id FROM memories WHERE session_id=? AND content LIKE ? LIMIT 1",
        (session_id, SUMMARY_PREFIX + "%"),
    ).fetchone()
    if existing:
        conn.execute("UPDATE memories SET content=? WHERE id=?", (text, existing["id"]))
    else:
        conn.execute(
            "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, 'long', ?)",
            (f"mem_sum_{int(time.time() * 1000)}", session_id, agent_id, text),
        )


def _bigrams(text: str) -> set[str]:
    """CJK 双字 + ASCII 词（与 agent_runtime._mem_relevance 同口径，零依赖）。"""
    import re

    t = (text or "").lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", t))
    cjk = re.findall(r"[\u4e00-\u9fff]", t)
    words.update({"".join(p) for p in zip(cjk, cjk[1:], strict=False)})
    return words


def _near_dup_score(a: str, b: str) -> float:
    """包含系数 |A∩B|/min(|A|,|B|)：一条记忆的词块大部分出现在另一条里 → 视为近重。"""
    x, y = _bigrams(a), _bigrams(b)
    if not x or not y:
        return 0.0
    return len(x & y) / min(len(x), len(y))


def _is_near_duplicate(conn, session_id: str, content: str, threshold: float = 0.5) -> str | None:
    """语义去重：与同会话最近 50 条记忆比较，包含系数 ≥阈值 视为重复，返回已有 id。

    「我喜欢简洁风格」与「用户偏好简洁」这类措辞不同但语义相近的会被合并，
    避免记忆表塞满近义条目（exact-string 去重的漏网）。冲突偏好（简洁 vs 详细）
    不在此例（词块重叠低）→ 两条都保留，交由 LLM 提取层去重。"""
    rows = conn.execute(
        "SELECT id, content FROM memories WHERE session_id=? AND content NOT LIKE ? "
        "ORDER BY created_at DESC LIMIT 50",
        (session_id, SUMMARY_PREFIX + "%"),
    ).fetchall()
    for r in rows:
        if _near_dup_score(content, r["content"]) >= threshold:
            return r["id"]
    return None


def add_memory(session_id: str, agent_id: str, content: str, memory_type: str = "short") -> str:
    """添加记忆（同 session 同内容去重；写入后自动治理裁剪到上限）。

    注：不做语义近重去重——用户/程序写入可能是模板化内容（「记忆 1/2/3」），
    误合并代价高于重复；语义去重只在 LLM 自动提取路径用（见 auto_extract_memory）。"""
    mem_id = f"mem_{int(time.time() * 1000)}"
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM memories WHERE session_id=? AND content=? LIMIT 1", (session_id, content)
    ).fetchone()
    if existing:
        conn.close()
        return existing["id"]
    conn.execute(
        "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, ?, ?)",
        (mem_id, session_id, agent_id, memory_type, content),
    )
    _prune_session_memories(conn, session_id, agent_id)
    conn.commit()
    conn.close()
    return mem_id


async def compress_memory_summary(session_id: str, agent_id: str) -> bool:
    """把规则 lossy 摘要升级为 LLM 语义压缩（v18 D，fire-and-forget 调用）。

    只对已有摘要记忆生效：LLM 把「最近 20 条各截 60 字」压成 ≤3 条真要点，原地更新。
    失败/无摘要 → 保持规则摘要（诚实降级，不影响主流程）。返回是否成功压缩。
    """
    import logging

    log = logging.getLogger(__name__)
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT id, content FROM memories WHERE session_id=? AND content LIKE ? LIMIT 1",
            (session_id, SUMMARY_PREFIX + "%"),
        ).fetchone()
        conn.close()
        if not row:
            return False
        from common.llm import call_llm_async

        system = ("你是记忆压缩器。把下面的旧记忆要点合并压缩为不超过 3 条最关键要点"
                   "（保留事实/偏好/决定，去掉细节与重复，每条一行以 - 开头）。只输出要点本身。")
        resp = await call_llm_async(system, row["content"][:1500], max_tokens=300, temperature=0.2)
        lines = [ln.strip().lstrip("-• ").strip() for ln in (resp or "").splitlines() if ln.strip()]
        lines = [ln for ln in lines if len(ln) > 3][:3]
        if not lines:
            return False  # 输出不可用 → 保持规则摘要
        new_text = f"{SUMMARY_PREFIX}（LLM 语义压缩）\n" + "\n".join(f"- {ln}" for ln in lines)
        conn = get_db()
        conn.execute("UPDATE memories SET content=? WHERE id=?", (new_text, row["id"]))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.warning(f"memory summary compress failed (keep rule summary): {e}")
        return False


def get_memories(session_id: str, agent_id: str = None) -> list:
    """获取记忆"""
    conn = get_db()
    if agent_id:
        rows = conn.execute(
            "SELECT * FROM memories WHERE session_id=? AND agent_id=? ORDER BY created_at DESC", (session_id, agent_id)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories WHERE session_id=? ORDER BY created_at DESC", (session_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def auto_extract_memory(session_id: str, agent_id: str, user_message: str, assistant_reply: str) -> int:
    """对话后自动提取记忆：LLM 判断是否有值得记住的内容并写入 memories 表。

    策略：将用户消息 + 助手回复交给 LLM，让它提取「用户偏好/关键决定/重要上下文」，
    返回 JSON {"memories": ["...", "..."]}。每条写入 memories 表，type=auto。
    失败静默（不影响主流程）。返回写入条数。
    """
    if not user_message or not assistant_reply:
        return 0
    try:
        from common.llm import call_llm_async

        system = (
            "你是记忆提取器。分析对话，提取值得长期记住的用户偏好、关键决定或重要上下文。"
            "如果没有值得记住的内容，返回空数组。只返回 JSON，不要其它内容。"
            '格式：{"memories": ["记忆1", "记忆2"]}'
        )
        prompt = f"用户说：{user_message[:800]}\n\n助手回复：{assistant_reply[:800]}"
        resp = await call_llm_async(system, prompt, max_tokens=300, temperature=0.2)
        import re

        m = re.search(r"\{.*\}", resp or "", re.S)
        if not m:
            return 0
        import json as _json

        data = _json.loads(m.group(0))
        memories = [str(item) for item in (data.get("memories") or []) if str(item).strip()][:5]
        if not memories:
            return 0
        conn = get_db()
        written = 0
        for content in memories:
            c = str(content)[:500]
            dup = conn.execute(
                "SELECT id FROM memories WHERE session_id=? AND content=? LIMIT 1", (session_id, c)
            ).fetchone()
            if dup:  # 已有相同记忆 → 不重复写
                continue
            if _is_near_duplicate(conn, session_id, c):  # 语义近重 → 不重复写（v18 D）
                continue
            mem_id = f"mem_{int(time.time() * 1000)}_{c[:4]}"
            conn.execute(
                "INSERT INTO memories (id, session_id, agent_id, memory_type, content) VALUES (?, ?, ?, ?, ?)",
                (mem_id, session_id, agent_id or "", "auto", c),
            )
            written += 1
        if written:
            _prune_session_memories(conn, session_id, agent_id or "")
        conn.commit()
        conn.close()
        return written
    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(f"auto_extract_memory failed: {e}")
        return 0


# ══════════════════════════════════════════════════════════════
# FastAPI 路由
# ══════════════════════════════════════════════════════════════


@router.get("/api/sessions")
async def api_list_sessions(agent_id: str = None):
    """获取会话列表"""
    return list_sessions(agent_id)


@router.post("/api/sessions")
async def api_create_session(req: dict):
    """创建会话"""
    agent_id = req.get("agent_id", "")
    if not agent_id:
        raise HTTPException(400, "agent_id 不能为空")
    session_id = create_session(agent_id, req.get("title", ""))
    return {"session_id": session_id, "agent_id": agent_id}


@router.get("/api/sessions/{session_id}/messages")
async def api_get_messages(session_id: str, limit: int = 50):
    """获取会话消息"""
    return get_messages(session_id, limit)


@router.post("/api/sessions/{session_id}/messages")
async def api_add_message(session_id: str, req: dict):
    """添加消息"""
    content = req.get("content", "")
    if not content:
        raise HTTPException(400, "内容不能为空")
    msg_id = add_message(session_id, req.get("role", "user"), content, req.get("metadata"))
    return {"id": msg_id, "session_id": session_id}


@router.delete("/api/sessions/{session_id}")
async def api_delete_session(session_id: str):
    """删除会话"""
    delete_session(session_id)
    return {"success": True}
