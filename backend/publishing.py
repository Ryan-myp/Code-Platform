#!/usr/bin/env python3
"""内容发布中心 — 公众号 / 抖音 / 快手 一键发布。

双模式：
- guide 引导式（默认，零配置）：把文章/图片/视频组装成发布素材包
  （标题 + 话题 + 正文 + 素材下载链接 + 分步指引），用户到官方 App/后台粘贴发布
- auto 自动发布（可选）：账号配置 AppID/Secret 后调用平台开放 API 直接发布
  （微信公众号：draft + freepublish；抖音/快手：素材上传 + 发布）

发布记录统一落库 publish_records，便于追溯。
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.config import load_config
from common.db import get_db
from common.llm import log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/publish", tags=["内容发布"])

load_config()

# 自动发布时下载站内素材的内部地址（asset_urls 为相对路径时拼接）
_INTERNAL_BASE = os.environ.get("PUBLISH_INTERNAL_BASE", "http://127.0.0.1:8888")

PLATFORM_LABELS = {"wechat": "微信公众号", "douyin": "抖音", "kuaishou": "快手"}
CONTENT_LABELS = {"article": "图文", "image": "图片", "video": "视频"}

# ── 引导式发布步骤（分平台分类型） ──────────────────────────
GUIDE_STEPS = {
    "wechat": {
        "article": [
            "打开微信公众平台（mp.weixin.qq.com），扫码登录公众号后台",
            "左侧菜单进入「内容与互动 → 草稿箱」，点击「新的创作 → 图文消息」",
            "粘贴右侧「正文内容」到编辑器，填写「标题」（可直接复制）",
            "下载并上传「封面图」（建议 900×383 比例）",
            "点击「保存为草稿」，检查排版无误后点击「发表」",
        ],
        "image": [
            "打开微信公众平台（mp.weixin.qq.com），扫码登录公众号后台",
            "进入「内容与互动 → 草稿箱」，点击「新的创作 → 图片消息」",
            "下载素材图片并上传，粘贴右侧「文案」",
            "点击「发表」即可推送",
        ],
        "video": [
            "打开微信公众平台（mp.weixin.qq.com），扫码登录公众号后台",
            "进入「内容与互动 → 草稿箱」，点击「新的创作 → 视频消息」",
            "下载视频文件并上传，填写标题与简介",
            "点击「发表」即可推送",
        ],
    },
    "douyin": {
        "article": [
            "打开抖音 App，点击底部「+」进入发布页",
            "选择「图文」模式，上传图片素材",
            "粘贴右侧「文案内容」到文字区，话题标签会自动识别",
            "点击「发布」即可（建议勾选同步到今日头条）",
        ],
        "image": [
            "打开抖音 App，点击底部「+」进入发布页",
            "选择「图文」模式，上传生成的图片",
            "粘贴右侧「文案内容」到文字区，话题标签会自动识别",
            "点击「发布」即可",
        ],
        "video": [
            "打开抖音 App，点击底部「+」进入发布页",
            "选择视频并上传（建议竖屏 9:16，时长 15-60s 完播率更高）",
            "粘贴右侧「文案内容」到文字区，话题标签会自动识别",
            "选择合适的封面，点击「发布」即可",
        ],
    },
    "kuaishou": {
        "article": [
            "打开快手 App，点击首页底部「+」进入拍摄页",
            "选择「多图」模式，上传图片素材",
            "粘贴右侧「文案内容」到文字区，话题标签会自动识别",
            "点击「发布」即可",
        ],
        "image": [
            "打开快手 App，点击首页底部「+」进入拍摄页",
            "选择「多图」模式，上传生成的图片",
            "粘贴右侧「文案内容」到文字区，话题标签会自动识别",
            "点击「发布」即可",
        ],
        "video": [
            "打开快手 App，点击首页底部「+」进入拍摄页",
            "选择视频并上传（建议竖屏，前 3 秒放亮点）",
            "粘贴右侧「文案内容」到文字区，话题标签会自动识别",
            "点击「发布」即可",
        ],
    },
}

# 自动发布的平台能力矩阵（False 表示该组合不支持自动发布，自动回落引导式）
AUTO_SUPPORT = {
    "wechat": {"article": True, "image": False, "video": False},
    "douyin": {"article": False, "image": True, "video": True},
    "kuaishou": {"article": False, "image": True, "video": True},
}


class AccountRequest(BaseModel):
    platform: str = Field(..., description="wechat/douyin/kuaishou")
    name: str = Field("", max_length=100)
    app_id: str = Field("", max_length=200)
    app_secret: str = Field("", max_length=200)


class PublishRequest(BaseModel):
    platform: str = Field(..., description="wechat/douyin/kuaishou")
    content_type: str = Field("article", description="article/image/video")
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=20000, description="正文/文案")
    topics: list[str] = Field(default_factory=list, description="话题标签")
    asset_urls: list[str] = Field(default_factory=list, description="素材文件相对/绝对 URL")
    account_id: str = Field("", description="指定账号（空则取该平台首个已配置账号）")


# ══════════════════════════════════════════════════════════════
# 账号配置
# ══════════════════════════════════════════════════════════════

def _mask_account(a: dict) -> dict:
    a = dict(a)
    if a.get("app_secret"):
        a["app_secret"] = "••••••" + (a["app_secret"][-4:] if len(a["app_secret"]) > 4 else "")
    if a.get("access_token"):
        a["access_token"] = "••••••"
    return a


@router.get("/accounts")
async def list_accounts(current_user: dict = require_auth()):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM publish_accounts WHERE active=1 ORDER BY platform, created_at"
    ).fetchall()
    conn.close()
    return [_mask_account(dict(r)) for r in rows]


@router.post("/accounts")
async def upsert_account(req: AccountRequest, current_user: dict = require_auth()):
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, f"未知平台: {req.platform}")
    now = datetime.now().isoformat()
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM publish_accounts WHERE platform=? AND active=1", (req.platform,)
    ).fetchone()
    if row:
        # 保留原 secret（前端脱敏回传时避免覆盖）
        secret = req.app_secret if req.app_secret and "•" not in req.app_secret else row["app_secret"]
        conn.execute(
            """UPDATE publish_accounts SET name=?, app_id=?, app_secret=?, configured=?,
               updated_at=? WHERE id=?""",
            (req.name or row["name"], req.app_id, secret, 1 if req.app_id and secret else 0, now, row["id"]),
        )
        conn.commit()
        conn.close()
        return {"id": row["id"], "configured": 1 if req.app_id and secret else 0}
    acc_id = f"pubacc_{uuid.uuid4().hex[:12]}"
    configured = 1 if req.app_id and req.app_secret else 0
    conn.execute(
        """INSERT INTO publish_accounts (id, platform, name, app_id, app_secret,
           configured, created_at, updated_at, active) VALUES (?,?,?,?,?,?,?,?,1)""",
        (acc_id, req.platform, req.name, req.app_id, req.app_secret, configured, now, now),
    )
    conn.commit()
    conn.close()
    return {"id": acc_id, "configured": configured}


@router.delete("/accounts/{acc_id}")
async def delete_account(acc_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("UPDATE publish_accounts SET active=0 WHERE id=?", (acc_id,))
    conn.commit()
    conn.close()
    return {"success": True}


async def _wechat_token(app_id: str, secret: str) -> str:
    """获取微信公众号 access_token（2 小时有效，接口有频控）。"""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": app_id, "secret": secret},
        )
        data = resp.json()
    if "access_token" not in data:
        raise HTTPException(502, f"微信 token 获取失败: {data.get('errmsg', data)}")
    return data["access_token"]


@router.post("/accounts/{acc_id}/test")
async def test_account(acc_id: str, current_user: dict = require_auth()):
    """测试账号连接：微信拉取 token；抖音/快手需应用审核后才有可用凭据。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM publish_accounts WHERE id=? AND active=1", (acc_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "账号不存在")
    acc = dict(row)
    if not acc["app_id"] or not acc["app_secret"]:
        raise HTTPException(400, "请先填写 AppID 与 AppSecret")
    try:
        if acc["platform"] == "wechat":
            token = await _wechat_token(acc["app_id"], acc["app_secret"])
            conn = get_db()
            conn.execute(
                "UPDATE publish_accounts SET access_token=?, token_expires_at=? WHERE id=?",
                (token, datetime.now().isoformat(), acc_id),
            )
            conn.commit()
            conn.close()
            return {"success": True, "message": "连接成功，微信 access_token 已获取"}
        raise HTTPException(400, (
            f"{PLATFORM_LABELS[acc['platform']]} 的 AppID/Secret 需先在开放平台完成应用创建与审核，"
            "凭据通过后即可自动发布。审核前请使用「引导式发布」（零配置）"
        ))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"连接测试失败: {e}") from e


