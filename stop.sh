#!/bin/bash
# 智能研发平台停止脚本
# 用法: ./stop.sh

echo "========================================"
echo "  AI 智能研发平台 - 停止服务"
echo "========================================"

# 清理端口占用
PORTS=(8888 5173)
for PORT in "${PORTS[@]}"; do
    PID=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ ! -z "$PID" ]; then
        echo "  关闭端口 $PORT (PID: $PID)"
        kill -9 $PID 2>/dev/null || true
    fi
done

sleep 1
echo ""
echo "✅ 所有服务已停止"
echo "========================================"
