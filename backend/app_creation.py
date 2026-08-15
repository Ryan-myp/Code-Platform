#!/usr/bin/env python3
"""内容创作独立版入口（模式 B：用户自带中转站 Key）。

只包含内容创作 + 工具相关路由（不含代码/Agent/PRD），
所有 AI 调用走用户中转站 Key（URL 平台写死），平台卖 token 盈利。

启动：python app_creation.py（默认 8888，PORT 环境变量可覆盖）
"""

import os
import sys
import json  # noqa: E402
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BASE_DIR / ".env")

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from common.auth import (  # noqa: E402
    decode_access_token,
    get_current_user,
    get_user_profile,
    get_user_relay_config,
    require_auth,
)
from common.config import ALLOWED_ORIGINS  # noqa: E402
from common.db import get_db, init_schema  # noqa: E402
from common.observability import RequestContextMiddleware  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动初始化：建表 + 用户中转站字段迁移。"""
    init_schema()
    # 模式 B：users 表补 relay 字段
    try:
        conn = get_db()
        try:
            conn.execute("ALTER TABLE users ADD COLUMN relay_api_key TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN relay_api_base TEXT DEFAULT ''")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE users ADD COLUMN relay_provider TEXT DEFAULT 'aixinghuo'")
        except Exception:
            pass
        try:
            # v1.0.30：多供应商 key 分存（relay_keys JSON：{"aixinghuo": "sk-..", "agnes": "sk-.."}）
            conn.execute("ALTER TABLE users ADD COLUMN relay_keys TEXT DEFAULT '{}'")
        except Exception:
            pass
        # 迁移旧数据：relay_api_key（旧单列）→ relay_keys[relay_provider]，避免升级后丢 key
        try:
            rows = conn.execute(
                "SELECT id, relay_api_key, relay_provider, relay_keys FROM users"
            ).fetchall()
            for r in rows:
                old_key = (r["relay_api_key"] or "").strip()
                if not old_key:
                    continue
                provider = (r["relay_provider"] or "aixinghuo").strip()
                try:
                    keys = json.loads(r["relay_keys"] or "{}")
                except Exception:
                    keys = {}
                if isinstance(keys, dict) and not keys.get(provider):
                    keys[provider] = old_key
                    conn.execute(
                        "UPDATE users SET relay_keys=? WHERE id=?",
                        (json.dumps(keys, ensure_ascii=False), r["id"]),
                    )
            conn.commit()
        except Exception:
            pass
        conn.commit()
        conn.close()
    except Exception:
        pass
    # 建 async_tasks 表（任务队列依赖）
    try:
        from task_queue import _ensure_table as _ensure_task_table

        conn = get_db()
        _ensure_task_table(conn)
        conn.commit()
        conn.close()
    except Exception:
        pass
    # 数字人记录表（digital_human._ensure_tables）
    try:
        from digital_human import _ensure_tables as _ensure_dh_tables

        conn = get_db()
        _ensure_dh_tables(conn)
        conn.close()
    except Exception:
        pass
    # 审计日志表（log_audit 依赖，主仓库在 lifespan 调用 ensure_audit_table）
    try:
        from common.audit import ensure_audit_table

        ensure_audit_table()
    except Exception:
        pass
    # 小游戏表（game_factory.ensure_game_tables）
    try:
        from game_factory import ensure_game_tables

        ensure_game_tables()
    except Exception:
        pass
    # 口播短视频流水线表（pipeline._ensure_tables）
    try:
        from pipeline import _ensure_tables as _ensure_pipeline_tables

        conn = get_db()
        _ensure_pipeline_tables(conn)
        conn.close()
    except Exception:
        pass
    from task_queue import start_workers  # noqa: E402
    start_workers()
    yield
    from task_queue import stop_workers  # noqa: E402
    stop_workers()


app = FastAPI(title="AI 星火 · 内容创作平台", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "db": "ok",
        "mode": "content-creation",
    }


from fastapi import HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402


class AuthRequest(BaseModel):
    username: str
    password: str


@app.post("/api/auth/login")
async def login(req: AuthRequest):
    """登录（无邀请码简版：独立版用户直接注册后登录）。"""
    from common.auth import login_user

    try:
        return login_user(req.username, req.password)
    except Exception as e:
        raise HTTPException(401, "用户名或密码错误") from e


@app.post("/api/auth/register")
async def register(req: AuthRequest):
    """注册（独立版：新用户自动获得中转站配置能力）。"""
    from common.auth import register_user

    try:
        return register_user(req.username, req.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/auth/auto")
async def auto_login():
    """本地版免登录：自动创建/复用本地用户并签发 token（无登录墙）。

    本地单机使用场景下用户无需注册，首次打开即自动登录。
    选择顺序：已有中转站 Key 的用户（避免升级后配置“丢失”）→ 本地默认用户 → 新建本地默认用户。
    """
    import secrets

    from common.auth import _gen_user_id, create_access_token, hash_password
    from common.db import get_db

    username = os.environ.get("LOCAL_USERNAME", "local_user")
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, username, role FROM users "
            "WHERE relay_api_key IS NOT NULL AND relay_api_key != '' "
            "ORDER BY created_at LIMIT 1"
        ).fetchone()
        if not row:
            row = conn.execute(
                "SELECT id, username, role FROM users WHERE username=?", (username,)
            ).fetchone()
    finally:
        conn.close()
    if not row:
        uid = _gen_user_id()
        pwd = secrets.token_urlsafe(24)
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, role, active, created_at) "
                "VALUES (?, ?, ?, 'user', 1, ?)",
                (uid, username, hash_password(pwd), datetime.now().isoformat()),
            )
            conn.commit()
            row = {"id": uid, "username": username, "role": "user"}
        finally:
            conn.close()
    token = create_access_token(row["username"], {"user_id": row["id"], "role": row["role"]})
    return {"access_token": token, "token_type": "bearer", "user": dict(row)}


@app.get("/api/auth/me")
async def me(current_user: dict = require_auth()):
    profile = get_user_profile(current_user.get("user_id", ""))
    return profile


# ── 创作模块路由 ──────────────────────────────────────────
from image_factory import router as image_factory_router  # noqa: E402
from video_factory import router as video_factory_router  # noqa: E402
from music_factory import router as music_factory_router  # noqa: E402
from voice_factory import router as voice_factory_router  # noqa: E402
from meme_factory import router as meme_factory_router  # noqa: E402
from game_factory import router as game_factory_router  # noqa: E402
from miniapp import router as miniapp_router  # noqa: E402
from short_drama import router as drama_router  # noqa: E402
from digital_human import router as digital_human_router  # noqa: E402
from relay_api import router as relay_router  # noqa: E402
from drafts import router as drafts_router  # noqa: E402
from gallery import router as gallery_router  # noqa: E402
# ── 应用与工具模块（v2：效率工具箱/PDF/思维导图/数据分析等）──
from tool_hub import router as tool_hub_router  # noqa: E402
from pdf_tools import router as pdf_tools_router  # noqa: E402
from mindmap import router as mindmap_router  # noqa: E402
from seo_analyzer import router as seo_analyzer_router  # noqa: E402
from stock_tools import router as stock_tools_router  # noqa: E402
from data_analyzer import router as data_analyzer_router  # noqa: E402
from data_forecast import router as data_forecast_router  # noqa: E402
from content_strategy import router as content_strategy_router  # noqa: E402
from growth_engine import router as growth_engine_router  # noqa: E402
from smart_dashboard import router as smart_dashboard_router  # noqa: E402
from competitor_monitor import router as competitor_monitor_router  # noqa: E402
from doc_qa import router as doc_qa_router  # noqa: E402
from web_search import router as web_search_router  # noqa: E402
from publishing import router as publishing_router  # noqa: E402
from video_analyzer import router as video_analyzer_router  # noqa: E402
from ai_video_api import router as ai_video_router  # noqa: E402
from favorites_api import router as favorites_api_router  # noqa: E402
from search_api import router as search_api_router  # noqa: E402
from realtime import router as realtime_router  # noqa: E402
from extended_api import router as extended_api_router  # noqa: E402
from template_store import router as template_store_router  # noqa: E402
from templates_market import router as templates_market_router  # noqa: E402
from apikey_api import router as apikey_api_router  # noqa: E402
from task_queue import router as task_queue_router  # noqa: E402
from platform_api import router as platform_api_router  # noqa: E402
from video_templates import router as video_templates_router  # noqa: E402
from app_extra import router as app_extra_router  # noqa: E402
from pipeline import router as pipeline_router  # noqa: E402

# 注意注册顺序：/api/tasks 冲突时 task_queue 优先（与主仓库 routers.py 一致）
for r in [
    image_factory_router, video_factory_router, music_factory_router,
    voice_factory_router, meme_factory_router, game_factory_router,
    miniapp_router, drama_router, digital_human_router,
    relay_router, drafts_router, gallery_router,
    tool_hub_router, pdf_tools_router, mindmap_router, seo_analyzer_router,
    stock_tools_router, data_analyzer_router, data_forecast_router,
    content_strategy_router, growth_engine_router, smart_dashboard_router,
    competitor_monitor_router, doc_qa_router, web_search_router,
    publishing_router, video_analyzer_router, ai_video_router,
    favorites_api_router, search_api_router,
    realtime_router, extended_api_router, template_store_router,
    templates_market_router, apikey_api_router,
    task_queue_router, platform_api_router, video_templates_router,
    app_extra_router, pipeline_router,
]:
    app.include_router(r)

# 静态上传目录（如有）
for d in ("uploads", "image_factory", "video_factory", "music_factory", "meme_factory"):
    p = BASE_DIR / d
    if p.is_dir():
        try:
            app.mount(f"/{d}", StaticFiles(directory=str(p)), name=d)
        except Exception:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8888"))
    uvicorn.run(app, host="0.0.0.0", port=port)
