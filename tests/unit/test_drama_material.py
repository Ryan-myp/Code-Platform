"""v13.25 短剧工厂开源化升级单元测试：素材库（Pexels/本地/缓存）/ 剧本 search 字段 / BGM / config 接口。

不依赖外部网络：Pexels 请求用 mock 拦截；PEXELS_API_KEY 用 patch 控制开关。
"""

import asyncio
import json
import subprocess
import types

import pytest
import requests

import short_drama as sd


class TestScriptSearchField:
    """剧本解析：search 素材关键词字段的清洗与回退。"""

    def test_search_passthrough_and_clean(self):
        raw = json.dumps({
            "title": "测试剧",
            "scenes": [
                {"id": 1, "shot": "雨中奔跑", "search": 'night "city" rain', "narrator": "旁白", "sec": 5},
            ],
        })
        script = sd._parse_script(raw)
        assert script["scenes"][0]["search"] == "night city rain"

    def test_search_truncated_to_60(self):
        raw = json.dumps({
            "scenes": [
                {"id": 1, "shot": "镜头", "search": "a" * 80, "narrator": "旁白"},
            ],
        })
        script = sd._parse_script(raw)
        assert len(script["scenes"][0]["search"]) == 60

    def test_search_missing_falls_back_to_shot(self):
        raw = json.dumps({
            "scenes": [
                {"id": 1, "shot": "深夜城市霓虹闪烁的街道", "narrator": "旁白"},
            ],
        })
        script = sd._parse_script(raw)
        assert script["scenes"][0]["search"] == "深夜城市霓虹闪烁的街道"

    def test_search_missing_and_shot_missing_is_empty(self):
        raw = json.dumps({"scenes": [{"id": 1, "narrator": "旁白"}]})
        script = sd._parse_script(raw)
        assert script["scenes"][0]["search"] == ""


class TestScriptSecClamp:
    """v13.27 长剧能力：单镜 sec 放宽到 45s、长剧本（20+ 场）解析通过。"""

    def test_sec_clamped_to_45(self):
        raw = json.dumps({"scenes": [{"id": 1, "shot": "镜头", "narrator": "旁白", "sec": 99}]})
        assert sd._parse_script(raw)["scenes"][0]["sec"] == 45

    def test_sec_min_2(self):
        raw = json.dumps({"scenes": [{"id": 1, "shot": "镜头", "narrator": "旁白", "sec": 1}]})
        assert sd._parse_script(raw)["scenes"][0]["sec"] == 2

    def test_long_script_28_scenes_parsed(self):
        scenes = [
            {"id": i, "shot": f"镜头{i}", "narrator": f"旁白{i}", "sec": 25}
            for i in range(1, 29)
        ]
        raw = json.dumps({"title": "长剧", "scenes": scenes})
        script = sd._parse_script(raw)
        assert len(script["scenes"]) == 28
        assert all(s["sec"] == 25 for s in script["scenes"])


