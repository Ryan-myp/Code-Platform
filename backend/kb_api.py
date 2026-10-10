"""知识库（KB）管理 API — 从 main.py 拆出的独立路由模块。"""

import json
import os
import re
import sqlite3
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from common.auth import require_auth
from common.db import get_db
from common.models import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest

router = APIRouter()


# ── 知识库管理 ──────────────────────────────────────────────────
def _mask_kb_config(cfg: dict) -> dict:
    """脱敏知识库连接配置（password 掩码）。"""
    cfg = dict(cfg or {})
    if cfg.get("password"):
        cfg["password"] = "••••••"
    return cfg


def _kb_connect_sqlite(cfg: dict):
    """SQLite 连接。"""
    path = (cfg.get("database") or "").strip()
    if not path:
        return None, None, "未配置数据库文件路径"
    if not os.path.exists(path):
        return None, None, f"数据库文件不存在：{path}"
    conn = sqlite3.connect(path, timeout=5)
    return conn, conn.cursor(), None


def _kb_connect_mysql(cfg: dict):
    """MySQL 连接。"""
    try:
        import pymysql
    except ImportError:
        return None, None, "未安装 pymysql 驱动（pip install pymysql）"
    conn = pymysql.connect(
        host=cfg.get("host") or "localhost",
        port=int(cfg.get("port") or 3306),
        user=cfg.get("user") or "",
        password=cfg.get("password") or "",
        database=cfg.get("database") or "",
        charset="utf8mb4",
        connect_timeout=5,
    )
    return conn, conn.cursor(), None


def _kb_connect_postgres(cfg: dict):
    """PostgreSQL 连接。"""
    try:
        import psycopg2
    except ImportError:
        return None, None, "未安装 psycopg2 驱动（pip install psycopg2-binary）"
    conn = psycopg2.connect(
        host=cfg.get("host") or "localhost",
        port=int(cfg.get("port") or 5432),
        user=cfg.get("user") or "",
        password=cfg.get("password") or "",
        dbname=cfg.get("database") or "",
        connect_timeout=5,
    )
    return conn, conn.cursor(), None


def _kb_connect(cfg: dict):
    """建立数据库连接，返回 (conn, cursor, error)。支持 sqlite / mysql / postgres。"""
    engine = (cfg.get("engine") or "sqlite").lower()
    try:
        if engine == "sqlite":
            return _kb_connect_sqlite(cfg)
        if engine == "mysql":
            return _kb_connect_mysql(cfg)
        if engine == "postgres":
            return _kb_connect_postgres(cfg)
        return None, None, f"不支持的数据库引擎：{engine}"
    except Exception as e:
        return None, None, f"连接失败：{e}"


def _kb_list_tables(cursor, engine: str) -> list[str]:
    """列出数据库中的表（最多 50 张）。"""
    try:
        if engine == "sqlite":
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        elif engine == "mysql":
            cursor.execute("SHOW TABLES")
        else:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema=current_schema() ORDER BY table_name"
            )
        return [r[0] for r in cursor.fetchall()][:50]
    except Exception:
        return []


def _kb_file_stats(p: str) -> tuple:
    """统计 file 类型知识库的文档数与大小。"""
    doc_count, total_size = 0, 0
    if os.path.isdir(p):
        for root, _, files in os.walk(p):
            for fn in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, fn))
                    doc_count += 1
                except OSError:
                    pass
    elif os.path.isfile(p):
        try:
            total_size = os.path.getsize(p)
            doc_count = 1
        except OSError:
            pass
    return doc_count, total_size


def _kb_db_stats(cfg: dict) -> tuple:
    """统计 db 类型知识库的行数（表内记录数）。"""
    try:
        db_conn, cursor, _err = _kb_connect(cfg)
        if not db_conn:
            return 0, 0
        try:
            table = (cfg.get("table") or "").strip()
            if table:
                cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
                row = cursor.fetchone()
                return (row[0] if row else 0), 0
        except Exception:
            pass
        finally:
            db_conn.close()
    except Exception:
        pass
    return 0, 0


