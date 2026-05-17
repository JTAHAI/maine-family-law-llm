# Maine Family Law LLM

Standalone Maine family-law legal AI system scaffold for source-grounded research, matter intake, evidence mapping, timeline building, draft review, citation verification, quote verification, filing-readiness review, and authority-grounded retrieval.

## Current status

**Post-GA reality review foundation added:** all numbered pass source controls through Pass 51 are present, and the repo now includes a post-GA review/build-path audit that explicitly separates source-code foundation completion from real production GA readiness.

This repository is still only the source release package. External live Maine authority snapshots, parsed authority builds, retrieval indexes, attorney-reviewed gold eval packs, production matter stores, model weights, runtime databases, pilot evidence, security evidence, and owner signoff evidence are referenced by manifests and must remain outside the source ZIP. Fixture artifact references and fixture signoffs are not production evidence.


## Enterprise hardening / local resource collection

This release adds a Windows-first enterprise hardening path for a local checkout at `C:\dev\ME_FM_LLM`. The collector and hardening wrappers download official/review resources into an external data root, defaulting to `C:\dev\ME_FM_LLM_data`, while keeping the source repository clean.

```powershell
cd C:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\scripts\harden-enterprise-local.ps1 `
  -RepoRoot C:\dev\ME_FM_LLM `
  -DataRoot C:\dev\ME_FM_LLM_data
```

Resource-only collection and audit:

```powershell
python .\scripts\collect-enterprise-resources.py --data-root C:\dev\ME_FM_LLM_data
python .\scripts\audit-enterprise-resource-collection.py --data-root C:\dev\ME_FM_LLM_data
```

The resource catalog lives at `configs/maine_enterprise_resource_catalog.json` and covers Maine statutes, court rules, standing orders, forms, family guidance, Law Court opinion indexes, eCourts/public-records rules, child-support resources, and federal family-law-adjacent authority. See `docs/enterprise-local-hardening.md`.

## Remaining numbered passes

All numbered implementation passes through **Pass 51 — GA shipped** now have source-code controls/scaffolding in this repo. The post-GA review audit reports that real production GA remains blocked until live official Maine authority, attorney-reviewed eval evidence, measured release metrics, pilot evidence, security/governance evidence, and signed security/legal/product/ops approvals are supplied to the release gates.


## Post-GA repo review / build path

Run the reality audit after Pass 51:

```bash
python scripts/run-post-ga-repo-review.py --data-root <external-data-root> --eval-root <external-eval-root>
```

This writes:

```text
post_ga_repo_review_build_path.json
```

The expected status in a source-only package is `blocked_real_build_path_required`, because the real external corpus, parsed authority, retrieval indexes, attorney-reviewed gold pack, production metrics, pilot evidence, security evidence, and owner signoffs are not bundled into the repository.

## Core principles

- Official Maine authority outranks generated content.
- Human review is required by default.
- No private matter data is packaged into releases.
- No private matter data trains shared models by default.
- No filing-ready export without verification gates.
- Source correctness matters more than prose quality.


## What Pass 11 foundation added

- `legal.model_orchestration` package.
- Model role catalog and model admission policy.
- Model admission records with benchmark, privacy, latency, cost, fallback, and eval-regression metadata.
- Orchestrator that routes tasks to admitted workers or safe review-required fallback.
- Hard block preventing any model from certifying citation validity, quote validity, authority validity, or filing readiness.

## What Pass 12 foundation added

- `legal.security` package.
- RBAC and tenant/matter isolation primitives.
- Append-only hash-chained audit log foundation.
- Prompt/document injection scanner.
- Governance checklist for required controls and LLM threat categories.
- Honest incomplete status for production controls that require real infrastructure/audit.

## What Pass 9 foundation added