class TestEnforceDuration:
    """v13.28 时长硬校验：场次数 + 台词量 + 单镜 sec 三重防御。"""

    def _scenes(self, n, words_each=200, sec=25):
        return [
            {
                "id": i, "shot": f"镜头{i}",
                "narrator": "字" * words_each, "dialogue": "对" * 10, "sec": sec,
            }
            for i in range(1, n + 1)
        ]

    def test_scene_count_capped_by_duration(self):
        # 210s 目标 → 每场至少约 20s → 上限 11 场，20 场剧本被截断
        scenes = sd._enforce_duration(self._scenes(20, words_each=30), 210)
        assert len(scenes) == 11

    def test_short_duration_min_4_scenes(self):
        # 45s 目标 → max(4, ceil(45/20)) = 4 场保底
        scenes = sd._enforce_duration(self._scenes(3, words_each=10), 45)
        assert len(scenes) == 3

    def test_long_duration_capped_at_32(self):
        scenes = sd._enforce_duration(self._scenes(60, words_each=50), 1800)
        assert len(scenes) == 32

    def test_dialogue_truncated_by_word_budget(self):
        # 210s → 口播预算 525 字（2.5 字/秒）；两场共 ~800 字 → 按比例截断，总字数降至预算内
        scenes = [
            {"id": 1, "shot": "镜头1", "narrator": "字" * 400, "dialogue": ""},
            {"id": 2, "shot": "镜头2", "narrator": "字" * 400, "dialogue": ""},
        ]
        out = sd._enforce_duration(scenes, 210)
        total = sum(len(s["narrator"]) for s in out)
        assert 500 <= total <= 530
        assert out[0]["narrator"].endswith("…")

    def test_within_budget_untouched(self):
        scenes = [{"id": 1, "shot": "镜头1", "narrator": "短台词", "dialogue": "好", "sec": 20}]
        out = sd._enforce_duration(scenes, 210)
        assert out[0]["narrator"] == "短台词"
        assert out[0]["dialogue"] == "好"

    def test_sec_capped_to_avg_when_out_of_range(self):
        # 210s / 11 场 → 均场 base=19s；sec 35（> 19*1.5=28.5）压到 19，sec 15 保留
        scenes = [
            {"id": 1, "shot": "镜头1", "narrator": "短", "sec": 35},
            {"id": 2, "shot": "镜头2", "narrator": "短", "sec": 15},
        ] + self._scenes(9, words_each=5, sec=20)
        out = sd._enforce_duration(scenes, 210)
        assert out[0]["sec"] == 19
        assert out[1]["sec"] == 15
        assert all(s["sec"] == 20 for s in out[2:])

    def test_sec_raised_when_too_short(self):
        # 210s / 11 场 → base=19；sec 5（< 19*0.5=9.5）抬到 19，防成片被短配音拉短
        scenes = self._scenes(11, words_each=5, sec=5)
        out = sd._enforce_duration(scenes, 210)
        assert all(s["sec"] == 19 for s in out)

    def test_sec_cap_does_not_break_long_drama(self):
        # 600s / 12 场 → base=min(45, ceil(570/12)=48)=45，sec 40 不动（≤ 67.5）
        scenes = self._scenes(12, words_each=80, sec=40)
        out = sd._enforce_duration(scenes, 600)
        assert all(s["sec"] == 40 for s in out)


class TestPexelsSearch:
    """Pexels 素材搜索：key 开关与 URL 选材策略。"""

    def test_no_key_returns_none(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "")
            assert sd._pexels_search_video("city") is None

    def test_picks_portrait_hd_url(self):
        fake_videos = {
            "videos": [
                {
                    "id": 1,
                    "duration": 20,  # v13.29 时长过滤 8-40s
                    "video_files": [
                        {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "https://x/landscape.mp4"},
                        {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "https://x/portrait.mp4"},
                        {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "https://x/portrait_hd.mp4"},
                    ],
                },
            ]
        }
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "test-key")

            def fake_get(url, params=None, headers=None, timeout=None):
                assert params.get("orientation") == "portrait"
                return SimpleResp(200, fake_videos)

            with pytest.MonkeyPatch.context() as mp2:
                mp2.setattr(requests, "get", fake_get)
                # v13.29 候选为竖屏 720-1920 中的轮换结果（横屏被竖屏池排除）
                assert sd._pexels_search_video("city") in {
                    "https://x/portrait.mp4",
                    "https://x/portrait_hd.mp4",
                }

    def test_http_error_returns_none(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "test-key")
            with pytest.MonkeyPatch.context() as mp2:
                mp2.setattr(requests, "get", lambda *a, **k: SimpleResp(401, {}))
                assert sd._pexels_search_video("city") is None


class TestLocalMaterial:
    """本地素材目录模糊匹配。"""

    def test_find_by_keyword(self, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "MATERIALS_DIR", tmp_path)
            (tmp_path / "city_rain.mp4").write_bytes(b"x")
            (tmp_path / "other.mp4").write_bytes(b"y")
            hit = sd._find_local_material("city")
            assert hit is not None and hit.name == "city_rain.mp4"
            assert sd._find_local_material("ocean") is None

    def test_fetch_falls_back_to_local_when_no_pexels(self, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "")
            mp.setattr(sd, "MATERIALS_DIR", tmp_path)
            (tmp_path / "sunset_sky.jpg").write_bytes(b"img")
            path, kind = sd._fetch_material("sunset")
            assert path is not None and kind == "image"

    def test_fetch_nothing_returns_none(self, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "")
            mp.setattr(sd, "MATERIALS_DIR", tmp_path)
            path, kind = sd._fetch_material("nonexistent-keyword-xyz")
            assert path is None and kind == ""


