"""数字人自定义形象/声音端到端验证。

流程：登录 → 上传自定义形象（PIL 生成测试头像）→ 上传自定义声音（ffmpeg 生成测试音频）
      → 用自定义形象+自定义声音生成视频 → 校验记录与产物文件。
用法: python scripts/verify_dh_custom.py
"""
import io
import os
import subprocess
import sys
import tempfile
import time

import requests

BASE = "http://127.0.0.1:8888"


def step(msg):
    print(f"\n=== {msg} ===")


def main():
    # 1. 登录
    step("1. 登录 admin")
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
    r.raise_for_status()
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("登录成功")

    # 2. 上传自定义形象（PIL 生成 512x640 测试人像图）
    step("2. 上传自定义形象")
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (512, 640), (240, 220, 200))
        d = ImageDraw.Draw(img)
        d.ellipse([156, 60, 356, 260], fill=(222, 184, 135))   # 脸
        d.ellipse([180, 130, 220, 170], fill=(60, 40, 30))     # 眼
        d.ellipse([292, 130, 332, 170], fill=(60, 40, 30))
        d.rectangle([206, 300, 306, 420], fill=(90, 120, 180)) # 衣服
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        r = requests.post(
            f"{BASE}/api/digital-human/custom-avatars", headers=headers,
            files={"file": ("test_avatar.png", buf, "image/png")},
            data={"name": "验证测试形象", "desc": "e2e 自动验证"},
            timeout=30,
        )
        r.raise_for_status()
        avatar = r.json()["avatar"]
        print("自定义形象:", avatar)
        assert avatar["id"].startswith("custom_"), "形象 ID 应为 custom_ 前缀"
        avatar_id = avatar["id"]
    except Exception as e:
        print(f"上传自定义形象失败: {e}")
        return 1

    # 3. 上传自定义声音（ffmpeg 生成 3 秒正弦波音频）
    step("3. 上传自定义声音")
    audio_tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    audio_tmp.close()
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
             "-ar", "16000", audio_tmp.name],
            check=True, capture_output=True, timeout=30,
        )
        with open(audio_tmp.name, "rb") as f:
            r = requests.post(
                f"{BASE}/api/digital-human/custom-voices", headers=headers,
                files={"file": ("test_voice.wav", f, "audio/wav")},
                data={"name": "验证测试声音", "desc": "e2e 自动验证"},
                timeout=30,
            )
        r.raise_for_status()
        voice = r.json()["voice"]
        print("自定义声音:", voice)
        assert voice["id"].startswith("custom_"), "声音 ID 应为 custom_ 前缀"
        assert voice["duration"] > 0, "时长应 > 0"
        voice_id = voice["id"]
    except Exception as e:
        print(f"上传自定义声音失败: {e}")
        return 1
    finally:
        if os.path.exists(audio_tmp.name):
            os.remove(audio_tmp.name)

    # 4. 列表校验（合并展示用）
    step("4. 列表校验")
    r = requests.get(f"{BASE}/api/digital-human/custom-avatars", headers=headers, timeout=10)
    avs = r.json()["avatars"]
    assert any(a["id"] == avatar_id for a in avs), "自定义形象应在列表中"
    r = requests.get(f"{BASE}/api/digital-human/custom-voices", headers=headers, timeout=10)
    vos = r.json()["voices"]
    assert any(v["id"] == voice_id for v in vos), "自定义声音应在列表中"
    print(f"列表 OK：形象 {len(avs)} 个，声音 {len(vos)} 个")

    # 5. 用自定义形象+自定义声音生成视频
    step("5. 生成数字人视频（自定义形象 + 自定义声音）")
    t0 = time.time()
    r = requests.post(
        f"{BASE}/api/digital-human/generate", headers=headers,
        json={
            "text": "大家好，这是我的自定义数字人形象和声音测试",
            "avatar_id": avatar_id,
            "voice_id": voice_id,
            "background_id": "tech",
            "scene_id": "product",
            "speed": 1.0,
        },
        timeout=180,
    )
    r.raise_for_status()
    res = r.json()
    print("生成结果:", {k: res.get(k) for k in ("record_id", "status", "audio_url", "video_url", "error")})
    assert res["status"] == "done", f"视频应生成成功: {res}"
    assert res["video_url"] and res["video_url"].startswith("/uploads/videos/"), "应产出视频文件"
    video_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", res["video_url"].lstrip("/"))
    assert os.path.exists(video_path) and os.path.getsize(video_path) > 1024, "视频文件应存在且非空"
    print(f"视频生成 OK：{video_path}（{os.path.getsize(video_path)} 字节，耗时 {round(time.time() - t0, 1)}s）")

    # 6. 记录校验（avatar_name / voice_name 应为自定义名）
    r = requests.get(f"{BASE}/api/digital-human/records?limit=5", headers=headers, timeout=10)
    rec = next((x for x in r.json() if x["id"] == res["record_id"]), None)
    assert rec, "记录应存在"
    assert rec["avatar_name"] == "验证测试形象", f"记录形象名错误: {rec['avatar_name']}"
    assert rec["voice_name"] == "验证测试声音", f"记录声音名错误: {rec['voice_name']}"
    print("记录 OK：", rec["avatar_name"], "+", rec["voice_name"], "->", rec["status"])

    # 7. 清理测试数据
    step("7. 清理测试数据")
    requests.delete(f"{BASE}/api/digital-human/custom-avatars/{avatar_id}", headers=headers, timeout=10)
    requests.delete(f"{BASE}/api/digital-human/custom-voices/{voice_id}", headers=headers, timeout=10)
    requests.delete(f"{BASE}/api/digital-human/records/{res['record_id']}", headers=headers, timeout=10)
    if os.path.exists(video_path):
        os.remove(video_path)
    print("清理完成 ✓")

    print("\n🎉 数字人自定义形象/声音全链路验证通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
