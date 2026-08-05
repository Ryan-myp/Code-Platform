#!/usr/bin/env python3
"""Platform v9.0 Extended API - 研发增强/内容创作/运营分析/办公效率"""

import json
import hashlib
import logging
import os
import re
import socket
import subprocess
import threading
import time
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm

logger = logging.getLogger(__name__)

router = APIRouter()


# ══════════════════════════════════════════════════════════════
# Phase 2: 研发增强
# ══════════════════════════════════════════════════════════════

class CodeGenRequest(BaseModel):
    language: str = "python"
    prompt: str
    model: str = ""

class CodeReviewRequest(BaseModel):
    language: str = "python"
    code: str
    model: str = ""

class CodeImproveRequest(BaseModel):
    """根据代码审查意见修改代码"""
    language: str = "python"
    code: str
    review: str
    model: str = ""

class PipelineCreate(BaseModel):
    name: str
    description: str = ""
    type: str = "ci"
    config: dict = {}


class DeployRequest(BaseModel):
    """一键部署请求：代码落盘 + 构建镜像 + 沙箱容器运行"""
    name: str
    language: str = "python"
    code: str
    requirement_id: str = ""


# ── 部署流水线（真实执行：podman 构建镜像 → 启动沙箱容器） ──────
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
DEPLOY_BASE_PORT = 18080
_PODMAN_LOCK = threading.Lock()

# 代码 import 顶层模块 → pip 包名（用于生成 requirements.txt）
_PIP_PACKAGES = {
    "fastapi": "fastapi", "uvicorn": "uvicorn", "flask": "flask",
    "requests": "requests", "httpx": "httpx", "pydantic": "pydantic",
    "sqlalchemy": "sqlalchemy", "numpy": "numpy", "pandas": "pandas",
    "aiohttp": "aiohttp", "redis": "redis", "openai": "openai",
    "dotenv": "python-dotenv", "bs4": "beautifulsoup4", "PIL": "pillow",
    "yaml": "pyyaml", "flask_cors": "flask-cors", "jwt": "pyjwt",
    "celery": "celery", "django": "django", "click": "click",
}


def _detect_python_deps(code: str) -> list:
    """从代码 import 语句提取 pip 依赖（Web 服务基础依赖兜底）。"""
    deps = {"fastapi", "uvicorn"}
    for m in re.finditer(r"^\s*(?:from|import)\s+([a-zA-Z_][\w\.]*)", code, re.M):
        top = m.group(1).split(".")[0]
        if top in _PIP_PACKAGES:
            deps.add(_PIP_PACKAGES[top])
    return sorted(deps)


def _gen_dockerfile() -> str:
    """生成 Python 服务 Dockerfile（容器内固定 8000 端口）。"""
    return (
        "FROM python:3.11-slim\n"
        "WORKDIR /app\n"
        "COPY main.py .\n"
        "COPY requirements.txt .\n"
        "RUN pip install --no-cache-dir -r requirements.txt\n"
        "EXPOSE 8000\n"
        'CMD ["python", "main.py"]\n'
    )


def _find_free_port() -> int:
    """从 DEPLOY_BASE_PORT 起扫描空闲端口（部署用）。"""
    with _PODMAN_LOCK:
        for port in range(DEPLOY_BASE_PORT, DEPLOY_BASE_PORT + 300):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) != 0:
                    return port
    return DEPLOY_BASE_PORT


def _update_run_log(run_id: str, log: str) -> None:
    """更新流水线运行日志（渐进式写入）。"""
    conn = get_db()
    try:
        conn.execute("UPDATE pipeline_runs SET log=? WHERE id=?", (log, run_id))
        conn.commit()
    finally:
        conn.close()


def _finish_run(run_id: str, pid: str, status: str, log: str) -> None:
    """结束运行：写状态/日志并同步流水线状态。"""
    finished = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            "UPDATE pipeline_runs SET status=?, log=?, finished_at=? WHERE id=?",
            (status, log, finished, run_id),
        )
        conn.execute(
            "UPDATE pipelines SET status=?, last_run=? WHERE id=?",
            (status, finished, pid),
        )
        conn.commit()
    finally:
        conn.close()


def _safe_slug(name: str) -> str:
    """容器/镜像名安全化：Docker 标签仅允许 [a-zA-Z0-9][a-zA-Z0-9_.-]*，
    中文/特殊字符名用 md5 摘要后缀生成合法 slug（原名保留用于展示）。"""
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name):
        return name
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()[:8]
    return f"svc-{digest}"


_INFRA_ERROR_MARKERS = (
    "cannot connect to podman", "connection refused",
    "no space left", "command not found", "permission denied",
    "cannot connect to the docker daemon", "docker daemon is not running",
    "executable file not found",
)


def _is_infra_error(msg: str) -> bool:
    """是否为基础设施故障（Docker/Podman 环境问题）——此类错误 AI 改代码无法解决，跳过修复。"""
    low = (msg or "").lower()
    return any(m in low for m in _INFRA_ERROR_MARKERS)


def _deploy_once(name, project_dir, port, image_tag, container_name, append, step_run, cfg=None) -> tuple:
    """单轮部署：构建镜像 → 启动依赖容器 → 启动服务容器 → 健康检查。返回 (ok, info)。"""
    cfg = cfg or {}
    # 阶段 1.5：外部依赖容器（Redis/MySQL）。podman 5.x 已移除 --link，
    # 改用自定义网络 + --network-alias（同网络容器名/别名可直接解析）
    deps = cfg.get("dependencies") or {}
    net = f"{container_name}-net"
    if deps:
        append(f"  - 依赖: 准备网络 {net} …")
        step_run(["podman", "rm", "-f", container_name], timeout=30)
        step_run(["podman", "network", "rm", "-f", net], timeout=30)
        ok, out = step_run(["podman", "network", "create", net], timeout=30)
        if not ok and "already exists" not in (out or "").lower():
            return False, f"创建依赖网络失败: {out[-300:]}"
    if deps.get("redis"):
        dep = f"{container_name}-redis"
        append(f"  - 依赖: 启动 Redis 容器 {dep} …")
        step_run(["podman", "rm", "-f", dep], timeout=30)
        ok, out = step_run([
            "podman", "run", "-d", "--name", dep, "--network", net, "--network-alias", "redis",
            "docker.io/library/redis:7-alpine",
        ], timeout=300)
        if not ok:
            return False, f"Redis 依赖容器启动失败: {out[-300:]}"
    if deps.get("mysql"):
        dep = f"{container_name}-mysql"
        pw = deps.get("mysql_password", "platform123")
        db = deps.get("mysql_database", "platform")
        img = deps.get("mysql_image", "docker.io/library/mysql:8")  # 国内网络可配置 mirror 源
        append(f"  - 依赖: 启动 MySQL 容器 {dep} …（首次拉取镜像较慢）")
        step_run(["podman", "rm", "-f", dep], timeout=30)
        ok, out = step_run([
            "podman", "run", "-d", "--name", dep, "--network", net, "--network-alias", "mysql",
            "-e", f"MYSQL_ROOT_PASSWORD={pw}", "-e", f"MYSQL_DATABASE={db}",
            img,
        ], timeout=600)
        if not ok:
            return False, f"MySQL 依赖容器启动失败: {out[-300:]}"
        append("  - 依赖: 等待 MySQL 初始化（约 20-40s）…")
        ready = False
        for _ in range(60):
            time.sleep(2)
            ok2, _ = step_run(["podman", "exec", dep, "mysqladmin", "ping", "-uroot", f"-p{pw}", "--silent"], timeout=10)
            if ok2:
                ready = True
                break
        if not ready:
            return False, "MySQL 依赖容器初始化超时"

    # 阶段 2：构建镜像
    append(f"  - 构建镜像: podman build -t {image_tag} …（首次拉取基础镜像较慢）")
    ok, out = step_run(["podman", "build", "-t", image_tag, project_dir])
    if out:
        lines = out.splitlines()
        tail = lines[-3:] if len(lines) > 3 else lines
        append("      " + "\n      ".join(tail))
    if not ok:
        return False, f"镜像构建失败: {out[-400:]}"
    append("  - 构建镜像: 完成 ✓")
    # 阶段 3：启动沙箱容器（先清理同名旧容器，支持修复重部署）
    step_run(["podman", "rm", "-f", container_name], timeout=30)
    append(f"  - 启动容器: podman run -d --name {container_name} -p {port}:8000" + (f" --network {net}" if deps else ""))
    cmd = ["podman", "run", "-d", "--name", container_name, "-p", f"{port}:8000"]
    if deps:
        cmd += ["--network", net]
        cmd += ["-e", "REDIS_URL=redis://redis:6379/0"] if deps.get("redis") else []
        cmd += ["-e", f"DATABASE_URL=mysql+aiomysql://root:{deps.get('mysql_password', 'platform123')}@mysql:3306/{deps.get('mysql_database', 'platform')}?charset=utf8mb4"] if deps.get("mysql") else []
    cmd += [image_tag]
    ok, out = step_run(cmd)
    if out:
        append("      " + out)
    if not ok:
        return False, f"容器启动失败: {out[-400:]}"
    # 阶段 4：健康检查（轮询端口，最多 60s）
    append(f"  - 健康检查: http://localhost:{port}/ …")
    code = "000"
    for _ in range(30):
        time.sleep(2)
        try:
            r = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://localhost:{port}/"],
                capture_output=True, text=True, timeout=5,
            )
            code = r.stdout.strip()
            if code and code != "000":
                return True, code
        except Exception:
            pass
    return False, "健康检查未通过，服务可能启动失败（查看容器日志定位问题）"


