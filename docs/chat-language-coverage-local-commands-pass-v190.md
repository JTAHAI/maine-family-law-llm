# v1.90 local command compatibility and chat language hardening pass

## Purpose

v1.90 fixes the operator-command mismatch discovered during local testing and expands deterministic chat routing for more real-world Maine family-law phrasing. This is still a source-backed local workbench pass, not attorney review, legal signoff, a real-matter pilot, production GA, or filing-ready output.

## Operator compatibility fixes

- Added `scripts/doctor_local_repo.py` as a compatibility wrapper for `scripts/doctor-local-repo.py` so either command works.
- Kept the canonical install path as `python -m pip install -e ".[dev,api]"`.
- Kept local chat startup on `maine_family_law_llm.api:app`; the enterprise API remains available as `app.api.main:app` for protected API work.

## Chat coverage added

The deterministic question library now covers at least 152 items and adds routes for:

- clerk logistics versus legal advice;
- interpreter, ADA, and access/accommodation questions;
- post-hearing/new-order checklists;
- emergency motion and urgent child-safety routing;
- PFA/protection-order violation triage;
- DHHS/support-enforcement overlap;
- financial affidavit and income paperwork;
- appeal transcript/record checks;
- Rule 59/Rule 60/reconsideration/finding/appeal routing;
- contempt/enforcement evidence checklist;
- caregiver school/medical authority proof;
- GAL fee/scope/report concerns;
- counselor subpoena/records requests;
- therapist court-ordered evaluation/recommendation boundaries.

## Validation target

The v1.90 focused gate is:

```powershell
python scripts\doctor-local-repo.py
python scripts\doctor_local_repo.py
python -m pytest -q `
  tests/test_chat_language_coverage_v189.py `
  tests/test_chat_language_coverage_v190.py `
  tests/test_local_operator_commands_v190.py `
  tests/test_repo_hygiene_recovery_v188.py `
  tests/test_chat_library_v187_input_clear_and_routing.py
python scripts\run-chat-library-evidence.py --output docs\external-evidence\chat_library_workbench_evidence_v190.json --require-ready
```

## Remaining pass count

- Formal enterprise GA pass count remains 33 passes: Pass 19 through Pass 51.
- Practical chat/LLM pass count is now 35 passes: the 33 formal GA passes plus 2 additional chat/answer-planner passes before or alongside live official-source ingestion.
