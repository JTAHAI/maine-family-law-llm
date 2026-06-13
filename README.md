# Maine Family Law LLM

Standalone Maine family-law legal AI system for source-grounded research, drafting support, document review, issue spotting, evidence mapping, and Maine-specific legal workflow assistance.

> **Plain-English status:** this repo can run a local source-backed chat workbench today. It is not legal advice, it is not a lawyer, and every draft/output remains review-required.

## Download

For most users, download the latest release ZIP from GitHub, extract it, and run the local chat starter.

```powershell
cd D:\dev
# Put the downloaded ZIP in your Downloads folder first.
$zipName = "ME_FM_LLM_latest.zip"
$zipPath = "$env:USERPROFILE\Downloads\$zipName"

Remove-Item D:\dev\ME_FM_LLM -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive $zipPath -DestinationPath D:\dev\ME_FM_LLM -Force
cd D:\dev\ME_FM_LLM
```

Repository users can also clone it directly:

```powershell
git clone https://github.com/JTAHAI/maine-family-law-llm.git D:\dev\ME_FM_LLM
cd D:\dev\ME_FM_LLM
```


## Local chat question library

The browser workbench now includes a built-in starter question library for parents, lawyers, caregivers, counselors, and therapists. Start it with:

```powershell
.\START_LOCAL_CHAT.ps1
```

Then open:

```text
http://127.0.0.1:8000/
```

Usability notes:

- Press **Enter** to ask. The v1.83 browser UI includes an explicit live marker in the footer and a script-syntax regression check for this behavior.
- Press **Shift+Enter** for a new line.
- Use the audience selector to browse parent, lawyer, caregiver, counselor, and therapist starter prompts.
- Use **Download transcript** to save a local text transcript.
- API/server errors are shown in the page instead of crashing with a JSON parse error.
- Answers remain source-backed, review-required, and not legal advice.

Evidence check:

```powershell
python scripts/run-chat-library-evidence.py --require-ready
```

## Family Justice Workbench v2.05

The v2.05 Family Justice Workbench adds a deterministic packet builder for parent, caregiver, lawyer, counselor, therapist, and reviewer pathways. It returns source cards, issue labels, posture routing, safety routing, missing-information checklists, next-best actions, red flags, filing-gate blocker explanations, authority matrix preview, and reviewer handoff metadata.

Generate the local evidence/demo page:

```powershell
python scripts/build-family-justice-workbench-evidence.py --require-ready
```

Open:

```text
docs/external-evidence/family_justice_workbench_v205.html
```

The local API also exposes `POST /api/family-justice-workbench`. Outputs remain legal-information-only, review_required, and not filing_ready. See `docs/family-justice-workbench-v205.md`.

## Enterprise release control v2.06

The v2.06 Enterprise Release Control Center audits the remaining Pass 48-51 production launch gates and shows why enterprise readiness, production legal readiness, and GA shipment remain blocked until real external attorney sandbox, limited pilot, release-candidate, and shipment evidence pass.

Generate the local release-control evidence:

```powershell
python scripts/build-enterprise-release-control-evidence.py --require-ready
```

Open:

```text
docs/external-evidence/enterprise_release_control_v206.html
```

See `docs/enterprise-release-control-v206.md`.

## For non-technical local testing

### FOCAF branded local workbench

The local browser workbench now includes the FOCAF Maine Family Law LLM brand kit as repo assets under `assets/brand/focaf_family_law_llm_brand_kit/`. When `START_LOCAL_CHAT.ps1` runs, the FastAPI app serves those files from `/brand-assets`, including the logo mark, horizontal lockup, favicon, theme CSS, design tokens, and social-card artwork. The page footer should show `UI v1.86 classic desktop FOCAF workbench` after a fresh restart and hard refresh.


Run one command and use the browser chat screen:

```powershell
cd D:\dev\ME_FM_LLM
.\START_LOCAL_CHAT.ps1
```

Then open:

```text
http://127.0.0.1:8000/
```

The page lets you type a Maine family-law question, press **Enter** or **Ask**, and see the source-backed answer plus source cards. If a browser still shows the old unbranded page, use Ctrl+F5 and verify the footer says `UI v1.83 live Enter/branding fix`. It runs locally and uses the bundled offline fixture sources unless you separately build an external official authority store.

Stop the local server:

```powershell
.\STOP_LOCAL_TEST.ps1
```

## Local chat/API endpoints

Start the local workbench API manually:

```powershell
cd D:\dev\ME_FM_LLM
python -m pip install -e ".[dev,api]"
$env:PYTHONPATH = "$PWD\src;$PWD"
python -m uvicorn maine_family_law_llm.api:app --host 127.0.0.1 --port 8000
```