def _register_sandbox(slug, port, project_dir, image_tag, cfg, display_name=None) -> None:
    """把部署服务注册到沙箱管理（可在沙箱页停止/删除/查看日志）。slug 为容器安全名，display_name 为展示名。"""
    name = display_name or slug
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO sandbox_projects (id, name, status, port, project_dir, image, ports, config, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=?, port=?, project_dir=?, image=?, ports=?, config=?, updated_at=?",
            (f"deploy-{slug}", name, "running", port, project_dir, image_tag, json.dumps([port]), json.dumps(cfg, ensure_ascii=False), now, now,
             "running", port, project_dir, image_tag, json.dumps([port]), json.dumps(cfg, ensure_ascii=False), now),
        )
        conn.commit()
    finally:
        conn.close()


def _extract_code_block(text: str) -> str:
    """从 LLM 输出提取完整代码（清洗 markdown 围栏）。

    - 优先提取所有 ``` 围栏代码块，取最长的一个（容忍前置解释文字/前导换行）
    - 无围栏时若全文无明显解释性文字则原样返回
    """
    text = (text or "").strip()
    if not text:
        return ""
    blocks = re.findall(r"```[a-zA-Z]*\s*\n(.*?)```", text, re.DOTALL)
    if blocks:
        return max(blocks, key=len).strip()
    clean = re.sub(r"^```[a-zA-Z]*\s*$", "", text).strip()
    # 无明显解释性文字才视为纯代码（避免把 LLM 的说明文字写入 main.py）
    if re.search(r"[，。；：、]|以下是|修复建议|问题|错误|请提供|您好|需要", clean[:200]):
        return ""
    return clean


def _fix_rounds(pid, run_id, cfg, log, append, step_run, initial_error, max_rounds=3) -> bool:
    """AI 诊断修复循环：错误日志 → LLM 修改 main.py → 重建 → 重启 → 健康检查。

    每轮把最新错误日志喂给 LLM，最多 max_rounds 轮；成功返回 True。
    """
    name = cfg["service_name"]
    slug = _safe_slug(name)
    project_dir = cfg["project_dir"]
    port = cfg["port"]
    image_tag = f"app-{slug}"
    container_name = f"sandbox-{slug}"
    main_file = os.path.join(project_dir, "main.py")
    last_error = initial_error
    for round_no in range(1, max_rounds + 1):
        append(f"── 第 {round_no}/{max_rounds} 轮 AI 诊断修复 ──")
        # 收集诊断信息：上轮错误 + 容器日志
        _, clogs = step_run(["podman", "logs", "--tail", "80", container_name], timeout=10)
        diag = last_error
        if clogs:
            diag += "\n【容器日志】\n" + clogs[-2500:]
        try:
            with open(main_file, encoding="utf-8") as f:
                code = f.read()
        except Exception as e:
            append(f"  - ❌ 读取代码失败: {e}")
            return False
        append("  - LLM 诊断失败原因并生成修复代码（约 10-60 秒）…")
        sys_prompt = (
            "你是一个资深的 Python 开发工程师与 SRE。根据下面的部署错误日志和当前 main.py 代码，"
            "定位问题根因并输出修复后的完整 main.py（必须是可直接运行的 Web 服务，监听 0.0.0.0:8000，"
            "提供 FastAPI 应用，可包含 Flask/Django 等，但根路径 / 必须返回 200）。"
            "只返回修复后的完整代码，放在 ```python 代码块中，不要任何解释文字。"
        )
        prompt = f"【部署错误日志】\n{diag}\n\n【当前 main.py】\n{code}"
        try:
            fix = call_llm(sys_prompt, prompt)
        except Exception as e:
            append(f"  - ❌ LLM 调用失败: {e}（可在系统配置-模型列表中设置模型 API Key）")
            return False
        fixed = _extract_code_block(fix)
        if not fixed:
            # LLM 可能返回了解释文字/空内容：强制要求只输出代码块，再试一次
            append("  - ⚠ LLM 未按格式输出代码，要求重新输出…")
            try:
                fix2 = call_llm(
                    sys_prompt,
                    prompt + "\n\n（你上一次没有输出代码块。请只输出 ```python 围栏包裹的完整代码，不要任何解释文字。）",
                )
            except Exception as e:
                append(f"  - ❌ LLM 重试调用失败: {e}")
                return False
            fixed = _extract_code_block(fix2)
            if not fixed:
                append("  - ❌ 未解析到修复代码，停止修复")
                return False
            append("  - 重新输出成功，继续修复…")
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(fixed)
        append(f"  - 修复代码已落盘（{len(fixed)} 字节），重新构建部署…")
        ok, info = _deploy_once(name, project_dir, port, image_tag, container_name, append, step_run, cfg)
        if ok:
            append(f"  - 第 {round_no} 轮修复成功 ✓（HTTP {info}）访问地址: http://localhost:{port}")
            _register_sandbox(slug, port, project_dir, image_tag, cfg, display_name=name)
            return True
        if _is_infra_error(info):
            append("  - ⚠ 检测到基础设施故障（Docker/Podman 环境问题），AI 修复无法解决，停止修复")
            return False
        append(f"  - 第 {round_no} 轮仍失败: {info[-300:]}")
        last_error = info
    append("  - ❌ AI 修复达到轮次上限，请人工查看日志处理")
    return False


