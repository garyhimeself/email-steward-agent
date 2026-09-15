$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$Host.UI.RawUI.WindowTitle = 'Email Steward - Secure Setup'

Write-Host ''
Write-Host 'Email Steward Agent - local secure setup'
Write-Host 'Only the hidden third-party client credential is entered in this window.'
Write-Host ''

$exitCode = 1
try {
    $installerScript = Join-Path -Path $PSScriptRoot -ChildPath 'install_agent.py'
    $installerArguments = [string[]]$args
    & py -3 $installerScript $installerArguments
    if ($null -ne $LASTEXITCODE) {
        $exitCode = $LASTEXITCODE
    }
    if ($exitCode -eq 0) {
        Write-Host ''
        Write-Host 'Installation finished. You may close this secure setup window.'
    }
} catch {
    Write-Host ''
    Write-Host 'The secure setup window could not start the installer. No credential was requested.'
    $exitCode = 1
}

Read-Host 'Press Enter to close this secure setup window'
exit $exitCode
