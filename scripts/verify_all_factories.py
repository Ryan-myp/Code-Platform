#!/usr/bin/env python3
"""全模块一键验证脚本：对平台全部创作工坊做冒烟 / 深度验证。

用法:
  .venv/bin/python scripts/verify_all_factories.py            # 冒烟（默认，只读接口，~30s）
  .venv/bin/python scripts/verify_all_factories.py --deep     # 深度（真实生成，~10-20min）
  环境变量: PLATFORM_USER / PLATFORM_PASS（默认 admin/admin123）

覆盖模块:
  图片工厂（文生图 / 分割 / 背景替换 / 模板渲染）/ 视频工厂（生成 / 拼接 / 配乐 / 字幕烧录）/
  音乐工厂 / 配音工坊 / 表情包工坊 / 小游戏工坊 / 小程序工坊 / PDF 工具 / 内容发布

退出码: 0=全部通过，1=存在失败
"""

import argparse
import json
import os
import random
import sqlite3
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("PLATFORM_BASE", "http://127.0.0.1:8888")
USER = os.environ.get("PLATFORM_USER", "admin")
PASS = os.environ.get("PLATFORM_PASS", "admin123")

results: list[tuple[str, bool, str]] = []


def http(method: str, path: str, token: str = "", body: bytes | None = None, ctype: str = "application/json", timeout: int = 300) -> tuple[int, dict | str]:
    """通用 HTTP 请求，返回 (status, json 或文本)。"""
    req = urllib.request.Request(BASE + path, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", ctype)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw.decode(errors="replace")[:300]
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")[:300]
    except Exception as e:
        return -1, str(e)


def multipart(fields: dict[str, tuple[str, bytes, str]]) -> tuple[str, bytes]:
    """构造 multipart/form-data：返回 (boundary, body)；纯文本字段 filename 传 None。"""
    boundary = "----verify-factories-" + str(int(time.time() * 1000))
    parts = []
    for name, (filename, content, ctype) in fields.items():
        if filename is None:
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + content)
        else:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n".encode() + content
            )
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(parts)


def check(module: str, name: str, ok: bool, detail: str = "") -> None:
    results.append((module, ok, detail))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {module} | {name}" + (f" | {detail[:120]}" if detail and not ok else ""))


def login() -> str:
    code, data = http("POST", "/api/auth/login", body=json.dumps({"username": USER, "password": PASS}).encode())
    if code == 200 and isinstance(data, dict) and data.get("access_token"):
        print(f"[登录] {USER} OK")
        return data["access_token"]
    print(f"[登录] 失败: {code} {data}")
    sys.exit(1)


