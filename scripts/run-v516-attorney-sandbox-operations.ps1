param(
    [Parameter(Mandatory=$true)][string]$PilotRoot,
    [ValidateSet("status","create-program","build-evidence","verify-evidence","export-eval-candidates","record-attestation")]
    [string]$Command = "status",
    [string[]]$AdditionalArguments = @()
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonScript = Join-Path $PSScriptRoot "run-v516-attorney-sandbox-operations.py"
& python $PythonScript --repo-root $RepoRoot --pilot-root $PilotRoot $Command @AdditionalArguments
exit $LASTEXITCODE
