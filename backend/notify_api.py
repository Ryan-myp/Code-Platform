#!/usr/bin/env python3
"""通知渠道管理（v10.1）。

- 邮件通知（SMTP 配置）
- Webhook URL 配置
- 通知发送测试
"""

import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, HTTPException

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notify", tags=["通知渠道"])


def _ensure_table():
    conn = get_db()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS notify_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                email_enabled INTEGER DEFAULT 0,
                email_smtp_host TEXT DEFAULT '',
                email_smtp_port INTEGER DEFAULT 587,
                email_smtp_user TEXT DEFAULT '',
                email_smtp_password TEXT DEFAULT '',
                email_from TEXT DEFAULT '',
                email_to TEXT DEFAULT '',
                webhook_enabled INTEGER DEFAULT 0,
                webhook_url TEXT DEFAULT '',
                webhook_secret TEXT DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        conn.commit()
    finally:
        conn.close()


_ensure_table()


@router.get("/config")
def get_config(current_user: dict = Depends(require_auth)):
    """获取当前用户的通知配置（敏感字段脱敏）。"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM notify_config WHERE user_id=?",
            (current_user["user_id"],),
        ).fetchone()
        if not row:
            return {
                "email_enabled": False,
                "email_smtp_host": "",
                "email_smtp_port": 587,
                "email_smtp_user": "",
                "email_smtp_password": "",
                "email_from": "",
                "email_to": "",
                "webhook_enabled": False,
                "webhook_url": "",
                "webhook_secret": "",
            }
        cfg = dict(row)
        # 脱敏
        if cfg.get("email_smtp_password"):
            cfg["email_smtp_password"] = "••••••••"
        if cfg.get("webhook_secret"):
            cfg["webhook_secret"] = "••••••••"
        return cfg
    finally:
        conn.close()


@router.put("/config")
def update_config(payload: dict, current_user: dict = Depends(require_auth)):
    """更新通知配置（upsert）。"""
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM notify_config WHERE user_id=?",
            (current_user["user_id"],),
        ).fetchone()

        fields = {
            "email_enabled": int(payload.get("email_enabled", False)),
            "email_smtp_host": payload.get("email_smtp_host", ""),
            "email_smtp_port": payload.get("email_smtp_port", 587),
            "email_smtp_user": payload.get("email_smtp_user", ""),
            "email_smtp_password": payload.get("email_smtp_password", ""),
            "email_from": payload.get("email_from", ""),
            "email_to": payload.get("email_to", ""),
            "webhook_enabled": int(payload.get("webhook_enabled", False)),
            "webhook_url": payload.get("webhook_url", ""),
            "webhook_secret": payload.get("webhook_secret", ""),
            "updated_at": now,
        }

        if existing:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE notify_config SET {set_clause} WHERE user_id=?",
                (*fields.values(), current_user["user_id"]),
            )
        else:
            conn.execute(
                """INSERT INTO notify_config (user_id, email_enabled, email_smtp_host, email_smtp_port,
                   email_smtp_user, email_smtp_password, email_from, email_to,
                   webhook_enabled, webhook_url, webhook_secret, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (current_user["user_id"], *fields.values()),
            )
        conn.commit()
        return {"message": "配置已保存"}
    finally:
        conn.close()


@router.post("/test-email")
def test_email(current_user: dict = Depends(require_auth)):
    """发送测试邮件。"""
    conn = get_db()
    try:
        cfg = conn.execute(
            "SELECT * FROM notify_config WHERE user_id=? AND email_enabled=1",
            (current_user["user_id"],),
        ).fetchone()
    finally:
        conn.close()

    if not cfg:
        raise HTTPException(400, "邮件通知未启用或未配置")

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[小团智能平台] 测试邮件"
        msg["From"] = cfg["email_from"] or cfg["email_smtp_user"]
        msg["To"] = cfg["email_to"]
        msg.attach(MIMEText(
            f"""<html><body>
            <h2>小团智能平台 - 通知测试</h2>
            <p>这是一封测试邮件，用于验证 SMTP 配置是否正确。</p>
            <p>发送时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr><p style='color:#999;font-size:12px'>小团智能平台 · AI赋能智效未来</p>
            </body></html>""",
            "html",
        ))

        with smtplib.SMTP(cfg["email_smtp_host"], cfg["email_smtp_port"], timeout=15) as server:
            server.starttls()
            server.login(cfg["email_smtp_user"], cfg["email_smtp_password"])
            server.sendmail(msg["From"], [cfg["email_to"]], msg.as_string())

        return {"message": "测试邮件发送成功"}
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(400, "SMTP 认证失败，请检查用户名和密码")
    except smtplib.SMTPConnectError:
        raise HTTPException(400, "无法连接 SMTP 服务器，请检查地址和端口")
    except Exception as e:
        raise HTTPException(500, f"发送失败：{str(e)}")


@router.post("/test-webhook")
async def test_webhook(current_user: dict = Depends(require_auth)):
    """发送测试 Webhook。"""
    conn = get_db()
    try:
        cfg = conn.execute(
            "SELECT * FROM notify_config WHERE user_id=? AND webhook_enabled=1",
            (current_user["user_id"],),
        ).fetchone()
    finally:
        conn.close()

    if not cfg or not cfg["webhook_url"]:
        raise HTTPException(400, "Webhook 未启用或未配置")

    payload = {
        "event": "test",
        "timestamp": datetime.now().isoformat(),
        "message": "小团智能平台 Webhook 测试通知",
    }
    headers = {"Content-Type": "application/json"}
    if cfg.get("webhook_secret"):
        headers["X-Webhook-Secret"] = cfg["webhook_secret"]

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(cfg["webhook_url"], json=payload, headers=headers)
        if 200 <= resp.status_code < 300:
            return {"message": f"Webhook 发送成功（HTTP {resp.status_code}）"}
        return {"message": f"Webhook 返回状态码 {resp.status_code}", "body": resp.text[:500]}
    except httpx.ConnectError:
        raise HTTPException(400, "无法连接 Webhook URL，请检查地址")
    except Exception as e:
        raise HTTPException(500, f"发送失败：{str(e)}")
