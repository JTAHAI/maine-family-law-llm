# Maine Family Law LLM v3.4.0 Test Summary

## Release identity

- Product version: **3.4.0**
- Microsoft Store package target: **3.4.0.0**
- UI identity: **3.4.0-family-justice-chat-b12**
- Structured answer contract: **family_answer_v3_4**

## Validation results

| Gate | Result |
|---|---|
| Collected automated suite | **658 tests** |
| Deterministic batched execution | **657 passed, 1 skipped** |
| New v3.4 regression module | **9 passed** |
| Extracted source-ZIP release smoke | **61 passed** |
| Focused chat/intake/OCR/Store/UI regression set | **88 passed** |
| Focused version/Store regression set | **59 passed** |
| Python compilation | **Passed** |
| JavaScript syntax (`node --check`) | **Passed** |
| Desktop/Tk coverage | **Passed under Xvfb** |
| Local repository doctor | **Passed; safe_to_push=true** |
| Release artifact audit | **Passed; zero blockers; safe_to_package=true** |
| Public-source readiness audit | **Passed; zero findings** |
| FOCAF printable asset audit | **Passed; 103/103 resolved; zero missing; zero hash mismatches** |
| Package privacy/runtime hygiene | **Passed** |

The single skipped test is the existing PowerShell parser check because PowerShell is unavailable on this Linux runner. The suite was executed in deterministic test-file batches because the environment imposes a per-command ceiling; every collected test was accounted for. The four long-running full-GA workbench cases were also run individually and passed.

## New regression coverage

The v3.4-specific tests prove:

- mixed source sets can be filtered by legal-authority or private-record lane;
- arbitrary ordinal and last-card selection work without rerunning retrieval;
- a source-free latest answer prevents stale-card reopening;
- short follow-ups reuse only a sanitized structured routing anchor;
- raw prior questions, dates, docket numbers, courts, and safety flags are not retained in the continuity anchor;
- current safety language is recomputed and overrides inherited routing;
- instruction-like private-record text is preserved but marked untrusted;
- prompt override language is reported without changing review requirements;
- inferred-year and relative-date normalization disclose their basis;
- browser source follow-ups use server logic and the handoff renderer has a local structured-answer value;
- empty source results clear browser state; and
- public query result counts are bounded.

## Scope limits

This is a clean source-repository release. The Linux environment cannot rebuild or sign the Windows MSIX and cannot run WACK. The Store-safe package target is **3.4.0.0**. Production legal GA remains false until real external official-authority builds, attorney-reviewed gold evaluations, measured release thresholds, security and pilot evidence, and required owner signoffs are complete.

## Remaining milestone count

**33 Enterprise GA plan passes remain (Pass 19 through Pass 51).** Existing code and tests do not substitute for the real external evidence, attorney review, operational security validation, controlled pilots, and signoffs required by those passes.
