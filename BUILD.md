# 构建与部署指南

## 🚀 快速开始

### 方式一：基础镜像 + 应用镜像（推荐生产环境）

```bash
# 1. 构建基础镜像（包含所有Python依赖和系统工具）
docker build -t code-platform-base:latest -f Dockerfile.base .

# 2. 构建应用镜像
docker build -t code-platform:latest .

# 3. 运行应用
docker run -d \
  --name code-platform \
  -p 8888:8888 \
  -e ADMIN_PASSWORD=your_secure_password \
  -e AGNES_API_KEY=your_agnes_key \
  -e DASHSCOPE_API_KEY=your_dashscope_key \
  -e SECRET_KEY=your_random_secret_key \
  -v $(pwd)/backend/platform.db:/data/platform.db \
  code-platform:latest
```

### 方式二：使用 Docker Compose

```bash
# 1. 构建基础镜像
docker compose --profile base up -d

# 2. 构建并运行应用
docker compose --profile app up -d

# 3. 查看状态
docker compose --profile app logs -f
```

### 方式三：单镜像（简单测试）

```bash
# 直接构建完整镜像（不需要基础镜像）
docker build -t code-platform:latest .

# 运行
docker run -d --name code-platform -p 8888:8888 code-platform:latest
```

## 📋 环境变量

| 变量名 | 说明 | 默认值 | 必填 |
|--------|------|--------|------|
| `ADMIN_PASSWORD` | 管理员密码 | `admin123` | ❌ |
| `AGNES_API_KEY` | AGNES AI API密钥 | `` | ❌ |
| `DASHSCOPE_API_KEY` | 百炼API密钥 | `` | ❌ |
| `SECRET_KEY` | JWT密钥 | `change-me-in-production` | ✅ 生产环境 |
| `APP_ENV` | 环境 | `production` | ❌ |
| `DATABASE_URL` | 数据库URL | `sqlite:///./backend/platform.db` | ❌ |

## 📦 依赖清单

### Python依赖（289个）
- **Web框架**: FastAPI, Uvicorn, Starlette
- **TTS语音**: edge-tts, pyttsx3, gTTS
- **视频处理**: imageio-ffmpeg, ffmpeg-python
- **AI/ML**: openai, torch, transformers
- **数据处理**: pandas, numpy, sqlalchemy
- **图像处理**: pillow, opencv-python
- **其他**: pydantic, httpx, requests

### 系统依赖
- **FFmpeg**: 视频编解码（核心依赖）
- **SoX**: 音频处理
- **eSpeak**: 语音合成
- **SQLite**: 数据库
- **中文字体**: fonts-noto-cjk, fonts-wqy-zenhei

## 🔄 构建优化

### 使用缓存加速构建

```bash
# 首次构建（较慢，约10-15分钟）
docker build -t code-platform-base:latest -f Dockerfile.base .

# 后续构建（使用缓存，更快）
docker build --cache-from code-platform-base:latest -t code-platform:latest .
```

### 推送到镜像仓库

```bash
# 登录Docker Hub
docker login

# 标签
docker tag code-platform-base:latest yourname/code-platform-base:latest
docker tag code-platform:latest yourname/code-platform:latest

# 推送
docker push yourname/code-platform-base:latest
docker push yourname/code-platform:latest
```

## 🐧 在其他Linux服务器部署

### 1. 拉取基础镜像

```bash
# 从Docker Hub拉取
docker pull yourname/code-platform-base:latest

# 或从私有仓库拉取
docker pull registry.example.com/code-platform-base:latest
```

### 2. 构建应用镜像（快速）

```bash
# 基础镜像已在本地，构建应用镜像会非常快
docker build -t code-platform:latest .
```

### 3. 运行应用

```bash
docker run -d \
  --name code-platform \
  -p 8888:8888 \
  -e ADMIN_PASSWORD=your_password \
  -e SECRET_KEY=your_secret \
  -v /data/platform.db:/data/platform.db \
  yourname/code-platform:latest
```

## 📊 监控与健康检查

```bash
# 查看容器状态
docker ps | grep code-platform

# 查看日志
docker logs -f code-platform

# 健康检查
curl http://localhost:8888/api/health

# 进入容器调试
docker exec -it code-platform bash

# 检查依赖
docker exec code-platform python -c "import edge_tts; print(edge_tts.__version__)"
docker exec code-platform ffmpeg -version | head -1
```

## 🔧 故障排除

### 问题：端口已被占用
```bash
# 检查端口
lsof -i :8888

# 停止现有容器
docker stop code-platform && docker rm code-platform

# 修改端口映射
docker run -p 8080:8888 code-platform:latest
```

### 问题：数据库锁定
```bash
# 检查数据库文件权限
ls -la backend/platform.db

# 修复权限
chmod 644 backend/platform.db
```

### 问题：依赖安装失败
```bash
# 清理Docker缓存重新构建
docker build --no-cache -t code-platform:latest .
```

### 问题：FFmpeg未找到
```bash
# 检查ffmpeg是否安装
docker exec code-platform which ffmpeg

# 如果没有，重新构建基础镜像
docker build -t code-platform-base:latest -f Dockerfile.base . --no-cache
```

## 📈 性能优化

### 减小镜像大小

```bash
# 使用多阶段构建（已内置）
# 最终镜像只包含运行时依赖，不包含构建工具

# 查看镜像大小
docker images | grep code-platform

# 清理悬空镜像
docker image prune -a
```

### 使用BuildKit加速

```bash
# 启用BuildKit
export DOCKER_BUILDKIT=1

# 构建
docker build -t code-platform:latest .
```

## 🎯 企业级部署建议

### 使用Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: code-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: code-platform
  template:
    metadata:
      labels:
        app: code-platform
    spec:
      containers:
      - name: code-platform
        image: yourname/code-platform:latest
        ports:
        - containerPort: 8888
        env:
        - name: ADMIN_PASSWORD
          valueFrom:
            secretKeyRef:
              name: code-platform-secrets
              key: admin-password
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: code-platform-secrets
              key: secret-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
---
apiVersion: v1
kind: Service
metadata:
  name: code-platform
spec:
  selector:
    app: code-platform
  ports:
  - port: 8888
    targetPort: 8888
  type: LoadBalancer
```

### 使用Nginx反向代理

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8888;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # 静态文件
    location /static/ {
        alias /app/frontend/dist/;
        expires 1y;
    }
}
```

## 📝 常见问题

### Q: 为什么需要基础镜像？
A: 基础镜像包含所有Python依赖（289个）和系统工具（ffmpeg、TTS等），构建一次后可以被多个应用镜像复用，大幅加速构建过程。

### Q: 镜像大小是多少？
A: 基础镜像约2-3GB（包含所有依赖），应用镜像在此基础上增加约500MB代码。

### Q: 如何在ARM架构（如树莓派）上运行？
A: 需要修改Dockerfile中的ffmpeg安装命令，使用ARM版本的预编译包。

### Q: 如何处理大文件上传？
A: 建议在docker-compose.yml中配置volume挂载，或使用对象存储（如S3）。