@router.get("/api/knowledge-bases")
async def list_knowledge_bases(current_user: dict = require_auth()):  # noqa: C901
    """获取所有知识库（连接配置脱敏；file/db 类型附文档统计）"""
    conn = get_db()
    kbs = conn.execute("SELECT * FROM knowledge_bases ORDER BY created_at DESC").fetchall()
    conn.close()
    result = []
    for kb in kbs:
        d = dict(kb)
        try:
            cfg = json.loads(d.get("config") or "{}") or {}
        except (ValueError, TypeError):
            cfg = {}
        d["config"] = _mask_kb_config(cfg)
        kb_type = d.get("type") or "file"
        doc_count, total_size = 0, 0
        if kb_type == "file" and d.get("path"):
            doc_count, total_size = _kb_file_stats(d["path"])
        elif kb_type == "db":
            doc_count, _ = _kb_db_stats(cfg)
        d["doc_count"] = doc_count
        d["total_size"] = total_size
        result.append(d)
    return result


@router.post("/api/knowledge-bases")
async def create_knowledge_base(req: KnowledgeBaseCreateRequest, current_user: dict = require_auth()):
    """创建知识库（file / url / db；db 类型需提供 config 连接配置）"""
    conn = get_db()
    kb_id = f"kb_{int(time.time() * 1000)}"
    conn.execute(
        """INSERT INTO knowledge_bases (id, name, type, path, url, filter, top_k, description, subtype, config, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            kb_id,
            req.name,
            req.type or req.source_type or "file",
            req.path or req.source_path or "",
            req.url,
            json.dumps(req.filter),
            req.top_k,
            req.description or "",
            req.subtype or "general",
            json.dumps(req.config or {}),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"id": kb_id, "name": req.name}


@router.delete("/api/knowledge-bases/{kb_id}")
async def delete_knowledge_base(kb_id: str, current_user: dict = require_auth()):
    """删除知识库"""
    conn = get_db()
    conn.execute("DELETE FROM knowledge_bases WHERE id=?", (kb_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.put("/api/knowledge-bases/{kb_id}")
async def update_knowledge_base(kb_id: str, req: KnowledgeBaseUpdateRequest, current_user: dict = require_auth()):
    """更新知识库（config 传 None = 不变；传 {} = 清空）"""
    conn = get_db()
    updates = []
    vals = []
    if req.name is not None:
        updates.append("name=?")
        vals.append(req.name)
    # type 和 source_type 都映射到数据库的 type 列
    db_type = req.type or req.source_type
    if db_type is not None:
        updates.append("type=?")
        vals.append(db_type)
    # path 和 source_path 都映射到数据库的 path 列
    db_path = req.path or req.source_path
    if db_path is not None:
        updates.append("path=?")
        vals.append(db_path)
    if req.url is not None:
        updates.append("url=?")
        vals.append(req.url)
    if req.top_k is not None:
        updates.append("top_k=?")
        vals.append(req.top_k)
    if req.description is not None:
        updates.append("description=?")
        vals.append(req.description)
    if req.subtype is not None:
        updates.append("subtype=?")
        vals.append(req.subtype)
    if req.config is not None:
        updates.append("config=?")
        vals.append(json.dumps(req.config))
    if not updates:
        raise HTTPException(400, "无更新字段")
    updates.append("created_at=created_at")
    vals.append(kb_id)
    conn.execute(f"UPDATE knowledge_bases SET {', '.join(updates)} WHERE id=?", vals)
    conn.commit()
    conn.close()
    return {"success": True, "id": kb_id}


@router.post("/api/knowledge-bases/test-connection")
async def test_kb_connection(req: dict, current_user: dict = require_auth()):
    """测试知识库连接（无需先保存）：file 检查路径；url 检查可达性；db 测试连接并列出表。"""
    kb_type = (req.get("type") or "file").strip()
    cfg = req.get("config") or {}
    if kb_type == "file":
        p = (req.get("path") or "").strip()
        if not p:
            return {"ok": False, "error": "未配置文件路径"}
        if not os.path.exists(p):
            return {"ok": False, "error": f"路径不存在：{p}"}
        if os.path.isdir(p):
            count = sum(len(files) for _, _, files in os.walk(p))
            return {"ok": True, "detail": f"目录存在，共 {count} 个文件", "doc_count": count}
        return {"ok": True, "detail": f"文件存在（{os.path.getsize(p)} 字节）", "doc_count": 1}
    if kb_type == "url":
        url = (req.get("url") or "").strip()
        if not url:
            return {"ok": False, "error": "未配置 URL"}
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            return {"ok": resp.status_code < 400, "detail": f"HTTP {resp.status_code}", "doc_count": 1}
        except Exception as e:
            return {"ok": False, "error": f"访问失败：{e}"}
    if kb_type == "db":
        db_conn, cursor, err = _kb_connect(cfg)
        if err:
            return {"ok": False, "error": err}
        try:
            tables = _kb_list_tables(cursor, (cfg.get("engine") or "sqlite").lower())
            return {"ok": True, "detail": f"连接成功，共 {len(tables)} 张表", "tables": tables}
        finally:
            db_conn.close()
    return {"ok": False, "error": f"不支持的类型：{kb_type}"}


@router.post("/api/knowledge-bases/{kb_id}/test")
async def test_knowledge_base(kb_id: str, current_user: dict = require_auth()):  # noqa: C901
    """测试知识库：file 检查路径；url 检查可达性；db 测试连接并列出表。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    kb_type = d.get("type") or "file"
    try:
        cfg = json.loads(d.get("config") or "{}") or {}
    except (ValueError, TypeError):
        cfg = {}
    if kb_type == "file":
        p = (d.get("path") or "").strip()
        if not p:
            return {"ok": False, "error": "未配置文件路径"}
        if not os.path.exists(p):
            return {"ok": False, "error": f"路径不存在：{p}"}
        if os.path.isdir(p):
            count = sum(len(files) for _, _, files in os.walk(p))
            return {"ok": True, "detail": f"目录存在，共 {count} 个文件", "doc_count": count}
        return {"ok": True, "detail": f"文件存在（{os.path.getsize(p)} 字节）", "doc_count": 1}
    if kb_type == "url":
        url = (d.get("url") or "").strip()
        if not url:
            return {"ok": False, "error": "未配置 URL"}
        try:
            resp = httpx.get(url, timeout=8, follow_redirects=True)
            return {"ok": resp.status_code < 400, "detail": f"HTTP {resp.status_code}", "doc_count": 1}
        except Exception as e:
            return {"ok": False, "error": f"访问失败：{e}"}
    if kb_type == "db":
        db_conn, cursor, err = _kb_connect(cfg)
        if err:
            return {"ok": False, "error": err}
        try:
            tables = _kb_list_tables(cursor, (cfg.get("engine") or "sqlite").lower())
            return {"ok": True, "detail": f"连接成功，共 {len(tables)} 张表", "tables": tables}
        finally:
            db_conn.close()
    return {"ok": False, "error": f"不支持的类型：{kb_type}"}


def _parse_search_request(kb_id: str, q: str, limit: int) -> dict:
    """解析搜索请求参数。"""
    return {"kb_id": kb_id, "query": q.strip()[:500], "limit": min(limit, 20), "offset": 0}


def _execute_vector_search(params: dict) -> list:
    """执行向量搜索。"""
    # 简化的搜索逻辑
    return []


def _format_search_response(results: list, total: int) -> dict:
    """格式化搜索结果。"""
    return {"results": results, "total": total, "limit": len(results)}


def _prepare_search_context(query_data):
    """准备知识库搜索上下文。"""
    return {
        "query": query_data.get("query", ""),
        "filters": query_data.get("filters", {}),
        "results": [],
        "status": "prepared",
    }


def _execute_search_step(search_type, search_params):
    """执行单步搜索。"""
    return {"type": search_type, "params": search_params, "status": "searched"}


def _finalize_search_results(results):
    """汇总搜索结果。"""
    return {"total_results": len(results), "results": results, "status": "completed"}


def _build_kb_context_simple(context_docs: list) -> str:
    """简化版：构建知识库上下文。"""
    if not context_docs:
        return ""
    return "\n".join([doc.get("content", "") for doc in context_docs[:5]])


def _kb_search_db(cfg: dict, q: str, limit: int) -> dict:
    """知识库 db 类型检索：多词候选集 + 词频打分排序。"""
    db_conn, cursor, err = _kb_connect(cfg)
    if err:
        raise HTTPException(400, "操作失败")
    try:
        engine = (cfg.get("engine") or "sqlite").lower()
        table = (cfg.get("table") or "").strip()
        if not table:
            tables = _kb_list_tables(cursor, engine)
            if not tables:
                raise HTTPException(400, "数据库中无可用表，请在连接配置中选择表")
            table = tables[0]
        cols = _kb_table_columns(cursor, engine, table)
        text_cols = [c for c in cols if c and c.lower() not in ("id", "created_at", "updated_at")]
        if not text_cols:
            text_cols = cols
        tokens, phrases = _kb_tokenize(q)
        place = "?" if engine in ("sqlite",) else "%s"
        # 候选集：任一 token/短语 LIKE 命中（上限 500 行防全表扫描事故）
        terms = [t for t in tokens if not any(p == t or t in p for p in phrases)] + phrases
        if not terms:
            terms = [q]
        cond = " OR ".join(f'"{c}" LIKE {place}' for c in text_cols for _ in terms)
        params = [f"%{t}%" for c in text_cols for t in terms]
        cursor.execute(f'SELECT * FROM "{table}" WHERE {cond} LIMIT 500', params)
        rows = cursor.fetchall()
        scored: list[tuple[float, dict]] = []
        for r in rows:
            item = {}
            for i, c in enumerate(cols):
                if i < len(r):
                    v = r[i]
                    item[c] = str(v)[:300] if v is not None else ""
            blob = " ".join(item.values()).lower()
            s = 0.0
            for t in tokens:
                if t in phrases:
                    continue
                s += blob.count(t)
            for p_ in phrases:
                if p_ in blob:
                    s += len(p_) * 2
            item["score"] = round(s, 2)
            scored.append((s, item))
        scored.sort(key=lambda x: -x[0])
        hits = [h for _, h in scored[:limit]]
        return {"ok": True, "hits": hits, "count": len(hits), "table": table}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, "服务异常，请稍后重试") from e
    finally:
        try:
            db_conn.close()
        except Exception:
            pass


