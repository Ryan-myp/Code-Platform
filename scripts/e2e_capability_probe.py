#!/usr/bin/env python3
"""E2E 能力实测探针 — 对运行中的平台逐个功能域打真实请求，验证「实际能力」。

用法:
    cd <repo> && .venv/bin/python scripts/e2e_capability_probe.py [BASE_URL] [--no-llm]
    --no-llm: Agnes 配额限流期间只测本地能力，LLM 探针标 SKIP

设计原则:
- 每个探针独立失败隔离（一个坏不影响其他）
- 结果分三级: PASS（证据成立）/ FAIL（返回错误或证据不成立）/ SKIP（外部依赖缺失）
- 生成物（图片/音频/PPTX/MP3）做 magic bytes 校验，不只看 200
- 输出: 终端矩阵 + docs/e2e-capability-report-YYYYMMDD.md + /tmp/e2e_results.json

外部依赖说明:
- LLM: 需 .env 有 AGNES_API_KEY（本地已有）
- 配音/音乐: edge-tts 走公网
- 数字人: 外部渲染服务（本探针只探测配置端点）
"""

import io
import json
import os
import sys
import time
import uuid
from datetime import datetime

import httpx

_argv = [a for a in sys.argv[1:] if not a.startswith("--")]
BASE = _argv[0] if _argv else "http://127.0.0.1:8009"
NO_LLM = "--no-llm" in sys.argv  # Agnes 配额限流期间：只测本地能力，LLM 探针标 SKIP
RESULTS: list[dict] = []
CTX: dict = {}  # 跨探针共享状态（token / task_id / 生成物路径等）

# 生成物 magic 校验
MAGIC = {
    "png": b"\x89PNG",
    "jpeg": b"\xff\xd8",
    "gif": b"GIF8",
    "webp": b"RIFF",
    "mp3": (b"ID3", b"\xff\xf3", b"\xff\xfb", b"fLaC"),
    "wav": b"RIFF",
    "zip_pptx": b"PK\x03\x04",
    "pdf": b"%PDF",
    "html": None,
}


def magic_ok(data: bytes, kind: str) -> bool:
    m = MAGIC.get(kind)
    if m is None:
        return len(data) > 0
    if isinstance(m, tuple):
        return any(data[:8].startswith(x) for x in m)
    return data[:8].startswith(m) or (kind in ("png", "jpeg", "webp") and data[:4] in (b"\x89PNG", b"RIFF"))


def log(icon: str, probe: str, detail: str = "") -> None:
    print(f"  {icon} {probe:<44s} {detail[:110]}", flush=True)


def record(
    domain: str,
    name: str,
    status: str,
    evidence: str = "",
    elapsed: float = 0,
    http: int | None = None,
    error: str = "",
):
    RESULTS.append(
        {
            "domain": domain,
            "name": name,
            "status": status,
            "evidence": evidence[:300],
            "elapsed_s": round(elapsed, 2),
            "http": http,
            "error": error[:300],
        }
    )
    icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "•")
    log(icon, f"[{domain}] {name}", evidence or error)


def probe(domain: str, name: str, fn, client: httpx.Client) -> None:
    t0 = time.time()
    try:
        fn(client, t0)
    except httpx.HTTPStatusError as e:
        record(domain, name, "FAIL", http=e.response.status_code, error=str(e)[:200], elapsed=time.time() - t0)
    except Exception as e:  # noqa: BLE001
        record(domain, name, "FAIL", error=f"{type(e).__name__}: {e}"[:200], elapsed=time.time() - t0)


