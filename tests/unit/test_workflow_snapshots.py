"""v18.2 工作流节点快照 + 输入重放。"""

import json


def _seed_workflow(setup_test_db) -> str:
    from common.db import get_db

    conn = get_db()
    steps = json.dumps([{"id": "n1", "type": "agent", "config": {"agent_id": "a1"}, "label": "节点1"}])
    conn.execute(
        "INSERT INTO workflows (id, name, steps, active) VALUES ('wf_snap', '快照测试', ?, 1)", (steps,)
    )
    conn.commit()
    conn.close()
    return "wf_snap"


def test_snapshots_endpoint_returns_node_timeline(setup_test_db, auth_headers):
    from common.db import get_db

    _seed_workflow(setup_test_db)
    conn = get_db()
    conn.execute("ALTER TABLE workflow_run_logs ADD COLUMN input_data TEXT DEFAULT ''"
                 if not any(r["name"] == "input_data" for r in conn.execute("PRAGMA table_info(workflow_run_logs)").fetchall())
                 else "SELECT 1")
    conn.execute(
        "INSERT INTO workflow_runs (id, workflow_id, status, input_data, started_at) VALUES ('r1','wf_snap','done','{}','2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO workflow_run_logs (id, run_id, node_id, status, output_data, input_data, completed_at) "
        "VALUES ('log1','r1','n1','success','{}','{\"node_type\": \"agent\"}','2026-01-01T00:00:01')"
    )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient

    from main import app

    res = TestClient(app).get("/api/workflows/runs/r1/snapshots", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["run_id"] == "r1" and body["workflow_id"] == "wf_snap"
    assert body["nodes"][0]["node_id"] == "n1" and body["nodes"][0]["input_data"]


def test_replay_reruns_with_saved_input(setup_test_db, auth_headers, monkeypatch):
    _seed_workflow(setup_test_db)

    import workflows.executor as ex

    captured = {}

    class _FakeExecutor:
        async def execute(self, workflow_id, input_data=None):
            captured["wf"] = workflow_id
            captured["input"] = input_data
            return "r_new"

    # chat_engine 在函数内 `from workflows.executor import executor` → patch 模块属性
    monkeypatch.setattr(ex, "executor", _FakeExecutor())

    from common.db import get_db

    conn = get_db()
    conn.execute("ALTER TABLE workflow_run_logs ADD COLUMN input_data TEXT DEFAULT ''"
                 if not any(r["name"] == "input_data" for r in conn.execute("PRAGMA table_info(workflow_run_logs)").fetchall())
                 else "SELECT 1")
    conn.execute(
        "INSERT INTO workflow_runs (id, workflow_id, status, input_data, started_at) "
        "VALUES ('r_old','wf_snap','done','{\"message\": \"重放我\"}','2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO workflow_runs (id, workflow_id, status, started_at) VALUES ('r_new','wf_snap','done','2026-01-01T00:00:01')"
    )
    conn.commit()
    conn.close()

    from fastapi.testclient import TestClient

    from main import app

    res = TestClient(app).post("/api/workflows/runs/r_old/replay", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert captured["wf"] == "wf_snap"
    assert json.dumps(captured["input"], ensure_ascii=False) == json.dumps({"message": "重放我"}, ensure_ascii=False)
    assert res.json()["new_run"] == "r_new"


def test_replay_unknown_run_404(setup_test_db, auth_headers):
    from fastapi.testclient import TestClient

    from main import app

    res = TestClient(app).post("/api/workflows/runs/no_such/replay", headers=auth_headers)
    assert res.status_code == 404


def test_resume_seeds_success_snapshots_and_reruns_failed(setup_test_db, auth_headers):
    """v18.3 断点续跑：n1 成功快照预填（不重执行），n2 错误 dict 不预填（重跑）。"""
    _seed_workflow_nodes(setup_test_db, "wf_res", [
        {"id": "n1", "type": "code", "config": {"code": "print('N1_OK')"}},
        {"id": "n2", "type": "code", "config": {"code": "import sys\nsys.exit(1)"}},
    ])

    import workflows.executor as ex

    run1 = _run_executor_blocking(ex.executor.execute, "wf_res", {"message": "resume test"})
    assert run1

    # n1 快照：success；n2：错误 dict（不预填）
    seeded = ex.executor._load_resume_snapshots(run1)
    assert "n1" in seeded and "n2" not in seeded, dict(seeded)

    # reset_nodes：连 n1 一并清除 → 全部重跑
    assert ex.executor._load_resume_snapshots(run1, reset_nodes=["n1"]) == {}

    # 续跑执行链：resume 后 n1 不重执行（skip_set），n2 仍重跑；旧 run 保持不动（新 run_id）
    run2 = _run_executor_blocking(ex.executor.execute, "wf_res", {"message": "resume test"},
                                  resume_run_id=run1)
    assert run2 != run1

    from common.db import get_db

    conn = get_db()
    r2_status = conn.execute("SELECT status FROM workflow_runs WHERE id=?", (run2,)).fetchone()[0]
    conn.close()
    assert r2_status == "completed"


def _seed_workflow_nodes(setup_test_db, wf_id, nodes):
    from common.db import get_db
    import json as _json2

    conn = get_db()
    conn.execute("INSERT INTO workflows (id, name, steps, active) VALUES (?, ?, ?, 1)",
                 (wf_id, "续跑测试", _json2.dumps(nodes)))
    conn.commit()
    conn.close()


def _run_executor_blocking(coro_fn, *args, **kw):
    """同步测试环境里跑 async executor（新事件循环，避免复用已关闭 loop）。"""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro_fn(*args, **kw))
    finally:
        loop.close()


def test_resume_endpoint(setup_test_db, auth_headers, monkeypatch):
    """resume 端点：以旧 run 快照 + 存档输入重跑（fake execute，验证参数透传）。"""
    import json as _json

    _seed_workflow_nodes(setup_test_db, "wf_res_ep", [
        {"id": "n1", "type": "code", "config": {"code": "print(1)"}},
    ])

    from common.db import get_db

    conn = get_db()
    conn.execute("ALTER TABLE workflow_run_logs ADD COLUMN input_data TEXT DEFAULT ''"
                 if not any(r["name"] == "input_data" for r in conn.execute("PRAGMA table_info(workflow_run_logs)").fetchall())
                 else "SELECT 1")
    conn.execute(
        "INSERT INTO workflow_runs (id, workflow_id, status, input_data, started_at) "
        "VALUES ('r_fail','wf_res_ep','failed','{\"message\": \"继续我\"}','2026-01-01T00:00:00')"
    )
    conn.execute(
        "INSERT INTO workflow_runs (id, workflow_id, status, started_at) VALUES ('r_new','wf_res_ep','done','2026-01-01T00:00:01')"
    )
    conn.execute(
        "INSERT INTO workflow_run_logs (id, run_id, node_id, status, output_data) "
        "VALUES ('log1','r_fail','n1','success','{\"status\": \"success\", \"stdout\": \"1\"}')"
    )
    conn.commit()
    conn.close()

    import workflows.executor as ex

    captured = {}

    async def fake_execute(workflow_id, input_data=None, resume_run_id="", reset_nodes=None):
        captured.update(wf=workflow_id, input=input_data, resume=resume_run_id, reset=reset_nodes)
        return "r_new"

    monkeypatch.setattr(ex.executor, "execute", fake_execute)

    from fastapi.testclient import TestClient

    from main import app

    res = TestClient(app).post("/api/workflows/runs/r_fail/resume?reset_node=n1", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert captured["resume"] == "r_fail" and captured["reset"] == ["n1"]
    assert captured["input"] == {"message": "继续我"}
    assert body["source_run"] == "r_fail" and body["new_run"] == "r_new"
    # reset n1 后无可续快照
    assert body["resumed_nodes"] == []
    assert _json is not None
