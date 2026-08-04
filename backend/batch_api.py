"""批量处理引擎 — 多文件一次性处理。

- POST /api/batch/translate   批量翻译
- POST /api/batch/doc-summary 批量文档摘要
- POST /api/batch/process     通用批量处理（文件→LLM）
"""

import json
import logging
import os
import tempfile
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["批量处理"])

# ── System Prompts ─────────────────────────────────────────

BATCH_TRANSLATE_SYSTEM = """你是一个专业翻译。将以下文本翻译为目标语言。只输出译文，不要解释。"""

BATCH_SUMMARY_SYSTEM = """你是一个文档摘要专家。对以下文档内容进行摘要（100-150字），提取3-5个关键点。输出JSON：
{"title": "标题", "summary": "摘要", "key_points": ["点1","点2","点3"]}
只输出JSON。"""

# ── 模型 ──────────────────────────────────────────────────

class BatchTextRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=20, description="待处理文本列表")
    target_lang: str = Field("en", description="目标语言")
    source_lang: str = Field("auto", description="源语言")


class BatchProcessRequest(BaseModel):
    task: str = Field(..., description="批量处理任务描述")


# ── 数据库初始化 ──────────────────────────────────────────

def init_db():
    with get_db_context() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS batch_jobs (
                id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                file_count INTEGER,
                results TEXT,
                status TEXT DEFAULT 'running',
                created_at TEXT NOT NULL
            )
        """)


init_db()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "batch")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── 文本提取辅助 ──────────────────────────────────────────

def extract_text(filepath: str, filename: str) -> str:
    """提取文件文本。"""
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext in ('.txt', '.md', '.csv'):
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()[:10000]
        if ext == '.pdf':
            try:
                import PyPDF2
                with open(filepath, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    return "\n".join(p.extract_text() or "" for p in reader.pages[:10])[:10000]
            except Exception:
                return "[PDF提取失败]"
        if ext in ('.docx', '.doc'):
            try:
                import docx
                doc = docx.Document(filepath)
                return "\n".join(p.text for p in doc.paragraphs)[:10000]
            except Exception:
                return "[DOCX提取失败]"
    except Exception:
        return "[文件读取失败]"
    return f"[不支持格式: {ext}]"


# ── API ──────────────────────────────────────────────────

@router.post("/translate")
async def batch_translate(req: BatchTextRequest, current_user: dict = require_auth()):
    """批量翻译文本。"""
    start = datetime.now()
    results = []

    for i, text in enumerate(req.texts):
        if not text.strip():
            results.append({"index": i, "original": text, "translated": "", "error": "文本为空"})
            continue
        try:
            user_prompt = f"将以下{req.source_lang}文本翻译为{req.target_lang}：\n\n{text[:2000]}"
            raw = call_llm(BATCH_TRANSLATE_SYSTEM, user_prompt, max_tokens=500, temperature=0.3, timeout=30)
            results.append({"index": i, "original": text[:200], "translated": raw.strip()})
        except Exception as e:
            results.append({"index": i, "original": text[:200], "translated": "", "error": str(e)})

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    total_chars = sum(len(t) for t in req.texts)
    log_usage("batch_translate", total_chars, len(json.dumps(results)), elapsed)

    return {
        "task": "translate",
        "count": len(req.texts),
        "success": sum(1 for r in results if not r.get("error")),
        "results": results,
    }


@router.post("/doc-summary")
async def batch_doc_summary(files: list[UploadFile] = File(...), current_user: dict = require_auth()):
    """批量文档上传并生成摘要。"""
    start = datetime.now()
    results = []
    bid = f"batch_{int(datetime.now().timestamp()*1000)}"

    for file in files:
        if not file.filename:
            continue
        try:
            content = await file.read()
            ext = os.path.splitext(file.filename)[1].lower()
            tmp_path = os.path.join(UPLOAD_DIR, f"{bid}_{file.filename}")
            with open(tmp_path, "wb") as f:
                f.write(content)

            text = extract_text(tmp_path, file.filename)
            if text and not text.startswith("["):
                raw = call_llm(BATCH_SUMMARY_SYSTEM, f"文档：{file.filename}\n\n内容：{text[:5000]}",
                               max_tokens=500, temperature=0.3, timeout=45)
                raw = raw.strip()
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                summary_data = json.loads(raw)
            else:
                summary_data = {"title": file.filename, "summary": text or "提取失败", "key_points": []}

            results.append({
                "filename": file.filename,
                "size": len(content),
                "title": summary_data.get("title", file.filename),
                "summary": summary_data.get("summary", ""),
                "key_points": summary_data.get("key_points", []),
            })

            try:
                os.remove(tmp_path)
            except OSError:
                pass
        except Exception as e:
            results.append({"filename": file.filename, "title": file.filename, "summary": "", "key_points": [], "error": str(e)})

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("batch_doc_summary", len(files), len(json.dumps(results)), elapsed)

    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO batch_jobs (id, task_type, file_count, results, status, created_at) VALUES (?,?,?,?,?,?)",
            (bid, "doc_summary", len(files), json.dumps(results, ensure_ascii=False), "done", datetime.now().isoformat()),
        )

    return {
        "job_id": bid,
        "task": "doc_summary",
        "file_count": len(files),
        "results": results,
    }


@router.post("/process")
async def batch_process(files: list[UploadFile] = File(...), task: str = Form("summarize"),
                        current_user: dict = require_auth()):
    """通用批量处理：上传多个文件 → 统一LLM处理。task: summarize/translate/keywords/sentiment"""
    start = datetime.now()
    results = []
    bid = f"batch_{int(datetime.now().timestamp()*1000)}"

    task_prompts = {
        "summarize": "请用中文摘要以下文档（100字以内）：",
        "keywords": "请提取以下文档的5-8个核心关键词，用逗号分隔。只输出关键词。",
        "sentiment": "请分析以下文本的情感倾向，只输出：正面/负面/中性，并附一句话原因。",
        "translate_en": "将以下文本翻译为英文，只输出译文：",
    }

    task_prompt = task_prompts.get(task, task_prompts["summarize"])

    for file in files:
        if not file.filename:
            continue
        try:
            content = await file.read()
            tmp_path = os.path.join(UPLOAD_DIR, f"{bid}_{file.filename}")
            with open(tmp_path, "wb") as f:
                f.write(content)

            text = extract_text(tmp_path, file.filename)
            if text and not text.startswith("["):
                raw = call_llm(task_prompt, f"文件：{file.filename}\n\n{text[:4000]}",
                               max_tokens=400, temperature=0.3, timeout=30)
                result_text = raw.strip()
            else:
                result_text = text or "处理失败"

            results.append({"filename": file.filename, "result": result_text})
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        except Exception as e:
            results.append({"filename": file.filename, "result": "", "error": str(e)})

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("batch_process", len(files), len(json.dumps(results)), elapsed)

    return {
        "job_id": bid,
        "task": task,
        "file_count": len(files),
        "results": results,
    }


@router.get("/jobs")
async def list_jobs(current_user: dict = require_auth()):
    """获取批量任务历史。"""
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, task_type, file_count, status, created_at FROM batch_jobs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return [{"id": r[0], "task_type": r[1], "file_count": r[2], "status": r[3], "created_at": r[4]} for r in rows]
