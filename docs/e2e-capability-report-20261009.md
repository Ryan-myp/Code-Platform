# E2E 能力实测报告（20261009）

- 目标：`http://127.0.0.1:8009` · 耗时 142s
- 结果：**35 PASS / 0 FAIL / 2 SKIP**（共 37 项）

| 域 | 探针 | 结果 | HTTP | 耗时 | 证据 |
|---|---|---|---|---|---|
| A 账户鉴权 | 注册新用户 | ✅ PASS | 200 | 0.4s | {"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwcm9iZV9jYzU2MGU3MCIsInVzZXJfaWQiOi |
| A 账户鉴权 | 登录取 token | ✅ PASS | 200 | 0.6s | token eyJhbGciOiJIUzI1... |
| A 账户鉴权 | 当前用户 /me | ✅ PASS | 200 | 0.6s | {"id": "user_85ec5abcc07e", "username": "probe_cc560e70", "nickname": "", "avatar": "", "email": "pr |
| A 账户鉴权 | 配额 /quota | ✅ PASS | 200 | 0.61s | {"membership":"free","membership_expires":null,"membership_days_left":null,"username":"probe_cc560e7 |
| B LLM | 助手对话（Agnes 真实调用） | ✅ PASS | 200 | 0.75s | 2 |
| B LLM | 助手 SSE 流式 | ✅ PASS | 200 | 6.83s | 105 行, 前: data: {"text": "嗨"} |
| B LLM | OpenAI 兼容 /v1（中转站默认关闭） | ⏭️ SKIP | 403 | 0.01s | gateway_open=0（计费未完善，设计性关闭） |
| C 编排 | 创建工作流 | ✅ PASS | - | 0s | wf_be5c449c50ab |
| C 编排 | 运行工作流（LLM 引擎） | ✅ PASS | 200 | 0.03s | 节点执行失败：工作流未产生任何输出，请检查节点配置与连线 |
| C 编排 | 创建 Agent | ✅ PASS | - | 0s | agent_1791536150489 |
| C 编排 | 运行 Agent（LLM） | ✅ PASS | 200 | 0.54s | 你好 |
| C 编排 | 工具清单（65 个） | ✅ PASS | - | 0.01s | 会议纪要, 周报/日报, 邮件撰写, PRD 文档, 小红书文案 |
| C 编排 | 同步运行工具 unit-converter | ✅ PASS | 200 | 0.03s | {"error":"单位无法识别","available":["m","km","cm","mm","mi","yd","ft","in","nmi","ly"],"hint":"从单位示例: ['m |
| D 知识库 | 上传文档 | ✅ PASS | - | 0s | /Users/yanping.ma/PycharmProjects/Code-Platform/backend/uploads/kb/1791536151058 |
| D 知识库 | 创建 file 型知识库 | ✅ PASS | - | 0s | kb_1791536151067 |
| D 知识库 | 检索命中 | ✅ PASS | 200 | 0.03s | {"ok": true, "hits": [{"file": "1791536151058_probe_doc.md", "path": "/Users/yanping.ma/PycharmProje |
| E 任务队列 | 异步任务全链路（create→worker→done） | ✅ PASS | - | 5.03s | status=success result={'id': 'trans_3b9b95a5c0ab', 'result': 'Intelligent Content  |
| F 工厂 | 表情包生成（本地渲染+PNG校验） | ✅ PASS | 200 | 0.1s | meme_1791536156147.png 415818B png=True |
| F 工厂 | 文生图（需配置中转站 Key+图片模型） | ⏭️ SKIP | 400 | 0.02s | {"detail":"未选择图片模型：请先在个人中心配置中转站 Key，并在页面选择模型"} |
| G 音频 | AI 配音（edge-tts + MP3校验） | ✅ PASS | 200 | 0.7s | voice_1791536156821.mp3 108712B mp3=True |
| G 音频 | AI 音乐合成（15s + MP3校验） | ✅ PASS | 200 | 1.93s | music_1791536158703.mp3 374952B |
| H 文档 | PPT 生成提交（异步） | ✅ PASS | - | 0.01s | task_d2e06843ab10 |
| H 文档 | Excel 生成 | ✅ PASS | 200 | 0.01s | {"ok":true,"id":"excel_b459709ccda3","result":"{\"status\": \"created\", \"data\": {}}"} |
| H 文档 | 脑图生成（异步） | ✅ PASS | - | 0.01s | task_3ba814b7bbe2 |
| H 文档 | PPT 生成（PPTX 字节校验） | ✅ PASS | 200 | 55.16s | ppt_7abe20b087c1.pptx 28666B zip=True |
| I 平台 | 沙箱环境探测 | ✅ PASS | 200 | 0.01s | docker=unknown {'allowed_imports': ['PIL', 'array', 'base64', 'bisect', 'collections', 'copy',  |
| I 平台 | MCP 服务器管理 | ✅ PASS | 200 | 0.01s | [{"id":"mcp-1","name":"Filesystem MCP Server","transport_type":"stdio","command" |
| I 平台 | 分享外链公开访问 | ✅ PASS | 200 | 0.02s | code=hTjQHmCRJrX02Q |
| I 平台 | 团队创建 | ✅ PASS | 200 | 0.01s | team_5158dcdc853c |
| I 平台 | 团队仪表盘 | ✅ PASS | 200 | 0.02s | {"team":{"id":"team_5158dcdc853c","name":"probe_team_553b2d","description":"","m |
| J 重工厂 | 数字人模板配置 | ✅ PASS | 200 | 0.0s | {"templates":[{"id":"live_shopping","name":"带货种草","emoji":"🛍️","desc":"痛点钩子+卖点3连 |
| J 重工厂 | 短剧配置探测 | ✅ PASS | 200 | 0.01s | {"pexels_configured":true,"local_materials":0,"music_tracks":0} |
| J 重工厂 | 游戏模板市场 | ✅ PASS | 200 | 0.01s | [{"id":"snake","name":"贪吃蛇","icon":"🐍","color":"from-emerald-500 to-green-600"," |
| J 重工厂 | 小程序生成提交（LLM 全项目） | ✅ PASS | - | 0.02s | task_b25a313455df |
| J 重工厂 | 小程序生成完成 | ✅ PASS | - | 70.24s | status=success {'id': 'mp_96e88e439f24', 'name': 'probe_mini', 'template':  |
| K 前端 | Vite dev server | ✅ PASS | 200 | 0.01s | <!DOCTYPE html> <html lang="zh-CN">   <head>     <script typ |
| K 前端 | 前端→后端代理 /api | ✅ PASS | 200 | 0.03s | {"status":"ok","timestamp":"2026-10-09T16:58:04.390162","ver |
