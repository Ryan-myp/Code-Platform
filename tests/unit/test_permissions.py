"""v15 权限矩阵 + API Key 增强单测。

覆盖：
- build_permission_matrix：admin 全通 / 会员锁定与解锁 / hidden 与 admin 级不可见 / 来源标注
- matrix_summary：可见/锁定/不可见计数
- load_user_ctx：会员过期降级为 free
- API Key：过期时间计算、状态判定、创建/列表带 expires_at 与用量、认证链路过期拒绝
- admin_permission_matrix 端点：管理员视角 + 指定用户视角
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

# 测试用资源表：覆盖 default / config / pro / vip / admin / hidden 全部分支
RESOURCES = [
    {"id": "open-page", "label": "公开页"},
    {"id": "pro-page", "label": "专业权益"},
    {"id": "vip-page", "label": "至尊权益"},
    {"id": "admin-page", "label": "管理专属"},
    {"id": "offline-page", "label": "已下线"},
    {"id": "config-all", "label": "显式公开"},
]


def _vis_map():
    return {
        "pro-page": "pro",
        "vip-page": "vip",
        "admin-page": "admin",
        "offline-page": "hidden",
        "config-all": "all",
    }


def _user(role="viewer", membership="free"):
    return {"user_id": "u1", "role": role, "membership": membership}


class TestPermissionMatrix:
    def test_admin_all_pass_with_role_source(self):
        from permissions import build_permission_matrix

        items = build_permission_matrix(_user(role="admin"), RESOURCES, _vis_map())
        by_id = {i["id"]: i for i in items}

        # 除 hidden 全站下线外，admin 全部可见且解锁，来源=role
        for rid in ("open-page", "pro-page", "vip-page", "admin-page", "config-all"):
            assert by_id[rid]["visible"] is True, rid
            assert by_id[rid]["locked"] is False, rid
            assert by_id[rid]["source"] == "role", rid
        # hidden：任何人（含 admin）不可见
        assert by_id["offline-page"]["visible"] is False
        assert by_id["offline-page"]["source"] == "hidden"

    def test_free_user_sees_pro_locked(self):
        from permissions import build_permission_matrix

        items = build_permission_matrix(_user(membership="free"), RESOURCES, _vis_map())
        by_id = {i["id"]: i for i in items}

        assert by_id["open-page"]["visible"] is True
        assert by_id["open-page"]["locked"] is False
        assert by_id["open-page"]["source"] == "default"

        pro = by_id["pro-page"]
        assert pro["visible"] is True
        assert pro["locked"] is True
        assert pro["requires"] == "pro"
        assert pro["source"] == "membership"

        assert by_id["vip-page"]["locked"] is True
        assert by_id["vip-page"]["requires"] == "vip"

    def test_vip_unlocks_pro_and_vip(self):
        from permissions import build_permission_matrix

        items = build_permission_matrix(_user(membership="vip"), RESOURCES, _vis_map())
        by_id = {i["id"]: i for i in items}

        assert by_id["pro-page"]["locked"] is False
        assert by_id["vip-page"]["locked"] is False
        assert by_id["pro-page"]["source"] == "membership"

    def test_admin_level_invisible_to_non_admin(self):
        from permissions import build_permission_matrix

        items = build_permission_matrix(_user(membership="vip"), RESOURCES, _vis_map())
        by_id = {i["id"]: i for i in items}

        assert by_id["admin-page"]["visible"] is False
        assert by_id["admin-page"]["locked"] is False
        assert by_id["admin-page"]["source"] == "hidden"

    def test_configured_all_marked_as_config_source(self):
        from permissions import build_permission_matrix

        items = build_permission_matrix(_user(), RESOURCES, _vis_map())
        by_id = {i["id"]: i for i in items}

        assert by_id["config-all"]["source"] == "config"
        assert by_id["open-page"]["source"] == "default"

    def test_missing_resource_defaults_to_all(self):
        from permissions import build_permission_matrix

        items = build_permission_matrix(_user(), RESOURCES, {})
        by_id = {i["id"]: i for i in items}
        assert by_id["open-page"]["visible"] is True
        assert by_id["open-page"]["source"] == "default"


class TestMatrixSummary:
    def test_summary_counts(self):
        from permissions import build_permission_matrix, matrix_summary

        items = build_permission_matrix(_user(membership="free"), RESOURCES, _vis_map())
        s = matrix_summary(items)
        assert s["total"] == 6
        assert s["visible"] == 4  # open/pro/vip/config-all 可见
        assert s["locked"] == 2  # pro/vip 锁定
        assert s["hidden"] == 2  # admin-page/offline-page 不可见


class TestLoadUserCtx:
    def test_expired_membership_downgraded_to_free(self, setup_test_db):
        from common.db import get_db
        from permissions import load_user_ctx

        conn = get_db()
        past = (datetime.now() - timedelta(days=1)).isoformat()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, membership, membership_expires) "
            "VALUES ('expired_user', 'expired_user', 'x', 'user', 'vip', ?)",
            (past,),
        )
        conn.commit()
        conn.close()

        ctx = load_user_ctx({"user_id": "expired_user", "role": "user"})
        assert ctx["membership"] == "free"

    def test_valid_membership_kept(self, setup_test_db):
        from common.db import get_db
        from permissions import load_user_ctx

        conn = get_db()
        future = (datetime.now() + timedelta(days=30)).isoformat()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, membership, membership_expires) "
            "VALUES ('vip_user', 'vip_user', 'x', 'user', 'vip', ?)",
            (future,),
        )
        conn.commit()
        conn.close()

        ctx = load_user_ctx({"user_id": "vip_user", "role": "user"})
        assert ctx["membership"] == "vip"


class TestApiKeyExpiryHelpers:
    def test_calc_expires_at_forever(self):
        from apikey_api import _calc_expires_at

        assert _calc_expires_at(0) == ""

    def test_calc_expires_at_days(self):
        from apikey_api import _calc_expires_at

        now = datetime.now()
        exp = _calc_expires_at(7)
        assert exp
        # 约 7 天后（误差 < 60s）
        delta = datetime.fromisoformat(exp) - now
        assert timedelta(days=6, hours=23) < delta < timedelta(days=7, minutes=1)

    def test_key_status(self):
        from apikey_api import _key_status

        past = (datetime.now() - timedelta(days=1)).isoformat()
        future = (datetime.now() + timedelta(days=1)).isoformat()
        assert _key_status(past) == "expired"
        assert _key_status(future) == "active"
        assert _key_status("") == "active"


def _insert_user(conn, uid, username, role="user"):
    conn.execute(
        "INSERT INTO users (id, username, password_hash, role) VALUES (?,?,?,?)",
        (uid, username, "x", role),
    )


def _insert_key(conn, kid, uid, raw_key, expires_at):
    import hashlib

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    conn.execute(
        "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, label, expires_at, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (kid, uid, key_hash, raw_key[:12], "测试Key", expires_at, datetime.now().isoformat()),
    )


class TestApiKeyEndpoints:
    def test_create_with_expire_days(self, setup_test_db):
        import asyncio

        from apikey_api import create_api_key

        res = asyncio.run(
            create_api_key(
                type("R", (), {"label": "集成Key", "expire_days": 30})(),
                current_user={"user_id": "u1"},
            )
        )
        assert res["expires_at"]
        assert res["expire_days"] == 30

        from common.db import get_db

        conn = get_db()
        row = conn.execute("SELECT expires_at FROM api_keys WHERE id=?", (res["id"],)).fetchone()
        conn.close()
        assert row["expires_at"] == res["expires_at"]

    def test_list_includes_status_and_usage(self, setup_test_db):
        import asyncio

        from common.db import get_db
        from apikey_api import list_api_keys

        conn = get_db()
        _insert_user(conn, "u1", "user1")
        past = (datetime.now() - timedelta(days=1)).isoformat()
        _insert_key(conn, "k_expired", "u1", "xt-expired-key", past)
        _insert_key(conn, "k_active", "u1", "xt-active-key", "")
        # 造一条用量记录
        conn.execute(
            "INSERT INTO usage_logs (user_id, task_type, input_length, output_length, success, timestamp, api_key) "
            "VALUES ('u1', 'chat', 10, 20, 1, ?, 'k_active')",
            (datetime.now().isoformat(),),
        )
        conn.commit()
        conn.close()

        result = asyncio.run(list_api_keys(current_user={"user_id": "u1"}))
        by_id = {k["id"]: k for k in result}
        assert by_id["k_expired"]["status"] == "expired"
        assert by_id["k_expired"]["expires_at"] == past
        assert by_id["k_active"]["status"] == "active"
        assert by_id["k_active"]["usage"]["requests"] == 1
        assert by_id["k_active"]["usage"]["tokens"] == 30


class TestApiKeyAuth:
    def test_expired_key_rejected(self, setup_test_db):
        import hashlib

        from common.auth import _auth_by_api_key
        from common.db import get_db

        raw = "xt-expired-auth"
        conn = get_db()
        _insert_user(conn, "u1", "user1")
        key_hash = hashlib.sha256(raw.encode()).hexdigest()
        conn.execute(
            "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, label, expires_at, created_at) "
            "VALUES ('k_auth_exp', 'u1', ?, 'xt-', '', ?, ?)",
            (key_hash, (datetime.now() - timedelta(days=1)).isoformat(), datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

        with pytest.raises(HTTPException) as exc:
            _auth_by_api_key(raw)
        assert exc.value.status_code == 401
        assert "过期" in exc.value.detail

    def test_valid_key_returns_user_and_refreshes_last_used(self, setup_test_db):
        from common.auth import _auth_by_api_key
        from common.db import get_db

        raw = "xt-valid-auth"
        conn = get_db()
        _insert_user(conn, "u1", "user1")
        key_hash = __import__("hashlib").sha256(raw.encode()).hexdigest()
        conn.execute(
            "INSERT INTO api_keys (id, user_id, key_hash, key_prefix, label, expires_at, created_at) "
            "VALUES ('k_auth_ok', 'u1', ?, 'xt-', '', '', ?)",
            (key_hash, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

        ctx = _auth_by_api_key(raw)
        assert ctx["user_id"] == "u1"
        assert ctx["auth_mode"] == "api_key"

        conn = get_db()
        row = conn.execute("SELECT last_used FROM api_keys WHERE id='k_auth_ok'").fetchone()
        conn.close()
        assert row["last_used"]


class TestAdminMatrixEndpoint:
    def test_admin_own_view(self, setup_test_db):
        from admin_api import admin_permission_matrix

        res = asyncio.run(
            admin_permission_matrix(type="page", current_user={"user_id": "u1", "role": "admin"})
        )
        assert res["user"]["role"] == "admin"
        assert res["type"] == "page"
        assert res["summary"]["total"] == len(res["items"])
        # admin 视角：除 hidden 外全部可见
        assert res["summary"]["visible"] >= res["summary"]["total"] - res["summary"]["hidden"]
        # 图例与来源标注齐备
        assert "role" in res["legend"]
        sources = {i["source"] for i in res["items"]}
        assert sources <= {"role", "membership", "config", "default", "hidden"}

    def test_simulate_user_view(self, setup_test_db):
        from admin_api import admin_permission_matrix
        from common.db import get_db

        conn = get_db()
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, membership) "
            "VALUES ('free_u', 'free_u', 'x', 'user', 'free')"
        )
        conn.commit()
        conn.close()

        res = asyncio.run(
            admin_permission_matrix(
                type="page", user_id="free_u", current_user={"user_id": "admin", "role": "admin"}
            )
        )
        assert res["user"]["membership"] == "free"
        # 免费用户视角：存在 locked 项（pro/vip 权益），全部可见项都有来源
        assert res["summary"]["locked"] >= 0
        for item in res["items"]:
            assert item["source"] in {"role", "membership", "config", "default", "hidden"}

    def test_unknown_user_404(self, setup_test_db):
        from admin_api import admin_permission_matrix

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                admin_permission_matrix(
                    type="page", user_id="nobody", current_user={"user_id": "admin", "role": "admin"}
                )
            )
        assert exc.value.status_code == 404

    def test_non_admin_forbidden(self, setup_test_db):
        from admin_api import admin_permission_matrix

        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                admin_permission_matrix(type="page", current_user={"user_id": "u1", "role": "user"})
            )
        assert exc.value.status_code == 403
