# Maine Family Law LLM v5.15.0 — Authority Change Impact

v5.15.0 adds verified authority-generation comparison and matter revalidation.

- Compare two immutable external authority generations.
- Detect added, removed, content-hash-changed, and metadata-changed official sources.
- Map changed sources to the exact document revision and its prior review packet.
- Invalidate affected prior approval rather than carrying it forward.
- Flag form-source changes and stale or unknown target freshness.
- Generate immutable JSON, HTML, receipt, and manifest artifacts.
- Refuse tampered packets, repository-contained authority roots, and packets made stale by later document edits.

A source change does not establish legal materiality or current law. Human revalidation remains required.

Product version: **5.15.0**. Microsoft Store package target: **5.15.0.0**. UI build: **42**.
