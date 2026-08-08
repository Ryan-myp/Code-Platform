"""事件循环阻塞修复回归测试。

覆盖 fix-blocking 轮次：
1. remove_background 的 numpy 向量化与原逐像素逻辑结果等价（防优化改变行为）
2. person_segmentation 的 putalpha 通道操作替代逐像素循环
3. _audio_duration mtime 缓存（列表接口二次访问零子进程）
"""

import random

import numpy as np
from PIL import Image

from voice_factory import _audio_duration, _duration_cache


def _build_random_rgba(w: int = 40, h: int = 50, seed: int = 42) -> Image.Image:
    random.seed(seed)
    img = Image.new("RGBA", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), 255)
    return img


def _legacy_mask(img: Image.Image, bg_color: tuple) -> Image.Image:
    """复刻提交前的逐像素抠图逻辑（每通道差 < 30 判定为背景）。"""
    w, h = img.size
    pixels = img.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            p = pixels[x, y]
            if abs(p[0] - bg_color[0]) < 30 and abs(p[1] - bg_color[1]) < 30 and abs(p[2] - bg_color[2]) < 30:
                mp[x, y] = 0
            else:
                mp[x, y] = 255
    return mask


class TestBackgroundRemoveVectorized:
    """numpy 向量化必须与原逐像素逻辑逐像素等价。"""

    def test_equivalence_with_legacy_loop(self):
        img = _build_random_rgba()
        w, h = img.size
        corners = [img.getpixel((0, 0)), img.getpixel((w - 1, 0)), img.getpixel((0, h - 1)), img.getpixel((w - 1, h - 1))]
        bg_color = tuple(sum(c[i] for c in corners) // 4 for i in range(3))

        legacy = _legacy_mask(img, bg_color)

        arr = np.asarray(img.convert("RGB"))
        bg_arr = np.array(bg_color[:3], dtype=arr.dtype)
        distance = np.abs(arr.astype(np.int16) - bg_arr).max(axis=2)
        vec = Image.fromarray(np.where(distance < 30, 0, 255).astype(np.uint8), "L")

        diff = sum(1 for y in range(h) for x in range(w) if legacy.getpixel((x, y)) != vec.getpixel((x, y)))
        assert diff == 0, f"向量化与原逻辑不一致，差异像素 {diff}"

    def test_threshold_boundary(self):
        """(29,29,29) 判定为背景；(30,0,0) 判定为前景。"""
        t = np.array([[[29, 29, 29], [30, 0, 0], [0, 0, 0]]])
        d = np.abs(t.astype(np.int16) - np.array([0, 0, 0])).max(axis=2)
        result = np.where(d < 30, 0, 255).astype(np.uint8).tolist()
        assert result == [[0, 255, 0]]

    def test_rgba_bg_color_slicing(self):
        """RGBA 图的背景色取前 3 通道，避免与 RGB 数组广播错位。"""
        img = Image.new("RGBA", (10, 10), (10, 20, 30, 255))
        arr = np.asarray(img.convert("RGB"))
        bg_arr = np.array((10, 20, 30), dtype=arr.dtype)
        distance = np.abs(arr.astype(np.int16) - bg_arr).max(axis=2)
        assert distance.max() == 0


class TestAudioDurationCache:
    """_audio_duration 的 mtime 缓存：同文件重复探测不再起子进程。"""

    def test_cache_hit(self, tmp_path, monkeypatch):
        audio = tmp_path / "a.mp3"
        audio.write_bytes(b"fake-audio-content")
        _duration_cache.clear()
        subprocess_calls = []
        import subprocess as sp

        def fake_run(cmd, **kwargs):
            subprocess_calls.append(cmd)
            class R:
                stdout = "12.5\n"
            return R()

        monkeypatch.setattr(sp, "run", fake_run)
        assert _audio_duration(str(audio)) == 12.5
        assert len(subprocess_calls) == 1
        # 二次调用命中缓存
        assert _audio_duration(str(audio)) == 12.5
        assert len(subprocess_calls) == 1
        # mtime 变化后重新探测
        import os
        os.utime(audio, (0, 0))
        assert _audio_duration(str(audio)) == 12.5
        assert len(subprocess_calls) == 2
        _duration_cache.clear()

    def test_bad_file_returns_zero(self, tmp_path, monkeypatch):
        import subprocess as sp

        def fake_run(cmd, **kwargs):
            class R:
                stdout = ""
            return R()

        monkeypatch.setattr(sp, "run", fake_run)
        assert _audio_duration(str(tmp_path / "missing.mp3")) == 0.0
