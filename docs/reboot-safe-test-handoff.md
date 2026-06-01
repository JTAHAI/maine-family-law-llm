# Reboot-safe local test handoff

This repo is safe to resume after a workstation reboot when the source tree stays in `C:\dev\ME_FM_LLM` and all generated legal data/runtime artifacts stay outside the repo in `C:\dev\ME_FM_LLM_data`.

Run this immediately after reboot:

```powershell
cd C:\dev\ME_FM_LLM
py -3.11 scripts\run-reboot-safe-healthcheck.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\run-test-readiness.py --data-root C:\dev\ME_FM_LLM_data --skip-pytest
py -3.11 scripts\run-enterprise-preflight.py --data-root C:\dev\ME_FM_LLM_data
```

The health check verifies required scripts/configs, external data-root layout, write permissions, and the rule that the repo contains exactly one pass-log TXT file: `PASS_CHANGES.txt`.

After local source/fixture checks pass, run the networked collection/build path:

```powershell
py -3.11 scripts\collect-enterprise-resources.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\ingest-maine-authority.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\build-parsed-authority-store.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\build-retrieval-indexes.py --data-root C:\dev\ME_FM_LLM_data
py -3.11 scripts\audit-enterprise-readiness.py --data-root C:\dev\ME_FM_LLM_data --eval-root C:\dev\ME_FM_LLM_data\eval_store
```

Passing the reboot health check means the source tree is resumable and locally testable. It does not mean production legal readiness. Production remains blocked until live official authority, attorney-reviewed eval packs, measured metrics, pilot/security evidence, and owner signoffs replace fixture evidence.
