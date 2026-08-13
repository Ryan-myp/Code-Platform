#!/usr/bin/env python3
"""小团智能平台 v8.0 — AI 赋能各行各业，智能解决工作难题。

v8.0 升级：安全加固、Pydantic 模型验证、异步架构、WebSocket、工作流并行。
"""

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from urllib.parse import quote, urlparse

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 加载 .env 文件
load_dotenv()

import skills_store  # noqa: E402
from admin_api import router as admin_api_router  # noqa: E402
from ai_video_api import router as ai_video_router  # noqa: E402
from apikey_api import router as apikey_api_router  # noqa: E402
from batch_api import router as batch_api_router  # noqa: E402
from chat_engine import router as chat_engine_router  # noqa: E402
from collab_engine import router as collab_engine_router  # noqa: E402
from common.auth import (  # noqa: E402
    change_password,
    consume_quota,
    create_order,
    create_share,
    decode_access_token,
    get_invite_info,
    get_my_orders,
    get_quota_info,
    _auth_by_api_key,
    get_share,
    get_user_profile,
    grant_free_trial,
    login_user,
    register_user,
    require_auth,
    reset_password,
    send_password_reset_token,
    submit_voucher,
    update_user_profile,
    get_usage_detail,
    get_usage_daily_timeline,
    get_billing_history,
)
from common.backup import ensure_daily_backup  # noqa: E402
from common.backup import router as backup_router  # noqa: E402
from common.config import ALLOWED_ORIGINS, is_production, validate_security_config  # noqa: E402
from common.db import get_db, init_schema  # noqa: E402
from common.db_async import is_pg_enabled, get_async_db, close_async_db  # noqa: E402
from common.llm import call_llm_async, log_usage, stream_llm_async  # noqa: E402
from common.audit import ensure_audit_table  # noqa: E402
from common.models import (  # noqa: E402
    AgentCreateRequest,
    AgentUpdateRequest,
    AssistantChatRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseUpdateRequest,
    LoginRequest,
    MCPServerCreateRequest,
    MCPServerUpdateRequest,
    OrderCreateRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SandboxProjectCreateRequest,
    SandboxPullImageRequest,
    SandboxRedisCommandRequest,
    SandboxSqlQueryRequest,
    ShareCreateRequest,
    SkillCreateRequest,
    SkillUpdateRequest,
    PortalSwitchRequest,
    TeamCreateRequest,
    TeamUpdateRequest,
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
)
from common.observability import (  # noqa: E402
    RequestContextMiddleware,
    get_metrics_snapshot,
    uptime_seconds,
)
from common.sandbox_check import MAX_CODE_LEN, check_sandbox_code, run_sandbox_python  # noqa: E402
from competitor_monitor import router as competitor_monitor_router  # noqa: E402
from content_strategy import router as content_strategy_router  # noqa: E402
from data_forecast import router as data_forecast_router  # noqa: E402
from dh_gateway import router as dh_gateway_router  # noqa: E402
from digital_human import router as digital_human_router  # noqa: E402
from doc_qa import router as doc_qa_router  # noqa: E402
from drafts import router as drafts_router  # noqa: E402
from drama_templates import router as drama_templates_router  # noqa: E402
from extensions_agents import router as extensions_agents_router  # noqa: E402
from favorites_api import router as favorites_api_router  # noqa: E402
from gallery import router as gallery_router  # noqa: E402
from game_factory import router as game_factory_router  # noqa: E402
from growth_engine import router as growth_engine_router  # noqa: E402
from image_factory import router as image_factory_router  # noqa: E402
from meme_factory import router as meme_factory_router  # noqa: E402
from meme_templates import router as meme_templates_router  # noqa: E402
from mindmap_templates import router as mindmap_templates_router  # noqa: E402
from mindmap import router as mindmap_router  # noqa: E402
from miniapp import router as miniapp_router  # noqa: E402
from music_factory import router as music_factory_router  # noqa: E402
from music_scene_templates import router as music_scene_templates_router  # noqa: E402
from notify_api import router as notify_api_router  # noqa: E402
from openai_gateway import router as openai_gateway_router  # noqa: E402
from pdf_tools import router as pdf_tools_router  # noqa: E402
from pdf_doc_templates import router as pdf_doc_templates_router  # noqa: E402
from prd_engine import router as prd_engine_router  # noqa: E402
from publishing import router as publishing_router  # noqa: E402
from realtime import router as realtime_router  # noqa: E402
from scheduler import router as scheduler_router  # noqa: E402
from scheduler import start_scheduler, stop_scheduler  # noqa: E402
from search_api import router as search_api_router  # noqa: E402
from seed_data import seed_if_empty  # noqa: E402
from seo_analyzer import router as seo_analyzer_router  # noqa: E402
from sessions import router as sessions_router  # noqa: E402
from short_drama import router as drama_router  # noqa: E402
from stripe_api import router as stripe_router  # noqa: E402
from oauth_api import router as oauth_router, ensure_social_bindings_table  # noqa: E402
from team_api import router as team_router, ensure_team_tables  # noqa: E402
from feedback_api import router as feedback_router, ensure_feedback_table  # noqa: E402
from smart_dashboard import router as smart_dashboard_router  # noqa: E402
from task_queue import recover_interrupted_tasks, start_workers, stop_workers  # noqa: E402
from task_queue import router as task_queue_router  # noqa: E402
from templates_market import router as templates_market_router  # noqa: E402
from template_store import router as template_store_router  # noqa: E402
from video_analyzer import router as video_analyzer_router  # noqa: E402
from video_factory import router as video_factory_router  # noqa: E402
from video_templates import router as video_templates_router  # noqa: E402
from voice_chat import router as voice_chat_router  # noqa: E402
from voice_factory import _tts_health_check as _tts_prewarm  # noqa: E402
from voice_factory import router as voice_factory_router  # noqa: E402
from voice_templates import router as voice_templates_router  # noqa: E402
from web_search import router as web_search_router  # noqa: E402

# ── 日志 ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── 限流器 ────────────────────────────────────────────────────
# 测试环境下禁用限流，避免干扰测试
_is_test = os.environ.get("APP_ENV") == "test"
limiter = Limiter(key_func=get_remote_address, default_limits=[] if _is_test else ["200 per minute"])


def _rl(rate: str) -> str:
    """装饰器级限流：测试环境放宽到 10000/min（default_limits 不影响 @limiter.limit）。"""
    return "10000 per minute" if _is_test else rate


def _safe_error(msg: str) -> str:
    """清洗命令执行错误信息，防止泄露内部路径/密码/IP 等敏感内容。"""
    import re as _re
    safe = _re.sub(r"/[^\s,;]{8,}", "<path>", msg)[:200]
    safe = _re.sub(r"(?:password|secret|token|key)\s*[:=]\s*\S+", "<cred>", safe, flags=_re.IGNORECASE)
    safe = _re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<ip>", safe)
    return safe or "命令执行失败，请检查配置后重试"


def _safe_exc_msg(e: Exception) -> str:
    """从异常中提取安全错误消息，过滤路径和敏感信息。"""
    import re as _re
    msg = str(e)[:200]
    msg = _re.sub(r"/[^\s,;]{6,}", "<path>", msg)
    msg = _re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<ip>", msg)
    return msg or "操作失败，请稍后重试"


# ── 数据库初始化（保留 init_db 名字供 conftest 调用） ─────────
def init_db():
    """委托给 common.db.init_schema（24 表 + 迁移 + admin 用户）。"""
    init_schema()


# ── 应用生命周期 ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化数据库 + 安全校验 + 排期后台调度器。关闭时无特殊处理。"""
    validate_security_config()
    init_db()
    # PostgreSQL 异步连接预热（仅在生产模式）
    if is_pg_enabled():
        try:
            async with get_async_db() as conn:
                await conn.fetchval("SELECT 1")
            logger.info("PostgreSQL 连接预热成功")
        except Exception as e:
            logger.warning(f"PostgreSQL 预热失败（回退 SQLite）: {e}")
    seed_if_empty()
    skills_store.migrate_legacy()
    # v17.2 审计日志表初始化
    ensure_audit_table()
    # v17.2 社交账号绑定表初始化
    ensure_social_bindings_table()
    # v17.2 团队空间表初始化
    ensure_team_tables()
    # v17.3 用户反馈表初始化
    ensure_feedback_table()
    # v12.0 数据可靠性：每日自动备份（按日期去重）
    ensure_daily_backup()
    # 发布排期后台自动执行（每 60s 扫描到期 pending 排期）
    from publishing import _run_due_schedules

    asyncio.create_task(_run_due_schedules())
    # v10.1 定时任务调度器
    start_scheduler()
    # 数字人：重启恢复中断的批量任务 + 存储保留期清理守护线程
    from digital_human import recover_interrupted_batches, start_storage_cleaner

    recover_interrupted_batches()
    start_storage_cleaner()
    # 上传文件自动清理
    start_uploads_cleaner()
    # 试用到期邮件提醒（商业化：引导续费）
    start_trial_reminder()
    # 通用异步任务框架（master-worker）：恢复中断任务 + 启动调度/工作线程
    # 注入主事件循环：worker 线程通过 realtime 向 WebSocket 任务频道广播进度
    import asyncio as _asyncio

    from realtime import set_loop as _realtime_set_loop

    _realtime_set_loop(_asyncio.get_running_loop())
    recover_interrupted_tasks()
    start_workers()
    # v13.1 数字人稳定性：启动即预热 edge-tts 通道探活（后台线程，不阻塞启动）
    import threading as _threading

    _threading.Thread(target=_tts_prewarm, args=(True,), daemon=True, name="tts-prewarm").start()
    logger.info("Smart R&D Platform v8.0 started")
    yield
    # 清理 PostgreSQL 连接
    import asyncio as _asyncio
    try:
        _asyncio.run_coroutine_threadsafe(close_async_db(), _asyncio.get_running_loop())
    except Exception:
        pass
    stop_workers()
    stop_scheduler()
    logger.info("Smart R&D Platform v8.0 shutting down")


# ── FastAPI 应用 ──────────────────────────────────────────────
_docs_disabled = is_production()
app = FastAPI(
    title="小团智能平台 v12.0", version="12.0.0", lifespan=lifespan,
    docs_url=None if _docs_disabled else "/docs",
    redoc_url=None if _docs_disabled else "/redoc",
    openapi_url=None if _docs_disabled else "/openapi.json",
)

# 支付凭证上传目录（静态可访问，管理后台预览）
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# 数字人写真肖像静态目录
PORTRAIT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_factory", "avatars")
os.makedirs(PORTRAIT_DIR, exist_ok=True)
app.mount("/api/image-factory/avatars", StaticFiles(directory=PORTRAIT_DIR), name="avatar_portraits")

# ── 上传文件自动清理（保留 N 天，默认 30，<=0 不清理）─────────────────
UPLOAD_RETENTION_DAYS = max(0, int(os.environ.get("UPLOAD_RETENTION_DAYS", "30")))


def _cleanup_expired_uploads() -> int:
    """删除超过保留期的上传文件，返回删除数量。"""
    if UPLOAD_RETENTION_DAYS <= 0:
        return 0
    import threading
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=UPLOAD_RETENTION_DAYS)).timestamp()
    deleted = 0
    for root, _, files in os.walk(UPLOAD_DIR):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                if os.path.getmtime(fp) < cutoff:
                    os.remove(fp)
                    deleted += 1
            except OSError:
                pass
    if deleted:
        logger.info("上传文件清理：删除 %d 个超过 %d 天的文件", deleted, UPLOAD_RETENTION_DAYS)
    return deleted


def start_uploads_cleaner() -> None:
    """启动上传文件清理守护线程：启动时执行一次，之后每 24h 执行。"""
    if UPLOAD_RETENTION_DAYS <= 0:
        logger.info("上传文件清理已禁用（UPLOAD_RETENTION_DAYS=%s）", UPLOAD_RETENTION_DAYS)
        return

    def _loop():
        while True:
            try:
                _cleanup_expired_uploads()
            except Exception:
                logger.exception("上传文件清理失败")
            time.sleep(24 * 3600)

    threading.Thread(target=_loop, daemon=True, name="uploads-cleaner").start()
    logger.info("上传文件清理守护线程已启动（保留 %s 天）", UPLOAD_RETENTION_DAYS)


# ── 试用到期邮件提醒（商业化：引导续费）──────────────────────
TRIAL_REMIND_DAYS = (3, 1)  # 剩余 3 天 / 1 天各提醒一次


def _send_trial_reminders() -> int:
    """扫描 pro 试用即将到期的用户，发送邮件提醒，返回发送数量。

    仅提醒还在 pro 试用期（trial_expires 非空且 membership=pro）的用户；
    已续费（membership_expires 晚于 trial_expires）自动跳过。
    """
    from common.mailer import is_smtp_configured, send_trial_expiry_email
    if not is_smtp_configured():
        return 0
    from datetime import datetime, timedelta

    conn = get_db()
    sent = 0
    try:
        rows = conn.execute(
            "SELECT id, username, email, membership, trial_expires, membership_expires FROM users "
            "WHERE email IS NOT NULL AND email != '' AND trial_expires IS NOT NULL AND trial_expires != ''"
        ).fetchall()
        now = datetime.now()
        for r in rows:
            try:
                trial_end = datetime.fromisoformat(r["trial_expires"])
            except (ValueError, TypeError):
                continue
            # 试用已结束或已过期则跳过
            if trial_end <= now:
                continue
            # 已续费（会员到期晚于试用到期）则跳过
            if r["membership_expires"]:
                try:
                    if datetime.fromisoformat(r["membership_expires"]) >= trial_end:
                        continue
                except (ValueError, TypeError):
                    pass
            days_left = (trial_end - now).days + (1 if (trial_end - now).seconds > 0 else 0)
            if days_left in TRIAL_REMIND_DAYS:
                res = send_trial_expiry_email(r["email"], r["username"], days_left)
                if res.get("ok"):
                    sent += 1
                    logger.info("试用到期提醒已发送: %s (%s 剩 %s 天)", r["username"], r["email"], days_left)
    except Exception as e:
        logger.exception("试用到期提醒扫描失败: %s", e)
    finally:
        conn.close()
    return sent


def start_trial_reminder() -> None:
    """启动试用到期提醒守护线程：每 6h 检查，仅每天首次命中时发送（防重复）。"""
    import threading

    def _loop():
        last_sent_date = ""
        while True:
            try:
                today = datetime.now().strftime("%Y-%m-%d")
                if today != last_sent_date:
                    n = _send_trial_reminders()
                    if n:
                        last_sent_date = today
            except Exception:
                logger.exception("试用提醒线程异常")
            time.sleep(6 * 3600)

    threading.Thread(target=_loop, daemon=True, name="trial-reminder").start()
    logger.info("试用到期提醒守护线程已启动（剩余 %s 天提醒）", TRIAL_REMIND_DAYS)

# workflow 写入防抖（阻断旧版前端自动保存循环）
_WF_LAST_WRITE: dict[str, float] = {}
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── 全局异常兜底：任何未捕获错误返回友好 JSON，不泄露堆栈 ──────
# 错误分类映射：根据异常类型返回不同的用户可见提示
_ERROR_HINTS = {
    "sqlite3.OperationalError": "数据库暂时繁忙，请稍后重试",
    "sqlite3.OperationalError: database is locked": "数据库写入冲突，请等待几秒后重试",
    "sqlite3.OperationalError: no such table": "数据库表不存在，请联系管理员重新初始化",
    "httpx.ConnectError": "无法连接到 LLM 服务，请检查 AGNES_API_KEY 配置",
    "httpx.ConnectTimeout": "LLM 服务响应超时，请稍后重试",
    "httpx.ReadTimeout": "LLM 服务读取超时，请稍后重试",
    "ConnectionRefusedError": "网络连接被拒绝，请检查服务状态",
    "json.JSONDecodeError": "收到无效的数据响应，请重试",
    "asyncpg.PostgresError": "数据库错误，请联系管理员",
    "asyncpg.InvalidAuthorizationSpecification": "PostgreSQL 认证失败，请检查 ASYNC_PG_URL",
    "asyncpg.ConnectionDoesNotExistError": "PostgreSQL 连接断开，请重启服务",
}


def _error_hint(exc: Exception) -> str:
    """根据异常类型返回友好的用户提示。"""
    exc_type = type(exc).__name__
    exc_msg = str(exc)
    # 精确匹配
    for pattern, hint in _ERROR_HINTS.items():
        if pattern in exc_type or pattern in exc_msg:
            return hint
    # 通用兜底
    return "服务器内部错误，请稍后重试或联系管理员"


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": _error_hint(exc),
            "request_id": getattr(request.state, "request_id", ""),
        },
    )


