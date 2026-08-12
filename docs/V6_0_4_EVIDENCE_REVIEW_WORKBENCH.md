# Evidence Review Workbench

This slice adds a matter-local evidence workbench for:

- timeline building
- claim contradiction review
- record coverage review
- missing-record checklists
- enforcement event ledgers
- append-only review history

## Evidentiary status labels

- `alleged` means a party or record asserts something happened.
- `observed` means a record or reviewer observed text, dates, or metadata.
- `found` means a court finding or operative order span supplied the statement.
- `review_required` means the item is organized for human review and is not a legal conclusion.

## Date meaning

- Explicit dates are preserved as written and normalized when possible.
- Unknown dates stay unknown.
- Empty date ranges do not prove nothing happened.
- Conflicting dates remain visible instead of being collapsed into one answer.

## Contradiction review

The claim review flow separates:

- supports
- contradicts
- qualifies
- alternative explanations
- missing context
- authenticity or reliability caveats
- unresolved items

It does not assign a binary truth score and does not convert allegations into findings.

## Missing-record methodology

Missing-record items may come from:

- user-created checklists
- approved matter templates
- system heuristics

Every item explains its basis and remains review required.

## Enforcement ledger limits

- Exact operative order language is mandatory.
- Stale or superseded orders are flagged.
- The ledger does not decide contempt, willfulness, or ability to comply.

## Child Impact Lens

Child impact tags are organizational only. They remain source-bound and review required. They do not diagnose, rank parents, or predict custody outcomes.

## Exports

Exports are hash-bound, review required, and matter-local. They include selected scope, source IDs, source hashes, unresolved items, and correction history summaries.

## Privacy

The workbench keeps private matter data local to the active case root and does not upload source text or records remotely.
