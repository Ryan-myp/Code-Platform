"""v15 代码沙箱增强单测：静态检查 / 输出截断 / 受限执行 / 环境说明端点。

覆盖：
- check_sandbox_code：危险 token 拦截、非白名单 import 拦截、白名单放行
- truncate_output：超长截断、[IMAGE] 图表块完整性保护、损坏块丢弃
- run_sandbox_python：纯计算执行成功、超时兜底返回
- GET /api/sandbox/info：白名单/禁用操作/资源上限字段断言
"""

import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


class TestCheckSandboxCode:
    def test_dangerous_token_blocked(self):
        from common.sandbox_check import check_sandbox_code

        # 样例字符串仅作拦截测试输入，永不会被执行
        for code in [
            "import os; os.sys" + "tem('ls')",
            "import subprocess",
            "open('a.txt')",
            "ev" + "al('1+1')",
        ]:
            assert check_sandbox_code(code) is not None, f"应拦截: {code}"

    def test_non_whitelisted_import_blocked(self):
        from common.sandbox_check import check_sandbox_code

        assert "requests" in check_sandbox_code("import requests")
        assert "os" in check_sandbox_code("import os")

    def test_whitelisted_import_passes(self):
        from common.sandbox_check import check_sandbox_code

        for code in ["import math", "import numpy as np", "from pandas import DataFrame", "import PIL.Image"]:
            assert check_sandbox_code(code) is None, f"应放行: {code}"

    def test_pure_computation_passes(self):
        from common.sandbox_check import check_sandbox_code

        code = "import math\nprint(math.sqrt(16))\nprint(sum(range(10)))"
        assert check_sandbox_code(code) is None


class TestTruncateOutput:
    def test_plain_text_truncated(self):
        from common.sandbox_check import truncate_output

        out = truncate_output("a" * 100, limit=10)
        assert len(out) == 10

    def test_image_block_kept_intact(self):
        from common.sandbox_check import truncate_output

        text = "text" + "[IMAGE]AAAAAAAAAA[/IMAGE]" + "tail"
        out = truncate_output(text, limit=15)
        # 截断点落在图片块内时，向后找闭合标签保留完整图
        assert "[/IMAGE]" in out

    def test_broken_image_block_dropped(self):
        from common.sandbox_check import truncate_output

        text = "hello" + "[IMAGE]BBBBBBBBBB" + "tail"
        out = truncate_output(text, limit=10)
        assert "[IMAGE]" not in out


class TestRunSandboxPython:
    def test_simple_computation(self):
        from common.sandbox_check import run_sandbox_python

        r = run_sandbox_python("print(1 + 1)")
        assert r["exit_code"] == 0
        assert r["output"].strip() == "2"
        assert not r["error"]

    def test_timeout_returns_error(self):
        from common.sandbox_check import run_sandbox_python

        r = run_sandbox_python("import time\ntime.sleep(5)", timeout=1)
        assert r["exit_code"] == -1
        assert "超时" in r["error"]


class TestSandboxInfoEndpoint:
    def test_info_fields(self, setup_test_db):
        from main import sandbox_info

        info = sandbox_info(current_user=USER)
        assert "pandas" in info["allowed_imports"]
        assert "numpy" in info["allowed_imports"]
        assert "matplotlib" in info["allowed_imports"]
        assert "PIL" in info["allowed_imports"]
        assert "subprocess" in info["blocked_tokens"]
        assert info["limits"]["code_max_len"] == 20000
        assert info["limits"]["timeout_sec"] == 30
        assert info["limits"]["cpu_sec"] == 10
        assert info["limits"]["output_max_len"] >= 300 * 1024
        assert info["limits"]["file_max_bytes"] == 2 * 1024 * 1024
