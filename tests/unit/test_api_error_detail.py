"""api_error_detail：外部 API 错误详情提取（可读性兜底）。"""

import json

import requests

from common.llm import api_error_detail


def _make_resp(status: int, body, is_json: bool = True) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    if is_json:
        resp.headers["Content-Type"] = "application/json"
        resp._content = json.dumps(body).encode("utf-8")
    else:
        resp._content = body.encode("utf-8") if isinstance(body, str) else body
    return resp


def _http_error(status: int, body, is_json: bool = True) -> requests.HTTPError:
    return requests.HTTPError(f"{status} Client Error", response=_make_resp(status, body, is_json))


class TestApiErrorDetail:
    def test_extract_message_and_code(self):
        exc = _http_error(400, {"error": {"message": "Model X is a chat model", "code": "invalid_request"}})
        msg = api_error_detail(exc)
        assert "HTTP 400" in msg
        assert "Model X is a chat model" in msg
        assert "invalid_request" in msg

    def test_content_policy_violation_hint(self):
        exc = _http_error(
            400, {"error": {"message": "Unable to generate this content.", "code": "content_policy_violation"}}
        )
        msg = api_error_detail(exc)
        assert "HTTP 400" in msg
        assert "content_policy_violation" in msg
        assert "平台受限内容" in msg

    def test_plain_text_body(self):
        exc = _http_error(502, "upstream timeout", is_json=False)
        msg = api_error_detail(exc)
        assert "HTTP 502" in msg
        assert "upstream timeout" in msg

    def test_error_without_response_falls_back_to_str(self):
        exc = ValueError("boom")
        assert api_error_detail(exc) == "boom"

    def test_http_error_without_response(self):
        exc = requests.HTTPError("400 Client Error for url")
        assert api_error_detail(exc) == "400 Client Error for url"

    def test_empty_str_exception_gets_fallback(self):
        class BlankError(Exception):
            def __str__(self):
                return ""

        msg = api_error_detail(BlankError())
        assert "连接异常" in msg or "BlankError" in msg

    def test_message_only_without_code(self):
        exc = _http_error(401, {"message": "unauthorized"})
        msg = api_error_detail(exc)
        assert "HTTP 401" in msg
        assert "unauthorized" in msg
