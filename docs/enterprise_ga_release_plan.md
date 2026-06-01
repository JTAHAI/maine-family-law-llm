# Enterprise GA Release Plan

The project can be open-source and free while still refusing unsafe claims. GA
release readiness means the code, corpus, indexes, safety gates, and review
evidence are all ready. Source-code readiness is not the same thing as legal
production readiness.

## GA Gates

1. Source registry complete for required Maine and federal lanes.
2. Official-source live fetch complete into external data root.
3. Raw files hashed with retrieval timestamps and immutable source metadata.
4. Structured parsers pass for statutes, rules, forms, opinions, guidance, and
   federal District of Maine materials.
5. Required retrieval indexes pass.
6. Citation resolver, quote verifier, claim-support verifier, stale-law detector,
   and jurisdiction mismatch detector pass.
7. Attorney-reviewed evaluation pack meets minimum row counts.
8. Safety red-team prompts pass for PFA, child safety, emergency, federal-court
   jurisdiction traps, fake citations, stale forms, and unsupported legal claims.
9. Clean ZIP excludes corpora, private facts, databases, vector stores, PDFs,
   model weights, venvs, caches, generated proof files, and runtime artifacts.
10. README and docs clearly state legal information only, no attorney-client
    relationship, no filing-ready output, and review required.

## Blocked Until Human Review

The following cannot be completed by code alone:

- attorney-reviewed eval rows
- attorney/legal-aid review of answer templates and refusal language
- accessibility/usability review for self-represented litigants
- source licensing review for secondary materials
- public launch governance and maintenance owners

Until those are done, the correct status is `source_ready_but_legal_ga_blocked`.