def pick_url(data) -> str:
    """从生成结果中提取图片/视频/音频 URL。"""
    if isinstance(data, dict):
        for k in ("url", "video_url", "audio_url", "image_url", "cover_url"):
            if data.get(k):
                return str(data[k])
        for k in ("images", "urls", "results", "data"):
            v = data.get(k)
            if isinstance(v, list) and v:
                first = v[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    for kk in ("url", "video_url", "audio_url", "image_url"):
                        if first.get(kk):
                            return str(first[kk])
    return ""


# ── 冒烟验证（只读接口 + 参数校验）──────────────────────────────
def smoke(token: str) -> None:
    print("\n== 冒烟验证（只读接口）==")
    # 图片工厂
    code, data = http("GET", "/api/image-factory/templates", token)
    check("图片工厂", "模板列表", code == 200 and isinstance(data, list) and len(data) >= 3)
    code, _ = http("GET", "/api/image-factory/stats", token)
    check("图片工厂", "stats", code == 200)
    code, _ = http("POST", "/api/image-factory/edit/personal-segmentation", token)
    check("图片工厂", "分割接口参数校验（无文件应 4xx 而非 5xx）", 400 <= code < 500)
    code, _ = http("POST", "/api/image-factory/edit/replace-background", token)
    check("图片工厂", "背景替换接口参数校验", 400 <= code < 500)

    # 视频工厂
    code, data = http("GET", "/api/video-factory/stats", token)
    check("视频工厂", "stats（含 channels 字段）", code == 200 and isinstance(data, dict) and "channels" in data)
    code, data = http("GET", "/api/video-factory/prompts", token)
    check("视频工厂", "预设提示词", code == 200 and isinstance(data, dict) and len(data.get("prompts", [])) >= 3)
    code, data = http("GET", "/api/video-factory/list", token)
    check("视频工厂", "视频列表", code == 200 and isinstance(data, dict))
    # 视频后期工具参数校验
    code, _ = http("POST", "/api/video-factory/tools/concat", token)
    check("视频工厂", "拼接接口参数校验", 400 <= code < 500)
    code, _ = http("POST", "/api/video-factory/tools/subtitle", token)
    check("视频工厂", "字幕接口参数校验", 400 <= code < 500)

    # 音乐工厂
    code, data = http("GET", "/api/music-factory/stats", token)
    check("音乐工厂", "stats", code == 200 and isinstance(data, dict))
    code, data = http("GET", "/api/music-factory/lyrics/examples", token)
    check("音乐工厂", "歌词示例", code == 200 and isinstance(data, dict))

    # 配音工坊
    code, data = http("GET", "/api/voice/stats", token)
    check("配音工坊", "stats", code == 200 and isinstance(data, dict))
    code, data = http("GET", "/api/voice/list", token)
    check("配音工坊", "音频列表", code == 200 and isinstance(data, list))
    code, _ = http("POST", "/api/voice/preview", token)
    check("配音工坊", "口播试听参数校验（缺 voice 应 4xx）", 400 <= code < 500)

    # 短剧工厂
    code, data = http("GET", "/api/drama/list", token)
    check("短剧工厂", "作品列表", code == 200 and isinstance(data, dict) and isinstance(data.get("items"), list))

    # 数字人（v13.24 情绪参数白名单）
    code, data = http("GET", "/api/digital-human/avatars", token)
    check("数字人", "形象列表", code == 200 and isinstance(data, dict) and len(data.get("avatars", [])) >= 3)
    code, data = http("POST", "/api/digital-human/generate", token,
                      body=json.dumps({"text": "这是一段用于验证情绪参数白名单的测试文案内容", "emotion": "bogus"}).encode())
    check("数字人", "情绪参数白名单（emotion=bogus 应 4xx）", 400 <= code < 500, f"{code} {str(data)[:120]}")

    # API Key 使用报表（T3.2）
    code, data = http("GET", "/api/api-keys/usage", token)
    check("APIKey报表", "按天聚合使用量", code == 200 and isinstance(data, dict) and "daily" in data and "total" in data)

    # 配额路径 402 分层引导（T1.3/T3.1）：临时用户置超限 → 短剧生成应 402
    smoke_quota_402(token)

    # 表情包工坊
    code, data = http("GET", "/api/meme/stats", token)
    check("表情包工坊", "stats", code == 200 and isinstance(data, dict))
    code, data = http("GET", "/api/meme/list", token)
    check("表情包工坊", "表情列表", code == 200 and isinstance(data, list))

    # 小游戏工坊
    code, data = http("GET", "/api/games/templates", token)
    check("小游戏工坊", "模板列表（≥15）", code == 200 and isinstance(data, list) and len(data) >= 15)
    code, data = http("GET", "/api/games/stats", token)
    check("小游戏工坊", "stats", code == 200 and isinstance(data, dict))

    # 小程序工坊
    code, data = http("GET", "/api/miniapp/templates", token)
    check("小程序工坊", "模板列表（≥8）", code == 200 and isinstance(data, list) and len(data) >= 8)
    code, data = http("GET", "/api/miniapp/projects", token)
    check("小程序工坊", "项目列表", code == 200 and isinstance(data, list))

    # PDF 工具
    code, data = http("GET", "/api/pdf/jobs", token)
    check("PDF工具", "任务列表", code == 200 and isinstance(data, list))

    # 内容发布
    code, data = http("GET", "/api/publish/stats", token)
    check("内容发布", "stats", code == 200 and isinstance(data, dict))


def smoke_quota_402(token: str) -> None:
    """配额 402 分层引导校验：注册临时用户 → DB 置超限 → drama sync 应 402 → 清理。"""
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    uname, pwd = f"verify_q_{suffix}", "verify1234"
    code, data = http("POST", "/api/auth/register", body=json.dumps({"username": uname, "password": pwd}).encode())
    if code != 200:
        check("配额", "402 校验前置（注册测试用户）", False, f"{code} {str(data)[:120]}")
        return
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "platform.db")
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE users SET used_today=99999, last_quota_date=date('now'), daily_quota=1 WHERE username=?", (uname,))
        conn.commit()
        conn.close()
        code, data = http("POST", "/api/auth/login", body=json.dumps({"username": uname, "password": pwd}).encode())
        if code != 200:
            check("配额", "402 校验前置（登录测试用户）", False, str(code))
            return
        code, data = http("POST", "/api/drama/generate?sync=true", data["access_token"],
                          body=urllib.parse.urlencode({"theme": "测试"}).encode(),
                          ctype="application/x-www-form-urlencoded", timeout=60)
        detail = str(data.get("detail", "")) if isinstance(data, dict) else str(data)[:80]
        check("配额", "短剧超配额返回 402 分层引导", code == 402 and ("额度" in detail or "会员" in detail), f"{code} {detail[:120]}")
    finally:
        try:
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM users WHERE username=?", (uname,))
            conn.commit()
            conn.close()
        except Exception:
            pass


