"""数字人按量计费 API 网关单元测试（Phase 5.1 商业化预留）。

验证：API Key 认证 / 余额不足 402 / 管理员充值 / 计费创建任务（账单落库）/
免费档强制分层（2D+720p）/ 计费规则读取与 config 覆盖 / 任务查询与惰性退费。
mock 任务创建与查询，不产生真实异步任务与外部依赖。
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _create_api_key(auth_headers, label="gateway-test"):
    """创建测试 API Key，返回 (raw_key, key_headers)。"""
    resp = client.post("/api/api-keys", json={"label": label}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    raw = resp.json()["api_key"]
    return raw, {"Authorization": f"Bearer {raw}"}


def _seed_user(username):
    """直接向测试库播种普通用户（绕过 register 限流），返回 user_id。

    API Key 认证（_auth_by_api_key）只需用户存在，无需登录 token。
    """
    import uuid
    from datetime import datetime

    from common.auth import hash_password
    from common.db import get_db_context

    uid = f"u_{uuid.uuid4().hex[:8]}"
    with get_db_context() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?,?,?,?,?)",
            (uid, username, hash_password("bob123456"), "user", datetime.now().isoformat()),
        )
    return uid


_LOGIN_CACHE: dict = {}


def _login(username):
    """播种用户后登录拿 JWT。per-username 缓存：避免全量运行触发登录限流（5/min）偶发 429。"""
    if username in _LOGIN_CACHE:
        return _LOGIN_CACHE[username]
    resp = client.post("/api/auth/login", json={"username": username, "password": "bob123456"})
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    _LOGIN_CACHE[username] = headers
    return headers


def _recharge(auth_headers, user_id, amount=100.0):
    resp = client.post(
        "/api/dh/billing/recharge",
        json={"user_id": user_id, "amount": amount, "remark": "test"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestAuth:
    """API Key 认证：缺失/非法 Key 一律 OpenAI 风格 401。"""

    def test_missing_api_key_401(self):
        resp = client.post("/v1/dh/videos", json={"text": "大家好，这是一段测试文案。"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "invalid_api_key"

    def test_invalid_api_key_401(self):
        resp = client.post(
            "/v1/dh/videos",
            json={"text": "大家好，这是一段测试文案。"},
            headers={"Authorization": "Bearer xt-invalid-key"},
        )
        assert resp.status_code == 401

    def test_pricing_requires_auth(self):
        assert client.get("/v1/dh/pricing").status_code == 401


class TestBilling:
    """余额充值 / 计费扣款 / 账单落库。"""

    def test_recharge_requires_admin(self, auth_headers, test_db_path):
        bob_id = _seed_user("bob_gw_admin")
        bob_headers = _login("bob_gw_admin")
        resp = client.post(
            "/api/dh/billing/recharge", json={"user_id": bob_id, "amount": 50}, headers=bob_headers
        )
        assert resp.status_code == 403
        # admin 充值成功
        r = _recharge(auth_headers, bob_id, 50)
        assert r["balance"] == 50.0

    def test_create_video_insufficient_balance(self, auth_headers, test_db_path):
        _, key_headers = _create_api_key(auth_headers)
        resp = client.post("/v1/dh/videos", json={"text": "大家好，这是一段测试文案。"}, headers=key_headers)
        assert resp.status_code == 402
        assert resp.json()["error"]["code"] == "insufficient_balance"

    def test_create_video_charged_and_billing_record(self, auth_headers, test_db_path):
        from common.db import get_db_context

        with get_db_context() as conn:
            admin_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
        _recharge(auth_headers, admin_id, 100)
        _, key_headers = _create_api_key(auth_headers)
        with patch("dh_gateway.create_task", return_value={"id": "task_gw1", "status": "pending"}) as mc:
            resp = client.post(
                "/v1/dh/videos",
                json={"text": "大家好，这是一段测试文案，内容足够长。", "resolution": "1080p"},
                headers=key_headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["task_id"] == "task_gw1"
        assert data["price"] == 1.5  # 2D 0.5 + 1080p 加价 1.0
        assert data["balance"] == 98.5
        payload = mc.call_args[0][1]
        assert payload["engine"] == "2d" and payload["resolution"] == "1080p"
        # 账单落库 + 余额扣减
        with get_db_context() as conn:
            rows = conn.execute("SELECT * FROM dh_billing_records").fetchall()
            assert len(rows) == 1
            assert rows[0]["price"] == 1.5 and rows[0]["status"] == "charged"
            assert rows[0]["task_id"] == "task_gw1"
            balance = conn.execute("SELECT balance FROM users WHERE id=?", (admin_id,)).fetchone()["balance"]
            assert balance == 98.5

    def test_free_key_forced_2d_720p(self, auth_headers, test_db_path):
        """免费/付费分层：免费用户经 API 强制 2D + 720p（按 2D 基础价计费）。"""
        bob_id = _seed_user("bob_gw_free")
        _recharge(auth_headers, bob_id, 100)
        bob_headers = _login("bob_gw_free")
        _, key_headers = _create_api_key(bob_headers, "bob-key")
        with patch("dh_gateway.create_task", return_value={"id": "task_gw2", "status": "pending"}) as mc:
            resp = client.post(
                "/v1/dh/videos",
                json={
                    "text": "大家好，这是一段测试文案，内容足够长。",
                    "engine": "live_portrait",
                    "resolution": "1080p",
                },
                headers=key_headers,
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["forced"] == ["engine=2d", "resolution=720p"]
        assert data["price"] == 0.5  # 强制后按 2D 基础价
        payload = mc.call_args[0][1]
        assert payload["engine"] == "2d" and payload["resolution"] == "720p"

    def test_unknown_template_rejected_no_charge(self, auth_headers, test_db_path):
        """未知模板 400：预检失败不扣费、不落账单。"""
        bob_id = _seed_user("bob_gw_tpl")
        _recharge(auth_headers, bob_id, 100)
        bob_headers = _login("bob_gw_tpl")
        _, key_headers = _create_api_key(bob_headers, "bob-tpl")
        with patch("dh_gateway.create_task") as mc:
            resp = client.post(
                "/v1/dh/videos",
                json={"text": "大家好，这是一段测试文案。", "template_id": "no_such_tpl"},
                headers=key_headers,
            )
        assert resp.status_code == 400, resp.text
        mc.assert_not_called()
        from common.db import get_db_context

        with get_db_context() as conn:
            n = conn.execute("SELECT COUNT(*) AS c FROM dh_billing_records").fetchone()["c"]
            balance = conn.execute("SELECT balance FROM users WHERE id=?", (bob_id,)).fetchone()["balance"]
        assert n == 0 and balance == 100.0  # 未扣费


class TestPricing:
    def test_pricing_endpoint(self, auth_headers, test_db_path):
        _, key_headers = _create_api_key(auth_headers)
        resp = client.get("/v1/dh/pricing", headers=key_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pricing"]["2d"] == 0.5
        assert data["pricing"]["live_portrait"] == 2.0
        assert data["pricing"]["voice_clone"] == 10.0
        assert data["pricing"]["hd_1080p_extra"] == 1.0
        assert "balance" in data and data["currency"] == "CNY"

    def test_pricing_overridable_via_config(self, auth_headers, test_db_path):
        from common.db import get_db_context

        with get_db_context() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES ('dh_pricing', ?)",
                ('{"2d": 0.8, "live_portrait": 3.0, "hd_1080p_extra": 2.0}',),
            )
        _, key_headers = _create_api_key(auth_headers)
        resp = client.get("/v1/dh/pricing", headers=key_headers)
        assert resp.json()["pricing"]["2d"] == 0.8
        # 计费按覆盖后的价格
        with get_db_context() as conn:
            admin_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
        _recharge(auth_headers, admin_id, 100)
        with patch("dh_gateway.create_task", return_value={"id": "task_gw3", "status": "pending"}):
            resp = client.post("/v1/dh/videos", json={"text": "大家好，这是一段测试文案。"}, headers=key_headers)
        assert resp.json()["price"] == 0.8


class TestTaskQuery:
    def test_task_owner_check(self, auth_headers, test_db_path):
        """越权查询其他用户任务 → 403。"""
        _seed_user("bob_gw_owner")
        bob_headers = _login("bob_gw_owner")
        _, key_headers = _create_api_key(bob_headers, "bob-owner")
        with patch("dh_gateway.get_task", return_value={"id": "t_owner", "created_by": "admin", "status": "running"}):
            resp = client.get("/v1/dh/videos/t_owner", headers=key_headers)
        assert resp.status_code == 403

    def test_failed_task_auto_refund(self, auth_headers, test_db_path):
        """任务失败 → 查询状态时惰性退费（账单 refunded + 余额回补）。"""
        bob_id = _seed_user("bob_gw_refund")
        _recharge(auth_headers, bob_id, 100)
        bob_headers = _login("bob_gw_refund")
        _, key_headers = _create_api_key(bob_headers, "bob-refund")
        with patch("dh_gateway.create_task", return_value={"id": "task_gw4", "status": "pending"}):
            resp = client.post("/v1/dh/videos", json={"text": "大家好，这是一段测试文案。"}, headers=key_headers)
        assert resp.status_code == 200
        assert resp.json()["balance"] == 99.5
        with patch(
            "dh_gateway.get_task",
            return_value={
                "id": "task_gw4",
                "created_by": "bob_gw_refund",
                "status": "failed",
                "progress": 80,
                "stage": "render",
                "error": "[stage:render] 渲染失败",
                "result": None,
            },
        ):
            resp = client.get("/v1/dh/videos/task_gw4", headers=key_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["refunded"] is True
        assert data["billing"][0]["status"] == "refunded"
        assert data["balance"] == 100.0  # 全额退回
