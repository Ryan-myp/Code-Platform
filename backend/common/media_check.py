#!/usr/bin/env python3
"""媒体文件有效性校验（防 0KB/假数据文件污染产出）。

背景：历史上 video/audio 目录出现过两类废文件——
  1. 0KB 空文件（云端返回空但照存）
  2. 假 MP3（重复 MPEG 帧头 ff fb ff fb...，如 2048 字节占位）

这类文件 ffprobe 无法解析，用户点开黑屏/无声，直接造成"像demo"的观感。

使用：
    from common.media_check import is_valid_audio, is_valid_video
    if not is_valid_audio(path): raise HTTPException(502, ...)
"""

import logging

logger = logging.getLogger(__name__)

_MIN_AUDIO_BYTES = 512
_MIN_VIDEO_BYTES = 1024


def _looks_like_placeholder(path: str) -> bool:
    """检测重复帧头占位文件（ff fb 重复 ≥16 次 = 假 MP3）。"""
    try:
        with open(path, "rb") as f:
            head = f.read(2048)
        # 检查是否全为重复的 0xff 0xfb 模式（MPEG 音频帧头）
        if len(head) >= 64:
            pat = head[:2]
            if pat == b"\xff\xfb" or pat == b"\xff\xf3":
                count = head.count(pat)
                if count >= 8 and len(set(head[: count * 2])) <= 2:
                    return True
        return False
    except OSError:
        return True


def is_valid_audio(path: str, min_bytes: int = _MIN_AUDIO_BYTES) -> bool:
    """音频文件是否有效：大小 + 非占位 + 可解析出时长（ffprobe 或 ffmpeg -i 兑底）。"""
    import os

    try:
        if not os.path.exists(path) or os.path.getsize(path) < min_bytes:
            return False
        if _looks_like_placeholder(path):
            return False
        from common.ffmpeg_bin import probe_media

        meta = probe_media(path)
        return bool(meta and meta["duration"] > 0)
    except Exception:
        return False


def is_valid_video(path: str, min_bytes: int = _MIN_VIDEO_BYTES, min_duration: float = 0.5) -> bool:
    """视频文件是否有效：大小 + 可解析 + 有时长 + 含视频流（ffprobe 或 ffmpeg -i 兑底）。"""
    import os

    try:
        if not os.path.exists(path) or os.path.getsize(path) < min_bytes:
            return False
        from common.ffmpeg_bin import probe_media

        meta = probe_media(path)
        return bool(meta and meta["duration"] >= min_duration and meta["has_video"])
    except Exception:
        return False
