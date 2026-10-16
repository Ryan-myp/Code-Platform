"""一次性脚本：为 Meta Marketing 工作流 wf_1dd4ebd6775f 增加 start 节点参数化。

- 备份 DB
- 在 workflow_versions 表快照当前状态（与 update_workflow API 行为一致）
- 更新 workflows.steps / connections：
  * 新增 n_start（start 节点，fields: doc_url / focus / ad_account_id）
  * n_doc.url → ${n_start.result.doc_url}
  * n_struct / n_example 提示词引用 ${n_start.result.focus} / ${n_start.result.ad_account_id}
  * 新边 n_start → n_doc（其余边不变）
- 校验新图可被 executor 的 _build_dag 解析（start 入度 0，DAG 无环）
"""
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "backend" / "platform.db"
WF_ID = "wf_1dd4ebd6775f"

# 1) 备份
backup = DB.with_suffix(f".bak_{datetime.now():%Y%m%d%H%M%S}").with_suffix(".bak")
shutil.copy2(DB, backup)
print(f"backup -> {backup.name}")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM workflows WHERE id=?", (WF_ID,)).fetchone()
if not row:
    sys.exit(f"workflow {WF_ID} not found")

steps = json.loads(row["steps"])
connections = json.loads(row["connections"])

start_node = next((n for n in steps if n.get("type") == "start"), None)
if start_node:
    print("start 节点已存在，跳过幂等修改:", start_node.get("id"))
else:
    # 2) 版本快照（模仿 agent_api._snapshot_workflow_version，保留旧状态可回滚）
    ver = conn.execute(
        "SELECT COALESCE(MAX(version), 0) + 1 FROM workflow_versions WHERE workflow_id=?", (WF_ID,)
    ).fetchone()[0]
    conn.execute(
        """INSERT INTO workflow_versions
           (id, workflow_id, version, name, description, steps, connections, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            f"wfver_{WF_ID}_{ver}", WF_ID, ver, row["name"], row["description"] or "",
            row["steps"], row["connections"], datetime.now().isoformat(),
        ),
    )
    print(f"version snapshot v{ver} saved")

    # 3) 新增 start 节点 + 参数化引用
    steps.insert(0, {
        "id": "n_start",
        "type": "start",
        "label": "开始（入参）",
        "x": 40, "y": 320,
        "config": {"fields": [
            {"name": "doc_url", "label": "文档 URL",
             "default": "https://developers.facebook.com/docs/marketing-api"},
            {"name": "focus", "label": "分析重点",
             "default": "广告层级结构与广告创建示例"},
            {"name": "ad_account_id", "label": "广告账户 ID（act_ 后）",
             "default": "123456789"},
        ]},
    })
    for c in connections:
        if c["from"] == "n_doc" and c["to"] == "n_sum":
            c["id"] = "e0"
            break
    connections.insert(0, {"id": "e_in", "from": "n_start", "to": "n_doc"})

    for n in steps:
        if n.get("id") == "n_doc":
            n["config"]["url"] = "${n_start.result.doc_url}"
        elif n.get("id") == "n_struct":
            n["config"]["message"] = (
                "本次分析重点：" + "${n_start.result.focus}" + "。\n" + n["config"]["message"]
            )
        elif n.get("id") == "n_example":
            n["config"]["message"] = n["config"]["message"].replace(
                "{ad_account_id}", "${n_start.result.ad_account_id}")

    conn.execute(
        "UPDATE workflows SET steps=?, connections=? WHERE id=?",
        (json.dumps(steps), json.dumps(connections), WF_ID),
    )
    conn.commit()
    print("steps/connections updated")

# 4) 校验：executor 的 DAG 构建可解析
sys.path.insert(0, str(ROOT / "backend"))
from workflows.executor import WorkflowExecutor  # noqa: E402

new_steps = json.loads(conn.execute(
    "SELECT steps FROM workflows WHERE id=?", (WF_ID,)).fetchone()[0])
new_conns = json.loads(conn.execute(
    "SELECT connections FROM workflows WHERE id=?", (WF_ID,)).fetchone()[0])
adj, indeg = WorkflowExecutor()._build_dag(new_steps, new_conns)
assert indeg.get("n_start") == 0, f"start 入度应为 0: {indeg}"
assert len(indeg) == len(new_steps), "节点/入度数量不一致"
assert any(t == "n_doc" for t, _ in adj.get("n_start", [])), "n_start 未连到 n_doc"
from workflows.executor import _substitute  # noqa: E402
resolved = _substitute("${n_start.result.doc_url}",
                      {"n_start": {"result": {"doc_url": "https://example.com/docs"}}})
assert resolved == "https://example.com/docs", resolved
print("DAG + 占位符替换校验通过")
print(f"nodes: {[n['id'] for n in new_steps]}")
print(f"edges: {[c['id'] for c in new_conns]}")
