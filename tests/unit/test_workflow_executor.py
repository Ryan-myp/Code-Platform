#!/usr/bin/env python3
"""workflow executor 单元测试 — 节点执行、占位符替换、条件求值、错误处理。"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def run(coro):
    """同步执行 async 函数的辅助。"""
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════
# 占位符替换 _substitute
# ══════════════════════════════════════════════════════════════


def test_substitute_simple():
    """简单占位符替换"""
    from workflows.executor import _substitute

    results = {"node1": {"output": "hello"}}
    assert _substitute("${node1.output}", results) == "hello"


def test_substitute_nested():
    """嵌套路径占位符替换"""
    from workflows.executor import _substitute

    results = {"node1": {"data": {"value": 42}}}
    assert _substitute("${node1.data.value}", results) == "42"


def test_substitute_no_match():
    """无匹配时保留原文"""
    from workflows.executor import _substitute

    results = {"node1": {"output": "hello"}}
    assert _substitute("${nonexistent.field}", results) == "${nonexistent.field}"


def test_substitute_dict_value():
    """替换为 dict 时序列化为 JSON"""
    from workflows.executor import _substitute

    results = {"node1": {"output": {"a": 1}}}
    result = _substitute("${node1.output}", results)
    parsed = json.loads(result)
    assert parsed == {"a": 1}


def test_substitute_non_string():
    """非字符串原样返回"""
    from workflows.executor import _substitute

    assert _substitute(123, {}) == 123
    assert _substitute(None, {}) is None


def test_substitute_in_text():
    """占位符嵌入文本中"""
    from workflows.executor import _substitute

    results = {"node1": {"output": "world"}}
    assert _substitute("hello ${node1.output}!", results) == "hello world!"


# ══════════════════════════════════════════════════════════════
# AST 安全求值 _safe_eval
# ══════════════════════════════════════════════════════════════


def test_safe_eval_arithmetic():
    """算术表达式"""
    from workflows.executor import _safe_eval

    assert _safe_eval("1 + 2", {}) == 3
    assert _safe_eval("10 - 3", {}) == 7
    assert _safe_eval("4 * 5", {}) == 20
    assert _safe_eval("10 / 2", {}) == 5.0


def test_safe_eval_comparison():
    """比较表达式"""
    from workflows.executor import _safe_eval

    assert _safe_eval("1 < 2", {}) is True
    assert _safe_eval("3 > 5", {}) is False
    assert _safe_eval("1 == 1", {}) is True
    assert _safe_eval("1 != 2", {}) is True


def test_safe_eval_boolean():
    """布尔逻辑"""
    from workflows.executor import _safe_eval

    assert _safe_eval("True and False", {}) is False
    assert _safe_eval("True or False", {}) is True
    assert _safe_eval("not False", {}) is True


def test_safe_eval_with_env():
    """带环境变量的表达式（使用下标访问，不允许属性访问）"""
    from workflows.executor import _safe_eval

    env = {"results": {"status": "success"}}
    assert _safe_eval("results['status'] == 'success'", env) is True


def test_safe_eval_if_exp():
    """三元表达式"""
    from workflows.executor import _safe_eval

    assert _safe_eval("1 if True else 2", {}) == 1
    assert _safe_eval("1 if False else 2", {}) == 2


def test_safe_eval_disallowed_call():
    """禁止函数调用"""
    from workflows.executor import _safe_eval

    with pytest.raises(ValueError):
        _safe_eval("len('abc')", {})


def test_safe_eval_disallowed_attribute():
    """禁止属性访问（非名称）"""
    from workflows.executor import _safe_eval

    with pytest.raises(ValueError):
        _safe_eval("().__class__", {})


def test_safe_eval_name_error():
    """未定义名称报错"""
    from workflows.executor import _safe_eval

    with pytest.raises(NameError):
        _safe_eval("undefined_var", {})


# ══════════════════════════════════════════════════════════════
# SSRF 防护
# ══════════════════════════════════════════════════════════════


def test_is_safe_url_public():
    """公网 URL 安全"""
    from workflows.executor import _is_safe_url

    # mock gethostbyname 返回公网 IP
    with patch("workflows.executor.socket.gethostbyname", return_value="8.8.8.8"):
        assert _is_safe_url("https://api.example.com/data") is True


def test_is_safe_url_localhost():
    """localhost 被阻止"""
    from workflows.executor import _is_safe_url

    with patch("workflows.executor.socket.gethostbyname", return_value="127.0.0.1"):
        assert _is_safe_url("http://localhost:8080/admin") is False


def test_is_safe_url_private_ip():
    """私有 IP 被阻止"""
    from workflows.executor import _is_safe_url

    with patch("workflows.executor.socket.gethostbyname", return_value="10.0.0.5"):
        assert _is_safe_url("http://internal-service/api") is False

    with patch("workflows.executor.socket.gethostbyname", return_value="192.168.1.1"):
        assert _is_safe_url("http://192.168.1.1/api") is False


def test_is_safe_url_invalid_scheme():
    """非 http(s) 协议被阻止"""
    from workflows.executor import _is_safe_url

    assert _is_safe_url("ftp://example.com/file") is False
    assert _is_safe_url("file:///etc/passwd") is False


# ══════════════════════════════════════════════════════════════
# 节点执行
# ══════════════════════════════════════════════════════════════


def test_execute_delay_node(test_db_path):
    """Delay 节点"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_delay_node({"seconds": 0.01}, {}))
    assert result["status"] == "delayed"
    assert result["seconds"] == 0.01


