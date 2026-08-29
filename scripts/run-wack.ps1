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
  $PackagePath = Join-Path $RepoRoot "dist\release\v8.0.0\msix\MaineFamilyLawLLM_8.0.0.0_x64.msix"
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\release\v8.0.0\evidence\wack"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$resultPath = Join-Path $OutputRoot "wack-result.json"
$parser = Join-Path $RepoRoot "scripts\parse-wack-report.py"

function Write-WackQualification([string]$ExecutionStatus, [string]$Reason) {
  if (-not (Test-Path -LiteralPath $parser)) { throw "WACK parser was not found: $parser" }
  & python $parser --package $PackagePath --output-root $OutputRoot --execution-status $ExecutionStatus --reason $Reason --output $resultPath
  if ($LASTEXITCODE -gt 1) { throw "WACK evidence parser failed with exit code $LASTEXITCODE" }
}

if (-not (Test-IsAdministrator)) {
  Write-WackQualification "not_run" "Windows App Certification Kit requires elevation on this machine."
  Write-Host "WACK was not run because elevation is required."
  return
}

$appCert = "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe"
if (-not (Test-Path -LiteralPath $appCert)) {
  Write-WackQualification "not_run" "appcert.exe was not found."
  Write-Host "WACK tool was not found."
  return
}

try {
  & $appCert test -appxpackagepath $PackagePath -reportoutputpath $OutputRoot
  if ($LASTEXITCODE -eq 0) {
    Write-WackQualification "completed" ""
  } else {
    Write-WackQualification "failed" "appcert.exe returned exit code $LASTEXITCODE."
  }
} catch {
  Write-WackQualification "failed" "WACK invocation threw an exception."
  throw
}
