#!/usr/bin/env python3
from common.helpers import _aggregate_compute_results, _execute_common_step, _execute_compute_step, _execute_single_step, _execute_step, _finalize_common_operation, _finalize_results, _finalize_step_results, _initialize_compute_context, _prepare_common_context, _prepare_context, _prepare_step_context, _notify_progress


def _build_review_simple(review_data: dict) -> dict:
    """简化版构建评测材料。"""
    return {
        "title": review_data.get("title", ""),
        "content": review_data.get("content", ""),
        "score": review_data.get("score", 0)
    }

def _prepare_review_params(request_data: dict) -> dict:
    """简化版准备评测参数。"""
    return {
        "template_id": request_data.get("template_id", ""),
        "data": request_data.get("data", {})
    }



from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic, Iterator, Sequence, Mapping, Iterable, Awaitable, Coroutine, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio
from typing import Any, Optional, Union, List, Dict, Tuple, Callable, Set, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from template_base import TemplateBase, create_template
"""小程序工坊 — AI 生成微信小程序项目。

- 内置常用模板（电商/预约/展示/工具/资讯），选模板 + 输入需求 → LLM 生成完整项目代码
- 项目文件树保存到 miniapp_projects（files 为 {path: content} JSON）
- 支持在线预览、复制、ZIP 打包下载（导入微信开发者工具即可运行）
"""

import io
import json
import logging
import re
import time
import uuid
import zipfile
import hashlib
from pathlib import Path
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db
from common.llm import call_llm_async, log_usage, _safe_exc_msg
from content_safety import check_text, quality_report
from publish_kit import license_text, pack_dir_name
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/miniapp", tags=["小程序工坊"])

# 内置模板：结构说明会注入生成 prompt，约束项目骨架
TEMPLATES = [
    {
        "id": "shop",
        "name": "电商购物",
        "description": "商品列表/详情/购物车/结算，适合电商小店、微商城",
        "icon": "🛍️",
        "color": "from-pink-500 to-rose-600",
        "structure": [
            "pages/index/index（首页：轮播+商品列表）",
            "pages/goods/detail（商品详情）",
            "pages/cart/cart（购物车）",
            "pages/order/list（订单列表）",
            "pages/mine/mine（个人中心）",
        ],
    },
    {
        "id": "booking",
        "name": "预约服务",
        "description": "服务列表/预约表单/我的预约，适合美容、家政、咨询等",
        "icon": "📅",
        "color": "from-blue-500 to-cyan-600",
        "structure": [
            "pages/index/index（首页：服务列表）",
            "pages/booking/form（预约表单）",
            "pages/booking/list（我的预约）",
            "pages/mine/mine（个人中心）",
        ],
    },
    {
        "id": "showcase",
        "name": "作品展示",
        "description": "首页/作品集/关于我们，适合个人品牌、作品集、公司官网",
        "icon": "🎨",
        "color": "from-violet-500 to-purple-600",
        "structure": [
            "pages/index/index（首页：Banner+简介）",
            "pages/works/works（作品集）",
            "pages/about/about（关于我们）",
        ],
    },
    {
        "id": "tool",
        "name": "效率工具",
        "description": "记事本/计算器/打卡等轻工具，适合工具型小程序",
        "icon": "🧰",
        "color": "from-amber-500 to-orange-600",
        "structure": [
            "pages/index/index（首页：工具入口）",
            "pages/note/note（记事本）",
            "pages/calc/calc（计算器）",
            "pages/checkin/checkin（打卡）",
        ],
    },
    {
        "id": "news",
        "name": "资讯阅读",
        "description": "文章列表/详情/分类，适合公众号配套、内容社区",
        "icon": "📰",
        "color": "from-emerald-500 to-green-600",
        "structure": [
            "pages/index/index（首页：资讯列表）",
            "pages/article/detail（文章详情）",
            "pages/category/category（分类页）",
        ],
    },
    {
        "id": "food",
        "name": "外卖点餐",
        "description": "菜品列表/购物车/下单结算，适合餐饮门店、外卖商家",
        "icon": "🍜",
        "color": "from-red-500 to-orange-600",
        "structure": [
            "pages/index/index（首页：分类+菜品列表）",
            "pages/cart/cart（购物车与下单）",
            "pages/order/list（我的订单）",
            "pages/mine/mine（个人中心）",
        ],
    },
    {
        "id": "community",
        "name": "社区论坛",
        "description": "帖子列表/发布/详情评论，适合兴趣社群、校园论坛",
        "icon": "💬",
        "color": "from-teal-500 to-cyan-600",
        "structure": [
            "pages/index/index（首页：帖子列表+分类）",
            "pages/post/detail（帖子详情+评论）",
            "pages/post/publish（发布帖子）",
            "pages/mine/mine（个人中心：我的帖子）",
        ],
    },
    {
        "id": "fitness",
        "name": "健身打卡",
        "description": "训练计划/打卡记录/数据统计，适合健身私教、自律打卡",
        "icon": "💪",
        "color": "from-lime-500 to-emerald-600",
        "structure": [
            "pages/index/index（首页：今日训练计划）",
            "pages/train/detail（训练动作详情）",
            "pages/checkin/checkin（打卡记录）",
            "pages/stats/stats（数据统计）",
            "pages/mine/mine（个人中心）",
        ],
    },
    {
        "id": "travel",
        "name": "旅游攻略",
        "description": "目的地/攻略详情/行程规划，适合旅游机构、个人博主",
        "icon": "🧳",
        "color": "from-sky-500 to-blue-600",
        "structure": [
            "pages/index/index（首页：目的地推荐）",
            "pages/spot/detail（目的地详情）",
            "pages/trip/plan（行程规划）",
            "pages/mine/mine（个人中心）",
        ],
    },
    {
        "id": "survey",
        "name": "问卷投票",
        "description": "问卷列表/填写表单/结果统计，适合市场调研、意见收集、投票活动",
        "icon": "📊",
        "color": "from-cyan-500 to-blue-600",
        "structure": [
            "pages/index/index（首页：问卷列表）",
            "pages/survey/detail（问卷详情与填写）",
            "pages/survey/result（结果统计）",
            "pages/mine/mine（个人中心：我的答卷）",
        ],
    },
    {
        "id": "event",
        "name": "活动报名",
        "description": "活动列表/详情报名/我的票券，适合沙龙、会议、演出、课程培训",
        "icon": "🎪",
        "color": "from-orange-500 to-red-600",
        "structure": [
            "pages/index/index（首页：活动列表）",
            "pages/event/detail（活动详情与报名）",
            "pages/event/ticket（我的票券）",
            "pages/mine/mine（个人中心）",
        ],
    },
    {
        "id": "market",
        "name": "二手闲置",
        "description": "闲置列表/发布求购/宝贝详情，适合个人闲置交易、校园跳蚤市场",
        "icon": "🔄",
        "color": "from-yellow-500 to-amber-600",
        "structure": [
            "pages/index/index（首页：闲置列表+分类）",
            "pages/goods/detail（宝贝详情）",
            "pages/publish/publish（发布闲置）",
            "pages/mine/mine（个人中心：我的发布）",
        ],
    },
]

