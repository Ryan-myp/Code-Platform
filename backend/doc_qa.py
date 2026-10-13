"""AI文档智能问答 — 上传文档 → 基于内容的问答对话。

- POST /api/doc-qa/upload   上传文档（PDF/Word/TXT）→ 提取文本
- POST /api/doc-qa/ask      基于文档内容提问
- GET  /api/doc-qa/records  历史文档记录
- DELETE /api/doc-qa/records/{id}
"""

import json
import logging
import os
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.helpers import _notify_progress
from common.llm import call_llm_async, log_usage, parse_llm_json
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/doc-qa", tags=["文档问答"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "docs")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_DOC_CHARS = 15000  # 文档最大字符数（用于LLM上下文窗口）

# ── System Prompts ─────────────────────────────────────────

DOC_QA_SYSTEM = """你是资深文档分析师，擅长从文档中精准提取信息并回答专业问题。

核心能力：
1. 精准定位：快速在检索片段中找到与问题最相关的段落和关键句
2. 结构化回答：用简洁清晰的结构呈现答案，先结论后细节
3. 引用溯源：每个关键结论后用 [N] 标注对应检索片段编号
4. 诚实边界：检索片段无相关信息时明确告知，不编造不推测

回答规范：
- 合同/法律类：重点关注风险条款、违约责任、关键期限
- 技术文档：提取架构设计、API规范、配置参数
- 研报/论文：抓取核心观点、数据来源、方法论
- 通用文档：总结要点 + 关键摘录

引用溯源规则（必须遵守）：
- 每个关键结论或数据后标注引用标记 [N]，N 对应检索片段编号
- 只引用检索片段中出现的内容，不得编造编号
- 无对应片段的信息不得标注引用
- 多文档联合问答时，优先交叉印证各文档信息

检索片段：
{context}

请基于以上检索片段回答用户的问题。回答要求：先给结论（1-2句），再展开细节，引用处标注 [N]。"""

DOC_EXTRACT_SYSTEM = """你是文档结构化学者，擅长从文本中提炼关键信息并构建知识图谱。

提取原则：
1. 标题：识别文档的核心主题（如有明确标题则使用原标题）
2. 摘要：100-150字覆盖文档的核心内容和价值
3. 关键点：提取5-8个最重要的信息点，每个15字以内
4. 实体识别：准确提取人名、组织、日期、金额、百分比等结构化数据
5. 建议问题：生成5-7个对该文档用户最可能提出的问题

输出JSON格式：
{
  "title": "文档标题",
  "type": "报告|合同|论文|手册|文章|技术文档|法律文件|其他",
  "summary": "文档摘要（100-150字，包含文档目的、核心内容、关键结论）",
  "key_points": ["关键点1", "关键点2", "关键点3", "关键点4", "关键点5", "关键点6"],
  "word_count": 字数,
  "suggested_questions": ["问题1", "问题2", "问题3", "问题4", "问题5", "问题6"],
  "entities": {
    "人物": ["张三"],
    "组织": ["公司A"],
    "日期": ["2024-01-01"],
    "金额": ["100万元"],
    "百分比": ["25%"],
    "专有名词": ["术语A"]
  },
  "structure": {
    "sections": ["章节1标题", "章节2标题"],
    "has_tables": true,
    "has_charts": false
  },
  "reading_time_minutes": 5
}

只输出JSON，不要其他内容。"""

# ── 模型 ──────────────────────────────────────────────────

class AskRequest(BaseModel):
    doc_id: str = Field("", description="文档ID（兼容单文档问答）")
    doc_ids: list[str] = Field(default_factory=list, description="多文档联合问答（最多5篇）")
    question: str = Field(..., min_length=1, max_length=500)
    history: list[dict] = Field(default_factory=list, description="对话历史")

# ── 数据库初始化 ──────────────────────────────────────────

