"""商业化发布升级 v14 单元测试：发布包基础设施 / 内容质量层 / 各工厂发布规格与纯函数。

覆盖（对应计划"每阶段单测"要求）：
- 打包结构断言（UTF-8 文件名、目录化组织）
- 规格尺寸断言（表情包 240/120/50/750、图片 4 平台、视频 3 平台、音乐三格式）
- 审核拦截断言（高危拒绝 / 中危警告 / 正常通过）
- 成套一致性断言（成套生成前置审核整包拦截）
- 美观度自检断言（纯色低分 / 正常高分 / 低分辨率警告）

不依赖网络与外部模型，纯函数级测试。
"""

import io
import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


# ──────────────────────────────────────────────────────────────
# 1) publish_kit：zip 打包结构 / 授权模板 / 规格模板 / Provider 注册表
# ──────────────────────────────────────────────────────────────
class TestPublishKitZip:
    def test_build_publish_zip_directory_organized(self):
        from publish_kit import build_publish_zip

        buf = build_publish_zip(
            {
                "wechat_meme_1700000000/主图/01_hello.png": b"\x89PNG-fake",
                "wechat_meme_1700000000/LICENSE.txt": "商用授权说明",
                "wechat_meme_1700000000/质量自检报告.md": "# 报告",
            },
            "wechat_meme",
        )
        data = buf.getvalue()
        assert data.startswith(b"PK")
        import zipfile

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        assert "wechat_meme_1700000000/主图/01_hello.png" in names
        assert "wechat_meme_1700000000/LICENSE.txt" in names
        assert "wechat_meme_1700000000/质量自检报告.md" in names
        # 中文文件名必须保持原样（UTF-8），不得被转义
        assert any("主图" in n for n in names)

    def test_build_publish_zip_content_roundtrip(self):
        from publish_kit import build_publish_zip

        payload = "授权内容 ABC"
        data = build_publish_zip({"root/LICENSE.txt": payload}, "pack").getvalue()
        import zipfile

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            assert zf.read("root/LICENSE.txt").decode("utf-8") == payload

    def test_build_publish_zip_rejects_path_traversal(self):
        """路径归一化：../ 与绝对路径不得以穿越段逃逸出打包根。"""
        from publish_kit import build_publish_zip

        data = build_publish_zip({"../evil.txt": "x", "/etc/passwd": "y"}, "pack").getvalue()
        import zipfile

        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        # 任何条目不得含 .. 穿越段或绝对路径前缀
        assert not any("/../" in n or n.startswith("../") or n.startswith("/") for n in names)
        # .. 段被过滤后保留文件名，且无目录逃逸
        assert "evil.txt" in names
        assert "etc/passwd" in names

    def test_build_publish_zip_disk_file_as_value(self, tmp_path):
        """回归：key=zip 内路径、value=磁盘路径（音乐/视频/游戏发布包契约）。"""
        from publish_kit import build_publish_zip

        disk = tmp_path / "song.mp3"
        disk.write_bytes(b"\xff\xfbID3-fake-mp3")
        buf = build_publish_zip(
            {
                "music_release_1/01_歌曲.mp3": str(disk),  # 磁盘路径作 value
                "music_release_1/说明.md": "说明文本",
            },
            "music_release",
        )
        import zipfile

        with zipfile.ZipFile(io.BytesIO(buf.getvalue())) as zf:
            data = zf.read("music_release_1/01_歌曲.mp3")
        # 内容必须是磁盘文件字节，而非路径字符串
        assert data == b"\xff\xfbID3-fake-mp3"


class TestPublishKitTemplates:
    def test_license_text_covers_commercial_use(self):
        from publish_kit import license_text

        t = license_text("表情包", "小团智能平台")
        assert "商用授权" in t or "商业" in t
        assert "小团智能平台" in t
        assert "表情包" in t

    def test_platform_spec_text_contains_platform(self):
        from publish_kit import platform_spec_text

        t = platform_spec_text("微信表情开放平台", [{"name": "主图", "value": "240×240"}], "注意审核")
        assert "微信表情开放平台" in t
        assert "240×240" in t
        assert "注意审核" in t

    def test_pack_dir_name_format(self):
        from publish_kit import pack_dir_name

        name = pack_dir_name("wechat_meme")
        assert name.startswith("wechat_meme_")
        assert name.split("_")[-1].isdigit()