def test_execute_condition_node(test_db_path):
    """Condition 节点（使用下标访问）"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    results = {"node1": {"status": "success"}}
    result = run(
        executor.execute_condition_node(
            {"expression": "results['node1']['status'] == 'success'"},
            results,
        )
    )
    assert result["status"] == "evaluated"
    assert result["result"] is True


def test_execute_condition_node_empty(test_db_path):
    """Condition 节点空表达式"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_condition_node({"expression": ""}, {}))
    assert result["status"] == "error"
    assert "为空" in result["message"]


def test_execute_code_node(test_db_path):
    """Code 节点执行简单 Python"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_code_node({"code": "print('hello world')"}, {}))
    assert result["status"] == "success"
    assert "hello world" in result["stdout"]
    assert result["returncode"] == 0


def test_execute_code_node_empty(test_db_path):
    """Code 节点空代码"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_code_node({"code": ""}, {}))
    assert result["status"] == "error"
    assert "不能为空" in result["message"]


def test_execute_code_node_unsupported_language(test_db_path):
    """Code 节点不支持的语言"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_code_node({"code": "console.log(1)", "language": "javascript"}, {}))
    assert result["status"] == "error"
    assert "javascript" in result["message"]


def test_execute_unknown_node_type(test_db_path):
    """未知节点类型"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_node("unknown_type", {}, {}, {}))
    assert result["status"] == "unknown_type"


def test_execute_parallel_node(test_db_path):
    """Parallel 扇出节点：透传成功标记（并行由 DAG 层保证，节点本身不产生新结果）"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_node("parallel", {}, {}, {}))
    assert result["status"] == "success"
    assert result["type"] == "parallel"
    # wait_all 缺省 true（全收敛语义）
    assert result["wait_all"] is True


def test_execute_parallel_node_custom_wait_all(test_db_path):
    """Parallel 节点 wait_all 可配"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_node("parallel", {"wait_all": False}, {}, {}))
    assert result["status"] == "success"
    assert result["wait_all"] is False


