#!/usr/bin/env python3
"""v12.0 升级冒烟测试：流式端点 / 可观测性 / OpenAI 网关。"""
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8888"
API_KEY = open("/tmp/v12_apikey.txt").read().strip()
results = []


def http(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:
        return -1, str(e).encode(), {}


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  {detail}" if detail and not ok else ""))


def parse_sse(data):  # noqa: C901 — 事件解析分支多，复杂度可控
    """解析 SSE 响应，返回 (events, full_text)。兼容 event: 行 + data: JSON 行格式。"""
    events, full, cur_event = [], "", None
    for line in data.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("event:"):
            cur_event = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        ev = cur_event
        try:
            obj = json.loads(payload)
            ev = obj.get("event") or obj.get("type") or obj.get("event_type") or ev or "?"
        except json.JSONDecodeError:
            pass
        if ev:
            events.append(ev)
        if ev in ("delta", "message", "content"):
            try:
                full += obj.get("delta") or obj.get("content") or obj.get("text") or ""
            except NameError:
                pass
        elif ev == "done":
            try:
                full += obj.get("result") or obj.get("full_text") or ""
            except NameError:
                pass
    return events, full


def main():  # noqa: C901 — 多组断言场景，复杂度可控
    print("=== 1. 可观测性 ===")
    code, body, _ = http("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
    token = json.loads(body)["access_token"] if code == 200 else ""
    check("登录 admin", code == 200)

    code, body, hdrs = http("GET", "/api/health")
    h = json.loads(body)
    check("health 200 + 四维探活", code == 200 and h.get("db") == "ok" and "llm" in h and "disk_free_gb" in h and "uptime_seconds" in h, str(h))

    code, body, hdrs = http("GET", "/api/ops/stats", token)
    rid = hdrs.get("X-Request-ID") or hdrs.get("x-request-id") or ""
    check("X-Request-ID 注入", code == 200 and rid.startswith("req_"), f"rid={rid}")
    st = json.loads(body)
    check("ops/stats 指标字段", code == 200 and ("requests_total" in st) and ("errors_total" in st) and ("llm" in st or "llm_calls" in st), str(st)[:200])

    code, body, hdrs = http("GET", "/api/nonexistent-xyz", token)
    check("404 JSON 结构", code == 404, body[:100].decode(errors="replace"))

    print("=== 2. prd_engine 流式端点（SSE） ===")
    prd_cases = [
        ("/api/prd/generate", {"prd_text": "做一个待办事项管理工具，支持增删改查", "stream": True}),
        ("/api/prd/review", {"prd_text": "# PRD\n## 功能\n1. 用户注册登录", "stream": True}),
        ("/api/prd/technical-design", {"prd_text": "# PRD\n用户管理系统", "stream": True}),
        ("/api/prd/test-cases", {"prd_text": "# PRD\n用户注册", "stream": True}),
        ("/api/prd/generate-code", {"tech_design": "# 技术方案\nREST API", "language": "python", "stream": True}),
    ]
    for path, payload in prd_cases:
        code, body, hdrs = http("POST", path, body=payload)
        events, full = parse_sse(body)
        ok = code == 200 and "delta" in events and "done" in events and len(full) > 10
        check(f"POST {path} SSE", ok, f"code={code} events={set(events)} len={len(full)}")

    print("=== 3. chat_engine 流式端点 ===")
    code, body, hdrs = http("POST", "/api/agents/agent-1/run/stream", body={"message": "你好，用一句话介绍自己"})
    events, full = parse_sse(body)
    check("POST /api/agents/{id}/run/stream SSE", code == 200 and "delta" in events and "done" in events and len(full) > 5, f"code={code} events={set(events)} len={len(full)}")

    # 创建会话后测 messages stream
    code, body, hdrs = http("POST", "/api/agents/agent-1/conversations", body={"title": "smoke-v12"})
    conv_id = ""
    if code == 200:
        conv_id = json.loads(body).get("conversation_id") or json.loads(body).get("id") or ""
    code, body, hdrs = http("POST", f"/api/conversations/{conv_id}/messages", body={"content": "你好", "stream": True}) if conv_id else (0, b"", {})
    events, full = parse_sse(body)
    check("POST /api/conversations/{id}/messages stream", code == 200 and "delta" in events and "done" in events, f"code={code} events={set(events)} len={len(full)}")

    print("=== 4. extended_api /api/code/review 流式 ===")
    code, body, hdrs = http("POST", "/api/code/review", token=token, body={"code": "def f():\n    return 1", "language": "python", "stream": True})
    events, full = parse_sse(body)
    check("/api/code/review SSE", code == 200 and "delta" in events and "done" in events and len(full) > 10, f"code={code} events={set(events)} len={len(full)}")

    print("=== 5. OpenAI 兼容网关 ===")
    code, body, hdrs = http("GET", "/v1/models")
    models = json.loads(body) if code == 200 else {}
    check("GET /v1/models", code == 200 and models.get("object") == "list" and len(models.get("data", [])) > 0)

    code, body, hdrs = http("POST", "/v1/chat/completions", body={"messages": [{"role": "user", "content": "hi"}]})
    err = json.loads(body).get("error", {}) if code == 401 else {}
    check("无 Key 401 OpenAI 风格", code == 401 and err.get("code") == "invalid_api_key", f"body={body[:120]!r}")

    code, body, hdrs = http("POST", "/v1/chat/completions", token=API_KEY, body={"model": "agnes-2.5-flash", "messages": [{"role": "user", "content": "用一句话介绍你自己"}], "max_tokens": 100})
    if code == 200:
        d = json.loads(body)
        content = d["choices"][0]["message"]["content"]
        check("POST /v1/chat/completions 非流式", bool(content), f"len={len(content)}")
    else:
        check("POST /v1/chat/completions 非流式", False, f"code={code} body={body[:200]!r}")

    code, body, hdrs = http("POST", "/v1/chat/completions", token=API_KEY, body={"model": "agnes-2.5-flash", "messages": [{"role": "user", "content": "数到三"}], "stream": True, "max_tokens": 50})
    if code == 200:
        chunks, full = 0, ""
        for line in body.decode("utf-8", "replace").splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
                d = obj["choices"][0]["delta"].get("content", "")
                if d:
                    chunks += 1
                    full += d
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                pass
        check("POST /v1/chat/completions 流式", chunks > 0 and bool(full), f"chunks={chunks} len={len(full)}")
    else:
        check("POST /v1/chat/completions 流式", False, f"code={code} body={body[:200]!r}")

    code, body, hdrs = http("POST", "/api/chat/completions", token=API_KEY, body={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 10})
    check("POST /api/chat/completions 别名", code == 200, f"code={code}")

    code, body, hdrs = http("POST", "/v1/chat/completions", token=API_KEY, body={"messages": [{"role": "user", "content": "记住数字 42"}, {"role": "assistant", "content": "好的"}, {"role": "user", "content": "刚才的数字是什么？"}], "max_tokens": 50})
    if code == 200:
        content = json.loads(body)["choices"][0]["message"]["content"]
        check("多轮 messages 上下文", bool(content), f"len={len(content)}")
    else:
        check("多轮 messages 上下文", False, f"code={code} body={body[:200]!r}")

    print("\n=== 汇总 ===")
    passed = sum(1 for _, ok, _ in results if ok)
    failed = [(n, d) for n, ok, d in results if not ok]
    print(f"PASS {passed}/{len(results)}  FAIL {len(failed)}")
    for n, d in failed:
        print(f"  x {n}: {d}")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
