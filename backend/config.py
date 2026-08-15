#!/usr/bin/env python3
"""全局配置 — LLM / 安全 / 路径 的单一来源。

业务模块应 `from common.config import ...` 而非各自定义 load_config / normalize_api_base。
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# backend/ 目录
PROJECT_DIR = Path(__file__).resolve().parent.parent

# ── 环境标识 ──────────────────────────────────────────────
APP_ENV = os.environ.get("APP_ENV", "development")


def is_production() -> bool:
    """判断当前是否为生产环境。"""
    return APP_ENV == "production"


def is_development() -> bool:
    """判断当前是否为开发环境。"""
    return APP_ENV in ("development", "dev", "test", "testing", "")


ARTIFACTS_DIR = PROJECT_DIR / "artifacts"
SKILLS_DIR = PROJECT_DIR / "skills_files"
LOGS_DIR = PROJECT_DIR / "logs"

for _d in (ARTIFACTS_DIR, SKILLS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ── LLM 配置（运行时可被 load_config() 用 config 表覆盖）──────────
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")  # TODO: 从安全存储读取
# 中转站地址平台写死（防用户指向其他服务商绕开计费）：爱星火 aixinghuo.net（OpenAI 兼容 /v1）
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://aixinghuo.net/v1")
# 本地版模型不写死：默认均为空，模型全部来自用户中转站（配置 Key 后自动拉取）。
# 前端各创作页会携带所选模型；未配置 Key/未选择模型时，工厂侧明确报错提示。
MODEL_NAME = os.environ.get("MODEL_NAME", "")
IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "")
VIDEO_MODEL = os.environ.get("VIDEO_MODEL", "")


def require_model(model_name: str, feature_label: str) -> str:
    """校验并返回生效模型；为空时抛出清晰错误（本地版不写死任何模型）。"""
    from fastapi import HTTPException

    model_name = (model_name or "").strip()
    if not model_name:
        raise HTTPException(
            400,
            f"未选择{feature_label}模型：请先在个人中心配置中转站 Key，并在页面选择模型",
        )
    return model_name

# ── 视频生成备用通道（预留）：阿里云百炼 wan2.2 文生视频 ─────────
# 配置 DASHSCOPE_API_KEY 后 video_factory 自动启用 dashscope 通道（agnes 失败时 failover）
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
# 通道顺序（逗号分隔，可被 .env / config 表覆盖）；未配置 key 的通道自动跳过
AI_VIDEO_CHANNELS = os.environ.get("AI_VIDEO_CHANNELS", "agnes,dashscope")

# 内置默认模型列表（content-platform 本地版不使用：模型必须从中转站拉取，不写死）
# 用户在个人中心配置中转站 Key 后，后端自动拉取该中转站的模型列表并保存到 config 表。
# 保留常量仅为向后兼容（env 显式配置 AGNES 系模型时仍生效）。
DEFAULT_MODELS = []

# ── 安全配置 ──────────────────────────────────────────────
_DEFAULT_SECRET_KEY = os.environ.get("SECRET_KEY", "")  # 必须从环境变量设置
SECRET_KEY = os.environ.get("SECRET_KEY", _DEFAULT_SECRET_KEY)
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "480"))


def validate_security_config() -> None:
    """启动时校验安全配置。生产环境下使用默认 SECRET_KEY 则抛 RuntimeError。"""
    if is_production() and SECRET_KEY == _DEFAULT_SECRET_KEY:
        raise RuntimeError("SECRET_KEY 使用了默认值，生产环境必须设置自定义 SECRET_KEY 环境变量！")
    if is_production() and len(SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY 长度不足 32 字节，生产环境要求更强密钥！")


# CORS 允许来源（逗号分隔），默认仅本地开发（含 127.0.0.1 防止 Chrome 缓存/直连登录被拦；
# 5173 为 vite 默认端口，5174 为端口被占用时 vite 自动递补的端口）
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:80,http://localhost,http://127.0.0.1",
    ).split(",")
    if o.strip()
]

# biz-delivery 引擎目录（可选，留空则 PRD 引擎走 LLM fallback）
BIZ_DELIVERY_DIR = os.environ.get("BIZ_DELIVERY_DIR", "")


def normalize_api_base(base: str) -> str:
    """规范化 API base：去掉尾部 /chat/completions，确保以 /v1 结尾。"""
    base = (base or "").strip()
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    if base.endswith("/v1"):
        return base
    return base.rstrip("/") + "/v1"


def normalize_model_base(base: str) -> str:
    """规范化模型级 base_url：去尾部 /chat/completions 与斜杠，保留供应商原始路径（不加 /v1）。"""
    base = (base or "").strip()
    if base.endswith("/chat/completions"):
        base = base[: -len("/chat/completions")]
    return base.rstrip("/")


def load_config() -> dict:
    """从 config 表加载配置，覆盖模块级全局变量。返回当前配置 dict。"""
    global AGNES_API_KEY, AGNES_API_BASE, MODEL_NAME, IMAGE_MODEL, VIDEO_MODEL
    try:
        # 独立连接：避免关闭线程复用池连接，影响 async 端点中后续 get_db 的使用
        from common.db import get_db_context

        with get_db_context() as conn:
            rows = conn.execute("SELECT key, value FROM config").fetchall()
        for k, v in rows:
            if not v:
                continue
            if k == "agnes_api_key":
                AGNES_API_KEY = v.strip()
            elif k == "agnes_api_base":
                AGNES_API_BASE = normalize_api_base(v)
            elif k == "model_name":
                MODEL_NAME = v.strip()
            elif k == "image_model":
                IMAGE_MODEL = v.strip()
            elif k == "video_model":
                VIDEO_MODEL = v.strip()
    except Exception as e:
        # 启动早期（init_schema 之前）config 表尚不存在属正常现象，静默跳过；
        # 仅对真实错误（权限/磁盘等）告警，避免误导用户以为启动失败
        if "no such table" not in str(e):
            logger.warning(f"load_config failed (使用环境变量默认值): {e}")
    return {
        "agnes_api_key": AGNES_API_KEY,
        "agnes_api_base": AGNES_API_BASE,
        "model_name": MODEL_NAME,
        "image_model": IMAGE_MODEL,
        "video_model": VIDEO_MODEL,
    }


def get_llm_config() -> tuple[str, str, str]:
    """返回 (api_key, api_base, model_name) 元组，供 call_llm 使用。"""
    return AGNES_API_KEY, AGNES_API_BASE, MODEL_NAME


def get_model_list() -> list[dict]:
    """读取当前生效的模型列表（config 表 model_list，空则内置默认）。

    v1.0.30：多供应商时优先读当前激活供应商的模型列表 model_list:{provider}，
    未命中回退全局 model_list（兼容旧数据）。
    """
    try:
        # 独立连接：避免关闭线程复用池连接，影响 async 端点中后续 get_db 的使用
        from common.db import get_db_context

        key = "model_list"
        try:
            from common.relay_context import get_relay_context

            ctx = get_relay_context()
            provider = (ctx or {}).get("provider") or ""
            if provider:
                key = f"model_list:{provider}"
        except Exception:
            pass
        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
            if not row and key != "model_list":
                row = conn.execute("SELECT value FROM config WHERE key='model_list'").fetchone()
        raw = row["value"] if row else ""
        if raw:
            models = json.loads(raw)
            if isinstance(models, list) and models and all("name" in m for m in models):
                return models
    except Exception:
        pass
    return [dict(m) for m in DEFAULT_MODELS]


def resolve_api_key() -> str:
    """解析当前请求应使用的中转站 API Key（模式 B）：

    - 请求上下文中用户已配置中转站 key → 用户 key（平台卖 token 盈利）
    - 否则 → 全局 AGNES_API_KEY（平台代付）
    供图片/视频/配音等工厂在请求处理时调用（LLM 走 get_model_config 已内置此逻辑）。
    """
    try:
        from common.relay_context import get_relay_context

        ctx = get_relay_context()
        if ctx and ctx.get("api_key"):
            return ctx["api_key"]
    except Exception:
        pass
    return AGNES_API_KEY


# 支持的供应商（模式 B：用户选择中转站，各自 base 平台写死，防绕开计费）
RELAY_PROVIDERS = {
    "aixinghuo": "https://aixinghuo.net/v1",        # 爱星火中转站（默认）
    "agnes": "https://apihub.agnes-ai.cn/v1",      # AGNES 官方 API
}


def resolve_api_base() -> str:
    """解析当前请求应使用的中转站 Base URL（按用户选择的供应商）。

    供应商 base 由平台写死（防用户指向其他服务商绕开计费）；
    请求上下文注入用户供应商对应的 base，未配置时回退默认（aixinghuo）。
    """
    try:
        from common.relay_context import get_relay_context

        ctx = get_relay_context()
        base = (ctx or {}).get("api_base") or ""
        if base:
            return base
        provider = (ctx or {}).get("provider") or ""
        if provider in RELAY_PROVIDERS:
            return RELAY_PROVIDERS[provider]
    except Exception:
        pass
    return AGNES_API_BASE


def get_model_config(model_name: str | None = None) -> dict:
    """返回某模型的调用配置 {model, api_key, api_base}：

    - 模式 B：当前请求用户已配置中转站 key → 优先使用用户 key/base（平台卖 token 盈利）
    - 在模型列表中命中 → 用其 base_url / api_key（留空则继承全局）
    - 未命中 → 全局配置（AGNES_API_KEY / AGNES_API_BASE）
    """
    load_config()  # 确保 config 表覆盖已生效
    name = (model_name or MODEL_NAME).strip()

    # 用户级中转站配置（请求上下文注入，见 common/relay_context）
    user_relay = None
    try:
        from common.relay_context import get_relay_context

        user_relay = get_relay_context()
    except Exception:
        pass
    user_key = (user_relay or {}).get("api_key") or ""

    # 未指定模型名（文案/工具等 LLM 功能前端不传 model）：
    # 优先用用户选择的「默认模型」（全局模型切换），其次取中转站模型列表第一个；无则明确报错
    if not name:
        name = ((user_relay or {}).get("default_model") or "").strip()
        if not name:
            _models = get_model_list()
            if _models:
                name = (_models[0].get("name") or "").strip()
        if not name:
            from fastapi import HTTPException

            raise HTTPException(
                400,
                "未选择模型：请先在个人中心配置中转站 Key（模型将从中转站拉取），或先选择一个模型",
            )

    for m in get_model_list():
        if m.get("name") == name:
            base = normalize_model_base(m.get("base_url") or "")
            key = (m.get("api_key") or "").strip()
            # 用户 key 优先；中转站 URL 平台写死（一律 AGNES_API_BASE，防绕开计费）
            if user_key:
                return {"model": name, "api_key": user_key, "api_base": resolve_api_base()}
            return {
                "model": name,
                "api_key": key or AGNES_API_KEY,
                "api_base": base or AGNES_API_BASE,
            }
    if user_key:
        return {"model": name, "api_key": user_key, "api_base": resolve_api_base()}
    return {"model": name, "api_key": AGNES_API_KEY, "api_base": resolve_api_base()}

def resolve_feature_model(uid: str, feature: str, fallback: str = "") -> str:
    """读取用户按功能选择的模型偏好（model_prefs:{uid} {feature}），未选择用 fallback。"""
    if not uid:
        return fallback
    try:
        from common.db import get_db_context

        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key=?", (f"model_prefs:{uid}",)).fetchone()
        if row and row["value"]:
            prefs = json.loads(row["value"])
            m = (prefs.get(feature) or "").strip()
            if m:
                return m
    except Exception:
        pass
    return fallback
