# ─── 智能研发平台 Makefile ──────────────────────────────────────
.PHONY: help install backend frontend dev test lint format clean docker-up docker-down reset-db

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 安装所有依赖（后端 + 前端）
	@echo "Installing backend dependencies..."
	pip install -r backend/requirements.txt
	pip install ruff pytest pytest-asyncio pytest-cov httpx
	@echo "Installing frontend dependencies..."
	cd frontend && npm ci

backend: ## 启动后端服务
	@echo "Starting backend on port 8888..."
	cd backend && python main.py

frontend: ## 启动前端开发服务器
	@echo "Starting frontend on port 5173..."
	cd frontend && npm run dev

dev: ## 同时启动前后端（前台运行，方便调试）
	@echo "Starting both backend and frontend..."
	$(MAKE) -j2 backend frontend

test: ## 运行所有测试
	@echo "Running tests..."
	pytest tests/ -v --cov=backend --cov-report=term-missing

test-unit: ## 运行单元测试
	@echo "Running unit tests..."
	pytest tests/unit/ -v

test-integration: ## 运行集成测试
	@echo "Running integration tests..."
	pytest tests/integration/ -v

test-coverage: ## 运行测试并生成覆盖率报告
	@echo "Running tests with coverage..."
	pytest tests/ -v --cov=backend --cov-report=html --cov-report=term-missing
	@echo "Open htmlcov/index.html to view report"

lint: ## 运行代码质量检查
	@echo "Running ruff (backend)..."
	ruff check backend/
	@echo "Running ESLint (frontend)..."
	cd frontend && npx eslint src/ || true

format: ## 格式化代码
	@echo "Formatting backend (ruff)..."
	ruff format backend/
	ruff check --fix backend/
	@echo "Formatting frontend (prettier)..."
	cd frontend && npx prettier --write "src/**/*.{js,jsx,ts,tsx,css}" || true

check: lint format ## 运行 lint + format 检查（不修改文件）
	@echo "All checks passed!"

docker-build: ## 构建 Docker 镜像
	@echo "Building Docker images..."
	docker compose build

docker-up: ## 启动 Docker 容器
	@echo "Starting Docker containers..."
	docker compose up -d

docker-down: ## 停止 Docker 容器
	@echo "Stopping Docker containers..."
	docker compose down

docker-logs: ## 查看容器日志
	docker compose logs -f

docker-restart: ## 重启 Docker 容器
	docker compose restart

reset-db: ## 重置数据库（⚠️ 删除所有数据）
	@echo "WARNING: This will delete all data!"
	@read -p "Type 'yes' to confirm: " answer && [ "$$answer" = "yes" ] || (echo "Aborted"; exit 1)
	rm -f backend/platform.db data/platform.db platform.db
	@echo "Database reset complete"

setup-env: ## 创建 .env 文件（从示例复制）
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env file created. Please edit it with your settings."; \
	else \
		echo ".env file already exists."; \
	fi

clean: ## 清理构建产物和缓存
	@echo "Cleaning..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache/ htmlcov/ .coverage coverage.xml
	cd frontend && rm -rf node_modules/ dist/
	@echo "Clean complete"
