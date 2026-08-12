# Maine Family Law LLM v5.10.0 — Immutable Evidence Work Product

v5.10.0 turns already-indexed private matter records into a bounded, review-required evidence work product without changing the underlying evidence.

## New workflow

- Build from the current indexed record or all indexed records in the active local matter.
- Add optional focus terms for a narrower timeline.
- Review dated events with exact indexed spans and source hashes.
- Review contempt/enforcement rows that separate order language from alleged or reported conduct.
- Inspect hard-field mismatches and opposing record language.
- Review a grouped exhibit index and missing-record checklist.
- Download immutable JSON, HTML, and receipt artifacts.

## Safety boundary

A timeline event means only that a date and statement were located in indexed text. The enforcement ledger does not determine contempt, willfulness, notice, ability to comply, authenticity, credibility, or entitlement to relief. Contradiction candidates may concern different dates, people, or contexts and require review of the originals.

Every build is content-addressed and bound to the selected record IDs, source hashes, indexed-text hashes, focus terms, and algorithm version. Existing identical builds are reused only after independent verification.

Product version: **5.10.0**. Microsoft Store package target: **5.10.0.0**. UI build: **37**.
