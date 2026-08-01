#!/usr/bin/env python3
"""智能研发平台 — 配置模块测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TestConfig:
    def test_config_has_required_attributes(self):
        from config import Config
        assert hasattr(Config, "AGNES_API_KEY")
        assert hasattr(Config, "AGNES_API_BASE")
        assert hasattr(Config, "MODEL_NAME")
        assert hasattr(Config, "DB_PATH")
        assert hasattr(Config, "SECRET_KEY")
        assert hasattr(Config, "HOST")
        assert hasattr(Config, "PORT")

    def test_default_values(self):
        from config import Config
        assert Config.MODEL_NAME == "agnes-2.0-flash"
        assert Config.HOST == "0.0.0.0"
        assert Config.PORT == 8888
        assert Config.ALGORITHM == "HS256"

    def test_is_production_false_by_default(self):
        from config import Config
        assert Config.is_production() is False

    def test_secret_key_default_warning(self):
        from config import Config
        assert Config.SECRET_KEY == "change-me-in-production"

    def test_env_override(self, monkeypatch):
        """测试环境变量覆盖默认值"""
        monkeypatch.setenv("MODEL_NAME", "custom-model")
        monkeypatch.setenv("PORT", "9999")
        monkeypatch.setenv("DEBUG", "true")
        # 需要重新加载 config 模块
        if "config" in sys.modules:
            del sys.modules["config"]
        from config import Config
        assert Config.MODEL_NAME == "custom-model"
        assert Config.PORT == 9999
        assert Config.DEBUG is True
