#!/usr/bin/env python3
"""小团智能平台 — 测试配置 fixtures"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 测试环境标识必须在任何测试模块 import main 之前设置：
# 否则模块级 `from main import app` 会绑定生产限流（login 5/min），
# 全量运行时多个测试文件的登录请求在同一 limiter 上累积，偶发 429 失败
os.environ["APP_ENV"] = "test"

# 添加 backend 到路径
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(autouse=True)
def setup_test_db():
    """为每个测试创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    original_db_path = os.environ.get("DB_PATH")
    os.environ["DB_PATH"] = db_path
    os.environ["APP_ENV"] = "test"  # 禁用限流避免干扰测试
    # 重置 Config 模块缓存
    if "config" in sys.modules:
        del sys.modules["config"]
    if "main" in sys.modules:
        del sys.modules["main"]
    # 重定向 Skills 文件目录到临时目录（避免污染真实 backend/skills_files/）
    from common import config as config_mod

    skills_tmp = Path(db_path).parent / f"{Path(db_path).stem}_skills"
    config_mod.SKILLS_DIR = skills_tmp
    from main import init_db

    init_db()
    # v17.2 团队空间表迁移（teams 表旧结构 → plan/seats/owner_id；与 main.py lifespan 行为一致）
    from team_api import ensure_team_tables

    ensure_team_tables()
    # v20 商业化表迁移（与 main.py lifespan 行为一致）
    from api_billing import ensure_api_keys_tables
    from conversion_analytics import ensure_analytics_tables
    from enterprise_api import ensure_enterprise_tables
    from prd_engine import ensure_requirements_tables
    from game_factory import ensure_game_tables

    ensure_api_keys_tables()
    ensure_analytics_tables()
    ensure_enterprise_tables()
    ensure_requirements_tables()
    ensure_game_tables()
    # dh_gateway 计费体系：users.balance 余额列 + dh_billing_records 账单表（幂等）
    from dh_gateway import _ensure_billing_tables
    from common.db import get_db_context as _gdb

    with _gdb() as conn:
        _ensure_billing_tables(conn)
    # api_keys 表由 web_search 模块级 init_db 创建（该模块可能在 DB_PATH 切换前已加载，
    # 表落在旧库），此处对测试库幂等补建，保证 API Key 认证链路可用
    from common.db import get_db_context

    with get_db_context() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                label TEXT,
                last_used TEXT,
                expires_at TEXT,
                created_at TEXT NOT NULL
            )"""
        )
        # favorites 表由 favorites_api 模块级创建（加载顺序不确定时可能落在旧库），幂等补建
        conn.execute(
            """CREATE TABLE IF NOT EXISTS favorites (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                fav_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                label TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, fav_type, target_id)
            )"""
        )
        # v20 API Key 计费表（api_billing 模块，独立于开放 API 密钥的 api_keys 表）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS api_key_billing (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                plan TEXT DEFAULT 'pay_as_you_go',
                monthly_limit INTEGER DEFAULT 0,
                rate_per_call INTEGER DEFAULT 5,
                remaining INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS api_usage (
                id TEXT PRIMARY KEY,
                key_id TEXT NOT NULL,
                amount INTEGER NOT NULL DEFAULT 1,
                endpoint TEXT,
                created_at TEXT
            )"""
        )
    yield db_path
    # Cleanup
    if original_db_path:
        os.environ["DB_PATH"] = original_db_path
    elif "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]
    try:
        os.unlink(db_path)
    except OSError:
        pass
    # 清理临时 Skills 目录
    import shutil

    if skills_tmp.exists():
        shutil.rmtree(skills_tmp, ignore_errors=True)


@pytest.fixture
def claim_and_run():
    """模拟 master 抢占（pending→running）后由 worker 执行 handler。

    worker 启动校验 status='running'（防取消竞态），单元测试直接调 _run_handler
    时任务仍是 pending，必须先模拟抢占再执行。
    """
    from datetime import datetime

    def _claim(task_id):
        from common.db import get_db
        from task_queue import _run_handler

        conn = get_db()
        try:
            conn.execute(
                "UPDATE async_tasks SET status='running', started_at=? WHERE id=?",
                (datetime.now().isoformat(), task_id),
            )
            conn.commit()
        finally:
            conn.close()
        _run_handler(task_id)

    return _claim


@pytest.fixture
def test_db_path(setup_test_db):
    """返回临时数据库路径"""
    return setup_test_db