class TestBgm:
    """背景音乐选择。"""

    def test_empty_music_dir_returns_none(self, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "MUSIC_DIR", tmp_path)
            assert sd._pick_bgm() is None

    def test_picks_audio_track(self, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "MUSIC_DIR", tmp_path)
            (tmp_path / "a.mp3").write_bytes(b"x")
            (tmp_path / "b.txt").write_bytes(b"x")
            bgm = sd._pick_bgm()
            assert bgm is not None and bgm.endswith("a.mp3")


class TestDramaConfig:
    """素材源状态接口。"""

    def test_config_shape(self, tmp_path):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "")
            mp.setattr(sd, "MATERIALS_DIR", tmp_path)
            mp.setattr(sd, "MUSIC_DIR", tmp_path)
            (tmp_path / "city.mp4").write_bytes(b"x")
            out = asyncio.run(sd.drama_config({"username": "tester"}))
            assert out == {"pexels_configured": False, "local_materials": 1, "music_tracks": 0}


class TestSceneVideoMotion:
    """v13.31 插画镜 Ken Burns 运镜 + 镜序 fade 控制（消除镜间黑场闪烁）。"""

    @staticmethod
    def _run_captured(tmp_path, duration=10.0, motion="zoom_in", fade_in=True, fade_out=True):
        """用假 subprocess 捕获 ffmpeg 命令；out 预置文件满足成功判定。"""
        captured = {}

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return types.SimpleNamespace(returncode=0, stderr=b"")

        img = tmp_path / "a.jpg"
        img.write_bytes(b"x" * 4096)
        out = tmp_path / "seg.mp4"
        out.write_bytes(b"x" * 4096)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd.subprocess, "run", fake_run)
            sd._scene_video(str(img), str(tmp_path / "a.mp3"), str(out), duration, motion, fade_in, fade_out)
        return captured["cmd"]

    @staticmethod
    def _vf(cmd):
        return cmd[cmd.index("-vf") + 1]

    def test_zoompan_uses_on_output_frame_counter(self, tmp_path):
        # 关键修复：in 是输入帧计数（按需求值只拉 1 帧时画面静止），必须用 on
        cmd = self._run_captured(tmp_path)
        vf = self._vf(cmd)
        assert "zoompan" in vf
        assert "*on/" in vf
        assert "*in/" not in vf
        assert "fade=t=in" in vf and "fade=t=out" in vf  # 默认首尾 fade 保留

    def test_middle_scene_no_fade(self, tmp_path):
        # 中间镜：无任何 fade（硬切，消除黑场闪烁）
        cmd = self._run_captured(tmp_path, fade_in=False, fade_out=False)
        vf = self._vf(cmd)
        assert "fade=" not in vf

    def test_first_scene_fade_in_only(self, tmp_path):
        cmd = self._run_captured(tmp_path, fade_in=True, fade_out=False)
        vf = self._vf(cmd)
        assert "fade=t=in" in vf and "fade=t=out" not in vf

    def test_motion_variants_alternate(self, tmp_path):
        # 4 种运镜交替：zoom_in 推近 / zoom_out 拉远 / pan_in / pan_out 带横摇
        zexprs = []
        for motion in sd._SCENE_MOTIONS:
            cmd = self._run_captured(tmp_path, motion=motion)
            vf = self._vf(cmd)
            assert "zoompan" in vf
            if motion.startswith("pan"):
                assert "sin(2*PI*on" in vf  # 横摇带 sin 摆动
            else:
                assert "sin(" not in vf
            zexprs.append(vf)
        # zoom_out/pan_out 从 1+amp 起（拉远），zoom_in/pan_in 从 1 起（推近）
        assert "z='1+" in zexprs[0] and "z='1.1-" in zexprs[1]

    def test_still_motion_no_zoompan(self, tmp_path):
        # 卡片兜底镜 still：无 zoompan（渐变海报文字不放大移动）
        cmd = self._run_captured(tmp_path, motion="still")
        assert "zoompan" not in self._vf(cmd)

    def test_real_encoding_with_motion(self, tmp_path):
        # 真实编码：2s Ken Burns 片段，产物 720x1280、时长≈2s
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (720, 1280), (10, 20, 30)).save(buf, format="JPEG")
        img = tmp_path / "s.jpg"
        img.write_bytes(buf.getvalue())
        audio = tmp_path / "s.m4a"
        subprocess.run(
            [sd.FFMPEG_BIN, "-nostdin", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", "1", "-c:a", "aac", str(audio)],
            capture_output=True, timeout=60,
        )
        out = tmp_path / "out.mp4"
        sd._scene_video(str(img), str(audio), str(out), 2.0, "zoom_in", True, True)
        assert out.exists() and out.stat().st_size > 4096
        assert abs(sd._probe_seconds(str(out)) - 2.0) < 0.1


class TestDhSceneVideo:
    """v13.32 数字人镜竖屏化：模糊填充背景（无黑边）+ 镜序 fade 对齐。"""

    @staticmethod
    def _run_captured(tmp_path, fade_in=False, fade_out=False):
        captured = {}

        def fake_generate(req, user, uid, role):
            return {"status": "done", "video_url": "dh_factory/test.mp4"}

        def fake_exists(p):
            return True

        def fake_run(cmd, **kw):
            captured["cmd"] = cmd
            return types.SimpleNamespace(returncode=0, stderr=b"")

        out = tmp_path / "clip.mp4"
        out.write_bytes(b"x" * 4096)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("digital_human._generate_one", fake_generate)
            mp.setattr(sd.os.path, "exists", fake_exists)
            mp.setattr(sd.subprocess, "run", fake_run)
            ok = sd._dh_scene_video("这是一段数字人口播台词", "business-female", "2d", "u", "uid", "r", str(out), "neutral", fade_in, fade_out)
        return ok, captured["cmd"]

    @staticmethod
    def _vf(cmd):
        return cmd[cmd.index("-vf") + 1]

    def test_blur_backdrop_replaces_pad(self, tmp_path):
        ok, cmd = self._run_captured(tmp_path)
        assert ok
        vf = self._vf(cmd)
        assert "split=2[bg][fg]" in vf and "gblur" in vf and "overlay" in vf
        assert "pad" not in vf  # 纯色 pad 黑边被模糊填充替代

    def test_fade_controlled_by_scene_order(self, tmp_path):
        _, cmd = self._run_captured(tmp_path, fade_in=True, fade_out=True)
        vf = self._vf(cmd)
        assert "fade=t=in:st=0:d=0.25" in vf
        assert "fade=t=out" in vf
        # 中间镜：无 fade（硬切，与插画/素材镜一致）
        _, cmd2 = self._run_captured(tmp_path, fade_in=False, fade_out=False)
        assert "fade=" not in self._vf(cmd2)

    def test_audio_kept(self, tmp_path):
        ok, cmd = self._run_captured(tmp_path)
        assert ok
        assert "-c:a", "aac" in [(cmd[i], cmd[i + 1]) for i in range(len(cmd) - 1)]


class SimpleResp:
    """最小 requests.Response 替身。"""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class TestSrtTiming:
    """v13.29 字幕时序收敛：配音短于画面时字幕提前结束，时间轴按画面时长推进。"""

    def _srt(self, scenes, durations, voice_durs, tmp_path):
        out = tmp_path / "t.srt"
        sd._make_srt(scenes, durations, voice_durs, str(out))
        return out.read_text(encoding="utf-8")

    def test_subtitle_ends_when_voice_ends(self, tmp_path):
        scenes = [{"narrator": "旁白一", "dialogue": ""}, {"narrator": "旁白二", "dialogue": ""}]
        srt = self._srt(scenes, [20.0, 20.0], [8.0, 10.0], tmp_path)
        lines = [l for l in srt.splitlines() if "-->" in l]
        # 画面 20s 配音 8s → 字幕 8.6s 即结束；下一镜从 20s 开始（时间轴按画面推进）
        assert lines[0].startswith("00:00:00,000 --> 00:00:08,600")
        assert lines[1].startswith("00:00:20,000 --> 00:00:30,600")

    def test_no_voice_dur_falls_back_full_scene(self, tmp_path):
        scenes = [{"narrator": "旁白", "dialogue": ""}]
        srt = self._srt(scenes, [15.0], [], tmp_path)
        assert "00:00:00,000 --> 00:00:15,000" in srt

    def test_voice_longer_than_scene_clamped(self, tmp_path):
        # 配音异常比画面长：字幕不超画面时长
        scenes = [{"narrator": "旁白", "dialogue": ""}]
        srt = self._srt(scenes, [10.0], [30.0], tmp_path)
        assert "00:00:00,000 --> 00:00:10,000" in srt


class TestSceneCardFallback:
    """v13.29 卡片画面：插画优先（shot 描述），失败回退渐变海报（去大字报）。"""

    def test_illustration_used_when_available(self, tmp_path):
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (720, 1280), (10, 20, 30)).save(buf, format="JPEG")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "_generate_scene_image", lambda shot: buf.getvalue())
            ok = sd._make_scene_card("台词", 0, 3, "测试剧", str(tmp_path / "a.jpg"), "雨夜街道")
        assert ok
        assert Image.open(tmp_path / "a.jpg").size == (720, 1280)

    def test_fallback_gradient_when_illustration_fails(self, tmp_path):
        from PIL import Image

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "_generate_scene_image", lambda shot: None)
            ok = sd._make_scene_card("台词" * 50, 1, 3, "测试剧", str(tmp_path / "b.jpg"), "雨夜街道")
        assert ok
        assert Image.open(tmp_path / "b.jpg").size == (720, 1280)

    def test_no_shot_falls_back_gradient(self, tmp_path):
        from PIL import Image

        ok = sd._make_scene_card("台词", 0, 1, "测试剧", str(tmp_path / "c.jpg"))
        assert ok
        assert Image.open(tmp_path / "c.jpg").size == (720, 1280)


