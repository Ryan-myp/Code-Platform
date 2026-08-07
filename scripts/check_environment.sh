#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# 小团智能平台 — 部署环境自检脚本
#
# 用法:
#   ./scripts/check_environment.sh              # 仅检查，不修改环境
#   ./scripts/check_environment.sh --fix        # 检查 + 自动安装缺失项
#   ./scripts/check_environment.sh --app-dir /opt/app/backend  # 指定后端目录
#
# 检查项（12 项，全部通过才允许部署）:
#   [1] 操作系统/架构           [2] Python >= 3.13
#   [3] pip                     [4] ffmpeg + ffprobe（视频/语音合成）
#   [5] node + npm（游戏/代码沙箱）  [6] 中文字体（Noto CJK / 文泉驿）
#   [7] emoji 字体              [8] Python 依赖（requirements.txt 全量可导入）
#   [9] ffmpeg 编码器（libx264 必需）  [10] 磁盘空间 >= 1GB
#   [11] 端口 8888 空闲          [12] 数据目录可写
#
# 退出码: 0 = 全部通过；1 = 存在未修复失败；2 = 自动修复失败
# ═══════════════════════════════════════════════════════════════════
set -u

# ─── 基础配置 ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="${PROJECT_ROOT}/backend"
FIX_MODE=0
REQUIRED_PORT=8888
MIN_DISK_KB=1048576   # 1GB（视频/音频/图片产物空间）

# ─── 颜色输出（无 tty 时自动降级为纯文本）────────────────────────
if [ -t 1 ]; then
    GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
    CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
else
    GREEN=''; YELLOW=''; RED=''; CYAN=''; BOLD=''; NC=''
fi

PASS=0; FAIL=0; WARN=0
FAILED_ITEMS=""

log_ok()   { printf "${GREEN}  ✅${NC} %s\n" "$1"; }
log_fail() { printf "${RED}  ❌${NC} %s\n" "$1"; FAIL=$((FAIL + 1)); }
log_warn() { printf "${YELLOW}  ⚠️${NC} %s\n" "$1"; WARN=$((WARN + 1)); }
log_info() { printf "${CYAN}  ·${NC} %s\n" "$1"; }

record_fail() { FAILED_ITEMS="${FAILED_ITEMS} $1"; }

# 逐项标题（保持计数对齐）
section() {
    local n=$1; shift
    printf "${BOLD}[%2d/12]${NC} %s\n" "$n" "$*"
}

# ─── 参数解析 ────────────────────────────────────────────────────
for arg in "$@"; do
    case "$arg" in
        --fix) FIX_MODE=1 ;;
        --app-dir)
            shift
            APP_DIR="${1:-$APP_DIR}"
            ;;
        -h|--help)
            head -30 "$0" | tail -22
            exit 0
            ;;
    esac
done

# ─── 检查项实现 ──────────────────────────────────────────────────
# [1] 操作系统/架构
check_os() {
    section 1 "操作系统/架构"
    local os arch
    os="$(uname -s)"; arch="$(uname -m)"
    case "$os" in
        Linux)  log_ok "Linux ${arch}（生产环境）" ;;
        Darwin) log_ok "macOS ${arch}（开发环境）" ;;
        *)      log_warn "未知系统 ${os} ${arch}（未覆盖验证，请谨慎部署）" ;;
    esac
    PASS=$((PASS + 1))
}

# [2] Python 版本（后端要求 >= 3.13，pydantic>=2.10 起才对齐 cp313 wheel）
check_python() {
    section 2 "Python >= 3.13"
    if command -v python3 >/dev/null 2>&1; then
        local ver
        ver="$(python3 --version 2>&1 | awk '{print $2}')"
        if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"; then
            log_ok "python3 ${ver}"
            PASS=$((PASS + 1))
        else
            log_fail "python3 ${ver} 过旧（需要 >= 3.13，3.13 起才有新版依赖 wheel）"
            record_fail python
        fi
    else
        log_fail "未找到 python3"
        record_fail python
    fi
}

# [3] pip
check_pip() {
    section 3 "pip"
    if command -v pip3 >/dev/null 2>&1 || python3 -m pip --version >/dev/null 2>&1; then
        log_ok "pip 可用（$(python3 -m pip --version 2>/dev/null | awk '{print $2}')）"
        PASS=$((PASS + 1))
    else
        log_fail "未找到 pip3"
        record_fail pip
    fi
}