# ── 深度验证（真实生成）────────────────────────────────────────
def deep(token: str) -> None:
    print("\n== 深度验证（真实生成，耗时长）==")
    gen_img = deep_image(token)
    deep_video(token, gen_img)
    deep_music(token)
    deep_voice(token)
    deep_meme(token)
    deep_game(token)
    deep_miniapp(token)
    deep_drama(token)
    deep_voice_preview(token)
    deep_dh_emotion(token)


def deep_image(token: str) -> str:
    print("\n[图片工厂] 文生图 + 分割 + 背景替换")
    code, data = http(
        "POST",
        "/api/image-factory/generate/text-to-image?sync=true",
        token,
        body=urllib.parse.urlencode({"prompt": "a cute cat sitting on grass, soft light", "size": "512x512"}).encode(),
        ctype="application/x-www-form-urlencoded",
        timeout=600,
    )
    url = pick_url(data) if isinstance(data, dict) else ""
    check("图片工厂", "文生图同步生成", code == 200 and bool(url), f"{code} {str(data)[:120]}")
    if not url:
        return ""
    img_path = url if url.startswith("http") else BASE + url
    try:
        img_bytes = urllib.request.urlopen(img_path, timeout=60).read()
    except Exception as e:
        check("图片工厂", "下载生成图", False, str(e))
        return ""
    check("图片工厂", "下载生成图", len(img_bytes) > 1000, f"{len(img_bytes)}B")

    boundary, body = multipart({"image": ("cat.png", img_bytes, "image/png"), "feather": (None, b"2", "text/plain")})
    code, data = http("POST", "/api/image-factory/edit/personal-segmentation", token, body=body, ctype=f"multipart/form-data; boundary={boundary}", timeout=600)
    check("图片工厂", "人像分割（rembg）", code == 200 and isinstance(data, dict), f"{code} {str(data)[:120]}")

    boundary, body = multipart({"image": ("cat.png", img_bytes, "image/png"), "background": (None, b"beach", "text/plain")})
    code, data = http("POST", "/api/image-factory/edit/replace-background", token, body=body, ctype=f"multipart/form-data; boundary={boundary}", timeout=600)
    check("图片工厂", "背景替换（beach 场景）", code == 200 and isinstance(data, dict), f"{code} {str(data)[:120]}")

    # 模板渲染：渐变背景 + 圆角矩形 + 文字（新能力冒烟）
    tpl = {
        "name": f"verify_tpl_{int(time.time())}",
        "width": 400, "height": 300, "background": "#6366f1→#8b5cf6",
        "layers": [
            {"type": "rect", "x": 40, "y": 40, "width": 320, "height": 100, "radius": 16, "fill": "#ffffff", "opacity": 0.9},
            {"type": "text", "x": 200, "y": 90, "text": "渐变模板验证", "font_size": 28, "color": "#1e293b", "align": "center"},
        ],
    }
    code, data = http("POST", "/api/image-factory/template/create", token, body=json.dumps(tpl).encode(), timeout=120)
    tpl_id = data.get("id", "") if isinstance(data, dict) else ""
    check("图片工厂", "模板创建（渐变背景）", code == 200 and bool(tpl_id), f"{code} {str(data)[:120]}")
    if tpl_id:
        code, data = http("POST", "/api/image-factory/template/render?sync=true", token, body=json.dumps({"template_id": tpl_id, "overrides": {}}).encode(), timeout=300)
        check("图片工厂", "模板渲染（渐变+圆角+文字）", code == 200 and isinstance(data, dict) and bool(data.get("url")), f"{code} {str(data)[:120]}")
    else:
        check("图片工厂", "模板渲染（渐变+圆角+文字）", False, "模板创建失败，无 id")
    return img_path


