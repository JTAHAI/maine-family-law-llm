## v2.05.0 — Family Justice Workbench polish

- Added `legal/product/family_justice_workbench_v205.py`, a deterministic Family Justice Workbench packet builder for parent, caregiver, lawyer, counselor, therapist, and reviewer pathways.
- Added source-card-first packets with issue labels, posture routing, safety/urgency routing, missing-information checklists, next-best-action planning, red flags, authority matrix previews, filing-gate blocker explanations, and reviewer handoff exports.
- Added `scripts/build-family-justice-workbench-evidence.py` and deterministic evidence outputs for packet JSON, audit JSON, HTML demo, and test summary under `docs/external-evidence/`.
- Exposed `/api/family-justice-workbench` in the local API without changing existing chat endpoints.
- Added focused v2.05 regression tests and a local clean ZIP helper script. Outputs remain legal-information-only, review_required by default, not filing_ready, and not current-law certified without official-source verification and human review.

## v1.93.0 — Attorney sandbox review kit and Pass 48 pilot prep

- Added a fail-closed attorney sandbox review-kit builder for Pass 48 that creates public/synthetic review queues, onboarding, feedback triage, dashboard, bar-status attestation, and reviewer-instruction templates outside the source repo.
- Added `scripts/build-attorney-sandbox-review-kit.py` so a local operator can produce an attorney-review packet without copying private matter data into Git.
- Wired v1.93 regression coverage into CI and the safe-push focused test list so the public push path checks the attorney-review-kit guardrails.
- Updated pre-push report defaults to v1.93 output names while preserving the existing no-op-safe push wrapper.
- No attorney review, Maine bar verification, real-matter pilot, GA shipment, production legal readiness, or filing-ready status is claimed.

## v1.92.0 — No-op-safe push wrapper and push gate regression

- Added a Python-backed `scripts/git-safe-push.py` wrapper that runs clean-local-artifacts, local doctor, public-source preflight, focused regression tests, `git add -A`, and `git push` from one tested path.
- Hardened `PUSH_SAFE.ps1`, `scripts/git-safe-push.ps1`, and `scripts/git-safe-push.sh` to delegate to the Python wrapper instead of duplicating raw commit/push logic.
- Made the push path no-op safe: after staging it checks `git diff --cached --quiet` and skips `git commit` when there are no staged changes, then still pushes the requested branch.
- Added dry-run/report output support and v1.92 regression tests for no-op commits, dry-run staged changes, wrapper delegation, and CI guardrails.
- Extended the public-source pre-push gate with a `git_safe_push_wrapper` check. No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status is claimed.


## v1.91.0 — Public-source pre-push gate and push wrappers

- Added a fail-closed public-source pre-push gate that aggregates local doctor hygiene, public repo readiness, version consistency, CI guardrail coverage, and the expected blocked Pass 48-51 external launch-evidence state.
- Added `scripts/run-public-source-preflight.py`, root `PUSH_SAFE.ps1`, `scripts/git-safe-push.ps1`, and `scripts/git-safe-push.sh` so a local push runs cleanup, doctor, preflight, focused tests, commit, and push in one command.
- Updated package metadata from the stale v1.89 value to v1.91.0 and added regression coverage so pyproject/package version drift is caught.
- Updated GitHub CI to run the public-source pre-push gate plus the strict Pass 48-51 launch-evidence tests.
- No attorney review, legal signoff, real-matter pilot, release-candidate approval, GA shipment, private data packaging, or filing-ready status is claimed.

## v1.89.0 — Pass 19-25 authority/retrieval hardening and Pass 28 evidence repair

- Fixed parsed Law Court opinion-index rows so official opinion references no longer fail when the index parser emits `OpinionReference` without a `court` field.
- Extended `RetrievalDocument` with `chunk_id` and `parent_document_id` so Pass 23 retrieval indexes, vector rows, parent-child chunk rows, and hybrid document reloads use the same schema.
- Hardened direct form parsing so official form PDFs/text snapshots can fall back to stable URL-derived identifiers without failing on absent `required_fields`.
- Re-ran focused Pass 19-28, parsed-authority, retrieval-index, and repo-hygiene tests.
- Preserves external-data boundaries: official snapshots, parsed stores, embedding stores, and gold eval packs remain outside the source repo.

## v1.88.0 — Repo hygiene recovery and enterprise collection repair

- Restored packaged `.gitignore` and required `.github` workflow/template files so `robocopy /MIR` no longer deletes required public repo metadata.
- Added missing `legal.documents.models`, `legal.retrieval.models`, `legal.matter.models`, and `legal.answering.models` dataclass stubs used by existing enterprise/test modules.
- Preserved v1.87 chat-library routing and Enter-submit input-clearing behavior.
- Added recovery guidance to remove previously committed `.mfl_work`, `.pytest_cache`, `__pycache__`, and `*.pyc` contamination from the Git index and working tree.
- Kept outputs source-backed, review-required, and not filing-ready.


## v1.87.0 — Chat library routing and Enter-submit input clearing

- Fixed the local browser workbench so accepted Enter-submit/send actions clear the question box after adding the user message to the transcript.
- Expanded the deterministic source-backed chat library from 105 to 122 items with more everyday Maine family-law phrasing.
- Added conservative route overrides for court routing, appeals/deadlines, service, no-response/default, PFA-child contact, DHHS overlap, GAL, UCCJEA, forms, support calculation boundaries, caregiver/relative, counselor, and therapist questions.
- Hardened matching to reduce wrong-topic answers from generic prompt words such as court, family, order, parent, and child.
- Added v1.87 regression tests and refreshed chat-library workbench evidence.
- No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status claimed.

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
