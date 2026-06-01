param(
    [string]$RepoRoot = "C:\dev\ME_FM_LLM",
    [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
    [string]$Python = "python",
    [switch]$DryRun,
    [int]$MaxResources = 0
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $RepoRoot)) {
    throw "RepoRoot does not exist: $RepoRoot"
}
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
Set-Location $RepoRoot

& $Python -m pip install -e .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts\run-quality-checks.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts\build-enterprise-local-plan.py --repo-root $RepoRoot --data-root $DataRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$collectArgs = @("scripts\collect-enterprise-resources.py", "--data-root", $DataRoot)
if ($DryRun) { $collectArgs += "--dry-run" }
if ($MaxResources -gt 0) { $collectArgs += @("--max-resources", "$MaxResources") }
& $Python @collectArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python scripts\audit-enterprise-resource-collection.py --data-root $DataRoot
$resourceAuditExit = $LASTEXITCODE
if (-not $DryRun -and $resourceAuditExit -ne 0) { exit $resourceAuditExit }

if (-not $DryRun) {
    & $Python scripts\ingest-maine-authority.py --data-root $DataRoot
    & $Python scripts\build-parsed-authority-store.py --data-root $DataRoot
    & $Python scripts\build-authority-layer.py --data-root $DataRoot
    & $Python scripts\build-retrieval-indexes.py --data-root $DataRoot
    & $Python scripts\audit-enterprise-readiness.py --data-root $DataRoot --eval-root (Join-Path $DataRoot "eval_store")
}

$hardeningArgs = @("scripts\run-enterprise-local-hardening.py", "--data-root", $DataRoot)
if ($DryRun) { $hardeningArgs += "--dry-run" }
if ($MaxResources -gt 0) { $hardeningArgs += @("--max-resources", "$MaxResources") }
& $Python @hardeningArgs
exit $LASTEXITCODE
