"""v15 音乐工厂增强单测：歌词押韵/分段参数 + 发布包封面自定义上传。

覆盖：
- 歌词 worker：押韵/分段参数进入 prompt、结果回传、非法参数兜底
- publish-pack：自定义封面居中裁剪缩放 640×640 并写入 zip、超限图片拒绝、
  无封面图片时回退 AI 封面
"""

import asyncio
import io
import os
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


@pytest.fixture(autouse=True)
def _isolated_music_dir(monkeypatch, tmp_path):
    """MUSIC_DIR 指向临时目录，避免污染真实产物目录。"""
    import music_factory

    monkeypatch.setattr(music_factory, "MUSIC_DIR", tmp_path)
    # 封面上传走 PIL，不依赖 ffmpeg；打包时 ffmpeg 转码失败会静默跳过
    return tmp_path


@pytest.fixture
def fake_agnes(monkeypatch):
    """假 AGNES 响应：返回固定歌词，并记录请求体供断言。"""
    import music_factory

    monkeypatch.setattr(music_factory, "AGNES_API_KEY", "test-key")
    captured = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {"choices": [{"message": {"content": "[Verse 1]\n测试歌词\n\n[Chorus]\n副歌"}}]}

        @staticmethod
        def text():
            return ""

    def _fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json") or {}
        captured["messages"] = kwargs.get("json", {}).get("messages", [])
        return _Resp()

    monkeypatch.setattr(music_factory.requests, "post", _fake_post)
    return captured


