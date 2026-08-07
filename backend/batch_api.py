"""批量处理引擎 — 多文件一次性处理（异步任务：进度跟踪 / 失败自动重试 / 并发控制）。

- POST /api/batch/translate   批量翻译
- POST /api/batch/doc-summary 批量文档摘要
- POST /api/batch/process     通用批量处理（文件→LLM）
- GET  /api/batch/jobs        处理记录（用户隔离）
"""

import json
import logging
import os
import uuid
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, File, Form, Query, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import _add_column_if_missing, get_db_context
from common.llm import call_llm, log_usage, parse_llm_json
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/batch", tags=["批量处理"])

# ── System Prompts ─────────────────────────────────────────

BATCH_TRANSLATE_SYSTEM = """你是一位拥有10年+经验的专业翻译，精通中英日韩等主流语言的互译，曾为跨国企业和国际会议提供翻译服务。

## 翻译方法论
1. **信达雅递进**：先保证准确（信），再追求流畅（达），最后考虑文采（雅）
2. **语境适配**：根据文本类型切换翻译风格
   - 商务/法律文档：严谨正式，术语精确，长句可拆分但逻辑不变
   - 技术文档：术语统一，直译为主，不添加修辞
   - 营销文案：意译优先，保留感染力和品牌调性，文化适配（如英文幽默可转换为中文网络梗）
   - 日常对话：口语化，保留语气和情绪
3. **文化桥接**：遇到文化特定概念时，优先找目标语言中的对等表达，其次加简短注释
4. **术语一致性**：同一原文术语全文统一译法，专有名词首次出现可标注原文

## 翻译原则
1. **忠实原文**：不增译、不漏译、不曲解原文意思
2. **语言地道**：目标语言表达自然流畅，读起来像母语者写的
3. **保持格式**：保留原文的段落结构、标点风格、强调标记
4. **专有名词**：人名、品牌名、地名保持原文不翻译
5. **数字精度**：数字、日期、货币单位准确转换格式（如10,000 ↔ 1万）

只输出译文，不要任何解释或注释。"""

BATCH_SUMMARY_SYSTEM = """你是一位资深信息架构师和文档摘要专家，拥有10年+大型企业知识管理经验，擅长从海量信息中提炼结构化知识。

## 摘要方法论
采用"金字塔摘要法"：
1. **核心结论**（第一句）：文档最重要的发现/结论/决策是什么
2. **支撑要点**（3-5句）：核心结论的关键论据和数据支撑
3. **行动/影响**（最后1句）：这个文档对读者意味着什么

## 摘要要求
1. **信息密度**：每句话都包含实质信息，删掉"本文介绍了"、"作者认为"等元描述
2. **逻辑顺序**：按重要性递减排列，而非按原文顺序
3. **关键点提取**：3-5个可执行/可验证的具体要点
   - 如果是方案文档 → 提炼决策点和资源需求
   - 如果是报告文档 → 提炼核心数据和趋势判断
   - 如果是会议纪要 → 提炼决议和待办事项
4. **立场识别**：准确判断文档的情感倾向和立场

## 输出规范
- title：精准概括，≤20字，不用"关于XX的文档"这类泛标题
- summary：100-150字，可独立传播的信息摘要
- key_points：每条≤30字，动词开头（如"决定采用微服务架构替代单体"）
- sentiment：positive（积极乐观）/ neutral（客观中立）/ negative（风险警示）
- category：精准分类（技术方案/商业报告/新闻稿/会议纪要/学术论文/产品文档/政策文件等）

严格按以下JSON格式输出（只输出JSON，不要其他文字）：
{
  "title": "标题（≤20字）",
  "summary": "摘要（100-150字）",
  "key_points": ["可执行的要点1", "要点2", "要点3"],
  "sentiment": "positive|neutral|negative",
  "category": "文档类型"
}"""

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
                user_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        # 历史表补 user_id（幂等迁移，并发安全）
        _add_column_if_missing(conn, "batch_jobs", "user_id", "TEXT")


init_db()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "batch")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── 文本提取辅助 ──────────────────────────────────────────


