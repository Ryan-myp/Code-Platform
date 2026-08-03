#!/usr/bin/env python3
"""Workflow 执行引擎。

节点类型:
- agent:     调用 LLM (使用指定 Agent 的 system prompt)
- http:      HTTP 请求 (aiohttp)
- code:      受限 Python 子进程 (10s 超时 + 4KB 输出截断 + 精简 env)
- condition: AST 白名单求值 (无 builtins，仅允许算术/逻辑/比较 + results 命名空间)
- delay:     asyncio.sleep
- image:     调用 Agnes /images/generations (图片工厂)
- video:     调用 Agnes /videos 创建视频任务 (视频工厂)
- music:     调用 LLM 生成歌词 (音乐工厂)
- prd:       复用 prd_engine 流程函数 (generate/review/td/test/code)
"""

import ast
import asyncio
import ipaddress
import json
import logging
import operator as _op
import os
import re
import resource
import socket
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp
import requests

from common.config import get_llm_config, load_config
from common.db import get_db
from common.llm import call_llm, log_usage

logger = logging.getLogger(__name__)

# 模块加载时同步 LLM 配置 (Agent/PRD/Music 节点直接使用)
load_config()

# 创作产物目录 (image 节点保存本地文件)
_IMAGE_DIR = Path(__file__).resolve().parent.parent / "image_factory"
_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# SSRF 防护 — 阻止对私有/内部网络的请求
# ══════════════════════════════════════════════════════════════
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),         # 私有网络 A
    ipaddress.ip_network("172.16.0.0/12"),      # 私有网络 B
    ipaddress.ip_network("192.168.0.0/16"),      # 私有网络 C
    ipaddress.ip_network("169.254.0.0/16"),     # 链路本地
    ipaddress.ip_network("0.0.0.0/8"),          # 本网络
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),           # IPv6 唯一本地
    ipaddress.ip_network("fe80::/10"),          # IPv6 链路本地
]


