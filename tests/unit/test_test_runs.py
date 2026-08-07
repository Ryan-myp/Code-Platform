#!/usr/bin/env python3
"""自动化测试执行记录：逐条 case 解析、落库、查询返回（AI 工作台按 case 展示）。"""

import asyncio
import json


class TestParsePytestCases:
    """pytest -rA 输出 → 逐条用例 [{name, path, status, message}]。"""

    def test_full_summary_block(self):
        from extended_api import _parse_pytest_cases

        out = (
            "============================= test session starts =============================\n"
            "test_main.py::test_hello PASSED                                           [ 33%]\n"
            "test_main.py::test_add PASSED                                             [ 66%]\n"
            "test_main.py::test_sub FAILED - AssertionError: assert 5 == 4             [100%]\n"
            "\n"
            "=========================== short test summary info ============================\n"
            "PASSED test_main.py::test_hello\n"
            "PASSED test_main.py::test_add\n"
            "FAILED test_main.py::test_sub - AssertionError: assert 5 == 4\n"
            "================= 2 passed, 1 failed in 0.12s =====================\n"
        )
        cases = _parse_pytest_cases(out)
        assert len(cases) == 3
        assert cases[0] == {"name": "test_hello", "path": "test_main.py::test_hello", "status": "passed", "message": ""}
        assert cases[2]["name"] == "test_sub" and cases[2]["status"] == "failed"
        assert "assert 5 == 4" in cases[2]["message"]

    def test_skipped_and_error_status(self):
        from extended_api import _parse_pytest_cases

        out = (
            "PASSED test_main.py::test_a\n"
            "SKIPPED test_main.py::test_b\n"
            "ERROR test_main.py::test_c - fixture 'db' not found\n"
        )
        cases = _parse_pytest_cases(out)
        assert {c["status"] for c in cases} == {"passed", "skipped", "error"}
        assert cases[2]["message"] == "fixture 'db' not found"

    def test_dedup_repeated_lines(self):
        """-rA 摘要与正文重复出现 FAILED 行时不产生重复条目。"""
        from extended_api import _parse_pytest_cases

        out = (
            "___________ test_main.py::test_x ___________\n"
            "    def test_x():\n"
            ">       assert 1 == 2\n"
            "FAILED test_main.py::test_x - AssertionError: assert 1 == 2\n"
            "\n"
            "short test summary info:\n"
            "FAILED test_main.py::test_x - AssertionError: assert 1 == 2\n"
        )
        cases = _parse_pytest_cases(out)
        assert len(cases) == 1 and cases[0]["name"] == "test_x"

    def test_fallback_only_failed_lines(self):
        """无 -rA 摘要时退化解析 FAILED 行（至少可见失败项）。"""
        from extended_api import _parse_pytest_cases

        out = "FAILED test_main.py::test_bad - assert 200 == 500"
        cases = _parse_pytest_cases(out)
        assert len(cases) == 1
        assert cases[0]["status"] == "failed" and cases[0]["message"] == "assert 200 == 500"

    def test_empty_and_non_python_output(self):
        from extended_api import _parse_pytest_cases

        assert _parse_pytest_cases("") == []
        assert _parse_pytest_cases("# pass 3\n# fail 1") == []  # node:test 输出不误解析


class TestAttachCaseMeta:
    """测试文件 docstring TC 编号 → 执行结果关联到生成的用例。"""

    def test_docstring_mapping(self, tmp_path):
        from extended_api import _attach_case_meta

        (tmp_path / "test_main.py").write_text(
            "def test_weather_live_only():\n"
            '    """TC-API-016: 仅获取实时天气"""\n'
            "    assert 1\n"
            "def test_search_beijing():\n"
            '    """TC-API-001 搜索北京"""\n'
            "    assert 1\n",
            encoding="utf-8",
        )
        cases = [
            {
                "name": "test_weather_live_only",
                "path": "a.py::test_weather_live_only",
                "status": "failed",
                "message": "AssertionError: x",
            },
            {"name": "test_search_beijing", "path": "a.py::test_search_beijing", "status": "passed", "message": ""},
        ]
        out = _attach_case_meta(cases, str(tmp_path))
        assert out[0]["case_id"] == "TC-API-016"
        assert out[0]["case_title"] == "仅获取实时天气"
        assert out[1]["case_id"] == "TC-API-001"
        assert out[1]["case_title"] == "搜索北京"

    def test_no_docstring_keeps_original(self, tmp_path):
        from extended_api import _attach_case_meta

        (tmp_path / "test_main.py").write_text(
            'def test_plain():\n    assert 1\ndef test_no_tc():\n    """普通描述无编号"""\n    assert 1\n',
            encoding="utf-8",
        )
        cases = [{"name": "test_plain", "path": "a.py::test_plain", "status": "passed", "message": ""}]
        out = _attach_case_meta(cases, str(tmp_path))
        assert "case_id" not in out[0] and "case_title" not in out[0]

    def test_multiple_files_and_missing_dir(self, tmp_path):
        from extended_api import _attach_case_meta

        (tmp_path / "test_main.py").write_text('def test_a():\n    """TC-A-1: 用例A"""\n', encoding="utf-8")
        (tmp_path / "test_extra.py").write_text('def test_b():\n    """TC-B-2: 用例B"""\n', encoding="utf-8")
        out = _attach_case_meta(
            [{"name": "test_b", "path": "test_extra.py::test_b", "status": "passed", "message": ""}], str(tmp_path)
        )
        assert out[0]["case_id"] == "TC-B-2"
        # 目录不存在/空 cases 安全返回
        assert _attach_case_meta([{"name": "x"}], "/no/such/dir") == [{"name": "x"}]
        assert _attach_case_meta([], str(tmp_path)) == []


