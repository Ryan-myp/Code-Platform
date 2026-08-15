"""口播短视频工厂 — 流水线编排层（Phase 1）。

把一个「主题」一键变成 N 条可发布的数字人口播短视频：
  ① 主题 → LLM 生成 N 组变体（标题/口播正文，复用 growth 变体逻辑）
  ② 建「视频项目」统一管理（video_projects + video_project_items）
  ③ 全部文案 → 数字人批量生成（复用 digital-human/batch：TTS→渲染成片）
  ④ 后台线程轮询批量状态，逐条回填 video_url/status
  ⑤ 项目列表/详情/重跑失败项/删除；前端可一键跳发布中心

本地免费版：无次数限制，AI 费用走用户中转站 Key（与各工厂一致）。
"""
import json
import os
import threading
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common.auth import require_auth  # noqa: E402
from common.db import get_db, get_db_context  # noqa: E402
from growth_engine import MetricsUpsertRequest  # noqa: E402

router = APIRouter(prefix="/api/pipeline", tags=["口播短视频流水线"])

MAX_VARIANTS = 10  # 单项目最大变体数（视频渲染耗时，防止一次堆太多）


def _now() -> str:
    return datetime.now().isoformat()


def _ensure_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS video_projects (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            theme TEXT DEFAULT '',
            platform TEXT DEFAULT '',
            variant_count INTEGER DEFAULT 1,
            avatar_id TEXT DEFAULT 'business-female',
            voice_id TEXT DEFAULT 'zh-CN-XiaoxiaoNeural',
            background_id TEXT DEFAULT 'tech',
            scene_id TEXT DEFAULT 'product',
            template_id TEXT DEFAULT '',
            engine TEXT DEFAULT '2d',
            resolution TEXT DEFAULT '720p',
            speed REAL DEFAULT 1.0,
            dh_batch_id TEXT DEFAULT '',
            status TEXT DEFAULT 'running',   -- running/done/partial/failed
            success INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )"""
    )
    _ensure_template_tables(conn)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS video_project_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT DEFAULT '',
            idx INTEGER DEFAULT 0,
            title TEXT DEFAULT '',
            content TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',   -- pending/running/success/failed
            dh_record_id TEXT DEFAULT '',
            video_url TEXT DEFAULT '',
            error TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )"""
    )


class PipelineRunRequest(BaseModel):
    theme: str = Field(..., min_length=2, max_length=200, description="选题/主题")
    platform: str = Field("douyin", description="目标平台（douyin/kuaishou/xiaohongshu/shipinhao/bilibili）")
    count: int = Field(3, ge=1, le=MAX_VARIANTS, description="变体数量（N 条视频）")
    avatar_id: str = Field("business-female", description="数字人形象ID")
    voice_id: str = Field("zh-CN-XiaoxiaoNeural", description="声音ID")
    background_id: str = Field("tech", description="背景ID")
    scene_id: str = Field("product", description="场景模板ID")
    template_id: str = Field("", max_length=40, description="行业模板ID（可选）")
    engine: str = Field("2d", pattern="^(2d|live_portrait|sadtalker)$", description="渲染引擎")
    resolution: str = Field("720p", pattern="^(720p|1080p)$", description="分辨率")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="语速")
    watermark: bool | None = Field(None, description="水印（None=跟随全局）")


class RetryRequest(BaseModel):
    indexes: list[int] = Field(default_factory=list, description="要重跑的 item 下标（空=全部失败项）")


def _generate_variants(theme: str, platform: str, count: int) -> list[dict]:
    """主题 → N 组变体（标题+口播正文）。复用 growth_engine 的变体提示词体系。"""
    from growth_engine import VARIANT_SYSTEM, PLATFORM_LABELS, batch_generate, BatchGenerateRequest
    from common.llm import call_llm
    import json as _json

    platform_name = PLATFORM_LABELS.get(platform, "抖音")
    user_prompt = (
        f"核心主题：{theme}\n"
        f"目标平台：{platform_name}\n"
        f"生成数量：{count} 组\n"
        f"要求：每组输出口播短视频文案，正文需可直接配音（口语化、有钩子、结尾引导互动），"
        f"每组 80-150 字。直接输出 JSON 数组。"
    )
    try:
        raw = call_llm(VARIANT_SYSTEM, user_prompt, max_tokens=4000, temperature=0.85, timeout=120)
        variants = _parse_variant_json(raw)
        if not isinstance(variants, list):
            raise ValueError("LLM 返回的不是数组")
        return [v for v in variants[:count] if (v.get("content") or v.get("text") or "").strip()]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"选题文案生成失败：{e}") from e


