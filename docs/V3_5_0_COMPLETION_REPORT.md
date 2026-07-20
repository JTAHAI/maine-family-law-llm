# Maine Family Law LLM v3.5.0 Completion Report

v3.5.0 upgrades source transparency and retrieval safety while preserving all v3.4 conversation-continuity and privacy controls.

## Completed

- Added a reusable grounding-integrity assessment layer.
- Distinguished source-backed answers from freshness-verified current-law answers.
- Added authority, freshness, currentness, and support-boundary metadata to every source card.
- Made bundled seed-source limitations visible in the answer, badges, source drawer, API, and reviewer handoff data.
- Fixed direct record searches from the **Both** selector so they finalize as private-record results.
- Improved hearing-date role classification and urgency review flags.
- Expanded prompt/document injection and review-bypass detection.
- Sanitized override clauses before retrieval without rewriting the visible user prompt.
- Added fail-closed behavior when no substantive question remains after sanitization.
- Bounded and normalized answer styles and search identifiers.
- Updated the product to 3.5.0 and the Store package target to 3.5.0.0.
- Added nine focused v3.5 regression tests.
- Corrected the sample-evidence manifest to include the existing v3.4 proof file.

## Validation

All 667 collected tests were accounted for: 666 passed and one environment-specific PowerShell parser test was skipped. Repository, public-source, release-artifact, Store identity, JavaScript, Python, and all 103 FOCAF asset checks passed.

## Not completed in this environment

- Windows MSIX rebuild and signing
- Windows App Certification Kit
- Live external official-authority freshness build
- Attorney-reviewed legal accuracy evaluation
- Negative-treatment certification
- Formal security, legal, product, and operations signoff

The source release remains review-required and must not be described as production legal GA.
