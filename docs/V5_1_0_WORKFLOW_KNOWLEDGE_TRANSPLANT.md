# v5.1.0 Workflow and Knowledge Transplant Upgrade

## Scope

This upgrade selectively adapts permissively licensed backend concepts from public repositories reviewed for fit with Maine Family Law LLM. The goal is rapid feature improvement without importing a foreign UI, changing the local-only boundary, adding a cloud dependency, or weakening existing release and security controls.

## Included components

### Declarative workflow-skill registry

`legal/workflow_skills/` loads strict JSON manifests only. A manifest declares:

- name and semantic version;
- module and user role;
- legal-workflow phases and categories;
- required permissions and dependencies;
- output contract and source requirements;
- whether network access is permitted;
- mandatory review status.

Loading a skill never imports or executes skill code. The bundled manifests in `configs/workflow_skills/` are data-only and network-disabled.

### Read-only matter inventory

`legal/matter/document_inventory.py` and `scripts/scan-matter-folder.py` provide:

- supported-format and size inventory;
- optional SHA-256 hashing;
- large-file warnings;
- recursive or top-level scan;
- symlink blocking and root-path containment;
- explicit blocked-entry reporting;
- no move, rename, delete, open-with, macro, or shell behavior.

### Many-to-many record classification

`legal/matter/multi_label_classifier.py` allows one record to carry multiple conservative labels. It exposes low confidence, unreadable records, broad bundles, and unclassified documents instead of forcing one exclusive folder.

### Cross-document consistency review

`legal/matter/consistency_review.py` extracts a bounded set of hard fields and reports conflicts only when the same context has different values across different documents. Each occurrence retains document ID, filename, offsets, and surrounding context. The component expressly leaves legal significance undetermined.

### Independent QC contract

`legal/qc/` provides structured issue classes:

- blocker;
- verify;
- evidence required;
- authority required;
- stale-law risk;
- contradicted;
- suggestion.

A QC report rejects identical drafter and reviewer run IDs and can never set `filing_ready=true`.

### Portable knowledge bundles

`legal/knowledge_bundle/` implements a strict local subset inspired by Open Knowledge Format:

- Markdown concept documents;
- strict non-executable frontmatter;
- path-safe concept IDs;
- generated indexes;
- SHA-256 manifest validation;
- tamper detection;
- no YAML object construction or arbitrary deserialization;
- no network, cloud, model, or crawler dependency.

### Local document utilities

- `scripts/extract-docx-media.py` safely extracts bounded `word/media/` content for local visual review. It writes only sanitized basenames under a selected directory and never executes extracted data.
- `scripts/package-workflow-skill.py` creates deterministic data-only `.skill` archives while rejecting symlinks, executables, credentials, caches, unsupported extensions, path escapes, oversized packages, and excessive file counts.

## Attribution

The workflow, classification, QC, scan, DOCX-media, and skill-package patterns are adapted from the MIT-licensed `zeweihan/A-market-ecm-lawyer-plugin` project. Credit is retained in source docstrings, `THIRD_PARTY_NOTICES.md`, `ATTRIBUTION.md`, and the included MIT license.

The portable knowledge-bundle design is inspired by the Apache-2.0 `GoogleCloudPlatform/knowledge-catalog` Open Knowledge Format work. Credit and the Apache 2.0 license are retained.

## Explicit exclusions

No source code was taken from:

- AGPL-licensed AI Workdeck;
- public repositories with no license;
- leaked or mirrored proprietary source snapshots;
- credentialed Chinese business-data connectors;
- Google ADK, Gemini, BigQuery, or cloud crawling code.

## Security posture

The transplanted feature code adds no feature-specific runtime dependency and no automatic network path. Existing PDF and optional API/build dependency floors were raised to current patched releases, and offline plus CI advisory gates were added. All new components are local, bounded, explicit, and review-required. Filesystem access is read-only except for user-selected derived outputs. Existing local source inspection remains the proper surface for opening source material.


## Dependency hardening

See [`V5_1_0_DEPENDENCY_SECURITY_REVIEW.md`](V5_1_0_DEPENDENCY_SECURITY_REVIEW.md). The source dependency declarations and Store build pins now exclude known vulnerable pypdf and Starlette generations, CI runs `pip-audit`, and Dependabot checks Python and GitHub Actions weekly.