def _exec_deploy_pipeline(pid: str, run_id: str, cfg: dict) -> None:
    """后台执行部署流水线：构建镜像 → 启动沙箱容器 → 健康检查；失败自动进入 AI 修复循环。"""
    name = cfg["service_name"]
    slug = _safe_slug(name)
    project_dir = cfg["project_dir"]
    port = cfg["port"]
    image_tag = f"app-{slug}"
    container_name = f"sandbox-{slug}"
    log: list = []

    def append(line: str) -> None:
        log.append(line)
        _update_run_log(run_id, "\n".join(log))

    def step_run(cmd: list, timeout: int = 900) -> tuple:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
        return (r.returncode == 0), (r.stdout or r.stderr or "").strip()

    try:
        append(f"[{datetime.now().isoformat()[:19]}] 部署流水线「{name}」开始执行（deploy 类型 · 真实构建）")
        # 阶段 1：检出代码
        main_file = os.path.join(project_dir, "main.py")
        if not os.path.exists(main_file):
            raise RuntimeError("main.py 不存在，无法构建")
        append(f"  - 检出代码: 就绪（artifacts/{name}/，{os.path.getsize(main_file)} 字节）")
        ok, info = _deploy_once(name, project_dir, port, image_tag, container_name, append, step_run, cfg)
        if not ok:
            append(f"  - ❌ {info}")
            if _is_infra_error(info):
                # 环境故障（podman 未启动/磁盘满等）：AI 改代码无法解决，直接终止避免无效修复轮次
                append("  - ⚠ 检测到基础设施故障（Docker/Podman 环境问题），AI 修复无法解决，请检查容器环境后重新部署")
                _finish_run(run_id, pid, "failed", "\n".join(log))
                return
            if cfg.get("auto_fix", True):
                append("  - ⚡ 失败自动修复已开启，进入 AI 诊断修复…")
                if _fix_rounds(pid, run_id, cfg, log, append, step_run, info, max_rounds=3):
                    _finish_run(run_id, pid, "success", "\n".join(log))
                else:
                    _finish_run(run_id, pid, "failed", "\n".join(log))
                return
            raise RuntimeError(info)
        append(f"  - 健康检查: 通过 ✓（HTTP {info}）")
        append(f"  - 部署完成 ✓ 访问地址: http://localhost:{port}")
        _register_sandbox(slug, port, project_dir, image_tag, cfg, display_name=name)
        _finish_run(run_id, pid, "success", "\n".join(log))
    except Exception as e:
        append(f"  - ❌ {e}")
        _finish_run(run_id, pid, "failed", "\n".join(log))


def _exec_auto_fix(pid: str, run_id: str, cfg: dict) -> None:
    """手动触发 AI 诊断修复：拉取现有容器日志 → 修复循环 → 重建部署。"""
    name = cfg["service_name"]
    slug = _safe_slug(name)
    container_name = f"sandbox-{slug}"
    log: list = []

    def append(line: str) -> None:
        log.append(line)
        _update_run_log(run_id, "\n".join(log))

    def step_run(cmd: list, timeout: int = 900) -> tuple:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
        return (r.returncode == 0), (r.stdout or r.stderr or "").strip()

    try:
        append(f"[{datetime.now().isoformat()[:19]}] 手动触发 AI 诊断修复「{name}」")
        _, clogs = step_run(["podman", "logs", "--tail", "100", container_name], timeout=10)
        initial = clogs if clogs else "容器无日志输出或尚未启动"
        if _fix_rounds(pid, run_id, cfg, log, append, step_run, initial, max_rounds=3):
            _finish_run(run_id, pid, "success", "\n".join(log))
        else:
            _finish_run(run_id, pid, "failed", "\n".join(log))
    except Exception as e:
        append(f"  - ❌ {e}")
        _finish_run(run_id, pid, "failed", "\n".join(log))


@router.post("/api/deployments")
async def create_deployment(data: DeployRequest, current_user: dict = require_auth()):
    """一键部署：AI 生成的代码落盘 → 创建部署流水线 → 后台真实构建并启动沙箱容器。"""
    if data.language != "python":
        raise HTTPException(400, "当前沙箱部署仅支持 Python 服务（后续支持更多语言）")
    code = (data.code or "").strip()
    if not code:
        raise HTTPException(400, "代码不能为空")
    name = re.sub(r"[^\w\-]+", "-", (data.name or "").strip()).strip("-") or "app"
    if len(name) > 40:
        name = name[:40]
    pid, run_id, port = _create_deploy_pipeline(name, code, data.requirement_id, current_user["username"])
    return {"ok": True, "pipeline_id": pid, "run_id": run_id, "name": name, "port": port, "status": "running"}


def _create_deploy_pipeline(name: str, code: str, requirement_id: str, username: str) -> tuple:
    """代码落盘 → 创建 deploy 流水线 → 后台线程真实构建部署。返回 (pid, run_id, port)。

    供「一键部署」与「一句话全自动」共用。
    """
    # 清洗 markdown 代码围栏（AI 输出可能带 ```python ... ```）
    code = re.sub(r"^```[a-zA-Z]*\s*\n?", "", code).rstrip()
    code = re.sub(r"\n?```\s*$", "", code).strip()
    # 1. 代码落盘到 artifacts/<name>/
    project_dir = os.path.join(ARTIFACTS_DIR, name)
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(code)
    with open(os.path.join(project_dir, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(_detect_python_deps(code)) + "\n")
    with open(os.path.join(project_dir, "Dockerfile"), "w", encoding="utf-8") as f:
        f.write(_gen_dockerfile())
    # 2. 创建部署流水线（type=deploy）
    pid = f"pipe_{uuid.uuid4().hex[:12]}"
    port = _find_free_port()
    desc = f"需求 {requirement_id} 自动部署" if requirement_id else f"{name} 沙箱部署"
    cfg = {"service_name": name, "project_dir": project_dir, "port": port, "requirement_id": requirement_id, "auto_fix": True}
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO pipelines (id, name, description, type, config, status, last_run, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, f"部署 {name}", desc, "deploy", json.dumps(cfg, ensure_ascii=False),
             "running", now, username, now, now),
        )
        conn.execute(
            "INSERT INTO pipeline_runs (id, pipeline_id, status, log, started_at) VALUES (?,?,?,?,?)",
            (run_id, pid, "running", f"[{now[:19]}] 部署任务已创建，等待执行…", now),
        )
        conn.commit()
    finally:
        conn.close()
    # 3. 后台线程真实执行（不阻塞请求）
    threading.Thread(target=_exec_deploy_pipeline, args=(pid, run_id, cfg), daemon=True).start()
    return pid, run_id, port


# ══════════════════════════════════════════════════════════════
# 一句话全自动：PRD → 审查 → 技术方案 → 测试 → 代码 → 审查 → 部署
# ══════════════════════════════════════════════════════════════

AUTO_STAGES = [
    ("prd", "PRD 生成"),
    ("review", "PRD 审查"),
    ("td", "技术方案"),
    ("test", "测试用例"),
    ("code", "代码生成"),
    ("review_code", "代码审查"),
]


class AutoRunRequest(BaseModel):
    name: str = ""
    description: str
    language: str = "python"
    deploy: bool = True
    target_stage: str = "deploy"  # prd/review/td/test/code/review_code/deploy


class _AutoRunStopped(Exception):
    """用户手动停止信号"""


def _auto_run_update(run_id: str, **fields) -> None:
    fields["updated_at"] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in fields)
    conn = get_db()
    try:
        conn.execute(f"UPDATE auto_runs SET {sets} WHERE id=?", (*fields.values(), run_id))
        conn.commit()
    finally:
        conn.close()


