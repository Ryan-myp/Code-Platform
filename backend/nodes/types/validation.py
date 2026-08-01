"""输入验证器模块——用于在节点执行前检查输入数据的有效性

这个模块提供了一系列预定义的验证器组合，用户可以快速为业务节点添加输入验证。
支持多种验证类型，包括必填字段、数据类型、长度限制、格式匹配等。

使用示例：
    from nodes.types.validation import RequiredFieldsValidator, TypeValidator

    validators = [
        RequiredFieldsValidator(["input_text"]),
        TypeValidator({"input_text": str}),
        MinLengthValidator({"input_text": 10})
    ]
"""

import re
from abc import ABC, abstractmethod
from typing import Any


class InputValidator(ABC):
    """输入验证器基类

    每个验证器负责验证输入数据的某个方面（如必填字段、类型、格式等）。
    如果验证失败，返回错误消息列表；通过则返回空列表。
    """

    @abstractmethod
    def validate(self, input_data: dict[str, Any]) -> list[str]:
        """验证输入数据

        Args:
            input_data: 传递给节点的输入字典

        Returns:
            错误消息列表，空列表表示验证通过
        """
        pass


class RequiredFieldsValidator(InputValidator):
    """必填字段验证器——检查所有指定字段是否存在且非空"""

    def __init__(self, required_fields: list[str]):
        self.required_fields = required_fields

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field in self.required_fields:
            if field not in input_data or input_data[field] is None or str(input_data[field]).strip() == "":
                errors.append(f"缺少必填字段: '{field}'")
        return errors


class TypeValidator(InputValidator):
    """类型验证器——检查指定字段的Python类型是否匹配"""

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
        """field_min_len: {"field_name": min_length}"""
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
        """field_max_len: {"field_name": max_length}"""
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
        """field_pattern: {"field_name": regex_pattern}"""
        self.field_pattern = field_pattern

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, pattern in self.field_pattern.items():
            if field in input_data and isinstance(input_data[field], str):
                if not re.match(pattern, str(input_data[field])):
                    errors.append(f"字段'{field}'格式不符合模式: {pattern}")
        return errors


class ChoiceValidator(InputValidator):
    """枚举选项验证器——值必须在允许列表中"""

    def __init__(self, field_choices: dict[str, list[Any]]):
        """field_choices: {"field_name": [allowed_values]}"""
        self.field_choices = field_choices

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, choices in self.field_choices.items():
            if field in input_data and input_data[field] not in choices:
                errors.append(f"字段'{field}'值'{input_data[field]}'不在允许选项[{choices}]中")
        return errors


class RangeValidator(InputValidator):
    """数值范围验证器（包含或不包含边界）"""

    def __init__(self, field_range: dict[str, dict]):
        """field_range: {"field_name": {"min": 0, "max": 100, "inclusive": True}}"""
        self.field_range = field_range

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        errors = []
        for field, config in self.field_range.items():
            if field in input_data and isinstance(input_data[field], (int, float)):
                val = input_data[field]
                min_val = config.get("min")
                max_val = config.get("max")
                inclusive = config.get("inclusive", True)

                if min_val is not None and val < (min_val if inclusive else min_val + 0.0001):
                    errors.append(f"字段'{field}'值{val}低于最小值{min_val}")
                if max_val is not None and val > (max_val if inclusive else max_val - 0.0001):
                    errors.append(f"字段'{field}'值{val}高于最大值{max_val}")
        return errors


class CombiningValidator(InputValidator):
    """组合验证器——将多个验证器组合在一起同时验证"""

    def __init__(self, validators: list[InputValidator]):
        self.validators = validators

    def validate(self, input_data: dict[str, Any]) -> list[str]:
        all_errors = []
        for validator in self.validators:
            errors = validator.validate(input_data)
            all_errors.extend(errors)
        return all_errors


# ─── 示例验证器组合 ─────────────────────────────────────────────


def create_prd_validator() -> CombiningValidator:
    """创建一个PRD输入验证器的标准组合（用于PRD生成场景）"""
    validators = [
        RequiredFieldsValidator(["text"]),
        TypeValidator({"text": str}),
        MinLengthValidator({"text": 50}),  # PRD至少50字符
        MaxLengthValidator({"text": 10000}),  # 最大1万字
    ]
    return CombiningValidator(validators)


def create_api_call_validator() -> CombiningValidator:
    """创建一个API调用输入验证器的标准组合"""
    validators = [
        RequiredFieldsValidator(["url"]),
        TypeValidator({"url": str}),
        PatternValidator(
            {
                "url": r"^https?://[^\s/$.?#].[^\s]*$"  # 基本URL格式
            }
        ),
    ]
    return CombiningValidator(validators)


if __name__ == "__main__":
    # 快速测试验证器

    # 测试RequiredFieldsValidator
    validator = RequiredFieldsValidator(["name", "age"])
    result = validator.validate({"name": "Test"})
    assert "age" in result[0], "应该报告age缺失"
    print(f"RequiredFieldsValidator测试: {result}")

    # 测试TypeValidator
    type_validator = TypeValidator({"value": int})
    result = type_validator.validate({"value": "string"})
    assert "类型错误" in result[0], "应该报告类型错误"
    print(f"TypeValidator测试: {result}")

    # 测试PatternValidator（邮箱格式）
    pattern_validator = PatternValidator({"email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"})
    result = pattern_validator.validate({"email": "invalid-email"})
    assert "格式不符合模式" in result[0], "应该报告格式错误"
    print(f"PatternValidator测试: {result}")

    # 测试组合验证器
    combined = CombiningValidator([RequiredFieldsValidator(["username"]), MinLengthValidator({"username": 5})])
    result = combined.validate({"username": "ab"})
    assert len(result) == 1, "应该有1个错误（长度不足）"
    print(f"CombiningValidator测试: {result}")

    print("\n所有验证器测试通过！")
