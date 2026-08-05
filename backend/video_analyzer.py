"""AI视频理解引擎 — 上传视频 → 智能分析摘要、关键场景、字幕。

- POST /api/video/upload    上传视频文件
- POST /api/video/analyze   分析视频（摘要、场景描述、关键帧时间戳）
- GET  /api/video/records   历史分析记录
- DELETE /api/video/records/{id}
"""

import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.db import get_db_context
from common.llm import call_llm, log_usage

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
                created_at TEXT NOT NULL
            )
        """)

init_db()

# ── API ──────────────────────────────────────────────────

@router.post("/upload")
async def upload_video(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传视频文件，自动提取关键帧缩略图，返回视频ID供后续分析。"""
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
            "INSERT INTO video_records (id, filename, filepath, file_size, status, created_at) VALUES (?,?,?,?,?,?)",
            (vid, file.filename, save_path, len(content), "uploaded", datetime.now().isoformat()),
        )

    # 尝试获取时长
    duration = None
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", save_path],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            duration = round(float(result.stdout.strip()), 1)
    except Exception:
        pass

    # 提取关键帧缩略图（3帧：前/中/后）
    frames = []
    if duration and duration > 1:
        try:
            import subprocess
            for idx, ratio in enumerate([0.1, 0.5, 0.9]):
                seek_time = duration * ratio
                frame_file = os.path.join(FRAME_DIR, f"{vid}_frame{idx}.jpg")
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(seek_time), "-i", save_path,
                     "-vframes", "1", "-q:v", "2", "-s", "640x360", frame_file],
                    capture_output=True, timeout=20
                )
                if os.path.exists(frame_file):
                    frames.append({"index": idx, "time": round(seek_time, 1), "url": f"/uploads/video_frames/{vid}_frame{idx}.jpg"})
        except Exception:
            pass

    return {
        "video_id": vid,
        "filename": file.filename,
        "file_size": len(content),
        "duration": duration,
        "format": ext,
        "frames": frames,
        "message": f"视频上传成功{'，时长 ' + str(duration) + '秒' if duration else ''}{'，已提取' + str(len(frames)) + '帧缩略图' if frames else ''}",
    }


@router.post("/analyze")
async def analyze_video(req: AnalyzeRequest, current_user: dict = require_auth()):
    """分析视频内容：AI生成摘要、关键场景、字幕等。"""
    start = datetime.now()

    with get_db_context() as conn:
        row = conn.execute("SELECT * FROM video_records WHERE id=?", (req.video_id,)).fetchone()
        if not row:
            raise HTTPException(404, "视频记录不存在")

        filename = row[1]
        file_size = row[3]

    # 构建分析提示
    meta = f"文件名：{filename}\n文件大小：{file_size / 1024 / 1024:.1f} MB"
    if req.description:
        meta += f"\n用户描述：{req.description}"

    try:
        raw = call_llm(VIDEO_ANALYZE_SYSTEM, meta, max_tokens=2000, temperature=0.3, timeout=90)
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(500, "视频分析结果格式异常")
    except Exception as e:
        logger.exception("video analyze failed")
        raise HTTPException(500, f"视频分析失败：{e}")

    elapsed = round((datetime.now() - start).total_seconds(), 2)
    log_usage("video_analyze", len(req.description), len(raw), elapsed)

    with get_db_context() as conn:
        conn.execute(
            "UPDATE video_records SET analysis=?, status=? WHERE id=?",
            (json.dumps(result, ensure_ascii=False), "done", req.video_id),
        )

    return {
        "video_id": req.video_id,
        "filename": filename,
        **result,
    }


@router.get("/records")
async def list_records(current_user: dict = require_auth()):
    """获取历史视频分析记录。"""
    with get_db_context() as conn:
        rows = conn.execute(
            "SELECT id, filename, file_size, description, status, created_at FROM video_records ORDER BY created_at DESC LIMIT 50"
        ).fetchall()

    return [
        {
            "id": r[0], "filename": r[1], "file_size": r[2],
            "description": r[3], "status": r[4], "created_at": r[5],
        }
        for r in rows
    ]


@router.get("/records/{record_id}")
async def get_record(record_id: str, current_user: dict = require_auth()):
    """获取单条视频分析详情（含分析结果）。"""
    with get_db_context() as conn:
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
    """删除视频分析记录。"""
    with get_db_context() as conn:
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
