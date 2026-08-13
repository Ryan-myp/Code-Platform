
"""
模板公共基类 - 提供类型注解支持
"""

from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from pathlib import Path as PathLib
from abc import ABC, abstractmethod

T = TypeVar('T')
"""泛型类型变量"""

@dataclass
class TemplateConfig:
    """模板配置数据类"""
    template_id: str = ""
    width: int = 1080
    height: int = 1920
    layers: List[Dict[str, Any]] = field(default_factory=list)
    output_format: str = "png"
    
    def validate(self) -> Tuple[bool, List[str]]:
        """验证配置"""
        errors = []
        if not self.template_id:
            errors.append("template_id is required")
        if self.width <= 0 or self.height <= 0:
            errors.append("width and height must be positive")
        return len(errors) == 0, errors


class TemplateBase(ABC):
    """模板处理抽象基类"""
    
    def __init__(self, template_id: str = "", config: Optional[TemplateConfig] = None):
        self.template_id = template_id
        self.config = config or TemplateConfig(template_id=template_id)
        self.layers: List[Dict[str, Any]] = []
        self.output_dir: str = "outputs"
    
    @abstractmethod
    def render(self, **kwargs) -> Any:
        """渲染模板（子类必须实现）"""
        pass
    
    def add_layer(self, layer: Dict[str, Any]) -> None:
        """添加图层"""
        self.layers.append(layer)
    
    def get_layer_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        """按key获取图层"""
        for layer in self.layers:
            if layer.get("key") == key:
                return layer
        return None
    
    def remove_layer(self, key: str) -> bool:
        """移除图层"""
        for i, layer in enumerate(self.layers):
            if layer.get("key") == key:
                self.layers.pop(i)
                return True
        return False
    
    def clear_layers(self) -> None:
        """清空所有图层"""
        self.layers.clear()
    
    def get_template_info(self) -> Dict[str, Any]:
        """获取模板信息"""
        return {
            "template_id": self.template_id,
            "width": self.config.width,
            "height": self.config.height,
            "layer_count": len(self.layers),
            "output_format": self.config.output_format
        }


def create_template(template_type: str, **kwargs) -> TemplateBase:
    """工厂方法创建模板实例"""
    # 这里可以根据template_type返回不同的子类实例
    return TemplateBase(**kwargs)


def batch_process_templates(templates: List[TemplateBase], processor: Callable) -> List[Any]:
    """批量处理模板"""
    results = []
    for template in templates:
        results.append(processor(template))
    return results
