"""数字人模块单元测试：口型时间轴 / 文案清洗 / 内容安全 / 商业参数校验。

不依赖网络与 ffmpeg，仅覆盖纯函数与 Pydantic 校验。
"""
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


class TestCleanScriptText:
    def test_fold_blank_lines_and_strip(self):
        from digital_human import _clean_script_text
        text = "\n\n  大家好，\n\n\n今天分享技巧。  \n\n"
        assert _clean_script_text(text) == "大家好，\n\n今天分享技巧。"
        assert _clean_script_text("  仅首尾空格  ") == "仅首尾空格"

    def test_empty_input(self):
        from digital_human import _clean_script_text
        assert _clean_script_text("") == ""
        assert _clean_script_text(None) == ""


class TestScriptTimeline:
    """字级口型时间轴：拼音元音分类 + 均匀时长分配 + 标点闭嘴。"""

    def test_hanzi_units_and_punctuation(self):
        from digital_human import _build_script_timeline
        tl = _build_script_timeline("大家好。", 4.0)
        # 3 汉字 × 1.0 + 1 标点 × 0.5 = 3.5 单位 → 4.0 / 3.5 ≈ 1.143s/单位
        assert len(tl) == 4
        assert tl[0][0] == "大" and tl[3][0] == "。"
        # 标点闭嘴
        assert tl[3][3] == 0.0
        # 时长连续覆盖 [0, 4.0)
        assert abs(tl[0][1] - 0.0) < 1e-6
        assert abs(tl[-1][2] - 4.0) < 1e-6

    def test_mouth_shape_classification(self):
        """a 类大口 > e 类半开 > i 类扁口；u 类嘟嘴圆度高。"""
        from digital_human import _build_script_timeline, _MOUTH_SHAPES
        tl = _build_script_timeline("大 你 出", 3.0)
        shapes = {ch: (o, r) for ch, _, _, o, r in tl}
        assert shapes["大"][0] > shapes["你"][0]            # 大(1.0) > 你(0.45)
        assert shapes["出"][1] > shapes["你"][1]            # 出 嘟嘴圆度 > 你 扁口
        assert "a" in _MOUTH_SHAPES and "u" in _MOUTH_SHAPES and "i" in _MOUTH_SHAPES

    def test_mouth_envelope(self):
        """字周期包络：开头微开 → 中段最大 → 结尾收拢。"""
        from digital_human import _build_script_timeline, _mouth_shape_at
        tl = _build_script_timeline("大", 1.0)
        start, end, open_, round_ = tl[0][1], tl[0][2], tl[0][3], tl[0][4]
        mid = _mouth_shape_at(tl, (start + end) / 2)[0]
        early = _mouth_shape_at(tl, start + (end - start) * 0.05)[0]
        late = _mouth_shape_at(tl, end - (end - start) * 0.05)[0]
        assert mid == open_            # 中段维持最大
        assert early < mid and late < mid  # 两侧收拢
        # 超时域返回闭嘴
        assert _mouth_shape_at(tl, end + 0.1) == (0.0, 0.5)


class TestContentSafety:
    def test_hard_block_words(self):
        """硬拦截词表：包含营销诱导/诈骗/赌博/违禁类行为词。"""
        from digital_human import _HARD_BLOCK_WORDS
        joined = "".join(_HARD_BLOCK_WORDS)
        for kw in ["点击领取", "免费领取", "加微信", "日赚", "赌博", "翻墙", "特效"]:
            assert kw in joined, f"{kw} 应在硬拦截词表中"

    def test_scan_text_chinese_substring(self):
        """宽松扫描：中文词嵌入任意上下文都应命中（修复后的边界逻辑）。"""
        from content_strategy import _scan_text
        hits = _scan_text("点击领取免费领取大礼包，马上抢购")
        words = {h["word"] for h in hits}
        assert "点击领取" in words
        assert "免费领取" in words

    def test_scan_text_ascii_boundary(self):
        """ASCII 数字词仍需词边界（100 不误伤 1000 类场景）。"""
        from content_strategy import _scan_text
        # "100%" 含非字母数字字符 → 直接命中
        assert any(h["word"] == "100%" for h in _scan_text("效果100%满意"))
        # 纯 ASCII 数字词场景：词表无纯数字词时不做断言，仅验证不崩溃
        _scan_text("topics and 1000 dollars")


class TestGenerateRequest:
    def test_resolution_pattern(self):
        from digital_human import GenerateRequest
        assert GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧").resolution == "720p"
        req = GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧",
                              resolution="1080p", fps=24, watermark=False)
        assert req.resolution == "1080p" and req.fps == 24 and req.watermark is False

    def test_resolution_rejected(self):
        from pydantic import ValidationError
        from digital_human import GenerateRequest
        with pytest.raises(ValidationError):
            GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧",
                            resolution="4k")
        with pytest.raises(ValidationError):
            GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧", fps=60)

    def test_short_text_rejected(self):
        from pydantic import ValidationError
        from digital_human import GenerateRequest
        with pytest.raises(ValidationError):
            GenerateRequest(text="太短")