# ══════════════════════════════════════════════════════════════
# 可发布素材聚合
# ══════════════════════════════════════════════════════════════

@router.get("/assets")
async def list_assets(current_user: dict = require_auth()):
    """聚合可发布素材：文章（文案历史）+ 图片/视频（成果仓库）。"""
    conn = get_db()
    articles = conn.execute(
        "SELECT id, type, title, prompt, result, created_at FROM copywriting_tasks ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    media = conn.execute(
        """SELECT id, type, content, media_url, thumbnail, created_at FROM artifacts
           WHERE active=1 AND type IN ('image','video') AND media_url != '' ORDER BY created_at DESC LIMIT 20"""
    ).fetchall()
    conn.close()
    return {
        "articles": [dict(r) for r in articles],
        "media": [
            {
                **dict(r),
                "url": r["media_url"],
                "prompt": (json.loads(r["content"]) if isinstance(r["content"], str) and r["content"].startswith("{") else {})
                          .get("prompt", "") if r["content"] else "",
            }
            for r in media
        ],
    }


# ══════════════════════════════════════════════════════════════
# 发布执行（引导式 / 自动发布）
# ══════════════════════════════════════════════════════════════

async def _fetch_asset_bytes(url: str) -> bytes:
    """下载素材（支持相对路径与绝对 URL）。"""
    full = url if url.startswith("http") else f"{_INTERNAL_BASE}{url}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(full)
        resp.raise_for_status()
        return resp.content


