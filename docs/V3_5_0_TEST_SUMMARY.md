# Maine Family Law LLM v3.5.0 Test Summary

## Identity

- Product version: **3.5.0**
- Microsoft Store package target: **3.5.0.0**
- UI identity: **3.5.0-family-justice-chat-b13**
- Structured answer contract: **family_answer_v3_5**
- Grounding contract: **grounding_integrity_v1**

## Test results

- Tests collected: **667**
- Passed: **666**
- Skipped: **1**
- Failed: **0**
- New v3.5 regression module: **9 passed**

The skipped test is the existing PowerShell parser check because PowerShell is unavailable on the Linux runner.

The suite was executed in deterministic file batches to stay within the command execution ceiling. The four long-running full-GA workbench cases passed individually. Tk/desktop coverage was executed under Xvfb.

## Additional validation

- Python compilation: passed
- JavaScript syntax: passed
- Repository doctor: passed
- Release artifact audit: passed with zero blockers
- Public-source readiness audit: passed with zero findings
- FOCAF packaged asset audit: **103 expected, 103 resolved**
- FOCAF missing files: zero
- FOCAF hash mismatches: zero
- Sample-evidence manifest hygiene: passed
- Store-compatible revision-zero identity: passed

## Important interpretation

These results establish source-repository behavior and packaging hygiene. They do not establish production legal GA, current-law certification, attorney-reviewed legal accuracy, a signed MSIX, or WACK compliance.
