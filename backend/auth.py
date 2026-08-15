#!/usr/bin/env python3
"""鉴权 — bcrypt 密码哈希 + JWT 令牌 + 用户 CRUD。

修复旧实现用裸 sha256 哈希密码的安全问题。
函数签名对齐 tests/unit/test_auth.py 的契约。
"""

import hashlib
import logging
import os
import secrets
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
            conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), row["id"]))
            conn.commit()
        return create_access_token(row["username"], {"user_id": row["id"], "role": row["role"]})
    finally:
        conn.close()


def login_user(username: str, password: str) -> dict:
    """登录，返回 {access_token, token_type, user}。失败抛 HTTPException。"""
    token = authenticate_user(username, password)
    if not token:
        from common.audit import log_audit
        log_audit(user_id=username, action="login", success=False, error="用户名或密码错误")
        raise HTTPException(401, "用户名或密码错误")
    from common.db import get_db
    from common.audit import log_audit

    conn = get_db()
    try:
        row = conn.execute("SELECT id, username, role FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        uid = row["id"] if row else username
        log_audit(user_id=uid, action="login", success=True)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": dict(row) if row else {"username": username},
        }
    finally:
        if conn:
            conn.close()


def register_user(username: str, password: str, invite_code: str = "", share_from: str = "", email: str = "") -> dict:
    """注册新用户（可选邀请码，双方各奖励一次性额度；可选分享来源用于转化统计；可选邮箱用于密码重置/试用提醒）。"""
    from common.db import get_db

    conn = get_db()
    try:
        inviter = None
        if invite_code:
            inviter = conn.execute(
                "SELECT * FROM users WHERE invite_code=? AND active=1", (invite_code.strip().upper(),)
            ).fetchone()
            if not inviter:
                raise ValueError("邀请码无效")
        existing = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            raise ValueError(f"用户名已存在: {username}")
        uid = _gen_user_id()
        # 分享转化来源：仅在分享码真实存在时记录
        share_ref = share_from.strip()
        if share_ref and not conn.execute("SELECT id FROM shares WHERE share_code=?", (share_ref,)).fetchone():
            share_ref = ""
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, active, created_at, invite_code, invited_by, share_from, email)
               VALUES (?, ?, ?, 'user', 1, ?, ?, ?, ?, ?)""",
            (
                uid,
                username,
                hash_password(password),
                datetime.now().isoformat(),
                _gen_invite_code(),
                inviter["id"] if inviter else "",
                share_ref,
                (email or "").strip(),
            ),
        )
        if inviter:
            # 双方各奖励一次性额度
            conn.execute("UPDATE users SET bonus_quota=bonus_quota+? WHERE id=?", (INVITE_REWARD, uid))
            conn.execute("UPDATE users SET bonus_quota=bonus_quota+? WHERE id=?", (INVITE_REWARD, inviter["id"]))
            conn.commit()
            # 记录邀请历史和奖励流水
            from common.auth import record_invite_history, record_invite_reward
            record_invite_history(inviter["id"], uid, invite_code.strip().upper())
            record_invite_reward(uid, INVITE_REWARD, "invite", f"邀请码 {invite_code} 注册奖励")
            record_invite_reward(inviter["id"], INVITE_REWARD, "invite", f"邀请 {username} 注册奖励")
        else:
            conn.commit()
    finally:
        conn.close()
    # v17.0：新注册用户自动授予 7 天 Pro 试用
    grant_free_trial(uid)
    from common.audit import log_audit
    log_audit(user_id=uid, action="register", target_id=username, success=True)
    return login_user(username, password)


# ══════════════════════════════════════════════════════════════
# 用户资料 / 额度（商业版）
# ══════════════════════════════════════════════════════════════

# 会员等级对应的每日免费额度
MEMBERSHIP_QUOTA = {"free": 30, "pro": 200, "vip": 9999}

# 会员套餐定价（元 / 30 天），与前端会员中心一致
# yearly 字段为年付价格（8 折），前端据此展示节省金额
MEMBERSHIP_PLANS = {
    "pro": {
        "name": "专业版",
        "price": 19.9,
        "days": 30,
        "yearly_price": 199,       # 年付 199 元（≈83 折）
        "yearly_discount": 17,     # 年付节省百分比
        "daily_quota": 200,
        "features": ["每日 200 次生成额度", "全部工具畅用", "专属客服支持"],
    },
    "vip": {
        "name": "至尊版",
        "price": 99.0,
        "days": 30,
        "yearly_price": 990,       # 年付 990 元（≈83 折）
        "yearly_discount": 17,
        "daily_quota": 9999,
        "features": ["无限生成额度", "全部工具畅用", "专属客服支持", "新功能抢先体验"],
    },
}

# 团队版按席位定价（元 / 人 / 月），年付 8 折
TEAM_SEAT_PRICING = {
    "pro": {"monthly": 15.0, "yearly": 144.0, "name": "专业版席位"},   # 15/人/月 或 144/人/年
    "vip": {"monthly": 79.0, "yearly": 790.0, "name": "至尊版席位"},   # 79/人/月 或 790/人/年
}

# 企业定制版基础定价（一次性部署费 + 年服务费）
ENTERPRISE_PRICING = {
    "basic": {"setup_fee": 5000, "yearly_service": 6000, "name": "企业基础版"},
    "standard": {"setup_fee": 15000, "yearly_service": 18000, "name": "企业标准版"},
    "premium": {"setup_fee": 50000, "yearly_service": 60000, "name": "企业尊享版"},
}

# ── A/B 定价实验配置 ───────────────────────────────────────────
# 环境变量控制实验分组，前端据此展示不同价格/试用策略
#   AB_TEST_ENABLED=true          启用 A/B 测试
#   AB_TRIAL_DAYS=7|14|30         试用期天数实验组（默认 7）
#   AB_DISCOUNT_CODE=SUMMER20     促销码实验组（折扣码）
#   AB_PRICING_PRO_MONTHLY=2990   专业版月付价格（分，替代默认）
AB_TEST_ENABLED = os.environ.get("AB_TEST_ENABLED", "false").lower() == "true"
AB_TRIAL_DAYS = int(os.environ.get("AB_TRIAL_DAYS", "7"))
AB_DISCOUNT_CODE = os.environ.get("AB_DISCOUNT_CODE", "").strip().upper()
AB_PRICING_PRO_MONTHLY = os.environ.get("AB_PRICING_PRO_MONTHLY", "").strip()
AB_PRICING_VIP_MONTHLY = os.environ.get("AB_PRICING_VIP_MONTHLY", "").strip()


def get_ab_trial_days() -> int:
    """返回 A/B 实验分配的试用期天数。"""
    if not AB_TEST_ENABLED:
        return 7
    return AB_TRIAL_DAYS


def get_ab_pricing_override(plan: str) -> int | None:
    """返回 A/B 实验组的价格覆盖（分），无覆盖则返回 None。"""
    if not AB_TEST_ENABLED:
        return None
    if plan == "pro" and AB_PRICING_PRO_MONTHLY:
        try:
            return int(AB_PRICING_PRO_MONTHLY)
        except ValueError:
            pass
    if plan == "vip" and AB_PRICING_VIP_MONTHLY:
        try:
            return int(AB_PRICING_VIP_MONTHLY)
        except ValueError:
            pass
    return None


def get_ab_discount_code() -> str:
    """返回 A/B 实验组的促销码（可为空）。"""
    return AB_DISCOUNT_CODE

# 邀请注册双方各奖励的一次性额度（不随天重置）
INVITE_REWARD = 5

# 分享裂变奖励：分享被去重有效访问达阈值 → 一次性奖励额度（每分享封顶一次，防刷）
SHARE_VISIT_THRESHOLD = 10
SHARE_VISIT_REWARD = 5


def _effective_membership(row: dict) -> str:
    """会员到期自动降级为 free（读取视角，不落库）。"""
    m = row.get("membership") or "free"
    if m != "free":
        exp = row.get("membership_expires")
        if exp and exp <= datetime.now().isoformat():
            return "free"
    return m


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load_user(user_id: str) -> dict | None:
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        # 惰性落库降级：会员已到期 → 立即降级为 free（与 _effective_membership 读取视角保持一致）
        m = d.get("membership") or "free"
        if m != "free":
            exp = d.get("membership_expires")
            if exp and exp <= datetime.now().isoformat():
                conn.execute(
                    "UPDATE users SET membership='free', membership_expires=NULL, daily_quota=NULL WHERE id=?",
                    (user_id,),
                )
                conn.commit()
                d["membership"] = "free"
                d["membership_expires"] = None
                d["daily_quota"] = None
                logger.info("membership expired, user %s downgraded to free", user_id)
        return d
    finally:
        conn.close()


def get_user_relay_config(user_id: str) -> dict:
    """读取用户配置的中转站 key/base_url（模式 B：用户自带 token，平台卖 token 盈利）。

    返回 {"api_key": str, "api_base": str}；未配置时 base 为空串（继承全局）。
    """
    from common.db import get_db

    if not user_id:
        return {}
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT relay_api_key, relay_api_base, relay_provider, relay_keys FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if not row:
            return {}
        provider = (row["relay_provider"] or "aixinghuo").strip()
        api_key = ""
        # v1.0.30：优先按供应商从 relay_keys 读（多供应商 key 分存，互不覆盖）
        try:
            import json as _json

            keys = _json.loads(row["relay_keys"] or "{}") if row["relay_keys"] else {}
            if isinstance(keys, dict):
                api_key = (keys.get(provider) or "").strip()
        except Exception:
            api_key = ""
        if not api_key:
            api_key = (row["relay_api_key"] or "").strip()
        return {
            "api_key": api_key,
            "api_base": (row["relay_api_base"] or "").strip(),
            "provider": provider,
        }
    finally:
        conn.close()


def get_user_profile(user_id: str) -> dict:
    """返回用户完整资料（含会员与额度），user_id 可能为 None（老 token）。"""
    if not user_id:
        return {"username": "guest", "role": "viewer", "membership": "free"}
    row = _load_user(user_id)
    if not row:
        return {"username": "guest", "role": "viewer", "membership": "free"}
    # 跨天自动重置每日已用次数
    used_today = row.get("used_today") or 0
    if row.get("last_quota_date") != _today():
        used_today = 0
    membership = _effective_membership(row)
    bonus = row.get("bonus_quota") or 0
    daily_quota = row.get("daily_quota") or MEMBERSHIP_QUOTA.get(membership, 30)
    return {
        "id": row["id"],
        "username": row["username"],
        "nickname": row.get("nickname") or "",
        "avatar": row.get("avatar") or "",
        "email": row.get("email") or "",
        "role": row["role"],
        "membership": membership,
        "membership_expires": row.get("membership_expires"),
        "trial_expires": row.get("trial_expires"),
        "invite_code": row.get("invite_code") or "",
        "daily_quota": daily_quota,
        "bonus_quota": bonus,
        "used_today": used_today,
        "remaining_today": max(0, daily_quota + bonus - used_today),
        "total_usage": row.get("total_usage") or 0,
        "created_at": row.get("created_at"),
        "relay_configured": bool(
            row.get("relay_api_key")
            or (row.get("relay_keys") and row["relay_keys"].strip() not in ("", "{}"))
        ),
    }


def update_user_profile(user_id: str, nickname: str = None, avatar: str = None, email: str = None) -> dict:
    """更新昵称/头像/邮箱，返回最新资料。"""
    from common.db import get_db

    conn = get_db()
    try:
        sets, params = [], []
        if nickname is not None:
            sets.append("nickname=?")
            params.append(nickname[:30])
        if avatar is not None:
            sets.append("avatar=?")
            params.append(avatar[:500])
        if email is not None:
            sets.append("email=?")
            params.append((email or "").strip()[:120])
        if sets:
            params.append(user_id)
            conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", params)
            conn.commit()
        return get_user_profile(user_id)
    finally:
        conn.close()


def change_password(user_id: str, old_password: str, new_password: str) -> None:
    """修改密码。旧密码错误抛 HTTPException(400)。"""
    row = _load_user(user_id)
    if not row:
        raise HTTPException(400, "用户不存在")
    if not verify_password(old_password, row["password_hash"]):
        raise HTTPException(400, "原密码错误")
    if len(new_password) < 6:
        raise HTTPException(400, "新密码至少 6 位")
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(new_password), user_id),
        )
        conn.commit()
    finally:
        conn.close()


def consume_quota(user_id: str) -> dict:
    """额度（本地免费版：不设次数限制，用户有中转站 token 即可随意使用，计费在中转站）。"""
    return {"allowed": True, "remaining": 9999, "charged": False}
    membership = _effective_membership(row)
    daily_quota = row.get("daily_quota") or MEMBERSHIP_QUOTA.get(membership, 30)
    # 会员无限制
    if membership == "vip":
        return {"allowed": True, "remaining": 9999, "charged": False}
    bonus = row.get("bonus_quota") or 0
    available = daily_quota + bonus
    used = 0 if row.get("last_quota_date") != today else (row.get("used_today") or 0)
    if used >= available:
        return {"allowed": False, "remaining": 0, "daily_quota": daily_quota, "charged": False}
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET used_today=?, last_quota_date=?, total_usage=total_usage+1 WHERE id=?",
            (used + 1, today, user_id),
        )
        conn.commit()
        return {
            "allowed": True,
            "remaining": max(0, available - used - 1),
            "daily_quota": daily_quota,
            "charged": True,
        }
    finally:
        conn.close()


def _refund_eligible(row: Any) -> bool:
    """退费资格：仅真实计费用户（非 admin/vip）且当日确有扣费。"""
    if row.get("role") == "admin":
        return False
    if _effective_membership(row) == "vip":
        return False
    if row.get("last_quota_date") != _today():
        return False  # 跨天后当日计数已重置，无费可退
    return (row.get("used_today") or 0) > 0


def refund_quota(user_id: str, conn: Any | None = None) -> bool:
    """失败退费：回退 1 次当日额度（商业公平：失败不扣费）。

    与扣费同规则：admin/vip 不限量无需退；跨天后当日计数已重置，无费可退；
    used_today 下限 0 防负数。返回是否实际退费（供调用方记录/去重）。

    conn: 可选连接——调用方已持有写事务（如任务失败标记）时传入同一连接，
    保证退费与状态更新同事务原子提交，避免跨连接 SQLite 写锁竞争。
    """
    if not user_id:
        return False
    row = _load_user(user_id)
    if not row or not _refund_eligible(row):
        return False
    used = row.get("used_today") or 0
    own_conn = conn is None
    if own_conn:
        from common.db import get_db

        conn = get_db()
    try:
        conn.execute(
            "UPDATE users SET used_today=?, "
            "total_usage=CASE WHEN total_usage>0 THEN total_usage-1 ELSE 0 END "
            "WHERE id=? AND used_today>0",
            (used - 1, user_id),
        )
        if own_conn:
            conn.commit()
        logger.info("额度退费: user=%s（%d -> %d）", user_id, used, used - 1)
        return True
    except Exception:
        logger.exception("额度退费失败: user=%s", user_id)
        return False
    finally:
        if own_conn:
            conn.close()


def get_quota_info(user_id: str) -> dict:
    """查询当前额度信息（不扣减），含会员到期提醒数据。"""
    profile = get_user_profile(user_id)
    _maybe_send_expiry_notice(user_id)  # 惰性发送到期提醒（≤3 天，去重）
    # 本地免费版：无次数限制（有中转站 token 即可随意使用）
    return {
        "membership": "free",
        "membership_expires": None,
        "membership_days_left": None,
        "username": profile.get("username", ""),
        "role": profile.get("role", ""),
        "daily_quota": None,
        "bonus_quota": 0,
        "used_today": 0,
        "remaining_today": 9999,
        "total_usage": profile.get("total_usage", 0),
        "relay_billed": True,
    }
    exp = profile.get("membership_expires")
    days_left = None
    if exp and profile["membership"] != "free":
        try:
            days_left = max(0, (datetime.fromisoformat(exp).date() - datetime.now().date()).days + 1)
        except ValueError:
            days_left = None
    return {
        "membership": profile.get("membership", "free"),
        "membership_expires": exp,
        "membership_days_left": days_left,
        "username": profile.get("username", ""),
        "role": profile.get("role", ""),  # 供前端识别 admin 豁免（水印/1080p/配额）
        "daily_quota": profile.get("daily_quota", 30),
        "bonus_quota": profile.get("bonus_quota", 0),
        "used_today": profile.get("used_today", 0),
        "remaining_today": profile.get("remaining_today", 30),
        "total_usage": profile.get("total_usage", 0),
    }


# ══════════════════════════════════════════════════════════════
# 结果分享（商业版：引流传播）
# ══════════════════════════════════════════════════════════════


def create_share(user_id: str, content_type: str, title: str, content: str) -> dict:
    """创建分享记录，返回带 share_code 的分享信息。"""
    import secrets

    from common.db import get_db

    share_id = f"share_{uuid.uuid4().hex[:12]}"
    share_code = secrets.token_urlsafe(10)
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO shares (id, share_code, user_id, content_type, title, content, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (share_id, share_code, user_id, content_type, title[:100], content, datetime.now().isoformat()),
        )
        conn.commit()
        return {
            "id": share_id,
            "share_code": share_code,
            "content_type": content_type,
            "title": title[:100],
            "created_at": datetime.now().isoformat(),
        }
    finally:
        conn.close()


def get_share(share_code: str) -> dict | None:
    """按 share_code 查询分享内容（访问时 +1 浏览量）。"""
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM shares WHERE share_code=?", (share_code,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE shares SET views=views+1 WHERE id=?", (row["id"],))
        conn.commit()
        return dict(row)
    finally:
        conn.close()


def _share_owner_if_eligible(share: dict, visitor_key: str) -> str | None:
    """裂变奖励资格：无效 key 或分享者本人访问 → None（不计）；否则返回分享者 user_id。"""
    if not visitor_key or not share:
        return None
    owner = str(share.get("user_id") or "")
    if visitor_key.startswith("u:") and visitor_key[2:] == owner:
        return None  # 分享者本人不计
    return owner


def _apply_share_reward(conn: Any, sid: str, owner: str, own_conn: bool) -> bool:
    """发放分享奖励（幂等：仅 rewarded=0 时发），返回是否发放。"""
    cur = conn.execute(
        "UPDATE shares SET rewarded=1, reward_quota=? WHERE id=? AND rewarded=0",
        (SHARE_VISIT_REWARD, sid),
    )
    if cur.rowcount and owner:
        conn.execute("UPDATE users SET bonus_quota=bonus_quota+? WHERE id=?", (SHARE_VISIT_REWARD, owner))
        if own_conn:
            conn.commit()
        logger.info("分享裂变奖励: share=%s owner=%s +%d 额度", sid, owner, SHARE_VISIT_REWARD)
        return True
    if own_conn:
        conn.commit()
    return False


def grant_share_visit_reward(share: dict, visitor_key: str, conn: Any | None = None) -> dict:
    """分享访问奖励（裂变闭环）：有效访问（去重后）达阈值且未发过奖 → 分享者得一次性额度。

    规则：
    - 分享者本人访问不计（visitor_key 为 u:{uid} 且等于分享者）
    - 同访问者对同一分享只计一次（main._record_share_visit 插入时已去重）
    - 每分享最多奖励一次（rewarded 标志幂等，防刷成本可控）
    conn: 可选连接——调用方持有写事务时传入，与事务同提交。
    """
    owner = _share_owner_if_eligible(share, visitor_key)
    if owner is None:
        return {"counted": False, "rewarded": False}
    from common.db import get_db

    own_conn = conn is None
    if own_conn:
        conn = get_db()
    try:
        sid = share["id"]
        row = conn.execute("SELECT rewarded FROM shares WHERE id=?", (sid,)).fetchone()
        if row and row["rewarded"]:
            return {"counted": True, "rewarded": False}  # 已发过奖，不再重复
        valid = conn.execute(
            """SELECT COUNT(*) AS c FROM share_visits
               WHERE share_id=? AND visitor_key!='' AND visitor_key <> 'u:'||?""",
            (sid, owner),
        ).fetchone()["c"]
        if valid < SHARE_VISIT_THRESHOLD:
            return {"counted": True, "rewarded": False}
        rewarded = _apply_share_reward(conn, sid, owner, own_conn)
        return {"counted": True, "rewarded": rewarded}
    except Exception:
        logger.exception("分享裂变奖励失败: share=%s", share.get("id"))
        return {"counted": False, "rewarded": False}
    finally:
        if own_conn:
            conn.close()


def get_my_share_stats(user_id: str) -> dict:
    """我的分享工作台：每分享的访问 / 注册转化 / 裂变奖励进度 + 全局汇总。"""
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM shares WHERE user_id=? ORDER BY created_at DESC LIMIT 100", (user_id,)
        ).fetchall()
        items = []
        totals = {"visits": 0, "conversions": 0, "reward_earned": 0}
        for r in rows:
            sid = r["id"]
            visits = conn.execute("SELECT COUNT(*) AS c FROM share_visits WHERE share_id=?", (sid,)).fetchone()["c"]
            conversions = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE share_from=?", (r["share_code"],)
            ).fetchone()["c"]
            reward = r["reward_quota"] or 0
            totals["visits"] += visits
            totals["conversions"] += conversions
            totals["reward_earned"] += reward
            items.append(
                {
                    "id": sid,
                    "share_code": r["share_code"],
                    "title": r["title"] or f"{r['content_type']} 分享",
                    "content_type": r["content_type"],
                    "views": r["views"],
                    "visits": visits,
                    "conversions": conversions,
                    "rewarded": bool(r["rewarded"]),
                    "reward_quota": reward,
                    "created_at": r["created_at"],
                }
            )
        totals["threshold"] = SHARE_VISIT_THRESHOLD
        totals["reward_per_share"] = SHARE_VISIT_REWARD
        totals["reward_per_invite"] = INVITE_REWARD
        return {"shares": items, "totals": totals}
    finally:
        conn.close()


def _maybe_send_expiry_notice(user_id: str) -> None:
    """惰性发送会员到期提醒站内信：距到期 ≤3 天时触发，target_id 存到期日期去重。"""
    row = _load_user(user_id)
    if not row:
        return
    m = row.get("membership") or "free"
    exp = row.get("membership_expires")
    if m == "free" or not exp:
        return
    try:
        days_left = (datetime.fromisoformat(exp).date() - datetime.now().date()).days
    except ValueError:
        return
    if days_left > 3:
        return
    from common.db import get_db

    conn = get_db()
    try:
        key = f"expiry:{exp[:10]}"
        dup = conn.execute(
            "SELECT id FROM notifications WHERE user_id=? AND type='membership_expiry' AND target_id=?",
            (row["username"], key),
        ).fetchone()
        if dup:
            return
        plan_name = MEMBERSHIP_PLANS.get(m, {}).get("name", m)
        title = f"会员将于 {exp[:10]} 到期" if days_left > 0 else "会员今日到期"
        content = (
            f"您的{plan_name}会员还剩 {days_left} 天到期" if days_left > 0 else f"您的{plan_name}会员今日到期"
        ) + "，到期后将自动降级为免费版，建议尽快续费以免影响使用。"
        conn.execute(
            """INSERT INTO notifications (id, type, title, content, target_type, target_id, user_id, created_at)
               VALUES (?, 'membership_expiry', ?, ?, 'membership', ?, ?, ?)""",
            (f"notif_{uuid.uuid4().hex[:12]}", title, content, key, row["username"], datetime.now().isoformat()),
        )
        conn.commit()
        logger.info("expiry notice sent to %s (%s days left)", row["username"], days_left)
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 会员订单（商业版：支付闭环）
# ══════════════════════════════════════════════════════════════

# 订单超时自动关闭：pending 7 天未提交凭证 / paid 14 天未审核 → expired
ORDER_EXPIRE_DAYS = {"pending": 7, "paid": 14}

# ── 优惠券 / 折扣码 ───────────────────────────────────────────


def validate_coupon(code: str) -> dict:
    """校验优惠券：存在 / 启用 / 未过期 / 未超用。无效抛 HTTPException(400)。"""
    from common.db import get_db

    code = (code or "").strip()
    if not code:
        raise HTTPException(400, "请填写优惠码")
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM coupons WHERE code=?", (code.upper(),)).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(400, "优惠码不存在")
    c = dict(row)
    if not c.get("active"):
        raise HTTPException(400, "优惠码已停用")
    exp = c.get("expires_at")
    if exp and exp < datetime.now().isoformat():
        raise HTTPException(400, "优惠码已过期")
    if (c.get("used_count") or 0) >= (c.get("max_uses") or 1):
        raise HTTPException(400, "优惠码已被用完")
    return c


def coupon_discount(price: float, coupon: dict) -> float:
    """按优惠券类型计算折扣后金额。"""
    if not coupon:
        return price
    value = float(coupon.get("value") or 0)
    if coupon.get("discount_type") == "percent":
        return round(max(0.0, price * (100 - min(value, 99)) / 100), 2)
    return round(max(0.0, price - value), 2)


def expire_stale_orders() -> int:
    """惰性关闭超时订单（查询/创建订单时自动触发），返回关闭数量。"""
    from common.db import get_db

    conn = get_db()
    try:
        now = datetime.now()
        cur = conn.execute(
            """UPDATE orders SET status='expired'
               WHERE status IN ('pending', 'paid')
                 AND ((status='pending' AND created_at < ?)
                   OR (status='paid' AND created_at < ?))""",
            (
                (now - timedelta(days=ORDER_EXPIRE_DAYS["pending"])).isoformat(),
                (now - timedelta(days=ORDER_EXPIRE_DAYS["paid"])).isoformat(),
            ),
        )
        n = cur.rowcount
        if n:
            conn.commit()
            logger.info("%s stale orders auto-expired", n)
        return n
    finally:
        conn.close()


def create_order(user_id: str, plan: str, coupon_code: str = "", stripe_session_id: str = "") -> dict:
    """创建会员订单；同一用户仅允许 1 个待处理订单。可选优惠码抵扣。"""
    if plan not in MEMBERSHIP_PLANS:
        raise HTTPException(400, "无效的会员套餐")
    expire_stale_orders()  # 先清理超时旧单，避免阻塞新订单
    coupon = validate_coupon(coupon_code) if coupon_code else None
    from common.db import get_db

    conn = get_db()
    try:
        pending = conn.execute(
            "SELECT id FROM orders WHERE user_id=? AND status IN ('pending','paid')", (user_id,)
        ).fetchone()
        if pending:
            raise HTTPException(400, "您已有待处理订单，请等待管理员审核")
        order_id = f"order_{uuid.uuid4().hex[:12]}"
        plan_info = MEMBERSHIP_PLANS[plan]
        original = plan_info["price"]
        amount = coupon_discount(original, coupon)
        conn.execute(
            """INSERT INTO orders (id, user_id, plan, amount, original_amount, coupon_code, stripe_session_id, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (order_id, user_id, plan, amount, original, coupon["code"] if coupon else "", stripe_session_id, datetime.now().isoformat()),
        )
        if coupon:
            conn.execute("UPDATE coupons SET used_count=used_count+1 WHERE id=?", (coupon["id"],))
        conn.commit()
        return dict(conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    finally:
        conn.close()


def get_my_orders(user_id: str) -> list[dict]:
    """我的订单（倒序）。"""
    expire_stale_orders()  # 惰性关闭超时订单
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def submit_voucher(order_id: str, user_id: str, voucher: str, remark: str = "") -> dict:
    """提交支付凭证（截图路径或说明），订单 pending → paid（待审核）。"""
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row or row["user_id"] != user_id:
            raise HTTPException(404, "订单不存在")
        if row["status"] != "pending":
            raise HTTPException(400, "当前订单状态不可提交凭证")
        conn.execute(
            "UPDATE orders SET voucher=?, remark=?, status='paid' WHERE id=?",
            (voucher[:500], remark[:200], order_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    finally:
        conn.close()


def review_order(order_id: str, reviewer_id: str, approve: bool) -> dict:
    """管理员审核订单：通过则开通对应会员（30 天），拒绝则关闭订单。"""
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(404, "订单不存在")
        if row["status"] != "paid":
            raise HTTPException(400, "仅可审核已提交凭证的订单")
        if approve:
            plan = MEMBERSHIP_PLANS.get(row["plan"])
            if not plan:
                raise HTTPException(400, "套餐无效")
            expires = (datetime.now() + timedelta(days=plan["days"])).isoformat()
            conn.execute(
                "UPDATE users SET membership=?, membership_expires=?, daily_quota=? WHERE id=?",
                (row["plan"], expires, plan["daily_quota"], row["user_id"]),
            )
        else:
            # 拒绝订单 → 回退优惠码占用次数
            if row["coupon_code"]:
                conn.execute(
                    "UPDATE coupons SET used_count=MAX(0, used_count-1) WHERE code=?",
                    (row["coupon_code"],),
                )
        conn.execute(
            "UPDATE orders SET status=?, reviewed_at=?, reviewed_by=? WHERE id=?",
            ("approved" if approve else "rejected", datetime.now().isoformat(), reviewer_id, order_id),
        )
        conn.commit()
        return dict(conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# 邀请码分销（商业版：引流）
# ══════════════════════════════════════════════════════════════

_INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 去除易混淆字符


def _gen_invite_code() -> str:
    return "".join(secrets.choice(_INVITE_ALPHABET) for _ in range(8))


def get_invite_info(user_id: str) -> dict:
    """邀请信息：我的邀请码 / 已邀请人数 / 奖励规则。"""
    from common.db import get_db

    row = _load_user(user_id)
    if not row:
        raise HTTPException(404, "用户不存在")
    code = row.get("invite_code") or ""
    if not code:
        conn = get_db()
        try:
            code = _gen_invite_code()
            conn.execute("UPDATE users SET invite_code=? WHERE id=?", (code, user_id))
            conn.commit()
        finally:
            conn.close()
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT username, created_at FROM users WHERE invited_by=? ORDER BY created_at DESC LIMIT 100",
            (user_id,),
        ).fetchall()
        invited = [dict(r) for r in rows]
    finally:
        conn.close()
    return {
        "invite_code": code,
        "invited_count": len(invited),
        "reward_per_invite": INVITE_REWARD,
        "invited_users": invited,
    }


def record_invite_history(inviter_id: str, invitee_id: str, invite_code: str) -> None:
    """记录邀请历史。"""
    from common.db import get_db
    import uuid
    hid = f"ih_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO invite_history (id, inviter_id, invitee_id, invite_code, reward_type, reward_amount, status, created_at) VALUES (?, ?, ?, ?, 'invite', ?, 'completed', ?)",
            (hid, inviter_id, invitee_id, invite_code, INVITE_REWARD, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def record_invite_reward(user_id: str, amount: int, source: str, description: str) -> None:
    """记录奖励流水。"""
    from common.db import get_db
    import uuid
    rid = f"ir_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO invite_rewards (id, user_id, reward_type, amount, source, description, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (rid, user_id, 'invite', amount, source, description, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_invite_history(user_id: str, limit: int = 50) -> dict:
    """获取邀请历史列表。"""
    from common.db import get_db
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT ih.id, ih.invitee_id, u.username AS invitee_name, u.created_at AS joined_at, ih.reward_amount, ih.status
               FROM invite_history ih
               LEFT JOIN users u ON u.id = ih.invitee_id
               WHERE ih.inviter_id = ?
               ORDER BY ih.created_at DESC
               LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        history = [dict(r) for r in rows]
        total = len(history)
    finally:
        conn.close()
    return {"history": history, "total": total}


def get_invite_rewards(user_id: str, limit: int = 50) -> dict:
    """获取奖励流水列表。"""
    from common.db import get_db
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, reward_type, amount, source, description, created_at FROM invite_rewards WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        rewards = [dict(r) for r in rows]
        total = len(rewards)
        total_amount = sum(r["amount"] for r in rewards)
    finally:
        conn.close()
    return {"rewards": rewards, "total": total, "total_amount": total_amount}


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
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
) -> dict[str, Any]:
    """FastAPI 依赖：解析 Bearer token 返回用户信息。

    支持两种凭证：
    - JWT（网页登录会话）
    - API Key（xt- 前缀，对外开发者 API 集成，见 _auth_by_api_key）
    """
    token = credentials.credentials
    if token.startswith("xt-"):
        return _auth_by_api_key(token)
    payload = decode_access_token(token)
    user_id = payload.get("user_id")
    # 校验用户仍存在（旧版本 token / 用户已被清理时 → 401，前端触发免登录恢复）
    if user_id:
        from common.db import get_db

        _c = get_db()
        try:
            _exists = _c.execute("SELECT 1 FROM users WHERE id=?", (user_id,)).fetchone()
        finally:
            _c.close()
        if not _exists:
            raise HTTPException(401, "登录状态已失效，请重新登录")
    # 模式 B：加载用户中转站 key 并注入请求上下文（所有 AI 调用按用户走中转站 token）
    try:
        relay = get_user_relay_config(user_id)
        if relay.get("api_key"):
            # 同时携带用户选择的「默认模型」+ 按供应商解析的 api_base
            try:
                from common.config import RELAY_PROVIDERS, resolve_feature_model

                relay["default_model"] = resolve_feature_model(user_id, "default", "")
                provider = (relay.get("provider") or "aixinghuo").lower()
                relay["api_base"] = RELAY_PROVIDERS.get(provider, relay.get("api_base") or "")
            except Exception:
                pass
            from common.relay_context import set_relay_context

            set_relay_context(relay)
    except Exception:
        pass  # 中转站配置加载失败不影响登录（AI 功能会提示配置）
    return {
        "user_id": user_id,
        "username": payload.get("sub"),
        "role": payload.get("role", "viewer"),
        "scope": payload.get("scope", ["read"]),
    }


def _auth_by_api_key(raw_key: str) -> dict[str, Any]:
    """API Key 认证：sha256 比对 api_keys 表，返回绑定用户身份并刷新 last_used。

    开发者通过 /api/api-keys 创建 key 后，可用 Bearer xt-xxx 直接调用
    平台所有 require_auth 端点（配额随绑定用户走），实现外部程序集成。
    """
    from common.db import get_db

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT k.user_id, k.id, k.expires_at, u.username, u.role, u.active FROM api_keys k "
            "JOIN users u ON u.id = k.user_id WHERE k.key_hash=?",
            (key_hash,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")
        if not row["active"]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已禁用")
        # v15：密钥过期校验（expires_at 为空 = 永不过期）
        expires_at = row["expires_at"]
        if expires_at and expires_at <= datetime.now().isoformat():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"API Key 已于 {expires_at[:10]} 过期，请到 API 开放平台重新创建",
            )
        conn.execute("UPDATE api_keys SET last_used=? WHERE id=?", (datetime.now().isoformat(), row["id"]))
        conn.commit()
        return {
            "user_id": row["user_id"],
            "username": row["username"],
            "role": row["role"],
            "scope": ["read", "write"],
            "auth_mode": "api_key",
            "api_key_id": row["id"],
        }
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# v17.0 密码重置 / 免费试用 / 用量明细 / 账单历史
# ══════════════════════════════════════════════════════════════

_FREE_TRIAL_DAYS = 7  # 注册即送 7 天 Pro 试用


def send_password_reset_token(username: str) -> dict:
    """为指定用户名生成一次性重置令牌（存库，有效期 30 分钟）。

    返回 {sent: True/False, reason: ...} —— 为兼容起见，
    无论用户是否存在均返回 sent=True（防枚举攻击）。
    """
    from common.db import get_db

    conn = get_db()
    try:
        user = conn.execute("SELECT id FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if not user:
            return {"sent": True}  # 安全：不暴露用户是否存在
        token = secrets.token_urlsafe(32)
        expires = (datetime.now() + timedelta(minutes=30)).isoformat()
        conn.execute(
            "UPDATE users SET reset_token=?, reset_token_expires=? WHERE id=?",
            (token, expires, user["id"]),
        )
        conn.commit()
        logger.info("password reset token generated for user %s", username)
        return {"sent": True, "token": token}  # 生产环境应发送邮件，此处返回 token 供管理端使用
    except Exception as e:
        logger.error("password reset token generation failed: %s", e)
        return {"sent": False, "reason": str(e)}
    finally:
        conn.close()


def reset_password(token: str, new_password: str) -> dict:
    """用一次性令牌重置密码。"""
    if len(new_password) < 6:
        return {"success": False, "reason": "新密码至少 6 位"}
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, reset_token, reset_token_expires FROM users WHERE reset_token=?",
            (token,),
        ).fetchone()
        if not row:
            return {"success": False, "reason": "无效的重置令牌"}
        if not row["reset_token_expires"] or row["reset_token_expires"] <= datetime.now().isoformat():
            return {"success": False, "reason": "重置令牌已过期，请重新获取"}
        conn.execute(
            "UPDATE users SET password_hash=?, reset_token='', reset_token_expires=NULL WHERE id=?",
            (hash_password(new_password), row["id"]),
        )
        conn.commit()
        logger.info("password reset successful for user %s", row["id"])
        return {"success": True}
    except Exception as e:
        logger.error("password reset failed: %s", e)
        return {"success": False, "reason": str(e)}
    finally:
        conn.close()


def grant_free_trial(user_id: str) -> bool:
    """为新注册用户授予 7 天 Pro 试用（幂等：已在试用期内不重复发放）。"""
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT membership, trial_expires FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if not row:
            return False
        m = row["membership"] or "free"
        trial_exp = row.get("trial_expires")
        # 已在试用期内或已是付费用户则跳过
        if m in ("pro", "vip") or (trial_exp and trial_exp > datetime.now().isoformat()):
            return False
        expires = (datetime.now() + timedelta(days=_FREE_TRIAL_DAYS)).isoformat()
        conn.execute(
            "UPDATE users SET membership='pro', membership_expires=?, trial_expires=? WHERE id=?",
            (expires, expires, user_id),
        )
        conn.commit()
        logger.info("free trial granted to user %s, expires %s", user_id, expires[:10])
        return True
    except Exception as e:
        logger.error("grant_free_trial failed: %s", e)
        return False
    finally:
        conn.close()


def get_usage_detail(user_id: str, days: int = 30) -> list[dict]:
    """按功能分组统计近 N 天的用量明细。"""
    from common.db import get_db

    conn = get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT feature, model, COUNT(*) as cnt,
                       SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                       SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as err
                FROM usage_logs
                WHERE user_id=? AND timestamp>=?
                GROUP BY feature, model
                ORDER BY cnt DESC""",
            (user_id, cutoff),
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "feature": r["feature"] or r["model"] or "unknown",
                "model": r["model"] or "",
                "count": r["cnt"],
                "success": r["ok"],
                "error": r["err"],
            })
        return result
    except Exception as e:
        logger.error("get_usage_detail failed: %s", e)
        return []
    finally:
        conn.close()


def get_usage_daily_timeline(user_id: str, days: int = 30) -> list[dict]:
    """每日用量趋势（用于折线图）。"""
    from common.db import get_db

    conn = get_db()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            """SELECT DATE(timestamp) as day, COUNT(*) as cnt,
                      SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok
               FROM usage_logs
               WHERE user_id=? AND timestamp>=?
               GROUP BY DATE(timestamp)
               ORDER BY day ASC""",
            (user_id, cutoff),
        ).fetchall()
        return [{"date": r["day"], "count": r["cnt"], "success": r["ok"]} for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_billing_history(user_id: str) -> list[dict]:
    """用户账单历史（订单 +  Stripe session 信息）。"""
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, plan, amount, status, voucher, remark, created_at, reviewed_at
               FROM orders WHERE user_id=?
               ORDER BY created_at DESC LIMIT 20""",
            (user_id,),
        ).fetchall()
        result = []
        for r in rows:
            result.append({
                "order_id": r["id"],
                "plan": r["plan"],
                "amount": r["amount"],
                "status": r["status"],
                "voucher": r["voucher"] or "",
                "remark": r["remark"] or "",
                "created_at": r["created_at"],
                "reviewed_at": r["reviewed_at"] or "",
            })
        return result
    except Exception as e:
        logger.error("get_billing_history failed: %s", e)
        return []
    finally:
        conn.close()


def require_auth(dependency=Depends(get_current_user)):  # noqa: B008
    """FastAPI 依赖别名：要求登录。用法 `current_user = require_auth()`。"""
    return dependency
