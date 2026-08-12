# Maine Family Law LLM v6.0.1 — Bug Hunt

v6.0.1 is a bounded defect-correction release on top of the v6 visual design system. It does not add new legal workflow scope or relax any human-review or external-evidence gate.

## Reproducible fixes

- Replaced path-string prefix checks with path-component containment checks, preventing sibling paths with matching name prefixes from being misclassified.
- Rejected Windows absolute and backslash-separated source-ZIP paths consistently on Windows and non-Windows hosts.
- Restricted release evidence references to opaque IDs, HTTPS references without embedded credentials, and URNs; active or local schemes such as `javascript:`, `data:`, and `file:` are refused.
- Required timezone-aware release-candidate signoff timestamps.
- Changed safety, consent, confirmation, and approval request fields to strict JSON booleans so strings such as `"yes"` cannot be coerced into approval.
- Repaired the documented API import fallback when FastAPI and Pydantic extras are absent.
- Made evidence-jump scrolling respect the operating system reduced-motion preference.

## Release identity

Product version: **6.0.1**
Microsoft Store package target: **6.0.1.0**
UI build: **48**

This is a source release. Signed MSIX, WACK, Store approval, real pilot evidence, legal signoff, and GA shipment evidence remain external qualification items.
