# Operator Handoff Bundle

Build this bundle before handing the repo to another operator, after a reboot, or before public GitHub staging:

```powershell
cd C:\dev\ME_FM_LLM
python scripts\build-operator-handoff-bundle.py --data-root C:\dev\ME_FM_LLM_data
```

The output fingerprints the operator scripts, summarizes source-tree readiness, embeds the local operator battery, and shows the networked-source gate status. It does not certify legal production readiness unless the external data root contains real non-fixture authority/eval/metrics evidence.