@pytest.fixture(scope="session")
def valid_mp3_bytes():
    """生成一段真实有效的 MP3 音频字节（数字人 TTS mock 用，须通过 ffprobe 校验）。

    用 ffmpeg 生成 1 秒静音 MP3；ffmpeg 不可用时回退 base64 内嵌的最小有效 MP3。
    """
    import base64
    import shutil
    import subprocess
    import tempfile

    if shutil.which("ffmpeg"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                out = f.name
            r = subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                 "-t", "1", "-c:a", "libmp3lame", "-b:a", "64k", out],
                capture_output=True, timeout=15,
            )
            if r.returncode == 0:
                with open(out, "rb") as f:
                    data = f.read()
                try:
                    os.unlink(out)
                except OSError:
                    pass
                if len(data) > 512:
                    return data
        except Exception:
            pass
    # 兜底：最小有效 MP3（1 秒静音，libmp3lame 编码）
    minimal_b64 = (
        "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA//tQxAADB"
        "QAAWAAADWFgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    )
    try:
        return base64.b64decode(minimal_b64)
    except Exception:
        return b"\xff\xfb" + b"\x00" * 2046


@pytest.fixture(scope="session")
def valid_mp4_bytes():
    """生成一段真实有效的 MP4 视频字节（数字人渲染 mock 用，须通过 ffprobe 校验）。

    用 ffmpeg 生成 1 秒 320x240 蓝色画面 + 静音；ffmpeg 不可用时回退最小 H.264 MP4。
    """
    import shutil
    import subprocess
    import tempfile

    if shutil.which("ffmpeg"):
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                out = f.name
            r = subprocess.run(
                ["ffmpeg", "-y",
                 "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1",
                 "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                 "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "64k", out],
                capture_output=True, timeout=20,
            )
            if r.returncode == 0:
                with open(out, "rb") as f:
                    data = f.read()
                try:
                    os.unlink(out)
                except OSError:
                    pass
                if len(data) > 1024:
                    return data
        except Exception:
            pass
    # 兜底：无法生成时返回标记数据（测试将跳过渲染校验场景）
    return b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2046


@pytest.fixture
def sample_agent_data():
    """示例 Agent 数据"""
    return {
        "id": "agent_test_001",
        "name": "测试Agent",
        "description": "用于单元测试的Agent",
        "instructions": "你是一个测试助手",
        "model": "agnes-2.0-flash",
        "enable_memory": False,
        "enable_reasoning": False,
        "tools": [],
        "knowledge_base_ids": [],
        "skill_ids": [],
        "mcp_server_ids": [],
    }


@pytest.fixture
def sample_knowledge_base_data():
    """示例知识库数据"""
    return {
        "id": "kb_test_001",
        "name": "测试知识库",
        "type": "file",
        "path": "/tmp/test_kb",
        "top_k": 3,
    }


@pytest.fixture
def sample_skill_data():
    """示例 Skill 数据"""
    return {
        "id": "skill_test_001",
        "name": "测试Skill",
        "description": "用于单元测试的Skill",
        "content": "# 技能说明\n这是一个测试技能",
    }


@pytest.fixture
def sample_mcp_server_data():
    """示例 MCP Server 数据"""
    return {
        "id": "mcp_test_001",
        "name": "测试MCP",
        "transport_type": "stdio",
        "command": "node",
        "args": ["server.js"],
        "env": {},
    }


@pytest.fixture
def sample_project_data():
    """示例项目数据"""
    return {
        "id": "proj_test_001",
        "name": "测试项目",
        "description": "用于单元测试的项目",
        "status": "planning",
        "team_id": "",
    }


@pytest.fixture
def sample_requirement_data():
    """示例需求数据"""
    return {
        "id": "req_test_001",
        "name": "测试需求",
        "description": "用于单元测试的需求",
        "status": "draft",
        "priority": "P1",
        "project_id": "proj_test_001",
        "creator": "tester",
    }


@pytest.fixture
def sample_task_data():
    """示例任务数据"""
    return {
        "id": "task_test_001",
        "project_id": "proj_test_001",
        "title": "测试任务",
        "description": "用于单元测试的任务",
        "type": "prd",
        "assignee": "dev1",
        "status": "todo",
        "priority": "P1",
    }


@pytest.fixture
def auth_headers(setup_test_db):
    """获取 admin 用户登录后的 Authorization 头。

    init_db 已 ensure admin/admin123 用户，直接 login 拿 token。
    供集成测试在调用受保护端点时使用：client.post(..., headers=auth_headers)
    """
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, f"admin login failed: {resp.status_code} {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
