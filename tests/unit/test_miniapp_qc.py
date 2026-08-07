"""小程序工坊 QC 门禁单元测试：WXML 标签配对 / 必需文件 / app.json 页面交叉校验。

不依赖网络，纯函数级测试。
"""
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _perfect_files() -> dict:
    """构造一个可通过全部 QC 的完整小程序项目。"""
    return {
        "app.js": "App({ onLaunch() {} })",
        "app.json": json_dumps({"pages": ["pages/index/index", "pages/about/about"]}),
        "app.wxss": "page { background: #fff; }",
        "project.config.json": '{"appid": "touristappid", "compileType": "miniprogram"}',
        "sitemap.json": '{"rules": [{"action": "allow", "page": "*"}]}',
        "pages/index/index.js": "Page({ data: { count: 0 } })",
        "pages/index/index.json": "{}",
        "pages/index/index.wxml": '<view class="box">{{count > 0 ? count : 0}}</view>',
        "pages/index/index.wxss": ".box { color: #333; }",
        "pages/about/about.js": "Page({ data: {} })",
        "pages/about/about.json": "{}",
        "pages/about/about.wxml": "<view>关于</view>",
        "pages/about/about.wxss": "",
    }


def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)


class TestCheckWxmlTags:
    """WXML 标签配对检查：{{}} 占位、void 组件豁免、栈式配对。"""

    def test_balanced_tags_pass(self):
        from miniapp import _check_wxml_tags
        src = """
<view class="a">
  <view wx:for="{{items}}" wx:key="id">
    <text>{{item.name}}</text>
  </view>
  <image src="/a.png"></image>
</view>
"""
        assert _check_wxml_tags(src, "pages/a/a.wxml") is None

    def test_self_closing_and_void_pass(self):
        from miniapp import _check_wxml_tags
        src = "<view><image src='x.png' /><input value='{{v}}' /></view>"
        assert _check_wxml_tags(src, "p.wxml") is None

    def test_unclosed_tag_detected(self):
        from miniapp import _check_wxml_tags
        src = "<view><text>内容</view>"
        err = _check_wxml_tags(src, "p.wxml")
        # 栈式检查：先命中 </view> 与未闭合 <text> 不配对（同为有效拦截）
        assert err is not None and "不配对" in err

    def test_deep_unclosed_reported_as_unclosed(self):
        from miniapp import _check_wxml_tags
        src = "<view><text>内容"  # 完全无闭合标签
        err = _check_wxml_tags(src, "p.wxml")
        assert err is not None and "未闭合标签 <text>" in err

    def test_mismatched_close_detected(self):
        from miniapp import _check_wxml_tags
        src = "<view><block></view></block>"
        err = _check_wxml_tags(src, "p.wxml")
        assert err is not None and "不配对" in err

    def test_extra_close_detected(self):
        from miniapp import _check_wxml_tags
        src = "</view>"
        err = _check_wxml_tags(src, "p.wxml")
        assert err is not None and "多余闭合标签" in err

    def test_expression_with_gt_not_misreported(self):
        """{{count > 0}} 中的 > 不能触发标签解析误报。"""
        from miniapp import _check_wxml_tags
        src = '<view>{{count > 0 ? "大" : "小"}}</view>'
        assert _check_wxml_tags(src, "p.wxml") is None


class TestQcCheck:
    """QC 门禁四组检查：必需文件 / app.json 交叉校验 / WXML / JS 语法。"""

    def test_perfect_project_passes(self):
        from miniapp import _qc_check
        qc = _qc_check(_perfect_files())
        assert qc["ok"] is True, [c for c in qc["checks"] if not c["ok"]]

    def test_missing_required_file(self):
        from miniapp import _qc_check
        files = _perfect_files()
        del files["app.wxss"]
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "必需文件 app.wxss" and not c["ok"] for c in qc["checks"])

    def test_generated_page_not_registered(self):
        from miniapp import _qc_check
        files = _perfect_files()
        files["pages/index/index.js"] = files["pages/index/index.js"]
        files["app.json"] = json_dumps({"pages": ["pages/about/about"]})  # 注册里少了 index
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "app.json 注册全部生成页面" and not c["ok"] for c in qc["checks"])

    def test_registered_page_missing_quartet(self):
        from miniapp import _qc_check
        files = _perfect_files()
        del files["pages/about/about.wxml"]  # 注册页缺四件套之一
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "注册页面四件套齐全" and not c["ok"] for c in qc["checks"])

    def test_wxml_error_captured(self):
        from miniapp import _qc_check
        files = _perfect_files()
        files["pages/index/index.wxml"] = "<view><text>未闭合</view>"
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "WXML 标签配对" and not c["ok"] for c in qc["checks"])

    def test_bad_js_syntax_captured(self):
        from miniapp import _qc_check
        files = _perfect_files()
        files["pages/index/index.js"] = "Page({ data: { count: 0 }"  # 缺右括号
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "JS 语法（node --check）" and not c["ok"] for c in qc["checks"])

    def test_invalid_app_json(self):
        from miniapp import _qc_check
        files = _perfect_files()
        files["app.json"] = "{not json"
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "app.json 可解析" and not c["ok"] for c in qc["checks"])
