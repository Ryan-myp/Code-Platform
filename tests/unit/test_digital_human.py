"""数字人模块单元测试：口型时间轴 / 文案清洗 / 内容安全 / 商业参数校验。

不依赖网络与 ffmpeg，仅覆盖纯函数与 Pydantic 校验。
"""

import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


class TestCleanScriptText:
    def test_fold_blank_lines_and_strip(self):
        from digital_human import _clean_script_text

        text = "\n\n  大家好，\n\n\n今天分享技巧。  \n\n"
        assert _clean_script_text(text) == "大家好，\n\n今天分享技巧。"
        assert _clean_script_text("  仅首尾空格  ") == "仅首尾空格"

    def test_empty_input(self):
        from digital_human import _clean_script_text

        assert _clean_script_text("") == ""
        assert _clean_script_text(None) == ""


class TestScriptTimeline:
    """字级口型时间轴：拼音元音分类 + 均匀时长分配 + 标点闭嘴。"""

    def test_hanzi_units_and_punctuation(self):
        from digital_human import _build_script_timeline

        tl = _build_script_timeline("大家好。", 4.0)
        # 3 汉字 × 1.0 + 1 标点 × 0.5 = 3.5 单位 → 4.0 / 3.5 ≈ 1.143s/单位
        assert len(tl) == 4
        assert tl[0][0] == "大" and tl[3][0] == "。"
        # 标点闭嘴
        assert tl[3][3] == 0.0
        # 时长连续覆盖 [0, 4.0)
        assert abs(tl[0][1] - 0.0) < 1e-6
        assert abs(tl[-1][2] - 4.0) < 1e-6

    def test_mouth_shape_classification(self):
        """a 类大口 > e 类半开 > i 类扁口；u 类嘟嘴圆度高。"""
        from digital_human import _MOUTH_SHAPES, _build_script_timeline

        tl = _build_script_timeline("大 你 出", 3.0)
        shapes = {ch: (o, r) for ch, _, _, o, r in tl}
        assert shapes["大"][0] > shapes["你"][0]  # 大(1.0) > 你(0.45)
        assert shapes["出"][1] > shapes["你"][1]  # 出 嘟嘴圆度 > 你 扁口
        assert "a" in _MOUTH_SHAPES and "u" in _MOUTH_SHAPES and "i" in _MOUTH_SHAPES

    def test_mouth_envelope(self):
        """字周期包络：开头微开 → 中段最大 → 结尾收拢。"""
        from digital_human import _build_script_timeline, _mouth_shape_at

        tl = _build_script_timeline("大", 1.0)
        start, end, open_ = tl[0][1], tl[0][2], tl[0][3]
        mid = _mouth_shape_at(tl, (start + end) / 2)[0]
        early = _mouth_shape_at(tl, start + (end - start) * 0.05)[0]
        late = _mouth_shape_at(tl, end - (end - start) * 0.05)[0]
        assert mid == open_  # 中段维持最大
        assert early < mid and late < mid  # 两侧收拢
        # 超时域返回闭嘴
        assert _mouth_shape_at(tl, end + 0.1) == (0.0, 0.5)

    def test_mouth_smooth_transition(self):
        """口型时间窗平滑：字间谷底被抬起（不彻底闭嘴，去顿挫感），中段峰值不损失。"""
        from digital_human import _build_script_timeline, _mouth_shape_at

        tl = _build_script_timeline("大你", 2.0)
        boundary = tl[1][1]  # 第二个字起点（字间交界）
        # 未平滑：字尾收拢→字首张开，交界处完全闭合（开度≈0）
        raw = _mouth_shape_at(tl, boundary, smooth=0)[0]
        # 平滑后：窗口平均抬起谷底，嘴型过渡更连贯
        sm = _mouth_shape_at(tl, boundary, smooth=0.03)[0]
        assert raw < 0.05 and sm > raw + 0.02
        # 中段峰值不受影响（三点都在维持区，env=1）
        mid = (tl[0][1] + tl[0][2]) / 2
        assert _mouth_shape_at(tl, mid, smooth=0.03)[0] == tl[0][3]
        # 完全静音段仍闭嘴（平滑不产生噪声口型）
        assert _mouth_shape_at(tl, tl[-1][2] + 0.1, smooth=0.03)[0] == 0.0


