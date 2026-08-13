# 构建与部署指南

## 🚀 快速开始

### 方式一：基础镜像 + 应用镜像（推荐生产环境）

```bash
# 1. 构建基础镜像（包含所有Python依赖）
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

## 🔄 构建优化

### 使用缓存加速构建

```bash
# 首次构建（较慢）
docker build -t code-platform:latest .

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

## 📈 性能优化

### 减小镜像大小

```bash
# 使用多阶段构建（已内置）
# 最终镜像只包含运行时依赖，不包含构建工具

# 查看镜像大小
docker images | grep code-platform
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
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
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
}
```

