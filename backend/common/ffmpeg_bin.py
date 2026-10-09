"""ffmpeg 二进制解析（全平台共享，杜绝各模块硬编码 "ffmpeg" 导致环境缺失即崩）。

解析顺序：
1. 系统 PATH 中的 ffmpeg（生产环境经 scripts/check_environment.sh 保证存在）
2. imageio-ffmpeg 自带二进制兜底（含 libass，支持 subtitles 滤镜烧录字幕）

任何部署/开发环境只要装了依赖（imageio-ffmpeg 在 requirements.txt），
数字人/短剧/视频工厂即可用，不依赖手工安装系统 ffmpeg。
"""

import shutil

_FFMPEG_BIN_CACHE: str | None = None


def ffmpeg_bin() -> str:
    """返回可用 ffmpeg 可执行路径（找不到系统版时回退 imageio-ffmpeg 自带二进制）。"""
    global _FFMPEG_BIN_CACHE
    if _FFMPEG_BIN_CACHE is None:
        found = shutil.which("ffmpeg")
        if found:
            _FFMPEG_BIN_CACHE = found
        else:
            try:
                import imageio_ffmpeg

                exe = imageio_ffmpeg.get_ffmpeg_exe()
                _FFMPEG_BIN_CACHE = exe or "ffmpeg"
            except Exception:  # noqa: BLE001 — imageio 未安装时回退命令名，交由子进程报清晰错误
                _FFMPEG_BIN_CACHE = "ffmpeg"
    return _FFMPEG_BIN_CACHE


FFMPEG_BIN = ffmpeg_bin()


def ffmpeg_available() -> bool:
    """当前解析到的 ffmpeg 是否真实可用（绝对路径存在 / 命令名在 PATH）。"""
    import os

    binpath = FFMPEG_BIN
    return os.path.exists(binpath) or bool(shutil.which(binpath))


def ffprobe_bin() -> str | None:
    """ffprobe 可执行路径；未安装时返回 None（调用方需走 ffmpeg -i 兑底）。"""
    return shutil.which("ffprobe")


def probe_media(path: str, timeout: float = 20) -> dict | None:
    """媒体文件元数据：{'duration': 秒, 'has_video': bool}；不可解析返回 None。

    优先 ffprobe（JSON）；无 ffprobe 时兑底 `ffmpeg -i` stderr 解析
    （Duration 行 + Stream 行）——确保即使部署环境只有 imageio 自带 ffmpeg 也能校验媒体。
    """
    import json
    import re
    import subprocess

    probe = ffprobe_bin()
    try:
        if probe:
            r = subprocess.run(
                [
                    probe,
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "json",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if r.returncode != 0:
                return None
            d = json.loads(r.stdout or "{}")
            streams = d.get("streams") or []
            return {
                "duration": float(d.get("format", {}).get("duration") or 0),
                "has_video": any(s.get("codec_type") == "video" for s in streams),
            }
        # 兑底：ffmpeg -i 读 stderr 里的 Duration / Stream 行
        r = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-i", path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        err = r.stderr or ""
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", err)
        if not m:
            return None
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        has_video = bool(re.search(r"Stream #\d+[:.].*\bVideo\b", err))
        return {"duration": duration, "has_video": has_video}
    except Exception:  # noqa: BLE001 — 解析失败统一归一为 None（调用方按无效媒体拦截）
        return None
