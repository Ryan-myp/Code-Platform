#!/usr/bin/env python3
"""工坊 v2 深度优化测试：视频增强 / 小程序 Mock+预览 / PRD 领域注入 /
表情包 GIF+动表情打包 / 数字人 lip-sync v2 / 效率工具箱实算工具"""

import os
import sys
import unittest

BACKEND = os.path.join(os.path.dirname(__file__), "..", "..", "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


class TestToolHubCompute(unittest.TestCase):
    """效率工具箱 v20 实算工具（不消耗 LLM）。"""

    def test_unit_converter_length(self):
        from tool_hub import _compute_unit_converter

        r = _compute_unit_converter({"category": "长度", "from_unit": "km", "to_unit": "m", "value": 1})
        self.assertIn("1,000", r["to"])

    def test_unit_converter_temperature(self):
        from tool_hub import _compute_unit_converter

        r = _compute_unit_converter({"category": "温度", "from_unit": "c", "to_unit": "f", "value": 100})
        self.assertIn("212", r["to"])

    def test_unit_converter_data(self):
        from tool_hub import _compute_unit_converter

        r = _compute_unit_converter({"category": "数据量", "from_unit": "gb", "to_unit": "mb", "value": 2})
        self.assertIn("2,048", r["to"])

    def test_json_formatter(self):
        from tool_hub import _compute_json_formatter

        r = _compute_json_formatter('{"a":1,"b":[1,2]}', {"operation": "格式化", "indent": "2"})
        self.assertIn('"a": 1', r["formatted"])

    def test_json_invalid(self):
        from tool_hub import _compute_json_formatter

        r = _compute_json_formatter("{bad json", {"operation": "校验"})
        self.assertFalse(r.get("valid"))

    def test_password_generator_strength(self):
        from tool_hub import _compute_password_generator

        r = _compute_password_generator({"length": 16, "include_symbols": True, "exclude_ambiguous": True})
        self.assertGreaterEqual(r["strength_score"], 75)
        self.assertEqual(len(r["password"]), 16)

    def test_base64_roundtrip(self):
        from tool_hub import _compute_base64_tool

        enc = _compute_base64_tool("Hello 世界", {"operation": "编码"})
        dec = _compute_base64_tool(enc["output"], {"operation": "解码"})
        self.assertEqual(dec["output"], "Hello 世界")

    def test_color_converter_hex_to_rgb(self):
        from tool_hub import _compute_color_converter

        r = _compute_color_converter("#FF0000", {"input_format": "HEX"})
        self.assertEqual(r["rgb"], "rgb(255, 0, 0)")

    def test_date_add(self):
        from tool_hub import _compute_date_calculator

        r = _compute_date_calculator("2024-01-15 加 30 天", {"calc_type": "日期加减"})
        self.assertEqual(r["target"], "2024-02-14")

    def test_diff_comparator(self):
        from tool_hub import _compute_diff_comparator

        r = _compute_diff_comparator("line1\nline2\n\n---\n\nline1\nline3", {"comparison_mode": "逐行对比"})
        self.assertEqual(r["added_lines"], 1)
        self.assertEqual(r["removed_lines"], 1)

    def test_markdown_table(self):
        from tool_hub import _compute_markdown_table

        r = _compute_markdown_table("姓名,年龄\n张三,28\n李四,32", {"alignment": "左对齐"})
        self.assertIn("张三", r["markdown_table"])

    def test_regex_builder(self):
        from tool_hub import _compute_regex_builder

        r = _compute_regex_builder("匹配邮箱地址", {"language": "Python"})
        self.assertTrue(any("@" in p["regex"] for p in r["patterns"]))

    def test_sql_generator(self):
        from tool_hub import _compute_sql_generator

        r = _compute_sql_generator("查询 users 表中所有数据", {"dialect": "PostgreSQL"})
        self.assertIn("SELECT", r["sql"])


class TestPrdEngineEnhancements(unittest.TestCase):
    """PRD 引擎 v20：领域知识注入 + 结构化审查解析。"""

    def test_domain_knowledge_keys(self):
        from prd_engine import DOMAIN_KNOWLEDGE

        for d in ("e-commerce", "social", "tools", "adtech", "fin-tech"):
            self.assertIn(d, DOMAIN_KNOWLEDGE)

    def test_enhance_review_system(self):
        from prd_engine import _enhance_review_system

        enhanced = _enhance_review_system("base", "e-commerce")
        self.assertIn("电商领域专项审查", enhanced)

    def test_parse_table_issues(self):
        from prd_engine import _parse_review_to_structured

        sample = """## 审查报告
评分：72 / 100
| 编号 | 级别 | 问题描述 | 修改建议 |
| 1 | P0 | 支付回调缺少幂等性 | 加分布式锁 |
| 2 | P1 | 数据库索引缺失 | 加索引 |
"""
        parsed = _parse_review_to_structured(sample, [])
        self.assertEqual(parsed["total_issues"], 2)
        self.assertEqual(parsed["p0_count"], 1)
        self.assertEqual(parsed["p1_count"], 1)
        self.assertEqual(parsed["score"], 72)

    def test_parse_list_issues(self):
        from prd_engine import _parse_review_to_structured

        sample = """## 审查结果
评分 88 / 100

1. **P0** 问题：支付回调缺少幂等性，需加分布式锁
2. **P1** 问题：数据库索引缺失
"""
        parsed = _parse_review_to_structured(sample, [])
        self.assertEqual(parsed["total_issues"], 2)
        self.assertEqual(parsed["p0_count"], 1)

    def test_parse_resolved_filter(self):
        from prd_engine import _parse_review_to_structured

        sample = "| 1 | P0 | 幂等性问题 | x |\n| 2 | P1 | 索引缺失 | y |"
        parsed = _parse_review_to_structured(sample, ["1"])
        self.assertEqual(parsed["total_issues"], 1)
        self.assertEqual(parsed["issues"][0]["id"], "2")


class TestVideoFactoryEnhancements(unittest.TestCase):
    """视频工坊 v20：脚本模板扩展 + 字幕时间格式。"""

    def test_template_count_expanded(self):
        from video_factory import ALL_SCRIPT_TEMPLATES

        self.assertGreaterEqual(len(ALL_SCRIPT_TEMPLATES), 15)

    def test_new_categories(self):
        from video_factory import EXTENDED_SCRIPT_TEMPLATES

        cats = {t["category"] for t in EXTENDED_SCRIPT_TEMPLATES}
        for c in ("Vlog", "广告", "教程", "音乐", "测评"):
            self.assertIn(c, cats)

    def test_srt_time_format(self):
        from video_factory import _secs_to_srt_time

        h, m, s = _secs_to_srt_time(65.5)
        self.assertEqual((h, m, s), (0, 1, 5))

    def test_script_template_has_structure(self):
        from video_factory import EXTENDED_SCRIPT_TEMPLATES

        for t in EXTENDED_SCRIPT_TEMPLATES:
            self.assertIn("structure", t)
            self.assertGreaterEqual(len(t["structure"]), 3)


class TestMiniappEnhancements(unittest.TestCase):
    """小程序工坊 v20：Mock 数据 + 预览 HTML 生成。"""

    def test_mock_templates(self):
        from miniapp import MOCK_DATA_TEMPLATES

        for t in ("shop", "booking", "food", "news"):
            self.assertIn(t, MOCK_DATA_TEMPLATES)

    def test_build_preview_html(self):
        from miniapp import _build_preview_html

        files = {
            "app.json": '{"pages": ["pages/index/index"]}',
            "pages/index/index.wxml": "<view>首页</view>",
            "pages/index/index.js": "Page({data: {name: 'x'}})",
            "pages/index/index.wxss": ".x{color:red}",
        }
        html = _build_preview_html(files, ["index"], {"products": [{"name": "A"}]}, "测试小程序", "shop")
        self.assertIn("测试小程序", html)
        self.assertIn("共 1 个页面", html)
        self.assertIn("preview-page", html)


class TestMemeFactoryEnhancements(unittest.TestCase):
    """表情包工坊 v20：GIF 动图生成 + 微信动表情打包。"""

    def test_make_gif(self):
        from PIL import Image
        from meme_factory import _make_meme_gif

        base = Image.new("RGB", (200, 200), (255, 255, 0))
        gif_data = _make_meme_gif(base, "测试", "文字", "yellow", frame_count=6, fps=10)
        self.assertGreater(len(gif_data), 100)
        self.assertTrue(gif_data[:4].startswith(b"GIF"))

    def test_gif_multi_frame(self):
        from PIL import Image
        from meme_factory import _make_meme_gif

        base = Image.new("RGB", (100, 100), (0, 0, 255))
        gif_data = _make_meme_gif(base, "A", "B", "yellow", frame_count=8, fps=12)
        # 0x2c = GIF image separator，多帧会多次出现
        self.assertGreaterEqual(gif_data.count(b"\x2c"), 2)


class TestDigitalHumanEnhancements(unittest.TestCase):
    """数字人 v20：lip-sync 双源融合 + 增强口型表。"""

    def test_enhanced_shapes(self):
        from digital_human import _ENHANCED_MOUTH_SHAPES

        for k in ("a", "o", "e", "i", "u", "an", "ang", "er"):
            self.assertIn(k, _ENHANCED_MOUTH_SHAPES)

    def test_timeline_build(self):
        from digital_human import _build_script_timeline_v2

        tl = _build_script_timeline_v2("你好世界", 2.0)
        self.assertEqual(len(tl), 4)
        self.assertEqual(tl[0][0], "你")

    def test_mouth_shape_at(self):
        from digital_human import _build_script_timeline_v2, _mouth_shape_at_v2

        tl = _build_script_timeline_v2("你好", 2.0)
        shape = _mouth_shape_at_v2(tl, 0.2, smooth=0.0)
        self.assertEqual(len(shape), 2)
        self.assertTrue(0.0 <= shape[0] <= 1.0)

    def test_blend_mouth_shapes(self):
        from digital_human import _blend_mouth_shapes

        script = [(0.8, 0.5), (0.6, 0.4)]
        audio = [(0.5, 0.5), (0.4, 0.5)]
        blended = _blend_mouth_shapes(script, audio, alpha=0.6)
        self.assertEqual(len(blended), 2)
        self.assertGreaterEqual(blended[0][0], 0.5)
        self.assertLessEqual(blended[0][0], 0.8)


if __name__ == "__main__":
    unittest.main()
