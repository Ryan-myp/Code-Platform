"""MCP 执行链路 v3：绑定 MCP Server 的 Agent 三层（单 Agent / Team / Workflow）真实调用外部工具。

测试用真实 stdio MCP Server（子进程 JSON-RPC 握手），不 mock 传输层：
- mcp_list_tools / mcp_call_tool 真实握手往返
- execute_tool_loop 的 [MCP:] 指令解析 + 白名单过滤 + 剥离
- load_agent_bundle 挂接 + 指令剥离（TOOL/MCP 双协议）
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "backend"))

MCP_SERVER_SCRIPT = r"""
import json, sys

def main():
    reqs = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        reqs.append(json.loads(line))
        if len(reqs) >= 3:
            break
    for r in reqs:
        if r.get("method") == "tools/list":
            print(json.dumps({"jsonrpc": "2.0", "id": r.get("id"), "result": {"tools": [
                {"name": "echo_up", "description": "把输入大写返回", "inputSchema": {"type": "object"}},
            ]}}))
        elif r.get("method") == "tools/call":
            args = (r.get("params") or {}).get("arguments") or {}
            text = str(args.get("word", "")).upper()
            print(json.dumps({"jsonrpc": "2.0", "id": r.get("id"), "result": {"content": [
                {"type": "text", "text": f"UP:{text}"}
            ]}}))

