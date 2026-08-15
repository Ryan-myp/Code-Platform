"""v15 视频工厂增强单测：脚本文案模板库 + 批量转码。

覆盖：
- SCRIPT_TEMPLATES：9 条模板 3 分类，字段齐全，{主题} 占位符可替换
- GET /prompts/scripts 端点返回模板库
- build_transcode_plan：数量/文件名/宽高成对/CRF clamp/分辨率边界/输出名唯一
- POST /tools/transcode：存在性校验、命令组装、逐项成功/失败报告
"""

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"username": "tester"}


@pytest.fixture(autouse=True)
def _isolated_video_dir(monkeypatch, tmp_path):
    """VIDEO_DIR 指向临时目录，避免污染真实产物目录。"""
    import video_factory

    monkeypatch.setattr(video_factory, "VIDEO_DIR", tmp_path)
    return tmp_path


def _seed_video(tmp_path, name="demo.mp4", size=1024):
    (tmp_path / name).write_bytes(b"\x00" * size)
    return name


class _FakeProc:
    def __init__(self, returncode, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def _make_fake_run(fail_sources=(), recorded=None):
    """打桩 subprocess.run：失败源写出错误，其余写出目标文件并返回成功。"""

    def fake_run(cmd, **kwargs):
        if recorded is not None:
            recorded.append(cmd)
        src = cmd[cmd.index("-i") + 1]
        if Path(src).name in fail_sources:
            return _FakeProc(1, "ffmpeg error: boom")
        Path(cmd[-1]).write_bytes(b"fake mp4")
        return _FakeProc(0)

    return fake_run


class TestScriptTemplates:
    """脚本文案模板库：结构完整且可直接替换主题。"""

    def test_template_count_and_categories(self):
        from video_factory import SCRIPT_TEMPLATES

        assert len(SCRIPT_TEMPLATES) == 9
        cats = {t["category"] for t in SCRIPT_TEMPLATES}
        assert cats == {"口播", "剧情", "科普"}
        # 每类 3 条
        from collections import Counter

        assert Counter(t["category"] for t in SCRIPT_TEMPLATES) == {"口播": 3, "剧情": 3, "科普": 3}

    def test_template_fields(self):
        from video_factory import SCRIPT_TEMPLATES

        for t in SCRIPT_TEMPLATES:
            assert {"id", "category", "name", "title", "structure", "desc"} <= set(t)
            assert len(t["structure"]) >= 4  # 分镜结构
            assert all(isinstance(s, str) and s for s in t["structure"])

    def test_topic_placeholder_replaceable(self):
        from video_factory import SCRIPT_TEMPLATES

        # 模板至少有一条分镜含 {主题} 占位符，替换后不留残留
        t = SCRIPT_TEMPLATES[0]
        assert any("{主题}" in s for s in t["structure"])
        title = t["title"].replace("{主题}", "智能音箱")
        assert "{主题}" not in title and "智能音箱" in title
        filled = [s.replace("{主题}", "智能音箱") for s in t["structure"]]
        assert all("{主题}" not in s for s in filled)
        assert any("智能音箱" in s for s in filled)

    def test_scripts_endpoint(self):
        from video_factory import get_script_templates

        resp = asyncio.run(get_script_templates())
        # v20 扩展：原 9 套（口播/剧情/科普）+ 7 套（Vlog/广告/教程/音乐/测评）
        assert len(resp["templates"]) >= 9
        cats = {t["category"] for t in resp["templates"]}
        assert "口播" in cats
        assert "Vlog" in cats
        assert "广告" in cats


class TestBuildTranscodePlan:
    """转码计划纯函数：参数校验与规范化。"""

    def test_empty_raises(self):
        from video_factory import build_transcode_plan

        with pytest.raises(ValueError):
            build_transcode_plan([])
        with pytest.raises(ValueError):
            build_transcode_plan([""])

    def test_batch_limit(self):
        from video_factory import build_transcode_plan

        names = [f"v{i}.mp4" for i in range(11)]
        with pytest.raises(ValueError, match="最多转码"):
            build_transcode_plan(names)

    def test_bad_filename(self):
        from video_factory import build_transcode_plan

        with pytest.raises(ValueError, match="非法"):
            build_transcode_plan(["../escape.mp4"])
        with pytest.raises(ValueError, match="非法"):
            build_transcode_plan([".hidden.mp4"])

    def test_size_must_pair(self):
        from video_factory import build_transcode_plan

        with pytest.raises(ValueError, match="成对"):
            build_transcode_plan(["a.mp4"], width=1280)
        with pytest.raises(ValueError, match="成对"):
            build_transcode_plan(["a.mp4"], height=720)

    def test_resolution_range(self):
        from video_factory import build_transcode_plan

        with pytest.raises(ValueError, match="分辨率"):
            build_transcode_plan(["a.mp4"], width=8, height=8)
        with pytest.raises(ValueError, match="分辨率"):
            build_transcode_plan(["a.mp4"], width=8000, height=720)

    def test_crf_clamp(self):
        from video_factory import build_transcode_plan

        assert build_transcode_plan(["a.mp4"], crf=5)[0]["crf"] == 18
        assert build_transcode_plan(["a.mp4"], crf=99)[0]["crf"] == 35
        assert build_transcode_plan(["a.mp4"], crf=0)[0]["crf"] == 23  # 0 视为未指定 → 默认
        assert build_transcode_plan(["a.mp4"])[0]["crf"] == 23

    def test_plan_structure_with_size(self):
        from video_factory import build_transcode_plan

        plan = build_transcode_plan(["a.mp4", "b.mp4"], width=1280, height=720, crf=28)
        assert len(plan) == 2
        p = plan[0]
        assert p["source"] == "a.mp4"
        assert p["output"].startswith("a_enc_") and p["output"].endswith(".mp4")
        assert p["width"] == 1280 and p["height"] == 720
        assert "pad=1280:720" in p["scale"] and "format=yuv420p" in p["scale"]

    def test_plan_keep_resolution(self):
        from video_factory import build_transcode_plan

        p = build_transcode_plan(["a.mp4"])[0]
        assert p["width"] is None and p["height"] is None
        assert p["scale"] == "format=yuv420p"

    def test_output_names_unique(self):
        from video_factory import build_transcode_plan

        plan = build_transcode_plan(["clip.mp4", "clip.mp4", "clip2.mp4"])
        outs = [p["output"] for p in plan]
        assert len(outs) == len(set(outs))  # 同批内唯一


class TestTranscodeEndpoint:
    """批量转码端点：校验、命令组装与逐项报告。"""

    def test_missing_file_404(self, tmp_path):
        import video_factory

        with pytest.raises(HTTPException) as e:
            asyncio.run(video_factory.transcode_videos(filenames="no_such.mp4", width=0, height=0, crf=23, current_user=USER))
        assert e.value.status_code == 404

    def test_too_many_400(self, tmp_path):
        import video_factory

        names = [_seed_video(tmp_path, f"v{i}.mp4") for i in range(11)]
        with pytest.raises(HTTPException) as e:
            asyncio.run(video_factory.transcode_videos(filenames=",".join(names), width=0, height=0, crf=23, current_user=USER))
        assert e.value.status_code == 400

    def test_success_all(self, tmp_path, monkeypatch):
        import video_factory

        _seed_video(tmp_path, "a.mp4")
        _seed_video(tmp_path, "b.mp4")
        monkeypatch.setattr(video_factory, "_probe_has_audio", lambda p: False)
        monkeypatch.setattr(video_factory, "_pick_ffmpeg", lambda: "ffmpeg")
        monkeypatch.setattr(video_factory, "_pick_video_encoder", lambda: "libx264")
        recorded = []
        monkeypatch.setattr(sys.modules["subprocess"], "run", _make_fake_run(recorded=recorded))

        resp = asyncio.run(
            video_factory.transcode_videos(filenames="a.mp4,b.mp4", width=1280, height=720, crf=99, current_user=USER)
        )
        assert resp["total"] == 2 and resp["ok"] == 2 and resp["failed"] == 0
        assert all(r["status"] == "ok" for r in resp["results"])
        assert resp["results"][0]["url"].startswith("/api/video-factory/videos/")
        assert resp["results"][0]["crf"] == 35  # crf=99 clamp 到 35
        assert resp["results"][0]["width"] == 1280
        # 命令组装：-vf 缩放 + -crf + 无音轨 -an
        cmd = recorded[0]
        assert "-vf" in cmd and "pad=1280:720" in cmd[cmd.index("-vf") + 1]
        assert cmd[cmd.index("-crf") + 1] == "35"
        assert "-an" in cmd

    def test_partial_failure(self, tmp_path, monkeypatch):
        import video_factory

        _seed_video(tmp_path, "a.mp4")
        _seed_video(tmp_path, "b.mp4")
        monkeypatch.setattr(video_factory, "_probe_has_audio", lambda p: True)  # 有音轨 → -c:a aac
        monkeypatch.setattr(video_factory, "_pick_ffmpeg", lambda: "ffmpeg")
        monkeypatch.setattr(video_factory, "_pick_video_encoder", lambda: "libx264")
        recorded = []
        monkeypatch.setattr(sys.modules["subprocess"], "run", _make_fake_run(fail_sources={"b.mp4"}, recorded=recorded))

        resp = asyncio.run(video_factory.transcode_videos(filenames="a.mp4,b.mp4", width=0, height=0, crf=23, current_user=USER))
        assert resp["total"] == 2 and resp["ok"] == 1 and resp["failed"] == 1
        ok_item = next(r for r in resp["results"] if r["status"] == "ok")
        err_item = next(r for r in resp["results"] if r["status"] == "error")
        assert ok_item["source"] == "a.mp4"
        assert err_item["source"] == "b.mp4" and "boom" in err_item["error"]
        # 无音轨时 -c:a aac；无尺寸时 vf 仅 yuv420p
        cmd = recorded[0]
        assert "scale=" not in cmd[cmd.index("-vf") + 1]
        assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "aac"
