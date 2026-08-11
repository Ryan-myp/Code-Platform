"""小程序工坊 v15 单元测试：模板库扩充 + 提审材料自动生成（app.json 字段核对）。

纯函数级测试（build_review_material / _scan_used_apis）+ 端点集成测试（review-material）。
"""

import json
import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _perfect_files() -> dict:
    """构造一个提审核对全部通过的项目（含 getLocation 且声明完整）。"""
    return {
        "app.js": "App({ onLaunch() {} })",
        "app.json": json.dumps(
            {
                "pages": ["pages/index/index", "pages/mine/mine"],
                "window": {"navigationBarTitleText": "附近探店"},
                "permission": {"scope.userLocation": {"desc": "用于展示附近店铺"}},
                "requiredPrivateInfos": ["getLocation"],
            },
            ensure_ascii=False,
        ),
        "app.wxss": "page { background: #fff; }",
        "project.config.json": '{"appid": "touristappid", "compileType": "miniprogram"}',
        "sitemap.json": '{"rules": [{"action": "allow", "page": "*"}]}',
        "pages/index/index.js": "Page({ data: { shops: [] }, onLoad() { wx.getLocation({ type: 'gcj02' }) } })",
        "pages/index/index.json": '{"navigationBarTitleText": "附近探店"}',
        "pages/index/index.wxml": '<view class="box">{{shops.length}}</view>',
        "pages/index/index.wxss": ".box { color: #333; }",
        "pages/mine/mine.js": "Page({ data: {} })",
        "pages/mine/mine.json": '{"navigationBarTitleText": "我的"}',
        "pages/mine/mine.wxml": "<view>我的</view>",
        "pages/mine/mine.wxss": "",
    }


class TestTemplates:
    """模板库扩充：数量、字段完整性、结构约束。"""

    def test_template_count(self):
        from miniapp import TEMPLATES

        assert len(TEMPLATES) == 12

    def test_template_ids_unique(self):
        from miniapp import TEMPLATES

        ids = [t["id"] for t in TEMPLATES]
        assert len(ids) == len(set(ids))

    def test_new_templates_fields_complete(self):
        from miniapp import TEMPLATES

        for tpl in TEMPLATES:
            assert tpl["id"] and tpl["name"] and tpl["icon"] and tpl["color"] and tpl["description"]
            assert isinstance(tpl["structure"], list) and tpl["structure"], f"{tpl['id']} 缺页面结构"

    def test_v15_templates_exist(self):
        from miniapp import TEMPLATES

        ids = {t["id"] for t in TEMPLATES}
        assert {"survey", "event", "market"} <= ids

    def test_every_template_has_index_page(self):
        from miniapp import TEMPLATES

        for tpl in TEMPLATES:
            assert any(s.startswith("pages/index/index") for s in tpl["structure"]), f"{tpl['id']} 缺首页"


class TestScanUsedApis:
    """代码权限扫描：只扫 js/wxml、去重、命中隐私接口。"""

    def test_detect_location_api(self):
        from miniapp import _scan_used_apis

        files = {"pages/a/a.js": "wx.getLocation({})", "pages/a/a.wxml": "<view>hi</view>"}
        apis = [r["api"] for r in _scan_used_apis(files)]
        assert "wx.getLocation" in apis

    def test_ignore_non_code_files(self):
        from miniapp import _scan_used_apis

        files = {"readme.md": "wx.getLocation", "assets/a.png": "wx.request"}
        assert _scan_used_apis(files) == []

    def test_dedup_across_files(self):
        from miniapp import _scan_used_apis

        files = {"a.js": "wx.request({})", "b.js": "wx.request({})"}
        assert len(_scan_used_apis(files)) == 1


