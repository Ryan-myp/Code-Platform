"""沙箱（Docker 项目管理）API — 从 main.py 拆出的独立路由模块。"""

import json
import re
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from common import sandbox_check as sc
from common.auth import require_auth
from common.db import get_db
from common.models import (
    SandboxProjectCreateRequest,
    SandboxPullImageRequest,
    SandboxRedisCommandRequest,
    SandboxSqlQueryRequest,
)
from common.sandbox_check import MAX_CODE_LEN, check_sandbox_code, run_sandbox_python

router = APIRouter()


def _safe_error(msg: str) -> str:
    """清洗命令执行错误信息，防止泄露内部路径/密码/IP 等敏感内容。"""
    import re as _re

    safe = _re.sub(r"/[^\s,;]{8,}", "<path>", msg)[:200]
    safe = _re.sub(r"(?:password|secret|token|key)\s*[:=]\s*\S+", "<cred>", safe, flags=_re.IGNORECASE)
    safe = _re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<ip>", safe)
    return safe or "命令执行失败，请检查配置后重试"


# ── 沙箱管理 ───────────────────────────────────────────────────
@router.get("/api/sandbox/images")
async def sandbox_list_images(current_user: dict = require_auth()):
    """列出沙箱镜像"""
    from sandbox import process_manager

    return {"images": process_manager.list_images()}


@router.post("/api/sandbox/images/pull")
async def sandbox_pull_image(req: SandboxPullImageRequest, current_user: dict = require_auth()):
    """拉取镜像"""
    from sandbox import process_manager

    return process_manager.pull_image(req.image)


@router.get("/api/sandbox/services")
async def sandbox_services(current_user: dict = require_auth()):
    """获取预置服务模板"""
    from sandbox import SERVICE_TEMPLATES

    # 转 list 返回并补充 id（前端以 id 作 React key）
    return {"services": [{**v, "id": k} for k, v in SERVICE_TEMPLATES.items()]}


# Redis 控制台安全白名单：仅允许数据操作命令，禁止 FLUSHALL/FLUSHDB/SHUTDOWN/CONFIG/EVAL 等危险命令
REDIS_SAFE_COMMANDS = {
    "PING",
    "ECHO",
    "DBSIZE",
    "KEYS",
    "EXISTS",
    "TYPE",
    "TTL",
    "PTTL",
    "GET",
    "MGET",
    "SET",
    "MSET",
    "APPEND",
    "DEL",
    "EXPIRE",
    "PERSIST",
    "RENAME",
    "INCR",
    "DECR",
    "INCRBY",
    "DECRBY",
    "HSET",
    "HGET",
    "HDEL",
    "HGETALL",
    "HLEN",
    "HEXISTS",
    "LPUSH",
    "RPUSH",
    "LPOP",
    "RPOP",
    "LRANGE",
    "LLEN",
    "SADD",
    "SREM",
    "SMEMBERS",
    "SCARD",
    "SISMEMBER",
    "ZADD",
    "ZREM",
    "ZRANGE",
    "ZCARD",
    "ZSCORE",
    "GETRANGE",
    "SETEX",
    "STRLEN",
    "OBJECT",
}


