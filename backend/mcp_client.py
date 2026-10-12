"""MCP 工具调用客户端：把绑定的 MCP Server 接进 Agent 执行链路。

历史短板：Agent 可绑定 MCP Server，但执行引擎从未调用过它们（只有测试连接）。
本模块提供：

- mcp_list_tools(server)：真实 tools/list（stdio 子进程 / HTTP+SSE JSON-RPC）
- mcp_call_tool(server, tool_name, arguments)：真实 tools/call，返回文本结果

所有函数失败时返回诚实降级值（空列表 / 降级说明字符串），绝不抛异常阻断
Agent 执行；15s 超时兜底；stdio 子进程始终清理，绝不残留。
"""

import json
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

_TIMEOUT = 15


def _parse_sse_maybe(text: str):
    """兼容纯 JSON 与 SSE（data: {...} 行）响应。"""
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("data:") and line[5:].strip():
            try:
                return json.loads(line[5:].strip())
            except ValueError:
                continue
    return None


def _server_args(server: dict) -> tuple[list, dict]:
    """解析 args/env（可能是 JSON 字符串）。"""
    try:
        args = json.loads(server.get("args") or "[]") or []
    except (ValueError, TypeError):
        args = []
    try:
        extra_env = json.loads(server.get("env") or "{}") or {}
    except (ValueError, TypeError):
        extra_env = {}
    env = {**os.environ, **extra_env}
    return [str(a) for a in args] if isinstance(args, list) else [], env


def _stdio_rpc(server: dict, method: str, params: dict, is_notification: bool = False) -> dict | None:
    """stdio 传输：启动子进程 → initialize(+initialized) 握手 → 目标请求。"""
    cmd = (server.get("command") or "").strip()
    if not cmd:
        return None
    args, env = _server_args(server)
    reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "xiaotuan", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    ]
    if is_notification:
        reqs.append({"jsonrpc": "2.0", "method": method})
    else:
        reqs.append({"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}})
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in reqs)

    import shutil

    proc = None
    cmd_parts = cmd.split()
    prog = cmd_parts[0]
    if not (shutil.which(prog) or os.path.exists(prog)):
        return None
    try:
        proc = subprocess.Popen(
            [*cmd_parts, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        out, err = proc.communicate(input=payload, timeout=_TIMEOUT)
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        logger.warning(f"mcp stdio timeout: {cmd}")
        return None
    except Exception as e:
        logger.warning(f"mcp stdio launch failed: {e}")
        return None
    finally:
        if proc and proc.poll() is None:
            proc.kill()

    if is_notification:
        return None
    for line in (out or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if msg.get("id") == 2:
            return msg
    return None


async def mcp_list_tools(server: dict) -> list[dict]:
    """真实 tools/list。失败返回 []（由调用方决定降级文案）。"""
    import asyncio

    transport = (server.get("transport_type") or "stdio").lower()
    if "http" in transport or "sse" in transport or transport == "streamable":
        url = (server.get("url") or "").strip()
        if not url:
            return []
        from mcp_api import _mcp_auth_headers

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **_mcp_auth_headers(server.get("auth_type") or "none", json.loads(server.get("auth_config") or "{}")),
        }
        try:
            import httpx

            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "xiaotuan", "version": "1.0"},
                        },
                    },
                )
                session_id = resp.headers.get("Mcp-Session-Id", "")
                if session_id:
                    headers["Mcp-Session-Id"] = session_id
                resp = await client.post(
                    url,
                    headers=headers,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
                data = _parse_sse_maybe(resp.text) or {}
        except Exception as e:
            logger.warning(f"mcp http list_tools failed: {e}")
            return []
        result = (data.get("result") or {}) if isinstance(data, dict) else {}
        tools = result.get("tools") if isinstance(result, dict) else None
        return [t for t in (tools or []) if isinstance(t, dict) and t.get("name")]
    else:
        msg = await asyncio.to_thread(_stdio_rpc, server, "tools/list", {})
        result = (msg or {}).get("result") or {}
        tools = result.get("tools") if isinstance(result, dict) else None
        return [t for t in (tools or []) if isinstance(t, dict) and t.get("name")]


async def mcp_call_tool(server: dict, tool_name: str, arguments: dict) -> str:
    """真实 tools/call。返回结果文本；失败返回诚实降级说明，不抛异常。"""
    import asyncio

    transport = (server.get("transport_type") or "stdio").lower()
    try:
        if "http" in transport or "sse" in transport or transport == "streamable":
            url = (server.get("url") or "").strip()
            if not url:
                return f"MCP Server「{server.get('name')}」未配置 URL，调用不可用。"
            from mcp_api import _mcp_auth_headers

            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **_mcp_auth_headers(server.get("auth_type") or "none", json.loads(server.get("auth_config") or "{}")),
            }
            import httpx

            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "xiaotuan", "version": "1.0"},
                        },
                    },
                )
                session_id = resp.headers.get("Mcp-Session-Id", "")
                if session_id:
                    headers["Mcp-Session-Id"] = session_id
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {"name": tool_name, "arguments": arguments or {}},
                    },
                )
                data = _parse_sse_maybe(resp.text) or {}
            return _format_mcp_result(server, tool_name, data)
        else:
            msg = await asyncio.to_thread(_stdio_rpc, server, "tools/call", {"name": tool_name, "arguments": arguments or {}})
            if not msg:
                return f"MCP Server「{server.get('name')}」stdio 调用无响应（命令不可用或超时），请检查配置。"
            return _format_mcp_result(server, tool_name, msg)
    except Exception as e:
        return f"MCP 调用异常：{str(e)[:200]}"