def _parse_variant_json(raw: str) -> list:
    """从 LLM 输出中稳健提取 JSON 数组（容忍 ```json 包裹、前后说明文字、尾随逗号等）。"""
    import json as _json
    import re as _re

    text = (raw or "").strip()
    # 1) 去掉 markdown 代码围栏
    m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    # 2) 直接尝试完整解析
    try:
        return _json.loads(text)
    except Exception:
        pass
    # 3) 截取第一个 [ 到最后一个 ]（容忍前后说明文字）
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e > s:
        candidate = text[s : e + 1]
        # 清理尾随逗号（LLM 常见错误）
        candidate = _re.sub(r",\s*([\]}])", r"\1", candidate)
        try:
            return _json.loads(candidate)
        except Exception:
            pass
    # 4) 最后手段：逐行拼出对象数组
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines and not lines[0].startswith("["):
        # 尝试把「每行一个 JSON 对象」拼成数组
        try:
            return [_json.loads(l) for l in lines if l.startswith("{")]
        except Exception:
            pass
    raise ValueError("无法解析 LLM 返回的变体 JSON")


def _run_pipeline(project_id: str, texts: list[str], cfg: dict, uid: str, user: str,
                  target_indexes: list[int] | None = None) -> None:
    """后台线程：提交数字人批量 → 轮询回填项目 items。

    target_indexes: 本次批量对应的项目 item 下标（None=0..n-1，全量首次生成；
    重跑失败项时传原始下标，因为新批次的 index 从 0 重新计数）。
    """
    from digital_human import BatchGenerateRequest, create_batch
    import asyncio

    mapping = target_indexes if target_indexes is not None else list(range(len(texts)))
    try:
        req = BatchGenerateRequest(
            texts=texts,
            avatar_id=cfg["avatar_id"],
            voice_id=cfg["voice_id"],
            background_id=cfg["background_id"],
            scene_id=cfg["scene_id"],
            template_id=cfg.get("template_id", ""),
            speed=cfg.get("speed", 1.0),
            resolution=cfg["resolution"],
            engine=cfg["engine"],
            watermark=cfg.get("watermark"),
        )
        current_user = {"username": user, "user_id": uid}
        batch = asyncio.run(create_batch(req, current_user))
        batch_id = batch["batch_id"]
        with get_db_context() as conn:
            _ensure_tables(conn)
            conn.execute("UPDATE video_projects SET dh_batch_id=? WHERE id=?", (batch_id, project_id))
        # 轮询批量状态，逐条回填（新批次 index → 项目原始下标）
        _poll_batch_into_project(project_id, batch_id, mapping)
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).error(f"pipeline {project_id} failed: {e!r}")
        with get_db_context() as conn:
            _ensure_tables(conn)
            conn.execute(
                "UPDATE video_projects SET status='failed', updated_at=? WHERE id=?",
                (_now(), project_id),
            )
        try:
            with get_db_context() as conn:
                _ensure_tables(conn)
                for i in mapping:
                    conn.execute(
                        "UPDATE video_project_items SET status='failed', error=?, updated_at=? WHERE project_id=? AND idx=?",
                        (str(e)[:300], _now(), project_id, i),
                    )
        except Exception:  # noqa: BLE001
            pass