def _auto_run_append(run_id: str, line: str) -> None:
    conn = get_db()
    try:
        row = conn.execute("SELECT log FROM auto_runs WHERE id=?", (run_id,)).fetchone()
        cur = (row["log"] if row else "") or ""
        # 日志上限 200 行，防止无限增长
        lines = (cur + line + "\n").split("\n")
        cur = "\n".join(lines[-200:])
        conn.execute("UPDATE auto_runs SET log=?, updated_at=? WHERE id=?", (cur, datetime.now().isoformat(), run_id))
        conn.commit()
    finally:
        conn.close()


def _auto_run_is_stopping(run_id: str) -> bool:
    conn = get_db()
    try:
        row = conn.execute("SELECT status FROM auto_runs WHERE id=?", (run_id,)).fetchone()
        return bool(row and row["status"] == "stopping")
    finally:
        conn.close()


def _extract_code_block(text: str) -> str:
    """从 LLM 输出中提取代码（去除 markdown 代码围栏）"""
    m = re.search(r"```[a-zA-Z]*\s*\n(.*?)```", text or "", re.S)
    return m.group(1).strip() if m else (text or "").strip()


def _auto_run_worker(run_id: str, req_id: str, name: str, description: str,
                     language: str, deploy: bool, target_stage: str, username: str) -> None:
    """后台执行全自动流水线：一句话需求 → 6 阶段产物 → 自动部署。"""
    import asyncio

    from prd_engine import CODE_SYSTEM, PRD_SYSTEM, REVIEW_SYSTEM, TD_SYSTEM, TEST_SYSTEM, save_pipeline_output

    def log(line: str) -> None:
        _auto_run_append(run_id, f"[{datetime.now().isoformat()[:19]}] {line}")

    def progress(stage: str, status: str) -> None:
        _auto_run_update(run_id, current_stage=stage,
                         stage_progress=json.dumps(progress_map, ensure_ascii=False))

    def check_stop() -> None:
        if _auto_run_is_stopping(run_id):
            raise _AutoRunStopped()

    def run_stage(stage_key: str, label: str, idx: int, prompt_fn) -> str:
        """执行单个阶段：标记进行中 → 调用 LLM → 保存产物 → 标记完成。返回产物内容。"""
        check_stop()
        progress_map[stage_key] = "running"
        progress(stage_key, "running")
        log(f"⏳ 阶段 {idx}/6：{label}…")
        content = prompt_fn()
        asyncio.run(save_pipeline_output(req_id, {"stage": stage_key, "content": content}))
        progress_map[stage_key] = "done"
        progress(stage_key, "done")
        log(f"✅ {label}完成（{len(content)} 字）")
        return content

    progress_map: dict = {}
    stage_idx = {s[0]: i for i, s in enumerate(AUTO_STAGES, 1)}
    try:
        started = time.time()
        log(f"🎯 一句话需求：{description[:150]}")
        results = {}

        # 1. PRD 生成
        results["prd"] = run_stage("prd", "PRD 生成", 1, lambda: call_llm(PRD_SYSTEM, description, max_tokens=4000))
        if target_stage == "prd":
            return

        # 2. PRD 审查
        results["review"] = run_stage("review", "PRD 审查", 2, lambda: call_llm(REVIEW_SYSTEM, results["prd"], max_tokens=4000))
        if target_stage == "review":
            return

        # 3. 技术方案
        results["td"] = run_stage("td", "技术方案", 3, lambda: call_llm(TD_SYSTEM, results["prd"], max_tokens=6000))
        if target_stage == "td":
            return

        # 4. 测试用例
        results["test"] = run_stage("test", "测试用例", 4,
                                     lambda: call_llm(TEST_SYSTEM, f"PRD:\n{results['prd']}\n\n技术方案:\n{results['td']}", max_tokens=4000))
        if target_stage == "test":
            return

        # 5. 代码生成（提取纯代码，供部署落盘）
        raw_code = run_stage("code", "代码生成", 5,
                             lambda: call_llm(CODE_SYSTEM, f"语言: {language}\n任务类型: code\n\n技术方案:\n{results['td']}", max_tokens=8000))
        results["code"] = _extract_code_block(raw_code)
        if target_stage == "code":
            return

        # 6. 代码审查
        review_system = (f"你是一位资深的{language}代码审查专家。审查以下代码，给出改进建议，包括："
                         "1.代码质量 2.潜在bug 3.性能优化 4.安全建议。")
        results["review_code"] = run_stage("review_code", "代码审查", 6,
                                            lambda: call_llm(review_system, results["code"]))
        log(f"⏱ 6 个阶段全部完成，耗时 {time.time() - started:.0f}s")
        if target_stage == "review_code":
            return

        # 7. 自动部署
        if deploy:
            check_stop()
            progress_map["deploy"] = "running"
            progress("deploy", "running")
            log("🚀 阶段 7/7：自动部署到沙箱容器…")
            safe = re.sub(r"[^\w\-]+", "-", name).strip("-") or "app"
            pid, run2, port = _create_deploy_pipeline(safe[:40], results["code"], req_id, username)
            _auto_run_update(run_id, pipeline_id=pid, port=port)
            # 等待部署流水线完成（最多 10 分钟，期间可停止）
            deadline = time.time() + 600
            deploy_status = "running"
            while time.time() < deadline:
                check_stop()
                conn = get_db()
                try:
                    row = conn.execute("SELECT status FROM pipeline_runs WHERE id=?", (run2,)).fetchone()
                finally:
                    conn.close()
                deploy_status = row["status"] if row else "unknown"
                if deploy_status != "running":
                    break
                time.sleep(3)
            progress_map["deploy"] = deploy_status
            progress("deploy", deploy_status)
            if deploy_status == "success":
                log(f"✅ 部署成功！访问地址：http://localhost:{port}")
            else:
                log(f"⚠️ 部署状态：{deploy_status}（可到流水线页面查看构建日志）")
            if deploy_status != "success":
                raise RuntimeError(f"部署未成功（{deploy_status}），请到流水线页面查看日志")
        else:
            progress_map["deploy"] = "skipped"

        _auto_run_update(run_id, status="success", current_stage="done",
                         stage_progress=json.dumps(progress_map, ensure_ascii=False),
                         finished_at=datetime.now().isoformat())
        log("🎉 一句话全自动完成！所有产物已保存到需求，可到 AI 工作台查看/微调。")
    except _AutoRunStopped:
        _auto_run_update(run_id, status="stopped", current_stage="stopped",
                         stage_progress=json.dumps(progress_map, ensure_ascii=False),
                         finished_at=datetime.now().isoformat())
        log("⏹ 已手动停止")
    except Exception as e:
        _auto_run_update(run_id, status="failed", error=str(e), current_stage="failed",
                         stage_progress=json.dumps(progress_map, ensure_ascii=False),
                         finished_at=datetime.now().isoformat())
        log(f"❌ 流程失败：{e}")


@router.post("/api/auto-run")
async def create_auto_run(data: AutoRunRequest, current_user: dict = require_auth()):
    """一句话全自动：创建需求 → 后台串行执行 6 阶段 → 自动部署到沙箱。"""
    desc = (data.description or "").strip()
    if not desc:
        raise HTTPException(400, "请描述你想要实现的功能")
    if data.target_stage not in [s[0] for s in AUTO_STAGES] + ["deploy"]:
        raise HTTPException(400, "无效的目标阶段")
    name = (data.name or "").strip() or desc[:30]
    req_id = f"req_{uuid.uuid4().hex[:12]}"
    run_id = f"arun_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO requirements (id, name, description, status, priority, creator, version, created_at, updated_at, active) "
            "VALUES (?,?,?,?,?,?,?,?,?,1)",
            (req_id, name, desc, "in_progress", "P1", current_user["username"], 1, now, now),
        )
        conn.execute(
            "INSERT INTO auto_runs (id, requirement_id, name, language, status, current_stage, stage_progress, log, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, req_id, name, data.language, "running", "prd", "{}",
             f"[{now[:19]}] 🚀 一句话全自动流水线已启动", current_user["username"], now, now),
        )
        conn.commit()
    finally:
        conn.close()
    threading.Thread(target=_auto_run_worker, daemon=True,
                     args=(run_id, req_id, name, desc, data.language, data.deploy, data.target_stage, current_user["username"])).start()
    return {"ok": True, "run_id": run_id, "requirement_id": req_id, "status": "running"}


