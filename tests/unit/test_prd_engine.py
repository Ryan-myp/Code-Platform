#!/usr/bin/env python3
"""prd_engine 单元测试 — PRD 生成/审查/技术方案/测试用例/代码生成（mock LLM）。"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def run(coro):
    """同步执行 async 函数的辅助。"""
    return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════
# PRD 生成
# ══════════════════════════════════════════════════════════════


def test_generate_prd(test_db_path):
    """AI 生成 PRD（mock LLM）"""
    from prd_engine import generate_prd

    with patch("prd_engine.call_llm", return_value="# PRD 文档\n## 背景\n这是一个测试PRD"):
        result = generate_prd({"prd_text": "做一个用户管理系统"})

    assert "result" in result
    assert "PRD" in result["result"]


def test_generate_prd_empty(test_db_path):
    """空需求描述应拒绝"""
    from prd_engine import generate_prd

    with pytest.raises(Exception) as exc_info:
        generate_prd({"prd_text": ""})
    assert "400" in str(exc_info.value) or "请输入" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# PRD 审查
# ══════════════════════════════════════════════════════════════


def test_review_prd(test_db_path):
    """PRD 审查（biz-delivery 不可用，fallback LLM）"""
    from prd_engine import review_prd

    with patch("prd_engine.call_llm", return_value="审查报告：总体评分 85/100"):
        result = review_prd({"prd_text": "# PRD\n## 功能需求\n1. 用户注册"})

    assert "result" in result
    assert "85" in result["result"]
    # biz-delivery 不可用时应 fallback
    assert result.get("engine") in ("llm", "biz-delivery")


def test_review_prd_empty(test_db_path):
    """空 PRD 内容应拒绝"""
    from prd_engine import review_prd

    with pytest.raises(Exception) as exc_info:
        review_prd({"prd_text": ""})
    assert "400" in str(exc_info.value) or "请输入" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# 技术方案
# ══════════════════════════════════════════════════════════════


def test_technical_design(test_db_path):
    """技术方案生成（mock LLM）"""
    from prd_engine import technical_design

    with patch("prd_engine.call_llm", return_value="# 技术方案\n## 架构总览\n```mermaid\ngraph TD\n```"):
        result = technical_design({"prd_text": "# PRD\n## 功能需求\n1. 用户注册"})

    assert "result" in result
    assert "技术方案" in result["result"]


def test_technical_design_empty(test_db_path):
    """空 PRD 内容应拒绝"""
    from prd_engine import technical_design

    with pytest.raises(Exception) as exc_info:
        technical_design({"prd_text": ""})
    assert "400" in str(exc_info.value) or "请输入" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# 测试用例
# ══════════════════════════════════════════════════════════════


def test_test_cases(test_db_path):
    """测试用例生成（mock LLM）"""
    from prd_engine import test_cases

    with patch("prd_engine.call_llm", return_value="# 测试用例\n| 编号 | 级别 | 步骤 | 预期结果 |"):
        result = test_cases({"prd_text": "# PRD\n用户注册功能", "tech_design": "# 技术方案\nREST API"})

    assert "result" in result
    assert "测试用例" in result["result"]


def test_test_cases_no_tech_design(test_db_path):
    """测试用例生成（无 tech_design 也能工作）"""
    from prd_engine import test_cases

    with patch("prd_engine.call_llm", return_value="# 测试用例\n仅基于 PRD"):
        result = test_cases({"prd_text": "# PRD\n用户注册功能"})

    assert "result" in result
    assert "测试用例" in result["result"]


def test_test_cases_empty_prd(test_db_path):
    """空 PRD 内容应拒绝"""
    from prd_engine import test_cases

    with pytest.raises(Exception) as exc_info:
        test_cases({"prd_text": ""})
    assert "400" in str(exc_info.value) or "请输入" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# 代码生成
# ══════════════════════════════════════════════════════════════


def test_generate_code(test_db_path):
    """根据技术方案生成代码（mock LLM）"""
    from prd_engine import generate_code

    with patch("prd_engine.call_llm", return_value="```python\nprint('hello')\n```"):
        result = generate_code({"tech_design": "# 技术方案\nREST API", "language": "python"})

    assert "result" in result
    assert "result" in result
    assert result.get("language") == "python"


def test_generate_code_empty(test_db_path):
    """空技术方案应拒绝"""
    from prd_engine import generate_code

    with pytest.raises(Exception) as exc_info:
        generate_code({"tech_design": ""})
    assert "400" in str(exc_info.value) or "请输入" in str(exc_info.value)


def test_generate_code_default_language(test_db_path):
    """代码生成默认语言为 python"""
    from prd_engine import generate_code

    with patch("prd_engine.call_llm", return_value="```python\ndef main(): pass"):
        result = generate_code({"tech_design": "# 方案"})

    assert result["language"] == "python"


# ══════════════════════════════════════════════════════════════
# 代码对话
# ══════════════════════════════════════════════════════════════


def test_code_chat(test_db_path):
    """代码对话 - 追问/修改代码（mock LLM）"""
    from prd_engine import code_chat

    with patch("prd_engine.call_llm", return_value="```python\ndef main():\n    print('updated')\n```"):
        result = code_chat({"message": "修改 main 函数", "language": "python"})

    assert "result" in result
    assert "updated" in result["result"]


def test_code_chat_empty_message(test_db_path):
    """空消息应拒绝"""
    from prd_engine import code_chat

    with pytest.raises(Exception) as exc_info:
        code_chat({"message": ""})
    assert "400" in str(exc_info.value) or "请输入" in str(exc_info.value)
