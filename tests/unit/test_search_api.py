"""v22.1 全局搜索补创作工厂作品单测。

覆盖：
- _search_works：artifacts 表（图片/表情包/视频/歌曲/歌词）类型与路由映射
- game_projects / miniapp_projects 表匹配（名称/需求描述）
- 全局搜索端点：types=works 时返回作品、空关键词空结果、类型过滤
"""

import json
import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1", "role": "user"}


def _insert_artifact(conn, art_id: str, atype: str, author: str, prompt: str = "", title: str = ""):
    meta = {"filename": f"{art_id}.png"}
    if prompt:
        meta["prompt"] = prompt
    if title:
        meta["title"] = title
    conn.execute(
        "INSERT INTO artifacts (id, type, author, content, media_url, metadata, created_at, active) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (
            art_id,
            atype,
            author,
            json.dumps({"prompt": prompt}),
            f"/api/x/{art_id}",
            json.dumps(meta),
            "2026-01-01T09:00:00",
        ),
    )


class TestSearchWorks:
    def test_artifact_types_mapping(self, setup_test_db):
        """artifacts 表 5 类作品：type/path/module 映射正确，标题优先取 metadata.title。"""
        from common.db import get_db
        from search_api import _search_works

        conn = get_db()
        _insert_artifact(conn, "a1", "image", "image_factory", prompt="夕阳下的城市剪影", title="城市剪影")
        _insert_artifact(conn, "a2", "video", "video_factory", prompt="无人机航拍海岸线")
        _insert_artifact(conn, "a3", "audio", "music_factory", prompt="轻快电子节奏")
        _insert_artifact(conn, "a4", "lyrics", "music_factory", prompt="午夜的星光")
        _insert_artifact(conn, "a5", "image", "meme_factory", prompt="搞笑猫表情")
        conn.commit()

        items = _search_works(conn, "%城市%", 10)
        assert len(items) == 1
        assert items[0]["type"] == "image"
        assert items[0]["path"] == "/image-factory"
        assert items[0]["module"] == "图片作品"
        assert items[0]["title"] == "城市剪影"  # metadata.title 优先

        by_type = {i["type"]: i for i in _search_works(conn, "%轻快%", 10)}
        assert by_type["audio"]["path"] == "/music-factory"
        assert by_type["audio"]["module"] == "歌曲作品"

        meme = _search_works(conn, "%搞笑%", 10)
        assert meme and meme[0]["type"] == "meme"
        assert meme[0]["path"] == "/meme"
        assert meme[0]["module"] == "表情包"

        video = _search_works(conn, "%海岸%", 10)
        assert video and video[0]["type"] == "video" and video[0]["path"] == "/video-factory"

        lyrics = _search_works(conn, "%星光%", 10)
        assert lyrics and lyrics[0]["type"] == "lyrics" and lyrics[0]["module"] == "歌词作品"

        conn.close()

    def test_title_fallback_to_prompt(self, setup_test_db):
        """无 metadata.title 时回退 prompt 前 24 字，避免裸 ID 展示。"""
        from common.db import get_db
        from search_api import _search_works

        conn = get_db()
        _insert_artifact(conn, "b1", "video", "video_factory", prompt="一段长达三十字的视频画面描述")
        conn.commit()
        items = _search_works(conn, "%视频画面%", 10)
        assert items and items[0]["title"].startswith("一段长达三十字")
        conn.close()

    def test_game_and_miniapp_tables(self, setup_test_db):
        """game_projects / miniapp_projects 名称与需求描述匹配。"""
        from common.db import get_db
        from search_api import _search_works

        conn = get_db()
        conn.execute(
            "INSERT INTO game_projects (id, name, requirement, created_at) VALUES ('g1','贪吃蛇','一个贪吃蛇小游戏','2026-01-01T09:00:00')"
        )
        conn.execute(
            "INSERT INTO miniapp_projects (id, name, requirement, created_at) VALUES ('m1','打卡助手','每日打卡提醒小程序','2026-01-01T09:00:00')"
        )
        conn.commit()

        games = _search_works(conn, "%贪吃%", 10)
        assert games and games[0]["type"] == "game"
        assert games[0]["path"] == "/games" and games[0]["module"] == "小游戏"
        assert games[0]["title"] == "贪吃蛇"

        apps = _search_works(conn, "%打卡%", 10)
        assert apps and apps[0]["type"] == "miniapp"
        assert apps[0]["path"] == "/miniapp" and apps[0]["module"] == "小程序"

        conn.close()

    def test_no_match_returns_empty(self, setup_test_db):
        """无匹配关键词返回空列表，不抛异常。"""
        from common.db import get_db
        from search_api import _search_works

        conn = get_db()
        assert _search_works(conn, "%不存在的关键词xyz%", 10) == []
        conn.close()

    def test_limit_applied(self, setup_test_db):
        """结果数量受 limit 约束。"""
        from common.db import get_db
        from search_api import _search_works

        conn = get_db()
        for i in range(5):
            _insert_artifact(conn, f"c{i}", "image", "image_factory", prompt=f"风景图第{i}号")
        conn.commit()
        items = _search_works(conn, "%风景图%", 2)
        assert len(items) == 2
        conn.close()


class TestGlobalSearchEndpoint:
    def test_works_type_returns_artifacts(self, setup_test_db):
        """types=works：端点返回作品结果并带 module/path。"""
        from common.db import get_db
        from search_api import global_search

        conn = get_db()
        _insert_artifact(conn, "d1", "audio", "music_factory", prompt="安静的钢琴曲")
        conn.commit()
        conn.close()

        res = global_search({"query": "钢琴", "types": ["works"], "limit": 5}, current_user=USER)
        assert res["total"] == 1
        assert res["results"][0]["type"] == "audio"
        assert res["results"][0]["module"] == "歌曲作品"

    def test_works_excluded_when_not_requested(self, setup_test_db):
        """types 不含 works：不返回作品结果（不影响其他类型）。"""
        from common.db import get_db
        from search_api import global_search

        conn = get_db()
        _insert_artifact(conn, "d2", "video", "video_factory", prompt="海边的日出")
        conn.commit()
        conn.close()

        res = global_search({"query": "日出", "types": ["requirements"], "limit": 5}, current_user=USER)
        assert res["total"] == 0

    def test_empty_query_returns_empty(self, setup_test_db):
        from search_api import global_search

        res = global_search({"query": "  ", "types": ["works"], "limit": 5}, current_user=USER)
        # query 会被 strip，空白查询返回空结果
        assert res == {"results": [], "total": 0, "query": ""}
