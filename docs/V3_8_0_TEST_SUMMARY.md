# Maine Family Law LLM v3.8.0 Test Summary

## Collection

- Tests collected: 676
- New v3.8 three-pass regression tests: 9

## Completed validation

- Three-pass hardening plus prior v3.3-v3.5 conversation/security regressions: passed.
- Claim-support, response-contract, conversation API, model-governance/injection, security-governance, and private-data scanner suite: 58 passed.
- New deterministic source builder reproducibility, exclusion, embedded-manifest, FOCAF allowance, and arbitrary-PDF rejection checks: passed.
- JavaScript syntax: passed.
- Python compilation of changed modules: passed.
- Store-compatible source version target: 3.8.0.0.

## Full-suite limitation

The repository contains several intentionally expensive evidence and full-GA tests. A single monolithic run exceeded this execution environment's command ceiling. Completed deterministic groups showed no assertion failures, but this report does not claim that all 676 tests completed in one uninterrupted invocation.

## Required Windows validation not run

- Signed MSIX build
- Windows App Certification Kit
- Windows PowerShell parser test

Those require the Windows release environment.
