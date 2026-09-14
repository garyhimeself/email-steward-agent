#!/bin/sh
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "[Email Steward] Python 3.11 or later is required. Install Python, then run this file again."
  echo "[邮件管家] 需要 Python 3.11 或更高版本。请安装 Python 后重新运行此文件。"
  exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
  echo "[Email Steward] Python 3.11 or later is required. Install or select Python 3.11+, then run this file again."
  echo "[邮件管家] 需要 Python 3.11 或更高版本。请安装或选择 Python 3.11+ 后重新运行此文件。"
  exit 1
fi
exec python3 "$SCRIPT_DIR/install_agent.py"
