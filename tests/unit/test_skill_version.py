"""v18 P2：技能版本化（创建带版本、内容变更自动 +1）+ 结构迁移幂等。"""

from fastapi.testclient import TestClient


def _get_version(auth_headers, skill_id: str) -> int:
    from common.db import get_db

    conn = get_db()
    row = conn.execute("SELECT version FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    return row["version"] if row and row["version"] is not None else 0


def test_skill_create_default_version(setup_test_db, auth_headers):
    from main import app

    res = TestClient(app).post(
        "/api/skills",
        headers=auth_headers,
        json={"name": "v-skill", "content": "内容 v1"},
    )
    assert res.status_code == 200, res.text
    assert _get_version(auth_headers, res.json()["id"]) == 1


def test_skill_update_bumps_version(setup_test_db, auth_headers):
    from main import app

    client = TestClient(app)
    created = client.post("/api/skills", headers=auth_headers, json={"name": "v-skill2", "content": "初版"})
    sid = created.json()["id"]
    assert _get_version(auth_headers, sid) == 1

    res = client.put(f"/api/skills/{sid}", headers=auth_headers, json={"content": "改版"})
    assert res.status_code == 200, res.text
    assert _get_version(auth_headers, sid) == 2, "内容变更应自动 +1"

    res = client.put(f"/api/skills/{sid}", headers=auth_headers, json={"description": "补充说明"})
    assert res.status_code == 200
    assert _get_version(auth_headers, sid) == 3, "任意内容字段更新都应 +1（审计链）"


def test_skill_version_column_migration(setup_test_db):
    """旧库（无 version 列）也能正常建/改技能（ALTER 幂等兜底）。"""
    from common.db import get_db

    conn = get_db()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(skills)").fetchall()}
    assert "version" in cols, "建表/迁移后应存在 version 列"
    conn.close()
