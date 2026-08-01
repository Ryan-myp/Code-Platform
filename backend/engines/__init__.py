#!/usr/bin/env python3
"""biz-delivery 引擎的 Plugin 适配层。
将现有的 review_engine / td_engine / test_engine / learn_repo 包装成 PluginInterface 协议。"""

import os
import sys
import time
from datetime import datetime

from plugin_registry import PluginInterface, registry

# biz-delivery scripts path
BIZ_DIR = "/Users/yanping.ma/biz-delivery/scripts"
if BIZ_DIR not in sys.path:
    sys.path.insert(0, BIZ_DIR)


class BizCodeScanPlugin(PluginInterface):
    """代码扫描插件 — 基于 learn_repo.py 的代码库理解引擎。"""

    name = "biz-code-scan"
    category = "code_analysis"
    version = "1.0.0"
    description = "扫描代码仓库，生成 IR 缓存、业务卡片、核心流程推断"

    def execute(self, input_data: dict) -> dict:
        repo_path = input_data.get("repo_path", "")
        languages = input_data.get("languages", None)

        try:
            from learn_repo import learn_from_repos

            result = learn_from_repos([repo_path], languages=languages or [])

            if isinstance(result, dict):
                return {
                    "status": "success",
                    "result": {
                        "ir_cache": result.get("ir_cache_file", ""),
                        "summary": result.get("summary", "")[:5000],
                        "entities": result.get("entities", []),
                        "functions_count": len(result.get("functions", [])),
                        "routes_count": len(result.get("routes", [])),
                        "business_cards": result.get("business_cards", []),
                    },
                    "meta": {"elapsed": 0},
                }
            return {"status": "success", "result": str(result)[:5000]}
        except Exception as e:
            return {"status": "failed", "error": str(e)}


class BizReviewPlugin(PluginInterface):
    """PRD 审查插件 — 基于 review_engine.py 的智能审查引擎。"""

    name = "biz-review"
    category = "prd_review"
    version = "1.0.0"
    description = "注入代码 IR 证据审查 PRD，22+ 预检查维度"

    def execute(self, input_data: dict) -> dict:
        prd_text = input_data.get("prd_text", "")
        repo_path = input_data.get("repo_path")
        ir_cache = input_data.get("ir_cache")

        start_time = time.time()
        try:
            from review_engine import ReviewEngine

            profile = {
                "name": "platform",
                "repositories": [repo_path] if repo_path else [],
                "ir_cache": ir_cache,
                "kb_dir": "",
                "business_rules": {},
            }
            engine = ReviewEngine(profile)
            result = engine.review(prd_text)
            elapsed = time.time() - start_time

            return {
                "status": "success",
                "result": result.get("report", "") if isinstance(result, dict) else str(result),
                "meta": {"elapsed": elapsed, "dimensions_checked": 22},
            }
        except Exception:
            elapsed = time.time() - start_time
            # Fallback to default LLM
            from main import Agent, get_model, prompt_templates, strip_base64_images

            agent = Agent(name="PRD审查员", model=get_model(), instructions=prompt_templates["review"]["instructions"])
            return {
                "status": "success",
                "result": str(agent.run(strip_base64_images(prd_text))),
                "meta": {"elapsed": elapsed, "fallback": True},
                "note": "biz-delivery unavailable, used fallback",
            }


class BizTDEnginePlugin(PluginInterface):
    """技术方案生成插件 — 基于 td_engine.py。"""

    name = "biz-technical-design"
    category = "tech_design"
    version = "1.0.0"
    description = "基于 PRD + 代码 IR 生成完整技术方案，含 Mermaid 图表"

    def execute(self, input_data: dict) -> dict:
        prd_text = input_data.get("prd_text", "")
        repo_path = input_data.get("repo_path")
        ir_cache = input_data.get("ir_cache")

        start_time = time.time()
        try:
            from td_engine import TDEngine

            profile = {
                "name": "platform",
                "repositories": [repo_path] if repo_path else [],
                "ir_cache": ir_cache,
            }
            engine = TDEngine(profile)
            result = engine.generate_td(prd_text)
            elapsed = time.time() - start_time

            return {
                "status": "success",
                "result": result.get("design", "") if isinstance(result, dict) else str(result),
                "meta": {"elapsed": elapsed},
            }
        except Exception:
            elapsed = time.time() - start_time
            from main import Agent, get_model, prompt_templates, strip_base64_images

            agent = Agent(
                name="架构师", model=get_model(), instructions=prompt_templates["technical_design"]["instructions"]
            )
            return {
                "status": "success",
                "result": str(agent.run(strip_base64_images(prd_text))),
                "meta": {"elapsed": elapsed, "fallback": True},
            }


class BizTestPlugin(PluginInterface):
    """测试用例生成插件 — 基于 test_engine.py。"""

    name = "biz-test-cases"
    category = "testing"
    version = "1.0.0"
    description = "注入错误码和 Request/Response struct 生成测试用例"

    def execute(self, input_data: dict) -> dict:
        prd_text = input_data.get("prd_text", "")
        tech_design = input_data.get("tech_design", "")
        repo_path = input_data.get("repo_path")
        ir_cache = input_data.get("ir_cache")

        start_time = time.time()
        try:
            from test_engine import TestEngine

            profile = {
                "name": "platform",
                "repositories": [repo_path] if repo_path else [],
                "ir_cache": ir_cache,
            }
            engine = TestEngine(profile)
            result = engine.generate_tests(prd_text, tech_design or "")
            elapsed = time.time() - start_time

            return {
                "status": "success",
                "result": result.get("cases", "") if isinstance(result, dict) else str(result),
                "meta": {"elapsed": elapsed},
            }
        except Exception:
            elapsed = time.time() - start_time
            from main import Agent, get_model, prompt_templates, strip_base64_images

            agent = Agent(
                name="测试工程师", model=get_model(), instructions=prompt_templates["test_cases"]["instructions"]
            )
            return {
                "status": "success",
                "result": str(agent.run(strip_base64_images(prd_text))),
                "meta": {"elapsed": elapsed, "fallback": True},
            }


# 注册所有插件

registry.register(BizCodeScanPlugin())
registry.register(BizReviewPlugin())
registry.register(BizTDEnginePlugin())
registry.register(BizTestPlugin())
