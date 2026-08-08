#!/usr/bin/env python3
"""沙箱容器管理器 — 基于 Podman/Docker 的容器化沙箱"""

import json
import subprocess
import threading
from datetime import datetime

# 沙箱状态
SANDBOX_STATUS = {"ready": "ready", "running": "running", "stopped": "stopped", "error": "error"}

# 预置服务模板（唯一数据源：环境模板 + 中间件服务，前端直接渲染本表，避免双份定义重复展示）
SERVICE_TEMPLATES = {
    "python": {
        "name": "Python 环境",
        "image": "python:3.11",
        "ports": ["8000:8000"],
        "command": None,
        "description": "Python 3.11 开发环境",
    },
    "node": {
        "name": "Node.js 环境",
        "image": "node:20",
        "ports": ["3000:3000"],
        "command": None,
        "description": "Node.js 20 LTS 环境",
    },
    "go": {
        "name": "Go 环境",
        "image": "golang:1.21",
        "ports": ["8080:8080"],
        "command": None,
        "description": "Go 1.21 开发环境",
    },
    "redis": {
        "name": "Redis",
        "image": "redis:7-alpine",
        "ports": ["6379:6379"],
        "command": None,
        "description": "Redis 缓存服务（支持控制台操作 Key）",
    },
    "postgres": {
        "name": "PostgreSQL",
        "image": "postgres:16-alpine",
        "ports": ["5432:5432"],
        "env": ["POSTGRES_PASSWORD=password", "POSTGRES_USER=postgres", "POSTGRES_DB=sandbox"],
        "command": None,
        "description": "PostgreSQL 数据库（支持控制台查询）",
    },
    "mysql": {
        "name": "MySQL",
        "image": "mysql:8.0",
        "ports": ["3306:3306"],
        "env": ["MYSQL_ROOT_PASSWORD=password", "MYSQL_DATABASE=sandbox"],
        "command": None,
        "description": "MySQL 数据库（支持控制台查询）",
    },
    "rabbitmq": {
        "name": "RabbitMQ",
        "image": "rabbitmq:3-management-alpine",
        "ports": ["5672:5672", "15672:15672"],
        "command": None,
        "description": "RabbitMQ 消息队列 (含管理界面)",
    },
    "nginx": {
        "name": "Nginx",
        "image": "nginx:alpine",
        "ports": ["8080:80"],
        "command": None,
        "description": "Nginx Web 服务器",
    },
    "mongo": {
        "name": "MongoDB",
        "image": "mongo:7",
        "ports": ["27017:27017"],
        "env": ["MONGO_INITDB_ROOT_USERNAME=admin", "MONGO_INITDB_ROOT_PASSWORD=password"],
        "command": None,
        "description": "MongoDB 文档数据库",
    },
}


