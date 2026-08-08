"""AI 工坊商业化升级验证。

覆盖：
- 5 大工坊工具（文档问答/思维导图/联网搜索/数据预测/视频理解）：
  POST 创建异步任务（task_id）→ handler 执行 → 记录落库（带 user_id）
- 历史接口用户隔离：普通用户仅见自己的记录，admin 全量；删除/详情归属校验
- 上传接口带用户归属
"""

import asyncio
import csv
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

import data_forecast
import doc_qa
import mindmap
import video_analyzer
import web_search
from task_queue import _handlers, create_task, get_task


def _user(uid: str, name: str, role: str = "user") -> dict:
    return {"user_id": uid, "username": name, "role": role}


@pytest.fixture(autouse=True)
def _init_workshop_tables(setup_test_db):
    """在临时库中重建 AI 工坊表（各模块 init_db 仅在首次 import 时执行一次）。"""
    doc_qa.init_db()
    mindmap.init_db()
    web_search.init_db()
    data_forecast.init_db()
    video_analyzer.init_db()


# ── 1. handler 注册 ────────────────────────────────────────


def test_ai_workshop_handlers_registered(setup_test_db):
    """五大工坊的异步任务处理器必须已注册。"""
    missing = {"docqa_ask", "mindmap_generate", "web_search_query", "forecast_analyze", "video_analyze"} - set(
        _handlers
    )
    assert not missing, f"未注册的任务类型: {missing}"


# ── 2. 文档问答 ────────────────────────────────────────────


def _seed_doc(conn, did: str, user_id: str, text: str = "产品说明书内容") -> None:
    conn.execute(
        "INSERT INTO doc_qa_records (id, filename, filepath, file_size, text_content, text_length, summary, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (did, "说明.pdf", f"/tmp/{did}.pdf", 1024, text, len(text), "{}", "ready", user_id, "2026-01-01T00:00:00"),
    )


def test_docqa_async_flow(setup_test_db, claim_and_run):
    """文档问答：异步任务执行后返回答案（RAG 上下文）。"""
    from common.db import get_db

    conn = get_db()
    try:
        _seed_doc(conn, "doc-alice", "u-alice")
        conn.commit()
    finally:
        conn.close()

    with patch("doc_qa.call_llm_async", new_callable=AsyncMock, return_value="根据文档，该产品支持远程升级。"):
        task = create_task(
            "docqa_ask",
            {"doc_id": "doc-alice", "question": "支持远程升级吗？", "user_id": "u-alice"},
            username="alice",
            user_id="u-alice",
            role="user",
        )
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"

    conn = get_db()
    try:
        # 问答不落新表，仅任务成功；文档记录仍归属 alice
        row = conn.execute("SELECT user_id FROM doc_qa_records WHERE id='doc-alice'").fetchone()
        assert row[0] == "u-alice"
    finally:
        conn.close()


