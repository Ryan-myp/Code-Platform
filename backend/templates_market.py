#!/usr/bin/env python3
"""模板市场 — 聚合各工厂内置模板，一站式浏览并跳转使用。

聚合来源：
- game_factory.TEMPLATES  小游戏玩法模板（9 种）
- miniapp.TEMPLATES       小程序结构模板
- meme_factory.STYLES     表情包样式模板
- voice_factory.SCENES    配音场景预设
"""

import json
import logging

from fastapi import APIRouter

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

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
        for r in conn.execute(
            "SELECT metadata FROM artifacts WHERE author='meme_factory' AND active=1"
        ).fetchall():
            try:
                md = json.loads(r["metadata"] or "{}")
                s = md.get("style", "")
                if s:
                    stats["meme"][s] = stats["meme"].get(s, 0) + 1
            except Exception:
                pass
        # 配音：artifacts.metadata.scene（author=voice_factory）
        for r in conn.execute(
            "SELECT metadata FROM artifacts WHERE author='voice_factory' AND active=1"
        ).fetchall():
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
            "path": "/voice",
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
            i for i in all_items
            if q_lower in i["name"].lower() or q_lower in i["description"].lower()
            or any(q_lower in t.lower() for t in i["tags"])
        ]

    grouped = {
        "game": {"label": "小游戏玩法", "count": sum(1 for i in all_items if i["category"] == "game"), "items": [i for i in all_items if i["category"] == "game"]},
        "miniapp": {"label": "小程序结构", "count": sum(1 for i in all_items if i["category"] == "miniapp"), "items": [i for i in all_items if i["category"] == "miniapp"]},
        "meme": {"label": "表情包样式", "count": sum(1 for i in all_items if i["category"] == "meme"), "items": [i for i in all_items if i["category"] == "meme"]},
        "voice": {"label": "配音场景", "count": sum(1 for i in all_items if i["category"] == "voice"), "items": [i for i in all_items if i["category"] == "voice"]},
    }
    return {
        "total": len(all_items),
        "groups": grouped,
    }
