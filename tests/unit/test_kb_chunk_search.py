"""KB file 型检索分块化（P1a）：行级匹配 → 400 字符重叠块匹配。

锁定行为：
- 多行相关段落作为一个块命中（旧行级实现只取孤行，上下文丢失）
- 块级打分（token 命中集 + 短语奖励 + 块头早期奖励，不再按词频堆分）
- 响应键向后兼容（file/path/matches/match_count/score，前端与 /search API 不变）
"""


def test_chunk_search_hit_multiline_block(setup_test_db, tmp_path):
    """多行答案块：查询应命中包含完整流程的块（含多行），而非孤行。"""
    from kb_api import _kb_search_file

    (tmp_path / "deploy.md").write_text(
        "# 部署\n旧章节噪音很多行\n\n"
        "部署流程：先构建镜像，再跑测试，最后经 CI 门禁发布生产\n"
        "构建使用 Dockerfile 与私有仓库\n"
        "测试执行 pytest 全量回归\n"
        "CI 门禁运行 code-quality-guard 检查\n"
        "发布采用蓝绿切换策略\n\n"
        "更多无关章节内容占位",
        encoding="utf-8",
    )
    kb_row = {"type": "file", "path": str(tmp_path), "name": "n", "id": "k", "config": "{}"}
    res = _kb_search_file(kb_row, "部署流程", 5)
    assert res["count"] >= 1
    best = res["hits"][0]
    assert "deploy.md" == best["file"]
    assert "部署流程" in best["matches"][0]
    # 分块核心收益：命中块包含后续行（旧行级实现只有 "部署流程：…" 单行）
    assert "蓝绿" in best["matches"][0], "整段流程应同块命中"


def test_chunk_search_ranking_strong_over_weak(setup_test_db, tmp_path):
    """词全命中且靠前的块 > 只命中单词的块。"""
    from kb_api import _kb_search_file

    (tmp_path / "strong.md").write_text(
        "\n".join("填充行" for _ in range(8)) + "\n监控告警方案：告警阈值联动自动扩容",
        encoding="utf-8",
    )
    (tmp_path / "weak.md").write_text("监控看板使用说明\n" + "噪音" * 200, encoding="utf-8")

    kb_row = {"type": "file", "path": str(tmp_path), "name": "n", "id": "k", "config": "{}"}
    res = _kb_search_file(kb_row, "告警阈值自动扩容", 5)
    assert res["hits"][0]["file"] == "strong.md"
    assert "告警阈值联动自动扩容" in res["hits"][0]["matches"][0]


def test_chunk_search_response_shape_compat(setup_test_db, tmp_path):
    """响应键与旧版一致（/api/knowledge-bases/{id}/search 消费方不破坏）。"""
    from kb_api import _kb_search_file

    (tmp_path / "x.md").write_text("向量数据库选型：PG 或 Milvus", encoding="utf-8")
    kb_row = {"type": "file", "path": str(tmp_path), "name": "n", "id": "k", "config": "{}"}
    res = _kb_search_file(kb_row, "向量数据库", 5)
    for h in res["hits"]:
        assert set(h.keys()) == {"file", "path", "matches", "match_count", "score"}, "响应键应保持兼容"
