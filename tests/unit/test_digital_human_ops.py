"""数字人生产运营链路集成测试（商业化 P0）：批量任务持久化/限流/重试/单条并发。

使用 mock 替换 TTS 与渲染，验证 worker 全链路逻辑（落库/状态流转/资源保护），
不依赖外部网络与 ffmpeg。
"""

import threading
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


_QUICK_TTS_BYTES = None


def _quick_tts(*args, **kwargs):
    """假 TTS：进程内用 ffmpeg 生成一次有效 mp3（2s 正弦波），后续复用。

    有效音频才能通过 _render_video 的 ffprobe 时长检查（真实渲染链路测试需要），
    纯 mp3 帧头（0xFFFB）会被 ffprobe 判为无效数据。
    """
    global _QUICK_TTS_BYTES
    if _QUICK_TTS_BYTES is None:
        import os
        import subprocess
        import tempfile

        tmp = tempfile.mktemp(suffix=".mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=2", "-ar", "22050", tmp],
            capture_output=True,
            check=True,
        )
        with open(tmp, "rb") as f:
            _QUICK_TTS_BYTES = f.read()
        os.unlink(tmp)
    return _QUICK_TTS_BYTES


def _fake_render(*args, **kwargs):
    """假渲染：写一个真实小文件到 output_path（download 可打包）。"""
    with open(kwargs["output_path"], "wb") as f:
        f.write(b"FAKE_MP4" * 64)


