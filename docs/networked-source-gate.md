# Networked Source Gate

This gate checks metadata prerequisites for subsequent evidence validation. It
does not certify current law, model quality, attorney review, or release readiness.

Run it after collecting official resources into the external data root:

```powershell
cd C:\dev\ME_FM_LLM
python scripts\collect-enterprise-resources.py --project-root C:\dev\ME_FM_LLM --data-root C:\dev\ME_FM_LLM_data
python scripts\ingest-maine-authority.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-authority-layer.py --data-root C:\dev\ME_FM_LLM_data
python scripts\build-retrieval-indexes.py --data-root C:\dev\ME_FM_LLM_data
python scripts\run-networked-source-gate.py --data-root C:\dev\ME_FM_LLM_data
```

A pass means the external manifests declare the required source classes, parsed
counts, indexes, review counts, and metric names, with no recognized fixture
marker. Those declarations alone do not authenticate the underlying artifacts
or the people who reviewed them. `production_legal_ready` therefore remains
false even on a metadata pass. Current-source/hash verification, independently
reviewed evaluation evidence, and the separate production release gates remain
required. A unit-test fixture passing this gate is never legal-use evidence.
