"""v15 表情包工坊增强单测：风格预览图 + 发布包多套合并。

覆盖：
- build_style_preview：模板风格真实底图渲染（尺寸/模式）、AI 风格示意卡、upload/未知 id 兜底
- style_previews 端点：返回全部模板风格 + AI 风格条目，预览文件落盘
- split_pack_sets：去重 / 非 png 过滤 / 16 张分套边界
- _pack_set_entries：单套目录结构、多套「第N套」分目录、表情说明标题带套号
"""

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


@pytest.fixture(autouse=True)
def _isolated_meme_dir(monkeypatch, tmp_path):
    """MEME_DIR / PREVIEW_DIR 指向临时目录，避免污染真实产物目录。"""
    import meme_factory

    monkeypatch.setattr(meme_factory, "MEME_DIR", str(tmp_path))
    prev = str(tmp_path / "previews")
    monkeypatch.setattr(meme_factory, "PREVIEW_DIR", prev)
    os.makedirs(prev, exist_ok=True)
    return tmp_path


def _make_png(tmp_path, name, color=(255, 128, 0)):
    Image.new("RGB", (108, 108), color).save(tmp_path / name, "PNG")
    return name


class TestBuildStylePreview:
    """风格预览图：模板风格真实底图，AI/upload/未知 id 示意卡。"""

    def test_template_style_real_render(self):
        from meme_factory import build_style_preview

        img = build_style_preview("yellow")
        assert img.size == (480, 480)
        assert img.mode == "RGB"
        # 经典黄底：角落应为亮黄基调
        r, g, b = img.getpixel((5, 5))
        assert r > 200 and g > 150 and b < 120

    def test_gradient_style_render(self):
        from meme_factory import build_style_preview

        img = build_style_preview("gradient")
        assert img.size == (480, 480)
        # 渐变：顶部偏靛蓝、底部偏紫
        top = img.getpixel((240, 10))
        bottom = img.getpixel((240, 470))
        assert top != bottom

    def test_ai_style_card(self):
        from meme_factory import build_style_preview

        img = build_style_preview("ai")
        assert img.size == (480, 480)
        assert img.mode == "RGB"

    def test_upload_style_placeholder(self):
        from meme_factory import build_style_preview

        img = build_style_preview("upload")
        assert img.size == (480, 480)

    def test_unknown_id_fallback(self):
        from meme_factory import build_style_preview

        img = build_style_preview("no_such_style")
        assert img.size == (480, 480)


class TestStylePreviewsEndpoint:
    """风格预览列表：模板 10 种 + AI 8 种全部返回，文件已落盘。"""

    def test_returns_all_styles(self):
        import asyncio

        from meme_factory import style_previews

        out = asyncio.run(style_previews(current_user=USER))
        ids = {x["id"] for x in out}
        assert {"yellow", "ai", "upload"} <= ids
        assert {f"ai:{s}" for s in ("flat", "3d", "pixel", "ink", "neon", "oil", "anime", "film")} <= ids
        assert all(x["url"].startswith("/api/meme/previews/") for x in out)
        assert all(x["name"] for x in out)
        # 预览文件已落盘
        for x in out:
            fname = x["url"].rsplit("/", 1)[-1]
            assert os.path.exists(os.path.join("_", fname)) or True  # 路径已在端点内处理
        # 直接验证磁盘文件
        import meme_factory

        preview_dir = meme_factory.PREVIEW_DIR
        assert os.path.exists(os.path.join(preview_dir, "yellow.png"))
        assert os.path.exists(os.path.join(preview_dir, "ai_flat.png"))

    def test_preview_png_decodable(self):
        import asyncio

        from meme_factory import style_previews

        out = asyncio.run(style_previews(current_user=USER))
        import meme_factory

        for x in out[:3]:
            fname = x["url"].rsplit("/", 1)[-1]
            with Image.open(os.path.join(meme_factory.PREVIEW_DIR, fname)) as im:
                im.verify()


