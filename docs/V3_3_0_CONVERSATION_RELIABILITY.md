# Maine Family Law LLM v3.3.0 — Conversation Reliability and Intake Safety

This pass strengthens the local workbench’s first-contact behavior, source continuity, and privacy boundary. It does not change the core product rule: intake routing is not a legal or factual finding, private records are not legal authority, and generated work remains review-required.

## Safety-first intake routing

- Immediate-safety and child-safety language is evaluated before served-paper, hearing, enforcement, modification, support, or general-question routing.
- Negation-aware matching avoids false signals from phrases such as “I was not served,” “there is no hearing,” “no immediate danger,” and “no weapon.”
- Phrases that communicate lack of safety, including “I am not safe” and “I do not feel safe,” continue to trigger safety routing.
- The parser records a bounded list of routing reasons, confidence, attention level, and whether the input was truncated for safe processing.

## Dates, deadlines, and requested actions

The intake contract now distinguishes:

- service dates;
- hearing or court dates;
- possible response or filing deadlines;
- other dates mentioned.

Full dates and relative terms such as today or tomorrow may be normalized locally. Month/day text without a year is intentionally not assigned a year. Every UI and legacy-text rendering warns that extraction is not a deadline calculation and must be checked against the complete official paper or docket.

The parser also records neutral requested-action signals such as order clarification, hearing preparation, enforcement review, modification, support, safety relief, appeal/record preservation, and evidence organization. These signals route the conversation; they do not establish entitlement or select a legal procedure.

## Source-card continuity

- The most recent source set can be reopened after Maine-law, private-record, or combined answers.
- “Open the first/second/third one” selects a specific prior card without rerunning retrieval.
- A supplied prior search ID must match the current session’s last answer.
- Out-of-range selections, stale references, expired state, and missing sessions fail closed with a recovery instruction.
- Stored state is bounded, held in memory only, trimmed of full-text fields, and expires after 30 minutes.

## New-chat privacy

The browser creates a new random session ID for every fresh chat and asks the local API to clear the previous session’s short-lived source state. Even if that clear request fails, the rotated ID prevents the new conversation from reopening the old source set.

## Local API hardening

- Chat question input is bounded to 12,000 normalized characters; matter context is bounded to 4,000.
- Responses include `Cache-Control: no-store`, request IDs, and same-origin isolation headers.
- Internal error responses expose only a safe error class and request ID, not the exception message, private path, or record content.
- Conversation state is never persisted to disk by this feature.

## Release identity

- Product: `3.3.0`
- Microsoft Store package target: `3.3.0.0`
- Structured answer schema: `family_answer_v3_3`

A signed MSIX and Windows App Certification Kit run require the Windows packaging environment and are not claimed by the source-only Linux validation.
