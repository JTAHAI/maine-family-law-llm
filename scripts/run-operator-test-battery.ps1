param(
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "operator_test_battery_evidence.json"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot
python scripts\run-operator-test-battery.py --data-root $DataRoot --output $Output
