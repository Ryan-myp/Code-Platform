"""Skill执行节点——调用已注册的skill模块中的函数执行任务

这是最灵活的节点类型，可以调用任何Python业务逻辑。
示例场景：
- 执行自定义的数据清洗脚本
- 调用特定的算法模型
- 生成行业特定的报告格式
- 与第三方SDK集成
"""

import importlib
import logging
import re
import traceback
from typing import Any

from ..base import BusinessNode, NodeResult, RequiredFieldsValidator

logger = logging.getLogger(__name__)


class SkillExecutionNode(BusinessNode):
    """Skill节点——动态执行技能脚本中的函数

    该节点会从指定的Python模块中导入并调用指定函数，将上下文数据作为参数传入。

    使用示例:
        # 在skills/文件夹下创建weather_skill.py
        # def get_weather(city: str) -> dict: ...

        skill_node = SkillExecutionNode(
            node_id="get_weather",
            skill_file="skills.weather_skill",
            function_name="get_weather",
            args_field="city",      # 从context.inputs.city取参数
            kwargs_field={}         # 可选的额外参数字典
        )

    工作流配置:
        - skill_file: Python模块路径 (如 "skills.weather_script")
        - function_name: 要调用的函数名
        - args_field: 从上下文中取哪个字段作为位置参数 (默认: None)
        - kwargs_field: 额外的参数字典 (字面量或占位符引用)
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        description: str,
        skill_file: str,
        function_name: str,
        args_field: str | None = None,
        kwargs_field: dict[str, Any] | None = None,
        input_schema: dict[str, Any] | None = None,
        validators: Any | None = None,
    ):

        super().__init__(node_id, name, description, input_schema=input_schema, validators=validators or [])

        self.skill_file = skill_file
        self.function_name = function_name
        self.args_field = args_field
        self.kwargs_field = kwargs_field or {}

        # 验证输入验证器（如果需要args_field）
        default_validators = []
        if args_field:
            default_validators.append(RequiredFieldsValidator([args_field]))

        if validators:
            default_validators.extend(validators)

        self.validators = default_validators

    def _resolve_kwargs(self, context: dict[str, Any]) -> dict[str, Any]:
        """解析kwargs中的变量占位符"""
        resolved = {}
        for key, value in self.kwargs_field.items():
            if isinstance(value, str) and value.startswith("{"):
                # 简单的变量替换: {outputs.node.field} -> 实际值
                outputs = context.get("outputs", {})
                match = re.match(r"\{outputs\.(\w+)\.(\w+)\}", value)
                if match:
                    node_id, field = match.groups()
                    resolved[key] = str(outputs.get(node_id, {}).get(field, ""))
                else:
                    resolved[key] = value.replace("{", "").replace("}", "")
            else:
                resolved[key] = value
        return resolved

    def execute(self, context: dict[str, Any]) -> NodeResult:
        try:
            # 导入skill模块
            logger.info(f"导入技能模块: {self.skill_file}")
            skill_module = importlib.import_module(self.skill_file)

            # 获取要执行的函数
            func = getattr(skill_module, self.function_name, None)
            if func is None:
                raise AttributeError(f"模块 {self.skill_file} 中没有函数 '{self.function_name}'")

            # 构建参数
            args = []
            kwargs = {}

            if self.args_field:
                current_input = context.get("current_node_input", {})
                if self.args_field in current_input:
                    args.append(current_input[self.args_field])

            # 解析kwargs
            resolved_kwargs = self._resolve_kwargs(context)
            kwargs.update(resolved_kwargs)

            # 执行函数
            logger.info(f"调用技能函数: {self.function_name}({args}, {kwargs})")
            result = func(*args, **kwargs)

            logger.info(f"技能函数执行成功，返回结果类型: {type(result)}")

            return NodeResult.success(
                output={"result": result, "function_returned": True}, messages=[f"{self.function_name}执行成功"]
            )

        except ImportError as e:
            error_msg = f"无法导入skill模块 {self.skill_file}: {str(e)}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)
        except AttributeError as e:
            error_msg = f"找不到函数 {self.function_name}: {str(e)}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)
        except Exception as e:
            error_msg = f"技能函数执行失败: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)

