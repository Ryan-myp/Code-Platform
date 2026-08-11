"""v20 图片工厂单测：AI 提示词润色接口。

覆盖：
- enhance_prompt：LLM 成功返回增强文本 + 自动负面词建议
- LLM 失败静默回退原 prompt
- 空输入/超长输入参数校验
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


@pytest.fixture(autouse=True)
def _isolated_image_dir(monkeypatch, tmp_path):
    """IMAGE_DIR 指向临时目录，避免污染真实产物目录。"""
    import image_factory

    monkeypatch.setattr(image_factory, "IMAGE_DIR", str(tmp_path))
    return tmp_path


class TestEnhancePrompt:
    """AI 润色提示词：增强/回退/参数校验。"""

    async def _call(self, prompt):
        import image_factory

        return await image_factory.enhance_prompt(prompt=prompt, current_user={"user_id": "u1"})

    def test_success_enhanced(self):
        with patch("common.llm.call_llm_async", new_callable=AsyncMock, return_value="一位少女站在金色麦田里，仰头望向天空，阳光洒落发丝，电影感构图，柔和逆光，细腻肌理，4k 高清"):
            out = self._call_sync("一个少女在麦田")
        assert out["ok"] is True
        assert out["original"] == "一个少女在麦田"
        assert "少女" in out["enhanced"] and "麦田" in out["enhanced"]
        assert "low quality" in out["negative_auto"]
        assert "blurry" in out["negative_auto"]

    def test_fallback_on_llm_failure(self):
        with patch("common.llm.call_llm_async", new_callable=AsyncMock, side_effect=RuntimeError("LLM 挂了")):
            out = self._call_sync("一只橘猫在窗台上晒太阳")
        assert out["ok"] is True
        assert out["enhanced"] == "一只橘猫在窗台上晒太阳"  # 静默回退原 prompt
        assert out["original"] == "一只橘猫在窗台上晒太阳"

    def test_fallback_on_empty_output(self):
        with patch("common.llm.call_llm_async", new_callable=AsyncMock, return_value="   "):
            out = self._call_sync("海边日落")
        assert out["enhanced"] == "海边日落"

    def test_empty_prompt_rejected(self):
        with pytest.raises(HTTPException) as ei:
            self._call_sync("   ")
        assert ei.value.status_code == 400
        assert "请输入" in str(ei.value.detail)

    def test_too_long_rejected(self):
        with pytest.raises(HTTPException) as ei:
            self._call_sync("字" * 501)
        assert ei.value.status_code == 400
        assert "500 字以内" in str(ei.value.detail)

    def test_endpoint_registered(self):
        import image_factory

        paths = [r.path for r in image_factory.router.routes]
        assert "/api/image-factory/enhance-prompt" in paths

    def _call_sync(self, prompt):
        import asyncio

        return asyncio.run(self._call(prompt))