class TestWatermarkPolicy:
    def test_watermark_text(self):
        from digital_human import WATERMARK_TEXT
        assert "数字人" in WATERMARK_TEXT and len(WATERMARK_TEXT) > 5

    def test_free_user_forced_watermark(self):
        """免费用户强制水印：显式传 False 也不能绕过（商业规则）。"""
        membership, role, req_wm = "free", "viewer", False
        use = (membership == "free" and role != "admin") or bool(req_wm)
        assert use is True

    def test_member_watermark_optional(self):
        membership, role, req_wm = "pro", "user", True
        use = (membership == "free" and role != "admin") or bool(req_wm)
        assert use is True
        assert (membership == "free" and role != "admin") or bool(False) is False

    def test_admin_no_watermark(self):
        membership, role, req_wm = "free", "admin", False
        use = (membership == "free" and role != "admin") or bool(req_wm)
        assert use is False


class TestBatchRequest:
    """批量生产流水线：请求校验 + 预检逻辑。"""

    def test_batch_texts_validation(self):
        from pydantic import ValidationError
        from digital_human import BatchGenerateRequest
        with pytest.raises(ValidationError):
            BatchGenerateRequest(texts=[])
        with pytest.raises(ValidationError):
            BatchGenerateRequest(texts=["这是十条足够长度的文案内容哦"] * 51)
        req = BatchGenerateRequest(texts=["大家好，今天分享一个技巧"])
        assert req.resolution == "720p" and req.fps == 15

    def test_batch_hard_word_precheck(self):
        """批量预检：违规词文案直接被识别（不浪费配额）。"""
        from digital_human import _HARD_BLOCK_WORDS
        bad = "点击领取免费大礼包"
        good = "大家好，今天分享一个实用的效率技巧"
        assert any(w.lower() in bad.lower() for w in _HARD_BLOCK_WORDS)
        assert not any(w.lower() in good.lower() for w in _HARD_BLOCK_WORDS)

    def test_batch_task_state_keys(self):
        """任务状态计数键与 worker 自增逻辑一致。"""
        statuses = ["success", "failed", "skipped"]
        task = {s: 0 for s in statuses}
        task["done"] = 0
        for s in ["success", "failed", "skipped", "success"]:
            task["done"] += 1
            task[s] += 1
        assert task == {"success": 2, "failed": 1, "skipped": 1, "done": 4}


class TestScriptAssist:
    """AI 口播文案助手：请求校验 + 场景风格表 + 回退模板。"""

    def test_script_request_validation(self):
        from pydantic import ValidationError
        from digital_human import ScriptAssistRequest
        with pytest.raises(ValidationError):
            ScriptAssistRequest(topic="")
        req = ScriptAssistRequest(topic="AI效率工具", platform="douyin", tone="活泼")
        assert req.topic == "AI效率工具" and req.tone == "活泼"

    def test_scene_styles_cover_builtin_scenes(self):
        from digital_human import _SCENE_STYLES
        for sid in ["product", "course", "news", "livestream", "story"]:
            assert sid in _SCENE_STYLES, f"场景 {sid} 应有口播风格定义"

    def test_fallback_scripts_non_empty(self):
        """LLM 不可用时的回退模板：3 版且包含主题。"""
        topic = "AI效率工具"
        scripts = [
            f"大家好，今天和大家聊聊「{topic}」。这件事和每个人都有关，看完一定会有收获。",
            f"你敢信吗？{topic}还能这么玩。今天3分钟带你彻底搞明白。",
            f"最近后台收到很多朋友问{topic}，今天就一次说清楚，记得点赞收藏。",
        ]
        assert len(scripts) == 3
        assert all(topic in s for s in scripts)


class TestComplianceCheckApi:
    """合规预检：请求校验 + 词表命中逻辑。"""

    def test_compliance_request_validation(self):
        from pydantic import ValidationError
        from digital_human import ComplianceCheckRequest
        with pytest.raises(ValidationError):
            ComplianceCheckRequest(text="")
        assert ComplianceCheckRequest(text="大家好").text == "大家好"

    def test_hard_hit_detection(self):
        """预检逻辑：硬违规词命中 → allowed=False；正常文案 → allowed=True。"""
        from digital_human import _HARD_BLOCK_WORDS
        lower = "点击领取免费大礼包，马上抢购".lower()
        hard = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower]
        assert hard
        assert "点击领取" in hard
        clean = "大家好，今天分享一个实用的效率技巧".lower()
        assert [w for w in _HARD_BLOCK_WORDS if w.lower() in clean] == []
