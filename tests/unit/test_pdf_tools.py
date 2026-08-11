"""v15 PDF 工具增强单测：合同风险归一化 + 压缩 PDF。

覆盖：
- _normalize_contract_result：risk 枚举收敛、party 责任标注补全、分级排序、level_count
- compress_pdf：PyMuPDF 压缩链路（结构压缩 + 图片重编码）、quality 收敛、结果字段
"""

import asyncio
import io
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


class TestNormalizeContractResult:
    def test_illegal_risk_converges_to_medium(self):
        from pdf_tools import _normalize_contract_result

        raw = {
            "risk_level": "catastrophic",
            "risks": [
                {"clause": "A", "content": "x", "risk": "critical", "issue": "i", "suggestion": "s"},
                {"clause": "B", "content": "y", "risk": "low", "issue": "i2", "suggestion": "s2"},
            ],
        }
        result = _normalize_contract_result(raw)
        assert result["risk_level"] == "medium"
        # critical 非法收敛为 medium，按 high<medium<low 排序应在 low 之前
        assert result["risks"][0]["risk"] == "medium"
        assert result["risks"][0]["clause"] == "A"
        assert result["risks"][1]["risk"] == "low"

    def test_party_annotation(self):
        from pdf_tools import _normalize_contract_result

        raw = {
            "risk_level": "high",
            "risks": [
                {"clause": "违约金", "content": "x", "risk": "high", "party": "乙方", "issue": "i", "suggestion": "s"},
                {"clause": "保密", "content": "y", "risk": "medium", "issue": "i2", "suggestion": "s2"},  # 缺 party
            ],
        }
        result = _normalize_contract_result(raw)
        assert result["risks"][0]["party"] == "乙方"
        assert result["risks"][1]["party"] == "未标注"

    def test_sorted_by_severity_and_level_count(self):
        from pdf_tools import _normalize_contract_result

        raw = {
            "risk_level": "high",
            "risks": [
                {"clause": "low1", "risk": "low"},
                {"clause": "high1", "risk": "high"},
                {"clause": "med1", "risk": "medium"},
                {"clause": "high2", "risk": "high"},
            ],
        }
        result = _normalize_contract_result(raw)
        order = [r["risk"] for r in result["risks"]]
        assert order == ["high", "high", "medium", "low"]
        assert result["risk_count"] == 4
        assert result["level_count"] == {"high": 2, "medium": 1, "low": 1}

    def test_drops_non_dict_items_and_empty(self):
        from pdf_tools import _normalize_contract_result

        result = _normalize_contract_result({"risk_level": "low", "risks": [None, "str", {"clause": "ok", "risk": "low"}]})
        assert result["risk_count"] == 1
        assert result["risks"][0]["clause"] == "ok"

        empty = _normalize_contract_result(None)
        assert empty["risks"] == []
        assert empty["risk_count"] == 0


def _make_test_pdf() -> bytes:
    """用 PyMuPDF 生成一个含文本+图片的 PDF，模拟未优化的原始文件。"""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "v15 compress test " * 200, fontsize=9)
    # 插入一张 600x600 彩色图（随机像素，便于压缩前后体积对比）
    import random

    random.seed(42)
    w, h = 600, 600
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), 0)
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            pix.set_pixel(x, y, (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    page.insert_image(fitz.Rect(72, 120, 72 + w / 2, 120 + h / 2), pixmap=pix)
    data = doc.tobytes(garbage=0, deflate=False)  # 未优化的原始流
    doc.close()
    return data


class TestCompressPdf:
    def test_compress_success_and_fields(self, setup_test_db):
        import os

        import pdf_tools
        from fastapi import UploadFile

        data = _make_test_pdf()
        f = UploadFile(filename="raw.pdf", file=io.BytesIO(data))

        res = asyncio.run(pdf_tools.compress_pdf(file=f, quality=3, current_user=USER))
        assert res["success"] is True
        assert res["filename"].endswith(".pdf")
        assert res["download_url"].startswith("/api/pdf/download/")
        assert res["original_size"] == len(data)
        assert res["compressed_size"] > 0
        assert 0 <= res["ratio"] <= 100
        # 输出文件真实存在
        assert os.path.exists(os.path.join(pdf_tools.PDF_DIR, res["filename"]))

    def test_compress_records_job(self, setup_test_db):
        import pdf_tools
        from common.db import get_db
        from fastapi import UploadFile

        f = UploadFile(filename="raw2.pdf", file=io.BytesIO(_make_test_pdf()))
        res = asyncio.run(pdf_tools.compress_pdf(file=f, quality=8, current_user=USER))

        conn = get_db()
        row = conn.execute("SELECT job_type, result_filename, result_data FROM pdf_jobs WHERE id LIKE 'compress_%' ORDER BY created_at DESC LIMIT 1").fetchone()
        conn.close()
        assert row is not None
        assert row["job_type"] == "compress"
        assert row["result_filename"] == res["filename"]

    def test_quality_clamped(self, setup_test_db):
        import pdf_tools
        from fastapi import UploadFile

        f = UploadFile(filename="raw3.pdf", file=io.BytesIO(_make_test_pdf()))
        # quality=99 应收敛到 10 而不报错
        res = asyncio.run(pdf_tools.compress_pdf(file=f, quality=99, current_user=USER))
        assert res["success"] is True

    def test_reject_non_pdf(self, setup_test_db):
        import pdf_tools
        from fastapi import HTTPException, UploadFile

        f = UploadFile(filename="evil.txt", file=io.BytesIO(b"not pdf"))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(pdf_tools.compress_pdf(file=f, quality=5, current_user=USER))
        assert exc.value.status_code == 400

    def test_reject_empty_file(self, setup_test_db):
        import pdf_tools
        from fastapi import HTTPException, UploadFile

        f = UploadFile(filename="empty.pdf", file=io.BytesIO(b""))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(pdf_tools.compress_pdf(file=f, quality=5, current_user=USER))
        assert exc.value.status_code == 400