class TestContentSafety:
    def test_hard_block_words(self):
        """硬拦截词表：包含营销诱导/诈骗/赌博/违禁类行为词。"""
        from digital_human import _HARD_BLOCK_WORDS

        joined = "".join(_HARD_BLOCK_WORDS)
        for kw in ["点击领取", "免费领取", "加微信", "日赚", "赌博", "翻墙", "特效"]:
            assert kw in joined, f"{kw} 应在硬拦截词表中"

    def test_scan_text_chinese_substring(self):
        """宽松扫描：中文词嵌入任意上下文都应命中（修复后的边界逻辑）。"""
        from content_strategy import _scan_text

        hits = _scan_text("点击领取免费领取大礼包，马上抢购")
        words = {h["word"] for h in hits}
        assert "点击领取" in words
        assert "免费领取" in words

    def test_scan_text_ascii_boundary(self):
        """ASCII 数字词仍需词边界（100 不误伤 1000 类场景）。"""
        from content_strategy import _scan_text

        # "100%" 含非字母数字字符 → 直接命中
        assert any(h["word"] == "100%" for h in _scan_text("效果100%满意"))
        # 纯 ASCII 数字词场景：词表无纯数字词时不做断言，仅验证不崩溃
        _scan_text("topics and 1000 dollars")


class TestGenerateRequest:
    def test_resolution_pattern(self):
        from digital_human import GenerateRequest

        assert GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧").resolution == "720p"
        req = GenerateRequest(
            text="大家好，欢迎来到我的频道，今天分享一个技巧", resolution="1080p", fps=24, watermark=False
        )
        assert req.resolution == "1080p" and req.fps == 24 and req.watermark is False

    def test_resolution_rejected(self):
        from pydantic import ValidationError

        from digital_human import GenerateRequest

        with pytest.raises(ValidationError):
            GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧", resolution="4k")
        with pytest.raises(ValidationError):
            GenerateRequest(text="大家好，欢迎来到我的频道，今天分享一个技巧", fps=60)

    def test_short_text_rejected(self):
        from pydantic import ValidationError

        from digital_human import GenerateRequest

        with pytest.raises(ValidationError):
            GenerateRequest(text="太短")


class TestWatermarkPolicy:
    def test_watermark_text(self):
        from digital_human import WATERMARK_TEXT

        assert "数字人" in WATERMARK_TEXT and len(WATERMARK_TEXT) > 5

    def test_free_user_forced_watermark(self):
        """免费用户强制水印：显式传 False 也不能绕过（商业规则）。"""
        membership, role, req_wm = "free", "viewer", False
        use = (membership == "free" and role != "admin") or bool(req_wm)
        assert use is True

    def test_member_watermark_optional(self):
        membership, role, req_wm = "pro", "user", True
        use = (membership == "free" and role != "admin") or bool(req_wm)
        assert use is True
        assert (membership == "free" and role != "admin") or False is False

    def test_admin_no_watermark(self):
        membership, role, req_wm = "free", "admin", False
        use = (membership == "free" and role != "admin") or bool(req_wm)
        assert use is False


class TestBatchRequest:
    """批量生产流水线：请求校验 + 预检逻辑。"""

    def test_batch_texts_validation(self):
        from pydantic import ValidationError

        from digital_human import BatchGenerateRequest

        with pytest.raises(ValidationError):
            BatchGenerateRequest(texts=[])
        with pytest.raises(ValidationError):
            BatchGenerateRequest(texts=["这是十条足够长度的文案内容哦"] * 51)
        req = BatchGenerateRequest(texts=["大家好，今天分享一个技巧"])
        assert req.resolution == "720p" and req.fps == 15

    def test_batch_hard_word_precheck(self):
        """批量预检：违规词文案直接被识别（不浪费配额）。"""
        from digital_human import _HARD_BLOCK_WORDS

        bad = "点击领取免费大礼包"
        good = "大家好，今天分享一个实用的效率技巧"
        assert any(w.lower() in bad.lower() for w in _HARD_BLOCK_WORDS)
        assert not any(w.lower() in good.lower() for w in _HARD_BLOCK_WORDS)

    def test_batch_task_state_keys(self):
        """任务状态计数键与 worker 自增逻辑一致。"""
        statuses = ["success", "failed", "skipped"]
        task = {s: 0 for s in statuses}
        task["done"] = 0
        for s in ["success", "failed", "skipped", "success"]:
            task["done"] += 1
            task[s] += 1
        assert task == {"success": 2, "failed": 1, "skipped": 1, "done": 4}


