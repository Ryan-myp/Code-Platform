"""KB 块向量层（v18 P1）单测：回填幂等 / 召回降级 / 关键词 miss 补召回。"""



def test_backfill_no_config_honest_degrade(setup_test_db, tmp_path, monkeypatch):
    """无 embedding 配置 → enabled=False 不写库不报错（诚实降级；显式钉死 _cfg 防环境泄入真实 key）。"""
    import kb_vector

    monkeypatch.setattr(kb_vector, "_cfg", lambda: ("", "", ""))
    (tmp_path / "a.md").write_text("内容" * 100, encoding="utf-8")
    res = kb_vector.backfill_kb_chunks("kb-v1", str(tmp_path))
    assert res["enabled"] is False
    assert res["embedded"] == 0


def test_backfill_and_idempotent_skip(setup_test_db, tmp_path, monkeypatch):
    """fake embed → 写入块向量；重复回填 skipped 增长、不重算。"""
    import kb_vector

    monkeypatch.setattr(kb_vector, "_cfg", lambda: ("emb-test", "k", "http://x"))

    def fake_embed(config, texts):
        # 确定性假向量：按文本长度取维度 4
        return [[float(len(t) % 7) / 10 + i * 0.1 for i in range(4)] for t in texts]

    monkeypatch.setattr(kb_vector, "_embed", fake_embed)
    (tmp_path / "a.md").write_text("索引重建排期与回滚预案" * 60, encoding="utf-8")

    r1 = kb_vector.backfill_kb_chunks("kb-v2", str(tmp_path))
    assert r1["enabled"] is True
    assert r1["embedded"] > 0
    assert r1["skipped"] == 0

    r2 = kb_vector.backfill_kb_chunks("kb-v2", str(tmp_path))
    assert r2["embedded"] == 0, "已有 hash 的块不重算（幂等）"
    assert r2["skipped"] == r1["embedded"]


def test_vector_recall_skipped_in_test_env(setup_test_db, monkeypatch):
    """APP_ENV=test → 召回直接跳过（不触发真实 API）。"""
    import kb_vector

    monkeypatch.setattr(kb_vector, "_cfg", lambda: ("emb-test", "k", "http://x"))
    monkeypatch.setattr(kb_vector, "_embed", lambda config, texts: [[0.1] * 4])
    assert kb_vector.vector_recall("kb-v3", "查询") == []


def test_vector_recall_cosine_topk(setup_test_db, monkeypatch):
    """直调召回逻辑（绕过 APP_ENV 闸）：cosine 高分块排前。"""
    import kb_vector

    kb_vector.ensure_embedding_table()
    import struct

    from common.db import get_db

    conn = get_db()
    for name, vec in (("a.md", [1.0, 0.0, 0.0, 0.0]), ("b.md", [0.0, 1.0, 0.0, 0.0])):
        blob = struct.pack("4f", *vec)
        conn.execute(
            "INSERT OR REPLACE INTO kb_chunk_embeddings (kb_id, file_name, chunk_hash, chunk_text, embedding, model)"
            " VALUES (?,?,?,?,?,?)",
            ("kb-v4", name, name + "_h", name + " 块文本", blob, "emb-test"),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(kb_vector, "_cfg", lambda: ("emb-test", "k", "http://x"))
    # 假 embed：query 向量与 a.md 同向（cosine≈1），与 b.md 正交（≈0）
    monkeypatch.setattr(kb_vector, "_embed", lambda config, texts: [[1.0, 0.0, 0.0, 0.0]])
    import os

    monkeypatch.delenv("APP_ENV", raising=False)  # 绕过测试闸（仅本函数内）
    try:
        hits = kb_vector.vector_recall("kb-v4", "查询", limit=2)
    finally:
        os.environ["APP_ENV"] = "test"
    assert hits and hits[0]["file"] == "a.md"
    assert hits[0]["vector_recall"] is True


def test_file_search_merges_vector_recall_miss(setup_test_db, tmp_path, monkeypatch):
    """关键词全 miss 的文件经向量召回补进结果（关键词命中文件不重复）。"""
    import kb_api
    import kb_vector

    kb_row = {"id": "kb-v5", "name": "向量库", "type": "file", "path": str(tmp_path), "config": "{}"}
    (tmp_path / "x.md").write_text("关键词命中内容", encoding="utf-8")
    (tmp_path / "y.md").write_text("语义相近但无关键词", encoding="utf-8")

    monkeypatch.setattr(
        kb_vector,
        "vector_recall",
        lambda kb_id, q, limit=3: [
            {"file": "y.md", "path": "", "matches": ["语义相近但无关键词"], "match_count": 1, "score": 0.9, "vector_recall": True}
        ],
    )
    res = kb_api._kb_search_file(kb_row, "关键词命中", 5)
    files = [h["file"] for h in res["hits"]]
    assert "x.md" in files
    assert "y.md" in files, "关键词 miss 的文件应由向量召回补进"
    # 不重复
    assert files.count("y.md") == 1


def test_cached_query_embedding_hits(monkeypatch, setup_test_db):
    """同 query 60s 内第二次零 API；precomputed 可回写缓存。"""
    import kb_vector

    calls = {"n": 0}

    def fake_embed(config, texts):
        calls["n"] += 1
        return [[0.5] * 4 for _ in texts]

    monkeypatch.setattr(kb_vector, "_embed", fake_embed)
    monkeypatch.setattr(kb_vector, "_cfg", lambda: ("m", "k", "http://x"))
    kb_vector._QUERY_EMB_CACHE.clear()
    cfg = ("m", "k", "http://x")

    v1 = kb_vector.cached_query_embedding(cfg, "查询词")
    assert calls["n"] == 1
    v2 = kb_vector.cached_query_embedding(cfg, "查询词")
    assert calls["n"] == 1, "缓存命中不应再调 embed"
    assert v1 == v2
    # precomputed 回写：不同 query 但给现成向量 → 不付费
    kb_vector.cached_query_embedding(cfg, "别的查询", precomputed=[1.0] * 4)
    assert calls["n"] == 1


def test_vector_recall_scans_beyond_500(setup_test_db, monkeypatch):
    """存量向量 >500 条时高分块不再被 LIMIT 500 漏掉（分批全扫）。"""
    import struct

    import kb_vector

    kb_vector.ensure_embedding_table()
    from common.db import get_db

    conn = get_db()
    for i in range(600):
        # 高分向量给第 599 号（旧 LIMIT 500 永远看不到它）
        vec = [1.0, 0.0, 0.0, 0.0] if i == 599 else [0.0, 1.0, 0.0, 0.0]
        blob = struct.pack("4f", *vec)
        conn.execute(
            "INSERT OR REPLACE INTO kb_chunk_embeddings (kb_id, file_name, chunk_hash, chunk_text, embedding, model)"
            " VALUES (?,?,?,?,?,?)",
            ("kb-scan", f"f{i % 10}.md", f"h{i}", f"块{i}", blob, "m"),
        )
    conn.commit()
    conn.close()

    monkeypatch.setattr(kb_vector, "_cfg", lambda: ("m", "k", "http://x"))
    monkeypatch.setattr(kb_vector, "_embed", lambda c, t: [[1.0, 0.0, 0.0, 0.0] for _ in t])
    import os

    monkeypatch.delenv("APP_ENV", raising=False)
    try:
        hits = kb_vector.vector_recall("kb-scan", "查询", limit=1)
    finally:
        os.environ["APP_ENV"] = "test"
    assert hits and hits[0]["file"] == "f9.md", "第 599 块（>500）高分应被全扫找到"
