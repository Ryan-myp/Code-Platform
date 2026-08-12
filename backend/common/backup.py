#!/usr/bin/env python3
"""数据库自动备份 — 在线快照 + 保留轮转 + 管理端点。

v12.0 新增：
- create_backup(): SQLite backup API 在线快照（不中断服务），
  保存到 backend/backups/platform-YYYYMMDD-HHMMSS.db，保留最近 10 份自动轮转
- ensure_daily_backup(): 每日一次自动备份（按日期标记去重，服务启动时调用）
- 管理端点（仅管理员）：
  POST /api/admin/backups            手动创建备份
  GET   /api/admin/backups           备份列表
  POST  /api/admin/backups/{name}/restore  恢复（恢复前自动留安全网快照）
"""

import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from common.auth import require_auth
from common.safe_guard import safe_api

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["备份管理"])

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
KEEP_MAX = 10  # 保留最近 10 份快照
_DAILY_MARK = BACKUP_DIR / ".last_daily"


def _ensure_dir() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _db_path() -> str:
    """当前生效的数据库路径（DB_PATH 环境变量优先，兼容测试）。"""
    return os.environ.get("DB_PATH") or str(Path(__file__).resolve().parent.parent / "platform.db")


def create_backup() -> dict:
    """在线快照数据库（SQLite backup API，服务不中断）。返回备份信息。"""
    _ensure_dir()
    # 毫秒级文件名：同一秒内多次创建（如连续手动触发）不会互相覆盖
    name = f"platform-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.db"
    dst = BACKUP_DIR / name
    src = sqlite3.connect(_db_path(), timeout=30)
    try:
        dst_conn = sqlite3.connect(str(dst), timeout=30)
        try:
            src.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src.close()
    _rotate()
    info = {
        "name": name,
        "path": str(dst),
        "size": dst.stat().st_size,
        "created_at": datetime.now().isoformat(),
    }
    logger.info(f"backup created: {name} ({info['size']} bytes)")
    return info