# [4] ffmpeg / ffprobe（数字人/视频工厂/语音合成核心依赖）
check_ffmpeg() {
    section 4 "ffmpeg + ffprobe"
    local missing=""
    command -v ffmpeg >/dev/null 2>&1 || missing="$missing ffmpeg"
    command -v ffprobe >/dev/null 2>&1 || missing="$missing ffprobe"
    if [ -z "$missing" ]; then
        log_ok "ffmpeg $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}') / ffprobe"
        PASS=$((PASS + 1))
    else
        log_fail "缺失:$missing（数字人/视频/语音合成必需）"
        record_fail ffmpeg
    fi
}

# [5] node / npm（游戏工坊 JS 校验、AI 工作台 Node 工程）
check_node() {
    section 5 "node + npm"
    local missing=""
    command -v node >/dev/null 2>&1 || missing="$missing node"
    command -v npm >/dev/null 2>&1 || missing="$missing npm"
    if [ -z "$missing" ]; then
        log_ok "node $(node --version 2>/dev/null) / npm $(npm --version 2>/dev/null)"
        PASS=$((PASS + 1))
    else
        log_fail "缺失:$missing（游戏 JS 校验 / 代码沙箱 Node 工程）"
        record_fail node
    fi
}

# [6] 中文字体（缺少时图片/视频中文渲染豆腐块）
check_cjk_font() {
    section 6 "中文字体"
    local found=""
    case "$(uname -s)" in
        Linux)
            for f in /usr/share/fonts/truetype/wqy/wqy-microhei.ttc \
                     /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc; do
                [ -f "$f" ] && found="$f" && break
            done
            ;;
        Darwin)
            for f in /System/Library/Fonts/PingFang.ttc \
                     /System/Library/Fonts/Hiragino\ Sans\ GB.ttc; do
                [ -f "$f" ] && found="$f" && break
            done
            ;;
    esac
    if [ -n "$found" ]; then
        log_ok "中文字体: $(basename "$found")"
        PASS=$((PASS + 1))
    else
        log_fail "未找到中文字体（图片/视频中文将渲染为豆腐块）"
        record_fail cjk-font
    fi
}

# [7] emoji 字体（数字人贴纸/表情渲染）
check_emoji_font() {
    section 7 "emoji 字体"
    local found=""
    case "$(uname -s)" in
        Linux)  [ -f /usr/share/fonts/truetype/noto/NotoColorEmoji.ttf ] && found="NotoColorEmoji" ;;
        Darwin) [ -f /System/Library/Fonts/Apple\ Color\ Emoji.ttc ] && found="Apple Color Emoji" ;;
    esac
    if [ -n "$found" ]; then
        log_ok "emoji 字体: $found"
        PASS=$((PASS + 1))
    else
        log_warn "未找到 emoji 字体（数字人 emoji 装饰将回退，不影响主功能）"
        record_fail emoji-font
    fi
}

# [8] Python 依赖（requirements.txt 全量 import 测试，防"装了但坏"）
check_pip_deps() {
    section 8 "Python 依赖"
    local req_file="$APP_DIR/requirements.txt"
    if [ ! -f "$req_file" ]; then
        log_warn "未找到 $req_file（跳过依赖检查）"
        WARN=$((WARN + 1))
        return
    fi
    local result
    result="$(python3 - "$req_file" <<'PYEOF'
import importlib, sys
# 包名 -> 模块名 映射（pip 包名与 import 名不一致的项）
MAPPING = {
    "python-multipart": "multipart",
    "python-jose": "jose",
    "python-dotenv": "dotenv",
    "pydantic-settings": "pydantic_settings",
    "pillow": "PIL",
    "edge-tts": "edge_tts",
    "python-pptx": "pptx",
    "pyyaml": "yaml",
}
missing = []
with open(sys.argv[1], encoding="utf-8") as f:
    for line in f:
        line = line.split("#")[0].strip()
        if not line or line.startswith(("-", "[")):
            continue
        pkg = line.split("=")[0].split(">")[0].split("<")[0].split("[")[0].split("!")[0].strip()
        if not pkg:
            continue
        mod = MAPPING.get(pkg.lower(), pkg.lower().replace("-", "_"))
        try:
            importlib.import_module(mod)
        except Exception:
            missing.append(pkg)
print("|".join(missing) if missing else "OK")
PYEOF
)"
    if [ "$result" = "OK" ]; then
        log_ok "requirements.txt 全部依赖可导入（$(wc -l < "$req_file" | tr -d ' ') 项）"
        PASS=$((PASS + 1))
    else
        log_fail "依赖缺失或损坏: $result"
        record_fail pip-deps
    fi
}

