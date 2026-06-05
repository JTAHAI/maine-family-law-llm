# Enterprise Release Control v2.06

The v2.06 Enterprise Release Control Center is a fail-closed operator packet for the final production launch gates. It audits the existing Pass 48-51 external evidence gate and summarizes what remains before any enterprise release, production legal readiness, or GA shipment claim can be made.

It does not create or fake:

- attorney sandbox pilot evidence
- limited real-matter pilot evidence
- legal, security, product, or ops signoff
- release-candidate approval
- GA shipment
- filing-ready legal output

## Evidence

Generate deterministic repo evidence:

```powershell
python scripts/build-enterprise-release-control-evidence.py --require-ready
```

This writes:

```text
docs/external-evidence/enterprise_release_control_v206_packet.json
docs/external-evidence/enterprise_release_control_v206_audit.json
docs/external-evidence/enterprise_release_control_v206.html
docs/external-evidence/enterprise_release_control_v206_test_summary.json
```

The committed evidence is expected to show `enterprise_ready: false`, `production_legal_ready: false`, and `ga_shipped: false` until real external evidence is supplied.

## External Gate

Create blocked templates outside the source repo:

```powershell
python scripts/build-pass48-51-launch-evidence-starter-kit.py `
  --output-root D:\dev\ME_FM_LLM_data\pass48_51_launch
```

After the real attorney sandbox, limited pilot, release-candidate, and shipment evidence exists, run:

```powershell
python scripts/run-pass48-51-launch-evidence-gates.py `
  --pilot-root D:\dev\ME_FM_LLM_data\pass48_51_launch\pilot `
  --release-root D:\dev\ME_FM_LLM_data\pass48_51_launch\release `
  --require-ready
```

Do not put private matter facts, party names, docket numbers, uploaded documents, parsed authority stores, retrieval indexes, model weights, runtime databases, eval stores, or `.env` files in the source repo.

## Tests

```powershell
python -m py_compile legal/release/enterprise_release_control_v206.py
python -m pytest tests/test_enterprise_release_control_v206.py -q
python -m pytest tests/test_pass48_51_launch_evidence_gates.py tests/test_pass48_51_launch_evidence_starter_kit.py -q
```
