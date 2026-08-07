"""表情包工坊增强单元测试：新风格配色 / 上传背景 / emoji 装饰 / 半透明底条。

不依赖网络与 AI 服务，仅覆盖纯函数与图像处理（PIL 可用即可）。
"""

import base64
import io
import sys
from pathlib import Path

import pytest
from PIL import Image

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from fastapi import HTTPException  # noqa: E402


def _tiny_png_b64(color: tuple = (255, 0, 0)) -> str:
    img = Image.new("RGB", (64, 32), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class TestNewStyles:
    """新增 4 种风格 + AI 风格表。"""

    def test_style_ids_present(self):
        from meme_factory import STYLES

        ids = {s["id"] for s in STYLES}
        assert {"neon", "paper", "sticker", "upload", "ai"} <= ids

    def test_ai_styles_table(self):
        from meme_factory import AI_STYLES

        assert {"flat", "3d", "pixel", "ink", "neon"} <= set(AI_STYLES)
        for v in AI_STYLES.values():
            assert len(v) > 5  # 每档都带画面风格描述

    def test_text_color(self):
        from meme_factory import _text_color

        assert _text_color("neon") == ("#FFFFFF", "#22D3EE")  # 白字青描边
        assert _text_color("paper") == ("#111111", "#D6CFC0")  # 报纸铅字
        assert _text_color("sticker") == ("#000000", "#FFFFFF")  # 贴纸黑字白边
        assert len(_text_color("red")) == 2 and len(_text_color("gradient")) == 2


class TestUploadBg:
    """上传背景：等比缩放居中、黑边填充、异常输入拦截。"""

    def test_resize_and_center(self):
        from meme_factory import _upload_bg

        img = _upload_bg(_tiny_png_b64())
        assert img.size == (1080, 1080)
        assert img.mode == "RGB"

    def test_landscape_keeps_aspect(self):
        from meme_factory import _upload_bg

        img = _upload_bg(_tiny_png_b64((0, 0, 255)))
        assert img.size == (1080, 1080)
        # 角落应是黑边填充（64x32 横图居中后上下留黑）
        assert img.getpixel((5, 5))[0] <= 20 and img.getpixel((5, 5))[1] <= 20

    def test_invalid_base64_rejected(self):
        from meme_factory import _upload_bg

        with pytest.raises(HTTPException) as e:
            _upload_bg("not-base64!!!")
        assert e.value.status_code == 400

    def test_oversize_rejected(self):
        from meme_factory import _upload_bg

        # 真实 >8MB 二进制数据编码的 base64，命中大小检查
        big = base64.b64encode(b"x" * (9 * 1024 * 1024)).decode()
        with pytest.raises(HTTPException) as e:
            _upload_bg(big)
        assert e.value.status_code == 400
        assert "过大" in str(e.value.detail)


class TestDecoration:
    """emoji 装饰：无字体环境安全降级、有字体时绘制不抛异常。"""

    def test_empty_decoration_noop(self):
        from meme_factory import _draw_decoration

        img = Image.new("RGB", (1080, 1080), "#FFFFFF")
        _draw_decoration(img, "")  # 空输入不抛
        _draw_decoration(img, None)  # None 不抛
        _draw_decoration(img, "   ")  # 空白不抛

    def test_draw_with_font_or_skip(self):
        from meme_factory import _draw_decoration, _load_emoji_font

        img = Image.new("RGB", (1080, 1080), "#FFFFFF")
        if _load_emoji_font(96) is not None:
            _draw_decoration(img, "😂 哈哈 😍")  # 有字体则至少不抛异常
        else:
            _draw_decoration(img, "😂")  # 无字体静默跳过
        assert img.size == (1080, 1080)


class TestOverlayTextBars:
    """顶部/底部半透明底条：提升复杂背景上的文字可读性。"""

    def test_bars_added_when_text(self):
        from meme_factory import _overlay_text_bars

        img = Image.new("RGB", (1080, 1080), "#FFFFFF")
        out = _overlay_text_bars(img, "顶部", "底部")
        assert out.size == (1080, 1080)
        # 顶部文字区被压暗（原纯白 → 非纯白）
        assert out.getpixel((540, 60)) != (255, 255, 255)
        # 底部文字区被压暗
        assert out.getpixel((540, 1060)) != (255, 255, 255)
        # 中间区域保持原样（不透明条只覆盖上下）
        assert out.getpixel((540, 540)) == (255, 255, 255)

    def test_no_bars_without_text(self):
        from meme_factory import _overlay_text_bars

        img = Image.new("RGB", (1080, 1080), (10, 20, 30))
        out = _overlay_text_bars(img, "", "")
        assert out.getpixel((540, 60)) == (10, 20, 30)
        assert out.getpixel((540, 1060)) == (10, 20, 30)
