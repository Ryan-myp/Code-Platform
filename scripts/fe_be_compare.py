#!/usr/bin/env python3
"""前端 API 调用路径 vs 后端路由全量对照（OpenAPI 为后端事实源）。
用法: python3 scripts/fe_be_compare.py [backend_base_url]
"""
import re, sys, os, json, urllib.request

BACKEND_URL = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8888'
SRC_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'src')

# ---------- 1. 提取前端调用（源码扫描，静态路径 + 模板字符串） ----------
fe_calls = set()
for root, dirs, files in os.walk(SRC_ROOT):
    for fn in files:
        if not fn.endswith(('.jsx', '.js')):
            continue
        src = open(os.path.join(root, fn)).read()
        for m in re.finditer(r'api\.(?:get|post|put|delete|patch)\(\s*(["\'])(/api/[^"\']*)\1', src):
            fe_calls.add(m.group(2))
        for m in re.finditer(r'api\.(?:get|post|put|delete|patch)\(\s*`([^`]*)`', src):
            p = m.group(1)
            if p.startswith('/api/') and '${' in p:
                fe_calls.add(p)
            elif p.startswith('/api/'):
                fe_calls.add(p)

# ---------- 2. 后端路由：直接拉取 OpenAPI ----------
try:
    with urllib.request.urlopen(f'{BACKEND_URL}/openapi.json', timeout=10) as r:
        spec = json.load(r)
    backend_routes = []  # (method, full_path, source)
    for path, methods in spec.get('paths', {}).items():
        for m in methods:
            if m in ('get', 'post', 'put', 'delete', 'patch'):
                backend_routes.append((m.upper(), path, 'openapi'))
    source_label = f"OpenAPI ({len(backend_routes)} 条)"
except Exception as e:
    print(f"[warn] OpenAPI 拉取失败({e})，回退源码扫描")
    backend_dir = '/Users/yanping.ma/PycharmProjects/Code-Platform/backend'
    route_pat = re.compile(r'@(?:router|app|bp)\.(get|post|put|delete|patch)\s*\(\s*(["\'])([^"\']*)\2', re.S)
    prefix_pat = re.compile(r'APIRouter\([^)]*prefix\s*=\s*["\']([^"\']*)["\']')
    router_prefixes = {}
    backend_routes = []
    for fname in sorted(os.listdir(backend_dir)):
        if not fname.endswith('.py'):
            continue
        src = open(os.path.join(backend_dir, fname)).read()
        for m in re.finditer(r'(\w+)\s*=\s*APIRouter\(([^)]*)\)', src):
            prefix = prefix_pat.search(m.group(2))
            router_prefixes[m.group(1)] = prefix.group(1) if prefix else ''
        for m in route_pat.finditer(src):
            decorator_line = src[m.start():src.find('\n', m.start())]
            rn = re.match(r'@(\w+)\.', decorator_line)
            if not rn:
                continue
            path = m.group(3)
            prefix = router_prefixes.get(rn.group(1), '')
            if not path.startswith('/'):
                path = '/' + path
            full = (prefix + path).replace('//', '/')
            backend_routes.append((m.group(1).upper(), full, fname))
    source_label = f"源码扫描 ({len(backend_routes)} 条)"

# ---------- 3. 前端模板转正则 ----------
def fe_to_regex(path):
    # 剥离 query 部分（?xxx），路径匹配只看 pathname
    path = path.split('?')[0]
    parts = re.split(r'(\$\{[^}]+\})', path)
    regex = ''
    for p in parts:
        if p.startswith('${'):
            regex += r'[^/]+'
        else:
            regex += re.escape(p)
    return '^' + regex + '$'

# ---------- 4. 对照 ----------
def match_backend(fe_path):
    regex = fe_to_regex(fe_path)
    matched = []
    for method, full, fname in backend_routes:
        if re.match(regex, full):
            matched.append((method, full, fname))
    return matched

# 提取前端调用的方法（从源码里抓 api.get/post 与路径的关系）
fe_method_map = {}
for root, dirs, files in os.walk(SRC_ROOT):
    for fn in files:
        if not fn.endswith(('.jsx', '.js')):
            continue
        src = open(os.path.join(root, fn)).read()
        for m in re.finditer(r'api\.(get|post|put|delete|patch)\(\s*(["\'])(.*?)\2', src, re.S):
            p = m.group(3)
            fe_method_map.setdefault(p, set()).add(m.group(1).upper())
        for m in re.finditer(r'api\.(get|post|put|delete|patch)\(\s*`([^`]*)`', src):
            p = m.group(2)
            fe_method_map.setdefault(p, set()).add(m.group(1).upper())

print(f"前端唯一调用路径: {len(fe_calls)} 条")
print(f"后端路由: {source_label}\n")

issues = []
ok_count = 0
for fe_path in sorted(fe_calls):
    methods = fe_method_map.get(fe_path, set())
    matched = match_backend(fe_path)
    if not matched:
        issues.append(('NO_ROUTE', fe_path, sorted(methods), None))
        continue
    if methods:
        backend_methods = {m[0] for m in matched}
        missing_methods = methods - backend_methods
        if missing_methods:
            issues.append(('METHOD_MISSING', fe_path, sorted(missing_methods), matched))
            continue
    ok_count += 1

print("=" * 70)
print("完全缺失路由 (NO_ROUTE):")
for kind, p, m, matched in issues:
    if kind == 'NO_ROUTE':
        print(f"  ❌ {p}  [methods={m}]")
print()
print("方法不匹配 (METHOD_MISSING):")
for kind, p, m, matched in issues:
    if kind == 'METHOD_MISSING':
        bm = {f"{mm} {fp} ({fn})" for mm, fp, fn in matched}
        print(f"  ⚠️  {p}  前端调 {m}，后端有: {bm}")
print()
print(f"✅ 路径匹配正常: {ok_count} / {len(fe_calls)}")