def _kb_table_columns(cursor, engine: str, table: str) -> list:
    """获取表的所有列名（按引擎方言）。"""
    if engine == "sqlite":
        cursor.execute(f'PRAGMA table_info("{table}")')
        return [r[1] for r in cursor.fetchall()]
    if engine == "mysql":
        cursor.execute(f"SHOW COLUMNS FROM `{table}`")
        return [r[0] for r in cursor.fetchall()]
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s", (table,))
    return [r[0] for r in cursor.fetchall()]


def _kb_tokenize(q: str) -> tuple[list[str], list[str]]:
    """多词拆分：ASCII 词 + CJK 连续串（整串加权）+ CJK 二元组。

    返回 (tokens, phrase_tokens)：phrase_tokens 整串出现时获得加分。
    """
    import re

    s = (q or "").strip().lower()
    tokens: list[str] = re.findall(r"[a-z0-9]+", s)
    phrases: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", s):
        if len(run) == 1:
            tokens.append(run)
        else:
            phrases.append(run)
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    tokens.extend(re.findall(r"[a-z0-9]+", s))  # 去重后在下方处理
    seen: set[str] = set()
    uniq: list[str] = []
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    if not uniq and s:
        uniq = [s]
    return uniq, phrases


def _kb_line_score(line: str, tokens: list[str], phrases: list[str]) -> float:
    """单行相关度：词频 × 词权重；整串短语命中双倍加分。"""
    lf = line.lower()
    score = 0.0
    for t in tokens:
        if t in phrases:
            continue  # 短语单独计，避免与二元组重复
        n = lf.count(t)
        if n:
            score += n
    for p in phrases:
        if p in lf:
            score += len(p) * 2  # phrase boost
    return score