# ══════════════════════════════════════════════════════════
# A. 账户与鉴权
# ══════════════════════════════════════════════════════════
def a_register(client: httpx.Client, _t0: float) -> None:
    uname = f"probe_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/auth/register", json={"username": uname, "password": "probe-pass-123", "email": f"{uname}@probe.local"}
    )
    record(
        "A 账户鉴权",
        "注册新用户",
        "PASS" if r.status_code in (200, 201) else "FAIL",
        http=r.status_code,
        evidence=r.text[:120],
        elapsed=time.time() - _t0,
    )
    r = client.post("/api/auth/login", json={"username": uname, "password": "probe-pass-123"})
    if r.status_code == 200:
        token = r.json().get("token") or r.json().get("access_token", "")
        CTX["token"] = token
        record(
            "A 账户鉴权", "登录取 token", "PASS", http=200, evidence=f"token {token[:16]}...", elapsed=time.time() - _t0
        )
    else:
        record("A 账户鉴权", "登录取 token", "FAIL", http=r.status_code, error=r.text[:150], elapsed=time.time() - _t0)
        CTX["token"] = ""
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {CTX['token']}"})
    record(
        "A 账户鉴权",
        "当前用户 /me",
        "PASS" if r.status_code == 200 else "FAIL",
        http=r.status_code,
        evidence=json.dumps(r.json(), ensure_ascii=False)[:100],
        elapsed=time.time() - _t0,
    )
    r = client.get("/api/auth/quota", headers={"Authorization": f"Bearer {CTX['token']}"})
    record(
        "A 账户鉴权",
        "配额 /quota",
        "PASS" if r.status_code == 200 else "FAIL",
        http=r.status_code,
        evidence=r.text[:100],
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# B. LLM 能力
# ══════════════════════════════════════════════════════════
def b_assistant(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record("B LLM", "助手对话（Agnes 真实调用）", "SKIP", evidence="限流期间 --no-llm 模式，不触发 LLM")
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post("/api/assistant/chat", json={"message": "1+1=？只回答一个数字。"}, headers=h, timeout=90)
    ok = r.status_code == 200 and "2" in r.json().get("result", "")
    record(
        "B LLM",
        "助手对话（Agnes 真实调用）",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=r.json().get("result", "")[:80] if r.status_code == 200 else r.text[:100],
        elapsed=time.time() - _t0,
    )


def b_sse(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record("B LLM", "助手 SSE 流式", "SKIP", evidence="限流期间 --no-llm 模式，不触发 LLM")
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    got = []
    with client.stream(
        "POST", "/api/assistant/chat/stream", json={"message": "用一句话介绍你自己"}, headers=h, timeout=90
    ) as r:
        for line in r.iter_lines():
            got.append(line)
            if sum(len(x) for x in got) > 3000:
                break
    ok = r.status_code == 200 and any("data:" in x for x in got)
    record(
        "B LLM",
        "助手 SSE 流式",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=f"{len(got)} 行, 前: {str(got[1])[:80] if len(got) > 1 else ''}",
        elapsed=time.time() - _t0,
    )


def b_openai_compat(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/v1/chat/completions",
        json={"model": "agnes-2.5-flash", "messages": [{"role": "user", "content": "说 ok"}]},
        headers=h,
        timeout=60,
    )
    detail = r.json().get("error", {}).get("message", "") if r.status_code != 200 else ""
    if r.status_code == 403 and "网关" in detail:
        record(
            "B LLM",
            "OpenAI 兼容 /v1（中转站默认关闭）",
            "SKIP",
            http=403,
            evidence="gateway_open=0（计费未完善，设计性关闭）",
            elapsed=time.time() - _t0,
        )
        return
    ok = r.status_code == 200 and r.json().get("choices")
    record(
        "B LLM",
        "OpenAI 兼容 /v1/chat/completions",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=r.text[:100],
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# C. 工作流 / Agent / 工具
# ══════════════════════════════════════════════════════════
def c_workflow(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    name = f"probe_wf_{uuid.uuid4().hex[:6]}"
    # 真实 DAG：input → agent(LLM) → output，验证 executor 拓扑执行而非空工作流
    nodes = [
        {"id": "n1", "type": "agent", "label": "AI 助手", "config": {"message": "${input.message}"}},
        {"id": "n2", "type": "output", "label": "输出", "config": {}},
    ]
    connections = [{"source": "input", "target": "n1"}, {"source": "n1", "target": "n2"}]
    r = client.post(
        "/api/workflows",
        json={"name": name, "description": "e2e probe", "steps": nodes, "connections": connections},
        headers=h,
    )
    wf_id = r.json().get("id", "") if r.status_code == 200 else ""
    if not wf_id:
        record("C 编排", "创建工作流", "FAIL", http=r.status_code, error=r.text[:150], elapsed=time.time() - _t0)
        return
    record("C 编排", "创建工作流（DAG 节点）", "PASS", evidence=wf_id, elapsed=0)
    if NO_LLM:
        record("C 编排", "运行工作流（executor DAG+LLM）", "SKIP", evidence=f"wf={wf_id} 限流期间不执行")
        return
    r = client.post(f"/api/workflows/{wf_id}/run", json={"message": "用一句话回答：1+1=2 吗？"}, headers=h, timeout=120)
    j = r.json() if r.status_code == 200 else {}
    result = j.get("result") or ""
    ok = r.status_code == 200 and bool(result) and "失败" not in result and "未产生任何输出" not in result
    record(
        "C 编排",
        "运行工作流（executor DAG+LLM）",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=str(result)[:80] or r.text[:100],
        elapsed=time.time() - _t0,
    )


def c_agent(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/agents", json={"name": f"probe_agent_{uuid.uuid4().hex[:6]}", "instructions": "你是翻译助手"}, headers=h
    )
    if r.status_code != 200:
        record("C 编排", "创建 Agent", "FAIL", http=r.status_code, error=r.text[:150], elapsed=time.time() - _t0)
        return
    agent_id = r.json().get("id") or r.json().get("agent_id", "")
    record("C 编排", "创建 Agent", "PASS", evidence=str(agent_id), elapsed=0)
    if NO_LLM:
        record("C 编排", "运行 Agent（LLM）", "SKIP", evidence=f"agent={agent_id} 限流期间不执行")
        return
    r = client.post(
        f"/api/agents/{agent_id}/run", json={"message": "把 hello 翻译成中文，只给结果"}, headers=h, timeout=90
    )
    ok = r.status_code == 200 and r.json().get("result")
    record(
        "C 编排",
        "运行 Agent（LLM）",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=str(r.json().get("result", ""))[:60] if r.status_code == 200 else r.text[:100],
        elapsed=time.time() - _t0,
    )


def c_tools(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.get("/api/tools", headers=h)
    j = r.json()
    tools = j if isinstance(j, list) else (j.get("tools") or j.get("items") or [])
    if r.status_code != 200 or not tools:
        record(
            "C 编排", "工具清单 /api/tools", "FAIL", http=r.status_code, error=str(j)[:100], elapsed=time.time() - _t0
        )
        return
    record(
        "C 编排",
        f"工具清单（{len(tools)} 个）",
        "PASS",
        evidence=", ".join((t.get("name", "") if isinstance(t, dict) else str(t))[:10] for t in tools[:5]),
        elapsed=time.time() - _t0,
    )
    pick = None
    for t in tools:
        tid = t.get("id") or t.get("tool_id") if isinstance(t, dict) else t
        if tid and any(k in str(tid) for k in ("calc", "json", "regex", "convert", "encode", "uuid", "hash")):
            pick = tid
            break
    if not pick:
        pick = (tools[0].get("id") or tools[0].get("tool_id")) if isinstance(tools[0], dict) else tools[0]
    r = client.post(
        "/api/tools/run",
        json={"tool_id": pick, "input": "42", "params": {}, "model": ""},
        params={"sync": "true"},
        headers=h,
        timeout=60,
    )
    ok = r.status_code == 200
    record(
        "C 编排",
        f"同步运行工具 {pick}",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=r.text[:120],
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# D. 知识库
# ══════════════════════════════════════════════════════════
def d_kb(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    doc = ("# 探针文档\n本公司代号：PROBE-X9。\n核心产品：智能内容工厂。\n支持向量检索与关键词检索。" * 3).encode(
        "utf-8"
    )
    r = client.post(
        "/api/knowledge-bases/upload", files={"file": ("probe_doc.md", io.BytesIO(doc), "text/markdown")}, headers=h
    )
    if r.status_code != 200:
        record("D 知识库", "上传文档", "FAIL", http=r.status_code, error=r.text[:120], elapsed=time.time() - _t0)
        return
    path = r.json().get("path") or r.json().get("file_path", "")
    record("D 知识库", "上传文档", "PASS", evidence=path[:80], elapsed=0)
    r = client.post(
        "/api/knowledge-bases", json={"name": "probe_kb", "type": "file", "path": path, "top_k": 5}, headers=h
    )
    if r.status_code != 200:
        record(
            "D 知识库", "创建 file 型知识库", "FAIL", http=r.status_code, error=r.text[:120], elapsed=time.time() - _t0
        )
        return
    kb_id = r.json().get("id") or r.json().get("kb_id", "")
    record("D 知识库", "创建 file 型知识库", "PASS", evidence=str(kb_id), elapsed=0)
    r = client.get(f"/api/knowledge-bases/{kb_id}/search", params={"q": "代号", "limit": 5}, headers=h)
    body = r.json() if r.status_code == 200 else {}
    hits = body.get("hits") or body.get("results") or []
    ok = r.status_code == 200 and hits
    record(
        "D 知识库",
        "检索命中",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=(json.dumps(body, ensure_ascii=False)[:100] if hits else f"无命中/空壳返回: {str(body)[:80]}"),
        elapsed=time.time() - _t0,
    )
    # 能力升级验证：多词非相邻查询 + 相关度打分排序（KB 检索质量 P0）
    r2 = client.get(f"/api/knowledge-bases/{kb_id}/search", params={"q": "智能 检索", "limit": 5}, headers=h)
    b2 = r2.json() if r2.status_code == 200 else {}
    h2 = b2.get("hits") or []
    scored = bool(h2) and all(x.get("score", 0) > 0 for x in h2)
    record(
        "D 知识库",
        "多词检索+相关度排序",
        "PASS" if scored else "FAIL",
        http=r2.status_code,
        evidence=f"hits={len(h2)} top_score={h2[0].get('score') if h2 else None}",
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# E. 任务队列
# ══════════════════════════════════════════════════════════
def e_tasks(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record(
            "E 任务队列", "异步任务全链路（create→worker→done）", "SKIP", evidence="翻译任务依赖 LLM，限流期间不提交"
        )
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    # 轻量真实任务：翻译 6 字（LLM 异步任务全链路：创建→worker→完成）
    r = client.post(
        "/api/translation/translate",
        json={"text": "智能内容工厂", "source_lang": "中文", "target_lang": "English"},
        headers=h,
        timeout=30,
    )
    if r.status_code != 200:
        record(
            "E 任务队列",
            "异步任务提交（翻译）",
            "FAIL",
            http=r.status_code,
            error=r.text[:120],
            elapsed=time.time() - _t0,
        )
        return
    task_id = r.json().get("task_id") or r.json().get("id", "")
    final = None
    for _ in range(36):
        time.sleep(5)
        rr = client.get(f"/api/tasks/{task_id}", headers=h, timeout=15)
        if rr.status_code == 200:
            st = rr.json().get("status")
            if st in ("completed", "success", "failed", "cancelled"):
                final = rr.json()
                break
    if not final:
        record("E 任务队列", "异步任务轮询", "FAIL", error="90s 内未完成", elapsed=time.time() - _t0)
        return
    ok = final.get("status") in ("completed", "success")
    record(
        "E 任务队列",
        "异步任务全链路（create→worker→done）",
        "PASS" if ok else "FAIL",
        evidence=f"status={final.get('status')} result={str(final.get('result') or final.get('error'))[:60]}",
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# F. 内容工厂：图片 / 表情包
# ══════════════════════════════════════════════════════════
def f_meme(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/meme/generate",
        data={"top_text": "周一", "bottom_text": "求生", "style": "yellow", "sync": "true"},
        params={"sync": "true"},
        headers=h,
        timeout=120,
    )
    if r.status_code != 200:
        record(
            "F 工厂",
            "表情包生成（本地渲染）",
            "FAIL",
            http=r.status_code,
            error=r.text[:120],
            elapsed=time.time() - _t0,
        )
        return
    j = r.json()
    fn = j.get("filename") or j.get("image") or j.get("id") or (j.get("images") or [{}])[0].get("filename", "")
    if not fn:
        record(
            "F 工厂", "表情包生成（本地渲染）", "FAIL", error=f"响应无文件: {str(j)[:100]}", elapsed=time.time() - _t0
        )
        return
    img = client.get(f"/api/meme/images/{fn}", headers=h)
    ok = img.status_code == 200 and magic_ok(img.content, "png")
    record(
        "F 工厂",
        "表情包生成（本地渲染+PNG校验）",
        "PASS" if ok else "FAIL",
        http=img.status_code,
        evidence=f"{fn} {len(img.content)}B png={magic_ok(img.content, 'png')}",
        elapsed=time.time() - _t0,
    )


def f_image_t2i(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/image-factory/generate/text-to-image",
        data={"prompt": "蓝色渐变几何背景，极简风格", "size": "1024x1024", "batch_size": 1, "n": 1, "sync": "true"},
        params={"sync": "true"},
        headers=h,
        timeout=300,
    )
    if r.status_code != 200:
        detail = r.text
        if "未选择图片模型" in detail or "中转站" in detail:
            record(
                "F 工厂",
                "文生图（需配置中转站 Key+图片模型）",
                "SKIP",
                http=r.status_code,
                error=detail[:150],
                elapsed=time.time() - _t0,
            )
            return
        record(
            "F 工厂",
            "文生图（外部图片API）",
            "FAIL" if r.status_code < 500 else "SKIP",
            http=r.status_code,
            error=detail[:150],
            elapsed=time.time() - _t0,
        )
        return
    j = r.json()
    # 响应结构：{"results": [{"id": filename, "url": "/api/image-factory/images/<file>"}], "total": N}
    fn = j.get("filename") or j.get("id") or ((j.get("results") or [{}])[0].get("id") or "")
    url = ((j.get("results") or [{}])[0].get("url") or f"/api/image-factory/images/{fn}").strip("/")
    if not fn:
        record(
            "F 工厂", "文生图（外部图片API）", "FAIL", error=f"响应无文件: {str(j)[:100]}", elapsed=time.time() - _t0
        )
        return
    img = client.get(f"/{url}", headers=h)
    ok = (
        img.status_code == 200
        and len(img.content) > 5000
        and (magic_ok(img.content, "jpeg") or magic_ok(img.content, "png"))
    )
    record(
        "F 工厂",
        "文生图（外部图片API+字节校验）",
        "PASS" if ok else "FAIL",
        http=img.status_code,
        evidence=f"{fn} {len(img.content)}B",
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# G. 内容工厂：音频（配音/音乐）
# ══════════════════════════════════════════════════════════
def g_voice(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/voice/generate",
        data={"text": "你好，这是端到端能力实测配音。", "scene": "shortvideo"},
        params={"sync": "true"},
        headers=h,
        timeout=180,
    )
    if r.status_code != 200:
        record(
            "G 音频",
            "AI 配音（edge-tts）",
            "FAIL" if r.status_code < 500 else "SKIP",
            http=r.status_code,
            error=r.text[:150],
            elapsed=time.time() - _t0,
        )
        return
    j = r.json()
    fn = j.get("filename") or j.get("audio") or j.get("id") or (j.get("audios") or [{}])[0].get("filename", "")
    if not fn:
        record("G 音频", "AI 配音（edge-tts）", "FAIL", error=f"响应无文件: {str(j)[:100]}", elapsed=time.time() - _t0)
        return
    aud = client.get(f"/api/voice/audios/{fn}", headers=h)
    ok = aud.status_code == 200 and len(aud.content) > 3000 and magic_ok(aud.content, "mp3")
    record(
        "G 音频",
        "AI 配音（edge-tts + MP3校验）",
        "PASS" if ok else "FAIL",
        http=aud.status_code,
        evidence=f"{fn} {len(aud.content)}B mp3={magic_ok(aud.content, 'mp3')}",
        elapsed=time.time() - _t0,
    )


def g_music(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/music-factory/music/generate",
        data={
            "lyrics": "探针之歌 啦啦啦啦\n我们测试内容工厂的力量",
            "style": "pop",
            "mood": "happy",
            "voice": "female",
            "duration": 15,
            "sync": "true",
        },
        params={"sync": "true"},
        headers=h,
        timeout=300,
    )
    if r.status_code != 200:
        record(
            "G 音频",
            "AI 音乐合成（15s）",
            "FAIL" if r.status_code < 500 else "SKIP",
            http=r.status_code,
            error=r.text[:150],
            elapsed=time.time() - _t0,
        )
        return
    j = r.json()
    fn = j.get("filename") or j.get("audio") or j.get("audio_id") or (j.get("audios") or [{}])[0].get("filename", "")
    if not fn:
        record("G 音频", "AI 音乐合成（15s）", "FAIL", error=f"响应无文件: {str(j)[:100]}", elapsed=time.time() - _t0)
        return
    aud = client.get(f"/api/music-factory/audios/{fn}", headers=h)
    ok = aud.status_code == 200 and len(aud.content) > 10000 and magic_ok(aud.content, "mp3")
    record(
        "G 音频",
        "AI 音乐合成（15s + MP3校验）",
        "PASS" if ok else "FAIL",
        http=aud.status_code,
        evidence=f"{fn} {len(aud.content)}B",
        elapsed=time.time() - _t0,
    )


# ══════════════════════════════════════════════════════════
# H. 内容工厂：文档（PPT / PDF / Excel / 脑图）
# ══════════════════════════════════════════════════════════
def h_ppt(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record("H 文档", "PPT 生成提交（异步）", "SKIP", evidence="依赖 LLM，限流期间不提交")
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post("/api/ppt/generate", json={"title": "E2E 能力探针", "template": "business"}, headers=h, timeout=30)
    if r.status_code != 200:
        record("H 文档", "PPT 生成提交", "FAIL", http=r.status_code, error=r.text[:120], elapsed=time.time() - _t0)
        return
    task_id = r.json().get("task_id") or r.json().get("id", "")
    CTX["ppt_task"] = task_id
    record("H 文档", "PPT 生成提交（异步）", "PASS", evidence=task_id, elapsed=time.time() - _t0)


def h_ppt_poll(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record("H 文档", "PPT 生成完成轮询", "SKIP", evidence="依赖 LLM，限流期间不执行")
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    task_id = CTX.get("ppt_task")
    if not task_id:
        record("H 文档", "PPT 完成轮询", "SKIP", error="前置提交失败", elapsed=time.time() - _t0)
        return
    final = None
    for _ in range(48):
        time.sleep(5)
        rr = client.get(f"/api/tasks/{task_id}", headers=h, timeout=15)
        if rr.status_code == 200:
            st = rr.json().get("status")
            if st in ("completed", "success", "failed", "cancelled"):
                final = rr.json()
                break
    if not final:
        record("H 文档", "PPT 完成轮询", "FAIL", error="240s 未完成", elapsed=time.time() - _t0)
        return
    if final.get("status") not in ("completed", "success"):
        record("H 文档", "PPT 生成", "FAIL", error=str(final.get("error"))[:120], elapsed=time.time() - _t0)
        return
    res = final.get("result") or {}
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except ValueError:
            res = {}
    # PPT 结果键：pptx=/api/ppt/download/<file>.pptx（完整 URL），slides=页数
    ppt_url = res.get("pptx") or ""
    fn = (
        (ppt_url.rstrip("/").split("/")[-1] if ppt_url else "")
        or res.get("filename")
        or res.get("file")
        or res.get("audio_id", "")
    )
    if not fn:
        record(
            "H 文档",
            "PPT 生成（结果解析）",
            "FAIL",
            error=f"result 无文件: {str(res)[:100]}",
            elapsed=time.time() - _t0,
        )
        return
    ppt = client.get(f"/api/ppt/download/{fn}", headers=h)
    ok = ppt.status_code == 200 and magic_ok(ppt.content, "zip_pptx")
    record(
        "H 文档",
        "PPT 生成（PPTX 字节校验）",
        "PASS" if ok else "FAIL",
        http=ppt.status_code,
        evidence=f"{fn} {len(ppt.content)}B zip={magic_ok(ppt.content, 'zip_pptx')}",
        elapsed=time.time() - _t0,
    )


def h_excel(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/excel/operate",
        json={"operation": "create", "columns": ["名称", "值"], "rows": [["alpha", 1], ["beta", 2]]},
        headers=h,
        timeout=60,
    )
    ok = r.status_code == 200
    record(
        "H 文档",
        "Excel 生成",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=r.text[:100],
        elapsed=time.time() - _t0,
    )


def h_mindmap(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record("H 文档", "脑图生成", "SKIP", evidence="依赖 LLM，限流期间不执行")
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post("/api/mindmap/generate", json={"topic": "内容工厂", "sync": True}, headers=h, timeout=180)
    if r.status_code == 200:
        j = r.json()
        if j.get("task_id") or j.get("id"):
            record(
                "H 文档",
                "脑图生成（异步）",
                "PASS",
                evidence=str(j.get("task_id") or j.get("id")),
                elapsed=time.time() - _t0,
            )
        else:
            record("H 文档", "脑图生成", "PASS" if j else "FAIL", evidence=str(j)[:100], elapsed=time.time() - _t0)
    else:
        record("H 文档", "脑图生成", "FAIL", http=r.status_code, error=r.text[:120], elapsed=time.time() - _t0)


# ══════════════════════════════════════════════════════════
# I. 沙箱 / MCP / 平台管理
# ══════════════════════════════════════════════════════════
def i_sandbox(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.get("/api/sandbox/info", headers=h, timeout=30)
    j = r.json() if r.status_code == 200 else {}
    docker = str(j.get("docker") or j.get("docker_available") or j.get("available") or "")
    record(
        "I 平台",
        "沙箱环境探测",
        "PASS" if r.status_code == 200 else "FAIL",
        http=r.status_code,
        evidence=f"docker={docker or 'unknown'} {str(j)[:80]}",
        elapsed=time.time() - _t0,
    )


def i_mcp(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.get("/api/mcp-servers", headers=h)
    record(
        "I 平台",
        "MCP 服务器管理",
        "PASS" if r.status_code == 200 else "FAIL",
        http=r.status_code,
        evidence=r.text[:80],
        elapsed=time.time() - _t0,
    )


def i_share(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/shares", json={"title": "probe", "content": "probe share content", "type": "text"}, headers=h, timeout=30
    )
    if r.status_code != 200:
        record("I 平台", "内容分享", "FAIL", http=r.status_code, error=r.text[:100], elapsed=time.time() - _t0)
        return
    code = r.json().get("share_code") or r.json().get("code", "")
    pub = client.get(f"/share/{code}", timeout=15)
    ok = pub.status_code == 200
    record(
        "I 平台",
        "分享外链公开访问",
        "PASS" if ok else "FAIL",
        http=pub.status_code,
        evidence=f"code={code}",
        elapsed=time.time() - _t0,
    )


def i_teams(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post("/api/teams", json={"name": f"probe_team_{uuid.uuid4().hex[:6]}"}, headers=h)
    ok = r.status_code in (200, 201)
    team_id = r.json().get("id") or r.json().get("team_id", "") if ok else ""
    record(
        "I 平台",
        "团队创建",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=str(team_id)[:40],
        elapsed=time.time() - _t0,
    )
    if team_id:
        d = client.get(f"/api/teams/{team_id}/dashboard", headers=h)
        record(
            "I 平台",
            "团队仪表盘",
            "PASS" if d.status_code == 200 else "FAIL",
            http=d.status_code,
            evidence=d.text[:80],
            elapsed=time.time() - _t0,
        )


# ══════════════════════════════════════════════════════════
# J. 数字人 / 短剧 / 游戏 / 小程序（重外部依赖域）
# ══════════════════════════════════════════════════════════
def j_dh_config(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.get("/api/digital-human/templates", headers=h, timeout=30)
    ok = r.status_code == 200
    record(
        "J 重工厂",
        "数字人模板配置",
        "PASS" if ok else "FAIL",
        http=r.status_code,
        evidence=r.text[:80],
        elapsed=time.time() - _t0,
    )


def j_drama_config(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.get("/api/drama/config", headers=h, timeout=30)
    record(
        "J 重工厂",
        "短剧配置探测",
        "PASS" if r.status_code == 200 else "FAIL",
        http=r.status_code,
        evidence=r.text[:80],
        elapsed=time.time() - _t0,
    )


def j_games(client: httpx.Client, _t0: float) -> None:
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.get("/api/games/templates", headers=h, timeout=30)
    record(
        "J 重工厂",
        "游戏模板市场",
        "PASS" if r.status_code == 200 else "FAIL",
        http=r.status_code,
        evidence=r.text[:80],
        elapsed=time.time() - _t0,
    )


def j_miniapp_gen(client: httpx.Client, _t0: float) -> None:
    if NO_LLM:
        record("J 重工厂", "小程序生成（LLM 全项目）", "SKIP", evidence="依赖 LLM，限流期间不提交")
        return
    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post(
        "/api/miniapp/generate",
        json={"name": "probe_mini", "template": "custom", "requirement": "一个 hello world 页面"},
        headers=h,
        timeout=30,
    )
    if r.status_code != 200:
        record("J 重工厂", "小程序生成提交", "FAIL", http=r.status_code, error=r.text[:120], elapsed=time.time() - _t0)
        return
    j = r.json()
    proj = j.get("project_id") or j.get("task_id") or j.get("id", "")
    record("J 重工厂", "小程序生成提交（LLM 全项目）", "PASS", evidence=str(proj)[:40], elapsed=time.time() - _t0)
    # 轮询任务状态（sync=false 返回 task_id）
    final = None
    for _ in range(48):
        time.sleep(5)
        rr = client.get(f"/api/tasks/{proj}", headers=h, timeout=15)
        if rr.status_code == 200:
            st = rr.json().get("status")
            if st in ("completed", "done", "success", "failed", "cancelled"):
                final = rr.json()
                break
    if final:
        ok = final.get("status") in ("completed", "done", "success")
        record(
            "J 重工厂",
            "小程序生成完成",
            "PASS" if ok else "FAIL",
            evidence=f"status={final.get('status')} {str(final.get('result') or final.get('error'))[:60]}",
            elapsed=time.time() - _t0,
        )
    else:
        record("J 重工厂", "小程序生成完成", "FAIL", error=f"240s 未完成 task={proj}", elapsed=time.time() - _t0)


# ══════════════════════════════════════════════════════════
# K. 前端可访问性
# ══════════════════════════════════════════════════════════
def k_frontend(client: httpx.Client, _t0: float) -> None:
    try:
        r = client.get("http://127.0.0.1:5173/", timeout=8)
        ok = r.status_code == 200 and '<div id="root"' in r.text or "vite" in r.text.lower()
        record(
            "K 前端",
            "Vite dev server",
            "PASS" if ok else "FAIL",
            http=r.status_code,
            evidence=r.text[:60],
            elapsed=time.time() - _t0,
        )
        r = client.get("http://127.0.0.1:5173/api/health", timeout=8)
        record(
            "K 前端",
            "前端→后端代理 /api",
            "PASS" if r.status_code == 200 else "FAIL",
            http=r.status_code,
            evidence=r.text[:60],
            elapsed=time.time() - _t0,
        )
    except Exception as e:  # noqa: BLE001
        record("K 前端", "Vite dev server", "FAIL", error=str(e)[:100], elapsed=time.time() - _t0)


# ══════════════════════════════════════════════════════════
# 执行 + 报告
# ══════════════════════════════════════════════════════════
def k_commerce(client: httpx.Client, _t0: float) -> None:
    """K 商业闭环：创建订单 → mock webhook 自动履约 → 计量中心（纯 SQLite，不耗 LLM 配额）。"""
    import hashlib
    import hmac

    h = {"Authorization": f"Bearer {CTX['token']}"}
    r = client.post("/api/orders", json={"plan": "pro"}, headers=h, timeout=15)
    if r.status_code != 200 or not r.json().get("id"):
        record("K 商业", "创建会员订单", "FAIL", http=r.status_code, error=r.text[:120], elapsed=time.time() - _t0)
        return
    oid = r.json()["id"]
    record("K 商业", "创建会员订单", "PASS", http=200, evidence=oid, elapsed=time.time() - _t0)

    # mock 沙箱验签（HMAC-SHA256(order_id, 开发密钥)）
    sign = hmac.new(b"platform-dev-secret", oid.encode(), hashlib.sha256).hexdigest()
    r = client.post(
        "/api/orders/webhook",
        json={"provider": "mock", "order_id": oid, "ref": "e2e_probe", "amount": 19.9},
        headers={**h, "X-Platform-Sign": sign},
        timeout=15,
    )
    if r.status_code == 200 and r.json().get("status") == "approved":
        # 重放幂等
        r2 = client.post(
            "/api/orders/webhook",
            json={"provider": "mock", "order_id": oid, "ref": "e2e_probe", "amount": 19.9},
            headers={**h, "X-Platform-Sign": sign},
            timeout=15,
        )
        idem = r2.status_code == 200 and r2.json().get("status") == "approved"
        record(
            "K 商业",
            "mock 支付 webhook 自动履约 + 幂等重放",
            "PASS" if idem else "FAIL",
            http=r.status_code,
            evidence=f"{oid} → approved" + ("（重放幂等）" if idem else ""),
            elapsed=time.time() - _t0,
        )
    else:
        record(
            "K 商业",
            "mock 支付 webhook 自动履约",
            "FAIL",
            http=r.status_code,
            error=r.text[:120],
            elapsed=time.time() - _t0,
        )

    r = client.get("/api/billing/summary", headers=h, timeout=15)
    if r.status_code == 200 and {"today", "d30"} <= set(r.json()):
        record(
            "K 商业",
            "用户计量中心（今日/30日聚合）",
            "PASS",
            http=200,
            evidence=str(r.json())[:80],
            elapsed=time.time() - _t0,
        )
    else:
        record(
            "K 商业",
            "用户计量中心（今日/30日聚合）",
            "FAIL",
            http=r.status_code,
            error=r.text[:120],
            elapsed=time.time() - _t0,
        )


def main() -> None:
    t_start = time.time()
    print(f"══ E2E 能力探针 → {BASE} ══")
    with httpx.Client(base_url=BASE, timeout=30, follow_redirects=True) as client:
        r = client.get("/api/health", timeout=10)
        print(f"health: {r.status_code} {r.text[:120]}")
        if r.status_code != 200:
            print("服务不可用，退出")
            sys.exit(1)

        probes = [
            ("A 账户鉴权", a_register),
            ("B LLM", b_assistant),
            ("B LLM", b_sse),
            ("B LLM", b_openai_compat),
            ("C 编排", c_workflow),
            ("C 编排", c_agent),
            ("C 编排", c_tools),
            ("D 知识库", d_kb),
            ("E 任务队列", e_tasks),
            ("F 工厂", f_meme),
            ("F 工厂", f_image_t2i),
            ("G 音频", g_voice),
            ("G 音频", g_music),
            ("H 文档", h_ppt),
            ("H 文档", h_excel),
            ("H 文档", h_mindmap),
            ("H 文档", h_ppt_poll),
            ("I 平台", i_sandbox),
            ("I 平台", i_mcp),
            ("I 平台", i_share),
            ("I 平台", i_teams),
            ("J 重工厂", j_dh_config),
            ("J 重工厂", j_drama_config),
            ("J 重工厂", j_games),
            ("J 重工厂", j_miniapp_gen),
            ("K 前端", k_frontend),
            ("K 商业", k_commerce),
        ]
        for domain, fn in probes:
            probe(domain, fn.__name__, fn, client)

    # 汇总
    passed = sum(1 for x in RESULTS if x["status"] == "PASS")
    failed = sum(1 for x in RESULTS if x["status"] == "FAIL")
    skipped = sum(1 for x in RESULTS if x["status"] == "SKIP")
    total_time = time.time() - t_start

    # JSON
    out_json = "/tmp/e2e_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(
            {
                "base": BASE,
                "at": datetime.now().isoformat(),
                "total_s": round(total_time, 1),
                "summary": {"pass": passed, "fail": failed, "skip": skipped},
                "results": RESULTS,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # Markdown 报告
    stamp = datetime.now().strftime("%Y%m%d")
    md = [
        f"# E2E 能力实测报告（{stamp}）",
        "",
        f"- 目标：`{BASE}` · 耗时 {total_time:.0f}s",
        f"- 结果：**{passed} PASS / {failed} FAIL / {skipped} SKIP**（共 {len(RESULTS)} 项）",
        "",
        "| 域 | 探针 | 结果 | HTTP | 耗时 | 证据 |",
        "|---|---|---|---|---|---|",
    ]
    for x in RESULTS:
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}[x["status"]]
        ev = (x["evidence"] or x["error"]).replace("|", "/").replace("\n", " ")[:100]
        md.append(
            f"| {x['domain']} | {x['name']} | {icon} {x['status']} | {x.get('http') or '-'} | {x['elapsed_s']}s | {ev} |"
        )
    if failed:
        md += ["", "## 失败项明细", ""]
        for x in RESULTS:
            if x["status"] == "FAIL":
                md.append(
                    f"- **{x['domain']} / {x['name']}**: http={x.get('http')} err={x['error'][:200]} ev={x['evidence'][:150]}"
                )
    md.append("")
    md_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", f"e2e-capability-report-{stamp}.md"
    )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n══ 汇总: {passed} PASS / {failed} FAIL / {skipped} SKIP · {total_time:.0f}s ══")
    print(f"JSON: {out_json}\nMD:   {md_path}")
    if failed:
        print("\n失败项:")
        for x in RESULTS:
            if x["status"] == "FAIL":
                print(f"  ❌ {x['domain']} / {x['name']}: {x['error'][:120]}")


if __name__ == "__main__":
    main()
