# Passes 48-51 launch evidence gates

This repo now has a fail-closed external evidence gate for the remaining launch and GA passes:

- Pass 48: `attorney_sandbox_pilot_report.json`
- Pass 49: `limited_real_matter_pilot_report.json`
- Pass 50: `ga_release_candidate_signoff.json`
- Pass 51: `ga_shipment_signoff.json`

The gate does not create or fake pilot reports, attorney participation, real-matter results, legal signoff, product signoff, ops signoff, or GA shipment. It only verifies that externally supplied evidence exists and has an allowed status.

Run:

```powershell
python scripts/run-pass48-51-launch-evidence-gates.py `
  --pilot-root D:\dev\ME_FM_LLM_data\pilot_evidence `
  --release-root D:\dev\ME_FM_LLM_data\release_evidence `
  --output D:\dev\ME_FM_LLM_data\pass48_51_launch_evidence_gate_report.json `
  --require-ready
```

Until the real external files exist, the gate returns `blocked` and lists the missing artifact for each pass.
