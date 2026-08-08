"""批量处理商业化升级验证。

覆盖：
- 3 大批量任务（翻译/文档摘要/通用处理）：
  POST 创建异步任务（task_id）→ handler 执行 → batch_jobs 落库（带 user_id）
- 历史接口用户隔离：普通用户仅见自己的记录，admin 全量
- LLM JSON 容错解析（parse_llm_json：带 ```json 围栏的返回）
- sync=1 兼容旧同步调用
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import batch_api
from task_queue import _handlers, create_task, get_task


def _user(uid: str, name: str, role: str = "user") -> dict:
    return {"user_id": uid, "username": name, "role": role}


@pytest.fixture(autouse=True)
def _init_batch_tables(setup_test_db):
    """在临时库中重建批量处理表（模块级 init_db 仅在首次 import 时执行一次）。"""
    batch_api.init_db()


# ── 1. handler 注册 ────────────────────────────────────────


def test_batch_handlers_registered(setup_test_db):
    """三大批量任务的异步处理器必须已注册。"""
    missing = {"batch_translate", "batch_doc_summary", "batch_process"} - set(_handlers)
    assert not missing, f"未注册的任务类型: {missing}"


# ── 2. 批量翻译 ────────────────────────────────────────────


def test_batch_translate_async_flow(setup_test_db, claim_and_run):
    """批量翻译：异步任务逐条处理 → 结果 + batch_jobs 落库（带用户归属）。"""
    with patch("batch_api.call_llm_async", new_callable=AsyncMock, side_effect=["Hello world", "Good morning"]):
        task = create_task(
            "batch_translate",
            {"texts": ["你好世界", "早上好"], "target_lang": "en", "user_id": "u-alice"},
            username="alice",
            user_id="u-alice",
            role="user",
        )
        claim_and_run(task["id"])
        t = get_task(task["id"])
        assert t["status"] == "success"
        assert t["result"]["count"] == 2
        assert t["result"]["success"] == 2
        assert [r["translated"] for r in t["result"]["results"]] == ["Hello world", "Good morning"]

    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM batch_jobs").fetchall()
        assert len(rows) == 1
        assert rows[0]["task_type"] == "translate"
        assert rows[0]["status"] == "done"
        assert rows[0]["user_id"] == "u-alice"
    finally:
        conn.close()


def test_batch_translate_skips_empty(setup_test_db, claim_and_run):
    """空文本直接标记失败，不调用 LLM。"""
    with patch("batch_api.call_llm_async", new_callable=AsyncMock, return_value="x") as mock_llm:
        task = create_task(
            "batch_translate",
            {"texts": ["有效文本", "   "], "target_lang": "en", "user_id": "u-bob"},
            username="bob",
            user_id="u-bob",
            role="user",
        )
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"
        assert get_task(task["id"])["result"]["results"][1]["error"] == "文本为空"
        assert mock_llm.call_count == 1


# ── 3. 批量文档摘要 ────────────────────────────────────────

_SUMMARY_RAW = """```json
{
  "title": "电商双11复盘",
  "summary": "GMV 同比增长 32%，直播渠道贡献过半。",
  "key_points": ["直播贡献 55% GMV", "新客占比提升至 40%"],
  "sentiment": "positive",
  "category": "商业报告"
}
```"""


def test_batch_doc_summary_async_flow(setup_test_db, claim_and_run, tmp_path):
    """文档摘要：逐文件提取 + LLM 容错解析（围栏 JSON）→ batch_jobs 落库。"""
    doc_path = tmp_path / "report.md"
    doc_path.write_text("# 双11 复盘\nGMV 同比增长 32%。", encoding="utf-8")

    with patch("batch_api.call_llm_async", new_callable=AsyncMock, return_value=_SUMMARY_RAW):
        task = create_task(
            "batch_doc_summary",
            {"files": [{"path": str(doc_path), "filename": "report.md", "size": 40}], "user_id": "u-carol"},
            username="carol",
            user_id="u-carol",
            role="user",
        )
        claim_and_run(task["id"])
        t = get_task(task["id"])
        assert t["status"] == "success"
        assert t["result"]["file_count"] == 1
        item = t["result"]["results"][0]
        assert item["title"] == "电商双11复盘"
        assert item["key_points"][0] == "直播贡献 55% GMV"

    # 临时文件已被 worker 清理
    assert not doc_path.exists()


def test_batch_doc_summary_failure_isolated(setup_test_db, claim_and_run, tmp_path):
    """单个文件失败不影响其他文件。"""
    bad_path = tmp_path / "bad.md"
    bad_path.write_text("内容", encoding="utf-8")
    good_path = tmp_path / "good.md"
    good_path.write_text("好文档内容", encoding="utf-8")

    def _fake_llm(system, prompt, **kwargs):
        if "good" in prompt:
            return '{"title": "好文档", "summary": "摘要", "key_points": []}'
        raise RuntimeError("LLM 超时")

    with patch("batch_api.call_llm_async", new_callable=AsyncMock, side_effect=_fake_llm):
        task = create_task(
            "batch_doc_summary",
            {
                "files": [
                    {"path": str(bad_path), "filename": "bad.md", "size": 10},
                    {"path": str(good_path), "filename": "good.md", "size": 20},
                ],
                "user_id": "u-carol",
            },
            username="carol",
            user_id="u-carol",
            role="user",
        )
        claim_and_run(task["id"])
        results = get_task(task["id"])["result"]["results"]
        assert results[0]["error"]
        assert results[1]["title"] == "好文档"


# ── 4. 通用批量处理 ────────────────────────────────────────


def test_batch_process_async_flow(setup_test_db, claim_and_run, tmp_path):
    """通用处理：按 task 类型执行 + 结果落库。"""
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("平台 AI 工具覆盖内容创作与办公效率。", encoding="utf-8")

    with patch("batch_api.call_llm_async", new_callable=AsyncMock, return_value="AI,内容创作,办公效率"):
        task = create_task(
            "batch_process",
            {
                "task": "keywords",
                "files": [{"path": str(doc_path), "filename": "doc.txt", "size": 30}],
                "user_id": "u-dana",
            },
            username="dana",
            user_id="u-dana",
            role="user",
        )
        claim_and_run(task["id"])
        t = get_task(task["id"])
        assert t["status"] == "success"
        assert t["result"]["task"] == "keywords"
        assert t["result"]["results"][0]["result"] == "AI,内容创作,办公效率"


# ── 5. jobs 列表用户隔离 ───────────────────────────────────


def test_batch_jobs_isolation(setup_test_db):
    """处理记录隔离：普通用户仅见自己的，admin 全量。"""
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO batch_jobs (id, task_type, file_count, results, status, user_id, created_at) VALUES (?,?,?,?,?,?,?)",
            ("j-a", "summarize", 1, "{}", "done", "u-a", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO batch_jobs (id, task_type, file_count, results, status, user_id, created_at) VALUES (?,?,?,?,?,?,?)",
            ("j-b", "translate", 2, "{}", "done", "u-b", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()

    alice_rows = asyncio.run(batch_api.list_jobs(_user("u-a", "alice")))
    assert len(alice_rows) == 1 and alice_rows[0]["id"] == "j-a"

    bob_rows = asyncio.run(batch_api.list_jobs(_user("u-b", "bob")))
    assert len(bob_rows) == 1 and bob_rows[0]["id"] == "j-b"

    admin_rows = asyncio.run(batch_api.list_jobs(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 2


# ── 6. POST 端点：异步返回 task_id / sync 兼容 ─────────────


def test_batch_post_endpoints_creates_task(setup_test_db):
    """三端点默认返回 task_id（不再同步阻塞）。"""
    resp = asyncio.run(
        batch_api.batch_translate(
            batch_api.BatchTextRequest(texts=["你好"]),
            current_user=_user("u1", "alice"),
        )
    )
    assert resp["ok"] is True and resp["task_id"].startswith("task_")

    resp = asyncio.run(
        batch_api.batch_process(
            files=[],
            task="summarize",
            current_user=_user("u1", "alice"),
        )
    )
    assert resp["ok"] is False  # 无文件 → 直接返回错误


def test_batch_translate_sync_mode(setup_test_db):
    """sync=1 直接执行，返回完整结果（兼容旧调用）。"""
    with patch("batch_api.call_llm_async", new_callable=AsyncMock, return_value="Translated"):
        resp = asyncio.run(
            batch_api.batch_translate(
                batch_api.BatchTextRequest(texts=["原文"]),
                True,
                _user("u1", "alice"),
            )
        )
    assert resp["count"] == 1
    assert resp["results"][0]["translated"] == "Translated"
