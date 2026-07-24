# Changelog

## 5.0.0 - Premium family-justice workbench UI

- Rebuilt the desktop workbench around a modern three-column layout matching the approved v5 design: primary chat, persistent research shortcuts, and an integrated Evidence & tools panel.
- Added a deep-navy FOCAF identity header, local-only status, top-level role/style/topic/context controls, matter access, and a clearer source-lane composer.
- Preserved local corpus, OCR, legal-source, private-record drill-down, reviewer handoff, printables, privacy, keyboard, and transcript workflows.
- Made the Evidence panel desktop-persistent by default while retaining a dismissible mobile drawer.
- Added responsive layout, accessible focus states, clearer typography, compact record/source cards, and v5 UI regression coverage.
- Hardened responsive resizing across full desktop, compact desktop, tablet, phone, and short-window layouts with no horizontal page overflow.
- Added a resize-aware drawer state machine that preserves explicit user preference, prevents the evidence panel from covering chat after a breakpoint change, and keeps focus/ARIA state synchronized.
- Added dynamic viewport sizing, mobile control consolidation, reduced-motion and forced-colors support, and short-height composer compaction.
- Bumped product version to 5.0.0 and Microsoft Store package target to 5.0.0.0.

## 4.5.0 - Private-record chat cards, clickable drill-down, and record open security

- Replaced plain-text "Relevant record slices" with grouped, deduplicated clickable drill-down cards in chat responses.
- Cards group by source document, attachment/member, page, and normalized snippet; show safe filename, document type, match count, page list, and a short snippet.
- Added working Open PDF, Open at page N, and Show all matches actions rendered directly inside chat responses using opaque one-time tokens.
- Implemented secure loopback `/api/records/open/{token}` endpoint: rejects forged, stale, cross-corpus, missing-file, traversal, and hash-mismatch requests.
- Verified ZIP member, email attachment, PDF, and non-PDF preview opening without exposing absolute paths or using file:// URLs.
- Removed generic legal boilerplate from records-only searches; a text match is never treated as a legal conclusion.
- Added comprehensive regression tests: card rendering, clickable links, duplicate collapse, correct file/page opening.
- Bumped version to 4.5.0 / 4.5.0.0.

## 4.4.0 - Windows startup, one-click OCR prerequisites, and corpus-command reliability

- Fixed the Windows launcher path quoting defect that could raise `Illegal characters in path` from `.NET GetFullPath()`, including generated Start, Verify, and Repair launchers.
- Added explicit one-click Tesseract installation through Windows Package Manager, manual-install fallback links, installer status polling, and a local recheck action.
- Bundled `pypdfium2` for local scanned-PDF rendering so a separate Poppler or MuPDF install is not required.
- Routed commands such as `find PDF re: contempt` to PDF-filtered private-record search and `list what is in my indexed corpus` to an actual inventory response with counts and record cards.
- Preserved local-only document handling, review-required output, and Store-safe package version `4.4.0.0`.

## 4.1.0 - Three-pass retrieval, drafting, and runtime integrity hardening

- Added exact Maine citation/form/rule recognition and transparent retrieval-quality diagnostics.
- Added conservative source diversity and duplicate-suppression reporting without representing retrieval rank as legal correctness.
- Added structured review-required drafting that separates legal authority from private records and rejects bypass-only prompts.
- Added privacy-safe runtime self-checks, full FOCAF resource verification, atomic local service state, stale-PID kill protection, and prior-manifest replacement in deterministic ZIP builds.
- Preserved local-only matter handling, Store-safe revision zero, and fail-closed GA boundaries.

## 3.8.0 - Three-pass input, claim-support, handoff, and release hardening

- Added local request integrity normalization for Unicode spoofing controls, null/control bytes, size limits, and opaque session/search identifiers.
- Added conservative claim-to-source diagnostics surfaced in the structured answer and browser, with stale, jurisdiction, current-law, unsupported, and contradiction blockers.
- Added reviewer-safe source-card projections that omit private excerpts and absolute paths by default, plus confirmation before complete private transcript exports.
- Added a deterministic full-source ZIP builder with sorted entries, fixed timestamps/permissions, embedded SHA-256 manifest, symlink rejection, and runtime/private/model exclusions.
- Corrected source ZIP auditing to permit only the product's bundled public FOCAF PDF paths while continuing to block arbitrary PDFs.
- Preserved local-only matter handling, review-required output, Store-safe revision zero, and all prior source/freshness controls.

## 3.5.0 - Grounding integrity, currentness transparency, and retrieval sanitization

- Added a machine-readable grounding-integrity contract that distinguishes source presence from current-law verification, claim support, and filing readiness.
- Annotated every legal and private-record card with authority, freshness, currentness, and support-capability metadata.
- Fixed direct record-search routing from the Both lane, improved hearing-date classification, and added date review flags.
- Expanded prompt/document injection coverage and removed matched override clauses from retrieval queries while preserving the original transcript and safety review.
- Added fail-closed handling when no substantive legal question remains after prompt sanitization.
- Preserved local-only private records, review-required outputs, Store-safe revision zero, and all prior v3.4 continuity/security controls.

## 3.4.0 - Safe continuity, source follow-up correctness, and instruction boundaries

- Fixed a browser runtime error in reviewer handoff rendering that could replace a successful chat answer with a visible error.
- Routed source-card follow-ups through the session-isolated server so ordinal and lane-specific requests open the correct cards without rerunning retrieval.
- Added bounded, raw-text-free structured conversation anchors for explicit short follow-ups; safety, dates, docket numbers, court names, and raw questions are never inherited.
- Replaced stale source-card reuse after an ungrounded turn with fail-closed latest-answer state.
- Added instruction-like text detection and trust-boundary metadata for prompts and retrieved private records without altering original snippets.
- Added disclosed year inference and relative-date normalization, request limits, and sanitized background OCR errors.
- Preserved review-required output, source-lane separation, local-only private data handling, and the Store-compatible 3.4.0.0 package version.

## 3.3.0 - Conversation reliability and intake safety hardening

- Added safety-first, negation-aware intake routing with structured event-date extraction and transparent routing evidence.
- Added session-isolated source-card continuity for legal, record, and combined answers, including ordinal selection and stale-reference checks.
- Added new-chat server-state clearing, bounded local session memory, no-store/security headers, request IDs, input limits, and sanitized internal errors.
- Preserved review-required output, source-lane separation, local-only private data handling, and the Store-compatible 3.3.0.0 package version.

## 2.07.0 - v1.0.0 full-record corpus-builder upgrade

- Added universal full-case corpus builder, local-first evidence intake, privacy-filtered external releases, role-specific GAL/court/lawyer/prosecutor packages, question-coverage audits, source-hash verification, and one-click launcher/self-builder workflow.