def _is_safe_url(url: str) -> bool:
    """检查 URL 是否安全（非私有/内部地址）。"""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.hostname:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        # 解析主机名为 IP 地址
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        except (ValueError, socket.gaierror):
            return False
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                logger.warning(f"SSRF blocked: {url} resolves to {ip}")
                return False
        return True
    except Exception as e:
        logger.warning(f"URL safety check failed for {url}: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# 工具：占位符替换 ${node_id.field.path} → previous_results 中的值
# ══════════════════════════════════════════════════════════════
_PLACEHOLDER_RE = re.compile(r"\$\{([^}]+)\}")


def _substitute(text, results: dict):
    """把 ${node_id.field.path} 替换为前序节点结果中的值。无匹配则保留原文。非字符串原样返回。"""
    if not isinstance(text, str) or not text:
        return text

    def _resolve(m):
        path = m.group(1).strip().split(".")
        cur = results
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return m.group(0)  # 找不到，原样保留
        if isinstance(cur, (dict, list)):
            return json.dumps(cur, ensure_ascii=False)
        return str(cur)

    return _PLACEHOLDER_RE.sub(_resolve, text)


# ══════════════════════════════════════════════════════════════
# 工具：AST 白名单求值器 (condition 节点)
# ══════════════════════════════════════════════════════════════
_ALLOWED_BINOPS = {
    ast.Add: _op.add, ast.Sub: _op.sub, ast.Mult: _op.mul, ast.Div: _op.truediv,
    ast.Mod: _op.mod, ast.FloorDiv: _op.floordiv, ast.Pow: _op.pow,
}
_ALLOWED_CMPOPS = {
    ast.Eq: _op.eq, ast.NotEq: _op.ne, ast.Lt: _op.lt, ast.LtE: _op.le,
    ast.Gt: _op.gt, ast.GtE: _op.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}
_ALLOWED_UNARYOPS = {ast.USub: _op.neg, ast.UAdd: _op.pos, ast.Not: _op.not_, ast.Invert: _op.invert}


class _SafeEval(ast.NodeVisitor):
    """AST 白名单求值器：仅允许常量/名称/下标/算术/逻辑/比较运算。

    显式拒绝 Attribute/Call/Lambda/Import 等，避免逃逸。
    """

    def visit_Expression(self, node):
        return self.visit(node.body)

    def visit_BoolOp(self, node):
        vals = [self.visit(v) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)

    def visit_BinOp(self, node):
        left = self.visit(node.left)
        right = self.visit(node.right)
        fn = _ALLOWED_BINOPS.get(type(node.op))
        if fn is None:
            raise ValueError(f"unsupported binop: {type(node.op).__name__}")
        return fn(left, right)

    def visit_UnaryOp(self, node):
        operand = self.visit(node.operand)
        fn = _ALLOWED_UNARYOPS.get(type(node.op))
        if fn is None:
            raise ValueError(f"unsupported unaryop: {type(node.op).__name__}")
        return fn(operand)

    def visit_Compare(self, node):
        left = self.visit(node.left)
        for op_node, right_node in zip(node.ops, node.comparators, strict=False):
            right = self.visit(right_node)
            fn = _ALLOWED_CMPOPS.get(type(op_node))
            if fn is None:
                raise ValueError(f"unsupported cmpop: {type(op_node).__name__}")
            if not fn(left, right):
                return False
            left = right
        return True

    def visit_Constant(self, node):
        return node.value

    def visit_Name(self, node):
        if node.id not in self.env:
            raise NameError(f"name '{node.id}' is not defined")
        return self.env[node.id]

    def visit_Subscript(self, node):
        value = self.visit(node.value)
        slice_val = self.visit(node.slice)
        return value[slice_val]

    def visit_List(self, node):
        return [self.visit(e) for e in node.elts]

    def visit_Tuple(self, node):
        return tuple(self.visit(e) for e in node.elts)

    def visit_Dict(self, node):
        return {self.visit(k): self.visit(v) for k, v in zip(node.keys, node.values, strict=False)}

    def visit_IfExp(self, node):
        return self.visit(node.body) if self.visit(node.test) else self.visit(node.orelse)

    def generic_visit(self, node):
        raise ValueError(f"disallowed expression node: {type(node).__name__}")


def _safe_eval(expr: str, env: dict) -> Any:
    tree = ast.parse(expr, mode="eval")
    evaluator = _SafeEval()
    evaluator.env = env
    return evaluator.visit(tree)


# ══════════════════════════════════════════════════════════════
# WorkflowExecutor
# ══════════════════════════════════════════════════════════════
class WorkflowExecutor:
    """工作流执行器

    v8.0 升级：
    - DAG 拓扑排序实现并行执行独立分支
    - 支持 BusinessNode 子类作为节点类型
    - 实时进度推送（WebSocket）
    """

    def __init__(self):
        self.running = False
        self.current_run = None

    def _build_dag(self, nodes: list, connections: list) -> tuple[dict, dict]:
        """从节点和连接构建 DAG 邻接表和入度表。

        Returns:
            (adjacency_list, in_degree)
            adjacency_list: {node_id: [downstream_node_ids]}
            in_degree: {node_id: count}
        """
        node_ids = {n["id"] for n in nodes}
        adjacency = {nid: [] for nid in node_ids}
        in_degree = {nid: 0 for nid in node_ids}

        for conn in connections:
            src = conn.get("source") or conn.get("from") or conn.get("source_id", "")
            dst = conn.get("target") or conn.get("to") or conn.get("target_id", "")
            if src in node_ids and dst in node_ids:
                adjacency[src].append(dst)
                in_degree[dst] += 1

        return adjacency, in_degree

    async def execute(self, workflow_id: str, input_data: dict = None) -> str:  # noqa: C901
        """执行工作流，返回 run_id。

        v8.0: 基于 DAG 拓扑排序的并行执行。无连接关系的节点按定义顺序执行；
        有独立分支时并行执行（asyncio.gather）。
        """
        conn = get_db()
        workflow = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
        conn.close()
        if not workflow:
            raise ValueError(f"工作流 {workflow_id} 不存在")

        # workflows.steps 存的是 JSON 编码的节点列表
        steps_raw = workflow["steps"] if "steps" in workflow.keys() else ""
        try:
            definition = json.loads(steps_raw or "[]") if steps_raw else []
        except json.JSONDecodeError:
            raise ValueError("工作流 steps 格式错误") from None

        if isinstance(definition, dict):
            nodes = definition.get("nodes", [])
        else:
            nodes = definition or []

        # 读取连接关系构建 DAG
        connections_raw = workflow["connections"] if "connections" in workflow.keys() else ""
        try:
            connections = json.loads(connections_raw or "[]") if connections_raw else []
            if not isinstance(connections, list):
                connections = []
        except (json.JSONDecodeError, TypeError):
            connections = []

        adjacency, in_degree = self._build_dag(nodes, connections)

        # 创建运行记录
        run_id = f"run_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}"
        conn = get_db()
        conn.execute(
            "INSERT INTO workflow_runs (id, workflow_id, status, input_data, started_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, workflow_id, "running", json.dumps(input_data or {}, ensure_ascii=False), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

        self.running = True
        self.current_run = run_id
        ws_channel = f"workflow:{run_id}"

        try:
            results = {}
            # 注入输入数据，使节点配置可通过 ${input.message} 引用工作流输入
            if input_data:
                results["input"] = input_data
            node_map = {n["id"]: n for n in nodes}
            processed = set()

            # Kahn 算法：按入度分层并行执行
            while len(processed) < len(nodes):
                # 找出当前可执行的节点（入度为 0 且未处理）
                ready = [
                    nid for nid in in_degree
                    if in_degree[nid] == 0 and nid not in processed
                ]
                if not ready:
                    # 有环：剩余节点无法执行
                    remaining = [nid for nid in in_degree if nid not in processed]
                    for nid in remaining:
                        results[nid] = {"status": "error", "message": "检测到循环依赖，节点未执行"}
                        self._log_node(run_id, nid, "failed", results[nid])
                    break

                # 并行执行就绪的节点
                async def _exec_one(node_id: str):
                    node = node_map[node_id]
                    node_type = node.get("type", "")
                    config = node.get("config", {}) or {}
                    try:
                        result = await self.execute_node(node_type, config, results, input_data or {})
                        results[node_id] = result
                        status = "success"
                        output = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception as e:
                        logger.exception(f"node {node_id} ({node_type}) failed")
                        results[node_id] = {"status": "error", "message": str(e)}
                        status = "failed"
                        output = json.dumps(results[node_id], ensure_ascii=False, default=str)
                    self._log_node(run_id, node_id, status, output)
                    # WebSocket 推送进度
                    try:
                        from realtime import manager
                        await manager.send_progress(ws_channel, "node_completed", {
                            "node_id": node_id, "status": status,
                            "result": results[node_id],
                        })
                    except Exception:
                        pass
                    return node_id

                await asyncio.gather(*[_exec_one(nid) for nid in ready])

                # 更新已处理集合和入度
                for nid in ready:
                    processed.add(nid)
                    for downstream in adjacency.get(nid, []):
                        in_degree[downstream] -= 1
        finally:
            self.running = False
            self.current_run = None

        # 更新运行状态
        conn = get_db()
        conn.execute(
            "UPDATE workflow_runs SET status=?, output_data=?, completed_at=? WHERE id=?",
            ("completed", json.dumps(results, ensure_ascii=False, default=str), datetime.now().isoformat(), run_id),
        )
        conn.commit()
        conn.close()

        # WebSocket 推送完成事件
        try:
            from realtime import manager
            await manager.send_progress(ws_channel, "workflow_completed", {"run_id": run_id, "results": results})
        except Exception:
            pass

        return run_id

    def _log_node(self, run_id: str, node_id: str, status: str, output: str) -> None:
        """记录节点执行日志到数据库。"""
        conn = get_db()
        conn.execute(
            "INSERT INTO workflow_run_logs (id, run_id, node_id, status, output_data, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"log_{node_id}_{uuid.uuid4().hex[:6]}", run_id, node_id, status, output, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    async def execute_node(self, node_type: str, config: dict, previous_results: dict, input_data: dict = None) -> Any:  # noqa: C901
        """执行单个节点"""
        if node_type == "agent":
            return await self.execute_agent_node(config, previous_results, input_data or {})
        elif node_type == "http":
            return await self.execute_http_node(config, previous_results)
        elif node_type == "code":
            return await self.execute_code_node(config, previous_results)
        elif node_type == "condition":
            return await self.execute_condition_node(config, previous_results)
        elif node_type == "delay":
            return await self.execute_delay_node(config, previous_results)
        elif node_type == "image":
            return await self.execute_image_node(config, previous_results)
        elif node_type == "video":
            return await self.execute_video_node(config, previous_results)
        elif node_type == "music":
            return await self.execute_music_node(config, previous_results)
        elif node_type == "prd":
            return await self.execute_prd_node(config, previous_results)
        elif node_type == "business":
            return await self.execute_business_node(config, previous_results)
        elif node_type == "output":
            return await self.execute_output_node(config, previous_results)
        else:
            return {"status": "unknown_type", "type": node_type}

    # ── Business 节点：加载并执行 BusinessNode 子类 ────────────
    async def execute_business_node(self, config: dict, previous_results: dict) -> dict:
        """执行 BusinessNode 子类节点。

        v8.0 新增：连接 nodes/base.py 的 BusinessNode 框架与工作流执行器。
        config 需包含 module_path 和 class_name，或 node_type 名称。
        """
        module_path = config.get("module_path", "")
        class_name = config.get("class_name", "")
        node_config = config.get("node_config", {})

        if not module_path or not class_name:
            return {"status": "error", "message": "business 节点需要 module_path 和 class_name"}

        try:
            import importlib
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            node = cls(node_id=class_name, name=class_name, **node_config)

            # 构建上下文
            context = {
                "inputs": previous_results,
                "outputs": previous_results,
                "global_outputs": {},
                "current_node_input": config.get("input_data", {}),
            }

            result = node.execute(context)
            return result.to_dict()
        except Exception as e:
            logger.exception(f"business node {class_name} failed")
            return {"status": "error", "message": str(e)}

    # ── Agent 节点：调用 LLM（用 Agent 的 instructions 作 system prompt）──
    async def execute_agent_node(self, config: dict, previous_results: dict, input_data: dict) -> dict:
        agent_id = config.get("agent_id", "")
        raw_message = config.get("message", "") or (input_data.get("message") if input_data else "") or ""
        message = _substitute(raw_message, previous_results)
        if not message:
            return {"status": "error", "message": "agent message 为空"}

        conn = get_db()
        agent = None
        if agent_id:
            agent = conn.execute("SELECT * FROM agents WHERE id=? AND active=1", (agent_id,)).fetchone()
        conn.close()
        system = agent["instructions"] if agent and agent["instructions"] else "你是一个智能助手"

        start = time.time()
        result = call_llm(system, message, max_tokens=2000)
        elapsed = time.time() - start
        log_usage("wf_agent_node", len(message), len(result), elapsed)
        return {
            "status": "success",
            "agent_id": agent_id,
            "result": result,
            "elapsed": round(elapsed, 2),
        }

    # ── HTTP 节点（含 SSRF 防护）────────────────────────────
    async def execute_http_node(self, config: dict, previous_results: dict) -> dict:
        url = _substitute(config.get("url", ""), previous_results)
        method = (config.get("method") or "GET").upper()
        if not url:
            return {"status": "error", "message": "URL 不能为空"}
        if not _is_safe_url(url):
            return {"status": "error", "message": "URL 不安全（指向私有/内部网络被阻止）"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    text = await resp.text()
                    return {
                        "status": "success" if resp.status < 400 else "error",
                        "status_code": resp.status,
                        "body": text[:4000],
                    }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Code 节点：受限 Python 子进程 ─────────────────────────
    async def execute_code_node(self, config: dict, previous_results: dict) -> dict:
        code = _substitute(config.get("code", ""), previous_results)
        language = (config.get("language") or "python").lower()
        if not code:
            return {"status": "error", "message": "代码不能为空"}
        if language != "python":
            return {"status": "error", "message": f"暂不支持的语言: {language}（仅支持 python）"}

        # 受限子进程：临时文件 + 10s 超时 + 输出截断 + 精简 env + -S 不导入 site + 资源限制
        # 注：非真正沙箱，仅做基本限制。生产环境应换容器/隔离执行器。
        env = {k: v for k, v in os.environ.items() if k not in ("AGNES_API_KEY", "SECRET_KEY", "DB_PATH")}
        env["PYTHONPATH"] = ""  # 阻止导入本工程模块
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
                tf.write(code)
                tmp_path = tf.name
            # 子进程资源限制：内存 256MB，CPU 10s，文件 4MB
            def _set_subprocess_limits():
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
                    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
                    resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024 * 1024, 4 * 1024 * 1024))
                except (ValueError, OSError):
                    pass  # 某些平台不支持某些限制
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-S", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                preexec_fn=_set_subprocess_limits if sys.platform != "win32" else None,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"status": "error", "language": language, "message": "执行超时（>10s）", "returncode": -1}
            return {
                "status": "success" if proc.returncode == 0 else "error",
                "language": language,
                "stdout": stdout.decode("utf-8", errors="replace")[:4000],
                "stderr": stderr.decode("utf-8", errors="replace")[:4000],
                "returncode": proc.returncode,
            }
        except Exception as e:
            return {"status": "error", "language": language, "message": str(e)}
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    # ── Condition 节点：AST 安全求值 ─────────────────────────
    async def execute_condition_node(self, config: dict, previous_results: dict) -> dict:
        expression = _substitute(config.get("expression", ""), previous_results)
        if not expression:
            return {"status": "error", "message": "表达式为空"}
        env = {
            "results": previous_results,
            "true": True, "false": False, "True": True, "False": False,
            "null": None, "None": None,
        }
        try:
            value = _safe_eval(expression, env)
            return {"status": "evaluated", "expression": expression, "result": bool(value)}
        except Exception as e:
            return {"status": "error", "expression": expression, "message": str(e)}

    # ── Delay 节点 ───────────────────────────────────────────
    async def execute_delay_node(self, config: dict, previous_results: dict) -> dict:
        seconds = float(config.get("seconds", 1))
        await asyncio.sleep(seconds)
        return {"status": "delayed", "seconds": seconds}

    # ── Output 节点：汇总上游结果作为工作流最终输出 ────────────
    async def execute_output_node(self, config: dict, previous_results: dict) -> dict:
        """输出节点：把上游最后一个成功节点的结果作为最终输出。"""
        success = {
            k: v for k, v in previous_results.items()
            if k != "input" and isinstance(v, dict) and v.get("status") == "success"
        }
        if not success:
            return {"status": "error", "message": "没有可输出的上游结果"}
        _, last = next(reversed(success.items()))
        for key in ("result", "lyrics", "content", "text"):
            if last.get(key):
                return {"status": "success", "result": last[key], "source": key}
        return {"status": "success", **last}

    # ── Image 节点：调 Agnes /images/generations ─────────────
    async def execute_image_node(self, config: dict, previous_results: dict) -> dict:
        prompt = _substitute(config.get("prompt", ""), previous_results)
        size = config.get("size", "1024x1024")
        model = config.get("model", "agnes-image-2.1-flash")
        if not prompt:
            return {"status": "error", "message": "prompt 为空"}

        api_key, api_base, _ = get_llm_config()
        if not api_key:
            return {"status": "error", "message": "未配置 AGNES_API_KEY"}
        try:
            resp = requests.post(
                f"{api_base}/images/generations",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "prompt": prompt, "size": size, "n": 1},
                timeout=180,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"图片生成失败: {resp.status_code} {resp.text[:300]}"}
            data = resp.json()
            items = data.get("data") or []
            if not items:
                return {"status": "error", "message": "API 返回空 data"}
            image_url = items[0].get("url")
            local_url = ""
            if image_url:
                img_resp = requests.get(image_url, timeout=60)
                filename = f"img_{int(time.time() * 1000)}.png"
                (_IMAGE_DIR / filename).write_bytes(img_resp.content)
                local_url = f"/api/image-factory/images/{filename}"
            return {"status": "success", "url": local_url, "remote_url": image_url, "prompt": prompt}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Video 节点：创建视频生成任务 ─────────────────────────
    async def execute_video_node(self, config: dict, previous_results: dict) -> dict:
        prompt = _substitute(config.get("prompt", ""), previous_results)
        duration = int(config.get("duration", 5))
        width = int(config.get("width", 1152))
        height = int(config.get("height", 768))
        if not prompt:
            return {"status": "error", "message": "prompt 为空"}

        api_key, api_base, _ = get_llm_config()
        if not api_key:
            return {"status": "error", "message": "未配置 AGNES_API_KEY"}
        frame_rate = 24
        num_frames = min(duration * frame_rate, 441)
        if (num_frames - 1) % 8 != 0:
            num_frames = ((num_frames - 1) // 8) * 8 + 1
        try:
            resp = requests.post(
                f"{api_base}/videos",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "agnes-video-v2.0",
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_frames": num_frames,
                    "frame_rate": frame_rate,
                    "mode": "ti2vid",
                },
                timeout=60,
            )
            if resp.status_code != 200:
                return {"status": "error", "message": f"视频任务创建失败: {resp.status_code} {resp.text[:300]}"}
            data = resp.json()
            video_id = data.get("video_id") or data.get("task_id")
            if not video_id:
                return {"status": "error", "message": f"未获取到 video_id: {data}"}
            return {
                "status": "success",
                "video_id": video_id,
                "prompt": prompt,
                "estimated_time": duration * 10,
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Music 节点：LLM 生成歌词 ─────────────────────────────
    async def execute_music_node(self, config: dict, previous_results: dict) -> dict:
        theme = _substitute(config.get("theme", "love"), previous_results)
        style = config.get("style", "pop")
        language = config.get("language", "zh")
        mood = config.get("mood", "happy")
        if not theme:
            return {"status": "error", "message": "theme 为空"}

        system = "你是一位专业的歌词创作者，擅长创作优美动人的歌词。"
        prompt = (
            f"创作一首{language}的{style}歌词。\n"
            f"主题：{theme}\n情感基调：{mood}\n\n"
            "要求：押韵自然、结构清晰（标注 Verse/Chorus/Bridge），适合演唱。只输出歌词。"
        )
        start = time.time()
        lyrics = call_llm(system, prompt, max_tokens=1500, temperature=0.8)
        log_usage("wf_music_node", len(prompt), len(lyrics), time.time() - start)
        return {"status": "success", "lyrics": lyrics, "theme": theme, "style": style}

    # ── PRD 节点：复用 prd_engine 流程函数 ────────────────────
    async def execute_prd_node(self, config: dict, previous_results: dict) -> dict:  # noqa: C901
        stage = (config.get("stage") or "generate").lower()
        prd_text = _substitute(config.get("prd_text", ""), previous_results)
        tech_design = _substitute(config.get("tech_design", ""), previous_results)
        language = config.get("language", "python")

        # 延迟导入避免循环依赖
        from prd_engine import (
            generate_code,
            generate_prd,
            review_prd,
            technical_design,
            test_cases,
        )

        try:
            if stage == "generate":
                if not prd_text:
                    return {"status": "error", "message": "prd_text 为空"}
                r = await generate_prd({"prd_text": prd_text})
            elif stage == "review":
                if not prd_text:
                    return {"status": "error", "message": "prd_text 为空"}
                r = await review_prd({"prd_text": prd_text})
            elif stage in ("td", "technical-design"):
                if not prd_text:
                    return {"status": "error", "message": "prd_text 为空"}
                r = await technical_design({"prd_text": prd_text})
            elif stage == "test":
                if not prd_text:
                    return {"status": "error", "message": "prd_text 为空"}
                r = await test_cases({"prd_text": prd_text, "tech_design": tech_design})
            elif stage == "code":
                if not tech_design:
                    return {"status": "error", "message": "tech_design 为空"}
                r = await generate_code({"tech_design": tech_design, "language": language})
            else:
                return {"status": "error", "message": f"未知 stage: {stage}"}
            return {"status": "success", "stage": stage, "result": r.get("result", "")}
        except Exception as e:
            return {"status": "error", "stage": stage, "message": str(e)}


# 全局执行器实例
executor = WorkflowExecutor()
