param(
    [string]$Message = "Run public-source pre-push gate",
    [string]$Branch = "main",
    [switch]$SkipTests,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    $ArgsList = @(
        ".\scripts\git-safe-push.py",
        "--repo-root", ".",
        "--message", $Message,
        "--branch", $Branch,
        "--output", ".\docs\external-evidence\git_safe_push_v192.json"
    )
    if ($SkipTests) { $ArgsList += "--skip-tests" }
    if ($DryRun) { $ArgsList += "--dry-run" }
    python @ArgsList
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}
