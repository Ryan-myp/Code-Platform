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
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
# 统一默认 base（消除旧代码 .cn / .com 漂移），仍可被 config 表覆盖
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://apihub.agnes-ai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "agnes-2.5-flash")

# 内置默认模型列表（config 表未配置 model_list 时使用，供全局模型切换 / Agent 创建下拉）
# base_url 留空 = 继承全局 AGNES_API_BASE；api_key 留空 = 继承全局 AGNES_API_KEY（.env / config 表）
# 多供应商模型需各自配置 base_url + api_key（均为 OpenAI 兼容 /chat/completions）
DEFAULT_MODELS = [
    {"name": "agnes-2.5-flash", "note": "推荐", "base_url": "", "api_key": ""},
    {"name": "agnes-2.5-pro", "note": "", "base_url": "", "api_key": ""},
    {"name": "agnes-2.5-mini", "note": "轻量快速", "base_url": "", "api_key": ""},
    {"name": "agnes-vision", "note": "视觉理解", "base_url": "", "api_key": ""},
    {"name": "deepseek-v3", "note": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "api_key": ""},
    {"name": "glm-4-plus", "note": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4", "api_key": ""},
    {
        "name": "doubao-seed-1.6",
        "note": "豆包·火山方舟",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": "",
    },
    {
        "name": "qwen-max",
        "note": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
    },
]

# ── 安全配置 ──────────────────────────────────────────────
_DEFAULT_SECRET_KEY = "your-super-secret-change-in-prod"
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
    global AGNES_API_KEY, AGNES_API_BASE, MODEL_NAME
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
    except Exception as e:
        logger.warning(f"load_config failed (使用环境变量默认值): {e}")
    return {
        "agnes_api_key": AGNES_API_KEY,
        "agnes_api_base": AGNES_API_BASE,
        "model_name": MODEL_NAME,
    }


def get_llm_config() -> tuple[str, str, str]:
    """返回 (api_key, api_base, model_name) 元组，供 call_llm 使用。"""
    return AGNES_API_KEY, AGNES_API_BASE, MODEL_NAME


def get_model_list() -> list[dict]:
    """读取当前生效的模型列表（config 表 model_list，空则内置默认）。"""
    try:
        # 独立连接：避免关闭线程复用池连接，影响 async 端点中后续 get_db 的使用
        from common.db import get_db_context

        with get_db_context() as conn:
            row = conn.execute("SELECT value FROM config WHERE key='model_list'").fetchone()
        raw = row["value"] if row else ""
        if raw:
            models = json.loads(raw)
            if isinstance(models, list) and models and all("name" in m for m in models):
                return models
    except Exception:
        pass
    return [dict(m) for m in DEFAULT_MODELS]


def get_model_config(model_name: str | None = None) -> dict:
    """返回某模型的调用配置 {model, api_key, api_base}：

    - 在模型列表中命中 → 用其 base_url / api_key（留空则继承全局）
    - 未命中 → 全局配置（AGNES_API_KEY / AGNES_API_BASE）
    """
    load_config()  # 确保 config 表覆盖已生效
    name = (model_name or MODEL_NAME).strip()
    for m in get_model_list():
        if m.get("name") == name:
            base = normalize_model_base(m.get("base_url") or "")
            key = (m.get("api_key") or "").strip()
            return {
                "model": name,
                "api_key": key or AGNES_API_KEY,
                "api_base": base or AGNES_API_BASE,
            }
    return {"model": name, "api_key": AGNES_API_KEY, "api_base": AGNES_API_BASE}
