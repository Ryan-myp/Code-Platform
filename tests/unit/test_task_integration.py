"""业务模块 × 异步任务框架 接入验证。

覆盖：
- 各业务模块（游戏/小程序/视频/音乐/梗图/图片/语音/数字人）的 handler 均已注册
- 对每个 task type 均可 create_task 成功（payload 透传）
- async handler 支持：worker 内 asyncio.run 执行并落库结果
- 图片工厂文件字段：sync base64 / async file:// 临时路径 往返一致且用完即删
- 用户级并发限制（register_handler user_limit）：超出抛 429
"""
import asyncio
import os

import pytest
from fastapi import HTTPException

from task_queue import (
    _handlers,
    create_task,
    get_task,
    register_handler,
)

# 预期注册的业务任务类型（各 factory 模块顶层注册）
EXPECTED_TASK_TYPES = {
    "game_generate", "game_evolve",
    "miniapp_generate",
    "video_generate",
    "music_lyrics", "music_sing",
    "meme_generate",
    "image_t2i", "image_i2i", "image_template", "image_tryon",
    "voice_generate",
    "dh_generate",
}


def _import_business_modules():
    """导入全部业务模块触发 register_handler（main.py 已做同样导入，测试环境可安全导入）。"""
    import importlib

    for mod in (
        "game_factory", "miniapp", "video_factory", "music_factory",
        "meme_factory", "image_factory", "voice_factory", "digital_human",
    ):
        importlib.import_module(mod)


def test_all_business_handlers_registered(setup_test_db):
    """各业务模块顶层注册的 task type 必须全部可用。"""
    _import_business_modules()
    missing = EXPECTED_TASK_TYPES - set(_handlers)
    assert not missing, f"未注册的业务任务类型: {missing}"


def test_create_task_for_each_business_type(setup_test_db):
    """每个业务 task type 均可创建任务：pending 入队、payload 原样保存。"""
    _import_business_modules()
    for ttype in sorted(EXPECTED_TASK_TYPES):
        payload = {"probe": ttype, "project_id": "p-test"}
        task = create_task(ttype, payload, username="alice", user_id="u1", role="user")
        assert task["status"] == "pending", ttype
        got = get_task(task["id"])
        assert got["payload"] == payload, ttype
        assert got["created_by"] == "alice"


def test_user_limit_exceeded_raises_429(setup_test_db, claim_and_run):
    """user_limit 并发限制：同用户第 2 个活跃任务创建被拒绝。"""
    register_handler("tq_limit", lambda task_id, payload, update, ctx: {"ok": True}, user_limit=1)
    t1 = create_task("tq_limit", {}, username="alice")
    with pytest.raises(HTTPException) as exc:
        create_task("tq_limit", {}, username="alice")
    assert exc.value.status_code == 429
    # 不同用户不受限
    create_task("tq_limit", {}, username="bob")
    # 活跃任务完成后可再次创建（alice 第 1 个任务完成）
    claim_and_run(t1["id"])
    assert get_task(t1["id"])["status"] == "success"
    create_task("tq_limit", {}, username="alice")


def test_async_handler_executed_via_asyncio_run(setup_test_db, claim_and_run):
    """async 处理器（协程返回）在 worker 内被 asyncio.run 执行，结果正确落库。"""
    async def handler(task_id, payload, update, ctx):
        await asyncio.sleep(0.01)
        update(50, "异步阶段")
        return {"async_ok": True, "v": payload.get("v")}
    register_handler("tq_async", handler)
    task = create_task("tq_async", {"v": 7}, username="alice")
    claim_and_run(task["id"])
    got = get_task(task["id"])
    assert got["status"] == "success"
    assert got["result"] == {"async_ok": True, "v": 7}
    assert got["progress"] == 100
    assert got["stage"] == "生成完成"


def test_async_handler_failure_records_error(setup_test_db, claim_and_run):
    """async 处理器内抛 HTTPException：error_code 记录、状态 failed。"""
    async def handler(task_id, payload, update, ctx):
        raise HTTPException(402, "余额不足")
    register_handler("tq_async_fail", handler)
    task = create_task("tq_async_fail", {}, username="alice")
    claim_and_run(task["id"])
    got = get_task(task["id"])
    assert got["status"] == "failed"
    assert got["error_code"] == 402
    assert "余额不足" in got["error"]


def test_image_file_field_tmp_roundtrip(setup_test_db):
    """图片工厂文件字段：async 模式写 file:// 临时路径，worker 读取后即删。"""
    from image_factory import _read_file_field, _write_file_field
    content = b"\x89PNG\r\n\x1a\n" + os.urandom(128)
    tmp_ref = asyncio.run(_write_file_field(content))
    assert tmp_ref.startswith("file://")
    path = tmp_ref[len("file://"):]
    assert os.path.exists(path)
    # 读取后临时文件被删除
    assert _read_file_field({"image": tmp_ref}, "image") == content
    assert not os.path.exists(path)
    # base64（sync 模式）读取
    import base64
    assert _read_file_field({"image": base64.b64encode(content).decode()}, "image") == content
    # 缺失字段返回 None
    assert _read_file_field({"image": ""}, "image") is None
