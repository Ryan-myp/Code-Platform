#!/usr/bin/env python3

"""小团智能平台 v8.0 — AI 赋能各行各业，智能解决工作难题。

v8.0 升级：安全加固、Pydantic 模型验证、异步架构、WebSocket、工作流并行。
"""

import asyncio
import logging
import os
import shutil
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 加载 .env 文件
load_dotenv()

import skills_store  # noqa: E402
from agent_api import router as agent_router  # noqa: E402
from commercial_api import (  # noqa: E402,F401  # 兼容旧 import 路径（测试/外部脚本）
    _record_share_visit,
    _share_visitor_key,
)
from commercial_api import router as commercial_router  # noqa: E402
from common.audit import ensure_audit_table  # noqa: E402
from common.auth import (  # noqa: E402
    _auth_by_api_key,
    change_password,
    consume_quota,
    decode_access_token,
    get_billing_history,
    get_quota_info,
    get_usage_daily_timeline,
    get_usage_detail,
    get_user_profile,
    login_user,
    register_user,
    require_auth,
    reset_password,
    send_password_reset_token,
    update_user_profile,
)
from common.backup import ensure_daily_backup  # noqa: E402
from common.config import ALLOWED_ORIGINS, is_production, validate_security_config  # noqa: E402
from common.db import get_db, init_schema  # noqa: E402
from common.db_async import close_async_db, get_async_db, is_pg_enabled  # noqa: E402
from common.llm import call_llm_async, log_usage, stream_llm_async  # noqa: E402
from common.models import (  # noqa: E402
    AssistantChatRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    PortalSwitchRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from common.observability import (  # noqa: E402
    RequestContextMiddleware,
    get_metrics_snapshot,
    uptime_seconds,
)
from feedback_api import ensure_feedback_table  # noqa: E402
from kb_api import router as kb_router  # noqa: E402
from mcp_api import router as mcp_router  # noqa: E402
from oauth_api import ensure_social_bindings_table  # noqa: E402
from routers import register_routers  # noqa: E402
from sandbox_api import router as sandbox_router  # noqa: E402
from scheduler import start_scheduler, stop_scheduler  # noqa: E402
from seed_data import seed_if_empty  # noqa: E402
from task_queue import recover_interrupted_tasks, start_workers, stop_workers  # noqa: E402
from team_api import ensure_team_tables  # noqa: E402
from voice_factory import _tts_health_check as _tts_prewarm  # noqa: E402

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
    # v20 商业化增强：API Key 计费 / 转化分析 / 企业询价 表初始化
    from api_billing import ensure_api_keys_tables
    from conversion_analytics import ensure_analytics_tables
    from enterprise_api import ensure_enterprise_tables
    from game_factory import ensure_game_tables
    from prd_engine import ensure_requirements_tables

    ensure_api_keys_tables()
    ensure_analytics_tables()
    ensure_enterprise_tables()
    ensure_requirements_tables()
    ensure_game_tables()
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
    title="小团智能平台 v12.0",
    version="12.0.0",
    lifespan=lifespan,
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
    from datetime import datetime

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
    response = await call_next(request)
    # 基本安全头（始终设置）
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    if not _docs_disabled:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'"
        )
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
                            detail = f"今日免费额度已用完（{daily} 次/日）。升级专业版解锁每日 200 次，或邀请好友得额度"
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
        stats["llm"] = {
            "total_calls": 0,
            "success_calls": 0,
            "avg_response_ms": 0,
            "today_calls": 0,
            "today_success": 0,
        }
    return stats


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
            async for delta, full in stream_llm_async(  # noqa: B007
                system_prompt=_ASSISTANT_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=1500,
                temperature=0.5,
            ):
                yield _sse_event("delta", {"text": delta})
            elapsed = round(time.time() - start, 2)
            log_usage(
                "assistant_chat_stream",
                len(user_prompt),
                len(full),
                elapsed,
                user_id=str(current_user.get("user_id", "")),
            )
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
                reset_link = (
                    f"{os.environ.get('APP_BASE_URL', 'http://localhost:5173')}/reset-password?token={result['token']}"
                )
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


# ══════════════════════════════════════════════════════════════
# 路由注册（统一入口，见 routers.py）
# ══════════════════════════════════════════════════════════════
register_routers(app)
# v8.1 拆分：知识库 / MCP / 沙箱 路由从 main.py 拆出（main.py 3822→约 2300 行）
app.include_router(commercial_router)
app.include_router(agent_router)
app.include_router(kb_router)
app.include_router(mcp_router)
app.include_router(sandbox_router)


# ══════════════════════════════════════════════════════════════# ══════════════════════════════════════════════════════════════
# 门户系统 API（v16.0）
# ══════════════════════════════════════════════════════════════
@app.get("/api/portal/current")
async def get_current_portal(current_user: dict = require_auth()):
    """获取当前用户绑定的门户配置（导航树 + 高亮工具），用于前端渲染侧边栏。"""
    from portals import get_portal_nav_for_user, load_user_ctx

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
    import os

    import uvicorn

    # 端口可配置：CLI/容器/云部署通过 PORT 环境变量覆盖（默认 8888）
    port = int(os.environ.get("PORT", "8888"))
    uvicorn.run(app, host="0.0.0.0", port=port)
