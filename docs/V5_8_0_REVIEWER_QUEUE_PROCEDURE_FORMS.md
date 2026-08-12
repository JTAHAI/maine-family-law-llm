# v5.8.0 Reviewer Queue, Procedure/Posture, Forms, and Claim Review

## Boundary

This release adds deterministic review workflow intelligence. It does not replace an attorney, certify filing readiness, or infer that a record allegation is true.

## Data contracts

A review packet now binds:

1. document and revision hashes;
2. admitted authority-verification output;
3. fact-to-record spans;
4. procedure/posture report;
5. current-form report;
6. normalized legal claims for reviewer annotation;
7. filing-gate preflight; and
8. one-use review confirmation capability.

A committed decision adds reviewer identity, role, attestation, notes, claim annotations, annotation blockers, filing-gate result, sequence number, previous-decision hash, and decision hash.

## Fail-closed rules

- Unknown procedure is not treated as checked.
- Conflicting top-ranked procedure signals remain ambiguous.
- Current-form status must come from admitted authority metadata.
- A required form selection cannot be silently skipped.
- Every material claim must be individually annotated before approval can pass.
- `needs_revision`, `unsupported`, `contradicted`, `needs_authority`, and `needs_fact_support` remain filing blockers.
- A newer document revision makes the older review stale.
- Queue results never disclose absolute paths, tokens, or private document text.
