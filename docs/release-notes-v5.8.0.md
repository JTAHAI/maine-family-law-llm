# Maine Family Law LLM v5.8.0 — Reviewer Queue, Procedure, Forms, and Claim Annotations

v5.8.0 turns the revision-bound review ledger into a matter-level reviewer workflow.

## Reviewer queue

- Lists documents waiting for review across the active local matter.
- Distinguishes pending packets, requested changes, stale reviews after revision changes, blocked review completion, rejected drafts, and filing-gate passes.
- Opens the selected document directly in the large drafting workbench.
- Exposes only safe document metadata and packet summaries; no local filesystem paths or confirmation capabilities are returned.

## Claim-by-claim annotations

Each material legal claim extracted by the admitted authority verifier can receive an immutable reviewer finding:

- accepted;
- not material;
- needs revision;
- unsupported;
- contradicted;
- needs authority; or
- needs fact support.

Missing annotations on material claims block an approval from passing the filing gate. Blocking annotations are retained in the hash-chained decision record and cannot be erased by model confidence or a general approval checkbox.

## Procedure and posture intelligence

The host now creates a deterministic review report for common family-law workflow postures, including initial complaints, temporary orders, post-judgment motions, contempt, enforcement, modification, PFA matters, findings motions, appeals, remands, and stays. Specific filing signals outrank contextual references to an existing order. Unknown or genuinely conflicting posture remains review-required.

The report supplies a workflow checklist only. It is not a legal conclusion and does not certify that the selected procedure is correct.

## Current-form checks

- Court-form identifiers are normalized across spacing and hyphen variants.
- Referenced forms must resolve to an admitted court-form source in the active authority generation.
- Stale, superseded, missing, or unknown form versions block filing review.
- When the detected workflow normally requires form review and no form has been selected, the packet records `required_form_selection_not_confirmed` rather than assuming no form is needed.

## Review integrity

The exact revision, authority report, fact-to-record map, procedure report, form report, claim set, reviewer annotations, blockers, and packet hash are preserved in the append-only local ledger. Revision changes invalidate prior pending packets and make prior review decisions visibly stale in the queue.

Product version: **5.8.0**. Microsoft Store package target: **5.8.0.0**. UI build: **35**.
