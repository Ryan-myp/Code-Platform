"""数字人 v15 增量单测：行业模板文案示例 + 口播文案质量体检。

模板层：8 个行业模板均含可直接填充的 script_sample（含占位符）；
体检层：长句无停顿 / emoji / 长数字 / 长英文 / 连续空行 / 无标点
问题识别 + 自动修复文案（fixed_text）；端点层：/script-check。
"""

import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


# 模板引用的场景/背景 id 必须真实存在（SCENE_TEMPLATES/BACKGROUNDS）
_VALID_SCENES = {"product", "course", "news", "livestream", "story"}
_VALID_BGS = {"office", "studio", "nature", "tech", "warm", "dark"}


class TestIndustryTemplatesV15:
    """v15：每模板补齐可直接填充的 script_sample 文案 + 新增 3 模板。"""

    def test_all_templates_have_script_sample(self):
        from digital_human import INDUSTRY_TEMPLATES

        assert len(INDUSTRY_TEMPLATES) >= 8
        for t in INDUSTRY_TEMPLATES:
            assert t.get("script_sample"), f"模板 {t['id']} 缺少 script_sample"
            assert len(t["script_sample"]) > 30, f"模板 {t['id']} 示例文案过短"
            assert t["scene_id"] in _VALID_SCENES, f"模板 {t['id']} 场景 id 非法"
            assert t["background_id"] in _VALID_BGS, f"模板 {t['id']} 背景 id 非法"

    def test_new_template_ids(self):
        from digital_human import INDUSTRY_TEMPLATES

        ids = {t["id"] for t in INDUSTRY_TEMPLATES}
        assert {"vlog", "corporate", "quote"} <= ids

    def test_script_sample_has_placeholder(self):
        from digital_human import INDUSTRY_TEMPLATES

        t = next(t for t in INDUSTRY_TEMPLATES if t["id"] == "live_shopping")
        assert "{产品}" in t["script_sample"]
        q = next(t for t in INDUSTRY_TEMPLATES if t["id"] == "quote")
        assert len(q["script_sample"]) > 50


class TestCheckScriptQuality:
    """口播文案质量体检纯函数：问题识别 + fixed_text 自动修复。"""

    def test_empty_text(self):
        from digital_human import check_script_quality

        r = check_script_quality("")
        assert r["ok"] is False
        assert r["issues"][0]["level"] == "error"
        assert r["issues"][0]["item"] == "空文案"
        assert r["char_count"] == 0
        assert r["fixed_text"] == ""
        assert r["fixed_changed"] is False

    def test_healthy_text(self):
        from digital_human import check_script_quality

        text = "大家好，今天分享一个技巧。坚持每天练习，三个月就能看到变化。"
        r = check_script_quality(text)
        assert r["ok"] is True
        assert r["issues"] == []
        assert r["char_count"] == 26
        assert r["estimate_sec"] == (26 + 3) // 4
        assert r["fixed_changed"] is False

    def test_too_short(self):
        from digital_human import check_script_quality

        r = check_script_quality("你好")
        assert r["ok"] is False
        assert any(i["item"] == "文案过短" and i["level"] == "error" for i in r["issues"])

    def test_long_segment_warn_and_error(self):
        from digital_human import check_script_quality

        r = check_script_quality("这" * 40)  # 40 字无标点 → warn
        assert any(i["level"] == "warn" and i["item"] == "长句无停顿" for i in r["issues"])
        r2 = check_script_quality("这" * 70)  # 70 字无标点 → error
        assert any(i["level"] == "error" and i["item"] == "超长无停顿句" for i in r2["issues"])

    def test_emoji_removed_in_fixed(self):
        from digital_human import check_script_quality

        text = "大家好，今天分享技巧 👍🎉 记得点赞！"
        r = check_script_quality(text)
        assert any(i["item"] == "含 emoji/特殊符号" for i in r["issues"])
        assert "👍" not in r["fixed_text"] and "🎉" not in r["fixed_text"]
        assert r["fixed_changed"] is True

    def test_digits_converted_in_fixed(self):
        from digital_human import check_script_quality

        text = "现在只要399元，错过再等一年！"
        r = check_script_quality(text)
        assert any(i["item"] == "长数字串" for i in r["issues"])
        assert "三九九" in r["fixed_text"]
        assert "399" not in r["fixed_text"]

    def test_latin_word_warn(self):
        from digital_human import check_script_quality

        r = check_script_quality("这个功能支持 OpenAIChat 接入，方便使用。")
        assert any(i["item"] == "长英文词" for i in r["issues"])

    def test_blank_lines_folded(self):
        from digital_human import check_script_quality

        text = "第一段内容。\n\n\n\n第二段内容。"
        r = check_script_quality(text)
        assert any(i["item"] == "连续空行过多" for i in r["issues"])
        assert "\n\n\n" not in r["fixed_text"]

    def test_no_punctuation_warn(self):
        from digital_human import check_script_quality

        text = "大家好今天分享一个超级好用的技巧坚持练习就能看到明显变化"
        r = check_script_quality(text)
        assert any(i["item"] == "全文无标点" for i in r["issues"])

    def test_estimate_sec(self):
        from digital_human import check_script_quality

        r = check_script_quality("一" * 40)  # 40 字 ≈ 10 秒
        assert r["estimate_sec"] == 10

    def test_digits_to_cn(self):
        from digital_human import _digits_to_cn

        assert _digits_to_cn("399") == "三九九"
        assert _digits_to_cn("2026") == "二零二六"
        assert _digits_to_cn("9") == "九"  # 单个数字原样转换


class TestScriptCheckEndpoint:
    """POST /api/digital-human/script-check：薄封装转发体检结果。"""

    def test_script_check_ok(self, auth_headers):
        from fastapi.testclient import TestClient

        import digital_human  # noqa: F401

        from main import app

        client = TestClient(app)
        resp = client.post(
            "/api/digital-human/script-check",
            json={"text": "大家好，今天分享一个技巧。坚持练习就能看到变化。"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "estimate_sec" in body and "fixed_text" in body

    def test_script_check_issues(self, auth_headers):
        from fastapi.testclient import TestClient

        import digital_human  # noqa: F401

        from main import app

        client = TestClient(app)
        resp = client.post(
            "/api/digital-human/script-check",
            json={"text": "今天只要399元 👍 记得点赞！"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert any(i["item"] == "长数字串" for i in body["issues"])
        assert "三九九" in body["fixed_text"]
