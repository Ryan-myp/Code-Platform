"""KB 检索质量测试（能力打造 P0）：多词查询、相关度排序、上下文片段。

现状缺陷（E2E 实锤）：file 型检索仅整串子串匹配（"多词不支持"）、无排序；
db 型 OR LIKE 无打分。目标：token 打分 + 排序 + 兼容旧响应键。
"""

import sqlite3

from fastapi.testclient import TestClient

from main import app


def _client() -> TestClient:
    return TestClient(app)


def _auth(c: TestClient) -> dict:
    r = c.post("/api/auth/register", json={"username": "kb_q_user", "password": "pass1234", "email": "kbq@t.cn"})
    assert r.status_code in (200, 201), r.text
    token = r.json().get("token") or r.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _make_file_kb(c: TestClient, h: dict, tmp_path: str, name="kbq") -> str:
    r = c.post("/api/knowledge-bases", json={"name": name, "type": "file", "path": tmp_path}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_file_kb_multi_word_query(setup_test_db, tmp_path):
    """多词非相邻查询（"智能 工厂"）必须命中，旧实现（整串子串）会 0 命中。"""
    files = {
        "a.md": "智能内容工厂\n支持 AI 视频与数字人\n工厂从文本到视听",
        "b.md": "工厂参观指南\n如何使用工厂功能",
        "c.md": "智能客服机器人",
    }
    for fn, content in files.items():
        (tmp_path / fn).write_text(content, encoding="utf-8")
    c = _client()
    h = _auth(c)
    kb = _make_file_kb(c, h, str(tmp_path))

    r = c.get(f"/api/knowledge-bases/{kb}/search", params={"q": "智能 工厂"}, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["count"] >= 2, j  # a/b/c 三篇都含"智能"或"工厂"
    names = [x["file"] for x in j["hits"]]
    assert "a.md" in names
    # 相关度排序：a（双词+多工厂）应排第一
    assert names[0] == "a.md", names
    for hit in j["hits"]:
        assert hit["score"] > 0 and "matches" in hit


def test_file_kb_single_word_backward_compat(setup_test_db, tmp_path):
    """单词查询行为兼容：命中行包含 matches/match_count。"""
    (tmp_path / "x.txt").write_text("第一行工厂\n第二行工厂\n第三行无", encoding="utf-8")
    c = _client()
    h = _auth(c)
    kb = _make_file_kb(c, h, str(tmp_path))

    r = c.get(f"/api/knowledge-bases/{kb}/search", params={"q": "工厂"}, headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["count"] == 1
    hit = j["hits"][0]
    assert hit["match_count"] == 2
    assert any("第一行" in m for m in hit["matches"])


def test_file_kb_phrase_boost(setup_test_db, tmp_path):
    """完整短语整串出现的行/文件获得加分（phrase boost）。"""
    (tmp_path / "p1.md").write_text("内容工厂 概念说明", encoding="utf-8")  # 整串"内容工厂"
    (tmp_path / "p2.md").write_text("内容生产 工厂介绍", encoding="utf-8")  # 拆开的
    c = _client()
    h = _auth(c)
    kb = _make_file_kb(c, h, str(tmp_path))

    r = c.get(f"/api/knowledge-bases/{kb}/search", params={"q": "内容工厂"}, headers=h)
    j = r.json()
    assert j["count"] >= 1
    assert [x["file"] for x in j["hits"]][0] == "p1.md"


def test_db_kb_scored_ranking(setup_test_db, tmp_path):
    """db 型检索：两词查询按命中词数排序（双命中 > 单命中）。"""
    dbfile = tmp_path / "corp.db"
    conn = sqlite3.connect(dbfile)
    conn.execute("CREATE TABLE docs (id INTEGER PRIMARY KEY, title TEXT, body TEXT)")
    conn.executemany(
        "INSERT INTO docs (title, body) VALUES (?, ?)",
        [("AI工厂", "智能工厂的概览与部署"), ("参观", "工厂的参观指南"), ("客服", "智能客服机器人")],
    )
    conn.commit()
    conn.close()

    c = _client()
    h = _auth(c)
    r = c.post(
        "/api/knowledge-bases",
        json={"name": "kbd", "type": "db", "config": {"engine": "sqlite", "database": str(dbfile), "table": "docs"}},
        headers=h,
    )
    assert r.status_code == 200, r.text
    kb = r.json()["id"]

    r = c.get(f"/api/knowledge-bases/{kb}/search", params={"q": "智能 工厂"}, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["count"] >= 2
    top = j["hits"][0]
    assert top["title"] == "AI工厂" and top.get("score", 0) > 0, j["hits"]


def test_search_empty_query_400(setup_test_db):
    c = _client()
    h = _auth(c)
    kb = _make_file_kb(c, h, "/tmp")
    r = c.get(f"/api/knowledge-bases/{kb}/search", params={"q": "  "}, headers=h)
    assert r.status_code == 400