def deep_video(token: str, gen_img: str) -> None:
    print("\n[视频工厂] 生成 + 拼接 + 配乐 + 字幕")
    code, data = http(
        "POST",
        "/api/video-factory/generate?sync=true",
        token,
        body=urllib.parse.urlencode({"prompt": "ocean waves at sunset", "duration": 3, "width": 640, "height": 360}).encode(),
        ctype="application/x-www-form-urlencoded",
        timeout=1800,
    )
    new_file = ""
    if code == 200 and isinstance(data, dict):
        new_file = str(data.get("filename") or "").strip()
    check("视频工厂", "视频同步生成", code == 200 and bool(new_file), f"{code} {str(data)[:120] if not new_file else new_file}")
    # 用已有视频 + 新视频测拼接
    code, data = http("GET", "/api/video-factory/list", token)
    files = [f["filename"] for f in data.get("videos", [])] if isinstance(data, dict) else []
    files = [f for f in files if f != new_file][:1]
    concat_names = (files + [new_file]) if (files and new_file) else []
    if len(concat_names) >= 2:
        code, data = http("POST", "/api/video-factory/tools/concat", token, body=urllib.parse.urlencode({"filenames": ",".join(concat_names)}).encode(), ctype="application/x-www-form-urlencoded", timeout=1800)
        check("视频工厂", "多视频拼接", code == 200 and isinstance(data, dict) and data.get("url"), f"{code} {str(data)[:120]}")
    else:
        check("视频工厂", "多视频拼接", False, "无足够视频文件（需 ≥2 个）")
    if new_file:
        music_abs = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "music_factory", "music_1786286572022.mp3")
        if os.path.exists(music_abs):
            body = urllib.parse.urlencode({"video": new_file, "music": music_abs, "bg_volume": "0.3"}).encode()
            code, data = http("POST", "/api/video-factory/tools/music", token, body=body, ctype="application/x-www-form-urlencoded", timeout=1800)
            check("视频工厂", "视频配乐（BGM 混音）", code == 200 and isinstance(data, dict) and data.get("url"), f"{code} {str(data)[:120]}")
        srt = "1\n00:00:00,000 --> 00:00:02,000\nAI 视频验证\n2\n00:00:02,000 --> 00:00:03,000\n智能创作平台"
        body = urllib.parse.urlencode({"video": new_file, "srt_content": srt}).encode()
        code, data = http("POST", "/api/video-factory/tools/subtitle", token, body=body, ctype="application/x-www-form-urlencoded", timeout=1800)
        check("视频工厂", "字幕烧录", code == 200 and isinstance(data, dict) and data.get("url"), f"{code} {str(data)[:120]}")


