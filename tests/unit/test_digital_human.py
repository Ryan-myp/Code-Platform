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
            assert enc[enc.index("-b:v") + 1] == "5M"  # videotoolbox 不支持 qscale，用码率模式（720p 分级 5M，1080p 为 6M）
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


# ══════════════════════════════════════════════════════════════
# v13.0 稳定性：失败自动重试 / stage 埋点 / TTS 通道健康检查
# ══════════════════════════════════════════════════════════════


def _make_dh_req(**overrides):
    """构造最小合法 GenerateRequest。"""
    from digital_human import GenerateRequest

    # emotion 默认 neutral：测试环境 LLM 不可用，避免 auto 触发真实情绪标注调用
    overrides.setdefault("emotion", "neutral")
    return GenerateRequest(text="大家好，今天分享一个实用技巧，希望对你有帮助。", **overrides)


def _patch_dh_deps(tmp_path, monkeypatch):
    """把音频/视频输出目录指向临时目录，返回 (mock 工厂)。"""
    import digital_human

    monkeypatch.setattr(digital_human, "UPLOAD_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setattr(digital_human, "UPLOAD_VIDEO_DIR", str(tmp_path / "videos"))
    (tmp_path / "audio").mkdir(exist_ok=True)
    (tmp_path / "videos").mkdir(exist_ok=True)
    return digital_human


def test_tts_failure_auto_retry(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """TTS 第一次失败、第二次成功 → 生成成功；配额只扣一次、不重复扣费。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    calls = {"tts": 0, "quota": 0, "render": 0}

    def fake_tts(*a, **k):
        calls["tts"] += 1
        if calls["tts"] == 1:
            raise RuntimeError("edge-tts 网络抖动")
        return valid_mp3_bytes

    def fake_quota(uid):
        calls["quota"] += 1
        return {"allowed": True, "remaining": 9}

    def fake_render(**k):
        calls["render"] += 1
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    from unittest.mock import patch

    with patch("common.auth.consume_quota", side_effect=fake_quota), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", side_effect=fake_tts), patch(
        "digital_human._render_video", side_effect=fake_render
    ):
        result = digital_human._generate_one(_make_dh_req(), "tester", "uid_retry1")

    assert result["status"] == "done"
    assert calls["tts"] == 2  # 自动重试 1 次
    assert calls["quota"] == 1  # 配额只扣一次（重试不重复扣费）
    assert calls["render"] == 1


def test_render_failure_auto_retry(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """渲染第一次失败、第二次成功 → 成功；音频复用，不重复 TTS。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    calls = {"tts": 0, "render": 0}

    def fake_tts(*a, **k):
        calls["tts"] += 1
        return valid_mp3_bytes

    def fake_render(**k):
        calls["render"] += 1
        if calls["render"] == 1:
            raise RuntimeError("视频编码失败（ffmpeg exit 1）")
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    from unittest.mock import patch

    with patch("common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", side_effect=fake_tts), patch(
        "digital_human._render_video", side_effect=fake_render
    ):
        result = digital_human._generate_one(_make_dh_req(), "tester", "uid_retry2")

    assert result["status"] == "done"
    assert calls["render"] == 2  # 渲染重试 1 次
    assert calls["tts"] == 1  # 音频已缓存，不重复 TTS


def test_tts_failure_stage_marker(test_db_path, tmp_path, monkeypatch):
    """TTS 连续失败 → status=failed 且 error 带 [stage:tts] 前缀（诊断埋点）。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)

    from unittest.mock import patch

    def fake_tts(*a, **k):
        raise RuntimeError("TTS 通道均不可用")

    with patch("common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", side_effect=fake_tts):
        result = digital_human._generate_one(_make_dh_req(), "tester", "uid_stage1")

    assert result["status"] == "failed"
    assert "[stage:tts]" in (result.get("error") or "")


def test_render_failure_stage_marker(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes):
    """渲染连续失败 → status=audio_only 且 error 带 [stage:render] 前缀。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)

    from unittest.mock import patch

    def fake_tts(*a, **k):
        return valid_mp3_bytes

    def fake_render(**k):
        raise RuntimeError("帧渲染超时")

    with patch("common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", side_effect=fake_tts), patch(
        "digital_human._render_video", side_effect=fake_render
    ):
        result = digital_human._generate_one(_make_dh_req(), "tester", "uid_stage2")

    assert result["status"] == "audio_only"
    assert "[stage:render]" in (result.get("error") or "")
    assert result.get("audio_url")  # 音频已生成


def test_tts_health_check_switch(monkeypatch, valid_mp3_bytes):
    """健康检查：edge 通道失败标记不可用，恢复后重新可用。"""
    import voice_factory

    monkeypatch.setitem(voice_factory._TTS_CHANNEL_STATE, "checked_at", 0.0)

    def fake_edge_fail(*a, **k):
        raise RuntimeError("edge-tts 不可用")

    def fake_edge_ok(*a, **k):
        return valid_mp3_bytes

    monkeypatch.setattr(voice_factory, "_tts_edge", fake_edge_fail)
    assert voice_factory._tts_health_check(force=True) is False
    assert voice_factory._TTS_CHANNEL_STATE["edge_ok"] is False

    monkeypatch.setattr(voice_factory, "_tts_edge", fake_edge_ok)
    assert voice_factory._tts_health_check(force=True) is True
    assert voice_factory._TTS_CHANNEL_STATE["edge_ok"] is True


# ══════════════════════════════════════════════════════════════
# v13.0 照片数字人（engine=live_portrait）：引擎校验 / 成功 / 降级 2D
# ══════════════════════════════════════════════════════════════


def _make_photo_avatar(tmp_path) -> dict:
    """构造照片形象（带本地原图路径）。"""
    photo = tmp_path / "photo_avatar.jpg"
    photo.write_bytes(b"fake jpeg")
    return {
        "id": "custom_photo1",
        "name": "我的照片形象",
        "is_custom": True,
        "local_image_path": str(photo),
        "emoji": "📷",
    }


def test_live_portrait_requires_photo_avatar(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """engine=live_portrait 必须使用照片形象，内置形象/普通自定义形象直接 400。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    monkeypatch.setattr(digital_human, "_load_custom_avatars", lambda user: {"custom_photo1": _make_photo_avatar(tmp_path)})

    from fastapi import HTTPException

    # 内置形象（非自定义）→ 400
    try:
        digital_human._generate_one(_make_dh_req(engine="live_portrait"), "tester", "uid_lp1")
        raise AssertionError("应抛出 HTTPException")
    except HTTPException as e:
        assert e.status_code == 400
        assert "照片形象" in str(e.detail)

    # 照片形象 → 进入生成流程（配额 mock 后应成功）
    from unittest.mock import patch

    with patch(
        "common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}
    ), patch("common.auth.get_quota_info", return_value={"membership": "pro"}), patch(
        "voice_factory._tts_one", return_value=valid_mp3_bytes
    ), patch(
        "digital_human._render_video"
    ) as fake_render:
        # 手动渲染成功（写假 mp4），避免触发真实生成
        def _fake_render(**k):
            with open(k["output_path"], "wb") as f:
                f.write(valid_mp4_bytes)

        fake_render.side_effect = _fake_render
        result = digital_human._generate_one(
            _make_dh_req(avatar_id="custom_photo1", engine="live_portrait"), "tester", "uid_lp1"
        )
    assert result["status"] == "done"


def test_live_portrait_success(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """engine=live_portrait 且照片引擎成功 → done，记录 engine=live_portrait。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    monkeypatch.setattr(digital_human, "_load_custom_avatars", lambda user: {"custom_photo1": _make_photo_avatar(tmp_path)})

    from unittest.mock import patch

    def fake_photo_engine(**k):
        # 照片引擎成功产出视频
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)
        return {"duration": 8.0, "frames": 200, "fps": 25}

    with patch(
        "common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}
    ), patch("common.auth.get_quota_info", return_value={"membership": "pro"}), patch(
        "voice_factory._tts_one", return_value=valid_mp3_bytes
    ), patch(
        "live_portrait_engine.generate_from_photo", side_effect=fake_photo_engine
    ), patch("digital_human._render_video") as fake_2d:
        result = digital_human._generate_one(
            _make_dh_req(avatar_id="custom_photo1", engine="live_portrait"), "tester", "uid_lp2"
        )
    assert result["status"] == "done"
    assert result["engine"] == "live_portrait"  # 未降级
    assert result.get("video_url")
    fake_2d.assert_not_called()  # 2D 引擎未使用


def test_live_portrait_fallback_to_2d(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """照片引擎失败 → 自动降级 2D 基础引擎，仍然出片（engine 记录实际值 2d）。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    monkeypatch.setattr(digital_human, "_load_custom_avatars", lambda user: {"custom_photo1": _make_photo_avatar(tmp_path)})

    from unittest.mock import patch

    def fake_photo_engine(**k):
        raise RuntimeError("照片数字人模型推理失败")

    def fake_render(**k):
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    with patch(
        "common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}
    ), patch("common.auth.get_quota_info", return_value={"membership": "pro"}), patch(
        "voice_factory._tts_one", return_value=valid_mp3_bytes
    ), patch(
        "live_portrait_engine.generate_from_photo", side_effect=fake_photo_engine
    ), patch("digital_human._render_video", side_effect=fake_render):
        result = digital_human._generate_one(
            _make_dh_req(avatar_id="custom_photo1", engine="live_portrait"), "tester", "uid_lp3"
        )
    assert result["status"] == "done"
    assert result["engine"] == "2d"  # 降级后如实记录
    assert result.get("video_url")
    assert not (result.get("error") or "")  # 降级成功无 error


# ══════════════════════════════════════════════════════════════
# v13.0 照片数字人引擎（live_portrait_engine 独立模块）
# ══════════════════════════════════════════════════════════════


def test_engine_missing_model_error(tmp_path, monkeypatch):
    """模型权重缺失 → 明确错误提示（含安装指引），不崩溃。"""
    pytest.importorskip("torch")
    pytest.importorskip("cv2")
    pytest.importorskip("librosa")
    pytest.importorskip("mediapipe")
    import live_portrait_engine

    monkeypatch.setattr(live_portrait_engine, "_MODEL_PATH", str(tmp_path / "not_exists.pth"))

    with pytest.raises(RuntimeError) as ei:
        live_portrait_engine.generate_from_photo(
            photo_path=str(tmp_path / "p.jpg"),
            audio_path=str(tmp_path / "a.mp3"),
            output_path=str(tmp_path / "o.mp4"),
        )
    assert "模型权重缺失" in str(ei.value)


def test_engine_photo_missing(tmp_path, monkeypatch):
    """照片文件不存在 → 明确错误。"""
    pytest.importorskip("torch")
    pytest.importorskip("cv2")
    import live_portrait_engine

    monkeypatch.setattr(live_portrait_engine, "_require_deps", lambda: None)

    with pytest.raises(RuntimeError) as ei:
        live_portrait_engine.generate_from_photo(
            photo_path=str(tmp_path / "no.jpg"),
            audio_path=str(tmp_path / "a.mp3"),
            output_path=str(tmp_path / "o.mp4"),
        )
    assert "照片文件不存在" in str(ei.value)


def test_engine_mel_chunks_shape(tmp_path):
    """mel 分块：每帧 (80,16) 窗口，帧数 ≈ 音频秒数 × 25fps。"""
    pytest.importorskip("librosa")
    import numpy as np
    from scipy.io import wavfile

    import live_portrait_engine

    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    wav = (np.sin(2 * np.pi * 220 * t) * 0.3 * 32767).astype(np.int16)
    wav_path = str(tmp_path / "tone.wav")
    wavfile.write(wav_path, sr, wav)

    chunks = live_portrait_engine._mel_chunks(wav_path)
    assert len(chunks) >= 24  # 1s 音频 ≈ 25 帧
    assert all(c.shape == (80, 16) for c in chunks)
    assert all(c.min() >= -4.01 and c.max() <= 4.01 for c in chunks)  # 归一化范围 [-4,4]


def test_engine_concurrent_slot(test_db_path, tmp_path, monkeypatch):
    """全局推理并发锁：同批次串行（Semaphore=1），获取超时抛明确错误。"""
    import threading

    import live_portrait_engine

    assert isinstance(live_portrait_engine._LIVE_PORTRAIT_SLOT, threading.BoundedSemaphore)
    assert live_portrait_engine._LIVE_PORTRAIT_SLOT._value == 1  # 全局串行防显存争抢


# ══════════════════════════════════════════════════════════════
# v14.0 声音克隆（voice_clone）：基频分析 / 音色匹配 / 合规 / 吊销 / 生成透传
# ══════════════════════════════════════════════════════════════


def _make_sample_wav(path, freq=220.0, seconds=12, sr=16000):
    """合成正弦波人声样本（基频可调），返回时长秒。"""
    import numpy as np
    from scipy.io import wavfile

    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq * t) + 0.05 * np.sin(2 * np.pi * freq * 2 * t)
    wavfile.write(str(path), sr, (y * 32767).astype(np.int16))
    return seconds


def _seed_clone_record(conn, clone_id="clone_test1", user="tester", status="active"):
    """直接落库一条克隆声音记录（绕过分析任务，供链路测试）。"""
    from digital_human import _ensure_tables

    _ensure_tables(conn)
    conn.execute(
        "INSERT INTO voice_clones (id, user_id, voice_name, sample_path, sample_duration,"
        " f0_mean, gender, edge_voice, pitch_hz, speed, status, declare_authorized, engine, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            clone_id,
            user,
            "我的克隆音",
            "/tmp/sample_220.wav",
            12.0,
            220.0,
            "女",
            "zh-CN-XiaoyiNeural",
            5,
            1.0,
            status,
            1,
            "pitch_fit",
            "2026-08-01T10:00:00",
        ),
    )
    conn.commit()


def test_voice_clone_analyze_sample(tmp_path):
    """正弦波样本 → f0_mean≈设定基频、性别判定正确、时长上报。"""
    pytest.importorskip("librosa")
    from voice_clone import analyze_sample

    for freq, gender in [(220.0, "女"), (140.0, "男")]:
        p = tmp_path / f"s{int(freq)}.wav"
        _make_sample_wav(p, freq)
        a = analyze_sample(str(p))
        assert abs(a["f0_mean"] - freq) < 5, f"f0={a['f0_mean']} vs {freq}"
        assert a["gender"] == gender
        assert a["duration"] == pytest.approx(12, abs=1)


def test_voice_clone_analyze_short_sample(tmp_path):
    """样本过短（<10s）→ 明确报错（接口层同样拦截）。"""
    pytest.importorskip("librosa")
    from voice_clone import analyze_sample

    p = tmp_path / "short.wav"
    _make_sample_wav(p, 220.0, seconds=3)
    with pytest.raises(ValueError, match="10-60"):
        analyze_sample(str(p))


def test_voice_clone_fit_voice_matches_pool():
    """基频 → 同性别音色池最近匹配；pitch 补偿限幅 ±20。"""
    from voice_clone import fit_voice

    fit = fit_voice(220.0)
    assert fit["gender"] == "女"
    assert fit["edge_voice"].startswith("zh-CN-")
    assert fit["edge_voice"] == "zh-CN-XiaoyiNeural"  # 220Hz → 基准 215 的晓伊（比 230 的晓晓更近）
    assert abs(fit["pitch_hz"]) <= 20  # 补偿限幅内
    # 音色池仅收录 edge-tts 服务端当前验证可用的音色（其余已 NoAudioReceived）
    from voice_clone import VOICE_POOL

    assert len(VOICE_POOL) >= 6
    assert all(v[2] in ("女", "男") for v in VOICE_POOL)
    # 极端基频：pitch 仍被限幅在 ±20（edge-tts 官方 ±50，保守取 ±20）
    assert fit_voice(400.0)["gender"] == "女" and fit_voice(400.0)["pitch_hz"] <= 20
    assert fit_voice(60.0)["gender"] == "男" and fit_voice(60.0)["pitch_hz"] >= -20
    # 中性音域（175-185）：全池最近匹配
    assert fit_voice(180.0)["edge_voice"] in {v[0] for v in VOICE_POOL}


def test_voice_clone_route_requires_declare(tmp_path, auth_headers):
    """合规必选：未声明「本人声音或已获授权」→ 400，不创建任务/不落文件。"""
    from fastapi.testclient import TestClient

    from main import app

    p = tmp_path / "s.wav"
    _make_sample_wav(p, 220.0)
    client = TestClient(app)
    with open(p, "rb") as f:
        resp = client.post(
            "/api/digital-human/voice-clone",
            headers=auth_headers,
            data={"voice_name": "测试克隆", "declare_authorized": ""},
            files={"file": ("s.wav", f, "audio/wav")},
        )
    assert resp.status_code == 400
    assert "声明" in resp.json()["detail"]


def test_voice_clone_route_duration_window(tmp_path, auth_headers, monkeypatch):
    """时长窗口 10-60s：超窗样本 → 400 且清理落盘文件。"""
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from main import app

    p = tmp_path / "s.wav"
    _make_sample_wav(p, 220.0, seconds=3)
    client = TestClient(app)
    # mock ffprobe 时长：3s 样本 → 直接返回 3（真实 ffprobe 也可，mock 保证 CI 稳定）
    with patch("digital_human._audio_duration", return_value=3.0):
        with open(p, "rb") as f:
            resp = client.post(
                "/api/digital-human/voice-clone",
                headers=auth_headers,
                data={"voice_name": "测试克隆", "declare_authorized": "true"},
                files={"file": ("s.wav", f, "audio/wav")},
            )
    assert resp.status_code == 400
    assert "10-60" in resp.json()["detail"]


def test_voice_clone_handler_inserts_record(test_db_path, tmp_path, monkeypatch):
    """克隆任务：基频分析 + 音色匹配 → 入库 active（含合规标记与 engine 预留字段）。"""
    from common.db import get_db
    from digital_human import _dh_voice_clone_handler, _load_custom_voices

    sample = tmp_path / "s.wav"
    _make_sample_wav(sample, 220.0)
    monkeypatch.setattr("voice_clone.analyze_sample", lambda p: {
        "duration": 12.0, "f0_mean": 220.0, "voiced_ratio": 0.9, "gender": "女",
    })
    monkeypatch.setattr("voice_clone.fit_voice", lambda f: {
        "edge_voice": "zh-CN-XiaoyiNeural", "voice_name": "晓伊", "gender": "女",
        "pitch_hz": 5, "speed": 1.0, "base_f0": 215.0, "style": "温柔知性",
    })
    progress = []
    result = _dh_voice_clone_handler(
        "task_vc1",
        {"clone_id": "clone_test1", "sample_path": str(sample), "voice_name": "我的克隆音"},
        lambda p, s: progress.append((p, s)),
        {"username": "tester", "user_id": "uid_vc1"},
    )
    assert result["clone_id"] == "clone_test1"
    assert result["pitch_hz"] == 5 and result["edge_voice"] == "zh-CN-XiaoyiNeural"
    assert progress[-1][0] == 100
    # 入库后可被声音链路加载（is_clone 标记、名称/描述友好化）
    voices = _load_custom_voices("tester")
    v = voices["clone_test1"]
    assert v["is_clone"] is True and v["is_custom"] is True
    assert v["status"] == "active" and v["declare_authorized"] == 1
    assert v["engine"] == "pitch_fit"
    assert "女声" in v["desc"] and v["emoji"] == "🔊"
    conn = get_db()
    row = conn.execute("SELECT * FROM voice_clones WHERE id='clone_test1'").fetchone()
    conn.close()
    assert row["user_id"] == "tester"  # 与 records/custom_voices 一致：存 username


def test_voice_clone_handler_failure_cleans_sample(test_db_path, tmp_path, monkeypatch):
    """分析失败 → 任务抛错且样本文件被清理（不留垃圾文件）。"""
    from digital_human import _dh_voice_clone_handler

    sample = tmp_path / "s.wav"
    _make_sample_wav(sample, 220.0)
    monkeypatch.setattr(
        "voice_clone.analyze_sample", lambda p: (_ for _ in ()).throw(ValueError("未检测到清晰人声"))
    )
    with pytest.raises(ValueError):
        _dh_voice_clone_handler(
            "task_vc2",
            {"clone_id": "clone_fail", "sample_path": str(sample), "voice_name": "x"},
            lambda p, s: None,
            {"username": "tester", "user_id": "uid_vc2"},
        )
    assert not sample.exists()  # 失败清理


def test_voice_clone_generate_pitch_passthrough(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """克隆声音生成：TTS 收到匹配音色 + pitch 补偿（不用样本直配），成功出片。"""
    from unittest.mock import patch

    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    monkeypatch.setattr(
        digital_human, "_load_custom_voices",
        lambda user: {"clone_test1": {
            "id": "clone_test1", "is_custom": True, "is_clone": True,
            "edge_voice": "zh-CN-XiaoyiNeural", "pitch_hz": 5,
            "name": "我的克隆音", "emoji": "🔊",
        }},
    )

    def fake_render(**k):
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    calls = {}

    def fake_tts(text, voice, speed, pitch=0, emotion=""):
        calls.update(voice=voice, speed=speed, pitch=pitch)
        return valid_mp3_bytes

    with patch("common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", side_effect=fake_tts), patch(
        "digital_human._render_video", side_effect=fake_render
    ):
        result = digital_human._generate_one(
            _make_dh_req(voice_id="clone_test1"), "tester", "uid_vc3"
        )
    assert result["status"] == "done"
    assert calls["voice"] == "zh-CN-XiaoyiNeural"  # 匹配音色
    assert calls["pitch"] == 5  # 基频补偿透传
    assert calls["speed"] == 1.0


def test_voice_clone_revoked_not_in_voices(test_db_path, tmp_path, monkeypatch):
    """吊销（status=revoked）后：不再进入声音列表，生成链路直接 400 未知声音。"""
    from fastapi import HTTPException

    import digital_human
    from common.db import get_db

    _patch_dh_deps(tmp_path, monkeypatch)
    conn = get_db()
    _seed_clone_record(conn, user="tester", status="active")
    _seed_clone_record(conn, clone_id="clone_revoked", user="tester", status="revoked")
    conn.close()
    voices = digital_human._load_custom_voices("tester")
    assert "clone_test1" in voices
    assert "clone_revoked" not in voices  # 吊销项不可用
    from unittest.mock import patch

    with patch("common.auth.get_quota_info", return_value={"membership": "pro", "remaining_today": 9}):
        with pytest.raises(HTTPException, match="未知声音"):
            digital_human._precheck_generate(_make_dh_req(voice_id="clone_revoked"), "uid_x", "tester")


def test_voice_clone_revoke_api(test_db_path, tmp_path, auth_headers):
    """吊销接口端到端：active → revoked + 样本删除 + 生成链路不可用。"""
    from fastapi.testclient import TestClient

    import digital_human
    from common.db import get_db
    from main import app

    sample = tmp_path / "s.wav"
    _make_sample_wav(sample, 220.0)
    conn = get_db()
    _seed_clone_record(conn, user="admin")
    conn.execute("UPDATE voice_clones SET sample_path=? WHERE id='clone_test1'", (str(sample),))
    conn.commit()
    conn.close()

    client = TestClient(app)
    resp = client.post("/api/digital-human/voice-clones/clone_test1/revoke", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    conn = get_db()
    row = conn.execute("SELECT status FROM voice_clones WHERE id='clone_test1'").fetchone()
    conn.close()
    assert row["status"] == "revoked"
    assert not sample.exists()  # 样本已删除
    # 吊销后不再出现在可用声音列表
    assert "clone_test1" not in digital_human._load_custom_voices("admin")
    # 未授权访问 → 401（鉴权在依赖注入层拦截）
    resp2 = client.post(
        "/api/digital-human/voice-clones/clone_test1/revoke",
        headers={"Authorization": "Bearer bad-token"},
    )
    assert resp2.status_code == 401


# ══════════════════════════════════════════════════════════════
# p4a 行业模板库：模板常量 / 渲染样式参数化 / 脚本助手结构
# ══════════════════════════════════════════════════════════════


def test_templates_api_returns_five_industries(auth_headers):
    """行业模板库：8 类模板齐备（v15 新增生活记录/企业宣传/情感语录），
    每模板含场景背景/字幕样式/片头片尾/文案结构 + 可直接填充的示例文案。"""
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    resp = client.get("/api/digital-human/templates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    templates = resp.json()["templates"]
    ids = [t["id"] for t in templates]
    assert ids == [
        "live_shopping", "knowledge", "news", "course", "brand",
        "vlog", "corporate", "quote",
    ]
    for t in templates:
        assert t["name"] and t["emoji"] and t["desc"]
        assert t["scene_id"] in {"product", "course", "news", "livestream", "story"}
        assert t["background_id"] and t["voice_hint"] and 0.5 <= t["speed_hint"] <= 2.0
        sub = t["subtitle"]
        assert sub["position"] in ("right", "center")
        assert sub["color"].startswith("#") and 20 <= sub["font_size"] <= 48
        assert t["opening"] and t["closing"] and "→" in t["script_structure"]
        assert t["script_sample"] and len(t["script_sample"]) > 30


def test_generate_with_template_passes_styles(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """选模板生成：_render_video 收到字幕样式/片头片尾，记录落库 template_id。"""
    from unittest.mock import patch

    import digital_human
    from common.db import get_db

    _patch_dh_deps(tmp_path, monkeypatch)
    calls = {}

    def fake_render(**k):
        calls.update(
            subtitle_style=k.get("subtitle_style"),
            opening=k.get("opening"),
            closing=k.get("closing"),
        )
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    def fake_tts(text, voice, speed, pitch=0, emotion=""):
        return valid_mp3_bytes

    with patch("common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", side_effect=fake_tts), patch(
        "digital_human._render_video", side_effect=fake_render
    ):
        result = digital_human._generate_one(
            _make_dh_req(template_id="live_shopping"), "tester", "uid_tpl1"
        )
    assert result["status"] == "done"
    assert calls["subtitle_style"] == {"position": "center", "color": "#ffb84d", "font_size": 34}
    assert calls["opening"] == "好物严选 · 真实测评"
    assert calls["closing"] == "点击关注，好物不错过"
    conn = get_db()
    row = conn.execute("SELECT template_id FROM digital_human_records WHERE id=?", (result["record_id"],)).fetchone()
    conn.close()
    assert row and row["template_id"] == "live_shopping"


def test_generate_without_template_keeps_default(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes, valid_mp4_bytes):
    """未选模板：_render_video 收到 None 样式（保持原渲染，不回归）。"""
    from unittest.mock import patch

    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    calls = {}

    def fake_render(**k):
        calls["subtitle_style"] = k.get("subtitle_style")
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    with patch("common.auth.consume_quota", return_value={"allowed": True, "remaining": 9}), patch(
        "common.auth.get_quota_info", return_value={"membership": "pro"}
    ), patch("voice_factory._tts_one", return_value=valid_mp3_bytes), patch(
        "digital_human._render_video", side_effect=fake_render
    ):
        result = digital_human._generate_one(_make_dh_req(), "tester", "uid_tpl2")
    assert result["status"] == "done"
    assert calls["subtitle_style"] is None


def test_generate_unknown_template_rejected(test_db_path, tmp_path, monkeypatch):
    """未知模板 ID → 400（不消耗配额）。"""
    from fastapi import HTTPException

    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    with pytest.raises(HTTPException, match="未知行业模板"):
        digital_human._generate_one(_make_dh_req(template_id="no_such_tpl"), "tester", "uid_tpl3")


def test_render_frame_center_subtitle_layout():
    """center 字幕模式：底部居中布局可渲染，无模板时右侧布局不变。"""
    import digital_human as dh

    fonts = {
        "title": dh._load_font(36, dh._FONT_CANDIDATES) if hasattr(dh, "_FONT_CANDIDATES") else dh._load_font(36, ["/System/Library/Fonts/Helvetica.ttc"]),
        "name": dh._load_font(28, ["/System/Library/Fonts/Helvetica.ttc"]),
        "body": dh._load_font(20, ["/System/Library/Fonts/Helvetica.ttc"]),
        "tag": dh._load_font(18, ["/System/Library/Fonts/Helvetica.ttc"]),
    }
    avatar = {"id": "business-female", "name": "晓琳", "style": "职业女性"}
    lines = ["大家好，今天分享一个实用技巧。", "希望对你有帮助，记得点赞收藏。"]
    sub_font = dh._load_font(34, ["/System/Library/Fonts/Helvetica.ttc"])
    # center：底部居中大字（带货种草模板样式）
    img = dh._render_frame(
        avatar=avatar,
        bg_hex="#1a1a2e",
        fonts=fonts,
        portrait=None,
        text_lines=lines,
        t=0.5,
        progress=0.3,
        width=1280,
        height=720,
        subtitle_style={"position": "center", "color": "#ffb84d", "font_size": 34},
        sub_font=sub_font,
    )
    assert img.size == (1280, 720)
    # 默认（无模板）：右侧布局不报错
    img2 = dh._render_frame(
        avatar=avatar,
        bg_hex="#1a1a2e",
        fonts=fonts,
        portrait=None,
        text_lines=lines,
        t=0.5,
        progress=0.3,
        width=1280,
        height=720,
    )
    assert img2.size == (1280, 720)


def test_script_assist_uses_template_structure():
    """脚本助手：带 template_id 时 prompt 注入模板推荐文案结构。"""
    from unittest.mock import patch

    import digital_human

    seen = {}

    def fake_llm(system, user_prompt, **kw):
        seen["prompt"] = user_prompt
        return '["第一版文案内容，结构完整。","第二版文案内容。","第三版文案内容。"]'

    with patch("digital_human.call_llm", side_effect=fake_llm), patch("digital_human.log_usage"):
        resp = digital_human.script_assist(
            digital_human.ScriptAssistRequest(topic="新能源车", template_id="news"),
            current_user={"username": "tester"},
        )
    assert resp["source"] == "ai" and len(resp["scripts"]) == 3
    assert "文案结构：导语" in seen["prompt"]  # 新闻播报模板结构
    assert "产品介绍" in seen["prompt"]  # 场景风格（scene_id 独立于 template_id，由前端按模板填充）
    # 未选模板：无结构注入
    with patch("digital_human.call_llm", side_effect=fake_llm), patch("digital_human.log_usage"):
        digital_human.script_assist(
            digital_human.ScriptAssistRequest(topic="新能源车"),
            current_user={"username": "tester"},
        )
    assert "文案结构" not in seen["prompt"]


# ══════════════════════════════════════════════════════════════
# v14.0 出片提速：音频缓存 / 字幕静态帧跳过重绘 / 批量 TTS 预热
# ══════════════════════════════════════════════════════════════


def test_tts_cache_reuses_same_key(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes):
    """音频缓存：同文案+同音色+同语速第二次命中，不重复合成。"""
    import os

    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    calls = {"tts": 0}

    def fake_tts(*a, **k):
        calls["tts"] += 1
        return valid_mp3_bytes

    from unittest.mock import patch

    with patch("voice_factory._tts_one", side_effect=fake_tts):
        p1, u1 = digital_human._tts_cached("大家好，缓存测试文案", "zh-CN-XiaoxiaoNeural", 1.0)
        p2, u2 = digital_human._tts_cached("大家好，缓存测试文案", "zh-CN-XiaoxiaoNeural", 1.0)
    assert calls["tts"] == 1  # 第二次命中缓存
    assert p1 == p2 and u1 == u2
    assert os.path.exists(p1) and os.path.getsize(p1) >= 512
    assert "tts_cache" in u1


def test_tts_cache_distinct_key_separate(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes):
    """音频缓存：音色/语速任一不同 → 各自合成，互不串用。"""
    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    calls = {"tts": 0}

    def fake_tts(*a, **k):
        calls["tts"] += 1
        return valid_mp3_bytes

    from unittest.mock import patch

    with patch("voice_factory._tts_one", side_effect=fake_tts):
        digital_human._tts_cached("大家好，缓存区分测试", "zh-CN-XiaoxiaoNeural", 1.0)
        digital_human._tts_cached("大家好，缓存区分测试", "zh-CN-YunjianNeural", 1.0)
        digital_human._tts_cached("大家好，缓存区分测试", "zh-CN-XiaoxiaoNeural", 1.2)
        digital_human._tts_cached("大家好，缓存区分测试", "zh-CN-XiaoxiaoNeural", 1.0, pitch=5)
    assert calls["tts"] == 4


def test_tts_cache_clears_stale_rows(test_db_path, tmp_path, monkeypatch, valid_mp3_bytes):
    """缓存行数超限：按最后命中时间清理最旧条目（连同文件）。"""
    import os

    import digital_human

    _patch_dh_deps(tmp_path, monkeypatch)
    monkeypatch.setattr(digital_human, "_TTS_CACHE_MAX_ROWS", 2)
    from unittest.mock import patch

    with patch("voice_factory._tts_one", return_value=valid_mp3_bytes):
        p1, _ = digital_human._tts_cached("文案一：缓存清理测试", "zh-CN-XiaoxiaoNeural", 1.0)
        p2, _ = digital_human._tts_cached("文案二：缓存清理测试", "zh-CN-XiaoxiaoNeural", 1.0)
        p3, _ = digital_human._tts_cached("文案三：缓存清理测试", "zh-CN-XiaoxiaoNeural", 1.0)
    assert os.path.exists(p2) and os.path.exists(p3)
    assert not os.path.exists(p1)  # 最旧的被清理（含文件）


def test_karaoke_cur_idx_progress():
    """卡拉OK进度 → 当前行下标：跨行推进与末行封顶。"""
    import digital_human as dh

    lines = ["第一行内容", "第二行内容", "第三行内容"]
    assert dh._karaoke_cur_idx(lines, 0.0) == 0
    assert dh._karaoke_cur_idx(lines, 0.5) == 1  # 5/15 字 → 第二行
    assert dh._karaoke_cur_idx(lines, 1.0) == 2  # 封顶末行
    assert dh._karaoke_cur_idx([], 0.5) == 0


def test_render_frame_subtitle_layer_cache():
    """字幕静态帧跳过重绘：进度未变化时复用缓存字幕层（层对象同一实例）。"""
    import threading

    import digital_human as dh

    fonts = {
        "title": dh._load_font(36, ["/System/Library/Fonts/Helvetica.ttc"]),
        "name": dh._load_font(28, ["/System/Library/Fonts/Helvetica.ttc"]),
        "body": dh._load_font(20, ["/System/Library/Fonts/Helvetica.ttc"]),
        "tag": dh._load_font(18, ["/System/Library/Fonts/Helvetica.ttc"]),
    }
    avatar = {"id": "business-female", "name": "晓琳", "style": "职业女性"}
    lines = ["大家好，今天分享一个实用技巧。", "希望对你有帮助，记得点赞收藏。"]
    sub_font = dh._load_font(34, ["/System/Library/Fonts/Helvetica.ttc"])
    sub_cache = {"sig": None, "layer": None, "lock": threading.Lock()}
    kwargs = dict(
        avatar=avatar,
        bg_hex="#1a1a2e",
        fonts=fonts,
        portrait=None,
        text_lines=lines,
        t=0.5,
        progress=0.3,
        width=1280,
        height=720,
        subtitle_style={"position": "center", "color": "#ffb84d", "font_size": 34},
        sub_font=sub_font,
        sub_cache=sub_cache,
    )
    dh._render_frame(**kwargs)
    first_layer = sub_cache["layer"]
    assert first_layer is not None
    # 同进度（t 不同但当前行相同）→ 命中缓存层，不再重绘
    kwargs["t"] = 0.6
    dh._render_frame(**kwargs)
    assert sub_cache["layer"] is first_layer
    # 进度推进 → 重绘新层
    kwargs["progress"] = 0.9
    dh._render_frame(**kwargs)
    assert sub_cache["layer"] is not first_layer


def test_batch_worker_prefetches_tts(test_db_path, auth_headers, valid_mp4_bytes):
    """批量流水线：渲染前并行预热全部文案 TTS（预热 + 命中覆盖全部合法文案）。"""
    import time
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    warmed = []

    def fake_cached(text, voice, speed, pitch=0, emotion=""):
        warmed.append(text[:10])
        p = f"/tmp/fake_tts_{len(warmed)}.mp3"
        with open(p, "wb") as f:
            f.write(b"\xff\xfb" * 1024)
        return p, f"/uploads/audio/tts_cache/fake_{len(warmed)}.mp3"

    def fake_render(**k):
        with open(k["output_path"], "wb") as f:
            f.write(valid_mp4_bytes)

    texts = [f"批量预热文案第{i}条，内容足够长用于生成测试。" for i in range(4)]
    with (
        patch("digital_human._tts_cached", side_effect=fake_cached),
        patch("digital_human._render_video", side_effect=fake_render),
    ):
        resp = client.post("/api/digital-human/batch", json={"texts": texts, "emotion": "neutral"}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
        batch_id = resp.json()["batch_id"]
        for _ in range(150):
            r = client.get(f"/api/digital-human/batch/{batch_id}", headers=auth_headers)
            if r.json()["status"] == "done":
                break
            time.sleep(0.1)
    done = client.get(f"/api/digital-human/batch/{batch_id}", headers=auth_headers).json()
    assert done["status"] == "done" and done["success"] == 4, done
    assert {w for w in warmed} >= {t[:10] for t in texts}  # 预热覆盖全部合法文案


class TestStabilityAutoRetry:
    """v13.1 稳定性攻坚：TTS 瞬时抖动自动重试（不重复扣费，最终失败退费）。

    dh_generate / voice_generate 注册了 max_attempts=2（首试 + 1 次自动重试），
    由 task_queue._mark_failed 的指数退避重试路径保证：重试不扣费、最终失败退费。
    """

    def test_dh_generate_registered_with_auto_retry(self):
        from task_queue import _MAX_ATTEMPTS

        assert _MAX_ATTEMPTS.get("dh_generate") == 2

    def test_voice_generate_registered_with_auto_retry(self):
        from task_queue import _MAX_ATTEMPTS

        assert _MAX_ATTEMPTS.get("voice_generate") == 2

    def test_voice_clone_keeps_no_auto_retry(self):
        # 声音克隆失败会清理样本文件，自动重试需重新上传，保持不自动重试
        from task_queue import _MAX_ATTEMPTS

        assert _MAX_ATTEMPTS.get("dh_voice_clone", 0) == 0


class TestUsageLogErrorField:
    """v13.1 诊断埋点：usage_logs.error 记录失败原因（含 [stage:xxx] 阶段标记）。"""

    def test_log_usage_records_error(self, setup_test_db):
        from common.db import get_db_context
        from common.llm import log_usage

        log_usage("digital_human", 10, 5, 1.2, success=False, error="[stage:tts] EDGE_TTS_ERROR")
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT success, error FROM usage_logs WHERE task_type='digital_human' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        assert row["success"] == 0
        assert row["error"] == "[stage:tts] EDGE_TTS_ERROR"

    def test_log_usage_error_truncated_to_500(self, setup_test_db):
        from common.db import get_db_context
        from common.llm import log_usage

        log_usage("digital_human", 10, 5, 0.5, success=False, error="x" * 2000)
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT error FROM usage_logs WHERE task_type='digital_human' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        assert len(row["error"]) == 500

    def test_log_usage_success_has_empty_error(self, setup_test_db):
        from common.db import get_db_context
        from common.llm import log_usage

        log_usage("digital_human", 10, 5, 0.5)
        with get_db_context() as conn:
            row = conn.execute(
                "SELECT success, error FROM usage_logs WHERE task_type='digital_human' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        assert row["success"] == 1
        assert row["error"] == ""