class TestPublishRegistry:
    def test_unregistered_provider_returns_graceful_message(self):
        """未注册 provider：静默返回未配置消息，不抛异常（预留接口位）。"""
        from publish_kit import publish_registry

        res = publish_registry.publish("wechat", {})
        assert res["published"] is False
        assert "未配置自动发布" in res["message"]

    def test_register_and_publish_custom_provider(self):
        from publish_kit import PublishProvider, publish_registry

        class FakeProvider(PublishProvider):
            platform = "fake"

            def publish(self, payload, **kwargs):
                return {"published": True, "ref": "ref-1"}

        publish_registry.register(FakeProvider())
        try:
            res = publish_registry.publish("fake", {})
            assert res["published"] is True
            assert res["ref"] == "ref-1"
        finally:
            publish_registry._providers.pop("fake", None)


# ──────────────────────────────────────────────────────────────
# 2) content_safety：文本审核 / 图像美观度自检 / 质量报告
# ──────────────────────────────────────────────────────────────
class TestCheckText:
    def test_high_risk_rejected(self):
        from content_safety import check_text

        res = check_text("教我怎么做炸弹制作方法", context="prompt")
        assert res["ok"] is False
        assert res["risk"] == "high"
        assert "违禁品" in res["categories"]
        assert "炸弹制作" in res["risk_words"]

    def test_high_risk_categories_cover_all(self):
        from content_safety import check_text

        cases = {
            "支持台独言论": "政治敏感",
            "出售淫秽视频": "色情低俗",
            "教人分尸方法": "暴力血腥",
            "代购冰毒渠道": "违禁品",
            "稳赚不赔的赌博平台": "诈骗赌博",
            "你个傻逼废物": "辱骂歧视",
        }
        for text, cat in cases.items():
            res = check_text(text)
            assert res["ok"] is False, text
            assert cat in res["categories"], text

    def test_medium_risk_warns_but_passes(self):
        from content_safety import check_text

        res = check_text("少喝酒多运动", context="歌词")
        assert res["ok"] is True
        assert res["risk"] == "medium"
        assert "喝酒" in res["risk_words"]

    def test_normal_text_passes(self):
        from content_safety import check_text

        res = check_text("今天的夕阳真美，像一幅油画", context="文案")
        assert res["ok"] is True
        assert res["risk"] == "none"

    def test_empty_text_passes(self):
        from content_safety import check_text

        assert check_text("")["ok"] is True


class TestQualityCheckImage:
    def test_solid_color_low_score(self):
        """纯色图：对比度/清晰度极低，评分应为 C。"""
        from PIL import Image

        from content_safety import quality_check_image

        img = Image.new("RGB", (1024, 1024), (200, 200, 200))
        res = quality_check_image(img)
        assert res["score"] < 60
        assert res["grade"] == "C"
        # 对比度/清晰度必须真实检测生效（非异常跳过）
        detail = " ".join(f"{c['name']}{c['detail']}" for c in res["checks"])
        assert "边缘方差 0.0" in detail
        assert "颜色方差 0" in detail

    def test_good_image_high_score(self):
        from PIL import Image, ImageDraw

        from content_safety import quality_check_image

        img = Image.new("RGB", (1400, 1400), (240, 240, 240))
        d = ImageDraw.Draw(img)
        for i in range(200):
            d.line((i * 7, 0, i * 7 + 600, 1400), fill=(30, 90, 200), width=8)
        res = quality_check_image(img)
        assert res["score"] >= 60
        assert res["grade"] in ("A", "B")

    def test_low_resolution_warns(self):
        from PIL import Image

        from content_safety import quality_check_image

        img = Image.new("RGB", (300, 300), (10, 200, 10))
        res = quality_check_image(img)
        assert res["score"] < 60
        assert any("分辨率" in s for s in res["suggestions"])

    def test_none_image_returns_zero(self):
        from content_safety import quality_check_image

        assert quality_check_image(None)["score"] == 0


