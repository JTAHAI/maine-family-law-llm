# Pass 30 — Claim-support production metric gate

Pass 30 measures whether generated legal claims are supported by admitted source text, not merely whether a citation string exists.

## Inputs

External only:

- `eval_store/maine_citation_validity_gold.jsonl`
- `parsed_authority_store/**/*.jsonl` or an explicit source-text JSONL file

Rows must be attorney-reviewed. Seed, synthetic, fixture, or generated rows block readiness.

Recommended row fields:

- `claim` or `legal_claim` or `assertion` or `text_span`
- `source_id` or `source_ids`
- `expected_status`: `supported`, `partially_supported`, `unsupported`, `contradicted`, `stale`, `jurisdiction_mismatch`, or `not_verifiable`
- `review_status`
- `annotator_or_generation_method`

## Commands

```powershell
python scripts/run-pass30-claim-support-metrics.py `
  --eval-root D:\dev\ME_FM_LLM_data\eval_store `
  --parsed-authority-root D:\dev\ME_FM_LLM_data\parsed_authority_store `
  --output D:\dev\ME_FM_LLM_data\pass30_claim_support_metrics.json `
  --measurement-output D:\dev\ME_FM_LLM_data\release_metric_measurements.pass30.partial.json `
  --require-ready

python scripts/audit-pass30-claim-support-production.py `
  --metrics D:\dev\ME_FM_LLM_data\pass30_claim_support_metrics.json `
  --output D:\dev\ME_FM_LLM_data\pass30_claim_support_metrics_audit.json `
  --require-ready
```

## Exit criteria

- `citation_support >= 0.95`
- non-empty sample
- all rows attorney-reviewed
- zero seed/synthetic rows
- unsupported, contradicted, stale, jurisdiction-mismatched, or not-verifiable claims are measured and blocked when expected