def _safe_serializable(obj):
    """递归把不可 JSON 序列化的对象转成字符串（如 UploadFile 校验失败时的 bytes）。"""
    if isinstance(obj, bytes):
        return f"<{len(obj)} bytes>"
    if isinstance(obj, dict):
        return {k: _safe_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serializable(v) for v in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError):
    """请求参数校验失败 → 提取第一条错误，返回中文可读提示"""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = first.get("loc", [])
    msg = first.get("msg", "")
    field = str(loc[-1]) if loc else ""
    # 字段名映射为中文
    _FIELD_LABELS = {
        "username": "用户名",
        "password": "密码",
        "message": "消息内容",
        "template_id": "模板 ID",
        "agent_id": "智能体 ID",
        "workflow_id": "工作流 ID",
        "plan": "套餐类型",
        "model": "模型",
        "size": "尺寸",
        "prompt": "提示词",
    }
    label = _FIELD_LABELS.get(field, field)
    if field in ("body", "query", "path", "header"):
        hint = "请求参数格式错误，请检查输入"
    elif msg and "ensure this input" in msg.lower():
        # Pydantic 标准错误消息，提取关键信息
        hint = f"{label}：{msg.split('ensure this input')[1].strip() if 'ensure this input' in msg else msg}"
    else:
        hint = f"{label} 输入不合法：{msg}"
    return JSONResponse(
        status_code=422,
        content={"detail": hint, "field": field, "raw_msg": msg},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# v12.0 可观测性：request-id 注入 + 结构化访问日志 + 运行指标（最外层，覆盖全部请求）
app.add_middleware(RequestContextMiddleware)


# ── 安全响应头中间件（CSP / HSTS / X-Frame-Options）──────────
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """为所有响应添加基础安全头，生产环境额外开启 HSTS。"""
    from starlette.responses import Response as StarletteResponse
    response = await call_next(request)
    # 基本安全头（始终设置）
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    if not _docs_disabled:
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'"
    # 生产环境启用 HSTS（31536000s = 1年）
    if _docs_disabled:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── 上传文件鉴权中间件（防止未登录用户直链下载敏感文件）────────
# 仅对敏感子目录（凭据/二维码/文档/数据等）要求鉴权；
# 图片/音视频等资源目录（<img>/<video>/<audio> 标签无法携带 JWT）直接放行，
# 否则前端所有 /uploads 静态资源会 401 导致图片全丢。
_UPLOAD_PROTECTED = (
    "/uploads/vouchers",
    "/uploads/qr",
    "/uploads/docs",
    "/uploads/kb",
    "/uploads/data",
    "/uploads/batch",
    "/uploads/ppt",
    "/uploads/translations",
)


@app.middleware("http")
async def uploads_auth_middleware(request: Request, call_next):
    """仅拦截敏感上传路径（凭据/二维码/文档），要求 Bearer JWT 或 API Key。

    资源目录（dh_avatars/dh_voices/audio/videos/tts 等）不鉴权，
    因为 <img>/<video> 标签无法携带 Authorization 头。
    """
    if not any(request.url.path.startswith(p) for p in _UPLOAD_PROTECTED):
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse({"error": "unauthorized", "code": "UPLOAD_AUTH_REQUIRED"}, status_code=401)
    token = auth[7:]
    try:
        if token.startswith("xt-"):
            _auth_by_api_key(token)
        else:
            decode_access_token(token)
        return await call_next(request)
    except Exception:
        return JSONResponse({"error": "unauthorized", "code": "UPLOAD_AUTH_INVALID"}, status_code=401)


# ── 额度扣减中间件（商业版） ─────────────────────────────────
# 命中的 AI 生成类端点，每次调用扣减 1 次用户当日额度（vip/admin 不限）。
_QUOTA_PATHS = (
    "/api/tools/run",
    "/api/code/generate",
    "/api/code/review",
    "/api/copywriting/generate",
    "/api/translation/translate",
    "/api/ppt/generate",
    "/api/prd/generate",
    "/api/prd/review",
    "/api/prd/technical-design",
    "/api/prd/test-cases",
    "/api/prd/generate-code",
    "/api/prd/code-chat",
    "/api/data-analyzer/analyze",
    "/api/image-factory/generate/",
    "/api/image-factory/edit/",
    "/api/image-factory/template/render",
    "/api/image-factory/try-on/generate",
    "/api/video-factory/generate",
    "/api/video-factory/tools/",
    "/api/music-factory/lyrics/generate",
    "/api/music-factory/music/generate",
    "/api/music-factory/tts/sing",
    "/api/meme/generate",
    "/api/games/generate",
    "/api/miniapp/generate",
    "/api/doc-qa/ask",
    "/api/mindmap/generate",
    "/api/search/web",
    "/api/forecast/analyze",
    "/api/video/analyze",
    "/api/auto-run",
)

# 后缀匹配（/run、/execute 结尾的 AI 执行端点）
_QUOTA_SUFFIXES = ("/run", "/execute")


@app.middleware("http")
async def quota_middleware(request: Request, call_next):
    """AI 生成端点统一扣减额度，额度不足返回 402；失败响应（>=400）自动退费。

    商业公平：提交即扣费（防并发薅额度），但请求失败（参数错误/服务故障）
    不消耗用户额度——响应失败时回退本次扣减。异步任务的失败由任务队列
    在任务终态时退费（见 task_queue._mark_failed），两条路径互不重复。
    """
    path = request.url.path
    charged = False
    if request.method == "POST" and (path.startswith(_QUOTA_PATHS) or path.endswith(_QUOTA_SUFFIXES)):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header[7:]
                if token.startswith("xt-"):
                    # API Key 调用：随绑定用户配额（见 common.auth._auth_by_api_key）
                    from common.auth import _auth_by_api_key

                    payload = _auth_by_api_key(token)
                else:
                    payload = decode_access_token(token)
                user_id = payload.get("user_id")
                if user_id:
                    result = consume_quota(user_id)
                    charged = bool(result.get("charged"))  # admin/vip 不扣费，无需退
                    if not result.get("allowed"):
                        # 402 分层引导：free 用户促升级 / pro 用户提示明日恢复，文案与会员体系对齐
                        # 配额数字取用户实际配置（管理员可调整 daily_quota），避免硬编码误导
                        qinfo = get_quota_info(user_id) or {}
                        membership = qinfo.get("membership") or "free"
                        daily = qinfo.get("daily_quota") or 30
                        if membership == "pro":
                            detail = f"今日专业版 {daily} 次额度已用完，明日 0 点自动恢复；升级至尊版可无限使用"
                        else:
                            detail = (
                                f"今日免费额度已用完（{daily} 次/日）。"
                                "升级专业版解锁每日 200 次，或邀请好友得额度"
                            )
                        return JSONResponse(
                            status_code=402,
                            content={"detail": detail, "membership": membership},
                        )
            except HTTPException:
                pass  # token 无效由端点鉴权兜底返回 401
    response = await call_next(request)
    if charged and response.status_code >= 400:
        from common.auth import refund_quota

        if refund_quota(payload["user_id"]):
            logger.info("中间件退费: %s %s -> %s", request.method, path, response.status_code)
    return response


# ── 健康检查（v12.0：四维探活 DB/LLM/磁盘/Uptime） ──────────
@app.get("/api/health")
async def health_check():
    import shutil

    db_ok = True
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
    except Exception:
        db_ok = False
    llm_ok = False
    try:
        from common.config import get_model_config

        llm_ok = bool(get_model_config().get("api_key"))
    except Exception:
        llm_ok = False
    try:
        disk = shutil.disk_usage(os.path.dirname(os.path.abspath(__file__)))
        disk_free_gb = round(disk.free / 1e9, 1)
        # 磁盘告警：低于 5GB 警告，低于 2GB 严重
        if disk_free_gb is not None and disk_free_gb < 2:
            disk_status = "critical"
        elif disk_free_gb is not None and disk_free_gb < 5:
            disk_status = "warning"
        else:
            disk_status = "ok"
    except Exception:
        disk_free_gb = None
        disk_status = "unknown"
    return {
        "status": "ok" if db_ok and disk_status != "critical" else "degraded",
        "timestamp": datetime.now().isoformat(),
        "version": app.version,
        "uptime_seconds": uptime_seconds(),
        "db": "ok" if db_ok else "error",
        "llm": "ok" if llm_ok else "not_configured",
        "disk_free_gb": disk_free_gb,
        "disk_status": disk_status,
    }


# ── 运行指标（v12.0：请求画像 + LLM 调用统计） ───────────────
@app.get("/api/ops/stats")
async def ops_stats():
    stats = get_metrics_snapshot()
    # LLM 调用统计（usage_logs 聚合：总调用/成功率/平均耗时/今日）
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(success),0) AS ok_n, COALESCE(AVG(response_time),0) AS avg_t "
            "FROM usage_logs"
        ).fetchone()
        today = datetime.now().strftime("%Y-%m-%d")
        trow = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(success),0) AS ok_n FROM usage_logs WHERE timestamp LIKE ?",
            (f"{today}%",),
        ).fetchone()
        conn.close()
        stats["llm"] = {
            "total_calls": row["n"] if row else 0,
            "success_calls": row["ok_n"] if row else 0,
            "avg_response_ms": round((row["avg_t"] if row else 0) * 1000, 1),
            "today_calls": trow["n"] if trow else 0,
            "today_success": trow["ok_n"] if trow else 0,
        }
    except Exception:
        stats["llm"] = {"total_calls": 0, "success_calls": 0, "avg_response_ms": 0, "today_calls": 0, "today_success": 0}
    return stats


# 分享访问埋点


def _share_visitor_key(request: Request) -> str:
    """访问者去重键：已登录用户 u:{uid}（分享者本人不计裂变奖励）；游客 ip:{ip}:{UA哈希}。"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_access_token(auth_header[7:])
            uid = payload.get("user_id")
            if uid:
                return f"u:{uid}"
        except HTTPException:
            pass  # token 无效按游客处理
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")[:64]
    return f"ip:{ip}:{hashlib.md5(ua.encode()).hexdigest()[:10]}"


def _record_share_visit(share_id: str, source: str, referer: str, visitor_key: str = "") -> bool:
    """写入分享访问埋点（渠道分析 + 裂变计数）。同访问者重复访问同一分享不重复记录。"""
    from common.db import get_db

    conn = get_db()
    try:
        if visitor_key:
            dup = conn.execute(
                "SELECT id FROM share_visits WHERE share_id=? AND visitor_key=? LIMIT 1",
                (share_id, visitor_key),
            ).fetchone()
            if dup:
                return False
        conn.execute(
            "INSERT INTO share_visits (share_id, source, referer, visited_at, visitor_key) VALUES (?, ?, ?, ?, ?)",
            (share_id, source, referer, datetime.now().isoformat(), visitor_key),
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ── 认证 ──────────────────────────────────────────────────────
@app.post("/api/auth/login")
@limiter.limit(_rl("5 per minute"))
async def login(request: Request, req: LoginRequest):
    return login_user(req.username, req.password)


@app.post("/api/auth/register")
@limiter.limit(_rl("3 per minute"))
async def register(request: Request, req: RegisterRequest):
    """注册新用户（可选邀请码/分享来源/邮箱）。"""
    try:
        return register_user(req.username, req.password, req.invite_code, req.share_ref, req.email)
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e


# ══════════════════════════════════════════════════════════════
# 全局智能助手（页面右下角浮动机器人）
# ══════════════════════════════════════════════════════════════
_ASSISTANT_SYSTEM = """你是「小团智能平台」的 AI 客服助手「小团」，一位热情、专业、靠谱的智能伙伴。用简体中文回答用户关于平台使用的一切问题。

## 回复风格
- 先理解再回答：简短确认用户意图，再给出答案（如"明白，你是想问XX对吧？"）
- 结论先行：先给最直接的答案，再补充细节和延伸建议
- 步骤化指引：操作类问题用"第1步→第2步→第3步"的叙述方式，不用列表序号
- 场景化推荐：了解用户需求后，主动推荐1-2个相关功能（如"你如果经常做XX，还可以试试YY功能"）
- 语气温度：像贴心同事而非冷冰冰的机器人，适当用"~"、"哦"等语气词

## 回复长度
- 简单问题：30-60字直接回答
- 操作指引：80-150字步骤说明
- 功能介绍：100-200字覆盖核心价值和访问路径

# 平台简介
小团智能平台是一个 AI 赋能各行各业的智能工作平台，提供研发管理、创作工厂、效率工具箱、个人中心四大板块，从需求到部署全流程 AI 驱动。

# 功能地图（用户可通过左侧导航直达）
1. 研发管理：需求看板 /board、AI 工作台 /workspace（一句话全自动：PRD 编写→审查→技术方案→测试用例→代码生成→代码审查→一键部署沙箱）、项目空间 /projects、流水线 /pipelines、Agent 智能体 /agents、Team 团队协作 /teams、Workflow 工作流编排 /workflows（拖拽节点编排，支持 Agent/图片/视频/音乐/PRD 等节点）、知识库 /knowledge-bases（支持上传文档、检索）、Skills /skills、MCP 服务器 /mcp-servers、沙箱运行 /sandbox、全局任务 /tasks。
2. 创作工厂：图片生成 /image-factory、视频生成 /video-factory、音乐生成 /music-factory、文案创作 /copywriting、翻译 /translation、PPT 生成 /ppt-factory、内容发布 /publish（文章/图片/视频一键发布公众号/抖音/快手，支持引导式素材包与账号自动发布，支持排期日历定时发布与数据看板追踪）、小程序开发 /miniapp（电商/预约/展示/工具/资讯等模板 + AI 生成完整微信小程序项目）、小游戏开发 /games（贪吃蛇/2048/飞机大战/打砖块/记忆翻牌/俄罗斯方块/扫雷/三消等模板 + AI 生成双版本小游戏：网页版在线试玩 + 微信小游戏版开发上线）、配音工坊 /voice（文字转语音，短视频旁白/广告口播/有声书等场景预设，长文本自动分段拼接）、表情包工坊 /meme（经典黄底/熊猫白底/公告红底等样式 + AI 场景一键生成表情包）、作品广场 /gallery（全平台 AI 作品聚合，点赞评论互动）、模板市场 /templates（四大工坊内置模板聚合浏览，一键跳转使用）。
3. 效率工具箱：/tool-hub 提供 50+ 覆盖职场办公、自媒体、学习研究的 AI 工具；另有 Excel 处理 /excel、股票分析 /stock、AB 实验 /ab-testing、数据看板 /dashboard。
4. 个人中心：/profile 查看每日额度、修改昵称头像密码；会员 /membership 升级套餐；使用记录 /records；帮助中心 /help（含新手引导回放）；首页 /home 支持深色/浅色一键切换（侧边栏底部月亮/太阳按钮）与「我的收藏」「常用工具」「草稿箱」快捷卡片。

# 常见问题速查
- 注册登录：登录页点「注册」，用户名 2-20 位、密码至少 6 位；默认管理员 admin / admin123。
- 每日额度：免费 30 次/天，专业版 200 次，至尊版无限；每次 AI 调用消耗 1 次；每天 0 点重置；可在 /profile 查看。
- 额度用完：联系平台管理员开通会员，或等次日 0 点重置。
- 快速找功能：按 ⌘K / Ctrl+K 打开全局搜索，或点击左侧边栏顶部搜索框。
- 分享结果：工具结果区点「分享」生成公开链接，对方无需登录即可查看。
- 切换模型：在「系统配置 → 模型配置」查看/调整；部分工具支持高级选项切换模型。
- 修改密码：个人中心 → 修改密码，填原密码+新密码。
- 部署失败：系统自动 AI 诊断修复（拉日志→定位根因→改码→重建→健康检查，最多 3 轮），也可在沙箱运行页手动触发。
- 内容发布：创作工厂 → 发布中心 /publish。从素材库加载历史文章/图片/视频，选平台（公众号/抖音/快手）一键发布；未配置自动发布账号时自动生成「素材包 + 分步操作指引」，到官方 App/后台粘贴即可。账号配置在发布中心 → 账号配置 Tab（公众号 AppID/Secret 可直接自动发布；抖音/快手需开放平台审核通过）。
- 小程序开发：创作工厂 → 小程序工坊 /miniapp。选模板（电商/预约/展示/工具/资讯/自定义）+ 描述需求，AI 生成完整微信小程序项目（含 app.json/app.js/WXML 页面），在线预览、复制、下载 ZIP，用微信开发者工具导入即可运行；部署指引见页面底部按钮。
- 小游戏开发：创作工厂 → 小游戏工坊 /games。选模板（贪吃蛇/2048/飞机大战/打砖块/记忆翻牌/自定义）+ 描述玩法需求，AI 生成双版本小游戏：网页版（单文件，可在页面直接「在线试玩」，也可下载部署到任意网站）+ 微信小游戏版（wx/ 目录用微信开发者工具导入，个人主体可注册上线）；每次生成约 1-2 分钟。
- 配音工坊：创作工厂 → 配音工坊 /voice。选场景（短视频旁白/广告口播/有声书/新闻播报/儿童故事）+ 输入文字，AI 合成中文/英文配音，长文本自动分段拼接，支持自定义语速音色。
- 表情包工坊：创作工厂 → 表情包工坊 /meme。输入顶部/底部文字，选样式（经典黄底/熊猫白底/公告红底/暗夜黑底/蓝紫渐变/AI 生成），一键生成 1080×1080 表情包图片。
- 发布排期：发布中心 → 排期日历 Tab。创建计划发布的内容，选平台/类型/时间，到点后一键「立即发布」；数据看板 Tab 查看发布总量、成功率、平台分布与近 30 天趋势。
- 作品广场：创作工厂 → 作品广场 /gallery。图片/视频/音频作品自动聚合展示，可点赞、评论互动。
- 模板市场：创作工厂 → 模板市场 /templates。小游戏玩法/小程序结构/表情包样式/配音场景四大类模板聚合，点击卡片直达对应工坊。
- 草稿箱：创作工厂各页面输入自动保存草稿，首页「草稿箱」卡片可恢复继续编辑或删除。
- 深色模式：点击侧边栏底部月亮/太阳按钮切换深色/浅色，选择会记住，跟随系统偏好。
- 新手引导：帮助中心可重播，首次登录自动弹出。

