"""API调用节点——通过HTTP请求调用外部RESTful API服务

适用场景：
- 获取天气数据查询天气API
- 调用支付网关完成交易
- 向Slack/钉钉发送通知
- 查询CRM系统客户信息
- 与任何支持HTTP接口的系统集成
"""

import json
import logging
from typing import Any

import requests

from ..base import BusinessNode, NodeResult, RequiredFieldsValidator, TypeValidator

logger = logging.getLogger(__name__)


class APINode(BusinessNode):
    """HTTP API调用节点——封装对外部服务的调用

    支持的所有HTTP方法: GET, POST, PUT, PATCH, DELETE, OPTIONS

    配置示例:
        api_node = APINode(
            node_id="notify_slack",
            method="POST",
            url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
            headers={"Content-Type": "application/json"},
            body_field="message",  # 从context中取message字段作为body
            auth_token="slack-webhook-token"
        )
    """

    VALID_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}

    def __init__(
        self,
        node_id: str,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body_field: str | None = None,
        auth_token: str | None = None,
        timeout: int = 30,
        input_schema: dict[str, Any] | None = None,
        validators: Any | None = None,
    ):

        method_upper = method.upper()
        if method_upper not in self.VALID_METHODS:
            raise ValueError(f"不支持的HTTP方法: {method}. 必须是: {self.VALID_METHODS}")

        super().__init__(node_id, f"API节点({method_upper})", f"调用URL: {url}")

        self.method = method_upper
        self.url = url
        self.headers = headers or {}
        self.body_field = body_field
        self.auth_token = auth_token
        self.timeout = timeout

        # 默认输入验证（如果有body_field，需要该字段存在）
        default_validators = []
        if body_field:
            default_validators.append(RequiredFieldsValidator([body_field]))
            default_validators.append(TypeValidator({body_field: (str, dict, list)}))

        if validators:
            default_validators.extend(validators)

        self.validators = default_validators

    def _build_request_body(self, context: dict[str, Any]) -> Any:
        """构建HTTP请求体"""
        if self.body_field and self.body_field in context.get("inputs", {}):
            return context["inputs"][self.body_field]

        # 如果没有指定body_field，使用整个输入上下文（转换为JSON可序列化格式）
        inputs = context.get("inputs", {})
        # 排除非JSON序列化的值
        serializable_inputs = {}
        for k, v in inputs.items():
            try:
                json.dumps(v)
                serializable_inputs[k] = v
            except (TypeError, ValueError):
                pass

        return serializable_inputs if serializable_inputs else None

    def _build_headers(self, context: dict[str, Any]) -> dict[str, str]:
        """构建HTTP请求头，支持变量替换"""
        headers = dict(self.headers)

        # 替换 {outputs.node.field} 等占位符
        outputs = context.get("outputs", {})
        for node_id, output_val in outputs.items():
            if isinstance(output_val, dict):
                for key, val in output_val.items():
                    placeholder = f"{{outputs.{node_id}.{key}}}"
                    if placeholder in headers.get("", ""):
                        headers[key.replace("placeholder", str(val))] = str(val)
                    # 简单的字符串替换
                    headers = {k.replace(f"{{{node_id}.{key}}}", str(val)) for k, v in headers.items()}

        # 添加认证头
        if self.auth_token:
            headers.setdefault("Authorization", f"Bearer {self.auth_token}")

        # 设置默认的Content-Type
        if "Content-Type" not in headers and self.method in ("POST", "PUT", "PATCH"):
            headers["Content-Type"] = "application/json"

        return headers

    def execute(self, context: dict[str, Any]) -> NodeResult:
        try:
            request_body = self._build_request_body(context)
            request_headers = self._build_headers(context)

            logger.info(f"发起{self.method}请求: {self.url}")

            resp = requests.request(
                method=self.method,
                url=self.url,
                data=json.dumps(request_body) if request_body else None,
                headers=request_headers,
                timeout=self.timeout,
                verify=True,  # 生产环境建议保持True
            )

            # 解析响应
            try:
                response_data = resp.json()
            except json.JSONDecodeError:
                response_data = resp.text

            logger.log(20 if resp.ok else 400, f"API调用完成, 状态码={resp.status_code}, 长度={len(response_data)}")

            return NodeResult.success(
                output={
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "content": response_data if isinstance(response_data, str) else response_data,
                    "elapsed": resp.elapsed.total_seconds() if resp.elapsed else None,
                },
                messages=[f"成功调用 {self.method} {self.url[:60]}..."],
            )

        except requests.exceptions.Timeout:
            error_msg = f"API请求超时 (timeout={self.timeout}s)"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)
        except requests.exceptions.ConnectionError as e:
            error_msg = f"连接失败: {str(e)}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误 {e.response.status_code if e.response else 'unknown'}: {e}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)
        except Exception as e:
            error_msg = f"API调用异常: {str(e)}"
            logger.error(error_msg)
            return NodeResult.failed(error_msg)

