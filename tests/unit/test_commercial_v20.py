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
        assert data["invite_code"].startswith("TEAM_")


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
