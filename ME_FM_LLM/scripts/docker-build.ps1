param(
    [string]$ImageTag = "maine-family-law-llm:local"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

docker build --pull -t $ImageTag -f Dockerfile .
