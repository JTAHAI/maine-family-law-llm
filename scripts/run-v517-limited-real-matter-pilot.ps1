param(
    [Parameter(Mandatory=$true)][string]$PilotRoot,
    [ValidateSet("status","create-program","enroll-matter","record-work-product","record-daily-review","record-signoff","build-evidence","verify-evidence")]
    [string]$Command = "status",
    [string[]]$AdditionalArguments = @()
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "run-v517-limited-real-matter-pilot.py"
& python $PythonScript --repo-root $RepoRoot --pilot-root $PilotRoot $Command @AdditionalArguments
exit $LASTEXITCODE
