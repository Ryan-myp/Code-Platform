"""图片编辑引擎 — rembg 语义分割（人像/商品抠图）与前景合成工具。

为图片工厂提供真实抠图能力（替代旧的颜色阈值/椭圆近似）：
- u2net 模型 ONNX 推理（CPU，~1s/张 512px），首次运行自动下载模型到 ~/.u2net
- 懒加载单例 + 线程锁（FastAPI 多 worker 场景只加载一次）
- rembg 不可用（未安装/模型缺失）时抛错，由调用方降级到旧逻辑
"""
from __future__ import annotations

import logging
import threading

from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

_session = None
_session_lock = threading.Lock()


def segmentation_session():
    """rembg u2net 会话（懒加载单例）。"""
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is None:
            from rembg import new_session

            logger.info("加载 rembg u2net 分割模型（首次运行自动下载 ~170MB）…")
            _session = new_session("u2net")
    return _session


def remove_background(img: Image.Image, feather: int = 0) -> Image.Image:
    """语义分割抠图：返回 RGBA（前景保留、背景透明）。

    feather>0 时对 alpha 做高斯羽化，柔和边缘（发丝/毛边场景）。
    """
    from rembg import remove

    out = remove(img.convert("RGB"), session=segmentation_session())
    if out.mode != "RGBA":
        out = out.convert("RGBA")
    if feather > 0:
        alpha = out.getchannel("A").filter(ImageFilter.GaussianBlur(feather))
        out.putalpha(alpha)
    return out


def compose_foreground(
    fg: Image.Image,
    bg: Image.Image,
    fg_scale: float = 0.92,
    bottom_margin_ratio: float = 0.05,
    add_shadow: bool = True,
) -> Image.Image:
    """将透明前景（RGBA）合成到背景图：等比缩放 → 水平居中 → 底部对齐留边。

    - 前景按高度占比 fg_scale 缩放（保留原比例，超出宽度则按宽收敛）
    - add_shadow 时在人物底部叠加柔影（提升真实感）
    """
    fg = fg.convert("RGBA")
    bg = bg.convert("RGBA")
    bw, bh = bg.size
    fw, fh = fg.size
    if fw <= 0 or fh <= 0:
        raise ValueError("前景图尺寸无效")

    # 目标高度 = 背景高 * fg_scale；宽度按原比例，超宽则收敛
    target_h = int(bh * fg_scale)
    target_w = int(fw * target_h / fh)
    if target_w > int(bw * 0.96):
        target_w = int(bw * 0.96)
        target_h = int(fh * target_w / fw)
    fg = fg.resize((target_w, target_h), Image.LANCZOS)

    x = (bw - target_w) // 2
    y = bh - target_h - int(bh * bottom_margin_ratio)

    result = bg.copy()
    if add_shadow:
        # 底部柔影：用 alpha 生成黑色阴影层，高斯模糊 + 下移
        shadow = Image.new("RGBA", fg.size, (0, 0, 0, 0))
        alpha = fg.getchannel("A").point(lambda a: int(a * 0.35))
        shadow.putalpha(alpha)
        shadow = shadow.filter(ImageFilter.GaussianBlur(max(4, target_h // 40)))
        result.alpha_composite(shadow, (x, min(bh - 4, y + target_h // 14)))

    result.alpha_composite(fg, (x, y))
    return result


def make_gradient(width: int, height: int, top_hex: str, bottom_hex: str) -> Image.Image:
    """垂直渐变画布（numpy 向量化）：自上而下从 top_hex 过渡到 bottom_hex。"""
    import numpy as np

    def _hex(h: str) -> tuple:
        h = (h or "#FFFFFF").lstrip("#")
        if len(h) != 6:
            h = "FFFFFF"
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    top, bottom = _hex(top_hex), _hex(bottom_hex)
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    arr = np.array(top, dtype=np.float32) * (1 - y) + np.array(bottom, dtype=np.float32) * y
    arr = np.repeat(arr[:, None, :], width, axis=1)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def make_scene_background(width: int, height: int, scene: str) -> Image.Image:
    """场景背景：纯色/垂直渐变（与旧背景替换的场景 id 兼容，视觉升级为渐变）。"""
    scenes = {
        "beach": ("#FFB6C1", "#87CEEB"),      # 粉色沙滩 → 蓝天
        "city": ("#6B7280", "#374151"),        # 城市灰
        "space": ("#0F172A", "#1E1B4B"),       # 深空蓝紫
        "studio": ("#F3F4F6", "#FFFFFF"),      # 摄影棚白
        "forest": ("#228B22", "#065F46"),      # 森林绿
        "snow": ("#FFFFFF", "#DCE7F3"),        # 雪景
        "sunset": ("#FF6B6B", "#FFD93D"),      # 日落橙黄
        "night": ("#111827", "#312E81"),       # 夜景
        "pastel": ("#FDE68A", "#FBCFE8"),      # 马卡龙粉黄
    }
    hexes = scenes.get(scene, scenes["studio"])
    if hexes[0] == hexes[1]:
        return Image.new("RGB", (width, height), hexes[0])
    return make_gradient(width, height, hexes[0], hexes[1])