class TestRecordTestRun:
    """test_runs 落库：cases JSON 列 + 旧库 ALTER 兼容。"""

    def test_record_with_cases(self, setup_test_db):
        from common.db import get_db
        from extended_api import _record_test_run

        cases = [
            {"name": "test_a", "path": "test_main.py::test_a", "status": "passed", "message": ""},
            {
                "name": "test_b",
                "path": "test_main.py::test_b",
                "status": "failed",
                "message": "AssertionError: assert 5 == 4",
            },
        ]
        _record_test_run("req_1", "pipe_1", "failed", "1 passed, 1 failed", "log...", cases)
        conn = get_db()
        try:
            row = conn.execute("SELECT status, summary, cases FROM test_runs WHERE requirement_id='req_1'").fetchone()
        finally:
            conn.close()
        assert row["status"] == "failed"
        assert row["summary"] == "1 passed, 1 failed"
        assert json.loads(row["cases"]) == cases

    def test_record_without_requirement_id(self, setup_test_db):
        from common.db import get_db
        from extended_api import _record_test_run

        _record_test_run(None, "pipe_1", "passed", "s", "log")
        conn = get_db()
        try:
            # 无 requirement_id 直接跳过：表都不应被创建（无任何记录）
            tbl = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_runs'").fetchone()
            cnt = conn.execute("SELECT COUNT(*) FROM test_runs").fetchone()[0] if tbl else 0
        finally:
            conn.close()
        assert cnt == 0

    def test_legacy_table_gets_cases_column(self, setup_test_db):
        """旧库 test_runs 无 cases 列：记录时自动 ALTER，不丢数据。"""
        from common.db import get_db
        from extended_api import _record_test_run

        conn = get_db()
        try:
            # 模拟旧表结构（无 cases 列），并插入一条旧记录
            conn.execute(
                "CREATE TABLE test_runs (id TEXT PRIMARY KEY, requirement_id TEXT, pipeline_id TEXT, "
                "status TEXT, summary TEXT, log TEXT, created_at TEXT)"
            )
            conn.execute(
                "INSERT INTO test_runs (id, requirement_id, pipeline_id, status, summary, log, created_at)"
                " VALUES ('old_1', 'req_1', 'p', 'passed', '旧记录', 'log', '2026-01-01T00:00:00')"
            )
            conn.commit()
        finally:
            conn.close()
        _record_test_run("req_1", "pipe_2", "failed", "1 failed", "new log", [{"name": "t", "status": "failed"}])
        conn = get_db()
        try:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(test_runs)").fetchall()}
            old = conn.execute("SELECT summary FROM test_runs WHERE id='old_1'").fetchone()
            new = conn.execute("SELECT cases FROM test_runs WHERE requirement_id='req_1' AND id!='old_1'").fetchone()
        finally:
            conn.close()
        assert "cases" in cols
        assert old["summary"] == "旧记录"  # 旧数据保留
        assert json.loads(new["cases"])[0]["name"] == "t"


class TestGetTestRuns:
    """GET /api/requirements/{id}/test-runs：cases 字段解析为列表返回。"""

    def test_cases_parsed(self, setup_test_db):
        from extended_api import _record_test_run
        from prd_engine import get_test_runs

        cases = [{"name": "test_ok", "path": "test_main.py::test_ok", "status": "passed", "message": ""}]
        _record_test_run("req_2", "pipe_1", "passed", "1 passed", "log", cases)
        runs = asyncio.run(get_test_runs("req_2"))
        assert len(runs) == 1
        assert runs[0]["cases"] == cases
        assert runs[0]["status"] == "passed"

    def test_malformed_cases_returns_empty_list(self, setup_test_db):
        from common.db import get_db
        from prd_engine import get_test_runs

        conn = get_db()
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS test_runs (id TEXT PRIMARY KEY, requirement_id TEXT, pipeline_id TEXT, "
                "status TEXT, summary TEXT, log TEXT, cases TEXT, created_at TEXT)"
            )
            conn.execute(
                "INSERT INTO test_runs (id, requirement_id, pipeline_id, status, summary, log, cases, created_at)"
                " VALUES ('t1', 'req_3', 'p', 'failed', 's', 'l', 'not-json{{{', '2026-01-01T00:00:00')"
            )
            conn.commit()
        finally:
            conn.close()
        runs = asyncio.run(get_test_runs("req_3"))
        assert runs[0]["cases"] == []

    def test_no_records(self, setup_test_db):
        from prd_engine import get_test_runs

        assert asyncio.run(get_test_runs("req_none")) == []
