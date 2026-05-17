param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
  [string]$Output = "local_test_readiness_report.json",
  [switch]$SkipPytest,
  [switch]$IncludeQualityChecks,
  [int]$TimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $RepoRoot
$argsList = @("scripts\run-test-readiness.py", "--repo-root", $RepoRoot, "--data-root", $DataRoot, "--output", $Output, "--timeout-seconds", "$TimeoutSeconds")
if ($SkipPytest) { $argsList += "--skip-pytest" }
if ($IncludeQualityChecks) { $argsList += "--include-quality-checks" }
python scripts\clean-local-artifacts.py --repo-root $RepoRoot | Out-Host
python @argsList
