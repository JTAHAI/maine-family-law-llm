# Contributing

Contributions should preserve the source-only boundary: no legal corpora, no private matter data, no model weights, no vector stores, and no generated runtime databases.

Before opening a pull request, run:

```bash
python -m pytest -q
python scripts/run-quality-checks.py
python scripts/build-enterprise-acceptance-evidence.py enterprise_acceptance_evidence.json
```

For Windows local testing under `C:\dev\ME_FM_LLM`, use `scripts/run-final-local-acceptance.ps1` after staging the external data root at `C:\dev\ME_FM_LLM_data`.
