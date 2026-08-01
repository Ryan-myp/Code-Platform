#!/usr/bin/env python3
"""智能研发平台 — 项目/需求/任务 CRUD 测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TestProjectCRUD:
    def test_create_project(self, sample_project_data):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, description, status, team_id, created_at, updated_at) VALUES (?, ?, ?, 'planning', ?, ?, ?)",
                (
                    sample_project_data["id"],
                    sample_project_data["name"],
                    sample_project_data["description"],
                    sample_project_data["team_id"],
                    "2024-01-01T00:00:00",
                    "2024-01-01T00:00:00",
                ),
            )
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?",
                (sample_project_data["id"],),
            ).fetchone()
            assert row is not None
            assert row["name"] == sample_project_data["name"]

    def test_delete_project_cascades(self, sample_project_data):
        from database import get_db
        proj_id = sample_project_data["id"]
        with get_db() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, description, status, team_id, created_at, updated_at) VALUES (?, ?, ?, 'planning', ?, ?, ?)",
                (proj_id, "测试项目", "", "", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
            )
            conn.execute(
                "INSERT INTO tasks (id, project_id, title, description, type, assignee, status, priority, parent_task_id, created_at) VALUES (?, ?, ?, '', 'prd', '', 'todo', 'P2', '', '2024-01-01T00:00:00')",
                ("task_del_001", proj_id, "关联任务"),
            )
            conn.execute(
                "INSERT INTO requirements (id, name, description, status, priority, project_id, creator, version, created_at, updated_at) VALUES (?, ?, ?, 'draft', 'P2', ?, ?, 1, ?, ?)",
                ("req_del_001", "关联需求", "", proj_id, "creator", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
            )
        # 删除项目
        with get_db() as conn:
            conn.execute("UPDATE projects SET active=0 WHERE id=?", (proj_id,))
            conn.execute("UPDATE tasks SET active=0 WHERE project_id=?", (proj_id,))
            conn.execute("UPDATE requirements SET active=0 WHERE project_id=?", (proj_id,))
        # 验证级联
        with get_db() as conn:
            proj_row = conn.execute("SELECT COUNT(*) FROM projects WHERE id=? AND active=1", (proj_id,)).fetchone()[0]
            task_row = conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND active=1", (proj_id,)).fetchone()[0]
            req_row = conn.execute("SELECT COUNT(*) FROM requirements WHERE project_id=? AND active=1", (proj_id,)).fetchone()[0]
            assert proj_row == 0
            assert task_row == 0
            assert req_row == 0


class TestRequirementCRUD:
    def test_create_requirement(self, sample_requirement_data):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO requirements (id, name, description, status, priority, project_id, creator, version, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?, ?, 1, ?, ?)",
                (
                    sample_requirement_data["id"],
                    sample_requirement_data["name"],
                    sample_requirement_data["description"],
                    sample_requirement_data["priority"],
                    sample_requirement_data["project_id"],
                    sample_requirement_data["creator"],
                    "2024-01-01T00:00:00",
                    "2024-01-01T00:00:00",
                ),
            )
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM requirements WHERE id = ?",
                (sample_requirement_data["id"],),
            ).fetchone()
            assert row is not None
            assert row["name"] == sample_requirement_data["name"]


class TestTaskCRUD:
    def test_create_task(self, sample_task_data):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO tasks (id, project_id, title, description, type, assignee, status, priority, parent_task_id, created_at) VALUES (?, ?, ?, ?, ?, ?, 'todo', ?, ?, ?)",
                (
                    sample_task_data["id"],
                    sample_task_data["project_id"],
                    sample_task_data["title"],
                    sample_task_data["description"],
                    sample_task_data["type"],
                    sample_task_data["assignee"],
                    sample_task_data["priority"],
                    sample_task_data.get("parent_task_id", ""),
                    "2024-01-01T00:00:00",
                ),
            )
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (sample_task_data["id"],),
            ).fetchone()
            assert row is not None
            assert row["title"] == sample_task_data["title"]

    def test_update_task_status(self, sample_task_data):
        from database import get_db
        task_id = sample_task_data["id"]
        with get_db() as conn:
            conn.execute(
                "INSERT INTO tasks (id, project_id, title, description, type, assignee, status, priority, parent_task_id, created_at) VALUES (?, ?, ?, '', 'prd', '', 'todo', 'P2', '', '2024-01-01T00:00:00')",
                (task_id, sample_task_data["project_id"], "测试任务"),
            )
        with get_db() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'done', completed_at = '2024-01-02T00:00:00' WHERE id = ?",
                (task_id,),
            )
        with get_db() as conn:
            row = conn.execute("SELECT status, completed_at FROM tasks WHERE id = ?", (task_id,)).fetchone()
            assert row["status"] == "done"
            assert row["completed_at"] is not None


class TestArtifactCRUD:
    def test_create_artifact(self, test_db_path):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO artifacts (id, project_id, requirement_id, type, content, version, author, created_at) VALUES (?, ?, ?, 'prd', '测试内容', 1, 'tester', '2024-01-01T00:00:00')",
                ("art_test_001", "proj_test_001", "req_test_001"),
            )
        with get_db() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE id = ?", ("art_test_001",)).fetchone()
            assert row is not None
            assert row["type"] == "prd"