def _poll_batch_into_project(project_id: str, batch_id: str, mapping: list[int] | None = None) -> None:
    """轮询 digital_human_batch_items，把每条结果回填到 video_project_items。"""
    if mapping is None:
        mapping = list(range(100))  # 兜底：直接按同序映射
    total_target = len(mapping)

    for _ in range(600):  # 最长 30 分钟
        time.sleep(3)
        try:
            task = _load_batch_direct(batch_id)
        except Exception:  # noqa: BLE001
            task = None
        if not task:
            continue
        items = task.get("items") or []
        done = 0
        ok = fail = 0
        with get_db_context() as conn:
            _ensure_tables(conn)
            for it in items:
                st = it.get("status")
                if st not in ("success", "failed", "skipped"):
                    continue
                done += 1
                if st == "success":
                    ok += 1
                else:
                    fail += 1
                # 新批次 index → 项目原始下标
                new_idx = it.get("index")
                if new_idx is None or new_idx >= len(mapping):
                    continue
                proj_idx = mapping[new_idx]
                conn.execute(
                    """UPDATE video_project_items SET status=?, dh_record_id=?,
                       video_url=?, error=?, updated_at=? WHERE project_id=? AND idx=?""",
                    (
                        "success" if st == "success" else "failed",
                        it.get("record_id", ""),
                        it.get("video_url", ""),
                        it.get("error", "")[:300],
                        _now(),
                        project_id,
                        proj_idx,
                    ),
                )
            # 项目整体状态：只看本次目标集合的完成度
            proj_status = "running"
            if done >= total_target:
                proj_status = "done" if ok > 0 and fail == 0 else ("partial" if ok > 0 else "failed")
            conn.execute(
                "UPDATE video_projects SET status=?, success=?, failed=?, updated_at=? WHERE id=?",
                (proj_status, ok, fail, _now(), project_id),
            )
        if done >= total_target:
            return


def _load_batch_direct(batch_id: str) -> dict | None:
    """直接从 DB 读批量任务（避免依赖内存 _BATCH_TASKS 的线程安全）。"""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM digital_human_batches WHERE id=?", (batch_id,)).fetchone()
        if not row:
            return None
        items = conn.execute(
            "SELECT * FROM digital_human_batch_items WHERE batch_id=? ORDER BY idx",
            (batch_id,),
        ).fetchall()
        return {
            "status": row["status"],
            "items": [
                {
                    "index": it["idx"],
                    "status": it["status"],
                    "record_id": it["record_id"],
                    "video_url": it["video_url"],
                    "error": it["error"],
                }
                for it in items
            ],
        }
    finally:
        conn.close()


@router.post("/run")
async def run_pipeline(req: PipelineRunRequest, current_user: dict = require_auth()):
    """一键跑通流水线：选题 → N 组口播文案 → 数字人批量成片 → 项目内跟踪进度。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    theme = req.theme.strip()
    if len(theme) < 2:
        raise HTTPException(400, "请输入选题主题（至少 2 个字）")

    # ① 生成变体文案
    variants = _generate_variants(theme, req.platform, req.count)
    if not variants:
        raise HTTPException(502, "文案生成失败：LLM 未返回有效内容，请重试")
    texts = [(v.get("content") or v.get("text") or "").strip() for v in variants]
    texts = [t for t in texts if t]
    if not texts:
        raise HTTPException(502, "文案生成失败：内容为空，请重试")
    texts = texts[:MAX_VARIANTS]

    # ② 建项目 + items
    project_id = f"vp_{uuid.uuid4().hex[:10]}"
    cfg = {
        "avatar_id": req.avatar_id,
        "voice_id": req.voice_id,
        "background_id": req.background_id,
        "scene_id": req.scene_id,
        "template_id": req.template_id,
        "engine": req.engine,
        "resolution": req.resolution,
        "speed": req.speed,
        "watermark": req.watermark,
    }
    with get_db_context() as conn:
        _ensure_tables(conn)
        conn.execute(
            """INSERT INTO video_projects
               (id, user_id, theme, platform, variant_count, avatar_id, voice_id, background_id,
                scene_id, template_id, engine, resolution, status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'running',?,?)""",
            (
                project_id, user, theme, req.platform, len(texts),
                req.avatar_id, req.voice_id, req.background_id,
                req.scene_id, req.template_id, req.engine, req.resolution,
                _now(), _now(),
            ),
        )
        for i, (v, t) in enumerate(zip(variants, texts)):
            conn.execute(
                """INSERT INTO video_project_items
                   (project_id, idx, title, content, status, created_at, updated_at)
                   VALUES (?,?,?,?,'pending',?,?)""",
                (project_id, i, str(v.get("title", ""))[:200], t, _now(), _now()),
            )

    # ③ 后台线程跑数字人批量 + 回填
    t = threading.Thread(target=_run_pipeline, args=(project_id, texts, cfg, uid, user), daemon=True)
    t.start()

    return {
        "project_id": project_id,
        "status": "running",
        "variant_count": len(texts),
        "message": f"流水线已启动：正在为「{theme}」生成 {len(texts)} 条口播视频，可关闭页面稍后查看",
    }


@router.get("/projects")
async def list_projects(page: int = 1, page_size: int = 20, current_user: dict = require_auth()):
    """视频项目列表（分页，最新在前）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM video_projects WHERE user_id=?", (user,)
        ).fetchone()[0]
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        rows = conn.execute(
            "SELECT * FROM video_projects WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user, page_size, (page - 1) * page_size),
        ).fetchall()
        items_rows = conn.execute(
            "SELECT * FROM video_project_items WHERE project_id IN (SELECT id FROM video_projects WHERE user_id=?)",
            (user,),
        ).fetchall()
        by_proj: dict[str, list] = {}
        for r in items_rows:
            by_proj.setdefault(r["project_id"], []).append(dict(r))
        out = []
        for r in rows:
            d = dict(r)
            d["items"] = by_proj.get(d["id"], [])
            out.append(d)
        return {"total": total, "items": out}
    finally:
        conn.close()