def deep_music(token: str) -> None:
    print("\n[音乐工厂] 音乐生成")
    lyrics = "清晨的阳光洒满窗台\n我轻轻哼着熟悉的旋律\n风儿带着花香飘过来\n这一刻世界如此安静"
    body = urllib.parse.urlencode({"lyrics": lyrics, "style": "pop", "mood": "happy", "voice": "female", "duration": "15"}).encode()
    code, data = http("POST", "/api/music-factory/music/generate?sync=true", token, body=body, ctype="application/x-www-form-urlencoded", timeout=1800)
    check("音乐工厂", "音乐同步生成", code == 200 and isinstance(data, dict) and bool(pick_url(data)), f"{code} {str(data)[:120]}")


def deep_voice(token: str) -> None:
    print("\n[配音工坊] TTS 生成")
    body = urllib.parse.urlencode({"text": "智能创作平台，让每一段内容都有声音。", "voice": "zh-CN-XiaoxiaoNeural"}).encode()
    code, data = http("POST", "/api/voice/generate?sync=true", token, body=body, ctype="application/x-www-form-urlencoded", timeout=600)
    check("配音工坊", "TTS 同步生成", code == 200 and isinstance(data, dict) and bool(pick_url(data)), f"{code} {str(data)[:120]}")


def deep_meme(token: str) -> None:
    print("\n[表情包工坊] 表情包生成")
    body = urllib.parse.urlencode({"top_text": "周末快乐", "bottom_text": "冲鸭！", "style": "yellow", "decoration": "🎉,😄"}).encode()
    code, data = http("POST", "/api/meme/generate?sync=true", token, body=body, ctype="application/x-www-form-urlencoded", timeout=600)
    check("表情包工坊", "表情包生成", code == 200 and isinstance(data, dict) and bool(pick_url(data)), f"{code} {str(data)[:120]}")


def deep_game(token: str) -> None:
    print("\n[小游戏工坊] 游戏生成 + AI 封面")
    body = json.dumps({"name": "验证贪吃蛇", "template": "snake", "requirement": "经典贪吃蛇，可玩性优先"}).encode()
    code, data = http("POST", "/api/games/generate?sync=true", token, body=body, timeout=1800)
    proj_id = str(data.get("id") or "") if isinstance(data, dict) else ""
    qc_ok = isinstance(data, dict) and data.get("qc", {}).get("ok") is True
    check("小游戏工坊", "双版本游戏生成（QC 通过）", code == 200 and bool(proj_id) and qc_ok, f"{code} {str(data)[:150]}")
    if proj_id:
        code, data = http("POST", f"/api/games/{proj_id}/ai-cover", token, body=json.dumps({"prompt": ""}).encode(), timeout=600)
        check("小游戏工坊", "AI 封面生成", code == 200 and isinstance(data, dict) and data.get("cover"), f"{code} {str(data)[:120]}")


def deep_miniapp(token: str) -> None:
    print("\n[小程序工坊] 小程序生成")
    body = json.dumps({"name": "验证工具集", "template": "tool", "requirement": "记事本与计算器功能"}).encode()
    code, data = http("POST", "/api/miniapp/generate?sync=true", token, body=body, timeout=1800)
    qc_ok = isinstance(data, dict) and data.get("qc", {}).get("ok") is True
    check("小程序工坊", "小程序生成（QC 通过）", code == 200 and qc_ok, f"{code} {str(data)[:150]}")


