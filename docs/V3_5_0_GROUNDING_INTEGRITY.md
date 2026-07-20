# Maine Family Law LLM v3.5.0 — Grounding Integrity

v3.5.0 hardens the boundary between four different concepts that must not be conflated in a legal-information product:

1. a source card was retrieved;
2. the card is an official legal source;
3. the card has an explicit currentness/freshness verification;
4. the card actually supports the proposition for which it is being used.

The workbench now reports those concepts separately. Bundled seed fixtures remain useful for local demonstrations and regression tests, but they no longer visually imply that the local bundle completed a live current-law audit.

## Grounding-integrity contract

Every finalized chat answer now includes `grounding_integrity_v1` with:

- legal and private-record source counts;
- distinct source count;
- official-source and official-primary-authority counts;
- verified-current, needs-verification, and stale/superseded counts;
- source scope and legal source types;
- current-law status and a boolean current-law verification result;
- support-boundary warnings.

Each source card also receives:

- `authority_status`;
- `freshness_status`;
- `current_law_verified`;
- `support_capability`.

Private matter records are always labeled as private records, never legal authority. A private card can show that text appears in a selected file; it does not prove an allegation.

## Retrieval and injection hardening

Matched override, source-suppression, safety-bypass, and filing-readiness-bypass clauses are removed from the internal retrieval query. The original prompt remains visible for the transcript and safety review.

When removal leaves no substantive Maine family-law question, retrieval fails closed with `substantive_question_required_after_prompt_sanitization`. A legitimate question that remains after sanitization can still be answered with source cards and visible warnings.

## Intake and lane corrections

- “Court is tomorrow” is classified as a hearing/court date rather than a service date.
- Date records include `days_from_reference` and transparent review flags for inferred years, relative dates, past/today events, and events within three or fourteen days.
- Date extraction remains explicitly not a legal deadline calculation.
- Direct record-search commands issued while **Both** is selected now finalize under **My records**, including the structured answer, source lanes, and grounding report.
- Unknown answer-style values fail closed to `plain_language`.

## Release limits

This source pass does not certify current Maine law, legal correctness, negative treatment, filing readiness, attorney review, WACK, or a signed Windows package. Those remain separate external-data, professional-review, and Windows release requirements.
