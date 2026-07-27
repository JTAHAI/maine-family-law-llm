# Maine Family Law LLM v5.0.0

## Premium local-first family-justice workbench

Maine Family Law LLM v5.0.0 is a major source release that brings the public repository forward from the older v2.08 SEO preview to the current local-first family-justice workbench.

This release remains a legal-information and review-support system. It is not a lawyer, does not provide legal advice, and does not mark generated work as filing-ready merely because an AI model produced it.

## Major upgrades

### Premium workbench experience

- Rebuilt the browser workbench around a responsive three-column desktop layout with primary chat, persistent research shortcuts, and an integrated Evidence & tools panel.
- Added clearer role, answer-style, topic, context, privacy, source-lane, corpus, OCR, and matter controls.
- Preserved keyboard access, responsive mobile behavior, local transcript handling, reviewer handoff, printables, and source-card workflows.

### Secure private-record drill-down

- Replaced plain-text record matches with grouped and deduplicated source cards.
- Added secure Open original, Open at page, and Show all matches actions using opaque active-corpus tokens.
- Rejects forged, stale, cross-corpus, missing-file, traversal, and content-hash mismatch requests.
- Keeps absolute paths and `file://` links out of browser responses.

### Local corpus and OCR reliability

- Added one-click Tesseract prerequisite installation through Windows Package Manager, a manual fallback, status polling, and local recheck controls.
- Bundled `pypdfium2` for local scanned-PDF rendering so OCR does not require a separate Poppler or MuPDF installation.
- Improved corpus inventory commands and private-record searches so they return actual counts and source cards rather than generic chat text.

### Grounding and verification integrity

- Added clearer separation between Maine legal authority, private matter records, and generated analysis.
- Added claim-to-source diagnostics, citation and quote-span review, freshness and jurisdiction warnings, contradiction handling, and filing-readiness blockers.
- Added conservative source diversity and duplicate-suppression reporting without treating retrieval rank or model consensus as legal correctness.
- Added prompt-injection and untrusted-record protections that prevent retrieved text from changing system, privacy, source, or review policy.

### Conversation, intake, and privacy hardening

- Added safety-first, negation-aware intake routing and structured handling of service dates, hearing dates, deadlines, and requested actions.
- Added session-isolated source-card follow-ups and bounded local conversation anchors.
- Added no-store and security headers, request identifiers, input limits, stale-state rejection, sanitized errors, and fail-closed behavior.
- Private matter files, extracted text, OCR output, indexes, locators, hashes, runtime databases, and model weights remain outside the public source release.

### Deterministic release and Windows packaging work

- Added deterministic full-source ZIP construction with sorted entries, fixed metadata, embedded SHA-256 manifests, symlink rejection, and private/runtime/model exclusions.
- Added Microsoft Store and MSIX architecture, privacy, audit, build, install-test, and WACK preparation materials.
- Added a GitHub Actions MSIX build workflow and Windows runtime entry points.

### FOCAF public resource library

- Added the bundled For Our Children & Families public printable library and inventory.
- Public FOCAF materials are family-support resources, not legal authority.
- Release auditing continues to allow only approved public resource paths while blocking arbitrary or private PDFs from source packages.

## Version

- Product version: `5.0.0`
- Microsoft Store package target: `5.0.0.0`
- Python requirement: `3.11+`

## Install or run from source

1. Download the v5.0.0 source archive or clone the repository.
2. On Windows, run `START_MAINE_FAMILY_LAW_LLM.cmd` from a normal checkout or portable distribution.
3. Build the neutral fictional sample corpus first to learn the workflow.
4. Select a protected external location before importing real matter records.

The standard local browser entry point is `http://127.0.0.1:8000/`.

## Important release boundary

This GitHub release is the current **source release**. A signed Microsoft Store/MSIX installer is a separate Windows release artifact and must be rebuilt, audited, signed, and WACK-tested before attachment or Store submission. The absence of a signed installer asset does not change the source version.

## Review and safety status

- Local-first and review-required by default.
- No attorney-client relationship is created.
- Model memory is not legal authority.
- Private records do not become legal authority.
- Source-backed does not automatically mean current-law verified.
- No output is guaranteed complete, correct, or filing-ready.

## Upgrade note

The previous public release, `v2.08-seo-preview-20260620`, was primarily a discovery and repository-positioning preview. The v5.0.0 source release incorporates 39 later commits and the v3.x, v4.x, and v5.0.0 product, security, retrieval, OCR, corpus, workbench, and packaging upgrades now present on `main`.
