# v4.1.0 Test Summary

## Result

- Collected: 686 tests
- Passed: 685
- Skipped: 1
- Assertion failures remaining: 0
- New v4.1 regression tests: 10 passed

The single skip is the existing PowerShell-parser test because PowerShell is unavailable on the Linux runner.

## Execution method

A monolithic run reached 24% with no failures before the command ceiling. The complete collection was then executed in deterministic test-file batches under Xvfb, with the four expensive full-GA workbench cases run individually. Subprocess-heavy operator/public-source tests that remained alive after printing a successful pytest summary were rerun in isolation with an explicit process timeout; their assertions passed and the isolated commands exited successfully where applicable.

## Covered areas

- Exact-reference retrieval and failure diagnostics
- Retrieval confidence, source diversity, and duplicate suppression
- Chat/API propagation of retrieval diagnostics
- Private-record/legal-authority separation in drafting
- Prompt-bypass neutralization in drafting
- Structured draft-integrity blocker reports
- Atomic local service state and malformed-state rejection
- Stale-PID termination protection
- Privacy-safe runtime health and FOCAF hash verification
- Existing chat, intake, OCR, Store, packaging, authority, evaluation, governance, security, pilot, and GA fail-closed gates

## Static and release checks

- Python compilation: passed
- JavaScript syntax: passed
- Desktop/Tk coverage under Xvfb: passed
- Strict public-source pre-push gate: passed with zero blockers
- Repository doctor: passed
- Release artifact audit: passed with zero blockers
- Public repository readiness: passed with zero findings
- FOCAF package audit: 103/103 resolved, zero hash mismatches
