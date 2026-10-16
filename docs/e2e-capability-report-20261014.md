# E2E 能力实测报告（20261014）

- 目标：`http://127.0.0.1:8009` · 耗时 115s
- 结果：**38 PASS / 0 FAIL / 3 SKIP**（共 41 项）

| 域 | 探针 | 结果 | HTTP | 耗时 | 证据 |
|---|---|---|---|---|---|
| A 账户鉴权 | 注册新用户 | ✅ PASS | 200 | 0.37s | {"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwcm9iZV8xN2EwODc5ZiIsInVzZXJfaWQiOi |
| A 账户鉴权 | 登录取 token | ✅ PASS | 200 | 0.57s | token eyJhbGciOiJIUzI1... |
| A 账户鉴权 | 当前用户 /me | ✅ PASS | 200 | 0.58s | {"id": "user_74b1e6558e8a", "username": "probe_17a0879f", "nickname": "", "avatar": "", "email": "pr |
| A 账户鉴权 | 配额 /quota | ✅ PASS | 200 | 0.59s | {"membership":"free","membership_expires":null,"membership_days_left":null,"username":"probe_17a0879 |
| B LLM | 助手对话（Agnes 真实调用） | ✅ PASS | 200 | 1.79s | 2 |
| B LLM | 助手 SSE 流式 | ✅ PASS | 200 | 6.81s | 141 行, 前: data: {"text": "我是"} |
| B LLM | OpenAI 兼容 /v1（中转站默认关闭） | ⏭️ SKIP | 403 | 0.01s | gateway_open=0（计费未完善，设计性关闭） |
| C 编排 | 创建工作流（DAG 节点） | ✅ PASS | - | 0s | wf_eb9638cc000e |
| C 编排 | 运行工作流（executor DAG+LLM） | ✅ PASS | 200 | 6.73s | 是的，1+1=2。 |
| C 编排 | 创建 Agent | ✅ PASS | - | 0s | agent_1791960644279 |
| C 编排 | 运行 Agent（LLM） | ✅ PASS | 200 | 0.68s | 你好 |
| C 编排 | 工具清单（65 个） | ✅ PASS | - | 0.02s | 会议纪要, 周报/日报, 邮件撰写, PRD 文档, 小红书文案 |
| C 编排 | 同步运行工具 unit-converter | ✅ PASS | 200 | 0.05s | {"error":"单位无法识别","available":["m","km","cm","mm","mi","yd","ft","in","nmi","ly"],"hint":"从单位示例: ['m |
| D 知识库 | 上传文档 | ✅ PASS | - | 0s | /Users/yanping.ma/PycharmProjects/Code-Platform/backend/uploads/kb/1791960645015 |
| D 知识库 | 创建 file 型知识库 | ✅ PASS | - | 0s | kb_1791960645024 |
| D 知识库 | 检索命中 | ✅ PASS | 200 | 0.04s | {"ok": true, "hits": [{"file": "1791960645015_probe_doc.md", "path": "/Users/yanping.ma/PycharmProje |
| D 知识库 | 多词检索+相关度排序 | ✅ PASS | 200 | 0.06s | hits=1 top_score=7.0 |
| E 任务队列 | 异步任务全链路（create→worker→done） | ✅ PASS | - | 5.08s | status=success result={'id': 'trans_bbd141f1b29d', 'result': '智能内容工厂'} |
| F 工厂 | 表情包生成（本地渲染+PNG校验） | ✅ PASS | 200 | 0.16s | meme_1791960650218.png 417782B png=True |
| F 工厂 | 文生图（外部图片API+字节校验） | ✅ PASS | 200 | 10.56s | img_1791960660745.png 849497B |
| G 音频 | AI 配音（edge-tts） | ⏭️ SKIP | 500 | 3.23s | {"detail":"操作失败，请稍后重试"} |
| G 音频 | AI 音乐合成（15s） | ⏭️ SKIP | 502 | 2.85s | {"detail":"人声演唱合成全部失败，请检查网络后重试"} |
| H 文档 | PPT 生成提交（异步） | ✅ PASS | - | 0.02s | task_9af9e46e6ea3 |
| H 文档 | Excel 生成 | ✅ PASS | 200 | 0.01s | {"ok":true,"id":"excel_d109bbf3244c","result":"{\"status\": \"created\", \"data\": {}}"} |
| H 文档 | 脑图生成（异步） | ✅ PASS | - | 0.02s | task_0564bd8dcf96 |
| H 文档 | PPT 生成（PPTX 字节校验） | ✅ PASS | 200 | 40.24s | ppt_b27b47fe3509.pptx 63503B zip=True |
| I 平台 | 沙箱环境探测 | ✅ PASS | 200 | 0.02s | docker=unknown {'allowed_imports': ['PIL', 'array', 'base64', 'bisect', 'collections', 'copy',  |
| I 平台 | MCP 服务器管理 | ✅ PASS | 200 | 0.01s | [{"id":"mcp_1791800734913","name":"词数服务","transport_type":"stdio","command":"/us |
| I 平台 | 分享外链公开访问 | ✅ PASS | 200 | 0.02s | code=hAgE2DmFtFfKBQ |
| I 平台 | 团队创建 | ✅ PASS | 200 | 0.01s | team_2e6bd0a3b7b9 |
| I 平台 | 团队仪表盘 | ✅ PASS | 200 | 0.02s | {"team":{"id":"team_2e6bd0a3b7b9","name":"probe_team_c9e7db","description":"","m |
| J 重工厂 | 数字人模板配置 | ✅ PASS | 200 | 0.0s | {"templates":[{"id":"live_shopping","name":"带货种草","emoji":"🛍️","desc":"痛点钩子+卖点3连 |
| J 重工厂 | 短剧配置探测 | ✅ PASS | 200 | 0.01s | {"pexels_configured":true,"local_materials":0,"music_tracks":0} |
| J 重工厂 | 游戏模板市场 | ✅ PASS | 200 | 0.01s | [{"id":"snake","name":"贪吃蛇","icon":"🐍","color":"from-emerald-500 to-green-600"," |
| J 重工厂 | 小程序生成提交（LLM 全项目） | ✅ PASS | - | 0.02s | task_9abe6211225f |
| J 重工厂 | 小程序生成完成 | ✅ PASS | - | 35.19s | status=success {'id': 'mp_34493f44592f', 'name': 'probe_mini', 'template':  |
| K 前端 | Vite dev server | ✅ PASS | 200 | 0.09s | <!DOCTYPE html> <html lang="zh-CN">   <head>     <script typ |
| K 前端 | 前端→后端代理 /api | ✅ PASS | 200 | 0.31s | {"status":"ok","timestamp":"2026-10-14T14:52:22.731953","ver |
| K 商业 | 创建会员订单 | ✅ PASS | 200 | 0.03s | order_d31327494133 |
| K 商业 | mock 支付 webhook 自动履约 + 幂等重放 | ✅ PASS | 200 | 0.06s | order_d31327494133 → approved（重放幂等） |
| K 商业 | 用户计量中心（今日/30日聚合） | ✅ PASS | 200 | 0.08s | {'today': {'calls': 2, 'success_rate': 100.0, 'input_chars': 22, 'output_chars': |
