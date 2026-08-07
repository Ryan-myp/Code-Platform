"""分享裂变闭环（商业增长：分享得额度）单元测试。

覆盖：
- 访问去重：同访问者对同一分享只计一次有效访问
- 分享者本人访问不计奖励
- 达标发奖：有效访问达阈值 → 分享者 bonus_quota +5（rewarded 幂等防刷）
- 未达标不发 / 已发奖不重复发
- 分享工作台 /api/shares/my 统计汇总
- 端到端：不同 UA 游客访问分享页 → 裂变奖励
- 402 分层：free / pro 用户额度耗尽不同引导文案
"""

import uuid
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from common.auth import create_share, login_user
from common.db import get_db


def _insert_user(username: str, membership: str = "free", used: int = 0) -> str:
    """直接插入测试用户（绕过注册接口），返回 user_id。"""
    from common.auth import hash_password

    uid = f"u_{uuid.uuid4().hex[:8]}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, membership, used_today,
                                  last_quota_date, total_usage, bonus_quota)
               VALUES (?,?,?,?,?,?,?,?,0)""",
            (
                uid,
                username,
                hash_password("pass123456"),
                "user",
                membership,
                used,
                datetime.now().strftime("%Y-%m-%d"),
                used,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return uid


def _bonus(uid: str) -> int:
    conn = get_db()
    try:
        row = conn.execute("SELECT bonus_quota FROM users WHERE id=?", (uid,)).fetchone()
        return row[0] or 0
    finally:
        conn.close()


def _rewarded(sid: str) -> tuple[int, int]:
    conn = get_db()
    try:
        row = conn.execute("SELECT rewarded, reward_quota FROM shares WHERE id=?", (sid,)).fetchone()
        return (row[0] or 0, row[1] or 0)
    finally:
        conn.close()


def _visit_count(sid: str) -> int:
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS c FROM share_visits WHERE share_id=?", (sid,)).fetchone()
        return row[0]
    finally:
        conn.close()


def _insert_share(user_id: str, title: str = "裂变测试分享") -> dict:
    """创建分享并返回完整记录（含 user_id，供奖励函数使用）。"""
    from common.auth import get_share

    created = create_share(user_id, "text", title, "测试内容")
    full = get_share(created["share_code"])
    assert full is not None
    return full


# ══════════════════════════════════════════════════════════════
# 访问去重
# ══════════════════════════════════════════════════════════════


class TestVisitDedup:
    def test_same_visitor_counted_once(self, test_db_path):
        """同一访问者重复访问同一分享只记录一次。"""
        from main import _record_share_visit

        uid = _insert_user("dedup_user")
        share = _insert_share(uid)
        assert _record_share_visit(share["id"], "direct", "", "ip:1:abc") is True
        assert _record_share_visit(share["id"], "wechat", "http://x", "ip:1:abc") is False
        assert _visit_count(share["id"]) == 1

    def test_different_visitors_all_counted(self, test_db_path):
        """不同访问者各自计数。"""
        from main import _record_share_visit

        uid = _insert_user("dedup_user2")
        share = _insert_share(uid)
        for i in range(3):
            _record_share_visit(share["id"], "direct", "", f"ip:1:ua{i}")
        assert _visit_count(share["id"]) == 3


# ══════════════════════════════════════════════════════════════
# 裂变奖励规则
# ══════════════════════════════════════════════════════════════


class TestRewardRules:
    def test_owner_visit_ignored(self, test_db_path):
        """分享者本人访问不计有效访问、不发奖。"""
        from common.auth import grant_share_visit_reward
        from main import _record_share_visit

        uid = _insert_user("owner_user")
        share = _insert_share(uid)
        _record_share_visit(share["id"], "direct", "", f"u:{uid}")
        result = grant_share_visit_reward(share, f"u:{uid}")
        assert result == {"counted": False, "rewarded": False}
        assert _bonus(uid) == 0
        assert _rewarded(share["id"]) == (0, 0)

    def test_below_threshold_no_reward(self, test_db_path):
        """有效访问 9/10 未达标：不发奖。"""
        from common.auth import grant_share_visit_reward
        from main import _record_share_visit

        uid = _insert_user("threshold_user")
        share = _insert_share(uid)
        for i in range(9):
            _record_share_visit(share["id"], "direct", "", f"ip:1:ua{i}")
            grant_share_visit_reward(share, f"ip:1:ua{i}")
        assert _bonus(uid) == 0
        assert _rewarded(share["id"]) == (0, 0)

    def test_threshold_grants_reward(self, test_db_path):
        """有效访问达阈值：分享者 +5 额度，分享标记已发奖。"""
        from common.auth import SHARE_VISIT_REWARD, grant_share_visit_reward
        from main import _record_share_visit

        uid = _insert_user("reward_user")
        share = _insert_share(uid)
        for i in range(10):
            key = f"ip:1:ua{i}"
            _record_share_visit(share["id"], "direct", "", key)
            grant_share_visit_reward(share, key)
        assert _bonus(uid) == SHARE_VISIT_REWARD
        assert _rewarded(share["id"]) == (1, SHARE_VISIT_REWARD)

    def test_reward_idempotent(self, test_db_path):
        """已发奖后新访问不再重复发奖（防刷）。"""
        from common.auth import SHARE_VISIT_REWARD, grant_share_visit_reward
        from main import _record_share_visit

        uid = _insert_user("idem_user")
        share = _insert_share(uid)
        for i in range(10):
            key = f"ip:1:ua{i}"
            _record_share_visit(share["id"], "direct", "", key)
            grant_share_visit_reward(share, key)
        assert _bonus(uid) == SHARE_VISIT_REWARD
        # 第 11 位访问者：计数但不再发奖
        _record_share_visit(share["id"], "direct", "", "ip:1:ua_extra")
        result = grant_share_visit_reward(share, "ip:1:ua_extra")
        assert result == {"counted": True, "rewarded": False}
        assert _bonus(uid) == SHARE_VISIT_REWARD


# ══════════════════════════════════════════════════════════════
# 分享工作台统计
# ══════════════════════════════════════════════════════════════


class TestMyShareStats:
    def test_stats_totals(self, test_db_path):
        """工作台汇总：访问 / 转化 / 已得额度。"""
        from common.auth import get_my_share_stats, grant_share_visit_reward
        from main import _record_share_visit

        uid = _insert_user("stats_user")
        s1 = _insert_share(uid, "第一份分享")
        s2 = _insert_share(uid, "第二份分享")
        # s1：10 次有效访问 → 已发奖
        for i in range(10):
            key = f"ip:1:ua{i}"
            _record_share_visit(s1["id"], "direct", "", key)
            grant_share_visit_reward(s1, key)
        # s2：3 次访问 + 1 个注册转化（share_from=s2 的 share_code）
        for i in range(3):
            _record_share_visit(s2["id"], "wechat", "", f"ip:2:ua{i}")
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET share_from=? WHERE id=?",
                (s2["share_code"], _insert_user("convert_user")),
            )
            conn.commit()
        finally:
            conn.close()

        stats = get_my_share_stats(uid)
        assert stats["totals"]["visits"] == 13
        assert stats["totals"]["conversions"] == 1
        assert stats["totals"]["reward_earned"] == 5
        by_id = {s["id"]: s for s in stats["shares"]}
        assert by_id[s1["id"]]["rewarded"] is True
        assert by_id[s1["id"]]["reward_quota"] == 5
        assert by_id[s2["id"]]["rewarded"] is False
        assert by_id[s2["id"]]["visits"] == 3
        assert by_id[s2["id"]]["conversions"] == 1


# ══════════════════════════════════════════════════════════════
# 端到端：分享页访问 → 裂变奖励
# ══════════════════════════════════════════════════════════════


class TestShareApiE2E:
    def test_visits_trigger_reward(self, test_db_path):
        """10 位不同游客访问分享页 → 分享者得额度；重复 UA 不计。"""
        from main import app

        client = TestClient(app)
        uid = _insert_user("e2e_share_owner")
        share = _insert_share(uid)
        code = share["share_code"]
        for i in range(10):
            resp = client.get(f"/api/shares/{code}", headers={"User-Agent": f"visitor-browser-{i}"})
            assert resp.status_code == 200, resp.text
        assert _bonus(uid) == 5
        assert _rewarded(share["id"]) == (1, 5)
        # 同 UA 重复访问不重复计数
        resp = client.get(f"/api/shares/{code}", headers={"User-Agent": "visitor-browser-0"})
        assert resp.status_code == 200
        assert _visit_count(share["id"]) == 10

    def test_owner_visit_not_counted(self, test_db_path):
        """分享者本人访问（带 token）不计入有效访问，补齐 9 位游客也不发奖。"""
        from main import app

        client = TestClient(app)
        uid = _insert_user("e2e_owner_login")
        token = login_user("e2e_owner_login", "pass123456")["access_token"]
        share = _insert_share(uid)
        code = share["share_code"]
        # 分享者本人访问
        resp = client.get(f"/api/shares/{code}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        # 9 位游客：有效 9 次（本人不计），不发奖
        for i in range(9):
            client.get(f"/api/shares/{code}", headers={"User-Agent": f"guest-{i}"})
        assert _bonus(uid) == 0
        # 第 10 位游客：有效达标，发奖
        client.get(f"/api/shares/{code}", headers={"User-Agent": "guest-final"})
        assert _bonus(uid) == 5

    def test_my_shares_endpoint(self, test_db_path):
        """/api/shares/my 返回分享列表与汇总（需登录）。"""
        from main import app

        client = TestClient(app)
        uid = _insert_user("e2e_my_shares")
        token = login_user("e2e_my_shares", "pass123456")["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        _insert_share(uid, "工作台分享")
        resp = client.get("/api/shares/my", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["shares"]) == 1
        assert body["shares"][0]["title"] == "工作台分享"
        assert body["totals"]["threshold"] == 10
        assert body["totals"]["reward_per_share"] == 5
        assert "reward_earned" in body["totals"]


# ══════════════════════════════════════════════════════════════
# 402 分层引导
# ══════════════════════════════════════════════════════════════


class TestQuota402Tiered:
    def test_free_402_promotes_upgrade(self, test_db_path):
        """free 用户额度耗尽：402 文案促升级。"""
        from main import app

        client = TestClient(app)
        resp = client.post("/api/auth/register", json={"username": "tier_free", "password": "pass123456"})
        assert resp.status_code in (200, 201), resp.text
        token = client.post("/api/auth/login", json={"username": "tier_free", "password": "pass123456"}).json()[
            "access_token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET used_today=30, last_quota_date=? WHERE username='tier_free'",
                (datetime.now().strftime("%Y-%m-%d"),),
            )
            conn.commit()
        finally:
            conn.close()
        resp = client.post("/api/meme/generate", data={"top_text": "x"}, headers=headers)
        assert resp.status_code == 402
        body = resp.json()
        assert "免费额度" in body["detail"]
        assert body["membership"] == "free"

    def test_pro_402_mentions_reset(self, test_db_path):
        """pro 用户额度耗尽：402 文案提示明日恢复 + 至尊版。"""
        from main import app

        client = TestClient(app)
        resp = client.post("/api/auth/register", json={"username": "tier_pro", "password": "pass123456"})
        assert resp.status_code in (200, 201), resp.text
        token = client.post("/api/auth/login", json={"username": "tier_pro", "password": "pass123456"}).json()[
            "access_token"
        ]
        headers = {"Authorization": f"Bearer {token}"}
        conn = get_db()
        try:
            conn.execute(
                """UPDATE users SET membership='pro', membership_expires=?,
                   used_today=200, last_quota_date=? WHERE username='tier_pro'""",
                (
                    (datetime.now() + timedelta(days=10)).isoformat(),
                    datetime.now().strftime("%Y-%m-%d"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        resp = client.post("/api/meme/generate", data={"top_text": "x"}, headers=headers)
        assert resp.status_code == 402
        body = resp.json()
        assert "专业版" in body["detail"]
        assert "明日" in body["detail"]
        assert body["membership"] == "pro"
