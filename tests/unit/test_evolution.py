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


def test_optimize_publishes_when_gate_passes(setup_test_db, monkeypatch, auth_headers):
    """候选保留占位符 + 足够长 → 自动 published。"""
    import prd_engine

    _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果")

    captured = {}

    def fake_llm(system, user, **kw):
        captured["user"] = user
        return "优化后的提示词：请写 {report_type} 汇报，控制在 {limit} 字，突出成果与数据，语言精炼专业。"

    monkeypatch.setattr(prd_engine, "call_llm", fake_llm)

    from main import app

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "published", f"过闸应自动发布：{body}"
    assert body["gate"]["ok"] is True


def test_optimize_holds_candidate_when_gate_fails(setup_test_db, monkeypatch, auth_headers):
    """候选丢占位符 → 留 candidate（诚实降级，不发布坏版本）。"""
    import prd_engine

    _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果")
    monkeypatch.setattr(prd_engine, "call_llm", lambda s, u, **kw: "全新提示词" * 10)

    from main import app

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "candidate"
    assert res.json()["gate"]["ok"] is False


def test_metrics_digest_injected_into_prompt(setup_test_db, monkeypatch, auth_headers):
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

    TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"}, headers=auth_headers)
    assert "transient" in captured.get("user", ""), "错误分布应注入优化上下文"
    assert "8200.0" in captured.get("user", ""), "p95 延迟应注入优化上下文"


def test_rollback_republishes_history(setup_test_db, auth_headers):
    """回滚：旧版本重新 published，当前 published 标记 rolled_back（审计链保留）。"""
    old = _seed_version("report", "旧版好提示词" * 8, status="rolled_back", when="2024-01-01T00:00:00")
    new = _seed_version("report", "新版提示词" * 10, status="published", when="2025-01-01T00:00:00")

    from main import app

    res = TestClient(app).post(f"/api/evolution/prompt-versions/{old}/rollback", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["published_id"] == old

    from common.db import get_db

    conn = get_db()
    st = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM prompt_versions").fetchall()}
    conn.close()
    assert st[old] == "published" and st[new] == "rolled_back"


def test_publish_rejected_when_gate_fails(setup_test_db, auth_headers):
    """手动发布也过结构闸：对基准版本缺占位符 → 400。"""
    base = _seed_version("report", "请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果与数据，便于团队评审",
                         status="published", when="2024-01-01T00:00:00")
    bad = _seed_version("report", "全新提示词" * 12, when="2025-06-01T00:00:00")

    from main import app

    res = TestClient(app).post(f"/api/evolution/prompt-versions/{bad}/publish", headers=auth_headers)
    assert res.status_code == 400, f"缺占位符应被结构闸拦截：{res.text}"
    res2 = TestClient(app).post(f"/api/evolution/prompt-versions/{base}/publish", headers=auth_headers)
    assert res2.status_code == 200, "对自身无缺失占位符（基准=排除自身后取上一版）可发布"


def test_evolution_endpoints_require_auth(setup_test_db):
    """evolution 端点必须鉴权（防匿名烧 LLM / 污染版本库）。"""
    from main import app

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "x"})
    assert res.status_code == 401, f"无 token 应 401：{res.status_code} {res.text[:100]}"
    res2 = TestClient(app).get("/api/evolution/prompt-history")
    assert res2.status_code == 401, "prompt-history 也应鉴权"


def test_evaluate_prompt_scores_cases(setup_test_db, monkeypatch, auth_headers):
    """v18.2：评测集打分——keywords 命中/未命中各算对。"""
    import prd_engine
    from main import app

    client = TestClient(app)
    client.post("/api/evolution/eval-cases", headers=auth_headers,
                json={"module": "report", "input": "写个周报", "pass_criteria": {"keywords": ["完成", "下周"]}})
    client.post("/api/evolution/eval-cases", headers=auth_headers,
                json={"module": "report", "input": "写个月报", "pass_criteria": {"keywords": ["不存在词"]}})

    monkeypatch.setattr(
        prd_engine, "call_llm",
        lambda s, u, **kw: ("本周期完成了核心模块，下周计划……" if "周报" in u else "空"),
    )

    res = client.post("/api/evolution/evaluate-prompt", headers=auth_headers,
                      json={"module": "report", "instructions": "你是周报助手"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total"] == 2 and body["passed"] == 1 and body["rate"] == 0.5, body


def test_optimize_publish_blocked_by_eval_regression(setup_test_db, monkeypatch, auth_headers):
    """v18.2：新 prompt 评测率劣于旧 prompt → 即使结构闸过，也不得自动发布（可度量闭环）。"""
    import prd_engine

    _seed_version("report", "旧版好提示词：请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果",
                  when="2024-01-01T00:00:00")

    from main import app

    TestClient(app).post("/api/evolution/eval-cases", headers=auth_headers,
                         json={"module": "report", "input": "写个周报", "pass_criteria": {"keywords": ["完成了"]}})

    def fake_llm(system, user, **kw):
        # 优化调用：生成候选（保留占位符 + 够长）
        if "优化目标" in user:
            return "候选提示词：请写 {report_type} 汇报，控制在 {limit} 字，语言精炼专业，突出成果与数据。"
        # 评测调用：旧 prompt（system 含「旧版好」）过，新 prompt（含「候选提示词」）不过 → 劣化
        if "旧版好" in system:
            return "本周期完成了核心模块"
        return "（没有完成信息）"

    monkeypatch.setattr(prd_engine, "call_llm", fake_llm)

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "report"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["eval"] is not None, "有评测集时 eval 结果必须返回"
    assert body["eval"]["before_rate"] == 1.0 and body["eval"]["after_rate"] == 0.0, body["eval"]
    assert body["status"] == "candidate", "评测劣化必须阻断自动发布"
    assert body["gate"]["ok"] is False


def test_optimize_no_eval_set_falls_back_to_structural_gate(setup_test_db, monkeypatch, auth_headers):
    """无评测集的 module → 退化为 v1 结构闸（诚实降级，eval=null）。"""
    import prd_engine

    _seed_version("nomodule", "基准提示词：请写 {report_type} 汇报，控制在 {limit} 字，语言要精炼且专业，突出关键成果与数据")
    monkeypatch.setattr(
        prd_engine, "call_llm",
        lambda s, u, **kw: "优化后：请写 {report_type} 汇报，控制在 {limit} 字，突出成果与数据，语言精炼专业。",
    )

    from main import app

    res = TestClient(app).post("/api/evolution/optimize-prompts", json={"target": "nomodule"}, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["eval"] is None and res.json()["status"] == "published"