@router.get("/projects/{project_id}")
async def get_project(project_id: str, current_user: dict = require_auth()):
    """项目详情（含每条视频状态/产物地址）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        row = conn.execute(
            "SELECT * FROM video_projects WHERE id=? AND user_id=?", (project_id, user)
        ).fetchone()
        if not row:
            raise HTTPException(404, "项目不存在")
        items = conn.execute(
            "SELECT * FROM video_project_items WHERE project_id=? ORDER BY idx",
            (project_id,),
        ).fetchall()
        return {**dict(row), "items": [dict(i) for i in items]}
    finally:
        conn.close()


@router.post("/projects/{project_id}/retry")
async def retry_project(project_id: str, req: RetryRequest, current_user: dict = require_auth()):
    """重跑失败项：重新生成失败/被跳过的视频。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        proj = conn.execute(
            "SELECT * FROM video_projects WHERE id=? AND user_id=?", (project_id, user)
        ).fetchone()
        if not proj:
            raise HTTPException(404, "项目不存在")
        if proj["status"] == "running":
            raise HTTPException(400, "项目正在生成中，请等待完成后再重试")
        targets = req.indexes or [
            i for i, r in enumerate(
                conn.execute(
                    "SELECT * FROM video_project_items WHERE project_id=? ORDER BY idx",
                    (project_id,),
                ).fetchall()
            )
            if r["status"] != "success"
        ]
        if not targets:
            return {"ok": True, "message": "没有需要重跑的视频"}
        rows = conn.execute(
            "SELECT * FROM video_project_items WHERE project_id=? ORDER BY idx", (project_id,)
        ).fetchall()
        texts = [rows[i]["content"] for i in targets if i < len(rows)]
        cfg = {
            "avatar_id": proj["avatar_id"],
            "voice_id": proj["voice_id"],
            "background_id": proj["background_id"],
            "scene_id": proj["scene_id"],
            "template_id": proj["template_id"],
            "engine": proj["engine"],
            "resolution": proj["resolution"],
            "speed": float(proj["speed"] or 1.0),
            "watermark": None,
        }
        with get_db_context() as conn2:
            _ensure_tables(conn2)
            for i in targets:
                conn2.execute(
                    "UPDATE video_project_items SET status='pending', error='', updated_at=? WHERE project_id=? AND idx=?",
                    (_now(), project_id, i),
                )
            conn2.execute(
                "UPDATE video_projects SET status='running', updated_at=? WHERE id=?",
                (_now(), project_id),
            )
        t = threading.Thread(
            target=_run_pipeline,
            args=(project_id, texts, cfg, uid, user),
            kwargs={"target_indexes": targets},
            daemon=True,
        )
        t.start()
        return {"ok": True, "message": f"已重新提交 {len(targets)} 条视频生成"}
    finally:
        conn.close()


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, current_user: dict = require_auth()):
    """删除项目及其条目（视频文件保留，仅删除项目记录）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        proj = conn.execute(
            "SELECT * FROM video_projects WHERE id=? AND user_id=?", (project_id, user)
        ).fetchone()
        if not proj:
            raise HTTPException(404, "项目不存在")
        conn.execute("DELETE FROM video_project_items WHERE project_id=?", (project_id,))
        conn.execute("DELETE FROM video_projects WHERE id=?", (project_id,))
        conn.commit()
        return {"ok": True, "message": "项目已删除"}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Phase 2：批量矩阵 —— 自动排期发布 + 效果数据 + AI 复盘
# ══════════════════════════════════════════════════════════════

class PipelineScheduleRequest(BaseModel):
    start_at: str = Field("", description="首条发布时间 ISO（空=从现在起 1 小时后）")
    interval_minutes: int = Field(30, ge=5, le=1440, description="相邻两条发布时间间隔（分钟）")
    platforms: list[str] = Field(default_factory=list, description="指定平台（空=沿用项目平台）")
    title_prefix: str = Field("", max_length=40, description="标题前缀（默认用变体标题）")


def _platform_publish_code(platform: str) -> str:
    """流水线平台 → publishing 平台 code。"""
    return {
        "douyin": "douyin", "kuaishou": "kuaishou", "xiaohongshu": "xiaohongshu",
        "shipinhao": "wechat", "bilibili": "bilibili",
    }.get(platform, "douyin")


@router.post("/projects/{project_id}/schedule")
async def schedule_project(project_id: str, req: PipelineScheduleRequest, current_user: dict = require_auth()):
    """批量排期：把项目成功视频按时间间隔批量创建发布排期（矩阵号自动错峰发布）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        proj = conn.execute(
            "SELECT * FROM video_projects WHERE id=? AND user_id=?", (project_id, user)
        ).fetchone()
        if not proj:
            raise HTTPException(404, "项目不存在")
        if proj["status"] == "running":
            raise HTTPException(400, "项目仍在生成中，请等视频全部生成后再排期")
        items = conn.execute(
            "SELECT * FROM video_project_items WHERE project_id=? AND status='success' ORDER BY idx",
            (project_id,),
        ).fetchall()
        if not items:
            raise HTTPException(400, "该项目没有成功生成的视频，无法排期")
        if len(items) > 20:
            items = items[:20]
        # 计算发布时间序列
        from datetime import datetime as _dt, timedelta as _td

        try:
            base = _dt.fromisoformat((req.start_at or "").replace("Z", "+00:00"))
        except Exception:
            base = _dt.now() + _td(hours=1)
        interval = _td(minutes=max(5, min(1440, req.interval_minutes)))
        platform = req.platforms[0] if req.platforms else _platform_publish_code(proj["platform"])
        # 去重已排期（避免重复点击批量创建重复排期）
        existing = {
            r["title"] for r in conn.execute(
                "SELECT title FROM publish_schedules WHERE user_id=? AND content_type='video'",
                (user,),
            ).fetchall()
        }
        created, skipped = [], 0
        for i, it in enumerate(items):
            title = (req.title_prefix + " " if req.title_prefix else "") + (it["title"] or f"口播视频 {i+1}")
            if title in existing:
                skipped += 1
                continue
            sched_id = f"sched_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """INSERT INTO publish_schedules (id, user_id, platform, content_type, title, content,
                   topics, asset_urls, account_id, scheduled_at, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,'pending',?)""",
                (
                    sched_id, user, platform, "video", title,
                    it["content"] or "", "[]",
                    json.dumps([it["video_url"]], ensure_ascii=False), "",
                    (base + i * interval).isoformat(), _now(),
                ),
            )
            created.append({"sched_id": sched_id, "title": title, "scheduled_at": (base + i * interval).isoformat()})
        conn.commit()
        return {
            "ok": True,
            "created": len(created),
            "skipped": skipped,
            "items": created,
            "message": f"已为 {len(created)} 条视频创建排期（间隔 {req.interval_minutes} 分钟）"
            + (f"，{skipped} 条已存在跳过" if skipped else ""),
        }
    finally:
        conn.close()


@router.post("/projects/{project_id}/metrics")
async def upsert_project_metrics(project_id: str, req: MetricsUpsertRequest, current_user: dict = require_auth()):
    """项目效果数据录入：把发布后的播放/点赞/评论等回填到项目，供 AI 复盘。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        proj = conn.execute(
            "SELECT * FROM video_projects WHERE id=? AND user_id=?", (project_id, user)
        ).fetchone()
        if not proj:
            raise HTTPException(404, "项目不存在")
        from growth_engine import _ensure_metrics_columns

        _ensure_metrics_columns(conn)
        # 每条成功视频对应一条 publish_metrics（record_id 用 dh_record_id 关联）
        items = conn.execute(
            "SELECT * FROM video_project_items WHERE project_id=? AND status='success' ORDER BY idx",
            (project_id,),
        ).fetchall()
        saved = 0
        for it in items:
            rid = it["dh_record_id"] or f"vp_{project_id}_{it['idx']}"
            existing = conn.execute(
                "SELECT id FROM publish_metrics WHERE record_id=? ORDER BY created_at DESC LIMIT 1",
                (rid,),
            ).fetchone()
            now = datetime.now().isoformat()
            if existing:
                conn.execute(
                    "UPDATE publish_metrics SET views=?, likes=?, comments=?, shares=?, followers_gained=?, created_at=? WHERE id=?",
                    (req.views, req.likes, req.comments, req.shares, req.followers_gained, now, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO publish_metrics (id, record_id, platform, views, likes, comments, shares,
                       followers_gained, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        f"pm_{uuid.uuid4().hex[:10]}", rid, proj["platform"],
                        req.views, req.likes, req.comments, req.shares, req.followers_gained, now,
                    ),
                )
            saved += 1
        conn.commit()
        return {"ok": True, "saved": saved, "message": f"已为 {saved} 条视频录入效果数据"}
    finally:
        conn.close()


@router.get("/projects/{project_id}/review")
async def review_project(project_id: str, days: int = 30, current_user: dict = require_auth()):
    """项目 AI 复盘：基于该项目视频的聚合效果数据生成运营复盘报告。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_tables(conn)
    try:
        proj = conn.execute(
            "SELECT * FROM video_projects WHERE id=? AND user_id=?", (project_id, user)
        ).fetchone()
        if not proj:
            raise HTTPException(404, "项目不存在")
        items = conn.execute(
            "SELECT * FROM video_project_items WHERE project_id=? AND status='success' ORDER BY idx",
            (project_id,),
        ).fetchall()
        if not items:
            return {"report": "该项目暂无成功视频，无法复盘。", "data_points": 0}
        from growth_engine import _ensure_metrics_columns

        _ensure_metrics_columns(conn)
        data_lines = [f"选题「{proj['theme']}」共 {len(items)} 条口播视频：\n"]
        total_v = total_l = total_f = 0
        for it in items:
            rid = it["dh_record_id"] or f"vp_{project_id}_{it['idx']}"
            m = conn.execute(
                "SELECT views, likes, comments, followers_gained FROM publish_metrics "
                "WHERE record_id=? ORDER BY created_at DESC LIMIT 1",
                (rid,),
            ).fetchone()
            v = m["views"] if m else 0
            lk = m["likes"] if m else 0
            fg = m["followers_gained"] if m else 0
            total_v += v; total_l += lk; total_f += fg
            data_lines.append(
                f"- 《{(it['title'] or '无标题')[:30]}》 播放:{v} 点赞:{lk} 涨粉:{fg}"
            )
        data_lines.append(f"\n汇总：总播放 {total_v}，总点赞 {total_l}，总涨粉 {total_f}")
        if total_v == 0 and total_l == 0:
            return {
                "report": "该项目视频尚未录入效果数据。发布后请到「发布中心」记录数据，或在本页「录入效果」填写播放/点赞/涨粉，即可生成 AI 复盘。",
                "data_points": len(items),
            }
        from common.llm import call_llm

        system = (
            "你是一个短视频矩阵号运营专家。基于以下口播视频矩阵的数据，输出复盘报告："
            "1.整体表现 2.哪条视频数据最好及其原因 3.下一轮迭代建议（选题/标题/口播结构/发布节奏）。"
            "简洁中文，markdown 列表，不要编造没有的数据。"
        )
        try:
            report = call_llm(system, "\n".join(data_lines), max_tokens=1200, temperature=0.6, timeout=90)
        except Exception as e:
            report = f"AI 复盘生成失败（{e}）。以下是原始数据：\n\n" + "\n".join(data_lines)
        return {"report": report, "data_points": len(items), "total_views": total_v, "total_likes": total_l, "total_followers": total_f}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════
# Phase 3：模板资产化 —— 把成功项目配置存为口播模板，一键复用/分享
# ══════════════════════════════════════════════════════════════

class PipelineTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=40, description="模板名称")
    note: str = Field("", max_length=200, description="模板说明（适用场景）")
    theme_pattern: str = Field("", max_length=200, description="主题模式（如：{产品} 的 3 个使用技巧）")
    platform: str = Field("douyin")
    avatar_id: str = Field("business-female")
    voice_id: str = Field("zh-CN-XiaoxiaoNeural")
    background_id: str = Field("tech")
    scene_id: str = Field("product")
    template_id: str = Field("")
    engine: str = Field("2d")
    resolution: str = Field("720p")
    speed: float = Field(1.0, ge=0.5, le=2.0)
    count: int = Field(3, ge=1, le=10)


def _ensure_template_tables(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pipeline_templates (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            name TEXT DEFAULT '',
            note TEXT DEFAULT '',
            theme_pattern TEXT DEFAULT '',
            platform TEXT DEFAULT 'douyin',
            avatar_id TEXT DEFAULT 'business-female',
            voice_id TEXT DEFAULT 'zh-CN-XiaoxiaoNeural',
            background_id TEXT DEFAULT 'tech',
            scene_id TEXT DEFAULT 'product',
            template_id TEXT DEFAULT '',
            engine TEXT DEFAULT '2d',
            resolution TEXT DEFAULT '720p',
            speed REAL DEFAULT 1.0,
            count INTEGER DEFAULT 3,
            source_project_id TEXT DEFAULT '',
            created_at TEXT DEFAULT '',
            updated_at TEXT DEFAULT ''
        )"""
    )


