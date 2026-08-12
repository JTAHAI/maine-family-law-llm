# Maine Family Law LLM v5.6.0 — Authority Verification Workbench

v5.6.0 lets users verify the legal support for an answer without leaving the main chat. It builds on the immutable authority generations introduced in v5.5.0.

## Highlights

- New in-chat **Verify support** action for answers with Maine-law evidence.
- Large main-window verification modal with claim, citation, blocker, and receipt review.
- Verification reads only from the active immutable authority generation.
- Exact claim-to-source offsets and bounded candidate spans.
- Citation-aware adjacent-sentence support matching.
- Numeric and polarity conflict checks.
- Deterministic receipt binding answer, authority manifest, source hashes, report, and filing blockers.
- New bounded local and standalone API endpoints.
- Original evidence cards, flyouts, document drafting, local-agent controls, and local-only defaults remain intact.

## Safety

The verifier is deterministic and conservative. A supported source span is not a legal conclusion, and no report can self-certify filing readiness. Human review remains mandatory.

## Version

Product version: **5.6.0**. Microsoft Store package target: **5.6.0.0**. UI build: **33**.