def _kb_search_file(d: dict, q: str, limit: int) -> dict:
    """知识库 file 类型检索：目录扫描 + 多词打分排序 + 上下文行。"""
    p = (d.get("path") or "").strip()
    if not p or not os.path.exists(p):
        raise HTTPException(400, "文件路径不存在")
    files = [p] if os.path.isfile(p) else []
    if not files:
        for root, _, fns in os.walk(p):
            for fn in fns:
                if fn.lower().endswith((".txt", ".md", ".csv", ".log")):
                    files.append(os.path.join(root, fn))
    tokens, phrases = _kb_tokenize(q)
    scored: list[tuple[float, dict]] = []
    for fp in files:
        try:
            with open(fp, encoding="utf-8", errors="ignore") as f:
                content = f.read(200000)
        except OSError:
            continue
        lines = content.splitlines()
        line_scores = [(_kb_line_score(ln, tokens, phrases), i) for i, ln in enumerate(lines)]
        matched = [(s, i, lines[i].strip()) for s, i in line_scores if s > 0]
        if not matched:
            continue
        matched.sort(key=lambda x: (-x[0], x[1]))
        top5 = matched[:5]
        # 文件分：top 行分之和 + 早期命中微加分（同一文件内靠前的内容更可能是主旨）
        f_score = sum(s for s, _, _ in top5) + (1.0 if top5[0][1] < 5 else 0.0)
        hits_item = {
            "file": os.path.basename(fp),
            "path": fp,
            "matches": [m[2] for m in top5],
            "match_count": len(matched),
            "score": round(f_score, 2),
        }
        scored.append((f_score, hits_item))
    scored.sort(key=lambda x: -x[0])
    hits = [h for _, h in scored[:limit]]
    return {"ok": True, "hits": hits, "count": len(hits)}


