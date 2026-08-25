# Third-Party Notices

Maine Family Law LLM v5.2.0 includes adapted concepts and small utilities from the following open-source projects. The adaptations were rewritten and security-hardened for a local, review-required Maine family-law workbench. No AGPL or unlicensed source code was incorporated.

## A-market ECM lawyer plugin

- Project: `zeweihan/A-market-ecm-lawyer-plugin`
- Copyright: 2026 zeweihan and A-market-ecm-lawyer-plugin contributors
- License: MIT
- Included license: `licenses/A-market-ecm-lawyer-plugin-MIT.md`
- Adapted work:
  - declarative legal workflow skill manifest and role-separation concepts;
  - many-to-many document classification and missing-record review patterns;
  - independent QC issue taxonomy and draft/QC separation;
  - read-only directory inventory utility, adapted from `scan_folder.py`;
  - DOCX embedded-media extraction utility, adapted from `extract_images.py`;
  - deterministic data-only skill packaging convention, adapted from `package-skill.sh`.

The original project targets Chinese A-share equity-capital-markets legal practice. Maine Family Law LLM does not import its jurisdiction-specific legal rules or represent them as Maine authority.

## Open Knowledge Format / knowledge-catalog

- Upstream project: `GoogleCloudPlatform/knowledge-catalog`
- License: Apache License 2.0
- Included license: `licenses/Google-knowledge-catalog-Apache-2.0.md`
- Adapted work:
  - portable Markdown knowledge bundles with strict frontmatter;
  - stable path-derived concept identifiers;
  - generated indexes and SHA-256 manifests;
  - human-readable, agent-readable, version-controllable source-pack design.

The implementation in `legal/knowledge_bundle/` is a modified, security-hardened subset inspired by Open Knowledge Format v0.1. It uses no Google ADK, Gemini, BigQuery, crawler, or cloud dependency.

## AI Legal Agent document-workspace patterns

- Project: `Paparusi/legal-ai-agent`
- Copyright: 2026 Lê Minh Hiếu (Paparusi)
- License: MIT
- Included license: `licenses/Paparusi-legal-ai-agent-MIT.md`
- Adapted work:
  - structured document-action and tool-result contracts;
  - revision, annotation, audit, and document-history data-model patterns;
  - main-chat document actions and structured line-diff concepts;
  - provider-neutral and hybrid-retrieval interface concepts.

The Maine implementation is independently rewritten and substantially hardened. It does not incorporate Paparusi's authentication layer, Docker defaults, billing/admin system, crawler, Vietnamese legal rules, autonomous destructive permissions, or formatting-destructive DOCX replacement code.

## docx-editor

- Project: `pablospe/docx-editor`
- Copyright: 2026 Pablo Speciale
- License: MIT
- Included license: `licenses/pablospe-docx-editor-MIT.md`
- Use in this project:
  - hash-anchored Word paragraph references;
  - tracked insertions, deletions, replacements, rewrites, and comments;
  - revision-aware Word output without requiring Microsoft Word;
  - atomic save and document-open collision protections supplied by the dependency.

Maine Family Law LLM wraps this dependency with source-root containment, size and operation caps, explicit user confirmation, immutable imported originals, and new-copy-only output. The optional session/Jupyter mode is not installed or exposed.

## whisper.cpp

- Project: `ggml-org/whisper.cpp`
- Version: 1.9.2 (CPU-only Windows x64 release)
- License: MIT
- Included license: `licenses/whisper.cpp-MIT.md`
- Included model: `ggml-tiny.en-q5_1.bin`, distributed by the whisper.cpp project
- Use in this project:
  - fully local English speech-to-text for admitted matter audio;
  - timestamped, source-hash-bound transcript derivatives;
  - offline runtime operation with no model or engine download.

The Store build pins and verifies the release archive, executable, and model by SHA-256. Transcripts remain derived, review-required work product and are not treated as official court transcripts.

## Excluded after review

The following repositories were reviewed but their code was not incorporated:

- `zeweihan/aiworkdeck` — AGPLv3/commercial-license project; architecture studied only.
- Unlicensed public repositories — design ideas only; no source copied.
- Claude Code source snapshot mirrors — no source copied or used.

All legal outputs remain review-required. Third-party attribution does not imply endorsement, affiliation, legal accuracy, or attorney review.
