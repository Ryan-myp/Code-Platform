#!/usr/bin/env python3
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
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.llm import call_llm_async, log_usage
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
12. 不要使用 tabBar 配置（避免图标资源缺失导致编译警告），导航用自定义按钮或页面内跳转"""


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
    return json.loads(text[start:end + 1])


@router.get("/templates")
async def list_templates(current_user: dict = require_auth()):
    return TEMPLATES


@router.get("/projects")
async def list_projects(current_user: dict = require_auth()):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, template, requirement, created_at FROM miniapp_projects ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def _miniapp_generate_worker(payload: dict, progress: Callable | None = None) -> dict:
    """AI 生成完整小程序项目（同步/异步任务共用执行体，异步时回报进度）。"""
    req = GenerateRequest(**payload)
    tpl = next((t for t in TEMPLATES if t["id"] == req.template), None)
    if req.template != "custom" and not tpl:
        raise HTTPException(400, f"未知模板: {req.template}")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    structure_desc = "\n".join(f"- {s}" for s in (tpl["structure"] if tpl else [
        "根据需求自行设计合理的页面结构（建议 3-5 个页面）",
    ]))
    user_prompt = f"""项目名称：{req.name}
选择模板：{tpl['name'] if tpl else '自定义'}
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
        raise HTTPException(500, f"生成失败: {e}") from e

    files = None
    try:
        files = _extract_json(result)
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("miniapp JSON parse failed (will retry compact): %s", e)
        # 输出被截断/超长：自动降级为精简版重试（只保留核心页面）
        try:
            retry_prompt = user_prompt + (
                "\n\n重要：上次输出因过长被截断导致失败。本次请严格精简：\n"
                "1. 页面数量控制在 2 个以内（首页 + 一个核心功能页），其余页面省略\n"
                "2. 每个文件控制在 40 行以内，全部文件总字符数不超过 15000\n"
                "3. app.json 只注册实际生成的页面"
            )
            result = await call_llm_async(_GENERATE_SYSTEM, retry_prompt, max_tokens=8000, temperature=0.3)
            files = _extract_json(result)
        except (ValueError, json.JSONDecodeError, HTTPException) as e2:
            raise HTTPException(502, f"AI 输出格式异常（已自动重试精简版仍失败），请重试或更换模型。详情: {e2}") from e2

    if not isinstance(files, dict) or not files:
        raise HTTPException(502, "AI 未生成任何文件，请重试")

    # 兜底：确保 app.json 存在（小程序运行必需）
    if "app.json" not in files:
        files = {"app.json": json.dumps({
            "pages": sorted({p.split("/", 1)[0] + "/index/index" for p in files if p.startswith("pages/")}) or ["pages/index/index"],
            "window": {"navigationBarTitleText": req.name, "navigationBarBackgroundColor": "#4F46E5",
                        "navigationBarTextStyle": "white"},
        }, ensure_ascii=False, indent=2), **files}

    proj_id = f"mp_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    conn.execute(
        """INSERT INTO miniapp_projects (id, name, template, requirement, files, created_at)
           VALUES (?,?,?,?,?,?)""",
        (proj_id, req.name, req.template, req.requirement,
         json.dumps(files, ensure_ascii=False), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    _report(85, "项目已保存")

    elapsed = round(time.time() - start, 2)
    log_usage("miniapp_generate", len(user_prompt), len(result), elapsed)
    return {
        "id": proj_id,
        "name": req.name,
        "template": req.template,
        "file_count": len(files),
        "files": files,
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
        raise HTTPException(400, f"未知模板: {req.template}")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    if sync:
        return await _miniapp_generate_worker(req.model_dump())
    task = create_task("miniapp_generate", req.model_dump(), username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"], "status": "pending",
        "message": "小程序生成任务已提交，后台执行中，可在任务中心查看进度", "task": task,
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
    return d


@router.delete("/{proj_id}")
async def delete_project(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM miniapp_projects WHERE id=?", (proj_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/{proj_id}/export-zip")
async def export_zip(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    row = conn.execute("SELECT * FROM miniapp_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "项目不存在")
    files = json.loads(row["files"] or "{}")
    if not files:
        raise HTTPException(400, "项目没有文件")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(files.keys()):
            zf.writestr(path.lstrip("/"), files[path])
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
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


def get_db():
    from common.db import get_db as _get_db

    return _get_db()


async def _miniapp_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装生成 worker，回报进度。"""
    return await _miniapp_generate_worker(payload, progress=update)


register_handler("miniapp_generate", _miniapp_generate_handler, user_limit=2)
