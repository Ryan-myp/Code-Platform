"""自进化闭环 v1（v18 P1）：结构闸 + 指标接地 + 版本化发布/回滚。"""

import datetime

from fastapi.testclient import TestClient


def _seed_version(module: str, instructions: str, status: str = "candidate", when: str = "") -> int:
    from common.db import get_db

    conn = get_db()
    conn.execute(
        "ALTER TABLE prompt_versions ADD COLUMN status TEXT DEFAULT 'candidate'"
        if not any(r["name"] == "status" for r in conn.execute("PRAGMA table_info(prompt_versions)").fetchall())
        else "SELECT 1",
    )
    cur = conn.execute(
        "INSERT INTO prompt_versions (module, version, instructions, optimized_at, created_by, status) "
        "VALUES (?,?,?,?,'system',?)",
        (module, 1, instructions, when or datetime.datetime.now().isoformat(), status),
    )
    conn.commit()
    vid = cur.lastrowid
    conn.close()
    return vid


def test_schema_migration_idempotent(setup_test_db):
    import prd_engine

    prd_engine._ensure_prompt_version_schema(__import__("common.db", fromlist=["get_db"]).get_db())
    prd_engine._ensure_prompt_version_schema(__import__("common.db", fromlist=["get_db"]).get_db())  # 两次不报错


def test_gate_placeholder_preservation(setup_test_db):
    import prd_engine

    ref = "请写 {report_type} 汇报，汇报人 {author}，控制在 {limit} 字"
    assert prd_engine._prompt_gate("同样的长提示词" * 5, ref)["ok"] is False, "丢占位符必须拦截"
    ok = "请写 {report_type} 汇报，汇报人 {author}，控制在 {limit} 字，突出数据"
    assert prd_engine._prompt_gate(ok, ref)["ok"] is True
    assert prd_engine._prompt_gate("太短", ref)["ok"] is False, "过短必须拦截"


def test_optimize_publishes_when_gate_passes(setup_test_db, monkeypatch):
    """候选保留占位符 + 足够长 → 自动 published。"""
    import prd_engine

    _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果")

    captured = {}

    def fake_llm(system, user, **kw):
        captured["user"] = user
        return "优化后的提示词：请写 {report_type} 汇报，控制在 {limit} 字，突出成果与数据，语言精炼专业。"

    monkeypatch.setattr(prd_engine, "call_llm", fake_llm)

    from main import app

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "published", f"过闸应自动发布：{body}"
    assert body["gate"]["ok"] is True


def test_optimize_holds_candidate_when_gate_fails(setup_test_db, monkeypatch):
    """候选丢占位符 → 留 candidate（诚实降级，不发布坏版本）。"""
    import prd_engine

    _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果")
    monkeypatch.setattr(prd_engine, "call_llm", lambda s, u, **kw: "全新提示词" * 10)

    from main import app

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "candidate"
    assert res.json()["gate"]["ok"] is False


def test_metrics_digest_injected_into_prompt(setup_test_db, monkeypatch):
    """可靠性指标接地：错误分布摘要进优化 prompt。"""
    import common.metrics as metrics
    import prd_engine

    _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果")

    async def _noop(*a, **k):  # pragma: no cover
        pass

    captured = {}

    def fake_llm(system, user, **kw):
        captured["user"] = user
        return "优化后的提示词：请写 {report_type} 汇报，控制在 {limit} 字，突出成果与数据，语言精炼专业。"

    monkeypatch.setattr(
        metrics, "summarize",
        lambda days=7: {"error_classes": {"transient": 3, "content": 1}, "latency": {"llm": {"p95_ms": 8200.0}}},
    )
    monkeypatch.setattr(prd_engine, "call_llm", fake_llm)

    from main import app

    TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"})
    assert "transient" in captured.get("user", ""), "错误分布应注入优化上下文"
    assert "8200.0" in captured.get("user", ""), "p95 延迟应注入优化上下文"


def test_rollback_republishes_history(setup_test_db):
    """回滚：旧版本重新 published，当前 published 标记 rolled_back（审计链保留）。"""
    old = _seed_version("report", "旧版好提示词" * 8, status="rolled_back", when="2024-01-01T00:00:00")
    new = _seed_version("report", "新版提示词" * 10, status="published", when="2025-01-01T00:00:00")

    from main import app

    res = TestClient(app).post(f"/api/evolution/prompt-versions/{old}/rollback")
    assert res.status_code == 200, res.text
    assert res.json()["published_id"] == old

    from common.db import get_db

    conn = get_db()
    st = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM prompt_versions").fetchall()}
    conn.close()
    assert st[old] == "published" and st[new] == "rolled_back"


def test_publish_rejected_when_gate_fails(setup_test_db):
    """手动发布也过结构闸：对基准版本缺占位符 → 400。"""
    base = _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果与数据，便于团队评审",
                         status="published", when="2024-01-01T00:00:00")
    bad = _seed_version("report", "全新提示词" * 12, when="2025-06-01T00:00:00")

    from main import app

    res = TestClient(app).post(f"/api/evolution/prompt-versions/{bad}/publish")
    assert res.status_code == 400, f"缺占位符应被结构闸拦截：{res.text}"
    res2 = TestClient(app).post(f"/api/evolution/prompt-versions/{base}/publish")
    assert res2.status_code == 200, "对自身无缺失占位符（基准=排除自身后取上一版）可发布"
