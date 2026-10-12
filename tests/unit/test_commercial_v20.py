"""商业化新功能单元测试 v20。

覆盖：年付定价、团队席位计费、API Key 独立配额、转化漏斗分析、企业询价。
"""
import os

import pytest
from fastapi.testclient import TestClient

os.environ["APP_ENV"] = "test"

from main import app

client = TestClient(app)


@pytest.fixture
def auth_token():
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


HEADER = lambda t: {"Authorization": f"Bearer {t}"}


# ══════════════════════════════════════════════════════════════
# 年付定价
# ══════════════════════════════════════════════════════════════

class TestYearlyPricing:
    def test_prices_endpoint_includes_yearly(self, auth_token):
        resp = client.get("/api/stripe/prices", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        # 验证 pro 和 vip 都有 yearly_amount
        assert "plans" in data
        for plan_key in ("pro", "vip"):
            assert plan_key in data["plans"]
            assert "yearly_amount" in data["plans"][plan_key]
            assert data["plans"][plan_key]["yearly_amount"] > 0

    def test_yearly_discount_displayed(self, auth_token):
        resp = client.get("/api/stripe/prices", headers=HEADER(auth_token))
        data = resp.json()["plans"]
        # 年付应比月付 × 12 便宜
        pro_monthly = data["pro"]["amount"]
        pro_yearly = data["pro"]["yearly_amount"]
        assert pro_yearly < pro_monthly * 12, "年付应有折扣"


# ══════════════════════════════════════════════════════════════
# 团队席位计费
# ══════════════════════════════════════════════════════════════

class TestTeamBilling:
    def test_create_team_with_plan(self, auth_token):
        resp = client.post(
            "/api/teams",
            headers=HEADER(auth_token),
            json={"name": "测试团队", "plan": "pro", "seats": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["seats"] == 3
        assert data["plan"] == "pro"
        return data["id"]

    def test_get_team_dashboard(self, auth_token):
        # 先创建团队
        create_resp = client.post(
            "/api/teams",
            headers=HEADER(auth_token),
            json={"name": "Dashboard 测试", "plan": "pro", "seats": 2},
        )
        assert create_resp.status_code == 200
        team_id = create_resp.json()["id"]

        # 获取仪表盘
        resp = client.get(f"/api/teams/{team_id}/dashboard", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "seats" in data
        assert "usage" in data
        assert "subscription_status" in data

    def test_dashboard_seats_are_scoped_per_team(self, auth_token):
        """v17.x 回归：dashboard 席位统计必须按 team_id 过滤（曾全库共享）。"""
        from common.db import get_db

        def make_team(name):
            r = client.post(
                "/api/teams",
                headers=HEADER(auth_token),
                json={"name": name, "plan": "pro", "seats": 5},
            )
            assert r.status_code == 200
            return r.json()["id"]

        t_a, t_b = make_team("Scope 团队A"), make_team("Scope 团队B")

        # 团队A 加 2 个成员，团队B 不加 → 修复前两队 seats.used 相同（bug）
        conn = get_db()
        for i, uid in enumerate(("scope_user_1", "scope_user_2")):
            conn.execute(
                "INSERT OR IGNORE INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, 'user', '2026-01-01T00:00:00')",
                (uid, f"scope_{i}", "x"),
            )
        for uid in ("scope_user_1", "scope_user_2"):
            conn.execute(
                "INSERT INTO team_members (id, team_id, user_id, role, joined_at) VALUES (?, ?, ?, 'member', '2026-01-01')",
                (f"sm_{t_a}_{uid}", t_a, uid),
            )
        conn.commit()
        conn.close()

        d_a = client.get(f"/api/teams/{t_a}/dashboard", headers=HEADER(auth_token)).json()
        d_b = client.get(f"/api/teams/{t_b}/dashboard", headers=HEADER(auth_token)).json()
        # 创建者自动成为 admin 成员：团队A = 1(创建者) + 2 = 3；团队B = 1
        assert d_a["seats"]["used"] == 3
        assert d_b["seats"]["used"] == 1, "席位统计不得跨团队共享"

    def test_invite_link(self, auth_token):
        create_resp = client.post(
            "/api/teams",
            headers=HEADER(auth_token),
            json={"name": "Invite 测试", "plan": "pro", "seats": 2},
        )
        team_id = create_resp.json()["id"]

        resp = client.get(f"/api/teams/{team_id}/invite-link", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "invite_code" in data
        assert "invite_url" in data

    def test_team_agent_members_persist_and_normalize(self, auth_token):
        """协作 Agent 成员：创建时持久化、对外输出为数组（库里是 JSON 字符串）。"""
        # 先造 3 个 Agent（members 校验要求 Agent 真实存在）
        agent_ids = []
        for n in ("协作文档", "代码审查", "数据分析"):
            r = client.post(
                "/api/agents", headers=HEADER(auth_token),
                json={"name": n, "description": "", "instructions": "", "model": "agnes-3.0-flash",
                      "tools": [], "knowledge_base_ids": [], "skill_ids": [], "mcp_server_ids": []},
            )
            assert r.status_code == 200
            agent_ids.append(r.json()["id"])
        a, b, c = agent_ids

        # 创建时带 2 个 Agent 成员
        r = client.post(
            "/api/teams", headers=HEADER(auth_token),
            json={"name": "成员持久化测试", "plan": "pro", "seats": 2, "members": [a, b]},
        )
        assert r.status_code == 200
        tid = r.json()["id"]
        detail = client.get(f"/api/teams/{tid}", headers=HEADER(auth_token)).json()
        assert detail["team"]["members"] == [a, b]

        # 更新 members（去重保序）
        up = client.patch(
            f"/api/teams/{tid}", headers=HEADER(auth_token),
            json={"members": [b, a, b]},
        )
        assert up.status_code == 200
        detail2 = client.get(f"/api/teams/{tid}", headers=HEADER(auth_token)).json()
        assert detail2["team"]["members"] == [b, a]

        # 加入未知 Agent → 400
        bad = client.patch(
            f"/api/teams/{tid}", headers=HEADER(auth_token),
            json={"members": ["no-such-agent"]},
        )
        assert bad.status_code == 400
        # 清空成员合法
        clear = client.patch(f"/api/teams/{tid}", headers=HEADER(auth_token), json={"members": []})
        assert clear.status_code == 200
        assert client.get(f"/api/teams/{tid}", headers=HEADER(auth_token)).json()["team"]["members"] == []

        # 列表接口也输出为数组
        client.patch(f"/api/teams/{tid}", headers=HEADER(auth_token), json={"members": [c]})
        lst = client.get("/api/teams", headers=HEADER(auth_token)).json()
        t = next((x for x in lst.get("teams", []) if x["id"] == tid), None)
        assert t is not None and t["members"] == [c]


# ══════════════════════════════════════════════════════════════
# API Key 计费
# ══════════════════════════════════════════════════════════════

class TestAPIKeyBilling:
    def test_create_api_key(self, auth_token):
        resp = client.post(
            "/api/api-key-billing",
            headers=HEADER(auth_token),
            json={"name": "测试 Key", "plan": "pay_as_you_go"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "key" in data
        assert data["key"].startswith("xt_")
        assert "message" in data
        return data["key"]

    def test_list_api_keys(self, auth_token):
        # 先创建一个
        client.post(
            "/api/api-key-billing",
            headers=HEADER(auth_token),
            json={"name": "列表测试", "plan": "pro"},
        )
        resp = client.get("/api/api-key-billing", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert isinstance(data["keys"], list)

    def test_topup_api_key(self, auth_token):
        # 创建 key
        create_resp = client.post(
            "/api/api-key-billing",
            headers=HEADER(auth_token),
            json={"name": "充值测试", "plan": "pay_as_you_go"},
        )
        key_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/api-key-billing/{key_id}/topup",
            headers=HEADER(auth_token),
            json={"amount": 100},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["new_remaining"] >= 100


# ══════════════════════════════════════════════════════════════
# 转化漏斗分析
# ══════════════════════════════════════════════════════════════

class TestConversionFunnel:
    def test_funnel_analytics(self, auth_token):
        resp = client.get("/api/analytics/funnel", headers=HEADER(auth_token))
        # 非管理员应返回 403
        if resp.status_code == 200:
            data = resp.json()
            assert "snapshot" in data
            assert "conversion_rates" in data
            assert "mrr_cny" in data
        else:
            assert resp.status_code in (403, 401)

    def test_trial_expiry_pipeline(self, auth_token):
        resp = client.get("/api/analytics/trial-expiry", headers=HEADER(auth_token))
        if resp.status_code == 200:
            data = resp.json()
            assert "expiring_in_7d" in data
            assert "conversion_rate" in data


# ══════════════════════════════════════════════════════════════
# 企业服务
# ══════════════════════════════════════════════════════════════

class TestEnterprise:
    def test_enterprise_features(self, auth_token):
        resp = client.get("/api/enterprise/features", headers=HEADER(auth_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "features" in data
        assert len(data["features"]) > 0
        assert "pricing_tiers" in data

    def test_submit_enterprise_inquiry(self, auth_token):
        resp = client.post(
            "/api/enterprise/inquiry",
            headers=HEADER(auth_token),
            json={
                "company_name": "测试公司",
                "contact_name": "张三",
                "contact_email": "test@example.com",
                "team_size": 50,
                "plan_tier": "standard",
                "requirements": "需要私有化部署",
            },
        )
        # 非管理员提交询价应成功（公开接口）
        assert resp.status_code == 200
        data = resp.json()
        assert "inquiry_id" in data
        assert "estimated_total" in data
        assert data["estimated_total"] > 0
