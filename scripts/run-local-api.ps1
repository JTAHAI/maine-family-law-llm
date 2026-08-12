param(
  [string]$RepoRoot = "",
  [string]$DataRoot = "",
  [string]$HostName = "127.0.0.1",
  [ValidateRange(1, 65535)]
  [int]$Port = 8000,
  [switch]$AllowNetworkHost,
  [ValidateSet("LocalWorkbench", "Enterprise")]
  [string]$ApiMode = "LocalWorkbench"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$loopbackHosts = @("127.0.0.1", "::1", "localhost")
if (-not $AllowNetworkHost -and $loopbackHosts -notcontains $HostName.ToLowerInvariant()) {
  throw "Refusing to expose a local legal-workbench API on '$HostName'. Use a loopback host, or pass -AllowNetworkHost only after applying your own network access controls."
}

if (-not $RepoRoot) {
  $RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}
if (-not $DataRoot) {
  $DataRoot = if ($env:MAINE_FAMILY_LAW_DATA_ROOT) {
    $env:MAINE_FAMILY_LAW_DATA_ROOT
  } else {
    Join-Path (Split-Path -Parent $RepoRoot) "$(Split-Path -Leaf $RepoRoot)_data"
  }
}

Set-Location -LiteralPath $RepoRoot
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
