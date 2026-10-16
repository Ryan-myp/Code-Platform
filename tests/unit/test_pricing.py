"""v18.3 模型成本估算。"""


def test_estimate_cost_known_and_unknown_model(setup_test_db):
    from common.pricing import estimate_cost, is_priced

    assert is_priced("gpt-4o") and not is_priced("not_a_model")
    # 1000 字符 ≈ 667 tokens；gpt-4o: 667*0.005/1000 ≈ 0.0033
    c = estimate_cost("gpt-4o", 1000, 0)
    assert 0.003 < c < 0.004, c
    # 未知模型走 fallback 中档价（不为 0，避免成本假象）
    assert estimate_cost("not_a_model", 1000, 1000) > 0
    # 空调用 0 成本
    assert estimate_cost("gpt-4o", 0, 0) == 0.0


def test_log_usage_records_cost_est(setup_test_db):
    from common.db import get_db
    from common.llm import log_usage

    log_usage("agent_run", 2000, 500, 1.2, agent_id="a_9", model="gpt-4o")
    conn = get_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(usage_logs)").fetchall()}
    row = conn.execute("SELECT model, cost_est FROM usage_logs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert "cost_est" in cols and row["model"] == "gpt-4o"
    assert row["cost_est"] > 0, "有模型时 cost_est 必须 > 0"

    # 无模型 → cost_est = 0（兼容旧调用点）
    log_usage("agent_run", 100, 50, 0.5, agent_id="a_9")
    conn = get_db()
    row2 = conn.execute("SELECT cost_est FROM usage_logs ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row2["cost_est"] == 0


def test_by_agent_includes_cost_est(setup_test_db, auth_headers):
    from common.db import get_db
    from common.llm import log_usage

    log_usage("agent_run", 2000, 500, 1.2, agent_id="a_cost", model="gpt-4o")

    from main import app

    from fastapi.testclient import TestClient

    res = TestClient(app).get("/api/admin/metrics/by-agent?days=7", headers=auth_headers)
    if res.status_code == 403:
        conn = get_db()
        conn.execute("UPDATE users SET role='admin' WHERE 1")
        conn.commit()
        conn.close()
        res = TestClient(app).get("/api/admin/metrics/by-agent?days=7", headers=auth_headers)
    assert res.status_code == 200, res.text
    row = next(r for r in res.json()["usage_by_agent"] if r["agent_id"] == "a_cost")
    assert row["cost_est_usd"] > 0, row
