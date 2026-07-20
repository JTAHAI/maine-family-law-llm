# Maine Family Law LLM v4.1.0 — Three-Pass Integrity Upgrade

## Pass 3.9 — Retrieval failure and confidence integrity

The local retriever now recognizes exact Maine statute, rule, opinion, and form references. An exact-reference miss is reported as `exact_reference_not_found` rather than being blurred into an ordinary keyword miss. Each result includes matched terms, lexical coverage, exact-reference status, and source class. Each retrieval response reports source diversity, official-source count, duplicate suppression, confidence, recognized references, and a human-review warning.

The confidence label is intentionally conservative. It describes lexical source discovery only. It does not certify proposition fit, legal correctness, currentness, negative treatment, or filing readiness.

## Pass 4.0 — Drafting and review integrity

Working drafts now require Maine legal source cards. Private matter records cannot substitute for legal authority. Mixed source sets keep private records outside the legal-authority citation appendix and disclose that separation in the draft-integrity report.

Draft requests are scanned for source, safety, citation, and human-review bypass language. Matched override clauses are ignored. A bypass-only request fails closed when no substantive drafting request remains. Valid requests return structured sections, source-backed review notes, explicit blockers, currentness limits, and export policy. Every draft remains a working outline, review-required, and not filing-ready.

## Pass 4.1 — Runtime and local-service resilience

The local runtime now exposes a privacy-safe health snapshot covering version alignment, UI assets, bundled source registry integrity, and all 103 hash-pinned FOCAF PDFs. Health output includes no local paths, private matter state, or raw exceptions, and it does not claim live legal currentness.

Local API service state is written atomically with same-directory temporary files, flush/fsync, restrictive permissions where supported, and `os.replace`. Malformed or impossible state is rejected. A stale state file can no longer cause the launcher to terminate a reused PID: the saved loopback service must answer the application health check before termination is attempted. The deterministic release builder also excludes any prior embedded `RELEASE_SOURCE_MANIFEST.json` before writing the current manifest, preventing duplicate ZIP entries across release-to-release rebuilds.

## Release boundary

This pass improves source discovery, drafting review, and runtime reliability. It does not provide live official-authority freshness certification, legal entailment certification, negative-treatment coverage, attorney-reviewed accuracy evidence, WACK results, a signed Windows MSIX, pilot signoff, or production legal GA.
