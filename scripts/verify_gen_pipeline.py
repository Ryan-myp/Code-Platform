"""通用化流水线端到端验证：node 多文件工程 → 落盘 → 测试门禁 → 构建部署。

验证 _create_deploy_pipeline 的完整链路（语言无关性），输出逐步日志。
用法: python scripts/verify_gen_pipeline.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import extended_api as E

NODE_CODE = """```javascript server.js
const express = require('express');
const app = express();
app.get('/', (req, res) => res.json({ ok: true, service: 'node-demo' }));
app.get('/api/hello', (req, res) => res.json({ message: 'hello from node' }));
const port = process.env.PORT || 8000;
app.listen(port, () => console.log(`listening on ${port}`));
```
```javascript test_api.test.js
const { test, before, after } = require('node:test');
const assert = require('node:assert');
const { spawn } = require('child_process');
let proc, base;
before(() => {
  const port = process.env.TEST_PORT || '8911';
  base = `http://127.0.0.1:${port}`;
  proc = spawn(process.execPath, ['server.js'], { env: { ...process.env, PORT: port }, stdio: 'ignore' });
});
after(() => proc && proc.kill());
test('root returns 200', async () => {
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch(base + '/'); if (r.status === 200) return; } catch (e) {}
    await new Promise(r => setTimeout(r, 500));
  }
  assert.fail('service not ready');
});
test('hello api', async () => {
  const r = await fetch(base + '/api/hello');
  assert.equal(r.status, 200);
  const body = await r.json();
  assert.equal(body.message, 'hello from node');
});
```"""


def main():
    name = "node-demo"
    pid, run_id, port = E._create_deploy_pipeline(name, NODE_CODE, "", "verify")
    print(f"pipeline: {pid}, run: {run_id}, port: {port}")
    project_dir = os.path.join(E.ARTIFACTS_DIR, name)
    print("落盘文件:", sorted(os.listdir(project_dir)))
    # 轮询流水线日志直到结束
    conn = E.get_db()
    try:
        for i in range(300):  # 最多 25 分钟
            time.sleep(5)
            row = conn.execute("SELECT status, log FROM pipeline_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                break
            if i % 6 == 0:
                print(f"--- [{i * 5}s] status={row['status']} ---")
                print((row["log"] or "")[-1200:])
            if row["status"] in ("success", "failed"):
                print(f"=== FINAL: {row['status']} ===")
                print(row["log"] or "")
                return 0 if row["status"] == "success" else 1
    finally:
        conn.close()
    print("超时未结束")
    return 1


if __name__ == "__main__":
    sys.exit(main())
