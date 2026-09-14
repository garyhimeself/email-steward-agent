@echo off
setlocal
where py >nul 2>nul
if errorlevel 1 (
  echo [Email Steward] Python 3.11 or later is required. Install Python, then run this file again.
  echo [邮件管家] 需要 Python 3.11 或更高版本。请安装 Python 后重新运行此文件。
  pause
  exit /b 1
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
  echo [Email Steward] Python 3.11 or later is required. Install or select Python 3.11+, then run this file again.
  echo [邮件管家] 需要 Python 3.11 或更高版本。请安装或选择 Python 3.11+ 后重新运行此文件。
  pause
  exit /b 1
)
py -3 "%~dp0install_agent.py"
