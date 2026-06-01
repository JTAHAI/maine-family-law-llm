param(
  [switch]$SkipTests,
  [int]$Port = 8000,
  [ValidateSet("LocalWorkbench", "Enterprise")]
  [string]$ApiMode = "LocalWorkbench",
  [string]$VenvPath = "D:\dev\ME_FM_LLM_venv",
  [switch]$OpenBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"

powershell -ExecutionPolicy Bypass -File .\REPAIR_LOCAL_REPO.ps1 -RepoRoot $repo

$venv = [System.IO.Path]::GetFullPath($VenvPath)
if (-not (Test-Path -LiteralPath $venv)) {
  python -m venv $venv
}

$python = Join-Path -Path $venv -ChildPath "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
  $python = Join-Path -Path $venv -ChildPath "bin/python"
}
if (-not (Test-Path -LiteralPath $python)) {
  throw "python_not_found_in_venv:$venv"
}

& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pip install -e ".[dev,api]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python .\scripts\clean-local-artifacts.py --repo-root $repo
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipTests) {
  & $python -m pytest -q
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$sep = [System.IO.Path]::PathSeparator
$env:PYTHONPATH = "$repo\src$sep$repo"
& $python -m pip show uvicorn | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

powershell -ExecutionPolicy Bypass -File .\scripts\local-test-spin-up.ps1 -RepoRoot $repo -Port $Port -SkipTests -PythonExe $python -ApiMode $ApiMode
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$url = "http://127.0.0.1:$Port/"
Write-Output "workbench_url=$url"
if ($OpenBrowser) { Start-Process $url }
