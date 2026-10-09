"""商业闭环 API（分享/案例墙/SEO/会员订单/收款码/邀请分销/审计/内容权限）— 从 main.py 拆出。"""

import hashlib
import json
import os
import uuid
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from common.auth import (
    create_order,
    create_share,
    decode_access_token,
    get_invite_info,
    get_my_orders,
    get_share,
    require_auth,
    submit_voucher,
)
from common.db import get_db
from common.models import OrderCreateRequest, ShareCreateRequest

router = APIRouter()

# 与 main.py 保持一致的目录常量（commercial 模块独立解析，避免循环导入）
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")

# ── 结果分享（商业版：引流传播） ─────────────────────────────
# 首页案例墙预置示例成果：平台暂无真实分享时展示（is_demo 标记，前端点击直达工具页）
_DEMO_SHOWCASE = [
    {
        "share_code": "",
        "is_demo": True,
        "route": "/ppt-factory",
        "content_type": "PPT 演示",
        "title": "2026年智能家居行业趋势分析",
        "preview": "AI 原生、无感互联、绿色能源三大趋势拆解，含市场数据、竞争格局与战略建议，12 页结构化演示文稿。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/image-factory",
        "content_type": "AI 图片",
        "title": "高端香水商业摄影",
        "preview": "金色时刻布光 + 纯白背景，专业级产品摄影提示词生成效果。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/data-analyzer",
        "content_type": "数据分析",
        "title": "电商销售数据分析报告",
        "preview": "区域 × 品类交叉分析、趋势对比与 Top 排名，自动生成图表与可执行建议。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/voice-dubbing",
        "content_type": "AI 配音",
        "title": "短视频口播配音（晓晓 · 1.0x）",
        "preview": "多音色场景化配音，支持语速/音调微调，一键导出 mp3。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/video-factory",
        "content_type": "AI 视频",
        "title": "文生视频：城市夜景延时",
        "preview": "提示词直接生成 5s 视频片段，支持分辨率/帧率/时长自定义。",
        "views": 0,
        "created_at": "",
    },
    {
        "share_code": "",
        "is_demo": True,
        "route": "/code-sandbox",
        "content_type": "代码运行",
        "title": "Python 销售数据分析沙箱",
        "preview": "在线编写并运行 pandas 分析代码，即时输出结果与可视化图表。",
        "views": 0,
        "created_at": "",
    },
]


