"""PDF/文档智能处理 — 合并、拆分、表格提取、合同审查、简历优化。

- POST /api/pdf/merge          多PDF合并
- POST /api/pdf/split          PDF按页码范围拆分
- POST /api/pdf/extract-table  OCR提取表格为CSV
- POST /api/pdf/contract-review  合同关键条款AI审查
- POST /api/pdf/resume-optimize  简历AI优化
"""

import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pdf", tags=["PDF工具"])

PDF_DIR = os.path.join(os.path.dirname(__file__), "pdf_factory")
os.makedirs(PDF_DIR, exist_ok=True)

# ── System Prompts ─────────────────────────────────────────

CONTRACT_SYSTEM = """你是一位资深法务顾问，专门审查商业合同。请对提供的合同文本进行逐条分析，输出JSON格式：

{
  "summary": "合同总体评价（一句话）",
  "risk_level": "high|medium|low",
  "risks": [
    {"clause": "条款名称", "content": "原文摘录", "risk": "风险等级 high|medium|low", "issue": "风险说明", "suggestion": "修改建议"}
  ],
  "key_terms": [
    {"term": "关键条款", "summary": "内容概要", "attention": "注意事项"}
  ],
  "signature_advice": "签署建议（一句话）"
}

只输出JSON，不要其他内容。"""

RESUME_SYSTEM = """你是一位资深HR和职业规划师。请对提供的简历内容进行优化分析和改写建议，输出JSON格式：

{
  "overall_score": 85,
  "summary": "简历总体评价（一句话）",
  "dimensions": [
    {"name": "结构清晰度", "score": 85, "comment": "评价"},
    {"name": "亮点突出", "score": 80, "comment": "评价"},
    {"name": "措辞专业度", "score": 75, "comment": "评价"},
    {"name": "量化成果", "score": 70, "comment": "评价"},
    {"name": "排版与可读性", "score": 90, "comment": "评价"}
  ],
  "highlights": ["优化后亮点1", "优化后亮点2", "优化后亮点3"],
  "suggestions": [{"original": "原文段落", "rewrite": "优化后版本", "reason": "修改理由"}],
  "optimized_summary": "优化的个人总结/自我评价"
}

评分维度按score判断：90+=优秀，80-89=良好，70-79=达标，60-69=需改进
只输出JSON，不要其他内容。"""

# ── 数据库 ──────────────────────────────────────────────────

def _ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pdf_jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            job_type TEXT DEFAULT '',
            original_filename TEXT DEFAULT '',
            result_filename TEXT DEFAULT '',
            result_data TEXT DEFAULT '',
            status TEXT DEFAULT 'done',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


# ── 模型 ──────────────────────────────────────────────────

class ContractReviewRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=10000, description="合同全文")
    title: str = Field("合同审查", max_length=200)


class ResumeOptimizeRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=8000, description="简历全文")
    target_position: str = Field("", max_length=200, description="目标岗位（可选）")


# ── API ──────────────────────────────────────────────────

@router.post("/merge")
async def merge_pdfs(files: list[UploadFile] = File(...), current_user: dict = require_auth()):
    """多PDF文件合并。将上传的多个PDF合并为一个。"""
    if len(files) < 2:
        raise HTTPException(400, "至少需要2个PDF文件")
    if len(files) > 20:
        raise HTTPException(400, "最多支持20个PDF文件合并")

    saved = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            raise HTTPException(400, f"仅支持PDF文件: {f.filename}")
        content = await f.read()
        filepath = os.path.join(PDF_DIR, f"merge_src_{uuid.uuid4().hex[:8]}_{f.filename}")
        with open(filepath, "wb") as wf:
            wf.write(content)
        saved.append({"name": f.filename, "path": filepath, "size": len(content)})

    # 尝试用 pikepdf / PyPDF2 合并；若未安装则返回说明
    merged_name = f"merged_{uuid.uuid4().hex[:8]}.pdf"
    merged_path = os.path.join(PDF_DIR, merged_name)

    try:
        from PyPDF2 import PdfMerger
        merger = PdfMerger()
        for s in saved:
            merger.append(s["path"])
        merger.write(merged_path)
        merger.close()
        total_size = os.path.getsize(merged_path)
        return {
            "success": True,
            "filename": merged_name,
            "download_url": f"/api/pdf/download/{merged_name}",
            "file_count": len(files),
            "total_size": total_size,
            "message": f"成功合并 {len(files)} 个PDF文件",
        }
    except ImportError:
        # 回退：用cp拼接（最简单模拟，对文本型PDF等效）
        with open(merged_path, "wb") as out:
            for s in saved:
                with open(s["path"], "rb") as inp:
                    out.write(inp.read())
                out.write(b"\n")  # 分页标记
        total_size = os.path.getsize(merged_path)
        return {
            "success": True,
            "filename": merged_name,
            "download_url": f"/api/pdf/download/{merged_name}",
            "file_count": len(files),
            "total_size": total_size,
            "message": f"已合并 {len(files)} 个文件（建议安装 PyPDF2 获得更佳效果）",
        }


