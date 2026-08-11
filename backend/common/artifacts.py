#!/usr/bin/env python3
"""成果仓库公共工具 — artifacts 登记 + 项目版本快照（单一来源）。

- save_artifact: 统一登记 artifacts 表（图片/视频/音频/游戏/小程序等创作产物）
- save_version_snapshot / list_project_versions / get_project_version:
  游戏/小程序项目的可回滚历史版本（project_versions 表）

替代 image_factory / meme_factory / music_factory / video_factory / voice_factory
中各自重复实现的 _save_artifact（相同的 INSERT SQL 与失败静默逻辑）。
"""

import json
import logging
import re
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

_TITLE_MAX = 30


def derive_title(art_type: str, content: dict | str | None = None, metadata: dict | None = None) -> str:
    """从产物登记信息派生展示标题（v13.26 统一命名体系）。

    优先级：metadata.title → metadata.theme → content 的 prompt/topic/text →
    lyrics 歌词首行 → 截断 30 字；无可用信息返回空串（由调用方兜底显示文件名）。
    各工厂 list 接口用同一函数保证展示命名一致，避免用户看到随机时间戳 ID。
    """
    md = metadata or {}
    for key in ("title", "theme"):
        v = str(md.get(key) or "").strip()
        if v:
            return _truncate(v)
    text = ""
    if isinstance(content, dict):
        for key in ("prompt", "topic", "text", "theme", "subject"):
            v = content.get(key)
            if v:
                text = str(v)
                break
    elif isinstance(content, str):
        text = content
    elif content is not None:
        text = str(content)
    text = text.strip().replace("\r", " ")
    if not text:
        return ""
    if art_type == "lyrics":
        first = text.split("\n")[0].strip()
        return _truncate(first) if first else ""
    return _truncate(text)


def _truncate(text: str) -> str:
    """单行化 + 限长 30 字（省略号收尾）。"""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_TITLE_MAX] + ("…" if len(text) > _TITLE_MAX else "")


def save_artifact(
    art_type: str,
    project_id: str = "",
    requirement_id: str = "",
    author: str = "system",
    media_url: str = "",
    content: dict | str | None = None,
    metadata: dict | None = None,
    duration: float | None = None,
    thumbnail: str = "",
) -> str:
    """登记一条成果到 artifacts 表，返回 artifact id。

    - type / media_url / metadata 由各工厂语义决定（image/video/audio/game/miniapp…）
    - thumbnail 存封面/缩略图 URL（发布页素材库直接展示）
    - 失败静默（不影响主流程）
    """
    art_id = f"art_{uuid.uuid4().hex[:12]}"
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            """INSERT INTO artifacts
               (id, project_id, requirement_id, type, content, version, author, created_at, active, media_url, duration, metadata, thumbnail)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, 1, ?, ?, ?, ?)""",
            (
                art_id,
                project_id or "",
                requirement_id or "",
                art_type,
                json.dumps(content if content is not None else {}, ensure_ascii=False),
                author or "system",
                datetime.now().isoformat(),
                media_url or "",
                float(duration or 0),
                json.dumps(metadata or {}, ensure_ascii=False),
                thumbnail or "",
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.debug(f"save_artifact skipped: {e}")
    return art_id


def _next_version_no(conn, project_type: str, project_id: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version_no), 0) AS n FROM project_versions WHERE project_type=? AND project_id=?",
        (project_type, project_id),
    ).fetchone()
    return (row["n"] if row else 0) + 1


def save_version_snapshot(
    project_type: str,
    project_id: str,
    files: dict,
    requirement: str = "",
    note: str = "",
) -> int:
    """保存项目文件快照（版本号自动递增），返回 version_no；失败静默返回 0。

    project_type: 'game' / 'miniapp'；files 为 {path: content} 或 {web: {...}, wx: {...}}。
    """
    try:
        from common.db import get_db

        conn = get_db()
        no = _next_version_no(conn, project_type, project_id)
        conn.execute(
            """INSERT INTO project_versions (project_type, project_id, version_no, files, requirement, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                project_type,
                project_id,
                no,
                json.dumps(files, ensure_ascii=False),
                requirement or "",
                note or "",
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return no
    except Exception as e:
        logger.debug(f"save_version_snapshot skipped: {e}")
        return 0


def list_project_versions(project_type: str, project_id: str) -> list[dict]:
    """版本列表（不含 files 内容，附 file_count），按版本号升序。"""
    from common.db import get_db

    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT version_no, requirement, note, created_at,
                      (SELECT COUNT(*) FROM json_each(pv.files)) AS file_count
               FROM project_versions pv
               WHERE project_type=? AND project_id=?
               ORDER BY version_no ASC""",
            (project_type, project_id),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_project_version(project_type: str, project_id: str, version_no: int) -> dict | None:
    """版本详情（含解析后的 files）。"""
    from common.db import get_db

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM project_versions WHERE project_type=? AND project_id=? AND version_no=?",
            (project_type, project_id, version_no),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["files"] = json.loads(d.get("files") or "{}")
        except Exception:
            d["files"] = {}
        return d
    finally:
        conn.close()
