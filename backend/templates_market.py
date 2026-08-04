#!/usr/bin/env python3
"""模板市场 — 聚合各工厂内置模板，一站式浏览并跳转使用。

聚合来源：
- game_factory.TEMPLATES  小游戏玩法模板（9 种）
- miniapp.TEMPLATES       小程序结构模板
- meme_factory.STYLES     表情包样式模板
- voice_factory.SCENES    配音场景预设
"""

import logging

from fastapi import APIRouter

from common.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/templates", tags=["模板市场"])

# 各工厂模板常量（轻量 import，避免循环依赖）
from game_factory import TEMPLATES as GAME_TEMPLATES  # noqa: E402
from meme_factory import STYLES as MEME_STYLES  # noqa: E402
from miniapp import TEMPLATES as MINIAPP_TEMPLATES  # noqa: E402
from voice_factory import SCENES as VOICE_SCENES  # noqa: E402


@router.get("/market")
async def template_market(current_user: dict = require_auth()):
    """模板市场总览：分类聚合 + 跳转路径。"""
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
        }
        for t in VOICE_SCENES
        if t.get("id") != "custom"  # 自定义场景不展示
    ]

    grouped = {
        "game": {"label": "小游戏玩法", "count": len(games), "items": games},
        "miniapp": {"label": "小程序结构", "count": len(miniapps), "items": miniapps},
        "meme": {"label": "表情包样式", "count": len(memes), "items": memes},
        "voice": {"label": "配音场景", "count": len(voices), "items": voices},
    }
    return {
        "total": len(games) + len(miniapps) + len(memes) + len(voices),
        "groups": grouped,
    }