@router.get("/api/knowledge-bases/{kb_id}/search")
def search_knowledge_base(kb_id: str, q: str = "", limit: int = 5, current_user: dict = require_auth()):  # noqa: C901
    """在知识库中检索：db 按配置的表对文本列 LIKE 匹配；file 扫描目录内文本文件。"""
    q = (q or "").strip()
    if not q:
        raise HTTPException(400, "检索关键词不能为空")
    limit = max(1, min(limit or 5, 20))
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    kb_type = d.get("type") or "file"
    try:
        cfg = json.loads(d.get("config") or "{}") or {}
    except (ValueError, TypeError):
        cfg = {}
    if kb_type == "db":
        return _kb_search_db(cfg, q, limit)
    if kb_type == "file":
        return _kb_search_file(d, q, limit)
    raise HTTPException(400, "该类型知识库暂不支持内容检索（db / file 支持）")


# ── 知识库文档管理（上传 / 列表 / 删除）─────────────────────
_KB_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "kb")
_KB_ALLOWED_EXT = {
    ".txt",
    ".md",
    ".csv",
    ".log",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
}
_KB_MAX_UPLOAD = 20 * 1024 * 1024  # 20MB


def _safe_kb_filename(filename: str) -> str:
    """清洗上传文件名：去除路径与非法字符，保留可读名称。"""
    name = os.path.basename((filename or "").replace("\\", "/"))
    name = re.sub(r"[^\w\u4e00-\u9fa5.\-]", "_", name)
    return name[:120] or f"doc_{int(time.time() * 1000)}"


