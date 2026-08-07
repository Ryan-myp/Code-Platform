"""游戏工坊 QC 门禁单元测试：HTML 结构配对 / 文件完整性 / 商用要素覆盖。

不依赖网络，纯函数级测试。
"""

import sys
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


GOOD_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>body { margin: 0; background: #111; }</style>
</head>
<body>
  <canvas id="game" width="480" height="640"></canvas>
  <script>
    const ctx = document.getElementById('game').getContext('2d');
    function startGame() { score = 0; best = localStorage.getItem('best') || 0; }
    function gameOver() { restart(); }
    function pause() {}
    const audio = new AudioContext();
    const osc = audio.createOscillator();
    const particles = [];
  </script>
</body>
</html>"""

WX_FILES = {
    "game.js": "const canvas = wx.createCanvas();\nconst ctx = canvas.getContext('2d');\n"
    "function startGame() {}\nfunction gameOver() {}\nwx.setStorageSync('best', 0);",
    "game.json": '{"deviceOrientation": "portrait", "showStatusBar": false}',
    "project.config.json": '{"appid": "touristappid", "compileType": "game"}',
}


def _perfect_files() -> dict:
    return {"web": {"index.html": GOOD_HTML}, "wx": dict(WX_FILES)}


class TestCheckHtmlPairs:
    """web 版 HTML 结构：script/style 开闭配对 + canvas/script 入口存在。"""

    def test_balanced_html_passes(self):
        from game_factory import _check_html_pairs

        assert _check_html_pairs(GOOD_HTML) is None

    def test_unbalanced_script_detected(self):
        from game_factory import _check_html_pairs

        html = GOOD_HTML.replace("</script>", "")
        err = _check_html_pairs(html)
        assert err is not None and "script" in err and "不配对" in err

    def test_missing_canvas_detected(self):
        from game_factory import _check_html_pairs

        html = GOOD_HTML.replace('<canvas id="game" width="480" height="640"></canvas>', "<div id='game'></div>")
        err = _check_html_pairs(html)
        assert err is not None and "<canvas>" in err

    def test_missing_inline_script_detected(self):
        from game_factory import _check_html_pairs

        html = GOOD_HTML.replace("<script>", "<script src='x.js'>").replace("</script>", "")
        err = _check_html_pairs(html)
        assert err is not None and "<script>" in err


class TestQcCheck:
    """QC 门禁：文件完整性 + HTML 结构 + JS 语法 + 商用要素。"""

    def test_perfect_project_passes(self):
        from game_factory import _qc_check

        qc = _qc_check(_perfect_files())
        assert qc["ok"] is True, [c for c in qc["checks"] if not c["ok"]]

    def test_missing_web_index(self):
        from game_factory import _qc_check

        files = _perfect_files()
        files["web"] = {}
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "web index.html 存在" and not c["ok"] for c in qc["checks"])

    def test_wx_missing_game_config(self):
        from game_factory import _qc_check

        files = _perfect_files()
        del files["wx"]["game.json"]
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "wx game.json 存在" and not c["ok"] for c in qc["checks"])

    def test_html_structure_error(self):
        from game_factory import _qc_check

        files = _perfect_files()
        files["web"]["index.html"] = GOOD_HTML.replace("</script>", "")  # script 不配对
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "HTML 结构完整" and not c["ok"] for c in qc["checks"])

    def test_feature_missing_detected(self):
        """去掉开始界面关键词后，要素门禁拦截。"""
        from game_factory import _qc_check

        files = _perfect_files()
        html = GOOD_HTML.replace("function startGame() { score = 0;", "function initGame() { score = 0;")
        html = html.replace("开始游戏", "")
        files["web"]["index.html"] = html
        files["wx"]["game.js"] = files["wx"]["game.js"].replace("function startGame()", "function initGame()")
        qc = _qc_check(files)
        assert qc["ok"] is False
        assert any(c["item"] == "开始界面" and not c["ok"] for c in qc["checks"])

    def test_wx_only_project_passes(self):
        """只生成 web 版（无 wx）时不应报 wx 文件缺失。"""
        from game_factory import _qc_check

        qc = _qc_check({"web": {"index.html": GOOD_HTML}})
        assert qc["ok"] is True