@router.get("/api/showcase")
async def showcase(limit: int = 12):
    """公开成果精选：用户主动分享的内容中挑高浏览案例（首页案例墙，无需登录）。

    分享内容本身即公开（分享页无鉴权），此处仅聚合展示，点击跳转分享页形成传播闭环。
    当平台暂无真实分享时，返回系统精选示例成果（is_demo: true，点击直达对应工具页），
    让新用户/访客首页不空、可感知平台能力；一旦出现真实分享，示例自动让位。
    """
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT share_code, title, content_type, views, created_at,
                      substr(content, 1, 200) AS preview
               FROM shares
               WHERE content != '' AND length(content) >= 10 AND is_test = 0
               ORDER BY views DESC, created_at DESC
               LIMIT ?""",
            (min(limit, 30),),
        ).fetchall()
        items = []
        for r in rows:
            item = dict(r)
            item["preview"] = (item.get("preview") or "").replace("\n", " ").strip()[:120]
            items.append(item)
        # 无真实分享时：返回系统精选示例成果（标记 is_demo，前端跳工具页）
        if not items:
            items = _DEMO_SHOWCASE[: min(limit, len(_DEMO_SHOWCASE))]
        return {"items": items}
    finally:
        conn.close()


# 工厂作品源 → 可读名称（与 gallery.SOURCE_LABEL 保持一致）
_FACTORY_SOURCE_LABEL = {
    "image_factory": "图片工厂",
    "video_factory": "视频工厂",
    "music_factory": "音乐工厂",
    "meme_factory": "表情包工坊",
    "game_factory": "小游戏工坊",
}

# 工厂类型 → 首页展示跳转路由（与前端菜单一致）
_FACTORY_ROUTE = {
    "image_factory": "/image-factory",
    "video_factory": "/video-factory",
    "music_factory": "/music-factory",
    "meme_factory": "/meme",
    "game_factory": "/games",
}


def _media_file_exists(media_url: str) -> bool:
    """按 media_url 前缀定位后端目录，校验媒体文件是否真实存在（过滤历史孤儿记录）。"""
    if not media_url:
        return False
    base = os.path.join(os.path.dirname(__file__))
    for prefix, sub in (
        ("/api/video-factory/videos/", "video_factory"),
        ("/api/image-factory/images/", "image_factory"),
        ("/api/meme-factory/images/", "meme_factory"),
    ):
        if media_url.startswith(prefix):
            return os.path.exists(os.path.join(base, sub, media_url[len(prefix) :]))
    return True


@router.get("/api/factory/latest")
async def factory_latest(limit: int = 12):
    """最新创作墙：聚合各工厂最新生成的图片/视频作品（含封面/缩略图），供首页真实作品展示。

    - 数据源：artifacts 表 type ∈ (image, video) 且 active=1 的最新记录
    - 图片作品自带 media_url 可直显；视频作品优先 thumbnail，缺时按 video_factory 规则推断封面 URL
    - 首页点击直达对应工厂页，展示平台最强生成能力的真实产出
    """
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT id, type, author, media_url, thumbnail, duration, created_at, content
               FROM artifacts
               WHERE type IN ('image','video') AND active=1 AND media_url != ''
               ORDER BY created_at DESC LIMIT ?""",
            (min(limit, 30),),
        ).fetchall()
        items = []
        for r in rows:
            media_url = r["media_url"] or ""
            # 过滤媒体文件已删除的孤儿记录（避免破损封面/黑屏视频出现在首页）
            if not _media_file_exists(media_url):
                continue
            thumbnail = r["thumbnail"] or ""
            if not thumbnail and r["type"] == "video" and "/video-factory/videos/" in media_url:
                stem = media_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if stem:
                    thumbnail = f"/api/video-factory/covers/{stem}.jpg"
            # 提取描述（content 为 dict 时取 prompt）
            prompt = ""
            try:
                obj = json.loads(r["content"] or "{}")
                if isinstance(obj, dict):
                    prompt = (obj.get("prompt") or "")[:80]
            except Exception:
                prompt = (r["content"] or "")[:80]
            items.append(
                {
                    "id": r["id"],
                    "type": r["type"],
                    "author": _FACTORY_SOURCE_LABEL.get(r["author"], r["author"] or "平台用户"),
                    "media_url": media_url,
                    "thumbnail": thumbnail,
                    "duration": float(r["duration"] or 0),
                    "prompt": prompt,
                    "created_at": r["created_at"] or "",
                    "route": _FACTORY_ROUTE.get(r["author"], "/gallery"),
                }
            )
        return {"items": items}
    finally:
        conn.close()


@router.post("/api/shares")
async def create_share_api(req: ShareCreateRequest, current_user: dict = require_auth()):
    """创建分享，返回 share_code。"""
    return create_share(current_user.get("user_id"), req.content_type, req.title, req.content)


@router.get("/api/shares/my")
async def my_shares(current_user: dict = require_auth()):
    """我的分享工作台：访问 / 注册转化 / 裂变奖励进度。"""
    from common.auth import get_my_share_stats

    return get_my_share_stats(current_user.get("user_id"))


@router.get("/api/shares/{share_code}")
async def get_share_api(share_code: str, request: Request, src: str = ""):
    """公开访问分享内容（无需登录，浏览量 +1，记录访问埋点 + 裂变奖励）。"""
    share = get_share(share_code)
    if not share:
        raise HTTPException(404, "分享不存在或已失效")
    # 埋点：来源渠道优先取 query src / utm_source，其次 Referer 域名，默认 direct
    source = (src or request.query_params.get("utm_source", "")).strip()[:32]
    referer = request.headers.get("referer", "")[:200]
    if not source:
        if referer:
            try:
                host = urlparse(referer).hostname or ""
                source = host if host not in ("localhost", "127.0.0.1") else "direct"
            except ValueError:
                source = "direct"
        else:
            source = "direct"
    # 去重键：同访问者只计一次有效访问；分享者本人访问不计奖励
    visitor_key = _share_visitor_key(request)
    _record_share_visit(share["id"], source, referer, visitor_key)
    # 裂变奖励：有效访问达阈值 → 分享者得一次性额度（幂等，见 grant_share_visit_reward）
    from common.auth import grant_share_visit_reward

    grant_share_visit_reward(share, visitor_key)
    return share


