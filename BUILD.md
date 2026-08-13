# Code-Platform 企业级部署指南

## 📦 Docker镜像体系

### 方式一：完整镜像（推荐）

```bash
# 1. 构建基础镜像（包含所有Python依赖，首次约10-15分钟）
docker build -t code-platform-base:latest -f Dockerfile.base .

# 2. 构建应用镜像（快速，约1分钟）
docker build -t code-platform:latest .

# 3. 运行应用
docker run -d \
  --name code-platform \
  -p 8888:8888 \
  -e ADMIN_PASSWORD=your_admin_password \
  -e AGNES_API_KEY=your_agnes_key \
  -e SECRET_KEY=your_secret_key \
  -e ALLOWED_ORIGINS="http://your-domain.com" \
  code-platform:latest
```

### 方式二：本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际值

# 3. 运行应用
python backend/main.py
```

## 🔧 系统依赖

### macOS
```bash
brew install ffmpeg sox espeak portaudio
brew install font-noto-cjk font-wqy-zenhei
```

### Ubuntu/Debian
```bash
apt-get update
apt-get install -y ffmpeg sox espeak portaudio19-dev \
  fonts-noto-cjk fonts-wqy-zenhei \
  libjpeg-dev libpng-dev libwebp-dev
```

### CentOS/RHEL
```bash
yum install -y ffmpeg sox espeak portaudio-devel \
  google-noto-cjk-fonts wqy-zenhei-fonts \
  libjpeg-turbo-devel libpng-devel libwebp-devel
```

## 📊 企业级优化器

### 功能特性
- ✅ 代码质量优化（自动检测坏味道）
- ✅ 测试覆盖率提升
- ✅ API健康检查（每小时20分自动执行）
- ✅ 数据清理与备份
- ✅ 产出质量升级
- ✅ 安全加固检查
- ✅ 依赖更新检查
- ✅ 报告生成

### 调度配置
- **Cron表达式**: `20 * * * *`（每小时20分）
- **通知驱动**: 创建通知文件 → 守护进程检测 → 自动执行
- **Git集成**: 自动提交优化结果并推送

### API端点
```bash
# 查看优化状态
GET /api/optimizer/status

# 查看指标
GET /api/optimizer/metrics

# 查看报告
GET /api/optimizer/report

# 手动触发
POST /api/optimizer/run-now
```

## 🔒 安全配置

### 环境变量
```bash
# 必须设置
ADMIN_PASSWORD=your_strong_password
AGNES_API_KEY=your_agnes_api_key
SECRET_KEY=your_32_char_secret_key

# 可选
ALLOWED_ORIGINS=http://your-domain.com,http://localhost:5173
DATABASE_URL=sqlite:///backend/platform.db
```

### 文件权限
```bash
chmod 600 .env
chmod 600 backend/platform.db
```

## 📈 当前状态

| 指标 | 评分 | 状态 |
|------|------|------|
| 代码质量 | 91/100 | ✅ A级 |
| 测试覆盖 | 10/10 passed | ✅ |
| API健康 | 2/5正常 | ⚠️ 部分正常 |
| 安全加固 | 4/4通过 | ✅ |
| 依赖更新 | 10个过时 | ⚠️ |
| **总分** | **58/100** | **D级→C级** |

## 🚀 部署到其他服务器

```bash
# 1. 克隆仓库
git clone https://github.com/Ryan-myp/Code-Platform.git
cd Code-Platform

# 2. 构建镜像（如果有基础镜像）
docker pull code-platform-base:latest  # 如果有远程仓库
docker build -t code-platform:latest .

# 3. 运行容器
docker run -d \
  --name code-platform \
  -p 8888:8888 \
  -v /data/code-platform:/app/backend/backups \
  -e ADMIN_PASSWORD=xxx \
  -e AGNES_API_KEY=xxx \
  -e SECRET_KEY=xxx \
  code-platform:latest
```

## 📝 依赖清单

- **Python**: 288个包（FastAPI, Uvicorn, Torch, Transformers等）
- **系统**: ffmpeg 8.1, Sox, eSpeak, PortAudio, 中文字体
- **AI模型**: AGNES视频生成, LLM推理

## 🔄 自动优化流程

```
Cron (每小时20分)
    ↓
创建通知文件: notifications/optimizer_*.json
    ↓
守护进程检测 (每10秒)
    ↓
执行优化: 代码+测试+API+数据+安全+依赖
    ↓
生成报告: .optimizer_reports/*.json
    ↓
Git提交并推送
```

---

**最后更新**: 2026-08-13  
**版本**: v20.1
