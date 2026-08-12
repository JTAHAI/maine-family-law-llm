# Maine Family Law LLM v5.5.0 — Immutable Local Authority Generations

v5.5.0 hardens the external Maine-law data product. Official snapshots, parsed authority, citation indexes, authority graphs, freshness reports, and retrieval artifacts can no longer be treated as one mutable directory that silently changes underneath the application.

## Immutable generation publishing

The authority pipeline now publishes a content-addressed generation under:

```text
<external-data-root>/authority_product/builds/<build-id>/authority_product_manifest.json
```

A generation is activated only after the publisher verifies:

- the external data root is outside the source repository;
- every official snapshot exists, is a regular non-symlink file, and matches its recorded SHA-256;
- the parsed-authority manifest exists and all referenced JSONL collections are present;
- the authority-layer report has passed;
- the retrieval-index manifest has passed;
- the source freshness/update report has passed;
- every referenced authority/retrieval artifact is contained within the external data root and is re-hashed during publication.

The publisher copies every official snapshot and every derived control/index artifact into the content-addressed generation before activation. The active generation therefore remains verifiable even when the mutable ingestion workspace is refreshed or removed.

The active generation is selected by an atomically written `authority_product/ACTIVE_BUILD.json` pointer. The pointer binds the build ID, immutable manifest path, and manifest SHA-256. A partial build never becomes active.

## Runtime verification

The new verifier checks the active pointer, build fingerprint, source snapshots, artifact sizes, and artifact hashes. Tampering, missing files, symlinks, path escapes, malformed control files, stale pointers, or build-ID collisions fail closed.

The local API exposes read-only authority endpoints:

- `GET /api/authority/status`
- `POST /api/authority/citations/resolve`
- `GET /api/sources/{source_id}`

The API returns bounded admitted source text and safe source cards only after the active generation verifies. Absolute local paths and snapshot paths are not exposed.

## Citation handling

Maine citations now normalize common variants to one canonical key, including:

- `19-A M.R.S. § 1653`
- `19-A M.R.S.A. § 1653`
- `19-A MRSA § 1653`
- `Title 19-A, § 1653`
- subdivisions such as `§ 1653(3)(A)`
- Law Court pinpoint forms such as `2026 ME 12, ¶ 14`
- spaced or hyphenated form IDs such as `FM 001` and `FM-001`

The citation index no longer overwrites an earlier source when several admitted records share the same citation. It retains all candidates and deterministically prefers direct, fresh official authority over an index/reference record. Retrieval indexes also emit `exact_citation_candidates.json` and hash every generated artifact.

## Pipeline changes

`run-authority-data-product.py` now includes required publication and verification stages after authority-layer and retrieval-index construction:

```text
publish_authority_product
verify_authority_product
```

Standalone commands are also available:

```bash
python scripts/publish-authority-product.py --data-root <external-data-root>
python scripts/verify-authority-product.py --data-root <external-data-root>
```

Large official source snapshots, parsed legal data, embeddings, indexes, and evaluation stores remain outside the repository and release ZIP.

## Release qualification

This source release adds the production boundary and tests for immutable authority generations. It does not claim that a live, complete Maine authority data build was executed in the offline packaging environment. A production operator must run official-source ingestion against the current official sites, complete the parser/retrieval audits, publish the generation, and preserve the resulting external evidence.

Product version: **5.5.0**. Microsoft Store package target: **5.5.0.0**. UI build: **32**.