# 回复规范
- 用简体中文，简洁清晰，优先用短段落和列表；可适当使用 Markdown（标题/列表/加粗）。
- 回答使用问题时可给出对应菜单路径或页面入口，帮助用户快速找到功能。
- 用户问「你能做什么」时，简明介绍你的能力并给出示例问题。
- 涉及账号安全、会员购买等敏感问题时，引导联系管理员（admin@xiaotuan.ai）。
- 不确定的信息不要编造，如实说明并建议查阅帮助中心或联系管理员。"""


# ── 全局助手 SSE 头（与 chat_engine 保持一致）────────────────
_ASSISTANT_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _sse_event(event: str, data: dict) -> str:
    """序列化 SSE 事件。"""
    import json as _json
    return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/assistant/chat")
@limiter.limit(_rl("10 per minute"))
async def assistant_chat(request: Request, req: AssistantChatRequest, current_user: dict = require_auth()):
    """全局浮动机器人对话（非流式，兼容旧客户端）。"""
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    parts = []
    for m in (req.history or [])[-10:]:
        role = "用户" if m.get("role") == "user" else "助手"
        content = (m.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content[:500]}")
    user_prompt = "\n\n".join(parts)
    if user_prompt:
        user_prompt += f"\n\n用户最新问题: {message}"
    else:
        user_prompt = message

    start = time.time()
    try:
        result = await call_llm_async(_ASSISTANT_SYSTEM, user_prompt, max_tokens=1500, temperature=0.5)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, "操作失败，请稍后重试") from e
    elapsed = round(time.time() - start, 2)
    log_usage("assistant_chat", len(user_prompt), len(result), elapsed, user_id=str(current_user.get("user_id", "")))
    return {"result": result, "elapsed": elapsed}


@app.post("/api/assistant/chat/stream")
@limiter.limit(_rl("10 per minute"))
async def assistant_chat_stream(request: Request, req: AssistantChatRequest, current_user: dict = require_auth()):
    """全局浮动机器人对话（SSE 流式）— 打字机增量输出。"""
    message = req.message.strip()
    if not message:
        raise HTTPException(400, "消息不能为空")

    import json as _json

    parts = []
    for m in (req.history or [])[-10:]:
        role = "用户" if m.get("role") == "user" else "助手"
        content = (m.get("content") or "").strip()
        if content:
            parts.append(f"{role}: {content[:500]}")
    user_prompt = "\n\n".join(parts)
    if user_prompt:
        user_prompt += f"\n\n用户最新问题: {message}"
    else:
        user_prompt = message

    start = time.time()

    async def gen():
        try:
            full = ""
            async for delta, full in stream_llm_async(
                system_prompt=_ASSISTANT_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.5,
            ):
                yield _sse_event("delta", {"text": delta})
            elapsed = round(time.time() - start, 2)
            log_usage("assistant_chat_stream", len(user_prompt), len(full), elapsed, user_id=str(current_user.get("user_id", "")))
            yield _sse_event("done", {"full": full, "elapsed": elapsed})
        except HTTPException as e:
            yield _sse_event("error", {"detail": e.detail})
        except Exception as e:
            logger.exception("assistant stream failed")
            yield _sse_event("error", {"detail": f"助手服务异常: {str(e)[:200]}"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers=_ASSISTANT_SSE_HEADERS)


@app.get("/api/auth/me")
async def get_me(current_user: dict = require_auth()):
    """当前用户资料（含会员与额度）。"""
    return get_user_profile(current_user.get("user_id"))


@app.put("/api/auth/me")
async def update_me(req: ProfileUpdateRequest, current_user: dict = require_auth()):
    """更新昵称/头像/邮箱。"""
    return update_user_profile(current_user.get("user_id"), nickname=req.nickname, avatar=req.avatar, email=req.email)


@app.put("/api/auth/password")
async def change_pwd(req: ChangePasswordRequest, current_user: dict = require_auth()):
    """修改密码。"""
    change_password(current_user.get("user_id"), req.old_password, req.new_password)
    return {"message": "密码已更新"}


@app.get("/api/auth/quota")
async def quota(current_user: dict = require_auth()):
    """当前额度信息。"""
    return get_quota_info(current_user.get("user_id"))


# ── v17.0 密码重置 / 试用 / 用量明细 / 账单 ───────────────────────


@app.post("/api/auth/forgot-password")
@limiter.limit(_rl("3 per minute"))
async def forgot_password(request: Request, req: ForgotPasswordRequest):
    """生成密码重置令牌（30 分钟有效）并发送邮件。"""
    result = send_password_reset_token(req.username)
    if result.get("sent"):
        from common.mailer import is_smtp_configured, send_password_reset_email
        # 若 SMTP 已配置，尝试真实发送邮件；未配置时返回 token 便于开发测试
        if is_smtp_configured():
            from common.db import get_db
            conn = get_db()
            try:
                row = conn.execute(
                    "SELECT id, email FROM users WHERE username=? AND active=1",
                    (req.username,),
                ).fetchone()
            finally:
                conn.close()
            to_email = row["email"] if row else ""
            if to_email and result.get("token"):
                reset_link = f"{os.environ.get('APP_BASE_URL', 'http://localhost:5173')}/reset-password?token={result['token']}"
                send_password_reset_email(to_email, req.username, reset_link)
        return {"sent": True, "message": "重置令牌已生成，请查收邮件"}
    raise HTTPException(400, result.get("reason", "操作失败"))


@app.post("/api/auth/reset-password")
async def reset_pwd(req: ResetPasswordRequest):
    """用令牌重置密码。"""
    result = reset_password(req.token, req.new_password)
    if result.get("success"):
        return {"message": "密码已重置，请使用新密码登录"}
    raise HTTPException(400, result.get("reason", "重置失败"))


@app.get("/api/auth/usage/detail")
async def usage_detail(current_user: dict = require_auth()):
    """近 30 天按功能分组的用量明细。"""
    return {"items": get_usage_detail(current_user.get("user_id"), days=30)}


@app.get("/api/auth/usage/timeline")
async def usage_timeline(current_user: dict = require_auth()):
    """每日用量趋势（用于折线图）。"""
    return {"data": get_usage_daily_timeline(current_user.get("user_id"), days=30)}


@app.get("/api/auth/billing")
async def billing_history(current_user: dict = require_auth()):
    """用户账单历史（订单 + Stripe 会话）。"""
    return {"orders": get_billing_history(current_user.get("user_id"))}


# ── 结果分享（商业版：引流传播） ─────────────────────────────
# 首页案例墙预置示例成果：平台暂无真实分享时展示（is_demo 标记，前端点击直达工具页）
_DEMO_SHOWCASE = [
    {
        "share_code": "",
        "is_demo": True,
        "route": "/ppt-factory",
        "content_type": "PPT 演示",
        "title": "2026年智能家居行业趋势分析",
        "preview": "AI 原生、无感互联、绿色能源三大趋势拆解，含市场数据、竞争格局与战略建议，12 页结构化演示文稿。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/image-factory",
        "content_type": "AI 图片",
        "title": "高端香水商业摄影",
        "preview": "金色时刻布光 + 纯白背景，专业级产品摄影提示词生成效果。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/data-analyzer",
        "content_type": "数据分析",
        "title": "电商销售数据分析报告",
        "preview": "区域 × 品类交叉分析、趋势对比与 Top 排名，自动生成图表与可执行建议。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/voice-dubbing",
        "content_type": "AI 配音",
        "title": "短视频口播配音（晓晓 · 1.0x）",
        "preview": "多音色场景化配音，支持语速/音调微调，一键导出 mp3。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/video-factory",
        "content_type": "AI 视频",
        "title": "文生视频：城市夜景延时",
        "preview": "提示词直接生成 5s 视频片段，支持分辨率/帧率/时长自定义。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/code-sandbox",
        "content_type": "代码运行",
        "title": "Python 销售数据分析沙箱",
        "preview": "在线编写并运行 pandas 分析代码，即时输出结果与可视化图表。",
        "views": 0,
        "created_at": "",
    },
]


@app.get("/api/showcase")
async def showcase(limit: int = 12):
    """公开成果精选：用户主动分享的内容中挑高浏览案例（首页案例墙，无需登录）。

    分享内容本身即公开（分享页无鉴权），此处仅聚合展示，点击跳转分享页形成传播闭环。
    当平台暂无真实分享时，返回系统精选示例成果（is_demo: true，点击直达对应工具页），
    让新用户/访客首页不空、可感知平台能力；一旦出现真实分享，示例自动让位。
    """
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT share_code, title, content_type, views, created_at,
                      substr(content, 1, 200) AS preview
               FROM shares
               WHERE content != '' AND length(content) >= 10 AND is_test = 0
               ORDER BY views DESC, created_at DESC
               LIMIT ?""",
            (min(limit, 30),),
        ).fetchall()
        items = []
        for r in rows:
            item = dict(r)
            item["preview"] = (item.get("preview") or "").replace("\n", " ").strip()[:120]
            items.append(item)
        # 无真实分享时：返回系统精选示例成果（标记 is_demo，前端跳工具页）
        if not items:
            items = _DEMO_SHOWCASE[: min(limit, len(_DEMO_SHOWCASE))]
        return {"items": items}
    finally:
        conn.close()


# 工厂作品源 → 可读名称（与 gallery.SOURCE_LABEL 保持一致）
_FACTORY_SOURCE_LABEL = {
    "image_factory": "图片工厂",
    "video_factory": "视频工厂",
    "music_factory": "音乐工厂",
    "meme_factory": "表情包工坊",
    "game_factory": "小游戏工坊",
}

# 工厂类型 → 首页展示跳转路由（与前端菜单一致）
_FACTORY_ROUTE = {
    "image_factory": "/image-factory",
    "video_factory": "/video-factory",
    "music_factory": "/music-factory",
    "meme_factory": "/meme",
    "game_factory": "/games",
}


def _media_file_exists(media_url: str) -> bool:
    """按 media_url 前缀定位后端目录，校验媒体文件是否真实存在（过滤历史孤儿记录）。"""
    if not media_url:
        return False
    base = os.path.join(os.path.dirname(__file__))
    for prefix, sub in (
        ("/api/video-factory/videos/", "video_factory"),
        ("/api/image-factory/images/", "image_factory"),
        ("/api/meme-factory/images/", "meme_factory"),
    ):
        if media_url.startswith(prefix):
            return os.path.exists(os.path.join(base, sub, media_url[len(prefix):]))
    return True