@router.post("/templates")
async def create_pipeline_template(req: PipelineTemplateRequest, current_user: dict = require_auth()):
    """保存口播模板（把一套成功配置沉淀为可复用模板）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_template_tables(conn)
    try:
        tid = f"pt_{uuid.uuid4().hex[:10]}"
        conn.execute(
            """INSERT INTO pipeline_templates (id, user_id, name, note, theme_pattern, platform,
               avatar_id, voice_id, background_id, scene_id, template_id, engine, resolution, speed, count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                tid, user, req.name.strip(), req.note.strip(), req.theme_pattern.strip(),
                req.platform, req.avatar_id, req.voice_id, req.background_id, req.scene_id,
                req.template_id, req.engine, req.resolution, req.speed, req.count, _now(), _now(),
            ),
        )
        conn.commit()
        return {"ok": True, "id": tid, "message": f"模板「{req.name.strip()}」已保存，可在流水线一键复用"}
    finally:
        conn.close()


@router.get("/templates")
async def list_pipeline_templates(current_user: dict = require_auth()):
    """口播模板列表。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_template_tables(conn)
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_templates WHERE user_id=? ORDER BY created_at DESC", (user,)
        ).fetchall()
        return {"templates": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.delete("/templates/{template_id}")
async def delete_pipeline_template(template_id: str, current_user: dict = require_auth()):
    """删除口播模板。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_template_tables(conn)
    try:
        row = conn.execute(
            "SELECT id FROM pipeline_templates WHERE id=? AND user_id=?", (template_id, user)
        ).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        conn.execute("DELETE FROM pipeline_templates WHERE id=?", (template_id,))
        conn.commit()
        return {"ok": True, "message": "模板已删除"}
    finally:
        conn.close()


@router.get("/templates/{template_id}/export")
async def export_pipeline_template(template_id: str, current_user: dict = require_auth()):
    """导出模板 JSON（可分享/导入）。"""
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    conn = get_db()
    _ensure_template_tables(conn)
    try:
        row = conn.execute(
            "SELECT * FROM pipeline_templates WHERE id=? AND user_id=?", (template_id, user)
        ).fetchone()
        if not row:
            raise HTTPException(404, "模板不存在")
        return {"template": {k: row[k] for k in (
            "name", "note", "theme_pattern", "platform", "avatar_id", "voice_id",
            "background_id", "scene_id", "template_id", "engine", "resolution", "speed", "count",
        )}}
    finally:
        conn.close()


@router.post("/templates/import")
async def import_pipeline_template(req: PipelineTemplateRequest, current_user: dict = require_auth()):
    """导入模板 JSON（复用他人分享的模板配置）。"""
    return await create_pipeline_template(req, current_user)
