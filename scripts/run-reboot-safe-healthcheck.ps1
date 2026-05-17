param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "reboot_recovery_healthcheck.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $RepoRoot
py -3.11 scripts\run-reboot-safe-healthcheck.py --repo-root $RepoRoot --data-root $DataRoot --output $Output