def _asset_filename(url: str) -> str:
    name = url.rsplit("/", 1)[-1].split("?", 1)[0]
    return name or "asset.bin"


# ── 微信公众号：草稿箱 + 群发 ────────────────────────────────
async def _publish_wechat(acc: dict, req: PublishRequest) -> str:
    token = acc.get("access_token") or await _wechat_token(acc["app_id"], acc["app_secret"])
    conn = get_db()
    conn.execute("UPDATE publish_accounts SET access_token=? WHERE id=?", (token, acc["id"]))
    conn.commit()
    conn.close()
    if not req.asset_urls:
        raise HTTPException(400, "图文发布需要至少一张封面图")
    # 1. 上传封面为永久图片素材
    cover_bytes = await _fetch_asset_bytes(req.asset_urls[0])
    files = {"media": (_asset_filename(req.asset_urls[0]), cover_bytes, "image/png")}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/material/add_material",
            params={"access_token": token, "type": "image"},
            files=files,
        )
        data = resp.json()
        if "media_id" not in data:
            raise HTTPException(502, f"微信封面上传失败: {data.get('errmsg', data)}")
        thumb_media_id = data["media_id"]
        # 2. 保存草稿
        articles = [{
            "title": req.title or "未命名",
            "author": acc.get("name") or "",
            "digest": (req.content or "")[:120],
            "content": (req.content or "").replace("\n", "<br>"),
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }]
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": token},
            json={"articles": articles},
        )
        data = resp.json()
        if "media_id" not in data:
            raise HTTPException(502, f"微信草稿保存失败: {data.get('errmsg', data)}")
        draft_media_id = data["media_id"]
        # 3. 发布（frepublish 不需要群发审核，走发布能力）
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/freepublish/submit",
            params={"access_token": token},
            json={"media_id": draft_media_id},
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise HTTPException(502, f"微信发布失败: {data.get('errmsg', data)}")
        return str(data.get("publish_id", ""))


