param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "docs/sample-evidence/local_smoke_report.json",
  [switch]$RunPytest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot
$env:MAINE_FAMILY_LAW_DATA_ROOT = $DataRoot
$env:PYTHONPATH = $RepoRoot
python scripts\clean-local-artifacts.py --repo-root $RepoRoot | Out-Host
$argsList = @("scripts\run-local-smoke.py", "--repo-root", $RepoRoot, "--data-root", $DataRoot, "--output", $Output)
if ($RunPytest) { $argsList += "--run-pytest" }
python @argsList
