#!/usr/bin/env python3
"""内容发布中心 — 公众号 / 抖音 / 快手 一键发布。

双模式：
- guide 引导式（默认，零配置）：把文章/图片/视频组装成发布素材包
  （标题 + 话题 + 正文 + 素材下载链接 + 分步指引），用户到官方 App/后台粘贴发布
- auto 自动发布（可选）：账号配置 AppID/Secret 后调用平台开放 API 直接发布
  （微信公众号：draft + freepublish；抖音/快手：素材上传 + 发布）

发布记录统一落库 publish_records，便于追溯。
"""

import asyncio
import io
import json
import logging
import os
import time
import uuid
import zipfile
from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.config import load_config
from common.db import get_db
from common.llm import call_llm_async, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/publish", tags=["内容发布"])

load_config()

# 自动发布时下载站内素材的内部地址（asset_urls 为相对路径时拼接）
_INTERNAL_BASE = os.environ.get("PUBLISH_INTERNAL_BASE", "http://127.0.0.1:8888")

PLATFORM_LABELS = {"wechat": "微信公众号", "douyin": "抖音", "kuaishou": "快手"}
CONTENT_LABELS = {"article": "图文", "image": "图片", "video": "视频"}

# 多平台自动适配规格（封面比例 + 文案调性）
PLATFORM_SPECS = {
    "wechat": {
        "cover": (900, 383),
        "cover_note": "900×383（2.35:1 横版）",
        "tone": "公众号深度图文风格：专业、结构化，首段点题，小标题分段，结尾引导互动；避免夸张标题党",
    },
    "douyin": {
        "cover": (1080, 1920),
        "cover_note": "1080×1920（9:16 竖版）",
        "tone": "抖音短视频风格：第一句即钩子，短句高频、情绪化、口语化，带话题标签，引导点赞评论；控制在 100 字内",
    },
    "kuaishou": {
        "cover": (1080, 1440),
        "cover_note": "1080×1440（3:4 竖版）",
        "tone": "快手老铁风格：真实接地气、亲切口吻，直白不端着，带话题标签；控制在 120 字内",
    },
}

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
    _ensure_account_columns(conn)
    rows = conn.execute("SELECT * FROM publish_accounts WHERE active=1 ORDER BY platform, created_at").fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["today_published"] = _count_today_published(conn, d["id"])
        d["daily_limit"] = int(d.get("daily_limit") or 10)
        result.append(_mask_account(d))
    conn.close()
    return result


@router.post("/accounts")
async def upsert_account(req: AccountRequest, current_user: dict = require_auth()):
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, "操作失败，请稍后重试")
    now = datetime.now().isoformat()
    conn = get_db()
    row = conn.execute("SELECT * FROM publish_accounts WHERE platform=? AND active=1", (req.platform,)).fetchone()
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
        raise HTTPException(502, "操作失败，请稍后重试")
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
        raise HTTPException(
            400,
            (
                f"{PLATFORM_LABELS[acc['platform']]} 的 AppID/Secret 需先在开放平台完成应用创建与审核，"
                "凭据通过后即可自动发布。审核前请使用「引导式发布」（零配置）"
            ),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, "服务异常，请稍后重试") from e


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
                "prompt": (
                    json.loads(r["content"]) if isinstance(r["content"], str) and r["content"].startswith("{") else {}
                ).get("prompt", "")
                if r["content"]
                else "",
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


# ══════════════════════════════════════════════════════════════
# 账号矩阵：配额控制 / 批量导入 / 失败换号
# ══════════════════════════════════════════════════════════════


def _ensure_account_columns(conn) -> None:
    """幂等补列：publish_accounts.daily_limit（每账号每日发布上限）。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(publish_accounts)").fetchall()]
    if "daily_limit" not in cols:
        conn.execute("ALTER TABLE publish_accounts ADD COLUMN daily_limit INTEGER DEFAULT 10")
        conn.commit()


def _count_today_published(conn, acc_id: str) -> int:
    """统计账号当日已成功发布数（防限流配额）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM publish_records "
        "WHERE account_id=? AND status='success' AND substr(created_at,1,10)=?",
        (acc_id, today),
    ).fetchone()
    return int(row["c"] or 0)


def _pick_account(conn, platform: str, account_id: str = "") -> dict | None:
    """配额感知选号：优先指定账号；超当日限额自动轮换同平台下一个有配额账号。"""
    _ensure_account_columns(conn)
    rows = conn.execute(
        "SELECT * FROM publish_accounts WHERE platform=? AND active=1 AND configured=1 ORDER BY created_at",
        (platform,),
    ).fetchall()
    if not rows:
        return None
    if account_id:
        row = next((r for r in rows if r["id"] == account_id), None)
        if row and _count_today_published(conn, row["id"]) < int(row.get("daily_limit") or 10):
            return dict(row)
    for r in rows:
        if _count_today_published(conn, r["id"]) < int(r.get("daily_limit") or 10):
            return dict(r)
    return None


