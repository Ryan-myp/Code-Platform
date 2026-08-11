"""v15 游戏工厂增强单测：模板库扩充 + 迭代历史对比/回滚。

覆盖：
- TEMPLATES：扩充到 21 个，新增音游/密室逃脱/平台跳跃模板字段完整
- diff_file_stats / build_version_stats：逐行 diff 统计纯函数
- GET /{proj_id}/history：版本时间线 + 逐版变更统计
- GET /{proj_id}/history/{version}：历史版本文件查看
- POST /{proj_id}/restore：回滚（当前版本先快照）
- evolve worker：迭代前自动保存版本快照
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"username": "tester"}

FILES_V1 = {
    "web": {"index.html": "<html><body>v1</body></html>"},
    "wx": {"game.js": "wx.createCanvas();", "game.json": "{}", "project.config.json": "{}"},
}
FILES_V2 = {
    "web": {"index.html": "<html><body>v2 with new feature</body></html>"},
    "wx": {"game.js": "wx.createCanvas();\nconsole.log('v2');", "game.json": "{}", "project.config.json": "{}"},
}


def _seed_project(conn, pid="gp_v15_001", files=None, history=None):
    from game_factory import _ensure_history_column

    _ensure_history_column(conn)
    conn.execute(
        """INSERT INTO game_projects (id, name, template, requirement, files, iterations, iteration_log, version_history)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            pid,
            "测试小游戏",
            "snake",
            "初始需求",
            json.dumps(files if files is not None else FILES_V1, ensure_ascii=False),
            0,
            "[]",
            json.dumps(history or [], ensure_ascii=False),
        ),
    )
    conn.commit()


class TestTemplatesExpansion:
    """模板库扩充：v15 新增 3 类玩法模板。"""

    def test_template_count(self):
        from game_factory import TEMPLATES

        assert len(TEMPLATES) == 22

    def test_new_templates_fields(self):
        from game_factory import TEMPLATES

        by_id = {t["id"]: t for t in TEMPLATES}
        for tid in ("rhythm", "escape", "platformer"):
            t = by_id[tid]
            assert {"id", "name", "icon", "color", "category", "description", "play"} <= set(t)
            assert t["category"] in ("音游", "解谜", "休闲")
            assert len(t["play"]) > 80  # 玩法说明足够具体

    def test_all_templates_play_detail(self):
        from game_factory import TEMPLATES

        for t in TEMPLATES:
            if t["id"] == "custom":  # 自定义模板无固定玩法说明
                continue
            assert len(t["play"]) > 60, t["id"]


class TestDiffFileStats:
    """逐行 diff 统计纯函数。"""

    def test_insert_only(self):
        from game_factory import diff_file_stats

        s = diff_file_stats("a\nb", "a\nb\nc\nd")
        assert s == {"added": 2, "removed": 0}

    def test_delete_only(self):
        from game_factory import diff_file_stats

        s = diff_file_stats("a\nb\nc", "a")
        assert s == {"added": 0, "removed": 2}

    def test_replace(self):
        from game_factory import diff_file_stats

        s = diff_file_stats("a\nold\nb", "a\nnew\nb")
        assert s == {"added": 1, "removed": 1}

    def test_empty_inputs(self):
        from game_factory import diff_file_stats

        assert diff_file_stats("", "") == {"added": 0, "removed": 0}
        assert diff_file_stats(None, "x") == {"added": 1, "removed": 0}


class TestBuildVersionStats:
    """多文件版本对比统计。"""

    def test_changed_and_new_files(self):
        from game_factory import build_version_stats

        prev = {"web": {"a.js": "x\ny", "b.js": "same"}}
        cur = {"web": {"a.js": "x\ny\nz", "b.js": "same", "c.js": "new"}}
        stats = build_version_stats(prev, cur)
        assert stats["web/a.js"] == {"added": 1, "removed": 0}
        assert "web/b.js" not in stats  # 未变化不出现
        assert stats["web/c.js"] == {"added": 1, "removed": 0}  # 新增文件

    def test_removed_file(self):
        from game_factory import build_version_stats

        prev = {"web": {"a.js": "x", "gone.js": "g\nh"}}
        cur = {"web": {"a.js": "x"}}
        stats = build_version_stats(prev, cur)
        assert stats["web/gone.js"] == {"added": 0, "removed": 2}

    def test_no_change(self):
        from game_factory import build_version_stats

        assert build_version_stats(FILES_V1, dict(FILES_V1)) == {}


