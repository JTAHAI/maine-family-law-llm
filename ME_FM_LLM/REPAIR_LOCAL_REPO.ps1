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

$cleanArgs = @(".\scripts\clean-local-artifacts.py", "--repo-root", $repo)
if ($IncludeVenv -or -not $PreserveVenv) { $cleanArgs += "--include-venv" }
python @cleanArgs

foreach ($name in @(".local_tmp", ".mfl_work", ".proofs", ".sentinel_tmp")) {
  $path = Join-Path -Path $repo -ChildPath $name
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
    Write-Output "removed $name"
  }
}

$pidFile = Join-Path -Path $repo -ChildPath ".local_server.pid"
if (Test-Path -LiteralPath $pidFile) {
  Remove-Item -LiteralPath $pidFile -Force
  Write-Output "removed .local_server.pid"
}

if (-not $PreserveVenv) {
  foreach ($name in @(".venv", "venv", "env", "ME_FM_LLM_venv")) {
    $path = Join-Path -Path $repo -ChildPath $name
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Recurse -Force
      Write-Output "removed $name"
    }
  }
}

$doctorArgs = @(".\scripts\doctor-local-repo.py", "--repo-root", $repo, "--json")
if ($PreserveVenv) { $doctorArgs += "--allow-venv" }
python @doctorArgs
