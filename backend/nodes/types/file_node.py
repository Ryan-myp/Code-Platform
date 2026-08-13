"""文件操作节点——执行文件系统的读写/移动/删除等操作

适用场景：
- 教育：保存生成的教案到文件系统
- 制造：保存工艺图纸到共享目录
- 金融：保存合规报告到指定路径
- 通用：任何需要持久化输出到文件的业务环节
"""

import logging
import os
import re
import shutil
from datetime import datetime
from typing import Any

from ..base import BusinessNode, NodeResult, RequiredFieldsValidator, TypeValidator

logger = logging.getLogger(__name__)


class FileOperationNode(BusinessNode):
    """文件操作节点——对文件系统进行增删改查操作

    支持的操作类型:
      - "read": 读取文件内容
      - "write": 写入文件内容
      - "create_dir": 创建目录
      - "delete": 删除文件或目录
      - "move": 移动/重命名文件

    节点配置示例:
        node = FileOperationNode(
            node_id="save_report",
            operation_type="write",
            path="/var/www/reports/{timestamp}.txt",
            content="{output_text}"  # 引用上游节点的输出
        )
    """

    OP_TYPES = ["read", "write", "create_dir", "delete", "move"]

    def __init__(
        self,
        node_id: str,
        operation_type: str,
        path: str,
        content: str | None = None,
        dest: str | None = None,
        input_schema: dict[str, Any] | None = None,
        validators: Any | None = None,
    ):

        if operation_type not in self.OP_TYPES:
            raise ValueError(f"不支持的操作类型: {operation_type}. 必须是: {self.OP_TYPES}")

        super().__init__(node_id, f"文件操作({operation_type})", f"执行{operation_type}操作于路径: {path}")

        self.operation_type = operation_type
        self.path = path
        self.content = content  # write/delete时需要指定要写入/删除的内容
        self.dest = dest  # move时的目标路径

        # 默认输入验证
        default_validators = []
        if operation_type == "read":
            default_validators.append(RequiredFieldsValidator(["path"]))
        elif operation_type == "write":
            default_validators.append(RequiredFieldsValidator(["path", "content"]))
            default_validators.append(TypeValidator({"content": str}))
        elif operation_type == "create_dir":
            default_validators.append(RequiredFieldsValidator(["path"]))
        elif operation_type == "delete":
            default_validators.append(RequiredFieldsValidator(["path"]))
        elif operation_type == "move":
            default_validators.append(RequiredFieldsValidator(["path", "dest"]))
            default_validators.append(TypeValidator({"dest": str}))

        if validators:
            default_validators.extend(validators)

        self.validators = default_validators

    def _resolve_path_vars(self, path: str, context: dict[str, Any]) -> str:
        """解析路径中的变量占位符如{timestamp},{outputs.node_id}等"""
        # 1. 替换 timestamp
        now = datetime.now()
        path = path.replace("{timestamp}", now.strftime("%Y%m%d_%H%M%S"))
        path = path.replace("{date}", now.strftime("%Y-%m-%d"))
        path = path.replace("{time}", now.strftime("%H:%M:%S"))

        # 2. 替换 outputs.{node_name}.{field}
        outputs = context.get("outputs", {})
        for node_id, output_val in outputs.items():
            output_key_pattern = rf"{{outputs\.{node_id}\.(\w+)}}"

            def replace_output(match, _output_val=output_val):
                key = match.group(1)
                return str(_output_val.get(key, "")) if isinstance(_output_val, dict) else str(_output_val)

            path = re.sub(output_key_pattern, replace_output, path)

        # 3. 替换 global_outputs.{key}
        global_out = context.get("global_outputs", {})
        for key, value in global_out.items():
            placeholder = f"{{global_outputs.{key}}}"
            if placeholder in path:
                path = path.replace(placeholder, str(value))

        # 4. 替换 simple {key} 来自当前输入
        current_input = context.get("current_node_input", {})
        for key, value in current_input.items():
            placeholder = f"{{{key}}}"
            if placeholder in path:
                path = path.replace(placeholder, str(value))

        # 展开用户家目录
        return os.path.expanduser(path)

    def resolve_content(self, content: str, context: dict[str, Any]) -> str:
        """解析内容中的变量占位符"""
        if not content:
            return content

        resolved = content

        # 1. 替换 outputs.{node}.{field}
        outputs = context.get("outputs", {})
        for node_id, output_val in outputs.items():
            if isinstance(output_val, dict):
                for key, val in output_val.items():
                    placeholder = f"{{outputs.{node_id}.{key}}}"
                    resolved = resolved.replace(placeholder, str(val))
            else:
                placeholder = f"{{outputs.{node_id}}}"
                resolved = resolved.replace(placeholder, str(output_val))

        # 2. 替换 global_outputs.{key}
        global_out = context.get("global_outputs", {})
        for key, value in global_out.items():
            placeholder = f"{{global_outputs.{key}}}"
            resolved = resolved.replace(placeholder, str(value))

        return resolved

    def _op_read(self, resolved_path: str) -> NodeResult:
        """读文件操作。"""
        if not os.path.exists(resolved_path):
            raise FileNotFoundError(f"文件不存在: {resolved_path}")
        with open(resolved_path, encoding="utf-8") as f:
            content = f.read()
        logger.info(f"成功读取文件: {resolved_path} ({len(content)}字符)")
        return NodeResult.success(output={"content": content, "file_path": resolved_path}, messages=["已读取文件"])

    def _op_write(self, resolved_path: str, context: dict[str, Any]) -> NodeResult:
        """写文件操作。"""
        resolved_content = self.resolve_content(self.content or "", context)
        dir_path = os.path.dirname(resolved_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(resolved_path, "w", encoding="utf-8") as f:
            f.write(resolved_content)
        logger.info(f"成功写入文件: {resolved_path}")
        return NodeResult.success(
            output={"written_to": resolved_path, "content_length": len(resolved_content)},
            messages=[f"已保存到 {resolved_path}"],
        )

    def _op_create_dir(self, resolved_path: str) -> NodeResult:
        """创建目录操作。"""
        os.makedirs(resolved_path, exist_ok=True)
        logger.info(f"已创建目录: {resolved_path}")
        return NodeResult.success(output={"created_directory": resolved_path}, messages=["已创建目录"])

    def _op_delete(self, resolved_path: str) -> NodeResult:
        """删除文件/目录操作。"""
        if os.path.isfile(resolved_path):
            os.remove(resolved_path)
        elif os.path.isdir(resolved_path):
            shutil.rmtree(resolved_path)
        else:
            raise FileNotFoundError(f"文件/目录不存在: {resolved_path}")
        logger.info(f"已删除: {resolved_path}")
        return NodeResult.success(output={"deleted": resolved_path}, messages=["已删除文件"])

    def _op_move(self, resolved_path: str, context: dict[str, Any]) -> NodeResult:
        """移动文件操作。"""
        resolved_dest = self._resolve_path_vars(self.dest, context)
        dest_dir = os.path.dirname(resolved_dest) or "."
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        shutil.move(resolved_path, resolved_dest)
        logger.info(f"已移动: {resolved_path} -> {resolved_dest}")
        return NodeResult.success(
            output={"moved_from": resolved_path, "moved_to": resolved_dest},
            messages=[f"已移动到 {resolved_dest}"],
        )

    def execute(self, context: dict[str, Any]) -> NodeResult:
        try:
            resolved_path = self._resolve_path_vars(self.path, context)
            ops = {
                "read": self._op_read,
                "write": self._op_write,
                "create_dir": self._op_create_dir,
                "delete": self._op_delete,
                "move": self._op_move,
            }
            handler = ops.get(self.operation_type)
            if not handler:
                raise ValueError(f"不支持的操作类型: {self.operation_type}")
            return handler(resolved_path, context) if self.operation_type in ("write", "move") else handler(resolved_path)
        except FileNotFoundError as e:
            logger.error(f"文件操作失败: {e}")
            return NodeResult.failed(f"文件不存在: {str(e)}")
        except PermissionError as e:
            logger.error(f"权限错误: {e}")
            return NodeResult.failed(f"无权限访问: {str(e)}")
        except Exception as e:
            logger.error(f"文件操作异常: {e}")
            return NodeResult.failed(f"操作失败: {str(e)}")
