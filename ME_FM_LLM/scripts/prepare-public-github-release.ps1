param(
  [string]$ProjectRoot = "C:\dev\ME_FM_LLM",
  [string]$Output = "docs/sample-evidence/public_release_readiness.json"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
python "$ProjectRoot\scripts\prepare-public-github-release.py" --project-root $ProjectRoot --output $Output