# [9] ffmpeg 编码器（libx264 必需；硬件编码器仅信息提示）
check_encoder() {
    section 9 "ffmpeg 编码器"
    if ! command -v ffmpeg >/dev/null 2>&1; then
        log_fail "ffmpeg 缺失，无法检查编码器"
        record_fail encoder
        return
    fi
    local encoders
    encoders="$(ffmpeg -hide_banner -encoders 2>/dev/null)"
    if echo "$encoders" | grep -q "libx264"; then
        log_ok "libx264（CPU 编码，兜底可用）"
        PASS=$((PASS + 1))
    else
        log_fail "ffmpeg 未编译 libx264（视频编码将不可用）"
        record_fail encoder
        return
    fi
    # 硬件编码器探测（仅报告编译情况，无 GPU 时实际不可用，不阻塞部署）
    if echo "$encoders" | grep -q "h264_videotoolbox"; then
        log_info "已编译: h264_videotoolbox（需 macOS/Apple 环境）"
    elif echo "$encoders" | grep -q "h264_nvenc"; then
        log_info "已编译: h264_nvenc（需 NVIDIA GPU 驱动）"
    else
        log_info "无硬件编码器，将使用 libx264 CPU 编码"
    fi
}

# [10] 磁盘空间（数据/产物目录所在分区 >= 1GB）
check_disk() {
    section 10 "磁盘空间 >= 1GB"
    local avail_kb
    avail_kb="$(df -Pk "$APP_DIR" 2>/dev/null | awk 'NR==2 {print $4}')"
    if [ -z "$avail_kb" ] || [ "$avail_kb" -lt "$MIN_DISK_KB" ]; then
        log_fail "可用磁盘不足（当前 ${avail_kb:-0}KB，需 >= ${MIN_DISK_KB}KB）"
        record_fail disk
    else
        log_ok "可用磁盘 $(awk -v k="$avail_kb" 'BEGIN {printf "%.1fGB", k/1048576}')"
        PASS=$((PASS + 1))
    fi
}

# [11] 端口空闲（后端默认 8888）
check_port() {
    section 11 "端口 $REQUIRED_PORT 空闲"
    if python3 - "$REQUIRED_PORT" <<'PYEOF' >/dev/null 2>&1
import socket, sys
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(("0.0.0.0", int(sys.argv[1])))
    s.close()
    sys.exit(0)
except OSError:
    sys.exit(1)
PYEOF
    then
        log_ok "端口 $REQUIRED_PORT 可绑定"
        PASS=$((PASS + 1))
    else
        log_fail "端口 $REQUIRED_PORT 被占用（请停止占用进程后重试）"
        record_fail port
    fi
}

# [12] 数据目录可写（backend/ 需写入数据库/上传/产物）
check_writable() {
    section 12 "数据目录可写"
    if [ -d "$APP_DIR" ] && [ -w "$APP_DIR" ]; then
        log_ok "$APP_DIR 可写"
        PASS=$((PASS + 1))
    else
        log_fail "$APP_DIR 不存在或不可写（检查权限/挂载）"
        record_fail writable
    fi
}

# ─── 自动修复 ────────────────────────────────────────────────────
# 系统包安装（按发行版选择包管理器；非 root 自动加 sudo）
sys_install() {
    local pkgs="$*"
    if [ "$(id -u)" -eq 0 ]; then
        SUDO=""
    else
        SUDO="sudo"
    fi
    case "$(uname -s)" in
        Linux)
            if command -v apt-get >/dev/null 2>&1; then
                $SUDO apt-get update -qq && $SUDO apt-get install -y --no-install-recommends $pkgs
            elif command -v dnf >/dev/null 2>&1; then
                $SUDO dnf install -y $pkgs
            elif command -v yum >/dev/null 2>&1; then
                $SUDO yum install -y $pkgs
            elif command -v apk >/dev/null 2>&1; then
                $SUDO apk add $pkgs
            else
                echo "  ❌ 未识别的包管理器，请手动安装: $pkgs"
                return 1
            fi
            ;;
        Darwin)
            command -v brew >/dev/null 2>&1 || { echo "  ❌ 需要 Homebrew（https://brew.sh）"; return 1; }
            brew install $pkgs
            ;;
        *) return 1 ;;
    esac
}

