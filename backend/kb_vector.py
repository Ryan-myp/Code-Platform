"""KB 块向量层（v18 P1：真向量召回，补关键词全 miss 的长尾）。

设计（零新依赖，降级安全）：
- 存储：SQLite 表 kb_chunk_embeddings（chunk_hash 去重；float32 BLOB 向量）
- 回填：显式 POST /api/knowledge-bases/{id}/vector-backfill 触发，信号量并发=2（低并发策略）；
  已有 hash 的块直接复用，不重算
- 召回：query embedding 与存量块向量做 cosine top-k，补进关键词未覆盖的命中
- 降级：无 embedding 配置 / APP_ENV=test / 无存量向量 → 原样返回（行为与 v17 完全一致）
"""

import hashlib
import logging
import math
import os
import struct

logger = logging.getLogger(__name__)

# 低并发策略：批量 embed 每批 32 块、批间串行（不冲击中转站限流）
_EMB_BATCH_LIMIT = 512  # 单次回填最多处理块数（防超大 KB 拖垮请求）


def ensure_embedding_table() -> None:
    """确保块向量表存在（幂等，老库 ALTER 兼容）。"""
    from common.db import get_db

    conn = get_db()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS kb_chunk_embeddings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kb_id TEXT NOT NULL,
            file_name TEXT NOT NULL DEFAULT '',
            chunk_hash TEXT NOT NULL,
            chunk_text TEXT NOT NULL DEFAULT '',
            embedding BLOB NOT NULL,
            model TEXT NOT NULL DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(kb_id, chunk_hash)
        )"""
    )
    conn.commit()
    conn.close()


def _embed(config: tuple[str, str, str], texts: list[str]) -> list[list[float]] | None:
    """调 OpenAI 兼容 /embeddings；任何异常 → None（调用方降级）。"""
    model, key, base = config
    if not key or not base:
        return None
    try:
        import httpx

        resp = httpx.post(
            f"{base.rstrip('/')}/embeddings",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "input": texts},
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        embs = [d["embedding"] for d in data.get("data", [])]
        if len(embs) != len(texts):
            return None
        return embs
    except Exception as e:
        logger.warning(f"kb vector embed failed: {e}")
        return None


# ── query embedding 缓存（v18 B：同 query 短 TTL 内复用，避免每次检索重付 API）──
_QUERY_EMB_CACHE: dict[str, tuple[float, list[float]]] = {}
_QUERY_EMB_TTL = 60.0


def cached_query_embedding(
    config: tuple[str, str, str], query: str, precomputed: list[float] | None = None
) -> list[float] | None:
    """query embedding，带 60s TTL 缓存（键含模型）。缓存命中零 API；失败 → None。

    precomputed：调用方刚付费算出的向量（如 rerank 批量 embed 的 query 段），
    传入即回写缓存供后续 vector_recall 复用，不重复 embed。"""
    import time as _time

    model, key, base = config
    q = (query or "").strip()
    if not q:
        return None
    now = _time.monotonic()
    qh = hashlib.sha1((model + "\n" + q).encode("utf-8")).hexdigest()[:24]
    if precomputed is not None:
        if len(_QUERY_EMB_CACHE) > 128:
            _QUERY_EMB_CACHE.clear()
        _QUERY_EMB_CACHE[qh] = (now, precomputed)
        return precomputed
    if not key or not base:
        return None
    hit = _QUERY_EMB_CACHE.get(qh)
    if hit and now - hit[0] < _QUERY_EMB_TTL:
        return hit[1]
    embs = _embed(config, [q])
    if not embs:
        return None
    if len(_QUERY_EMB_CACHE) > 128:
        _QUERY_EMB_CACHE.clear()
    _QUERY_EMB_CACHE[qh] = (now, embs[0])
    return embs[0]



def _cfg() -> tuple[str, str, str]:
    """embedding 配置（复用 kb_api 的解析：专属 env 优先，继承全局中转站）。"""
    import kb_api

    return kb_api._kb_embedding_config()


def _chunk_text_by_hash(text: str, size: int = 400, overlap: int = 100) -> list[tuple[str, str]]:
    """(hash, 块文本)；与 _kb_search_file 的分块口径一致（400 重叠 100）。"""
    out: list[tuple[str, str]] = []
    step = max(1, size - overlap)
    for i in range(0, max(1, len(text)), step):
        c = text[i : i + size].strip()
        if len(c) < 20:
            continue
        h = hashlib.sha1(c.encode("utf-8")).hexdigest()[:16]
        out.append((h, c[:500]))
    return out


def backfill_kb_chunks(kb_id: str, kb_path: str) -> dict:
    """回填指定 file KB 的块向量（低并发；幂等：已有 hash 跳过）。

    返回 {embedded, skipped, total, enabled}。无 embedding 配置时 enabled=False，
    不报错不写库（诚实降级）。
    """
    ensure_embedding_table()
    config = _cfg()
    if not config[1] or not config[2]:
        return {"embedded": 0, "skipped": 0, "total": 0, "enabled": False}

    # 收集全部块的 (hash, text, file_name)
    import kb_api

    try:
        files: list[str] = []
        if os.path.isfile(kb_path):
            files = [kb_path]
        elif os.path.isdir(kb_path):
            for root, _, fns in os.walk(kb_path):
                for fn in fns:
                    if fn.lower().endswith(kb_api._KB_SEARCH_EXTS):
                        files.append(os.path.join(root, fn))
    except Exception as e:
        logger.warning(f"kb vector backfill walk failed: {e}")
        files = []

    pairs: list[tuple[str, str, str]] = []
    for fp in files:
        try:
            content = kb_api._kb_read_or_extract(fp)
        except Exception:
            continue
        if not content:
            continue
        fname = os.path.basename(fp)
        for h, c in _chunk_text_by_hash(content):
            pairs.append((h, c, fname))
    if not pairs:
        return {"embedded": 0, "skipped": 0, "total": 0, "enabled": True}

    # 已存量的 hash 不重算
    from common.db import get_db

    conn = get_db()
    existing = {
        r["chunk_hash"]
        for r in conn.execute(
            "SELECT chunk_hash FROM kb_chunk_embeddings WHERE kb_id=?", (kb_id,)
        ).fetchall()
    }
    conn.close()
    todo = [p for p in pairs if p[0] not in existing]
    skipped = len(pairs) - len(todo)
    todo = todo[:_EMB_BATCH_LIMIT]

    embedded = 0
    for i in range(0, len(todo), 32):
        batch = todo[i : i + 32]
        vectors = _embed(config, [b[1] for b in batch])
        if vectors is None:
            break  # 无 key/失败 → 停止（不写脏数据）
        c2 = get_db()
        for (h, c, fname), vec in zip(batch, vectors, strict=False):
            c2.execute(
                """INSERT OR IGNORE INTO kb_chunk_embeddings
                   (kb_id, file_name, chunk_hash, chunk_text, embedding, model)
                   VALUES (?,?,?,?,?,?)""",
                (kb_id, fname, h, c, _pack_vec(vec), config[0]),
            )
        c2.commit()
        c2.close()
        embedded += len(batch)
    return {"embedded": embedded, "skipped": skipped, "total": len(pairs), "enabled": True}


def _pack_vec(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _unpack_vec(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


def vector_recall(kb_id: str, query: str, limit: int = 3) -> list[dict]:
    """真向量召回：query embedding × 存量块向量 cosine top-k。

    返回与 file 检索同构的 hits 片段（file/matches/match_count/score）；
    无配置/无存量/失败 → []（调用方原样保留关键词结果，行为不变）。
    """
    if not (query or "").strip():
        return []
    try:
        if os.environ.get("APP_ENV") == "test":
            return []  # 测试环境不触发真实 API
    except Exception:
        pass
    ensure_embedding_table()
    from common.db import get_db

    conn = get_db()
    n = conn.execute("SELECT COUNT(*) AS c FROM kb_chunk_embeddings WHERE kb_id=?", (kb_id,)).fetchone()["c"]
    conn.close()
    if n == 0:
        return []  # 无存量向量（未回填）→ 不调 embed，零额外延迟
    config = _cfg()
    if not config[1] or not config[2]:
        return []
    qv = cached_query_embedding(config, query)  # v18 B：60s TTL 缓存，命中零 API
    if not qv:
        return []

    # v18 B：分批全扫（不再 LIMIT 500 硬顶漏召回；进程内上限 5000 块控成本）
    from common.db import get_db as _gdb

    _BATCH = 500
    _CAP = 5000
    scored: list[tuple[float, dict]] = []
    offset = 0
    while True:
        conn = _gdb()
        rows = conn.execute(
            "SELECT id, file_name, chunk_text, embedding FROM kb_chunk_embeddings WHERE kb_id=? "
            "ORDER BY id LIMIT ? OFFSET ?",
            (kb_id, _BATCH, offset),
        ).fetchall()
        conn.close()
        if not rows:
            break
        for r in rows:
            s = _cos(qv, _unpack_vec(r["embedding"]))
            scored.append((s, dict(r)))
        offset += _BATCH
        if offset >= _CAP or len(rows) < _BATCH:
            break
    if not scored:
        return []
    scored.sort(key=lambda x: -x[0])
    # 按文件聚合（同文件多块取最高分）
    by_file: dict[str, tuple[float, str]] = {}
    for s, r in scored:
        if s <= 0.15:  # 低相关度截断（cosine 语义阈值，避免噪声）
            continue
        if r["file_name"] not in by_file or s > by_file[r["file_name"]][0]:
            by_file[r["file_name"]] = (s, r["chunk_text"])
    out = []
    for fname, (s, c) in sorted(by_file.items(), key=lambda kv: -kv[1][0])[: max(1, limit)]:
        out.append(
            {
                "file": fname,  # 向量表存 file_name（子目录信息不在块内）
                "path": "",
                "matches": [c[:300]],
                "match_count": 1,
                "score": round(s, 3),
                "vector_recall": True,
            }
        )
    return out


def delete_file_chunks(kb_id: str, file_name: str) -> int:
    """删除指定文件的块向量（文件从 KB 目录被删后清理孤儿向量，防召回已不存在的文件）。

    返回删除行数；表不存在/无行 → 0（幂等，不报错）。"""
    ensure_embedding_table()
    from common.db import get_db

    conn = get_db()
    cur = conn.execute(
        "DELETE FROM kb_chunk_embeddings WHERE kb_id=? AND file_name=?", (kb_id, file_name)
    )
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


def delete_kb_chunks(kb_id: str) -> int:
    """KB 删除时清理其全部块向量。返回删除行数。"""
    ensure_embedding_table()
    from common.db import get_db

    conn = get_db()
    cur = conn.execute("DELETE FROM kb_chunk_embeddings WHERE kb_id=?", (kb_id,))
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n


_BG_TASKS: set = set()  # 保持强引用防 GC（与 chat_engine 同模式）


def schedule_backfill(kb_id: str, kb_path: str) -> bool:
    """创建/更新 file 型 KB 后 fire-and-forget 增量回填（v18 C）。

    幂等（已有 hash 不重算）；无 embedding 配置时静默 no-op；
    APP_ENV=test 不触发（防测试误打真实 API）。返回是否已调度。
    """
    import asyncio
    import os

    if os.environ.get("APP_ENV") == "test":
        return False
    if not (kb_path or "").strip():
        return False

    async def _task() -> None:
        try:
            await asyncio.to_thread(backfill_kb_chunks, kb_id, kb_path)
        except Exception as e:
            logger.warning(f"kb vector incremental backfill failed (ignored): {e}")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return False  # 非异步上下文（不应发生，端点均为 async）
    task = loop.create_task(_task())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
    return True


# ── FastAPI 路由：显式回填（低并发、幂等）──
from fastapi import APIRouter, HTTPException

from common.auth import require_auth
from common.db import get_db

router = APIRouter(tags=["知识库向量"])


@router.post("/api/knowledge-bases/{kb_id}/vector-backfill")
def vector_backfill(kb_id: str, current_user: dict = require_auth()):
    """触发 file KB 块向量回填（幂等；无 embedding 配置时返回 enabled=false，不报错）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    if (d.get("type") or "file") != "file":
        raise HTTPException(400, "向量召回仅支持 file 型知识库")
    res = backfill_kb_chunks(kb_id, (d.get("path") or "").strip())
    return {"kb_id": kb_id, **res}
