# Retention and Deletion Policy

This policy is a Pass 1 scaffold. Deployments must adapt it to the law firm, legal aid organization, or institutional environment.

## Policy source

Machine-readable retention rules live in `configs/maine_retention_policy.json` and are exposed by `legal.data_boundaries.retention_policy_for()`.

## Class-level policy

| Data class | Retention | User deletion request |
|---|---|---|
| `official_public_authority` | Indefinite snapshot history | No |
| `public_non_official_source` | Until source review or superseded | No |
| `licensed_secondary_source` | License term or shorter | License governed |
| `user_provided_confidential_matter_data` | Matter policy defined | Yes |
| `synthetic_eval_data` | Project lifetime | No |
| `attorney_reviewed_eval_data` | Review approval term | Yes |
| `model_artifact` | Until deprecated and audit window closed | No |
| `audit_record` | Firm/deployment policy | Redact or tombstone if legal hold allows |

## Minimum deletion action for matter data

When deletion is permitted for user-provided confidential matter data, deletion must cover:

1. source files,
2. extracted text,
3. OCR caches,
4. embeddings,
5. vector index entries,
6. generated private work product,
7. non-required audit references where legal holds allow.

## Legal hold and audit caveat

Audit records may need to be retained or tombstoned rather than fully deleted when a legal hold, compliance duty, or institutional audit policy requires preservation. The source system must record the deletion decision and reason.
