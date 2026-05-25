param(
  [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
  [string]$DataRoot = "D:\dev\ME_FM_LLM_data",
  [switch]$Install,
  [switch]$NoClean,
  [string]$PytestArgs = "-q"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot
$env:MAINE_FAMILY_LAW_DATA_ROOT = $DataRoot
$env:PYTHONPATH = "$RepoRoot\src;$RepoRoot"
$env:PYTHONDONTWRITEBYTECODE = "1"

if ($Install) {
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev,api]"
}

if (-not $NoClean) {
  python scripts\clean-local-artifacts.py --repo-root $RepoRoot | Out-Host
}

python -m pytest $PytestArgs
