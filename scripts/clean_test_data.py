"""清理平台可见的测试/残留数据（scan4 审查发现）。
用法：python3 clean_test_data.py [--apply]
不带参数时仅预览将删除的记录；加 --apply 执行删除。
"""
import sqlite3
import sys

DB = "platform.db"
APPLY = "--apply" in sys.argv

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# (表, 过滤SQL, 参数, 说明)
TARGETS = [
    (
        "publish_records",
        "title LIKE '%测试%' OR title LIKE '%验证%' OR title LIKE '%批量取消%'",
        (),
        "发布记录中的测试标题",
    ),
    (
        "publish_accounts",
        "name LIKE '%主号%' OR name LIKE '%矩阵号%' OR app_id LIKE 'app%' OR app_id LIKE 'id%'",
        (),
        "账号配置中的测试账号",
    ),
    ("competitors", "name LIKE '%测试%'", (), "竞品监控中的测试竞品"),
    ("user_templates", "name LIKE '%测试%'", (), "模板市场中的测试模板"),
    ("copywriting_tasks", "title = '测试文案'", (), "素材库中的测试文案"),
    ("copywriting_tasks", "title = 'google'", (), "素材库中的测试条目"),
]

total = 0
for table, where, params, desc in TARGETS:
    try:
        rows = conn.execute(f"SELECT * FROM {table} WHERE {where}", params).fetchall()
    except sqlite3.Error as e:
        print(f"[跳过] {desc}: {e}")
        continue
    if not rows:
        print(f"[无] {desc}")
        continue
    print(f"[{len(rows)}条] {desc}（{table}）:")
    for r in rows:
        d = dict(r)
        title = str(d.get("title") or d.get("name") or "")[:40]
        print(f"   id={d.get('id')} | {title}")
    total += len(rows)
    if APPLY:
        conn.execute(f"DELETE FROM {table} WHERE {where}", params)

if APPLY:
    conn.commit()
    print(f"\n已删除 {total} 条记录并提交")
else:
    print(f"\n共 {total} 条待删除，加 --apply 执行（预览模式未改动数据）")

conn.close()