def _rotate() -> None:
    """保留最近 KEEP_MAX 份快照，更早的自动删除。"""
    files = sorted(BACKUP_DIR.glob("platform-*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[KEEP_MAX:]:
        try:
            f.unlink()
            logger.info(f"backup rotated: {f.name}")
        except OSError:
            logger.warning(f"backup rotate failed: {f}")


def list_backups() -> list[dict]:
    """备份列表（按创建时间倒序）。"""
    _ensure_dir()
    rows = []
    for f in sorted(BACKUP_DIR.glob("platform-*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
        rows.append(
            {
                "name": f.name,
                "size": f.stat().st_size,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
        )
    return rows


def restore_backup(name: str) -> dict:
    """从快照恢复数据库。恢复前自动备份当前数据作为安全网。

    name 校验：仅接受 backups/ 目录下 platform-*.db 格式文件名，防路径穿越。
    """
    _ensure_dir()
    if not name.startswith("platform-") or not name.endswith(".db") or "/" in name or "\\" in name:
        raise ValueError("备份文件名不合法")
    src_path = BACKUP_DIR / name
    if not src_path.exists():
        raise ValueError("备份文件不存在")

    # 安全网：恢复前先备份当前数据
    safety = create_backup()
    src = sqlite3.connect(str(src_path), timeout=30)
    try:
        dst = sqlite3.connect(_db_path(), timeout=30)
        try:
            dst.backup(src)
        finally:
            dst.close()
    finally:
        src.close()
    logger.warning(f"backup restored from {name} (safety snapshot: {safety['name']})")
    return {
        "success": True,
        "name": name,
        "safety_backup": safety["name"],
        "message": "恢复成功（建议重启服务使缓存与连接完全刷新）",
    }


def ensure_daily_backup() -> bool:
    """每日一次自动备份（按 .last_daily 标记跨天去重）。返回是否执行了备份。"""
    _ensure_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        last = _DAILY_MARK.read_text().strip() if _DAILY_MARK.exists() else ""
    except OSError:
        last = ""
    if last == today:
        return False
    result = create_backup()
    try:
        _DAILY_MARK.write_text(today)
    except OSError:
        pass
    logger.info(f"daily backup marked: {today}")
    # 异步上传远程（不阻塞主流程）
    try:
        from concurrent.futures import ThreadPoolExecutor
        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(upload_to_remote, result["name"])
    except Exception:
        pass
    return True


# ── 异地备份（S3/OSS/MinIO 兼容存储）───────────────────────────────
_REMOTE_BACKUP_BUCKET = os.environ.get("BACKUP_BUCKET", "").strip()
_REMOTE_BACKUP_ENDPOINT = os.environ.get("BACKUP_ENDPOINT", "").strip()
_REMOTE_BACKUP_ACCESS_KEY = os.environ.get("BACKUP_ACCESS_KEY", "").strip()
_REMOTE_BACKUP_SECRET_KEY = os.environ.get("BACKUP_SECRET_KEY", "").strip()
_REMOTE_BACKUP_PREFIX = os.environ.get("BACKUP_PREFIX", "backups").strip()


def _remote_enabled() -> bool:
    """检查是否配置了远程备份（S3/OSS/MinIO）。"""
    return bool(
        _REMOTE_BACKUP_BUCKET
        and _REMOTE_BACKUP_ENDPOINT
        and _REMOTE_BACKUP_ACCESS_KEY
        and _REMOTE_BACKUP_SECRET_KEY
    )


def upload_to_remote(backup_name: str) -> dict:
    """上传最新备份到 S3/OSS/MinIO 兼容存储。

    支持三种驱动：boto3（AWS S3）、oss2（阿里云 OSS）、本地 S3 兼容协议。
    未安装对应库时自动跳过并记录警告。
    """
    if not _remote_enabled():
        return {"uploaded": False, "reason": "remote backup not configured"}

    src = BACKUP_DIR / backup_name
    if not src.exists():
        return {"uploaded": False, "reason": f"backup not found: {backup_name}"}

    try:
        import boto3
        from botocore.config import Config as BotoConfig

        endpoint_url = _REMOTE_BACKUP_ENDPOINT
        if "aliyuncs.com" in endpoint_url:
            region = "cn-hangzhou"
        else:
            region = "auto"

        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region if region != "auto" else None,
            aws_access_key_id=_REMOTE_BACKUP_ACCESS_KEY,
            aws_secret_access_key=_REMOTE_BACKUP_SECRET_KEY,
            config=BotoConfig(retries={"max_attempts": 3, "mode": "standard"}),
        )
        remote_key = f"{_REMOTE_BACKUP_PREFIX}/{backup_name}"
        s3.upload_file(str(src), _REMOTE_BACKUP_BUCKET, remote_key)
        logger.info("remote backup uploaded: %s → s3://%s/%s", backup_name, _REMOTE_BACKUP_BUCKET, remote_key)
        return {"uploaded": True, "bucket": _REMOTE_BACKUP_BUCKET, "key": remote_key, "size": src.stat().st_size}
    except ImportError:
        logger.warning("remote backup skipped: boto3 not installed (pip install boto3)")
        return {"uploaded": False, "reason": "boto3 not installed"}
    except Exception as e:
        logger.error("remote backup upload failed: %s", e)
        return {"uploaded": False, "reason": str(e)}


# ── 管理端点（仅管理员） ──────────────────────────────────────


def _require_admin(current_user: dict) -> None:
    if (current_user or {}).get("role") != "admin":
        raise HTTPException(403, "仅管理员可执行备份操作")


@router.post("/backups")
@safe_api
async def admin_create_backup(current_user: dict = require_auth()):
    """手动创建数据库备份。"""
    _require_admin(current_user)
    return create_backup()


@router.get("/backups")
@safe_api
async def admin_list_backups(current_user: dict = require_auth()):
    """备份列表。"""
    _require_admin(current_user)
    backups = list_backups()
    return {"backups": backups, "total": len(backups)}


@router.post("/backups/{name}/restore")
@safe_api
async def admin_restore_backup(name: str, current_user: dict = require_auth()):
    """从快照恢复数据库（恢复前自动留安全网快照）。"""
    _require_admin(current_user)
    try:
        return restore_backup(name)
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
