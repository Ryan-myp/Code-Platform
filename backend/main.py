#!/usr/bin/env python3
"""智能研发平台 v7.0 — 智能研发 + Agent 工作流平台"""

import os, time, json, sqlite3, logging, importlib, re, zipfile, base64, shutil
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime, timedelta
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Request, status, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from agno.agent import Agent
from agno.team import Team
from agno.workflow import Workflow
from agno.models.openai import OpenAIChat
from functools import lru_cache

# ── 配置 ──────────────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_DIR, "platform.db")
SKILLS_DIR = os.path.join(PROJECT_DIR, "skills_files")
ARTIFACTS_DIR = os.path.join(PROJECT_DIR, "artifacts")
LOGS_DIR = os.path.join(PROJECT_DIR, "logs")

os.makedirs(SKILLS_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://apihub.agnes-ai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "agnes-2.0-flash")
SECRET_KEY = os.environ.get("SECRET_KEY", "your-super-secret-change-in-prod")

# ── 日志 ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── 密码哈希 ──────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
security = HTTPBearer()

# ── Token 辅助函数 ────────────────────────────────────────────
def create_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ── 鉴权依赖 ──────────────────────────────────────────────────
async def get_current_user(request: Request, 
                           credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    token = credentials.credentials
    payload = decode_token(token)
    user_info = {
        "user_id": payload.get("user_id"),
        "username": payload.get("sub"),
        "role": payload.get("role", "viewer"),
        "scope": payload.get("scope", ["read"]),
    }
    return user_info

def require_auth(dependency: Callable = Depends(get_current_user)):
    return dependency

# ── 数据库 ────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # 创建 users 表（如果不存在）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'viewer',
            created_at TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    
    # 创建 agents 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            instructions TEXT,
            model TEXT DEFAULT 'agnes-2.0-flash',
            tools TEXT DEFAULT '[]',
            knowledge_base_ids TEXT DEFAULT '[]',
            skill_ids TEXT DEFAULT '[]',
            mcp_server_ids TEXT DEFAULT '[]',
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    
    # 创建 workflows 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            definition TEXT,
            created_at TEXT
        )
    """)
    
    # 创建 sessions 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            title TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 创建 messages 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    
    # 创建 memories 表
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            agent_id TEXT,
            memory_type TEXT DEFAULT 'short',
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        )
    """)
    
    # 创建 admin 用户（如果不存在）
    import hashlib
    admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
    cur.execute("INSERT OR IGNORE INTO users (id, username, password_hash, role, active) VALUES (?, ?, ?, ?, ?)",
                ('admin_001', 'admin', admin_hash, 'admin', 1))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# ── FastAPI 应用 ──────────────────────────────────────────────
app = FastAPI(title="智能研发平台 v7.0", version="7.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 健康检查 ──────────────────────────────────────────────────
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "version": "7.0.0"}

# ── 认证 ──────────────────────────────────────────────────────
@app.post("/api/auth/login")
async def login(req: dict):
    username = req.get("username", "")
    password = req.get("password", "")
    
    if not username or not password:
        raise HTTPException(400, "用户名和密码不能为空")
    
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(401, "用户名或密码错误")
    
    import hashlib
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    if user["password_hash"] != password_hash:
        raise HTTPException(401, "用户名或密码错误")
    
    token = create_token({
        "user_id": user["id"],
        "sub": user["username"],
        "role": user["role"],
    })
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
        }
    }

# ── Agent 管理 ────────────────────────────────────────────────
@app.get("/api/agents")
async def list_agents(current_user: Dict = require_auth()):
    """获取所有 Agent"""
    conn = get_db()
    agents = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(a) for a in agents]

@app.post("/api/agents")
async def create_agent(req: dict, current_user: Dict = require_auth()):
    """创建 Agent"""
    name = req.get("name", "").strip()
    if not name:
        raise HTTPException(400, "名称不能为空")
    
    conn = get_db()
    agent_id = f"agent_{int(time.time()*1000)}"
    conn.execute(
        """INSERT INTO agents (id, name, description, instructions, model, tools, knowledge_base_ids, skill_ids, mcp_server_ids, active, created_at) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (agent_id, name, req.get("description", ""), req.get("instructions", ""),
         req.get("model", "agnes-2.0-flash"), json.dumps(req.get("tools", [])),
         json.dumps(req.get("knowledge_base_ids", [])), json.dumps(req.get("skill_ids", [])),
         json.dumps(req.get("mcp_server_ids", [])), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"id": agent_id, "name": name}

# ── Workflow 管理 ──────────────────────────────────────────────
@app.get("/api/workflows")
async def list_workflows(current_user: Dict = require_auth()):
    """获取工作流列表"""
    conn = get_db()
    workflows = conn.execute("SELECT * FROM workflows ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(w) for w in workflows]

@app.post("/api/workflows")
async def create_workflow(req: dict, current_user: Dict = require_auth()):
    """创建工作流"""
    import uuid
    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, description, definition, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (workflow_id, req.get("name", ""), req.get("description", ""),
         json.dumps(req.get("definition", {})), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"id": workflow_id, "name": req.get("name", "")}

# ── 会话管理 ──────────────────────────────────────────────────
@app.get("/api/sessions")
async def list_sessions(agent_id: str = None, current_user: Dict = require_auth()):
    """获取会话列表"""
    conn = get_db()
    if agent_id:
        sessions = conn.execute("SELECT * FROM sessions WHERE agent_id=? ORDER BY created_at DESC", (agent_id,)).fetchall()
    else:
        sessions = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(s) for s in sessions]

@app.post("/api/sessions")
async def create_session(req: dict, current_user: Dict = require_auth()):
    """创建新会话"""
    import uuid
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    agent_id = req.get("agent_id", "")
    title = req.get("title", "")
    conn = get_db()
    conn.execute(
        """INSERT INTO sessions (id, agent_id, title, created_at)
           VALUES (?, ?, ?, ?)""",
        (session_id, agent_id, title, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"session_id": session_id}

# ── 初始化 ─────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Smart R&D Platform v7.0 started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)
