"""决策节点——条件判断分支节点

决策节点用于在工作流中引入条件分支，根据某个条件的真假选择不同的执行路径。

典型应用场景：
- 审批流程: 金额 > 10万 → 总监审批; ≤ 1万 → 部门经理审批
- 异常处理: 检测结果合格 → 进入下一环节; 不合格 → 退回重做
- A/B测试: 随机选择不同方案并跟踪结果
- 多语言支持: 用户所在地区 = CN → 中文界面; 否则英文界面
"""

import logging
from typing import Any

from ..base import BusinessNode, NodeResult, RequiredFieldsValidator

logger = logging.getLogger(__name__)


class DecisionNode(BusinessNode):
    """决策节点——根据条件判断决定工作流走向

    配置说明:
      - condition_expr: 条件表达式，使用Python语法，可引用上下文变量
        例如: "output.score > 80" 或 "inputs.input_text.lower() contains 'urgent'"
        支持的变量: inputs.{field}, outputs.{node}.{field}, global_outputs.{key}

      - true_next_node: 条件为TRUE时跳转的下一个节点ID（必填）
      - false_next_node: 条件为FALSE时跳转的下一个节点ID（可选，默认为当前节点的下一个）

    在顺序执行的工作流中，默认false_next_node指向列表中的下一个节点。
    如果要创建复杂的多分支结构，需要使用独立的决策链式节点。
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        description: str,
        condition_expr: str,
        true_next_node: str,
        false_next_node: str | None = None,
        input_schema: dict[str, Any] | None = None,
        validators: Any | None = None,
    ):

        super().__init__(node_id, name, description, input_schema=input_schema, validators=validators or [])

        self.condition_expr = condition_expr
        self.true_next_node = true_next_node
        self.false_next_node = false_next_node

        # 默认验证：条件表达式非空
        default_validators = [RequiredFieldsValidator(["condition_expr", "true_next_node"])]
        if validators:
            default_validators.extend(validators)
        self.validators = default_validators

    def _evaluate_condition(self, context: dict[str, Any]) -> bool:
        """评估条件表达式，返回布尔值

        支持的变量前缀：
        - inputs.X: 当前节点的输入字段X
        - outputs.node_name.X: 上一个输出节点output.X
        - global_outputs.X: 全局输出变量X
        """
        try:
            # 构建安全的全局命名空间
            safe_globals = {
                "inputs": context.get("current_node_input", {}),
                "outputs": context.get("outputs", {}),
                "global_outputs": context.get("global_outputs", {}),
                "str": str,
                "int": int,
                "float": float,
                "len": len,
                "contains": lambda s, sub: sub in s,  # 中文字符匹配助记
                "lower": lambda s: s.lower() if isinstance(s, str) else "",
                "upper": lambda s: s.upper() if isinstance(s, str) else "",
            }

            # 安全地eval表达式
            result = eval(self.condition_expr, {"__builtins__": {}}, safe_globals)

            # 确保结果是布尔值或可转换为布尔值
            return bool(result)

        except Exception as e:
            logger.error(f"条件表达式求值错误: {self.condition_expr}, 错误: {e}")
            raise

    def execute(self, context: dict[str, Any]) -> NodeResult:
        try:
            # 验证输入
            current_input = context.get("current_node_input", {})
            validation_errors = self.validate_input(current_input)
            if validation_errors:
                error_msg = f"输入验证失败: {'; '.join(validation_errors)}"
                logger.warning(error_msg)
                return NodeResult.failed(error_msg)

            # 评估条件
            should_follow_true = self._evaluate_condition(context)
            logger.info(f"决策节点 {self.node_id}: condition='{self.condition_expr}' => {should_follow_true}")

            # 记录决策结果作为输出
            output = {
                "condition_evaluated": self.condition_expr,
                "result": should_follow_true,
                "next_node": self.true_next_node if should_follow_true else (self.false_next_node or "unknown"),
            }

            return NodeResult.success(
                output=output,
                messages=[
                    f"条件评估结果: {'通过' if should_follow_true else '未通过'} -> 跳转至 {self.true_next_node if should_follow_true else (self.false_next_node or '下一节点')}"
                ],
            )

        except Exception as e:
            error_msg = f"决策节点执行异常: {str(e)}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)

    def get_true_next(self) -> str:
        """获取真分支的目标节点ID"""
        return self.true_next_node

    def get_false_next(self) -> str | None:
        """获取假分支的目标节点ID"""
        return self.false_next_node
