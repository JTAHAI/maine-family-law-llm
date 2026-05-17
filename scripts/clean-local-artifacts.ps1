param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [switch]$IncludeVenv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$argsList = @("scripts\clean-local-artifacts.py", "--repo-root", $RepoRoot)
if ($IncludeVenv) { $argsList += "--include-venv" }
py -3.11 @argsList
