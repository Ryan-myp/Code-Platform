#!/usr/bin/env python3
"""鉴权 — bcrypt 密码哈希 + JWT 令牌 + 用户 CRUD。

修复旧实现用裸 sha256 哈希密码的安全问题。
函数签名对齐 tests/unit/test_auth.py 的契约。
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Any

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from common.config import ALGORITHM, SECRET_KEY, TOKEN_EXPIRE_MINUTES

logger = logging.getLogger(__name__)

security = HTTPBearer()

# bcrypt 限制密码 72 字节，截断处理避免 ValueError
_BCRYPT_MAX_BYTES = 72


# ══════════════════════════════════════════════════════════════
# 密码哈希（直接使用 bcrypt，避免 passlib 与 bcrypt 4.x 的兼容问题）
# ══════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    """bcrypt 哈希密码，返回字符串。"""
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码。兼容旧的 sha256 哈希（迁移期自动升级为 bcrypt）。"""
    if not password_hash:
        return False
    # bcrypt 哈希以 $2 开头
    if password_hash.startswith("$2"):
        try:
            pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
            return bcrypt.checkpw(pw, password_hash.encode("utf-8"))
        except Exception:
            return False
    # 兼容旧 sha256（无 salt），仅用于过渡
    return hashlib.sha256(password.encode()).hexdigest() == password_hash


# ══════════════════════════════════════════════════════════════
# JWT 令牌
# ══════════════════════════════════════════════════════════════

def create_access_token(subject: str, extra: dict = None, expires_delta: timedelta = None) -> str:
    """创建 JWT。subject 通常是 username。"""
    to_encode = {"sub": subject}
    if extra:
        to_encode.update(extra)
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# 旧代码使用的别名
create_token = create_access_token


def decode_access_token(token: str) -> dict:
    """解码并校验 JWT。失败抛 401。"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        logger.warning(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期令牌",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


decode_token = decode_access_token


# ══════════════════════════════════════════════════════════════
# 用户 CRUD
# ══════════════════════════════════════════════════════════════

def _gen_user_id() -> str:
    return f"user_{uuid.uuid4().hex[:12]}"


def create_user(username: str, password: str, role: str = "user") -> dict:
    """创建用户。重名抛 ValueError。"""
    from common.db import get_db

    conn = get_db()
    try:
        existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            raise ValueError(f"用户名已存在: {username}")
        uid = _gen_user_id()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (uid, username, hash_password(password), role, datetime.now().isoformat()),
        )
        conn.commit()
        return {"id": uid, "username": username, "role": role}
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> str | None:
    """校验用户名密码，成功返回 JWT，失败返回 None。"""
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        # 旧 sha256 哈希自动升级为 bcrypt
        if not row["password_hash"].startswith("$2"):
            conn.execute(
                "UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["id"])
            )
            conn.commit()
        return create_access_token(row["username"], {"user_id": row["id"], "role": row["role"]})
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    """登录，返回 {access_token, token_type, user}。失败抛 HTTPException。"""
    token = authenticate_user(username, password)
    if not token:
        raise HTTPException(401, "用户名或密码错误")
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT id, username, role FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": dict(row) if row else {"username": username},
        }
    finally:
        if conn:
            conn.close()


def register_user(username: str, password: str) -> dict:
    """注册新用户并返回登录结果。"""
    create_user(username, password)
    return login_user(username, password)


def ensure_admin_user() -> None:
    """预置 admin 用户（密码来自 ADMIN_PASSWORD 环境变量，默认 admin123）。

    仅在 users 表为空或无 admin 时创建；已存在则跳过。
    """
    from common.db import get_db

    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
        if row:
            return
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, active, created_at) VALUES (?, 'admin', ?, 'admin', 1, ?)",
            ("admin_001", hash_password(admin_password), datetime.now().isoformat()),
        )
        conn.commit()
        logger.info("admin user ensured")
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# FastAPI 依赖
# ══════════════════════════════════════════════════════════════

async def get_current_user(
    request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)  # noqa: B008
) -> dict[str, Any]:
    """FastAPI 依赖：解析 Bearer token 返回用户信息。"""
    payload = decode_access_token(credentials.credentials)
    return {
        "user_id": payload.get("user_id"),
        "username": payload.get("sub"),
        "role": payload.get("role", "viewer"),
        "scope": payload.get("scope", ["read"]),
    }


def require_auth(dependency=Depends(get_current_user)):  # noqa: B008
    """FastAPI 依赖别名：要求登录。用法 `current_user = require_auth()`。"""
    return dependency