def _format_mcp_result(server: dict, tool_name: str, rpc_msg: dict | None) -> str:
    """从 JSON-RPC 响应提取工具结果文本（content[] → text 拼接）。"""
    if not rpc_msg:
        return f"MCP Server「{server.get('name')}」调用 {tool_name} 无响应。"
    if rpc_msg.get("error"):
        return f"MCP 调用 {tool_name} 失败：{json.dumps(rpc_msg['error'], ensure_ascii=False)[:300]}"
    result = rpc_msg.get("result") or {}
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                parts.append(str(c["text"]))
        if parts:
            text = "\n".join(parts)
            if isinstance(result, dict) and result.get("isError"):
                return f"MCP 工具 {tool_name} 报告错误：{text[:500]}"
            return f"MCP「{server.get('name')}」工具 {tool_name} 执行结果：\n{text[:3000]}"
    if result:
        return f"MCP 工具 {tool_name} 执行结果：{json.dumps(result, ensure_ascii=False)[:1500]}"
    return f"MCP 工具 {tool_name} 执行完成（无文本输出）。"


# ── 指令协议解析（Agent 系统提示词约定的调用格式）─────────────────────
# 同一正则匹配两种格式（strip 与 parse 共用，保证能解析的都能剥干净）：
#   完整：[MCP:server_id|tool_name|json-args]（group3 非 None）
#   短式：[MCP:tool_name|json-args]（group3 为 None，经 tools_map 映射）
_MCP_DIRECTIVE_RE = re.compile(r"\[MCP:([^\]\|]+)\|([^\]\|]*)(?:\|([^\[\]]*))?\]")


def parse_mcp_directives(text: str, mcp_server_ids: set[str], mcp_tools: dict[str, str] | None = None) -> list[tuple[str, str, dict]]:
    """解析 MCP 调用指令（两种格式，仅保留绑定内的工具）：

    - 完整：[MCP:server_id|tool_name|json-args]
    - 短式：[MCP:tool_name|json-args]（经 mcp_tools 工具名→server_id 映射）

    返回 [(server_id, tool, args)]，最多 2 条。
    """
    tools_map = mcp_tools or {}
    out: list[tuple[str, str, dict]] = []

    def _args(raw: str) -> dict:
        try:
            v = json.loads((raw or "{}").strip())
            return v if isinstance(v, dict) else {"input": raw}
        except ValueError:
            return {"input": raw}

    for m in _MCP_DIRECTIVE_RE.finditer(text or ""):
        g1, g2, g3 = m.group(1).strip(), m.group(2).strip(), m.group(3)
        if g3 is not None:
            # 完整三段式：第一段是 server_id
            if g1 in mcp_server_ids and g2:
                out.append((g1, g2, _args(g3)))
        else:
            # 短式两段式：第一段是工具名（未 attach 成功 / 未绑定 → 不执行）
            if g1 in tools_map and tools_map[g1] in mcp_server_ids:
                out.append((tools_map[g1], g1, _args(g2)))
        if len(out) >= 2:
            break
    return out


def strip_mcp_directives(text: str) -> str:
    """移除全部 [MCP:...] 协议块（两种格式 + 未知工具），给用户干净答案。"""
    return _MCP_DIRECTIVE_RE.sub("", text or "").strip()