def extract_text(filepath: str, filename: str) -> str:
    """提取文件文本。"""
    ext = os.path.splitext(filename)[1].lower()
    try:
        if ext in (".txt", ".md", ".csv"):
            with open(filepath, encoding="utf-8") as f:
                return f.read()[:10000]
        if ext == ".pdf":
            try:
                import PyPDF2

                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    return "\n".join(p.extract_text() or "" for p in reader.pages[:10])[:10000]
            except Exception:
                return "[PDF提取失败]"
        if ext in (".docx", ".doc"):
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
async def batch_translate(req: BatchTextRequest, sync: bool = Query(False), current_user: dict = require_auth()):
    """批量翻译文本（异步任务：逐条处理 + 进度上报；sync=1 直接执行兼容旧调用）。"""
    payload = {
        **req.model_dump(),
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    if sync is True:
        return await _batch_translate_worker(payload)
    task = create_task(
        "batch_translate",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"]}


@router.post("/doc-summary")
async def batch_doc_summary(
    files: list[UploadFile] = File(...), sync: bool = Query(False), current_user: dict = require_auth()
):
    """批量文档上传并生成摘要（异步任务；文件落盘后由 worker 逐份处理）。"""
    saved = []
    for file in files:
        if not file.filename:
            continue
        content = await file.read()
        fid = f"{uuid.uuid4().hex[:10]}_{file.filename}"
        tmp_path = os.path.join(UPLOAD_DIR, fid)
        with open(tmp_path, "wb") as f:
            f.write(content)
        saved.append({"path": tmp_path, "filename": file.filename, "size": len(content)})

    if not saved:
        return {"ok": False, "error": "未收到有效文件"}

    payload = {
        "files": saved,
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    if sync is True:
        return await _batch_doc_summary_worker(payload)
    task = create_task(
        "batch_doc_summary",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"]}


@router.post("/process")
async def batch_process(
    files: list[UploadFile] = File(...),
    task: str = Form("summarize"),
    sync: bool = Query(False),
    current_user: dict = require_auth(),
):
    """通用批量处理（异步任务）：上传多个文件 → 统一LLM处理。task: summarize/translate/keywords/sentiment"""
    saved = []
    for file in files:
        if not file.filename:
            continue
        content = await file.read()
        fid = f"{uuid.uuid4().hex[:10]}_{file.filename}"
        tmp_path = os.path.join(UPLOAD_DIR, fid)
        with open(tmp_path, "wb") as f:
            f.write(content)
        saved.append({"path": tmp_path, "filename": file.filename, "size": len(content)})

    if not saved:
        return {"ok": False, "error": "未收到有效文件"}

    payload = {
        "task": task,
        "files": saved,
        "user_id": str(current_user.get("user_id", "")),
        "username": current_user.get("username", ""),
    }
    if sync is True:
        return await _batch_process_worker(payload)
    task_obj = create_task(
        "batch_process",
        payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task_obj["id"], "status": task_obj["status"]}


# ── 异步任务：批量处理 worker（逐条/逐文件处理 + 进度上报）──


async def _batch_translate_worker(payload: dict, progress: Callable | None = None) -> dict:
    """批量翻译 worker：逐条调用 LLM，按条上报进度。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            progress(pct, stage)

    texts = payload.get("texts", [])
    target_lang = payload.get("target_lang", "en")
    source_lang = payload.get("source_lang", "auto")
    user_id = payload.get("user_id", "")
    start = datetime.now()
    results = []
    total = len(texts)

    for i, text in enumerate(texts):
        _report(round((i / total) * 90, 1) if total else 10, f"翻译第 {i + 1}/{total} 条")
        if not text.strip():
            results.append({"index": i, "original": text, "translated": "", "error": "文本为空"})
            continue
        try:
            user_prompt = f"将以下{source_lang}文本翻译为{target_lang}：\n\n{text[:2000]}"
            raw = call_llm(BATCH_TRANSLATE_SYSTEM, user_prompt, max_tokens=500, temperature=0.3, timeout=30)
            results.append({"index": i, "original": text[:200], "translated": raw.strip()})
        except Exception as e:
            results.append({"index": i, "original": text[:200], "translated": "", "error": str(e)})

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    total_chars = sum(len(t) for t in texts)
    log_usage("batch_translate", total_chars, len(json.dumps(results)), elapsed)

    result = {
        "task": "translate",
        "count": total,
        "success": sum(1 for r in results if not r.get("error")),
        "results": results,
    }
    _save_job(f"batch_{uuid.uuid4().hex[:8]}", "translate", total, result, user_id)
    _report(100, "完成")
    return result


async def _batch_doc_summary_worker(payload: dict, progress: Callable | None = None) -> dict:
    """批量文档摘要 worker：逐文件提取文本 + LLM 摘要（容错解析），按文件上报进度。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            progress(pct, stage)

    files = payload.get("files", [])
    user_id = payload.get("user_id", "")
    start = datetime.now()
    results = []
    total = len(files)

    for i, file in enumerate(files):
        _report(round((i / total) * 90, 1) if total else 10, f"摘要第 {i + 1}/{total} 份文档")
        try:
            text = extract_text(file["path"], file["filename"])
            if text and not text.startswith("["):
                raw = call_llm(
                    BATCH_SUMMARY_SYSTEM,
                    f"文档：{file['filename']}\n\n内容：{text[:5000]}",
                    max_tokens=500,
                    temperature=0.3,
                    timeout=45,
                )
                summary_data = parse_llm_json(raw.strip())
            else:
                summary_data = {"title": file["filename"], "summary": text or "提取失败", "key_points": []}

            results.append(
                {
                    "filename": file["filename"],
                    "size": file.get("size", 0),
                    "title": summary_data.get("title", file["filename"]),
                    "summary": summary_data.get("summary", ""),
                    "key_points": summary_data.get("key_points", []),
                }
            )
        except Exception as e:
            results.append(
                {
                    "filename": file["filename"],
                    "title": file["filename"],
                    "summary": "",
                    "key_points": [],
                    "error": str(e),
                }
            )
        finally:
            try:
                os.remove(file["path"])
            except OSError:
                pass

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("batch_doc_summary", len(files), len(json.dumps(results)), elapsed)

    result = {
        "job_id": f"batch_{uuid.uuid4().hex[:8]}",
        "task": "doc_summary",
        "file_count": total,
        "results": results,
    }
    _save_job(result["job_id"], "doc_summary", total, result, user_id)
    _report(100, "完成")
    return result


async def _batch_process_worker(payload: dict, progress: Callable | None = None) -> dict:
    """通用批量处理 worker：逐文件提取文本 + 统一 LLM 处理，按文件上报进度。"""

    def _report(pct: float, stage: str) -> None:
        if progress:
            progress(pct, stage)

    files = payload.get("files", [])
    user_id = payload.get("user_id", "")
    task = payload.get("task", "summarize")
    start = datetime.now()
    results = []
    total = len(files)

    task_prompts = {
        "summarize": "请用中文摘要以下文档（100字以内）：",
        "keywords": "请提取以下文档的5-8个核心关键词，用逗号分隔。只输出关键词。",
        "sentiment": "请分析以下文本的情感倾向，只输出：正面/负面/中性，并附一句话原因。",
        "translate_en": "将以下文本翻译为英文，只输出译文：",
    }
    task_prompt = task_prompts.get(task, task_prompts["summarize"])

    for i, file in enumerate(files):
        _report(round((i / total) * 90, 1) if total else 10, f"处理第 {i + 1}/{total} 个文件")
        try:
            text = extract_text(file["path"], file["filename"])
            if text and not text.startswith("["):
                raw = call_llm(
                    task_prompt,
                    f"文件：{file['filename']}\n\n{text[:4000]}",
                    max_tokens=400,
                    temperature=0.3,
                    timeout=30,
                )
                result_text = raw.strip()
            else:
                result_text = text or "处理失败"

            results.append({"filename": file["filename"], "result": result_text})
        except Exception as e:
            results.append({"filename": file["filename"], "result": "", "error": str(e)})
        finally:
            try:
                os.remove(file["path"])
            except OSError:
                pass

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("batch_process", len(files), len(json.dumps(results)), elapsed)

    result = {
        "job_id": f"batch_{uuid.uuid4().hex[:8]}",
        "task": task,
        "file_count": total,
        "results": results,
    }
    _save_job(result["job_id"], task, total, result, user_id)
    _report(100, "完成")
    return result


def _save_job(job_id: str, task_type: str, file_count: int, result: dict, user_id: str) -> None:
    """写入 batch_jobs 记录（任务完成后调用，含用户归属）。"""
    try:
        with get_db_context() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO batch_jobs (id, task_type, file_count, results, status, user_id, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    job_id,
                    task_type,
                    file_count,
                    json.dumps(result, ensure_ascii=False),
                    "done",
                    user_id,
                    datetime.now().isoformat(),
                ),
            )
    except Exception as e:
        logger.warning("save batch_jobs failed: %s", e)


async def _batch_translate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装批量翻译，回报进度。"""
    return await _batch_translate_worker(payload, progress=update)


async def _batch_doc_summary_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装批量文档摘要，回报进度。"""
    return await _batch_doc_summary_worker(payload, progress=update)


async def _batch_process_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装通用批量处理，回报进度。"""
    return await _batch_process_worker(payload, progress=update)


# ── 异步任务处理器注册（进度/自动重试/并发控制）──
register_handler("batch_translate", _batch_translate_handler, user_limit=1, max_attempts=1)
register_handler("batch_doc_summary", _batch_doc_summary_handler, user_limit=1, max_attempts=1)
register_handler("batch_process", _batch_process_handler, user_limit=1, max_attempts=1)


@router.get("/jobs")
async def list_jobs(current_user: dict = require_auth()):
    """获取批量任务历史（用户隔离：admin 全量，普通用户仅自己的）。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    with get_db_context() as conn:
        if role in ("admin", "super_admin"):
            rows = conn.execute(
                "SELECT id, task_type, file_count, status, created_at FROM batch_jobs ORDER BY created_at DESC LIMIT 20"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, task_type, file_count, status, created_at FROM batch_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
                (uid,),
            ).fetchall()
    return [{"id": r[0], "task_type": r[1], "file_count": r[2], "status": r[3], "created_at": r[4]} for r in rows]