@router.get("/api/auto-runs/{run_id}")
async def get_auto_run(run_id: str, current_user: dict = require_auth()):
    """查询单条全自动运行进度"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM auto_runs WHERE id=?", (run_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(404, "未找到运行记录")
    d = dict(row)
    d["stage_progress"] = json.loads(d.get("stage_progress") or "{}")
    return d


@router.post("/api/auto-runs/{run_id}/stop")
async def stop_auto_run(run_id: str, current_user: dict = require_auth()):
    """停止全自动运行（阶段间生效）"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM auto_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(404, "未找到运行记录")
        if row["status"] == "running":
            conn.execute("UPDATE auto_runs SET status='stopping', updated_at=? WHERE id=?",
                         (datetime.now().isoformat(), run_id))
            conn.commit()
    finally:
        conn.close()
    return {"ok": True, "status": "stopping"}


@router.post("/api/code/generate")
async def generate_code(data: CodeGenRequest, current_user: dict = require_auth()):
    """AI 代码生成"""
    try:
        system_prompt = f"""你是一位资深{data.language}开发工程师，拥有10年+生产级项目经验。

代码生成要求：
1. 生产级质量：包含错误处理、输入验证、边界条件处理
2. 可维护性：清晰的变量命名、适当的注释、单一职责原则
3. 安全性：防止注入攻击、敏感信息不硬编码、使用参数化查询
4. 性能意识：避免不必要的循环、合理使用缓存、注意内存管理
5. 测试友好：函数粒度适中、依赖可注入、纯函数优先

输出格式：
```{data.language}
// 完整可运行代码
```
后面附简要说明（3-5行）：核心技术选型、时间复杂度、使用方式

只返回代码和说明，不要冗余解释。"""
        result = call_llm(system_prompt, data.prompt)

        gen_id = f"cg_{uuid.uuid4().hex[:12]}"
        # 独立连接：避免 LLM 调用期间其他函数关闭线程复用连接
        from common.db import get_db_context
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO code_generations (id, language, prompt, result, model) VALUES (?,?,?,?,?)",
                (gen_id, data.language, data.prompt, result, data.model)
            )
        return {"ok": True, "id": gen_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"代码生成失败: {str(e)}")


@router.get("/api/code/generations")
async def list_code_generations(current_user: dict = require_auth()):
    """获取代码生成历史"""
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM code_generations ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.post("/api/code/review")
async def review_code(data: CodeReviewRequest, current_user: dict = require_auth()):
    """AI 代码审查"""
    try:
        system_prompt = f"""你是资深{data.language}代码审查专家，负责把关生产级代码质量。

审查维度（按严重程度排列）：
🔴 严重（必须修复）：
1. 安全漏洞：注入攻击、越权访问、敏感信息泄露、不安全的反序列化
2. 逻辑错误：边界条件错误、空指针/None引用、竞态条件、死锁风险
3. 数据问题：数据丢失风险、事务不一致、类型转换错误

🟡 重要（应该修复）：
4. 性能瓶颈：N+1查询、不必要的循环、内存泄漏、阻塞IO
5. 可维护性：过长函数、过深嵌套、重复代码、魔法数字

🟢 建议（可选优化）：
6. 代码风格：命名规范、注释质量、代码组织
7. 最佳实践：设计模式运用、库函数使用建议

输出格式：
## 审查总结（1-2句整体评价）
## 问题清单
### 🔴 [严重] 问题标题
- 位置：第X行 / 函数名
- 问题：具体描述
- 风险：可能导致什么后果
- 修复：给出修改代码

（每个问题独立一节，按严重程度排序，最多列出10个问题）"""
        result = call_llm(system_prompt, data.code)

        review_id = f"cr_{uuid.uuid4().hex[:12]}"
        # 独立连接：避免 LLM 调用期间其他函数关闭线程复用连接
        from common.db import get_db_context
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO code_reviews (id, language, code, result, model) VALUES (?,?,?,?,?)",
                (review_id, data.language, data.code, result, data.model)
            )
        return {"ok": True, "id": review_id, "result": result}
    except Exception as e:
        logger.error(f"[review_code] {traceback.format_exc()}")
        raise HTTPException(500, f"代码审查失败: {str(e)}")


@router.post("/api/code/improve")
async def improve_code(data: CodeImproveRequest, current_user: dict = require_auth()):
    """AI 根据代码审查意见修改代码：审查结果 → 修改后的完整代码。"""
    try:
        system_prompt = (
            f"你是一位资深{data.language}开发工程师，负责根据审查意见修复代码。\n\n"
            "修复原则：\n"
            "1. 逐一处理所有审查意见中标记为🔴严重和🟡重要的问题\n"
            "2. 修复后代码必须保持原有功能不变，不引入新bug\n"
            "3. 每次修改标注修复了哪个问题（行内注释 // fix: ...）\n"
            "4. 如某个建议因架构限制无法采纳，标注说明原因\n\n"
            "输出格式：\n"
            "## 修改后的完整代码\n"
            "```{data.language}\n...\n```\n"
            "## 修改说明（表格格式）\n"
            "| 问题 | 修复方式 | 影响范围 |\n"
            "|------|----------|----------|\n"
            "| ... | ... | ... |"
        )
        prompt = f"【原始代码】\n{data.code}\n\n【代码审查意见】\n{data.review}"
        result = call_llm(system_prompt, prompt)
        return {"ok": True, "result": result}
    except Exception as e:
        logger.error(f"[code_improve] {traceback.format_exc()}")
        raise HTTPException(500, f"代码修改失败: {str(e)}")


@router.get("/api/code/reviews")
async def list_code_reviews(current_user: dict = require_auth()):
    """获取代码审查历史"""
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM code_reviews ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


# Pipeline CRUD
@router.get("/api/pipelines")
async def list_pipelines(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM pipelines WHERE active=1 ORDER BY created_at DESC").fetchall():
            p = dict(row)
            p["config"] = json.loads(p.get("config", "{}"))
            # deploy 流水线：补充关联需求名称（前端卡片展示部署了什么）
            if p["type"] == "deploy" and p["config"].get("requirement_id"):
                req = conn.execute(
                    "SELECT name FROM requirements WHERE id=? AND active=1", (p["config"]["requirement_id"],)
                ).fetchone()
                if req:
                    p["config"]["requirement_name"] = req["name"]
            # 最近一次运行摘要
            run = conn.execute(
                "SELECT status, started_at, finished_at FROM pipeline_runs WHERE pipeline_id=? ORDER BY started_at DESC LIMIT 1", (p["id"],)
            ).fetchone()
            p["last_run"] = dict(run) if run else None
            items.append(p)
        return items
    finally:
        conn.close()


@router.post("/api/pipelines")
async def create_pipeline(data: PipelineCreate, current_user: dict = require_auth()):
    conn = get_db()
    try:
        pid = f"pipe_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO pipelines (id, name, description, type, config, created_by) VALUES (?,?,?,?,?,?)",
            (pid, data.name, data.description, data.type, json.dumps(data.config), current_user["username"])
        )
        conn.commit()
        return {"ok": True, "id": pid}
    finally:
        conn.close()