def test_agent_node_row_get_regression(test_db_path, monkeypatch):
    """回归：agent 节点命中 DB 行（sqlite3.Row）时不得因 Row.get 崩溃（v22 修复）。"""
    import common.db
    import common.llm
    from workflows.executor import WorkflowExecutor

    async def fake_fc(system, prompt, tools, **kw):
        return {"content": "ok", "tool_calls": None}

    monkeypatch.setattr(common.llm, "call_llm_with_tools_async", fake_fc)

    conn = common.db.get_db()
    conn.execute(
        "INSERT INTO agents (id, name, description, instructions, model, tools, "
        "knowledge_base_ids, skill_ids, mcp_server_ids, active, created_at) "
        "VALUES ('agent_wfx', 'wx', '', '你是助手', 'agnes-2.5-flash', '[\"code_interpreter\"]', '[]', '[]', '[]', 1, '2026-01-01')",
    )
    conn.commit()
    conn.close()

    executor = WorkflowExecutor()
    out = run(executor.execute_node("agent", {"agent_id": "agent_wfx", "message": "hi"}, {}, {}))
    assert out["status"] == "success"
    assert out["result"] == "ok"


def test_execute_http_node_ssrf(test_db_path):
    """HTTP 节点 SSRF 防护"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    with patch("workflows.executor.socket.gethostbyname", return_value="127.0.0.1"):
        result = run(executor.execute_http_node({"url": "http://localhost:8080/admin", "method": "GET"}, {}))
    assert result["status"] == "error"
    assert "不安全" in result["message"]


def test_execute_http_node_no_url(test_db_path):
    """HTTP 节点空 URL"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    result = run(executor.execute_http_node({"url": "", "method": "GET"}, {}))
    assert result["status"] == "error"
    assert "URL" in result["message"]


# ══════════════════════════════════════════════════════════════
# DAG 构建
# ══════════════════════════════════════════════════════════════


def test_build_dag_simple():
    """简单 DAG 构建（邻接表存储 (dst, port) 元组）"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    nodes = [
        {"id": "n1", "type": "delay", "config": {"seconds": 0.01}},
        {"id": "n2", "type": "delay", "config": {"seconds": 0.01}},
        {"id": "n3", "type": "delay", "config": {"seconds": 0.01}},
    ]
    connections = [
        {"source": "n1", "target": "n2"},
        {"source": "n2", "target": "n3"},
    ]
    adj, in_degree = executor._build_dag(nodes, connections)
    assert adj["n1"] == [("n2", "")]
    assert adj["n2"] == [("n3", "")]
    assert in_degree["n1"] == 0
    assert in_degree["n2"] == 1
    assert in_degree["n3"] == 1


def test_build_dag_condition_branch():
    """条件分支 DAG：if_true / if_false 边端口保留"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    nodes = [
        {"id": "cond", "type": "condition", "config": {"expression": "True"}},
        {"id": "true_branch", "type": "delay"},
        {"id": "false_branch", "type": "delay"},
    ]
    connections = [
        {"source": "cond", "target": "true_branch", "source_port": "if_true"},
        {"source": "cond", "target": "false_branch", "source_port": "if_false"},
    ]
    adj, in_degree = executor._build_dag(nodes, connections)
    assert ("true_branch", "if_true") in adj["cond"]
    assert ("false_branch", "if_false") in adj["cond"]
    assert in_degree["true_branch"] == 1
    assert in_degree["false_branch"] == 1


def test_build_dag_parallel():
    """并行 DAG 构建（两个独立分支）"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    nodes = [
        {"id": "start", "type": "delay"},
        {"id": "a", "type": "delay"},
        {"id": "b", "type": "delay"},
        {"id": "end", "type": "delay"},
    ]
    connections = [
        {"source": "start", "target": "a"},
        {"source": "start", "target": "b"},
        {"source": "a", "target": "end"},
        {"source": "b", "target": "end"},
    ]
    adj, in_degree = executor._build_dag(nodes, connections)
    assert in_degree["start"] == 0
    assert in_degree["a"] == 1
    assert in_degree["b"] == 1
    assert in_degree["end"] == 2


# ══════════════════════════════════════════════════════════════
# 工作流执行
# ══════════════════════════════════════════════════════════════


def test_execute_workflow_simple(test_db_path):
    """执行简单工作流（单节点 delay）"""
    from common.db import get_db
    from workflows.executor import WorkflowExecutor

    # 创建工作流
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, steps, connections, created_at, active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        (
            "wf_exec_test_1",
            "测试工作流",
            json.dumps([{"id": "n1", "type": "delay", "config": {"seconds": 0.01}, "name": "delay1"}]),
            json.dumps([]),
            "2024-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()

    executor = WorkflowExecutor()
    run_id = run(executor.execute("wf_exec_test_1", {"message": "test"}))

    assert run_id.startswith("run_")

    # 验证运行记录
    conn = get_db()
    run_record = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    assert run_record is not None
    assert run_record["status"] == "completed"


def test_execute_workflow_not_found(test_db_path):
    """执行不存在的工作流应报错"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    with pytest.raises(ValueError) as exc_info:
        run(executor.execute("nonexistent_wf", {}))
    assert "不存在" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# 条件分支路由