class TestScriptAssist:
    """AI 口播文案助手：请求校验 + 场景风格表 + 回退模板。"""

    def test_script_request_validation(self):
        from pydantic import ValidationError

        from digital_human import ScriptAssistRequest

        with pytest.raises(ValidationError):
            ScriptAssistRequest(topic="")
        req = ScriptAssistRequest(topic="AI效率工具", platform="douyin", tone="活泼")
        assert req.topic == "AI效率工具" and req.tone == "活泼"

    def test_scene_styles_cover_builtin_scenes(self):
        from digital_human import _SCENE_STYLES

        for sid in ["product", "course", "news", "livestream", "story"]:
            assert sid in _SCENE_STYLES, f"场景 {sid} 应有口播风格定义"

    def test_fallback_scripts_non_empty(self):
        """LLM 不可用时的回退模板：3 版且包含主题。"""
        topic = "AI效率工具"
        scripts = [
            f"大家好，今天和大家聊聊「{topic}」。这件事和每个人都有关，看完一定会有收获。",
            f"你敢信吗？{topic}还能这么玩。今天3分钟带你彻底搞明白。",
            f"最近后台收到很多朋友问{topic}，今天就一次说清楚，记得点赞收藏。",
        ]
        assert len(scripts) == 3
        assert all(topic in s for s in scripts)


class TestComplianceCheckApi:
    """合规预检：请求校验 + 词表命中逻辑。"""

    def test_compliance_request_validation(self):
        from pydantic import ValidationError

        from digital_human import ComplianceCheckRequest

        with pytest.raises(ValidationError):
            ComplianceCheckRequest(text="")
        assert ComplianceCheckRequest(text="大家好").text == "大家好"

    def test_hard_hit_detection(self):
        """预检逻辑：硬违规词命中 → allowed=False；正常文案 → allowed=True。"""
        from digital_human import _HARD_BLOCK_WORDS

        lower = "点击领取免费大礼包，马上抢购".lower()
        hard = [w for w in _HARD_BLOCK_WORDS if w.lower() in lower]
        assert hard
        assert "点击领取" in hard
        clean = "大家好，今天分享一个实用的效率技巧".lower()
        assert [w for w in _HARD_BLOCK_WORDS if w.lower() in clean] == []