@router.post("/api/knowledge-bases/upload")
async def upload_kb_document(file: UploadFile = File(...), current_user: dict = require_auth()):
    """上传知识库文档：保存到 uploads/kb/，返回可用于创建 file 类型知识库的路径。"""
    os.makedirs(_KB_UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _KB_ALLOWED_EXT:
        raise HTTPException(
            400, f"不支持的文件类型：{ext or '(无扩展名)'}（支持 {', '.join(sorted(_KB_ALLOWED_EXT))}）"
        )
    content = await file.read()
    if len(content) > _KB_MAX_UPLOAD:
        raise HTTPException(400, "文件过大，单个文件不能超过 20MB")
    if not content:
        raise HTTPException(400, "文件内容为空")
    # 保留原始名 + 短随机前缀，避免重名覆盖
    safe_name = _safe_kb_filename(file.filename)
    stored = f"{int(time.time() * 1000)}_{safe_name}"
    dest = os.path.join(_KB_UPLOAD_DIR, stored)
    with open(dest, "wb") as f:
        f.write(content)
    return {
        "path": dest,
        "filename": safe_name,
        "size": len(content),
        "detail": f"已上传 {safe_name}（{len(content) / 1024:.1f} KB），可直接用于创建知识库",
    }


@router.get("/api/knowledge-bases/{kb_id}/documents")
def _kb_docs_file(p: str) -> list:
    """file 类型知识库文档列表（目录扫描或单文件）。"""
    docs = []
    if p and os.path.isdir(p):
        for fn in sorted(os.listdir(p)):
            fp = os.path.join(p, fn)
            if os.path.isfile(fp):
                try:
                    docs.append(
                        {
                            "name": fn,
                            "path": fp,
                            "size": os.path.getsize(fp),
                            "mtime": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                        }
                    )
                except OSError:
                    continue
    elif p and os.path.isfile(p):
        try:
            docs.append(
                {
                    "name": os.path.basename(p),
                    "path": p,
                    "size": os.path.getsize(p),
                    "mtime": datetime.fromtimestamp(os.path.getmtime(p)).isoformat(),
                }
            )
        except OSError:
            pass
    return docs


def _kb_docs_db(d: dict) -> list:
    """db 类型知识库文档列表（表信息）。"""
    try:
        cfg = json.loads(d.get("config") or "{}") or {}
        db_conn, cursor, err = _kb_connect(cfg)
        if db_conn and not err:
            try:
                tables = _kb_list_tables(cursor, (cfg.get("engine") or "sqlite").lower())
                return [{"name": t, "path": t, "size": 0, "mtime": "", "is_table": True} for t in tables]
            finally:
                db_conn.close()
    except Exception:
        pass
    return []


async def list_kb_documents(kb_id: str, current_user: dict = require_auth()):  # noqa: C901
    """列出知识库文档：file 类型扫描目录/文件；db 类型返回表信息；url 返回空。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    kb_type = d.get("type") or "file"
    docs = []
    if kb_type == "file":
        docs = _kb_docs_file((d.get("path") or "").strip())
    elif kb_type == "db":
        docs = _kb_docs_db(d)
    return {"type": kb_type, "docs": docs, "count": len(docs)}


@router.delete("/api/knowledge-bases/{kb_id}/documents")
async def delete_kb_document(kb_id: str, filename: str = "", current_user: dict = require_auth()):
    """删除知识库中的文档（仅限该知识库路径下的文件，防目录穿越）。"""
    if not filename:
        raise HTTPException(400, "请指定要删除的文件名")
    conn = get_db()
    row = conn.execute("SELECT * FROM knowledge_bases WHERE id=?", (kb_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "知识库不存在")
    d = dict(row)
    if (d.get("type") or "file") != "file":
        raise HTTPException(400, "仅 file 类型知识库支持删除文档")
    base = (d.get("path") or "").strip()
    if not base or not os.path.isdir(base):
        raise HTTPException(400, "知识库目录不存在")
    target = os.path.realpath(os.path.join(base, os.path.basename(filename)))
    base_real = os.path.realpath(base)
    if not target.startswith(base_real + os.sep):
        raise HTTPException(400, "文件名不合法")
    if not os.path.isfile(target):
        raise HTTPException(404, "文件不存在")
    os.remove(target)
    return {"success": True, "filename": os.path.basename(target)}
