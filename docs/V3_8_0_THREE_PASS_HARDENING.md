# v3.8.0 Three-Pass Hardening

This increment contains three separately scoped production passes.

## Pass 1 — v3.6 Input and Session Integrity

- Normalize text at API boundaries with Unicode NFKC.
- Remove null bytes, bidirectional direction controls, and nonprinting controls.
- Bound normalized inputs without retaining raw text in integrity reports.
- Validate opaque local session and recent-search identifiers before hashing or lookup.
- Remove exception classes and internal exception details from public API errors.
- Apply the same boundary controls to chat, retrieval, drafting, and workbench routes.

## Pass 2 — v3.7 Claim-to-Source Support Integrity

- Extract candidate legal claims from chat answers.
- Compare claims with retrieved legal-authority snippets using the existing verifier layer.
- Report supported, partially supported, unsupported, contradicted, stale, jurisdiction-mismatch, and not-verifiable states.
- Block current-law language when the retrieved source set has not been freshness-verified.
- Keep every result review-required and never let the diagnostic certify filing readiness.
- Render claim-support status, blockers, and warnings in the structured answer and browser UI.

## Pass 3 — v3.8 Privacy-Safe Handoff and Deterministic Packaging

- Produce reviewer-safe source-card projections that omit private-record excerpts by default.
- Remove absolute paths and raw/full text from handoff metadata.
- Detect and redact common SSN, email, phone, and labeled date-of-birth patterns.
- Make default source-card clipboard actions use the redacted projection.
- Require a visible confirmation before full local transcript/JSON exports when the conversation may contain private records.
- Build source ZIPs with sorted entries, fixed timestamps and permissions, a per-file SHA-256 manifest, and fail-closed exclusions for runtime, private, database, cache, and model artifacts.
- Permit only the intentionally bundled hash-pinned FOCAF public PDFs; arbitrary PDFs remain blocked.

## Safety Boundary

The support diagnostic is a review aid, not a legal entailment engine or citator. It does not establish currentness, negative treatment, factual truth, procedural correctness, or filing readiness. External official-authority ingestion, attorney-reviewed evaluations, and formal legal/security/operations signoff remain separate release requirements.
