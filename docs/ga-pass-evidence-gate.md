# GA pass evidence gate

The formal GA roadmap count must not drop just because repo scaffolding, fixture evidence, or harnesses exist. `scripts/audit-ga-pass-evidence.py` checks the tracker in `configs/maine_true_ga_pass_tracker.json` and validates every pass marked complete against machine-checkable requirements in `configs/maine_ga_pass_evidence_requirements.json`.

Internal conversation pilot-readiness Passes 47A-47H are audited separately. They live in `configs/maine_internal_conversation_passes.json` and emit `docs/external-evidence/pass47a_47h_conversation_pilot_readiness_summary.json`, but they do not reduce the true GA count and they cannot satisfy Passes 48-51.

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

The conversation pilot-readiness summary is intentionally boundary-heavy:

- `does_not_reduce_true_ga_count` must remain `true`
- `attorney_reviewed`, `legal_signoff`, `security_signoff`, `product_signoff`, `ops_signoff`, `pilot_signoff`, `ga_release_candidate_complete`, and `ga_shipped` must remain `false` unless real external evidence exists
- Passes 48-51 stay open until external attorney sandbox, real-matter pilot, release-candidate, and shipment evidence are attached