Useful URLs:

```text
http://127.0.0.1:8000/          # non-technical chat workbench
http://127.0.0.1:8000/docs      # Swagger API docs
http://127.0.0.1:8000/sources   # loaded source manifest
http://127.0.0.1:8000/api/health
```

PowerShell chat test:

```powershell
$body = @{ question = "What Maine sources should I check before drafting a parental rights motion?" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/chat" -Method Post -ContentType "application/json" -Body $body
```

## Command-line testing

```powershell
cd D:\dev\ME_FM_LLM
python -m pip install -e ".[dev,api]"
python -m maine_family_law_llm.cli sources validate
python -m maine_family_law_llm.cli sources fetch --fixtures
python -m maine_family_law_llm.cli sources normalize --fixtures
python -m maine_family_law_llm.cli index build --fixtures
python -m maine_family_law_llm.cli ask "What Maine sources should I check for child support?"
python -m maine_family_law_llm.cli draft "checklist for a child support issue"
```

## What this is and is not

This is a local-first Maine family-law AI workbench. It prioritizes official/source-backed Maine authority over model memory. It can help test retrieval, source cards, citation-aware answers, review-required drafting, and release gates. It does **not** certify legal advice, does **not** create an attorney-client relationship, and does **not** mark filings ready without verification gates.

---

## V1 local legal-source workbench

This project is an open-source, local-first Maine family law LLM / RAG workbench. It is not legal advice, does not create an attorney-client relationship, and does not produce filing-ready documents.

The product claim is narrow: Maine family law help with receipts. Answers must come from retrieved sources, prefer official Maine sources, include citations, preserve effective-date/version metadata, and refuse unsupported legal/procedure/form claims.

Quick local path:

```powershell
cd D:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\START_LOCAL_TEST.ps1 -SkipTests
```

CLI examples:

```powershell
python -m maine_family_law_llm.cli sources validate
python -m maine_family_law_llm.cli sources fetch --fixtures
python -m maine_family_law_llm.cli sources normalize --fixtures
python -m maine_family_law_llm.cli index build --fixtures
python -m maine_family_law_llm.cli ask "How do I start a family matter?"
python -m maine_family_law_llm.cli draft "checklist for a child support form"
python -m maine_family_law_llm.cli inspect-source mrs-title-19a-domestic-relations
python -m maine_family_law_llm.cli doctor
```

The local API exposes `/healthz`, `/sources`, `/retrieve`, `/ask`, `/draft`, `/inspect-source/{source_id}`, `/api/question-library`, `/api/question-topics`, `/api/starter-prompt-packs`, and interactive docs at `http://127.0.0.1:8000/docs`.

Source metadata lives in `data/sources/manifest.seed.json`. The seed manifest is representative, not a complete corpus. Small offline fixtures live in `data/fixtures` so tests work without internet. Do not add private client facts, raw corpora, databases, vector stores, model weights, caches, venvs, or generated junk to release ZIPs.

## Current status

This repository is ready for local testing and reviewer-outreach preparation. It is not true legal GA, not legal advice, and not filing-ready.

Internal conversation, workflow, reviewer-packet, outreach-template, and demo-journey foundations are present. External live Maine authority snapshots, parsed authority builds, retrieval indexes, attorney-reviewed gold eval packs, production matter stores, model weights, runtime databases, real pilot evidence, security evidence, and owner signoff evidence must remain outside the source ZIP unless a source-safe redacted summary is intentionally accepted by the gates.

Passes 48-51 remain open unless the existing evidence gates verify real external attorney sandbox, limited real-matter pilot, release-candidate, and shipment evidence.

Internal product-polish Passes 47I-47T add session continuity, guided workflow routing, drafting/document-review conversations, reviewer packets, unsent outreach templates, demo user journeys, UI/service adapters, conversation quality regression, doc-safety checks, and repo cleanup checks. They are internal preparation only and do not reduce the true GA count.


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

The source-code foundations are broad, but real production GA remains blocked until live official Maine authority, attorney-reviewed eval evidence, measured release metrics, pilot evidence, security/governance evidence, and signed security/legal/product/ops approvals are supplied to the release gates. Passes 48-51 remain the open true-GA gates.

## How reviewers can help

Reviewers can check whether workflows are understandable, source and uncertainty status stay visible, citations and quote spans are handled honestly, and filing-ready blockers cannot be bypassed.

## What evidence would count

Real evidence would include actual attorney sandbox feedback, signed reviewer artifacts, real pilot reports, measured release metrics, and accountable legal/security/product/ops signoffs.

## What evidence does not count