class ContainerManager:
    def __init__(self, runtime: str = "podman"):
        self.runtime = runtime
        self.containers: dict[str, dict] = {}
        self.lock = threading.Lock()
        self._ensure_runtime()

    def _ensure_runtime(self):
        """确保容器运行时可用"""
        try:
            result = subprocess.run([self.runtime, "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise RuntimeError(f"{self.runtime} 不可用")
        except FileNotFoundError:
            raise RuntimeError(f"{self.runtime} 未安装") from None

    def _run_cmd(self, cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
        """运行命令（stdin 重定向，防后台环境继承 tty 触发 SIGTTIN 进程组停止）"""
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)

    def list_images(self) -> list[dict]:
        """列出本地镜像"""
        result = self._run_cmd([self.runtime, "images", "--format", "json"])
        if result.returncode != 0:
            return []
        images = []
        for line in result.stdout.strip().split("\n"):
            if line:
                try:
                    img = json.loads(line)
                    images.append(
                        {
                            "id": img.get("Id", "")[:12],
                            "tag": img.get("Tag", "latest"),
                            "size": img.get("Size", "0"),
                            "created": img.get("CreatedAt", ""),
                        }
                    )
                except Exception:
                    pass
        return images

    def pull_image(self, image: str) -> dict:
        """拉取镜像"""
        result = self._run_cmd([self.runtime, "pull", image], timeout=300)
        if result.returncode == 0:
            return {"status": "success", "message": f"镜像 {image} 拉取成功"}
        return {"status": "error", "message": result.stderr}

    def create_container(self, project_id: str, config: dict) -> dict:
        """创建容器"""
        image = config.get("image", "")
        name = f"sandbox-{project_id}"
        ports = config.get("ports", [])
        env = config.get("env", [])
        volumes = config.get("volumes", [])

        cmd = [self.runtime, "run", "-d", "--name", name]

        # 端口映射
        for port in ports:
            cmd.extend(["-p", port])

        # 环境变量
        for e in env:
            cmd.extend(["-e", e])

        # 卷挂载
        for v in volumes:
            cmd.extend(["-v", v])

        # 容器名
        cmd.append(image)

        result = self._run_cmd(cmd)
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr}

        container_id = result.stdout.strip()

        with self.lock:
            self.containers[project_id] = {
                "container_id": container_id,
                "name": name,
                "image": image,
                "status": "running",
                "created_at": datetime.now().isoformat(),
            }

        return {"status": "success", "container_id": container_id, "name": name}

    def start_container(self, project_id: str) -> dict:
        """启动容器"""
        with self.lock:
            if project_id not in self.containers:
                return {"status": "error", "message": "容器不存在"}

        result = self._run_cmd([self.runtime, "start", f"sandbox-{project_id}"])
        if result.returncode == 0:
            with self.lock:
                self.containers[project_id]["status"] = "running"
            return {"status": "success"}
        return {"status": "error", "message": result.stderr}

    def stop_container(self, project_id: str) -> dict:
        """停止容器"""
        with self.lock:
            if project_id not in self.containers:
                return {"status": "error", "message": "容器不存在"}

        result = self._run_cmd([self.runtime, "stop", f"sandbox-{project_id}"])
        if result.returncode == 0:
            with self.lock:
                self.containers[project_id]["status"] = "stopped"
            return {"status": "success"}
        return {"status": "error", "message": result.stderr}

    def remove_container(self, project_id: str) -> dict:
        """删除容器"""
        with self.lock:
            if project_id not in self.containers:
                return {"status": "error", "message": "容器不存在"}
            container_id = self.containers[project_id]["container_id"]

        # 先停止再删除
        self._run_cmd([self.runtime, "stop", container_id])
        self._run_cmd([self.runtime, "rm", container_id])

        with self.lock:
            del self.containers[project_id]

        return {"status": "success"}

    def exec_command(self, project_id: str, cmd: list, timeout: int = 30) -> dict:
        """在项目容器内执行命令（服务控制台入口：Redis-cli / SQL 客户端等）。

        容器名与项目绑定（sandbox-{project_id}）；deploy 部署的容器名为 sandbox-{name}，需去掉前缀。
        """
        if project_id.startswith("deploy-"):
            container = f"sandbox-{project_id[len('deploy-'):]}"
        else:
            container = f"sandbox-{project_id}"
        try:
            result = self._run_cmd([self.runtime, "exec", container, *cmd], timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": f"命令执行超时（{timeout}s）"}
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "").strip()
            return {"status": "error", "message": err or f"命令执行失败（exit {result.returncode}）"}
        # 部分命令（nginx -v / -t 等）把结果写到 stderr，成功时合并返回，避免输出丢失
        merged = result.stdout or ""
        if result.stderr:
            merged += result.stderr
        return {"status": "success", "output": merged}

    def get_status(self, project_id: str) -> dict | None:
        """获取容器状态"""
        with self.lock:
            if project_id not in self.containers:
                return None
            return self.containers[project_id].copy()

    def get_all(self) -> dict[str, dict]:
        """获取所有容器状态"""
        with self.lock:
            return {k: v.copy() for k, v in self.containers.items()}

    def get_logs(self, project_id: str, tail: int = 100) -> list[str]:
        """获取容器日志"""
        result = self._run_cmd([self.runtime, "logs", "--tail", str(tail), f"sandbox-{project_id}"])
        if result.returncode != 0:
            return []
        return result.stdout.strip().split("\n") if result.stdout else []

    def get_ports(self, project_id: str) -> list[dict]:
        """获取端口映射"""
        result = self._run_cmd([self.runtime, "port", f"sandbox-{project_id}"])
        ports = []
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        container_port = parts[0]
                        host_port = parts[1] if len(parts) > 1 else "0"
                        ports.append({"container": container_port, "host": host_port})
        return ports


# 全局实例
process_manager = ContainerManager(runtime="podman")
