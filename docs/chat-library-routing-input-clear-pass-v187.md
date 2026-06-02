# v1.87.0 — Chat library routing and Enter-submit input clearing

This pass continues the deterministic, source-backed Maine family-law chat library build-out from v1.86.0.

## Changes

- Fixed the local workbench composer so pressing Enter submits the question and immediately clears the input box after the user message is accepted into the transcript.
- Added a regression marker for `enter_submit_clears_input` in the browser UI and runtime diagnostics payload.
- Expanded the deterministic chat library from 105 to 122 items.
- Added real-world phrasing coverage for:
  - court/process routing for ordinary family matters versus appeals;
  - appeal deadline and notice-of-appeal triage;
  - service method and proof-of-service questions;
  - no-response/default procedural questions;
  - continuance/postponement preparation;
  - PFA and parenting-time overlap;
  - DHHS/child-protection overlap;
  - grandparent/relative visitation triage;
  - caregiver guardianship versus informal-care questions;
  - GAL role/report questions;
  - modification/enforcement/contempt routing;
  - UCCJEA/out-of-state custody triage;
  - appellate standard-of-review/record triage;
  - required forms/fields audit;
  - school-counselor family-court boundaries;
  - reunification/progress-report therapist boundaries;
  - child-support calculation boundary language.
- Added conservative route overrides so broad words like `court`, `family`, `order`, `parent`, and `child` do not steal common questions from the correct topic.
- Reduced prompt-token overmatching by ignoring generic prompt words during deterministic scoring.

## Evidence

- Added `tests/test_chat_library_v187_input_clear_and_routing.py`.
- Refreshed chat-library workbench evidence at `docs/external-evidence/chat_library_workbench_evidence_v187.json`.
- Targeted local chat/UI tests passed.
- `scripts/doctor-local-repo.py --repo-root . --json` passed after cleaning local caches.

## Boundaries

Outputs remain source-backed, review-required, legal-information-only, not legal advice, and not filing-ready. This pass does not claim attorney review, legal signoff, real-matter pilot evidence, production GA, or filing-ready output.
