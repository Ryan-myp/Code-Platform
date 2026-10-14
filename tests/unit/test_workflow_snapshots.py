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
