## v1.86.0 — Classic desktop FOCAF research workbench UI

- Reworked the local browser workbench into a classic Windows-style FOCAF Research Workbench shell matching the requested layout reference.
- Added title bar, menu bar, hero band, control strip, dense two-column chat/sidebar workspace, bottom tabs, and status bar.
- Preserved Enter-to-submit, appeals routing, runtime diagnostics, brand asset serving, source cards, transcript export, and reviewer handoff metadata.
- Added v1.86 UI regression tests for the classic desktop shell markers and appeals/Enter wiring.
- No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status claimed.


## v1.86.0 — FOCAF classic desktop FOCAF workbench UI

- Adds the FOCAF Maine Family Law LLM brand kit to the repo under `assets/brand/focaf_family_law_llm_brand_kit/`.
- Serves local brand assets from `/brand-assets`.
- Updates the local browser workbench with favicon, FOCAF logo assets, brand CSS, a hero shell, runtime status cards, and brand asset diagnostics.
- Preserves Enter-to-submit, runtime diagnostics, and appeals routing regression coverage.
- Outputs remain source-backed, review-required, legal-information-only, and not filing-ready.

## v1.57.0 — Derived authority quarantine continuation hardening

- Second-wave derived authority ingestion now quarantines isolated failed follow-up targets and continues through later batches instead of blocking the entire authority data-product run after partial success.
- Quarantine remains bounded and auditable with failure count/rate limits, a persistent `derived_authority_quarantine.json`, and a machine-readable `derived_authority_ingest_report.json`.
- Derived official URLs now percent-encode spaces/control-character artifacts before fetch.
- Added regression coverage for the exact failure shape seen in live ingestion: successful records plus a small number of stale/malformed official-rule PDF links.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains open until the rerun completes with external evidence.

## v1.56.0 — Resumable derived authority ingest hardening

- Replaced all-or-nothing second-wave direct authority ingestion with a resumable chunked runner.
- Added per-batch timeout controls for large derived target catalogs.
- Added a narrow official Title 19-A direct statute-section bootstrap target when title indexes expose no direct section links.
- Increased the authority data-product harness default step timeout so full follow-up ingestion is not killed at 600 seconds.

## v1.55.0 — Follow-up direct authority gate ordering repair

Fixes the Pass 19/20 handoff ordering discovered during live local ingestion: when `--ingest-followup-targets` and `--require-direct-authority` are both set, the first parsed-authority audit now permits reference/index-only records so derived direct targets can be built and fetched. The strict direct-authority gate still runs after follow-up ingest and parsed-store rebuild.

## v1.54.0 — Official source target 404 repair

- Replaced stale Maine Judicial Branch records-access target with the current Court Records help page URL.
- Replaced unpublished/404 2026 Law Court opinion index target with the stable 2019 published-opinions index so the required seven Law Court index baseline can pass when current-year index is not yet published.
- Added regression coverage to prevent reintroducing the known 404 source targets.

## v1.53.0 — Conflicting status fail-closed hardening

- Hardened true-GA evidence status checks so terminal negative status/readiness/result values override otherwise-positive booleans such as `signed: true`.
- Added regression coverage proving a blocked GA release-candidate signoff cannot close Pass 50 merely because a signoff flag is true.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains the live external-data blocker.

## v1.52.0 — External evidence report schema hardening

- Hardened the formal GA evidence auditor so skeletal status-only JSON reports cannot close true-GA passes.
- Pass 19 authority-build evidence now requires an explicit production-ready audit report, ready-state marker, nonzero source count, and an external manifest path.
- Pass 26 annotation-queue evidence now requires nonempty queue-audit counts, all rows to remain `needs_attorney_review`, and zero private-training rows.
- Added regression coverage proving `{"status":"pass"}` is not enough to close Pass 19.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains the live external-data blocker.

## v1.51.0 — GA tracker integrity hardening

- Hardened the formal true-GA tracker so the completed-pass list, per-pass status rows, pass range, duplicate pass numbers, and next-pass marker must agree before the tracker reports pass.
- Hardened the GA evidence auditor so a blocked or warning-bearing tracker blocks completed-pass evidence counting even when individual artifacts exist.
- Added regression tests for mismatched completed pass rows, wrong next-pass markers, and evidence-audit refusal under a corrupted tracker.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains the live external-data blocker.

## v1.50.0 — External audit CLI fail-closed hardening

- Hardened external authority and enterprise readiness audit CLIs so subprocess automation fails closed when reports are not production-ready.
- Added regression coverage for blocked external authority evidence and incomplete enterprise readiness evidence.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains the live external-data blocker.

## v1.49.0 — Source ZIP evidence packaging hardening