def init_db():
    with get_db_context() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS doc_qa_records (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                file_size INTEGER,
                text_content TEXT,
                text_length INTEGER,
                summary TEXT,
                status TEXT DEFAULT 'pending',
                user_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        # 存量库补 user_id 列（幂等，并发竞态忽略）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(doc_qa_records)").fetchall()]
        if "user_id" not in cols:
            try:
                conn.execute("ALTER TABLE doc_qa_records ADD COLUMN user_id TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()

init_db()

# ── 文本提取 ──────────────────────────────────────────────
# v20 重构：委托 kb_rag 统一 RAG 管线，doc_qa.py 作为壳保留旧名导出（test_docqa_tools.py 依赖）

def extract_text(filepath: str, filename: str) -> str:
    """委托 kb_rag.extract_text；doc_qa 侧保留原名导出以兼容旧调用方。"""
    import kb_rag

    return kb_rag.extract_text(filepath, filename)

def _chunk_text(text: str, chunk_size: int = 500) -> list[dict]:
    """委托 kb_rag.chunk_text。"""
    import kb_rag

    return kb_rag.chunk_text(text, chunk_size)

def _retrieve_chunks(question: str, chunks: list[dict], top_k: int = 4) -> list[dict]:
    """委托 kb_rag.retrieve_chunks。"""
    import kb_rag

    return kb_rag.retrieve_chunks(question, chunks, top_k)

def _extract_citations(answer: str, retrieved: list[dict]) -> list[dict]:
    """委托 kb_rag.extract_citations。"""
    import kb_rag

    return kb_rag.extract_citations(answer, retrieved)

# ── API ──────────────────────────────────────────────────

@router.post("/upload")
async def upload_doc(
    file: UploadFile = File(...), background: BackgroundTasks = BackgroundTasks(), current_user: dict = require_auth()
):
    """上传文档，自动提取文本并生成摘要。"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")

    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {".txt", ".pdf", ".docx", ".doc", ".md", ".csv"}
    if ext not in allowed:
        raise HTTPException(400, "不支持的文件格式")

    did = f"doc_{int(datetime.now().timestamp() * 1000)}"
    save_path = os.path.join(UPLOAD_DIR, f"{did}{ext}")

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # 提取文本
    text = extract_text(save_path, file.filename)

    # AI 摘要：后台异步生成，上传立即返回（LLM 慢时不再阻塞上传 60s+）
    placeholder = {"title": file.filename, "type": "文档", "summary": "摘要生成中…", "key_points": []}
    if text and not text.startswith("["):
        background.add_task(_summarize_doc_async, did, text[:3000], file.filename)

    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO doc_qa_records (id, filename, filepath, file_size, text_content, text_length, summary, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                did,
                file.filename,
                save_path,
                len(content),
                text,
                len(text),
                json.dumps(placeholder, ensure_ascii=False),
                "ready",
                str(current_user.get("user_id", "")),
                datetime.now().isoformat(),
            ),
        )

    return {
        "doc_id": did,
        "filename": file.filename,
        "file_size": len(content),
        "text_length": len(text),
        "text_preview": text[:300],
        "summary": placeholder,
        "message": f"文档上传成功，已提取 {len(text)} 字符，摘要生成中…",
    }

async def _summarize_doc_async(did: str, text: str, filename: str) -> None:
    """后台生成文档摘要并回写记录（失败降级占位，不影响主流程）。"""
    summary = {"title": filename, "type": "文档", "summary": "自动摘要生成失败", "key_points": []}
    try:
        raw = await call_llm_async(
            DOC_EXTRACT_SYSTEM,
            f"文档文本（前3000字）：\n{text[:3000]}",
            max_tokens=1000,
            temperature=0.3,
            timeout=120,
        )
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        summary = parse_llm_json(raw)
    except Exception as e:
        logger.warning(f"doc summary failed: {e}")
    try:
        with get_db_context() as conn:
            conn.execute(
                "UPDATE doc_qa_records SET summary=? WHERE id=?", (json.dumps(summary, ensure_ascii=False), did)
            )
    except Exception as e:
        logger.warning(f"doc summary persist failed: {e}")

# ── 异步任务：文档问答（进度/自动重试/并发控制）──

async def _docqa_ask_worker(payload: dict, progress: Callable | None = None) -> dict:
    """文档问答 worker：RAG 上下文 → LLM 回答。"""

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    _report(10, "定位文档")
    doc_ids = payload.get("doc_ids") or []
    if not doc_ids and payload.get("doc_id"):
        doc_ids = [payload["doc_id"]]
    if not doc_ids:
        raise HTTPException(400, "请先选择文档")
    if len(doc_ids) > 5:
        raise HTTPException(400, "一次最多联合问答 5 篇文档")
    with get_db_context() as conn:
        docs = []
        for did in doc_ids:
            row = conn.execute("SELECT * FROM doc_qa_records WHERE id=?", (did,)).fetchone()
            if not row:
                raise HTTPException(404, "操作失败，请稍后重试")
            text = row[4] or ""
            if text and not text.startswith("["):
                docs.append({"doc_id": row[0], "doc_name": row[1], "text": text})
    if not docs:
        raise HTTPException(400, "所选文档文本为空或提取失败，无法问答")

    _report(35, "检索相关片段")
    chunks: list[dict] = []
    for doc in docs:
        for c in _chunk_text(doc["text"]):
            c["doc_id"] = doc["doc_id"]
            c["doc_name"] = doc["doc_name"]
            chunks.append(c)
    question = payload.get("question", "")
    retrieved = _retrieve_chunks(question, chunks, top_k=4)
    context_lines = [f"[{i}]（来源：{c['doc_name']}）\n{c['text']}" for i, c in enumerate(retrieved, 1)]
    system_prompt = DOC_QA_SYSTEM.replace("{context}", "\n\n".join(context_lines))
    history_text = ""
    for h in (payload.get("history") or [])[-6:]:
        role = "用户" if h.get("role") == "user" else "助手"
        history_text += f"{role}：{h.get('content', '')}\n"
    user_prompt = f"{history_text}用户：{question}"

    _report(50, "AI 回答中")
    # 注意：必须 (await …) 整体括起再 strip，否则 .strip() 会作用在协程对象上；
    # timeout=120：上游 LLM 慢时（实测可超 60s）避免误判失败
    answer = (await call_llm_async(system_prompt, user_prompt, max_tokens=800, temperature=0.4, timeout=120)).strip()
    _report(90, "记录用量")
    log_usage("doc_qa", len(user_prompt), len(answer), 0)
    _report(100, "完成")
    return {
        "doc_id": doc_ids[0],
        "doc_ids": doc_ids,
        "sources": [{"doc_id": d["doc_id"], "doc_name": d["doc_name"]} for d in docs],
        "question": question,
        "answer": answer,
        "citations": _extract_citations(answer, retrieved),
        "source": "、".join(d["doc_name"] for d in docs),
        "confidence": "基于文档内容",
    }

async def _docqa_ask_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装文档问答，回报进度。"""
    return await _docqa_ask_worker(payload, progress=update)

@router.post("/ask")
async def ask_document(req: AskRequest, current_user: dict = require_auth()):
    """基于文档内容智能问答（异步任务：进度跟踪 / 失败自动重试 / 并发控制）"""
    payload = {
        **req.model_dump(),
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    task = create_task(
        "docqa_ask",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"]}

@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    """获取历史文档记录（用户隔离：admin 全量，普通用户仅自己的）。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    with get_db_context() as conn:
        if role in ("admin", "super_admin"):
            rows = conn.execute(
                "SELECT id, filename, file_size, text_length, status, created_at FROM doc_qa_records ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, filename, file_size, text_length, status, created_at FROM doc_qa_records WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (uid,),
            ).fetchall()

    return [
        {"id": r[0], "filename": r[1], "file_size": r[2], "text_length": r[3], "status": r[4], "created_at": r[5]}
        for r in rows
    ]

def _can_access(conn, record_id: str, current_user: dict) -> bool:
    """记录归属校验：admin 可访问全部；普通用户仅自己的记录。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    if role in ("admin", "super_admin"):
        return True
    row = conn.execute("SELECT user_id FROM doc_qa_records WHERE id=?", (record_id,)).fetchone()
    return bool(row) and str(row[0] or "") == uid

@router.get("/records/{record_id}")
async def get_record(record_id: str, current_user: dict = require_auth()):
    """获取单个文档详情（含摘要，归属校验）。"""
    with get_db_context() as conn:
        if not _can_access(conn, record_id, current_user):
            raise HTTPException(404, "记录不存在")
        row = conn.execute("SELECT * FROM doc_qa_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")

    return {
        "id": row[0],
        "filename": row[1],
        "file_size": row[3],
        "text_length": row[5],
        "text_preview": (row[4] or "")[:500],
        "summary": json.loads(row[6]) if row[6] else {},
        "status": row[7],
        "created_at": row[8],
    }

@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    """删除文档记录（归属校验）。"""
    with get_db_context() as conn:
        if not _can_access(conn, record_id, current_user):
            raise HTTPException(404, "记录不存在")
        row = conn.execute("SELECT filepath FROM doc_qa_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")
        try:
            os.remove(row[0])
        except OSError:
            pass
        conn.execute("DELETE FROM doc_qa_records WHERE id=?", (record_id,))
    return {"message": "已删除"}

# ── 异步任务处理器注册 ──
register_handler("docqa_ask", _docqa_ask_handler, user_limit=1, max_attempts=1)
