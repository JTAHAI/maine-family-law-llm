param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$VenvRoot = "C:\dev\ME_FM_LLM_venv",
  [switch]$NoVenv,
  [switch]$CleanAfterInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot

if (-not $NoVenv) {
  if (-not (Test-Path $VenvRoot)) {
    py -3.11 -m venv $VenvRoot
  }
  & "$VenvRoot\Scripts\python.exe" -m pip install --upgrade pip
  & "$VenvRoot\Scripts\python.exe" -m pip install -e ".[dev,api]"
  if ($CleanAfterInstall) {
    & "$VenvRoot\Scripts\python.exe" scripts\clean-local-artifacts.py --repo-root $RepoRoot
  }
  Write-Host "Installed. Activate with: $VenvRoot\Scripts\Activate.ps1"
} else {
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev,api]"
  if ($CleanAfterInstall) {
    python scripts\clean-local-artifacts.py --repo-root $RepoRoot
  }
}
