param(
  [switch]$SkipTests,
  [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"

powershell -ExecutionPolicy Bypass -File .\REPAIR_LOCAL_REPO.ps1 -RepoRoot $repo

$venv = Join-Path -Path $repo -ChildPath ".venv"
if (-not (Test-Path -LiteralPath $venv)) {
  python -m venv $venv
}

$python = Join-Path -Path $venv -ChildPath "Scripts\python.exe"
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m pip install -e ".[api]"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python .\scripts\clean-local-artifacts.py --repo-root $repo

if (-not $SkipTests) {
  & $python -m pytest -q
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$env:PYTHONPATH = "$repo\src;$repo"
& $python -m pip show uvicorn | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
powershell -ExecutionPolicy Bypass -File .\scripts\local-test-spin-up.ps1 -RepoRoot $repo -Port $Port -SkipTests -PythonExe $python
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
