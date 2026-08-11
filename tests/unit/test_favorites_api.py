"""v16 收藏 API 增强单测：类型校验 / 随机 ID / 分页 / 用户隔离。

覆盖：
- add_favorite：成功、重复收藏 400、非法类型/空 target 拒绝、ID 唯一
- list_favorites：全量、按类型筛选、分页（limit/offset）、用户隔离
- remove_favorite：成功、他人收藏 404
"""

import asyncio
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def _add(username, fav_type="tool", target_id="t1", label=""):
    from favorites_api import add_favorite
    from favorites_api import FavoriteRequest

    req = FavoriteRequest(fav_type=fav_type, target_id=target_id, label=label)
    return asyncio.run(add_favorite(req, current_user={"user_id": username}))


class TestAddFavorite:
    def test_success_returns_fav_id(self, setup_test_db):
        res = _add("u1", "tool", "t1", "我的工具")
        assert res["id"].startswith("fav_")
        assert res["message"] == "收藏成功"

    def test_duplicate_rejected(self, setup_test_db):
        _add("u1", "tool", "t1")
        with pytest.raises(Exception) as exc:
            _add("u1", "tool", "t1")
        assert "已收藏" in str(exc.value)

    def test_same_target_different_type_ok(self, setup_test_db):
        _add("u1", "tool", "t1")
        _add("u1", "record", "t1")  # 同 target 不同类型允许
        _add("u2", "tool", "t1")  # 不同用户允许

    def test_random_id_unique(self, setup_test_db):
        a = _add("u1", "gallery", "g1")
        b = _add("u1", "gallery", "g2")
        assert a["id"] != b["id"]

    def test_invalid_type_rejected(self, setup_test_db):
        from favorites_api import FavoriteRequest

        with pytest.raises(ValidationError):
            FavoriteRequest(fav_type="hack", target_id="x")

    def test_empty_target_rejected(self, setup_test_db):
        from favorites_api import FavoriteRequest

        with pytest.raises(ValidationError):
            FavoriteRequest(fav_type="tool", target_id="")

    def test_overlong_label_rejected(self, setup_test_db):
        from favorites_api import FavoriteRequest

        with pytest.raises(ValidationError):
            FavoriteRequest(fav_type="tool", target_id="x", label="长" * 101)


class TestListFavorites:
    def test_list_all(self, setup_test_db):
        _add("u1", "tool", "t1")
        _add("u1", "record", "r1")
        _add("u2", "tool", "t9")  # 他人收藏不可见

        from favorites_api import list_favorites

        rows = asyncio.run(list_favorites(fav_type="", limit=100, offset=0, current_user={"user_id": "u1"}))
        assert len(rows) == 2

    def test_filter_by_type(self, setup_test_db):
        _add("u1", "tool", "t1")
        _add("u1", "gallery", "g1")

        from favorites_api import list_favorites

        rows = asyncio.run(list_favorites(fav_type="gallery", limit=100, offset=0, current_user={"user_id": "u1"}))
        assert len(rows) == 1
        assert rows[0]["fav_type"] == "gallery"

    def test_pagination(self, setup_test_db):
        for i in range(5):
            _add("u1", "tool", f"t{i}")

        from favorites_api import list_favorites

        page1 = asyncio.run(list_favorites(fav_type="", limit=2, offset=0, current_user={"user_id": "u1"}))
        page2 = asyncio.run(list_favorites(fav_type="", limit=2, offset=2, current_user={"user_id": "u1"}))
        assert len(page1) == 2
        assert len(page2) == 2
        ids1 = {r["target_id"] for r in page1}
        ids2 = {r["target_id"] for r in page2}
        assert not (ids1 & ids2)  # 分页不重叠

    def test_invalid_type_param_rejected(self, auth_headers):
        """非法 fav_type 由 FastAPI 校验层拒绝（422）。"""
        from fastapi.testclient import TestClient

        from main import app

        client = TestClient(app)
        resp = client.get("/api/favorites", params={"fav_type": "hack"}, headers=auth_headers)
        assert resp.status_code == 422


class TestRemoveFavorite:
    def test_remove_own(self, setup_test_db):
        res = _add("u1", "tool", "t1")

        from favorites_api import remove_favorite

        out = asyncio.run(remove_favorite(res["id"], current_user={"user_id": "u1"}))
        assert out["message"] == "已取消收藏"

    def test_remove_others_404(self, setup_test_db):
        res = _add("u1", "tool", "t1")

        from favorites_api import remove_favorite

        with pytest.raises(Exception) as exc:
            asyncio.run(remove_favorite(res["id"], current_user={"user_id": "u2"}))
        assert "无权" in str(exc.value)
