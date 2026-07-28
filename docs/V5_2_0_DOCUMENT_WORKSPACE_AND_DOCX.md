# v5.2.0 Document Workspace and Tracked Word Review

## What users can do

The local workbench now places document handling inside the main user experience. A user can:

- save an assistant answer as a new working draft;
- import a hash-verified private record into an editable working copy;
- create letters, memoranda, motions, affidavits, parenting plans, court-form notes, and attorney-review packets;
- propose changes and review a line-by-line diff before committing;
- inspect an append-only revision history;
- export review-required TXT, Markdown, or DOCX files;
- move a document to recoverable local trash and restore it; and
- create a new Word copy containing tracked changes or comments when an imported DOCX is available.

## Safety model

The document workspace is local and data-only. It does not execute document content or grant the model unrestricted file permissions.

- Imported originals are stored separately and hash verified.
- A working revision never overwrites the original evidence file.
- Revision commits require the current base revision, a one-use confirmation capability, and an explicit user confirmation.
- Delete is a separate two-phase soft-delete operation.
- Every mutation is recorded in a SHA-256 hash-chained JSONL audit log.
- Paths and symlinks are contained within the active matter workspace.
- Document, title, tag, source-reference, audit, diff, DOCX, and edit-operation sizes are bounded.
- Word tracked edits always write a new artifact.
- Drafts remain review-required and are never represented as filing-ready or legal advice.

## Word engine

Tracked Word editing uses the MIT-licensed [`pablospe/docx-editor`](https://github.com/pablospe/docx-editor) package. The adapter exposes only a bounded subset:

- hash-anchored paragraph listing;
- tracked replacement;
- tracked deletion;
- tracked insertion;
- paragraph rewrite with tracked changes; and
- comments.

The optional persistent Jupyter/session mode is not installed or exposed. The adapter runs without Microsoft Word and creates a separate review copy.

## Architecture credit

The local document-workspace, structured action, revision-history, and audit data-model patterns were informed by the MIT-licensed [`Paparusi/legal-ai-agent`](https://github.com/Paparusi/legal-ai-agent) project by Lê Minh Hiếu. The Maine implementation was independently rewritten and hardened. It does not incorporate the upstream authentication layer, Docker defaults, crawler, billing/admin system, Vietnamese legal rules, autonomous destructive permissions, or formatting-destructive DOCX editor.

See `THIRD_PARTY_NOTICES.md` and the full license texts under `licenses/`.
