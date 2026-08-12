# v5.5 Immutable Authority Product

## Purpose

The source repository and the Maine legal data product have different trust and release boundaries. The repository contains code, schemas, policies, tests, and public documentation. Official legal snapshots, parsed authority, indexes, embeddings, evaluation data, and private matter data remain outside the repository.

v5.5 introduces an immutable generation boundary so a running application can identify exactly which legal data build it is using and verify that the build has not changed.

## External layout

```text
<external-data-root>/
  official_authority_store/
    source_manifest.json
    ... content-addressed snapshots ...
  parsed_authority_store/
    parsed_authority_manifest.json
    statutes/*.jsonl
    rules/*.jsonl
    forms/*.jsonl
    opinions/*.jsonl
  authority_layer/
    citation_index.json
    authority_graph.json
    source_cards.jsonl
    authority_layer_report.json
  embedding_store/
    retrieval_index_manifest.json
    bm25/
    vector/
    hybrid/
  source_update_report.json
  authority_product/
    ACTIVE_BUILD.json
    builds/<build-id>/
      authority_product_manifest.json
      sources/        # verified copies of admitted official snapshots
      artifacts/      # verified copies of parsed/index/control artifacts
```

## Build identity

The build fingerprint is a SHA-256 over a canonical structure containing:

- product/schema version;
- every admitted `source_id` and official snapshot SHA-256;
- every parsed/authority/retrieval artifact path and SHA-256.

The first 24 hexadecimal characters form the build ID. Generated timestamps do not affect identity.

## Activation sequence

1. Complete official-source ingestion and its audit.
2. Build and audit parsed authority.
3. Build the freshness/update report.
4. Build the citation layer and authority graph.
5. Build and audit retrieval indexes.
6. Materialize official snapshots and all admitted derived artifacts into a staging generation.
7. Verify the staged generation independently.
8. Atomically promote the staging directory and activate it through `ACTIVE_BUILD.json`.

The application must not label an answer as based on current Maine law when the active generation is missing, unverified, stale, or blocked.

## API behavior

The source API uses the active manifest rather than accepting paths from callers. Source IDs are bounded. JSONL line/row limits prevent unbounded parsing. Each artifact used by a request is hash-checked against the active manifest before being read.

Source cards remove local snapshot paths. A filesystem locator is returned only when it is an HTTP or HTTPS official-source URL.

## Failure behavior

The product fails closed for:

- a data root inside the repository;
- path traversal or symlinked files;
- missing, malformed, or oversized control files;
- duplicate/missing source IDs;
- snapshot hash mismatch;
- failed freshness, authority-layer, or retrieval reports;
- artifacts changing during publication;
- active pointer or manifest hash mismatch;
- build fingerprint mismatch;
- artifact size/hash mismatch.

## Citation candidate policy

One legal citation can appear in an index row, direct statute section, opinion metadata, form dependency, or mirror. v5.5 preserves every candidate. Primary selection is deterministic and favors:

1. verified official Maine authority;
2. fresh/current source status;
3. direct authority records over index/reference records;
4. stable source ID as the final tie-breaker.

The resolution response includes the primary source and all ranked alternatives so ambiguity is visible rather than silently discarded.
