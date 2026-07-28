# Maine Family Law LLM v5.1.0

## Local workflow, matter consistency, independent QC, and portable knowledge packs

v5.1.0 upgrades the v5.0.1 full-source workbench with security-hardened backend components adapted from permissively licensed legal-tech and knowledge-catalog projects. The UI remains the Maine Family Law LLM UI; no foreign UI framework was imported.

## New capabilities

### Declarative legal workflow skills

- Added a strict, read-only JSON skill registry with versioned roles, phases, categories, permissions, dependencies, source requirements, output contracts, and review requirements.
- Added five bundled Maine workflow manifests for matter inventory, multi-label classification, consistency review, review-required drafting, and independent QC.
- Loading a skill never imports or executes plugin code.

### Matter inventory and classification

- Added a read-only matter-folder scanner with optional SHA-256 hashing, file-type counts, large-file warnings, root-containment checks, symlink blocking, and explicit blocked-entry reporting.
- Added conservative many-to-many record classification so one document can support multiple legal-workflow categories.
- Added review states for unreadable, low-confidence, broad-bundle, and unclassified files instead of silently forcing a category.

### Cross-document consistency review

- Added bounded extraction of context-specific dates, docket numbers, and monetary fields.
- Added source-linked conflict records when different documents state different values for the same context.
- Contact details are not treated as contradictions without a stable subject identifier.
- Legal significance is never inferred automatically; every conflict remains review-required.

### Independent QC contracts

- Added structured QC issue classes: blocker, verify, evidence required, authority required, stale-law risk, contradicted, and suggestion.
- Draft and QC runs must be independent; the same run cannot approve its own work.
- QC output cannot mark a result filing-ready.

### Portable knowledge bundles

- Added strict local Markdown knowledge bundles with non-executable frontmatter, stable concept IDs, generated indexes, SHA-256 manifests, tamper detection, file-count and size limits, and symlink/path traversal rejection.
- The bundle format is suitable for portable Maine authority packs, source registries, reviewer playbooks, and state-fork knowledge packages.

### Local document utilities

- Added safe DOCX embedded-media extraction with archive-member, byte, filename, and path controls.
- Added deterministic data-only workflow-skill packaging that rejects executables, credentials, caches, symlinks, path escapes, oversized packages, and malformed manifests.
- Added CLI commands for skill validation, matter scanning, knowledge-bundle validation, and dependency-floor checks.

## Dependency and release security

- Raised `pypdf` to `>=6.14.2,<7` and `pypdfium2` to `>=5.12.1,<6`.
- Raised the optional loopback API stack to FastAPI `>=0.139.2,<1`, Starlette `>=1.3.1,<2`, Uvicorn `>=0.51,<1`, and HTTPX `>=0.28.1,<1`.
- Raised Microsoft Store build pins for the API, image, and packaging stack.
- Added an offline dependency-floor gate, CI `pip-audit`, and weekly Dependabot checks.
- New transplanted features add no automatic network access and no feature-specific runtime dependency.

## Attribution

Credit is retained for the source projects that informed or supplied adapted components:

- `zeweihan/A-market-ecm-lawyer-plugin` — MIT License; workflow skill contracts, role separation, document-classification and QC patterns, folder scanning, DOCX media extraction, and skill packaging.
- `GoogleCloudPlatform/knowledge-catalog` / Open Knowledge Format — Apache License 2.0; portable Markdown-plus-frontmatter knowledge-bundle concepts, path-derived concept IDs, indexes, and version-controllable source packs.

Full notices and license copies are included in `THIRD_PARTY_NOTICES.md` and `licenses/`.

No AGPL AI Workdeck code, unlicensed repository code, leaked proprietary source, credentialed business-data connectors, Google ADK, Gemini, BigQuery, or cloud-crawler code was incorporated.

## Validation

- All 28 new v5.1.0 feature/security tests passed.
- The 87-test CI-targeted regression set passed.
- A broad 170-test legacy batch completed with 169 passes and one intentional skip.
- Python compilation, local repository doctor, and fail-closed public-source preflight passed.
- The full 758-test monolithic run exceeded the execution ceiling in this environment; validation was therefore performed in bounded, actionable groups. No failure from the v5.1.0 changes remained in the completed groups.
- `pip-audit` is required in CI and release preparation. It could not be executed in this offline build environment because the current patched dependency set was not available from a package index here.

## Version and boundary

- Product version: `5.1.0`
- Microsoft Store package target: `5.1.0.0`
- Build number: `28`
- Python: `3.11+`

This is a source release. Signed MSIX/Store artifacts remain a separate Windows build, audit, signing, and WACK process. The system remains local-first, review-required, not legal advice, and not filing-ready by default.