class TestGenerateScript:
    """v13.29 _generate_script：LLM 坏 JSON 自动重试 + 时长防御兜底。"""

    def test_success_after_retries(self):
        calls = {"n": 0}

        async def fake_llm(system, prompt, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                return "not json at all"
            return json.dumps({"title": "T", "scenes": [{"id": 1, "shot": "s", "narrator": "n", "dialogue": "d", "sec": 99}]})

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "call_llm_async", fake_llm)
            script = asyncio.run(sd._generate_script("主题", 45))
        assert calls["n"] == 3
        assert script["scenes"][0]["sec"] == 45  # clamp + 防御收敛

    def test_all_fail_raises(self):
        async def fake_llm(system, prompt, **kw):
            raise RuntimeError("boom")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "call_llm_async", fake_llm)
            with pytest.raises(Exception):
                asyncio.run(sd._generate_script("主题", 45))


class TestPexelsRotation:
    """v13.29 Pexels 相关性：时长过滤 + 同日稳定轮换（避免缓存死锁）。"""

    @staticmethod
    def _video(vid, dur, w, h):
        return {
            "id": vid,
            "duration": dur,
            "video_files": [{"file_type": "video/mp4", "link": f"https://x/{vid}.mp4", "width": w, "height": h}],
        }

    def test_filters_too_short_duration(self):
        payload = {"videos": [self._video(1, 3, 720, 1280), self._video(2, 12, 720, 1280)]}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "k")
            mp.setattr("requests.get", lambda *a, **k: SimpleResp(200, payload))
            assert sd._pexels_search_video("rain") == "https://x/2.mp4"

    def test_rotation_stable_same_day(self):
        payload = {"videos": [self._video(i, 20, 720, 1280) for i in range(6)]}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "k")
            mp.setattr("requests.get", lambda *a, **k: SimpleResp(200, payload))
            a = sd._pexels_search_video("night")
            b = sd._pexels_search_video("night")
            assert a == b  # 同日稳定（缓存友好）
            assert a in {f"https://x/{i}.mp4" for i in range(6)}

    def test_no_key_returns_none(self):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "PEXELS_API_KEY", "")
            assert sd._pexels_search_video("rain") is None


