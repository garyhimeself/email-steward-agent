@echo off
setlocal
chcp 65001 >nul
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
if /I "%~1"=="--preflight" (
  py -3 "%~dp0install_agent.py" %*
  exit /b %errorlevel%
)

if /I "%~1"=="--upgrade-workspace" (
  py -3 "%~dp0install_agent.py" %*
  exit /b %errorlevel%
)

if /I "%~1"=="--secure-window" (
  start "Email Steward - Secure Setup" /wait powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0secure_install_window.ps1" %*
  exit /b %errorlevel%
)

echo [Email Steward] Setup must be started from Codex so it can open a separate secure PowerShell window.
echo [邮件管家] 请从 Codex 启动安装；它会打开独立的安全 PowerShell 窗口。
echo Run this file with --preflight only for a credential-free network check.
echo 仅进行无凭据网络预检时，请使用 --preflight。
exit /b 2
