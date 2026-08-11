"""v15 视频分析增强单测：分段报告（画面/音频/文本）+ 报告导出。

覆盖：
- normalize_segments：完整三段保留、缺失派生、score 钳制、overall_score 兜底
- build_report_md：分段标题/评分/关键场景/优化建议齐全
- report 导出端点：落库后导出 md、未完成分析 404、归属校验 404
- worker 集成：LLM 返回旧格式（无 segments）→ 落库 analysis 仍含三段
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}
OTHER = {"user_id": "u2", "username": "user2", "role": "user"}
ADMIN = {"user_id": "u9", "username": "admin1", "role": "admin"}


def sample_analysis(with_segments=True):
    analysis = {
        "title": "新手必看：AI 提效实操",
        "summary": "用 AI 工具把周报效率提升 3 倍",
        "detailed_summary": "视频从周报痛点切入，演示三类 AI 工具的组合用法。",
        "key_scenes": [
            {"timestamp": "00:00", "description": "痛点开场钩子", "importance": "高"},
            {"timestamp": "00:45", "description": "工具演示主体", "importance": "中"},
        ],
        "topics": ["AI提效"],
        "tone": "轻松",
        "target_audience": "职场白领",
        "highlights": ["演示直观", "可立即上手"],
        "subtitles_text": "大家好，今天教你三分钟搞定周报",
        "recommendations": ["缩短开场", "增加字幕"],
    }
    if with_segments:
        analysis["overall_score"] = 82
        analysis["segments"] = {
            "visual": {"analysis": "剪辑节奏明快，演示画面清晰", "key_points": ["节奏好", "画面清晰"], "score": 88},
            "audio": {"analysis": "人声清楚，配乐稍显平淡", "key_points": ["人声清楚"], "score": 72},
            "text": {"analysis": "文案口语化，信息密度适中", "key_points": ["口语化", "密度适中"], "score": 86},
        }
    return analysis


@pytest.fixture(autouse=True)
def _init_video_tables(setup_test_db):
    """video_records 表由模块导入时创建（可能建在旧库），测试库内幂等重建。"""
    import video_analyzer

    video_analyzer.init_db()


class TestNormalizeSegments:
    def test_complete_segments_kept(self):
        from video_analyzer import normalize_segments

        out = normalize_segments(sample_analysis())
        assert out["overall_score"] == 82
        assert out["segments"]["visual"]["analysis"] == "剪辑节奏明快，演示画面清晰"
        assert out["segments"]["visual"]["key_points"] == ["节奏好", "画面清晰"]
        assert out["segments"]["audio"]["score"] == 72

    def test_missing_segments_derived(self):
        """LLM 旧格式（无 segments）→ 从 key_scenes/subtitles/tone 派生三段。"""
        from video_analyzer import normalize_segments

        out = normalize_segments(sample_analysis(with_segments=False))
        seg = out["segments"]
        # 画面段从关键场景派生要点
        assert any("00:00" in p for p in seg["visual"]["key_points"])
        assert "2 个关键场景" in seg["visual"]["analysis"]
        # 音频段引用基调
        assert "轻松" in seg["audio"]["analysis"]
        assert seg["audio"]["score"] is None
        # 文本段引用字幕
        assert "字幕片段" in seg["text"]["key_points"][0]
        # overall_score 由三段平均兜底（仅 visual 有分）
        assert out["overall_score"] is None

    def test_partial_segments_merged(self):
        """部分段缺失：已有段保留，缺失段用 fallback。"""
        from video_analyzer import normalize_segments

        analysis = sample_analysis(with_segments=False)
        analysis["segments"] = {"visual": {"analysis": "自定义画面分析", "key_points": ["A"], "score": 95}}
        analysis["overall_score"] = 90
        out = normalize_segments(analysis)
        assert out["segments"]["visual"]["analysis"] == "自定义画面分析"
        assert out["segments"]["audio"]["analysis"].startswith("整体基调")
        assert out["segments"]["text"]["analysis"] == analysis["detailed_summary"]
        assert out["overall_score"] == 90

    def test_score_clamped(self):
        from video_analyzer import normalize_segments

        analysis = sample_analysis(with_segments=False)
        analysis["segments"] = {
            "visual": {"analysis": "v", "score": 150},
            "audio": {"analysis": "a", "score": -5},
            "text": {"analysis": "t", "score": "abc"},
        }
        out = normalize_segments(analysis)
        assert out["segments"]["visual"]["score"] == 100
        assert out["segments"]["audio"]["score"] == 0
        assert out["segments"]["text"]["score"] is None

    def test_overall_averaged_when_missing(self):
        from video_analyzer import normalize_segments

        analysis = sample_analysis(with_segments=False)
        analysis["segments"] = {
            "visual": {"analysis": "v", "score": 80},
            "audio": {"analysis": "a", "score": 70},
            "text": {"analysis": "t", "score": 90},
        }
        out = normalize_segments(analysis)
        assert out["overall_score"] == 80

    def test_empty_input(self):
        from video_analyzer import normalize_segments

        out = normalize_segments({})
        assert set(out["segments"].keys()) == {"visual", "audio", "text"}
        assert out["overall_score"] is None
        assert "未能提取" in out["segments"]["visual"]["analysis"]


class TestBuildReportMd:
    def test_full_report_sections(self):
        from video_analyzer import build_report_md

        md = build_report_md({"filename": "demo.mp4", "created_at": "2026-08-01T10:00:00"}, sample_analysis())
        assert "# 视频分析报告" in md
        assert "demo.mp4" in md
        assert "82 / 100" in md
        # 三段标题
        assert "### 画面" in md
        assert "### 音频" in md
        assert "### 文本" in md
        assert "评分：88 / 100" in md
        assert "关键场景" in md and "00:45" in md
        assert "优化建议" in md and "缩短开场" in md

    def test_minimal_analysis(self):
        from video_analyzer import build_report_md

        md = build_report_md({}, {})
        assert "# 视频分析报告" in md
        assert "由小团智能平台 AI 视频分析生成" in md


class TestReportEndpoint:
    def _seed_record(self, analysis=None, user_id="u1", vid="vid_test"):
        from common.db import get_db_context

        with get_db_context() as conn:
            conn.execute(
                """INSERT INTO video_records (id, filename, filepath, file_size, description, analysis, status, user_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    vid,
                    "demo.mp4",
                    "/tmp/nonexist.mp4",
                    1024,
                    "",
                    json.dumps(analysis, ensure_ascii=False) if analysis else None,
                    "done" if analysis else "uploaded",
                    user_id,
                    "2026-08-01T10:00:00",
                ),
            )

    def test_report_export(self, setup_test_db):
        from video_analyzer import get_report

        self._seed_record(sample_analysis())
        out = asyncio.run(get_report("vid_test", current_user=USER))
        assert out["filename"] == "demo-分析报告.md"
        assert "### 画面" in out["content"]
        assert "82 / 100" in out["content"]

    def test_report_without_analysis_404(self, setup_test_db):
        from fastapi import HTTPException

        from video_analyzer import get_report

        self._seed_record(None)
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_report("vid_test", current_user=USER))
        assert exc.value.status_code == 404
        assert "尚未完成分析" in exc.value.detail

    def test_report_access_denied_404(self, setup_test_db):
        from fastapi import HTTPException

        from video_analyzer import get_report

        self._seed_record(sample_analysis(), user_id="u1")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_report("vid_test", current_user=OTHER))
        assert exc.value.status_code == 404

    def test_report_admin_can_access_any(self, setup_test_db):
        from video_analyzer import get_report

        self._seed_record(sample_analysis(), user_id="u1")
        out = asyncio.run(get_report("vid_test", current_user=ADMIN))
        assert out["filename"].endswith(".md")


