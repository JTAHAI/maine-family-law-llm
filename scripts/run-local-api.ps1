param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000,
  [ValidateSet("LocalWorkbench", "Enterprise")]
  [string]$ApiMode = "LocalWorkbench"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot
$env:MAINE_FAMILY_LAW_DATA_ROOT = $DataRoot
$sep = [System.IO.Path]::PathSeparator
$env:PYTHONPATH = "$RepoRoot\src$sep$RepoRoot"

$appTarget = if ($ApiMode -eq "Enterprise") { "app.api.main:app" } else { "maine_family_law_llm.api:app" }
Write-Host "Starting $ApiMode API on http://$HostName`:$Port"
Write-Host "Chat UI: http://$HostName`:$Port/"
Write-Host "Health: http://$HostName`:$Port/api/health"
Write-Host "Version: http://$HostName`:$Port/api/version"
Write-Host "Swagger: http://$HostName`:$Port/docs"
python -m uvicorn $appTarget --host $HostName --port $Port
