"""v13.24 数字人情绪系统单元测试：TTS 情绪通道 / 缓存分区 / 白名单 / LLM 标注 / 表情模板。

不依赖外部网络：_tts_edge 用 mock 拦截子进程调用；_detect_emotion 用 mock 拦截 LLM。
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pydantic import ValidationError


class TestEmotionTtsChannel:
    """声音情绪通道：emotion 参与缓存 key 与子进程参数透传。"""

    def test_tts_cache_key_emotion_partition(self):
        from digital_human import _tts_cache_key

        k_neutral = _tts_cache_key("测试文案", "zh-CN-XiaoxiaoNeural", 1.0, 0, "")
        k_happy = _tts_cache_key("测试文案", "zh-CN-XiaoxiaoNeural", 1.0, 0, "cheerful")
        k_sad = _tts_cache_key("测试文案", "zh-CN-XiaoxiaoNeural", 1.0, 0, "sad")
        assert k_neutral != k_happy != k_sad
        # 同情绪幂等
        assert _tts_cache_key("测试文案", "zh-CN-XiaoxiaoNeural", 1.0, 0, "cheerful") == k_happy

    def test_tts_edge_emotion_maps_to_pitch(self):
        """v13.28：emotion 不再透传 SSML style（语速黑洞），改映射为 pitch 叠加。"""
        import voice_factory as vf

        cases = [
            ("cheerful", "+15Hz"),  # happy 的 Azure 风格别名
            ("happy", "+15Hz"),
            ("sad", "-15Hz"),
            ("angry", "+12Hz"),
            ("gentle", "-5Hz"),
            ("serious", ""),  # pitch 叠加 0 → 参数为空串（不追加 Hz）
        ]
        for emotion, expect_pitch in cases:
            captured = {}

            def fake_run(args, **kwargs):
                captured["args"] = args
                with open(args[5], "wb") as f:  # args[5]=tmp 输出路径
                    f.write(b"fake-mp3-bytes-ok")
                return SimpleNamespace(returncode=0, stderr=b"")

            with patch("voice_factory.subprocess.run", side_effect=fake_run):
                out = vf._tts_edge("今天真开心", "zh-CN-XiaoxiaoNeural", 1.0, 0, emotion)

            assert out == b"fake-mp3-bytes-ok"
            args = captured["args"]
            # [py, worker, text, voice, rate, tmp, pitch, words]——无 style 参数
            assert args[2] == "今天真开心"
            assert args[3] == "zh-CN-XiaoxiaoNeural"
            assert args[6] == expect_pitch, f"{emotion} 应映射 pitch {expect_pitch}"
            assert args[7] == ""  # words_path 占位
            assert len(args) == 8  # 不再透传 style

    def test_tts_edge_no_style_when_empty(self):
        """无情绪时不传 style 参数（兼容音乐工厂等旧调用方）。"""
        import voice_factory as vf

        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            with open(args[5], "wb") as f:
                f.write(b"fake-mp3-bytes-ok")
            return SimpleNamespace(returncode=0, stderr=b"")

        with patch("voice_factory.subprocess.run", side_effect=fake_run):
            vf._tts_edge("普通语音", "zh-CN-XiaoxiaoNeural", 1.0)

        assert len(captured["args"]) == 8  # 不追加 style
        assert captured["args"][7] == ""


class TestEmotionRequestValidation:
    """请求模型白名单：非法情绪值应被 pydantic 拒绝。"""

    def test_generate_request_rejects_invalid_emotion(self):
        from digital_human import GenerateRequest

        with pytest.raises(ValidationError):
            GenerateRequest(text="这是一段测试口播文案内容", emotion="bogus")
        with pytest.raises(ValidationError):
            GenerateRequest(text="这是一段测试口播文案内容", emotion="HAPPY")

    def test_generate_request_accepts_valid_emotions(self):
        from digital_human import GenerateRequest

        for emo in ("auto", "neutral", "happy", "sad", "angry", "gentle", "serious"):
            req = GenerateRequest(text="这是一段测试口播文案内容", emotion=emo)
            assert req.emotion == emo

    def test_batch_request_rejects_invalid_emotion(self):
        from digital_human import BatchGenerateRequest

        with pytest.raises(ValidationError):
            BatchGenerateRequest(texts=["测试文案一条"], emotion="angry!!")


class TestDetectEmotion:
    """LLM 情绪标注：正常/中文别名/非法输出/异常均需安全回落。"""

    def test_valid_english_label(self):
        with patch("common.llm.call_llm", return_value="happy"):
            from digital_human import _detect_emotion

            assert _detect_emotion("测试文案") == "happy"

    def test_chinese_alias_fuzzy_match(self):
        with patch("common.llm.call_llm", return_value="情绪的答案是：悲伤"):
            from digital_human import _detect_emotion

            assert _detect_emotion("测试文案") == "sad"

    def test_invalid_output_falls_back_neutral(self):
        with patch("common.llm.call_llm", return_value="BOGUS 123"):
            from digital_human import _detect_emotion

            assert _detect_emotion("测试文案") == "neutral"

    def test_llm_exception_falls_back_neutral(self):
        with patch("common.llm.call_llm", side_effect=RuntimeError("llm down")):
            from digital_human import _detect_emotion

            assert _detect_emotion("测试文案") == "neutral"


class TestEmotionFaceRender:
    """2D 情绪表情：参数表完整 + 表情模板差异化输出。"""

    def test_emotion_face_table_complete(self):
        from digital_human import _EMOTION_FACE

        for emo in ("neutral", "happy", "sad", "angry", "gentle", "serious"):
            cfg = _EMOTION_FACE[emo]
            for k in ("brow", "brow_k", "squint", "smile", "cheek", "move", "head"):
                assert k in cfg, f"{emo} 缺 {k}"
            assert 0.0 <= cfg["squint"] <= 1.0

    def test_mouth_template_smile_variants_differ(self):
        """微笑（+1）与撇嘴（-1）模板像素必须不同，且 smile=0 与原始一致。"""
        from digital_human import _get_mouth_template

        smile_up = _get_mouth_template(3, 2, 1.0)
        smile_down = _get_mouth_template(3, 2, -1.0)
        smile_zero = _get_mouth_template(3, 2, 0.0)
        assert smile_up.tobytes() != smile_down.tobytes()
        assert smile_up.tobytes() != smile_zero.tobytes()
        # 开度档位仍有区分（回归：smile 维度不应破坏原有分级）
        assert _get_mouth_template(1, 2, 0.5).tobytes() != _get_mouth_template(5, 2, 0.5).tobytes()

    def test_eyebrow_poses_differ(self):
        """四种眉形贴图输出必须不同（情绪差异可视化基础）。"""
        from digital_human import _get_eyebrow_template

        poses = {p: _get_eyebrow_template(60, p) for p in ("flat", "rise", "droop", "knit")}
        for p1, img1 in poses.items():
            for p2, img2 in poses.items():
                if p1 != p2:
                    assert img1.tobytes() != img2.tobytes(), f"{p1} 与 {p2} 输出相同"


class TestDramaEmotionCleanup:
    """短剧剧本情绪清洗：合法保留、中文映射、非法回落 neutral、缺省补 neutral。"""

    def test_parse_script_emotion_whitelist(self):
        from short_drama import _parse_script

        raw = """{"title": "T", "scenes": [
            {"id": 1, "dialogue": "a", "emotion": "happy", "sec": 5},
            {"id": 2, "dialogue": "b", "emotion": "悲伤", "sec": 5},
            {"id": 3, "dialogue": "c", "emotion": "BOGUS", "sec": 5},
            {"id": 4, "dialogue": "d", "sec": 5}
        ]}"""
        script = _parse_script(raw)
        emotions = [s["emotion"] for s in script["scenes"]]
        assert emotions == ["happy", "sad", "neutral", "neutral"]