class PipelineUpdate(BaseModel):
    name: str = ""
    description: str = ""
    type: str = ""
    config: dict = None


@router.put("/api/pipelines/{pid}")
async def update_pipeline(pid: str, data: PipelineUpdate, current_user: dict = require_auth()):
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM pipelines WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise HTTPException(404, "流水线不存在")
        updates, values = [], []
        if data.name:
            updates.append("name=?"); values.append(data.name)
        if data.description is not None:
            updates.append("description=?"); values.append(data.description)
        if data.type:
            updates.append("type=?"); values.append(data.type)
        if data.config is not None:
            updates.append("config=?"); values.append(json.dumps(data.config, ensure_ascii=False))
        if not updates:
            raise HTTPException(400, "没有需要更新的字段")
        updates.append("updated_at=?"); values.append(datetime.now().isoformat())
        values.append(pid)
        conn.execute(f"UPDATE pipelines SET {','.join(updates)} WHERE id=?", values)
        conn.commit()
        return {"ok": True, "id": pid}
    finally:
        conn.close()


@router.post("/api/pipelines/{pid}/run")
async def run_pipeline(pid: str, current_user: dict = require_auth()):
    """执行流水线：deploy 类型真实构建并部署沙箱；其余类型按模拟日志执行。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM pipelines WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise HTTPException(404, "流水线不存在")
        p = dict(row)
        cfg = json.loads(p.get("config", "{}") or "{}")
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        started = datetime.now().isoformat()
        ptype = p.get("type") or "ci"

        # deploy 类型：后台线程真实执行（构建镜像 + 启动沙箱容器）
        if ptype == "deploy":
            if not cfg.get("service_name") or not cfg.get("project_dir"):
                # 手动新建的 deploy 流水线缺少部署配置，直接标记失败
                err_log = f"[{started[:19]}] 部署配置缺失（service_name/project_dir）\n  - ❌ 该流水线由 AI 工作台「一键部署」自动创建，不支持手动新建运行"
                conn.execute(
                    "INSERT INTO pipeline_runs (id, pipeline_id, status, log, started_at, finished_at) VALUES (?,?,?,?,?,?)",
                    (run_id, pid, "failed", err_log, started, started),
                )
                conn.execute("UPDATE pipelines SET status='failed', last_run=? WHERE id=?", (started, pid))
                conn.commit()
                return {"ok": False, "id": run_id, "status": "failed", "error": "部署配置缺失（service_name/project_dir）"}
            conn.execute(
                "INSERT INTO pipeline_runs (id, pipeline_id, status, log, started_at) VALUES (?,?,?,?,?)",
                (run_id, pid, "running", f"[{started[:19]}] 部署任务已创建，等待执行…", started),
            )
            conn.execute("UPDATE pipelines SET status='running', last_run=? WHERE id=?", (started, pid))
            conn.commit()
            threading.Thread(target=_exec_deploy_pipeline, args=(pid, run_id, cfg), daemon=True).start()
            return {"ok": True, "id": run_id, "status": "running", "started_at": started}

        # 其余类型：模拟执行阶段（按类型生成日志）
        stages = {
            "ci": [
                ("检出代码", f"git clone --depth 1 {cfg.get('repo', 'https://example.com/repo.git')}"),
                ("安装依赖", "pip install -r requirements.txt（模拟）"),
                ("静态检查", "ruff check . --select E,F（模拟）"),
                ("单元测试", f"pytest -q {cfg.get('test_path', 'tests/')}（模拟）"),
                ("构建产物", "构建完成，产物打包成功（模拟）"),
            ],
            "cd": [
                ("拉取产物", "docker pull registry.example.com/app:latest（模拟）"),
                ("滚动发布", "kubectl rollout status deploy/app（模拟）"),
                ("健康检查", "GET /healthz -> 200 OK（模拟）"),
                ("发布完成", "新版本 v1.0.0 已上线（模拟）"),
            ],
            "test": [
                ("收集用例", "pytest --collect-only（模拟）"),
                ("执行用例", f"pytest -q {cfg.get('test_path', 'tests/')}（模拟）"),
                ("覆盖率", "coverage report -m（模拟）"),
            ],
            "build": [
                ("编译", "编译源码（模拟）"),
                ("打包", "构建 Docker 镜像 app:latest（模拟）"),
                ("推送镜像", "push registry.example.com/app:latest（模拟）"),
            ],
        }
        lines = [f"[{started[:19]}] 流水线「{p['name']}」开始执行（{ptype} 类型）"]
        for name, cmd in stages.get(ptype, stages["ci"]):
            lines.append(f"  - {name}: {cmd}")
        # 模拟耗时
        time.sleep(0.8)
        lines.append("  - 全部阶段通过 ✓")
        log = "\n".join(lines)
        finished = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO pipeline_runs (id, pipeline_id, status, log, started_at, finished_at) VALUES (?,?,?,?,?,?)",
            (run_id, pid, "success", log, started, finished),
        )
        conn.execute("UPDATE pipelines SET status='success', last_run=? WHERE id=?", (finished, pid))
        conn.commit()
        return {"ok": True, "id": run_id, "status": "success", "log": log, "started_at": started, "finished_at": finished}
    finally:
        conn.close()


@router.post("/api/pipelines/{pid}/auto-fix")
async def auto_fix_pipeline(pid: str, current_user: dict = require_auth()):
    """AI 诊断修复：拉取容器日志 → LLM 分析根因并修改代码 → 重建 → 重启 → 健康检查。

    用户可控：部署失败后可手动触发；deploy 流水线失败且 auto_fix 开启时自动触发。
    """
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM pipelines WHERE id=? AND active=1", (pid,)).fetchone()
        if not row:
            raise HTTPException(404, "流水线不存在")
        p = dict(row)
        if p.get("type") != "deploy":
            raise HTTPException(400, "仅支持对沙箱部署（deploy）流水线执行 AI 修复")
        cfg = json.loads(p.get("config", "{}") or "{}")
        if not cfg.get("service_name") or not cfg.get("project_dir"):
            raise HTTPException(400, "部署配置缺失，无法修复")
        # 确保 auto_fix 生效（修复后也保持开启）
        cfg["auto_fix"] = True
        conn.execute("UPDATE pipelines SET config=?, status='running', last_run=? WHERE id=?",
                     (json.dumps(cfg, ensure_ascii=False), datetime.now().isoformat(), pid))
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        started = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO pipeline_runs (id, pipeline_id, status, log, started_at) VALUES (?,?,?,?,?)",
            (run_id, pid, "running", f"[{started[:19]}] AI 诊断修复任务已创建，等待执行…", started),
        )
        conn.commit()
        threading.Thread(target=_exec_auto_fix, args=(pid, run_id, cfg), daemon=True).start()
        return {"ok": True, "id": run_id, "status": "running", "started_at": started}
    finally:
        conn.close()


@router.post("/api/sandbox/projects/{project_id}/logs/analyze")
async def analyze_sandbox_logs(project_id: str, current_user: dict = require_auth()):
    """AI 分析沙箱容器日志：拉取日志 → LLM 定位问题根因 → 返回诊断报告。"""
    import subprocess as _sp
    logs = ""
    if project_id.startswith("deploy-"):
        container = f"sandbox-{project_id[len('deploy-'):]}"
        r = _sp.run(["podman", "logs", "--tail", "200", container], capture_output=True, text=True, timeout=15)
        logs = r.stdout if r.returncode == 0 else (r.stderr or "")
    else:
        from sandbox import process_manager
        logs = "\n".join(process_manager.get_logs(project_id, tail=200))
    if not logs.strip():
        return {"ok": True, "analysis": "容器暂无日志输出，可能尚未启动或无错误信息。", "logs": ""}
    sys_prompt = (
        "你是一个资深的 SRE 运维专家。分析下面的容器运行日志，定位问题根因，"
        "给出：1.问题现象 2.根本原因 3.修复建议（具体到代码/配置层面）。"
        "简洁清晰，使用中文，用 markdown 列表组织。不要猜测没有依据的问题。"
    )
    try:
        analysis = call_llm(sys_prompt, f"【容器日志】\n{logs[-6000:]}")
    except Exception as e:
        raise HTTPException(500, f"日志分析失败: {str(e)}")
    return {"ok": True, "analysis": analysis, "logs": logs}


@router.get("/api/pipelines/{pid}/runs")
async def list_pipeline_runs(pid: str, current_user: dict = require_auth()):
    """获取流水线运行历史。"""
    conn = get_db()
    try:
        items = []
        for row in conn.execute(
            "SELECT * FROM pipeline_runs WHERE pipeline_id=? ORDER BY started_at DESC LIMIT 20", (pid,)
        ).fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.delete("/api/pipelines/{pid}")
async def delete_pipeline(pid: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("UPDATE pipelines SET active=0 WHERE id=?", (pid,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Phase 3: 内容创作增强
# ══════════════════════════════════════════════════════════════

class CopywritingRequest(BaseModel):
    type: str = "marketing"
    title: str = ""
    prompt: str
    model: str = ""

class TranslationRequest(BaseModel):
    source_lang: str = "中文"
    target_lang: str = "English"
    text: str
    model: str = ""


@router.post("/api/copywriting/generate")
async def generate_copywriting(data: CopywritingRequest, current_user: dict = require_auth()):
    """AI 文案生成"""
    try:
        type_specs = {
            "marketing": {
                "role": "资深营销文案专家（8年+4A公司经验）",
                "focus": ["卖点提炼", "行动号召(CTA)", "情感共鸣", "信任背书"],
                "format": "标题（3-5个备选）+ 正文（300-500字）+ 标语Slogan + 发布建议"
            },
            "social": {
                "role": "社交媒体内容策划专家",
                "focus": ["话题性", "互动引导", "平台适配", "时效热点"],
                "format": "标题 + 正文（150-300字）+ 话题标签# + 配图建议 + 发布时间建议"
            },
            "seo": {
                "role": "SEO内容策略专家",
                "focus": ["关键词密度", "标题标签优化", "元描述", "内部链接建议"],
                "format": "SEO标题（含主关键词）+ 元描述（150-160字符）+ 正文（800-1500字）+ 关键词列表 + 结构建议"
            },
            "email": {
                "role": "邮件营销转化率优化专家",
                "focus": ["打开率优化", "点击率优化", "个性化", "A/B测试建议"],
                "format": "邮件主题行（3个备选）+ 预览文本 + 正文HTML（含CTA按钮）+ 发送时间建议"
            },
            "ad": {
                "role": "创意广告策略专家",
                "focus": ["差异化定位", "用户痛点", "场景植入", "记忆点设计"],
                "format": "广告语（5-8个备选）+ 长文案（200-400字）+ 视觉创意brief + 投放渠道建议"
            },
        }
        spec = type_specs.get(data.type, type_specs["marketing"])

        system_prompt = f"""你是{spec['role']}。

