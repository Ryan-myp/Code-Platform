#!/usr/bin/env python3
"""Workflow 执行引擎"""
import sqlite3
import json
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiohttp

DB_PATH = Path(__file__).parent / "platform.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class WorkflowExecutor:
    """工作流执行器"""
    
    def __init__(self):
        self.running = False
        self.current_run = None
    
    async def execute(self, workflow_id: str, input_data: dict = None) -> str:
        """执行工作流"""
        conn = get_db()
        workflow = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
        conn.close()
        
        if not workflow:
            raise ValueError(f"工作流 {workflow_id} 不存在")
        
        # 创建工作流运行记录
        run_id = f"run_{int(time.time()*1000)}"
        conn = get_db()
        conn.execute(
            "INSERT INTO workflow_runs (id, workflow_id, status, input_data, started_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, workflow_id, "running", json.dumps(input_data or {}), datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        
        # 解析工作流定义
        try:
            definition = json.loads(workflow["definition"]) if isinstance(workflow["definition"], str) else workflow["definition"]
        except:
            raise ValueError("工作流定义格式错误")
        
        nodes = definition.get("nodes", [])
        edges = definition.get("edges", [])
        
        # 执行节点
        results = {}
        for node in nodes:
            node_id = node["id"]
            node_type = node["type"]
            config = node.get("config", {})
            
            # 执行节点
            result = await self.execute_node(node_type, config, results)
            results[node_id] = result
            
            # 记录节点执行日志
            conn = get_db()
            conn.execute(
                "INSERT INTO workflow_run_logs (id, run_id, node_id, status, output_data, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (f"log_{node_id}", run_id, node_id, "success", json.dumps(result), datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
        
        # 更新运行状态
        conn = get_db()
        conn.execute(
            "UPDATE workflow_runs SET status=?, output_data=?, completed_at=? WHERE id=?",
            ("completed", json.dumps(results), datetime.now().isoformat(), run_id)
        )
        conn.commit()
        conn.close()
        
        return run_id
    
    async def execute_node(self, node_type: str, config: dict, previous_results: dict) -> Any:
        """执行单个节点"""
        
        if node_type == "agent":
            return await self.execute_agent_node(config, previous_results)
        elif node_type == "http":
            return await self.execute_http_node(config, previous_results)
        elif node_type == "code":
            return await self.execute_code_node(config, previous_results)
        elif node_type == "condition":
            return await self.execute_condition_node(config, previous_results)
        elif node_type == "delay":
            return await self.execute_delay_node(config, previous_results)
        else:
            return {"status": "unknown_type", "type": node_type}
    
    async def execute_agent_node(self, config: dict, previous_results: dict) -> dict:
        """执行 Agent 节点"""
        agent_id = config.get("agent_id", "")
        # TODO: 调用 Agent 执行 API
        return {
            "status": "executed",
            "agent_id": agent_id,
            "result": "Agent execution result"
        }
    
    async def execute_http_node(self, config: dict, previous_results: dict) -> dict:
        """执行 HTTP 请求节点"""
        url = config.get("url", "")
        method = config.get("method", "GET")
        
        if not url:
            return {"status": "error", "message": "URL 不能为空"}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url) as resp:
                    text = await resp.text()
                    return {
                        "status": "success",
                        "status_code": resp.status,
                        "body": text[:1000]  # 限制长度
                    }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def execute_code_node(self, config: dict, previous_results: dict) -> dict:
        """执行代码节点"""
        code = config.get("code", "")
        language = config.get("language", "python")
        
        if not code:
            return {"status": "error", "message": "代码不能为空"}
        
        # TODO: 实现代码执行沙箱
        return {
            "status": "executed",
            "language": language,
            "result": "代码执行结果"
        }
    
    async def execute_condition_node(self, config: dict, previous_results: dict) -> dict:
        """执行条件判断节点"""
        expression = config.get("expression", "")
        # TODO: 实现表达式求值
        return {
            "status": "evaluated",
            "expression": expression,
            "result": True
        }
    
    async def execute_delay_node(self, config: dict, previous_results: dict) -> dict:
        """执行延迟节点"""
        seconds = config.get("seconds", 1)
        await asyncio.sleep(seconds)
        return {
            "status": "delayed",
            "seconds": seconds
        }

# 全局执行器实例
executor = WorkflowExecutor()
