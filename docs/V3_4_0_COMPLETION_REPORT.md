# Maine Family Law LLM v3.4.0 Completion Report

v3.4.0 upgrades multi-turn conversation reliability and the trust boundary between user instructions, Maine-law authority, and private records.

## Completed

- Fixed the browser reviewer-handoff runtime defect that could replace a successful chat answer with an error.
- Routed all source-card follow-ups through the session-isolated server instead of browser-local stale state.
- Added lane-aware, ordinal, and last-card source selection without rerunning retrieval.
- Prevented an older source set from surviving a newer answer with no citations.
- Added explicit, bounded continuity for short follow-ups using only sanitized routing labels.
- Prevented raw prior questions, dates, docket numbers, courts, search targets, and safety flags from entering continuity state.
- Recomputed current-turn safety independently on every message.
- Added prompt and source-text instruction-boundary scanning with visible warnings.
- Preserved original source snippets while labeling instruction-like content as untrusted data.
- Added inferred-year and relative-date normalization with visible basis disclosures.
- Bounded additional public API surfaces and sanitized OCR background-worker errors.
- Bumped product and Store package targets to 3.4.0 / 3.4.0.0.
- Added regression tests and synthetic, non-private release evidence.

## Validation

- Automated collection: **658 tests**.
- Batched execution: **657 passed, 1 skipped**.
- New v3.4 tests: **9 passed**.
- Extracted source-ZIP release smoke: **61 passed**.
- FOCAF assets: **103/103 resolved with matching hashes**.
- Python compilation, JavaScript syntax, desktop coverage under Xvfb, local doctor, release artifact audit, public-source readiness, and package hygiene passed.

## Not claimed

No signed Windows MSIX was produced and WACK was not run in this Linux environment. This source package does not claim production legal GA, attorney validation, current-law completeness, or filing-ready automation.