class TestHistoryEndpoints:
    """迭代历史时间线 + 版本查看 + 回滚。"""

    def test_history_empty(self, setup_test_db):
        from common.db import get_db
        from game_factory import project_history

        conn = get_db()
        _seed_project(conn, history=[])
        conn.close()

        out = asyncio.run(project_history("gp_v15_001", current_user=USER))
        assert out["history"] == []
        assert out["iterations"] == 0

    def test_history_stats_relative(self, setup_test_db):
        from common.db import get_db
        from game_factory import project_history

        conn = get_db()
        _seed_project(
            conn,
            files=FILES_V2,
            history=[
                {"version": 1, "created_at": "2026-08-01T10:00:00", "requirement": "初始版本", "files": FILES_V1},
                {"version": 2, "created_at": "2026-08-02T10:00:00", "requirement": "迭代前快照：加个新功能", "files": FILES_V2},
            ],
        )
        conn.close()

        out = asyncio.run(project_history("gp_v15_001", current_user=USER))
        assert len(out["history"]) == 2
        v1, v2 = out["history"]
        assert v1["version"] == 1 and v1["stats"] == {}  # 初始版本无对比
        assert v2["version"] == 2
        assert v2["requirement"].startswith("迭代前快照")
        assert v2["stats"]["web/index.html"]["added"] >= 1
        assert v2["stats"]["wx/game.js"]["added"] >= 1

    def test_history_missing_project_404(self, setup_test_db):
        from game_factory import project_history

        with pytest.raises(HTTPException) as e:
            asyncio.run(project_history("nope", current_user=USER))
        assert e.value.status_code == 404

    def test_history_version_view(self, setup_test_db):
        from common.db import get_db
        from game_factory import project_history_version

        conn = get_db()
        _seed_project(
            conn,
            history=[
                {"version": 1, "created_at": "2026-08-01T10:00:00", "requirement": "初始版本", "files": FILES_V1},
            ],
        )
        conn.close()

        out = asyncio.run(project_history_version("gp_v15_001", version=1, current_user=USER))
        assert out["files"] == FILES_V1
        assert out["requirement"] == "初始版本"

    def test_history_version_missing_404(self, setup_test_db):
        from common.db import get_db
        from game_factory import project_history_version

        conn = get_db()
        _seed_project(conn, history=[{"version": 1, "created_at": "", "requirement": "", "files": FILES_V1}])
        conn.close()

        with pytest.raises(HTTPException) as e:
            asyncio.run(project_history_version("gp_v15_001", version=9, current_user=USER))
        assert e.value.status_code == 404
        assert "v9" in e.value.detail

    def test_restore_snapshot_and_files(self, setup_test_db):
        from common.db import get_db
        from game_factory import RestoreRequest, project_history, restore_project

        conn = get_db()
        _seed_project(
            conn,
            files=FILES_V2,
            history=[
                {"version": 1, "created_at": "2026-08-01T10:00:00", "requirement": "初始版本", "files": FILES_V1},
            ],
        )
        conn.close()

        out = asyncio.run(restore_project("gp_v15_001", req=RestoreRequest(version=1), current_user=USER))
        assert out["files"] == FILES_V1  # 已回滚到 v1 文件
        assert "已回滚到 v1" in out["message"]

        # 回滚前当前版本（v2）已快照进历史
        hist = asyncio.run(project_history("gp_v15_001", current_user=USER))
        assert len(hist["history"]) == 2
        assert hist["history"][1]["requirement"].startswith("回滚前快照")
        assert hist["history"][1]["stats"]["web/index.html"]["added"] >= 1

        conn = get_db()
        row = conn.execute("SELECT iteration_log FROM game_projects WHERE id='gp_v15_001'").fetchone()
        conn.close()
        assert json.loads(row["iteration_log"])[-1]["requirement"] == "回滚到 v1"

    def test_restore_missing_version_404(self, setup_test_db):
        from common.db import get_db
        from game_factory import RestoreRequest, restore_project

        conn = get_db()
        _seed_project(conn, history=[])
        conn.close()

        with pytest.raises(HTTPException) as e:
            asyncio.run(restore_project("gp_v15_001", req=RestoreRequest(version=3), current_user=USER))
        assert e.value.status_code == 404


class TestEvolveWorkerSnapshot:
    """迭代 worker：执行前自动保存当前版本快照。"""

    def test_evolve_saves_snapshot(self, setup_test_db):
        from common.db import get_db
        from game_factory import _game_evolve_worker

        conn = get_db()
        _seed_project(conn, files=FILES_V1, history=[])
        conn.close()

        new_json = json.dumps(
            {
                "web": {"index.html": "<html><body>evolved</body></html>"},
                "wx": {"game.js": "wx.createCanvas();\n// evolved", "game.json": "{}", "project.config.json": "{}"},
            },
            ensure_ascii=False,
        )
        with patch("game_factory.call_llm_async", new=AsyncMock(return_value=new_json)), patch(
            "game_factory.log_usage", lambda *a, **kw: None
        ):
            result = asyncio.run(
                _game_evolve_worker({"proj_id": "gp_v15_001", "params": {"requirement": "增加排行榜"}})
            )

        assert result["iterations"] == 1

        conn = get_db()
        row = conn.execute("SELECT files, iterations, version_history FROM game_projects WHERE id='gp_v15_001'").fetchone()
        conn.close()
        assert row["iterations"] == 1
        assert "evolved" in json.loads(row["files"])["web"]["index.html"]
        history = json.loads(row["version_history"])
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["files"] == FILES_V1  # 快照是迭代前的旧代码
        assert "排行榜" in history[0]["requirement"]