@router.get("/share/{share_code}", response_class=HTMLResponse)
async def share_seo_page(share_code: str):
    """分享页 SEO 渲染：为爬虫/社交平台返回带 og meta 的 HTML。

    nginx 将 /share/* 代理到本端点；普通浏览器会立即跳转到前端 SPA
    （?share=code 由 App.jsx 解析），抓取器则读到完整 meta 信息。
    """
    share = get_share(share_code)
    if not share:
        return HTMLResponse(
            """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">"""
            """<title>分享内容不存在 - 小团智能平台</title>"""
            """<meta http-equiv="refresh" content="0; url=/"></head><body></body></html>""",
            status_code=404,
        )
    title = (share.get("title") or "分享内容")[:80]
    desc = ((share.get("content") or "").replace("#", " ").replace("\n", " ").strip())[:200]
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - 小团智能平台</title>
<meta name="description" content="{desc}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="小团智能平台">
<meta property="og:url" content="/share/{share_code}">
<meta property="og:locale" content="zh_CN">
<meta http-equiv="refresh" content="0; url=/?share={share_code}">
<script>location.replace("/?share={share_code}")</script>
</head>
<body>
<article style="max-width:720px;margin:40px auto;font-family:system-ui;padding:0 20px">
<h1>{title}</h1>
<p>{desc}</p>
<p><a href="/?share={share_code}">查看完整内容</a></p>
</article>
</body>
</html>"""
    return HTMLResponse(html)


# ── SEO 基础设施（获客：robots / sitemap） ─────────────────────
# 按请求 Host 动态生成绝对 URL，适配任意部署域名；nginx / serve_frontend 将
# /robots.txt、/sitemap.xml 代理到本端点，避免 SPA fallback 吞掉。

# 主要公开页面（工具/能力入口，登录后运营页不收录）
_SEO_PAGES = [
    ("/", "小团智能平台 - AI 赋能各行各业", "0.9"),
    ("/tool-hub", "工具箱 - 30+ AI 效率工具", "0.9"),
    ("/ppt-factory", "AI PPT 演示文稿生成器", "0.8"),
    ("/image-factory", "AI 图片创作工厂", "0.8"),
    ("/video-factory", "AI 视频生成工厂", "0.8"),
    ("/music-factory", "AI 音乐生成工厂", "0.8"),
    ("/copywriting", "AI 文案创作", "0.8"),
    ("/translation", "AI 翻译", "0.8"),
    ("/voice-dubbing", "AI 配音（多音色）", "0.8"),
    ("/meme-factory", "AI 表情包工坊", "0.7"),
    ("/digital-human", "AI 数字人视频", "0.8"),
    ("/mindmap", "AI 思维导图", "0.7"),
    ("/forecast", "AI 数据预测", "0.7"),
    ("/doc-qa", "AI 文档问答", "0.7"),
    ("/pdf-tools", "PDF 工具箱", "0.7"),
    ("/web-search", "AI 联网搜索", "0.7"),
    ("/batch-process", "AI 批量处理", "0.7"),
    ("/code-interpreter", "AI 代码解释器", "0.7"),
    ("/data-analyzer", "AI 数据分析", "0.8"),
    ("/excel", "Excel 智能处理", "0.7"),
    ("/stock", "AI 股票分析", "0.7"),
    ("/miniapp", "小程序工坊", "0.7"),
    ("/publish", "内容发布中心", "0.7"),
    ("/templates", "行业模板库", "0.7"),
    ("/gallery", "灵感画廊", "0.7"),
    ("/api-platform", "开放 API 平台", "0.6"),
    ("/help", "帮助中心", "0.5"),
]


async def _site_base(request: Request) -> str:
    """按请求 Host 构造站点绝对地址（跟随 X-Forwarded-Proto，适配反代）。"""
    scheme = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host", "localhost:8888")
    return f"{scheme}://{host}"


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
async def robots_txt(request: Request):
    """爬虫规则：公开页可抓，运营/账号页禁抓；声明 sitemap 绝对地址。"""
    base = await _site_base(request)
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /login\n"
        "Disallow: /profile\n"
        "Disallow: /membership\n"
        "Disallow: /tasks\n"
        "Disallow: /records\n"
        "Disallow: /usage-analytics\n"
        "Disallow: /scheduler\n"
        "Disallow: /notifications\n"
        "Disallow: /favorites\n"
        f"\nSitemap: {base}/sitemap.xml\n"
    )
    return PlainTextResponse(body)


@router.get("/sitemap.xml", response_class=Response, include_in_schema=False)
async def sitemap_xml(request: Request):
    """站点地图：核心工具页 + 公开分享内容（浏览量/时效排序，最多 100 条）。"""
    from xml.sax.saxutils import escape

    base = await _site_base(request)
    urls = []
    for path, _title, priority in _SEO_PAGES:
        urls.append(
            f"<url><loc>{escape(base + path)}</loc><changefreq>weekly</changefreq><priority>{priority}</priority></url>"
        )
    try:
        from common.db import get_db

        conn = get_db()
        rows = conn.execute(
            """SELECT share_code, created_at FROM shares
               WHERE content != '' AND length(content) >= 10 AND is_test = 0
               ORDER BY views DESC, created_at DESC LIMIT 100"""
        ).fetchall()
        conn.close()
        for r in rows:
            lastmod = (r["created_at"] or "")[:10]
            urls.append(
                f"<url><loc>{escape(base + '/share/' + r['share_code'])}</loc>"
                + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
                + "<changefreq>monthly</changefreq><priority>0.6</priority></url>"
            )
    except Exception:
        pass  # 分享表不可用时仅返回静态页
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


# ── 会员套餐 / 订单（商业版：支付闭环） ─────────────────────
@router.get("/api/membership/plans")
async def membership_plans():
    """会员套餐列表（公开，前端渲染套餐卡片）。"""
    from common.auth import MEMBERSHIP_PLANS, MEMBERSHIP_QUOTA

    plans = {
        "free": {
            "name": "免费版",
            "price": 0,
            "daily_quota": MEMBERSHIP_QUOTA["free"],
            "features": ["每日 30 次生成额度", "全部工具基础使用", "标准响应速度"],
        }
    }
    for key, info in MEMBERSHIP_PLANS.items():
        plans[key] = {**info, "daily_quota": info["daily_quota"]}
    return plans


@router.post("/api/orders")
async def create_order_api(req: OrderCreateRequest, current_user: dict = require_auth()):
    """创建会员订单（同一时间仅 1 个待处理订单，可选优惠码抵扣）。"""
    return create_order(current_user.get("user_id"), req.plan, req.coupon_code, req.stripe_session_id)


@router.get("/api/orders")
async def my_orders(current_user: dict = require_auth()):
    """我的订单列表（倒序）。"""
    return get_my_orders(current_user.get("user_id"))


@router.post("/api/orders/{order_id}/voucher")
async def submit_voucher_api(
    order_id: str,
    file: UploadFile | None = File(None),
    remark: str = Form(""),
    current_user: dict = require_auth(),
):
    """提交支付凭证（截图 + 备注），订单进入待审核。"""
    voucher = ""
    if file and file.filename:
        ext = os.path.splitext(file.filename or "")[1][:10] or ".png"
        name = f"v_{uuid.uuid4().hex[:12]}{ext}"
        path = os.path.join(UPLOAD_DIR, "vouchers", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(400, "凭证图片不能超过 5MB")
        with open(path, "wb") as f:
            f.write(content)
        voucher = f"/uploads/vouchers/{name}"
    if not voucher and not remark.strip():
        raise HTTPException(400, "请上传支付凭证截图或填写转账说明")
    return submit_voucher(order_id, current_user.get("user_id"), voucher, remark)


# ── 收款码配置（商业版：扫码支付） ──────────────────────────
PAYMENT_QR_KEY = os.environ.get("PAYMENT_QR_KEY", "payment_qr")  # 配置键名，非敏感


def _get_payment_qr() -> str:
    """当前收款码路径（config 表，空串表示未配置）。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT value FROM config WHERE key=?", (PAYMENT_QR_KEY,)).fetchone()
    finally:
        conn.close()
    return row["value"] if row else ""