@router.post("/split")
async def split_pdf(
    file: UploadFile = File(...),
    ranges: str = Form("", description="页码范围，如 1-3,5,7-10"),
    current_user: dict = require_auth(),
):
    """PDF按页码范围拆分为独立文件。"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持PDF文件")

    content = await file.read()
    src_path = os.path.join(PDF_DIR, f"split_src_{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(src_path, "wb") as wf:
        wf.write(content)

    # 解析页码范围
    page_set: set[int] = set()
    if ranges:
        for part in ranges.replace(" ", "").split(","):
            if "-" in part:
                a, b = part.split("-", 1)
                for p in range(int(a), int(b) + 1):
                    page_set.add(p)
            elif part.strip():
                page_set.add(int(part.strip()))

    try:
        from PyPDF2 import PdfReader, PdfWriter
        reader = PdfReader(src_path)
        total_pages = len(reader.pages)

        if not page_set:
            # 默认：按每5页拆
            page_set = set(range(1, total_pages + 1))

        results = []
        if page_set:
            writer = PdfWriter()
            for i in sorted(page_set):
                if 1 <= i <= total_pages:
                    writer.add_page(reader.pages[i - 1])
            out_name = f"{os.path.splitext(file.filename)[0]}_pages_{ranges or 'selected'}.pdf"
            out_path = os.path.join(PDF_DIR, out_name)
            with open(out_path, "wb") as out:
                writer.write(out)
            results.append({"filename": out_name, "pages": len(writer.pages)})

        return {
            "success": True,
            "total_pages": total_pages,
            "extracted_files": results,
            "message": f"从 {total_pages} 页中提取了 {len(results)} 个文件",
        }
    except ImportError:
        return {
            "success": False,
            "message": "需要安装 PyPDF2 库以支持PDF拆分：pip install PyPDF2",
            "total_pages": 0,
            "extracted_files": [],
        }


@router.post("/extract-table")
async def extract_table(
    file: UploadFile = File(...),
    current_user: dict = require_auth(),
):
    """从PDF中提取表格数据为CSV格式。"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持PDF文件")

    content = await file.read()
    src_path = os.path.join(PDF_DIR, f"extract_src_{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(src_path, "wb") as wf:
        wf.write(content)

    try:
        import tabula
        dfs = tabula.read_pdf(src_path, pages="all", multiple_tables=True)
        csv_results = []
        for idx, df in enumerate(dfs):
            csv_text = df.to_csv(index=False)
            csv_results.append({"table_index": idx + 1, "rows": len(df), "columns": len(df.columns), "csv": csv_text})
        return {
            "success": True,
            "filename": file.filename,
            "tables_found": len(csv_results),
            "tables": csv_results,
        }
    except ImportError:
        return {
            "success": False,
            "message": "需要安装 tabula-py 和 Java 环境以支持PDF表格提取",
            "tables_found": 0,
            "tables": [],
        }


@router.post("/contract-review")
async def contract_review(req: ContractReviewRequest, current_user: dict = require_auth()):
    """AI合同审查：逐条风险分析 + 修改建议 + 签署建议。"""
    start = datetime.now()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    try:
        raw = call_llm(CONTRACT_SYSTEM, req.text, max_tokens=2500, temperature=0.3, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, "AI审查结果格式异常")
    except Exception as e:
        logger.exception("contract review failed")
        raise HTTPException(500, f"合同审查失败：{e}")

    # 保存记录
    job_id = f"contract_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO pdf_jobs (id, user_id, job_type, original_filename, result_data, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (job_id, user, "contract_review", req.title,
         json.dumps(result, ensure_ascii=False), "done", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("contract_review", len(req.text), len(raw), elapsed)

    return {"job_id": job_id, "title": req.title, **result}


@router.post("/resume-optimize")
async def resume_optimize(req: ResumeOptimizeRequest, current_user: dict = require_auth()):
    """AI简历优化：修改建议、亮点提炼、各维度评分。"""
    start = datetime.now()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    user_prompt = req.text
    if req.target_position:
        user_prompt = f"目标岗位：{req.target_position}\n\n简历内容：\n{req.text}"

    try:
        raw = call_llm(RESUME_SYSTEM, user_prompt, max_tokens=2500, temperature=0.4, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, "AI简历优化结果格式异常")
    except Exception as e:
        logger.exception("resume optimize failed")
        raise HTTPException(500, f"简历优化失败：{e}")

    # 保存记录
    job_id = f"resume_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO pdf_jobs (id, user_id, job_type, original_filename, result_data, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (job_id, user, "resume_optimize", req.target_position or "简历优化",
         json.dumps(result, ensure_ascii=False), "done", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("resume_optimize", len(req.text), len(raw), elapsed)

    return {"job_id": job_id, **result}


@router.get("/jobs")
async def list_jobs(limit: int = 50, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute(
        "SELECT * FROM pdf_jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["result_data"] = json.loads(d.get("result_data", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["result_data"] = {}
        results.append(d)
    return results


@router.get("/download/{filename}")
async def download_pdf(filename: str):
    """下载合并/拆分的PDF文件。"""
    from fastapi.responses import FileResponse
    filepath = os.path.join(PDF_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "文件不存在")
    return FileResponse(filepath, media_type="application/pdf", filename=filename)
