param(
  [int]$Port = 8000,
  [string]$VenvPath = "D:\dev\ME_FM_LLM_venv",
  [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repo

powershell -ExecutionPolicy Bypass -File .\START_LOCAL_TEST.ps1 -SkipTests -Port $Port -ApiMode LocalWorkbench -VenvPath $VenvPath
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$url = "http://127.0.0.1:$Port/"
Write-Host ""
Write-Host "Maine Family Law LLM local chat is ready:" -ForegroundColor Green
Write-Host "  $url"
Write-Host ""
Write-Host "Stop it later with: .\STOP_LOCAL_TEST.ps1"
if (-not $NoBrowser) {
  Start-Process $url
}
