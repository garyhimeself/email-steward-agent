$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$Host.UI.RawUI.WindowTitle = 'Email Steward - Secure Setup / 邮件管家 - 安全验证'

Write-Host ''
Write-Host 'Email Steward Agent — local secure setup'
Write-Host '邮件管家 Agent —— 本地安全验证'
Write-Host 'Only the hidden third-party client credential is entered in this window.'
Write-Host '此窗口仅输入隐藏的第三方客户端安全密码。'
Write-Host ''

$exitCode = 1
try {
    & py -3 (Join-Path $PSScriptRoot 'install_agent.py') @args
    if ($null -ne $LASTEXITCODE) {
        $exitCode = $LASTEXITCODE
    }
    if ($exitCode -eq 0) {
        Write-Host ''
        Write-Host 'Installation finished. You may close this secure setup window.'
        Write-Host '安装流程已结束。你现在可以关闭此安全验证窗口。'
    }
} catch {
    Write-Host ''
    Write-Host 'The secure setup window could not start the installer. No credential was requested.'
    Write-Host '安全验证窗口无法启动安装器，未请求任何安全密码。'
    $exitCode = 1
}

Read-Host 'Press Enter to close this secure setup window / 按 Enter 关闭此安全验证窗口'
exit $exitCode
