#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# 小团智能平台 · 本地 AI 引擎与服务编排（Mac 开发环境）
#
# 启动顺序: voice_engine(9888 CosyVoice) → acestep(9889 ACE-Step) → avatar(9890 SadTalker) → backend(8888)
# 用法:
#   ./scripts/start_all.sh            # 启动全部（含后端）
#   ./scripts/start_all.sh --engines  # 仅启动本地 AI 引擎（不含后端）
#   ./scripts/start_all.sh --backend  # 仅启动后端
#
# 依赖: voice_engine 用 ~/ai-models/cv-venv；acestep 用 ~/ai-models/ACE-Step-1.5/.venv；avatar 用 ~/ai-models/SadTalker/.venv
# 日志: /tmp/voice_engine.log /tmp/acestep_server.log /tmp/avatar_engine.log /tmp/backend_restart.log
# ═══════════════════════════════════════════════════════════════════
set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
MODE="all"
for arg in "$@"; do
    case "$arg" in
        --engines) MODE="engines" ;;
        --backend) MODE="backend" ;;
        -h|--help) head -18 "$0" | tail -14; exit 0 ;;
    esac
done

is_up() { nc -z 127.0.0.1 "$1" >/dev/null 2>&1; }
start_session() {  # start_session <name> <cwd> <python> <script...>
    local name=$1 cwd=$2 py=$3; shift 3
    echo "  · 启动 $name ..."
    if [ "$name" = "backend" ]; then
        LOG=/tmp/backend_restart.log
    else
        LOG=/tmp/${name}.log
    fi
    (cd "$cwd" && nohup "$py" "$@" < /dev/null > "$LOG" 2>&1 & disown)
    echo "    PID $! | 日志 $LOG"
}

echo "══ 小团智能平台 · 服务编排 ══"

# ─── voice_engine 9888 ────────────────────────────────────────────
start_voice() {
    if is_up 9888; then
        echo "  ✅ voice_engine(9888) 已在运行"
    elif [ -x "$HOME/ai-models/cv-venv/bin/python" ]; then
        start_session voice_engine "$BACKEND_DIR" \
            "$HOME/ai-models/cv-venv/bin/python" \
            "$BACKEND_DIR/voice_engine/server.py"
    else
        echo "  ⚠️ 未找到 cv-venv（~/ai-models/cv-venv），跳过 voice_engine"
    fi
}

# ─── acestep 9889 ─────────────────────────────────────────────────
start_acestep() {
    if is_up 9889; then
        echo "  ✅ acestep(9889) 已在运行"
    elif [ -x "$HOME/ai-models/ACE-Step-1.5/.venv/bin/python" ]; then
        start_session acestep "$HOME/ai-models/ACE-Step-1.5" \
            "$HOME/ai-models/ACE-Step-1.5/.venv/bin/python" \
            -m acestep.api_server --port 9889
    else
        echo "  ⚠️ 未找到 ACE-Step venv（~/ai-models/ACE-Step-1.5），跳过 acestep"
    fi
}

# ─── avatar_engine 9890（SadTalker 数字人）─────────────────────────
start_avatar() {
    if is_up 9890; then
        echo "  ✅ avatar_engine(9890) 已在运行"
    elif [ -x "$HOME/ai-models/SadTalker/.venv/bin/python" ]; then
        start_session avatar_engine "$BACKEND_DIR/avatar_engine" \
            "$HOME/ai-models/SadTalker/.venv/bin/python" \
            -m uvicorn server:app --host 127.0.0.1 --port 9890 --log-level info
    else
        echo "  ⚠️ 未找到 SadTalker venv（~/ai-models/SadTalker），跳过 avatar_engine"
    fi
}

# ─── backend 8888 ─────────────────────────────────────────────────
start_backend() {
    if is_up 8888; then
        echo "  ✅ backend(8888) 已在运行"
    else
        start_session backend "$BACKEND_DIR" "$PROJECT_ROOT/.venv/bin/python" main.py
    fi
}

case "$MODE" in
    engines) start_voice; start_acestep; start_avatar ;;
    backend) start_backend ;;
    *)       start_voice; start_acestep; start_avatar; start_backend ;;
esac

echo ""
echo "  探活确认（等待启动）..."
sleep 8
for p in 9888 9889 9890 8888; do
    case "$MODE:$p" in
        engines:8888|backend:9888|backend:9889|backend:9890) continue ;;
    esac
    if is_up "$p"; then echo "  ✅ 端口 $p 就绪"; else echo "  ⚠️ 端口 $p 未就绪（引擎懒加载/启动慢时属正常）"; fi
done
echo "完成。"
