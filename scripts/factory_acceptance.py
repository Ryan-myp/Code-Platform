#!/usr/bin/env python3
"""工厂族 LLM 真实验收（串行，低并发，逐一生成 + magic-bytes 校验）。

覆盖除视频/音乐外的全部加工厂家族：
  小游戏 / 小程序 / PPT / 图片 / 表情包 / 配音 / PDF合同审查

配额纪律：严格串行（一次只跑一个工厂的 LLM 生成）。
用法：先起探测服务（DB_PATH=/tmp/factory_probe.db PORT=8010 APP_ENV=dev），再
  `python scripts/factory_acceptance.py [BASE_URL]`
"""

import json
import secrets
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"
RESULTS = []


def magic(b: bytes) -> str:
    if b[:4] == b"\x89PNG":
        return "PNG"
    if b[:3] == b"ID3" or b[:2] == b"\xff\xf3" or b[:2] == b"\xff\xfb":
        return "MP3"
    if b[:2] == b"PK":
        return "ZIP/PPTX"
    if b[:4] == b"%PDF":
        return "PDF"
    return "UNKNOWN"


def record(name: str, ok: bool, detail: str) -> None:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}", flush=True)


class C:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE, timeout=90)

    def register(self) -> str:
        uname = f"facc_{secrets.token_hex(3)}"
        r = self.client.post("/api/auth/register", json={"username": uname, "password": "pass1234", "email": f"{uname}@t.cn"})
        tok = (r.json().get("access_token") or r.json().get("token") or "") if r.status_code < 400 else ""
        if not tok:
            r = self.client.post("/api/auth/login", json={"username": uname, "password": "pass1234"})
            tok = r.json().get("access_token") or r.json().get("token") or ""
        if not tok:
            raise RuntimeError(f"注册/登录失败: {uname}")
        self.client.headers["Authorization"] = f"Bearer {tok}"
        return uname

    def submit(self, path: str, body: dict | None = None, form: dict | None = None):
        if form is not None:
            r = self.client.post(path, data=form)
        else:
            r = self.client.post(path, json=body or {})
        if r.status_code >= 400:
            raise RuntimeError(f"{path} -> {r.status_code} {r.text[:200]}")
        d = r.json()
        return d["task_id"] if "task_id" in d else d

    def wait(self, task_id: str, timeout: int = 480) -> dict:
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(5)
            r = self.client.get(f"/api/tasks/{task_id}")
            if r.status_code == 200:
                d = r.json()
                if d.get("status") in ("success", "failed", "error", "completed"):
                    return d
        return {"status": "timeout"}

    def fetch_url(self, url: str) -> httpx.Response:
        return self.client.get(url)


def check_image(c: C, res: dict, key: str) -> tuple[bool, str]:
    """从工厂结果里取 url，下载并校验 magic bytes。"""
    url = res.get("url") or ""
    ok = False
    detail = f"status={'success' if res.get('url') else 'no-url'} url={url}"
    if url:
        r = c.fetch_url(url)
        ok = r.status_code == 200 and len(r.content) > 1000
        detail += f" http={r.status_code} bytes={len(r.content)} magic={magic(r.content[:4])}"
        if key == "image":
            ok = ok and r.content[:4] == b"\x89PNG"
    return ok, detail