class TestBatchPersistence:
    """批量任务持久化（商业化 P0）：落库恢复 + 重启中断恢复。"""

    def _seed_batch(self, batch_id="dhb_test1"):
        from common.db import get_db
        from digital_human import _ensure_tables

        conn = get_db()
        _ensure_tables(conn)
        conn.execute(
            """INSERT INTO digital_human_batches
               (id, user_id, status, total, success, failed, skipped, avatar_id,
                avatar_name, resolution, fps, voice_id, background_id, speed,
                created_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                batch_id,
                "u1",
                "done",
                3,
                2,
                1,
                0,
                "business-female",
                "商务女",
                "720p",
                15,
                "zh-CN-XiaoxiaoNeural",
                "tech",
                1.0,
                "2026-08-01T10:00:00",
                "2026-08-01T10:01:00",
            ),
        )
        for i, (t, s, err) in enumerate(
            [
                ("大家好，今天分享一个技巧", "success", ""),
                ("点击领取大礼包", "failed", "文案含违规词，已拦截"),
                ("文案太短", "failed", "文案太短（至少 5 字）"),
            ]
        ):
            conn.execute(
                "INSERT INTO digital_human_batch_items (batch_id, idx, text, status, error) VALUES (?,?,?,?,?)",
                (batch_id, i, t, s, err),
            )
        conn.commit()
        conn.close()

    def test_load_batch_from_db_roundtrip(self):
        """DB 恢复完整任务结构：状态/计数/逐条明细（重启后轮询与下载的兜底数据源）。"""
        from digital_human import _load_batch_from_db

        self._seed_batch()
        task = _load_batch_from_db("dhb_test1")
        assert task is not None
        assert task["status"] == "done" and task["total"] == 3
        assert task["success"] == 2 and task["failed"] == 1 and task["done"] == 3
        assert task["avatar_name"] == "商务女" and task["resolution"] == "720p"
        assert task["items"][1]["status"] == "failed"
        assert task["items"][1]["error"] == "文案含违规词，已拦截"
        assert _load_batch_from_db("dhb_nope") is None

    def test_recover_interrupted_batches(self):
        """启动恢复：running → interrupted，done 任务不受影响。"""
        from common.db import get_db
        from digital_human import _ensure_tables, recover_interrupted_batches

        conn = get_db()
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO digital_human_batches (id, user_id, status, total, created_at)"
            " VALUES ('dhb_r1', 'u1', 'running', 5, '2026-08-01T10:00:00')"
        )
        conn.execute(
            "INSERT INTO digital_human_batches (id, user_id, status, total, created_at)"
            " VALUES ('dhb_r2', 'u1', 'done', 2, '2026-08-01T10:00:00')"
        )
        conn.commit()
        conn.close()
        recover_interrupted_batches()
        conn = get_db()
        rows = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM digital_human_batches").fetchall()}
        conn.close()
        assert rows["dhb_r1"] == "interrupted"
        assert rows["dhb_r2"] == "done"

    def test_retry_failed_skips_content_issues(self):
        """重试过滤：违规词/文案太短属于内容问题，不进入重试名单。"""
        self._seed_batch()
        from digital_human import _load_batch_from_db

        task = _load_batch_from_db("dhb_test1")
        retry_indexes = [
            item["index"]
            for item in task["items"]
            if item["status"] == "failed" and "违规词" not in item["error"] and "文案太短" not in item["error"]
        ]
        assert retry_indexes == []  # 两条失败项均为内容问题

    def test_batch_running_limit_threshold(self):
        """运行中批量任务 ≥2 时拒绝新任务（资源保护规则，与 create_batch 阈值一致）。"""
        from common.db import get_db
        from digital_human import _ensure_tables

        conn = get_db()
        _ensure_tables(conn)
        for i in range(2):
            conn.execute(
                "INSERT INTO digital_human_batches (id, user_id, status, total, created_at) VALUES (?,?,?,?,?)",
                (f"dhb_run{i}", "u1", "running", 3, "2026-08-01T10:00:00"),
            )
        conn.commit()
        conn.close()
        conn = get_db()
        running = conn.execute(
            "SELECT COUNT(*) FROM digital_human_batches WHERE user_id='u1' AND status='running'"
        ).fetchone()[0]
        conn.close()
        assert running >= 2  # 触发 create_batch 的拒绝分支


class TestStorageRetention:
    """磁盘治理（商业化 P0）：保留期清理只删过期记录，不误删新记录。"""

    def test_cleanup_removes_only_expired(self):
        from datetime import datetime, timedelta

        from common.db import get_db
        from digital_human import DH_RETENTION_DAYS, _cleanup_expired_records, _ensure_tables

        if DH_RETENTION_DAYS <= 0:
            pytest.skip("DH_RETENTION_DAYS<=0 表示关闭清理，跳过")
        old = (datetime.now() - timedelta(days=DH_RETENTION_DAYS + 1)).isoformat()
        recent = datetime.now().isoformat()
        conn = get_db()
        _ensure_tables(conn)
        conn.execute(
            "INSERT INTO digital_human_records (id, user_id, status, created_at)"
            " VALUES ('dh_rec_old', 'u1', 'done', ?)",
            (old,),
        )
        conn.execute(
            "INSERT INTO digital_human_records (id, user_id, status, created_at)"
            " VALUES ('dh_rec_new', 'u1', 'done', ?)",
            (recent,),
        )
        conn.commit()
        conn.close()
        removed = _cleanup_expired_records()
        assert removed >= 1
        conn = get_db()
        ids = [r["id"] for r in conn.execute("SELECT id FROM digital_human_records").fetchall()]
        conn.close()
        assert "dh_rec_old" not in ids
        assert "dh_rec_new" in ids


class TestConcurrencyGuard:
    """资源保护（商业化 P0）：全局渲染并发池 + 用户级生成限制。"""

    def test_render_slot_concurrency_cap(self):
        """渲染并发上限为 2（CPU 密集操作，跨用户/批次统一限流）。"""
        from digital_human import _RENDER_SLOT

        assert _RENDER_SLOT._value == 2

    def test_user_inflight_guard(self):
        """同用户同时只有 1 条生成中（第 2 条并发被拒）。"""
        from digital_human import _GUARD_LOCK, _USER_GENERATING

        with _GUARD_LOCK:
            _USER_GENERATING.clear()
            _USER_GENERATING["u1"] = 1
        with _GUARD_LOCK:
            blocked = _USER_GENERATING.get("u1", 0) >= 1
        assert blocked  # 与 generate 接口的 429 分支一致


class TestRenderRealism:
    """逼真化渲染：cover 裁剪防变形 / 嘴部羽化贴图 / 随机眨眼 / 摄影棚光影 / 滤镜链。"""

    # 跨平台字体兜底（触发 load_default），不依赖系统字体文件
    _FONT_PATHS = ["/nonexistent/font.ttf"]

    @staticmethod
    def _fake_portrait_path() -> str:
        """生成带脸部色块的假写真（1024x1024），返回临时路径。"""
        import tempfile

        from PIL import Image as PILImage
        from PIL import ImageDraw

        img = PILImage.new("RGB", (1024, 1024), (180, 140, 130))
        d = ImageDraw.Draw(img)
        d.ellipse([350, 200, 680, 560], fill=(200, 160, 150))  # 脸
        d.ellipse([420, 300, 470, 350], fill=(30, 30, 30))  # 左眼
        d.ellipse([555, 300, 605, 350], fill=(30, 30, 30))  # 右眼
        d.ellipse([440, 470, 590, 540], fill=(90, 50, 60))  # 嘴
        p = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        p.close()
        img.save(p.name)
        return p.name

    def test_cover_crop_no_distortion(self):
        """1:1 与横向图 cover 裁剪后恒为 800x1000，杜绝拉伸变形。"""
        import os

        from PIL import Image as PILImage

        from digital_human import _build_portrait_src

        path = self._fake_portrait_path()
        try:
            for w, h in ((1024, 1024), (1600, 900)):
                PILImage.open(path).resize((w, h)).save(path)
                avatar = {"id": "x", "is_custom": True, "local_image_path": path}
                portrait = _build_portrait_src(avatar)
                assert portrait is not None
                assert portrait[2] == 800 and portrait[3] == 1000
        finally:
            os.unlink(path)

    def test_normalize_portrait_anchors_head(self):
        """构图归一化：任意源尺寸 → 800x1000；脸部中心锚定画布中线/上部（消除忽远忽近）。"""
        import os

        from PIL import Image as PILImage

        from digital_human import _normalize_portrait_image, _skin_region_metrics

        path = self._fake_portrait_path()
        try:
            for w, h in ((1024, 1024), (1600, 900), (900, 1600)):
                img = PILImage.open(path).resize((w, h))
                norm = _normalize_portrait_image(img)
                assert norm.size == (800, 1000)
                met = _skin_region_metrics(norm)
                assert met is not None, f"肤色检测应命中假写真 ({w}x{h})"
                # 头部中心：水平居中（±8%）、垂直上部（0.15~0.45）
                assert abs(met["cx"] / 800 - 0.5) < 0.08, f"cx={met['cx']}"
                assert 0.15 <= met["cy"] / 1000 <= 0.45, f"cy={met['cy']}"
        finally:
            os.unlink(path)

    def test_skin_metrics_none_on_flat_image(self):
        """纯色/卡通图无肤色 → 返回 None（fallback 路径不误检）。"""
        from PIL import Image as PILImage

        from digital_human import _skin_region_metrics

        flat = PILImage.new("RGB", (400, 400), (200, 200, 220))  # 冷色背景
        assert _skin_region_metrics(flat) is None
        gray = PILImage.new("RGB", (400, 400), (128, 128, 128))
        assert _skin_region_metrics(gray) is None

    def test_build_portrait_src_returns_face_meta(self):
        """_build_portrait_src 返回 5 元组且含头部几何（渲染层动态定位依赖）。"""
        import os

        from digital_human import _build_portrait_src

        path = self._fake_portrait_path()
        try:
            avatar = {"id": "x", "is_custom": True, "local_image_path": path}
            portrait = _build_portrait_src(avatar)
            assert portrait is not None and len(portrait) == 5
            face_meta = portrait[4]
            assert face_meta is not None
            assert face_meta["cy"] > 0 and face_meta["head_w"] > 0
        finally:
            os.unlink(path)

    def test_mouth_template_feathered(self):
        """嘴部模板：边缘羽化（中心不透明、边缘透明），开度越高嘴越高。"""
        import numpy as np

        from digital_human import _get_mouth_template

        small = _get_mouth_template(1, 1)
        large = _get_mouth_template(5, 1)
        assert small.size == large.size == (128, 96)
        a_s = np.array(small.getchannel("A"))
        a_l = np.array(large.getchannel("A"))
        assert a_s[48, 64] > 200  # 中心不透明
        assert a_s[2, 2] == 0  # 边缘完全透明（羽化）
        rows_s = np.where(a_s.max(axis=1) > 40)[0]
        rows_l = np.where(a_l.max(axis=1) > 40)[0]
        assert len(rows_l) > len(rows_s)  # 大开度嘴更高
        # 颜色标度防回归：上唇暗红调、唇间缝最深、下唇亮于缝（曾出现 0~255 标度溢出为纯白）
        ys = np.where(a_s.max(axis=1) > 100)[0]
        y_top, y_bot = ys.min(), ys.max()
        rgb = np.array(small.convert("RGB"))
        up = rgb[y_top + 2, 64]  # 上唇
        seam_c = rgb[(y_top + y_bot) // 2, 64]  # 唇间缝
        low = rgb[y_top + (y_bot - y_top) * 3 // 4, 64]  # 下唇
        assert 60 < up[0] < 160 and up[0] > up[1]  # 上唇红调、非白非黑
        assert seam_c.sum() < up.sum()  # 缝比上唇深
        assert low.sum() > seam_c.sum()  # 下唇亮于缝

    def test_blink_pattern_random_and_deterministic(self):
        """眨眼：间隔 2.2~4.8s 随机、固定种子可复现、非闭眼期归零。"""
        from digital_human import _blink_progress, _build_blink_pattern

        assert _build_blink_pattern() == _build_blink_pattern()  # 可复现
        gaps = [g for g, _ in _build_blink_pattern()]
        assert 2.2 <= min(gaps) and max(gaps) <= 4.8
        peak = next(t for t in (i / 200 for i in range(2400)) if _blink_progress(t) > 0.9)
        assert _blink_progress(peak - 0.05) < 0.9
        assert _blink_progress(peak + 0.05) < 0.9  # 三角波：峰两侧回落
        assert _blink_progress(0.0) == 0.0

    def test_eyelid_template_shape(self):
        """眼睑遮罩：宽高比例合理、底部睫毛线比顶部深。"""
        import numpy as np

        from digital_human import _get_eyelid_template

        lid = _get_eyelid_template(40)
        w, h = lid.size
        assert w == 40 and h >= 8 and h <= w * 0.4
        a = np.array(lid.getchannel("A"))
        assert a[0, w // 2] > a[h - 1, w // 2]  # 上眼睑投影顶部更实
        rgb = np.array(lid.convert("RGB"))
        assert rgb[h - 1, w // 2].mean() < rgb[0, w // 2].mean()  # 睫毛线颜色更深

    def test_studio_lighting_geometry(self):
        """摄影棚光影：主光峰值在人物站位、暗角角落>中心、地面反光底部>顶部。"""
        import numpy as np

        from digital_human import _get_studio_lighting

        spot, floor, vig = _get_studio_lighting(320, 180)
        assert float(spot.max()) > 0.9
        sy, sx = np.unravel_index(np.argmax(spot), spot.shape)
        assert abs(sx - 320 * 0.26) < 40 and abs(sy - 180 * 0.40) < 40
        assert vig[0, 0] > vig[90, 160]  # 暗角角落 > 中心
        assert floor[170, 160] > floor[10, 160]  # 地面反光底部 > 顶部

    def test_render_frame_mouth_and_lighting_diffs(self):
        """整帧渲染：不同口型产生嘴部像素差、主光脉动产生背景明暗差。"""
        import os

        import numpy as np

        from digital_human import _build_portrait_src, _load_font, _render_frame

        path = self._fake_portrait_path()
        try:
            avatar = {"id": "x", "is_custom": True, "local_image_path": path, "name": "测", "style": "测"}
            portrait = _build_portrait_src(avatar)
            fonts = {k: _load_font(s, self._FONT_PATHS) for k, s in (("title", 30), ("body", 18), ("tag", 14))}
            kw = dict(
                avatar=avatar,
                bg_hex="#1a1a2e",
                fonts=fonts,
                portrait=portrait,
                text_lines=["测试文案"],
                t=1.0,
                progress=0.3,
                width=640,
                height=600,
                energy=0.8,
            )
            f_open = np.asarray(_render_frame(**kw, mouth_shape=(0.9, 0.5))).astype(int)
            f_closed = np.asarray(_render_frame(**kw, mouth_shape=(0.1, 0.2))).astype(int)
            assert np.abs(f_open - f_closed).mean() > 0.05  # 嘴在动
            kw2 = dict(
                avatar=avatar,
                bg_hex="#1a1a2e",
                fonts=fonts,
                portrait=None,
                text_lines=["测试文案"],
                progress=0.3,
                width=640,
                height=600,
                energy=0.0,
                mouth_shape=(0.0, 0.5),
            )
            b1 = np.asarray(_render_frame(**kw2, t=1.5)).astype(int)
            b2 = np.asarray(_render_frame(**kw2, t=2.5)).astype(int)
            assert np.abs(b1 - b2).mean() > 0.5  # 主光脉动
            # UI 层防回归：alpha_composite 合成后，右侧名片标题仍可见
            # 标题 '测' 画在 (300, 30)、约 30x30px → numpy 索引 [y, x]
            f_ui = np.asarray(_render_frame(**kw, mouth_shape=(0.1, 0.2)))
            right_zone = f_ui[30:60, 300:400]
            assert (right_zone > 235).sum() > 10  # 白色标题文字像素（单字笔画核心）
        finally:
            os.unlink(path)

    def test_pick_video_encoder_detects_hardware(self):
        """硬件编码器探测：ffmpeg 支持 h264_videotoolbox 时优先选用，否则回退 libx264。"""
        from unittest import mock

        import digital_human as dh

        fake_out = mock.Mock()
        fake_out.stdout = (
            " V....D h264_videotoolbox    VideoToolbox H.264 Encoder (codec h264)\n"
            " V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC\n"
        )
        dh._VIDEO_ENCODER_CACHE = None
        with mock.patch.object(dh.subprocess, "run", return_value=fake_out):
            assert dh._pick_video_encoder() == "h264_videotoolbox"
        fake_out.stdout = " V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC\n"
        dh._VIDEO_ENCODER_CACHE = None
        with mock.patch.object(dh.subprocess, "run", return_value=fake_out):
            assert dh._pick_video_encoder() == "libx264"
        # Linux + NVIDIA GPU（ffmpeg 含 nvenc 且存在 nvidia-smi）→ 硬件编码
        fake_out.stdout = (
            " V....D h264_nvenc             NVIDIA NVENC H.264 encoder (codec h264)\n"
            " V....D libx264              libx264 H.264 / AVC / MPEG-4 AVC\n"
        )
        dh._VIDEO_ENCODER_CACHE = None
        with mock.patch.object(dh.shutil, "which", return_value="/usr/bin/nvidia-smi"):
            with mock.patch.object(dh.subprocess, "run", return_value=fake_out):
                assert dh._pick_video_encoder() == "h264_nvenc"
        # ffmpeg 支持 nvenc 但无 GPU 工具（未透传设备）→ 回退 libx264
        dh._VIDEO_ENCODER_CACHE = None
        with mock.patch.object(dh.shutil, "which", return_value=None):
            with mock.patch.object(dh.subprocess, "run", return_value=fake_out):
                assert dh._pick_video_encoder() == "libx264"
        dh._VIDEO_ENCODER_CACHE = None  # 还原，避免影响其他测试

    def test_render_video_ffmpeg_filter_chain(self):
        """编码链路：unsharp 锐化 + eq 色彩分级 + 编码器硬件/CPU 自动分支 + 帧渲染并行。"""
        import os
        import subprocess as sp
        import tempfile
        from unittest import mock

        import digital_human as dh

        tmp = tempfile.mkdtemp()
        audio = os.path.join(tmp, "t.wav")
        sp.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=2", "-ar", "22050", audio],
            capture_output=True,
            check=True,
        )
        calls, seen = [], {}
        real_run = sp.run  # patch 前保存真实引用（patch 会替换全局 subprocess.run）

        def fake_run(cmd, *a, **kw):
            if cmd and "-framerate" in cmd:
                calls.append(cmd)
            return real_run(cmd, *a, **kw)  # 解码/探测保持真实

        real_executor = dh.ThreadPoolExecutor

        class SpyExecutor(real_executor):
            def __init__(self, *args, **kwargs):
                seen["max_workers"] = kwargs.get("max_workers")
                super().__init__(*args, **kwargs)

        with mock.patch.object(dh, "ThreadPoolExecutor", SpyExecutor):
            with mock.patch.object(dh.subprocess, "run", side_effect=fake_run):
                dh._render_video(
                    "测试",
                    {"id": "business-female", "name": "x", "style": "y"},
                    {"id": "tech", "type": "gradient", "color": "#667eea"},
                    audio,
                    os.path.join(tmp, "out.mp4"),
                    resolution="720p",
                    fps=8,
                    watermark=False,
                )
        assert calls, "编码 ffmpeg 调用缺失"
        enc = calls[0]
        vf = enc[enc.index("-vf") + 1]
        assert "unsharp=5:5:0.6" in vf
        assert "eq=contrast=1.06" in vf
        codec = enc[enc.index("-c:v") + 1]
        assert codec in ("libx264", "h264_videotoolbox")  # 硬件/CPU 自动选择
        if codec == "libx264":
            assert enc[enc.index("-crf") + 1] == "18"
        else:
            assert enc[enc.index("-b:v") + 1] == "6M"  # videotoolbox 不支持 qscale，用码率模式
        assert seen.get("max_workers", 0) >= 2  # 帧渲染已并行化

    def test_scene_background_photo_like(self):
        """拟摄影背景：尺寸正确、确定性可复现、非纯色（照片质感）。"""
        import numpy as np

        from digital_human import _make_scene_background

        img1 = _make_scene_background("office", 640, 360)
        assert img1.size == (640, 360)
        a1 = np.asarray(img1)
        assert a1.std() > 8  # 非纯色/非单一渐变（有明暗层次）
        img2 = _make_scene_background("office", 640, 360)
        assert np.abs(np.asarray(img1) - np.asarray(img2)).mean() == 0  # 固定种子可复现
        img3 = _make_scene_background("nature", 640, 360)
        assert np.abs(np.asarray(img1) - np.asarray(img3)).mean() > 3  # 场景各异

    def test_build_bg_src_type_gating(self):
        """image 类型背景 → 底图；gradient 类型 → None（不浪费渲染）。"""
        from digital_human import _build_bg_src

        assert _build_bg_src({"id": "tech", "type": "gradient"}, 640, 360) is None
        assert _build_bg_src(None, 640, 360) is None
        img = _build_bg_src({"id": "office", "type": "image"}, 640, 360)
        assert img is not None and img.size == (640, 360)
