# ===== 主应用镜像（多阶段构建）=====
#
# 构建方式：
#   docker build -t code-platform:latest .
#
# 运行方式：
#   docker run -p 8888:8888 -e ADMIN_PASSWORD=your_password code-platform:latest

# 阶段1：基于基础镜像（如果有的话）或从零构建
FROM code-platform-base:latest AS base

# 如果基础镜像不存在，则从零开始（自动fallback）
FROM python:3.13-slim AS fallback

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    ca-certificates \
    sqlite3 \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
COPY pyproject.toml .

# 创建虚拟环境并安装所有Python依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 阶段2：应用镜像
FROM base AS app

WORKDIR /app

# 复制应用代码
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY docs/ ./docs/
COPY tests/ ./tests/
COPY *.md .

# 创建必要目录
RUN mkdir -p backend/.optimizer_reports backend/backups backend/listener/notifications

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    DATABASE_URL=sqlite:///./backend/platform.db

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/health || exit 1

# 暴露端口
EXPOSE 8888

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888", "--log-level", "info"]
