# Pass 31 — Stale-law, jurisdiction, negative-treatment, and form-freshness metric gate

Pass 31 adds a production evidence gate for source-scope safety:

- current-law language must be blocked when source freshness is stale or unknown;
- out-of-Maine authority must be detected when the expected scope is Maine;
- negative-treatment unknown/unsafe authority must be surfaced as a blocker;
- court-form freshness must be measured with a current-version baseline.

The gate supports two honest review modes:

- `attorney_reviewed` for future lawyer-reviewed gold rows;
- `operator_source_backed` for rows built directly from verified source artifacts without labeling them attorney-reviewed.

## Required external datasets

`maine_staleness_jurisdiction_gold.jsonl` rows should include:

- `answer_text` or `text_span`
- `source_metadata` or source fields such as `source_id`, `source_class`, `jurisdiction`, `freshness_status`, `authority_status`, `negative_treatment_status`, `form_version_status`
- `expected_status`: `verified_scope`, `stale_or_unknown_freshness`, `jurisdiction_mismatch`, `negative_treatment_unknown`, `form_freshness_not_verified`, or `current_law_claim_without_sources`
- review-mode fields matching the selected mode

`maine_forms_freshness_gold.jsonl` rows should include:

- `form_id`
- `version_date`
- `current_version_date` or `current_versions`
- `expected_freshness_status`: `current`, `stale`, or `unknown`
- review-mode fields matching the selected mode

## Outputs

The runner writes:

- `pass31_staleness_jurisdiction_metrics.json`
- `release_metric_measurements.pass31.partial.json`

The measurement file includes:

- `scope_verification` target `>= 1.0`
- `form_freshness_detection` target `>= 0.99`

The release metric needed by full GA evidence is `form_freshness_detection`.
