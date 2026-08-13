#!/usr/bin/env python3
from template_base import TemplateBase, create_template
"""模板市场 — 内置模板聚合 + C2C 用户模板交易。

聚合来源：
- game_factory.TEMPLATES  小游戏玩法模板（9 种）
- miniapp.TEMPLATES       小程序结构模板
- meme_factory.STYLES     表情包样式模板
- voice_factory.SCENES    配音场景预设

C2C 用户模板市场：
- 用户上传模板（命名/描述/分类/定价积分）
- 积分购买下载（平台分成可配，默认 30%）
- 我的上传 / 我的购买
"""

import json
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.config import load_config
from common.db import get_db

logger = logging.getLogger(__name__)
load_config()

router = APIRouter(prefix="/api/templates", tags=["模板市场"])

# 各工厂模板常量（轻量 import，避免循环依赖）
from game_factory import TEMPLATES as GAME_TEMPLATES  # noqa: E402
from meme_factory import STYLES as MEME_STYLES  # noqa: E402
from miniapp import TEMPLATES as MINIAPP_TEMPLATES  # noqa: E402
from voice_factory import SCENES as VOICE_SCENES  # noqa: E402


def _usage_stats() -> dict:
    """统计各模板被使用次数（从数据库产物记录聚合）。

    返回 {game: {snake: 3, ...}, miniapp: {...}, meme: {...}, voice: {...}}
    """
    stats = {"game": {}, "miniapp": {}, "meme": {}, "voice": {}}
    try:
        conn = get_db()
        # 小游戏：game_projects.template
        for r in conn.execute("SELECT template, COUNT(*) n FROM game_projects GROUP BY template").fetchall():
            stats["game"][r["template"]] = r["n"]
        # 小程序：miniapp_projects.template
        for r in conn.execute("SELECT template, COUNT(*) n FROM miniapp_projects GROUP BY template").fetchall():
            stats["miniapp"][r["template"]] = r["n"]
        # 表情包：artifacts.metadata.style（author=meme_factory）
        for r in conn.execute("SELECT metadata FROM artifacts WHERE author='meme_factory' AND active=1").fetchall():
            try:
                md = json.loads(r["metadata"] or "{}")
                s = md.get("style", "")
                if s:
                    stats["meme"][s] = stats["meme"].get(s, 0) + 1
            except Exception:
                pass
        # 配音：artifacts.metadata.scene（author=voice_factory）
        for r in conn.execute("SELECT metadata FROM artifacts WHERE author='voice_factory' AND active=1").fetchall():
            try:
                md = json.loads(r["metadata"] or "{}")
                s = md.get("scene", "")
                if s:
                    stats["voice"][s] = stats["voice"].get(s, 0) + 1
            except Exception:
                pass
        conn.close()
    except Exception as e:
        logger.debug(f"_usage_stats skipped: {e}")
    return stats


@router.get("/market")
async def template_market(q: str = "", current_user: dict = require_auth()):
    """模板市场总览：分类聚合 + 跳转路径 + 使用量统计。q 按名称/描述/标签搜索。"""
    usage = _usage_stats()
    games = [
        {
            "id": f"game-{t['id']}",
            "category": "game",
            "tool": "小游戏工坊",
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "icon": t.get("icon", "🎮"),
            "color": t.get("color", "from-brand-500 to-indigo-600"),
            "path": "/games",
            "tags": ["玩法", "双端"],
            "used": usage["game"].get(t["id"], 0),
        }
        for t in GAME_TEMPLATES
    ]
    miniapps = [
        {
            "id": f"miniapp-{t['id']}",
            "category": "miniapp",
            "tool": "小程序工坊",
            "name": t.get("name", ""),
            "description": t.get("description", ""),
            "icon": t.get("icon", "📱"),
            "color": t.get("color", "from-pink-500 to-rose-600"),
            "path": "/miniapp",
            "tags": ["微信小程序"],
            "used": usage["miniapp"].get(t["id"], 0),
        }
        for t in MINIAPP_TEMPLATES
    ]
    memes = [
        {
            "id": f"meme-{t['id']}",
            "category": "meme",
            "tool": "表情包工坊",
            "name": t.get("name", ""),
            "description": t.get("desc", ""),
            "icon": "😜",
            "color": "from-amber-400 to-orange-500",
            "path": "/meme",
            "tags": ["表情包"],
            "used": usage["meme"].get(t["id"], 0),
        }
        for t in MEME_STYLES
    ]
    voices = [
        {
            "id": f"voice-{t['id']}",
            "category": "voice",
            "tool": "配音工坊",
            "name": t.get("name", ""),
            "description": t.get("desc", ""),
            "icon": "🎙️",
            "color": "from-sky-500 to-blue-600",
            "path": "/voice-dubbing",
            "tags": ["配音", "TTS"],
            "used": usage["voice"].get(t["id"], 0),
        }
        for t in VOICE_SCENES
        if t.get("id") != "custom"  # 自定义场景不展示
    ]

    # 搜索过滤
    q_lower = (q or "").strip().lower()
    all_items = games + miniapps + memes + voices
    if q_lower:
        all_items = [
            i
            for i in all_items
            if q_lower in i["name"].lower()
            or q_lower in i["description"].lower()
            or any(q_lower in t.lower() for t in i["tags"])
        ]

    grouped = {
        "game": {
            "label": "小游戏玩法",
            "count": sum(1 for i in all_items if i["category"] == "game"),
            "items": [i for i in all_items if i["category"] == "game"],
        },
        "miniapp": {
            "label": "小程序结构",
            "count": sum(1 for i in all_items if i["category"] == "miniapp"),
            "items": [i for i in all_items if i["category"] == "miniapp"],
        },
        "meme": {
            "label": "表情包样式",
            "count": sum(1 for i in all_items if i["category"] == "meme"),
            "items": [i for i in all_items if i["category"] == "meme"],
        },
        "voice": {
            "label": "配音场景",
            "count": sum(1 for i in all_items if i["category"] == "voice"),
            "items": [i for i in all_items if i["category"] == "voice"],
        },
    }
    return {
        "total": len(all_items),
        "groups": grouped,
    }


