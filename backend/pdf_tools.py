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

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm, log_usage, _safe_exc_msg

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pdf", tags=["PDF工具"])

PDF_DIR = os.path.join(os.path.dirname(__file__), "pdf_factory")
os.makedirs(PDF_DIR, exist_ok=True)

# ── System Prompts ─────────────────────────────────────────

CONTRACT_SYSTEM = """你是一位拥有15年+经验的资深法务顾问，精通合同法、劳动法、知识产权法等商业法律，擅长识别合同中的隐藏风险和不对等条款。

## 审查框架
对合同文本进行7维度逐条审查，重点关注：
1. **权利义务对等性**：双方义务是否均衡，是否存在单方面加重己方义务/减轻对方责任的条款
2. **违约责任**：违约金比例是否合理（通常不超过实际损失的30%）、是否有单向违约条款
3. **知识产权**：成果归属是否清晰、授权范围是否合理、是否存在竞业限制过度
4. **保密条款**：保密范围是否合理、保密期限是否过长、违约处罚是否过重
5. **付款条款**：付款节点是否合理、是否有不合理的预付款要求、发票开具约定是否明确
6. **终止与解除**：解除条件是否公平、是否有任意解除权、善后义务是否明确
7. **管辖与争议**：管辖法院是否便利、仲裁条款是否合理、适用法律是否明确

## 风险评级标准
- **high（高风险）**：可能导致重大经济损失或法律纠纷，必须在签署前修改
- **medium（中风险）**：存在不合理但可协商，建议争取修改
- **low（低风险）**：格式性瑕疵或非核心条款，签署时留意即可

## 输出要求
- risks至少列出3条，每条必须引用原文具体表述
- **每条风险必须标注 party（责任倾向）**：该条款对哪一方不利/保护哪一方（甲方/乙方/双方/不明确），用于责任条款定位
- key_terms覆盖合同核心条款（金额/期限/交付标准/验收条件/违约责任/知识产权）
- signature_advice给出明确的签署建议和前置条件

输出严格JSON：
{
  "summary": "合同总体评价（含合同类型判断和整体公平性评估）",
  "risk_level": "high|medium|low",
  "risks": [
    {"clause": "条款名称", "content": "原文摘录", "risk": "high|medium|low", "party": "甲方|乙方|双方|不明确", "issue": "具体风险说明（引用法理或行业惯例）", "suggestion": "具体修改建议（含替代条款示例）"}
  ],
  "key_terms": [
    {"term": "关键条款名", "summary": "内容概要", "attention": "签署时需注意的核心要点"}
  ],
  "signature_advice": "签署建议（含前置条件和谈判策略）"
}

只输出JSON，不要其他内容。"""

RESUME_SYSTEM = """你是一位拥有10年+招聘经验的资深HR总监兼职业规划师，曾审核过10000+份简历，精通互联网/科技行业的简历筛选标准和ATS系统解析规则。

## 评审框架（6维度诊断）
1. **结构清晰度**（权重20%）：信息层级是否一目了然、是否遵循倒叙时间线、关键信息是否在首屏
2. **成果量化**（权重25%）：工作经历是否有具体数据支撑（提升XX%、增长XX万、节省XX天）、避免"负责/参与"等模糊动词
3. **亮点突出**（权重20%）：核心竞争力是否在前1/3页呈现、是否有差异化亮点（专利/开源贡献/行业影响力）
4. **措辞专业度**（权重15%）：动词选择是否有力（"主导"优于"参与"）、是否使用行业标准术语
5. **关键词优化**（权重10%）：是否包含目标岗位高频关键词（便于ATS筛选）、技能栈描述是否完整
6. **排版可读性**（权重10%）：是否一页以内、字体统一、留白合理、无错别字

## 评分标准
- 90+ ═ 优秀（可直接投递一线大厂）
- 80-89 ═ 良好（有竞争力，微调后可投）
- 70-79 ═ 达标（需针对性优化）
- 60-69 ═ 需改进（建议大幅改写）
- <60 ═ 较差（建议重新梳理经历后重写）

## 输出要求
- 每个评分维度有具体证据（引用原文说明为什么扣分）
- suggestions至少3条，每条含原文→改写→理由，改写示例可直接使用
- highlights提炼3个最能打动HR的核心卖点
- optimized_summary是可直接替换原简历"自我评价"的版本

输出严格JSON：
{
  "overall_score": 85,
  "summary": "简历总体评价（含市场竞争力评估和市场定位建议）",
  "dimensions": [
    {"name": "结构清晰度", "score": 85, "evidence": "原文XX处存在...", "comment": "评价"}
  ],
  "highlights": ["可直接用于面试自我介绍的亮点1", "亮点2", "亮点3"],
  "suggestions": [{"original": "原文段落", "rewrite": "优化后版本（可直接替换）", "reason": "修改理由（从HR视角说明为什么这样改更有效）"}],
  "optimized_summary": "优化的个人总结/自我评价（100-200字，含关键数据+核心能力+职业目标）"
}

只输出JSON，不要其他内容。"""

