param(
  [string]$RepoRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
  [switch]$IncludeVenv,
  [switch]$PreserveVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"

function Remove-WorkspacePath {
  param([string]$Path, [string]$Label)
  if (-not (Test-Path -LiteralPath $Path)) { return }
  $item = Get-Item -LiteralPath $Path -Force
  if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
    throw "Refusing to remove reparse-point workspace path: $Label"
  }
  Remove-Item -LiteralPath $Path -Recurse -Force
  Write-Output "removed $Label"
}

$cleanArgs = @(".\scripts\clean-local-artifacts.py", "--repo-root", $repo)
if ($IncludeVenv -or -not $PreserveVenv) { $cleanArgs += "--include-venv" }
python @cleanArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

foreach ($name in @(".local_tmp", ".mfl_work", ".proofs", ".sentinel_tmp")) {
  $path = Join-Path -Path $repo -ChildPath $name
  Remove-WorkspacePath -Path $path -Label $name
}

$pidFile = Join-Path -Path $repo -ChildPath ".local_server.pid"
if (Test-Path -LiteralPath $pidFile) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File .\STOP_LOCAL_TEST.ps1 -RepoRoot $repo
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $PreserveVenv) {
  foreach ($name in @(".venv", "venv", "env", "ME_FM_LLM_venv")) {
    $path = Join-Path -Path $repo -ChildPath $name
    Remove-WorkspacePath -Path $path -Label $name
  }
}

$doctorArgs = @(".\scripts\doctor-local-repo.py", "--repo-root", $repo, "--json")
if ($PreserveVenv) { $doctorArgs += "--allow-venv" }
python @doctorArgs
exit $LASTEXITCODE
