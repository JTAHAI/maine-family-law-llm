# Maine Family Law LLM v3.8.0 Completion Report

v3.8.0 delivers three hardening passes in one increment: input/session integrity, claim-to-source support diagnostics, and privacy-safe deterministic release packaging.

## Completed

- Hardened chat, retrieval, drafting, and workbench inputs against invisible Unicode controls, null bytes, malformed identifiers, and oversized values.
- Removed internal exception-class disclosure from public API errors.
- Added conservative sentence-level claim-to-source diagnostics that remain explicitly review-required.
- Added stale-source, jurisdiction, unsupported-claim, contradiction, and unverified-current-law blockers.
- Added privacy-safe source-card handoff projections and default redacted clipboard behavior.
- Added explicit confirmation for potentially private full local exports.
- Added reproducible source ZIP construction with a per-file SHA-256 manifest.
- Aligned source packaging policy with the intentionally bundled, hash-pinned public FOCAF library while continuing to reject arbitrary PDFs.
- Updated product identity to 3.8.0 and Store package target to 3.8.0.0.

## Not completed in this environment

- Windows MSIX rebuild/signing and WACK
- Live external official-authority freshness build
- Attorney-reviewed legal accuracy and claim-entailment evaluation
- Negative-treatment certification
- Formal security, legal, product, and operations signoff

The source remains review-required and must not be represented as production legal GA.