main()
"""


def _start_mcp_server(tmp_path: Path) -> str:
    """写一个真实的 stdio MCP Server 脚本，返回命令。"""
    script = tmp_path / "fake_mcp_server.py"
    script.write_text(textwrap.dedent(MCP_SERVER_SCRIPT), encoding="utf-8")
    return f"{sys.executable} {script}"


# ══════════════════════════════════════════════════════════════
# mcp_client 真实握手
# ══════════════════════════════════════════════════════════════

class TestMcpClient:
    def test_list_tools_and_call_round_trip(self, tmp_path):
        import asyncio
        import mcp_client

        cmd = _start_mcp_server(tmp_path)
        server = {"id": "mcp_test_1", "name": "测试MCP", "transport_type": "stdio", "command": cmd,
                  "args": "[]", "env": "{}", "auth_type": "none", "auth_config": "{}"}

        tools = asyncio.new_event_loop().run_until_complete(mcp_client.mcp_list_tools(server))
        assert [t["name"] for t in tools] == ["echo_up"]

        out = asyncio.new_event_loop().run_until_complete(
            mcp_client.mcp_call_tool(server, "echo_up", {"word": "hello"})
        )
        assert "UP:HELLO" in out

    def test_missing_command_degrades_honestly(self):
        import asyncio
        import mcp_client

        server = {"id": "mcp_x", "name": "坏配置", "transport_type": "stdio", "command": "",
                  "args": "[]", "env": "{}"}
        tools = asyncio.new_event_loop().run_until_complete(mcp_client.mcp_list_tools(server))
        assert tools == []
        out = asyncio.new_event_loop().run_until_complete(mcp_client.mcp_call_tool(server, "t", {}))
        assert "调用不可用" in out or "无响应" in out


# ══════════════════════════════════════════════════════════════
# 指令协议解析
# ══════════════════════════════════════════════════════════════

class TestMcpDirectives:
    def test_parse_and_whitelist(self):
        import mcp_client

        text = "好\n[MCP:mcp_a|echo_up|{\"word\": \"hi\"}]\n[MCP:mcp_b|nope|{}]\n[MCP:mcp_c|x|]"
        out = mcp_client.parse_mcp_directives(text, {"mcp_a"})
        assert out == [("mcp_a", "echo_up", {"word": "hi"})]

    def test_invalid_json_args_fallback(self):
        import mcp_client

        out = mcp_client.parse_mcp_directives("[MCP:mcp_a|echo_up|not-json]", {"mcp_a"})
        assert out == [("mcp_a", "echo_up", {"input": "not-json"})]

    def test_short_format_via_tool_map(self):
        """[MCP:工具名|json] 短式：经 mcp_tools 映射到绑定 server。"""
        import mcp_client

        out = mcp_client.parse_mcp_directives(
            "[MCP:echo_up|{\"word\": \"hi\"}]", {"mcp_a", "mcp_b"}, {"echo_up": "mcp_a"}
        )
        assert out == [("mcp_a", "echo_up", {"word": "hi"})]

    def test_short_format_unbound_tool_ignored(self):
        import mcp_client

        out = mcp_client.parse_mcp_directives("[MCP:ghost|{}]", {"mcp_a"}, {"echo_up": "mcp_a"})
        assert out == []

    def test_strip_mixed_directives(self):
        import agent_runtime

        text = "答案：\n[TOOL:code_interpreter|print(1)]\n[MCP:mcp_a|echo_up|{}]"
        clean = agent_runtime.strip_tool_directives(text)
        assert "答案：" in clean
        assert "TOOL:" not in clean and "MCP:" not in clean

    def test_short_format_is_stripped_from_user_answer(self):
        """P1 回归：系统提示词教 LLM 输出两段式 [MCP:工具名|参数]，strip 必须剥干净，不得泄漏进用户答案。"""
        import agent_runtime

        text = '最终答案：HELLO\n[MCP:echo_up|{"word": "hi"}]'
        clean = agent_runtime.strip_tool_directives(text)
        assert "最终答案：HELLO" in clean
        assert "MCP:" not in clean

    def test_unknown_tool_directive_stripped_not_executed(self):
        """未知工具的 [MCP:] 指令不执行，且从展示文本中剥除（协议块不泄漏）。"""
        import agent_runtime

        out = agent_runtime.strip_tool_directives("done\n[MCP:ghost|{}]")
        assert "MCP:" not in out and "done" in out

    def test_short_format_empty_args(self):
        import mcp_client

        out = mcp_client.parse_mcp_directives("[MCP:echo_up|]", {"mcp_a"}, {"echo_up": "mcp_a"})
        assert out == [("mcp_a", "echo_up", {})]

    def test_short_format_collects_up_to_two(self):
        """短式多条指令：最多收集 2 条（与提示词“最多 2 个”一致）。"""
        import mcp_client

        text = '[MCP:echo_up|{"a": 1}]\n[MCP:other_tool|{}]\n[MCP:third|{}]'
        out = mcp_client.parse_mcp_directives(
            text, {"mcp_a", "mcp_b"}, {"echo_up": "mcp_a", "other_tool": "mcp_b", "third": "mcp_a"}
        )
        assert out == [("mcp_a", "echo_up", {"a": 1}), ("mcp_b", "other_tool", {})]

    def test_exec_loop_with_mcp_call(self, tmp_path):
        """execute_tool_loop：LLM 发 [MCP:] 指令 → 真实调用 stdio server → 回喂。"""
        import agent_runtime
        import asyncio

        cmd = _start_mcp_server(tmp_path)
        server = {"id": "mcp_test_2", "name": "测试MCP", "transport_type": "stdio", "command": cmd,
                  "args": "[]", "env": "{}"}

        async def fake_llm(system, prompt, **kw):
            if "MCP echo_up 执行结果" in prompt:
                return "大写结果是 HELLO"
            return "调用 [MCP:mcp_test_2|echo_up|{\"word\": \"hello\"}]"

        out = asyncio.new_event_loop().run_until_complete(
            agent_runtime.execute_tool_loop(
                "sys",
                "把 hello 大写",
                set(),
                mcp_servers=[server],
                llm_call=fake_llm,
            )
        )
        assert out["mcp_calls"] == ["mcp_test_2:echo_up"]
        assert "HELLO" in out["result"]
        assert "[MCP:" not in out["result"]

    def test_unbound_server_directive_ignored(self):
        """白名单外的 MCP Server 指令必须被忽略（不执行、不泄露）。"""
        import agent_runtime
        import asyncio

        async def fake_llm(system, prompt, **kw):
            return "结果 [MCP:unknown_server|evil|{}]"

        out = asyncio.new_event_loop().run_until_complete(
            agent_runtime.execute_tool_loop("sys", "任务", set(), mcp_servers=[], llm_call=fake_llm)
        )
        assert out["mcp_calls"] == []
        assert "[MCP:" not in out["result"]


# ══════════════════════════════════════════════════════════════
# SSRF 防护 + HTTP 工具清单缓存
# ══════════════════════════════════════════════════════════════

class TestMcpHttpGuardAndCache:
    @staticmethod
    def _guard(url: str) -> str:
        import mcp_client

        return mcp_client._http_target_guard(url)

    def test_metadata_address_blocked(self):
        assert "元数据" in self._guard("http://169.254.169.254/latest/meta-data/")

    def test_scheme_whitelist(self):
        assert "http/https" in self._guard("ftp://example.com/x")
        assert self._guard("http://127.0.0.1:9000") == ""  # loopback 放行（本地自托管）

    def test_call_tool_blocks_metadata_url_without_connecting(self):
        """元数据地址在发请求前就被拦截（不会真连云内网）。"""
        import asyncio
        import mcp_client

        server = {"id": "mcp_ssrf", "name": "ssrf", "transport_type": "http",
                  "url": "http://169.254.169.254/mcp", "auth_type": "none", "auth_config": "{}"}
        out = asyncio.new_event_loop().run_until_complete(mcp_client.mcp_call_tool(server, "t", {}))
        assert "元数据" in out

    def test_http_list_tools_cached(self):
        """真实本地 HTTP JSON-RPC server：第二次 list 命中缓存，不再发 tools/list 请求。"""
        import asyncio
        import json as _json
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        import mcp_client

        counters = {"tools_list": 0}

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8")
                if "tools/list" in body:
                    counters["tools_list"] += 1
                    payload = {"jsonrpc": "2.0", "id": 2, "result": {"tools": [
                        {"name": "http_echo", "description": "d", "inputSchema": {"type": "object"}},
                    ]}}
                else:
                    payload = {"jsonrpc": "2.0", "id": 1, "result": {}}
                data = _json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            mcp = {"id": "mcp_cache_test", "name": "cache", "transport_type": "http",
                   "url": f"http://127.0.0.1:{httpd.server_address[1]}/mcp",
                   "auth_type": "none", "auth_config": "{}"}
            loop = asyncio.new_event_loop()
            first = loop.run_until_complete(mcp_client.mcp_list_tools(mcp))
            second = loop.run_until_complete(mcp_client.mcp_list_tools(mcp))
            assert [x["name"] for x in first] == ["http_echo"]
            assert second == first
            assert counters["tools_list"] == 1, "第二次应命中缓存，不再发 tools/list"
        finally:
            httpd.shutdown()


# ══════════════════════════════════════════════════════════════
# bundle 挂接：agent 绑定 mcp_server_ids
# ══════════════════════════════════════════════════════════════

class TestAgentMcpBundle:
    def test_bundle_loads_enabled_mcp_servers(self, tmp_path):
        """API 建的 MCP Server 进 bundle；disabled 的排除。"""
        from fastapi.testclient import TestClient

        from main import app

        c = TestClient(app)
        token = c.post("/api/auth/login", json={"username": "admin", "password": "admin123"}).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        r = c.post("/api/mcp-servers", headers=h, json={
            "name": "bundle-mcp", "transport_type": "stdio",
            "command": f"{sys.executable} {tmp_path / 'no_such.py'}", "url": "",
        })
        assert r.status_code == 200, r.text
        mcp_id = r.json()["id"]

        # Agent 绑定 enabled + disabled 两个
        r2 = c.post("/api/mcp-servers", headers=h, json={
            "name": "disabled-mcp", "transport_type": "stdio", "command": "x", "url": "", "enabled": False,
        })
        mcp_off = r2.json()["id"]

        r3 = c.post("/api/agents", headers=h, json={
            "name": "MCP Agent", "description": "", "instructions": "x", "model": "agnes-3.0-flash",
            "tools": [], "knowledge_base_ids": [], "skill_ids": [],
            "mcp_server_ids": [mcp_id, mcp_off],
        })
        assert r3.status_code == 200, r3.text
        agent_id = r3.json()["id"]

        import agent_runtime

        bundle = agent_runtime.load_agent_bundle(agent_id, "hi")
        # 只挂 enabled 的
        assert bundle["mcp_server_ids"] == [mcp_id]
        assert len(bundle["mcp_servers"]) == 1
