param(
  [string]$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path,
  [string]$DataRoot = "",
  [switch]$Install,
  [switch]$NoClean,
  [string]$PytestArgs = "-q"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot
$DataRoot = if ($DataRoot) {
  $DataRoot
} elseif ($env:MAINE_FAMILY_LAW_DATA_ROOT) {
  $env:MAINE_FAMILY_LAW_DATA_ROOT
} else {
  Join-Path (Split-Path -Parent $RepoRoot) "$(Split-Path -Leaf $RepoRoot)_data"
}
$env:MAINE_FAMILY_LAW_DATA_ROOT = $DataRoot
$sep = [System.IO.Path]::PathSeparator
$env:PYTHONPATH = "$RepoRoot\src$sep$RepoRoot"
$env:PYTHONDONTWRITEBYTECODE = "1"

if ($Install) {
  python -m pip install --upgrade pip
  python -m pip install -e ".[dev,api]"
}

if (-not $NoClean) {
  python scripts\clean-local-artifacts.py --repo-root $RepoRoot | Out-Host
}

python -m pytest $PytestArgs