Templates, sample evidence, generated fixture reports, unsent emails, demo journeys, and internal pass summaries do not count as attorney review or pilot evidence.

## Running local checks

```powershell
python -m pytest
python scripts\run-quality-checks.py
python scripts\run-conversation-evals.py
python scripts\run-conversation-pilot-readiness-evidence.py
python scripts\run-user-journey-evals.py
python scripts\run-conversation-quality-regression.py
python scripts\run-conversation-product-polish-evidence.py
python scripts\check-outreach-truthfulness.py
python scripts\check-doc-unsafe-claims.py
python scripts\doctor-local-repo.py --repo-root D:\dev\maine-family-law-llm_git --json
```


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

Open `http://127.0.0.1:8000/` for the non-technical chat workbench, or use `http://127.0.0.1:8000/api/health`, `http://127.0.0.1:8000/api/version`, and `http://127.0.0.1:8000/docs` for API testing.

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
- Pass 20 adds parsed authority JSONL builders/auditors for statute title indexes, direct statute sections, PDF snapshots, rules, forms, and Law Court opinion indexes.
- Pass 21 adds source freshness classification, manifest diffing, and `source_update_report.json` generation.
- Pass 1.31 adds second-wave target derivation from parsed official indexes, producing `official_authority_store/derived_authority_targets.json` for direct section/rule/form/opinion ingestion.
- Pass 1.32 adds a direct-authority parsed-store audit mode so index-only stores cannot be mistaken for retrieval-ready full legal authority.

Run the authority data-product path in a networked environment with an external data root:

```bash
python scripts/ingest-maine-authority.py --data-root <external-data-root>
python scripts/audit-authority-build.py --data-root <external-data-root>
python scripts/build-parsed-authority-store.py --data-root <external-data-root>
python scripts/audit-parsed-authority-store.py --data-root <external-data-root>
python scripts/build-authority-followup-targets.py --data-root <external-data-root>
python scripts/ingest-maine-authority.py --data-root <external-data-root> --target-catalog <external-data-root>/official_authority_store/derived_authority_targets.json
python scripts/build-parsed-authority-store.py --data-root <external-data-root>
python scripts/audit-parsed-authority-store.py --data-root <external-data-root> --require-direct-authority
python scripts/build-source-update-report.py --data-root <external-data-root>
```

Or run the hardened one-command external authority pipeline, which records each required and optional step in one evidence JSON:

```bash
python scripts/run-authority-data-product.py --data-root <external-data-root> --strict-content-type
python scripts/run-authority-data-product.py --data-root <external-data-root> --strict-content-type --ingest-followup-targets --require-direct-authority
python scripts/run-authority-data-product.py --data-root <external-data-root> --strict-content-type --ingest-followup-targets --require-direct-authority --require-retrieval-smoke --require-gold-eval-pack --require-release-metrics
```

Useful preflight commands before touching the network:

```bash
python scripts/ingest-maine-authority.py --data-root <external-data-root> --dry-run
python scripts/run-authority-data-product.py --data-root <external-data-root> --plan-only
python scripts/run-authority-data-product.py --data-root <external-data-root> --plan-only --require-direct-authority

Gold eval and release metrics gates can be run independently:

```bash
python scripts/audit-gold-eval-pack.py --eval-root <external-eval-root> --require-ready
python scripts/run-release-metrics-evidence.py --eval-root <external-eval-root> --output <external-eval-root>/release_metrics_evidence.json --require-ready
```

These flags intentionally fail closed until real attorney-reviewed JSONL rows and task-specific measured metrics exist. Annotation queues and seed rows do not count as GA evidence.
python scripts/build-authority-followup-targets.py --data-root <external-data-root> --no-write
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
- The retrieval index audit blocks missing, empty, in-repo, or internally inconsistent index artifacts before retrieval smoke metrics are accepted.

Run the authority/retrieval data-product path in a networked environment with an external data root:

```bash
python scripts/ingest-maine-authority.py --data-root <external-data-root>
python scripts/audit-authority-build.py --data-root <external-data-root>
python scripts/build-parsed-authority-store.py --data-root <external-data-root>
python scripts/audit-parsed-authority-store.py --data-root <external-data-root>
python scripts/build-authority-followup-targets.py --data-root <external-data-root>
python scripts/ingest-maine-authority.py --data-root <external-data-root> --target-catalog <external-data-root>/official_authority_store/derived_authority_targets.json
python scripts/build-parsed-authority-store.py --data-root <external-data-root>
python scripts/audit-parsed-authority-store.py --data-root <external-data-root> --require-direct-authority
python scripts/build-source-update-report.py --data-root <external-data-root>
python scripts/build-authority-layer.py --data-root <external-data-root>
python scripts/build-retrieval-indexes.py --data-root <external-data-root>
python scripts/audit-retrieval-indexes.py --data-root <external-data-root> --require-direct-lookups
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

