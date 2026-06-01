# Operator Test Battery

This source tree includes a one-command operator acceptance battery for local testing after a reboot, before handing the project to another operator, or before staging a public GitHub push.

Windows command:

```powershell
cd C:\dev\ME_FM_LLM
python scripts\run-operator-test-battery.py --data-root C:\dev\ME_FM_LLM_data
```

The battery checks source hygiene, external data-root separation, reboot recovery, public repo readiness, enterprise acceptance, and supply-chain metadata. A pass means the source package is ready for local fixture/source testing. It is not legal production readiness.

Production legal readiness remains blocked until a networked operator attaches real official Maine authority manifests, parsed authority stores, retrieval index manifests, attorney-reviewed gold eval manifests, measured release metrics, pilot/security evidence, and owner signoffs.
