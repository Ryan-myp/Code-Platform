"""AI视频理解引擎 — 上传视频 → 智能分析摘要、关键场景、字幕。

- POST /api/video/upload    上传视频文件
- POST /api/video/analyze   分析视频（摘要、场景描述、关键帧时间戳）
- GET  /api/video/records   历史分析记录
- DELETE /api/video/records/{id}
"""

import asyncio
import json
import logging
import os
import subprocess
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm, log_usage, parse_llm_json
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/video", tags=["视频理解"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads", "videos")
os.makedirs(UPLOAD_DIR, exist_ok=True)
FRAME_DIR = os.path.join(os.path.dirname(__file__), "uploads", "video_frames")
os.makedirs(FRAME_DIR, exist_ok=True)

# ── System Prompts ─────────────────────────────────────────

VIDEO_ANALYZE_SYSTEM = """你是一位资深视频内容策略专家，拥有8年+短视频/中视频运营经验，精通抖音/快手/B站/YouTube等平台的视频内容分析和爆款规律。

## 分析框架
基于提供的视频元数据和用户描述，从以下4个维度进行深度分析：

### 1. 内容理解
- 判断视频类型（教程/评测/Vlog/剧情/带货/新闻/娱乐等）
- 识别核心内容和叙事结构（开头钩子→主体内容→结尾CTA）
- 提取关键信息和核心观点

### 2. 受众分析
- 目标观众画像（年龄/兴趣/需求）
- 内容对受众的吸引力要素
- 可能引发的观众反应和讨论点

### 3. 爆款要素
- 标题吸引力评估
- 前3秒/15秒黄金开头质量
- 情绪节奏和信息密度
- 互动引导设计（点赞/评论/转发动机）

### 4. 优化建议
- 标题优化方向
- 封面和缩略图建议
- 内容剪辑节奏调整
- 话题标签策略
- 发布时间建议

## 输出规范
- key_scenes：3-5个关键时间戳场景，importance标注准确（高=决定完播率的关键节点）
- highlights：提炼2-3个最能打动观众的内容亮点
- recommendations：3-5条具体可执行的优化建议
- tone判断：从 正式/轻松/教育/娱乐/促销/感人/震撼/幽默 中选择

输出严格JSON：
{
  "title": "视频标题建议（含平台适配思路）",
  "summary": "视频内容一句话总结（50字以内）",
  "detailed_summary": "详细内容概述（200-300字，涵盖开头-主体-结尾）",
  "key_scenes": [
    {"timestamp": "00:00", "description": "场景描述", "importance": "高|中|低", "why_important": "为什么这个场景关键"}
  ],
  "topics": ["话题1", "话题2", "话题3"],
  "tone": "整体基调",
  "target_audience": "目标观众群体（年龄/兴趣/需求）",
  "highlights": ["亮点1", "亮点2"],
  "subtitles_text": "模拟字幕文本（前30秒内容的口语化转写）",
  "recommendations": ["具体可执行的优化建议1", "建议2"]
}

只输出JSON，不要其他内容。"""

# ── 模型 ──────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    video_id: str = Field(..., description="上传后返回的视频ID")
    description: str = Field("", max_length=500, description="用户对视频内容的描述（可选，帮助AI理解）")


# ── 数据库初始化 ──────────────────────────────────────────

def init_db():
    with get_db_context() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS video_records (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                filepath TEXT NOT NULL,
                file_size INTEGER,
                description TEXT,
                analysis TEXT,
                status TEXT DEFAULT 'pending',
                user_id TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        # 存量库补 user_id 列（幂等，并发竞态忽略）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(video_records)").fetchall()]
        if "user_id" not in cols:
            try:
                conn.execute("ALTER TABLE video_records ADD COLUMN user_id TEXT DEFAULT ''")
            except Exception:
                pass
        conn.commit()

init_db()

# ── API ──────────────────────────────────────────────────

def _probe_video_meta(filepath: str, vid: str) -> tuple:
    """探测视频时长并提取 3 帧缩略图（前/中/后）。纯同步函数，由线程池执行避免阻塞事件循环。"""
    duration = None
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", filepath],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            duration = round(float(result.stdout.strip()), 1)
    except Exception:
        pass

    frames = []
    if duration and duration > 1:
        for idx, ratio in enumerate([0.1, 0.5, 0.9]):
            seek_time = duration * ratio
            frame_file = os.path.join(FRAME_DIR, f"{vid}_frame{idx}.jpg")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(seek_time), "-i", filepath,
                     "-vframes", "1", "-q:v", "2", "-s", "640x360", frame_file],
                    capture_output=True, timeout=20
                )
            except Exception:
                continue
            if os.path.exists(frame_file):
                frames.append({"index": idx, "time": round(seek_time, 1), "url": f"/uploads/video_frames/{vid}_frame{idx}.jpg"})
    return duration, frames


