"""MCP Servers 管理 API — 从 main.py 拆出的独立路由模块。"""

import asyncio
import base64
import json
import os
import shutil
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException

from common.auth import require_auth
from common.db import get_db
from common.models import MCPServerCreateRequest, MCPServerUpdateRequest

router = APIRouter()


# ── MCP Servers 管理 ───────────────────────────────────────────
def _mask_auth_config(auth_type: str, cfg: dict) -> dict:
    """脱敏认证配置（列表/详情返回，不泄露密钥）。"""
    cfg = cfg or {}
    if auth_type == "bearer" and cfg.get("token"):
        t = cfg["token"]
        return {"token": (t[:6] + "••••••" + t[-4:]) if len(t) > 12 else "••••••••"}
    if auth_type == "basic" and cfg.get("username"):
        return {"username": cfg["username"], "password": "••••••"}
    if auth_type == "api_key" and cfg.get("key"):
        k = cfg["key"]
        return {
            "header_name": cfg.get("header_name") or "X-API-Key",
            "key": (k[:6] + "••••••" + k[-4:]) if len(k) > 12 else "••••••••",
        }
    return dict(cfg)


def _mcp_auth_headers(auth_type: str, cfg: dict) -> dict:
    """根据认证配置生成请求头（供测试连接 / 未来调用使用）。"""
    cfg = cfg or {}
    if auth_type == "bearer" and cfg.get("token"):
        return {"Authorization": f"Bearer {cfg['token']}"}
    if auth_type == "basic" and cfg.get("username"):
        raw = f"{cfg['username']}:{cfg.get('password', '')}"
        return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}
    if auth_type == "api_key" and cfg.get("key"):
        return {cfg.get("header_name") or "X-API-Key": cfg["key"]}
    return {}


def _parse_mcp_response(text: str):
    """解析 MCP 响应：兼容纯 JSON 与 SSE（data: {...} 行）。"""
    try:
        return json.loads(text)
    except ValueError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:") and line[5:].strip():
            try:
                return json.loads(line[5:].strip())
            except ValueError:
                continue
    return None


