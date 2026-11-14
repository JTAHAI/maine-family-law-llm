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
  throw "An explicit exact candidate -PackagePath is required for WACK qualification."
}
if (-not $OutputRoot) {
  $OutputRoot = Join-Path $RepoRoot "dist\store\evidence\wack"
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null
$OutputRoot = (Resolve-Path -LiteralPath $OutputRoot).Path
$PackagePath = (Resolve-Path -LiteralPath $PackagePath).Path
$resultPath = Join-Path $OutputRoot "wack-result.json"
$nativeReportPath = Join-Path $OutputRoot "appcert-report.xml"
if ((Test-Path -LiteralPath $resultPath) -or @(Get-ChildItem -LiteralPath $OutputRoot -Filter "*.xml" -File -Recurse).Count) {
  throw "Use a fresh WACK output directory for this exact candidate."
}
$parser = Join-Path $RepoRoot "scripts\parse-wack-report.py"

function Write-WackQualification([string]$ExecutionStatus, [string]$Reason) {
  if (-not (Test-Path -LiteralPath $parser)) { throw "WACK parser was not found: $parser" }
  & python $parser --package $PackagePath --output-root $OutputRoot --execution-status $ExecutionStatus --reason $Reason --output $resultPath | Out-Host
  if ($LASTEXITCODE -gt 1) { throw "WACK evidence parser failed with exit code $LASTEXITCODE" }
  $record = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
  return ($record.status -eq "pass")
}

if (-not (Test-IsAdministrator)) {
  $null = Write-WackQualification "not_run" "Windows App Certification Kit requires elevation on this machine."
  Write-Host "WACK was not run because elevation is required."
  exit 1
}

$appCert = "C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe"
if (-not (Test-Path -LiteralPath $appCert)) {
  $null = Write-WackQualification "not_run" "appcert.exe was not found."
  Write-Host "WACK tool was not found."
  exit 1
}

try {
  & $appCert reset
  if ($LASTEXITCODE -ne 0) {
    $null = Write-WackQualification "failed" "appcert.exe reset returned exit code $LASTEXITCODE."
    exit 1
  }
  & $appCert test -appxpackagepath $PackagePath -reportoutputpath $nativeReportPath
  $nativeExit = $LASTEXITCODE
  if ($nativeExit -eq 0) {
    $passed = Write-WackQualification "completed" ""
    if (-not $passed) { exit 1 }
    exit 0
  } else {
    $null = Write-WackQualification "failed" "appcert.exe returned exit code $nativeExit."
    exit 1
  }
} catch {
  if (-not (Test-Path -LiteralPath $resultPath)) {
    $null = Write-WackQualification "failed" "WACK invocation threw an exception."
  }
  throw
}