def main() -> None:
    c = C()
    print(f"user={c.register()}\n", flush=True)

    # ── 1. 小游戏（真实 LLM，双版本 + QC 门禁）──────────────
    try:
        tid = c.submit("/api/games/generate", {"name": "霓虹贪吃蛇", "template": "custom", "requirement": "经典贪吃蛇，霓虹配色，吃食物加速，撞墙或撞自己结束"})
        d = c.wait(tid)
        res = d.get("result") or {}
        files = res.get("files", {})
        qc = res.get("qc", {})
        all_keys = [str(k) for k in files.keys()] + [str(k) for v in files.values() if isinstance(v, dict) for k in v.keys()]
        has_index = any("index.html" in k for k in all_keys)
        record("小游戏", d.get("status") == "success" and bool(files) and qc.get("ok") is True and has_index,
               f"status={d.get('status')} files={res.get('file_count')} qc_ok={qc.get('ok')} versions={res.get('versions')}")
    except Exception as e:  # noqa: BLE001
        record("小游戏", False, f"异常: {e}")

    # ── 2. 小程序（真实 LLM，完整项目 + QC 门禁）──────────────
    try:
        tid = c.submit("/api/miniapp/generate", {"name": "预约到店", "template": "custom", "requirement": "美容预约：首页项目展示、预约表单、我的订单列表"})
        d = c.wait(tid)
        res = d.get("result") or {}
        files = res.get("files", {})
        qc = res.get("qc", {})
        record("小程序", d.get("status") == "success" and "app.json" in files and qc.get("ok") is True,
               f"status={d.get('status')} files={res.get('file_count')} app.json={'app.json' in files} qc_ok={qc.get('ok')}")
    except Exception as e:  # noqa: BLE001
        record("小程序", False, f"异常: {e}")

    # ── 3. PPT（真实 LLM 大纲 + PPTX 渲染，magic 校验）──────
    try:
        tid = c.submit("/api/ppt/generate", {"title": "2026 智能内容工厂产品介绍", "template": "business"})
        d = c.wait(tid)
        res = d.get("result") or {}
        url = res.get("pptx", "")
        ok = False
        detail = f"status={d.get('status')} slides={res.get('slides')} pptx={url}"
        if url:
            r = c.fetch_url(url)
            ok = r.status_code == 200 and r.content[:2] == b"PK"
            detail += f" magic={magic(r.content[:4])}"
        record("PPT", ok, detail)
    except Exception as e:  # noqa: BLE001
        record("PPT", False, f"异常: {e}")

    # ── 4. 图片文生图（magic 校验）─────────────────────────
    try:
        tid = c.submit("/api/image-factory/generate/text-to-image",
                       form={"prompt": "赛博朋克城市夜景，霓虹雨", "size": "1024x1024", "batch_size": 1, "n": 1})
        d = c.wait(tid) if isinstance(tid, str) else tid
        res = d.get("result") or d
        results = res.get("results") or []
        if results and results[0].get("url"):
            ok, detail = check_image(c, results[0], "image")
            detail = f"status={d.get('status')} " + detail
        else:
            ok, detail = False, f"status={d.get('status')} no-image: {str(res)[:120]}"
        record("图片(文生图)", ok, detail)
    except Exception as e:  # noqa: BLE001
        record("图片(文生图)", False, f"异常: {e}")

    # ── 5. 表情包（PIL 渲染，magic 校验）─────────────────────
    try:
        tid = c.submit("/api/meme/generate", form={"top_text": "班味", "bottom_text": "检测成功", "style": "yellow"})
        d = c.wait(tid) if isinstance(tid, str) else tid
        res = d.get("result") or d
        ok, detail = check_image(c, res, "image")
        record("表情包", ok, detail)
    except Exception as e:  # noqa: BLE001
        record("表情包", False, f"异常: {e}")

    # ── 6. 配音（edge-tts，mp3）────────────────────────────
    try:
        tid = c.submit("/api/voice/generate", form={"text": "欢迎使用智能内容工厂，三分钟生成一条爆款视频", "scene": "shortvideo", "format": "mp3"})
        d = c.wait(tid) if isinstance(tid, str) else tid
        res = d.get("result") or d
        url = res.get("url", "")
        ok = False
        detail = f"status={d.get('status')} url={url} duration={res.get('duration')}"
        if url:
            r = c.fetch_url(url)
            ok = r.status_code == 200 and len(r.content) > 2000
            detail += f" bytes={len(r.content)} magic={magic(r.content[:4])}"
        record("配音", ok, detail)
    except Exception as e:  # noqa: BLE001
        record("配音", False, f"异常: {e}")

    # ── 7. PDF 合同审查（真实 LLM，文本质量）────────────────
    try:
        r = c.client.post("/api/pdf/contract-review",
                          json={"text": "甲方同意乙方独占使用商标，乙方可随时终止且无需赔偿，乙方违约仅承担口头责任。"})
        d = r.json()
        text = json.dumps(d, ensure_ascii=False)
        ok = r.status_code == 200 and ("风险" in text or "建议" in text or "条款" in text)
        record("PDF合同审查", ok, f"status={r.status_code} 含风险词={'风险' in text} 长度={len(text)}")
    except Exception as e:  # noqa: BLE001
        record("PDF合同审查", False, f"异常: {e}")

    # ── 汇总 ─────────────────────────────────────────
    passed = sum(1 for x in RESULTS if x[1])
    print(f"\n== 工厂族验收: {passed}/{len(RESULTS)} PASS ==", flush=True)
    for name, ok, detail in RESULTS:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    json.dump(RESULTS, open("/tmp/factory_results.json", "w"), ensure_ascii=False, indent=1)
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
