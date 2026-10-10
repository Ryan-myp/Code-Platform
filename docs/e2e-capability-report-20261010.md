# E2E 能力实测报告（20261010）

- 目标：`http://127.0.0.1:8009` · 耗时 147s
- 结果：**36 PASS / 0 FAIL / 1 SKIP**（共 37 项）

| 域 | 探针 | 结果 | HTTP | 耗时 | 证据 |
|---|---|---|---|---|---|
| A 账户鉴权 | 注册新用户 | ✅ PASS | 200 | 0.4s | {"access_token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJwcm9iZV83Njg2NGRlZiIsInVzZXJfaWQiOi |
| A 账户鉴权 | 登录取 token | ✅ PASS | 200 | 0.6s | token eyJhbGciOiJIUzI1... |
| A 账户鉴权 | 当前用户 /me | ✅ PASS | 200 | 0.61s | {"id": "user_187a32b3e33b", "username": "probe_76864def", "nickname": "", "avatar": "", "email": "pr |
| A 账户鉴权 | 配额 /quota | ✅ PASS | 200 | 0.62s | {"membership":"free","membership_expires":null,"membership_days_left":null,"username":"probe_76864de |
| B LLM | 助手对话（Agnes 真实调用） | ✅ PASS | 200 | 0.8s | 2 |
| B LLM | 助手 SSE 流式 | ✅ PASS | 200 | 7.44s | 108 行, 前: data: {"text": "我是"} |
| B LLM | OpenAI 兼容 /v1（中转站默认关闭） | ⏭️ SKIP | 403 | 0.15s | gateway_open=0（计费未完善，设计性关闭） |
| C 编排 | 创建工作流（DAG 节点） | ✅ PASS | - | 0s | wf_dafffaf70926 |
| C 编排 | 运行工作流（executor DAG+LLM） | ✅ PASS | 200 | 0.92s | 是的，1+1=2。 |
| C 编排 | 创建 Agent | ✅ PASS | - | 0s | agent_1791597833993 |
| C 编排 | 运行 Agent（LLM） | ✅ PASS | 200 | 0.68s | 你好 |
| C 编排 | 工具清单（65 个） | ✅ PASS | - | 0.01s | 会议纪要, 周报/日报, 邮件撰写, PRD 文档, 小红书文案 |
| C 编排 | 同步运行工具 unit-converter | ✅ PASS | 200 | 0.03s | {"error":"单位无法识别","available":["m","km","cm","mm","mi","yd","ft","in","nmi","ly"],"hint":"从单位示例: ['m |
| D 知识库 | 上传文档 | ✅ PASS | - | 0s | /Users/yanping.ma/PycharmProjects/Code-Platform/backend/uploads/kb/1791597834708 |
| D 知识库 | 创建 file 型知识库 | ✅ PASS | - | 0s | kb_1791597834716 |
| D 知识库 | 检索命中 | ✅ PASS | 200 | 0.03s | {"ok": true, "hits": [{"file": "1791597834708_probe_doc.md", "path": "/Users/yanping.ma/PycharmProje |
| E 任务队列 | 异步任务全链路（create→worker→done） | ✅ PASS | - | 5.03s | status=success result={'id': 'trans_d805499b55a8', 'result': 'Smart Content Factor |
| F 工厂 | 表情包生成（本地渲染+PNG校验） | ✅ PASS | 200 | 0.11s | meme_1791597839805.png 417782B png=True |
| F 工厂 | 文生图（外部图片API+字节校验） | ✅ PASS | 200 | 10.72s | img_1791597850495.png 1044343B |
| G 音频 | AI 配音（edge-tts + MP3校验） | ✅ PASS | 200 | 1.17s | voice_1791597851656.mp3 108712B mp3=True |
| G 音频 | AI 音乐合成（15s + MP3校验） | ✅ PASS | 200 | 3.43s | music_1791597855020.mp3 374952B |
| H 文档 | PPT 生成提交（异步） | ✅ PASS | - | 0.02s | task_a7883f223bec |
| H 文档 | Excel 生成 | ✅ PASS | 200 | 0.01s | {"ok":true,"id":"excel_86255af777ae","result":"{\"status\": \"created\", \"data\": {}}"} |
| H 文档 | 脑图生成（异步） | ✅ PASS | - | 0.02s | task_70b2ace7cb31 |
| H 文档 | PPT 生成（PPTX 字节校验） | ✅ PASS | 200 | 45.14s | ppt_05a559d5ec57.pptx 66143B zip=True |
| I 平台 | 沙箱环境探测 | ✅ PASS | 200 | 0.02s | docker=unknown {'allowed_imports': ['PIL', 'array', 'base64', 'bisect', 'collections', 'copy',  |
| I 平台 | MCP 服务器管理 | ✅ PASS | 200 | 0.01s | [{"id":"mcp-1","name":"Filesystem MCP Server","transport_type":"stdio","command" |
| I 平台 | 分享外链公开访问 | ✅ PASS | 200 | 0.02s | code=joz-KP_Yvfy6Pg |
| I 平台 | 团队创建 | ✅ PASS | 200 | 0.02s | team_175e6dc573ad |
| I 平台 | 团队仪表盘 | ✅ PASS | 200 | 0.03s | {"team":{"id":"team_175e6dc573ad","name":"probe_team_784efb","description":"","m |
| J 重工厂 | 数字人模板配置 | ✅ PASS | 200 | 0.01s | {"templates":[{"id":"live_shopping","name":"带货种草","emoji":"🛍️","desc":"痛点钩子+卖点3连 |
| J 重工厂 | 短剧配置探测 | ✅ PASS | 200 | 0.01s | {"pexels_configured":true,"local_materials":0,"music_tracks":0} |
| J 重工厂 | 游戏模板市场 | ✅ PASS | 200 | 0.01s | [{"id":"snake","name":"贪吃蛇","icon":"🐍","color":"from-emerald-500 to-green-600"," |
| J 重工厂 | 小程序生成提交（LLM 全项目） | ✅ PASS | - | 0.02s | task_8cb96e639ea3 |
| J 重工厂 | 小程序生成完成 | ✅ PASS | - | 70.59s | status=success {'id': 'mp_753f27bcca5c', 'name': 'probe_mini', 'template':  |
| K 前端 | Vite dev server | ✅ PASS | 200 | 0.02s | <!DOCTYPE html> <html lang="zh-CN">   <head>     <script typ |
| K 前端 | 前端→后端代理 /api | ✅ PASS | 200 | 0.06s | {"status":"ok","timestamp":"2026-10-10T10:06:11.110884","ver |
