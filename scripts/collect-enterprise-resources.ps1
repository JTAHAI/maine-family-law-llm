param(
    [string]$RepoRoot = "C:\dev\ME_FM_LLM",
    [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
    [string]$Python = "python",
    [switch]$DryRun,
    [int]$MaxResources = 0,
    [switch]$IgnoreRobotsTxt
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $RepoRoot)) {
    throw "RepoRoot does not exist: $RepoRoot"
}
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null
Set-Location $RepoRoot

$argsList = @("scripts\collect-enterprise-resources.py", "--data-root", $DataRoot)
if ($DryRun) { $argsList += "--dry-run" }
if ($MaxResources -gt 0) { $argsList += @("--max-resources", "$MaxResources") }
if ($IgnoreRobotsTxt) { $argsList += "--ignore-robots-txt" }

& $Python @argsList
exit $LASTEXITCODE