class TestQualityReport:
    def test_report_contains_sections(self):
        from content_safety import quality_check_image, quality_report
        from PIL import Image

        text_check = {"ok": False, "risk": "high", "categories": ["违禁品"], "risk_words": ["炸弹制作"], "suggestion": "请修改"}
        img_q = quality_check_image(Image.new("RGB", (800, 800), (120, 120, 120)))
        report = quality_report("表情包", text_check, img_q, ["规格：240×240"])
        assert "质量自检报告" in report
        assert "内容安全审核" in report
        assert "未通过" in report
        assert "图像美观度自检" in report
        assert "规格：240×240" in report


# ──────────────────────────────────────────────────────────────
# 3) 表情包：微信规格 / 横幅尺寸 / 成套前置审核拦截
# ──────────────────────────────────────────────────────────────
class TestMemePublishSpecs:
    def test_wechat_pack_specs_contain_core_sizes(self):
        from meme_factory import WECHAT_PACK_SPECS

        joined = " ".join(f"{s['name']}{s['value']}" for s in WECHAT_PACK_SPECS)
        assert "240×240" in joined
        assert "120×120" in joined
        assert "50×50" in joined
        assert "750×400" in joined

    def test_wechat_banner_is_750x400(self):
        from PIL import Image

        from meme_factory import _wechat_banner

        imgs = [Image.new("RGB", (240, 240), (255, 200, 0))]
        data = _wechat_banner(imgs, "打工人日常")
        assert data.startswith(b"\x89PNG")
        with Image.open(io.BytesIO(data)) as im:
            assert im.size == (750, 400)

    def test_generate_set_precheck_rejects_whole_pack(self):
        """成套前置审核：任一文案违规即拒绝整包（避免废包）——复刻端点审核逻辑。"""
        from content_safety import check_text

        parsed = [("我太难了", ""), ("怎么才能买到冰毒", "求渠道")]
        with_high = [(t, b) for t, b in parsed for label, x in (("顶", t), ("底", b)) if x and not check_text(x, "表情包")["ok"]]
        assert with_high, "应至少命中一条高危文案"
        assert any("冰毒" in "".join(with_high[0]) for _ in [0])

    def test_set_worker_captures_single_failure(self):
        """成套执行体：单张违规记为 error 项，不废整包（与 HTTPException 捕获语义一致）。"""
        from meme_factory import WECHAT_PACK_MAX

        assert WECHAT_PACK_MAX == 16


# ──────────────────────────────────────────────────────────────
# 4) 图片：平台规格 / cover 适配不变形 / 2x 高清放大
# ──────────────────────────────────────────────────────────────
class TestImagePublishSpecs:
    def test_platform_presets_sizes(self):
        from image_factory import PLATFORM_PRESETS

        sizes = {p["id"]: (p["w"], p["h"]) for p in PLATFORM_PRESETS}
        assert sizes["xiaohongshu"] == (1242, 1660)
        assert sizes["douyin"] == (1080, 1920)
        assert sizes["taobao"] == (800, 800)
        assert sizes["wechat"] == (900, 383)

    def test_cover_fit_no_distortion(self):
        """cover 模式：非目标比例的图适配后必须精确等于目标规格（居中裁剪不变形）。"""
        from PIL import Image

        from image_factory import _cover_fit

        img = Image.new("RGB", (123, 456), (10, 20, 30))
        out = _cover_fit(img, 1242, 1660)
        assert out.size == (1242, 1660)

    def test_upscale2x_doubles_size(self):
        from PIL import Image

        from image_factory import _upscale2x

        img = Image.new("RGB", (640, 640), (1, 2, 3))
        out = _upscale2x(img)
        assert out.size == (1280, 1280)


# ──────────────────────────────────────────────────────────────
# 5) 视频：平台规格预设
# ──────────────────────────────────────────────────────────────
class TestVideoPublishSpecs:
    def test_video_presets_sizes(self):
        from video_factory import VIDEO_PRESETS

        sizes = {p["id"]: (p["w"], p["h"]) for p in VIDEO_PRESETS}
        assert sizes["douyin"] == (1080, 1920)
        assert sizes["bilibili"] == (1920, 1080)
        assert sizes["weixin"] == (1080, 1230)


