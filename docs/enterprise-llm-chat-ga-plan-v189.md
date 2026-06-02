# v1.89 enterprise LLM + chat plan

Status: planning and engineering roadmap only. This repo still does not claim attorney review, legal signoff, real-matter pilot, production GA, or filing-ready output.

## Pass count from v1.89

There are two counts because the project has two tracks:

1. **Formal enterprise GA count:** 33 passes remain, matching the existing Pass 19 through Pass 51 enterprise GA plan. Those passes start with live official-source ingestion and end with GA shipped.
2. **Practical LLM + chat count from this ZIP:** 36 passes remain. This is the 33 formal enterprise GA passes plus 3 additional chat/LLM language-quality passes needed to make the public chat experience broad, deterministic, and usable before or alongside live-source ingestion.

The v1.89 pass completed one chat/LLM language hardening pass. It did not reduce the formal GA count because it did not execute live official-source ingestion, attorney-reviewed gold promotion, pilot evidence, security signoff, or legal signoff.

## Completed in v1.89

- Expanded deterministic chat-language coverage for deadline/service, eCourts/record access, parentage, child-support arrears, PFA hearing prep, appellate finality, Rule 52/findings preservation, stay pending appeal, interlocutory/nonfinal order appeal, magistrate/order objection triage, counselor hearing-support boundaries, and therapist record-release disputes.
- Added wrong-match routing overrides for these higher-risk phrases.
- Added fixture text so the offline workbench still requires source cards and does not answer from model memory.
- Added regression tests for every new wrong-match class.
- Added this enterprise LLM + chat plan.

## 36-pass practical path from here

| Block | Passes | Goal | Exit gate |
|---|---:|---|---|
| A. Chat language completeness | 3 | Finish deterministic coverage for public, lawyer, caregiver, counselor, therapist, appellate, forms, service, deadlines, PFA, GAL, support, and court-routing language. | Wrong-match regression suite passes for every class; no answer without source cards. |
| B. Live official-source data product | 7 | Execute official Maine source ingestion, parsing, freshness, citation resolver, authority graph, retrieval indexes, retrieval tuning, and failure triage. | External data root contains versioned source manifests, parsed authority, retrieval indexes, and retrieval metrics. |
| C. Maine legal answer intelligence | 6 | Build source-backed answer planner, appellate intelligence, forms intelligence, support/PFA/GAL/caregiver routing, stale-law/jurisdiction warnings, and claim-support checks. | Every legal claim maps to source cards or is refused/flagged. |
| D. Gold eval and attorney review moat | 4 | Build annotation queue, attorney-reviewed gold data, eval runner, and release metrics evidence. | Synthetic/seed rows cannot count as GA gold; missing attorney review blocks GA. |
| E. Secure matter workflows | 4 | Add matter ingestion, PII/privacy classification, timeline/evidence map, missing-record checklist, and audit-safe storage outside repo. | Matter files never enter repo or shared training by default; every fact maps to evidence/span. |
| F. Drafting and filing gates | 4 | Build review-required drafting workspace, citation/quote reports, unsupported-claim report, proposed findings review, and hardened filing-ready gate. | Filing-ready false-pass rate is zero on test set; human review remains mandatory. |
| G. Product API/UI completion | 3 | Finish standalone API and web UI source cards, source drilldown, authority matrix, evidence map, draft workspace, reports, and reviewer queue. | Contract tests, UI route tests, and source-card drilldown pass. |
| H. Model governance and injection defense | 2 | Add model registry/admission, prompt/document injection tests, tool-context isolation, and role boundaries for every model. | Generator cannot self-certify legal correctness; injection red-team passes. |
| I. Enterprise security, ops, and release | 3 | Add auth/RBAC, audit logs, retention/deletion, observability, backup/restore, red-team, attorney sandbox pilot, release candidate, and GA package gates. | Security, legal, product, and ops signoff evidence exists before GA. |

Total remaining practical passes after v1.89: **36**.

## Next three recommended passes

1. **v1.90 chat wrong-match closure:** Add another 50 to 75 real-world phrasings, especially ambiguous parent questions that currently risk matching a broad topic. Include regressions before broadening answers.
2. **v1.91 answer planner / source-scope router:** Add a deterministic answer planner that classifies whether a question needs statute, rule, form, appellate, safety/PFA, DHHS/support, federal/tribal/out-of-state, or professional-boundary sources before matching a library item.
3. **v1.92 live-ingestion preflight and external-data runbook:** Move from fixture-backed chat to the formal Pass 19 workstream: live official-source ingestion into an external data root, source manifest audit, parser audit, and no-repo-data doctor gates.

## Non-negotiable guardrails

- Official Maine law and court materials outrank model memory, snippets, and summaries.
- No current-law claim unless source freshness is known or the warning is visible.
- No filing-ready output unless authority, citations, quote spans, facts, source scope, and human review are verified.
- Private matter data, corpora, vector stores, OCR caches, runtime DBs, model weights, and generated work product stay outside the source repo.
- Chat answers remain legal information, not legal advice.
