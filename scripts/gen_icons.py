#!/usr/bin/env python3
"""生成 PWA/品牌图标集（512/192/180 + favicon）。

SVG 源：紫色渐变圆角方块 + 白色四角星 sparkle（AI 符号）。
输出到 frontend/public/icons/ 与 frontend/public/favicon.svg。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "frontend", "public", "icons")
os.makedirs(OUT_DIR, exist_ok=True)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#7c3aed"/>
      <stop offset="100%" style="stop-color:#4f46e5"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="42%" r="60%">
      <stop offset="0%" style="stop-color:#ffffff;stop-opacity:0.28"/>
      <stop offset="100%" style="stop-color:#ffffff;stop-opacity:0"/>
    </radialGradient>
  </defs>
  <rect width="1024" height="1024" rx="220" fill="url(#bg)"/>
  <rect width="1024" height="1024" rx="220" fill="url(#glow)"/>
  <!-- 四角星（主 sparkle） -->
  <path d="M512 240
           C 532 390, 600 458, 760 478
           C 600 498, 532 566, 512 716
           C 492 566, 424 498, 264 478
           C 424 458, 492 390, 512 240 Z"
        fill="#ffffff"/>
  <!-- 小星（右上点缀） -->
  <path d="M760 560
           C 768 606, 790 628, 836 636
           C 790 644, 768 666, 760 712
           C 752 666, 730 644, 684 636
           C 730 628, 752 606, 760 560 Z"
        fill="#ffffff" opacity="0.85"/>
  <!-- 小星（左下点缀） -->
  <path d="M300 700
           C 306 732, 322 748, 354 754
           C 322 760, 306 776, 300 808
           C 294 776, 278 760, 246 754
           C 278 748, 294 732, 300 700 Z"
        fill="#ffffff" opacity="0.7"/>
</svg>"""

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#7c3aed"/>
      <stop offset="100%" style="stop-color:#4f46e5"/>
    </linearGradient>
    <radialGradient id="glow" cx="50%" cy="42%" r="60%">
      <stop offset="0%" style="stop-color:#ffffff;stop-opacity:0.28"/>
      <stop offset="100%" style="stop-color:#ffffff;stop-opacity:0"/>
    </radialGradient>
  </defs>
  <rect width="1024" height="1024" rx="220" fill="url(#bg)"/>
  <rect width="1024" height="1024" rx="220" fill="url(#glow)"/>
  <path d="M512 240
           C 532 390, 600 458, 760 478
           C 600 498, 532 566, 512 716
           C 492 566, 424 498, 264 478
           C 424 458, 492 390, 512 240 Z"
        fill="#ffffff"/>
  <path d="M760 560
           C 768 606, 790 628, 836 636
           C 790 644, 768 666, 760 712
           C 752 666, 730 644, 684 636
           C 730 628, 752 606, 760 560 Z"
        fill="#ffffff" opacity="0.85"/>
</svg>"""

SIZES = [512, 192, 180]


def render():
    import cairosvg

    for size in SIZES:
        path = os.path.join(OUT_DIR, f"icon-{size}.png")
        cairosvg.svg2png(bytestring=SVG.encode(), write_to=path, scale=size / 1024)
        print(f"icon-{size}.png -> {os.path.getsize(path)} bytes")
    with open(os.path.join(ROOT, "frontend", "public", "favicon.svg"), "w") as f:
        f.write(FAVICON_SVG)
    print("favicon.svg updated")


if __name__ == "__main__":
    try:
        render()
    except Exception as e:  # noqa: BLE001
        print(f"render failed: {e}", file=sys.stderr)
        sys.exit(1)
