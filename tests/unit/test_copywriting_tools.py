"""v15 文案创作增强单测：模板/平台适配参数注入。

覆盖：
- _PLATFORM_STYLES：6 个平台（公众号/小红书/抖音/知乎/微博/头条）规格齐全
- _build_copywriting_prompt：platform 非空时注入「平台适配」规则块、空/未知平台不注入
- generate_copywriting 端点：platform 参数透传到异步任务 payload
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


class TestPlatformStyles:
    def test_required_platforms_present(self):
        from extended_api import _PLATFORM_STYLES

        assert set(_PLATFORM_STYLES.keys()) == {
            "wechat",
            "xiaohongshu",
            "douyin",
            "zhihu",
            "weibo",
            "toutiao",
        }

    def test_each_platform_has_full_spec(self):
        from extended_api import _PLATFORM_STYLES

        for key, spec in _PLATFORM_STYLES.items():
            assert spec["label"], f"{key} 缺少 label"
            assert spec["title"], f"{key} 缺少标题要求"
            assert isinstance(spec["rules"], list) and len(spec["rules"]) >= 3, f"{key} 规则不足3条"

    def test_platform_labels_distinct(self):
        from extended_api import _PLATFORM_STYLES

        labels = [s["label"] for s in _PLATFORM_STYLES.values()]
        assert len(set(labels)) == len(labels)


class TestCopywritingPrompt:
    def test_platform_block_injected(self):
        from extended_api import _build_copywriting_prompt

        prompt = _build_copywriting_prompt("social", "测试", platform="xiaohongshu")
        assert "## 平台适配" in prompt
        assert "小红书" in prompt
        assert "标题含关键词" in prompt
        assert "话题标签" in prompt

    def test_no_platform_no_block(self):
        from extended_api import _build_copywriting_prompt

        # 用「## 平台适配」章节头精确断言（social 规格的 focus 本身含“平台适配”字样）
        assert "## 平台适配" not in _build_copywriting_prompt("social", "测试")
        assert "## 平台适配" not in _build_copywriting_prompt("social", "测试", "")
        assert "## 平台适配" not in _build_copywriting_prompt("social", "测试", None)

    def test_unknown_platform_ignored(self):
        from extended_api import _build_copywriting_prompt

        prompt = _build_copywriting_prompt("marketing", "测试", "unknown_platform")
        assert "## 平台适配" not in prompt

    def test_spec_core_kept_with_platform(self):
        from extended_api import _build_copywriting_prompt

        prompt = _build_copywriting_prompt("seo", "测试", "wechat")
        assert "SEO内容策略专家" in prompt  # 类型规格仍生效
        assert "公众号" in prompt


class TestGenerateEndpoint:
    def test_platform_passed_to_payload(self, setup_test_db, monkeypatch):
        import extended_api
        from extended_api import CopywritingRequest

        captured = {}

        def fake_create_task(job_type, payload, **kw):
            captured["job_type"] = job_type
            captured["payload"] = payload
            return {"id": "task_1", "status": "pending"}

        monkeypatch.setattr(extended_api, "create_task", fake_create_task)
        resp = asyncio.run(
            extended_api.generate_copywriting(
                CopywritingRequest(
                    type="social", title="t", prompt="写一条小红书种草文案", platform="xiaohongshu"
                ),
                current_user=USER,
            )
        )
        assert resp["ok"] is True
        assert captured["job_type"] == "copywriting_generate"
        assert captured["payload"]["platform"] == "xiaohongshu"
        assert captured["payload"]["type"] == "social"
        assert captured["payload"]["user_id"] == "u1"

    def test_platform_default_empty(self, setup_test_db, monkeypatch):
        import extended_api
        from extended_api import CopywritingRequest

        captured = {}

        def fake_create_task(job_type, payload, **kw):
            captured["payload"] = payload
            return {"id": "task_1", "status": "pending"}

        monkeypatch.setattr(extended_api, "create_task", fake_create_task)
        asyncio.run(
            extended_api.generate_copywriting(
                CopywritingRequest(type="marketing", title="", prompt="测试"), current_user=USER
            )
        )
        assert captured["payload"]["platform"] == ""
