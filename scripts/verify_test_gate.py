"""真实验证自动化测试门禁：天气服务 → 生成测试 → 容器内执行 → 结果记录"""
import os
import sys
import subprocess

sys.path.insert(0, "/Users/yanping.ma/PycharmProjects/Code-Platform/backend")
os.chdir("/Users/yanping.ma/PycharmProjects/Code-Platform/backend")

from dotenv import load_dotenv
load_dotenv(".env")  # 独立脚本需手动加载 .env（main.py 启动时自动加载）

import extended_api as E

project_dir = "/Users/yanping.ma/PycharmProjects/Code-Platform/backend/artifacts/天气"
cfg = {
    "service_name": "天气",
    "project_dir": project_dir,
    "port": 18080,
    "requirement_id": "req_73087b070a54",
    "auto_fix": True,
    "auto_test": True,
    "dependencies": {
        "redis": True,
        "mysql": True,
        "mysql_password": "platform123",
        "mysql_database": "platform",
        "mysql_image": "docker.m.daocloud.io/library/mysql:8",
    },
}

log = []
def append(line):
    log.append(line)
    print(line, flush=True)

def step_run(cmd, timeout=900):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "命令执行超时"
    except Exception as e:
        return False, str(e)
    return (r.returncode == 0), (r.stdout or r.stderr or "").strip()

ok, summary = E._run_test_gate("pipe_verify_test", "run_verify_test", cfg, append, step_run)
print("\n=== RESULT ===")
print("ok:", ok)
print("summary:", summary)
print("log lines:", len(log))
sys.exit(0 if ok else 1)