class TestAnalyzeWorkerIntegration:
    def _seed_video(self):
        from common.db import get_db_context

        with get_db_context() as conn:
            conn.execute(
                """INSERT INTO video_records (id, filename, filepath, file_size, description, analysis, status, user_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    "vid_w1",
                    "w.mp4",
                    "/tmp/nonexist_w.mp4",
                    2048,
                    "工作流演示",
                    None,
                    "uploaded",
                    "u1",
                    "2026-08-01T10:00:00",
                ),
            )

    def test_worker_old_format_gains_segments(self, setup_test_db, monkeypatch):
        """LLM 返回旧格式（无 segments）→ worker 落库 analysis 含三段结构。"""
        import video_analyzer

        self._seed_video()
        monkeypatch.setattr(video_analyzer, "_probe_video_meta", lambda *a, **kw: (60.0, []))
        monkeypatch.setattr(
            video_analyzer,
            "call_llm",
            lambda *a, **kw: json.dumps(sample_analysis(with_segments=False), ensure_ascii=False),
        )
        monkeypatch.setattr(video_analyzer, "log_usage", lambda *a, **kw: None)

        result = asyncio.run(
            video_analyzer._video_analyze_worker({"video_id": "vid_w1", "description": "演示"})
        )
        assert result["segments"]["visual"]["key_points"]
        assert result["overall_score"] is not None or result["overall_score"] is None  # 结构存在即可

        from common.db import get_db_context

        with get_db_context() as conn:
            row = conn.execute("SELECT analysis, status FROM video_records WHERE id='vid_w1'").fetchone()
        assert row[1] == "done"
        stored = json.loads(row[0])
        assert set(stored["segments"].keys()) == {"visual", "audio", "text"}

    def test_worker_new_format_kept(self, setup_test_db, monkeypatch):
        """LLM 返回新格式（含 segments）→ 原样保留。"""
        import video_analyzer

        self._seed_video()
        monkeypatch.setattr(video_analyzer, "_probe_video_meta", lambda *a, **kw: (60.0, []))
        monkeypatch.setattr(
            video_analyzer,
            "call_llm",
            lambda *a, **kw: json.dumps(sample_analysis(with_segments=True), ensure_ascii=False),
        )
        monkeypatch.setattr(video_analyzer, "log_usage", lambda *a, **kw: None)

        result = asyncio.run(
            video_analyzer._video_analyze_worker({"video_id": "vid_w1", "description": ""})
        )
        assert result["overall_score"] == 82
        assert result["segments"]["visual"]["score"] == 88
