"""统一 RAG 管线 — 文本提取 / 切块 / 检索 / 引用溯源。

知识库（kb_api.py）与文档问答（doc_qa.py）共用这套管线，
避免两套平行实现漂移出不同行为。

模块级 MAX_DOC_CHARS 控制单次文本提取上限；调用方可按需覆盖。
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# 单次文本提取上限（字）。用于 PDF/DOCX 等文件；纯 txt/md 不额外截断。
MAX_DOC_CHARS = 15000


# ── 文本提取 ──────────────────────────────────────────────


def extract_text(filepath: str, filename: str) -> str:  # noqa: C901
    """从文件提取纯文本（支持 .txt/.md/.csv/.log/.json/.yaml/.pdf/.docx/.xlsx/.pptx）。

    不支持的扩展名返回 ``[不支持的文件格式：.ext]`` 占位字符串，
    调用方通过 ``startswith('[')`` 判断失败并跳过。
    """
    ext = os.path.splitext(filename)[1].lower()

    # ── 纯文本（直接读）────────────────────────────────────
    if ext in (".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".html", ".htm"):
        try:
            with open(filepath, encoding="utf-8", errors="ignore") as f:
                return f.read()[:MAX_DOC_CHARS]
        except OSError:
            return "[文本文件读取失败]"

    # ── PDF ────────────────────────────────────────────────
    if ext == ".pdf":
        return _extract_pdf(filepath)

    # ── Word ──────────────────────────────────────────────
    if ext in (".docx", ".doc"):
        return _extract_docx(filepath)

    # ── Excel ─────────────────────────────────────────────
    if ext in (".xlsx", ".xls"):
        return _extract_xlsx(filepath)

    # ── PowerPoint ─────────────────────────────────────────
    if ext in (".pptx", ".ppt"):
        return _extract_pptx(filepath)

    return f"[不支持的文件格式：{ext}]"


def _extract_pdf(filepath: str) -> str:
    try:
        import PyPDF2

        text = ""
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:30]:  # 最多 30 页
                try:
                    t = page.extract_text() or ""
                except Exception:
                    t = ""
                if t:
                    text += t + "\n"
                    if len(text) > MAX_DOC_CHARS:
                        break
        return text[:MAX_DOC_CHARS]
    except ImportError:
        return "[PDF解析库未安装，请安装 PyPDF2]"
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return "[PDF文本提取失败，请确认文件是否为可读 PDF]"


def _extract_docx(filepath: str) -> str:
    try:
        import docx

        d = docx.Document(filepath)
        text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
        return text[:MAX_DOC_CHARS]
    except ImportError:
        return "[Word解析库未安装，请安装 python-docx]"
    except Exception as e:
        logger.warning(f"DOCX extraction failed: {e}")
        return "[Word文档文本提取失败]"


def _extract_xlsx(filepath: str) -> str:
    try:
        from openpyxl import load_workbook

        wb = load_workbook(filepath, read_only=True, data_only=True)
        text_parts: list[str] = []
        for ws in wb.worksheets[:10]:  # 最多 10 个 sheet
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if cells:
                    text_parts.append("\t".join(cells))
                if sum(len(p) for p in text_parts) > MAX_DOC_CHARS:
                    break
            if sum(len(p) for p in text_parts) > MAX_DOC_CHARS:
                break
        wb.close()
        return "\n".join(text_parts)[:MAX_DOC_CHARS]
    except ImportError:
        return "[Excel解析库未安装，请安装 openpyxl]"
    except Exception as e:
        logger.warning(f"XLSX extraction failed: {e}")
        return "[Excel文档文本提取失败]"


def _extract_pptx(filepath: str) -> str:
    try:
        from pptx import Presentation

        prs = Presentation(filepath)
        text_parts: list[str] = []
        for i, slide in enumerate(prs.slides[:30], 1):  # 最多 30 页
            slide_text: list[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        if para.text.strip():
                            slide_text.append(para.text.strip())
                elif shape.has_table:
                    for row in shape.table.rows:
                        cells = [c.text.strip() for c in row.cells if c.text.strip()]
                        if cells:
                            slide_text.append("\t".join(cells))
            if slide_text:
                text_parts.append(f"--- 第 {i} 页 ---\n" + "\n".join(slide_text))
            if sum(len(p) for p in text_parts) > MAX_DOC_CHARS:
                break
        return "\n\n".join(text_parts)[:MAX_DOC_CHARS]
    except ImportError:
        return "[PPTX解析库未安装，请安装 python-pptx]"
    except Exception as e:
        logger.warning(f"PPTX extraction failed: {e}")
        return "[PPT 文档文本提取失败]"


# ── 切块 ──────────────────────────────────────────────────


def chunk_text(text: str, chunk_size: int = 500) -> list[dict]:
    """按段落切块（尽量以完整段落为边界），返回 ``[{id, text}]``。

    - 短段落累积到接近 chunk_size 才切
    - 超长段落（单段超上限）先落盘已有 buf，再按固定大小拆段
    """
    chunks: list[dict] = []
    buf = ""
    for para in re.split(r"\n+", text or ""):
        para = para.strip()
        if not para:
            continue
        if len(para) > chunk_size:
            # 超长段落：先落盘已有 buf
            if buf.strip():
                chunks.append({"id": f"c{len(chunks) + 1}", "text": buf.strip()})
                buf = ""
            for i in range(0, len(para), chunk_size):
                chunks.append({"id": f"c{len(chunks) + 1}", "text": para[i : i + chunk_size]})
            continue
        if len(buf) + len(para) > chunk_size and buf:
            chunks.append({"id": f"c{len(chunks) + 1}", "text": buf.strip()})
            buf = ""
        buf += para + "\n"
    if buf.strip():
        chunks.append({"id": f"c{len(chunks) + 1}", "text": buf.strip()})
    return chunks


# ── 检索 ──────────────────────────────────────────────────


def retrieve_chunks(question: str, chunks: list[dict], top_k: int = 4) -> list[dict]:
    """2-gram 重叠检索：问题与片段字符级 2-gram 集合的 Jaccard 相似度打分。

    无重叠命中时回退返回前 top_k 块（保证 LLM 有上下文可用）。
    """

    def _sig(text: str) -> set:
        t = re.sub(r"\s+", "", str(text or "")).lower()
        return {t[i : i + 2] for i in range(max(0, len(t) - 1))}

    qsig = _sig(question)
    if not qsig or not chunks:
        return chunks[:top_k]
    scored = []
    for c in chunks:
        csig = _sig(c["text"])
        score = len(qsig & csig) / max(len(qsig), 1)
        scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    top = [c for s, c in scored[:top_k] if s > 0]
    return top or chunks[:top_k]


# ── 引用溯源 ──────────────────────────────────────────────


def extract_citations(answer: str, retrieved: list[dict]) -> list[dict]:
    """从回答中提取 ``[N]`` 引用标记 → 映射到检索片段（去重、越界忽略）。

    返回 [{id, doc_name, text}]；doc_name 来自 retrieved 块（多文档联合问答场景）。
    """
    citations = []
    seen = set()
    for m in re.finditer(r"\[(\d+)\]", answer or ""):
        idx = int(m.group(1))
        if idx < 1 or idx > len(retrieved) or idx in seen:
            continue
        seen.add(idx)
        src = retrieved[idx - 1]
        citations.append(
            {
                "id": src.get("id", f"c{idx}"),
                "doc_name": src.get("doc_name", ""),
                "text": src.get("text", "")[:200],
            }
        )
    return citations
