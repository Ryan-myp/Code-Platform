"""v13.26 产物语义化命名：derive_title 派生规则 + 各工厂登记 title。

背景：图片/视频/音乐列表此前展示随机时间戳 ID（img_xxx / video_xxx / music_xxx），
本套用例锁定「展示标题」的派生与写入链路。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common.artifacts import derive_title


class TestDeriveTitle:
    """公共派生函数：metadata.title → theme → content 关键词 → 截断 30 字。"""

    def test_metadata_title_priority(self):
        assert derive_title("image", {"prompt": "x"}, {"title": "我的标题"}) == "我的标题"

    def test_theme_fallback(self):
        assert derive_title("audio", {}, {"theme": "赛博朋克夜城"}) == "赛博朋克夜城"

    def test_prompt_derived_and_truncated(self):
        t = derive_title(
            "image", {"prompt": "一座未来城市在雨夜的霓虹灯下，AI 生成的超现实场景，细节丰富"}
        )
        assert t.startswith("一座未来城市") and t.endswith("…") and len(t) == 31

    def test_content_topic_key(self):
        assert derive_title("video", {"topic": "出海创业纪录片"}) == "出海创业纪录片"

    def test_lyrics_first_line(self):
        assert derive_title("lyrics", "第一行歌词\n第二行") == "第一行歌词"

    def test_empty_fallback(self):
        assert derive_title("video", {}, {}) == ""
        assert derive_title("image", None, None) == ""

    def test_whitespace_collapse(self):
        assert derive_title("image", {"prompt": "  多    空格  换行\n测试  "}) == "多 空格 换行 测试"


class TestFactorySaveTitle:
    """各工厂 _save_artifact 登记时自动写入语义化 title。"""

    def test_image_save_writes_title(self, monkeypatch):
        import image_factory

        captured = {}

        def fake_save(**kw):
            captured.update(kw)
            return "art_1"

        monkeypatch.setattr(image_factory, "save_artifact", fake_save)
        image_factory._save_artifact("img_1.png", "p1", "一只橘猫坐在窗台")
        assert captured["metadata"]["title"] == "一只橘猫坐在窗台"

    def test_video_save_writes_title(self, monkeypatch):
        import video_factory

        captured = {}

        def fake_save(**kw):
            captured.update(kw)
            return "art_2"

        monkeypatch.setattr(video_factory, "save_artifact", fake_save)
        video_factory._save_artifact("video_1.mp4", "p1", "夏日海边冲浪纪录片", 30.0)
        assert captured["metadata"]["title"] == "夏日海边冲浪纪录片"

    def test_video_save_keeps_extra_meta_title(self, monkeypatch):
        import video_factory

        captured = {}

        def fake_save(**kw):
            captured.update(kw)
            return "art_3"

        monkeypatch.setattr(video_factory, "save_artifact", fake_save)
        video_factory._save_artifact(
            "video_2.mp4", "p1", "长提示词", 30.0, {"title": "自定义标题"}
        )
        assert captured["metadata"]["title"] == "自定义标题"


class TestFallbackTitle:
    """存量旧数据/后期产物文件名语义化兜底（无 artifacts 元数据时）。"""

    def test_video_post_process_prefixes(self):
        from video_factory import _fallback_title

        assert _fallback_title("subtitle_1786.mp4") == "字幕合成视频"
        assert _fallback_title("music_1786.mp4") == "配乐视频"
        assert _fallback_title("concat_1786.mp4") == "视频拼接合成"

    def test_video_legacy_base64_name(self):
        from video_factory import _fallback_title

        assert _fallback_title("video_bGl0ZWxsbTpjdXN0b21fbGxt.mp4") == "AI 视频作品"

    def test_image_timestamp_to_date(self):
        from image_factory import _fallback_title

        t = _fallback_title("img_1786337267291.png")
        assert t.startswith("图片 · ") and t.count("-") == 1

    def test_image_plain_name_kept(self):
        from image_factory import _fallback_title

        assert _fallback_title("wechat_photo.jpg") == "wechat_photo"
