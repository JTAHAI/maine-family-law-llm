# Data Boundaries

Enterprise Pass 1 establishes hard separation between legal authority, private matter files, evaluation assets, model artifacts, and audit records.

## Canonical stores

The canonical stores are configured in `configs/maine_storage_boundaries.json` and represented in code by `legal.data_boundaries.StoreName`.

| Store | Purpose | Release package? | Notes |
|---|---|---:|---|
| `official_authority_store` | Immutable raw official authority snapshots | No | Maine statutes, rules, forms, opinions, and federal authority snapshots. |
| `parsed_authority_store` | Parsed authority, chunks, source cards, citation spans | No | May include official, non-official public, or licensed authority with restrictions. |
| `matter_store` | User-provided confidential matter data and derived private work product | No | Encrypted-required store. Never trains shared models by default. |
| `eval_store` | Synthetic or approved evaluation data | Synthetic only | `eval_data/` remains a tiny source-controlled scaffold for non-private examples. |
| `embedding_store` | Embeddings and vector indexes | No | Derived artifacts remain outside the repo. |
| `audit_store` | Audit records and export logs | No | Encrypted-required store. Retention is deployment-defined. |
| `model_registry` | Model cards, model pointers, weights/adapters/tokenizers | No | Model artifacts are not source repository content. |

By default, runtime stores resolve under `.local_data/` or under the external path set by `MAINE_FAMILY_LAW_DATA_ROOT`. The release scanner blocks `.local_data/` and every canonical store name if one is accidentally created inside the source tree.

## Data classes

The canonical data classes are configured in `configs/maine_data_classes.json` and enforced by `legal.data_boundaries.DataClass`.

| Data class | Shared training by default? | Release package? |
|---|---:|---:|
| `official_public_authority` | Yes | No |
| `public_non_official_source` | No | No |
| `licensed_secondary_source` | No | No |
| `user_provided_confidential_matter_data` | No | No |
| `synthetic_eval_data` | Yes | Yes, after private-data scan |
| `attorney_reviewed_eval_data` | No | No |
| `model_artifact` | No | No |
| `audit_record` | No | No |

## Required document metadata

Every source or document record must carry:

- `source_id`
- `source_class`
- `jurisdiction`
- `retrieved_at`
- `hash`
- `parser_status`
- `freshness_status`
- `data_class`
- `use_restrictions`

The schema is in `legal/corpus/maine_source_manifest.schema.json`. The `SourceRecord` class now refuses incomplete boundary metadata.

## Default training rule

Private matter data, licensed secondary material, attorney-reviewed eval data, audit records, embeddings, and model artifacts are excluded from shared training by default.

Only official public authority and synthetic eval data may be used by default. Even then, release packaging remains blocked for official authority snapshots and derived authority stores.

## Default release rule

The source repository release package must not include:

- private matter files
- runtime databases
- authority corpora
- parsed authority stores
- embeddings or vector stores
- model weights/adapters/tokenizers
- audit records
- local environment files or secrets

`legal.release.ReleaseManifest` and `scripts/package-release.sh` enforce this at package time.