# ══════════════════════════════════════════════════════════════
# C2C 用户模板市场（上传 / 定价 / 积分购买 / 分成）
# ══════════════════════════════════════════════════════════════

PLATFORM_SHARE = float(os.environ.get("TEMPLATE_PLATFORM_SHARE", "0.3"))  # 平台分成比例


def _ensure_user_templates(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS user_templates (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'other',
            price INTEGER DEFAULT 0,
            content_json TEXT DEFAULT '{}',
            sales INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS template_purchases (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            template_id TEXT NOT NULL,
            price INTEGER DEFAULT 0,
            seller_id TEXT DEFAULT '',
            created_at TEXT DEFAULT ''
        )"""
    )
    conn.commit()


class TemplateUploadRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=500)
    category: str = Field("other", description="game/miniapp/meme/voice/other")
    price: int = Field(0, ge=0, le=10000, description="定价（积分）")
    content_json: str = Field("{}", description="模板内容 JSON")


@router.post("/upload")
async def upload_template(req: TemplateUploadRequest, current_user: dict = require_auth()):
    """用户上传付费模板到 C2C 市场。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_user_templates(conn)
    tid = f"utpl_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """INSERT INTO user_templates (id, user_id, name, description, category,
           price, content_json, sales, active, created_at)
           VALUES (?,?,?,?,?,?,?,0,1,?)""",
        (tid, user, req.name, req.description, req.category, req.price, req.content_json, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"id": tid, "name": req.name, "price": req.price, "message": "模板已上架"}


@router.get("/user")
async def my_templates(current_user: dict = require_auth()):
    """我的上传模板列表。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_user_templates(conn)
    rows = conn.execute(
        "SELECT * FROM user_templates WHERE user_id=? AND active=1 ORDER BY created_at DESC",
        (user,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/c2c")
async def c2c_market(category: str = "", q: str = "", current_user: dict = require_auth()):
    """C2C 模板市场列表（所有用户上传的付费/免费模板）。"""
    conn = get_db()
    _ensure_user_templates(conn)
    where, params = ["active=1"], []
    if category:
        where.append("category=?")
        params.append(category)
    if q:
        where.append("(name LIKE ? OR description LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    sql = f"SELECT * FROM user_templates WHERE {' AND '.join(where)} ORDER BY sales DESC, created_at DESC LIMIT 100"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/{template_id}/buy")
async def buy_template(template_id: str, current_user: dict = require_auth()):
    """积分购买模板（从用户配额/积分余额扣减）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_user_templates(conn)

    tpl = conn.execute("SELECT * FROM user_templates WHERE id=? AND active=1", (template_id,)).fetchone()
    if not tpl:
        conn.close()
        raise HTTPException(404, "模板不存在或已下架")
    tpl = dict(tpl)
    if tpl["user_id"] == user:
        conn.close()
        raise HTTPException(400, "不能购买自己上传的模板")

    # 检查是否已购买
    existing = conn.execute(
        "SELECT id FROM template_purchases WHERE user_id=? AND template_id=?",
        (user, template_id),
    ).fetchone()
    if existing:
        conn.close()
        return {"owned": True, "template": tpl, "message": "你已购买过此模板，无需重复购买"}

    price = tpl["price"]
    if price > 0:
        # 扣减积分：从 user_quotas 表扣减 credits
        quota = conn.execute("SELECT credits FROM user_quotas WHERE username=?", (user,)).fetchone()
        balance = int(quota["credits"]) if quota else 0
        if balance < price:
            conn.close()
            raise HTTPException(402, "余额不足，请先充值")
        conn.execute(
            "UPDATE user_quotas SET credits=credits-? WHERE username=?",
            (price, user),
        )
        # 平台分成：seller 获得 (1 - PLATFORM_SHARE) * price
        seller_share = int(price * (1 - PLATFORM_SHARE))
        if seller_share > 0 and tpl["user_id"]:
            conn.execute(
                "UPDATE user_quotas SET credits=credits+? WHERE username=?",
                (seller_share, tpl["user_id"]),
            )

    # 记录购买
    pid = f"tbuy_{uuid.uuid4().hex[:8]}"
    conn.execute(
        """INSERT INTO template_purchases (id, user_id, template_id, price, seller_id, created_at)
           VALUES (?,?,?,?,?,?)""",
        (pid, user, template_id, price, tpl["user_id"], datetime.now().isoformat()),
    )
    # 更新销量
    conn.execute("UPDATE user_templates SET sales=sales+1 WHERE id=?", (template_id,))
    conn.commit()
    conn.close()
    return {
        "owned": True,
        "template": tpl,
        "price_paid": price,
        "message": f"购买成功！花费 {price} 积分" if price > 0 else "免费领取成功",
    }


@router.get("/purchases")
async def my_purchases(current_user: dict = require_auth()):
    """我的购买记录。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_user_templates(conn)
    rows = conn.execute(
        """SELECT p.*, t.name as template_name, t.description as template_desc
           FROM template_purchases p LEFT JOIN user_templates t ON p.template_id=t.id
           WHERE p.user_id=? ORDER BY p.created_at DESC LIMIT 100""",
        (user,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.delete("/{template_id}")
async def delete_template(template_id: str, current_user: dict = require_auth()):
    """下架自己的模板。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    conn.execute(
        "UPDATE user_templates SET active=0 WHERE id=? AND user_id=?",
        (template_id, user),
    )
    conn.commit()
    conn.close()
    return {"success": True}


# ── 创作者中心 ───────────────────────────────────────────────

@router.get("/creator/stats")
async def creator_stats(current_user: dict = require_auth()):
    """我的创作者统计：模板数/销量/收益。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    try:
        tpl_count = conn.execute(
            "SELECT COUNT(*) FROM user_templates WHERE user_id=? AND active=1", (user,)
        ).fetchone()[0]
        total_sales = conn.execute(
            "SELECT COALESCE(SUM(sales), 0) FROM user_templates WHERE user_id=? AND active=1", (user,)
        ).fetchone()[0]
        total_revenue = conn.execute(
            """SELECT COALESCE(SUM(p.price * 0.7), 0) 
               FROM template_purchases p 
               JOIN user_templates t ON p.template_id = t.id 
               WHERE t.user_id = ?""",
            (user,),
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM user_templates WHERE user_id=? AND active=1 ORDER BY sales DESC, created_at DESC",
            (user,),
        ).fetchall()
        templates = [dict(r) for r in rows]
    finally:
        conn.close()
    return {
        "template_count": tpl_count,
        "total_sales": int(total_sales),
        "total_revenue": float(total_revenue),
        "templates": templates,
    }


@router.get("/creator/top")
async def top_creators(limit: int = 10, current_user: dict = require_auth()):
    """热门创作者排行榜。"""
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT t.user_id, u.username, u.nickname, 
                    COUNT(t.id) as template_count,
                    SUM(t.sales) as total_sales,
                    SUM(p.price * 0.7) as total_revenue
               FROM user_templates t
               LEFT JOIN users u ON u.id = t.user_id
               LEFT JOIN template_purchases p ON p.template_id = t.id
               WHERE t.active = 1
               GROUP BY t.user_id
               ORDER BY total_sales DESC, total_revenue DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        creators = []
        for r in rows:
            creators.append({
                "user_id": r["user_id"],
                "username": r["username"] or r["user_id"],
                "nickname": r["nickname"] or r["username"] or "",
                "template_count": r["template_count"] or 0,
                "total_sales": r["total_sales"] or 0,
                "total_revenue": r["total_revenue"] or 0,
            })
    finally:
        conn.close()
    return {"creators": creators}


@router.get("/creator/{username}")
async def creator_profile(username: str, current_user: dict = require_auth()):
    """创作者主页：个人信息 + 模板列表。"""
    conn = get_db()
    try:
        user_row = conn.execute(
            "SELECT id, username, nickname, avatar FROM users WHERE username=?", (username,)
        ).fetchone()
        if not user_row:
            raise HTTPException(404, "创作者不存在")
        user = dict(user_row)
        
        tpl_rows = conn.execute(
            "SELECT * FROM user_templates WHERE user_id=? AND active=1 ORDER BY sales DESC, created_at DESC",
            (user["id"],),
        ).fetchall()
        templates = [dict(r) for r in tpl_rows]
        
        stats = {
            "template_count": len(templates),
            "total_sales": sum(t.get("sales", 0) or 0 for t in templates),
            "total_revenue": sum(t.get("price", 0) * (t.get("sales", 0) or 0) * 0.7 for t in templates),
        }
    finally:
        conn.close()
    return {"user": user, "templates": templates, "stats": stats}