class TestCharactersParse:
    """v13.30 角色表解析：id 规范化去重、anchor 生成、chars 白名单过滤。"""

    def test_parses_characters_with_anchor(self):
        raw = json.dumps({
            "title": "测试剧",
            "characters": [
                {"id": "Lin Xiao Man!", "name": "林小满", "gender": "女", "age": "24岁",
                 "appearance": "黑色长发齐刘海", "outfit": "白裙红围巾", "search": "young chinese woman black hair"},
            ],
            "scenes": [{"id": 1, "chars": ["linxiao_man"], "shot": "雨夜", "narrator": "旁白"}],
        })
        script = sd._parse_script(raw)
        c = script["characters"][0]
        assert c["id"] == "linxiaoman"  # 非字母数字下划线全部清洗
        assert c["anchor"] == "林小满，女，24岁，黑色长发齐刘海，白裙红围巾"
        assert script["scenes"][0]["chars"] == ["linxiaoman"]  # 清洗后的 id 通过白名单

    def test_missing_characters_empty(self):
        raw = json.dumps({"scenes": [{"id": 1, "shot": "s", "narrator": "n"}]})
        script = sd._parse_script(raw)
        assert script["characters"] == []
        assert script["scenes"][0]["chars"] == []

    def test_invalid_chars_filtered_and_dup_dropped(self):
        raw = json.dumps({
            "characters": [
                {"id": "a", "name": "A", "appearance": "短发"},
                {"id": "a", "name": "A2", "appearance": "长发"},  # 重复 id 丢弃
                {"id": "b", "name": "B", "appearance": "眼镜"},
            ],
            "scenes": [{"id": 1, "chars": ["a", "ghost"], "shot": "s", "narrator": "n"}],
        })
        script = sd._parse_script(raw)
        assert [c["id"] for c in script["characters"]] == ["a", "b"]
        assert script["scenes"][0]["chars"] == ["a"]

    def test_char_singleton_legacy_compat(self):
        raw = json.dumps({
            "characters": [{"id": "hero", "name": "主角", "appearance": "黑衣"}],
            "scenes": [{"id": 1, "char": "HERO", "shot": "s", "narrator": "n"}],  # 旧单值，大小写混合
        })
        script = sd._parse_script(raw)
        assert script["scenes"][0]["chars"] == ["hero"]


