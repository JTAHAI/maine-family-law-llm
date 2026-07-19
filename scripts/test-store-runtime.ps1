param(
  [string]$RepoRoot = "",
  [string]$RuntimeRoot = "",
  [string]$EvidenceRoot = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}
if (-not $RuntimeRoot) {
  $RuntimeRoot = Join-Path $RepoRoot "dist\store\runtime"
}
if (-not $EvidenceRoot) {
  $EvidenceRoot = Join-Path $RepoRoot "dist\store\evidence"
}

$runtimeExe = Join-Path $RuntimeRoot "MaineFamilyLawLLM.exe"
if (-not (Test-Path -LiteralPath $runtimeExe)) {
  & (Join-Path $RepoRoot "scripts\build-store-runtime.ps1") -RepoRoot $RepoRoot
}
if (-not (Test-Path -LiteralPath $runtimeExe)) {
  throw "Store runtime executable missing at $runtimeExe"
}

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
$smokeJson = Join-Path $EvidenceRoot "store-build-smoke.json"
$smokeArguments = @(
    "--smoke-test"
    "--smoke-json"
    $smokeJson
)

$smokeProcess = Start-Process `
    -FilePath $runtimeExe `
    -ArgumentList $smokeArguments `
    -WindowStyle Hidden `
    -PassThru

if (-not $smokeProcess.WaitForExit(120000)) {
    Stop-Process `
        -Id $smokeProcess.Id `
        -Force `
        -ErrorAction SilentlyContinue

    throw "Store runtime smoke timed out after 120 seconds."
}

if ($smokeProcess.ExitCode -ne 0) {
    throw "Store runtime smoke exited with code $($smokeProcess.ExitCode)."
}

if (-not (Test-Path -LiteralPath $smokeJson)) {
  throw "Smoke evidence was not written to $smokeJson"
}

$payload = Get-Content -Path $smokeJson -Raw | ConvertFrom-Json
if ($payload.launch_result -ne "pass" -or -not $payload.api_health_result -or -not $payload.fictional_sample_workflow_result -or -not $payload.answer_grounded -or $payload.answer_failure_class -ne "none") {
  throw "Store runtime smoke test did not produce a passing payload."
}

$summary = @(
  "Store runtime smoke: PASS",
  "Application version: $($payload.application_version)",
  "Local service URL: $($payload.local_service_url)",
  "Sample workflow: $($payload.fictional_sample_workflow_result)",
  "Fork guide exists: $($payload.fork_guide_exists)",
  "Privacy policy exists: $($payload.privacy_policy_exists)"
) -join "`r`n"
Set-Content -Path (Join-Path $EvidenceRoot "test-summary.txt") -Value $summary -Encoding UTF8

Write-Host "Store runtime smoke passed. Evidence: $smokeJson"