def _tiny_png_bytes(color: tuple = (10, 20, 200), size: tuple = (320, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


async def _collect_body(resp) -> bytes:
    """StreamingResponse 的 body_iterator 为 async_generator，需异步收集。"""
    chunks = []
    async for chunk in resp.body_iterator:
        chunks.append(chunk)
    return b"".join(chunks)


class TestLyricsRhymeStructure:
    """歌词押韵/分段参数：prompt 注入与回传。"""

    def test_params_in_prompt(self, fake_agnes):
        from music_factory import _music_lyrics_worker

        out = asyncio.run(
            _music_lyrics_worker(
                {
                    "theme": "星空",
                    "style": "rap",
                    "language": "zh",
                    "length": "short",
                    "mood": "happy",
                    "rhyme": "strict",
                    "structure": "rap_verse",
                }
            )
        )
        prompt = fake_agnes["messages"][1]["content"]
        assert "严格押韵" in prompt
        assert "说唱段落结构" in prompt
        assert out["rhyme"] == "strict" and out["structure"] == "rap_verse"
        assert "[Verse 1]" in out["lyrics"]

    def test_default_params(self, fake_agnes):
        from music_factory import _music_lyrics_worker

        out = asyncio.run(
            _music_lyrics_worker({"theme": "夏日", "style": "pop", "language": "zh", "length": "medium", "mood": "happy"})
        )
        prompt = fake_agnes["messages"][1]["content"]
        assert "押韵自然流畅" in prompt
        assert "主歌 Verse + 副歌 Chorus" in prompt
        assert out["rhyme"] == "natural" and out["structure"] == "verse_chorus"

    def test_unknown_param_fallback(self, fake_agnes):
        from music_factory import _music_lyrics_worker

        out = asyncio.run(
            _music_lyrics_worker(
                {"theme": "夜风", "style": "pop", "rhyme": "no_such", "structure": "weird"}
            )
        )
        # 未知值走 get 默认文案，不抛异常
        assert out["lyrics"]

    def test_missing_theme_rejected(self, fake_agnes):
        from fastapi import HTTPException

        from music_factory import _music_lyrics_worker

        with pytest.raises(HTTPException) as e:
            asyncio.run(_music_lyrics_worker({}))
        assert e.value.status_code == 400


class TestPublishPackCover:
    """发布包自定义封面：裁剪缩放、zip 落包、超限拒绝。"""

    def _seed_audio(self, tmp_path):
        (tmp_path / "song_123.mp3").write_bytes(b"ID3 fake mp3 data")
        return "song_123.mp3"

    def _call_publish(self, audio_id, cover_bytes=None, cover_name="cover.png"):
        from music_factory import music_publish_pack

        cover_upload = None
        if cover_bytes is not None:
            from starlette.datastructures import UploadFile

            cover_upload = UploadFile(
                file=io.BytesIO(cover_bytes),
                filename=cover_name,
                headers={"content-type": "image/png"},
            )
        return asyncio.run(
            music_publish_pack(
                audio_id=audio_id,
                song_title="",
                artist="",
                genre="",
                cover_image=cover_upload,
                current_user=USER,
            )
        )

    def test_custom_cover_in_zip(self, tmp_path):
        audio_id = self._seed_audio(tmp_path)
        resp = self._call_publish(audio_id, _tiny_png_bytes(size=(320, 240)))
        body = asyncio.run(_collect_body(resp))
        zf = zipfile.ZipFile(io.BytesIO(body))
        cover_bytes = zf.read("音乐发布包" if False else next(n for n in zf.namelist() if n.endswith("封面.jpg")))
        img = Image.open(io.BytesIO(cover_bytes))
        assert img.size == (640, 640)  # 横向图居中裁剪后仍为 640 方形
        assert img.getpixel((10, 10))[0] < 60  # 裁剪中心区域为原图颜色（非纯黑填充）

    def test_custom_cover_overrides_ai(self, tmp_path):
        import music_factory

        audio_id = self._seed_audio(tmp_path)
        # 预置 AI 封面（会被覆盖）
        ai_cover = tmp_path / "song_123.jpg"
        Image.new("RGB", (640, 640), (200, 100, 100)).save(ai_cover, "JPEG")
        resp = self._call_publish(audio_id, _tiny_png_bytes(color=(10, 200, 20), size=(200, 200)))
        body = asyncio.run(_collect_body(resp))
        zf = zipfile.ZipFile(io.BytesIO(body))
        cover_bytes = zf.read(next(n for n in zf.namelist() if n.endswith("封面.jpg")))
        img = Image.open(io.BytesIO(cover_bytes))
        assert img.size == (640, 640)
        # 自定义绿色封面生效
        assert img.getpixel((320, 320))[1] > 150
        # 质量报告标注自定义封面
        report = zf.read(next(n for n in zf.namelist() if n.endswith("质量自检报告.md"))).decode("utf-8")
        assert "自定义封面" in report

    def test_oversize_cover_rejected(self, tmp_path):
        from fastapi import HTTPException

        from music_factory import music_publish_pack

        audio_id = self._seed_audio(tmp_path)
        big = b"x" * (9 * 1024 * 1024)
        from starlette.datastructures import UploadFile

        cover_upload = UploadFile(file=io.BytesIO(big), filename="big.png")
        with pytest.raises(HTTPException) as e:
            asyncio.run(
                music_publish_pack(
                    audio_id=audio_id, song_title="", artist="", genre="", cover_image=cover_upload, current_user=USER
                )
            )
        assert e.value.status_code == 400
        assert "8MB" in str(e.value.detail)

    def test_invalid_cover_rejected(self, tmp_path):
        from fastapi import HTTPException

        from music_factory import music_publish_pack

        audio_id = self._seed_audio(tmp_path)
        from starlette.datastructures import UploadFile

        cover_upload = UploadFile(file=io.BytesIO(b"not-an-image"), filename="bad.png")
        with pytest.raises(HTTPException) as e:
            asyncio.run(
                music_publish_pack(
                    audio_id=audio_id, song_title="", artist="", genre="", cover_image=cover_upload, current_user=USER
                )
            )
        assert e.value.status_code == 400

    def test_no_cover_falls_back_to_ai(self, tmp_path):
        audio_id = self._seed_audio(tmp_path)
        resp = self._call_publish(audio_id, None)
        body = asyncio.run(_collect_body(resp))
        zf = zipfile.ZipFile(io.BytesIO(body))
        assert not any(n.endswith("封面.jpg") for n in zf.namelist())  # 无 AI 封面时缺省不抛错
