# Chat missing-information and reviewer-handoff hardening — v1.82.0

This pass makes the local browser chat workbench more useful when a user does not yet know what to ask or what facts/documents a lawyer, advocate, caregiver, counselor, or therapist needs for review.

## Added

- Expanded deterministic chat library from 78 to 104 items.
- Added `missing_information` answer style.
- Added role-specific missing-information and follow-up metadata to grounded answers.
- Added `/api/missing-information-prompts` for UI/testing integrations.
- Added reviewer handoff UI panel with copyable reviewer-handoff JSON.
- Upgraded JSON transcript export to include reviewer handoff metadata.
- Added a reviewer handoff prompt pack.
- Added v1.82 focused regression tests.

## Guardrails

- Outputs remain legal information only, not legal advice.
- Outputs remain `review_required` and not filing-ready.
- No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status is claimed.
- Private records should not be pasted into the workbench or included in release ZIPs.
