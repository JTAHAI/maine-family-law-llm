# V6.0.3 Release Control Center

The release control center is a local operator view for release hardening evidence. It does not certify Store approval, GA shipment, legal release, or production readiness on its own.

## What it shows

- Local observability status and SLO evidence
- Accessibility contract pass/fail state for the release dashboard
- Source SBOM and packaging hygiene
- Vulnerability evidence from Grype, pip-audit, and Semgrep
- MSIX signing, install smoke, and WACK evidence
- Red-team results
- Attorney sandbox pilot status
- Release candidate and shipment-readiness gate state

## What it does not claim

- It does not claim Microsoft Store approval
- It does not claim GA shipment
- It does not claim production legal readiness
- It does not replace the underlying evidence files

## Evidence sources

- `configs/maine_sre_reliability_policy.json`
- `configs/maine_release_pilot_hardening_policy.json`
- `legal/ops/release_pilot_hardening.py`
- `legal/ops/release_control_center.py`
- `legal/ops/supply_chain.py`
- `legal/security/legal_red_team.py`
- `legal/release/release_manifest.py`

## Operator flow

1. Open the release control center.
2. Review observability, accessibility, supply chain, and red-team sections.
3. Check the MSIX and vulnerability evidence sections.
4. Inspect the release candidate and shipment-readiness blockers.
5. Use the blocker list as the fail-closed ship gate.