class BatchAccountRequest(BaseModel):
    platform: str = Field(..., description="wechat/douyin/kuaishou")
    lines: str = Field(..., description="每行一个账号：名称|AppID|AppSecret")


@router.post("/accounts/batch")
async def batch_import_accounts(req: BatchAccountRequest, current_user: dict = require_auth()):
    """账号矩阵：一次粘贴多行批量导入账号（矩阵号运营）。"""
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, "操作失败，请稍后重试")
    conn = get_db()
    _ensure_account_columns(conn)
    now = datetime.now().isoformat()
    imported, skipped = [], []
    for i, line in enumerate(req.lines.strip().splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            skipped.append(f"第 {i} 行格式错误（应为：名称|AppID|AppSecret）")
            continue
        name, app_id, app_secret = parts[0], parts[1], parts[2]
        if not app_id or not app_secret:
            skipped.append(f"第 {i} 行缺少 AppID/AppSecret")
            continue
        acc_id = f"pubacc_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """INSERT INTO publish_accounts (id, platform, name, app_id, app_secret,
               configured, created_at, updated_at, active) VALUES (?,?,?,?,?,?,?,?,1)""",
            (acc_id, req.platform, name, app_id, app_secret, 1, now, now),
        )
        imported.append({"id": acc_id, "name": name, "app_id": app_id})
    conn.commit()
    conn.close()
    return {"count": len(imported), "imported": imported, "skipped": skipped}


# ══════════════════════════════════════════════════════════════
# 多平台自动适配：封面裁切 + 正文改写 + 话题标签
# ══════════════════════════════════════════════════════════════

_ADAPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "adapted")
_ADAPT_SYSTEM = """你是一位拥有8年+经验的新媒体运营主编，精通微信公众号、抖音、快手等主流内容平台的算法机制和用户阅读习惯，擅长将同一内容精准适配到不同平台以最大化阅读和互动。

## 平台适配策略

### 微信公众号
- **标题**：深度悬念型，善用数字+对比（"月入3万的人，都在偷偷做这3件事"），15-25字
- **正文**：结构化长文风，开头钩子→痛点共鸣→干货输出→互动引导
- **话题标签**：2-3个精准领域标签
- **排版**：段落间空行、重点加粗、适当用小标题分段

### 抖音
- **标题**：短冲击型，强情绪触发（"千万别XX！""这个方法太绝了"），8-15字
- **正文**：口语化短句，每段1-2行，emoji点缀，结尾设问引导评论
- **话题标签**：4-5个，金字塔结构（1个大流量标签+2-3个精准标签）
- **节奏**：前15字决定完播率，开头必须有钩子

### 快手
- **标题**：接地气真实感（"老铁们，这个办法真的好使"），10-20字
- **正文**：唠嗑风，信任感优先，生活化表达，像跟朋友分享
- **话题标签**：2-3个社区感标签

### 小红书
- **标题**：种草风，用"姐妹们"开头，emoji点缀，突出效果/体验，10-20字
- **正文**：真实体验感，用"我个人觉得"、"用完感觉"等主观表达
- **话题标签**：5-8个，覆盖大标签+精准标签+品牌标签

## 改写原则
1. **保留核心信息**：不编造、不曲解原意，关键数据和结论必须保留
2. **适配语气**：同一信息用不同平台的"方言"表达（如微信说"建议收藏"，抖音说"点赞收藏防走丢"）
3. **标题差异化**：同一内容给不同平台的标题可以从不同角度切入（数据角度/情感角度/悬念角度）
4. **字数控制**：根据平台特性调整内容长短（微信可长、抖音快手宜短）

严格只输出一个 JSON 对象（不要解释文字、不要 markdown 代码块）：
{"title": "改写后的标题", "content": "改写后的正文", "topics": ["话题1", "话题2", "话题3"]}"""


def _extract_json_loose(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象（容忍噪音）。"""
    import re as _re

    text = (text or "").strip()
    m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("输出中未找到 JSON 对象")
    return json.loads(text[start : end + 1])


def _crop_cover(data: bytes, target: tuple[int, int], out_path: str) -> bool:
    """中心裁切 + 缩放封面到目标尺寸（Pillow），成功返回 True。"""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        if img.mode != "RGB":
            img = img.convert("RGB")
        tw, th = target
        w, h = img.size
        target_ratio = tw / th
        ratio = w / h
        if ratio > target_ratio:
            nw = int(h * target_ratio)
            x = (w - nw) // 2
            img = img.crop((x, 0, x + nw, h))
        else:
            nh = int(w / target_ratio)
            y = (h - nh) // 2
            img = img.crop((0, y, w, y + nh))
        img = img.resize((tw, th), Image.LANCZOS)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, "PNG")
        return True
    except Exception as e:
        logger.warning("cover crop failed: %s", e)
        return False


