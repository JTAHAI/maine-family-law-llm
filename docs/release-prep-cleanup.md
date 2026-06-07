# Release prep cleanup

This cleanup checklist supports source-repo hygiene before outreach.

- Run `git status --short`.
- Do not stage private matter data, runtime databases, vector stores, corpora, OCR caches, model weights, local logs, or real outreach correspondence.
- Keep generated sample evidence only when deterministic and intentionally part of source-controlled evidence.
- Run `python scripts\check-outreach-truthfulness.py`.
- Run `python scripts\check-doc-unsafe-claims.py`.
- Run `python scripts\run-conversation-product-polish-evidence.py`.
- Run `python scripts\doctor-local-repo.py --repo-root D:\dev\maine-family-law-llm_git --json`.

The expected final state for this internal workstream is reviewer-outreach preparation complete, emails unsent, attorney review unclaimed, and true GA passes 48-51 still open.
