#!/usr/bin/env python3
"""全局邮件发送模块（SMTP）。

配置来自环境变量（backend/.env）：
    SMTP_HOST     SMTP 服务器（如 smtp.163.com）
    SMTP_PORT     SSL 端口（163/QQ=465）
    SMTP_USER     发件邮箱账号
    SMTP_PASSWORD 客户端授权码（163/QQ 需授权码，非登录密码）
    SMTP_FROM     发件人显示（默认取 SMTP_USER）

使用：
    from common.mailer import send_email, is_smtp_configured
    send_email(to="x@163.com", subject="标题", html="<p>内容</p>")
"""

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465").strip() or "465")
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or SMTP_USER


def is_smtp_configured() -> bool:
    """SMTP 是否已配置完整。"""
    return bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def send_email(to: str, subject: str, html: str = "", text: str = "") -> dict:
    """发送一封邮件。返回 {ok, reason}。"""
    if not is_smtp_configured():
        return {"ok": False, "reason": "SMTP 未配置"}
    if not to:
        return {"ok": False, "reason": "收件人为空"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    if text:
        msg.attach(MIMEText(text, "plain", "utf-8"))
    if html:
        msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [to], msg.as_string())
        logger.info("邮件已发送 -> %s (%s)", to, subject)
        return {"ok": True}
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP 认证失败: %s", e)
        return {"ok": False, "reason": "SMTP 认证失败，请检查账号/授权码"}
    except smtplib.SMTPConnectError as e:
        logger.error("SMTP 连接失败: %s", e)
        return {"ok": False, "reason": "无法连接 SMTP 服务器"}
    except smtplib.SMTPRecipientsRefused as e:
        logger.error("收件人被拒绝: %s", e)
        return {"ok": False, "reason": "收件邮箱不存在或被拒绝"}
    except Exception as e:
        logger.error("邮件发送失败: %s", e)
        return {"ok": False, "reason": f"邮件发送失败"}


def send_password_reset_email(to_email: str, username: str, reset_link: str) -> dict:
    """发送密码重置邮件（带链接）。"""
    html = f"""<html><body style="font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f7;padding:24px">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #eee">
  <h2 style="color:#333;margin:0 0 16px">🔐 重置密码</h2>
  <p style="color:#666;line-height:1.7">你好 <b>{username}</b>：</p>
  <p style="color:#666;line-height:1.7">你刚刚请求重置密码，点击下方按钮完成重置（30 分钟内有效）：</p>
  <p style="text-align:center;margin:28px 0">
    <a href="{reset_link}" style="background:#6366f1;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;display:inline-block">重置密码</a>
  </p>
  <p style="color:#999;font-size:13px;line-height:1.6">如果按钮无法点击，请复制以下链接到浏览器打开：<br>
    <span style="word-break:break-all">{reset_link}</span>
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#bbb;font-size:12px">如果不是你本人操作，请忽略此邮件，你的账号是安全的。</p>
</div></body></html>"""
    text = f"你好 {username}，重置密码链接（30分钟有效）：{reset_link}"
    return send_email(to=to_email, subject="[小团智能平台] 密码重置", html=html, text=text)


def send_trial_expiry_email(to_email: str, username: str, days_left: int) -> dict:
    """发送试用期即将到期提醒。"""
    html = f"""<html><body style="font-family:'PingFang SC','Microsoft YaHei',sans-serif;background:#f5f5f7;padding:24px">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;border:1px solid #eee">
  <h2 style="color:#333;margin:0 0 16px">⏰ 试用即将到期</h2>
  <p style="color:#666;line-height:1.7">你好 <b>{username}</b>：</p>
  <p style="color:#666;line-height:1.7">你的 <b>Pro 试用</b> 还剩 <b style="color:#f59e0b">{days_left} 天</b>，到期后将继续使用免费版（每日 30 次）。</p>
  <p style="text-align:center;margin:28px 0">
    <a href="https://localhost:5173/membership" style="background:#6366f1;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;display:inline-block">查看会员方案</a>
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#bbb;font-size:12px">小团智能平台 · AI赋能智效未来</p>
</div></body></html>"""
    return send_email(to=to_email, subject="[小团智能平台] 试用即将到期", html=html)
