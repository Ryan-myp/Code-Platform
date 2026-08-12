"""社交登录API — 微信/钉钉 OAuth。

注意：真实OAuth需要申请开发者账号并配置回调地址。
此处提供扩展点和模拟实现，便于后续接入。
"""
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from common.auth import require_auth, login_user, get_user_profile
from common.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["社交登录"])

# OAuth配置（从环境变量读取）
WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_SECRET = os.environ.get("WECHAT_SECRET", "")
DINGTALK_APPID = os.environ.get("DINGTALK_APPID", "")
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "")


class OAuthConfigResponse(BaseModel):
    wechat_enabled: bool = False
    dingtalk_enabled: bool = False
    wechat_appid: str = ""
    dingtalk_appid: str = ""


@router.get("/oauth/config")
async def get_oauth_config():
    """获取社交登录配置状态。"""
    return OAuthConfigResponse(
        wechat_enabled=bool(WECHAT_APPID),
        dingtalk_enabled=bool(DINGTALK_APPID),
        wechat_appid=WECHAT_APPID[:8] + "..." if WECHAT_APPID else "",
        dingtalk_appid=DINGTALK_APPID[:8] + "..." if DINGTALK_APPID else "",
    )


@router.get("/oauth/wechat/login-url")
async def get_wechat_login_url(state: str = ""):
    """获取微信登录跳转URL。"""
    if not WECHAT_APPID:
        raise HTTPException(400, "微信OAuth未配置")
    # 微信OAuth2.0授权URL
    redirect_uri = os.environ.get("WECHAT_REDIRECT_URI", "http://localhost:5173/auth/callback/wechat")
    scope = "snsapi_login"
    url = f"https://open.weixin.qq.com/connect/qrconnect?appid={WECHAT_APPID}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&state={state}#wechat_redirect"
    return {"url": url}


@router.get("/oauth/dingtalk/login-url")
async def get_dingtalk_login_url(state: str = ""):
    """获取钉钉登录跳转URL。"""
    if not DINGTALK_APPID:
        raise HTTPException(400, "钉钉OAuth未配置")
    # 钉钉OAuth2.0授权URL
    redirect_uri = os.environ.get("DINGTALK_REDIRECT_URI", "http://localhost:5173/auth/callback/dingtalk")
    url = f"https://login.dingtalk.com/oauth2/auth?client_id={DINGTALK_APPID}&redirect_uri={redirect_uri}&response_type=code&scope=openid&state={state}"
    return {"url": url}


@router.get("/oauth/wechat/callback")
async def wechat_callback(code: str = Query(...), state: str = ""):
    """微信OAuth回调处理。"""
    if not WECHAT_APPID:
        raise HTTPException(400, "微信OAuth未配置")
    
    # 实际实现需要调用微信API换取access_token
    # 此处返回模拟数据，提示用户配置
    return {
        "enabled": False,
        "message": "微信OAuth未配置，请在环境变量中设置 WECHAT_APPID 和 WECHAT_SECRET",
        "docs": "https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html"
    }


@router.get("/oauth/dingtalk/callback")
async def dingtalk_callback(code: str = Query(...), state: str = ""):
    """钉钉OAuth回调处理。"""
    if not DINGTALK_APPID:
        raise HTTPException(400, "钉钉OAuth未配置")
    
    # 实际实现需要调用钉钉API换取access_token
    # 此处返回模拟数据，提示用户配置
    return {
        "enabled": False,
        "message": "钉钉OAuth未配置，请在环境变量中设置 DINGTALK_APPID 和 DINGTALK_SECRET",
        "docs": "https://open.dingtalk.com/document/orgapp/oauth-authorizing-user"
    }


@router.post("/oauth/bind")
async def bind_oauth(current_user: dict = require_auth(), platform: str = "", openid: str = ""):
    """绑定社交账号到现有账户。"""
    if not platform or not openid:
        raise HTTPException(400, "参数不完整")
    
    user_id = current_user.get("user_id")
    conn = get_db()
    try:
        # 检查是否已绑定
        existing = conn.execute(
            "SELECT id FROM social_bindings WHERE user_id=? AND platform=?",
            (user_id, platform)
        ).fetchone()
        if existing:
            raise HTTPException(400, "该社交账号已绑定")
        
        # 插入绑定记录
        conn.execute(
            """INSERT INTO social_bindings (id, user_id, platform, openid, bound_at)
               VALUES (?, ?, ?, ?, ?)""",
            (f"sb_{uuid.uuid4().hex[:12]}", user_id, platform, openid, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()
    
    return {"success": True, "message": f"{platform}账号绑定成功"}


def ensure_social_bindings_table():
    """确保social_bindings表存在。"""
    from common.db import get_db
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS social_bindings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                openid TEXT NOT NULL,
                bound_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_social_platform ON social_bindings(platform, openid)")
        conn.commit()
    finally:
        conn.close()