async def _adapt_content(req: PublishRequest) -> dict:
    """多平台自动适配：封面按平台规格裁切 + 正文按平台调性 LLM 改写 + 话题标签生成。

    LLM 改写失败不影响发布（回退原文），返回 adapted 记录供展示与追溯。
    """
    spec = PLATFORM_SPECS.get(req.platform, {})
    adapted = {
        "platform": req.platform,
        "title": req.title,
        "content": req.content,
        "topics": list(req.topics),
        "cover_url": req.asset_urls[0] if req.asset_urls else "",
        "note": [],
    }
    # 1. 封面按平台规格裁切（仅首张图片素材）
    if req.asset_urls and spec.get("cover"):
        try:
            data = await _fetch_asset_bytes(req.asset_urls[0])
            fname = f"{uuid.uuid4().hex[:10]}_{req.platform}.png"
            out_path = os.path.join(_ADAPT_DIR, fname)
            if _crop_cover(data, spec["cover"], out_path):
                adapted["cover_url"] = f"/uploads/adapted/{fname}"
                adapted["note"].append(f"封面已适配为 {spec['cover_note']}")
            else:
                adapted["note"].append("封面裁切失败，使用原图")
        except Exception as e:
            logger.warning("cover fetch failed: %s", e)
            adapted["note"].append("封面下载失败，使用原图")
    # 2. 正文按平台调性改写 + 话题标签生成
    if spec.get("tone") and (req.content or req.title):
        try:
            prompt = (
                f"目标平台：{PLATFORM_LABELS[req.platform]}。平台调性：{spec['tone']}\n\n"
                f"原标题：{req.title or '（无）'}\n原正文：{req.content or '（无）'}\n"
                f"已有话题：{' '.join('#' + t for t in req.topics) if req.topics else '（无）'}\n\n"
                "请按平台调性改写标题与正文，并生成平台话题标签（如已有话题则优化补充）。"
            )
            result = await call_llm_async(_ADAPT_SYSTEM, prompt, max_tokens=1500, temperature=0.6, timeout=90)
            data = _extract_json_loose(result)
            if data.get("title"):
                adapted["title"] = str(data["title"])[:200]
            if data.get("content"):
                adapted["content"] = str(data["content"])[:20000]
            if data.get("topics"):
                adapted["topics"] = [str(t).strip("#").strip() for t in data["topics"] if str(t).strip()][:8]
            adapted["note"].append("正文已按平台调性改写，话题标签已生成")
        except Exception as e:
            logger.warning("content adapt skipped: %s", e)
            adapted["note"].append("AI 改写不可用，保留原文")
    return adapted


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
            raise HTTPException(502, "操作失败，请稍后重试")
        thumb_media_id = data["media_id"]
        # 2. 保存草稿
        articles = [
            {
                "title": req.title or "未命名",
                "author": acc.get("name") or "",
                "digest": (req.content or "")[:120],
                "content": (req.content or "").replace("\n", "<br>"),
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 1,
                "only_fans_can_comment": 0,
            }
        ]
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": token},
            json={"articles": articles},
        )
        data = resp.json()
        if "media_id" not in data:
            raise HTTPException(502, "操作失败，请稍后重试")
        draft_media_id = data["media_id"]
        # 3. 发布（frepublish 不需要群发审核，走发布能力）
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/freepublish/submit",
            params={"access_token": token},
            json={"media_id": draft_media_id},
        )
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise HTTPException(502, "操作失败，请稍后重试")
        return str(data.get("publish_id", ""))


# ── 抖音：素材上传 + 发布 ────────────────────────────────────

