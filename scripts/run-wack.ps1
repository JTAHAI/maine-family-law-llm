param(
  [string]$RepoRoot = "",
  [string]$PackagePath = "",
  [string]$OutputRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $PackagePath) {
  $PackagePath = Join-Path $RepoRoot "dist\store\msix\MaineFamilyLawLLM_x64.msix"
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\store\evidence\wack"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$resultPath = Join-Path $OutputRoot "wack-result.json"

if (-not (Test-IsAdministrator)) {
  @{
    status = "not_run"
    reason = "Windows App Certification Kit requires elevation on this machine."
    package_path = $PackagePath
  } | ConvertTo-Json -Depth 4 | Set-Content -Path $resultPath -Encoding UTF8
  Write-Host "WACK was not run because elevation is required."
  return
}

$appCert = "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe"
if (-not (Test-Path -LiteralPath $appCert)) {
  @{
    status = "not_run"
    reason = "appcert.exe was not found."
    package_path = $PackagePath
  } | ConvertTo-Json -Depth 4 | Set-Content -Path $resultPath -Encoding UTF8
  Write-Host "WACK tool was not found."
  return
}

try {
  & $appCert test -appxpackagepath $PackagePath -reportoutputpath $OutputRoot
  @{
    status = "completed"
    package_path = $PackagePath
    output_root = $OutputRoot
  } | ConvertTo-Json -Depth 4 | Set-Content -Path $resultPath -Encoding UTF8
} catch {
  @{
    status = "failed"
    reason = $_.Exception.Message
    package_path = $PackagePath
    output_root = $OutputRoot
  } | ConvertTo-Json -Depth 4 | Set-Content -Path $resultPath -Encoding UTF8
  throw
}