# ── 抖音：素材上传 + 发布 ────────────────────────────────────
async def _publish_douyin(acc: dict, req: PublishRequest) -> str:
    if not req.asset_urls:
        raise HTTPException(400, "请选择要发布的图片/视频素材")
    # 1. client_credential 获取 access_token（需开放平台已审核通过）
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://open.douyin.com/oauth/access_token/",
            json={"client_key": acc["app_id"], "client_secret": acc["app_secret"], "grant_type": "client_credential"},
        )
        data = resp.json()
        token = (data.get("data") or {}).get("access_token")
        if not token:
            raise HTTPException(502, f"抖音授权失败: {data}")
        headers = {"access-token": token}
        # 2. 上传素材（视频走 video/init → upload → complete）
        if req.content_type == "video":
            resp = await client.post(
                "https://open.douyin.com/video/init/",
                headers=headers,
                json={"upload_url": "", "video_id": ""},
            )
            init_data = resp.json()
            upload_url = ((init_data.get("data") or {}).get("upload") or {}).get("upload_url")
            video_id = ((init_data.get("data") or {}).get("upload") or {}).get("video_id")
            if not upload_url or not video_id:
                raise HTTPException(502, f"抖音视频初始化失败: {init_data}")
            video_bytes = await _fetch_asset_bytes(req.asset_urls[0])
            resp = await client.post(upload_url, content=video_bytes, headers=headers)
            if resp.status_code != 200:
                raise HTTPException(502, f"抖音视频上传失败: {resp.status_code}")
            resp = await client.post(
                "https://open.douyin.com/video/complete/",
                headers=headers,
                json={"video_id": video_id},
            )
            complete_data = resp.json()
            if (complete_data.get("data") or {}).get("error_code") != 0:
                raise HTTPException(502, f"抖音视频上传确认失败: {complete_data}")
        # 3. 发布
        text = req.title
        if req.content:
            text = f"{text}\n{req.content}" if text else req.content
        if req.topics:
            text = f"{text}\n{' '.join(f'#{t}' for t in req.topics)}"
        if req.content_type == "video":
            resp = await client.post(
                "https://open.douyin.com/video/create/",
                headers=headers,
                json={"video_id": video_id, "text": text, "privacy_level": 0},
            )
        else:
            # 图片发布（image/create）
            img_ids = []
            for url in req.asset_urls[:9]:
                resp = await client.post(
                    "https://open.douyin.com/image/upload/",
                    headers=headers,
                    data={"text": ""},
                    files={"image": (_asset_filename(url), await _fetch_asset_bytes(url))},
                )
                img_id = ((resp.json().get("data") or {}).get("image") or {}).get("image_id")
                if img_id:
                    img_ids.append(img_id)
            if not img_ids:
                raise HTTPException(502, "抖音图片上传失败")
            resp = await client.post(
                "https://open.douyin.com/image/create/",
                headers=headers,
                json={"image_ids": img_ids, "text": text, "privacy_level": 0},
            )
        data = resp.json()
        post_id = ((data.get("data") or {}).get("item_id")) or ""
        if not post_id:
            raise HTTPException(502, f"抖音发布失败: {data}")
        return str(post_id)


