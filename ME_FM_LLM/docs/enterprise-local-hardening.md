# Enterprise local hardening and official-resource collection

This repo is source code only. Enterprise legal data, authority snapshots, parsed stores, retrieval indexes, gold-eval stores, OCR caches, model weights, runtime databases, and matter files must stay outside the repository.

## Windows-first local path

Use this layout:

```powershell
C:\dev\ME_FM_LLM       # source repository
C:\dev\ME_FM_LLM_data  # external legal data/runtime/evidence root; never commit
```

## One-command hardening run

From PowerShell:

```powershell
cd C:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\scripts\harden-enterprise-local.ps1 `
  -RepoRoot C:\dev\ME_FM_LLM `
  -DataRoot C:\dev\ME_FM_LLM_data
```

For a no-network planning run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\harden-enterprise-local.ps1 `
  -RepoRoot C:\dev\ME_FM_LLM `
  -DataRoot C:\dev\ME_FM_LLM_data `
  -DryRun
```

## Resource collector

The enterprise resource collector reads `configs/maine_enterprise_resource_catalog.json` and writes:

```text
C:\dev\ME_FM_LLM_data\research_resources\resource_manifest.json
C:\dev\ME_FM_LLM_data\research_resources\failed_resources.json
C:\dev\ME_FM_LLM_data\research_resources\collection_report.json
C:\dev\ME_FM_LLM_data\research_resources\snapshots\...
```

Run only collection:

```powershell
python .\scripts\collect-enterprise-resources.py --data-root C:\dev\ME_FM_LLM_data
python .\scripts\audit-enterprise-resource-collection.py --data-root C:\dev\ME_FM_LLM_data
```

Smoke run with only a few targets:

```powershell
python .\scripts\collect-enterprise-resources.py --data-root C:\dev\ME_FM_LLM_data --max-resources 5
```

## What the catalog covers

The catalog includes official or official-adjacent targets for:

- Maine Revised Statutes title list, title indexes, and title PDFs for family-law-relevant titles.
- Maine Judicial Branch court rules, civil/family rules, MRECS, administrative orders, and the Rule 120/Rule 52 family findings standing order.
- Maine Judicial Branch forms index, public forms portal, family packets, child-support affidavit, and child-support table resources.
- Maine Judicial Branch family-law guidance pages.
- Maine Law Court published-opinion indexes for current and recent years.
- Federal family-law-adjacent authority: ICWA, bankruptcy, bankruptcy rules, federal child-support statutes, and current eCFR Title 45 child-support regulations.

## Enterprise readiness chain

After collection, run the existing authority/data/eval chain:

```powershell
python .\scripts\ingest-maine-authority.py --data-root C:\dev\ME_FM_LLM_data
python .\scripts\build-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
python .\scripts\build-authority-layer.py --data-root C:\dev\ME_FM_LLM_data
python .\scripts\build-retrieval-indexes.py --data-root C:\dev\ME_FM_LLM_data
python .\scripts\audit-enterprise-readiness.py --data-root C:\dev\ME_FM_LLM_data --eval-root C:\dev\ME_FM_LLM_data\eval_store
```

A release is not production-ready merely because these scripts exist. It becomes production-ready only when the external manifests contain real official source snapshots, parsed authority stores, retrieval indexes, attorney-reviewed gold evals, real metrics, pilot/security evidence, and owner signoffs.
