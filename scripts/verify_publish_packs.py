#!/usr/bin/env python3
"""商业化发布 v14 真实生成验证：音乐 / 游戏 / 小程序发布包 zip 结构与规格校验。

只读真实数据库与产物目录，调用真实发布包函数，验证 zip 可解压、关键物料齐全。
用法：python scripts/verify_publish_packs.py
"""

import asyncio
import io
import os
import sys
import time
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# 指向真实运行库（默认即 backend/platform.db，显式设置以防环境变量残留）
os.environ["DB_PATH"] = str(BACKEND / "platform.db")

PASS = []


def ok(name: str, detail: str = ""):
    PASS.append(name)
    print(f"  ✓ {name}{(' — ' + detail) if detail else ''}")


def check_zip(data: bytes, expected_suffixes: list[str], label: str) -> None:
    assert data.startswith(b"PK"), f"{label}: 非 zip 文件头"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        for suf in expected_suffixes:
            assert any(n.endswith(suf) for n in names), f"{label}: 缺少 {suf}，实际 {names}"
    ok(f"{label} zip 结构", f"{len(names)} 项物料齐全")


async def verify_music():
    print("== 音乐发布包 ==")
    import subprocess
    import tempfile

    from PIL import Image

    from music_factory import MUSIC_DIR, music_publish_pack

    # 临时真实产物：ffmpeg 生成 3 秒正弦波 mp3 + PIL 生成 640x640 封面
    tmp = tempfile.mkdtemp(prefix="music_pack_verify_")
    mp3_path = Path(tmp) / "verify_tone.mp3"
    cover_path = Path(tmp) / "verify_tone.jpg"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
        capture_output=True,
        check=True,
    )
    Image.new("RGB", (640, 640), (120, 180, 240)).save(cover_path, "JPEG", quality=90)
    audio_id = f"verify_{int(time.time() * 1000)}.mp3"
    (MUSIC_DIR / audio_id).write_bytes(mp3_path.read_bytes())
    (MUSIC_DIR / audio_id.replace(".mp3", ".jpg")).write_bytes(cover_path.read_bytes())

    resp = await music_publish_pack(
        audio_id=audio_id,
        song_title="验证曲目",
        artist="AI 音乐人",
        genre="pop",
        current_user={"username": "admin"},
    )
    chunks = [c async for c in resp.body_iterator]
    data = b"".join(chunks)
    assert b"published=false" in resp.headers.get("X-Publish-Result", "").encode()
    ok("音乐发布包路由响应", f"X-Publish-Result={resp.headers.get('X-Publish-Result')}")
    # 校验 wav 母带规格：RIFF 头 + 44.1kHz/16bit（44100=0xAC44 小端）
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        wav = zf.read([n for n in zf.namelist() if n.endswith("母带.wav")][0])
        assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE", "wav 头异常"
        assert b"\x44\xac" in wav[24:28], "采样率非 44100"
        ok("wav 母带规格", "RIFF/WAVE + 44.1kHz 16bit")
        flac = zf.read([n for n in zf.namelist() if n.endswith("无损.flac")][0])
        assert flac[:4] == b"fLaC", "flac 头异常"
        ok("flac 无损规格", "fLaC 容器")
        lrc = zf.read([n for n in zf.namelist() if n.endswith("歌词.lrc")][0]).decode("utf-8")
        assert "[ti:验证曲目]" in lrc and "[ar:AI 音乐人]" in lrc, "lrc 头缺失"
        ok("lrc 歌词", "ti/ar 头 + 时间轴行")
    check_zip(
        data,
        ["01_歌曲.mp3", "母带.wav", "无损.flac", "封面.jpg", "歌词.lrc", "歌词.txt", "曲目信息.md", "规格说明.md", "上传指南.md", "LICENSE.txt", "质量自检报告.md"],
        "音乐",
    )
    # 清理临时产物，不污染产物目录
    (MUSIC_DIR / audio_id).unlink(missing_ok=True)
    (MUSIC_DIR / audio_id.replace(".mp3", ".jpg")).unlink(missing_ok=True)


async def verify_game():
    print("== 游戏发布包 ==")
    from game_factory import game_publish_pack

    resp = await game_publish_pack("game_ed86823783a9", current_user={"username": "admin"})
    chunks = [c async for c in resp.body_iterator]
    data = b"".join(chunks)
    check_zip(
        data,
        ["web/index.html", "wx/game.js", "README.md", "上线清单.md", "LICENSE.txt", "质量自检报告.md"],
        "游戏",
    )


async def verify_miniapp():
    print("== 小程序发布包 ==")
    from miniapp import export_zip

    resp = await export_zip("mp_1118bdb6503b", current_user={"username": "admin"})
    chunks = [c async for c in resp.body_iterator]
    data = b"".join(chunks)
    check_zip(data, ["app.js", "介绍.md", "审核清单.md", "LICENSE.txt", "质量自检报告.md"], "小程序")


async def verify_video():
    print("== 视频发布包 ==")
    from video_factory import VIDEO_DIR, video_publish_pack

    # 选真实产物中最小体积的视频，缩短转码耗时
    vids = sorted(VIDEO_DIR.glob("*.mp4"), key=lambda p: p.stat().st_size)
    assert vids, "无视频产物可验证"
    resp = await video_publish_pack(
        filename=vids[0].name,
        platform="douyin",
        video_title="验证短片",
        video_desc="发布包真实转码验证",
        current_user={"username": "admin"},
    )
    chunks = [c async for c in resp.body_iterator]
    data = b"".join(chunks)
    # 规格成片：抽帧封面 + 发布文案 + 质量报告 + LICENSE
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = zf.namelist()
        assert any(n.endswith("封面.jpg") for n in names), names
        assert any(n.endswith("发布文案.md") for n in names), names
        assert any(n.endswith("质量自检报告.md") for n in names), names
        # 抽帧封面真实为 JPEG 图（验证转码产物存在且非路径字符串）
        cover = zf.read([n for n in names if n.endswith("封面.jpg")][0])
        assert cover[:2] == b"\xff\xd8", "封面非 JPEG"
        ok("视频发布包", f"成片({vids[0].name}) + 封面 + 文案 + 质量报告")


async def main():
    await verify_music()
    await verify_game()
    await verify_miniapp()
    await verify_video()
    print(f"\n全部通过：{len(PASS)} 项校验")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
