"""v20 音乐工厂单测：歌词段落解析 + 歌词 prompt 丰富度。

覆盖：
- parse_lyrics_sections：英文/中文/全角标注、无标注降级、空输入、行内标注不识别
- 歌词 prompt：v20 丰富度要求（记忆点 Hook/画面感/情感递进/段落配比）注入
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


@pytest.fixture(autouse=True)
def _isolated_music_dir(monkeypatch, tmp_path):
    """MUSIC_DIR 指向临时目录，避免污染真实产物目录。"""
    import music_factory

    monkeypatch.setattr(music_factory, "MUSIC_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def fake_agnes(monkeypatch):
    """假 AGNES 响应：记录请求体供 prompt 断言。"""
    import music_factory

    monkeypatch.setattr(music_factory, "AGNES_API_KEY", "test-key")
    captured = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "[Verse 1]\n测试歌词"}}]}

        @staticmethod
        def text():
            return ""

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["messages"] = kwargs.get("json", {}).get("messages", [])
        return _Resp()

    monkeypatch.setattr(music_factory.requests, "post", _fake_post)
    return captured


class TestParseLyricsSections:
    """歌词段落解析：标注变体兼容与降级兜底。"""

    def test_english_tags(self):
        from music_factory import parse_lyrics_sections

        text = "[Verse 1]\n阳光透过窗帘\n洒在你脸上\n\n[Chorus]\n你是我最美的遇见\n\n[Bridge]\n未来\n"
        sections = parse_lyrics_sections(text)
        assert [s["title"] for s in sections] == ["Verse 1", "Chorus", "Bridge"]
        assert sections[0]["lines"] == ["阳光透过窗帘", "洒在你脸上"]
        assert sections[1]["is_hook"] is True
        assert sections[2]["is_hook"] is False
        assert sections[1]["lines"] == ["你是我最美的遇见"]

    def test_chinese_tags(self):
        from music_factory import parse_lyrics_sections

        sections = parse_lyrics_sections("（副歌）\n金句在这里\n【主歌】\n普通段落")
        assert [s["title"] for s in sections] == ["Chorus", "Verse"]
        assert sections[0]["is_hook"] is True

    def test_hook_alias(self):
        from music_factory import parse_lyrics_sections

        sections = parse_lyrics_sections("[HOOK]\n记忆点")
        assert sections[0]["title"] == "Chorus"
        assert sections[0]["is_hook"] is True

    def test_no_tags_fallback(self):
        from music_factory import parse_lyrics_sections

        sections = parse_lyrics_sections("没有任何标注的歌词\n第二行")
        assert len(sections) == 1
        assert sections[0]["title"] == "歌词"
        assert sections[0]["lines"] == ["没有任何标注的歌词", "第二行"]
        assert sections[0]["is_hook"] is False

    def test_empty_input(self):
        from music_factory import parse_lyrics_sections

        assert parse_lyrics_sections("") == []
        assert parse_lyrics_sections(None) == []
        assert parse_lyrics_sections("   ") == []

    def test_inline_tag_not_recognized(self):
        from music_factory import parse_lyrics_sections

        sections = parse_lyrics_sections("[Verse 1] 带行内文本\n不应被识别")
        assert len(sections) == 1
        assert sections[0]["title"] == "歌词"
        assert sections[0]["lines"] == ["[Verse 1] 带行内文本", "不应被识别"]


class TestLyricsPromptRichness:
    """v20 歌词 prompt 丰富度要求注入。"""

    def test_richness_requirements_in_prompt(self, fake_agnes):
        from music_factory import _music_lyrics_worker

        out = asyncio.run(
            _music_lyrics_worker(
                {"theme": "星空下的告白", "style": "pop", "language": "zh", "length": "medium", "mood": "romantic"}
            )
        )
        prompt = fake_agnes["messages"][1]["content"]
        assert "记忆点 Hook" in prompt
        assert "画面感" in prompt
        assert "情感递进" in prompt
        assert "段落配比" in prompt
        assert "[Verse 1]/[Chorus]/[Bridge]" in prompt
        assert "[Verse 1]" in out["lyrics"]
