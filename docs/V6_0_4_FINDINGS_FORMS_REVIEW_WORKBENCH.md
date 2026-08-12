# Maine Rule 52 and Best-Interest Review Matrix, Restriction-Support Review, and Guided Official-Form Assistant

This slice adds a review-only workspace for:

- Rule 52 and best-interest factor review
- restriction-support review
- official Maine form catalog browsing
- guided, review-required form sessions
- immutable working-copy generation and receipts

## What It Does

- Exposes the current admitted Maine form catalog through the verified authority store.
- Builds a findings matrix from admitted evidence and flags missing or unsupported factor coverage.
- Keeps contact restriction review separate from legal conclusions.
- Preserves original source forms and generates separate working copies only.
- Records review history and completion receipts as matter-local artifacts.

## What It Does Not Do

- It does not decide custody, residence, or contact outcomes.
- It does not say a restriction is lawful, necessary, or unnecessary.
- It does not autofill unknown facts.
- It does not file anything with a court.
- It does not overwrite original official forms.

## Freshness Behavior

- Current or verified-current form records may be used for review.
- Stale, superseded, or unknown-freshness forms remain blocked from final-like completion.
- Missing or stale authority stays visible as a review limitation.

## Working-Copy Policy

- Inserted values are previewed and reviewable.
- Required field gaps and cross-form conflicts remain visible.
- Completion receipts document the review state and artifact hashes.

## Privacy And Safety

- Keep private matter data local to the matter workspace.
- Treat unknown facts as unresolved, not as fillable defaults.
- Preserve review-required status in all outputs.