def _sandbox_project_env(project_id: str) -> dict:
    """读取沙箱项目创建配置中的环境变量（服务控制台凭据：MYSQL_ROOT_PASSWORD 等）"""
    conn = get_db()
    row = conn.execute("SELECT image, config FROM sandbox_projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    env_map = {}
    if row:
        try:
            cfg = json.loads(row["config"] or "{}")
            for e in cfg.get("env") or []:
                if isinstance(e, str) and "=" in e:
                    k, _, v = e.partition("=")
                    env_map[k.strip()] = v.strip()
        except Exception:
            pass
    return env_map


@router.post("/api/sandbox/projects/{project_id}/redis/command")
def sandbox_redis_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """Redis 控制台：在项目容器内执行 redis-cli 安全命令（查看/修改/删除 Key）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    verb = cmd.split()[0].upper()
    if verb not in REDIS_SAFE_COMMANDS:
        raise HTTPException(400, "命令不在安全白名单内")
    # 命令按空白拆分为 argv，避免注入（redis-cli 接收参数数组，无 shell 解释）
    result = process_manager.exec_command(project_id, ["redis-cli", *cmd.split()], timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


# SQL 控制台白名单：仅允许只读查询（沙箱内数据浏览，禁止写操作）
SQL_SAFE_VERBS = {"SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN"}


@router.post("/api/sandbox/projects/{project_id}/sql/query")
def sandbox_sql_query(project_id: str, req: SandboxSqlQueryRequest, current_user: dict = require_auth()):
    """SQL 控制台：在项目容器内执行只读查询（MySQL/PostgreSQL），返回结构化表格"""
    from sandbox import process_manager

    sql = req.sql.strip().rstrip(";")
    if not sql:
        raise HTTPException(400, "SQL 不能为空")
    verb = sql.split()[0].upper()
    if verb not in SQL_SAFE_VERBS:
        raise HTTPException(400, "仅支持只读查询，禁止写操作")
    if ";" in sql:
        raise HTTPException(400, "一次只能执行一条 SQL")

    # 从项目镜像与创建配置（env）确定数据库客户端与凭据：
    # 沙箱项目创建时可自定义密码（如 MYSQL_ROOT_PASSWORD），不可硬编码默认值
    conn = get_db()
    row = conn.execute("SELECT image FROM sandbox_projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    image = (row["image"] if row else "") or ""
    image_l = image.lower()
    env_map = _sandbox_project_env(project_id)
    if "mysql" in image_l:
        pwd = env_map.get("MYSQL_ROOT_PASSWORD", "password")
        # 不加 -N：非交互 -e 模式自带表头（tab 分隔），解析器以首行为列名；-N 会吞掉首行数据
        argv = ["mysql", "-uroot", f"-p{pwd}", "--default-character-set=utf8mb4", "-e", sql]
    elif "postgres" in image_l or "postgresql" in image_l:
        # 密码经连接串传递（容器内 stdin 为 /dev/null，无法交互输入，PGPASSWORD 需 -e 注入）
        pwd = env_map.get("POSTGRES_PASSWORD", "password")
        user = env_map.get("POSTGRES_USER", "postgres")
        db = env_map.get("POSTGRES_DB", "sandbox")
        # -A 禁用对齐装饰、-F 指定 tab 分隔；保留表头（不用 -t），与 mysql 行为对齐，解析器以首行为列名
        argv = ["psql", f"postgresql://{user}:{pwd}@localhost/{db}", "-A", "-F", "\t", "-c", sql]
    else:
        raise HTTPException(400, "该项目不是 MySQL/PostgreSQL 数据库服务，无法执行 SQL")

    result = process_manager.exec_command(project_id, argv, timeout=30)
    if result["status"] != "success":
        # 过滤 mysql 客户端的“命令行密码不安全”警告行，保留真实错误
        err_lines = [ln for ln in result["message"].split("\n") if "Using a password on the command line" not in ln]
        raise HTTPException(500, "\n".join(err_lines).strip() or "SQL 执行失败")
    raw = result["output"].rstrip("\n")
    # 过滤 mysql 客户端的“命令行密码不安全”警告行（成功时也可能出现在 stderr 合并输出中）
    raw = "\n".join(ln for ln in raw.split("\n") if "Using a password on the command line" not in ln)
    # 解析 tab 分隔输出为结构化表格（首行表头）
    columns: list[str] = []
    rows: list[list] = []
    if raw.strip():
        lines = raw.split("\n")
        columns = [c for c in lines[0].split("\t") if c != ""]
        rows = [[c for c in line.split("\t")] for line in lines[1:] if line.strip() and line.strip() != "(0 rows)"]
    return {"ok": True, "sql": sql, "columns": columns, "rows": rows, "raw": raw}


# MongoDB 控制台：mongosh 只读白名单（正则匹配允许模式 + 全局禁词双重拦截）
MONGO_SAFE_PATTERNS = [
    re.compile(r"^(show|use)\s+(dbs|databases|collections|tables|[a-zA-Z0-9_\-]+)$"),
    re.compile(r"^db\.\w+\.(find|findOne|count|countDocuments|distinct|listIndexes)\(.*\)$"),
    re.compile(r"^db\.(stats|getName|getCollectionNames|getCollectionInfos)\(.*\)$"),
    re.compile(r"^db\.\w+\.getIndexes\(\)$"),
]
# 写操作/危险操作禁词（大小写不敏感，命中即拒绝）
MONGO_BLOCKED = [
    "insert",
    "update",
    "delete",
    "remove",
    "drop",
    "create",
    "rename",
    "aggregate",
    "eval(",
    "runcommand",
    "admincommand",
    "$out",
    "$merge",
    "copytodatabase",
]


@router.post("/api/sandbox/projects/{project_id}/mongo/command")
def sandbox_mongo_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """MongoDB 控制台：在项目容器内执行 mongosh 只读命令（show dbs / db.collection.find 等）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    cmd_l = cmd.lower()
    if any(b in cmd_l for b in MONGO_BLOCKED):
        raise HTTPException(400, "仅支持只读操作（禁止 insert/update/delete/drop/create/aggregate 等）")
    if not any(p.match(cmd) for p in MONGO_SAFE_PATTERNS):
        raise HTTPException(
            400, "命令格式不在允许范围（支持 show dbs / use db / db.集合.find(...) / db.stats() 等只读操作）"
        )

    # 凭据从项目创建配置读取（模板默认 admin/password）
    env_map = _sandbox_project_env(project_id)
    user = env_map.get("MONGO_INITDB_ROOT_USERNAME", "admin")
    pwd = env_map.get("MONGO_INITDB_ROOT_PASSWORD", "password")
    argv = ["mongosh", "--quiet", "-u", user, "-p", pwd, "--authenticationDatabase", "admin", "--eval", cmd]
    result = process_manager.exec_command(project_id, argv, timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


# RabbitMQ 控制台：rabbitmqctl 只读白名单（状态/列表类命令）
RABBITMQ_SAFE_VERBS = {
    "status",
    "ping",
    "list_queues",
    "list_exchanges",
    "list_bindings",
    "list_connections",
    "list_channels",
    "list_users",
    "list_permissions",
    "list_vhosts",
    "list_policies",
    "list_consumers",
}
RABBITMQ_FIELD_RE = re.compile(r"^[a-zA-Z0-9_ ]*$")


@router.post("/api/sandbox/projects/{project_id}/rabbitmq/command")
def sandbox_rabbitmq_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """RabbitMQ 控制台：在项目容器内执行 rabbitmqctl 只读命令（status / list_queues 等）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    parts = cmd.split()
    verb = parts[0]
    if verb not in RABBITMQ_SAFE_VERBS:
        raise HTTPException(400, "命令不在安全白名单内")
    # 参数仅允许字段名（如 name messages），防止注入
    if len(parts) > 1 and not RABBITMQ_FIELD_RE.match(" ".join(parts[1:])):
        raise HTTPException(400, "参数格式不合法")
    result = process_manager.exec_command(project_id, ["rabbitmqctl", *parts], timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


# Nginx 控制台：只读参数白名单（版本/配置测试/配置转储）
NGINX_SAFE_ARGS = {"-v", "-V", "-t", "-T"}


@router.post("/api/sandbox/projects/{project_id}/nginx/command")
def sandbox_nginx_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """Nginx 控制台：在项目容器内执行 nginx 只读命令（-v 版本 / -t 配置测试 / -T 配置转储）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    args = cmd.split()
    if args[0] != "nginx" or len(args) != 2 or args[1] not in NGINX_SAFE_ARGS:
        raise HTTPException(400, "仅支持 nginx -v / nginx -V / nginx -t / nginx -T 只读命令")
    result = process_manager.exec_command(project_id, ["nginx", args[1]], timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


@router.get("/api/sandbox/projects")
async def sandbox_list_projects(current_user: dict = require_auth()):
    """列出沙箱项目"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM sandbox_projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/api/sandbox/projects")
async def sandbox_create_project(req: SandboxProjectCreateRequest, current_user: dict = require_auth()):
    """创建沙箱项目"""
    from sandbox import process_manager

    project_id = f"proj_{int(time.time() * 1000)}"
    # 前端可能传字符串或列表，统一转为列表
    raw_ports = req.ports
    if isinstance(raw_ports, str):
        ports = [p.strip() for p in raw_ports.split(",") if p.strip()]
    else:
        ports = raw_ports or []
    raw_env = req.env
    if isinstance(raw_env, str):
        env = [e.strip() for e in raw_env.split(",") if e.strip()]
    else:
        env = raw_env or []
    config = {
        "image": req.image,
        "ports": ports,
        "env": env,
        "command": req.command,
    }
    result = process_manager.create_container(project_id, config)
    conn = get_db()
    conn.execute(
        """INSERT INTO sandbox_projects (id, name, image, status, ports, config, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            req.name,
            config["image"],
            result.get("status", "created"),
            json.dumps(config.get("ports", [])),
            json.dumps(config),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": project_id, **result}


@router.get("/api/sandbox/projects/{project_id}")
async def sandbox_get_project(project_id: str, current_user: dict = require_auth()):
    """获取沙箱项目状态"""
    from sandbox import process_manager

    status = process_manager.get_status(project_id)
    return {"id": project_id, "status": status or {"state": "unknown"}}


@router.post("/api/sandbox/projects/{project_id}/start")
def sandbox_start_project(project_id: str, current_user: dict = require_auth()):
    """启动沙箱项目"""
    # deploy 部署的容器由 CI/CD 创建（容器名 sandbox-{name}，记录 id 为 deploy-{name}），走真实容器管理
    if project_id.startswith("deploy-"):
        import subprocess
        from datetime import datetime

        container = f"sandbox-{project_id[len('deploy-') :]}"
        r = subprocess.run(
            ["podman", "start", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30
        )
        if r.returncode != 0:
            return {"status": "error", "message": (r.stderr or "").strip() or f"容器 {container} 不存在"}
        conn = get_db()
        conn.execute(
            "UPDATE sandbox_projects SET status='running', updated_at=? WHERE id=?",
            (datetime.now().isoformat(), project_id),
        )
        conn.commit()
        conn.close()
        return {"status": "success", "container": container}
    from sandbox import process_manager

    return process_manager.start_container(project_id)


@router.post("/api/sandbox/projects/{project_id}/stop")
def sandbox_stop_project(project_id: str, current_user: dict = require_auth()):
    """停止沙箱项目"""
    # deploy 部署的容器由 CI/CD 创建（容器名 sandbox-{name}，记录 id 为 deploy-{name}），走真实容器管理
    if project_id.startswith("deploy-"):
        import subprocess
        from datetime import datetime

        container = f"sandbox-{project_id[len('deploy-') :]}"
        r = subprocess.run(
            ["podman", "stop", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30
        )
        if r.returncode != 0:
            return {"status": "error", "message": (r.stderr or "").strip() or f"容器 {container} 不存在"}
        conn = get_db()
        conn.execute(
            "UPDATE sandbox_projects SET status='stopped', updated_at=? WHERE id=?",
            (datetime.now().isoformat(), project_id),
        )
        conn.commit()
        conn.close()
        return {"status": "success", "container": container}
    from sandbox import process_manager

    return process_manager.stop_container(project_id)


@router.delete("/api/sandbox/projects/{project_id}")
def sandbox_delete_project(project_id: str, current_user: dict = require_auth()):
    """删除沙箱项目"""
    # deploy 部署的容器由 CI/CD 创建（容器名 sandbox-{name}，记录 id 为 deploy-{name}），走真实容器管理
    if project_id.startswith("deploy-"):
        import subprocess

        container = f"sandbox-{project_id[len('deploy-') :]}"
        subprocess.run(
            ["podman", "stop", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30
        )
        subprocess.run(
            ["podman", "rm", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30
        )
        conn = get_db()
        conn.execute("DELETE FROM sandbox_projects WHERE id=?", (project_id,))
        conn.commit()
        conn.close()
        return {"status": "success", "container": container}
    from sandbox import process_manager

    result = process_manager.remove_container(project_id)
    conn = get_db()
    conn.execute("DELETE FROM sandbox_projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return result


@router.get("/api/sandbox/projects/{project_id}/logs")
def sandbox_project_logs(project_id: str, tail: int = 200, current_user: dict = require_auth()):
    """获取沙箱项目/部署容器日志（tail 默认 200 行）"""
    import subprocess as _sp

    if project_id.startswith("deploy-"):
        container = f"sandbox-{project_id[len('deploy-') :]}"
        r = _sp.run(["podman", "logs", "--tail", str(tail), container], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return {"logs": [], "message": (r.stderr or "").strip() or f"容器 {container} 不存在或未启动"}
        lines = r.stdout.splitlines()
        return {"logs": lines, "container": container}
    from sandbox import process_manager

    logs = process_manager.get_logs(project_id, tail=tail)
    return {"logs": logs, "container": f"sandbox-{project_id}"}


# ── 代码沙箱静态检查（AI 代码解释器安全）──────────────────────
# 策略与实现见 common/sandbox_check.py（黑名单/白名单/受限执行器，
# 供代码解释器与数据分析沙箱共用）。


@router.get("/api/sandbox/info")
def sandbox_info(current_user: dict = require_auth()):
    """沙箱环境说明：白名单库 / 禁用操作 / 资源上限（v15，前端提示卡片数据源）。"""

    return {
        "allowed_imports": sorted(sc.ALLOWED_IMPORTS),
        "blocked_tokens": sc.BLOCKED_TOKENS,
        "limits": {
            "code_max_len": sc.MAX_CODE_LEN,
            "output_max_len": sc.MAX_OUTPUT_LEN,
            "timeout_sec": sc.DEFAULT_TIMEOUT,
            "cpu_sec": 10,
            "file_max_bytes": 2 * 1024 * 1024,
        },
    }


@router.post("/api/sandbox/execute")
def sandbox_execute_code(req: dict, current_user: dict = require_auth()):
    """AI 代码解释器：安全子进程执行 Python 代码。

    安全措施：
    - 静态扫描：禁止 os/subprocess/socket/open/eval/importlib 等危险操作，import 白名单
    - 资源限制：CPU 10s / 单文件 2MB / 文件描述符 128（子进程 preexec_fn；
      macOS 不支持 AS/DATA 内存限制，内存保护靠静态扫描+超时兜底）
    - 隔离环境：独立临时工作目录，清空 HOME/TMPDIR，忽略 PYTHON* 环境变量
    - 超时 30s + 输出截断 20KB
    """
    code = (req.get("code") or "").strip()
    language = (req.get("language") or "python").lower()
    if not code:
        raise HTTPException(400, "代码不能为空")
    if len(code) > MAX_CODE_LEN:
        raise HTTPException(400, "代码过长（上限 20KB）")
    if language not in ("python", "python3", "py"):
        raise HTTPException(400, "仅支持 Python 语言")

    # ── 静态安全检查 ──
    blocked = check_sandbox_code(code)
    if blocked:
        return {"output": "", "error": blocked, "duration": 0.0, "exit_code": -1}

    result = run_sandbox_python(code)
    output = result["output"]
    # 沙箱自动收集工作目录内落盘的 PNG（如 plt.savefig 输出），统一转 [IMAGE] 标记供前端渲染
    for _name, b64 in result.get("files", {}).items():
        output += f"\n[IMAGE]{b64}[/IMAGE]"
    return {
        "output": output,
        "error": result["error"],
        "duration": result["duration"],
        "exit_code": result["exit_code"],
    }
