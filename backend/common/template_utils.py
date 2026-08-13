"""模板工具函数 — 统一各模板文件（drama/mindmap/voice/music_scene/meme）重复逻辑。

5 个模板文件此前各自复制了 _load_all / _load_one / _get_usage / record_usage，
仅表名与 404 消息不同，现收敛为参数化公共函数。
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def load_all(template_dir: Path | str) -> list[dict]:
    """加载目录下全部 JSON 模板。"""
    items = []
    for f in sorted(os.listdir(template_dir)):
        if not f.endswith(".json"):
            continue
        try:
            with open(Path(template_dir) / f, encoding="utf-8") as fh:
                items.append(json.load(fh))
        except Exception:  # noqa: BLE001
            continue
    return items


def load_one(template_dir: Path | str, tid: str, not_found_msg: str = "模板不存在") -> dict:
    """按 id 加载单个 JSON 模板，不存在抛 404。"""
    path = Path(template_dir) / f"{tid}.json"
    if not path.exists():
        raise HTTPException(404, not_found_msg)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_usage(tid: str, table: str) -> int:
    """查询模板热度计数。"""
    try:
        from common.db import get_db

        conn = get_db()
        row = conn.execute(
            f"SELECT usage_count FROM {table} WHERE template_id=?", (tid,)
        ).fetchone()
        conn.close()
        return int(row["usage_count"]) if row else 0
    except Exception:  # noqa: BLE001
        return 0


def record_usage(tid: str, table: str) -> None:
    """记录模板热度（生成时调用，失败静默）。"""
    try:
        from common.db import get_db

        conn = get_db()
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} "
            "(template_id TEXT PRIMARY KEY, usage_count INTEGER DEFAULT 0)"
        )
        conn.execute(
            f"INSERT INTO {table}(template_id, usage_count) VALUES(?,1) "
            "ON CONFLICT(template_id) DO UPDATE SET usage_count=usage_count+1",
            (tid,),
        )
        conn.commit()
        conn.close()
    except Exception:  # noqa: BLE001
        pass
