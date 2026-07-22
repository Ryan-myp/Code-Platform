#!/bin/bash
# 智能研发平台启动脚本
# 用法: ./start.sh

echo "========================================"
echo "  AI 智能研发平台 - 启动服务"
echo "========================================"

PROJECT_DIR="$HOME/PycharmProjects/Code-Platform"

# 1. 清理端口占用
echo ""
echo "[1/3] 清理端口占用..."
for PORT in 8888 5173; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ ! -z "$PID" ]; then
        echo "  关闭端口 $PORT (PID: $PID)"
        kill -9 $PID 2>/dev/null || true
    fi
done
sleep 1

# 2. 启动后端
echo ""
echo "[2/3] 启动后端服务 (port: 8888)..."
cd "$PROJECT_DIR/backend"
AGNES_API_KEY=*** /usr/local/bin/python3.13 -m uvicorn main:app --host 0.0.0.0 --port 8888 &
BACKEND_PID=$!
echo "  后端 PID: $BACKEND_PID"

# 等待后端启动
sleep 3
curl -s http://localhost:8888/api/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ 后端启动成功"
else
    echo "  ❌ 后端启动失败"
    exit 1
fi

# 3. 启动前端
echo ""
echo "[3/3] 启动前端服务 (port: 5173)..."
cd "$PROJECT_DIR/frontend"
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use 18 > /dev/null 2>&1
npm install > /dev/null 2>&1
npm run dev &
FRONTEND_PID=$!
echo "  前端 PID: $FRONTEND_PID"

# 等待前端启动
sleep 5
curl -s http://localhost:5173 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  ✅ 前端启动成功"
else
    echo "  ⚠️  前端可能还在编译中，请稍候..."
fi

# 显示状态
echo ""
echo "========================================"
echo "  ✅ 服务已全部启动"
echo "========================================"
echo ""
echo "  前端访问: http://localhost:5173"
echo "  后端 API: http://localhost:8888"
echo "  Swagger:  http://localhost:8888/docs"
echo ""
echo "  后端 PID: $BACKEND_PID"
echo "  前端 PID: $FRONTEND_PID"
echo ""
echo "  停止服务: 运行 ./stop.sh 或 kill $BACKEND_PID $FRONTEND_PID"
echo "========================================"
