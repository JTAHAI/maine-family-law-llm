param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "final_local_acceptance_evidence.json"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

if (-not (Test-Path $DataRoot)) {
  New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
}

python -m pytest -q
python scripts\run-quality-checks.py
python scripts\build-release-lockfile.py source_release_lock.json
python scripts\audit-release-lockfile.py source_release_lock.json
python scripts\build-enterprise-acceptance-evidence.py enterprise_acceptance_evidence.json
python scripts\run-final-local-acceptance.py $Output

Write-Host "Final local source acceptance complete. Production legal readiness still requires external evidence and signoffs."
