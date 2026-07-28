# Maine Family Law LLM v5.2.0

## Answer-first evidence

Evidence used for an answer now appears inside the large assistant response. Users can open official sources, inspect private records, jump to PDF pages, preview sources, copy source cards, and open the full evidence workspace without scrolling through the narrow rail.

## Documents and drafting in the app

- Save any assistant answer as a new local draft.
- Import a hash-verified private record into a protected working copy.
- Draft letters, memoranda, motions, affidavits, parenting plans, court-form notes, and review packets.
- Review a line-by-line diff before committing a revision.
- Inspect revision history and local audit status.
- Export review-required TXT, Markdown, or Word documents.
- Move drafts to recoverable trash and restore them.

The first revision is immutable. Commits use optimistic concurrency and a one-use confirmation capability. Delete is separately confirmed. Every mutation enters a SHA-256 hash-chained local audit log, and mutations fail closed if that chain is damaged.

## Tracked Word review

The optional tracked Word workflow uses the MIT-licensed `pablospe/docx-editor` package by Pablo Speciale. It provides hash-anchored paragraph references, tracked insertions/deletions/replacements/rewrites, comments, and revision-aware Word output without requiring Microsoft Word.

Maine Family Law LLM always creates a new review copy. Imported Word evidence is never overwritten. The adapter adds source-root containment, symlink refusal, a 50 MB file limit, bounded edit counts and text sizes, and explicit user confirmation.

## Architecture credit

The document-workspace, structured action, revision-history, audit-schema, and structured-diff patterns were informed by the MIT-licensed `Paparusi/legal-ai-agent` project by Lê Minh Hiếu. The Maine implementation was independently rewritten and hardened. It does not import the upstream authentication code, unsafe Docker defaults, billing/admin system, crawler, Vietnamese legal rules, autonomous destructive permissions, or formatting-destructive DOCX editor.

Full notices are in `THIRD_PARTY_NOTICES.md`; license texts are retained under `licenses/`.

## Security

- Loopback requests are filtered for local clients, valid local Host headers, same-origin mutation requests, and bounded request bodies.
- Record capability storage is thread-safe and active-corpus scoped.
- Record-open cache size and age are bounded.
- Document content is not executed and the new document modules make no network calls or subprocess calls.
- Imported originals are immutable and hash verified.
- Revisions and delete actions require explicit confirmation.
- The document audit chain is verified before new events are appended.
- Dependency floors include `python-docx`, `defusedxml`, and `docx-editor`; CI retains `pip-audit`.

## Release boundary

- Product version: `5.2.0`
- Microsoft Store package target: `5.2.0.0`
- Source ZIP only. A signed MSIX remains a separate Windows rebuild, signing, WACK, and Store-validation process.
- All legal output remains review-required and not legal advice.
