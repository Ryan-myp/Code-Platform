"""v15 公共底座单测：common/safe_guard.py 统一异常兜底。

覆盖：
- async 函数：未预期异常 → HTTPException(500) 友好消息；业务 HTTPException 原样透传
- 同步函数：同样兜底
- 正常路径返回值不受影响
"""

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


@pytest.fixture(autouse=True)
def _silence_logger():
    import logging

    logging.getLogger("common.safe_guard").setLevel(logging.CRITICAL)
    yield


class TestSafeApi:
    def test_async_unexpected_error_becomes_500(self):
        from common.safe_guard import safe_api

        @safe_api
        async def boom():
            raise ValueError("磁盘写入失败")

        with pytest.raises(HTTPException) as ei:
            import asyncio

            asyncio.run(boom())
        assert ei.value.status_code == 500
        assert "磁盘写入失败" in ei.value.detail
        assert "服务异常" in ei.value.detail

    def test_http_exception_passthrough(self):
        from common.safe_guard import safe_api

        @safe_api
        async def biz():
            raise HTTPException(400, "参数不合法")

        with pytest.raises(HTTPException) as ei:
            import asyncio

            asyncio.run(biz())
        assert ei.value.status_code == 400
        assert ei.value.detail == "参数不合法"

    def test_async_success_returns_value(self):
        from common.safe_guard import safe_api

        @safe_api
        async def ok():
            return {"ok": True}

        import asyncio

        assert asyncio.run(ok()) == {"ok": True}

    def test_sync_unexpected_error_becomes_500(self):
        from common.safe_guard import safe_api

        @safe_api
        def boom():
            raise RuntimeError("内部错误")

        with pytest.raises(HTTPException) as ei:
            boom()
        assert ei.value.status_code == 500

    def test_sync_success_returns_value(self):
        from common.safe_guard import safe_api

        @safe_api
        def ok():
            return 42

        assert ok() == 42

    def test_original_metadata_preserved(self):
        from common.safe_guard import safe_api

        @safe_api
        async def named():
            return 1

        assert named.__name__ == "named"

    def test_safe_sync_exported(self):
        from common.safe_guard import safe_sync

        @safe_sync
        def boom():
            raise OSError("io")

        with pytest.raises(HTTPException) as ei:
            boom()
        assert ei.value.status_code == 500
