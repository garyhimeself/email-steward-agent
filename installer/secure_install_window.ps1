$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$Host.UI.RawUI.WindowTitle = 'Email Steward secure setup v6'

Write-Host ''
Write-Host 'Email Steward secure setup v6'
Write-Host 'Only the hidden third-party client credential is entered in this window.'
Write-Host ''

$exitCode = 1
$installerScript = Join-Path -Path $PSScriptRoot -ChildPath 'install_agent.py'
$installerArguments = [string[]]$args
& py -3 $installerScript $installerArguments
if ($null -ne $LASTEXITCODE) {
    $exitCode = $LASTEXITCODE
} else {
    Write-Host ''
    Write-Host 'The secure setup window could not run Python. No installation was completed.'
}

if ($exitCode -eq 0) {
    Write-Host ''
    Write-Host 'Installation finished. You may close this secure setup window.'
} else {
    Write-Host ''
    Write-Host "The installer reported an installation failure (exit code $exitCode). Review the diagnosis above."
}
Read-Host 'Press Enter to close this secure setup window'
exit $exitCode
