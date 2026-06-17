param(
  [string]$RepoRoot = "",
  [switch]$CleanAfterInstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
  $RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
}

$bootstrapScript = Join-Path $RepoRoot "scripts\bootstrap-windows-launcher.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $bootstrapScript -RepoRoot $RepoRoot -InstallOnly
if ($LASTEXITCODE -ne 0) {
  throw "Launcher bootstrap install failed."
}

if ($CleanAfterInstall) {
  python (Join-Path $RepoRoot "scripts\clean-local-artifacts.py") --repo-root $RepoRoot | Out-Host
}

Write-Host "Install complete. Launch START_MAINE_FAMILY_LAW_LLM.cmd from $RepoRoot"
