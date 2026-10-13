"""MCP 工具调用客户端：把绑定的 MCP Server 接进 Agent 执行链路。

历史短板：Agent 可绑定 MCP Server，但执行引擎从未调用过它们（只有测试连接）。
本模块提供：

- mcp_list_tools(server)：真实 tools/list（stdio 子进程 / HTTP+SSE JSON-RPC）
- mcp_call_tool(server, tool_name, arguments)：真实 tools/call，返回文本结果

所有函数失败时返回诚实降级值（空列表 / 降级说明字符串），绝不抛异常阻断
Agent 执行；15s 超时兜底；stdio 子进程始终清理，绝不残留。
"""

import ipaddress
import json
import logging
import os
import re
import socket
import subprocess
import time
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_TIMEOUT = 15

# ── tools/list 短 TTL 缓存（避免每次 Agent 组装都实时握手拉清单）──────
_TOOLS_CACHE: dict[str, tuple[float, list[dict]]] = {}
_TOOLS_CACHE_TTL = 120.0
_TOOLS_CACHE_MAX = 200


def _http_target_guard(url: str) -> str:
    """SSRF 防护：URL 安全检查。返回 '' 表示放行，否则返回人类可读拒绝原因。

    策略：仅 http/https；拒绝解析到 链路本地（169.254.0.0/16 = 云元数据）/
    组播/未指定地址。loopback 与私网放行（本地部署时运行自家 MCP Server 是正当场景）；
    如需更高安全水位可扩展拒绝私有地址段。DNS 检查与建连存在 TOCTOU 窗口（DNS 重绑定），
    httpx 已默认不跟随重定向，进一步收窄逃逸面。
    """
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "URL 必须为 http/https"
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return f"无法解析主机 {host}"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_link_local:
            return "禁止访问内网/云元数据地址（169.254.0.0/16）"
        if ip.is_multicast or ip.is_unspecified:
            return "非法目标地址"
    return ""


def _tools_cache_key(server: dict) -> str:
    """缓存键 = 配置指纹：任一关键字段变更即自动失效。"""
    fields = {k: server.get(k) for k in ("id", "transport_type", "command", "url", "args", "env", "auth_type", "auth_config")}
    return json.dumps(fields, sort_keys=True, ensure_ascii=False)


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


async def _http_rpc(server: dict, method: str, params: dict) -> dict:
    """HTTP/SSE 传输公共路径：initialize 握手 → 目标请求（携带 Mcp-Session-Id）。

    返回解析后的最终响应（无法解析时 {}）；连接/请求异常直接上抛由调用方捕获降级。
    """
    import httpx

    from mcp_api import _mcp_auth_headers

    url = (server.get("url") or "").strip()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        **_mcp_auth_headers(server.get("auth_type") or "none", json.loads(server.get("auth_config") or "{}")),
    }
    requests = [
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
        {"jsonrpc": "2.0", "id": 2, "method": method, "params": params or {}},
    ]
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, headers=headers, json=requests[0])
        session_id = resp.headers.get("Mcp-Session-Id", "")
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        resp = await client.post(url, headers=headers, json=requests[1])
    return _parse_sse_maybe(resp.text) or {}


def _http_transport(server: dict) -> bool:
    transport = (server.get("transport_type") or "stdio").lower()
    return "http" in transport or "sse" in transport or transport == "streamable"


def _extract_tools(raw: dict | None) -> list[dict]:
    """tools/list 响应 → 合法工具列表（形状异常返回 []）。"""
    result = (raw.get("result") or {}) if isinstance(raw, dict) else {}
    tools = result.get("tools") if isinstance(result, dict) else None
    return [t for t in (tools or []) if isinstance(t, dict) and t.get("name")]


async def mcp_list_tools(server: dict) -> list[dict]:
    """真实 tools/list。失败返回 []（由调用方决定降级文案）。

    HTTP 工具清单带 120s 短 TTL 缓存（键为 server 配置指纹，配置变更自动失效）；
    空结果不缓存，避免把临时不可达钉在缓存里。
    """
    import asyncio

    if _http_transport(server):
        url = (server.get("url") or "").strip()
        if not url:
            return []
        guard = _http_target_guard(url)
        if guard:
            logger.warning(f"mcp http url blocked for {server.get('id')}: {guard}")
            return []
        key = _tools_cache_key(server)
        now = time.monotonic()
        hit = _TOOLS_CACHE.get(key)
        if hit and now - hit[0] < _TOOLS_CACHE_TTL:
            return hit[1]
        try:
            data = await _http_rpc(server, "tools/list", {})
        except Exception as e:
            logger.warning(f"mcp http list_tools failed: {e}")
            return []
        tools = _extract_tools(data)
        if tools:
            if len(_TOOLS_CACHE) >= _TOOLS_CACHE_MAX:
                _TOOLS_CACHE.clear()
            _TOOLS_CACHE[key] = (now, tools)
        return tools
    else:
        msg = await asyncio.to_thread(_stdio_rpc, server, "tools/list", {})
        return _extract_tools(msg or {})


async def mcp_call_tool(server: dict, tool_name: str, arguments: dict) -> str:
    """真实 tools/call。返回结果文本；失败返回诚实降级说明，不抛异常。

    HTTP 传输瞬时故障（连接/超时类）自动重试 1 次（统一错误分类口径，低并发：
    至多重试 1 次 + 短退避）；stdio 不重试（进程成本 + 超时已有上限）。
    """
    import asyncio

    from common import errors

    try:
        if _http_transport(server):
            url = (server.get("url") or "").strip()
            if not url:
                return f"MCP Server「{server.get('name')}」未配置 URL，调用不可用。"
            guard = _http_target_guard(url)
            if guard:
                return f"MCP Server「{server.get('name')}」调用不可用：{guard}"
            data = await errors.run_with_retry_async(
                lambda: _http_rpc(server, "tools/call", {"name": tool_name, "arguments": arguments or {}}),
                attempts=2,
                on_retry=lambda a, e: logger.warning(f"mcp tools/call transient retry {a}: {e}"),
            )
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
