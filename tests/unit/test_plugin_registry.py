#!/usr/bin/env python3
"""智能研发平台 — Plugin Registry 测试"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


class TestPluginInterface:
    def test_plugin_interface_abstract(self):
        from plugin_registry import PluginInterface
        # PluginInterface 是抽象类，不能直接实例化
        try:
            PluginInterface()
            assert False, "Should not be able to instantiate abstract class"
        except TypeError:
            pass


class TestPluginRegistry:
    def test_singleton(self):
        from plugin_registry import PluginRegistry
        r1 = PluginRegistry()
        r2 = PluginRegistry()
        assert r1 is r2

    def test_register_and_get(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class TestPlugin(PluginInterface):
            @property
            def name(self):
                return "test-plugin"

            @property
            def category(self):
                return "testing"

            @property
            def version(self):
                return "1.0.0"

            def execute(self, input_data):
                return {"status": "success", "result": "hello"}

        registry = PluginRegistry()
        registry.register(TestPlugin())
        plugin = registry.get("test-plugin")
        assert plugin is not None
        assert plugin.name == "test-plugin"

    def test_execute_plugin(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class EchoPlugin(PluginInterface):
            @property
            def name(self):
                return "echo"

            @property
            def category(self):
                return "testing"

            @property
            def version(self):
                return "1.0.0"

            def execute(self, input_data):
                return {"status": "success", "result": input_data.get("msg", "")}

        registry = PluginRegistry()
        registry.register(EchoPlugin())
        result = registry.execute("echo", {"msg": "hello world"})
        assert result["status"] == "success"
        assert result["result"] == "hello world"

    def test_execute_nonexistent_plugin(self):
        from plugin_registry import PluginRegistry
        registry = PluginRegistry()
        result = registry.execute("nonexistent", {})
        assert result["status"] == "failed"
        assert "not found" in result["error"].lower() or "未找到" in result["error"]

    def test_categories(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class CatPlugin(PluginInterface):
            @property
            def name(self):
                return "cat-plugin"

            @property
            def category(self):
                return "test-category"

            @property
            def version(self):
                return "1.0.0"

            def execute(self, input_data):
                return {"status": "success"}

        registry = PluginRegistry()
        registry.register(CatPlugin())
        categories = registry.categories()
        assert "test-category" in categories

    def test_health_check(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class HealthPlugin(PluginInterface):
            @property
            def name(self):
                return "health-test"

            @property
            def category(self):
                return "testing"

            @property
            def version(self):
                return "1.0.0"

            def execute(self, input_data):
                return {"status": "success"}

        registry = PluginRegistry()
        registry.register(HealthPlugin())
        hc = registry.health_check("health-test")
        assert hc["status"] == "healthy"

    def test_unregister(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class UnregPlugin(PluginInterface):
            @property
            def name(self):
                return "unreg-test"

            @property
            def category(self):
                return "testing"

            @property
            def version(self):
                return "1.0.0"

            def execute(self, input_data):
                return {"status": "success"}

        registry = PluginRegistry()
        registry.register(UnregPlugin())
        assert registry.get("unreg-test") is not None
        registry.unregister("unreg-test")
        assert registry.get("unreg-test") is None

    def test_list_all_plugins(self):
        from plugin_registry import PluginRegistry, PluginInterface

        class ListPlugin(PluginInterface):
            @property
            def name(self):
                return "list-test"

            @property
            def category(self):
                return "testing"

            @property
            def version(self):
                return "1.0.0"

            def execute(self, input_data):
                return {"status": "success"}

        registry = PluginRegistry()
        registry.register(ListPlugin())
        plugins = registry.list_all()
        names = [p["name"] for p in plugins]
        assert "list-test" in names
