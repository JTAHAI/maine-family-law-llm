# Pass 48 attorney sandbox review kit — v1.93

This pass adds a dedicated external review-kit builder for the attorney-only sandbox pilot. The kit is designed for Maine-licensed attorney reviewers and intentionally remains fail-closed until real external review is completed and signed.

## What the kit creates

Run:

```powershell
python .\scripts\build-attorney-sandbox-review-kit.py --output-root D:\dev\MFL_pass48_attorney_sandbox_review --max-questions 48
```

The builder writes an external folder with:

- a public/synthetic chat-library review queue,
- attorney onboarding checklist,
- feedback triage queue template,
- dashboard template,
- bar-status attestation template,
- reviewer instructions,
- a blocked `attorney_sandbox_pilot_report.json` launch-evidence template.

## What the kit does not do

The kit does not create attorney review, does not claim Maine bar verification, does not allow real private matter files, does not mark any answer filing-ready, and does not close Pass 48. The generated `attorney_sandbox_pilot_report.json` defaults to `blocked`, so `scripts/run-pass48-51-launch-evidence-gates.py --require-ready` continues to fail until external evidence is actually completed.

## Data boundary

The generated question queue is built from the bundled public/synthetic chat library. Reviewers must not paste real client facts, party names, docket numbers, sealed or juvenile records, treatment records, or uploaded documents into the sandbox. Any approved feedback that becomes an eval candidate still requires separate review before it can be counted as gold evidence.

## Acceptance checks

The v1.93 regression tests verify that the kit is created, contains review-required queue rows, blocks real matter/private data by default, and does not close the Pass 48-51 launch gate without external signoff.