class TestBatchPipeline:
    """批量任务全链路：创建 → 落库 → worker 逐条 → done → 持久化查询。"""

    def _create(self, auth_headers, texts, expect=200):
        resp = client.post(
            "/api/digital-human/batch",
            json={"texts": texts},
            headers=auth_headers,
        )
        assert resp.status_code == expect, resp.text
        return resp.json()

    def _wait_done(self, auth_headers, batch_id, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = client.get(f"/api/digital-human/batch/{batch_id}", headers=auth_headers)
            assert resp.status_code == 200, resp.text
            task = resp.json()
            if task["status"] != "running":
                return task
            time.sleep(0.2)
        raise AssertionError(f"batch {batch_id} 未在 {timeout}s 内完成")

    def test_full_pipeline_success_and_blocked_word(self, auth_headers):
        with (
            patch("voice_factory._tts_one", side_effect=_quick_tts),
            patch("digital_human._render_video", side_effect=_fake_render),
        ):
            task = self._create(auth_headers, ["大家好，今天分享一个效率技巧", "点击领取免费大礼包"])
            done = self._wait_done(auth_headers, task["batch_id"])
        assert done["status"] == "done"
        assert done["total"] == 2
        assert done["success"] == 1 and done["failed"] == 1
        items = {i["index"]: i for i in done["items"]}
        assert items[0]["status"] == "success" and items[0]["video_url"]
        assert items[1]["status"] == "failed" and "违规词" in items[1]["error"]
        # 持久化兜底：清掉内存缓存后仍能从 DB 恢复
        import digital_human

        with patch.dict(digital_human._BATCH_TASKS, {}, clear=True):
            resp = client.get(f"/api/digital-human/batch/{task['batch_id']}", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "done"

    def test_running_limit_rejects_third(self, auth_headers):
        """运行中批量任务 ≥2 时第 3 个被拒（资源保护）。"""
        with (
            patch("voice_factory._tts_one", side_effect=_quick_tts),
            patch("digital_human._render_video", side_effect=_fake_render),
            patch("digital_human._batch_worker") as mock_worker,
        ):
            # 冻结 worker：任务保持 running，便于测限流
            def _freeze(*a, **k):
                time.sleep(5)

            mock_worker.side_effect = _freeze
            self._create(auth_headers, ["大家好，第一条测试文案"])
            self._create(auth_headers, ["大家好，第二条测试文案"])
            self._create(auth_headers, ["大家好，第三条测试文案"], expect=400)

    def test_retry_failed_retries_only_fixable(self, auth_headers):
        """重试失败项：非内容问题失败可重试并成功，违规词不进入重试。"""
        with (
            patch("voice_factory._tts_one", side_effect=_quick_tts),
            patch("digital_human._render_video", side_effect=_fake_render),
        ):
            task = self._create(auth_headers, ["点击领取大礼包", "大家好，第二条测试文案"])
            done = self._wait_done(auth_headers, task["batch_id"])
        assert done["failed"] == 1  # 违规词项
        # 无失败项可重试（内容问题）→ 400
        resp = client.post(f"/api/digital-human/batch/{task['batch_id']}/retry-failed", headers=auth_headers)
        assert resp.status_code == 400
        assert "内容问题" in resp.json()["detail"]

    def test_retry_failed_with_real_failure(self, auth_headers):
        """偶发失败（渲染异常）重试：先失败 → 重试成功。"""
        import digital_human

        real_render = digital_human._render_video

        def _flaky_render(**kwargs):
            # _generate_one 内置自动重试 1 次：连续失败 2 次才真正落 failed
            if getattr(_flaky_render, "failed", 0) < 2:
                _flaky_render.failed = getattr(_flaky_render, "failed", 0) + 1
                raise RuntimeError("模拟渲染进程崩溃")
            real_render(**kwargs)

        with (
            patch("voice_factory._tts_one", side_effect=_quick_tts),
            patch("digital_human._render_video", side_effect=_flaky_render),
        ):
            task = self._create(auth_headers, ["大家好，渲染会失败一次再成功"])
            done = self._wait_done(auth_headers, task["batch_id"])
        assert done["status"] == "done"
        assert done["failed"] == 1, done
        # 重试失败项 → running → 成功
        resp = client.post(f"/api/digital-human/batch/{task['batch_id']}/retry-failed", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["retrying"] == 1
        retried = self._wait_done(auth_headers, task["batch_id"])
        assert retried["status"] == "done"
        assert retried["success"] == 1 and retried["failed"] == 0

    def test_batch_access_denied_for_other_user(self, auth_headers):
        """批量任务仅创建者可查（越权 404）。"""
        with (
            patch("voice_factory._tts_one", side_effect=_quick_tts),
            patch("digital_human._render_video", side_effect=_fake_render),
        ):
            task = self._create(auth_headers, ["大家好，仅创建者可见"])
            self._wait_done(auth_headers, task["batch_id"])
        # 注册另一个用户
        client.post(
            "/api/auth/register", json={"username": "bob_ops", "password": "bob123456", "email": "bob@test.com"}
        )
        login = client.post("/api/auth/login", json={"username": "bob_ops", "password": "bob123456"})
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        resp = client.get(f"/api/digital-human/batch/{task['batch_id']}", headers=other_headers)
        assert resp.status_code == 404


class TestSingleGenerateConcurrency:
    """单条生成用户级并发限制：同用户同时 2 个请求 → 1 个 200、1 个 429。"""

    def test_concurrent_generate_second_rejected(self, auth_headers):
        with (
            patch("voice_factory._tts_one", side_effect=_quick_tts),
            patch("digital_human._render_video", side_effect=_fake_render),
            patch("digital_human._generate_one") as mock_gen,
        ):

            def _slow(*a, **k):
                time.sleep(1.5)
                return {
                    "record_id": "x",
                    "audio_url": "",
                    "video_url": "",
                    "watermark": False,
                    "sensitive_warning": "",
                    "status": "done",
                    "error": "",
                    "message": "ok",
                    "quota_remaining": 99,
                    "text_length": 10,
                }

            mock_gen.side_effect = _slow
            payload = {"text": "大家好，并发测试文案"}
            results = {}

            def _call():
                r = client.post("/api/digital-human/generate", json=payload, headers=auth_headers)
                results[r.status_code] = results.get(r.status_code, 0) + 1

            t1 = threading.Thread(target=_call)
            t2 = threading.Thread(target=_call)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        assert results.get(200) == 1, results
        assert results.get(429) == 1, results