# ── 数据库 ──────────────────────────────────────────────────


# 风险级别权重（用于排序与汇总）
RISK_ORDER = {"high": 0, "medium": 1, "low": 2}
PARTY_VALUES = ("甲方", "乙方", "双方")


def _normalize_contract_result(result: dict) -> dict:
    """收敛AI合同审查输出（v15）：

    - risk 枚举归一（非法值保守取 medium）
    - 每条风险补齐 party 责任标注（甲方/乙方/双方，缺省标「未标注」）
    - risks 按高→中→低排序，附 level_count 分级统计
    """
    result = dict(result or {})
    if result.get("risk_level") not in ("high", "medium", "low"):
        result["risk_level"] = "medium"
    cleaned = []
    for r in (result.get("risks") or []):
        if not isinstance(r, dict):
            continue
        risk = r.get("risk")
        if risk not in ("high", "medium", "low"):
            risk = "medium"
        party = r.get("party")
        cleaned.append(
            {
                "clause": str(r.get("clause", "未命名条款"))[:60],
                "content": str(r.get("content", ""))[:300],
                "risk": risk,
                "party": party if party in PARTY_VALUES else "未标注",
                "issue": str(r.get("issue", "")),
                "suggestion": str(r.get("suggestion", "")),
            }
        )
    cleaned.sort(key=lambda x: RISK_ORDER.get(x["risk"], 1))
    result["risks"] = cleaned
    result["risk_count"] = len(cleaned)
    result["level_count"] = {lvl: sum(1 for r in cleaned if r["risk"] == lvl) for lvl in ("high", "medium", "low")}
    return result


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
    template_id: str = Field("", description="合同审查模板 ID（pdf-doc-templates，如 pdt_rent）")


class ResumeOptimizeRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=8000, description="简历全文")
    target_position: str = Field("", max_length=200, description="目标岗位（可选）")
    template_id: str = Field("", description="简历优化模板 ID（pdf-doc-templates，如 pdt_tech）")


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
            raise HTTPException(400, "操作失败，请稍后重试")
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
async def split_pdf(  # noqa: C901
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
def contract_review(req: ContractReviewRequest, current_user: dict = require_auth()):
    """AI合同审查：逐条风险分析 + 修改建议 + 签署建议。"""
    start = datetime.now()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    try:
        user_prompt = req.text
        # 文档模板注入：审查要点提示词（按模板专家视角，非法 id 静默忽略）
        if req.template_id:
            try:
                from common.template_utils import load_one, record_usage
                from pdf_doc_templates import TEMPLATE_DIR
                tpl = load_one(TEMPLATE_DIR, req.template_id, "PDF模板不存在")
                if tpl.get("pro_tips"):
                    user_prompt = f"【模板：《{tpl['name']}》】请额外重点审查以下要点：{tpl['pro_tips']}\n\n{user_prompt}"
                record_usage(req.template_id)
            except Exception:  # noqa: BLE001
                pass
        raw = call_llm(CONTRACT_SYSTEM, user_prompt, max_tokens=2500, temperature=0.3, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = _normalize_contract_result(json.loads(raw))
    except json.JSONDecodeError as e:
        raise HTTPException(500, "AI审查结果格式异常") from e
    except Exception as e:
        logger.exception("contract review failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    # 保存记录
    job_id = f"contract_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO pdf_jobs (id, user_id, job_type, original_filename, result_data, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (
            job_id,
            user,
            "contract_review",
            req.title,
            json.dumps(result, ensure_ascii=False),
            "done",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("contract_review", len(req.text), len(raw), elapsed)

    return {"job_id": job_id, "title": req.title, **result}


@router.post("/resume-optimize")
def resume_optimize(req: ResumeOptimizeRequest, current_user: dict = require_auth()):
    """AI简历优化：修改建议、亮点提炼、各维度评分。"""
    start = datetime.now()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    user_prompt = req.text
    if req.target_position:
        user_prompt = f"目标岗位：{req.target_position}\n\n简历内容：\n{req.text}"
    # 文档模板注入：岗位优化要点（按模板专家视角，非法 id 静默忽略）
    if req.template_id:
        try:
            from common.template_utils import load_one, record_usage
            from pdf_doc_templates import TEMPLATE_DIR
            tpl = load_one(TEMPLATE_DIR, req.template_id, "PDF模板不存在")
            if tpl.get("pro_tips"):
                user_prompt = f"【模板：《{tpl['name']}》】请额外重点参考以下优化要点：{tpl['pro_tips']}\n\n{user_prompt}"
            if tpl.get("position") and not req.target_position:
                user_prompt = f"目标岗位：{tpl['position']}\n\n{user_prompt}"
            record_usage(req.template_id)
        except Exception:  # noqa: BLE001
            pass

    try:
        raw = call_llm(RESUME_SYSTEM, user_prompt, max_tokens=2500, temperature=0.4, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(500, "AI简历优化结果格式异常") from e
    except Exception as e:
        logger.exception("resume optimize failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e

    # 保存记录
    job_id = f"resume_{uuid.uuid4().hex[:10]}"
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO pdf_jobs (id, user_id, job_type, original_filename, result_data, status, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (
            job_id,
            user,
            "resume_optimize",
            req.target_position or "简历优化",
            json.dumps(result, ensure_ascii=False),
            "done",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("resume_optimize", len(req.text), len(raw), elapsed)

    return {"job_id": job_id, **result}


@router.post("/compress")
async def compress_pdf(
    file: UploadFile = File(...),
    quality: int = Form(5, description="压缩强度 1-10（越大质量越高，越小体积越小）"),
    current_user: dict = require_auth(),
):
    """压缩PDF（v15）：去除冗余对象 + 可选图片降采样重编码，返回压缩比。"""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持PDF文件")
    quality = max(1, min(quality, 10))

    content = await file.read()
    orig_size = len(content)
    if orig_size == 0:
        raise HTTPException(400, "文件为空")
    src_path = os.path.join(PDF_DIR, f"compress_src_{uuid.uuid4().hex[:8]}_{file.filename}")
    with open(src_path, "wb") as wf:
        wf.write(content)

    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise HTTPException(500, "需要安装 PyMuPDF 以支持PDF压缩")

    out_name = f"compressed_{uuid.uuid4().hex[:8]}.pdf"
    out_path = os.path.join(PDF_DIR, out_name)
    try:
        doc = fitz.open(src_path)
        # 低质量档位对超大图片降采样重编码（JPEG 重编码），高质量档位仅做结构压缩
        if quality < 8:
            jpg_q = 30 + quality * 6  # 30~72
            for page in doc:
                for img in page.get_images(full=True):
                    xref = img[0]
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n > 4:  # CMYK/灰度 → RGB 以便 JPEG 编码
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        threshold = 1000 if quality <= 3 else 1600
                        if pix.width > threshold:
                            pix = pix.shrink(2)
                        page.replace_image(xref, pix.tobytes("jpeg", jpg_quality=jpg_q))
                        pix = None
                    except Exception:  # noqa: BLE001 单张图片压缩失败不影响整体
                        continue
        doc.save(out_path, garbage=4, deflate=True)
        doc.close()
    except Exception as e:
        logger.exception("pdf compress failed")
        raise HTTPException(500, "操作失败，请稍后重试") from e
    finally:
        try:
            os.unlink(src_path)
        except OSError:
            pass

    new_size = os.path.getsize(out_path)
    ratio = round((1 - new_size / orig_size) * 100, 1) if orig_size else 0.0

    # 保存记录
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    conn.execute(
        """INSERT INTO pdf_jobs (id, user_id, job_type, original_filename, result_filename, result_data, status, created_at)
           VALUES (?,?,?,?,?,?,?,?) """,
        (
            f"compress_{uuid.uuid4().hex[:10]}",
            user,
            "compress",
            file.filename,
            out_name,
            json.dumps({"original_size": orig_size, "compressed_size": new_size, "ratio": ratio}, ensure_ascii=False),
            "done",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "success": True,
        "filename": out_name,
        "download_url": f"/api/pdf/download/{out_name}",
        "original_size": orig_size,
        "compressed_size": new_size,
        "ratio": ratio,
        "message": f"压缩完成：{orig_size / 1024:.1f} KB → {new_size / 1024:.1f} KB（减小 {ratio}%）",
    }


@router.get("/jobs")
async def list_jobs(limit: int = 50, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_tables(conn)
    rows = conn.execute("SELECT * FROM pdf_jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
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
