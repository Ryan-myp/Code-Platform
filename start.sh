#!/bin/bash
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# ─── 颜色输出 ────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─── 加载环境变量 ────────────────────────────────────────────────
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    log_info "Loaded .env file"
else
    log_warn "No .env file found. Using defaults."
fi

# ─── 后端启动 ────────────────────────────────────────────────────
start_backend() {
    log_info "Starting backend on port 8888..."
    export AGNES_API_KEY="${AGNES_API_KEY:-}"
    cd "$PROJECT_ROOT/backend"
    nohup python3 main.py > /tmp/backend.log 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > /tmp/backend.pid
    log_info "Backend PID: $BACKEND_PID"
}

# ─── 前端启动 ────────────────────────────────────────────────────
start_frontend() {
    log_info "Starting frontend on port 5173..."
    cd "$PROJECT_ROOT/frontend"
    if command -v nvm &> /dev/null; then
        export NVM_DIR="$HOME/.nvm"
        [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
        nvm use 18 >/dev/null 2>&1 || true
    fi
    nohup npm run dev > /tmp/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > /tmp/frontend.pid
    log_info "Frontend PID: $FRONTEND_PID"
}

# ─── 停止服务 ────────────────────────────────────────────────────
stop_services() {
    log_info "Stopping services..."

    # 停止后端
    if [ -f /tmp/backend.pid ]; then
        BACKEND_PID=$(cat /tmp/backend.pid)
        kill "$BACKEND_PID" 2>/dev/null || true
        rm -f /tmp/backend.pid
        log_info "Backend stopped (PID: $BACKEND_PID)"
    fi

    # 停止前端
    if [ -f /tmp/frontend.pid ]; then
        FRONTEND_PID=$(cat /tmp/frontend.pid)
        kill "$FRONTEND_PID" 2>/dev/null || true
        rm -f /tmp/frontend.pid
        log_info "Frontend stopped (PID: $FRONTEND_PID)"
    fi

    # 额外清理：按端口杀进程
    lsof -ti:8888 | xargs kill 2>/dev/null || true
    lsof -ti:5173 | xargs kill 2>/dev/null || true
}

# ─── 检查状态 ────────────────────────────────────────────────────
check_status() {
    log_info "Checking service status..."
    if lsof -ti:8888 >/dev/null 2>&1; then
        log_info "Backend is running on port 8888 ✓"
    else
        log_error "Backend is NOT running on port 8888 ✗"
    fi
    if lsof -ti:5173 >/dev/null 2>&1; then
        log_info "Frontend is running on port 5173 ✓"
    else
        log_error "Frontend is NOT running on port 5173 ✗"
    fi
}

# ─── 主逻辑 ──────────────────────────────────────────────────────
case "${1:-start}" in
    start)
        start_backend
        sleep 1
        start_frontend
        sleep 2
        check_status
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 1
        start_backend
        sleep 1
        start_frontend
        sleep 2
        check_status
        ;;
    status)
        check_status
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
