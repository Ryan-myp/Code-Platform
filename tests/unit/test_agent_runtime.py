"""Agent 运行时（v17.0）单测：绑定资源接入执行链路。

覆盖：RAG 上下文组装 / 技能注入 / 工具白名单 / 工具指令解析与清洗 / 沙箱工具真实执行 /
绑定资源损坏时的降级不阻断。
"""

import pytest
from fastapi import HTTPException


@pytest.fixture
def runtime():
    import agent_runtime

    return agent_runtime


def test_parse_tool_directives(runtime):
    text = "先用计算器算一下。\n[TOOL:code_interpreter|print(1+1)]\n[TOOL:regex-builder|检查 ^\\d+$ 匹配 12345]\n[TOOL:evil_tool|rm -rf /]"
    out = runtime.parse_tool_directives(text, {"code_interpreter", "regex-builder"})
    # 白名单过滤：evil_tool 不执行；最多 2 条
    assert [o[0] for o in out] == ["code_interpreter", "regex-builder"]
    assert out[0][1] == "print(1+1)"


def test_parse_directives_no_whitelist(runtime):
    assert runtime.parse_tool_directives("[TOOL:code_interpreter|1]", set()) == []


def test_strip_tool_directives(runtime):
    text = "答案是 2。\n[TOOL:code_interpreter|print(1+1)]"
    assert "TOOL:" not in runtime.strip_tool_directives(text)
    assert runtime.strip_tool_directives("答案是 2。").startswith("答案是")


def test_semantic_map(runtime):
    assert runtime._SEMANTIC_TOOL_MAP.get("code_interpreter") == "code_interpreter"


def test_load_agent_bundle_missing_404(runtime):
    with pytest.raises(HTTPException):
        runtime.load_agent_bundle("no_such_agent", "hi")


def test_tool_descriptions_runnable(runtime):
    lines, runnable = runtime._tool_descriptions(["code_interpreter", "regex-builder", "terminal", "weekly-report"])
    assert "code_interpreter" in runnable
    assert "regex-builder" in runnable  # compute 实算
    assert "terminal" not in runnable  # 诚实降级
    assert any("code_interpreter" in line for line in lines)


@pytest.mark.asyncio
async def test_execute_code_interpreter_runtime(runtime, monkeypatch):
    # 真实沙箱执行（不 mock：直接跑，验证受限子进程可用）
    out = await runtime.execute_tool_async("code_interpreter", "print(6*7)")
    assert "42" in out


@pytest.mark.asyncio
async def test_execute_unknown_tool_degrade(runtime):
    out = await runtime.execute_tool_async("no_such_tool_xyz", "hi")
    assert "不存在" in out or "失败" in out


def test_kb_rag_empty_query(runtime, tmp_path):
    assert runtime._kb_rag_context(["kb-x"], "") == ""
    assert runtime._kb_rag_context([], "问题") == ""


def test_kb_rag_file(setup_test_db, tmp_path):
    """绑定 file 知识库 → 检索命中注入 rag_context（真实 DB + 真实文件）。"""
    from datetime import datetime

    import kb_api
    from common.db import get_db

    doc = tmp_path / "ad.md"
    doc.write_text("广告出价策略：智能出价支持分时段与自动调价\n仓库管理：先进先出原则", encoding="utf-8")

    # file KB 检索（内部函数，不依赖路由）
    kb_row = {"type": "file", "path": str(tmp_path), "name": "测试库", "id": "kb-x", "config": "{}"}
    res = kb_api._kb_search_file(kb_row, "广告出价策略", 3)
    assert res["count"] >= 1
    assert any("广告出价策略" in m for m in res["hits"][0]["matches"]), "强相关行应排第一"

    # 插入 KB 行到测试库 → _kb_rag_context 注入「参考知识」段
    conn = get_db()
    conn.execute(
        "INSERT INTO knowledge_bases (id, name, type, path, created_at) VALUES (?,?,?,?,?)",
        ("kb-x", "测试库", "file", str(tmp_path), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    import agent_runtime

    ctx = agent_runtime._kb_rag_context(["kb-x"], "广告出价策略")
    assert "参考知识" in ctx
    assert "广告出价策略" in ctx
    assert "测试库" in ctx
