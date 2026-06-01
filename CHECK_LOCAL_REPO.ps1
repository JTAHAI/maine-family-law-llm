param(
  [string]$RepoRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
  [switch]$AllowVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repo = [System.IO.Path]::GetFullPath($RepoRoot)
$argsList = @(".\scripts\doctor-local-repo.py", "--repo-root", $repo, "--json")
if ($AllowVenv) { $argsList += "--allow-venv" }
python @argsList
exit $LASTEXITCODE
