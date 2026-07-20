param(
  [string]$RepoRoot = "",
  [string]$DataRoot = "",
  [string]$Output = "docs/sample-evidence/local_smoke_report.json",
  [switch]$RunPytest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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
$env:PYTHONPATH = $RepoRoot
python scripts\clean-local-artifacts.py --repo-root $RepoRoot | Out-Host
$argsList = @("scripts\run-local-smoke.py", "--repo-root", $RepoRoot, "--data-root", $DataRoot, "--output", $Output)
if ($RunPytest) { $argsList += "--run-pytest" }
python @argsList
