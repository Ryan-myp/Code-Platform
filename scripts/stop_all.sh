#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# 小团智能平台 · 停止本地 AI 引擎与服务
#
# 用法:
#   ./scripts/stop_all.sh             # 停止全部（voice_engine + acestep + backend）
#   ./scripts/stop_all.sh --engines   # 仅停止本地 AI 引擎（保留 backend）
#   ./scripts/stop_all.sh --backend   # 仅停止 backend
# ═══════════════════════════════════════════════════════════════════
set -u
MODE="all"
for arg in "$@"; do
    case "$arg" in
        --engines) MODE="engines" ;;
        --backend) MODE="backend" ;;
        -h|--help) head -12 "$0" | tail -8; exit 0 ;;
    esac
done

stop_port() {  # stop_port <port> <name>
    local port=$1 name=$2 pid
    pid=$(lsof -ti tcp:"$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null && echo "  · 已停止 $name($port) PID $pid"
        sleep 1
        kill -9 "$pid" 2>/dev/null  # 兜底强杀
    else
        echo "  · $name($port) 未运行"
    fi
}

echo "══ 小团智能平台 · 停止服务 ══"
case "$MODE" in
    engines) stop_port 9888 voice_engine; stop_port 9889 acestep ;;
    backend) stop_port 8888 backend ;;
    *)       stop_port 9888 voice_engine; stop_port 9889 acestep; stop_port 8888 backend ;;
esac
echo "完成。"