@router.get("/api/membership/payment-qr")
async def membership_payment_qr(current_user: dict = require_auth()):
    """当前收款码（登录用户可见，会员中心扫码支付展示）。"""
    return {"url": _get_payment_qr()}


@router.get("/api/admin/payment-qr")
async def admin_payment_qr(current_user: dict = require_auth()):
    """管理员查看收款码配置。"""
    from admin_api import _check_admin

    _check_admin(current_user)
    return {"url": _get_payment_qr()}


@router.post("/api/admin/payment-qr")
async def admin_upload_payment_qr(
    file: UploadFile = File(...),
    current_user: dict = require_auth(),
):
    """上传收款码图片（png/jpg/jpeg/webp，最多 5MB）。"""
    from admin_api import _check_admin

    _check_admin(current_user)
    if not file.filename:
        raise HTTPException(400, "请选择收款码图片")
    ext = os.path.splitext(file.filename)[1].lower()[:10]
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(400, "仅支持 png / jpg / jpeg / webp 图片")
    name = f"qr_{uuid.uuid4().hex[:12]}{ext}"
    path = os.path.join(UPLOAD_DIR, "qr", name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "收款码图片不能超过 5MB")
    with open(path, "wb") as f:
        f.write(content)
    url = f"/uploads/qr/{name}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO config (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
            (PAYMENT_QR_KEY, url),
        )
        conn.commit()
    finally:
        conn.close()
    return {"url": url, "message": "收款码已更新"}