核心能力：
{chr(10).join(f'- {f}' for f in spec['focus'])}

输出格式（必须严格遵循）：
{spec['format']}

创作原则：
1. 始终以目标用户视角思考，回答"这对我有什么用？"
2. 语言简洁有力，避免行业黑话和空洞形容词
3. 每个观点用数据或场景支撑，拒绝泛泛而谈
4. 结尾始终包含可衡量的下一步行动建议
5. 如涉及品牌，需注明品牌调性建议（如：年轻活泼/专业稳重/温暖亲切）"""
        result = call_llm(system_prompt, data.prompt)

        task_id = f"copy_{uuid.uuid4().hex[:12]}"
        # 独立连接：避免 LLM 调用期间其他函数关闭线程复用连接
        from common.db import get_db_context
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO copywriting_tasks (id, type, title, prompt, result, model) VALUES (?,?,?,?,?,?)",
                (task_id, data.type, data.title, data.prompt, result, data.model)
            )
        return {"ok": True, "id": task_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"文案生成失败: {str(e)}")


@router.get("/api/copywriting/history")
async def list_copywriting_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM copywriting_tasks ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.delete("/api/copywriting/{task_id}")
async def delete_copywriting(task_id: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("DELETE FROM copywriting_tasks WHERE id = ?", (task_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.post("/api/translation/translate")
async def translate_text(data: TranslationRequest, current_user: dict = require_auth()):
    """AI 翻译"""
    try:
        system_prompt = f"""你是专业翻译，精通{data.source_lang}和{data.target_lang}双语互译。

翻译原则：
1. 忠实原文：准确传达原文信息，不添加、不删减、不曲解
2. 语言地道：目标语言表达自然流畅，符合母语者表达习惯
3. 风格一致：保持原文的正式/非正式语体、行业术语、修辞手法
4. 文化适配：涉及文化特定概念时，提供等效表达并标注注释
5. 格式保留：保持原文的段落结构、列表、编号、Markdown标记

