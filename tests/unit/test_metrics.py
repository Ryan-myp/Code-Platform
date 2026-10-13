"""可靠性指标层（common/metrics + LLM/工具/MCP 挂点 + 管理端点）。

锁定行为：
- record 失败静默（指标永不阻断主流程）
- 30 天滚动保留
- summarize 聚合：kind×outcome 计数 / 五类错误分布 / 延迟 avg/p50/p95
- LLM 调用挂点：成功记 ok + 失败记 error（状态码分类）
- 工具执行挂点：降级结果记 degraded
- MCP 调用挂点：失败记 error
- /api/admin/metrics/reliability 需 admin，非 admin 403
"""

import time

from common import metrics


def test_record_and_summarize(setup_test_db):
    for i in range(10):
        metrics.record("llm", "ok", latency_ms=100 + i * 10, detail="model=test")
    metrics.record("llm", "error", latency_ms=50, err_class="transient", detail="model=test status=503")
    metrics.record("tool", "degraded", detail="tool=nope")
    metrics.record("mcp", "error", err_class="unknown", detail="tool=x")

    s = metrics.summarize(days=7)
    assert s["total_events"] == 13
    assert s["by_kind"]["llm"] == {"ok": 10, "error": 1, "degraded": 0}
    assert s["by_kind"]["tool"]["degraded"] == 1
    assert s["error_classes"]["transient"] == 1
    assert s["latency"]["llm"]["avg_ms"] > 100
    assert s["latency"]["llm"]["p95_ms"] >= s["latency"]["llm"]["p50_ms"]
    # 最近错误含分类
    kinds = {r["kind"] for r in s["recent_errors"]}
    assert "llm" in kinds and "mcp" in kinds


def test_record_silent_on_bad_input(setup_test_db):
    """非法 kind/outcome 归一而非报错；detail 截断。"""
    metrics.record("不存在的kind", "不存在的outcome", detail="x" * 1000)
    conn = metrics._conn()
    row = conn.execute(
        "SELECT kind, outcome, detail FROM metrics_events ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row["kind"] == "workflow"  # 未知 kind 归一
    assert row["outcome"] == "degraded"
    assert len(row["detail"]) <= 300


def test_retention_30d(setup_test_db):
    """30 天前的事件被清掉。"""
    import common.db

    metrics.record("llm", "ok", detail="seed")  # 先建表（幂等 DDL）
    conn = common.db.get_db()
    old_ts = time.time() - 40 * 86400
    conn.execute(
        "INSERT INTO metrics_events (ts, kind, outcome, err_class, latency_ms, detail) VALUES (?,?,?,?,?,?)",
        (old_ts, "llm", "ok", "", 5.0, "old"),
    )
    conn.commit()
    conn.close()
    metrics.record("llm", "ok", detail="new")
    conn = common.db.get_db()
    n_old = conn.execute("SELECT COUNT(*) AS c FROM metrics_events WHERE ts < ?", (old_ts + 1,)).fetchone()["c"]
    conn.close()
    assert n_old == 0, "30 天滚动保留：旧事件应被清理"


def test_llm_hook_records(setup_test_db, monkeypatch):
    """LLM 挂点：_call_one_sync 成功记 ok，非 200 记 error + 状态分类。"""
    import requests
    from fastapi import HTTPException

    import common.llm

    captured = []
    real_record = metrics.record

    def spy(kind, outcome, latency_ms=None, err_class="", detail="", **kw):
        captured.append((kind, outcome, {"latency_ms": latency_ms, "err_class": err_class, "detail": detail}))
        return real_record(kind, outcome, latency_ms, err_class, detail, **kw)

    monkeypatch.setattr(metrics, "record", spy)
    cfg = {"api_key": "k", "api_base": "http://invalid.test", "model": "m1", "name": "t"}
    monkeypatch.setattr(common.llm, "get_model_config", lambda mname=None: cfg)

    # 成功路径：伪造 requests.post 返回 200
    class FakeResp:
        status_code = 200
        text = ""
        def json(self):
            return {"choices": [{"message": {"content": "hi"}}]}

    monkeypatch.setattr(requests, "post", lambda *a, **kw: FakeResp())
    out = common.llm.call_llm("s", "u", model="default", max_tokens=10)
    assert "hi" in out
    assert ("llm", "ok") in [ (c[0], c[1]) for c in captured ]

    # 失败路径：503
    class BadResp:
        status_code = 503
        text = "busy"
        def json(self):
            raise ValueError("no json")

    captured.clear()
    monkeypatch.setattr(requests, "post", lambda *a, **kw: BadResp())
    try:
        common.llm.call_llm("s", "u", model="default", max_tokens=10, retries=0)
    except HTTPException:
        pass
    llm_events = [c for c in captured if c[0] == "llm"]
    assert llm_events and llm_events[0][1] == "error"
    assert llm_events[0][2].get("err_class") == "transient"  # 503 → transient


def test_tool_hook_degraded(setup_test_db):
    """工具挂点：未知工具 → 降级结果记 degraded。"""
    import asyncio

    import agent_runtime

    out = asyncio.run(agent_runtime.execute_tool_async("not_a_real_tool_x", "x"))
    assert "不存在" in out
    conn = metrics._conn()
    row = conn.execute(
        "SELECT outcome FROM metrics_events WHERE kind='tool' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row["outcome"] == "degraded"


def test_mcp_hook_error(setup_test_db):
    """MCP 挂点：不可达本地端口 → 失败结果记 error。"""
    import asyncio

    import mcp_client

    server = {"id": "srv-local", "name": "local", "transport_type": "http", "url": "http://127.0.0.1:9/"}
    out = asyncio.run(mcp_client.mcp_call_tool(server, "t", {}))
    assert "失败" in out or "异常" in out or "连接被拒" in out or "无响应" in out
    conn = metrics._conn()
    row = conn.execute(
        "SELECT outcome FROM metrics_events WHERE kind='mcp' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row["outcome"] in ("error", "degraded")


def test_reliability_endpoint_admin_only(setup_test_db, auth_headers):
    from fastapi.testclient import TestClient

    import auth as auth_mod
    import common.metrics as metrics
    from common.auth import create_access_token
    from main import app

    metrics.record("llm", "error", err_class="auth", detail="model=x status=401")
    client = TestClient(app)
    res = client.get(
        "/api/admin/metrics/reliability",
        headers=auth_headers,
        params={"days": 7},
    )
    assert res.status_code == 200
    body = res.json()
    assert "by_kind" in body and "error_classes" in body and "recent_errors" in body
    assert body["window_days"] == 7
    assert body["error_classes"].get("auth") == 1

    # 非 admin 用户 → 403
    u = auth_mod.create_user("m-rel-n", "m-rel-p", role="user")
    token = create_access_token(u["username"], {"user_id": u["id"], "role": u["role"]})
    bad = client.get(
        "/api/admin/metrics/reliability", headers={"Authorization": f"Bearer {token}"}
    )
    assert bad.status_code == 403
