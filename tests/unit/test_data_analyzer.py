"""产品吸引力升级 — showcase 公开成果 + AI 数据分析沙箱测试。

覆盖：
- 沙箱静态检查：危险 token / 非白名单 import 拦截，合法代码放行
- 受限执行器：正常输出 / extra_files 数据注入 / matplotlib 图表收集 / 死循环超时
- /api/showcase：公开精选（无需登录）、内容过滤、views 排序、limit 限制
- /api/data-analyzer/upload：类型校验 / CSV 解析
- /api/data-analyzer/analyze：参数校验 / mock LLM 生成代码全流程（结论+图表+代码）
"""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from common.auth import create_share


def _insert_user(username: str) -> str:
    """直接插入测试用户，返回 user_id。"""
    from common.auth import hash_password
    from common.db import get_db

    uid = f"u_{uuid.uuid4().hex[:8]}"
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO users (id, username, password_hash, role, membership, used_today,
                                  last_quota_date, total_usage, bonus_quota)
               VALUES (?,?,?,?,?,?,?,?,0)""",
            (uid, username, hash_password("pass123456"), "user", "free", 0, "2026-01-01", 0),
        )
        conn.commit()
    finally:
        conn.close()
    return uid


def _set_views(share_code: str, views: int):
    from common.db import get_db

    conn = get_db()
    try:
        conn.execute("UPDATE shares SET views=? WHERE share_code=?", (views, share_code))
        conn.commit()
    finally:
        conn.close()


def _client() -> TestClient:
    from main import app

    return TestClient(app)


# ══════════════════════════════════════════════════════════════
# 沙箱静态检查（安全）
# ══════════════════════════════════════════════════════════════


class TestSandboxCheck:
    def test_clean_code_passes(self):
        """合法计算代码通过检查。"""
        from common.sandbox_check import check_sandbox_code

        code = "import math\nprint(math.sqrt(16))"
        assert check_sandbox_code(code) is None

    def test_pandas_matplotlib_allowed(self):
        """数据分析白名单库放行。"""
        from common.sandbox_check import check_sandbox_code

        code = (
            "import pandas as pd\nimport numpy as np\nimport matplotlib\n"
            'matplotlib.use("Agg")\nimport matplotlib.pyplot as plt\n'
            'df = pd.DataFrame({"a": [1, 2]})\nprint(df.mean())'
        )
        assert check_sandbox_code(code) is None

    def test_blocked_os_token(self):
        """os. 操作被拦截。"""
        from common.sandbox_check import check_sandbox_code

        assert "禁止" in check_sandbox_code('import os\nos.system("ls")')

    def test_blocked_open_eval_subprocess(self):
        """open/eval/subprocess/__import__ 均被拦截。"""
        from common.sandbox_check import check_sandbox_code

        for bad in ['open("x")', 'eval("1+1")', "import subprocess", '__import__("os")']:
            assert check_sandbox_code(bad) is not None, bad

    def test_blocked_non_whitelisted_import(self):
        """白名单外的 import 被拦截。"""
        from common.sandbox_check import check_sandbox_code

        assert "禁止导入" in check_sandbox_code("import flask")


# ══════════════════════════════════════════════════════════════
# 受限执行器（功能）
# ══════════════════════════════════════════════════════════════


class TestRunSandboxPython:
    def test_simple_execution(self):
        """普通代码执行返回 stdout。"""
        from common.sandbox_check import run_sandbox_python

        r = run_sandbox_python('print("hello sandbox")')
        assert r["exit_code"] == 0
        assert r["output"].strip() == "hello sandbox"
        assert r["error"] == ""

    def test_extra_files_injected(self):
        """extra_files 注入 data.csv 供代码读取。"""
        from common.sandbox_check import run_sandbox_python

        code = (
            "import pandas as pd\n"
            'df = pd.read_csv("data.csv")\n'
            'print(df["a"].sum())'
        )
        r = run_sandbox_python(code, extra_files={"data.csv": "a,b\n1,4\n2,5\n3,6\n"})
        assert r["exit_code"] == 0
        assert r["output"].strip() == "6"

    def test_chart_collected_as_base64(self):
        """matplotlib 保存的 PNG 自动收集为 base64。"""
        from common.sandbox_check import run_sandbox_python

        code = (
            "import matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n"
            "plt.plot([1, 2, 3])\nplt.savefig('chart1.png')"
        )
        r = run_sandbox_python(code)
        assert r["exit_code"] == 0
        assert "chart1.png" in r["files"]
        assert r["files"]["chart1.png"].startswith("iVBOR")  # PNG magic

    def test_timeout_kills_infinite_loop(self):
        """死循环代码被超时终止。"""
        from common.sandbox_check import run_sandbox_python

        r = run_sandbox_python("while True: pass", timeout=5)
        assert r["exit_code"] == -1
        assert "超时" in r["error"]


# ══════════════════════════════════════════════════════════════
# /api/showcase 公开成果精选
# ══════════════════════════════════════════════════════════════


class TestShowcaseApi:
    def test_empty_returns_demo_items(self):
        """无真实分享时返回系统精选示例成果（is_demo 标记，保证首页不空）。"""
        resp = _client().get("/api/showcase")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0
        assert all(it["is_demo"] for it in items)
        assert all(it["route"] for it in items)
    
    def test_public_no_auth_required(self):
        """showcase 无需登录即可访问。"""
        uid = _insert_user("showcase_owner")
        create_share(uid, "text", "公开成果", "这是一段超过十个字符的公开成果内容")
        resp = _client().get("/api/showcase")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        assert not resp.json()["items"][0].get("is_demo")
    
    def test_filters_short_or_empty_content(self):
        """空内容 / 过短内容不出现在精选里（此时回落为示例成果，不返回脏数据）。"""
        uid = _insert_user("showcase_filter")
        create_share(uid, "text", "短内容", "太短")
        create_share(uid, "text", "空内容", "")
        resp = _client().get("/api/showcase")
        items = resp.json()["items"]
        # 脏分享被过滤 → 无真实成果 → 回落示例成果
        assert items and all(it["is_demo"] for it in items)

    def test_sorted_by_views_and_limit(self):
        """按浏览量排序，limit 生效。"""
        uid = _insert_user("showcase_sort")
        for title, content, views in [
            ("低流量", "这是一个低流量的公开成果内容", 3),
            ("高流量", "这是一个高流量的公开成果内容", 99),
            ("中流量", "这是一个中流量的公开成果内容", 50),
        ]:
            share = create_share(uid, "text", title, content)
            _set_views(share["share_code"], views)
        resp = _client().get("/api/showcase", params={"limit": 2})
        items = resp.json()["items"]
        assert [i["title"] for i in items] == ["高流量", "中流量"]
        assert "share_code" in items[0]

    def test_preview_truncated(self):
        """preview 截断为 120 字内。"""
        uid = _insert_user("showcase_preview")
        long_content = "很" * 500
        create_share(uid, "text", "长内容", long_content)
        resp = _client().get("/api/showcase")
        preview = resp.json()["items"][0]["preview"]
        assert len(preview) <= 120
        assert preview == "很" * 120


# ══════════════════════════════════════════════════════════════
# /api/data-analyzer 上传与分析
# ══════════════════════════════════════════════════════════════


class TestDataAnalyzerUpload:
    def test_rejects_unsupported_type(self, auth_headers):
        """非表格文件类型被拒绝。"""
        resp = _client().post(
            "/api/data-analyzer/upload",
            headers=auth_headers,
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "不支持的文件类型" in resp.json()["detail"]

    def test_parses_csv(self, auth_headers):
        """CSV 上传返回文本/列名/行数。"""
        content = "日期,区域,金额\n2026-01-01,华东,100\n2026-01-02,华南,200\n"
        resp = _client().post(
            "/api/data-analyzer/upload",
            headers=auth_headers,
            files={"file": ("sales.csv", content.encode("utf-8"), "text/csv")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["columns"] == ["日期", "区域", "金额"]
        assert body["rows"] == 2
        assert "csv" in body

    def test_empty_csv_rejected(self, auth_headers):
        """空内容 CSV 被拒绝。"""
        resp = _client().post(
            "/api/data-analyzer/upload",
            headers=auth_headers,
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert resp.status_code == 400

    def test_requires_auth(self):
        """未登录不能上传。"""
        resp = _client().post(
            "/api/data-analyzer/upload",
            files={"file": ("a.csv", b"a,b\n1,2", "text/csv")},
        )
        assert resp.status_code == 401


class TestDataAnalyzerAnalyze:
    CSV = "区域,金额\n华东,100\n华南,200\n华东,300\n"

    def _post(self, auth_headers, **payload):
        return _client().post("/api/data-analyzer/analyze", headers=auth_headers, json=payload)

    def test_requires_question_and_data(self, auth_headers):
        """缺问题或缺数据返回 400。"""
        assert self._post(auth_headers, question="", data=self.CSV).status_code == 400
        assert self._post(auth_headers, question="分析一下", data="").status_code == 400

    def test_invalid_csv_rejected(self, auth_headers):
        """非 CSV 数据被拒绝。"""
        resp = self._post(auth_headers, question="分析一下", data="这不是表格数据")
        assert resp.status_code == 400

    def test_full_flow_with_mock_llm(self, auth_headers):
        """mock LLM 生成代码 → 沙箱执行 → 返回结论+图表+代码。"""
        mock_code = (
            "import pandas as pd\nimport matplotlib\n"
            "matplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n"
            'df = pd.read_csv("data.csv")\n'
            'print("总金额:", df["金额"].sum())\n'
            'df["region"] = df["区域"].map({"华东": "East", "华南": "South"})\n'
            'df.groupby("region")["金额"].sum().plot(kind="bar")\n'
            'plt.savefig("chart1.png")'
        )
        with patch(
            "data_analyzer.call_llm_async",
            return_value=f"```python\n{mock_code}\n```",
        ) as mocked:
            resp = self._post(auth_headers, question="按区域汇总金额", data=self.CSV)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "总金额: 600" in body["conclusion"]
        assert len(body["charts"]) == 1
        assert body["charts"][0]["name"] == "chart1.png"
        assert body["code"] == mock_code
        assert body["error"] == ""
        mocked.assert_called_once()

    def test_blocked_code_rejected(self, auth_headers):
        """LLM 生成的危险代码被沙箱拒绝（400）。"""
        with patch(
            "data_analyzer.call_llm_async",
            return_value="```python\nimport os\nos.system('rm -rf /')\n```",
        ):
            resp = self._post(auth_headers, question="删除文件", data=self.CSV)
        assert resp.status_code == 400
        assert "未通过安全检查" in resp.json()["detail"]

    def test_requires_auth(self):
        """未登录不能分析。"""
        resp = _client().post(
            "/api/data-analyzer/analyze",
            json={"question": "分析", "data": self.CSV},
        )
        assert resp.status_code == 401

    def test_quota_charged(self, auth_headers):
        """analyze 计入配额中间件（消耗 1 次当日额度）。"""
        from datetime import datetime

        from common.db import get_db

        # 注册一个 free 用户并设置额度为 1，跑一次后应剩 0
        uid = _insert_user("analyzer_quota_user")
        conn = get_db()
        try:
            conn.execute(
                "UPDATE users SET used_today=29, last_quota_date=? WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d"), uid),
            )
            conn.commit()
        finally:
            conn.close()
        # admin 是 vip 不扣费；用新用户登录
        from common.auth import login_user

        token = login_user("analyzer_quota_user", "pass123456")["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        with patch("data_analyzer.call_llm_async", return_value="```python\nprint('ok')\n```"):
            resp = self._post(headers, question="简单统计", data=self.CSV)
        assert resp.status_code == 200
        conn = get_db()
        try:
            row = conn.execute("SELECT used_today FROM users WHERE id=?", (uid,)).fetchone()
        finally:
            conn.close()
        assert row[0] == 30  # 已扣减
