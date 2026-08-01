"""LLM节点——调用Agent执行自然语言任务

这是业务编排中最核心的节点类型，适用于几乎所有行业场景的AI决策环节。
例如：
- 教育：生成教案、批改作业、解答问题
- 医疗：生成诊断建议、药方推荐
- 金融：风险评估报告、投资建议
- 制造：工艺方案生成、质量检测规则
- 行政：公文撰写、会议纪要整理
"""

import json
import logging
import re
from typing import Any

from ..base import BusinessNode, NodeResult, RequiredFieldsValidator, TypeValidator

# Import strip_base64_images from main.py (avoid circular import by dynamic loading)
logger = logging.getLogger(__name__)


def get_strip_func():
    """动态导入 strip_base64_images 函数，避免循环导入问题"""
    try:
        from main import strip_base64_images

        return strip_base64_images
    except ImportError:
        # Fallback: basic regex-based cleaner if main.py not directly available
        def fallback_strip(text: str) -> str:
            if not text:
                return text
            text = re.sub(r"<img[^>]*>", "[图片已移除]", text, flags=re.IGNORECASE)
            text = re.sub(r"data:image/[a-zA-Z]+;base64,[A-Za-z0-9+/=]{50,}", "[图片已移除]", text, flags=re.IGNORECASE)
            return text

        return fallback_strip


_STRIPPER = get_strip_func()


