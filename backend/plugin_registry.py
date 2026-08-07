#!/usr/bin/env python3
"""插件注册表 - 注册和发现 biz-delivery 引擎插件"""

import logging

logger = logging.getLogger(__name__)


class PluginInterface:
    """插件协议基类"""

    name = ""
    category = ""
    version = "1.0.0"
    description = ""

    def execute(self, input_data: dict) -> dict:
        raise NotImplementedError


class PluginRegistry:
    """插件注册表"""

    def __init__(self):
        self._plugins = {}

    def register(self, plugin: PluginInterface) -> None:
        if not plugin.name:
            raise ValueError("plugin.name required")
        self._plugins[plugin.name] = plugin
        logger.info(f"Plugin registered: {plugin.name} v{plugin.version}")

    def unregister(self, name: str) -> None:
        self._plugins.pop(name, None)

    def list_all(self) -> list:
        return [
            {
                "name": p.name,
                "label": p.name,
                "category": p.category,
                "version": p.version,
                "description": p.description,
                "enabled": True,
            }
            for p in self._plugins.values()
        ]

    def execute(self, name: str, input_data: dict) -> dict:
        plugin = self._plugins.get(name)
        if not plugin:
            raise KeyError(f"Plugin not found: {name}")
        return plugin.execute(input_data)

    def health_check(self) -> list:
        return [{"name": p.name, "version": p.version, "status": "ok"} for p in self._plugins.values()]


# 全局注册表实例
registry = PluginRegistry()

# 尝试加载 engines 包中的插件（biz-delivery 适配层）
try:
    from engines import (
        BizCodeScanPlugin,
        BizReviewPlugin,
        BizTDEnginePlugin,
        BizTestPlugin,
    )

    registry.register(BizCodeScanPlugin())
    registry.register(BizReviewPlugin())
    registry.register(BizTDEnginePlugin())
    registry.register(BizTestPlugin())
except Exception as e:
    logger.warning(f"engines plugins load skipped: {e}")
