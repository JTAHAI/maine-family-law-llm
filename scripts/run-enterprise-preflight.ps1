param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "docs/sample-evidence/enterprise_preflight_report.json"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
python "$RepoRoot\scripts\run-enterprise-preflight.py" --repo-root $RepoRoot --data-root $DataRoot --output $Output
