param(
  [string]$RepoRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
  [switch]$IncludeVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
Set-Location -LiteralPath $repo
$env:PYTHONDONTWRITEBYTECODE = "1"

$cleanArgs = @(".\scripts\clean-local-artifacts.py", "--repo-root", $repo)
if ($IncludeVenv) { $cleanArgs += "--include-venv" }
python @cleanArgs

$localTmp = Join-Path -Path $repo -ChildPath ".local_tmp"
if (Test-Path -LiteralPath $localTmp) {
  Remove-Item -LiteralPath $localTmp -Recurse -Force
  Write-Output "removed .local_tmp"
}

$workDir = Join-Path -Path $repo -ChildPath ".mfl_work"
if (Test-Path -LiteralPath $workDir) {
  Remove-Item -LiteralPath $workDir -Recurse -Force
  Write-Output "removed .mfl_work"
}

$pidFile = Join-Path -Path $repo -ChildPath ".local_server.pid"
if (Test-Path -LiteralPath $pidFile) {
  Remove-Item -LiteralPath $pidFile -Force
  Write-Output "removed .local_server.pid"
}

if ($IncludeVenv) {
  foreach ($name in @(".venv", "venv", "ME_FM_LLM_venv")) {
    $path = Join-Path -Path $repo -ChildPath $name
    if (Test-Path -LiteralPath $path) {
      Remove-Item -LiteralPath $path -Recurse -Force
      Write-Output "removed $name"
    }
  }
}

$doctorArgs = @(".\scripts\doctor-local-repo.py", "--repo-root", $repo, "--json")
if (-not $IncludeVenv) { $doctorArgs += "--allow-venv" }
python @doctorArgs
