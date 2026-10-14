"""v18.2 指标归因（ref/contextvars）+ 工具输出截断治理 + by-agent 端点。"""



def test_record_includes_ref_from_context(setup_test_db):
    """set_ref 后 record 自动带 ref（contextvars 继承，无需逐层透传）。"""
    import common.metrics as metrics
    from common.db import get_db

    tok = metrics.set_ref("agent:a_42")
    try:
        metrics.record("llm", "ok", 120, detail="model=x")
    finally:
        metrics._ctx_ref.reset(tok)

    conn = get_db()
    row = conn.execute("SELECT ref FROM metrics_events WHERE kind='llm' ORDER BY id DESC LIMIT 1").fetchone()
    assert row["ref"] == "agent:a_42", dict(row)
    conn.close()

    # 未 set_ref 的路径 ref 为空（兼容）
    metrics.record("llm", "ok", 50, detail="model=y")
    conn = get_db()
    row2 = conn.execute("SELECT ref FROM metrics_events WHERE detail='model=y' ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row2["ref"] == ""


def test_truncate_for_context_marker_and_metrics(setup_test_db, monkeypatch):
    """超限输出：截断 + 明示总量 + 记 degraded/content 指标。"""
    import agent_runtime as runtime

    events = []
    import common.metrics as metrics

    monkeypatch.setattr(metrics, "record", lambda *a, **k: events.append((a, k)))

    long_out = "x" * 10000
    out = runtime._truncate_for_context(long_out, "tool:big")
    assert len(out) <= runtime._MAX_TOOL_RESULT + 100, "截断后不得远超上限"
    assert "已截断" in out and "10000" in out, "必须明示总长（诚实降级）"
    assert events, "截断必须记指标"

    short = runtime._truncate_for_context("ok", "tool:small")
    assert short == "ok", "未超限不处理"
    assert len(events) == 1


def test_by_agent_admin_endpoint(setup_test_db, auth_headers, monkeypatch):
    """by-agent 端点：usage_logs.agent_id + metrics_events.ref 双口径聚合。"""
    from common.db import get_db

    conn = get_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(usage_logs)").fetchall()}
    if "agent_id" not in cols:
        conn.execute("ALTER TABLE usage_logs ADD COLUMN agent_id TEXT DEFAULT ''")
    conn.execute(
        "INSERT INTO usage_logs (timestamp, task_type, input_length, output_length, response_time, success, agent_id) "
        "VALUES (datetime('now','localtime'), 'agent_run', 100, 200, 2.5, 1, 'a_1')",
    )
    import time as _time

    import common.metrics as metrics

    metrics._ensure_table(conn)
    mc = {r["name"] for r in conn.execute("PRAGMA table_info(metrics_events)").fetchall()}
    if "ref" not in mc:
        conn.execute("ALTER TABLE metrics_events ADD COLUMN ref TEXT DEFAULT ''")
    conn.execute(
        "INSERT INTO metrics_events (ts, kind, outcome, ref) VALUES (?, 'llm', 'ok', 'agent:a_1')",
        (_time.time(),),
    )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient

    from main import app

    # 端点要求 admin 用户
    res = TestClient(app).get("/api/admin/metrics/by-agent?days=7", headers=auth_headers)
    if res.status_code == 403:
        # 非 admin 用户 → 提权
        c2 = get_db()
        c2.execute("UPDATE users SET role='admin' WHERE 1")
        c2.commit()
        c2.close()
        res = TestClient(app).get("/api/admin/metrics/by-agent?days=7", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["usage_by_agent"], "usage 口径应有数据"
    assert any(r["agent_id"] == "a_1" for r in body["usage_by_agent"]), body
    assert any(r["ref"] == "agent:a_1" for r in body["reliability_by_ref"]), body