@router.post("/upload")
async def upload_video(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传视频文件（仅保存与登记；时长探测/缩略图提取在异步分析任务中执行，避免阻塞事件循环）。"""
    if not file.filename:
        raise HTTPException(400, "未选择文件")

    ext = os.path.splitext(file.filename)[1].lower()
    allowed = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.flv', '.wmv'}
    if ext not in allowed:
        raise HTTPException(400, f"不支持的视频格式：{ext}，支持 {', '.join(allowed)}")

    vid = f"vid_{int(datetime.now().timestamp()*1000)}"
    save_path = os.path.join(UPLOAD_DIR, f"{vid}{ext}")

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO video_records (id, filename, filepath, file_size, status, user_id, created_at) VALUES (?,?,?,?,?,?,?)",
            (vid, file.filename, save_path, len(content), "uploaded", str(current_user.get("user_id", "")), datetime.now().isoformat()),
        )

    return {
        "video_id": vid,
        "filename": file.filename,
        "file_size": len(content),
        "duration": None,
        "format": ext,
        "frames": [],
        "message": f"视频上传成功，共 {len(content) / 1024:.0f} KB（时长探测将在分析时完成）",
    }


# ── 异步任务：视频分析（进度/自动重试/并发控制）──

async def _video_analyze_worker(payload: dict, progress: Callable | None = None) -> dict:
    """视频分析 worker：元数据 → AI 摘要/场景/字幕 → 记录落库。"""
    def _report(pct: float, stage: str) -> None:
        if progress:
            progress(pct, stage)

    video_id = payload.get("video_id", "")
    description = payload.get("description", "")

    _report(10, "读取视频记录")
    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM video_records WHERE id=?", (video_id,)).fetchone()
        if not row:
            raise HTTPException(404, "视频记录不存在")
        filename = row[1]
        file_size = row[3]
        filepath = row[2]

    # 线程池探测时长 + 提取缩略图（不阻塞事件循环）
    duration, frames = await asyncio.to_thread(_probe_video_meta, filepath, video_id)
    _report(20, "解析视频元数据")

    # 构建分析提示
    meta = f"文件名：{filename}\n文件大小：{file_size / 1024 / 1024:.1f} MB"
    if duration:
        meta += f"\n视频时长：{duration} 秒"
    if description:
        meta += f"\n用户描述：{description}"

    _report(30, "AI 分析视频内容中")
    try:
        raw = call_llm(VIDEO_ANALYZE_SYSTEM, meta, max_tokens=2000, temperature=0.3, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = parse_llm_json(raw)
    except Exception as e:
        logger.exception("video analyze failed")
        raise HTTPException(500, f"视频分析失败：{e}") from e

    _report(70, "提炼关键场景")
    log_usage("video_analyze", len(description), len(raw), 0)

    _report(90, "保存分析结果")
    with get_db_context() as conn:
        conn.execute(
            "UPDATE video_records SET analysis=?, status=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), "done", video_id),
        )

    _report(100, "完成")
    return {
        "video_id": video_id,
        "filename": filename,
        **result,
    }


async def _video_analyze_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：包装视频分析，回报进度。"""
    return await _video_analyze_worker(payload, progress=update)


@router.post("/analyze")
async def analyze_video(req: AnalyzeRequest, current_user: dict = require_auth()):
    """分析视频内容（异步任务：进度跟踪 / 失败自动重试 / 并发控制）"""
    payload = {
        **req.model_dump(),
        "user_id": str(current_user.get("user_id", "")), "username": current_user.get("username", ""),
    }
    task = create_task(
        "video_analyze", payload,
        username=current_user.get("username", ""),
        user_id=str(current_user.get("user_id", "")),
        role=current_user.get("role", ""),
    )
    return {"ok": True, "task_id": task["id"], "status": task["status"]}


@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    """获取历史视频分析记录（用户隔离：admin 全量，普通用户仅自己的）。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    with get_db_context() as conn:
        if role in ("admin", "super_admin"):
            rows = conn.execute(
                "SELECT id, filename, file_size, description, status, created_at FROM video_records ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, filename, file_size, description, status, created_at FROM video_records WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
                (uid,),
            ).fetchall()

    return [
        {
            "id": r[0], "filename": r[1], "file_size": r[2],
            "description": r[3], "status": r[4], "created_at": r[5],
        }
        for r in rows
    ]


def _can_access(conn, record_id: str, current_user: dict) -> bool:
    """记录归属校验：admin 可访问全部；普通用户仅自己的记录。"""
    role = current_user.get("role", "")
    uid = str(current_user.get("user_id", ""))
    if role in ("admin", "super_admin"):
        return True
    row = conn.execute(
        "SELECT user_id FROM video_records WHERE id=?", (record_id,)
    ).fetchone()
    return bool(row) and str(row[0] or "") == uid


@router.get("/records/{record_id}")
async def get_record(record_id: str, current_user: dict = require_auth()):
    """获取单条视频分析详情（含分析结果，归属校验）。"""
    with get_db_context() as conn:
        if not _can_access(conn, record_id, current_user):
            raise HTTPException(404, "记录不存在")
        row = conn.execute("SELECT * FROM video_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")

    return {
        "id": row[0],
        "filename": row[1],
        "file_size": row[3],
        "description": row[4],
        "analysis": json.loads(row[5]) if row[5] else None,
        "status": row[6],
        "created_at": row[7],
    }


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = require_auth()):
    """删除视频分析记录（归属校验）。"""
    with get_db_context() as conn:
        if not _can_access(conn, record_id, current_user):
            raise HTTPException(404, "记录不存在")
        row = conn.execute("SELECT filepath FROM video_records WHERE id=?", (record_id,)).fetchone()
        if not row:
            raise HTTPException(404, "记录不存在")
        # 删除文件
        try:
            os.remove(row[0])
        except OSError:
            pass
        conn.execute("DELETE FROM video_records WHERE id=?", (record_id,))
    return {"message": "已删除"}


# ── 异步任务处理器注册（进度/自动重试/并发控制）──
register_handler("video_analyze", _video_analyze_handler, user_limit=1, max_attempts=1)