@app.get("/api/factory/latest")
async def factory_latest(limit: int = 12):
    """最新创作墙：聚合各工厂最新生成的图片/视频作品（含封面/缩略图），供首页真实作品展示。

    - 数据源：artifacts 表 type ∈ (image, video) 且 active=1 的最新记录
    - 图片作品自带 media_url 可直显；视频作品优先 thumbnail，缺时按 video_factory 规则推断封面 URL
    - 首页点击直达对应工厂页，展示平台最强生成能力的真实产出
    """
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, type, author, media_url, thumbnail, duration, created_at, content
               FROM artifacts
               WHERE type IN ('image','video') AND active=1 AND media_url != ''
               ORDER BY created_at DESC LIMIT ?""",
            (min(limit, 30),),
        ).fetchall()
        items = []
        for r in rows:
            media_url = r["media_url"] or ""
            # 过滤媒体文件已删除的孤儿记录（避免破损封面/黑屏视频出现在首页）
            if not _media_file_exists(media_url):
                continue
            thumbnail = r["thumbnail"] or ""
            if not thumbnail and r["type"] == "video" and "/video-factory/videos/" in media_url:
                stem = media_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if stem:
                    thumbnail = f"/api/video-factory/covers/{stem}.jpg"
            # 提取描述（content 为 dict 时取 prompt）
            prompt = ""
            try:
                obj = json.loads(r["content"] or "{}")
                if isinstance(obj, dict):
                    prompt = (obj.get("prompt") or "")[:80]
            except Exception:
                prompt = (r["content"] or "")[:80]
            items.append(
                {
                    "id": r["id"],
                    "type": r["type"],
                    "author": _FACTORY_SOURCE_LABEL.get(r["author"], r["author"] or "平台用户"),
                    "media_url": media_url,
                    "thumbnail": thumbnail,
                    "duration": float(r["duration"] or 0),
                    "prompt": prompt,
                    "created_at": r["created_at"] or "",
                    "route": _FACTORY_ROUTE.get(r["author"], "/gallery"),
                }
            )
        return {"items": items}
    finally:
        conn.close()


@app.post("/api/shares")
async def create_share_api(req: ShareCreateRequest, current_user: dict = require_auth()):
    """创建分享，返回 share_code。"""
    return create_share(current_user.get("user_id"), req.content_type, req.title, req.content)


@app.get("/api/shares/my")
async def my_shares(current_user: dict = require_auth()):
    """我的分享工作台：访问 / 注册转化 / 裂变奖励进度。"""
    from common.auth import get_my_share_stats

    return get_my_share_stats(current_user.get("user_id"))


@app.get("/api/shares/{share_code}")
async def get_share_api(share_code: str, request: Request, src: str = ""):
    """公开访问分享内容（无需登录，浏览量 +1，记录访问埋点 + 裂变奖励）。"""
    share = get_share(share_code)
    if not share:
        raise HTTPException(404, "分享不存在或已失效")
    # 埋点：来源渠道优先取 query src / utm_source，其次 Referer 域名，默认 direct
    source = (src or request.query_params.get("utm_source", "")).strip()[:32]
    referer = request.headers.get("referer", "")[:200]
    if not source:
        if referer:
            try:
                host = urlparse(referer).hostname or ""
                source = host if host not in ("localhost", "127.0.0.1") else "direct"
            except ValueError:
                source = "direct"
        else:
            source = "direct"
    # 去重键：同访问者只计一次有效访问；分享者本人访问不计奖励
    visitor_key = _share_visitor_key(request)
    _record_share_visit(share["id"], source, referer, visitor_key)
    # 裂变奖励：有效访问达阈值 → 分享者得一次性额度（幂等，见 grant_share_visit_reward）
    from common.auth import grant_share_visit_reward

    grant_share_visit_reward(share, visitor_key)
    return share


@app.get("/share/{share_code}", response_class=HTMLResponse)
async def share_seo_page(share_code: str):
    """分享页 SEO 渲染：为爬虫/社交平台返回带 og meta 的 HTML。

    nginx 将 /share/* 代理到本端点；普通浏览器会立即跳转到前端 SPA
    （?share=code 由 App.jsx 解析），抓取器则读到完整 meta 信息。
    """
    share = get_share(share_code)
    if not share:
        return HTMLResponse(
            """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">"""
            """<title>分享内容不存在 - 小团智能平台</title>"""
            """<meta http-equiv="refresh" content="0; url=/"></head><body></body></html>""",
            status_code=404,
        )
    title = (share.get("title") or "分享内容")[:80]
    desc = ((share.get("content") or "").replace("#", " ").replace("\n", " ").strip())[:200]
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - 小团智能平台</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="小团智能平台">
<meta property="og:url" content="/share/{share_code}">
<meta property="og:locale" content="zh_CN">
<meta http-equiv="refresh" content="0; url=/?share={share_code}">
<script>location.replace("/?share={share_code}")</script>
</head>
<body>
<article style="max-width:720px;margin:40px auto;font-family:system-ui;padding:0 20px">
<h1>{title}</h1>
<p>{desc}</p>
<p><a href="/?share={share_code}">查看完整内容</a></p>
</article>
</body>
</html>"""
    return HTMLResponse(html)


# ── SEO 基础设施（获客：robots / sitemap） ─────────────────────
# 按请求 Host 动态生成绝对 URL，适配任意部署域名；nginx / serve_frontend 将
# /robots.txt、/sitemap.xml 代理到本端点，避免 SPA fallback 吞掉。

# 主要公开页面（工具/能力入口，登录后运营页不收录）
_SEO_PAGES = [
    ("/", "小团智能平台 - AI 赋能各行各业", "0.9"),
    ("/tool-hub", "工具箱 - 30+ AI 效率工具", "0.9"),
    ("/ppt-factory", "AI PPT 演示文稿生成器", "0.8"),
    ("/image-factory", "AI 图片创作工厂", "0.8"),
    ("/video-factory", "AI 视频生成工厂", "0.8"),
    ("/music-factory", "AI 音乐生成工厂", "0.8"),
    ("/copywriting", "AI 文案创作", "0.8"),
    ("/translation", "AI 翻译", "0.8"),
    ("/voice-dubbing", "AI 配音（多音色）", "0.8"),
    ("/meme-factory", "AI 表情包工坊", "0.7"),
    ("/digital-human", "AI 数字人视频", "0.8"),
    ("/mindmap", "AI 思维导图", "0.7"),
    ("/forecast", "AI 数据预测", "0.7"),
    ("/doc-qa", "AI 文档问答", "0.7"),
    ("/pdf-tools", "PDF 工具箱", "0.7"),
    ("/web-search", "AI 联网搜索", "0.7"),
    ("/batch-process", "AI 批量处理", "0.7"),
    ("/code-interpreter", "AI 代码解释器", "0.7"),
    ("/data-analyzer", "AI 数据分析", "0.8"),
    ("/excel", "Excel 智能处理", "0.7"),
    ("/stock", "AI 股票分析", "0.7"),
    ("/miniapp", "小程序工坊", "0.7"),
    ("/publish", "内容发布中心", "0.7"),
    ("/templates", "行业模板库", "0.7"),
    ("/gallery", "灵感画廊", "0.7"),
    ("/api-platform", "开放 API 平台", "0.6"),
    ("/help", "帮助中心", "0.5"),
]


async def _site_base(request: Request) -> str:
    """按请求 Host 构造站点绝对地址（跟随 X-Forwarded-Proto，适配反代）。"""
    scheme = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host", "localhost:8888")
    return f"{scheme}://{host}"


@app.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt(request: Request):
    """爬虫规则：公开页可抓，运营/账号页禁抓；声明 sitemap 绝对地址。"""
    base = await _site_base(request)
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /login\n"
        "Disallow: /profile\n"
        "Disallow: /membership\n"
        "Disallow: /tasks\n"
        "Disallow: /records\n"
        "Disallow: /usage-analytics\n"
        "Disallow: /scheduler\n"
        "Disallow: /notifications\n"
        "Disallow: /favorites\n"
        f"\nSitemap: {base}/sitemap.xml\n"
    )
    return PlainTextResponse(body)


@app.get("/sitemap.xml", response_class=Response, include_in_schema=False)
async def sitemap_xml(request: Request):
    """站点地图：核心工具页 + 公开分享内容（浏览量/时效排序，最多 100 条）。"""
    from xml.sax.saxutils import escape

    base = await _site_base(request)
    urls = []
    for path, _title, priority in _SEO_PAGES:
        urls.append(
            f"<url><loc>{escape(base + path)}</loc><changefreq>weekly</changefreq>"
            f"<priority>{priority}</priority></url>"
        )
    try:
        from common.db import get_db

        conn = get_db()
        rows = conn.execute(
            """SELECT share_code, created_at FROM shares
               WHERE content != '' AND length(content) >= 10 AND is_test = 0
               ORDER BY views DESC, created_at DESC LIMIT 100"""
        ).fetchall()
        conn.close()
        for r in rows:
            lastmod = (r["created_at"] or "")[:10]
            urls.append(
                f"<url><loc>{escape(base + '/share/' + r['share_code'])}</loc>"
                + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
                + "<changefreq>monthly</changefreq><priority>0.6</priority></url>"
            )
    except Exception:
        pass  # 分享表不可用时仅返回静态页
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    return Response(content=xml, media_type="application/xml")


# ── 会员套餐 / 订单（商业版：支付闭环） ─────────────────────
@app.get("/api/membership/plans")
async def membership_plans():
    """会员套餐列表（公开，前端渲染套餐卡片）。"""
    from common.auth import MEMBERSHIP_PLANS, MEMBERSHIP_QUOTA

    plans = {
        "free": {
            "name": "免费版",
            "price": 0,
            "daily_quota": MEMBERSHIP_QUOTA["free"],
            "features": ["每日 30 次生成额度", "全部工具基础使用", "标准响应速度"],
        }
    }
    for key, info in MEMBERSHIP_PLANS.items():
        plans[key] = {**info, "daily_quota": info["daily_quota"]}
    return plans


@app.post("/api/orders")
async def create_order_api(req: OrderCreateRequest, current_user: dict = require_auth()):
    """创建会员订单（同一时间仅 1 个待处理订单，可选优惠码抵扣）。"""
    return create_order(current_user.get("user_id"), req.plan, req.coupon_code, req.stripe_session_id)


@app.get("/api/orders")
async def my_orders(current_user: dict = require_auth()):
    """我的订单列表（倒序）。"""
    return get_my_orders(current_user.get("user_id"))


@app.post("/api/orders/{order_id}/voucher")
async def submit_voucher_api(
    order_id: str,
    file: UploadFile | None = File(None),
    remark: str = Form(""),
    current_user: dict = require_auth(),
):
    """提交支付凭证（截图 + 备注），订单进入待审核。"""
    voucher = ""
    if file and file.filename:
        ext = os.path.splitext(file.filename or "")[1][:10] or ".png"
        name = f"v_{uuid.uuid4().hex[:12]}{ext}"
        path = os.path.join(UPLOAD_DIR, "vouchers", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "凭证图片不能超过 5MB")
        with open(path, "wb") as f:
            f.write(content)
        voucher = f"/uploads/vouchers/{name}"
    if not voucher and not remark.strip():
        raise HTTPException(400, "请上传支付凭证截图或填写转账说明")
    return submit_voucher(order_id, current_user.get("user_id"), voucher, remark)


# ── 收款码配置（商业版：扫码支付） ──────────────────────────
PAYMENT_QR_KEY = os.environ.get("PAYMENT_QR_KEY", "payment_qr")  # 配置键名，非敏感


def _get_payment_qr() -> str:
    """当前收款码路径（config 表，空串表示未配置）。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM config WHERE key=?", (PAYMENT_QR_KEY,)).fetchone()
    finally:
        conn.close()
    return row["value"] if row else ""


@app.get("/api/membership/payment-qr")
async def membership_payment_qr(current_user: dict = require_auth()):
    """当前收款码（登录用户可见，会员中心扫码支付展示）。"""
    return {"url": _get_payment_qr()}


@app.get("/api/admin/payment-qr")
async def admin_payment_qr(current_user: dict = require_auth()):
    """管理员查看收款码配置。"""
    from admin_api import _check_admin

    _check_admin(current_user)
    return {"url": _get_payment_qr()}


@app.post("/api/admin/payment-qr")
async def admin_upload_payment_qr(
    file: UploadFile = File(...),
    current_user: dict = require_auth(),
):
    """上传收款码图片（png/jpg/jpeg/webp，最多 5MB）。"""
    from admin_api import _check_admin

    _check_admin(current_user)
    if not file.filename:
        raise HTTPException(400, "请选择收款码图片")
    ext = os.path.splitext(file.filename)[1].lower()[:10]
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "仅支持 png / jpg / jpeg / webp 图片")
    name = f"qr_{uuid.uuid4().hex[:12]}{ext}"
    path = os.path.join(UPLOAD_DIR, "qr", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "收款码图片不能超过 5MB")
    with open(path, "wb") as f:
        f.write(content)
    url = f"/uploads/qr/{name}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO config (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (PAYMENT_QR_KEY, url),
        )
        conn.commit()
    finally:
        conn.close()
    return {"url": url, "message": "收款码已更新"}


@app.delete("/api/admin/payment-qr")
async def admin_remove_payment_qr(current_user: dict = require_auth()):
    """移除收款码配置。"""
    from admin_api import _check_admin

    _check_admin(current_user)
    conn = get_db()
    try:
        conn.execute("DELETE FROM config WHERE key=?", (PAYMENT_QR_KEY,))
        conn.commit()
    finally:
        conn.close()
    return {"message": "收款码已移除"}


# ── 邀请码分销（商业版：引流） ───────────────────────────────
@app.get("/api/invite")
async def invite_info(current_user: dict = require_auth()):
    """我的邀请码 / 已邀请用户 / 奖励规则。"""
    return get_invite_info(current_user.get("user_id"))


@app.get("/api/invite/leaderboard")
async def invite_leaderboard(limit: int = 10, current_user: dict = require_auth()):
    """邀请排行榜：邀请人数 Top N（仅展示有邀请记录的用户）+ 我的排名。"""
    limit = max(3, min(limit, 50))
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT u.id, u.username, u.nickname, COUNT(i.id) AS invites
               FROM users u LEFT JOIN users i ON i.invited_by = u.id
               GROUP BY u.id
               ORDER BY invites DESC, u.created_at ASC""",
        ).fetchall()
    finally:
        conn.close()
    board = []
    my_rank = None
    me_id = str(current_user.get("user_id"))
    for idx, r in enumerate(rows, 1):
        invites = int(r["invites"])
        if str(r["id"]) == me_id:
            my_rank = idx
        if invites > 0 and len(board) < limit:
            board.append(
                {
                    "rank": len(board) + 1,
                    "username": r["username"],
                    "nickname": r["nickname"] or r["username"],
                    "invites": invites,
                }
            )
    # 若我的排名在榜单外，附带返回（前端展示"我的排名"）
    my_invites = next((int(r["invites"]) for r in rows if str(r["id"]) == me_id), 0)
    return {"board": board, "my_rank": my_rank, "my_invites": my_invites}


@app.get("/api/invite/history")
async def invite_history(limit: int = 50, current_user: dict = require_auth()):
    """邀请历史列表。"""
    from common.auth import get_invite_history
    return get_invite_history(current_user.get("user_id"), limit)


@app.get("/api/invite/rewards")
async def invite_rewards(limit: int = 50, current_user: dict = require_auth()):
    """奖励流水列表。"""
    from common.auth import get_invite_rewards
    return get_invite_rewards(current_user.get("user_id"), limit)


# ── 审计日志（v17.2）───────────────────────────────────────────
@app.get("/api/audit/logs")
async def get_audit_log_entries(
    user_id: str = "",
    action: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
    current_user: dict = require_auth(),
):
    """获取审计日志（仅管理员可访问）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "权限不足")
    from common.audit import get_audit_logs
    return get_audit_logs(user_id, action, start_date, end_date, limit)


@app.get("/api/audit/stats")
async def get_audit_stats(current_user: dict = require_auth()):
    """获取审计统计（仅管理员可访问）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "权限不足")
    from common.db import get_db
    conn = get_db()
    try:
        # 今日操作数
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]
        
        # 操作类型分布
        action_stats = conn.execute(
            "SELECT action, COUNT(*) as cnt FROM audit_logs GROUP BY action ORDER BY cnt DESC LIMIT 10"
        ).fetchall()
        
        # 失败操作数
        fail_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE success = 0"
        ).fetchone()[0]
        
        return {
            "today_count": today_count,
            "fail_count": fail_count,
            "action_stats": [dict(r) for r in action_stats],
        }
    finally:
        conn.close()


# ── 内容权限（v9.3：页面可见性 / 灰度发布） ─────────────────
@app.get("/api/access/pages")
async def access_pages(current_user: dict = require_auth()):
    """当前用户可见的页面列表（Sidebar / 路由守卫使用）。"""
    from permissions import PAGES, access_status, get_visibility_map, load_user_ctx

    vis_map = get_visibility_map("page")
    user_ctx = load_user_ctx(current_user)
    result = []
    for p in PAGES:
        status = access_status(user_ctx, vis_map.get(p["id"], "all"))
        if not status["visible"]:
            continue
        item = {**p}
        if status.get("locked"):
            item["locked"] = True
            item["requires"] = status["requires"]
        result.append(item)
    return result


# ── Agent 管理 ────────────────────────────────────────────────
@app.get("/api/agents")
async def list_agents(current_user: dict = require_auth()):
    """获取所有 Agent（含绑定资源统计与最近运行信息）"""
    conn = get_db()
    agents = conn.execute("SELECT * FROM agents ORDER BY created_at DESC").fetchall()
    # 会话统计：会话数近似执行次数，最新会话时间作为 last_run
    run_stats = {}
    try:
        rows = conn.execute(
            "SELECT agent_id, COUNT(*) cnt, MAX(updated_at) last_run FROM conversations GROUP BY agent_id"
        ).fetchall()
        for r in rows:
            run_stats[r["agent_id"]] = {"execution_count": r["cnt"], "last_run": r["last_run"]}
    except Exception:
        pass
    conn.close()
    result = []
    for a in agents:
        d = dict(a)

        def _parse_list(raw):
            try:
                v = json.loads(raw or "[]")
                return v if isinstance(v, list) else []
            except (json.JSONDecodeError, TypeError):
                return []

        tools = _parse_list(d.get("tools"))
        kbs = _parse_list(d.get("knowledge_base_ids"))
        skills = _parse_list(d.get("skill_ids"))
        mcps = _parse_list(d.get("mcp_server_ids"))
        st = run_stats.get(d["id"], {})
        d["tool_count"] = len(tools)
        d["kb_count"] = len(kbs)
        d["skill_count"] = len(skills)
        d["mcp_count"] = len(mcps)
        d["execution_count"] = st.get("execution_count", 0)
        d["last_run"] = st.get("last_run")
        result.append(d)
    return result


@app.post("/api/agents")
async def create_agent(req: AgentCreateRequest, current_user: dict = require_auth()):
    """创建 Agent"""
    conn = get_db()
    agent_id = f"agent_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO agents (id, name, description, instructions, model, tools, knowledge_base_ids, skill_ids, mcp_server_ids, active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            agent_id,
            req.name,
            req.description,
            req.instructions,
            req.model,
            json.dumps(req.tools),
            json.dumps(req.knowledge_base_ids),
            json.dumps(req.skill_ids),
            json.dumps(req.mcp_server_ids),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": agent_id, "name": req.name}


@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, req: AgentUpdateRequest, current_user: dict = require_auth()):
    """更新 Agent"""
    conn = get_db()
    updates = []
    vals = []
    for f in ["name", "description", "instructions", "model"]:
        v = getattr(req, f, None)
        if v is not None:
            updates.append(f"{f}=?")
            vals.append(v)
    if req.active is not None:
        updates.append("active=?")
        vals.append(1 if req.active else 0)
    for f in ["tools", "knowledge_base_ids", "skill_ids", "mcp_server_ids"]:
        v = getattr(req, f, None)
        if v is not None:
            updates.append(f"{f}=?")
            vals.append(json.dumps(v))
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(agent_id)
    conn.execute(f"UPDATE agents SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": agent_id}


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str, current_user: dict = require_auth()):
    """删除 Agent"""
    conn = get_db()
    conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── Agent 模板（agent_templates/ 标准目录）────────────────────
_AGENT_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_templates")

# 模板中文名与展示元信息（无映射时回退 frontmatter name）
_AGENT_TEMPLATE_META = {
    "architect-agent": {"name": "架构师 Agent", "tag": "analysis", "desc": "技术方案、系统架构、技术选型"},
    "dba-agent": {"name": "DBA 数据库 Agent", "tag": "analysis", "desc": "数据建模、SQL 优化、备份恢复"},
    "dev-agent": {"name": "开发工程师 Agent", "tag": "coding", "desc": "代码生成、重构、审查"},
    "pm-agent": {"name": "产品经理 Agent", "tag": "analysis", "desc": "PRD 编写、需求分析、用户故事"},
    "qa-agent": {"name": "测试工程师 Agent", "tag": "coding", "desc": "测试用例、自动化测试、质量保障"},
    "sre-agent": {"name": "SRE 运维 Agent", "tag": "service", "desc": "部署、监控、故障排查"},
    "tech-writer-agent": {"name": "技术写手 Agent", "tag": "writing", "desc": "文档生成、API 文档、用户手册"},
    "ui-designer-agent": {"name": "UI/UX 设计师 Agent", "tag": "analysis", "desc": "界面设计、交互原型、设计规范"},
}


def _parse_agent_template_file(skill_path: str) -> dict | None:
    """解析 SKILL.md：提取 frontmatter（name/description）+ Instructions 正文。"""
    try:
        with open(skill_path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None
    fm = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
            body = parts[2]
    raw_name = fm.get("name", "").strip()
    if not raw_name:
        return None
    # Instructions：取 `## Instructions` 标题后的正文（截取到下一个二级标题）
    instructions = ""
    idx = body.find("## Instructions")
    if idx >= 0:
        rest = body[idx + len("## Instructions") :]
        next_h2 = rest.find("\n## ")
        instructions = rest[:next_h2].strip() if next_h2 >= 0 else rest.strip()
    if not instructions:
        instructions = body.strip()[:2000]
    meta = _AGENT_TEMPLATE_META.get(raw_name, {})
    return {
        "name": raw_name,
        "label": meta.get("name") or fm.get("label") or raw_name.replace("-", " ").title(),
        "description": fm.get("description", ""),
        "tag": meta.get("tag", "general"),
        "instructions": instructions,
        "title": (body.strip().splitlines() or [""])[0].lstrip("# ").strip(),
    }


@app.get("/api/agent-templates")
async def list_agent_templates(current_user: dict = require_auth()):
    """获取 Agent 模板列表（来自 agent_templates/ 标准目录）。"""
    templates = []
    if not os.path.isdir(_AGENT_TEMPLATES_DIR):
        return []
    for sub in sorted(os.listdir(_AGENT_TEMPLATES_DIR)):
        skill_path = os.path.join(_AGENT_TEMPLATES_DIR, sub, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        tpl = _parse_agent_template_file(skill_path)
        if tpl:
            templates.append(tpl)
    return templates


@app.post("/api/agent-templates/{template_name}/create")
async def create_agent_from_template(template_name: str, current_user: dict = require_auth()):
    """从模板一键创建 Agent：解析 SKILL.md 的 Instructions 作为系统指令。"""
    if not template_name or "/" in template_name or ".." in template_name:
        raise HTTPException(400, "模板名不合法")
    skill_path = None
    if os.path.isdir(_AGENT_TEMPLATES_DIR):
        for sub in os.listdir(_AGENT_TEMPLATES_DIR):
            candidate = os.path.join(_AGENT_TEMPLATES_DIR, sub, "SKILL.md")
            if os.path.isfile(candidate):
                tpl = _parse_agent_template_file(candidate)
                if tpl and tpl["name"] == template_name:
                    skill_path = candidate
                    break
    if not skill_path:
        raise HTTPException(404, "操作失败，请稍后重试")
    tpl = _parse_agent_template_file(skill_path)
    if not tpl:
        raise HTTPException(400, "模板解析失败")

    conn = get_db()
    agent_id = f"agent_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO agents (id, name, description, instructions, model, tools, knowledge_base_ids, skill_ids, mcp_server_ids, active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
        (
            agent_id,
            tpl["label"],
            tpl["description"] or tpl["title"],
            tpl["instructions"],
            "agnes-2.5-flash",
            "[]",
            "[]",
            "[]",
            "[]",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": agent_id, "name": tpl["label"], "template": template_name}


# ── Workflow 管理 ──────────────────────────────────────────────
@app.get("/api/workflows")
async def list_workflows(current_user: dict = require_auth()):
    """获取工作流列表"""
    conn = get_db()
    workflows = conn.execute("SELECT * FROM workflows ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for w in workflows:
        d = dict(w)
        d["status"] = "active" if d.get("active") else "inactive"
        try:
            d["nodes"] = json.loads(d.get("steps") or "[]")
        except (json.JSONDecodeError, TypeError):
            d["nodes"] = []
        result.append(d)
    return result


@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, current_user: dict = require_auth()):  # noqa: C901
    """获取工作流详情"""
    conn = get_db()
    row = conn.execute("SELECT * FROM workflows WHERE id=?", (workflow_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "工作流不存在")
    d = dict(row)
    d["status"] = "active" if d.get("active") else "inactive"
    try:
        nodes = json.loads(d.get("steps") or "[]")
    except (json.JSONDecodeError, TypeError):
        nodes = []
    try:
        edges = json.loads(d.get("connections") or "[]")
        if not isinstance(edges, list):
            edges = []
    except (json.JSONDecodeError, TypeError):
        edges = []

    # 规范化节点格式：确保每个节点都有 x/y/config/type 字段
    valid_types = {"agent", "http", "condition", "parallel", "code", "delay", "output"}
    type_map = {"start": "agent", "end": "output", "llm": "agent", "http": "http", "condition": "condition"}
    normalized_nodes = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        # 映射旧类型到新类型
        raw_type = n.get("type", "agent")
        n["type"] = type_map.get(raw_type, raw_type) if raw_type not in valid_types else raw_type
        # 确保有 x/y 坐标
        if "x" not in n:
            n["x"] = 80 + len(normalized_nodes) * 180
        if "y" not in n:
            n["y"] = 160
        # 确保有 config
        if "config" not in n:
            n["config"] = {}
        normalized_nodes.append(n)

    # 规范化边格式：统一使用 from/to
    normalized_edges = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        # 兼容 source/target 和 from/to
        edge_from = e.get("from") or e.get("source")
        edge_to = e.get("to") or e.get("target")
        if edge_from and edge_to:
            normalized_edges.append(
                {
                    "id": e.get("id") or f"edge_{edge_from}_{edge_to}",
                    "from": edge_from,
                    "to": edge_to,
                }
            )

    d["nodes"] = normalized_nodes
    d["definition"] = {"nodes": normalized_nodes, "edges": normalized_edges}
    return d


@app.post("/api/workflows")
async def create_workflow(req: WorkflowCreateRequest, current_user: dict = require_auth()):
    """创建工作流"""
    import uuid

    workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
    # 处理 definition 字段（前端编辑器可能发送 WorkflowDefinition 对象或 JSON 字符串）
    steps = req.steps
    connections = req.connections
    if req.definition is not None:
        defn = req.definition
        if isinstance(defn, str):
            try:
                defn = json.loads(defn)
            except json.JSONDecodeError:
                defn = {}
        if hasattr(defn, "nodes"):
            steps = steps or defn.nodes
            connections = connections or defn.edges
        elif isinstance(defn, dict):
            steps = steps or defn.get("nodes", [])
            connections = connections or defn.get("edges", [])
    conn = get_db()
    conn.execute(
        """INSERT INTO workflows (id, name, description, steps, connections, created_at, active)
           VALUES (?, ?, ?, ?, ?, ?, 1)""",
        (
            workflow_id,
            req.name,
            req.description,
            json.dumps(steps or []),
            json.dumps(connections or []),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": workflow_id, "name": req.name}


@app.put("/api/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, req: WorkflowUpdateRequest, current_user: dict = require_auth()):  # noqa: C901
    """更新工作流"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    if req.description is not None:
        updates.append("description=?")
        vals.append(req.description)
    if req.steps is not None:
        updates.append("steps=?")
        vals.append(json.dumps(req.steps))
    if req.connections is not None:
        updates.append("connections=?")
        vals.append(json.dumps(req.connections))
    # 前端编辑器发送 definition 字段（JSON 字符串或对象），含 nodes 和 edges
    if req.definition is not None:
        defn = req.definition
        if isinstance(defn, str):
            try:
                defn = json.loads(defn)
            except json.JSONDecodeError:
                defn = {}
        if hasattr(defn, "nodes"):
            updates.append("steps=?")
            vals.append(json.dumps(defn.nodes))
            updates.append("connections=?")
            vals.append(json.dumps(defn.edges))
        elif isinstance(defn, dict):
            updates.append("steps=?")
            vals.append(json.dumps(defn.get("nodes", [])))
            updates.append("connections=?")
            vals.append(json.dumps(defn.get("edges", [])))
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(workflow_id)

    # 防抖保护：1.5s 内同一 workflow 的重复写入直接跳过（阻断旧页面循环）
    import time as _time

    now = _time.time()
    key = f"wf_write:{workflow_id}"
    last = _WF_LAST_WRITE.get(key, 0)
    if now - last < 1.5:
        conn.close()
        return {"success": True, "id": workflow_id, "deduped": True}
    _WF_LAST_WRITE[key] = now

    conn.execute(f"UPDATE workflows SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": workflow_id}


@app.delete("/api/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, current_user: dict = require_auth()):
    """删除工作流"""
    conn = get_db()
    conn.execute("DELETE FROM workflows WHERE id=?", (workflow_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── 会话管理 ──────────────────────────────────────────────────
# 会话/消息/记忆 API 已迁移至 sessions.py router（/api/sessions/*）


# ── Team 管理 ───────────────────────────────────────────────────
@app.get("/api/teams")
async def list_teams(current_user: dict = require_auth()):
    """获取所有 Teams"""
    conn = get_db()
    teams = conn.execute("SELECT * FROM teams ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(t) for t in teams]


@app.post("/api/teams")
async def create_team(req: TeamCreateRequest, current_user: dict = require_auth()):
    """创建 Team"""
    conn = get_db()
    team_id = f"team_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO teams (id, name, description, mode, members, instructions, respond_directly, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            team_id,
            req.name,
            req.description,
            req.mode,
            json.dumps(req.members),
            req.instructions,
            1 if req.respond_directly else 0,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": team_id, "name": req.name}


@app.put("/api/teams/{team_id}")
async def update_team(team_id: str, req: TeamUpdateRequest, current_user: dict = require_auth()):
    """更新 Team"""
    conn = get_db()
    conn.execute(
        """UPDATE teams SET name=?, description=?, mode=?, members=?, instructions=?, respond_directly=?
           WHERE id=?""",
        (
            req.name or "",
            req.description or "",
            req.mode or "coordinate",
            json.dumps(req.members or []),
            req.instructions or "",
            1 if req.respond_directly else 0,
            team_id,
        ),
    )
    conn.commit()
    conn.close()
    return {"id": team_id, "name": req.name or ""}


@app.delete("/api/teams/{team_id}")
async def delete_team(team_id: str, current_user: dict = require_auth()):
    """删除 Team"""
    conn = get_db()
    conn.execute("DELETE FROM teams WHERE id=?", (team_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ── Skills 管理（标准 Agent Skills 目录结构）───────────────────
@app.get("/api/skills")
async def list_skills(current_user: dict = require_auth()):
    """获取所有 Skills（含文件系统统计）"""
    conn = get_db()
    skills = conn.execute("SELECT * FROM skills ORDER BY created_at DESC").fetchall()
    conn.close()
    stats = skills_store.scan_stats()
    result = []
    for s in skills:
        d = dict(s)
        st = stats.get(d["id"], {"file_count": 0, "dir_counts": {}})
        d["file_count"] = st["file_count"]
        d["dir_counts"] = st.get("dir_counts", {})
        result.append(d)
    return result


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str, current_user: dict = require_auth()):
    """获取单个 Skill 详情（含文件统计）"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    d = dict(row)
    try:
        tree = skills_store.list_tree(skill_id)
        d["file_count"] = tree["file_count"]
        d["dir_counts"] = tree["dir_counts"]
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
    return d


@app.post("/api/skills")
async def create_skill(req: SkillCreateRequest, current_user: dict = require_auth()):
    """创建 Skill（落库 + 初始化标准目录结构）"""
    conn = get_db()
    skill_id = f"skill_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO skills (id, name, description, content, `references`, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            skill_id,
            req.name,
            req.description,
            req.content,
            req.references,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    try:
        # 标准目录结构：SKILL.md + scripts/references/examples/assets
        skills_store.ensure_standard_dirs(skill_id)
        skills_store.write_file(
            skill_id,
            "SKILL.md",
            skills_store.render_skill_markdown(
                {
                    "name": req.name,
                    "description": req.description,
                    "content": req.content,
                }
            ),
        )
    except (ValueError, OSError) as e:
        raise HTTPException(500, "操作失败，请稍后重试") from e
    return {"id": skill_id, "name": req.name}


def _sync_skill_meta_to_fs(skill_id: str, skill: dict, fields_updated: set) -> None:
    """将 DB 元数据同步到标准目录：SKILL.md 与 references/references.md。

    - name/description 更新：重写 frontmatter，保留磁盘正文（文件浏览器可能更新过）
    - content 更新：整体重写 SKILL.md（以 DB 为准）
    - references 更新：同步 references/references.md（空值删除）
    """
    if fields_updated & {"name", "description", "content"}:
        existing = skills_store.read_skill_md(skill_id)
        if "content" in fields_updated:
            body = skill.get("content") or ""
        else:
            body = skills_store.parse_skill_markdown(existing)["content"] if existing else (skill.get("content") or "")
        md = skills_store.render_skill_markdown(
            {
                "name": skill["name"],
                "description": skill["description"],
                "content": body,
            }
        )
        skills_store.write_file(skill_id, "SKILL.md", md)
    if "references" in fields_updated:
        refs = (skill.get("references") or "").strip()
        if refs:
            skills_store.write_file(skill_id, "references/references.md", refs)
        else:
            try:
                skills_store.delete_path(skill_id, "references/references.md")
            except FileNotFoundError:
                pass


@app.put("/api/skills/{skill_id}")
async def update_skill(skill_id: str, req: SkillUpdateRequest, current_user: dict = require_auth()):
    """更新 Skill（元数据 + 同步标准目录文件）"""
    conn = get_db()
    updates = []
    values = []
    for field in ["name", "description", "content", "references"]:
        v = getattr(req, field, None)
        if v is not None:
            updates.append(f"{field}=?")
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            values.append(v)
    if not updates:
        raise HTTPException(400, "没有需要更新的字段")
    values.append(skill_id)
    conn.execute(f"UPDATE skills SET {','.join(updates)} WHERE id=?", values)
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    try:
        _sync_skill_meta_to_fs(
            skill_id, dict(row), {u for u in updates if u in ("name", "description", "content", "references")}
        )
    except (ValueError, OSError) as e:
        raise HTTPException(500, "操作失败，请稍后重试") from e
    return {"success": True, "id": skill_id}


@app.delete("/api/skills/{skill_id}")
async def delete_skill(skill_id: str, current_user: dict = require_auth()):
    """删除 Skill（含标准目录）"""
    conn = get_db()
    conn.execute("DELETE FROM skills WHERE id=?", (skill_id,))
    conn.commit()
    conn.close()
    try:
        skills_store.delete_path(skill_id, "")
    except (ValueError, FileNotFoundError):
        pass
    return {"success": True}


# ── 标准 SKILL.md 支持（导入 / 导出 / ZIP 打包）────────────────
@app.post("/api/skills/import")
async def import_skill(req: dict, current_user: dict = require_auth()):
    """导入标准 SKILL.md 文本：自动解析 frontmatter 创建 Skill 并落盘。"""
    markdown = (req.get("markdown") or "").strip()
    if not markdown:
        raise HTTPException(400, "SKILL.md 内容不能为空")
    parsed = skills_store.parse_skill_markdown(markdown)
    name = (parsed["name"] or req.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "无法识别 Skill 名称（请在 frontmatter 中提供 name）")
    conn = get_db()
    skill_id = f"skill_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO skills (id, name, description, content, `references`, created_at)
           VALUES (?, ?, ?, ?, '', ?)""",
        (skill_id, name, parsed["description"], parsed["content"], datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    skills_store.ensure_standard_dirs(skill_id)
    skills_store.write_file(skill_id, "SKILL.md", markdown)
    return {"id": skill_id, "name": name, "description": parsed["description"]}


@app.post("/api/skills/import-zip")
async def import_skill_zip(file: UploadFile = File(...), current_user: dict = require_auth()):
    """导入标准 Skill 目录 zip 包（SKILL.md + scripts/references/examples/assets 等）。"""
    content = await file.read()
    if not content:
        raise HTTPException(400, "ZIP 文件为空")
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(400, "ZIP 包不能超过 20MB")
    try:
        parsed = skills_store.parse_skill_zip(content)
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
    name = (parsed["name"] or "").strip()
    if not name:
        raise HTTPException(400, "SKILL.md 缺少 frontmatter name，无法识别技能名称")
    conn = get_db()
    skill_id = f"skill_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO skills (id, name, description, content, `references`, created_at)
           VALUES (?, ?, ?, '', '', ?)""",
        (skill_id, name, parsed["description"], datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    skills_store.ensure_standard_dirs(skill_id)
    imported = skills_store.extract_zip_to(skill_id, content)
    return {"id": skill_id, "name": imported["name"], "imported": imported["imported"]}


@app.get("/api/skills/{skill_id}/export")
async def export_skill(skill_id: str, current_user: dict = require_auth()):
    """导出为标准 SKILL.md 文本（优先读取磁盘，兼容任意 Agent 工具）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    disk = skills_store.read_skill_md(skill_id)
    if disk is not None:
        return {"filename": f"{row['name']}/SKILL.md", "content": disk}
    return {
        "filename": f"{row['name']}/SKILL.md",
        "content": skills_store.render_skill_markdown(dict(row)),
    }


@app.get("/api/skills/{skill_id}/export-zip")
async def export_skill_zip(skill_id: str, current_user: dict = require_auth()):
    """导出整个 Skill 目录为 zip 包（标准结构，可直接用于其他 Agent 工具）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Skill 不存在")
    try:
        data, filename = skills_store.export_zip(skill_id, row["name"])
    except FileNotFoundError as e:
        raise HTTPException(400, "请求参数错误") from e
    except ValueError as e:
        raise HTTPException(400, "请求参数错误") from e
    # Content-Disposition 需 latin-1 安全：中文名走 RFC 5987 filename* 编码
    try:
        filename.encode("latin-1")
        ascii_name = filename
    except UnicodeEncodeError:
        ascii_name = "skill.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": (f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}")},
    )


# ── 知识库管理 ──────────────────────────────────────────────────
def _mask_kb_config(cfg: dict) -> dict:
    """脱敏知识库连接配置（password 掩码）。"""
    cfg = dict(cfg or {})
    if cfg.get("password"):
        cfg["password"] = "••••••"
    return cfg


def _kb_connect(cfg: dict):
    """建立数据库连接，返回 (conn, cursor, error)。支持 sqlite / mysql / postgres。"""
    engine = (cfg.get("engine") or "sqlite").lower()
    try:
        if engine == "sqlite":
            path = (cfg.get("database") or "").strip()
            if not path:
                return None, None, "未配置数据库文件路径"
            if not os.path.exists(path):
                return None, None, f"数据库文件不存在：{path}"
            conn = sqlite3.connect(path, timeout=5)
            return conn, conn.cursor(), None
        if engine == "mysql":
            try:
                import pymysql
            except ImportError:
                return None, None, "未安装 pymysql 驱动（pip install pymysql）"
            conn = pymysql.connect(
                host=cfg.get("host") or "localhost",
                port=int(cfg.get("port") or 3306),
                user=cfg.get("user") or "",
                password=cfg.get("password") or "",
                database=cfg.get("database") or "",
                charset="utf8mb4",
                connect_timeout=5,
            )
            return conn, conn.cursor(), None
        if engine == "postgres":
            try:
                import psycopg2
            except ImportError:
                return None, None, "未安装 psycopg2 驱动（pip install psycopg2-binary）"
            conn = psycopg2.connect(
                host=cfg.get("host") or "localhost",
                port=int(cfg.get("port") or 5432),
                user=cfg.get("user") or "",
                password=cfg.get("password") or "",
                dbname=cfg.get("database") or "",
                connect_timeout=5,
            )
            return conn, conn.cursor(), None
        return None, None, f"不支持的数据库引擎：{engine}"
    except Exception as e:
        return None, None, f"连接失败：{e}"


def _kb_list_tables(cursor, engine: str) -> list[str]:
    """列出数据库中的表（最多 50 张）。"""
    try:
        if engine == "sqlite":
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        elif engine == "mysql":
            cursor.execute("SHOW TABLES")
        else:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() ORDER BY table_name"
            )
        return [r[0] for r in cursor.fetchall()][:50]
    except Exception:
        return []


@app.get("/api/knowledge-bases")
async def list_knowledge_bases(current_user: dict = require_auth()):  # noqa: C901
    """获取所有知识库（连接配置脱敏；file/db 类型附文档统计）"""
    conn = get_db()
    kbs = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for kb in kbs:
        d = dict(kb)
        try:
            cfg = json.loads(d.get("config") or "{}") or {}
        except (ValueError, TypeError):
            cfg = {}
        d["config"] = _mask_kb_config(cfg)
        kb_type = d.get("type") or "file"
        doc_count, total_size = 0, 0
        if kb_type == "file" and d.get("path"):
            p = d["path"]
            if os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for fn in files:
                        try:
                            total_size += os.path.getsize(os.path.join(root, fn))
                            doc_count += 1
                        except OSError:
                            pass
            elif os.path.isfile(p):
                try:
                    total_size = os.path.getsize(p)
                    doc_count = 1
                except OSError:
                    pass
        elif kb_type == "db":
            db_conn, cursor, _err = _kb_connect(cfg)
            if db_conn:
                try:
                    table = (cfg.get("table") or "").strip()
                    if table:
                        cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                        row = cursor.fetchone()
                        doc_count = row[0] if row else 0
                except Exception:
                    pass
                finally:
                    db_conn.close()
        d["doc_count"] = doc_count
        d["total_size"] = total_size
        result.append(d)
    return result


@app.post("/api/knowledge-bases")
async def create_knowledge_base(req: KnowledgeBaseCreateRequest, current_user: dict = require_auth()):
    """创建知识库（file / url / db；db 类型需提供 config 连接配置）"""
    conn = get_db()
    kb_id = f"kb_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO knowledge_bases (id, name, type, path, url, filter, top_k, description, subtype, config, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            kb_id,
            req.name,
            req.type or req.source_type or "file",
            req.path or req.source_path or "",
            req.url,
            json.dumps(req.filter),
            req.top_k,
            req.description or "",
            req.subtype or "general",
            json.dumps(req.config or {}),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": kb_id, "name": req.name}


@app.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str, current_user: dict = require_auth()):
    """删除知识库"""
    conn = get_db()
    conn.execute("DELETE FROM knowledge_bases WHERE id=?", (kb_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.put("/api/knowledge-bases/{kb_id}")
async def update_knowledge_base(kb_id: str, req: KnowledgeBaseUpdateRequest, current_user: dict = require_auth()):
    """更新知识库（config 传 None = 不变；传 {} = 清空）"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    # type 和 source_type 都映射到数据库的 type 列
    db_type = req.type or req.source_type
    if db_type is not None:
        updates.append("type=?")
        vals.append(db_type)
    # path 和 source_path 都映射到数据库的 path 列
    db_path = req.path or req.source_path
    if db_path is not None:
        updates.append("path=?")
        vals.append(db_path)
    if req.url is not None:
        updates.append("url=?")
        vals.append(req.url)
    if req.top_k is not None:
        updates.append("top_k=?")
        vals.append(req.top_k)
    if req.description is not None:
        updates.append("description=?")
        vals.append(req.description)
    if req.subtype is not None:
        updates.append("subtype=?")
        vals.append(req.subtype)
    if req.config is not None:
        updates.append("config=?")
        vals.append(json.dumps(req.config))
    if not updates:
        raise HTTPException(400, "无更新字段")
    updates.append("created_at=created_at")
    vals.append(kb_id)
    conn.execute(f"UPDATE knowledge_bases SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": kb_id}


@app.post("/api/knowledge-bases/test-connection")
async def test_kb_connection(req: dict, current_user: dict = require_auth()):
    """测试知识库连接（无需先保存）：file 检查路径；url 检查可达性；db 测试连接并列出表。"""
    kb_type = (req.get("type") or "file").strip()
    cfg = req.get("config") or {}
    if kb_type == "file":
        p = (req.get("path") or "").strip()
        if not p:
            return {"ok": False, "error": "未配置文件路径"}
        if not os.path.exists(p):
            return {"ok": False, "error": f"路径不存在：{p}"}
        if os.path.isdir(p):
            count = sum(len(files) for _, _, files in os.walk(p))
            return {"ok": True, "detail": f"目录存在，共 {count} 个文件", "doc_count": count}
        return {"ok": True, "detail": f"文件存在（{os.path.getsize(p)} 字节）", "doc_count": 1}
    if kb_type == "url":
        url = (req.get("url") or "").strip()
        if not url:
            return {"ok": False, "error": "未配置 URL"}
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            return {"ok": resp.status_code < 400, "detail": f"HTTP {resp.status_code}", "doc_count": 1}
        except Exception as e:
            return {"ok": False, "error": f"访问失败：{e}"}
    if kb_type == "db":
        db_conn, cursor, err = _kb_connect(cfg)
        if err:
            return {"ok": False, "error": err}
        try:
            tables = _kb_list_tables(cursor, (cfg.get("engine") or "sqlite").lower())
            return {"ok": True, "detail": f"连接成功，共 {len(tables)} 张表", "tables": tables}
        finally:
            db_conn.close()
    return {"ok": False, "error": f"不支持的类型：{kb_type}"}


@app.post("/api/knowledge-bases/{kb_id}/test")
async def test_knowledge_base(kb_id: str, current_user: dict = require_auth()):  # noqa: C901
    """测试知识库：file 检查路径；url 检查可达性；db 测试连接并列出表。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    kb_type = d.get("type") or "file"
    try:
        cfg = json.loads(d.get("config") or "{}") or {}
    except (ValueError, TypeError):
        cfg = {}
    if kb_type == "file":
        p = (d.get("path") or "").strip()
        if not p:
            return {"ok": False, "error": "未配置文件路径"}
        if not os.path.exists(p):
            return {"ok": False, "error": f"路径不存在：{p}"}
        if os.path.isdir(p):
            count = sum(len(files) for _, _, files in os.walk(p))
            return {"ok": True, "detail": f"目录存在，共 {count} 个文件", "doc_count": count}
        return {"ok": True, "detail": f"文件存在（{os.path.getsize(p)} 字节）", "doc_count": 1}
    if kb_type == "url":
        url = (d.get("url") or "").strip()
        if not url:
            return {"ok": False, "error": "未配置 URL"}
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            return {"ok": resp.status_code < 400, "detail": f"HTTP {resp.status_code}", "doc_count": 1}
        except Exception as e:
            return {"ok": False, "error": f"访问失败：{e}"}
    if kb_type == "db":
        db_conn, cursor, err = _kb_connect(cfg)
        if err:
            return {"ok": False, "error": err}
        try:
            tables = _kb_list_tables(cursor, (cfg.get("engine") or "sqlite").lower())
            return {"ok": True, "detail": f"连接成功，共 {len(tables)} 张表", "tables": tables}
        finally:
            db_conn.close()
    return {"ok": False, "error": f"不支持的类型：{kb_type}"}


@app.get("/api/knowledge-bases/{kb_id}/search")
async def _search_kb_internal(params: dict) -> dict:
    """内部搜索函数。"""
    return {}

async def _parse_search_request(kb_id: str, q: str, limit: int) -> dict:
    """解析搜索请求参数。"""
    return {
        "kb_id": kb_id,
        "query": q.strip()[:500],
        "limit": min(limit, 20),
        "offset": 0
    }

def _execute_vector_search(params: dict) -> list:
    """执行向量搜索。"""
    # 简化的搜索逻辑
    return []

def _format_search_response(results: list, total: int) -> dict:
    """格式化搜索结果。"""
    return {
        "results": results,
        "total": total,
        "limit": len(results)
    }

def search_knowledge_base(kb_id: str, q: str = "", limit: int = 5, current_user: dict = require_auth()):  # noqa: C901
    """在知识库中检索：db 按配置的表对文本列 LIKE 匹配；file 扫描目录内文本文件。"""
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "检索关键词不能为空")
    limit = max(1, min(limit or 5, 20))
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    kb_type = d.get("type") or "file"
    try:
        cfg = json.loads(d.get("config") or "{}") or {}
    except (ValueError, TypeError):
        cfg = {}
    if kb_type == "db":
        db_conn, cursor, err = _kb_connect(cfg)
        if err:
            raise HTTPException(400, "操作失败")
        try:
            engine = (cfg.get("engine") or "sqlite").lower()
            table = (cfg.get("table") or "").strip()
            if not table:
                tables = _kb_list_tables(cursor, engine)
                if not tables:
                    raise HTTPException(400, "数据库中无可用表，请在连接配置中选择表")
                table = tables[0]
            # 获取列
            if engine == "sqlite":
                cursor.execute(f'PRAGMA table_info("{table}")')
                cols = [r[1] for r in cursor.fetchall()]
            elif engine == "mysql":
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                cols = [r[0] for r in cursor.fetchall()]
            else:
                cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
                cols = [r[0] for r in cursor.fetchall()]
            text_cols = [c for c in cols if c and c.lower() not in ("id", "created_at", "updated_at")]
            if not text_cols:
                text_cols = cols
            place = "%s" if engine == "mysql" else "?"
            cond = " OR ".join(f'"{c}" LIKE {place}' for c in text_cols)
            cursor.execute(f'SELECT * FROM "{table}" WHERE {cond} LIMIT {place}', [f"%{q}%"] * len(text_cols) + [limit])
            rows = cursor.fetchall()
            hits = []
            for r in rows:
                item = {}
                for i, c in enumerate(cols):
                    if i < len(r):
                        v = r[i]
                        item[c] = str(v)[:300] if v is not None else ""
                hits.append(item)
            return {"ok": True, "hits": hits, "count": len(hits), "table": table}
        except Exception as e:
            raise HTTPException(400, "服务异常，请稍后重试") from e
        finally:
            try:
                db_conn.close()
            except Exception:
                pass
    if kb_type == "file":
        p = (d.get("path") or "").strip()
        if not p or not os.path.exists(p):
            raise HTTPException(400, "文件路径不存在")
        files = [p] if os.path.isfile(p) else []
        if not files:
            for root, _, fns in os.walk(p):
                for fn in fns:
                    if fn.lower().endswith((".txt", ".md", ".csv", ".log")):
                        files.append(os.path.join(root, fn))
        hits = []
        for fp in files:
            try:
                with open(fp, encoding="utf-8", errors="ignore") as f:
                    content = f.read(200000)
            except OSError:
                continue
            matched = [ln.strip() for ln in content.splitlines() if q.lower() in ln.lower()]
            if matched:
                hits.append(
                    {
                        "file": os.path.basename(fp),
                        "path": fp,
                        "matches": matched[:5],
                        "match_count": len(matched),
                    }
                )
            if len(hits) >= limit:
                break
        return {"ok": True, "hits": hits, "count": len(hits)}
    raise HTTPException(400, "该类型知识库暂不支持内容检索（db / file 支持）")


# ── 知识库文档管理（上传 / 列表 / 删除）─────────────────────
_KB_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "kb")
_KB_ALLOWED_EXT = {
    ".txt",
    ".md",
    ".csv",
    ".log",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}
_KB_MAX_UPLOAD = 20 * 1024 * 1024  # 20MB


def _safe_kb_filename(filename: str) -> str:
    """清洗上传文件名：去除路径与非法字符，保留可读名称。"""
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[^\w\u4e00-\u9fa5.\-]", "_", name)
    return name[:120] or f"doc_{int(time.time() * 1000)}"


@app.post("/api/knowledge-bases/upload")
async def upload_kb_document(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传知识库文档：保存到 uploads/kb/，返回可用于创建 file 类型知识库的路径。"""
    os.makedirs(_KB_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _KB_ALLOWED_EXT:
        raise HTTPException(
            400, f"不支持的文件类型：{ext or '(无扩展名)'}（支持 {', '.join(sorted(_KB_ALLOWED_EXT))}）"
        )
    content = await file.read()
    if len(content) > _KB_MAX_UPLOAD:
        raise HTTPException(400, "文件过大，单个文件不能超过 20MB")
    if not content:
        raise HTTPException(400, "文件内容为空")
    # 保留原始名 + 短随机前缀，避免重名覆盖
    safe_name = _safe_kb_filename(file.filename)
    stored = f"{int(time.time() * 1000)}_{safe_name}"
    dest = os.path.join(_KB_UPLOAD_DIR, stored)
    with open(dest, "wb") as f:
        f.write(content)
    return {
        "path": dest,
        "filename": safe_name,
        "size": len(content),
        "detail": f"已上传 {safe_name}（{len(content) / 1024:.1f} KB），可直接用于创建知识库",
    }


@app.get("/api/knowledge-bases/{kb_id}/documents")
async def list_kb_documents(kb_id: str, current_user: dict = require_auth()):  # noqa: C901
    """列出知识库文档：file 类型扫描目录/文件；db 类型返回表信息；url 返回空。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    kb_type = d.get("type") or "file"
    docs = []
    if kb_type == "file":
        p = (d.get("path") or "").strip()
        if p and os.path.isdir(p):
            for fn in sorted(os.listdir(p)):
                fp = os.path.join(p, fn)
                if os.path.isfile(fp):
                    try:
                        docs.append(
                            {
                                "name": fn,
                                "path": fp,
                                "size": os.path.getsize(fp),
                                "mtime": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                            }
                        )
                    except OSError:
                        continue
        elif p and os.path.isfile(p):
            try:
                docs.append(
                    {
                        "name": os.path.basename(p),
                        "path": p,
                        "size": os.path.getsize(p),
                        "mtime": datetime.fromtimestamp(os.path.getmtime(p)).isoformat(),
                    }
                )
            except OSError:
                pass
    elif kb_type == "db":
        try:
            cfg = json.loads(d.get("config") or "{}") or {}
            db_conn, cursor, err = _kb_connect(cfg)
            if db_conn and not err:
                try:
                    tables = _kb_list_tables(cursor, (cfg.get("engine") or "sqlite").lower())
                    docs = [{"name": t, "path": t, "size": 0, "mtime": "", "is_table": True} for t in tables]
                finally:
                    db_conn.close()
        except Exception:
            pass
    return {"type": kb_type, "docs": docs, "count": len(docs)}


@app.delete("/api/knowledge-bases/{kb_id}/documents")
async def delete_kb_document(kb_id: str, filename: str = "", current_user: dict = require_auth()):
    """删除知识库中的文档（仅限该知识库路径下的文件，防目录穿越）。"""
    if not filename:
        raise HTTPException(400, "请指定要删除的文件名")
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    if (d.get("type") or "file") != "file":
        raise HTTPException(400, "仅 file 类型知识库支持删除文档")
    base = (d.get("path") or "").strip()
    if not base or not os.path.isdir(base):
        raise HTTPException(400, "知识库目录不存在")
    target = os.path.realpath(os.path.join(base, os.path.basename(filename)))
    base_real = os.path.realpath(base)
    if not target.startswith(base_real + os.sep):
        raise HTTPException(400, "文件名不合法")
    if not os.path.isfile(target):
        raise HTTPException(404, "文件不存在")
    os.remove(target)
    return {"success": True, "filename": os.path.basename(target)}


# ── MCP Servers 管理 ───────────────────────────────────────────
def _mask_auth_config(auth_type: str, cfg: dict) -> dict:
    """脱敏认证配置（列表/详情返回，不泄露密钥）。"""
    cfg = cfg or {}
    if auth_type == "bearer" and cfg.get("token"):
        t = cfg["token"]
        return {"token": (t[:6] + "••••••" + t[-4:]) if len(t) > 12 else "••••••••"}
    if auth_type == "basic" and cfg.get("username"):
        return {"username": cfg["username"], "password": "••••••"}
    if auth_type == "api_key" and cfg.get("key"):
        k = cfg["key"]
        return {
            "header_name": cfg.get("header_name") or "X-API-Key",
            "key": (k[:6] + "••••••" + k[-4:]) if len(k) > 12 else "••••••••",
        }
    return dict(cfg)


def _mcp_auth_headers(auth_type: str, cfg: dict) -> dict:
    """根据认证配置生成请求头（供测试连接 / 未来调用使用）。"""
    cfg = cfg or {}
    if auth_type == "bearer" and cfg.get("token"):
        return {"Authorization": f"Bearer {cfg['token']}"}
    if auth_type == "basic" and cfg.get("username"):
        raw = f"{cfg['username']}:{cfg.get('password', '')}"
        return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}
    if auth_type == "api_key" and cfg.get("key"):
        return {cfg.get("header_name") or "X-API-Key": cfg["key"]}
    return {}


def _parse_mcp_response(text: str):
    """解析 MCP 响应：兼容纯 JSON 与 SSE（data: {...} 行）。"""
    try:
        return json.loads(text)
    except ValueError:
        pass
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:") and line[5:].strip():
            try:
                return json.loads(line[5:].strip())
            except ValueError:
                continue
    return None


@app.get("/api/mcp-servers")
async def list_mcp_servers(current_user: dict = require_auth()):
    """获取所有 MCP Servers（认证配置脱敏）"""
    conn = get_db()
    servers = conn.execute("SELECT * FROM mcp_servers ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for s in servers:
        d = dict(s)
        d["status"] = "active" if d.get("enabled") else "inactive"
        d["transport"] = d.get("transport_type") or "stdio"
        try:
            auth_cfg = json.loads(d.get("auth_config") or "{}") or {}
        except (ValueError, TypeError):
            auth_cfg = {}
        d["auth_config"] = _mask_auth_config(d.get("auth_type") or "none", auth_cfg)
        result.append(d)
    return result


@app.post("/api/mcp-servers")
async def create_mcp_server(req: MCPServerCreateRequest, current_user: dict = require_auth()):
    """创建 MCP Server（支持认证配置：none/bearer/basic/api_key）"""
    conn = get_db()
    server_id = f"mcp_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO mcp_servers (id, name, transport_type, command, args, env, url, auth_type, auth_config, enabled, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            server_id,
            req.name,
            req.transport_type,
            req.command,
            json.dumps(req.args),
            json.dumps(req.env),
            req.url,
            req.auth_type or "none",
            json.dumps(req.auth_config or {}),
            1 if req.enabled else 0,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": server_id, "name": req.name}


@app.put("/api/mcp-servers/{server_id}")
async def update_mcp_server(server_id: str, req: MCPServerUpdateRequest, current_user: dict = require_auth()):  # noqa: C901
    """更新 MCP Server（auth_config 传空字典 = 清空认证）"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    if req.command is not None:
        updates.append("command=?")
        vals.append(req.command)
    if req.url is not None:
        updates.append("url=?")
        vals.append(req.url)
    if req.env is not None:
        updates.append("env=?")
        vals.append(json.dumps(req.env))
    if req.transport is not None or req.transport_type is not None:
        updates.append("transport_type=?")
        vals.append(req.transport_type or req.transport)
    if req.args is not None:
        updates.append("args=?")
        vals.append(json.dumps(req.args))
    if req.auth_type is not None:
        updates.append("auth_type=?")
        vals.append(req.auth_type)
    if req.auth_config is not None:
        updates.append("auth_config=?")
        vals.append(json.dumps(req.auth_config))
    if req.enabled is not None:
        updates.append("enabled=?")
        vals.append(1 if req.enabled else 0)
    if not updates:
        raise HTTPException(400, "无更新字段")
    vals.append(server_id)
    conn.execute(f"UPDATE mcp_servers SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": server_id}


@app.post("/api/mcp-servers/{server_id}/toggle")
async def toggle_mcp_server(server_id: str, current_user: dict = require_auth()):
    """切换 MCP Server 启用状态"""
    conn = get_db()
    row = conn.execute("SELECT enabled FROM mcp_servers WHERE id=?", (server_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "MCP 服务器不存在")
    new_val = 0 if row["enabled"] else 1
    conn.execute("UPDATE mcp_servers SET enabled=? WHERE id=?", (new_val, server_id))
    conn.commit()
    conn.close()
    return {"success": True, "enabled": bool(new_val), "status": "active" if new_val else "inactive"}


@app.delete("/api/mcp-servers/{server_id}")
async def delete_mcp_server(server_id: str, current_user: dict = require_auth()):
    """删除 MCP Server"""
    conn = get_db()
    conn.execute("DELETE FROM mcp_servers WHERE id=?", (server_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/mcp-servers/{server_id}/test")
async def test_mcp_server(server_id: str, current_user: dict = require_auth()):  # noqa: C901
    """测试 MCP 连接：stdio 检查命令可执行；SSE/HTTP 执行 JSON-RPC initialize 握手（自动注入认证头）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM mcp_servers WHERE id=?", (server_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "MCP 服务器不存在")
    d = dict(row)
    transport = d.get("transport_type") or "stdio"
    try:
        auth_cfg = json.loads(d.get("auth_config") or "{}") or {}
    except (ValueError, TypeError):
        auth_cfg = {}
    headers = _mcp_auth_headers(d.get("auth_type") or "none", auth_cfg)

    if transport == "stdio":
        cmd = (d.get("command") or "").strip()
        if not cmd:
            return {"ok": False, "error": "未配置启动命令"}
        prog = cmd.split()[0]
        if not (shutil.which(prog) or os.path.exists(prog)):
            return {"ok": False, "error": f"找不到可执行命令：{prog}"}
        # 真实连接测试：启动进程 → JSON-RPC initialize 握手 → tools/list
        # （放线程池执行，避免同步子进程 I/O 阻塞事件循环）
        try:
            args = json.loads(d.get("args") or "[]") or []
            env = {**os.environ, **(json.loads(d.get("env") or "{}") or {})}
        except (ValueError, TypeError):
            args, env = [], {**os.environ}
        return await asyncio.to_thread(_mcp_stdio_test, cmd, args, env)

    url = (d.get("url") or "").strip()
    if not url:
        return {"ok": False, "error": "未配置 URL"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xiaotuan", "version": "1.0"},
                },
            }
            resp = await client.post(
                url,
                json=init_payload,
                headers={
                    **headers,
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code >= 400:
                return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            data = _parse_mcp_response(resp.text)
            if not data or "result" not in data:
                return {"ok": True, "detail": "服务响应正常（未识别到 JSON-RPC 结果）", "tools": []}
            server_info = data.get("result", {}).get("serverInfo", {}) or {}
            # 获取工具列表
            tools = []
            try:
                resp2 = await client.post(
                    url,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                    headers={
                        **headers,
                        "Accept": "application/json, text/event-stream",
                        "Content-Type": "application/json",
                    },
                )
                data2 = _parse_mcp_response(resp2.text)
                tools = [t.get("name", "?") for t in (data2.get("result", {}).get("tools", []) if data2 else [])]
            except Exception:
                pass
            name = server_info.get("name", "")
            return {"ok": True, "detail": f"initialize 握手成功（{name or 'MCP 服务'}）", "tools": tools}
    except Exception as e:
        return {"ok": False, "error": f"连接失败：{e}"}


def _mcp_stdio_test(cmd: str, args: list, env: dict) -> dict:  # noqa: C901
    """MCP stdio 真实连接测试：启动子进程 → initialize 握手 → tools/list。

    一次性写入 initialize / initialized / tools/list 三个 JSON-RPC 请求（
    服务器按序处理），从 stdout 解析 id=1 与 id=2 的响应；stderr 用于报错诊断。
    15s 超时兜底，进程始终清理，绝不残留。
    """
    import subprocess

    proc = None
    try:
        proc = subprocess.Popen(
            [cmd, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        reqs = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "xiaotuan", "version": "1.0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        payload = "".join(json.dumps(r) + "\n" for r in reqs)
        out, err = proc.communicate(input=payload, timeout=15)
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
        return {"ok": False, "error": "连接超时（服务器 15s 无响应）"}
    except Exception as e:
        return {"ok": False, "error": f"启动失败：{e}"}
    finally:
        if proc and proc.poll() is None:
            proc.kill()
    init_data = tools_data = None
    for line in (out or "").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("id") == 1:
            init_data = d
        elif d.get("id") == 2:
            tools_data = d
    if not init_data or "result" not in init_data:
        detail = (err or out or "无输出")[:200]
        return {"ok": False, "error": f"未收到 initialize 响应：{detail}"}
    tools = [t.get("name", "?") for t in (tools_data or {}).get("result", {}).get("tools", [])] or []
    name = init_data.get("result", {}).get("serverInfo", {}).get("name", "") or "MCP 服务"
    return {"ok": True, "detail": f"initialize 握手成功（{name}），发现 {len(tools)} 个工具", "tools": tools}


# ── 沙箱管理 ───────────────────────────────────────────────────
@app.get("/api/sandbox/images")
async def sandbox_list_images(current_user: dict = require_auth()):
    """列出沙箱镜像"""
    from sandbox import process_manager

    return {"images": process_manager.list_images()}


@app.post("/api/sandbox/images/pull")
async def sandbox_pull_image(req: SandboxPullImageRequest, current_user: dict = require_auth()):
    """拉取镜像"""
    from sandbox import process_manager

    return process_manager.pull_image(req.image)


@app.get("/api/sandbox/services")
async def sandbox_services(current_user: dict = require_auth()):
    """获取预置服务模板"""
    from sandbox import SERVICE_TEMPLATES

    # 转 list 返回并补充 id（前端以 id 作 React key）
    return {"services": [{**v, "id": k} for k, v in SERVICE_TEMPLATES.items()]}


# Redis 控制台安全白名单：仅允许数据操作命令，禁止 FLUSHALL/FLUSHDB/SHUTDOWN/CONFIG/EVAL 等危险命令
REDIS_SAFE_COMMANDS = {
    "PING", "ECHO", "DBSIZE", "KEYS", "EXISTS", "TYPE", "TTL", "PTTL", "GET", "MGET", "SET", "MSET",
    "APPEND", "DEL", "EXPIRE", "PERSIST", "RENAME", "INCR", "DECR", "INCRBY", "DECRBY",
    "HSET", "HGET", "HDEL", "HGETALL", "HLEN", "HEXISTS",
    "LPUSH", "RPUSH", "LPOP", "RPOP", "LRANGE", "LLEN",
    "SADD", "SREM", "SMEMBERS", "SCARD", "SISMEMBER",
    "ZADD", "ZREM", "ZRANGE", "ZCARD", "ZSCORE",
    "GETRANGE", "SETEX", "STRLEN", "OBJECT",
}


def _sandbox_project_env(project_id: str) -> dict:
    """读取沙箱项目创建配置中的环境变量（服务控制台凭据：MYSQL_ROOT_PASSWORD 等）"""
    conn = get_db()
    row = conn.execute(
        "SELECT image, config FROM sandbox_projects WHERE id=?", (project_id,)
    ).fetchone()
    conn.close()
    env_map = {}
    if row:
        try:
            cfg = json.loads(row["config"] or "{}")
            for e in (cfg.get("env") or []):
                if isinstance(e, str) and "=" in e:
                    k, _, v = e.partition("=")
                    env_map[k.strip()] = v.strip()
        except Exception:
            pass
    return env_map


@app.post("/api/sandbox/projects/{project_id}/redis/command")
def sandbox_redis_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """Redis 控制台：在项目容器内执行 redis-cli 安全命令（查看/修改/删除 Key）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    verb = cmd.split()[0].upper()
    if verb not in REDIS_SAFE_COMMANDS:
        raise HTTPException(400, "命令不在安全白名单内")
    # 命令按空白拆分为 argv，避免注入（redis-cli 接收参数数组，无 shell 解释）
    result = process_manager.exec_command(project_id, ["redis-cli", *cmd.split()], timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


# SQL 控制台白名单：仅允许只读查询（沙箱内数据浏览，禁止写操作）
SQL_SAFE_VERBS = {"SELECT", "SHOW", "DESC", "DESCRIBE", "EXPLAIN"}


@app.post("/api/sandbox/projects/{project_id}/sql/query")
def sandbox_sql_query(project_id: str, req: SandboxSqlQueryRequest, current_user: dict = require_auth()):
    """SQL 控制台：在项目容器内执行只读查询（MySQL/PostgreSQL），返回结构化表格"""
    from sandbox import process_manager

    sql = req.sql.strip().rstrip(";")
    if not sql:
        raise HTTPException(400, "SQL 不能为空")
    verb = sql.split()[0].upper()
    if verb not in SQL_SAFE_VERBS:
        raise HTTPException(400, "仅支持只读查询，禁止写操作")
    if ";" in sql:
        raise HTTPException(400, "一次只能执行一条 SQL")

    # 从项目镜像与创建配置（env）确定数据库客户端与凭据：
    # 沙箱项目创建时可自定义密码（如 MYSQL_ROOT_PASSWORD），不可硬编码默认值
    conn = get_db()
    row = conn.execute(
        "SELECT image FROM sandbox_projects WHERE id=?", (project_id,)
    ).fetchone()
    conn.close()
    image = (row["image"] if row else "") or ""
    image_l = image.lower()
    env_map = _sandbox_project_env(project_id)
    if "mysql" in image_l:
        pwd = env_map.get("MYSQL_ROOT_PASSWORD", "password")
        # 不加 -N：非交互 -e 模式自带表头（tab 分隔），解析器以首行为列名；-N 会吞掉首行数据
        argv = ["mysql", "-uroot", f"-p{pwd}", "--default-character-set=utf8mb4", "-e", sql]
    elif "postgres" in image_l or "postgresql" in image_l:
        # 密码经连接串传递（容器内 stdin 为 /dev/null，无法交互输入，PGPASSWORD 需 -e 注入）
        pwd = env_map.get("POSTGRES_PASSWORD", "password")
        user = env_map.get("POSTGRES_USER", "postgres")
        db = env_map.get("POSTGRES_DB", "sandbox")
        # -A 禁用对齐装饰、-F 指定 tab 分隔；保留表头（不用 -t），与 mysql 行为对齐，解析器以首行为列名
        argv = ["psql", f"postgresql://{user}:{pwd}@localhost/{db}", "-A", "-F", "\t", "-c", sql]
    else:
        raise HTTPException(400, "该项目不是 MySQL/PostgreSQL 数据库服务，无法执行 SQL")

    result = process_manager.exec_command(project_id, argv, timeout=30)
    if result["status"] != "success":
        # 过滤 mysql 客户端的“命令行密码不安全”警告行，保留真实错误
        err_lines = [ln for ln in result["message"].split("\n") if "Using a password on the command line" not in ln]
        raise HTTPException(500, "\n".join(err_lines).strip() or "SQL 执行失败")
    raw = result["output"].rstrip("\n")
    # 过滤 mysql 客户端的“命令行密码不安全”警告行（成功时也可能出现在 stderr 合并输出中）
    raw = "\n".join(ln for ln in raw.split("\n") if "Using a password on the command line" not in ln)
    # 解析 tab 分隔输出为结构化表格（首行表头）
    columns: list[str] = []
    rows: list[list] = []
    if raw.strip():
        lines = raw.split("\n")
        columns = [c for c in lines[0].split("\t") if c != ""]
        rows = [
            [c for c in line.split("\t")]
            for line in lines[1:]
            if line.strip() and line.strip() != "(0 rows)"
        ]
    return {"ok": True, "sql": sql, "columns": columns, "rows": rows, "raw": raw}


# MongoDB 控制台：mongosh 只读白名单（正则匹配允许模式 + 全局禁词双重拦截）
MONGO_SAFE_PATTERNS = [
    re.compile(r"^(show|use)\s+(dbs|databases|collections|tables|[a-zA-Z0-9_\-]+)$"),
    re.compile(r"^db\.\w+\.(find|findOne|count|countDocuments|distinct|listIndexes)\(.*\)$"),
    re.compile(r"^db\.(stats|getName|getCollectionNames|getCollectionInfos)\(.*\)$"),
    re.compile(r"^db\.\w+\.getIndexes\(\)$"),
]
# 写操作/危险操作禁词（大小写不敏感，命中即拒绝）
MONGO_BLOCKED = [
    "insert", "update", "delete", "remove", "drop", "create", "rename", "aggregate",
    "eval(", "runcommand", "admincommand", "$out", "$merge", "copytodatabase",
]


@app.post("/api/sandbox/projects/{project_id}/mongo/command")
def sandbox_mongo_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """MongoDB 控制台：在项目容器内执行 mongosh 只读命令（show dbs / db.collection.find 等）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    cmd_l = cmd.lower()
    if any(b in cmd_l for b in MONGO_BLOCKED):
        raise HTTPException(400, "仅支持只读操作（禁止 insert/update/delete/drop/create/aggregate 等）")
    if not any(p.match(cmd) for p in MONGO_SAFE_PATTERNS):
        raise HTTPException(400, "命令格式不在允许范围（支持 show dbs / use db / db.集合.find(...) / db.stats() 等只读操作）")

    # 凭据从项目创建配置读取（模板默认 admin/password）
    env_map = _sandbox_project_env(project_id)
    user = env_map.get("MONGO_INITDB_ROOT_USERNAME", "admin")
    pwd = env_map.get("MONGO_INITDB_ROOT_PASSWORD", "password")
    argv = ["mongosh", "--quiet", "-u", user, "-p", pwd, "--authenticationDatabase", "admin", "--eval", cmd]
    result = process_manager.exec_command(project_id, argv, timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


# RabbitMQ 控制台：rabbitmqctl 只读白名单（状态/列表类命令）
RABBITMQ_SAFE_VERBS = {
    "status", "ping", "list_queues", "list_exchanges", "list_bindings", "list_connections",
    "list_channels", "list_users", "list_permissions", "list_vhosts", "list_policies", "list_consumers",
}
RABBITMQ_FIELD_RE = re.compile(r"^[a-zA-Z0-9_ ]*$")


@app.post("/api/sandbox/projects/{project_id}/rabbitmq/command")
def sandbox_rabbitmq_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """RabbitMQ 控制台：在项目容器内执行 rabbitmqctl 只读命令（status / list_queues 等）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    parts = cmd.split()
    verb = parts[0]
    if verb not in RABBITMQ_SAFE_VERBS:
        raise HTTPException(400, "命令不在安全白名单内")
    # 参数仅允许字段名（如 name messages），防止注入
    if len(parts) > 1 and not RABBITMQ_FIELD_RE.match(" ".join(parts[1:])):
        raise HTTPException(400, "参数格式不合法")
    result = process_manager.exec_command(project_id, ["rabbitmqctl", *parts], timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


# Nginx 控制台：只读参数白名单（版本/配置测试/配置转储）
NGINX_SAFE_ARGS = {"-v", "-V", "-t", "-T"}


@app.post("/api/sandbox/projects/{project_id}/nginx/command")
def sandbox_nginx_command(project_id: str, req: SandboxRedisCommandRequest, current_user: dict = require_auth()):
    """Nginx 控制台：在项目容器内执行 nginx 只读命令（-v 版本 / -t 配置测试 / -T 配置转储）"""
    from sandbox import process_manager

    cmd = req.command.strip()
    if not cmd:
        raise HTTPException(400, "命令不能为空")
    args = cmd.split()
    if args[0] != "nginx" or len(args) != 2 or args[1] not in NGINX_SAFE_ARGS:
        raise HTTPException(400, "仅支持 nginx -v / nginx -V / nginx -t / nginx -T 只读命令")
    result = process_manager.exec_command(project_id, ["nginx", args[1]], timeout=30)
    if result["status"] != "success":
        raise HTTPException(500, _safe_error(result["message"]))
    return {"ok": True, "command": cmd, "output": result["output"].rstrip("\n")}


@app.get("/api/sandbox/projects")
async def sandbox_list_projects(current_user: dict = require_auth()):
    """列出沙箱项目"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM sandbox_projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/sandbox/projects")
async def sandbox_create_project(req: SandboxProjectCreateRequest, current_user: dict = require_auth()):
    """创建沙箱项目"""
    from sandbox import process_manager

    project_id = f"proj_{int(time.time() * 1000)}"
    # 前端可能传字符串或列表，统一转为列表
    raw_ports = req.ports
    if isinstance(raw_ports, str):
        ports = [p.strip() for p in raw_ports.split(",") if p.strip()]
    else:
        ports = raw_ports or []
    raw_env = req.env
    if isinstance(raw_env, str):
        env = [e.strip() for e in raw_env.split(",") if e.strip()]
    else:
        env = raw_env or []
    config = {
        "image": req.image,
        "ports": ports,
        "env": env,
        "command": req.command,
    }
    result = process_manager.create_container(project_id, config)
    conn = get_db()
    conn.execute(
        """INSERT INTO sandbox_projects (id, name, image, status, ports, config, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            req.name,
            config["image"],
            result.get("status", "created"),
            json.dumps(config.get("ports", [])),
            json.dumps(config),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": project_id, **result}


@app.get("/api/sandbox/projects/{project_id}")
async def sandbox_get_project(project_id: str, current_user: dict = require_auth()):
    """获取沙箱项目状态"""
    from sandbox import process_manager

    status = process_manager.get_status(project_id)
    return {"id": project_id, "status": status or {"state": "unknown"}}


@app.post("/api/sandbox/projects/{project_id}/start")
def sandbox_start_project(project_id: str, current_user: dict = require_auth()):
    """启动沙箱项目"""
    # deploy 部署的容器由 CI/CD 创建（容器名 sandbox-{name}，记录 id 为 deploy-{name}），走真实容器管理
    if project_id.startswith("deploy-"):
        import subprocess
        from datetime import datetime

        container = f"sandbox-{project_id[len('deploy-') :]}"
        r = subprocess.run(["podman", "start", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        if r.returncode != 0:
            return {"status": "error", "message": (r.stderr or "").strip() or f"容器 {container} 不存在"}
        conn = get_db()
        conn.execute(
            "UPDATE sandbox_projects SET status='running', updated_at=? WHERE id=?",
            (datetime.now().isoformat(), project_id),
        )
        conn.commit()
        conn.close()
        return {"status": "success", "container": container}
    from sandbox import process_manager

    return process_manager.start_container(project_id)


@app.post("/api/sandbox/projects/{project_id}/stop")
def sandbox_stop_project(project_id: str, current_user: dict = require_auth()):
    """停止沙箱项目"""
    # deploy 部署的容器由 CI/CD 创建（容器名 sandbox-{name}，记录 id 为 deploy-{name}），走真实容器管理
    if project_id.startswith("deploy-"):
        import subprocess
        from datetime import datetime

        container = f"sandbox-{project_id[len('deploy-') :]}"
        r = subprocess.run(["podman", "stop", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        if r.returncode != 0:
            return {"status": "error", "message": (r.stderr or "").strip() or f"容器 {container} 不存在"}
        conn = get_db()
        conn.execute(
            "UPDATE sandbox_projects SET status='stopped', updated_at=? WHERE id=?",
            (datetime.now().isoformat(), project_id),
        )
        conn.commit()
        conn.close()
        return {"status": "success", "container": container}
    from sandbox import process_manager

    return process_manager.stop_container(project_id)


@app.delete("/api/sandbox/projects/{project_id}")
def sandbox_delete_project(project_id: str, current_user: dict = require_auth()):
    """删除沙箱项目"""
    # deploy 部署的容器由 CI/CD 创建（容器名 sandbox-{name}，记录 id 为 deploy-{name}），走真实容器管理
    if project_id.startswith("deploy-"):
        import subprocess

        container = f"sandbox-{project_id[len('deploy-') :]}"
        subprocess.run(["podman", "stop", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        subprocess.run(["podman", "rm", container], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
        conn = get_db()
        conn.execute("DELETE FROM sandbox_projects WHERE id=?", (project_id,))
        conn.commit()
        conn.close()
        return {"status": "success", "container": container}
    from sandbox import process_manager

    result = process_manager.remove_container(project_id)
    conn = get_db()
    conn.execute("DELETE FROM sandbox_projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()
    return result


@app.get("/api/sandbox/projects/{project_id}/logs")
def sandbox_project_logs(project_id: str, tail: int = 200, current_user: dict = require_auth()):
    """获取沙箱项目/部署容器日志（tail 默认 200 行）"""
    import subprocess as _sp

    if project_id.startswith("deploy-"):
        container = f"sandbox-{project_id[len('deploy-') :]}"
        r = _sp.run(["podman", "logs", "--tail", str(tail), container], capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            return {"logs": [], "message": (r.stderr or "").strip() or f"容器 {container} 不存在或未启动"}
        lines = r.stdout.splitlines()
        return {"logs": lines, "container": container}
    from sandbox import process_manager

    logs = process_manager.get_logs(project_id, tail=tail)
    return {"logs": logs, "container": f"sandbox-{project_id}"}


# ── 代码沙箱静态检查（AI 代码解释器安全）──────────────────────
# 策略与实现见 common/sandbox_check.py（黑名单/白名单/受限执行器，
# 供代码解释器与数据分析沙箱共用）。


@app.get("/api/sandbox/info")
def sandbox_info(current_user: dict = require_auth()):
    """沙箱环境说明：白名单库 / 禁用操作 / 资源上限（v15，前端提示卡片数据源）。"""
    from common import sandbox_check as sc

    return {
        "allowed_imports": sorted(sc.ALLOWED_IMPORTS),
        "blocked_tokens": sc.BLOCKED_TOKENS,
        "limits": {
            "code_max_len": sc.MAX_CODE_LEN,
            "output_max_len": sc.MAX_OUTPUT_LEN,
            "timeout_sec": sc.DEFAULT_TIMEOUT,
            "cpu_sec": 10,
            "file_max_bytes": 2 * 1024 * 1024,
        },
    }


@app.post("/api/sandbox/execute")
def sandbox_execute_code(req: dict, current_user: dict = require_auth()):
    """AI 代码解释器：安全子进程执行 Python 代码。

    安全措施：
    - 静态扫描：禁止 os/subprocess/socket/open/eval/importlib 等危险操作，import 白名单
    - 资源限制：CPU 10s / 单文件 2MB / 文件描述符 128（子进程 preexec_fn；
      macOS 不支持 AS/DATA 内存限制，内存保护靠静态扫描+超时兜底）
    - 隔离环境：独立临时工作目录，清空 HOME/TMPDIR，忽略 PYTHON* 环境变量
    - 超时 30s + 输出截断 20KB
    """
    code = (req.get("code") or "").strip()
    language = (req.get("language") or "python").lower()
    if not code:
        raise HTTPException(400, "代码不能为空")
    if len(code) > MAX_CODE_LEN:
        raise HTTPException(400, "代码过长（上限 20KB）")
    if language not in ("python", "python3", "py"):
        raise HTTPException(400, "仅支持 Python 语言")

    # ── 静态安全检查 ──
    blocked = check_sandbox_code(code)
    if blocked:
        return {"output": "", "error": blocked, "duration": 0.0, "exit_code": -1}

    result = run_sandbox_python(code)
    output = result["output"]
    # 沙箱自动收集工作目录内落盘的 PNG（如 plt.savefig 输出），统一转 [IMAGE] 标记供前端渲染
    for _name, b64 in result.get("files", {}).items():
        output += f"\n[IMAGE]{b64}[/IMAGE]"
    return {
        "output": output,
        "error": result["error"],
        "duration": result["duration"],
        "exit_code": result["exit_code"],
    }


app.include_router(ai_video_router)
app.include_router(image_factory_router)
app.include_router(video_factory_router)
app.include_router(video_templates_router)
app.include_router(music_factory_router)
app.include_router(miniapp_router)
app.include_router(publishing_router)
app.include_router(game_factory_router)
app.include_router(growth_engine_router)
app.include_router(voice_factory_router)
app.include_router(voice_templates_router)
app.include_router(meme_factory_router)
app.include_router(meme_templates_router)
app.include_router(drafts_router)
app.include_router(gallery_router)
app.include_router(templates_market_router)
app.include_router(template_store_router)
app.include_router(prd_engine_router)
app.include_router(chat_engine_router)
app.include_router(sessions_router)
app.include_router(stripe_router)
app.include_router(collab_engine_router)
app.include_router(content_strategy_router)
app.include_router(digital_human_router)
app.include_router(drama_router)
app.include_router(drama_templates_router)
app.include_router(music_scene_templates_router)
app.include_router(task_queue_router)
app.include_router(smart_dashboard_router)
app.include_router(pdf_tools_router)
app.include_router(pdf_doc_templates_router)
app.include_router(competitor_monitor_router)
app.include_router(seo_analyzer_router)
app.include_router(realtime_router)
app.include_router(extensions_agents_router)

# v9.3: 5大高科技功能
app.include_router(voice_chat_router)
app.include_router(video_analyzer_router)
app.include_router(mindmap_router)
app.include_router(mindmap_templates_router)
app.include_router(data_forecast_router)
app.include_router(doc_qa_router)
app.include_router(web_search_router)
app.include_router(batch_api_router)
app.include_router(favorites_api_router)
app.include_router(apikey_api_router)
app.include_router(search_api_router)
app.include_router(scheduler_router)
app.include_router(openai_gateway_router)
app.include_router(dh_gateway_router)
app.include_router(backup_router)
app.include_router(oauth_router)
app.include_router(team_router)
app.include_router(feedback_router)
app.include_router(notify_api_router)

# v9.0: Platform API
from platform_api import router as platform_api_router  # noqa: E402

app.include_router(platform_api_router)

# v9.0: Extended API (Phase 2-4 + Office)
from extended_api import router as extended_api_router  # noqa: E402

app.include_router(extended_api_router)

# v9.0: Tool Hub API
from tool_hub import router as tool_hub_router  # noqa: E402

app.include_router(tool_hub_router)

# v9.0: AI 数据分析沙箱
from data_analyzer import router as data_analyzer_router  # noqa: E402

app.include_router(data_analyzer_router)

# v9.0: Stock Tools API
from stock_tools import router as stock_tools_router  # noqa: E402

app.include_router(stock_tools_router)

# v9.1: 管理后台 API
app.include_router(admin_api_router)
# 企业级优化器集成
from optimizer_integration import init_optimizer_system
init_optimizer_system()

# ══════════════════════════════════════════════════════════════
# 门户系统 API（v16.0）
# ══════════════════════════════════════════════════════════════
@app.get("/api/portal/current")
async def get_current_portal(current_user: dict = require_auth()):
    """获取当前用户绑定的门户配置（导航树 + 高亮工具），用于前端渲染侧边栏。"""
    from portals import get_user_portal_type, load_user_ctx, get_portal_nav_for_user

    user_ctx = load_user_ctx(current_user)
    return get_portal_nav_for_user(user_ctx)


@app.get("/api/portal/list")
async def list_portals():
    """列出所有可用门户（公开接口，前端切换器展示）。"""
    from portals import PORTAL_DEFS

    return {"portals": list(PORTAL_DEFS.values())}


@app.post("/api/portal/switch")
async def switch_portal(req: PortalSwitchRequest, current_user: dict = require_auth()):
    """切换当前用户的门户类型（用户自主切换）。"""
    from portals import set_user_portal_type

    set_user_portal_type(current_user["user_id"], req.portal_type)
    return {"portal_type": req.portal_type, "message": "门户已切换"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8888)

# ══════════════════════════════════════════════════════════════
# 企业级优化器系统（v18.0）
# ══════════════════════════════════════════════════════════════
from optimizer_integration import (
    router as optimizer_router,
    init_optimizer_system,
)

init_optimizer_system()
app.include_router(optimizer_router)