def deep_drama(token: str) -> None:
    print("\n[短剧工厂] 短剧生成（自定义分镜，本地管线）")
    scenes = [
        {"shot": "清晨街道", "narrator": "城市刚刚苏醒，第一缕阳光洒在街道上。", "dialogue": "", "sec": 4},
        {"shot": "咖啡店", "narrator": "一杯咖啡，开启元气满满的一天。", "dialogue": "", "sec": 4},
        {"shot": "办公室", "narrator": "努力的人，运气不会太差。", "dialogue": "", "sec": 4},
    ]
    body = urllib.parse.urlencode({
        "theme": "都市奋斗", "title": "验证短剧", "duration": "12",
        "scenes_json": json.dumps(scenes, ensure_ascii=False),
    }).encode()
    code, data = http("POST", "/api/drama/generate?sync=true", token, body=body,
                      ctype="application/x-www-form-urlencoded", timeout=1800)
    url = data.get("url", "") if isinstance(data, dict) else ""
    srt = data.get("srt_url", "") if isinstance(data, dict) else ""
    check("短剧工厂", "同步生成（含字幕）", code == 200 and bool(url) and bool(srt), f"{code} {str(data)[:150]}")
    if url:
        try:
            raw = urllib.request.urlopen(url if url.startswith("http") else BASE + url, timeout=60).read()
            check("短剧工厂", "下载成片", len(raw) > 10_000, f"{len(raw)}B")
        except Exception as e:
            check("短剧工厂", "下载成片", False, str(e))


def deep_voice_preview(token: str) -> None:
    print("\n[数字人口播] 口播试听（TTS 短句预览）")
    body = urllib.parse.urlencode({"voice": "zh-CN-XiaoxiaoNeural", "text": "你好，这是口播试听验证。"}).encode()
    req = urllib.request.Request(BASE + "/api/voice/preview", data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read()
            check("口播试听", "短句 TTS 预览（audio/mpeg）", resp.status == 200 and len(raw) > 1000, f"{resp.status} {len(raw)}B")
    except urllib.error.HTTPError as e:
        check("口播试听", "短句 TTS 预览（audio/mpeg）", False, f"{e.code}")


def deep_dh_emotion(token: str) -> None:
    """v13.24 数字人情绪链路：emotion=happy 全链路生成（TTS 风格 + 2D 表情 + DB 落库）。"""
    print("\n[数字人] 情绪化口播生成（emotion=happy，声音风格+表情联动）")
    body = json.dumps({
        "text": "哇，今天真的是太棒了！阳光明媚，心情超级好，感觉整个世界都在对我微笑！",
        "engine": "2d",
        "emotion": "happy",
        "watermark": False,
    }).encode()
    code, data = http("POST", "/api/digital-human/generate?sync=true", token, body=body, timeout=1800)
    url = (data.get("video_url") or data.get("audio_url")) if isinstance(data, dict) else ""
    emotion = data.get("emotion", "") if isinstance(data, dict) else ""
    check("数字人", "情绪化生成（happy 透传+落库）", code == 200 and bool(url) and emotion == "happy", f"{code} {str(data)[:150]}")


def main() -> None:
    ap = argparse.ArgumentParser(description="全模块一键验证")
    ap.add_argument("--deep", action="store_true", help="深度验证（真实生成，耗时长）")
    args = ap.parse_args()

    print(f"目标: {BASE} | 用户: {USER}")
    token = login()
    t0 = time.time()
    smoke(token)
    if args.deep:
        deep(token)
    elapsed = round(time.time() - t0, 1)

    fails = [r for r in results if not r[1]]
    print(f"\n===== 汇总：{len(results) - len(fails)}/{len(results)} 通过（耗时 {elapsed}s）=====")
    if fails:
        print("失败项：")
        for module, _, detail in fails:
            print(f"  ✗ {module} | {detail[:150]}")
        sys.exit(1)
    print("全部通过 🎉")
    sys.exit(0)


if __name__ == "__main__":
    main()
