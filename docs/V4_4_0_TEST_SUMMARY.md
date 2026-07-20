# Maine Family Law LLM v4.4.0 Test Summary

## Result

- Tests collected: **693**
- Passed: **692**
- Skipped: **1**
- Failed: **0**

The single skip is the existing PowerShell-parser check on a Linux runner without PowerShell. Windows launcher behavior is covered by static regression tests; desktop/Tk tests were run under Xvfb.

## New v4.4 regression coverage

- Windows launcher path normalization and trailing-quote protection.
- Generated Start, Verify, and Repair launcher templates use the corrected repository-root argument.
- One-click OCR installation requires explicit consent and invokes only the fixed `UB-Mannheim.TesseractOCR` package.
- OCR dialog exposes one-click, manual-link, and recheck actions with local-only disclosures.
- `list what is in my indexed corpus` routes to real inventory output.
- `find PDF re: contempt` routes to PDF-scoped private-record search.
- PDF-scoped search excludes non-PDF records.
- Inventory chat output reports actual counts and record cards.
- Version and Store manifest alignment at `4.4.0` / `4.4.0.0`.

## Static and release checks

- Python compilation: passed.
- JavaScript syntax: passed.
- Repository doctor: passed; safe to push/package.
- Release artifact audit: passed with zero blockers.
- Public-source readiness: passed with zero findings.
- FOCAF runtime resource audit: 103 expected, 103 resolved, zero missing, zero hash mismatches.

## Test execution note

The suite was executed in deterministic file groups because some evidence-generation and full-GA workbench tests exceed the per-command execution ceiling when combined. All 204 test modules were accounted for, including the four expensive full-GA workbench tests run individually.
