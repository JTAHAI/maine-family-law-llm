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

# v3.1.2 release blocker: verify every FOCAF inventory row resolves to actual
# packaged PDF bytes from the frozen runtime, including the exact item that
# returned printable_not_found in v3.1.1.
$runtimeInternal = Join-Path $RuntimeRoot "_internal"
$runtimeSource = Join-Path $runtimeInternal "src"
$assetAuditScript = Join-Path $EvidenceRoot "verify-focaf-runtime-assets.py"
$assetAuditJson = Join-Path $EvidenceRoot "focaf-runtime-asset-audit.json"
$assetAuditPython = @'
from __future__ import annotations
import json
import sys
from pathlib import Path

runtime_internal = Path(sys.argv[1]).resolve()
output_path = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(runtime_internal / "src"))
sys._MEIPASS = str(runtime_internal)

from maine_family_law_llm.focaf_library import audit_packaged_printables, printable_pdf_path

broken_id = "focaf-restoring-parent-child-relationships-after-disparagement-contact-refusal"
audit = audit_packaged_printables(verify_hashes=True)
path = printable_pdf_path(broken_id, verify_hash=True)
audit["exact_regression_id"] = broken_id
audit["exact_regression_resolved"] = bool(path and path.is_file())
audit["exact_regression_pdf_header"] = bool(path and path.read_bytes()[:4] == b"%PDF")
output_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
if audit["status"] != "pass" or not audit["exact_regression_resolved"] or not audit["exact_regression_pdf_header"]:
    raise SystemExit(2)
'@
Set-Content -Path $assetAuditScript -Value $assetAuditPython -Encoding UTF8
$storeBuildPython = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "MaineFamilyLawLLM\build-venvs\store\Scripts\python.exe"
$pythonExe = if (Test-Path -LiteralPath $storeBuildPython) { $storeBuildPython } else { "python" }
& $pythonExe $assetAuditScript $runtimeInternal $assetAuditJson
if ($LASTEXITCODE -ne 0) {
  throw "FOCAF packaged-runtime asset audit failed. See $assetAuditJson"
}
Remove-Item -LiteralPath $assetAuditScript -Force -ErrorAction SilentlyContinue

$assetAudit = Get-Content -Path $assetAuditJson -Raw | ConvertFrom-Json
if ($assetAudit.status -ne "pass" -or -not $assetAudit.exact_regression_resolved) {
  throw "FOCAF runtime assets did not pass the fail-closed audit."
}

$summary = @(
  "Store runtime smoke: PASS",
  "Application version: $($payload.application_version)",
  "Local service URL: $($payload.local_service_url)",
  "Sample workflow: $($payload.fictional_sample_workflow_result)",
  "FOCAF assets resolved: $($assetAudit.resolved)/$($assetAudit.expected)",
  "FOCAF exact regression: $($assetAudit.exact_regression_resolved)",
  "Fork guide exists: $($payload.fork_guide_exists)",
  "Privacy policy exists: $($payload.privacy_policy_exists)"
) -join "`r`n"
Set-Content -Path (Join-Path $EvidenceRoot "test-summary.txt") -Value $summary -Encoding UTF8

Write-Host "Store runtime smoke passed. Evidence: $smokeJson"