class LLMNode(BusinessNode):
    """LLM节点——通过Agent执行自然语言任务

    每个LLM节点都有一个固定的prompt模板和可选的技能集（tools）。
    输入数据会通过prompt模板注入到上下文中，然后由Agent执行。

    使用示例：
        llm_node = LLMNode(
            node_id="analyze_prd",
            name="PRD分析Agent",
            description="分析PRD文档并提取关键信息",
            model="agnes-2.0-flash",
            prompt_template="请从以下PRD中提取产品名称、核心功能、目标用户:\n\n{input_text}",
            input_schema={"input_text": str},
            validators=[RequiredFieldsValidator(["input_text"]), TypeValidator({"input_text": str})]
        )
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        description: str,
        model: str = "agnes-2.0-flash",
        prompt_template: str = "",
        tools: list[str] | None = None,
        knowledge_base_ids: list[str] | None = None,
        skill_ids: list[str] | None = None,
        input_schema: dict[str, Any] | None = None,
        validators: list[Any] | None = None,
    ):

        # 默认输入验证器（根据input_schema自动生成）
        default_validators = []
        if input_schema:
            for field_name, field_type in input_schema.items():
                # map Python type to type object
                type_map = {str: str, int: int, float: float, bool: bool, list: list, dict: dict}
                expected_type = type_map.get(field_type, str)
                if expected_type:
                    default_validators.append(TypeValidator({field_name: expected_type}))

        super().__init__(
            node_id, name, description, input_schema=input_schema, validators=default_validators + (validators or [])
        )

        self.model = model
        self.prompt_template = prompt_template
        self.tools = tools or []
        self.knowledge_base_ids = knowledge_base_ids or []
        self.skill_ids = skill_ids or []

        # 运行时缓存: 实际创建的Agent实例
        self._agent_instance = None

    def _get_agent(self):
        """获取或创建Agent实例（懒加载）"""
        if self._agent_instance is None:
            from main import create_agent_instance

            # Clean prompt_template before passing to Agent (strip base64 images)
            clean_prompt = _STRIPPER(self.prompt_template or "")

            agent_config = {
                "name": self.name,
                "instructions": clean_prompt,  # 使用清理后的prompt
                "model": self.model,
                "enable_memory": False,
                "enable_reasoning": False,
                "tools": self.tools,
                "knowledge_base_ids": self.knowledge_base_ids,
                "skill_ids": self.skill_ids,
                "mcp_server_ids": [],
            }
            self._agent_instance = create_agent_instance(agent_config)
        return self._agent_instance

    def execute(self, context: dict[str, Any]) -> NodeResult:
        """执行LLM节点

        Args:
            context: 包含inputs、outputs、global_outputs等上下文

        Returns:
            NodeResult: 包含输出结果和消息列表
        """
        try:
            # 从当前节点的输入字段获取文本
            current_input = context.get("current_node_input", {})
            if not isinstance(current_input, dict):
                current_input = {}

            # 查找输入中的文本字段（首选input_text，然后找第一个string字段）
            input_text = ""
            if "input_text" in current_input:
                input_text = str(current_input["input_text"])
            elif "text" in current_input:
                input_text = str(current_input["text"])
            else:
                # 尝试找到第一个字符串值作为输入
                for key, value in current_input.items():
                    if isinstance(value, str) and value.strip():
                        input_text = str(value)
                        break

            if not input_text.strip():
                raise ValueError(f"缺少有效的输入文本. 节点: {self.node_id}, 输入: {current_input}")

            # Fill prompt template (supports {input_text}, {inputs.{key}}, etc. placeholders)
            formatted_prompt = self._format_prompt(input_text, context=context)

            # 🔒 二次清理：确保formatted_prompt中没有任何base64图片数据（防御性编程）
            clean_prompt = _STRIPPER(formatted_prompt)

            # 🔒 三级验证：检查清理后的提示中是否仍残留可疑的图片模式
            if re.search(r"data:image", clean_prompt, re.IGNORECASE):
                raise ValueError("检测到残留的图片数据，请检查输入内容")
            if re.search(r"<img\s", clean_prompt, re.IGNORECASE):
                raise ValueError("检测到残留的图片标签，请检查输入内容")

            # 调用Agent执行
            agent = self._get_agent()
            result = agent.run(clean_prompt)  # 使用清理后的prompt

            output_content = result.content if result.content else str(result)

            # 记录执行时间
            elapsed = getattr(self, "_last_exec_time", 0)

            logger.info(f"LLM节点 {self.node_id} 执行完成，输出长度: {len(output_content)}字符")

            return NodeResult.success(
                output={
                    "output_text": output_content,
                    "model_used": self.model,
                    "prompt_length": len(formatted_prompt),
                    "output_length": len(output_content),
                    "raw_result": result.__dict__ if hasattr(result, "__dict__") else {},
                },
                messages=[f"已生成内容，长度{len(output_content)}字符"],
            )

        except Exception as e:
            error_msg = f"LLM节点执行失败: {str(e)}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)

    def _format_prompt(self, input_text: str, context: dict[str, Any]) -> str:
        """格式化prompt模板，替换占位符

        支持的占位符：
        - {input_text}: 主输入文本
        - {inputs.key}: 当前节点的某个输入字段
        - {outputs.prev_node_id}: 上一个节点的输出
        - {outputs.*}: 所有上游节点的输出（通配符）
        - {global_outputs.some_key}: 全局输出变量
        """
        prompt = self.prompt_template

        # 替换主输入文本
        prompt = prompt.replace("{input_text}", input_text)

        # 替换单个输入字段
        for key, value in context.get("current_node_input", {}).items():
            placeholder = f"{{{key}}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))

        # 替换输出占位符 {outputs.node_name}
        outputs = context.get("outputs", {})
        for node_id, output_val in outputs.items():
            if isinstance(output_val, dict):
                for out_key, out_value in output_val.items():
                    placeholder = f"{{outputs.{node_id}.{out_key}}}"
                    if placeholder in prompt:
                        prompt = prompt.replace(placeholder, str(out_value))
            else:
                placeholder = f"{{outputs.{node_id}}}"
                if placeholder in prompt:
                    prompt = prompt.replace(placeholder, str(output_val))

        # 替换全局输出 {global_outputs.key}
        global_out = context.get("global_outputs", {})
        for key, value in global_out.items():
            placeholder = f"{{global_outputs.{key}}}"
            if placeholder in prompt:
                prompt = prompt.replace(placeholder, str(value))

        return prompt


# ─── 示例用法 ───────────────────────────────────────────────

if __name__ == "__main__":
    # 创建一个PRD分析节点
    prd_analyzer = LLMNode(
        node_id="analyze_prd",
        name="PRD分析Agent",
        description="从PRD中提取产品信息",
        model="agnes-2.0-flash",
        prompt_template="""请从以下PRD中提取：产品名称、核心功能、目标用户、关键需求
PRD内容: {input_text}

请以JSON格式返回，键为: product_name, features, users, requirements""",
        input_schema={"input_text": str},
        validators=[
            RequiredFieldsValidator(["input_text"]),
            MinLengthValidator({"input_text": 50}),  # 最小50字符
        ],
    )

    # 测试执行
    test_context = {
        "current_node_input": {"input_text": "这是一个电商平台的购物功能..."},
        "outputs": {},
        "global_outputs": {},
    }

    result = prd_analyzer.execute(test_context)
    print(f"状态: {result.status}, 输出: {json.dumps(result.output, ensure_ascii=False)[:200]}")