@router.delete("/api/admin/payment-qr")
async def admin_remove_payment_qr(current_user: dict = require_auth()):
    """移除收款码配置。"""
    from admin_api import _check_admin

    _check_admin(current_user)
    conn = get_db()
    try:
        conn.execute("DELETE FROM config WHERE key=?", (PAYMENT_QR_KEY,))
        conn.commit()
    finally:
        conn.close()
    return {"message": "收款码已移除"}


# ── 邀请码分销（商业版：引流） ───────────────────────────────
@router.get("/api/invite")
async def invite_info(current_user: dict = require_auth()):
    """我的邀请码 / 已邀请用户 / 奖励规则。"""
    return get_invite_info(current_user.get("user_id"))


@router.get("/api/invite/leaderboard")
async def invite_leaderboard(limit: int = 10, current_user: dict = require_auth()):
    """邀请排行榜：邀请人数 Top N（仅展示有邀请记录的用户）+ 我的排名。"""
    limit = max(3, min(limit, 50))
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT u.id, u.username, u.nickname, COUNT(i.id) AS invites
               FROM users u LEFT JOIN users i ON i.invited_by = u.id
               GROUP BY u.id
               ORDER BY invites DESC, u.created_at ASC""",
        ).fetchall()
    finally:
        conn.close()
    board = []
    my_rank = None
    me_id = str(current_user.get("user_id"))
    for idx, r in enumerate(rows, 1):
        invites = int(r["invites"])
        if str(r["id"]) == me_id:
            my_rank = idx
        if invites > 0 and len(board) < limit:
            board.append(
                {
                    "rank": len(board) + 1,
                    "username": r["username"],
                    "nickname": r["nickname"] or r["username"],
                    "invites": invites,
                }
            )
    # 若我的排名在榜单外，附带返回（前端展示"我的排名"）
    my_invites = next((int(r["invites"]) for r in rows if str(r["id"]) == me_id), 0)
    return {"board": board, "my_rank": my_rank, "my_invites": my_invites}


@router.get("/api/invite/history")
async def invite_history(limit: int = 50, current_user: dict = require_auth()):
    """邀请历史列表。"""
    from common.auth import get_invite_history

    return get_invite_history(current_user.get("user_id"), limit)


@router.get("/api/invite/rewards")
async def invite_rewards(limit: int = 50, current_user: dict = require_auth()):
    """奖励流水列表。"""
    from common.auth import get_invite_rewards

    return get_invite_rewards(current_user.get("user_id"), limit)


# ── 审计日志（v17.2）───────────────────────────────────────────
@router.get("/api/audit/logs")
async def get_audit_log_entries(
    user_id: str = "",
    action: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 100,
    current_user: dict = require_auth(),
):
    """获取审计日志（仅管理员可访问）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "权限不足")
    from common.audit import get_audit_logs

    return get_audit_logs(user_id, action, start_date, end_date, limit)


