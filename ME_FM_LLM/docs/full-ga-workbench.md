# Full GA Workbench

This repo can be source-test-ready before it is legal-production-ready. The full GA workbench keeps that boundary explicit.

## Windows path

```powershell
cd C:\dev\ME_FM_LLM
python scripts\run-operator-test-battery.py --data-root C:\dev\ME_FM_LLM_data
python scripts\collect-enterprise-resources.py --project-root C:\dev\ME_FM_LLM --data-root C:\dev\ME_FM_LLM_data
python scripts\ingest-maine-authority.py --data-root C:\dev\ME_FM_LLM_data
python scripts\audit-authority-build.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
python scripts\audit-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-authority-layer.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-retrieval-indexes.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-gold-annotation-queue.py --manifest C:\dev\ME_FM_LLM_data\official_authority_store\source_manifest.json --output C:\dev\ME_FM_LLM_data\eval_store\gold_annotation_queue.jsonl
python scripts\audit-gold-eval-pack.py --eval-root C:\dev\ME_FM_LLM_data\eval_store
python scripts\run-networked-source-gate.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-full-ga-workbench.py --data-root C:\dev\ME_FM_LLM_data --allow-fail-report
python scripts\run-production-promotion-gate.py --data-root C:\dev\ME_FM_LLM_data
```

## What the report means

`full_ga_workbench_report.json` aggregates three layers:

1. source/local operator testing;
2. networked official-source evidence validation;
3. final production-promotion gate.

The report may say local testing is ready while production remains locked. That is expected until the external data root contains live official Maine authority, parsed stores, retrieval indexes, attorney-reviewed gold evals, measured release metrics, pilot/security evidence, rollback evidence, and owner signoffs.

Only `production_legal_ready: true` from the production-promotion phase allows a build to be described as production legal ready.
