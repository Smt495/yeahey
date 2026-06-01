#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# 美股每日简报 — 启动脚本
# 用法:
#   ./run_briefing.sh              # 立刻生成当前时段简报
#   ./run_briefing.sh run          # 同上
#   ./run_briefing.sh run --session pre_market
#   ./run_briefing.sh schedule     # 守护进程模式 (Mon-Fri 定时触发)
#   ./run_briefing.sh install-cron # 安装 crontab 自动触发
# ──────────────────────────────────────────────────────────────
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV="$SCRIPT_DIR/.venv"
PYTHON="$VENV/bin/python"
REPORTS_DIR="$SCRIPT_DIR/reports"

# ── ensure venv & deps ──────────────────────────────────────────
if [[ ! -f "$PYTHON" ]]; then
  echo "[setup] Creating virtual environment …"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip -q
  "$VENV/bin/pip" install -r requirements.txt -q
  echo "[setup] Done."
fi

mkdir -p "$REPORTS_DIR"

# ── dispatch ────────────────────────────────────────────────────
CMD="${1:-run}"

case "$CMD" in
  run)
    shift || true
    PYTHONPATH="$SCRIPT_DIR" "$PYTHON" -m briefing.main run "$@"
    ;;
  schedule)
    echo "[scheduler] Starting daemon (Mon-Fri, ET timezone) …"
    PYTHONPATH="$SCRIPT_DIR" "$PYTHON" -m briefing.main schedule
    ;;
  install-cron)
    CRON_LINE="30 7,35 9,0 12,5 16,30 17 * * 1-5 PYTHONPATH=$SCRIPT_DIR $PYTHON -m briefing.main run >> $SCRIPT_DIR/briefing.log 2>&1"
    # Use Python-based schedule daemon instead (simpler)
    CRON_DAEMON="@reboot cd $SCRIPT_DIR && $SCRIPT_DIR/run_briefing.sh schedule >> $SCRIPT_DIR/briefing.log 2>&1"
    ( crontab -l 2>/dev/null | grep -v "briefing"; echo "$CRON_DAEMON" ) | crontab -
    echo "[cron] Installed: $CRON_DAEMON"
    ;;
  *)
    echo "Unknown command: $CMD"
    echo "Usage: $0 [run|schedule|install-cron] [options]"
    exit 1
    ;;
esac