async def _dy_upload_video(client, headers: dict, req: PublishRequest) -> str:
    """抖音视频上传（init → upload → complete），返回 video_id。"""
    resp = await client.post("https://open.douyin.com/video/init/", headers=headers, json={"upload_url": "", "video_id": ""})
    init_data = resp.json()
    upload_url = ((init_data.get("data") or {}).get("upload") or {}).get("upload_url")
    video_id = ((init_data.get("data") or {}).get("upload") or {}).get("video_id")
    if not upload_url or not video_id:
        raise HTTPException(502, "操作失败，请稍后重试")
    video_bytes = await _fetch_asset_bytes(req.asset_urls[0])
    resp = await client.post(upload_url, content=video_bytes, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(502, "操作失败，请稍后重试")
    resp = await client.post("https://open.douyin.com/video/complete/", headers=headers, json={"video_id": video_id})
    if (resp.json().get("data") or {}).get("error_code") != 0:
        raise HTTPException(502, "操作失败，请稍后重试")
    return video_id


async def _dy_publish_images(client, headers: dict, req: PublishRequest, text: str) -> dict:
    """抖音图片上传 + 发布，返回响应 JSON。"""
    img_ids = []
    for url in req.asset_urls[:9]:
        resp = await client.post(
            "https://open.douyin.com/image/upload/", headers=headers,
            data={"text": ""}, files={"image": (_asset_filename(url), await _fetch_asset_bytes(url))},
        )
        img_id = ((resp.json().get("data") or {}).get("image") or {}).get("image_id")
        if img_id:
            img_ids.append(img_id)
    if not img_ids:
        raise HTTPException(502, "抖音图片上传失败")
    return await client.post(
        "https://open.douyin.com/image/create/", headers=headers,
        json={"image_ids": img_ids, "text": text, "privacy_level": 0},
    )

async def _publish_douyin(acc: dict, req: PublishRequest) -> str:  # noqa: C901
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
            raise HTTPException(502, "操作失败，请稍后重试")
        headers = {"access-token": token}
        # 2-3. 上传素材 + 发布
        text = req.title
        if req.content:
            text = f"{text}\n{req.content}" if text else req.content
        if req.topics:
            text = f"{text}\n{' '.join(f'#{t}' for t in req.topics)}"
        if req.content_type == "video":
            video_id = await _dy_upload_video(client, headers, req)
            resp = await client.post(
                "https://open.douyin.com/video/create/",
                headers=headers,
                json={"video_id": video_id, "text": text, "privacy_level": 0},
            )
        else:
            resp = await _dy_publish_images(client, headers, req, text)
        data = resp.json()
        post_id = ((data.get("data") or {}).get("item_id")) or ""
        if not post_id:
            raise HTTPException(502, "操作失败，请稍后重试")
        return str(post_id)


# ── 快手：素材上传 + 发布 ────────────────────────────────────

async def _ks_upload_media(client, headers: dict, req: PublishRequest) -> object:
    """上传素材到快手：视频走 uploadId 两段式，图片逐个上传。返回 resourceId 或 id 列表。"""
    if req.content_type == "video":
        resp = await client.post(
            "https://open.kuaishou.com/api/open/file/upload/start",
            headers=headers,
            json={"fileName": _asset_filename(req.asset_urls[0])},
        )
        upload = resp.json()
        upload_id = upload.get("uploadId") or (upload.get("data") or {}).get("uploadId")
        if not upload_id:
            raise HTTPException(502, "操作失败，请稍后重试")
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
            raise HTTPException(502, "操作失败，请稍后重试")
        return resource_id
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
    return img_ids

async def _publish_kuaishou(acc: dict, req: PublishRequest) -> str:  # noqa: C901
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
            raise HTTPException(502, "操作失败，请稍后重试")
        headers = {"Authorization": f"Bearer {token}"}
        # 2. 上传素材（支持图片/视频）
        resource_id = await _ks_upload_media(client, headers, req)
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
            raise HTTPException(502, "操作失败，请稍后重试")
        return str(photo_id)


async def _auto_publish(acc: dict, req: PublishRequest) -> str:
    if req.platform == "wechat":
        return await _publish_wechat(acc, req)
    if req.platform == "douyin":
        return await _publish_douyin(acc, req)
    return await _publish_kuaishou(acc, req)


def _ensure_publish_columns(conn) -> None:
    """幂等补列：publish_records.adapted（多平台适配结果 JSON）+ review_status（审核状态）。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(publish_records)").fetchall()]
    if "adapted" not in cols:
        conn.execute("ALTER TABLE publish_records ADD COLUMN adapted TEXT DEFAULT ''")
    if "review_status" not in cols:
        conn.execute("ALTER TABLE publish_records ADD COLUMN review_status TEXT DEFAULT 'draft'")
    if "review_note" not in cols:
        conn.execute("ALTER TABLE publish_records ADD COLUMN review_note TEXT DEFAULT ''")
    if "reviewed_by" not in cols:
        conn.execute("ALTER TABLE publish_records ADD COLUMN reviewed_by TEXT DEFAULT ''")
    conn.commit()



def _publish_pick_candidates(acc: dict | None, platform: str) -> list:
    """配额感知选号：指定账号 + 同平台有配额账号（最多3个候选）。"""
    candidates = []
    if acc:
        candidates.append(acc)
    conn2 = get_db()
    for r in conn2.execute(
        "SELECT * FROM publish_accounts WHERE platform=? AND active=1 AND configured=1 ORDER BY created_at",
        (platform,),
    ).fetchall():
        if all(c["id"] != r["id"] for c in candidates) and _count_today_published(conn2, r["id"]) < int(
            r.get("daily_limit") or 10
        ):
            candidates.append(dict(r))
    conn2.close()
    return candidates[:3]


async def _publish_auto_try(candidates: list, req: PublishRequest, adapted_json: str, record_id: str, acc) -> tuple:
    """自动发布 + 账号矩阵换号重试。成功返回结果 dict，全部失败返回 None。"""
    last_err = ""
    for acc_try in candidates:
        try:
            post_id = await _auto_publish(acc_try, req)
            conn = get_db()
            _ensure_publish_columns(conn)
            conn.execute(
                """UPDATE publish_records SET status='success', mode='auto', account_id=?, platform_post_id=?,
                   adapted=? WHERE id=?""",
                (acc_try["id"], post_id, adapted_json, record_id),
            )
            conn.commit()
            conn.close()
            return {
                "record_id": record_id,
                "mode": "auto",
                "status": "success",
                "platform": req.platform,
                "platform_post_id": post_id,
                "account_id": acc_try["id"],
                "message": f"已通过{PLATFORM_LABELS[req.platform]}开放接口发布成功（账号：{acc_try.get('name') or '默认'}"
                + ("，已换号重试" if acc_try["id"] != (acc or {}).get("id") else "")
                + "）",
            }, ""
        except HTTPException as e:
            last_err = str(e.detail)
            logger.warning("auto publish failed with account %s: %s", acc_try["id"], last_err)
            continue
        except Exception as e:
            last_err = str(e)
            logger.warning("auto publish unexpected error with account %s: %s", acc_try["id"], last_err)
            continue
    return None, last_err


def _publish_guide_response(record_id: str, req: PublishRequest, adapted: dict, user: str, last_err: str = "") -> dict:
    """引导式素材包响应（未配置账号或自动发布失败时）。"""
    return {
        "record_id": record_id,
        "mode": "guide_fallback",
        "status": "failed",
        "error": last_err,
        "platform": req.platform,
        "content_type": req.content_type,
        "title": adapted["title"],
        "content": adapted["content"],
        "topics": adapted["topics"],
        "cover_url": adapted.get("cover_url", ""),
        "adapted": adapted,
        "asset_urls": req.asset_urls,
        "steps": GUIDE_STEPS[req.platform][req.content_type],
        "platform_label": PLATFORM_LABELS[req.platform],
        "message": f"自动发布未成功（{last_err}），已生成素材包可手动发布",
    }

@router.post("/submit")
async def submit_publish(req: PublishRequest, current_user: dict = require_auth()):  # noqa: C901
    """一键发布（增长引擎版）。

    - 多平台自动适配：封面按平台规格裁切、正文按平台调性改写、话题标签生成
    - 账号矩阵：配额感知选号（指定账号超当日限额自动轮换），自动发布失败自动换号重试
    - 平台账号已配置且组合支持自动发布 → auto 模式；否则 → guide 模式（返回素材包）
    """
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, "操作失败，请稍后重试")
    if req.content_type not in CONTENT_LABELS:
        raise HTTPException(400, "操作失败，请稍后重试")
    start = time.time()
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""

    record_id = f"pub_{uuid.uuid4().hex[:12]}"

    # 1. 多平台自动适配（封面裁切 + 正文改写 + 话题标签，失败回退原文不影响发布）
    #    注意：线程级共享 sqlite 连接不能跨越 await，适配完成后再统一取连接
    adapted = await _adapt_content(req)
    adapted_json = json.dumps(adapted, ensure_ascii=False)
    topics_json = json.dumps(adapted["topics"], ensure_ascii=False)
    assets_json = json.dumps(req.asset_urls, ensure_ascii=False)

    def save_record(status, mode, post_id="", error=""):
        # 自管理连接：内部取用/关闭，避免闭包连接跨 await 失效
        c = get_db()
        _ensure_publish_columns(c)
        c.execute(
            """INSERT INTO publish_records (id, user_id, platform, content_type, title, content,
               topics, asset_urls, account_id, mode, status, platform_post_id, error, adapted, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record_id,
                user,
                req.platform,
                req.content_type,
                adapted["title"],
                adapted["content"],
                topics_json,
                assets_json,
                req.account_id,
                mode,
                status,
                post_id,
                error,
                adapted_json,
                datetime.now().isoformat(),
            ),
        )
        c.commit()
        c.close()

    # 2. 配额感知选号（指定账号超限自动轮换同平台其他账号）
    conn = get_db()
    _ensure_account_columns(conn)
    acc = _pick_account(conn, req.platform, req.account_id)
    can_auto = bool(acc) and AUTO_SUPPORT.get(req.platform, {}).get(req.content_type, False)
    if not can_auto:
        conn.close()
        save_record("pending", "guide")
        elapsed = round(time.time() - start, 2)
        log_usage("publish_guide", len(req.content or ""), len(GUIDE_STEPS[req.platform][req.content_type]), elapsed)
        resp = _publish_guide_response(record_id, req, adapted, user)
        resp["mode"] = "guide"
        resp["status"] = "pending"
        resp["message"] = "未配置自动发布账号，已生成引导式素材包（到官方 App 粘贴即可发布）"
        return resp

    # 3. 自动发布 + 账号矩阵换号重试（同平台有配额账号逐个尝试）
    candidates = _publish_pick_candidates(acc, req.platform)
    result, last_err = await _publish_auto_try(candidates, req, adapted_json, record_id, acc)
    if result:
        elapsed = round(time.time() - start, 2)
        log_usage("publish_auto", len(req.content or ""), len(result.get("platform_post_id", "")), elapsed)
        return result

    # 全部账号失败 → 回退引导式素材包（不阻断用户）
    save_record("failed", "guide_fallback", error=last_err)
    elapsed = round(time.time() - start, 2)
    log_usage("publish_auto", len(req.content or ""), 0, elapsed, success=False)
    conn.close()
    return _publish_guide_response(record_id, req, adapted, user, last_err)