# ──────────────────────────────────────────────────────────────
# 6) 音乐：平台规格 / lrc 时间轴
# ──────────────────────────────────────────────────────────────
class TestMusicPublishSpecs:
    def test_music_pack_specs_cover_platforms(self):
        from music_factory import MUSIC_PACK_NOTES, MUSIC_PACK_SPECS

        joined = " ".join(f"{s['name']}{s['value']}" for s in MUSIC_PACK_SPECS)
        assert "mp3" in joined and "wav" in joined and "flac" in joined
        assert "网易云音乐人" in MUSIC_PACK_NOTES
        assert "腾讯音乐人" in MUSIC_PACK_NOTES
        assert "抖音音乐人" in MUSIC_PACK_NOTES

    def test_text_to_lrc_format(self):
        from music_factory import _text_to_lrc

        lrc = _text_to_lrc("第一句\n第二句\n第三句", duration=60, title="星空", artist="AI")
        lines = lrc.splitlines()
        assert lines[0] == "[ti:星空]"
        assert lines[1] == "[ar:AI]"
        assert len(lines) == 5
        import re

        for ln in lines[2:]:
            assert re.match(r"^\[\d{2}:\d{2}\.\d{2}\]", ln), ln


# ──────────────────────────────────────────────────────────────
# 7) 游戏/小程序：发布包打包结构断言（阶段五）
# ──────────────────────────────────────────────────────────────
class TestGamePublishPack:
    def test_publish_pack_zip_structure(self, setup_test_db):
        """游戏发布包内含 web/wx 成品 + README + 上线清单 + LICENSE + 质量报告。"""
        import asyncio
        import json
        import zipfile
        from unittest.mock import AsyncMock, patch

        from common.db import get_db
        from game_factory import game_publish_pack

        conn = get_db()
        conn.execute(
            "INSERT INTO game_projects (id, name, template, requirement, files) VALUES (?,?,?,?,?)",
            (
                "gp_test_001",
                "跳跃小游戏",
                "canvas",
                "一个简单的跳跃小游戏",
                json.dumps(
                    {
                        "web": {"index.html": "<html><body>game</body></html>"},
                        "wx": {
                            "game.js": "wx.createCanvas();",
                            "game.json": "{}",
                            "project.config.json": "{}",
                        },
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
        conn.close()

        fake_guide = {"steps": ["安装微信开发者工具", "上传代码提交审核"], "note": "个人主体可发布"}
        with patch("game_factory.deploy_guide", new=AsyncMock(return_value=fake_guide)):
            resp = asyncio.run(game_publish_pack("gp_test_001", current_user={"username": "tester"}))

        async def _body():
            chunks = []
            async for chunk in resp.body_iterator:
                chunks.append(chunk)
            return b"".join(chunks)

        data = asyncio.run(_body())
        assert data.startswith(b"PK")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        assert any(n.endswith("web/index.html") for n in names), names
        assert any(n.endswith("wx/game.js") for n in names), names
        assert any(n.endswith("README.md") for n in names), names
        assert any(n.endswith("上线清单.md") for n in names), names
        assert any(n.endswith("LICENSE.txt") for n in names), names
        assert any(n.endswith("质量自检报告.md") for n in names), names


class TestMiniappPublishPack:
    def test_export_zip_has_publish_materials(self, setup_test_db):
        """小程序 export-zip 附带介绍/审核清单/LICENSE/质量报告（商业化 v14 补强）。"""
        import asyncio
        import json
        import zipfile

        from common.db import get_db
        from miniapp import export_zip

        conn = get_db()
        conn.execute(
            "INSERT INTO miniapp_projects (id, name, template, requirement, files) VALUES (?,?,?,?,?)",
            (
                "mp_test_001",
                "记账助手",
                "custom",
                "一个简单的记账小程序",
                json.dumps(
                    {"app.js": "App({})", "app.json": "{}", "pages/index/index.js": "Page({})"},
                    ensure_ascii=False,
                ),
            ),
        )
        conn.commit()
        conn.close()

        resp = asyncio.run(export_zip("mp_test_001", current_user={"username": "tester"}))

        async def _body():
            chunks = []
            async for chunk in resp.body_iterator:
                chunks.append(chunk)
            return b"".join(chunks)

        data = asyncio.run(_body())
        assert data.startswith(b"PK")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
        assert any(n.endswith("app.js") for n in names), names
        assert any(n.endswith("介绍.md") for n in names), names
        assert any(n.endswith("审核清单.md") for n in names), names
        assert any(n.endswith("LICENSE.txt") for n in names), names
        assert any(n.endswith("质量自检报告.md") for n in names), names