_GENERATE_SYSTEM = """你是资深微信小程序开发工程师，擅长编写视觉效果精美、用户体验优秀的小程序代码。
请根据用户需求生成一个完整的微信小程序项目。

重要提示：用户可以在浏览器中实时预览你的代码（WXML自动转HTML渲染），
因此请注重UI视觉设计：漂亮的配色、合理的间距、精致的卡片布局、清晰的排版层次。

硬性要求：
1. 只输出一个 JSON 对象（不要输出任何解释文字、不要用 markdown 代码块包裹），
   key 为文件路径，value 为文件完整内容
2. 必须包含以下基础文件：app.js、app.json、app.wxss、project.config.json、sitemap.json
3. 页面文件必须包含：pages/<page>/<page>.js、.wxml、.wxss、.json 四件套
4. app.json 中必须正确注册所有页面路径，并设置 window 导航栏标题与颜色
5. 使用微信原生语法（WXML/WXSS/JS），不使用任何第三方框架
6. 数据使用本地 mock（Page data 中硬编码示例数据），丰富真实的示例数据让预览更生动
7. 代码要完整可用、注释清晰，样式美观（WXSS 需完整编写，注重色彩、圆角、阴影、渐变等细节）
8. 图片资源使用 https://images.unsplash.com 等真实图片URL或纯色背景占位
9. 用户需求中的业务逻辑要在代码中真实实现，不要留 TODO
10. 输出必须精简！每个 .wxml 不超过 50 行、.wxss 不超过 70 行、.js 不超过 60 行，
    页面数量 3-5 个，全部文件总字符数必须控制在 30000 以内，严禁超长输出
11. app.json 的 pages 必须注册全部生成的页面文件路径，不得遗漏任何页面
12. 不要使用 tabBar 配置（避免图标资源缺失导致编译警告），导航用自定义按钮或页面内跳转
13. 商用级交互要求（预览体验的关键，全部页面都要做到）：
    - 数据加载：页面 onLoad 中模拟异步加载（setTimeout 300ms + wx.showLoading），完成后 setData 渲染，严禁空白页/未定义数据渲染
    - 空状态：列表无数据时显示友好空状态视图（图标 + 提示文字 + 引导按钮）
    - 交互反馈：按钮点击/提交/删除等关键操作必须有 wx.showToast 成功或失败提示；表单提交前做必填校验（未填时 toast 提示并聚焦对应输入框）
    - 页面分享：所有页面 .js 实现 onShareAppMessage（返回 {title: 页面标题, path: 当前页面路径}）
    - 列表页下拉刷新：页面 json 配置 enablePullDownRefresh: true 并实现 onPullDownRefresh（完成后 wx.stopPullDownRefresh）；列表数据量 ≥ 6 条时实现 onReachBottom 触底加载更多（mock 分页）
14. 细节：
    - 首页轮播/列表图片使用真实图片URL（https://images.unsplash.com/...），图片加载失败时显示渐变色占位背景
    - 导航栏标题与页面内容一致；页面底部留安全间距（padding-bottom: env(safe-area-inset-bottom)）
    - 卡片间距统一（16rpx）、圆角统一（16rpx-24rpx），主色 + 辅助色的配色方案贯穿全站"""


class GenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="项目名称")
    template: str = Field("custom", description="模板 ID")
    requirement: str = Field(..., min_length=2, max_length=2000, description="功能需求")


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象（容忍 ```json 包裹与前后噪音）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("LLM 输出中未找到 JSON 对象")
    return json.loads(text[start : end + 1])


# ─── QC 质量门禁（对齐 game_factory 商用交付标准）──────────────────
# 小程序运行必需的基础文件
_REQUIRED_FILES = ["app.js", "app.json", "app.wxss", "project.config.json", "sitemap.json"]
# WXML 中常自闭合的组件（不要求配对闭合）
_VOID_WXML = {
    "input",
    "image",
    "icon",
    "progress",
    "slider",
    "switch",
    "checkbox",
    "radio",
    "textarea",
    "canvas",
    "video",
    "audio",
    "ad",
}


def _node_check_js(js: str) -> tuple[bool, str]:
    """node --check 语法校验；node 不可用时跳过（避免环境强依赖）。"""
    import os
    import subprocess
    import tempfile

    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
            tmp = f.name
        try:
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                return True, "语法通过"
            return False, (r.stderr or r.stdout or "").strip()[:300]
        finally:
            os.unlink(tmp)
    except FileNotFoundError:
        return True, "node 不可用，跳过"
    except Exception as e:
        return True, f"校验器异常，跳过: {e}"


def _check_wxml_tags(src: str, path: str) -> str | None:
    """WXML 标签配对检查：{{}} 表达式先占位，忽略自闭合/void 组件。"""
    src = re.sub(r"\{\{.*?\}\}", "{{}}", src, flags=re.DOTALL)
    stack = []
    pat = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*)>")
    for m in pat.finditer(src):
        closing, tag, attrs = m.group(1), m.group(2), m.group(3)
        if closing:
            # void 组件的显式闭合（<image></image>）是微信官方合法写法，忽略
            if tag.lower() in _VOID_WXML:
                continue
            if not stack:
                return f"{path}: 多余闭合标签 </{tag}>"
            if stack[-1] != tag:
                return f"{path}: </{tag}> 与最近未闭合 <{stack[-1]}> 不配对"
            stack.pop()
        elif not attrs.rstrip().endswith("/") and tag.lower() not in _VOID_WXML:
            stack.append(tag)
    if stack:
        return f"{path}: 未闭合标签 <{stack[-1]}>"
    return None


def _qc_check(files: dict) -> dict:
    """生成产物质量门禁：必需文件 + app.json 页面注册交叉校验 + WXML 配对 + JS 语法。"""
    checks = []
    # 1. 必需基础文件（app.json 缺失时 worker 会兜底生成，此处主要拦空内容）
    for req in _REQUIRED_FILES:
        ok = req in files and bool(str(files[req]).strip())
        checks.append({"item": f"必需文件 {req}", "ok": ok, "detail": "存在" if ok else "缺失"})
    # 2. app.json 可解析 + 页面注册交叉校验（生成页面必须注册、注册页面必须四件套齐全）
    app_cfg, app_err = {}, ""
    try:
        app_cfg = json.loads(files.get("app.json") or "{}")
    except Exception as e:
        app_err = str(e)
    checks.append({"item": "app.json 可解析", "ok": not app_err, "detail": "OK" if not app_err else app_err})
    if app_cfg:
        registered = set(app_cfg.get("pages") or [])
        generated = {p.rsplit(".", 1)[0] for p in files if p.startswith("pages/")}
        unregistered = sorted(generated - registered)
        checks.append(
            {
                "item": "app.json 注册全部生成页面",
                "ok": not unregistered,
                "detail": "OK" if not unregistered else f"未注册: {unregistered}",
            }
        )
        missing = sorted(
            {f"{rp}.{ext}" for rp in registered for ext in ("js", "wxml", "wxss", "json") if f"{rp}.{ext}" not in files}
        )
        checks.append(
            {"item": "注册页面四件套齐全", "ok": not missing, "detail": "OK" if not missing else f"缺失: {missing}"}
        )
    # 3. WXML 标签配对
    wxml_errors = [e for p in sorted(k for k in files if k.endswith(".wxml")) if (e := _check_wxml_tags(files[p], p))]
    checks.append(
        {
            "item": "WXML 标签配对",
            "ok": not wxml_errors,
            "detail": "OK" if not wxml_errors else "；".join(wxml_errors[:3]),
        }
    )
    # 4. JS 语法（node --check，逐文件）
    js_bad = None
    for p in sorted(k for k in files if k.endswith(".js")):
        ok, msg = _node_check_js(files[p])
        if not ok:
            js_bad = f"{p}: {msg}"
            break
    checks.append(
        {"item": "JS 语法（node --check）", "ok": js_bad is None, "detail": "OK" if js_bad is None else js_bad}
    )
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _ensure_qc_column(conn) -> None:
    """幂等补列：miniapp_projects.qc 存质量门禁报告（JSON）。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(miniapp_projects)").fetchall()]
    if "qc" not in cols:
        conn.execute("ALTER TABLE miniapp_projects ADD COLUMN qc TEXT DEFAULT ''")
        conn.commit()


# ─── 提审材料自动生成（v15）：app.json 字段核对 + 代码权限扫描 + 类目建议 ───
# 服务类目建议（提审时按业务选择，类目与功能不符会被驳回）
_CATEGORY_SUGGEST = {
    "shop": "电商平台 / 商家自营（需营业执照；个人主体可选「商家自营-服饰箱包鞋」等细类）",
    "booking": "生活服务（预约类目，如美业/家政/咨询）",
    "showcase": "工具 / 企业展示",
    "tool": "工具（效率）",
    "news": "资讯（需互联网新闻信息服务资质，个人主体慎选）",
    "food": "餐饮 / 外卖点餐",
    "community": "社交-社区/论坛（需内容安全审核机制）",
    "fitness": "体育 / 健身",
    "travel": "旅游（旅行社业务需资质，个人建议选「旅游-旅游攻略/游记」）",
    "survey": "工具-表单/调查",
    "event": "活动/票务（演出票务需资质，沙龙/课程选「教育-在线视频课程」或「生活服务」）",
    "market": "闲置交易（个人闲置物品交易，禁止商家入驻模式）",
}

# 隐私接口 → 提审声明要求（扫描代码命中后逐项核对 app.json）
# level: 未声明时的核对级别（error=运行/审核硬伤，warn=后台配置类提示）
_PRIVACY_API_RULES = [
    {
        "api": "wx.getLocation",
        "name": "位置信息",
        "desc": "获取用户位置",
        "key": "permission",
        "private": "getLocation",
        "level": "error",
    },
    {
        "api": "wx.chooseLocation",
        "name": "选择位置",
        "desc": "地图选点",
        "key": "private",
        "private": "chooseLocation",
        "level": "error",
    },
    {
        "api": "wx.chooseAddress",
        "name": "收货地址",
        "desc": "获取收货地址",
        "key": "private",
        "private": "chooseAddress",
        "level": "error",
    },
    {
        "api": "wx.chooseInvoiceTitle",
        "name": "发票抬头",
        "desc": "获取发票抬头",
        "key": "private",
        "private": "chooseInvoiceTitle",
        "level": "error",
    },
    {
        "api": "wx.chooseMedia",
        "name": "相册/相机",
        "desc": "选择图片/视频",
        "key": "private",
        "private": "chooseMedia",
        "level": "error",
    },
    {
        "api": "wx.chooseMessageFile",
        "name": "聊天文件",
        "desc": "选择微信聊天文件",
        "key": "private",
        "private": "chooseMessageFile",
        "level": "error",
    },
    {
        "api": "wx.getUserProfile",
        "name": "用户信息",
        "desc": "头像昵称（需在后台「设置-服务内容声明」配置用户信息用途）",
        "key": "console",
        "private": "",
        "level": "warn",
    },
    {
        "api": "wx.request",
        "name": "网络请求",
        "desc": "需在后台「开发-开发管理-服务器域名」配置 request 合法域名",
        "key": "console",
        "private": "",
        "level": "warn",
    },
]


# 页面路径最后一段 → 中文功能名（用于提审材料页面清单，未命中时用路径兜底）
_PAGE_NAME_HINT = {
    "index": "首页",
    "mine": "个人中心",
    "cart": "购物车",
    "order": "订单列表",
    "detail": "详情页",
    "list": "列表页",
    "form": "表单填写",
    "publish": "发布页",
    "stats": "数据统计",
    "checkin": "打卡记录",
    "result": "结果统计",
    "ticket": "我的票券",
}


def _scan_used_apis(files: dict) -> list[dict]:
    """扫描项目代码中使用到的隐私相关 wx.* API（按规则表顺序去重）。"""
    used = []
    for path, content in (files or {}).items():
        if not path.endswith((".js", ".wxml")):
            continue
        for rule in _PRIVACY_API_RULES:
            if rule["api"] in str(content) and rule not in used:
                used.append(rule)
    return used


def _page_desc(files: dict, page: str) -> str:
    """从页面 json 的 navigationBarTitleText 或路径推断页面功能说明。"""
    try:
        cfg = json.loads(files.get(f"{page}.json") or "{}")
        title = (cfg.get("navigationBarTitleText") or "").strip()
        if title:
            return title
    except Exception:
        pass
    last = page.rsplit("/", 1)[-1]
    return _PAGE_NAME_HINT.get(last, last)



def _validate_app_config(files: dict) -> tuple:
    """验证小程序配置。"""
    app_json = files.get("app.json")
    if not app_json:
        return {}, [{"item": "app.json", "ok": False}]
    try:
        config = json.loads(app_json)
        return config, [{"item": "app.json", "ok": True}]
    except Exception as e:
        return {}, [{"item": "app.json", "ok": False, "error": str(e)}]

def _check_page_files(app_config: dict, files: dict) -> list:
    """检查页面文件。"""
    checks = []
    registered_pages = set(app_config.get("pages") or [])
    actual_pages = {p.replace(".json", "") for p in files if p.startswith("pages/") and p.endswith(".json")}
    missing = actual_pages - registered_pages
    if missing:
        checks.append({"item": "页面注册", "ok": False, "detail": f"未注册: {list(missing)[:5]}"})
    else:
        checks.append({"item": "页面注册", "ok": True})
    return checks

def _generate_review_report(checks: list) -> dict:
    """生成审核报告。"""
    passed = sum(1 for c in checks if c.get("ok"))
    total = len(checks)
    return {
        "passed": passed,
        "total": total,
        "pass_rate": f"{passed/total*100:.1f}%" if total > 0 else "0%",
        "checks": checks
    }


def _prepare_review_context(review_data):
    """准备评测材料构建上下文。"""
    return {
        "data": review_data,
        "materials": [],
        "status": "prepared"
    }

def _build_review_material(material_type, material_content):
    """构建单个评测材料。"""
    return {
        "type": material_type,
        "content": material_content,
        "status": "built"
    }

def _finalize_review_results(materials):
    """汇总评测材料构建结果。"""
    return {
        "total_materials": len(materials),
        "materials": materials,
        "status": "completed"
    }


def _build_review_simple(review_data: dict) -> dict:
    """简化版评测材料构建。"""
    return {
        "title": review_data.get("title", ""),
        "content": review_data.get("content", ""),
        "status": "completed"
    }


def _review_check_appjson(files: dict, checks: list) -> dict:
    """检查 app.json 可解析 + 页面注册 + 四件套齐全。返回 app_cfg。"""
    app_cfg: dict = {}
    raw_app = files.get("app.json")
    if raw_app is None or not str(raw_app).strip():
        checks.append({"item": "app.json 可解析", "ok": False, "level": "error", "detail": "app.json 缺失（小程序运行必需）"})
    else:
        try:
            app_cfg = json.loads(raw_app)
            checks.append({"item": "app.json 可解析", "ok": True, "level": "ok", "detail": "格式正确"})
        except Exception as e:
            checks.append({"item": "app.json 可解析", "ok": False, "level": "error", "detail": str(e)})
    registered = set(app_cfg.get("pages") or [])
    generated = {p.rsplit(".", 1)[0] for p in files if p.startswith("pages/")}
    unregistered = sorted(generated - registered)
    checks.append({
        "item": "app.json 注册全部页面",
        "ok": not unregistered,
        "level": "error" if unregistered else "ok",
        "detail": "OK" if not unregistered else f"未注册: {unregistered}",
    })
    missing_quartet = sorted(
        {f"{rp}.{ext}" for rp in registered for ext in ("js", "wxml", "wxss", "json") if f"{rp}.{ext}" not in files}
    )
    checks.append({
        "item": "注册页面四件套齐全",
        "ok": not missing_quartet,
        "level": "error" if missing_quartet else "ok",
        "detail": "OK" if not missing_quartet else f"缺失: {missing_quartet}",
    })
    return app_cfg


def _review_check_meta(app_cfg: dict, files: dict, checks: list) -> None:
    """导航栏标题 + tabBar 图标 + sitemap。"""
    title = ((app_cfg.get("window") or {}).get("navigationBarTitleText") or "").strip()
    checks.append({
        "item": "导航栏标题已设置",
        "ok": bool(title),
        "level": "warn" if not title else "ok",
        "detail": f"「{title}」" if title else "window.navigationBarTitleText 缺失，审核截图展示异常",
    })
    tabbar = app_cfg.get("tabBar")
    if isinstance(tabbar, dict) and tabbar.get("list"):
        missing_icons = sorted({
            p.lstrip("/")
            for it in tabbar["list"]
            for p in (it.get("iconPath"), it.get("selectedIconPath"))
            if p and p.lstrip("/") not in files
        })
        checks.append({
            "item": "tabBar 图标资源齐全",
            "ok": not missing_icons,
            "level": "warn" if missing_icons else "ok",
            "detail": "OK" if not missing_icons else f"图标缺失: {missing_icons}",
        })
    else:
        checks.append({"item": "tabBar 配置", "ok": True, "level": "ok", "detail": "未使用 tabBar（无需图标资源）"})
    has_sitemap = "sitemap.json" in files
    checks.append({
        "item": "sitemap.json 存在",
        "ok": has_sitemap,
        "level": "warn" if not has_sitemap else "ok",
        "detail": "存在（页面收录规则）" if has_sitemap else "缺失：建议保留 sitemap.json 以控制搜索收录范围",
    })


def _review_check_permissions(app_cfg: dict, files: dict, checks: list) -> list:
    """权限声明扫描：代码用到的隐私 API 必须已在 app.json 声明。返回 used_apis。"""
    used_apis = _scan_used_apis(files)
    permission = app_cfg.get("permission") or {}
    private_declared = set(app_cfg.get("requiredPrivateInfos") or [])
    for rule in used_apis:
        if rule["key"] == "permission":
            declared = bool((permission.get("scope.userLocation") or {}).get("desc")) and rule["private"] in private_declared
            need = f"permission.scope.userLocation（desc） + requiredPrivateInfos: [\"{rule['private']}\"]"
        elif rule["key"] == "private":
            declared = rule["private"] in private_declared
            need = f"requiredPrivateInfos: [\"{rule['private']}\"]"
        else:
            declared = True
            need = rule["desc"]
        checks.append({
            "item": f"权限声明：{rule['name']}（{rule['api']}）",
            "ok": declared,
            "level": rule["level"] if not declared else "ok",
            "detail": "已声明" if declared else f"代码使用 wx.{rule['api'][3:]} 但未声明，需在 app.json 配置 {need}",
        })
    return used_apis


def _review_material_md(files: dict, name: str, template: str, app_cfg: dict, checks: list, used_apis: list) -> str:
    """生成提审材料 Markdown。"""
    tpl_name = next((t["name"] for t in TEMPLATES if t["id"] == template), template or "自定义")
    category = _CATEGORY_SUGGEST.get(template, "按业务功能选择对应服务类目")
    pages = sorted(set(app_cfg.get("pages") or []))
    failed = [c for c in checks if c["level"] == "error"]
    warns = [c for c in checks if c["level"] == "warn"]
    ok = not failed
    lines = [
        f"# 《{name}》微信小程序提审材料",
        "",
        "> 由小团智能平台自动生成（app.json 字段核对 + 代码权限扫描），请核对后补充资料提交审核。",
        "",
        "## 一、项目信息",
        f"- 名称：{name}",
        f"- 模板类型：{tpl_name}",
        f"- 规模：{len(pages)} 个页面 / {len(files)} 个文件",
        f"- 建议服务类目：{category}",
        "",
        "## 二、页面清单与功能说明",
        "",
        "| 页面路径 | 功能说明 |",
        "| --- | --- |",
    ]
    lines += [f"| {p} | {_page_desc(files, p)} |" for p in pages]
    lines += ["", "## 三、权限使用清单", ""]
    if used_apis:
        lines += [f"- {r['name']}（{r['api']}）：{r['desc']}" for r in used_apis]
    else:
        lines += ["- 未扫描到隐私接口调用（本项目默认不采集用户信息）"]
    lines += ["", "## 四、提审前核对清单", ""]
    lines += [f"- [{'x' if c['ok'] else ' '}] {c['item']}：{c['detail']}" for c in checks]
    lines += [
        "",
        "## 五、补充资料",
        "- 隐私协议：涉及用户信息需在 mp.weixin.qq.com → 设置 → 服务内容声明 完善用途说明",
        "- 截图：提交 1-5 张页面功能演示截图（审核必填）",
        "- 测试账号：如涉及登录/付费功能，需提供可用的测试账号",
        "- 名称与头像：名称不得含违禁词，头像需与功能相关",
        "",
        "## 六、自检结论",
        f"- {'✅ 全部核对通过，可提交审核' if ok else f'❌ {len(failed)} 项不通过，请先修复后再提交（附 {len(warns)} 项提醒）'}",
        "",
    ]
    return "\n".join(lines)

def build_review_material(files: dict, name: str, template: str = "") -> dict:
    """自动生成微信小程序提审材料：app.json 字段核对 + 代码权限扫描 + 提审清单 md。"""
    files = files or {}
    checks: list[dict] = []

    # 1. app.json 可解析 + 页面注册 + 四件套
    app_cfg = _review_check_appjson(files, checks)
    # 2. 导航栏标题 + tabBar 图标 + sitemap
    _review_check_meta(app_cfg, files, checks)
    # 3. 权限声明扫描
    used_apis = _review_check_permissions(app_cfg, files, checks)

    failed = [c for c in checks if c["level"] == "error"]
    warns = [c for c in checks if c["level"] == "warn"]
    ok = not failed

    # ── 提审材料 Markdown ──
    material = _review_material_md(files, name, template, app_cfg, checks, used_apis)
    return {"ok": ok, "checks": checks, "material": material}

@router.get("/projects")
async def list_projects(current_user: dict = require_auth()):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, template, requirement, created_at FROM miniapp_projects ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _miniapp_ensure_appjson(files: dict, req) -> dict:
    """兜底：确保 app.json 存在（小程序运行必需）。"""
    if "app.json" in files:
        return files
    pages = sorted({p.split("/", 1)[0] + "/index/index" for p in files if p.startswith("pages/")})
    app_json = {
        "pages": pages or ["pages/index/index"],
        "window": {
            "navigationBarTitleText": req.name,
            "navigationBarBackgroundColor": "#4F46E5",
            "navigationBarTextStyle": "white",
        },
    }
    return {"app.json": json.dumps(app_json, ensure_ascii=False, indent=2), **files}


async def _miniapp_quality_gate(user_prompt: str, req, _report) -> tuple:
    """生成链路质量门禁：最多 3 轮（解析失败→精简重试；QC 未过→附问题清单修复）。"""
    result = None
    files = None
    qc = None
    for attempt in range(3):
        _report(55, f"正在执行质量门禁检查（第 {attempt + 1} 轮）…")
        try:
            files = _extract_json(result)
            if not isinstance(files, dict) or not files:
                raise ValueError("AI 未生成任何文件")
            files = _miniapp_ensure_appjson(files, req)
            qc = _qc_check(files)
            if qc["ok"]:
                break
            last_err = "；".join(f"{c['item']}: {c['detail']}" for c in qc["checks"] if not c["ok"])
            logger.warning("miniapp QC failed (attempt %d): %s", attempt + 1, last_err)
            retry_prompt = user_prompt + (
                "\n\n重要：上次输出的代码未通过质量门禁（商用交付前必须全部通过）。"
                f"问题清单：{last_err}\n"
                "请针对性地修复以上问题，重新输出完整的项目 JSON（不要省略任何文件、不要截断，"
                "app.json 的 pages 必须与生成页面完全一致）。"
            )
            result = await call_llm_async(_GENERATE_SYSTEM, retry_prompt, max_tokens=12000, temperature=0.3)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning("miniapp JSON parse failed (attempt %d): %s", attempt + 1, e)
            try:
                retry_prompt = user_prompt + (
                    "\n\n重要：上次输出因过长被截断导致失败。本次请严格精简：\n"
                    "1. 页面数量控制在 2 个以内（首页 + 一个核心功能页），其余页面省略\n"
                    "2. 每个文件控制在 40 行以内，全部文件总字符数不超过 15000\n"
                    "3. app.json 只注册实际生成的页面"
                )
                result = await call_llm_async(_GENERATE_SYSTEM, retry_prompt, max_tokens=8000, temperature=0.3)
            except (HTTPException, ValueError, json.JSONDecodeError) as e2:
                raise HTTPException(
                    502, f"AI 输出格式异常（已自动重试精简版仍失败），请重试或更换模型。详情: {e2}"
                ) from e2
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, "操作失败，请稍后重试") from e
    if not files or qc is None or not qc["ok"]:
        raise HTTPException(502, "操作失败，请稍后重试")
    return files, qc, result


def _save_miniapp_project(proj_id: str, req, files: dict, qc: dict) -> None:
    """保存小程序项目到数据库。"""
    conn = get_db()
    _ensure_qc_column(conn)
    conn.execute(
        """INSERT INTO miniapp_projects (id, name, template, requirement, files, qc, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (proj_id, req.name, req.template, req.requirement,
         json.dumps(files, ensure_ascii=False), json.dumps(qc, ensure_ascii=False),
         datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

async def _miniapp_generate_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """AI 生成完整小程序项目（同步/异步任务共用执行体，异步时回报进度）。"""
    req = GenerateRequest(**payload)
    tpl = next((t for t in TEMPLATES if t["id"] == req.template), None)
    if req.template != "custom" and not tpl:
        raise HTTPException(400, "操作失败，请稍后重试")

    def _report(pct: float, stage: str) -> None:
        _notify_progress(progress, pct, stage)

    structure_desc = "\n".join(
        f"- {s}"
        for s in (
            tpl["structure"]
            if tpl
            else [
                "根据需求自行设计合理的页面结构（建议 3-5 个页面）",
            ]
        )
    )
    user_prompt = f"""项目名称：{req.name}
选择模板：{tpl["name"] if tpl else "自定义"}
模板页面结构：
{structure_desc}

用户需求：
{req.requirement}

请生成完整小程序项目 JSON。"""
    _report(10, "已受理，正在组织生成提示词…")

    start = time.time()
    try:
        _report(30, "AI 正在生成小程序代码…")
        result = await call_llm_async(_GENERATE_SYSTEM, user_prompt, max_tokens=12000, temperature=0.4)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, "操作失败，请稍后重试") from e

    files, qc, result = await _miniapp_quality_gate(user_prompt, req, _report)

    proj_id = f"mp_{uuid.uuid4().hex[:12]}"
    _save_miniapp_project(proj_id, req, files, qc)
    _report(85, "项目已保存")

    elapsed = round(time.time() - start, 2)
    log_usage("miniapp_generate", len(user_prompt), len(result), elapsed)
    return {
        "id": proj_id,
        "name": req.name,
        "template": req.template,
        "file_count": len(files),
        "files": files,
        "qc": qc,
    }


@router.post("/generate")
async def generate_project(
    req: GenerateRequest,
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """选模板 + 需求 → AI 生成完整小程序项目（默认异步任务，立即返回 task_id）。"""
    tpl = next((t for t in TEMPLATES if t["id"] == req.template), None)
    if req.template != "custom" and not tpl:
        raise HTTPException(400, "操作失败，请稍后重试")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    if sync:
        return await _miniapp_generate_worker(req.model_dump())
    task = create_task("miniapp_generate", req.model_dump(), username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "小程序生成任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


@router.get("/deploy-guide")
async def deploy_guide(current_user: dict = require_auth()):
    """小程序部署指引（Markdown 步骤）。注意：必须注册在 /{proj_id} 之前，避免路径冲突。"""
    return {
        "steps": [
            "下载生成的 ZIP 项目包并解压",
            "安装微信开发者工具（微信公众平台官网 → 下载 → 稳定版）",
            "打开微信开发者工具 → 「导入项目」，选择解压后的目录",
            "AppID 选择「测试号」（无需注册，功能完整）或填入你自己的小程序 AppID",
            "点击「编译」即可在模拟器预览运行",
            "确认无误后：登录 mp.weixin.qq.com → 开发管理 → 版本管理 → 上传代码",
            "在微信公众平台提交审核，审核通过后点「发布」即可上线",
        ],
        "note": "个人主体小程序无需企业资质即可注册，建议用「测试号」先体验完整流程。",
    }


@router.get("/{proj_id}")
async def get_project(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    row = conn.execute("SELECT * FROM miniapp_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "项目不存在")
    d = dict(row)
    d["files"] = json.loads(d.get("files") or "{}")
    try:
        d["qc"] = json.loads(d.get("qc") or "{}")
    except Exception:
        d["qc"] = {}
    return d


@router.delete("/{proj_id}")
async def delete_project(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM miniapp_projects WHERE id=?", (proj_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ══════════════════════════════════════════════════════════════
# 小程序工坊 v2 增强：Mock 数据层 + 在线预览 + 更多模板
# ══════════════════════════════════════════════════════════════

# ── Mock 数据生成器（让生成的静态页面有动态数据感）───────────
MOCK_DATA_TEMPLATES = {
    "shop": {
        "products": [
            {"id": 1, "name": "精选商品A", "price": 99, "image": "/static/prod1.jpg", "sales": 1203},
            {"id": 2, "name": "热销商品B", "price": 199, "image": "/static/prod2.jpg", "sales": 856},
            {"id": 3, "name": "新品上市C", "price": 59, "image": "/static/prod3.jpg", "sales": 432},
            {"id": 4, "name": "限时特惠D", "price": 149, "image": "/static/prod4.jpg", "sales": 2100},
        ],
        "categories": [{"id": 1, "name": "全部"}, {"id": 2, "name": "新品"}, {"id": 3, "name": "热卖"}, {"id": 4, "name": "促销"}],
        "banners": [
            {"id": 1, "image": "/static/banner1.jpg", "link": "/pages/goods/detail?id=1"},
            {"id": 2, "image": "/static/banner2.jpg", "link": "/pages/goods/detail?id=2"},
        ],
    },
    "booking": {
        "services": [
            {"id": 1, "name": "基础服务", "price": 99, "duration": "30分钟", "description": "标准体验"},
            {"id": 2, "name": "VIP服务", "price": 199, "duration": "60分钟", "description": "尊享体验"},
            {"id": 3, "name": "定制服务", "price": 299, "duration": "90分钟", "description": "个性化方案"},
        ],
        "slots": ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00", "19:00", "20:00"],
    },
    "food": {
        "dishes": [
            {"id": 1, "name": "招牌炒饭", "price": 28, "image": "/static/dish1.jpg", "sales": 320, "rating": 4.8},
            {"id": 2, "name": "香辣虾仁", "price": 58, "image": "/static/dish2.jpg", "sales": 180, "rating": 4.9},
            {"id": 3, "name": "清蒸鲈鱼", "price": 88, "image": "/static/dish3.jpg", "sales": 95, "rating": 4.7},
        ],
        "categories": [{"id": 1, "name": "热销"}, {"id": 2, "name": "主食"}, {"id": 3, "name": "海鲜"}, {"id": 4, "name": "饮料"}],
    },
    "news": {
        "articles": [
            {"id": 1, "title": "今日要闻：行业最新动态", "summary": "简短摘要内容...", "author": "编辑", "date": "2024-01-15", "views": 1500},
            {"id": 2, "title": "深度报道：趋势分析", "summary": "更多内容...", "author": "记者", "date": "2024-01-14", "views": 890},
        ],
        "categories": ["热点", "科技", "生活", "财经"],
    },
}


@router.get("/mock-data/{template_id}")
async def get_mock_data(template_id: str, current_user: dict = require_auth()):
    """获取模板对应的 Mock 数据（用于预览时填充静态页面）。"""
    mock = MOCK_DATA_TEMPLATES.get(template_id, {})
    if not mock:
        # 通用 fallback
        mock = {
            "items": [{"id": i, "name": f"示例项{i}", "desc": f"第 {i} 条内容"} for i in range(1, 6)],
            "meta": {"total": 100, "page": 1, "pageSize": 20},
        }
    return {"template": template_id, "data": mock}


@router.get("/preview-html/{proj_id}")
async def preview_html(proj_id: str, current_user: dict = require_auth()):
    """生成 HTML 预览页面（将小程序代码转换为可在浏览器中预览的 HTML）。

    v20：把 wxss → css，wxml → html，js → 普通 JS，注入 mock 数据后渲染。
    """
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM miniapp_projects WHERE id=?", (proj_id,)).fetchone()
        if not row:
            raise HTTPException(404, "项目不存在")
        files = json.loads(row["files"] or "{}")
        tpl = row.get("template", "custom")
    finally:
        conn.close()

    if not files:
        raise HTTPException(400, "项目没有文件")

    # 构建 HTML 预览（首页 + 各页面 tab 切换）
    from common.auth import get_user_profile
    user = get_user_profile(current_user.get("user_id", ""))

    mock_data = MOCK_DATA_TEMPLATES.get(tpl, {})

    # 收集所有页面
    pages = {p.replace(".js", "").replace(".wxml", "").replace(".wxss", "").replace(".json", "")
             for p in files if p.startswith("pages/") and p.endswith((".wxml", ".js", ".wxss"))}
    page_list = sorted(set(p.split("/")[1] for p in pages if len(p.split("/")) >= 2))

    # 构建单页 HTML（含所有页面的简单渲染）
    html_content = _build_preview_html(files, page_list, mock_data, row["name"], tpl)

    # 保存预览文件
    import hashlib
    html_filename = f"preview_{hashlib.md5(proj_id.encode()).hexdigest()[:8]}.html"
    preview_dir = VIDEO_DIR.parent / "previews" if hasattr(VIDEO_DIR, 'parent') else Path(__file__).parent / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    preview_path = preview_dir / html_filename
    preview_path.write_text(html_content, encoding="utf-8")

    return {
        "url": f"/api/miniapp/preview/{html_filename}",
        "filename": html_filename,
        "pages": page_list,
        "mock_injected": bool(mock_data),
    }


def _build_preview_html(files: dict, page_list: list, mock_data: dict, project_name: str, template: str) -> str:
    """将小程序文件转换为可浏览器预览的 HTML。"""
    # 提取首页 wxml
    home_wxml = ""
    for path, content in files.items():
        if path.endswith("index/index.wxml"):
            home_wxml = content
            break

    # 提取 JS 数据
    home_js_data = {}
    for path, content in files.items():
        if path.endswith("index/index.js"):
            # 简单提取 data 字段
            match = re.search(r'data\s*:\s*\{([^}]+)\}', content, re.DOTALL)
            if match:
                try:
                    js_str = "data:" + match.group(1) + "}"
                    # 简化处理：只提取字符串值
                    home_js_data = {"raw": match.group(1)[:500]}
                except Exception:
                    pass
            break

    # 构建预览 HTML
    pages_html_parts = []
    for page_name in page_list:
        wxml = ""
        js_data = ""
        for path, content in files.items():
            if f"pages/{page_name}/{page_name}.wxml" in path:
                wxml = content
            if f"pages/{page_name}/{page_name}.js" in path:
                js_data = content

        # 简单 wxml → html 转换
        html_body = wxml
        if wxml:
            # 替换 wx 组件为 html
            html_body = html_body.replace("<view", "<div").replace("</view", "</div")
            html_body = html_body.replace("<text", "<span").replace("</text", "</span")
            html_body = html_body.replace("<image", "<img").replace("<button", "<button")
            html_body = html_body.replace("<scroll-view", "<div class='scroll-view'")
            html_body = html_body.replace("<swiper", "<div class='swiper'")
            html_body = html_body.replace("<swiper-item", "<div class='swiper-item'")
            html_body = html_body.replace("<block", "<!-- block -->")
            html_body = re.sub(r'\{\{(.*?)\}\}', r'<span class="dynamic">\1</span>', html_body)
            html_body = re.sub(r'bindtap="(.*?)"', r'data-action="\1"', html_body)

        pages_html_parts.append(f"""
<div class="preview-page" id="page-{page_name}" style="display:{'block' if page_name==page_list[0] else 'none'}">
  <h3>📄 {page_name}</h3>
  <div class="page-content" style="border:1px solid #eee;padding:12px;margin:8px 0;border-radius:8px;">
    <pre style="font-size:11px;white-space:pre-wrap;word-break:break-all;color:#555;">{html_body[:2000]}</pre>
  </div>
</div>""")

    pages_html = "\n".join(pages_html_parts)

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{project_name} - 预览</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; background:#f5f5f5; }}
  .header {{ background:linear-gradient(135deg,#667eea,#764ba2); color:#fff; padding:16px 20px; }}
  .header h1 {{ font-size:18px; }}
  .header p {{ font-size:12px; opacity:0.8; margin-top:4px; }}
  .tabs {{ display:flex; background:#fff; border-bottom:1px solid #eee; overflow-x:auto; }}
  .tab {{ padding:12px 16px; font-size:13px; cursor:pointer; white-space:nowrap; border-bottom:2px solid transparent; }}
  .tab.active {{ color:#667eea; border-bottom-color:#667eea; }}
  .preview-container {{ padding:16px; max-width:800px; margin:0 auto; }}
  .preview-page {{ background:#fff; border-radius:12px; padding:16px; margin-bottom:16px; box-shadow:0 2px 8px rgba(0,0,0,0.06); }}
  .page-content {{ background:#fafafa; border-radius:8px; }}
  .mock-badge {{ display:inline-block; background:#e0e7ff; color:#4f46e5; padding:2px 8px; border-radius:4px; font-size:11px; margin-bottom:8px; }}
  .info-box {{ background:#f0f9ff; border:1px solid #bae6fd; border-radius:8px; padding:12px; margin-bottom:16px; font-size:13px; color:#0369a1; }}
  pre {{ line-height:1.6; }}
  .dynamic {{ color:#dc2626; font-weight:500; }}
</style>
</head>
<body>
<div class="header">
  <h1>📱 {project_name}</h1>
  <p>模板：{template} | Mock 数据：{('已注入' if mock_data else '无')} | 共 {len(page_list)} 个页面</p>
</div>
<div class="tabs">
  {''.join('<div class="tab active" onclick="showPage(' + p + ')">' + p + '</div>' for p in page_list)}
</div>
<div class="preview-container">
  <div class="info-box">
    💡 预览模式：此为代码结构预览，非真实运行环境。导入微信开发者工具可获得完整预览体验。
    {('<br>Mock 数据已注入：<code>' + json.dumps(mock_data, ensure_ascii=False)[:200] + '</code>') if mock_data else ''}
  </div>
  {pages_html}
</div>
<script>
function showPage(name) {{
  document.querySelectorAll('.preview-page').forEach(p => p.style.display='none');
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  const el = document.getElementById('page-'+name);
  if(el) el.style.display='block';
  event.target.classList.add('active');
}}
</script>
</body>
</html>"""
    return full_html


@router.get("/preview/{filename}")
async def serve_preview(filename: str):
    """提供预览 HTML 文件下载。"""
    preview_dir = Path(__file__).parent / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    filepath = preview_dir / filename
    if not filepath.exists():
        raise HTTPException(404, "预览文件不存在")
    return FileResponse(str(filepath), media_type="text/html")


@router.get("/templates/extended")
async def get_extended_templates(current_user: dict = require_auth()):
    """返回扩展模板列表（含 Mock 数据配置说明）。"""
    extended = [
        {
            "id": "membership",
            "name": "会员订阅",
            "description": "会员等级/积分/签到/兑换，适合付费内容平台",
            "icon": "👑",
            "color": "from-yellow-500 to-amber-600",
            "structure": [
                "pages/index/index（首页：会员权益总览）",
                "pages/membership/detail（会员等级详情）",
                "pages/checkin/checkin（签到打卡）",
                "pages/points/list（积分明细）",
                "pages/mine/mine（会员中心）",
            ],
            "has_mock": True,
        },
        {
            "id": "chat",
            "name": "即时通讯",
            "description": "单聊/群聊/消息列表，适合社交/客服场景",
            "icon": "💬",
            "color": "from-green-500 to-teal-600",
            "structure": [
                "pages/index/index（会话列表）",
                "pages/chat/detail（聊天窗口）",
                "pages/contact/list（联系人）",
            ],
            "has_mock": True,
        },
        {
            "id": "delivery",
            "name": "同城配送",
            "description": "订单跟踪/骑手定位/配送范围，适合本地生活服务",
            "icon": "🚀",
            "color": "from-orange-500 to-red-600",
            "structure": [
                "pages/index/index（首页：下单入口）",
                "pages/order/track（订单追踪地图）",
                "pages/order/list（我的订单）",
                "pages/address/list（收货地址）",
            ],
            "has_mock": True,
        },
        {
            "id": "course",
            "name": "在线教育",
            "description": "课程列表/视频播放/学习进度/测试答题",
            "icon": "📚",
            "color": "from-indigo-500 to-purple-600",
            "structure": [
                "pages/index/index（课程列表+分类）",
                "pages/course/detail（课程详情+目录）",
                "pages/lesson/play（视频播放+笔记）",
                "pages/quiz/list（章节测试）",
                "pages/my/course（我的课程）",
            ],
            "has_mock": True,
        },
    ]
    return {"templates": extended, "mock_available": True}


from fastapi.responses import FileResponse


@router.get("/{proj_id}/export-zip")
async def export_zip(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    row = conn.execute("SELECT * FROM miniapp_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "项目不存在")
    row = dict(row)  # sqlite3.Row 无 .get，转 dict 供物料模板使用
    files = json.loads(row["files"] or "{}")
    if not files:
        raise HTTPException(400, "项目没有文件")

    buf = io.BytesIO()
    root = pack_dir_name("miniapp_release")
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(files.keys()):
            zf.writestr(f"{root}/{path.lstrip('/')}", files[path])
        # 发布物料：介绍 + 审核清单 + 商用授权 + 质量自检报告（商业化发布 v14）
        zf.writestr(
            f"{root}/介绍.md",
            f"# {row['name']}\n\n- 模板：{row.get('template', '自定义')}\n"
            f"- 功能需求：{(row.get('requirement') or '')[:300]}\n\n"
            "## 使用方式\n解压后目录即微信小程序项目，用微信开发者工具导入即可编译运行。",
        )
        zf.writestr(
            f"{root}/审核清单.md",
            "# 微信小程序提审清单\n\n"
            "1. 登录 mp.weixin.qq.com → 注册小程序账号（个人主体即可）\n"
            "2. 微信开发者工具导入本包目录 → 编译 → 上传代码\n"
            "3. 填写：类目（按业务选择）、名称、简介、图标\n"
            "4. 截图：需提供 1-5 张页面截图（功能演示）\n"
            "5. 隐私协议：涉及用户信息需声明（本项目默认不采集）\n"
            "6. 提交审核（1-7 个工作日），通过后发布上线",
        )
        zf.writestr(f"{root}/LICENSE.txt", license_text(f"小程序《{row['name']}》"))
        try:
            qc = json.loads(row.get("qc") or "null") if "qc" in row.keys() else None
            failed = [c for c in (qc or {}).get("checks", []) if not c.get("ok")]
            name_check = check_text(row["name"], "文案")
            req_check = check_text(row.get("requirement") or "", "prompt")
            zf.writestr(
                f"{root}/质量自检报告.md",
                quality_report(
                    f"小程序《{row['name']}》",
                    text_check=name_check if not name_check["ok"] else (req_check if not req_check["ok"] else None),
                    image_quality=None,
                    extra=[
                        f"QC 门禁：{'全部通过 ✓' if (qc or {}).get('ok') else f'{len(failed)} 项未过'}",
                        "代码规模：" + f"{len(files)} 个文件",
                    ],
                ),
            )
        except Exception:
            pass
    data = buf.getvalue()
    # Content-Disposition：中文名走 RFC 5987 编码
    from urllib.parse import quote

    filename = f"{row['name']}.zip"
    try:
        filename.encode("latin-1")
        ascii_name = filename
    except UnicodeEncodeError:
        ascii_name = "miniapp.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": (f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}")},
    )


@router.get("/{proj_id}/review-material")
async def review_material(proj_id: str, current_user: dict = require_auth()):
    """自动生成提审材料：app.json 字段核对 + 代码权限扫描 + 提审清单 md。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM miniapp_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "项目不存在")
    row = dict(row)
    files = json.loads(row["files"] or "{}")
    if not files:
        raise HTTPException(400, "项目没有文件")
    result = build_review_material(files, row["name"], row.get("template") or "")
    result["name"] = row["name"]
    return result




async def _miniapp_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装生成 worker，回报进度。"""
    return await _miniapp_generate_worker(payload, progress=update)


register_handler("miniapp_generate", _miniapp_generate_handler, user_limit=2)
