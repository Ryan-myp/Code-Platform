"""v15 批量处理增强单测：任务模板（批量改写）+ 失败项单独重试。

覆盖：
- extract_text：txt 读取、不支持格式标记
- _batch_translate_worker：失败项保留完整原文（支持重试）、成功项截断
- _batch_retry_worker：重试保留原索引、再次失败保留 error
- batch_retry 端点：非法 task_type 返回 400
- 批量改写模板：prompt 注入断言
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
def _init_batch_tables(setup_test_db):
    """在临时库中重建 batch_jobs 表（init_db 仅在首次 import 时执行一次）。"""
    import batch_api

    batch_api.init_db()


class TestExtractText:
    def test_txt_read(self, tmp_path):
        from batch_api import extract_text

        f = tmp_path / "a.txt"
        f.write_text("你好世界", encoding="utf-8")
        assert extract_text(str(f), "a.txt") == "你好世界"

    def test_unsupported_format(self, tmp_path):
        from batch_api import extract_text

        f = tmp_path / "a.xyz"
        f.write_text("x")
        assert "[不支持格式" in extract_text(str(f), "a.xyz")


class TestBatchTranslateWorker:
    def test_failed_item_keeps_full_original(self, monkeypatch):
        """失败项 original 必须是完整原文（截断则无法重试）。"""

        async def boom(_system, _user, **_kw):
            raise RuntimeError("llm down")

        monkeypatch.setattr("batch_api.call_llm_async", boom)
        monkeypatch.setattr("batch_api.log_usage", lambda *a, **kw: None)
        from batch_api import _batch_translate_worker

        long_text = "长文本" * 300  # 超过 200 截断线
        result = asyncio.run(
            _batch_translate_worker(
                {"texts": [long_text], "target_lang": "en", "user_id": "u1"},
                progress=lambda p, s: None,
            )
        )
        assert result["success"] == 0
        failed = result["results"][0]
        assert failed["error"]
        assert failed["original"] == long_text

    def test_success_item_truncated(self, monkeypatch):
        async def fake_llm(_system, _user, **_kw):
            return "hello"

        monkeypatch.setattr("batch_api.call_llm_async", fake_llm)
        monkeypatch.setattr("batch_api.log_usage", lambda *a, **kw: None)
        from batch_api import _batch_translate_worker

        long_text = "长文本" * 300
        result = asyncio.run(
            _batch_translate_worker(
                {"texts": [long_text], "target_lang": "en", "user_id": "u1"},
                progress=lambda p, s: None,
            )
        )
        assert result["success"] == 1
        assert result["results"][0]["translated"] == "hello"
        assert len(result["results"][0]["original"]) <= 200


class TestBatchRetryWorker:
    def test_retry_keeps_original_index(self, monkeypatch):
        async def fake_llm(_system, _user, **_kw):
            return "retried ok"

        monkeypatch.setattr("batch_api.call_llm_async", fake_llm)
        monkeypatch.setattr("batch_api.log_usage", lambda *a, **kw: None)
        from batch_api import _batch_retry_worker

        result = asyncio.run(
            _batch_retry_worker(
                {
                    "items": [
                        {"index": 3, "original": "失败原文A", "target_lang": "en", "source_lang": "auto"},
                        {"index": 7, "original": "失败原文B", "target_lang": "en", "source_lang": "auto"},
                    ],
                    "user_id": "u1",
                },
                progress=lambda p, s: None,
            )
        )
        assert result["task"] == "translate_retry"
        assert result["success"] == 2
        assert [r["index"] for r in result["results"]] == [3, 7]
        assert result["results"][0]["translated"] == "retried ok"

    def test_retry_keeps_error_on_second_failure(self, monkeypatch):
        async def boom(_system, _user, **_kw):
            raise RuntimeError("still down")

        monkeypatch.setattr("batch_api.call_llm_async", boom)
        monkeypatch.setattr("batch_api.log_usage", lambda *a, **kw: None)
        from batch_api import _batch_retry_worker

        result = asyncio.run(
            _batch_retry_worker(
                {"items": [{"index": 0, "original": "x", "target_lang": "en", "source_lang": "auto"}]},
                progress=lambda p, s: None,
            )
        )
        assert result["success"] == 0
        assert result["results"][0]["index"] == 0
        assert "still down" in result["results"][0]["error"]


class TestBatchRetryEndpoint:
    def test_unsupported_task_type_rejected(self):
        from fastapi import HTTPException

        from batch_api import BatchRetryRequest, batch_retry

        req = BatchRetryRequest(task_type="doc_summary", items=[{"index": 0, "original": "x"}])
        with pytest.raises(HTTPException) as exc:
            asyncio.run(batch_retry(req, sync=True, current_user=USER))
        assert exc.value.status_code == 400

    def test_valid_retry_payload_accepted(self):
        from batch_api import BatchRetryRequest

        req = BatchRetryRequest(task_type="translate", items=[{"index": 0, "original": "x"}])
        assert req.items[0].original == "x"


class TestRewriteTemplate:
    def test_rewrite_prompt_injected(self, monkeypatch, tmp_path):
        """批量改写任务：LLM prompt 包含改写要求，结果回写。"""

        captured = {}

        async def fake_llm(prompt, _user, **_kw):
            captured["prompt"] = prompt
            return "改写好文"

        monkeypatch.setattr("batch_api.call_llm_async", fake_llm)
        monkeypatch.setattr("batch_api.log_usage", lambda *a, **kw: None)
        from batch_api import _batch_process_worker

        f = tmp_path / "doc.txt"
        f.write_text("这是一段需要改写的原文", encoding="utf-8")
        result = asyncio.run(
            _batch_process_worker(
                {"task": "rewrite", "files": [{"path": str(f), "filename": "doc.txt", "size": 10}], "user_id": "u1"},
                progress=lambda p, s: None,
            )
        )
        assert "改写" in captured["prompt"]
        assert result["results"][0]["result"] == "改写好文"
