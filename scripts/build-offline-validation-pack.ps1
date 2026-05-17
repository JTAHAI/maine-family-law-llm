param(
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "offline_validation_pack_report.json"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
python "scripts\build-offline-validation-pack.py" --data-root $DataRoot --output $Output