# ══════════════════════════════════════════════════════════════


def test_skip_downstream_propagation():
    """_skip_downstream 传播跳过到无其他依赖的后续节点"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    in_degree = {"a": 1, "b": 1, "c": 1}
    adjacency = {"a": [("b", "")], "b": [("c", "")]}
    processed = set()
    results = {}
    executor._skip_downstream("a", in_degree, adjacency, processed, results, "run_test")
    assert "a" in processed
    assert "b" in processed
    assert "c" in processed
    assert results["a"]["status"] == "skipped"
    assert results["b"]["status"] == "skipped"
    assert results["c"]["status"] == "skipped"
    assert in_degree["b"] == 0
    assert in_degree["c"] == 0


def test_skip_downstream_blocked_by_other_dependency():
    """_skip_downstream 不跳过有其他未处理上游的节点"""
    from workflows.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    in_degree = {"a": 1, "b": 2}  # b 依赖 a 和另一个未处理节点
    adjacency = {"a": [("b", "")]}
    processed = set()
    results = {}
    executor._skip_downstream("a", in_degree, adjacency, processed, results, "run_test")
    assert "a" in processed
    assert "b" not in processed  # b 仍有 in_degree=1，不被跳过
    assert in_degree["b"] == 1


def test_condition_routing_true_branch(test_db_path):
    """条件为 True 时 if_true 分支执行，if_false 分支跳过"""
    from common.db import get_db
    from workflows.executor import WorkflowExecutor

    nodes = [
        {"id": "cond", "type": "condition", "config": {"expression": "True"}},
        {"id": "yes", "type": "delay", "config": {"seconds": 0.01}},
        {"id": "no", "type": "delay", "config": {"seconds": 0.01}},
    ]
    connections = [
        {"source": "cond", "target": "yes", "source_port": "if_true"},
        {"source": "cond", "target": "no", "source_port": "if_false"},
    ]
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, steps, connections, created_at, active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        ("wf_cond_true", "条件路由测试-True", json.dumps(nodes), json.dumps(connections), "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    executor = WorkflowExecutor()
    run_id = run(executor.execute("wf_cond_true", {}))

    conn = get_db()
    run_record = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    output = json.loads(run_record["output_data"])
    assert output["cond"]["result"] is True
    assert output["yes"]["status"] == "delayed"
    assert output["no"]["status"] == "skipped"


def test_condition_routing_false_branch(test_db_path):
    """条件为 False 时 if_false 分支执行，if_true 分支跳过"""
    from common.db import get_db
    from workflows.executor import WorkflowExecutor

    nodes = [
        {"id": "cond", "type": "condition", "config": {"expression": "False"}},
        {"id": "yes", "type": "delay", "config": {"seconds": 0.01}},
        {"id": "no", "type": "delay", "config": {"seconds": 0.01}},
    ]
    connections = [
        {"source": "cond", "target": "yes", "source_port": "if_true"},
        {"source": "cond", "target": "no", "source_port": "if_false"},
    ]
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, steps, connections, created_at, active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        ("wf_cond_false", "条件路由测试-False", json.dumps(nodes), json.dumps(connections), "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    executor = WorkflowExecutor()
    run_id = run(executor.execute("wf_cond_false", {}))

    conn = get_db()
    run_record = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    output = json.loads(run_record["output_data"])
    assert output["cond"]["result"] is False
    assert output["yes"]["status"] == "skipped"
    assert output["no"]["status"] == "delayed"


def test_condition_routing_merge_branches(test_db_path):
    """条件分支后汇聚到同一节点：无论走哪个分支，汇聚节点都执行"""
    from common.db import get_db
    from workflows.executor import WorkflowExecutor

    nodes = [
        {"id": "cond", "type": "condition", "config": {"expression": "True"}},
        {"id": "yes", "type": "delay", "config": {"seconds": 0.01}},
        {"id": "no", "type": "delay", "config": {"seconds": 0.01}},
        {"id": "merge", "type": "delay", "config": {"seconds": 0.01}},
    ]
    connections = [
        {"source": "cond", "target": "yes", "source_port": "if_true"},
        {"source": "cond", "target": "no", "source_port": "if_false"},
        {"source": "yes", "target": "merge"},
        {"source": "no", "target": "merge"},
    ]
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, steps, connections, created_at, active)
           VALUES (?, ?, ?, ?, ?, 1)""",
        ("wf_cond_merge", "条件路由测试-汇聚", json.dumps(nodes), json.dumps(connections), "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    executor = WorkflowExecutor()
    run_id = run(executor.execute("wf_cond_merge", {}))

    conn = get_db()
    run_record = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    output = json.loads(run_record["output_data"])
    assert output["cond"]["result"] is True
    assert output["yes"]["status"] == "delayed"
    assert output["no"]["status"] == "skipped"
    assert output["merge"]["status"] == "delayed"  # 汇聚节点仍执行（yes 路径激活）


# ════════════════════════════════════════════════════════════════
# P2 循环节点（for-each + 限次）
# ════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_loop_node_foreach_with_cap(setup_test_db):
    """items 逐项执行内层节点；max_iterations 截断；单项错误不中断（status=partial）。"""
    from workflows.executor import WorkflowExecutor

    ex = WorkflowExecutor()
    out = await ex.execute_node(
        "loop",
        {
            "items": ["a", "b", "c", "d", "e"],
            "body": "delay",
            "body_config": {"seconds": 0},
            "max_iterations": 3,
        },
        {},
    )
    assert out["count"] == 3, "max_iterations=3 应只跑 3 项"
    assert out["truncated"] is True
    assert out["status"] == "success"
    assert [r["item"] for r in out["results"]] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_loop_node_unknown_body_reports_partial(setup_test_db):
    """内层节点未知类型 → 单项 error，循环继续，整体 status=partial。"""
    from workflows.executor import WorkflowExecutor

    ex = WorkflowExecutor()
    out = await ex.execute_node(
        "loop",
        {"items": [1, 2], "body": "no_such_type", "body_config": {}},
        {},
    )
    assert out["status"] == "partial"
    assert out["errors"] == 2
    assert out["count"] == 2


@pytest.mark.asyncio
async def test_loop_node_until_mode(setup_test_db, monkeypatch):
    """until 迭代模式：重复执行内层直到输出 key==value，达上限则 status=max_reached。"""
    from workflows.executor import WorkflowExecutor

    ex = WorkflowExecutor()
    seq = iter([
        {"status": "success", "done": False, "round": 1},
        {"status": "success", "done": True, "round": 2},
    ])

    async def fake_node(node_type, config, previous, input_data=None):
        return next(seq)

    monkeypatch.setattr(ex, "execute_node", fake_node)
    out = await ex.execute_loop_node(
        {"body": "code", "body_config": {}, "until": {"key": "done", "value": True}, "max_iterations": 3},
        {},
    )
    assert out["until_satisfied"] is True
    assert out["count"] == 2, "第 2 轮满足即停"
    assert out["status"] == "success"

    # 永远不满足 → max_reached
    async def never(node_type, config, previous, input_data=None):
        return {"status": "success", "done": False}

    monkeypatch.setattr(ex, "execute_node", never)
    out2 = await ex.execute_loop_node(
        {"body": "code", "body_config": {}, "until": {"key": "done", "value": True}, "max_iterations": 4},
        {},
    )
    assert out2["until_satisfied"] is False
    assert out2["count"] == 4
    assert out2["status"] == "max_reached"
