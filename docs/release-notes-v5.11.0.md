# Maine Family Law LLM v5.11.0 — Maine Findings and Forms Workbench

v5.11.0 adds a revision-bound findings and current-form review inside the protected drafting workspace.

## Findings matrix

- Reviews the exact current document revision.
- Maps best-interest factors to exact draft offsets.
- Shows candidate supporting private-record spans without treating them as proof.
- Blocks materially missing factors for parental-rights, residence, contact, or custody decisions.
- Detects missing findings sections and sparse best-interest analysis.
- Reviews contact restrictions for nearby explanatory findings.
- Flags GAL or therapist delegation language.
- Requires an express independent family-case analysis when PFA facts are used to affect contact, residence, or custody.

## Guided forms

- Loads court-form cards only from the verified active immutable authority generation.
- Shows form ID, title, version, freshness, filing context, and detected required fields.
- Disables stale or unknown forms from ordinary guided selection.
- Requires explicit local approval before building a review.
- Creates structured working-copy data rather than pretending to fill an unavailable official PDF.
- Shows every inserted value and every missing required field.
- Detects cross-form value conflicts.
- Produces deterministic working-copy and completion receipts.

## Integrity

Review generations are content-addressed, independently verifiable, bound to the document revision and source hashes, and exposed through opaque matter-scoped download capabilities. Editing the document invalidates completion of the older review.

Product version: **5.11.0**. Microsoft Store package target: **5.11.0.0**. UI build: **38**.
