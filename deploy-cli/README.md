# 小团智能平台 — npx 一键部署

AI 驱动的智能研发与创作平台（FastAPI + React），**无需购买服务器**，通过 npx 一键在本地/任何 Node 环境启动完整服务。

## 快速开始

```bash
# 完整启动（前端 + 后端）
npx @xiaotuan/code-platform web

# 指定端口
npx @xiaotuan/code-platform web --port 3000 --backend-port 8888

# 仅启动后端
npx @xiaotuan/code-platform backend

# 仅启动前端（对接已有后端）
npx @xiaotuan/code-platform frontend --api http://127.0.0.1:8888

# 环境检查
npx @xiaotuan/code-platform doctor
```

## 工作原理

```
npx @xiaotuan/code-platform web
  ├─ ① 检测系统 Python 3.10+
  ├─ ② 引导/复用 .venv（首次自动 pip install requirements.txt）
  ├─ ③ 启动 Python 后端（FastAPI :8888）
  └─ ④ 启动前端静态服务（内置 dist，SPA fallback + /api 反向代理）
```

参考 DeepSeek Harness（`npx @deepseek-ai/dsh web`）的部署模式：
- CLI 是**纯 Node.js 引导器**，零平台二进制
- 前端 dist 内置于 npm 包（Vite 构建产物 ~7MB）
- Python 环境本地管理（venv），不打包重型依赖
- 前端 API 同源部署（`/api` 相对路径），免 CORS

## 部署到云端（可选）

npx 包天然可在任何 Node 环境运行：

```bash
# 云服务器 / GitHub Codespaces / 免费 Node 沙箱
npx @xiaotuan/code-platform web --port 8080
```

配合 pm2/forever 可后台常驻：

```bash
npm i -g pm2
pm2 start "npx @xiaotuan/code-platform web" --name code-platform
```

## 发布到 npm

```bash
cd deploy-cli
npm login
npm publish --access public
```

发布前确保：
1. `frontend-dist/` 已包含最新前端构建（`cd ../frontend && npx vite build`）
2. `package.json` 版本号已更新

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Node.js | >= 18 | npx 运行环境 |
| Python | >= 3.10 | 后端运行环境（首次自动建 venv） |
| ffmpeg | 可选 | 视频/音频处理（未装时相关功能降级） |

## 目录结构

```
deploy-cli/
├── package.json        # npm 包定义（bin: code-platform）
├── bin/cli.js          # npx 入口（Commander CLI）
├── lib/
│   ├── bootstrap.js    # Python 环境引导（venv + pip install）
│   ├── backend.js      # 后端启动 + 健康等待
│   └── server.js       # SPA 静态服务 + /api 反向代理
└── frontend-dist/      # 前端构建产物（Vite dist）
```
