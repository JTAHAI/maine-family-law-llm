# Pass 29 verifier production metric gate

Pass 29 is not a prose/workbench pass. It closes only when the citation and quote verifier are measured against external, attorney-reviewed gold rows.

Required external inputs:

- `eval_store/maine_citation_validity_gold.jsonl`
- `eval_store/maine_quote_span_gold.jsonl`
- an external authority citation index JSONL with `kind`, `normalized_citation`, `source_id`, and `authority_status`
- either a source-text JSONL or the parsed authority store containing `source_id` or `record_id` plus `text`

Run:

```powershell
python scripts/run-pass29-verifier-metrics.py `
  --eval-root D:\dev\ME_FM_LLM_data\eval_store `
  --authority-index D:\dev\ME_FM_LLM_data\authority_data_product\citation_index.jsonl `
  --parsed-authority-root D:\dev\ME_FM_LLM_data\parsed_authority_store `
  --output D:\dev\ME_FM_LLM_data\pass29_verifier_metrics.json `
  --measurement-output D:\dev\ME_FM_LLM_data\release_metric_measurements.pass29.partial.json `
  --require-ready

python scripts/audit-pass29-verifier-production.py `
  --metrics D:\dev\ME_FM_LLM_data\pass29_verifier_metrics.json `
  --output D:\dev\ME_FM_LLM_data\pass29_verifier_metrics_audit.json `
  --require-ready
```

True-GA pass criteria:

- citation existence rate is at least `0.99`
- quote-span verification rate is at least `0.97`
- every measured row is attorney-reviewed
- no seed, synthetic, fixture, or schema-validation row is counted
- every verified quote has a source ID and offsets
- unresolved citations and missing quote spans remain filing-ready blockers

The source repository now contains the metric runner and audit gate. It intentionally does not mark Pass 29 complete without the external metric report.