fix_attempt() {
    echo ""
    printf "${BOLD}── 自动修复（--fix）${NC}\n"
    local ok=1

    # 分组: 命令类
    local need_cmd=""
    case "$FAILED_ITEMS" in
        *" ffmpeg"*) need_cmd="$need_cmd ffmpeg" ;;
    esac
    case "$FAILED_ITEMS" in
        *" node"*)   need_cmd="$need_cmd nodejs npm" ;;
    esac
    if [ -n "$need_cmd" ]; then
        echo "  · 安装系统命令:$need_cmd"
        sys_install $need_cmd || ok=0
    fi

    # 分组: 字体类
    local need_font=""
    case "$FAILED_ITEMS" in
        *" cjk-font"*)   need_font="$need_font fonts-noto-cjk fonts-wqy-microhei" ;;
    esac
    case "$FAILED_ITEMS" in
        *" emoji-font"*) need_font="$need_font fonts-noto-color-emoji" ;;
    esac
    if [ -n "$need_font" ]; then
        echo "  · 安装字体:$need_font"
        sys_install $need_font || ok=0
    fi

    # 分组: Python 依赖
    case "$FAILED_ITEMS" in
        *" python"*|*" pip"*|*" pip-deps"*)
            echo "  · 安装 Python 依赖: $APP_DIR/requirements.txt"
            if [ -f "$APP_DIR/requirements.txt" ]; then
                if [ "$(id -u)" -eq 0 ]; then
                    python3 -m pip install --no-cache-dir -r "$APP_DIR/requirements.txt" || ok=0
                else
                    python3 -m pip install --user --no-cache-dir -r "$APP_DIR/requirements.txt" || ok=0
                fi
            else
                echo "  ❌ requirements.txt 不存在，无法自动修复"
                ok=0
            fi
            ;;
    esac

    # 无法自动修复的项
    case "$FAILED_ITEMS" in
        *" port"*)      echo "  ⚠️ 端口被占用无法自动修复：请用 lsof -i :$REQUIRED_PORT 定位并停止进程" ;;
        *" disk"*)      echo "  ⚠️ 磁盘不足无法自动修复：请清理磁盘或扩容后重试" ;;
        *" writable"*)  echo "  ⚠️ 目录不可写无法自动修复：请检查挂载权限（chown/chmod）" ;;
        *" encoder"*)   echo "  ⚠️ 编码器缺失无法自动修复：请安装带 libx264 的 ffmpeg（apt 默认包含）" ;;
    esac

    [ "$ok" -eq 1 ] || { echo ""; printf "${RED}── 部分修复失败，请按上方提示手动处理 ──${NC}\n"; exit 2; }
}

# ─── 主流程 ──────────────────────────────────────────────────────
main() {
    echo ""
    printf "${BOLD}══ 小团智能平台 · 部署环境自检 ══${NC}\n"
    echo "  应用目录: $APP_DIR"
    echo "  模式: $([ "$FIX_MODE" -eq 1 ] && echo "检查 + 自动修复" || echo "仅检查（加 --fix 自动安装缺失项）")"
    echo ""

    check_os
    check_python
    check_pip
    check_ffmpeg
    check_node
    check_cjk_font
    check_emoji_font
    check_pip_deps
    check_encoder
    check_disk
    check_port
    check_writable

    echo ""
    printf "${BOLD}── 检查结果 ──${NC}  ${GREEN}${PASS} 通过${NC} / ${RED}${FAIL} 失败${NC} / ${YELLOW}${WARN} 警告${NC}\n"

    if [ "$FAIL" -eq 0 ]; then
        printf "${GREEN}✅ 环境检查通过，可以部署！${NC}\n"
        exit 0
    fi

    if [ "$FIX_MODE" -eq 1 ]; then
        fix_attempt
        echo ""
        echo "  修复完成，请重新运行本脚本确认全部通过"
        exit 1
    else
        printf "${RED}❌ 环境检查未通过（${FAIL} 项失败）${NC}\n"
        echo "  运行以下命令自动安装缺失项:"
        echo "    $0 --fix"
        echo ""
        exit 1
    fi
}

main "$@"