@router.get("/api/audit/stats")
async def get_audit_stats(current_user: dict = require_auth()):
    """获取审计统计（仅管理员可访问）。"""
    if current_user.get("role") != "admin":
        raise HTTPException(403, "权限不足")
    from common.db import get_db

    conn = get_db()
    try:
        # 今日操作数
        today = datetime.now().strftime("%Y-%m-%d")
        today_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE created_at LIKE ?", (f"{today}%",)
        ).fetchone()[0]

        # 操作类型分布
        action_stats = conn.execute(
            "SELECT action, COUNT(*) as cnt FROM audit_logs GROUP BY action ORDER BY cnt DESC LIMIT 10"
        ).fetchall()

        # 失败操作数
        fail_count = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE success = 0").fetchone()[0]

        return {
            "today_count": today_count,
            "fail_count": fail_count,
            "action_stats": [dict(r) for r in action_stats],
        }
    finally:
        conn.close()


# ── 内容权限（v9.3：页面可见性 / 灰度发布） ─────────────────
@router.get("/api/access/pages")
async def access_pages(current_user: dict = require_auth()):
    """当前用户可见的页面列表（Sidebar / 路由守卫使用）。"""
    from permissions import PAGES, access_status, get_visibility_map, load_user_ctx

    vis_map = get_visibility_map("page")
    user_ctx = load_user_ctx(current_user)
    result = []
    for p in PAGES:
        status = access_status(user_ctx, vis_map.get(p["id"], "all"))
        if not status["visible"]:
            continue
        item = {**p}
        if status.get("locked"):
            item["locked"] = True
            item["requires"] = status["requires"]
        result.append(item)
    return result


# 分享访问埋点


def _share_visitor_key(request: Request) -> str:
    """访问者去重键：已登录用户 u:{uid}（分享者本人不计裂变奖励）；游客 ip:{ip}:{UA哈希}。"""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            payload = decode_access_token(auth_header[7:])
            uid = payload.get("user_id")
            if uid:
                return f"u:{uid}"
        except HTTPException:
            pass  # token 无效按游客处理
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")[:64]
    return f"ip:{ip}:{hashlib.md5(ua.encode()).hexdigest()[:10]}"


def _record_share_visit(share_id: str, source: str, referer: str, visitor_key: str = "") -> bool:
    """写入分享访问埋点（渠道分析 + 裂变计数）。同访问者重复访问同一分享不重复记录。"""
    from common.db import get_db

    conn = get_db()
    try:
        if visitor_key:
            dup = conn.execute(
                "SELECT id FROM share_visits WHERE share_id=? AND visitor_key=? LIMIT 1",
                (share_id, visitor_key),
            ).fetchone()
            if dup:
                return False
        conn.execute(
            "INSERT INTO share_visits (share_id, source, referer, visited_at, visitor_key) VALUES (?, ?, ?, ?, ?)",
            (share_id, source, referer, datetime.now().isoformat(), visitor_key),
        )
        conn.commit()
        return True
    finally:
        conn.close()