class CrossPostRequest(BaseModel):
    platforms: list[str] = Field(..., min_length=1, description="目标平台列表 [wechat, douyin, kuaishou]")
    content_type: str = Field("article", description="article/image/video")
    title: str = Field("", max_length=200)
    content: str = Field("", max_length=20000)
    topics: list[str] = Field(default_factory=list)
    asset_urls: list[str] = Field(default_factory=list)


@router.post("/cross-post")
async def cross_post(req: CrossPostRequest, current_user: dict = require_auth()):
    """跨平台一键分发：一次编辑，同时发布到多个平台。

    循环每个目标平台：独立适配 → 选号 → 发布，聚合返回结果。
    """
    results = []
    for p in req.platforms:
        if p not in PLATFORM_LABELS:
            results.append({"platform": p, "status": "error", "message": f"未知平台: {p}"})
            continue
        try:
            sub_req = PublishRequest(
                platform=p,
                content_type=req.content_type,
                title=req.title,
                content=req.content,
                topics=req.topics,
                asset_urls=req.asset_urls,
            )
            r = await submit_publish(sub_req, current_user)
            results.append(
                {
                    "platform": p,
                    "status": r.get("status", "pending"),
                    "mode": r.get("mode", "guide"),
                    "record_id": r.get("record_id", ""),
                    "message": r.get("message", ""),
                    "adapted": r.get("adapted"),
                }
            )
        except Exception as e:
            results.append({"platform": p, "status": "error", "message": str(e)})
    success_count = sum(1 for r in results if r["status"] in ("success", "pending"))
    return {
        "total": len(req.platforms),
        "success": success_count,
        "results": results,
        "message": f"已向{success_count}/{len(req.platforms)}个平台提交发布",
    }


