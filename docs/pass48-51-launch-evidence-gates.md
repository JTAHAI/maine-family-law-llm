# Passes 48-51 launch evidence gates

This repo has a fail-closed external evidence gate for the remaining launch and GA passes:

- Pass 48: `attorney_sandbox_pilot_report.json`
- Pass 49: `limited_real_matter_pilot_report.json`
- Pass 50: `ga_release_candidate_signoff.json`
- Pass 51: `ga_shipment_signoff.json`

The gate does not create or fake pilot reports, attorney participation, real-matter results, legal signoff, product signoff, ops signoff, or GA shipment. It only verifies externally supplied evidence, and it now requires structured supporting fields. A placeholder file such as `{ "status": "pass" }` stays blocked.

## Create blank external templates

The starter kit writes blocked-by-default templates. Use it outside the source repository in a data/evidence workspace:

```powershell
python scripts/build-pass48-51-launch-evidence-starter-kit.py `
  --output-root D:\dev\ME_FM_LLM_data\pass48_51_launch_evidence_starter
```

The templates intentionally default to `status: blocked`, empty signatures, and false controls. They are an operator convenience only and do not close Passes 48-51.

## Run the gate

```powershell
python scripts/run-pass48-51-launch-evidence-gates.py `
  --pilot-root D:\dev\ME_FM_LLM_data\pilot_evidence `
  --release-root D:\dev\ME_FM_LLM_data\release_evidence `
  --output D:\dev\ME_FM_LLM_data\pass48_51_launch_evidence_gate_report.json `
  --require-ready
```

Until the real external files exist, the gate returns `blocked` and lists the missing or incomplete evidence for each pass.

## Required structured fields

Pass 48 requires `source: external_pilot`, signature fields, at least one attorney reviewer, verified bar status, completed training, `real_matter_allowed: false`, zero open critical issues, and a reviewed feedback queue.

Pass 49 requires `source: external_pilot`, signature fields, at least one matter, explicit consent, tenant isolation, encrypted storage, completed human/attorney/daily review, no private training use, zero data leakage, zero unsupported filing-ready exports, and zero open incidents.

Pass 50 requires `source: external_release`, signature fields, a frozen release candidate, zero open P0/P1 blockers, an artifact inventory hash, and approved security, legal, product, and ops signoffs.

Pass 51 requires `source: external_release`, signature fields, `ga_shipped: true`, a passing release-candidate status, a shipment manifest hash, and every GA control set to true.

Do not put private matter facts, party names, docket numbers, uploaded documents, parsed authority stores, retrieval indexes, model weights, runtime databases, or eval stores in these files.
