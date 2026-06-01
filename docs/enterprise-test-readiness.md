# Enterprise test readiness

This repository is ready for **local enterprise testing** when `scripts/run-test-readiness.py` passes. That means the source tree, tests, public-source hygiene, release lockfile, supply-chain summary, enterprise preflight, and offline fixture wiring are runnable.

It does **not** mean the product is ready for legal production use. Production legal readiness remains blocked until real external official Maine authority, parsed stores, retrieval indexes, attorney-reviewed gold evals, measured metrics, pilot/security evidence, and owner signoffs replace fixture evidence.

## Windows path

Target repo:

```powershell
C:\dev\ME_FM_LLM
```

External data root:

```powershell
C:\dev\ME_FM_LLM_data
```

## Source-only readiness test

```powershell
cd C:\dev\ME_FM_LLM
powershell -ExecutionPolicy Bypass -File .\scripts\run-test-readiness.ps1 `
  -RepoRoot C:\dev\ME_FM_LLM `
  -DataRoot C:\dev\ME_FM_LLM_data
```

Expected result: `local_test_readiness_report.json` with `status: pass` and `ready_to_test_locally: true`.

## Full quality pass

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-test-readiness.ps1 `
  -RepoRoot C:\dev\ME_FM_LLM `
  -DataRoot C:\dev\ME_FM_LLM_data `
  -IncludeQualityChecks `
  -TimeoutSeconds 600
```

## Networked legal-data run

After source-only readiness passes, run the networked external-data path:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\collect-enterprise-resources.ps1 `
  -RepoRoot C:\dev\ME_FM_LLM `
  -DataRoot C:\dev\ME_FM_LLM_data

py -3.11 scripts\audit-enterprise-resource-collection.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\ingest-maine-authority.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\audit-authority-build.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\build-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\build-authority-layer.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\build-retrieval-indexes.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\audit-enterprise-readiness.py --data-root C:\dev\ME_FM_LLM_data --eval-root C:\dev\ME_FM_LLM_data\eval_store
```

The external data root must never be committed to the public source repository.
