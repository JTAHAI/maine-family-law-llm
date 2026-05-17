param(
  [string]$RepoRoot = "C:\dev\ME_FM_LLM",
  [string]$DataRoot = "C:\dev\ME_FM_LLM_data"
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot
python scripts\run-enterprise-preflight.py --repo-root $RepoRoot --data-root $DataRoot --output enterprise_preflight_report.json
python scripts\build-public-attribution-kit.py --project-root $RepoRoot --output public_attribution_kit_report.json
python scripts\run-public-supply-chain-hardening.py --project-root $RepoRoot --output smoke_evidence_public_supply_chain_hardening.json --sbom-output source_sbom.json
python scripts\run-quality-checks.py
Write-Host "Local GitHub staging checks complete. Review JSON evidence before publishing."
