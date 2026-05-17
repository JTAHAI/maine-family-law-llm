param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot
$env:MAINE_FAMILY_LAW_DATA_ROOT = $DataRoot
$env:PYTHONPATH = $RepoRoot

Write-Host "Starting API on http://$HostName`:$Port"
Write-Host "Health: http://$HostName`:$Port/api/health"
Write-Host "Version: http://$HostName`:$Port/api/version"
Write-Host "Swagger: http://$HostName`:$Port/docs"
python -m uvicorn app.api.main:app --host $HostName --port $Port
