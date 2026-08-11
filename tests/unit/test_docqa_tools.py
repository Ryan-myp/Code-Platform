"""v15 DocQA 增强单测：引用溯源（切块/检索/引用提取）+ 多文档联合问答。

覆盖：
- _chunk_text：按段落切块、大段自动拆分、空文本
- _retrieve_chunks：2-gram 重叠检索相关片段优先、无重叠回退
- _extract_citations：提取 [N] 标记、去重、越界忽略
- _docqa_ask_worker：多文档联合问答（sources/citations/doc_ids 断言）
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


@pytest.fixture(autouse=True)
def _init_docqa_tables(setup_test_db):
    """在临时库中重建 doc_qa_records 表（init_db 仅在首次 import 时执行一次）。"""
    import doc_qa

    doc_qa.init_db()


class TestChunkText:
    def test_paragraph_boundary_chunks(self):
        from doc_qa import _chunk_text

        # 短段落累积到接近 chunk_size 才切块；切分不拆断段落
        chunks = _chunk_text("第一段。\n第二段内容。\n\n第三段。", chunk_size=10)
        assert len(chunks) == 3
        assert chunks[0]["text"] == "第一段。"
        assert chunks[0]["id"] == "c1"

    def test_long_paragraph_split(self):
        from doc_qa import _chunk_text

        chunks = _chunk_text("甲" * 1200, chunk_size=500)
        assert len(chunks) >= 2
        assert all(len(c["text"]) <= 510 for c in chunks)

    def test_short_text_single_chunk(self):
        from doc_qa import _chunk_text

        chunks = _chunk_text("第一段。\n第二段内容。\n\n第三段。")
        assert len(chunks) == 1

    def test_empty_text(self):
        from doc_qa import _chunk_text

        assert _chunk_text("") == []
        assert _chunk_text("\n\n  \n") == []


class TestRetrieveChunks:
    def test_relevant_chunk_ranked_first(self):
        from doc_qa import _chunk_text, _retrieve_chunks

        chunks = _chunk_text("合同约定违约金为合同总价的20%。\n今天天气晴朗适合出行。\n付款方式为分三期支付。")
        top = _retrieve_chunks("违约金是多少？", chunks, top_k=2)
        assert "违约金" in top[0]["text"]

    def test_no_overlap_falls_back(self):
        from doc_qa import _chunk_text, _retrieve_chunks

        # 两段各超上限 → 切成多块；无重叠时回退前 2 块
        chunks = _chunk_text("甲" * 600 + "\n" + "乙" * 600, chunk_size=500)
        assert len(chunks) >= 2
        top = _retrieve_chunks("zzzzzzz", chunks, top_k=2)
        assert len(top) == 2

    def test_empty_question(self):
        from doc_qa import _chunk_text, _retrieve_chunks

        chunks = _chunk_text("段落A。")
        assert _retrieve_chunks("", chunks) == chunks


class TestExtractCitations:
    def test_extract_valid_citations(self):
        from doc_qa import _extract_citations

        retrieved = [{"id": "c1", "doc_name": "a.pdf", "text": "x" * 300}, {"id": "c2", "doc_name": "b.pdf", "text": "y"}]
        cites = _extract_citations("答案是A [1]，另有B [2] 佐证。", retrieved)
        assert len(cites) == 2
        assert cites[0]["doc_name"] == "a.pdf"
        assert len(cites[0]["text"]) <= 200  # 片段截断

    def test_duplicate_and_out_of_range_ignored(self):
        from doc_qa import _extract_citations

        retrieved = [{"id": "c1", "doc_name": "a", "text": "x"}]
        cites = _extract_citations("重复引用 [1] 和 [1]，越界 [9] 忽略。", retrieved)
        assert len(cites) == 1

    def test_no_markers(self):
        from doc_qa import _extract_citations

        assert _extract_citations("没有引用标记的回答。", [{"id": "c1", "doc_name": "a", "text": "x"}]) == []


class TestMultiDocWorker:
    def test_multi_doc_joint_qa(self, setup_test_db, monkeypatch):
        import doc_qa as dq
        from common.db import get_db

        conn = get_db()
        try:
            for did, name, text in [
                ("d1", "产品手册.pdf", "产品A支持语音控制功能，可通过语音指令开关。"),
                ("d2", "价格表.pdf", "产品A售价为999元，支持分期付款。"),
            ]:
                conn.execute(
                    "INSERT INTO doc_qa_records (id, filename, filepath, file_size, text_content, text_length, summary, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (did, name, f"/tmp/{did}.pdf", 100, text, len(text), "{}", "ready", "u1", "2026-01-01T00:00:00"),
                )
            conn.commit()
        finally:
            conn.close()

        async def fake_llm(system, prompt, **kw):
            assert "产品手册.pdf" in system and "价格表.pdf" in system  # 跨文档上下文注入
            return "产品A支持语音控制 [1]，售价999元 [2]。"

        monkeypatch.setattr(dq, "call_llm_async", fake_llm)
        resp = asyncio.run(
            dq._docqa_ask_worker(
                {"doc_ids": ["d1", "d2"], "doc_id": "d1", "question": "产品A支持什么？", "user_id": "u1"}
            )
        )
        assert resp["doc_ids"] == ["d1", "d2"]
        assert len(resp["sources"]) == 2
        assert len(resp["citations"]) == 2
        assert {c["doc_name"] for c in resp["citations"]} == {"产品手册.pdf", "价格表.pdf"}
        assert "产品手册.pdf、价格表.pdf" in resp["source"]

    def test_worker_rejects_missing_docs(self, setup_test_db):
        import doc_qa as dq
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                dq._docqa_ask_worker({"doc_ids": ["nope"], "question": "q", "user_id": "u1"})
            )
        assert exc.value.status_code == 404

    def test_worker_rejects_too_many_docs(self, setup_test_db):
        import doc_qa as dq
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                dq._docqa_ask_worker(
                    {"doc_ids": [f"d{i}" for i in range(6)], "question": "q", "user_id": "u1"}
                )
            )
        assert exc.value.status_code == 400

    def test_worker_fallback_single_doc_id(self, setup_test_db, monkeypatch):
        import doc_qa as dq
        from common.db import get_db

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO doc_qa_records (id, filename, filepath, file_size, text_content, text_length, summary, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                ("s1", "单一文档.txt", "/tmp/s1.txt", 10, "这是唯一的内容。", 7, "{}", "ready", "u1", "2026-01-01T00:00:00"),
            )
            conn.commit()
        finally:
            conn.close()

        async def fake_llm(system, prompt, **kw):
            return "单一文档回答。"

        monkeypatch.setattr(dq, "call_llm_async", fake_llm)
        resp = asyncio.run(
            dq._docqa_ask_worker({"doc_id": "s1", "question": "内容是什么？", "user_id": "u1"})
        )
        assert resp["doc_ids"] == ["s1"]
        assert resp["sources"][0]["doc_name"] == "单一文档.txt"
