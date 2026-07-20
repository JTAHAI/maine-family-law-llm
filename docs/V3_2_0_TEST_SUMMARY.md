# Maine Family Law LLM v3.2.0 Test Summary

## Results

- Focused chat, intake, source-card, release-hygiene, and printable suite: **38 passed**.
- Full repository suite: **638 passed, 1 skipped** from **639 collected** tests.
- Python compilation: **passed**.
- JavaScript syntax (`node --check`): **passed**.
- Local repository doctor: **passed**.
- Release artifact audit: **passed**, zero blocked paths.
- Public source readiness audit: **passed**. This does not claim production legal readiness.
- FOCAF printable audit: **103/103 PDFs resolved and hash-verified**.

## Chat and intake coverage

The focused suite verifies served-paper triage, order clarification, immediate-safety routing, neutral handling of interference/contempt language, exact private-record search, prior-result source-card follow-up, EML attachments, safe ZIP members, mixed native/OCR PDF handling, page-accurate OCR candidate counts, local-only OCR behavior, and practical FOCAF printable ranking.

## Windows release gates

This Linux build environment cannot rebuild or sign the Windows MSIX and cannot run WACK. The next Windows package target is **3.2.0.0**. The source repository contains the Store build scripts and fail-closed printable/package checks.