@router.get("/records")
async def list_records(
    platform: str = "",
    content_type: str = "",
    status: str = "",
    mode: str = "",
    q: str = "",
    limit: int = 100,
    current_user: dict = require_auth(),
):
    """发布记录：支持按平台/内容类型/状态/模式筛选 + 关键词搜索（标题/内容）。"""
    where, params = [], []
    if platform:
        where.append("platform=?")
        params.append(platform)
    if content_type:
        where.append("content_type=?")
        params.append(content_type)
    if status:
        where.append("status=?")
        params.append(status)
    if mode:
        where.append("mode=?")
        params.append(mode)
    if q:
        where.append("(title LIKE ? OR content LIKE ?)")
        params.append(f"%{q}%")
        params.append(f"%{q}%")
    sql = "SELECT * FROM publish_records"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["asset_urls"] = json.loads(d.get("asset_urls") or "[]")
        d["adapted"] = json.loads(d.get("adapted") or "null")
        d["platform_label"] = PLATFORM_LABELS.get(d["platform"], d["platform"])
        d["content_label"] = CONTENT_LABELS.get(d["content_type"], d["content_type"])
        result.append(d)
    return result


@router.get("/records/{record_id}/package")
async def download_package(record_id: str, current_user: dict = require_auth()):
    """素材包 ZIP 一键下载：README 步骤 + 正文文案 + 全部素材文件（商用发布素材包）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM publish_records WHERE id=?", (record_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "发布记录不存在")
    r = dict(row)
    topics = json.loads(r.get("topics") or "[]")
    asset_urls = json.loads(r.get("asset_urls") or "[]")
    steps = GUIDE_STEPS.get(r["platform"], {}).get(r["content_type"], [])
    platform_label = PLATFORM_LABELS.get(r["platform"], r["platform"])
    content_label = CONTENT_LABELS.get(r["content_type"], r["content_type"])

    readme = [
        f"# {r.get('title') or '发布素材包'}",
        "",
        f"- 目标平台：{platform_label}",
        f"- 内容类型：{content_label}",
        f"- 创建时间：{r.get('created_at', '')}",
        "",
        "## 发布步骤",
    ]
    readme += [f"{i + 1}. {s}" for i, s in enumerate(steps)]
    if topics:
        readme += ["", "## 话题标签", " ".join(f"#{t}" for t in topics)]
    if asset_urls:
        readme += ["", "## 素材文件", "本包 assets/ 目录下包含以下素材："]
        readme += [f"- {_asset_filename(u)}" for u in asset_urls]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", "\n".join(readme))
        zf.writestr("content.txt", f"标题：{r.get('title', '')}\n\n{r.get('content', '')}")
        for i, url in enumerate(asset_urls):
            try:
                data = await _fetch_asset_bytes(url)
            except Exception as e:
                logger.warning("package asset fetch failed %s: %s", url, e)
                continue
            zf.writestr(f"assets/{i + 1:02d}_{_asset_filename(url)}", data)
    from urllib.parse import quote

    fname = f"{platform_label}_{r.get('title') or record_id}.zip"
    try:
        fname.encode("latin-1")
        ascii_name = fname
    except UnicodeEncodeError:
        ascii_name = "publish_package.zip"
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(fname)}"},
    )


# ══════════════════════════════════════════════════════════════
# 发布排期（内容运营日历）
# ══════════════════════════════════════════════════════════════


def _ensure_schedule_columns(conn) -> None:
    """幂等补列：publish_schedules.attempts（自动执行重试计数）。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(publish_schedules)").fetchall()]
    if "attempts" not in cols:
        conn.execute("ALTER TABLE publish_schedules ADD COLUMN attempts INTEGER DEFAULT 0")
        conn.commit()


