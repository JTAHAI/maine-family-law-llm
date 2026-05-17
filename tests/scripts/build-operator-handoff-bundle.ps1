param(
    [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
    [string]$Output = "operator_handoff_bundle.json"
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot
python scripts\build-operator-handoff-bundle.py --data-root $DataRoot --output $Output
