#!/usr/bin/env python3
"""智能研发平台 — Plugin Registry 测试（适配 plugin_registry.py 当前 API）

当前 API:
- PluginInterface: 普通基类（name/category/version 类属性，execute 抛 NotImplementedError）
- PluginRegistry: 普通类（非单例）
  - register(plugin) / unregister(name) / list_all() / execute(name, input) / health_check()
  - execute 找不到插件时抛 KeyError
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TestPluginInterface:
    def test_plugin_interface_default_attributes(self):
        from plugin_registry import PluginInterface
        # PluginInterface 是普通基类，可实例化；子类需覆盖 name/category/version
        assert PluginInterface.name == ""
        assert PluginInterface.category == ""
        assert PluginInterface.version == "1.0.0"

    def test_plugin_interface_execute_raises_not_implemented(self):
        from plugin_registry import PluginInterface
        with pytest.raises(NotImplementedError):
            PluginInterface().execute({})


class TestPluginRegistry:
    def test_registry_independent_instances(self):
        """PluginRegistry 是普通类，每次实例化得到独立实例（非单例）"""
        from plugin_registry import PluginRegistry
        r1 = PluginRegistry()
        r2 = PluginRegistry()
        assert r1 is not r2

    def test_register_and_list_all(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class TestPlugin(PluginInterface):
            name = "test-plugin"
            category = "testing"
            version = "1.0.0"
            description = "a test plugin"

            def execute(self, input_data):
                return {"status": "success", "result": "hello"}

        registry = PluginRegistry()
        registry.register(TestPlugin())
        plugins = registry.list_all()
        assert any(p["name"] == "test-plugin" for p in plugins)
        target = next(p for p in plugins if p["name"] == "test-plugin")
        assert target["category"] == "testing"
        assert target["version"] == "1.0.0"
        assert target["enabled"] is True

    def test_register_requires_name(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class AnonymousPlugin(PluginInterface):
            name = ""  # 空 name

            def execute(self, input_data):
                return {}

        registry = PluginRegistry()
        with pytest.raises(ValueError):
            registry.register(AnonymousPlugin())

    def test_execute_plugin(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class EchoPlugin(PluginInterface):
            name = "echo"
            category = "testing"
            version = "1.0.0"

            def execute(self, input_data):
                return {"status": "success", "result": input_data.get("msg", "")}

        registry = PluginRegistry()
        registry.register(EchoPlugin())
        result = registry.execute("echo", {"msg": "hello world"})
        assert result["status"] == "success"
        assert result["result"] == "hello world"

    def test_execute_nonexistent_plugin_raises_key_error(self):
        from plugin_registry import PluginRegistry
        registry = PluginRegistry()
        with pytest.raises(KeyError):
            registry.execute("nonexistent", {})

    def test_health_check_returns_all_plugins(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class HealthPlugin(PluginInterface):
            name = "health-test"
            category = "testing"
            version = "2.1.0"

            def execute(self, input_data):
                return {"status": "success"}

        registry = PluginRegistry()
        registry.register(HealthPlugin())
        hc = registry.health_check()
        assert isinstance(hc, list)
        assert any(h["name"] == "health-test" for h in hc)
        assert all(h["status"] == "ok" for h in hc)

    def test_unregister(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class UnregPlugin(PluginInterface):
            name = "unreg-test"
            category = "testing"
            version = "1.0.0"

            def execute(self, input_data):
                return {"status": "success"}

        registry = PluginRegistry()
        registry.register(UnregPlugin())
        assert any(p["name"] == "unreg-test" for p in registry.list_all())
        registry.unregister("unreg-test")
        assert not any(p["name"] == "unreg-test" for p in registry.list_all())
        # unregister 不存在的 name 也不报错
        registry.unregister("never-registered")

    def test_global_registry_loads_engines_if_available(self):
        """全局 registry 实例在模块加载时尝试加载 engines 包插件。

        没有 biz-delivery 引擎时静默跳过，registry 仍可用。
        """
        from plugin_registry import registry
        # 至少能调用 list_all 与 health_check
        assert isinstance(registry.list_all(), list)
        assert isinstance(registry.health_check(), list)
