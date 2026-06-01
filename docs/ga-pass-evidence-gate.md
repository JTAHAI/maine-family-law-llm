# GA pass evidence gate

The formal GA roadmap count must not drop just because repo scaffolding, fixture evidence, or harnesses exist. `scripts/audit-ga-pass-evidence.py` checks the tracker in `configs/maine_true_ga_pass_tracker.json` and validates every pass marked complete against machine-checkable requirements in `configs/maine_ga_pass_evidence_requirements.json`.

Normal public-repo state is expected to pass with zero completed true-GA passes:

```powershell
py -3.11 scripts\audit-ga-pass-evidence.py
```

When a true pass is marked complete, run the audit with external roots:

```powershell
py -3.11 scripts\audit-ga-pass-evidence.py `
  --data-root D:\dev\ME_FM_LLM_data `
  --eval-root D:\dev\ME_FM_LLM_eval `
  --security-root D:\dev\ME_FM_LLM_security_evidence `
  --pilot-root D:\dev\ME_FM_LLM_pilot_evidence
```

Required evidence must live outside the source repository unless a pass is explicitly repo-completion work such as API/UI contract completion. `docs/sample-evidence/` is demonstration evidence only and does not count toward true GA pass completion.
