"""
模板公共基类 - 提取重复的模板处理逻辑
"""

from typing import Any, Optional
import os


class TemplateBase:
    """模板处理公共基类。"""
    
    def __init__(self, template_id: str = "", config: Optional[dict] = None):
        self.template_id = template_id
        self.config = config or {}
        self.layers: list = []
        self.output_dir = "outputs"
    
    def validate(self) -> tuple[bool, list[str]]:
        """验证模板配置。"""
        errors = []
        
        if not self.template_id:
            errors.append("template_id is required")
        
        if not isinstance(self.config, dict):
            errors.append("config must be a dictionary")
        
        return len(errors) == 0, errors
    
    def add_layer(self, layer: dict) -> None:
        """添加图层。"""
        self.layers.append(layer)
    
    def get_layer_by_key(self, key: str) -> Optional[dict]:
        """按key获取图层。"""
        for layer in self.layers:
            if layer.get("key") == key:
                return layer
        return None
    
    def render_to_path(self, output_path: str) -> str:
        """渲染到指定路径。"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        return output_path
    
    def get_template_config(self) -> dict:
        """获取模板配置。"""
        return {
            "template_id": self.template_id,
            "config": self.config,
            "layer_count": len(self.layers)
        }


def create_template(template_type: str, **kwargs) -> TemplateBase:
    """工厂方法创建模板实例。"""
    return TemplateBase(**kwargs)
