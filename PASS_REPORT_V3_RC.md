# v3.0.0 Release-Candidate Pass Report

## Package evidence

- Artifact: `MaineFamilyLawLLM_x64.msix`
- Package version: `3.0.0.5`
- SHA-256: `2EB0EFFD71986624906F87B3866EC06285B9E7A402AAE9DEB62AAF8F74A2650A`
- Package identity: `TAHAIWebServices.MaineFamilyLawLLM`
- Package publisher: `CN=D75EE668-B409-45ED-87E5-E37AA5FE3868`
- Display name: `Maine Family Law LLM`
- Publisher display name: `TAHAI Web Services`

## Evidence-backed checks

- Complete Python suite: 623 tests passed.
- Focused release checks: 44 passed.
- Python compilation: passed.
- Browser JavaScript syntax check: passed.
- `git diff --check`: passed.
- Local repository doctor: passed after generated-artifact cleanup.
- MSIX runtime smoke: passed using a fictional sample case.
- Private-data audit: passed with no blocked paths, blocked files, or absolute-path hits in the package.
- Responsive live UI verification: passed at desktop and mobile dimensions with no horizontal overflow. The combined lane rendered one structured answer without nested duplicate sections.

## WACK

`scripts/run-wack.ps1` was invoked against the final MSIX. Windows reported that elevation is required, so WACK was not run in this session. This is a known release-candidate limitation and must be completed before Store submission.

## Safety boundary

The packaged application and source release contain no personal corpus, raw Gmail/MBOX/PST/OST material, case-specific evidence, runtime databases, model weights, or local virtual environments.
