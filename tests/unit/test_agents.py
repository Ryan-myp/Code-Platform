#!/usr/bin/env python3
"""智能研发平台 — Agent CRUD 测试"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TestAgentCRUD:
    """测试 Agent 的增删改查"""

    def test_create_agent(self, sample_agent_data):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO agents (id, name, description, instructions, model, enable_memory, enable_reasoning, tools, knowledge_base_ids, skill_ids, mcp_server_ids, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sample_agent_data["id"],
                    sample_agent_data["name"],
                    sample_agent_data["description"],
                    sample_agent_data["instructions"],
                    sample_agent_data["model"],
                    int(sample_agent_data["enable_memory"]),
                    int(sample_agent_data["enable_reasoning"]),
                    json.dumps(sample_agent_data["tools"]),
                    json.dumps(sample_agent_data["knowledge_base_ids"]),
                    json.dumps(sample_agent_data["skill_ids"]),
                    json.dumps(sample_agent_data["mcp_server_ids"]),
                    "2024-01-01T00:00:00",
                    1,
                ),
            )
        # 验证
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE id = ?",
                (sample_agent_data["id"],),
            ).fetchone()
            assert row is not None
            assert row["name"] == sample_agent_data["name"]

    def test_update_agent(self, sample_agent_data):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO agents (id, name, description, instructions, model, enable_memory, enable_reasoning, tools, knowledge_base_ids, skill_ids, mcp_server_ids, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sample_agent_data["id"],
                    sample_agent_data["name"],
                    sample_agent_data["description"],
                    sample_agent_data["instructions"],
                    sample_agent_data["model"],
                    0,
                    0,
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "2024-01-01T00:00:00",
                    1,
                ),
            )
        # 更新
        with get_db() as conn:
            conn.execute(
                "UPDATE agents SET name = ?, instructions = ? WHERE id = ?",
                ("Updated Name", "New instructions", sample_agent_data["id"]),
            )
        # 验证
        with get_db() as conn:
            row = conn.execute(
                "SELECT name, instructions FROM agents WHERE id = ?",
                (sample_agent_data["id"],),
            ).fetchone()
            assert row["name"] == "Updated Name"
            assert row["instructions"] == "New instructions"

    def test_delete_agent_soft_delete(self, sample_agent_data):
        from database import get_db
        with get_db() as conn:
            conn.execute(
                "INSERT INTO agents (id, name, description, instructions, model, enable_memory, enable_reasoning, tools, knowledge_base_ids, skill_ids, mcp_server_ids, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sample_agent_data["id"],
                    sample_agent_data["name"],
                    "",
                    "",
                    "agnes-2.0-flash",
                    0,
                    0,
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "2024-01-01T00:00:00",
                    1,
                ),
            )
        # 软删除
        with get_db() as conn:
            conn.execute(
                "UPDATE agents SET active = 0 WHERE id = ?",
                (sample_agent_data["id"],),
            )
        # 验证
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM agents WHERE id = ? AND active = 1",
                (sample_agent_data["id"],),
            ).fetchone()
            assert row is None

    def test_list_agents(self, sample_agent_data):
        from database import get_db
        # 插入两个 agent
        with get_db() as conn:
            conn.execute(
                "INSERT INTO agents (id, name, description, instructions, model, enable_memory, enable_reasoning, tools, knowledge_base_ids, skill_ids, mcp_server_ids, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sample_agent_data["id"], sample_agent_data["name"], "", "", "agnes-2.0-flash", 0, 0, "[]", "[]", "[]", "[]", "2024-01-01T00:00:00", 1),
            )
            conn.execute(
                "INSERT INTO agents (id, name, description, instructions, model, enable_memory, enable_reasoning, tools, knowledge_base_ids, skill_ids, mcp_server_ids, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("agent_test_002", "Agent 2", "", "", "agnes-2.0-flash", 0, 0, "[]", "[]", "[]", "[]", "2024-01-01T00:00:00", 1),
            )
        # 查询
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM agents WHERE active = 1").fetchall()
            assert len(rows) == 2