# ── 快手：素材上传 + 发布 ────────────────────────────────────
async def _publish_kuaishou(acc: dict, req: PublishRequest) -> str:
    if not req.asset_urls:
        raise HTTPException(400, "请选择要发布的图片/视频素材")
    async with httpx.AsyncClient(timeout=120) as client:
        # 1. client_credential 获取 access_token
        resp = await client.post(
            "https://open.kuaishou.com/oauth2/access_token",
            json={"app_id": acc["app_id"], "app_secret": acc["app_secret"], "grant_type": "client_credentials"},
        )
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise HTTPException(502, f"快手授权失败: {data}")
        headers = {"Authorization": f"Bearer {token}"}
        # 2. 上传素材（支持图片/视频）
        if req.content_type == "video":
            resp = await client.post(
                "https://open.kuaishou.com/api/open/file/upload/start",
                headers=headers,
                json={"fileName": _asset_filename(req.asset_urls[0])},
            )
            upload = resp.json()
            upload_id = upload.get("uploadId") or (upload.get("data") or {}).get("uploadId")
            if not upload_id:
                raise HTTPException(502, f"快手上传初始化失败: {upload}")
            video_bytes = await _fetch_asset_bytes(req.asset_urls[0])
            resp = await client.post(
                "https://open.kuaishou.com/api/open/file/upload/complete",
                headers=headers,
                json={"uploadId": upload_id},
                files={"file": (_asset_filename(req.asset_urls[0]), video_bytes)},
            )
            upload_data = resp.json()
            resource_id = (upload_data.get("data") or {}).get("resourceId") or upload_data.get("resourceId")
            if not resource_id:
                raise HTTPException(502, f"快手上传失败: {upload_data}")
        else:
            resource_id = None
            img_ids = []
            for url in req.asset_urls[:9]:
                resp = await client.post(
                    "https://open.kuaishou.com/api/open/file/upload/complete",
                    headers=headers,
                    data={},
                    files={"file": (_asset_filename(url), await _fetch_asset_bytes(url))},
                )
                rid = (resp.json().get("data") or {}).get("resourceId")
                if rid:
                    img_ids.append(rid)
            resource_id = img_ids
        # 3. 发布
        text = req.title
        if req.content:
            text = f"{text}\n{req.content}" if text else req.content
        if req.topics:
            text = f"{text}\n{' '.join(f'#{t}' for t in req.topics)}"
        resp = await client.post(
            "https://open.kuaishou.com/api/open/photo/publish",
            headers=headers,
            json={
                "caption": text,
                "resources": resource_id if isinstance(resource_id, list) else [resource_id],
                "type": "video" if req.content_type == "video" else "image",
                "coverUrl": "",
            },
        )
        data = resp.json()
        photo_id = data.get("photoId") or (data.get("data") or {}).get("photoId")
        if not photo_id:
            raise HTTPException(502, f"快手发布失败: {data}")
        return str(photo_id)


async def _auto_publish(acc: dict, req: PublishRequest) -> str:
    if req.platform == "wechat":
        return await _publish_wechat(acc, req)
    if req.platform == "douyin":
        return await _publish_douyin(acc, req)
    return await _publish_kuaishou(acc, req)


