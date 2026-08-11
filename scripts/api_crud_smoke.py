#!/usr/bin/env python3
"""核心业务 POST/PUT 接口闭环验证：创建→查询→更新→删除。"""
import json
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8888"
results = []


def http(method, path, token=None, body=None, timeout=90):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def http_upload(path, token, file_path, fields=None, timeout=90):
    """multipart/form-data 上传：图片编辑接口契约（UploadFile + Form）。"""
    boundary = uuid.uuid4().hex
    parts = []
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
        f"filename=\"{file_path.rsplit('/', 1)[-1]}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode()
        + file_bytes
        + b"\r\n"
    )
    for k, v in (fields or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        )
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  {'✓' if ok else '✗'} {name}" + (f"  [{detail[:120]}]" if detail else ""))


def main():
    code, body = http("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
    token = json.loads(body)["access_token"]

    # ── 1. Agent CRUD ──
    print("\n== Agent ==")
    c, b = http("POST", "/api/agents", token, {"name": "冒烟测试Agent", "system_prompt": "你是测试助手", "model_name": "agnes-2.5-flash"})
    check("创建 Agent", c == 200, str(c))
    agent_id = ""
    if c == 200:
        agent_id = json.loads(b).get("id", "")
    c, b = http("PUT", f"/api/agents/{agent_id}", token, {"name": "冒烟测试Agent-改", "system_prompt": "你是测试助手v2"})
    check("更新 Agent", c == 200, str(c))
    c, _ = http("DELETE", f"/api/agents/{agent_id}", token)
    check("删除 Agent", c == 200, str(c))

    # ── 2. Workflow CRUD ──
    print("\n== Workflow ==")
    c, b = http("POST", "/api/workflows", token, {"name": "冒烟测试流程", "description": "测试", "nodes": [], "edges": []})
    check("创建 Workflow", c == 200, str(c))
    wf_id = ""
    if c == 200:
        wf_id = json.loads(b).get("id", "")
    c, _ = http("PUT", f"/api/workflows/{wf_id}", token, {"name": "冒烟测试流程-改", "nodes": [], "edges": []})
    check("更新 Workflow", c == 200, str(c))
    c, _ = http("DELETE", f"/api/workflows/{wf_id}", token)
    check("删除 Workflow", c == 200, str(c))

    # ── 3. Team CRUD ──
    print("\n== Team ==")
    c, b = http("POST", "/api/teams", token, {"name": "冒烟测试团队", "description": "测试"})
    check("创建 Team", c == 200, str(c))
    team_id = ""
    if c == 200:
        team_id = json.loads(b).get("id", "")
    c, _ = http("PUT", f"/api/teams/{team_id}", token, {"name": "冒烟测试团队-改"})
    check("更新 Team", c == 200, str(c))
    c, _ = http("DELETE", f"/api/teams/{team_id}", token)
    check("删除 Team", c == 200, str(c))

    # ── 4. Skill CRUD ──
    print("\n== Skill ==")
    c, b = http("POST", "/api/skills", token, {"name": "冒烟测试技能", "description": "测试技能", "content": "这是一个测试技能"})
    check("创建 Skill", c == 200, str(c))
    skill_id = ""
    if c == 200:
        skill_id = json.loads(b).get("id", "")
    c, _ = http("PUT", f"/api/skills/{skill_id}", token, {"name": "冒烟测试技能-改", "description": "测试技能v2", "content": "v2"})
    check("更新 Skill", c == 200, str(c))
    c, _ = http("DELETE", f"/api/skills/{skill_id}", token)
    check("删除 Skill", c == 200, str(c))

    # ── 5. Knowledge Base CRUD ──
    print("\n== Knowledge Base ==")
    c, b = http("POST", "/api/knowledge-bases", token, {"name": "冒烟测试知识库", "description": "测试", "provider": "local"})
    check("创建 KB", c == 200, str(c))
    kb_id = ""
    if c == 200:
        kb_id = json.loads(b).get("id", "")
    c, _ = http("PUT", f"/api/knowledge-bases/{kb_id}", token, {"name": "冒烟测试知识库-改", "description": "v2", "provider": "local"})
    check("更新 KB", c == 200, str(c))
    c, _ = http("DELETE", f"/api/knowledge-bases/{kb_id}", token)
    check("删除 KB", c == 200, str(c))

    # ── 6. MCP Server CRUD ──
    print("\n== MCP Server ==")
    c, b = http("POST", "/api/mcp-servers", token, {"name": "冒烟测试MCP", "server_type": "http", "command": "", "url": "http://localhost:9999"})
    check("创建 MCP Server", c == 200, str(c))
    srv_id = ""
    if c == 200:
        srv_id = json.loads(b).get("id", "")
    c, _ = http("PUT", f"/api/mcp-servers/{srv_id}", token, {"name": "冒烟测试MCP-改", "server_type": "http", "command": "", "url": "http://localhost:9999"})
    check("更新 MCP Server", c == 200, str(c))
    c, _ = http("DELETE", f"/api/mcp-servers/{srv_id}", token)
    check("删除 MCP Server", c == 200, str(c))

    # ── 7. 图片编辑（本地处理链路，multipart 契约）──
    print("\n== 图片工厂编辑 ==")
    test_img = "/tmp/img_smoke.png"
    # 先准备一张测试图
    try:
        from PIL import Image
        Image.new("RGB", (200, 150), "#667eea").save(test_img)
    except Exception:
        pass
    import os
    if os.path.exists(test_img):
        c, _ = http_upload("/api/image-factory/edit/resize", token, test_img, {"width": "100", "height": "100", "maintain_aspect": "false"})
        check("resize", c == 200, str(c))
        c, _ = http_upload("/api/image-factory/edit/rotate", token, test_img, {"degrees": "45"})
        check("rotate", c == 200, str(c))
        c, _ = http_upload("/api/image-factory/edit/blur", token, test_img, {"radius": "3"})
        check("blur", c == 200, str(c))
        c, _ = http_upload("/api/image-factory/edit/filter", token, test_img, {"filter": "grayscale"})
        check("filter(grayscale)", c == 200, str(c))
    else:
        check("图片编辑(跳过-无PIL)", False)

    # ── 8. 轻量AI工具（LLM链路）──
    print("\n== AI工具（LLM链路） ==")
    c, b = http("POST", "/api/mindmap/generate", token, {"topic": "人工智能学习路线", "style": "professional", "depth": 2}, timeout=120)
    check("思维导图生成", c == 200, str(c))
    c, b = http("POST", "/api/batch/translate", token, {"texts": ["你好世界", "Good morning"], "target": "en", "source": "zh"}, timeout=120)
    check("批量翻译", c == 200, str(c))

    # ── 9. 账号/资料 ──
    print("\n== 账号 ==")
    c, _ = http("GET", "/api/auth/me", token)
    check("获取用户信息", c == 200, str(c))
    c, _ = http("GET", "/api/auth/quota", token)
    check("获取配额", c == 200, str(c))

    # ── 10. 搜索/通知 ──
    print("\n== 其他 ==")
    c, _ = http("POST", "/api/search/global", token, {"query": "测试", "types": ["requirements", "tools", "docs", "history"]})
    check("全平台搜索", c == 200, str(c))
    c, _ = http("GET", "/api/notifications", token)
    check("通知列表", c == 200, str(c))

    fails = [r for r in results if not r[1]]
    print(f"\n=== POST/PUT 闭环验证完成: 共{len(results)}项, 失败{len(fails)}项 ===")
    for f in fails:
        print(f"  ✗ {f[0]}: {f[2]}")
    return 1 if fails else 0

if __name__ == "__main__":
    raise SystemExit(main())
