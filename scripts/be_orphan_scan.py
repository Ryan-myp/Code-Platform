#!/usr/bin/env python3
"""反向对照：后端路由中从未被前端调用的孤儿接口扫描。"""
import json, re, os, urllib.request

spec = json.load(urllib.request.urlopen('http://127.0.0.1:8888/openapi.json'))
backend_paths = set(spec['paths'].keys())

# 前端调用（静态 + 模板，覆盖 api./callApi/.post/fetch 等封装）
fe = set()
PATTERNS = [
    r"api\.(?:get|post|put|delete|patch)\(\s*(['\"])(/api/[^'\"]*)\1",
    r"callApi\(\s*(['\"])(/api/[^'\"]*)\1",
    r"\.(?:get|post|put|delete|patch)\(\s*(['\"])(/api/[^'\"]*)\1",
    r"fetch\(\s*(['\"])([^'\"]*api[^'\"]*)\1",
    r"(?:src|href)=?[({]?\s*([`'\"])([^`'\"]*api[^`'\"]*)\1",
]
for root, dirs, files in os.walk('frontend/src'):
    for fn in files:
        if not fn.endswith(('.jsx', '.js')) or fn.endswith('.test.js'):
            continue
        src = open(os.path.join(root, fn)).read()
        for pat in PATTERNS:
            for m in re.finditer(pat, src, re.S):
                p = (m.group(2) or m.group(3) or '').strip()
                if p.startswith('/api/'):
                    fe.add(p.split('?')[0])
        for m in re.finditer(r"api\.(?:get|post|put|delete|patch)\(\s*`([^`]*)`", src):
            p = m.group(1)
            if p.startswith('/api/'):
                fe.add(p.split('?')[0])

def to_regex(path):
    return '^' + ''.join(
        r'[^/]+' if p.startswith('${') else re.escape(p)
        for p in re.split(r'(\$\{[^}]+\})', path)
    ) + '$'

fe_matched = set()
for p in fe:
    rx = to_regex(p)
    for b in backend_paths:
        if re.match(rx, b):
            fe_matched.add(b)

unused = sorted(backend_paths - fe_matched)
print(f"后端路由: {len(backend_paths)} | 前端可达: {len(fe_matched)} | 疑似孤儿: {len(unused)}\n")
for u in unused:
    print(f"  {u}  ->  {sorted(spec['paths'][u].keys())}")
