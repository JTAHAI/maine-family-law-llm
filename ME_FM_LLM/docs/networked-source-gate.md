# Networked Source Gate

This gate is the line between local fixture/source testing and real legal validation.

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

A pass means the external data root has non-fixture official-source evidence, parsed authority records, retrieval manifests, attorney-reviewed eval evidence, and release metrics. A fail is expected before live collection and attorney review are complete.