## Full corpus and GA legal-data readiness

The v1 source tree now includes a full-corpus registry for the maintained legal
data product this project needs. It covers Maine statutes, non-legislature court
authority, forms, Law Court opinions, professional-conduct materials, judicial
conduct, eCourts, and a federal District of Maine lane for intake, service,
CM/ECF, Local Rules, pro se forms, emergency relief, and jurisdiction blockers.

The live corpus belongs outside this repository:

```powershell
cd D:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\START_LOCAL_TEST.ps1 -SkipTests
mfl corpus requirements
mfl corpus build-manifest --data-root D:\dev\ME_FM_LLM_data
mfl corpus fetch-live --allow-live --data-root D:\dev\ME_FM_LLM_data
mfl corpus normalize --data-root D:\dev\ME_FM_LLM_data
mfl corpus parse --data-root D:\dev\ME_FM_LLM_data
mfl corpus build-indexes --data-root D:\dev\ME_FM_LLM_data
mfl corpus audit --data-root D:\dev\ME_FM_LLM_data
```

See `docs/full_corpus_requirements.md` and
`docs/enterprise_ga_release_plan.md`. The code can build the external corpus
scaffold and fetch official raw sources, but enterprise GA legal-data readiness
remains blocked until the full parse/index pipeline and attorney-reviewed eval
pack pass.


## Release artifact hygiene

Generated evidence JSON, SBOMs, release locks, smoke reports, official authority stores, parsed stores, retrieval indexes, model files, and matter data must not live at the repository root or be packaged as source. Use explicit output paths or the external data/evidence root for current run evidence. Historical JSON under `docs/sample-evidence/` is sample-only and does not prove production legal GA.

Before creating a public review ZIP, run:

```bash
python scripts/clean-local-artifacts.py --repo-root .
python scripts/audit-release-artifacts.py --repo-root . --require-ready
python scripts/doctor-local-repo.py --repo-root . --json
```

### Try these local questions

After starting `http://127.0.0.1:8000/`, test the source-backed chat with:

```text
What are Maine's best-interest factors under 19-A M.R.S. § 1653?
What Maine sources should I check for parental rights and responsibilities?
What should I review before drafting a child support checklist?
```

The browser workbench now includes answer style controls, optional context, copyable answers, grounded/failure badges, and source cards. The bundled fixture contains a short source-backed excerpt of **19-A M.R.S. § 1653(3)** so the offline demo can answer the best-interest-factor question without model memory. Always verify against the current official statute before relying on the answer.


## v1.81 chat prompt packs and source drilldown

The browser workbench now includes role-specific starter prompt packs for parents, lawyers/advocates, caregivers, counselors, and therapists. The new `questions_to_ask` answer style separates lawyer/reviewer questions from court-clerk logistics questions. Source cards now include an inspect action, and transcript export includes a JSON option with payload metadata and source cards.

New starter examples include:

- What should I ask a lawyer before filing a family case?
- What can I ask the court clerk about my family case?
- What if I cannot afford family court filing fees?
- How do I serve family court papers in Maine?
- What if we agree on a parenting plan?
- What should I know if a GAL is involved?
- A client asked me what to file in family court. What can I say?
- A child resists contact with a parent. What should a therapist do?

All outputs remain review-required and not filing-ready. No attorney review, legal signoff, real-matter pilot, production GA, or filing-ready status is claimed.

## v1.79 chat library expansion

The browser workbench now includes a larger starter-question library for parents, lawyers/advocates, caregivers, counselors, and therapists. Use the audience selector and the question-library search box to find starter questions such as:

- I was served with family court papers. What should I do first?
- How do I organize evidence for family court?
- Can my child choose which parent to live with?
- What jurisdiction issues should I flag in a Maine custody matter?
- Should I write a court letter for a parent?
- Can therapy records be used in family court?

The local `/ask` endpoint now returns structured JSON recovery payloads for empty questions and internal workbench exceptions so the browser UI should show a usable recovery message instead of crashing on a plain `Internal Server Error` response.


## v1.82 chat missing-information and reviewer handoff

The local chat workbench now includes a missing-information answer style, a reviewer handoff panel, JSON transcript handoff metadata, and `/api/missing-information-prompts`. The deterministic chat library now contains 104 source-backed starter items and remains review-required, not legal advice, and not filing-ready.


## Universal full-case corpus builder

This repository now includes a reusable local-first corpus builder for private forensic masters, external legal-matter releases, and role-specific review packages.