- `legal.matter` package with matter and matter-document models.
- External-only `MatterStore` adapter that refuses repository-local matter storage.
- Matter document ingestion with hashing, classification, private-data scanning, and redaction.
- Privilege, confidentiality, sealed-record, and juvenile/sensitive-family warnings.
- Fact extraction, timeline normalization, fact-to-evidence mapping, and missing-record checklist generation.
- API shell endpoints for `/api/intake/matter` and `/api/intake/document`.

## What Pass 10 foundation added

- Review-required drafting templates for motions, affidavits, proposed findings, objections, client letters, and plain-language explainers.
- Draft generation that carries source cards and authority matrix placeholders.
- Draft review that blocks export for missing sections, source cards, authority matrix, evidence map, citation report, quote report, and human review.
- API shell endpoint for `/api/draft`.

## Earlier completed foundations

- Pass 7: verifier intelligence foundation for citations, quote spans, claim support, stale authority, jurisdiction mismatch, and filing blockers.
- Pass 8: rule-based Maine Law Court intelligence foundation.
- Pass 5: dependency-free BM25, exact lookup, semantic adapter, hybrid fusion, source cards, and retrieval metrics.
- Pass 6 foundation: schemas and seed rows for required gold dataset families.
- Pass 2–4: official source catalog, ingestion primitives, canonical document model, citation/source resolution, authority graph.
- Pass 1: data-boundary policies, private-data scanning/redaction, retention policy, and release scanning.
- Pass 0: repo hardening, packaging, CI, quality checks, and private/runtime artifact exclusion.


## Windows local operator path

After extracting the ZIP to `C:\dev\ME_FM_LLM`, use the Windows scripts rather than manual one-off commands:

```powershell
cd C:\dev\ME_FM_LLM
C:\dev\ME_FM_LLM_venv\Scripts\Activate.ps1
.\scripts\run-tests.ps1 -RepoRoot C:\dev\ME_FM_LLM -DataRoot C:\dev\ME_FM_LLM_data -Install
.\scripts\run-local-smoke.ps1 -RepoRoot C:\dev\ME_FM_LLM -DataRoot C:\dev\ME_FM_LLM_data
.\scripts\run-local-api.ps1 -RepoRoot C:\dev\ME_FM_LLM -DataRoot C:\dev\ME_FM_LLM_data
```

Open `http://127.0.0.1:8000/api/health`, `http://127.0.0.1:8000/api/version`, or `http://127.0.0.1:8000/docs`. The root URL `/` is intentionally not a product UI route yet.

The smoke script is a source-only local operator check. It does not certify production legal GA and does not require official authority corpora to be baked into the repo.

## Local setup

```bash
python -m pip install -e ".[dev]"
```

## Test

```bash
python -m pytest -q
```

Expected Pass 13 + Pass 14 + Pass 15 foundation result:

```text
79 tests passed
```

## Run quality checks

```bash
python scripts/run-quality-checks.py
```

This writes:

```text
smoke_evidence_pass13_pass14_pass15_foundation.json
```

## Package clean release

```bash
scripts/package-release.sh /tmp/maine-family-law-llm-pass13-pass14-pass15-foundation-release.zip
```

The package excludes runtime/private artifacts by policy.

## Legal readiness warning

This repo now has all numbered roadmap foundations through Pass 15. It is not enterprise-ready until the foundations are expanded with real official corpus volume, attorney-reviewed evaluation data, measured release gates, production security controls, and attorney pilot validation.


## Pass 16 enterprise legal data product gate

This release adds an enterprise data-product gate. The source ZIP is still a clean code artifact, not the bundled legal corpus. Production release requires external official Maine authority stores, parsed authority, retrieval indexes, source freshness reports, and attorney-reviewed gold eval datasets meeting minimum sample sizes.

## Pass 19–21 authority execution, parsed store, and freshness update

This release advances the external legal data-product workstream:

- Pass 19 hardens official-source ingestion with retry/backoff, rate limiting, robots handling, failed-source reporting, and run reports.
- Pass 20 adds parsed authority JSONL builders/auditors for statute title indexes, PDF snapshots, rules, forms, and Law Court opinion indexes.
- Pass 21 adds source freshness classification, manifest diffing, and `source_update_report.json` generation.

Run the authority data-product path in a networked environment with an external data root:

```bash
python scripts/ingest-maine-authority.py --data-root <external-data-root>
python scripts/audit-authority-build.py --data-root <external-data-root>
python scripts/build-parsed-authority-store.py --data-root <external-data-root>
python scripts/audit-parsed-authority-store.py --data-root <external-data-root>
python scripts/build-source-update-report.py --data-root <external-data-root>
```

Quality evidence for this release is written to:

```text
smoke_evidence_pass19_pass20_pass21_authority_execution.json
```

Expected test result for this release:

```text
92 tests passed
```

Important: this source ZIP does not include the external official authority corpus, parsed authority store, eval store, embedding store, runtime DBs, model weights, secrets, private matter files, or attorney work product.


## Pass 22–25 authority graph, retrieval indexes, smoke eval, and triage

This release turns parsed authority records into an external authority/retrieval product:

- Pass 22 builds `authority_layer/citation_index.json`, `authority_layer/authority_graph.json`, and `authority_layer/source_cards.jsonl`.
- Pass 23 builds external `embedding_store/bm25/`, `embedding_store/vector/`, and `embedding_store/hybrid/` artifacts, including exact citation, form ID, case name, statute section, parent-child chunk, and source-card indexes.
- Pass 24 adds measured source-derived retrieval smoke eval with Recall@5, Recall@10, Recall@20, MRR, and nDCG.
- Pass 25 adds retrieval failure clustering/tickets and query-expansion output.

Run the authority/retrieval data-product path in a networked environment with an external data root:

```bash
python scripts/ingest-maine-authority.py --data-root <external-data-root>
python scripts/audit-authority-build.py --data-root <external-data-root>
python scripts/build-parsed-authority-store.py --data-root <external-data-root>
python scripts/audit-parsed-authority-store.py --data-root <external-data-root>
python scripts/build-source-update-report.py --data-root <external-data-root>
python scripts/build-authority-layer.py --data-root <external-data-root>
python scripts/build-retrieval-indexes.py --data-root <external-data-root>
python scripts/run-retrieval-smoke-eval.py --data-root <external-data-root>
python scripts/triage-retrieval-failures.py --data-root <external-data-root>
```

Quality evidence for this release is written to:

```text
smoke_evidence_pass22_pass23_pass24_pass25_authority_retrieval.json
```

Expected test result for this release:

```text
96 tests passed
```


## Reboot-safe resume check

After a Windows reboot, resume local testing from `C:\dev\ME_FM_LLM` with the external data root at `C:\dev\ME_FM_LLM_data`:

```powershell
cd C:\dev\ME_FM_LLM
py -3.11 scripts\run-reboot-safe-healthcheck.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\run-test-readiness.py --data-root C:\dev\ME_FM_LLM_data --skip-pytest
py -3.11 scripts\run-enterprise-preflight.py --data-root C:\dev\ME_FM_LLM_data
```

This verifies required scripts/configs, external data-root write access, forbidden runtime-data exclusions, and the one-pass-log rule. See `docs/reboot-safe-test-handoff.md`. Passing this check means source/fixture testing can resume; it does not mean production legal readiness.


### Operator test battery

After extracting the repo to `C:\dev\ME_FM_LLM`, run this source/local-test acceptance battery before deeper testing or public GitHub staging:

```powershell
cd C:\dev\ME_FM_LLM
python scripts\run-operator-test-battery.py --data-root C:\dev\ME_FM_LLM_data
```

A passing operator battery means the package is ready for local fixture/source testing. It does not make the system legal-production-ready; live official Maine authority, attorney-reviewed evals, measured metrics, pilot/security evidence, and owner signoffs are still required.