- Regenerated missing Pass 41/42 model governance and injection-defense evidence artifacts that the formal GA evidence gate requires for the already-closed repo-only passes.
- Removed broad `*_report.json` / `*_evidence.json` package exclusions that could silently drop machine-audited repo evidence from source ZIPs.
- Added `scripts/audit-source-zip-contents.py` and wired package scripts to verify finished ZIPs contain required GA evidence artifacts while still excluding runtime/legal data products.
- Added regression coverage proving packaged source ZIPs cannot omit required GA evidence files.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains the live external-data blocker.

# Release Notes

## v1.48.0 — GA evidence status hardening

- Hardened GA evidence status checks so a report with non-empty blockers or explicit negative gate fields cannot satisfy true-GA evidence, even if a legacy `status` field says `pass`.
- Added regression coverage proving a blocked authority-build audit cannot close Pass 19 through status-string spoofing.
- True GA count remains 7 complete / 26 remaining; Pass 19 remains open until live official-source ingestion runs in an external data root and passes the real authority audit.

## v1.47.0 — Source manifest evidence hardening

- Hardened true-GA evidence audit so a completed Pass 19 cannot be accepted with a minimal placeholder source manifest.
- Required source manifest evidence records to include official authority metadata, parser audit, freshness status, snapshot path, and snapshot hash integrity.
- Added regression coverage for placeholder records and missing external snapshots.

# Maine Family Law LLM Release Notes

## v1.46.0 — Authority manifest containment hardening

This package hardens external authority-build auditing so live-ingestion evidence cannot point at repo-local or out-of-store snapshot files. The official source manifest audit now blocks non-object manifest rows, duplicate source IDs, invalid retrieved timestamps, malformed parser audit payloads, parser-status mismatches, snapshots outside the external official authority store, and snapshots inside the source repository.

True GA count remains 7 complete / 26 remaining. Pass 19 remains open until live official-source ingestion runs in a networked external data root and the real authority audit passes.

## v1.45.0 — Release metric measurement integrity hardening

This package hardens the GA release metric path so attorney-reviewed gold rows alone cannot create placeholder production metrics. Legal-quality GA metrics now require a task-specific external measurement report, and the runner fails closed on missing measurements, malformed metric values, repo-local measurement files, repo-local eval roots used for GA metrics, inflated sample sizes, and missing passing source-freshness evidence.

True GA count remains 7 complete / 26 remaining. Pass 19 remains open until live official-source ingestion runs in a networked external data root and the real authority audit passes.

## Pass 50-51 GA release-control package

This package completes the source-code controls for the release-candidate and GA shipment stages:

- Versioned release-candidate artifact inventory.
- Security, legal, product, and operations signoff gate.
- Open P0/P1 blocker gate.
- Final GA shipment artifact manifest.
- GA definition controls for clean deployment, official authority, attorney-reviewed evals, release metrics, filing-ready gate behavior, matter-data protection, audit trails, security, pilot evidence, rollback, and maintenance operations.

The source repository still does not package external legal corpora, parsed authority stores, retrieval indexes, matter files, model weights, or runtime databases.

## v1.81.0 — Chat prompt packs and source drilldown hardening

- Expanded source-backed deterministic chat library to 78 items.
- Added role-specific starter prompt packs for parent, lawyer/advocate, caregiver, counselor, and therapist users.
- Added `/api/starter-prompt-packs` and `questions_to_ask` answer style.
- Added source-card inspection and JSON transcript export in the local browser workbench.
- Added focused regression tests and refreshed chat evidence at `docs/external-evidence/chat_library_workbench_evidence_v181.json`.
- Outputs remain review-required and not filing-ready; no attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status is claimed.


## v1.82.0 — Chat missing-information and reviewer-handoff hardening

- Expanded deterministic chat library to 104 items.
- Added missing-information checklist style and role-specific follow-up metadata.
- Added `/api/missing-information-prompts`.
- Added reviewer handoff UI panel and JSON transcript export metadata.
- Added v1.82 focused regression tests and refreshed chat evidence.
- No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status is claimed.


## v1.83.0 - Live browser Enter-submit and FOCAF branding fix

- Fixes live local chat workbench JavaScript parsing so the Enter key handler attaches.
- Adds visible FOCAF/live UI version markers for browser cache verification.
- Restores required `.github` public repo files and `.gitignore` to prevent doctor failures after ZIP overlay.
- Adds v1.83 regression coverage and evidence output.

## v1.84.0 — Appeals routing and runtime diagnostics

- Fixed deterministic chat-library routing for `What court handles appeals?` so the answer no longer returns a parenting/contact schedule response.
- Added source-backed appeals fixtures and source cards for Maine Judicial Branch appeals and Maine Rules of Appellate Procedure.
- Added `/api/runtime-diagnostics` and visible UI diagnostics so stale local servers/builds are obvious.
- Added v1.84 regression tests and refreshed chat-library evidence.