class TestBuildReviewMaterial:
    """提审材料：app.json 字段核对 + 权限扫描 + md 生成。"""

    def test_perfect_project_passes(self):
        from miniapp import build_review_material

        result = build_review_material(_perfect_files(), "附近探店", "shop")
        assert result["ok"] is True, [c for c in result["checks"] if not c["ok"]]
        assert "requiredPrivateInfos" not in "".join(c["detail"] for c in result["checks"])

    def test_empty_files_fails(self):
        from miniapp import build_review_material

        result = build_review_material({}, "空项目", "")
        assert result["ok"] is False
        assert any(c["item"] == "app.json 可解析" and not c["ok"] for c in result["checks"])

    def test_unregistered_page_detected(self):
        from miniapp import build_review_material

        files = _perfect_files()
        files["pages/extra/extra.js"] = "Page({})"
        files["pages/extra/extra.json"] = "{}"
        files["pages/extra/extra.wxml"] = "<view>多</view>"
        files["pages/extra/extra.wxss"] = ""
        result = build_review_material(files, "x", "")
        assert result["ok"] is False
        assert any(c["item"] == "app.json 注册全部页面" and "extra" in c["detail"] for c in result["checks"])

    def test_location_without_declaration_is_error(self):
        from miniapp import build_review_material

        files = _perfect_files()
        app = json.loads(files["app.json"])
        app.pop("permission")
        app.pop("requiredPrivateInfos")
        files["app.json"] = json.dumps(app, ensure_ascii=False)
        result = build_review_material(files, "x", "")
        assert result["ok"] is False
        loc = next(c for c in result["checks"] if "wx.getLocation" in c["item"])
        assert loc["level"] == "error" and "permission.scope.userLocation" in loc["detail"]

    def test_choose_media_requires_private_infos(self):
        from miniapp import build_review_material

        files = _perfect_files()
        files["pages/index/index.js"] = "Page({ onLoad() { wx.chooseMedia({ count: 1 }) } })"
        result = build_review_material(files, "x", "")
        med = next(c for c in result["checks"] if "wx.chooseMedia" in c["item"])
        assert med["level"] == "error" and "requiredPrivateInfos" in med["detail"]

    def test_tabbar_missing_icon_warns(self):
        from miniapp import build_review_material

        files = _perfect_files()
        app = json.loads(files["app.json"])
        app["tabBar"] = {
            "list": [
                {"pagePath": "pages/index/index", "text": "首页", "iconPath": "images/home.png", "selectedIconPath": "images/home-active.png"}
            ]
        }
        files["app.json"] = json.dumps(app, ensure_ascii=False)
        result = build_review_material(files, "x", "")
        tb = next(c for c in result["checks"] if c["item"] == "tabBar 图标资源齐全")
        assert tb["level"] == "warn" and "images/home.png" in tb["detail"]

    def test_missing_nav_title_warns(self):
        from miniapp import build_review_material

        files = _perfect_files()
        app = json.loads(files["app.json"])
        app["window"] = {}
        files["app.json"] = json.dumps(app, ensure_ascii=False)
        result = build_review_material(files, "x", "")
        assert any(c["item"] == "导航栏标题已设置" and c["level"] == "warn" for c in result["checks"])

    def test_invalid_app_json_reported(self):
        from miniapp import build_review_material

        files = _perfect_files()
        files["app.json"] = "{not json"
        result = build_review_material(files, "x", "")
        assert result["ok"] is False
        assert any(c["item"] == "app.json 可解析" and c["level"] == "error" for c in result["checks"])

    def test_material_md_sections(self):
        from miniapp import build_review_material

        result = build_review_material(_perfect_files(), "附近探店", "shop")
        md = result["material"]
        assert "# 《附近探店》微信小程序提审材料" in md
        assert "## 一、项目信息" in md and "## 二、页面清单" in md
        assert "## 三、权限使用清单" in md and "## 六、自检结论" in md
        assert "电商平台" in md  # shop 类目建议
        assert "| pages/index/index |" in md  # 页面清单行

    def test_material_page_desc_from_page_json(self):
        from miniapp import build_review_material

        result = build_review_material(_perfect_files(), "附近探店", "")
        assert "| pages/mine/mine | 我的 |" in result["material"]

    def test_material_failed_summary(self):
        from miniapp import build_review_material

        result = build_review_material({}, "空", "")
        assert "❌" in result["material"] and "不通过" in result["material"]


class TestReviewMaterialEndpoint:
    """review-material 端点：200 正常 / 404 不存在 / 400 无文件。"""

    def _seed(self, files=None):
        from datetime import datetime

        from common.db import get_db
        from miniapp import _ensure_qc_column

        conn = get_db()
        _ensure_qc_column(conn)
        data = _perfect_files() if files is None else files
        conn.execute(
            """INSERT INTO miniapp_projects (id, name, template, requirement, files, qc, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                "mp_review_001",
                "附近探店",
                "shop",
                "一个探店小程序",
                json.dumps(data, ensure_ascii=False),
                "{}",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    def test_endpoint_returns_material(self, auth_headers):
        from fastapi.testclient import TestClient

        from main import app

        self._seed()
        client = TestClient(app)
        resp = client.get("/api/miniapp/mp_review_001/review-material", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "附近探店"
        assert data["ok"] is True
        assert isinstance(data["checks"], list) and data["checks"]
        assert "## 一、项目信息" in data["material"]

    def test_endpoint_404(self, auth_headers):
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        resp = client.get("/api/miniapp/mp_nope/review-material", headers=auth_headers)
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_endpoint_400_empty_files(self, auth_headers):
        from fastapi.testclient import TestClient

        from main import app

        self._seed(files={})
        client = TestClient(app)
        resp = client.get("/api/miniapp/mp_review_001/review-material", headers=auth_headers)
        assert resp.status_code == 400
