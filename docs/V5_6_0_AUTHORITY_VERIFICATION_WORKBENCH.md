# v5.6.0 Authority Verification Workbench

v5.6.0 turns the existing citation, quote, claim-support, freshness, jurisdiction, and filing-gate components into an answer-level verification product.

## Trust boundary

The verifier does not accept caller-supplied authority metadata as proof. Legal support must come from the currently active immutable authority generation published under `authority_product/builds/{build_id}` and admitted by its verified manifest.

Every verification report binds:

- the answer SHA-256;
- the active authority build ID;
- the active authority manifest SHA-256;
- each selected source ID and bounded source-text SHA-256;
- citation-resolution results;
- extracted legal claims;
- exact best-source offsets and candidate spans;
- freshness, jurisdiction, form-version, and treatment checks;
- filing-gate blockers; and
- one deterministic verification-receipt SHA-256.

## In-chat workflow

Each answer with Maine-law evidence receives a **Verify support** action beside Save as draft, Ask local model, and Evidence. It opens a large main-window modal rather than sending the user to the evidence rail.

The modal shows:

- active authority build;
- citations resolved;
- claims supported;
- exact supporting source span and offsets;
- unresolved, partial, contradicted, stale, or jurisdiction-risk claims;
- filing-ready blockers; and
- a copyable verification receipt.

Evidence cards and their large source flyouts remain the primary source-review interface.

## Claim matching

The deterministic baseline now:

- preserves legal abbreviations such as `M.R.S.` while segmenting sentences;
- considers an adjacent two-sentence window because citations often precede the supporting proposition;
- records exact source offsets;
- checks numeric and citation tokens;
- checks polarity/negation conflicts;
- returns the five strongest bounded candidate spans; and
- fails closed when support is partial, stale, outside jurisdiction, contradicted, or unavailable.

It is not a legal-entailment model and cannot replace human review.

## API

Read-only endpoints:

```text
GET  /api/authority/status
POST /api/authority/verify-answer
POST /api/authority/verify-output
```

The local workbench endpoint accepts answer text and source IDs only. Absolute paths and caller-provided authority status are not admitted.

## Release boundary

The source ZIP contains no authority database, private matter, model, vector index, or runtime state. A connected operator must build and activate the external authority generation separately.
