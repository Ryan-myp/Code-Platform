"""小团智能平台 v6.4 — 业务节点基类和输入验证器

这是业务编排引擎的基础模块，定义了所有业务节点和输入验证器的抽象接口。
所有的行业流程最终都会被拆解为一系列的"节点"来执行。
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class WorkflowStatus:
    """工作流实例的状态码"""

    PENDING = "pending"  # 待启动
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    PAUSED = "paused"  # 暂停
    CANCELLED = "cancelled"  # 已取消


class InputValidator(ABC):
    """输入验证器基类

    用于在节点执行前检查输入数据是否满足要求。验证失败时会返回错误消息列表。

    使用示例：
        validator = RequiredFieldsValidator(["input_text"])
        errors = validator.validate({"text": "some content"})  # 返回 []
    """

    @abstractmethod
    def validate(self, input_data: dict[str, Any]) -> list[str]:
        """验证输入数据

        Args:
            input_data: 要验证的输入数据字典

        Returns:
            错误消息列表，空列表表示通过验证
        """
        pass


class RequiredFieldsValidator(InputValidator):
    """必填字段验证器——检查指定的字段是否存在且非空"""

    def __init__(self, required_fields: list[str]):
        self.required_fields = required_fields

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field in self.required_fields:
            if field not in input_data or input_data[field] is None:
                errors.append(f"缺少必填字段: '{field}'")
        return errors


class TypeValidator(InputValidator):
    """类型验证器——检查指定字段的类型是否正确"""

    def __init__(self, field_type_map: dict[str, type]):
        """field_type_map: {"field_name": expected_type}"""
        self.field_type_map = field_type_map

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, expected_type in self.field_type_map.items():
            if field in input_data and not isinstance(input_data[field], expected_type):
                errors.append(
                    f"字段'{field}'类型错误: 期望{expected_type.__name__}, 实际{type(input_data[field]).__name__}"
                )
        return errors


class MinLengthValidator(InputValidator):
    """字符串最小长度验证器"""

    def __init__(self, field_min_len: dict[str, int]):
        self.field_min_len = field_min_len

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, min_len in self.field_min_len.items():
            if field in input_data and isinstance(input_data[field], str):
                if len(input_data[field]) < min_len:
                    errors.append(f"字段'{field}'长度{len(input_data[field])}低于最小值{min_len}")
        return errors


class MaxLengthValidator(InputValidator):
    """字符串最大长度验证器"""

    def __init__(self, field_max_len: dict[str, int]):
        self.field_max_len = field_max_len

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, max_len in self.field_max_len.items():
            if field in input_data and isinstance(input_data[field], str):
                if len(input_data[field]) > max_len:
                    errors.append(f"字段'{field}'长度{len(input_data[field])}超过最大值{max_len}")
        return errors


class PatternValidator(InputValidator):
    """正则模式验证器（如邮箱、手机号、URL等）"""

    def __init__(self, field_pattern: dict[str, str]):
        self.field_pattern = field_pattern

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        import re

        errors = []
        for field, pattern in self.field_pattern.items():
            if field in input_data and isinstance(input_data[field], str):
                if not re.match(pattern, str(input_data[field])):
                    errors.append(f"字段'{field}'格式不符合模式: {pattern}")
        return errors


class ChoiceValidator(InputValidator):
    """枚举选项验证器——值必须在允许列表中"""

    def __init__(self, field_choices: dict[str, list[Any]]):
        self.field_choices = field_choices

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, choices in self.field_choices.items():
            if field in input_data and input_data[field] not in choices:
                errors.append(f"字段'{field}'值'{input_data[field]}'不在允许选项[{choices}]中")
        return errors


class NodeResult:
    """单个节点的执行结果封装"""

    def __init__(
        self,
        status: str,
        output: dict[str, Any] = None,
        messages: list[str] | None = None,
        error: str | None = None,
    ):
        self.status = status  # "success" | "failed" | "running"
        self.output = output or {}
        self.messages = messages or []
        self.error = error
        self.timestamp = datetime.now().isoformat()

    @classmethod
    def success(cls, output: dict[str, Any], messages: list[str] | None = None) -> "NodeResult":
        return cls(status="success", output=output, messages=messages or [])

    @classmethod
    def failed(
        cls, error: str, output: dict[str, Any] | None = None, messages: list[str] | None = None
    ) -> "NodeResult":
        return cls(status="failed", output=output or {}, messages=messages or [], error=error)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output": self.output,
            "messages": self.messages,
            "error": self.error,
            "timestamp": self.timestamp,
        }


class BusinessNode(ABC):
    """业务节点基类——任何行业的最小任务单元

    所有具体的业务操作都必须继承自这个基类并实现execute方法。
    每个节点都有唯一的node_id，可以有自己的输入验证规则，
    并能够接收来自上游节点的上下文数据，执行后输出新的数据。
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        description: str,
        input_schema: dict[str, Any] | None = None,
        validators: list[InputValidator] | None = None,
    ):
        self.node_id = node_id
        self.name = name
        self.description = description
        self.input_schema = input_schema or {}
        self.validators = validators or []
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.last_executed: str | None = None

    def add_validator(self, validator: InputValidator) -> None:
        """添加输入验证器到节点"""
        self.validators.append(validator)

    def validate_input(self, input_data: dict[str, Any]) -> list[str]:
        """验证输入数据，返回所有错误消息列表"""
        all_errors = []
        for validator in self.validators:
            errors = validator.validate(input_data)
            all_errors.extend(errors)
        return all_errors

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> NodeResult:
        """
        执行节点逻辑

        Args:
            context: 包含所有上游节点输出的完整上下文字典
                     expected structure: {
                         "inputs": {node_id: current_node_input},
                         "outputs": {prev_node_id: prev_result.output},
                         "global_outputs: {} （全局共享变量）
                         "current_node_input": 当前节点的直接输入
                     }

        Returns:
            NodeResult: 包含执行状态、输出数据和消息
        """
        pass

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化到数据库或传输）"""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "validators_type": [v.__class__.__name__ for v in self.validators],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_executed": self.last_executed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BusinessNode":
        """从字典反序列化创建节点实例（子类需要重写此方法）"""
        raise NotImplementedError("子类需要实现from_dict方法")


# ─── 简单示例节点（用于测试和基本功能演示） ─────────────────────


class DummyNode(BusinessNode):
    """哑节点——用于测试框架和演示的基本节点"""

    def __init__(self, node_id: str, name: str, dummy_value: str = "dummy"):
        super().__init__(node_id, name, "哑节点示例")
        self.dummy_value = dummy_value

    def execute(self, context: dict[str, Any]) -> NodeResult:
        # 模拟一些处理时间
        time.sleep(0.1)
        return NodeResult.success(
            output={"result": f"DummyNode '{self.node_id}' executed with value: {self.dummy_value}"},
            messages=[f"{self.node_id}执行完成"],
        )


class PrintNode(BusinessNode):
    """打印节点——将输入内容输出到控制台并返回"""

    def __init__(self, node_id: str, name: str = "打印节点"):
        super().__init__(node_id, name, "将输入内容打印并返回")

    def execute(self, context: dict[str, Any]) -> NodeResult:
        current_input = context.get("current_node_input", {})
        print(f"[PrintNode {self.node_id}] Input: {json.dumps(current_input, ensure_ascii=False)}")
        return NodeResult.success(output={"echo": current_input}, messages=[f"已打印 {self.node_id} 的输入"])