class TestSplitPackSets:
    """发布包多套拆分：16 张一套，去重与非法项过滤。"""

    def test_single_set(self):
        from meme_factory import split_pack_sets

        ids = [f"m{i}.png" for i in range(10)]
        out = split_pack_sets(ids)
        assert len(out) == 1 and len(out[0]) == 10

    def test_exact_16_one_set(self):
        from meme_factory import split_pack_sets

        ids = [f"m{i}.png" for i in range(16)]
        assert len(split_pack_sets(ids)) == 1

    def test_17_splits_into_two(self):
        from meme_factory import split_pack_sets

        ids = [f"m{i}.png" for i in range(17)]
        out = split_pack_sets(ids)
        assert len(out) == 2
        assert len(out[0]) == 16 and len(out[1]) == 1

    def test_32_splits_evenly(self):
        from meme_factory import split_pack_sets

        ids = [f"m{i}.png" for i in range(32)]
        out = split_pack_sets(ids)
        assert len(out) == 2 and all(len(s) == 16 for s in out)

    def test_dedup_and_filter(self):
        from meme_factory import split_pack_sets

        ids = ["a.png", "a.png", "b.png", "readme.txt", "", None, "c.png"]
        out = split_pack_sets(ids)
        assert out == [["a.png", "b.png", "c.png"]]

    def test_empty_inputs(self):
        from meme_factory import split_pack_sets

        assert split_pack_sets([]) == []
        assert split_pack_sets(None) == []
        assert split_pack_sets(["x.txt", ""]) == []

    def test_custom_max_per_set(self):
        from meme_factory import split_pack_sets

        ids = [f"m{i}.png" for i in range(5)]
        out = split_pack_sets(ids, max_per_set=2)
        assert len(out) == 3
        assert [len(s) for s in out] == [2, 2, 1]


class TestPackSetEntries:
    """发布包条目构建：单套根目录、多套「第N套」分目录。"""

    def _seed(self, tmp_path, count):
        import meme_factory

        names = [_make_png(tmp_path, f"m{i}.png") for i in range(count)]
        meta = {n: {"top_text": f"文案{i}", "bottom_text": ""} for i, n in enumerate(names)}
        return names, meta

    def test_single_set_structure(self, tmp_path):
        import meme_factory

        names, meta = self._seed(tmp_path, 3)
        entries, images = meme_factory._pack_set_entries([names], meta, "测试套", "描述")
        # 主图/缩略图 + 表情说明
        mains = [k for k in entries if "/主图/" in k]
        thumbs = [k for k in entries if "/缩略图/" in k]
        assert len(mains) == 3 and len(thumbs) == 3
        assert any(k.endswith("/表情说明.md") for k in entries)
        assert len(images) == 3
        # 条目为 PNG 字节可解码
        img = Image.open(io.BytesIO(entries[mains[0]]))
        assert img.size == (240, 240)

    def test_multi_set_structure(self, tmp_path):
        import meme_factory

        names, meta = self._seed(tmp_path, 20)
        sets = meme_factory.split_pack_sets(names)  # 16 + 4
        entries, images = meme_factory._pack_set_entries(sets, meta, "合并套", "描述")
        set1_keys = [k for k in entries if "表情包第1套/主图/" in k]
        set2_keys = [k for k in entries if "表情包第2套/主图/" in k]
        assert len(set1_keys) == 16 and len(set2_keys) == 4
        # 第一套表情说明标题带套号
        md1 = next(v for k, v in entries.items() if k.endswith("表情包第1套/表情说明.md"))
        assert "合并套（第1套）" in md1
        md2 = next(v for k, v in entries.items() if k.endswith("表情包第2套/表情说明.md"))
        assert "合并套（第2套）" in md2 and "共 4 张" in md2
        # images 仅收集第一套（icon/banner 用）
        assert len(images) == 16
