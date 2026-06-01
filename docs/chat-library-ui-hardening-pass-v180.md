# Chat library and local workbench hardening — v1.80.0

This pass expands the local browser chat workbench so more everyday Maine family-law questions receive deterministic, source-backed, review-required responses without relying on model memory.

## What changed

- Expanded the deterministic chat library to 54 starter responses across parents, lawyers/advocates, caregivers, counselors, and therapists.
- Added common parent questions for divorce first steps, unmarried parents, temporary/interim hearings, supervised contact, school/medical decision-making, relocation/move flags, messages/evidence, missed exchanges, and support-change preparation.
- Added lawyer/advocate questions for intake triage, plain-language client explanations, appeal/findings checks, source-card audits, contrary-authority review, and self-represented helper boundaries.
- Added caregiver questions for school/medical records, grandparent/relative contact, and DHHS/child-safety overlap.
- Added counselor and therapist questions for subpoenas/orders, questions-for-counsel support, safety disclosures, session-note upload boundaries, parenting-recommendation boundaries, child-preference boundaries, and contact-work safety boundaries.
- Added answer styles: intake triage, professional-boundary note, and source-card audit table.
- Added `/api/question-topics` for UI topic filtering.
- Improved the local workbench with topic filtering, quick topic search, audience-based answer-style presets, richer source cards, copyable source-card JSON, and transcript exports that include the latest payload metadata and source cards.

## Safety and authority posture

All responses remain legal information only, not legal advice. All workbench answers remain `review_required`. This pass does not claim attorney review, legal signoff, a real-matter pilot, production GA, or filing-ready output.

## Evidence generated

- `docs/external-evidence/chat_library_workbench_evidence_v180.json`
- `tests/test_chat_library_ui_hardening_v180.py`

## Known non-chat issue observed during broad test sweeps

The chat-focused tests pass. Broad GA tracker/evidence tests still contain historical expectation conflicts against the current “4 remaining true GA passes” tracker state and/or require external eval/security roots that are not included in the clean source ZIP. This pass did not claim those external evidence roots exist.
