param(
    [string]$ImageTag = "maine-family-law-llm:local",
    [string]$DataRoot = $(if ($env:MAINE_FAMILY_LAW_DATA_ROOT) { $env:MAINE_FAMILY_LAW_DATA_ROOT } else { "C:\dev\ME_FM_LLM_data" }),
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force -Path $DataRoot | Out-Null

docker run --rm `
    --name maine-family-law-llm-api `
    --user 10001:10001 `
    --read-only `
    --tmpfs /tmp:rw,noexec,nosuid,size=64m `
    --security-opt no-new-privileges:true `
    --cap-drop ALL `
    -e MAINE_FAMILY_LAW_DATA_ROOT=/data `
    -e PYTHONPATH=/app `
    -p "127.0.0.1:$Port`:8000" `
    -v "${DataRoot}:/data" `
    -v "${RepoRoot}:/app:ro" `
    $ImageTag
