"""v20 视频工厂单测：AI 画质增强提示词接口。

覆盖：
- enhance_prompt：ti2vid 增强成功、i2vid 保留主体前缀指令
- LLM 失败静默回退原 prompt
- 空输入/超长输入参数校验、mode 归一化
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


@pytest.fixture(autouse=True)
def _isolated_video_dir(monkeypatch, tmp_path):
    """VIDEO_DIR 指向临时目录，避免污染真实产物目录。"""
    import video_factory

    monkeypatch.setattr(video_factory, "VIDEO_DIR", tmp_path)
    return tmp_path


class TestEnhancePrompt:
    """AI 画质增强：增强/回退/参数校验/mode 处理。"""

    def _call(self, prompt, mode="ti2vid"):
        import video_factory

        return asyncio.run(
            video_factory.enhance_prompt(prompt=prompt, mode=mode, current_user={"user_id": "u1"})
        )

    def test_ti2vid_success(self):
        with patch("common.llm.call_llm_async", new_callable=AsyncMock, return_value="黄昏海面，金色阳光在浪尖跳动，镜头缓慢推进，低角度广角，海鸥掠过，温暖氛围，电影感画质"):
            out = self._call("海边黄昏")
        assert out["ok"] is True
        assert out["mode"] == "ti2vid"
        assert "海" in out["enhanced"]
        assert out["original"] == "海边黄昏"

    def test_i2vid_keeps_subject_prefix_instruction(self):
        captured = {}

        async def _fake_llm(system, user, **kw):
            captured["system"] = system
            return "穿红裙的女孩保持原样，缓缓转身面向镜头，镜头缓慢推近"

        with patch("common.llm.call_llm_async", new_callable=AsyncMock, side_effect=_fake_llm):
            out = self._call("穿红裙的女孩站在老式电话亭前", mode="i2vid")
        assert out["mode"] == "i2vid"
        assert "图生视频" in captured["system"]
        assert "保留用户描述中的主体特征" in captured["system"]
        assert "穿红裙的女孩" in out["enhanced"]

    def test_ti2vid_no_prefix_instruction(self):
        captured = {}

        async def _fake_llm(system, user, **kw):
            captured["system"] = system
            return "城市夜景灯光璀璨，镜头缓缓拉远，展现高楼全貌，冷色调氛围"

        with patch("common.llm.call_llm_async", new_callable=AsyncMock, side_effect=_fake_llm):
            self._call("城市夜景", mode="ti2vid")
        assert "图生视频" not in captured["system"]

    def test_fallback_on_llm_failure(self):
        with patch("common.llm.call_llm_async", new_callable=AsyncMock, side_effect=RuntimeError("LLM 挂了")):
            out = self._call("一只猫在雪地里奔跑")
        assert out["ok"] is True
        assert out["enhanced"] == "一只猫在雪地里奔跑"  # 静默回退原 prompt

    def test_empty_prompt_rejected(self):
        with pytest.raises(HTTPException) as ei:
            self._call("   ")
        assert ei.value.status_code == 400
        assert "请输入" in str(ei.value.detail)

    def test_too_long_rejected(self):
        with pytest.raises(HTTPException) as ei:
            self._call("字" * 801)
        assert ei.value.status_code == 400
        assert "800 字以内" in str(ei.value.detail)

    def test_mode_normalization(self):
        with patch("common.llm.call_llm_async", new_callable=AsyncMock, return_value="x" * 30):
            assert self._call("描述", mode="img2vid")["mode"] == "i2vid"
            assert self._call("描述", mode="")["mode"] == "ti2vid"

    def test_endpoint_registered(self):
        import video_factory

        paths = [r.path for r in video_factory.router.routes]
        assert "/api/video-factory/enhance-prompt" in paths