@router.post("/submit")
async def submit_publish(req: PublishRequest, current_user: dict = require_auth()):
    """一键发布。

    - 平台账号已配置且该组合支持自动发布 → auto 模式（调用平台 API）
    - 否则 → guide 模式（返回素材包：正文/话题/素材/分步指引），记录 pending
    """
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, f"未知平台: {req.platform}")
    if req.content_type not in CONTENT_LABELS:
        raise HTTPException(400, f"未知内容类型: {req.content_type}")
    start = time.time()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    conn = get_db()
    if req.account_id:
        row = conn.execute("SELECT * FROM publish_accounts WHERE id=? AND active=1", (req.account_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM publish_accounts WHERE platform=? AND active=1 AND configured=1 ORDER BY created_at LIMIT 1",
            (req.platform,),
        ).fetchone()
    record_id = f"pub_{uuid.uuid4().hex[:12]}"
    topics_json = json.dumps(req.topics, ensure_ascii=False)
    assets_json = json.dumps(req.asset_urls, ensure_ascii=False)

    def save_record(status, mode, post_id="", error=""):
        conn.execute(
            """INSERT INTO publish_records (id, user_id, platform, content_type, title, content,
               topics, asset_urls, account_id, mode, status, platform_post_id, error, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (record_id, user, req.platform, req.content_type, req.title, req.content,
             topics_json, assets_json, req.account_id, mode, status, post_id, error,
             datetime.now().isoformat()),
        )
        conn.commit()

    # 无账号或组合不支持自动发布 → 引导式
    can_auto = bool(row) and AUTO_SUPPORT.get(req.platform, {}).get(req.content_type, False)
    if not can_auto:
        save_record("pending", "guide")
        conn.close()
        elapsed = round(time.time() - start, 2)
        log_usage("publish_guide", len(req.content or ""), len(GUIDE_STEPS[req.platform][req.content_type]), elapsed)
        return {
            "record_id": record_id,
            "mode": "guide",
            "status": "pending",
            "platform": req.platform,
            "content_type": req.content_type,
            "title": req.title,
            "content": req.content,
            "topics": req.topics,
            "asset_urls": req.asset_urls,
            "steps": GUIDE_STEPS[req.platform][req.content_type],
            "platform_label": PLATFORM_LABELS[req.platform],
            "message": "未配置自动发布账号，已生成引导式素材包（到官方 App 粘贴即可发布）",
        }

    # 自动发布
    acc = dict(row)
    try:
        post_id = await _auto_publish(acc, req)
        save_record("success", "auto", post_id=post_id)
        elapsed = round(time.time() - start, 2)
        log_usage("publish_auto", len(req.content or ""), len(post_id), elapsed)
        return {
            "record_id": record_id,
            "mode": "auto",
            "status": "success",
            "platform": req.platform,
            "platform_post_id": post_id,
            "message": f"已通过{PLATFORM_LABELS[req.platform]}开放接口发布成功",
        }
    except HTTPException as e:
        save_record("failed", "auto", error=str(e.detail))
        elapsed = round(time.time() - start, 2)
        log_usage("publish_auto", len(req.content or ""), 0, elapsed, success=False)
        # 自动发布失败 → 回退返回引导素材包，不阻断用户
        return {
            "record_id": record_id,
            "mode": "guide_fallback",
            "status": "failed",
            "error": str(e.detail),
            "platform": req.platform,
            "content_type": req.content_type,
            "title": req.title,
            "content": req.content,
            "topics": req.topics,
            "asset_urls": req.asset_urls,
            "steps": GUIDE_STEPS[req.platform][req.content_type],
            "platform_label": PLATFORM_LABELS[req.platform],
            "message": f"自动发布未成功（{e.detail}），已为你生成素材包，可手动发布",
        }
    finally:
        conn.close()


@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM publish_records ORDER BY created_at DESC LIMIT 100"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["asset_urls"] = json.loads(d.get("asset_urls") or "[]")
        d["platform_label"] = PLATFORM_LABELS.get(d["platform"], d["platform"])
        d["content_label"] = CONTENT_LABELS.get(d["content_type"], d["content_type"])
        result.append(d)
    return result


# ══════════════════════════════════════════════════════════════
# 发布排期（内容运营日历）
# ══════════════════════════════════════════════════════════════

class ScheduleRequest(PublishRequest):
    scheduled_at: str = Field(..., description="计划发布时间 ISO 格式，如 2026-08-05T09:00:00")


@router.post("/schedules")
async def create_schedule(req: ScheduleRequest, current_user: dict = require_auth()):
    """创建发布排期：先锁定内容，到点后一键执行。"""
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, f"未知平台: {req.platform}")
    try:
        from datetime import datetime as _dt
        _dt.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(400, "计划时间格式不正确，应为 YYYY-MM-DDTHH:MM")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    sched_id = f"sched_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    conn.execute(
        """INSERT INTO publish_schedules (id, user_id, platform, content_type, title, content,
           topics, asset_urls, account_id, scheduled_at, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (sched_id, user, req.platform, req.content_type, req.title, req.content,
         json.dumps(req.topics, ensure_ascii=False),
         json.dumps(req.asset_urls, ensure_ascii=False),
         req.account_id, req.scheduled_at, "pending", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"id": sched_id, "status": "pending", "message": "排期已创建，到点后可一键执行发布"}


@router.get("/schedules")
async def list_schedules(month: str = "", current_user: dict = require_auth()):
    """排期列表；month=YYYY-MM 时按计划月份过滤，否则返回全部未取消排期。"""
    conn = get_db()
    if month:
        rows = conn.execute(
            "SELECT * FROM publish_schedules WHERE substr(scheduled_at,1,7)=? "
            "ORDER BY scheduled_at", (month,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM publish_schedules WHERE status!='cancelled' "
            "ORDER BY scheduled_at DESC LIMIT 100"
        ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["asset_urls"] = json.loads(d.get("asset_urls") or "[]")
        d["platform_label"] = PLATFORM_LABELS.get(d["platform"], d["platform"])
        d["content_label"] = CONTENT_LABELS.get(d["content_type"], d["content_type"])
        result.append(d)
    return result


@router.delete("/schedules/{sched_id}")
async def cancel_schedule(sched_id: str, current_user: dict = require_auth()):
    conn = get_db()
    row = conn.execute("SELECT * FROM publish_schedules WHERE id=?", (sched_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "排期不存在")
    conn.execute("UPDATE publish_schedules SET status='cancelled' WHERE id=?", (sched_id,))
    conn.commit()
    conn.close()
    return {"success": True, "message": "排期已取消"}


@router.post("/schedules/{sched_id}/execute")
async def execute_schedule(sched_id: str, current_user: dict = require_auth()):
    """执行排期：复用 submit_publish 发布逻辑，成功后关联发布记录。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM publish_schedules WHERE id=?", (sched_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "排期不存在")
    s = dict(row)
    if s["status"] != "pending":
        conn.close()
        raise HTTPException(400, f"排期当前状态为 {s['status']}，无法执行")
    conn.close()
    req = PublishRequest(
        platform=s["platform"], content_type=s["content_type"], title=s["title"],
        content=s["content"], topics=json.loads(s["topics"] or "[]"),
        asset_urls=json.loads(s["asset_urls"] or "[]"), account_id=s["account_id"] or "",
    )
    result = await submit_publish(req, current_user)
    conn = get_db()
    conn.execute(
        "UPDATE publish_schedules SET status=?, published_record_id=? WHERE id=?",
        ("published" if result.get("status") == "success" else "pending",
         result.get("record_id", ""), sched_id),
    )
    conn.commit()
    conn.close()
    return result


# ══════════════════════════════════════════════════════════════
# 发布数据统计（运营看板）
# ══════════════════════════════════════════════════════════════

@router.get("/stats")
async def publish_stats(current_user: dict = require_auth()):
    """运营看板统计：总量 / 平台分布 / 状态分布 / 近 30 天趋势 / 排期概览。"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS n FROM publish_records").fetchone()["n"]
    success = conn.execute(
        "SELECT COUNT(*) AS n FROM publish_records WHERE status='success'"
    ).fetchone()["n"]
    by_platform = {}
    for r in conn.execute(
        "SELECT platform, COUNT(*) AS n FROM publish_records GROUP BY platform"
    ).fetchall():
        by_platform[r["platform"]] = r["n"]
    by_status = {}
    for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM publish_records GROUP BY status"
    ).fetchall():
        by_status[r["status"]] = r["n"]
    # 近 30 天趋势（SQLite date 函数按本地日期聚合）
    trend = []
    rows = conn.execute(
        """SELECT substr(created_at,1,10) AS day, COUNT(*) AS n
           FROM publish_records WHERE created_at >= datetime('now','-29 days')
           GROUP BY day ORDER BY day"""
    ).fetchall()
    day_map = {r["day"]: r["n"] for r in rows}
    from datetime import timedelta
    today = datetime.now().date()
    for i in range(29, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        trend.append({"date": d, "count": day_map.get(d, 0)})
    # 排期概览
    upcoming = conn.execute(
        "SELECT COUNT(*) AS n FROM publish_schedules WHERE status='pending' "
        "AND scheduled_at >= datetime('now','-1 day')"
    ).fetchone()["n"]
    overdue = conn.execute(
        "SELECT COUNT(*) AS n FROM publish_schedules WHERE status='pending' "
        "AND scheduled_at < datetime('now')"
    ).fetchone()["n"]
    conn.close()
    return {
        "total": total,
        "success": success,
        "failed": by_status.get("failed", 0),
        "pending": by_status.get("pending", 0),
        "success_rate": round(success / total * 100, 1) if total else 0,
        "by_platform": by_platform,
        "by_status": by_status,
        "trend_30d": trend,
        "upcoming_schedules": upcoming,
        "overdue_schedules": overdue,
    }
