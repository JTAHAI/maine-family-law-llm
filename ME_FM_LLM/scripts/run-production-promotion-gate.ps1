param(
    [string]$ProjectRoot = "C:\dev\ME_FM_LLM",
    [string]$DataRoot = "C:\dev\ME_FM_LLM_data",
    [string]$Output = "docs/sample-evidence/production_promotion_gate_report.json",
    [switch]$AllowFailReport
)

$ErrorActionPreference = "Stop"
Push-Location $ProjectRoot
try {
    $argsList = @("scripts\run-production-promotion-gate.py", "--data-root", $DataRoot, "--output", $Output)
    if ($AllowFailReport) { $argsList += "--allow-fail-report" }
    python @argsList
}
finally {
    Pop-Location
}
