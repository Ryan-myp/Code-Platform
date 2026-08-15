"""AI 视频 / AI 形象网关测试：配置指引、扣费退费、云端任务全链路（mock 云端调用）。

覆盖 Phase 5.5 AI 视频商业化核心路径，不依赖真实云端 API Key 与网络。
注意：任务处理器在 worker 线程异步执行，mock 生命周期无法跨越（with 块退出即恢复），
故任务逻辑采用「直接调用 handler」单元级验证；接口层仅验证提交与扣费。
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

_CFG = {"api_key": "sk-test", "workspace_id": "ws-test"}


_CACHED_HEADERS: dict | None = None


def _login() -> dict:
    """登录并缓存 token（避免多次登录触发登录限流 5/min）。"""
    global _CACHED_HEADERS
    if _CACHED_HEADERS is not None:
        return _CACHED_HEADERS
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    _CACHED_HEADERS = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    return _CACHED_HEADERS


def _recharge(amount: float = 100.0) -> None:
    """管理员为 admin 充值（测试库初始余额 0）。"""
    resp = client.post(
        "/api/dh/billing/recharge",
        headers=_login(),
        json={"user_id": "admin_001", "amount": amount, "remark": "测试充值"},
    )
    assert resp.status_code == 200, resp.text


def _balance() -> float:
    from common.db import get_db_context

    with get_db_context() as conn:
        from dh_gateway import _ensure_billing_tables

        _ensure_billing_tables(conn)
        row = conn.execute("SELECT balance FROM users WHERE username='admin'").fetchone()
        return float(row["balance"] or 0) if row else 0.0


# ── 配置与定价 ────────────────────────────────────────────────


def test_config_reports_not_configured():
    """未配置 API Key 时：config 返回 configured=false + 定价。"""
    with patch("ai_video_api._config", return_value={"api_key": "", "workspace_id": ""}):
        resp = client.get("/api/ai-video/config", headers=_login())
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["pricing"]["text2video_720p"] == 5.0
    assert data["pricing"]["text2video_1080p"] == 10.0
    assert data["pricing"]["avatar_image"] == 1.0


def test_generate_without_config_returns_guidance():
    """网关未配置时提交任务：400 + 配置指引，且不扣费。

    v22.2：直接 mock _require_gateway 抛 400（网关检查已由该函数统一负责，
    避免测试环境真实 AGNES_API_KEY 非空导致检查被提前放行）。
    """
    from fastapi import HTTPException

    before = _balance()
    with patch(
        "ai_video_api._require_gateway",
        side_effect=HTTPException(
            400,
            "AI 视频网关未配置：请在 backend/.env 填写 AGNES_API_KEY（推荐，已配置），"
            "或 DASHSCOPE_API_KEY + DASHSCOPE_WORKSPACE_ID（阿里云百炼），联系平台管理员配置后重试",
        ),
    ):
        resp = client.post(
            "/api/ai-video/generate",
            headers=_login(),
            json={"mode": "text2video", "prompt": "一只小猫在月光下奔跑"},
        )
    assert resp.status_code == 400
    assert "DASHSCOPE_API_KEY" in resp.json()["detail"]
    assert abs(_balance() - before) < 0.001  # 未扣费


def test_invalid_upload_ref_rejected():
    """平台内引用的文件不存在：400 且不扣费。"""
    before = _balance()
    with patch("ai_video_api._config", return_value=_CFG):
        resp = client.post(
            "/api/ai-video/generate",
            headers=_login(),
            json={"mode": "image2video", "prompt": "产品宣传视频", "image_url": "/uploads/videos/not_exist.jpg"},
        )
    assert resp.status_code == 400
    assert "不存在" in resp.json()["detail"]
    assert abs(_balance() - before) < 0.001


# ── 接口提交与扣费 ────────────────────────────────────────────


def test_submit_charges_and_creates_task():
    """提交任务：200 + 扣费 5 元 + 返回 task_id（任务异步执行，不在此验证结果）。"""
    _recharge()
    before = _balance()
    with patch("ai_video_api._config", return_value=_CFG):
        resp = client.post(
            "/api/ai-video/generate",
            headers=_login(),
            json={"mode": "text2video", "prompt": "一只小猫在月光下奔跑", "duration": 5},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["task_id"].startswith("task_")
    assert data["price"] == 5.0
    assert abs(_balance() - before + 5.0) < 0.001  # 已扣 5 元


def test_submit_insufficient_balance_rejected():
    """余额不足：402 拒绝，不创建任务。"""
    with patch("ai_video_api._config", return_value=_CFG):
        resp = client.post(
            "/api/ai-video/generate",
            headers=_login(),
            json={"mode": "text2video", "prompt": "余额不足测试内容", "duration": 5},
        )
    assert resp.status_code == 402
    assert "余额不足" in resp.json()["detail"]


# ── 任务处理器逻辑（直接调用，mock 云端） ─────────────────────


def _run_handler(fn, payload: dict, ctx: dict | None = None):
    """直接调用任务处理器（同步执行，mock 在 with 块内生效）。"""
    progress = []
    result = fn("task_test", payload, lambda p, s: progress.append((p, s)), ctx or {})
    return result, progress


def test_handler_ai_video_success():
    """文生视频处理器：提交→轮询→下载→结果含 video_url。"""
    _recharge()
    submitted = {}

    def fake_submit(payload: dict) -> str:
        submitted["payload"] = payload
        return "cloud_task_001"

    def fake_query(tid: str) -> dict:
        return {"status": "SUCCEEDED", "video_url": "https://cdn.example.com/v.mp4", "image_url": "", "error": ""}

    def fake_download(url: str, dest: str) -> str:
        with open(dest, "wb") as f:
            f.write(b"\x00" * 2048)
        return dest

    import ai_video_api

    with (
        patch("ai_video_api._config", return_value=_CFG),
        patch("ai_video_api._agnes_available", return_value=False),  # 强制走百炼通道（测试 mock 该通道）
        patch("ai_video_api._submit_cloud", side_effect=fake_submit),
        patch("ai_video_api._query_cloud", side_effect=fake_query),
        patch("ai_video_api._download", side_effect=fake_download),
        patch("ai_video_api.time.sleep", return_value=None),
    ):
        result, progress = _run_handler(
            ai_video_api._ai_video_handler,
            {"billing_id": "b_test", "price": 5.0, "mode": "text2video", "prompt": "一只小猫在月光下奔跑", "duration": 5, "resolution": "720p", "aspect_ratio": "16:9", "image_url": "", "audio_url": ""},
        )
    assert result["status"] == "done"
    assert result["video_url"].startswith("/uploads/videos/ai_")
    assert result["mode"] == "text2video"
    assert submitted["payload"]["model"] == "kling/kling-v3-video-generation"
    assert submitted["payload"]["parameters"]["duration"] == 5
    assert submitted["payload"]["parameters"]["watermark"] is False
    assert progress[0][0] == 5  # 首条进度事件


def test_handler_lipsync_uses_omni_model():
    """口型同步模式：omni 模型 + audio_url 透传。"""

    def fake_submit(payload: dict) -> str:
        assert payload["model"] == "kling/kling-v3-omni-video-generation"
        assert "audio_url" in payload["input"]
        return "cloud_omni"

    def fake_query(tid: str) -> dict:
        return {"status": "SUCCEEDED", "video_url": "https://cdn.example.com/v.mp4", "image_url": "", "error": ""}

    def fake_download(url: str, dest: str) -> str:
        with open(dest, "wb") as f:
            f.write(b"\x00" * 2048)
        return dest

    import ai_video_api

    with (
        patch("ai_video_api._config", return_value=_CFG),
        patch("ai_video_api._agnes_available", return_value=False),  # 强制走百炼通道
        patch("ai_video_api._submit_cloud", side_effect=fake_submit),
        patch("ai_video_api._query_cloud", side_effect=fake_query),
        patch("ai_video_api._download", side_effect=fake_download),
        patch("ai_video_api.time.sleep", return_value=None),
    ):
        result, _ = _run_handler(
            ai_video_api._ai_video_handler,
            {"billing_id": "b_lip", "price": 5.0, "mode": "lipsync", "prompt": "口播演示", "duration": 5, "resolution": "720p", "aspect_ratio": "16:9", "image_url": "/uploads/dh_avatars/x.jpg", "audio_url": "https://cdn.example.com/a.mp3"},
        )
    assert result["status"] == "done"


def test_handler_ai_video_failure_refunds():
    """云端失败：handler 抛异常 + 自动退费。"""
    before = _balance()
    refunded = []

    def fake_query(tid: str) -> dict:
        return {"status": "FAILED", "video_url": "", "image_url": "", "error": "内容审核未通过"}

    import ai_video_api

    with (
        patch("ai_video_api._config", return_value=_CFG),
        patch("ai_video_api._agnes_available", return_value=False),  # 强制走百炼通道
        patch("ai_video_api._submit_cloud", return_value="cloud_fail"),
        patch("ai_video_api._query_cloud", side_effect=fake_query),
        patch("ai_video_api.time.sleep", return_value=None),
        patch("ai_video_api._refund", side_effect=lambda bid: refunded.append(bid)),
    ):
        try:
            _run_handler(
                ai_video_api._ai_video_handler,
                {"billing_id": "b_refund", "price": 5.0, "mode": "text2video", "prompt": "测试失败内容", "duration": 5, "resolution": "720p", "aspect_ratio": "16:9", "image_url": "", "audio_url": ""},
            )
            raise AssertionError("应当抛出异常")
        except RuntimeError as e:
            assert "审核" in str(e)
    assert refunded == ["b_refund"]  # 已退费
    assert abs(_balance() - before) < 0.001


def test_handler_ai_avatar_image_success():
    """AI 形象处理器：云端成功 → 创建照片数字人形象 → 返回 avatar_id。"""
    _recharge()
    submitted = {}

    def fake_submit(payload: dict) -> str:
        submitted["payload"] = payload
        return "cloud_img_001"

    def fake_query(tid: str) -> dict:
        return {"status": "SUCCEEDED", "video_url": "", "image_url": "https://cdn.example.com/a.jpg", "error": ""}

    def fake_download(url: str, dest: str) -> str:
        import base64

        jpg = base64.b64decode(
            "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAH/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oACAEBAAEFAqf/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAEDAQE/AR//xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oACAECAQE/AR//2gAMAwEAAgADAAAAEP/EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABQQAQAAAAAAAAAAAAAAAAAAABD/2gAIAQEAAT8QH//Z"
        )
        with open(dest, "wb") as f:
            f.write(jpg)
        return dest

    import ai_video_api

    with (
        patch("ai_video_api._config", return_value=_CFG),
        patch("ai_video_api._submit_cloud", side_effect=fake_submit),
        patch("ai_video_api._query_cloud", side_effect=fake_query),
        patch("ai_video_api._download", side_effect=fake_download),
        patch("ai_video_api.time.sleep", return_value=None),
    ):
        result, _ = _run_handler(
            ai_video_api._ai_avatar_image_handler,
            {"billing_id": "b_img", "price": 1.0, "prompt": "一位 30 岁中国女性职场精英，正脸，证件照风格，高清", "name": "AI 职业女性"},
            ctx={"username": "admin"},
        )
    assert result["status"] == "done"
    assert result["avatar_id"].startswith("custom_")
    assert result["image_url"].startswith("/uploads/dh_avatars/")
    assert submitted["payload"]["model"] == "wanx2.1-t2i-turbo"
    # 形象已落库
    from common.db import get_db_context

    with get_db_context() as conn:
        row = conn.execute(
            "SELECT style, user_id FROM digital_human_custom_avatars WHERE id=?", (result["avatar_id"],)
        ).fetchone()
        assert row and row["style"] == "照片数字人" and row["user_id"] == "admin"