async def _run_due_schedules():
    """排期后台调度器：每 60s 扫描到期 pending 排期并自动执行发布。

    - 自动发布成功 / 素材包生成成功 → 排期标记 published 并关联发布记录
    - 自动发布失败 → 保留 pending 自动重试（≤3 次后标记 failed），不丢排期
    """
    while True:
        try:
            conn = get_db()
            _ensure_schedule_columns(conn)
            rows = conn.execute(
                "SELECT * FROM publish_schedules WHERE status='pending' "
                "AND scheduled_at <= ? ORDER BY scheduled_at LIMIT 10",
                (datetime.now().isoformat(),),
            ).fetchall()
            conn.close()
            for row in rows:
                s = dict(row)
                try:
                    req = PublishRequest(
                        platform=s["platform"],
                        content_type=s["content_type"],
                        title=s["title"],
                        content=s["content"],
                        topics=json.loads(s["topics"] or "[]"),
                        asset_urls=json.loads(s["asset_urls"] or "[]"),
                        account_id=s["account_id"] or "",
                    )
                    result = await submit_publish(req, {"username": s.get("user_id", "")})
                    conn = get_db()
                    _ensure_schedule_columns(conn)
                    if result.get("status") in ("success", "pending"):
                        # 已发布成功或素材包已生成（guide 模式）→ 排期完成
                        conn.execute(
                            "UPDATE publish_schedules SET status='published', published_record_id=? WHERE id=?",
                            (result.get("record_id", ""), s["id"]),
                        )
                    else:
                        attempts = int(s.get("attempts") or 0) + 1
                        conn.execute(
                            "UPDATE publish_schedules SET attempts=? WHERE id=?",
                            (attempts, s["id"]),
                        )
                        if attempts >= 3:
                            conn.execute("UPDATE publish_schedules SET status='failed' WHERE id=?", (s["id"],))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    logger.warning("scheduled publish failed %s: %s", s["id"], e)
                    try:
                        conn = get_db()
                        _ensure_schedule_columns(conn)
                        attempts = int(s.get("attempts") or 0) + 1
                        if attempts >= 3:
                            conn.execute(
                                "UPDATE publish_schedules SET status='failed', attempts=? WHERE id=?",
                                (attempts, s["id"]),
                            )
                        else:
                            conn.execute("UPDATE publish_schedules SET attempts=? WHERE id=?", (attempts, s["id"]))
                        conn.commit()
                        conn.close()
                    except Exception:
                        logger.exception("schedule attempt update failed")
        except Exception:
            logger.exception("schedule runner error")
        await asyncio.sleep(60)


class ScheduleRequest(PublishRequest):
    scheduled_at: str = Field(..., description="计划发布时间 ISO 格式，如 2026-08-05T09:00:00")


