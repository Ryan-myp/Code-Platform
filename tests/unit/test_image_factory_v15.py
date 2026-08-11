"""v15 图片工厂增强单测：批量参数上限优化 + 历史缩略图。

覆盖：
- normalize_batch_params：clamp 与总张数上限（batch × n ≤ 16）
- normalize_size：合法/非法/超范围尺寸回退默认
- thumb 端点：≤256px JPEG 内存缩略图、404、损坏文件回退原图
- list_images：返回 thumb_url 字段
"""

import asyncio
import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


@pytest.fixture(autouse=True)
def _isolated_image_dir(monkeypatch, tmp_path):
    """IMAGE_DIR 指向临时目录，避免污染真实产物目录。"""
    import image_factory

    monkeypatch.setattr(image_factory, "IMAGE_DIR", str(tmp_path))
    return tmp_path


def _seed_image(tmp_path, name="img_1000.png", size=(800, 600), color=(30, 120, 200)):
    Image.new("RGB", size, color).save(tmp_path / name, "PNG")
    return name


class TestNormalizeBatchParams:
    """批量参数：各自 clamp 且总张数 ≤ 16。"""

    def test_defaults(self):
        from image_factory import normalize_batch_params

        assert normalize_batch_params(None, None) == (1, 1)
        assert normalize_batch_params(0, 0) == (1, 1)
        assert normalize_batch_params(-3, 2) == (1, 2)

    def test_upper_clamp(self):
        from image_factory import normalize_batch_params

        assert normalize_batch_params(99, 1) == (4, 1)
        assert normalize_batch_params(1, 99) == (1, 4)

    def test_total_cap(self):
        from image_factory import normalize_batch_params

        # 4×5=20 > 16 → 截断到 4×4
        assert normalize_batch_params(4, 5) == (4, 4)
        # 5×4 → 4×4
        assert normalize_batch_params(5, 4) == (4, 4)
        # 3×6：n 先被单维上限截断到 4 → 3×4=12 未超总量
        assert normalize_batch_params(3, 6) == (3, 4)

    def test_batch_side_prefers_trim(self):
        from image_factory import normalize_batch_params

        # 5×5 → 4×4
        assert normalize_batch_params(5, 5) == (4, 4)


class TestNormalizeSize:
    """尺寸参数：格式与范围校验。"""

    def test_valid(self):
        from image_factory import normalize_size

        assert normalize_size("1024x1024") == "1024x1024"
        assert normalize_size(" 800X600 ") == "800x600"  # 大小写与空白容忍
        assert normalize_size(None) == "1024x1024"

    def test_invalid_fallback(self):
        from image_factory import normalize_size

        assert normalize_size("abc") == "1024x1024"
        assert normalize_size("1024") == "1024x1024"
        assert normalize_size("1024x") == "1024x1024"
        assert normalize_size("") == "1024x1024"

    def test_out_of_range_fallback(self):
        from image_factory import normalize_size

        assert normalize_size("100x100") == "1024x1024"  # 小于下限 256
        assert normalize_size("99999x99999") == "1024x1024"  # 超过上限 4096
        assert normalize_size("1024x100") == "1024x1024"


class TestThumbEndpoint:
    """历史缩略图：尺寸、格式与错误兜底。"""

    def test_thumb_smaller_than_original(self, tmp_path):
        from image_factory import get_image_thumb

        _seed_image(tmp_path, "big.png", size=(1200, 900))
        resp = asyncio.run(get_image_thumb("big.png"))
        assert resp.media_type == "image/jpeg"
        img = Image.open(io.BytesIO(resp.body))
        assert max(img.size) <= 256  # 长边 ≤256
        assert img.size[0] < 1200

    def test_thumb_small_image_kept(self, tmp_path):
        from image_factory import get_image_thumb

        _seed_image(tmp_path, "small.png", size=(100, 80))
        resp = asyncio.run(get_image_thumb("small.png"))
        img = Image.open(io.BytesIO(resp.body))
        assert max(img.size) <= 256  # 原图小于阈值不放大

    def test_missing_404(self):
        from fastapi import HTTPException

        from image_factory import get_image_thumb

        with pytest.raises(HTTPException) as e:
            asyncio.run(get_image_thumb("no_such.png"))
        assert e.value.status_code == 404

    def test_corrupt_file_fallback(self, tmp_path):
        from image_factory import get_image_thumb

        (tmp_path / "corrupt.png").write_bytes(b"not a real image")
        resp = asyncio.run(get_image_thumb("corrupt.png"))
        assert resp.media_type == "image/png"  # 回退原图（FileResponse 自动识别）


class TestListImagesThumbUrl:
    """图片列表：附带 thumb_url 供缩略图墙使用。"""

    def test_thumb_url_present(self, tmp_path):
        from image_factory import list_images

        _seed_image(tmp_path, "img_111.png")
        files = asyncio.run(list_images())
        assert len(files) == 1
        assert files[0]["thumb_url"].endswith("/images/img_111.png/thumb")
        assert files[0]["url"].endswith("/images/img_111.png")

    def test_non_image_ignored(self, tmp_path):
        from image_factory import list_images

        (tmp_path / "readme.txt").write_text("x")
        assert asyncio.run(list_images()) == []
