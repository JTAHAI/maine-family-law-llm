# Maine Family Law LLM

[![Version](https://img.shields.io/badge/source-v7.0.0-0A6E75)](docs/RELEASE_NOTES_v7.0.0.md)
[![Python](https://img.shields.io/badge/Python-3.11%2B-306998)](pyproject.toml)
[![Local first](https://img.shields.io/badge/default-local--only-17324D)](docs/privacy.md)
[![Review required](https://img.shields.io/badge/output-review_required-BB6B38)](docs/safety.md)
[![License](https://img.shields.io/badge/license-see%20LICENSE.md-59636E)](LICENSE.md)

Maine Family Law LLM is an open-source, local-first Windows workbench for Maine legal research, record review, source verification, privacy-aware document processing, and review-required drafting.

It is not a lawyer, does not provide legal advice, and does not turn model confidence into legal authority. Official Maine sources, exact source spans, citation and quote checks, factual support, privacy review, and human review remain separate gates.

[Project site](https://jtahai.github.io/maine-family-law-llm/) · [Current Microsoft Store build](https://apps.microsoft.com/detail/9NV67WCQW0DM) · [v7 release notes](docs/RELEASE_NOTES_v7.0.0.md) · [Safety](docs/safety.md) · [Privacy](docs/privacy.md)

## Release truth

| Surface | Current status |
| --- | --- |
| Source branch | `main`, product version `7.0.0` |
| Windows package target | `7.0.0.0`, x64, `en-us` |
| Current Microsoft Store listing | v7 is published and available as a free Windows download |
| Current source release | v7.0.0 on `main` |
| v7 package | Distributed through the official Microsoft Store listing |
| Enterprise GA | Blocked pending real attorney-reviewed evaluation, controlled pilot evidence, and organizational sign-offs |

See [the public v7 release status](docs/RELEASE_STATUS_v7.0.0.md) for Store availability, source evidence, and the separate Enterprise-GA boundary.

## Verified v7 public scope

The release scope is deliberately smaller than the codebase. These are the public v7 surfaces retained after source and frozen-runtime verification:

- application launch, health, and production workbench;
- matter/corpus creation, selection, and reopening;
- mixed-record import and deterministic inventory;
- deterministic PDF, DOCX, and text parsing;
- OCR searchable derivatives that preserve originals;
- document intelligence, privacy review, and redacted derivatives;
- exact-duplicate and changed-copy review;
- Ask Maine Family Law with admitted official-source cards;
- exact source preview and source metadata;
- citation, pinpoint, quote, and claim-support verification;
- review-required drafting and immutable revision history;
- revision comparison;
- review-required evidence/filing packets and receipts;
- the canonical fail-closed filing gate;
- Local-only and privacy controls;
- synthetic backup and restore.

All generated legal work remains `review_required` by default.

## Verified specialized workbenches

Slices 21–44 now complete the production service → canonical local API → matter-scoped encrypted store → shipped desktop UI → exact-source inspection → review-required result path. Their focused synthetic suite, production-browser journey, and full-tier frozen-runtime reachability checks pass:

- slices 21–31 cover intake/posture trees, operative-order resolution, service/deadline calendars, docket reconciliation, discovery, exhibits, witness comparison, hearing preparation, appellate preservation, UCCJEA, and ICWA review;
- slices 32–44 cover family pathways, safety records, parenting schedules, negotiation, property, modification, FOAA, filing readiness, image/email integrity, reviewer handoff, language access, and resource navigation;
- all 24 are local-only, matter-scoped, source-bound, auditable, and review-required.

Additional source capabilities still under qualification include:

- timeline event correction;
- claim-disposition workbench;
- current guided forms;
- installed tracked-DOCX workflow;
- whole-matter command center and snapshots;
- missing-attachment coverage claims.

The feature catalog keeps readiness evidence visible; code presence alone is never represented as end-to-end acceptance.

## Why this is different from a generic chatbot

The workbench separates three lanes:

1. **Official Maine authority** — admitted external sources with hashes, retrieval dates, freshness, lineage, citations, and exact spans.
2. **Private matter records** — evidence candidates scoped to the active matter; never legal authority.
3. **Model analysis** — review-required work product that cannot silently outrank either source lane.

A legal claim fails closed when its source is missing, stale, wrong-jurisdiction, contradicted, unsupported, or unverifiable. A verifier exception is a blocker, not a pass.

## Local-first data boundaries

Private matter data does not belong in this repository. Runtime matter stores, authority snapshots, parsed authority products, retrieval indexes, OCR caches, logs, credentials, model caches, evaluation stores, and generated work product remain outside the source tree and MSIX.

The standard runtime binds its local API to loopback. Local-only mode forbids silent provider discovery, telemetry, model downloads, background updates, arbitrary URL requests, and remote fallback.

Read [Privacy](docs/privacy.md), [Safety and data boundaries](docs/safety.md), and [MSIX privacy boundaries](docs/MSIX_PRIVACY_BOUNDARIES.md) before using private records.

## Official Maine authority

Legal-authority data is built and activated outside the repository:

```powershell
python scripts/ingest-maine-authority.py --data-root <external-data-root>
python scripts/audit-authority-build.py --data-root <external-data-root>
```

An accepted generation includes an immutable build fingerprint, official URLs, source and parsed hashes, retrieval timestamps, freshness, citation aliases, exact spans, and atomic activation/rollback pointers. If no accepted build is active, the application must say so and must not substitute model memory as current law.

## Run from source

Requirements:

- Windows 10 or 11 x64;
- Python 3.11 or newer;
- a dedicated virtual environment;
- user-controlled storage for matter and authority data.

```powershell
git clone https://github.com/JTAHAI/maine-family-law-llm.git
cd maine-family-law-llm
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[api,dev]"
.\START_MAINE_FAMILY_LAW_LLM.cmd
```

Start with fictional demonstration data. Do not post private records, identifying screenshots, logs, tokens, or local paths in GitHub issues.

## Validate a checkout

```powershell
python -m compileall -q legal app src maine_family_law_llm scripts tests
node --check src\maine_family_law_llm\ui\workbench.js
python -m pytest --collect-only -q
python -m pytest
```

The v7 closure run collected 1,234 tests: 1,220 passed, 14 documented Windows skips, and no failures or errors. The final focused package/release set added 64 passing tests. Those results describe the tested source and frozen runtime; Store availability and enterprise validation remain distinct evidence layers.

## Package status

The canonical build produces:

```text
MaineFamilyLawLLM_7.0.0.0_x64.msix
```

The locally built candidate passed manifest, sealed-payload, path, private-data, bundled-engine, offline-runtime, and 16-case filing-gate audits. The distributable is not committed to this repository; v7 is obtained through the official Microsoft Store listing.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/maine_family_law_llm/` | Canonical application package and production UI |
| `maine_family_law_llm/` | Shipped compatibility mirror |
| `legal/` | Authority, retrieval, evidence, drafting, verification, and privacy services |
| `app/` | Desktop/local API integration and supporting UI contracts |
| `store/msix/` | Store identity, manifest template, and package assets |
| `scripts/` | Build, authority, audit, migration, and release tooling |
| `tests/` | Unit, contract, security, UI, frozen-runtime, and release tests |
| `docs/` | Public guides, safety policy, architecture, and release truth |

The frozen executable loads the production assets from `src/maine_family_law_llm/ui`; mirrored or development-only frontends are not accepted as production proof.

## Security model

Release-critical controls include:

- matter-scoped record capabilities and stale-token rejection;
- path traversal, symlink, archive bomb, executable-content, size, and format validation;
- untrusted document/prompt/OCR/tool instructions treated as data;
- loopback origin/session protections;
- encrypted private sidecars and hash-chained audit events;
- fail-closed filing/export gates;
- no private data, authority stores, credentials, logs, caches, or test residue in the MSIX.

Please report security issues through the process in [SECURITY.md](SECURITY.md), not through a public issue containing sensitive details.

## Build a verified edition for another state

Forking the code is only the beginning. A safe state edition must replace and validate its official statutes, rules, forms, appellate opinions, citation patterns, freshness controls, evaluation data, privacy policy, unauthorized-practice boundaries, and human-review rules.

See [Fork for your state](docs/FORK_FOR_YOUR_STATE.md).

## Contributing

Contributions are welcome for reproducible bugs, accessibility, privacy, retrieval correctness, source parsing, testing, documentation, and safe state-specific adaptations.

- Read [CONTRIBUTING.md](CONTRIBUTING.md).
- Use fictional or fully synthetic fixtures.
- Preserve original records and fail-closed review behavior.
- Do not weaken matter isolation, source verification, privacy review, or filing gates to make a test pass.

## Legal and project notices

- Not legal advice.
- No attorney-client relationship.
- Not affiliated with the Maine Judicial Branch, any court, Microsoft, or a government agency.
- Official sources and qualified human review control over generated text.
- See [LICENSE.md](LICENSE.md), [NOTICE.md](NOTICE.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
