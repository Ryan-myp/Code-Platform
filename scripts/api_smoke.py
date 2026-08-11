#!/usr/bin/env python3
"""批量接口冒烟测试：遍历 OpenAPI 全部接口，GET 直接调，记录 5xx 错误。"""
import json
import re
import urllib.request

BASE = "http://127.0.0.1:8888"

def http(method, path, token=None, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode()

def main():  # noqa: C901
    spec = json.loads(urllib.request.urlopen(BASE + "/openapi.json").read())
    # 登录
    code, body = http("POST", "/api/auth/login", body={"username": "admin", "password": "admin123"})
    token = ""
    if code == 200:
        token = json.loads(body)["access_token"]
        print("[登录] admin OK")
    else:
        print(f"[登录] 失败: {code}")
        return

    results = {"ok": [], "skip": [], "fail": [], "errors": []}
    sample_ids = {
        "avatar_id": "tech-female", "voice_id": "zh-CN-XiaoxiaoNeural",
        "background_id": "tech", "record_id": "dh_7b4f3499fac7",
        "share_code": "test", "tool_id": "web-search",
        "workflow_id": "wf_demo", "agent_id": "agent_demo",
        "kb_id": "kb_demo", "team_id": "team_demo", "server_id": "srv_demo",
        "skill_id": "skill_demo", "pid": "proj_demo", "proj_id": "proj_demo",
        "filename": "test.mp3", "order_id": "order_demo",
        "session_id": "sess_demo", "series_id": "ser_demo",
        "template_name": "architect_agent", "task_id": "task_demo",
        "coupon_id": "cp_demo", "plan_id": "plan_demo",
    }

    for path, methods in spec["paths"].items():
        for method, _info in methods.items():
            if method not in ("get", "delete"):
                continue
            test_path = path
            skip = False
            for m in re.finditer(r"\{(\w+)\}", path):
                name = m.group(1)
                if name in sample_ids:
                    test_path = test_path.replace("{" + name + "}", sample_ids[name])
                else:
                    skip = True
            if skip:
                results["skip"].append(f"{method.upper()} {path}")
                continue
            code, body = http(method.upper(), test_path, token)
            if code == 200:
                results["ok"].append(f"{method.upper()} {path}")
            elif code == 404:
                results["ok"].append(f"{method.upper()} {path} (404-资源不存在属正常)")
            elif 400 <= code < 500:
                results["skip"].append(f"{method.upper()} {path} ({code})")
            else:
                results["fail"].append(f"{method.upper()} {path} → {code}: {body[:100]}")
                results["errors"].append((method.upper(), path, code, body[:150]))

    print("\n=== 结果汇总 ===")
    print(f"成功(200/404): {len(results['ok'])}")
    print(f"跳过(需参数/4xx): {len(results['skip'])}")
    print(f"失败(5xx/异常): {len(results['fail'])}")
    if results["fail"]:
        print("\n=== 失败接口明细 ===")
        for e in results["errors"]:
            print(f"  {e[0]} {e[1]} → {e[2]}: {e[3].decode(errors='replace')[:120]}")

    with open("/tmp/smoke_result.json", "w") as f:
        json.dump({"ok": results["ok"], "fail": results["fail"], "skip": results["skip"]}, f, ensure_ascii=False, indent=1)
    print("\n明细已保存 /tmp/smoke_result.json")

if __name__ == "__main__":
    main()
