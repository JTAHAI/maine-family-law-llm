param(
  [switch]$SkipTests,
  [ValidateRange(1, 65535)]
  [int]$Port = 8000,
  [ValidateSet("LocalWorkbench", "Enterprise")]
  [string]$ApiMode = "LocalWorkbench",
  [string]$VenvPath = "",
  [switch]$OpenBrowser,
  [switch]$ResetEnvironment,
  [switch]$RefreshDependencies
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"

# Keep the environment beside the checkout unless an operator explicitly
# chooses another location.  A release ZIP must not depend on a developer's
# old drive letter or unrelated checkout.
if (-not $VenvPath) {
  $VenvPath = Join-Path $repo ".venv"
}

# Stop only a verified workbench process before maintenance removes its PID
# receipt. This prevents a prior successful launch from becoming an opaque
# port conflict on the next launch.
$pidPath = Join-Path $repo ".local_server.pid"
if (Test-Path -LiteralPath $pidPath) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File .\STOP_LOCAL_TEST.ps1 -RepoRoot $repo
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# A normal launch preserves the nearby environment so local startup remains
# usable offline and does not reinstall every dependency. Operators can opt
# into a full environment reset when troubleshooting a corrupted venv.
$repairArgs = @("-RepoRoot", $repo, "-PreserveVenv")
if ($ResetEnvironment) {
  $repairArgs = @("-RepoRoot", $repo, "-IncludeVenv")
}
& powershell -NoProfile -ExecutionPolicy Bypass -File .\REPAIR_LOCAL_REPO.ps1 @repairArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

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

$dependenciesReady = $false
try {
  & $python -c "import fastapi, uvicorn, pypdf, docx, pytest"
  $dependenciesReady = ($LASTEXITCODE -eq 0)
} catch {
  $dependenciesReady = $false
}

if ($RefreshDependencies -or -not $dependenciesReady) {
  Write-Output "dependencies=installing"
  & $python -m pip install --upgrade pip
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & $python -m pip install -e ".[dev,api]"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
  Write-Output "dependencies=ready; install_skipped=true"
}

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

& powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local-test-spin-up.ps1 -RepoRoot $repo -Port $Port -SkipTests -PythonExe $python -ApiMode $ApiMode
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$url = "http://127.0.0.1:$Port/"
Write-Output "workbench_url=$url"
if ($OpenBrowser) { Start-Process $url }
