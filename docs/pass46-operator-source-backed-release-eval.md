# Pass 46 operator/source-backed release-eval gate

This gate gives the project a no-lawyer, no-fabrication release-eval lane.

It accepts only explicit `operator_source_backed` external measurements and keeps the boundary clear:

- `operator_release_allowed` may pass when source-backed metrics meet thresholds.
- `true_ga_release_allowed` remains `false` unless separate legal/pilot/signoff gates are satisfied.
- `attorney_reviewed`, `legal_signoff`, and `pilot_signoff` are never inferred by this lane.

Inputs:

- `retrieval_smoke_report.json`
- `source_update_report.json`
- `release_metric_measurements.pass29.partial.json`
- `release_metric_measurements.pass30.partial.json`
- `release_metric_measurements.pass31.partial.json`

Command:

```powershell
python scripts/run-pass46-operator-source-backed-release-eval.py `
  --data-root D:\dev\ME_FM_LLM_data `
  --eval-root D:\dev\ME_FM_LLM_data\eval_store `
  --output D:\dev\ME_FM_LLM_data\pass46_operator_source_backed_release_eval.json `
  --measurement-output D:\dev\ME_FM_LLM_data\release_metric_measurements.operator_source_backed.json `
  --require-ready
```

If any input is missing, undersized, non-source-backed, synthetic, or below threshold, the gate blocks.
