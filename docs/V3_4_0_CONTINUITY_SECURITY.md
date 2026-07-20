# Maine Family Law LLM v3.4.0 — Safe Continuity and Conversation Security

This pass strengthens multi-turn chat behavior, source-card reopening, instruction-boundary handling, date disclosures, and API privacy. It preserves the product's controlling rules: official Maine authority outranks model memory, private records remain a separate evidence lane, retrieved text is data rather than executable instruction, and generated legal work remains review-required.

## Browser reliability fixes

- Fixed the reviewer-handoff renderer so a valid server answer is not replaced by a browser error caused by an undefined structured-answer variable.
- Removed browser-only interception of source follow-ups. Requests such as “open the second record source” now use the session-isolated server selection logic.
- Empty source results clear prior browser source state, preventing stale cards from remaining available through the transcript or copy controls.

## Safe structured continuity

A short, explicit follow-up such as “What should I gather?” may reuse only a bounded routing anchor from the prior turn:

- task;
- issue labels;
- procedural posture;
- requested-action labels;
- child-relevance flag; and
- routing confidence.

The continuity layer does **not** retain or inherit the prior raw question, dates, docket numbers, court names, search targets, or safety flags. Current-turn safety language is always recalculated. The answer discloses when continuity was used and describes the limited fields that were reused.

## Source-card follow-ups

- Supports arbitrary ordinal selection from 1 through 24, plus “last source.”
- Supports lane filtering for Maine-law authority or private records.
- A request such as “open the second record source” selects the second private-record card, not the second card from the mixed list.
- A later answer with no citations replaces the earlier source set. “Show sources” then fails closed rather than reopening stale authority or private snippets.
- Reopening cards does not rerun retrieval.

## Instruction-boundary defenses

- User prompts are scanned for direct instruction-override patterns.
- Source snippets are scanned separately for instruction-like text.
- The original source text remains visible for evidentiary integrity, but is labeled as untrusted source or record data.
- Instruction-like content cannot alter source ranking, privacy boundaries, safety routing, review requirements, or filing-readiness gates.
- Security warnings are returned in the structured answer and displayed in the workbench.

## Date handling

The local parser now recognizes ISO dates, common numeric formats, month/day text with optional year, “yesterday,” and bounded relative expressions such as “in 2 weeks.” When a year is omitted, the inferred year and its basis are disclosed. Relative dates are labeled as calculations from the local reference date. Extracted dates remain routing aids—not deadline calculations—and must be checked against the official paper or docket.

## API and OCR privacy

- Public retrieval and printable-search limits are clamped to 20 results.
- Draft, source-inspection, workbench, and query fields are bounded.
- OCR worker failures return a generic message and error class instead of exception text that could expose a local path.
- API responses retain request IDs, no-store controls, and same-origin isolation headers.

## Release identity

- Product: `3.4.0`
- Microsoft Store package target: `3.4.0.0`
- UI build: `3.4.0-family-justice-chat-b12`
- Structured answer schema: `family_answer_v3_4`

This is a source-repository release. A signed MSIX and Windows App Certification Kit run require the Windows packaging environment and are not claimed by this pass.