输出要求：
- 只返回翻译结果，不要任何前置说明或后记
- 如果遇到专有名词、品牌名、人名，保持原文不翻译
- 如果原文有歧义，选择最合理的解释并标注 [注: ...]
- 技术术语统一使用目标语言行业标准译法"""
        result = call_llm(system_prompt, data.text)

        trans_id = f"trans_{uuid.uuid4().hex[:12]}"
        # 独立连接：避免 LLM 调用期间其他函数关闭线程复用连接
        from common.db import get_db_context
        with get_db_context() as conn:
            conn.execute(
                "INSERT INTO translations (id, source_lang, target_lang, source_text, result, model) VALUES (?,?,?,?,?,?)",
                (trans_id, data.source_lang, data.target_lang, data.text, result, data.model)
            )
        return {"ok": True, "id": trans_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"翻译失败: {str(e)}")


@router.get("/api/translation/history")
async def list_translation_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM translations ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.delete("/api/translation/{task_id}")
async def delete_translation(task_id: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("DELETE FROM translations WHERE id = ?", (task_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Phase 4: 运营分析
# ══════════════════════════════════════════════════════════════

class ABTestCreate(BaseModel):
    name: str
    description: str = ""
    variant_a: str = ""
    variant_b: str = ""


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = require_auth()):
    """获取仪表盘统计数据"""
    conn = get_db()
    try:
        stats = {
            "agents": conn.execute("SELECT COUNT(*) FROM agents WHERE active=1").fetchone()[0],
            "workflows": conn.execute("SELECT COUNT(*) FROM workflows WHERE active=1").fetchone()[0],
            "projects": conn.execute("SELECT COUNT(*) FROM projects WHERE active=1").fetchone()[0],
            "tasks": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE active=1").fetchone()[0],
            "tasks_completed": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE status='done' AND active=1").fetchone()[0],
            "pipelines": conn.execute("SELECT COUNT(*) FROM pipelines WHERE active=1").fetchone()[0],
            "code_generations": conn.execute("SELECT COUNT(*) FROM code_generations").fetchone()[0],
            "translations": conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
            "artifacts": conn.execute("SELECT COUNT(*) FROM artifacts WHERE active=1").fetchone()[0],
        }
        return stats
    finally:
        conn.close()


@router.get("/api/analytics/overview")
async def get_analytics_overview(current_user: dict = require_auth()):
    """获取分析概览"""
    conn = get_db()
    try:
        return {
            "total_agents": conn.execute("SELECT COUNT(*) FROM agents WHERE active=1").fetchone()[0],
            "total_workflows": conn.execute("SELECT COUNT(*) FROM workflows WHERE active=1").fetchone()[0],
            "total_projects": conn.execute("SELECT COUNT(*) FROM projects WHERE active=1").fetchone()[0],
            "total_tasks": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE active=1").fetchone()[0],
            "completed_tasks": conn.execute("SELECT COUNT(*) FROM global_tasks WHERE status='done'").fetchone()[0],
            "total_artifacts": conn.execute("SELECT COUNT(*) FROM artifacts WHERE active=1").fetchone()[0],
            "total_code_gens": conn.execute("SELECT COUNT(*) FROM code_generations").fetchone()[0],
            "total_translations": conn.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
        }
    finally:
        conn.close()


@router.get("/api/ab-tests")
async def list_ab_tests(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM ab_tests WHERE active=1 ORDER BY created_at DESC").fetchall():
            t = dict(row)
            t["result"] = json.loads(t.get("result", "{}"))
            items.append(t)
        return items
    finally:
        conn.close()


@router.post("/api/ab-tests")
async def create_ab_test(data: ABTestCreate, current_user: dict = require_auth()):
    conn = get_db()
    try:
        tid = f"ab_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO ab_tests (id, name, description, variant_a, variant_b, created_by) VALUES (?,?,?,?,?,?)",
            (tid, data.name, data.description, data.variant_a, data.variant_b, current_user["username"])
        )
        conn.commit()
        return {"ok": True, "id": tid}
    finally:
        conn.close()


@router.delete("/api/ab-tests/{tid}")
async def delete_ab_test(tid: str, current_user: dict = require_auth()):
    conn = get_db()
    try:
        conn.execute("UPDATE ab_tests SET active=0 WHERE id=?", (tid,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 办公效率: PPT + Excel
# ══════════════════════════════════════════════════════════════

class PPTGenerateRequest(BaseModel):
    title: str
    outline: str = ""
    model: str = ""

class ExcelRequest(BaseModel):
    operation: str = "create"
    title: str = ""
    data: dict = {}


@router.post("/api/ppt/generate")
async def generate_ppt(data: PPTGenerateRequest, current_user: dict = require_auth()):
    """AI PPT 大纲生成"""
    conn = get_db()
    try:
        system_prompt = """你是资深PPT策划与演示设计专家，服务于500强企业高管汇报场景。

PPT大纲设计原则：
1. 黄金结构：封面→目录→问题/背景（Why）→方案/产品（What）→执行/数据（How）→案例/成果→下一步行动→感谢页
2. 每页原则：一页一个核心观点，标题即是结论（非描述性标题）
3. 视觉思维：优先用图表代替文字（对比用柱状图、趋势用折线图、占比用饼图、流程用箭头）
4. 数据说话：每个观点尽量用可量化数据支撑，标注数据来源
5. 记忆锚点：设计一个贯穿全篇的视觉隐喻或故事线

请严格按以下JSON格式返回（只返回JSON，不要任何其他文字）：
{
  "meta": {
    "storyline": "一句话概括全篇叙述逻辑",
    "visual_theme": "建议配色方案和视觉风格",
    "estimated_duration": "预计演讲时长（分钟）"
  },
  "slides": [
    {
      "type": "cover|toc|content|data|case|summary|thanks",
      "title": "结论式标题（不超过15字）",
      "subtitle": "副标题或上下文说明",
      "content": ["要点1", "要点2", "要点3"],
      "chart_suggestion": "如适用，建议的图表类型和数据维度",
      "notes": "演讲备注：过渡语、强调点、互动问题",
      "duration_seconds": 60
    }
  ]
}

生成8-12页幻灯片，确保逻辑递进、首尾呼应。"""

        prompt = f"主题：{data.title}"
        if data.outline:
            prompt += f"\n大纲：{data.outline}"

        result = call_llm(system_prompt, prompt)

        ppt_id = f"ppt_{uuid.uuid4().hex[:12]}"
        conn.execute(
            "INSERT INTO ppt_generations (id, title, outline, result, model) VALUES (?,?,?,?,?)",
            (ppt_id, data.title, data.outline, result, data.model)
        )
        conn.commit()
        return {"ok": True, "id": ppt_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"PPT生成失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/ppt/history")
async def list_ppt_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM ppt_generations ORDER BY created_at DESC LIMIT 50").fetchall():
            items.append(dict(row))
        return items
    finally:
        conn.close()


@router.post("/api/excel/operate")
async def excel_operate(data: ExcelRequest, current_user: dict = require_auth()):
    """Excel 操作"""
    conn = get_db()
    try:
        op_id = f"excel_{uuid.uuid4().hex[:12]}"
        result = ""

        if data.operation == "analyze":
            system_prompt = """你是资深数据分析师，精通Excel数据分析与商业洞察。

分析框架（按此结构输出）：
## 📊 数据概览
- 数据规模（行数、列数）
- 核心指标（均值、中位数、最大值、最小值）

## 🔍 关键发现（3-5条）
每条发现包含：
- 发现描述（用数据说话）
- 业务含义（这对业务意味着什么）
- 行动建议（接下来该做什么）

## 📈 趋势与模式
- 时间趋势（如有日期列）
- 相关性分析（如有多个数值列）
- 异常值识别

## ⚠️ 风险与机会
- 潜在风险点
- 改善机会点

## 💡 建议的可视化方案
- 图表类型 × 数据维度组合建议（如：柱状图 × 按月份销售额）

要求：语言简洁务实，面向业务决策者，避免技术术语堆砌。"""
            result = call_llm(system_prompt, json.dumps(data.data, ensure_ascii=False))
        elif data.operation == "formula":
            system_prompt = """你是Excel高级公式专家，精通VLOOKUP/XLOOKUP/INDEX-MATCH/SUMIFS/数组公式/Power Query等高级功能。

输出格式：
## 推荐公式
```excel
=公式表达式
```

## 公式解读
- 函数说明：每个函数的用途
- 参数解释：每个参数的含义
- 计算逻辑：逐步解释公式如何工作

## 使用场景
- 适用版本：Excel 2016/2019/365/Mac
- 前置条件：数据需要满足什么格式
- 常见陷阱：使用时容易犯的错误

## 替代方案（如有）
- 方案2：XX公式（适用YY场景）
- 方案的优缺点对比

要求：用通俗语言解释，让非技术用户也能理解。"""
            prompt = data.data.get("prompt", "")
            result = call_llm(system_prompt, prompt)
        else:
            result = json.dumps({"status": "created", "data": data.data})

        conn.execute(
            "INSERT INTO excel_operations (id, operation, title, data, result) VALUES (?,?,?,?,?)",
            (op_id, data.operation, data.title, json.dumps(data.data), result)
        )
        conn.commit()
        return {"ok": True, "id": op_id, "result": result}
    except Exception as e:
        raise HTTPException(500, f"Excel操作失败: {str(e)}")
    finally:
        conn.close()


@router.get("/api/excel/history")
async def list_excel_history(current_user: dict = require_auth()):
    conn = get_db()
    try:
        items = []
        for row in conn.execute("SELECT * FROM excel_operations ORDER BY created_at DESC LIMIT 50").fetchall():
            e = dict(row)
            e["data"] = json.loads(e.get("data", "{}"))
            items.append(e)
        return items
    finally:
        conn.close()