class TestAnchorSearch:
    """v13.30 素材搜索锚定：主角特征词前缀（尽力同性别/同特征）。"""

    def test_prepend_lead_char_search(self):
        char = {"id": "a", "search": "young chinese woman black hair"}
        assert sd._anchor_search(char, "night city rain") == "young chinese woman black hair night city rain"

    def test_no_char_returns_raw(self):
        assert sd._anchor_search(None, "night city rain") == "night city rain"

    def test_char_without_search_returns_raw(self):
        assert sd._anchor_search({"id": "a", "search": ""}, "rain") == "rain"


class TestSceneImageRefs:
    """v13.30 插画参考图链路：图生图 image 数组 + anchors 文字锚定。"""

    @staticmethod
    def _mock_image():
        import io
        from PIL import Image

        buf = io.BytesIO()
        Image.new("RGB", (736, 1312), (5, 5, 5)).save(buf, format="JPEG")
        return buf.getvalue()

    def test_refs_sent_as_image_array(self):
        captured = {}

        def fake_post(url, **kw):
            captured["json"] = kw.get("json")
            return SimpleResp(200, {"data": [{"url": "https://img/x.jpg"}]})

        img = self._mock_image()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "AGNES_API_KEY", "k")
            mp.setattr("requests.post", fake_post)
            mp.setattr("requests.get", lambda *a, **k: types.SimpleNamespace(status_code=200, content=img))
            out = sd._generate_scene_image("雨夜便利店", "林小满，女，黑色长发", [img, img])
        body = captured["json"]
        assert out is not None
        assert len(body["image"]) == 2  # 多图参考（多角色同镜）
        assert body["image"][0].startswith("data:image/jpeg;base64,")
        assert "林小满，女，黑色长发" in body["prompt"]  # anchors 文字锚定
        assert body["size"] == "1K" and body["ratio"] == "9:16"

    def test_no_refs_pure_t2i(self):
        captured = {}

        def fake_post(url, **kw):
            captured["json"] = kw.get("json")
            return SimpleResp(200, {"data": [{"url": "https://img/x.jpg"}]})

        img = self._mock_image()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sd, "AGNES_API_KEY", "k")
            mp.setattr("requests.post", fake_post)
            mp.setattr("requests.get", lambda *a, **k: SimpleResp(200, img))
            sd._generate_scene_image("雨夜便利店")
        assert "image" not in captured["json"]  # 无参考图 → 纯文生图
        assert captured["json"]["prompt"].endswith("雨夜便利店")