@router.post("/schedules")
async def create_schedule(req: ScheduleRequest, current_user: dict = require_auth()):
    """创建发布排期：先锁定内容，到点后一键执行。"""
    if req.platform not in PLATFORM_LABELS:
        raise HTTPException(400, "操作失败，请稍后重试")
    try:
        from datetime import datetime as _dt

        _dt.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
    except ValueError as e:
        raise HTTPException(400, "计划时间格式不正确，应为 YYYY-MM-DDTHH:MM") from e
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    sched_id = f"sched_{uuid.uuid4().hex[:12]}"
    conn = get_db()
    _ensure_schedule_columns(conn)
    conn.execute(
        """INSERT INTO publish_schedules (id, user_id, platform, content_type, title, content,
           topics, asset_urls, account_id, scheduled_at, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            sched_id,
            user,
            req.platform,
            req.content_type,
            req.title,
            req.content,
            json.dumps(req.topics, ensure_ascii=False),
            json.dumps(req.asset_urls, ensure_ascii=False),
            req.account_id,
            req.scheduled_at,
            "pending",
            datetime.now().isoformat(),
        ),
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
            "SELECT * FROM publish_schedules WHERE substr(scheduled_at,1,7)=? ORDER BY scheduled_at",
            (month,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM publish_schedules WHERE status!='cancelled' ORDER BY scheduled_at DESC LIMIT 100"
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


class BatchCancelRequest(BaseModel):
    ids: list[str] = Field(..., min_length=1, description="要取消的排期 ID 列表")


@router.post("/schedules/batch-cancel")
async def batch_cancel_schedules(req: BatchCancelRequest, current_user: dict = require_auth()):
    """批量取消排期（仅 pending 状态生效，已发布/已取消的跳过）。"""
    conn = get_db()
    cancelled = 0
    for sid in req.ids:
        row = conn.execute("SELECT status FROM publish_schedules WHERE id=?", (sid,)).fetchone()
        if row and row["status"] == "pending":
            conn.execute("UPDATE publish_schedules SET status='cancelled' WHERE id=?", (sid,))
            cancelled += 1
    conn.commit()
    conn.close()
    return {"success": True, "cancelled": cancelled}


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
        raise HTTPException(400, "操作失败，请稍后重试")
    conn.close()
    req = PublishRequest(
        platform=s["platform"],
        content_type=s["content_type"],
        title=s["title"],
        content=s["content"],
        topics=json.loads(s["topics"] or "[]"),
        asset_urls=json.loads(s["asset_urls"] or "[]"),
        account_id=s["account_id"] or "",
    )
    result = await submit_publish(req, current_user)
    conn = get_db()
    conn.execute(
        "UPDATE publish_schedules SET status=?, published_record_id=? WHERE id=?",
        ("published" if result.get("status") == "success" else "pending", result.get("record_id", ""), sched_id),
    )
    conn.commit()
    conn.close()
    return result


# ══════════════════════════════════════════════════════════════
# 团队审核流
# ══════════════════════════════════════════════════════════════


class ReviewRequest(BaseModel):
    action: str = Field(..., description="approve / reject / reset")
    note: str = Field("", max_length=500)


@router.get("/review-queue")
async def review_queue(
    platform: str = "",
    limit: int = 50,
    current_user: dict = require_auth(),
):
    """审核队列：待审核的发布记录列表。"""
    conn = get_db()
    _ensure_publish_columns(conn)
    where, params = ["review_status='pending_review'"], []
    if platform:
        where.append("platform=?")
        params.append(platform)
    rows = conn.execute(
        f"SELECT * FROM publish_records WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["topics"] = json.loads(d.get("topics") or "[]")
        d["adapted"] = json.loads(d.get("adapted") or "null")
        d["platform_label"] = PLATFORM_LABELS.get(d["platform"], d["platform"])
        result.append(d)
    return result


@router.put("/records/{record_id}/review")
async def review_record(record_id: str, req: ReviewRequest, current_user: dict = require_auth()):
    """审核发布记录：approve 通过 / reject 驳回 / reset 重置为草稿。"""
    if req.action not in ("approve", "reject", "reset"):
        raise HTTPException(400, "action 必须为 approve/reject/reset")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    status_map = {"approve": "approved", "reject": "rejected", "reset": "draft"}
    conn = get_db()
    _ensure_publish_columns(conn)
    row = conn.execute("SELECT * FROM publish_records WHERE id=?", (record_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "发布记录不存在")
    conn.execute(
        """UPDATE publish_records SET review_status=?, review_note=?, reviewed_by=?
           WHERE id=?""",
        (status_map[req.action], req.note, user, record_id),
    )
    conn.commit()
    conn.close()
    label = {"approve": "已通过", "reject": "已驳回", "reset": "已重置为草稿"}
    return {
        "success": True,
        "record_id": record_id,
        "status": status_map[req.action],
        "message": f"审核{label[req.action]}",
    }


# ══════════════════════════════════════════════════════════════
# 发布数据统计（运营看板）
# ══════════════════════════════════════════════════════════════


@router.get("/stats")
async def publish_stats(current_user: dict = require_auth()):
    """运营看板统计：总量 / 平台分布 / 状态分布 / 近 30 天趋势 / 排期概览。"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS n FROM publish_records").fetchone()["n"]
    success = conn.execute("SELECT COUNT(*) AS n FROM publish_records WHERE status='success'").fetchone()["n"]
    by_platform = {}
    for r in conn.execute("SELECT platform, COUNT(*) AS n FROM publish_records GROUP BY platform").fetchall():
        by_platform[r["platform"]] = r["n"]
    by_status = {}
    for r in conn.execute("SELECT status, COUNT(*) AS n FROM publish_records GROUP BY status").fetchall():
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
        "SELECT COUNT(*) AS n FROM publish_schedules WHERE status='pending' AND scheduled_at < datetime('now')"
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
