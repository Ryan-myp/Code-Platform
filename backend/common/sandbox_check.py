#!/usr/bin/env python3
"""AI 代码沙箱安全策略 — 静态检查 + 受限子进程执行（单一来源）。

供 /api/sandbox/execute（代码解释器）与 /api/data-analyzer/analyze（数据分析沙箱）共用。
策略：宁误伤勿放过——沙箱仅服务“纯计算 + 白名单绘图/分析”场景。
"""

import base64
import glob
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time

# 黑名单：危险操作 token（小写匹配）；白名单：允许 import 的模块。
BLOCKED_TOKENS = [
    "os.",
    "system(",
    "subprocess",
    "socket",
    "shutil",
    "ctypes",
    "importlib",
    "__import__",
    "eval(",
    "exec(",
    "open(",
    "path(",
    "tempfile",
    "glob",
    "urllib",
    "http.",
    "ftp",
    "pickle",
    "marshal",
    "pty",
    "popen",
    "fork(",
    "environ",
    "getenv",
    "chmod",
    "chown",
    "remove(",
    "unlink(",
    "rmdir",
    "sqlite3",
    "requests",
    "multiprocessing",
    "threading",
    "signal",
    "compile(",
    "input(",
]

ALLOWED_IMPORTS = {
    "math",
    "random",
    "json",
    "time",
    "datetime",
    "statistics",
    "collections",
    "itertools",
    "functools",
    "re",
    "base64",
    "io",
    "string",
    "decimal",
    "fractions",
    "heapq",
    "bisect",
    "array",
    "textwrap",
    "unicodedata",
    "operator",
    "types",
    "copy",
    "pprint",
    "traceback",
    "matplotlib",
    "pandas",
    "numpy",
    "PIL",
}

MAX_CODE_LEN = 20000
MAX_OUTPUT_LEN = 300 * 1024  # 300KB：容纳 base64 图表（图表以 [IMAGE] 标记内嵌）
DEFAULT_TIMEOUT = 30


def truncate_output(text: str, limit: int = MAX_OUTPUT_LEN) -> str:
    """截断输出，优先保证 [IMAGE] 图表块完整（避免闭合标签丢失导致前端无法渲染）。"""
    if len(text) <= limit:
        return text
    head = text[:limit]
    if "[IMAGE]" in head and "[/IMAGE]" not in head:
        # 截断点落在图片块内：向后找闭合标签，保证至少一张完整图
        close = text.find("[/IMAGE]", limit)
        if close != -1:
            return text[: close + len("[/IMAGE]")]
        # 无闭合标签（损坏块）：丢弃半截图片，保留前面文本
        last_open = head.rfind("[IMAGE]")
        return text[:last_open] if last_open > 0 else head
    return head


def check_sandbox_code(code: str) -> str | None:
    """静态检查：返回违规说明（None=通过）。"""
    import re as _re

    lowered = code.lower()
    for tok in BLOCKED_TOKENS:
        if tok in lowered:
            return f"代码包含被禁止的操作: {tok!r}（沙箱仅允许纯计算与白名单库）"
    for line in code.splitlines():
        m = _re.match(r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
        if m and m.group(1) not in ALLOWED_IMPORTS:
            return f"禁止导入模块: {m.group(1)}（不在沙箱白名单内）"
    return None


def _make_headless_safe(code: str) -> str:
    """无头环境适配：matplotlib 强制 Agg 后端，plt.show() 改写为自动保存 PNG。

    演示/教学代码习惯用 plt.show()，在无显示环境（macOS 默认 MacOSX 后端）会
    阻塞进程直到超时；改写为 plt.savefig 后图表落盘，由沙箱自动收集并以
    [IMAGE] 标记渲染到前端。
    """
    if "matplotlib" in code or "plt." in code:
        counter = {"n": 0}

        def _repl(_m):
            counter["n"] += 1
            return f"plt.savefig('_auto_show_{counter['n']}.png')"

        code = re.sub(r"plt\.show\s*\(\s*\)", _repl, code)
    return code


def run_sandbox_python(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
    extra_files: dict[str, str] | None = None,
) -> dict:
    """受限执行 Python 代码（隔离临时目录）。

    extra_files 以 {文件名: 文本内容} 写入工作目录（如 data.csv 供分析代码读取）。
    执行后自动收集工作目录内生成的 PNG 图片并以 base64 返回（数据分析图表）。
    返回 {output, error, duration, exit_code, files: {文件名: base64}}。
    """
    code = _make_headless_safe(code)
    workdir = tempfile.mkdtemp(prefix="sandbox_exec_")
    start = time.time()

    def _limits():
        """子进程资源限制。

        注意：macOS 上 Python 进程 VIRT 基础值达十几 GB，RLIMIT_AS/RLIMIT_DATA
        会导致 exec 失败，故内存保护依赖静态扫描 + 超时兜底。
        """
        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))  # CPU 10 秒
        resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))  # 单文件 2MB
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))  # 文件描述符上限

    try:
        if extra_files:
            for name, content in extra_files.items():
                with open(workdir + "/" + name, "w", encoding="utf-8") as f:
                    f.write(content)
        r = subprocess.run(
            [sys.executable, "-E", "-c", code],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,  # 防后台环境继承 tty 触发 SIGTTIN 进程组停止
            timeout=timeout,
            cwd=workdir,
            env={
                "HOME": workdir,
                "TMPDIR": workdir,
                "PYTHONIOENCODING": "utf-8",
                "MPLBACKEND": "Agg",  # 无显示环境强制非交互后端，杜绝 plt.show() 阻塞
            },
            preexec_fn=_limits,
        )
        files = {}
        for png in sorted(glob.glob(workdir + "/*.png")):
            try:
                with open(png, "rb") as f:
                    files[os.path.basename(png)] = base64.b64encode(f.read()).decode()
            except Exception:
                pass
        return {
            "output": truncate_output(r.stdout or ""),
            "error": truncate_output(r.stderr or ""),
            "duration": round(time.time() - start, 2),
            "exit_code": r.returncode,
            "files": files,
        }
    except subprocess.TimeoutExpired:
        return {"output": "", "error": f"执行超时（{timeout}秒）", "duration": timeout, "exit_code": -1, "files": {}}
    except Exception as e:
        return {"output": "", "error": f"执行器错误: {e}", "duration": 0.0, "exit_code": -1, "files": {}}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
