# Enterprise Acceptance and Public GitHub Publish Runbook

This repository can be staged publicly as source code only after public-readiness, supply-chain, release-lock, and enterprise-acceptance checks pass.

## Local Windows target

Expected source checkout:

```powershell
C:\dev\ME_FM_LLM
```

Expected external data root:

```powershell
C:\dev\ME_FM_LLM_data
```

The external data root is where official Maine authority snapshots, parsed stores, retrieval indexes, attorney-reviewed evals, matter files, and runtime evidence belong. Those artifacts are not committed to the public source repository.

## Final local acceptance commands

```powershell
cd C:\dev\ME_FM_LLM
python -m pytest -q
python scripts\run-quality-checks.py
python scripts\build-release-lockfile.py source_release_lock.json
python scripts\audit-release-lockfile.py source_release_lock.json
python scripts\build-enterprise-acceptance-evidence.py enterprise_acceptance_evidence.json
```

Or run:

```powershell
scripts\run-final-local-acceptance.ps1 -RepoRoot C:\dev\ME_FM_LLM -DataRoot C:\dev\ME_FM_LLM_data
```

## Publish rule

Public GitHub source readiness is not production legal readiness. The production gate stays blocked until the external official-authority data product, parsed authority store, retrieval indexes, attorney-reviewed gold evals, measured release metrics, security and pilot evidence, and owner signoffs replace fixtures.
