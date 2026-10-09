#!/usr/bin/env python3
"""平台质量门禁 — 拦住"能 import、点击才崩"的隐性 bug。

三道闸（对应架构评审里的 P0/P1）：
- contract : 前端所有静态 API 调用必须有后端路由（防 404 断链）
- undefined: pyflakes 扫描未定义变量/导入（防"看起来能用、运行时 NameError"）
- secrets  : 扫描硬编码密钥/密码（安全红线）

用法：
    python3 backend/quality_gates.py contract   # 单跑契约闸
    python3 backend/quality_gates.py undefined  # 单跑未定义闸
    python3 backend/quality_gates.py secrets    # 单跑密钥闸
    python3 backend/quality_gates.py all        # 全跑（CI 默认）

退出码：0=全部通过，1=有闸未过。CI 直接以退出码决定 build 成败。
"""

import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent  # 仓库根
BACKEND = BASE / "backend"
FRONTEND = BASE / "frontend" / "src"


def _iter_py():
    for f in BACKEND.rglob("*.py"):
        # 第三方 vendored 不纳入
        if "node_modules" in f.parts or f.name == "__init__.py" and f.stat().st_size == 0:
            continue
        yield f


def _route_matches(bp: str, path: str) -> bool:
    """后端路由 bp（含 {param} 动态段）能否匹配前端静态 path。逐段比对，{x} 段匹配任意单段。"""
    if bp == path:
        return True
    bs = [s for s in bp.split("/") if s]
    ps = [s for s in path.split("/") if s]
    if len(bs) != len(ps):
        return False
    for b, p in zip(bs, ps):
        if b.startswith("{") and b.endswith("}"):
            continue  # 动态段匹配任意
        if b != p:
            return False
    return True


def gate_contract() -> tuple[bool, str]:
    """前端静态 API 调用必须有后端路由（含 @router prefix 与 @app 空路径）。"""
    routes: set[tuple[str, str]] = set()
    for f in BACKEND.glob("*.py"):
        if "voice_engine" in str(f):
            continue
        text = f.read_text(encoding="utf-8")
        prefix = ""
        m = re.search(r'APIRouter\(prefix="([^"]*)"', text)
        if m:
            prefix = m.group(1)
        for r in re.finditer(r'@router\.(get|post|put|delete)\("([^"]*)"', text):
            routes.add((r.group(1).upper(), prefix + r.group(2)))
        for r in re.finditer(r'@app\.(get|post|put|delete)\("([^"]+)"', text):
            routes.add((r.group(1).upper(), r.group(2)))

    missing: set[tuple[str, str, str]] = set()
    for f in FRONTEND.rglob("*.jsx"):
        text = f.read_text(encoding="utf-8")
        for m in re.finditer(r"api\.(get|post|put|delete)\(['\"](/api/[^'\"${}?]+)", text):
            method, path = m.group(1).upper(), m.group(2)
            ok = any(bm == method and _route_matches(bp, path) for bm, bp in routes)
            if not ok:
                missing.add((method, path, f.name))

    if missing:
        lines = "\n".join(f"  {m} {p}  [{fn}]" for m, p, fn in sorted(missing))
        return False, f"契约闸 FAIL：{len(missing)} 个前端调用无后端路由\n{lines}"
    return True, f"契约闸 PASS：{len(routes)} 条后端路由，前端 0 断链"


def gate_undefined() -> tuple[bool, str]:
    """pyflakes 未定义变量闸（只算会崩的 undefined name，排除无法静态判定的导入）。"""
    files = [str(f) for f in _iter_py()]
    if not files:
        return True, "undefined 闸 PASS：无 py 文件"
    # 优先用 pyflakes，缺失时回退 py_compile（只查语法）
    py = sys.executable or "python3"
    try:
        proc = subprocess.run([py, "-m", "pyflakes", *files],
                               capture_output=True, text=True, timeout=180)
        undefined = [ln for ln in (proc.stdout + proc.stderr).splitlines()
                     if "undefined name" in ln and "unable to detect" not in ln]
    except FileNotFoundError:
        # 无 pyflakes：退化为逐文件语法编译
        bad = []
        for fp in files:
            p2 = subprocess.run([py, "-m", "py_compile", fp], capture_output=True)
            if p2.returncode != 0:
                bad.append(f"{fp}: {p2.stderr.strip().splitlines()[-1] if p2.stderr else 'syntax error'}")
        if bad:
            return False, "undefined 闸 FAIL（无 pyflakes，语法编译失败）：\n" + "\n".join(bad[:30])
        return True, "undefined 闸 PASS（无 pyflakes，语法编译通过）"

    if undefined:
        return False, f"undefined 闸 FAIL：{len(undefined)} 个未定义变量（会运行时 NameError）\n" + "\n".join(undefined[:40])
    return True, f"undefined 闸 PASS：全后端 0 未定义变量"


def gate_secrets() -> tuple[bool, str]:
    """硬编码密钥闸：literal 赋值 sk-*/长 secret/明文口令。"""
    pats = [
        re.compile(r'(?:api_key|apikey|secret|token|password|passwd)\s*[:=]\s*[\'"]([A-Za-z0-9_\-]{16,})[\'"]', re.I),
        re.compile(r'[\'"]sk-[A-Za-z0-9]{20,}[\'"]'),
    ]
    allow = re.compile(r'getenv|environ|os\.environ|placeholder|example|your_|xxxx|test|dummy', re.I)
    hits: list[str] = []
    for f in BACKEND.rglob("*.py"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or "def " in s:
                continue
            for p in pats:
                m = p.search(line)
                if m and not allow.search(line):
                    hits.append(f"{f.relative_to(BASE)}:{i}: {s[:80]}")
                    break
    if hits:
        return False, f"密钥闸 FAIL：{len(hits)} 处疑似硬编码密钥\n" + "\n".join(hits[:30])
    return True, "密钥闸 PASS：0 处硬编码密钥"


def main() -> None:
    gates = {
        "contract": gate_contract,
        "undefined": gate_undefined,
        "secrets": gate_secrets,
    }
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    to_run = [gates[target]] if target in gates else list(gates.values())

    all_ok = True
    for gate in to_run:
        ok, msg = gate()
        print(("✅ " if ok else "❌ ") + msg)
        if not ok:
            all_ok = False
    print("\n══ 门禁结论：" + ("全部通过 ✅" if all_ok else "存在未过闸项 ❌") + " ══")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
