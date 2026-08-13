"""核心API端点测试（企业级）"""
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture
def auth_token():
    """获取测试token"""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestHealthAPI:
    """健康检查API"""
    
    def test_health(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] == "ok"


class TestAuthAPI:
    """认证API"""
    
    def test_login(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert resp.status_code == 200
        assert "access_token" in resp.json()
    
    def test_quota(self, auth_token):
        resp = client.get("/api/auth/quota", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        data = resp.json()
        # 验证额度相关字段
        assert any(k in data for k in ["balance", "points", "daily_quota", "remaining"])


class TestSearchAPI:
    """搜索API"""
    
    def test_search_quick(self, auth_token):
        resp = client.get("/api/search/quick?q=test", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
    
    def test_search_categories(self, auth_token):
        resp = client.get("/api/search/categories", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200


class TestTemplateAPI:
    """模板API"""
    
    def test_templates_market(self, auth_token):
        resp = client.get("/api/templates/market", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200


class TestDashboardAPI:
    """看板API"""
    
    def test_dashboard_stats(self, auth_token):
        resp = client.get("/api/dashboard/stats", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200


class TestOptimizerAPI:
    """优化器API"""
    
    def test_optimizer_status(self, auth_token):
        resp = client.get("/api/optimizer/status", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "enterprise_readiness" in data
    
    def test_optimizer_metrics(self, auth_token):
        resp = client.get("/api/optimizer/metrics", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert "total_score" in data
    
    def test_optimizer_report(self, auth_token):
        resp = client.get("/api/optimizer/report", headers={"Authorization": f"Bearer {auth_token}"})
        assert resp.status_code == 200
