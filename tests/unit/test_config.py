#!/usr/bin/env python3
"""小团智能平台 — 配置模块测试（common.config 单一来源）"""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


def test_config_has_required_attributes():
    """common.config 模块应暴露 LLM / 安全 / CORS 关键变量"""
    from common import config
    assert hasattr(config, "AGNES_API_KEY")
    assert hasattr(config, "AGNES_API_BASE")
    assert hasattr(config, "MODEL_NAME")
    assert hasattr(config, "SECRET_KEY")
    assert hasattr(config, "ALGORITHM")
    assert hasattr(config, "ALLOWED_ORIGINS")
    assert hasattr(config, "ARTIFACTS_DIR")


def test_default_values():
    """检查默认值"""
    from common import config
    assert config.ALGORITHM == "HS256"
    assert config.AGNES_API_BASE.endswith("/v1")
    assert isinstance(config.ALLOWED_ORIGINS, list)
    assert config.TOKEN_EXPIRE_MINUTES > 0


def test_normalize_api_base():
    """normalize_api_base 去掉 /chat/completions 并补 /v1"""
    from common.config import normalize_api_base
    assert normalize_api_base("https://api.example.com/v1") == "https://api.example.com/v1"
    assert normalize_api_base("https://api.example.com/v1/chat/completions") == "https://api.example.com/v1"
    assert normalize_api_base("https://api.example.com") == "https://api.example.com/v1"
    assert normalize_api_base("https://api.example.com/") == "https://api.example.com/v1"
    assert normalize_api_base("") == "/v1"


def test_get_llm_config_returns_tuple():
    """get_llm_config 返回 (api_key, api_base, model) 三元组"""
    from common.config import get_llm_config
    api_key, api_base, model = get_llm_config()
    assert isinstance(api_key, str)
    assert isinstance(api_base, str)
    assert isinstance(model, str)
    assert api_base.endswith("/v1")


def test_load_config_persists_to_module_globals(test_db_path):
    """load_config 从 config 表加载并覆盖模块级全局变量"""
    from common.db import get_db
    # 写入配置
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("agnes_api_key", "sk-test-key-12345"))
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("agnes_api_base", "https://my-test-api.example.com/v1"))
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ("model_name", "test-model-7b"))
    conn.commit()
    conn.close()

    from common import config
    cfg = config.load_config()
    assert cfg["agnes_api_key"] == "sk-test-key-12345"
    assert cfg["agnes_api_base"] == "https://my-test-api.example.com/v1"
    assert cfg["model_name"] == "test-model-7b"
    # 模块级全局变量也被覆盖
    assert config.AGNES_API_KEY == "sk-test-key-12345"
    assert config.AGNES_API_BASE == "https://my-test-api.example.com/v1"
    assert config.MODEL_NAME == "test-model-7b"


def test_load_config_normalizes_api_base(test_db_path):
    """load_config 调用 normalize_api_base 规范化 base url"""
    from common.db import get_db
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                 ("agnes_api_base", "https://api.example.com/v1/chat/completions"))
    conn.commit()
    conn.close()

    from common import config
    config.load_config()
    assert config.AGNES_API_BASE == "https://api.example.com/v1"