def test_docqa_records_isolation(setup_test_db):
    """文档记录列表隔离 + 删除归属校验。"""
    from common.db import get_db

    conn = get_db()
    try:
        _seed_doc(conn, "doc-a", "u-a")
        _seed_doc(conn, "doc-b", "u-b")
        conn.commit()
    finally:
        conn.close()

    # alice 仅见自己的记录
    alice_rows = asyncio.run(doc_qa.list_records(_user("u-a", "alice")))
    assert len(alice_rows) == 1 and alice_rows[0]["id"] == "doc-a"

    # admin 全量
    admin_rows = asyncio.run(doc_qa.list_records(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 2

    # alice 删除 bob 的记录 → 不生效（归属校验拒绝）
    with pytest.raises(HTTPException) as exc:
        asyncio.run(doc_qa.delete_record("doc-b", _user("u-a", "alice")))
    assert exc.value.status_code == 404
    admin_rows = asyncio.run(doc_qa.list_records(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 2

    # alice 删除自己的记录 → 生效
    asyncio.run(doc_qa.delete_record("doc-a", _user("u-a", "alice")))
    admin_rows = asyncio.run(doc_qa.list_records(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 1


# ── 3. 思维导图 ────────────────────────────────────────────

_MINDMAP_JSON = json.dumps(
    {
        "title": "AI 商业化",
        "description": "概述",
        "root": {
            "name": "AI 商业化",
            "color": "#667eea",
            "children": [
                {"name": "产品", "color": "#4A90D9", "children": [{"name": "订阅制", "children": []}]},
            ],
        },
    },
    ensure_ascii=False,
)


def test_mindmap_async_flow(setup_test_db, claim_and_run):
    """思维导图：异步任务 → LLM 树结构 → 记录落库（带用户归属）。"""
    with patch("mindmap.call_llm", return_value=_MINDMAP_JSON):
        task = create_task(
            "mindmap_generate",
            {"topic": "AI 商业化", "depth": 3, "style": "business", "user_id": "u-dana"},
            username="dana",
            user_id="u-dana",
            role="user",
        )
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"

    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM mindmap_records").fetchall()
        assert len(rows) == 1
        assert rows[0]["user_id"] == "u-dana"
        result = json.loads(rows[0]["result"])
        assert result["title"] == "AI 商业化"
    finally:
        conn.close()


def test_mindmap_records_isolation(setup_test_db, claim_and_run):
    """思维导图记录隔离 + 删除归属校验。"""
    with patch("mindmap.call_llm", return_value=_MINDMAP_JSON):
        for uid, name in (("u-a", "alice"), ("u-b", "bob")):
            task = create_task(
                "mindmap_generate",
                {"topic": f"主题{uid}", "depth": 2, "style": "professional", "user_id": uid},
                username=name,
                user_id=uid,
                role="user",
            )
            claim_and_run(task["id"])

    alice_rows = asyncio.run(mindmap.list_records(_user("u-a", "alice")))
    assert len(alice_rows) == 1
    admin_rows = asyncio.run(mindmap.list_records(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 2

    # alice 删除 bob 的记录 → 不生效（归属校验拒绝）
    bob_rows = asyncio.run(mindmap.list_records(_user("u-b", "bob")))
    bob_id = bob_rows[0]["id"]
    with pytest.raises(HTTPException) as exc:
        asyncio.run(mindmap.delete_record(bob_id, _user("u-a", "alice")))
    assert exc.value.status_code == 404
    admin_rows = asyncio.run(mindmap.list_records(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 2

    # alice 删除自己的 → 生效
    alice_id = asyncio.run(mindmap.list_records(_user("u-a", "alice")))[0]["id"]
    asyncio.run(mindmap.delete_record(alice_id, _user("u-a", "alice")))
    admin_rows = asyncio.run(mindmap.list_records(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 1


# ── 4. 联网搜索 ────────────────────────────────────────────


def test_web_search_async_flow(setup_test_db, claim_and_run):
    """联网搜索：多源结果 → AI 摘要 → 历史入库（带用户归属）。"""
    fake_results = [
        {
            "title": "AI 行业报告",
            "snippet": "2026 年 AI 市场规模达万亿",
            "url": "https://a.example",
            "source": "DuckDuckGo",
        },
        {
            "title": "AI 商业化案例",
            "snippet": "头部企业商业化路径分析",
            "url": "https://b.example",
            "source": "DuckDuckGo",
        },
    ]
    with (
        patch("web_search._search_ddg", return_value=fake_results),
        patch("web_search.call_llm_async", new_callable=AsyncMock, return_value="2026 年 AI 市场持续增长，头部企业加速商业化。"),
    ):
        task = create_task(
            "web_search_query",
            {"query": "AI 商业化趋势", "num_results": 5, "user_id": "u-eve"},
            username="eve",
            user_id="u-eve",
            role="user",
        )
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"

    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM search_history").fetchall()
        assert len(rows) == 1
        assert rows[0]["user_id"] == "u-eve"
        assert rows[0]["query"] == "AI 商业化趋势"
    finally:
        conn.close()

    # 历史接口隔离
    eve_rows = asyncio.run(web_search.search_history(_user("u-eve", "eve")))
    assert len(eve_rows) == 1
    other_rows = asyncio.run(web_search.search_history(_user("u-x", "xavier")))
    assert len(other_rows) == 0
    admin_rows = asyncio.run(web_search.search_history(_user("admin", "admin", role="admin")))
    assert len(admin_rows) == 1


# ── 5. 数据预测 ────────────────────────────────────────────


def _seed_forecast(conn, did: str, user_id: str, csv_path: str) -> None:
    conn.execute(
        "INSERT INTO forecast_records (id, filename, filepath, row_count, columns, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (did, "sales.csv", csv_path, 3, '["month", "sales"]', "uploaded", user_id, "2026-01-01T00:00:00"),
    )


_FORECAST_JSON = json.dumps(
    {
        "overview": {
            "record_count": 3,
            "columns": ["month", "sales"],
            "data_quality": "A",
            "summary": "销售额逐月上升",
        },
        "statistics": {"columns": []},
        "trend_analysis": {
            "overall_trend": "上升",
            "seasonal_patterns": "",
            "anomalies": [],
            "correlations": [],
            "key_findings": ["销售额上升"],
        },
        "predictions": {
            "method": "趋势外推",
            "short_term": {"description": "下季度 +10%", "confidence": "中"},
            "medium_term": {},
            "forecast_values": [],
            "risks": [],
        },
        "recommendations": [
            {"priority": 1, "level": "重要", "action": "加大投放", "expected_impact": "营收 +15%", "timeline": "Q3"}
        ],
        "charts": {
            "labels": ["1月", "2月", "3月"],
            "actual": [100, 120, 115],
            "forecast": [],
            "trend_line": [],
            "upper_bound": [],
            "lower_bound": [],
        },
    },
    ensure_ascii=False,
)


def test_forecast_async_flow(setup_test_db, claim_and_run, tmp_path):
    """数据预测：异步任务 → 统计+AI 分析 → 记录落库（带用户归属）。"""
    csv_path = tmp_path / "sales.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "sales"])
        w.writerow(["1月", 100])
        w.writerow(["2月", 120])
        w.writerow(["3月", 115])

    from common.db import get_db

    conn = get_db()
    try:
        _seed_forecast(conn, "data-1", "u-frank", str(csv_path))
        conn.commit()
    finally:
        conn.close()

    with patch("data_forecast.call_llm", return_value=_FORECAST_JSON):
        task = create_task(
            "forecast_analyze",
            {"data_id": "data-1", "target_column": "sales", "forecast_periods": 3, "user_id": "u-frank"},
            username="frank",
            user_id="u-frank",
            role="user",
        )
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"

    conn = get_db()
    try:
        row = conn.execute("SELECT analysis, status, user_id FROM forecast_records WHERE id='data-1'").fetchone()
        assert row[1] == "done"
        assert row[2] == "u-frank"
        result = json.loads(row[0])
        assert result["overview"]["record_count"] == 3
    finally:
        conn.close()

    # 记录列表隔离 + 详情归属
    frank_rows = asyncio.run(data_forecast.list_records(_user("u-frank", "frank")))
    assert len(frank_rows) == 1
    assert asyncio.run(data_forecast.list_records(_user("u-x", "xavier"))) == []

    detail = asyncio.run(data_forecast.get_record("data-1", _user("u-frank", "frank")))
    assert detail["status"] == "done"

    # 越权读 → 404
    with pytest.raises(HTTPException) as exc:
        asyncio.run(data_forecast.get_record("data-1", _user("u-x", "xavier")))
    assert exc.value.status_code == 404


# ── 6. 视频理解 ────────────────────────────────────────────


def _seed_video(conn, vid: str, user_id: str) -> None:
    conn.execute(
        "INSERT INTO video_records (id, filename, filepath, file_size, description, status, user_id, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (vid, "demo.mp4", f"/tmp/{vid}.mp4", 2048, "产品演示", "uploaded", user_id, "2026-01-01T00:00:00"),
    )


_VIDEO_JSON = json.dumps(
    {
        "title": "产品演示视频",
        "summary": "展示核心功能",
        "detailed_summary": "开头展示痛点，中间演示功能，结尾 CTA",
        "key_scenes": [
            {"timestamp": "00:05", "description": "痛点引入", "importance": "高", "why_important": "决定留存"}
        ],
        "topics": ["效率工具", "AI"],
        "tone": "轻松",
        "target_audience": "职场人群",
        "highlights": ["真实场景演示"],
        "subtitles_text": "大家好，今天演示……",
        "recommendations": ["前 3 秒加钩子"],
    },
    ensure_ascii=False,
)


def test_video_async_flow(setup_test_db, claim_and_run):
    """视频理解：异步任务 → AI 分析 → 记录落库（带用户归属）。"""
    from common.db import get_db

    conn = get_db()
    try:
        _seed_video(conn, "vid-1", "u-gina")
        conn.commit()
    finally:
        conn.close()

    with patch("video_analyzer.call_llm", return_value=_VIDEO_JSON):
        task = create_task(
            "video_analyze",
            {"video_id": "vid-1", "description": "产品演示", "user_id": "u-gina"},
            username="gina",
            user_id="u-gina",
            role="user",
        )
        claim_and_run(task["id"])
        assert get_task(task["id"])["status"] == "success"

    conn = get_db()
    try:
        row = conn.execute("SELECT analysis, status, user_id FROM video_records WHERE id='vid-1'").fetchone()
        assert row[1] == "done"
        assert row[2] == "u-gina"
        result = json.loads(row[0])
        assert result["summary"] == "展示核心功能"
    finally:
        conn.close()

    # 记录隔离 + 越权删除
    gina_rows = asyncio.run(video_analyzer.list_records(_user("u-gina", "gina")))
    assert len(gina_rows) == 1
    assert asyncio.run(video_analyzer.list_records(_user("u-x", "xavier"))) == []

    with pytest.raises(HTTPException) as exc:
        asyncio.run(video_analyzer.delete_record("vid-1", _user("u-x", "xavier")))
    assert exc.value.status_code == 404
    gina_rows = asyncio.run(video_analyzer.list_records(_user("u-gina", "gina")))
    assert len(gina_rows) == 1

    # 本人删除生效
    asyncio.run(video_analyzer.delete_record("vid-1", _user("u-gina", "gina")))
    assert asyncio.run(video_analyzer.list_records(_user("u-gina", "gina"))) == []


# ── 7. POST 端点返回 task_id ───────────────────────────────


def test_workshop_post_endpoints_creates_task(setup_test_db):
    """五模块 POST 接口直接返回 task_id（不再同步阻塞）。"""
    resp = asyncio.run(
        doc_qa.ask_document(
            doc_qa.AskRequest(doc_id="doc-x", question="问"),
            _user("u1", "alice"),
        )
    )
    assert resp["ok"] is True and resp["task_id"].startswith("task_")

    resp = asyncio.run(
        mindmap.generate_mindmap(
            mindmap.MindMapRequest(topic="主题"),
            _user("u1", "alice"),
        )
    )
    assert resp["ok"] is True and resp["task_id"].startswith("task_")

    resp = asyncio.run(
        web_search.web_search(
            web_search.WebSearchRequest(query="查询"),
            _user("u1", "alice"),
        )
    )
    assert resp["ok"] is True and resp["task_id"].startswith("task_")

    resp = asyncio.run(
        data_forecast.analyze_data(
            data_forecast.AnalyzeRequest(data_id="data-x"),
            _user("u1", "alice"),
        )
    )
    assert resp["ok"] is True and resp["task_id"].startswith("task_")

    resp = asyncio.run(
        video_analyzer.analyze_video(
            video_analyzer.AnalyzeRequest(video_id="vid-x"),
            _user("u1", "alice"),
        )
    )
    assert resp["ok"] is True and resp["task_id"].startswith("task_")