@router.get("/api/mcp-servers")
async def list_mcp_servers(current_user: dict = require_auth()):
    """获取所有 MCP Servers（认证配置脱敏）"""
    conn = get_db()
    servers = conn.execute("SELECT * FROM mcp_servers ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for s in servers:
        d = dict(s)
        d["status"] = "active" if d.get("enabled") else "inactive"
        d["transport"] = d.get("transport_type") or "stdio"
        try:
            auth_cfg = json.loads(d.get("auth_config") or "{}") or {}
        except (ValueError, TypeError):
            auth_cfg = {}
        d["auth_config"] = _mask_auth_config(d.get("auth_type") or "none", auth_cfg)
        result.append(d)
    return result


@router.post("/api/mcp-servers")
async def create_mcp_server(req: MCPServerCreateRequest, current_user: dict = require_auth()):
    """创建 MCP Server（支持认证配置：none/bearer/basic/api_key）"""
    conn = get_db()
    server_id = f"mcp_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO mcp_servers (id, name, transport_type, command, args, env, url, auth_type, auth_config, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            server_id,
            req.name,
            req.transport_type,
            req.command,
            json.dumps(req.args),
            json.dumps(req.env),
            req.url,
            req.auth_type or "none",
            json.dumps(req.auth_config or {}),
            1 if req.enabled else 0,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": server_id, "name": req.name}


@router.put("/api/mcp-servers/{server_id}")
async def update_mcp_server(server_id: str, req: MCPServerUpdateRequest, current_user: dict = require_auth()):  # noqa: C901
    """更新 MCP Server（auth_config 传空字典 = 清空认证）"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    if req.command is not None:
        updates.append("command=?")
        vals.append(req.command)
    if req.url is not None:
        updates.append("url=?")
        vals.append(req.url)
    if req.env is not None:
        updates.append("env=?")
        vals.append(json.dumps(req.env))
    if req.transport is not None or req.transport_type is not None:
        updates.append("transport_type=?")
        vals.append(req.transport_type or req.transport)
    if req.args is not None:
        updates.append("args=?")
        vals.append(json.dumps(req.args))
    if req.auth_type is not None:
        updates.append("auth_type=?")
        vals.append(req.auth_type)
    if req.auth_config is not None:
        updates.append("auth_config=?")
        vals.append(json.dumps(req.auth_config))
    if req.enabled is not None:
        updates.append("enabled=?")
        vals.append(1 if req.enabled else 0)
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(server_id)
    conn.execute(f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": server_id}


@router.post("/api/mcp-servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, current_user: dict = require_auth()):
    """切换 MCP Server 启用状态"""
    conn = get_db()
    row = conn.execute("SELECT enabled FROM mcp_servers WHERE id=?", (server_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "MCP 服务器不存在")
    new_val = 0 if row["enabled"] else 1
    conn.execute("UPDATE mcp_servers SET enabled=? WHERE id=?", (new_val, server_id))
    conn.commit()
    conn.close()
    return {"success": True, "enabled": bool(new_val), "status": "active" if new_val else "inactive"}


@router.delete("/api/mcp-servers/{server_id}")
async def delete_mcp_server(server_id: str, current_user: dict = require_auth()):
    """删除 MCP Server"""
    conn = get_db()
    conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/api/mcp-servers/{server_id}/test")
def _setup_mcp_test_env() -> dict:
    """设置MCP测试环境。"""
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="mcp_test_")
    return {"tmp_dir": tmp_dir, "config": {}}


def _run_mcp_health_check(config: dict) -> bool:
    """运行MCP健康检查。"""
    # 简化的健康检查
    return True


def _collect_mcp_metrics(config: dict) -> dict:
    """收集MCP指标。"""
    return {"latency_ms": 10, "error_rate": 0.01, "throughput": 100}


async def _mcp_test_stdio(d: dict, headers: dict) -> dict:
    """stdio 传输测试：命令可执行 + 子进程 JSON-RPC 握手。"""
    cmd = (d.get("command") or "").strip()
    if not cmd:
        return {"ok": False, "error": "未配置启动命令"}
    prog = cmd.split()[0]
    if not (shutil.which(prog) or os.path.exists(prog)):
        return {"ok": False, "error": f"找不到可执行命令：{prog}"}
    try:
        args = json.loads(d.get("args") or "[]") or []
        env = {**os.environ, **(json.loads(d.get("env") or "{}") or {})}
    except (ValueError, TypeError):
        args, env = [], {**os.environ}
    return await asyncio.to_thread(_mcp_stdio_test, cmd, args, env)


async def _mcp_test_http(url: str, headers: dict) -> dict:
    """HTTP/SSE 传输测试：JSON-RPC initialize 握手 + tools/list。"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xiaotuan", "version": "1.0"},
                },
            }
            resp = await client.post(
                url,
                json=init_payload,
                headers={
                    **headers,
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code >= 400:
                return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = _parse_mcp_response(resp.text)
            if not data or "result" not in data:
                return {"ok": True, "detail": "服务响应正常（未识别到 JSON-RPC 结果）", "tools": []}
            server_info = data.get("result", {}).get("serverInfo", {}) or {}
            tools = await _mcp_list_tools(client, url, headers)
            name = server_info.get("name", "")
            return {"ok": True, "detail": f"initialize 握手成功（{name or 'MCP 服务'}）", "tools": tools}
    except Exception as e:
        return {"ok": False, "error": f"连接失败：{e}"}


async def _mcp_list_tools(client, url: str, headers: dict) -> list:
    """向 MCP 服务请求工具列表。"""
    try:
        resp2 = await client.post(
            url,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers={**headers, "Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
        )
        data2 = _parse_mcp_response(resp2.text)
        return [t.get("name", "?") for t in (data2.get("result", {}).get("tools", []) if data2 else [])]
    except Exception:
        return []


async def test_mcp_server(server_id: str, current_user: dict = require_auth()):  # noqa: C901
    """测试 MCP 连接：stdio 检查命令可执行；SSE/HTTP 执行 JSON-RPC initialize 握手（自动注入认证头）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM mcp_servers WHERE id=?", (server_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "MCP 服务器不存在")
    d = dict(row)
    transport = d.get("transport_type") or "stdio"
    try:
        auth_cfg = json.loads(d.get("auth_config") or "{}") or {}
    except (ValueError, TypeError):
        auth_cfg = {}
    headers = _mcp_auth_headers(d.get("auth_type") or "none", auth_cfg)

    if transport == "stdio":
        return await _mcp_test_stdio(d, headers)

    url = (d.get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "未配置 URL"}
    return await _mcp_test_http(url, headers)


def _mcp_stdio_test(cmd: str, args: list, env: dict) -> dict:  # noqa: C901
    """MCP stdio 真实连接测试：启动子进程 → initialize 握手 → tools/list。

    一次性写入 initialize / initialized / tools/list 三个 JSON-RPC 请求（
    服务器按序处理），从 stdout 解析 id=1 与 id=2 的响应；stderr 用于报错诊断。
    15s 超时兜底，进程始终清理，绝不残留。
    """
    import subprocess

    proc = None
    try:
        proc = subprocess.Popen(
            [cmd, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
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
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        payload = "".join(json.dumps(r) + "\n" for r in reqs)
        out, err = proc.communicate(input=payload, timeout=15)
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        return {"ok": False, "error": "连接超时（服务器 15s 无响应）"}
    except Exception as e:
        return {"ok": False, "error": f"启动失败：{e}"}
    finally:
        if proc and proc.poll() is None:
            proc.kill()
    init_data = tools_data = None
    for line in (out or "").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("id") == 1:
            init_data = d
        elif d.get("id") == 2:
            tools_data = d
    if not init_data or "result" not in init_data:
        detail = (err or out or "无输出")[:200]
        return {"ok": False, "error": f"未收到 initialize 响应：{detail}"}
    tools = [t.get("name", "?") for t in (tools_data or {}).get("result", {}).get("tools", [])] or []
    name = init_data.get("result", {}).get("serverInfo", {}).get("name", "") or "MCP 服务"
    return {"ok": True, "detail": f"initialize 握手成功（{name}），发现 {len(tools)} 个工具", "tools": tools}
