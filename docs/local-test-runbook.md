# Local Test Runbook for `C:\dev\ME_FM_LLM`

Use this runbook before a public GitHub release or a networked enterprise-data build.

## Source-only smoke test

```powershell
cd C:\dev\ME_FM_LLM
python -m pip install -e ".[dev]"
pytest -q
python scripts/run-quality-checks.py
python scripts/run-enterprise-preflight.py --repo-root C:\dev\ME_FM_LLM --data-root C:\dev\ME_FM_LLM_data --output .\enterprise_preflight_report.json
python scripts/build-offline-validation-pack.py --data-root C:\dev\ME_FM_LLM_data --output .\offline_validation_pack_report.json
python scripts/prepare-public-github-release.py --project-root C:\dev\ME_FM_LLM --output .\public_release_readiness.json
```

## Networked resource collection test

```powershell
cd C:\dev\ME_FM_LLM
.\scripts\collect-enterprise-resources.ps1 -ProjectRoot C:\dev\ME_FM_LLM -DataRoot C:\dev\ME_FM_LLM_data
python scripts/audit-enterprise-resource-collection.py --project-root C:\dev\ME_FM_LLM --data-root C:\dev\ME_FM_LLM_data
python scripts/ingest-maine-authority.py --data-root C:\dev\ME_FM_LLM_data
python scripts/build-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
python scripts/build-authority-layer.py --data-root C:\dev\ME_FM_LLM_data
python scripts/build-retrieval-indexes.py --data-root C:\dev\ME_FM_LLM_data
python scripts/audit-enterprise-readiness.py --data-root C:\dev\ME_FM_LLM_data --eval-root C:\dev\ME_FM_LLM_data\eval_store
```

The offline validation pack is synthetic. It proves wiring only. It is not legal authority and does not satisfy production GA evidence.
