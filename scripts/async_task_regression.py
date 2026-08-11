#!/usr/bin/env python3
"""异步任务接入回归验证：各生成端点应返回 task_id + pending，随后任务被 worker 执行。"""
import json
import time
import urllib.request

BASE = "http://localhost:8888"


def req(method, path, token=None, data=None, form=None, timeout=30):
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if form:
        headers.pop("Content-Type", None)
        body = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
    else:
        body = None
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"detail": str(e)}


def check(label, resp, expect_task=True):
    status, body = resp
    task_id = body.get("task_id") if isinstance(body, dict) else None
    ok = status == 200 and (not expect_task or task_id)
    print(f"{'PASS' if ok else 'FAIL'} {label}: http={status} task_id={task_id} "
          f"msg={(body.get('message') or body.get('detail') or '')[:30]}")
    return task_id if ok else None


def main():
    _, login = req("POST", "/api/auth/login", data={"username": "admin", "password": "admin123"})
    token = login.get("access_token", "")
    print("login:", "ok" if token else "FAIL")

    # 无文件端点
    tasks = []
    tasks.append(("game", check("game generate", req("POST", "/api/games/generate", token,
                                                     data={"name": "回归2", "description": "回归", "genre": "puzzle",
                                                           "requirement": "经典俄罗斯方块"}))))
    tasks.append(("miniapp", check("miniapp generate", req("POST", "/api/miniapp/generate?sync=false", token,
                                                           data={"name": "回归小程序", "template": "custom",
                                                                 "requirement": "记账"}))))
    tasks.append(("music_lyrics", check("music lyrics", req("POST", "/api/music-factory/lyrics/generate", token,
                                                            form={"theme": "夏天"}))))
    tasks.append(("music_sing", check("music sing", req("POST", "/api/music-factory/tts/sing", token,
                                                        form={"lyrics": "啦啦啦 啦啦啦", "style": "pop"}))))
    tasks.append(("video", check("video generate", req("POST", "/api/video-factory/generate", token,
                                                       form={"prompt": "一只猫在草地上奔跑"}))))
    tasks.append(("meme", check("meme generate", req("POST", "/api/meme/generate", token,
                                                     form={"top_text": "测试", "bottom_text": "验证", "style": "yellow"}))))
    tasks.append(("voice", check("voice generate", req("POST", "/api/voice/generate", token,
                                                       form={"text": "你好世界", "voice": "zh-CN-XiaoxiaoNeural"}))))
    tasks.append(("image_t2i", check("image t2i", req("POST", "/api/image-factory/generate/text-to-image", token,
                                                      form={"prompt": "一只橘猫", "size": "512x512"}))))

    print("\n== 等待 8s 后检查任务状态 ==")
    time.sleep(8)
    for ttype, task_id in tasks:
        if not task_id:
            continue
        _, body = req("GET", f"/api/tasks/{task_id}", token)
        if isinstance(body, dict):
            print(f"{ttype}: status={body.get('status')} progress={body.get('progress')} "
                  f"stage={(body.get('stage') or '')[:20]} err={(body.get('error') or '')[:40]}")
        else:
            print(f"{ttype}: 查询失败 {body}")

    print("\n== 任务列表（最近 15 条） ==")
    _, body = req("GET", "/api/tasks?limit=15", token)
    for t in body.get("tasks", []):
        print(f"  {t['type']:15s} {t['id']} {t['status']:12s} {t.get('progress'):5.1f} {(t.get('stage') or '')[:25]}")


if __name__ == "__main__":
    main()
