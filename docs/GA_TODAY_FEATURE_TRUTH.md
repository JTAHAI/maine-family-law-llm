# GA-today feature truth: slices 21–31

Audit timestamp: 2026-08-11T16:27:33.7764623Z

## Decision

No slice 21–31 feature is accepted for public or Store release today. All eleven are hidden and production-disabled. The backend implementations are substantive and their focused synthetic tests pass, but no feature completes the required chain through protected canonical API, complete shipped UI, exact-source drill-down, browser-level action, and installed frozen reachability.

The Store feature list generated from this audit is therefore empty for slices 21–31.

## Feature status

| ID | Feature | Service/API evidence | Production UI evidence | Frozen evidence | Status |
|---|---|---|---|---|---|
| 21 | Matter intake, posture, issue tree | Encrypted matter store; create, posture, issue tree, coverage, receipt tested | Partial hidden panel; no protected role/audit envelope or source drill-down | Installed 6.0.4 has no command entry | `hidden` |
| 22 | Operative order and supersession | Terms, graph, diff, candidate review, ledger tested | Partial hidden panel cannot perform the complete review workflow | Not reachable | `hidden` |
| 23 | Service, notice, deadlines, hearings | Source-bound event/rule and candidate calculation tested | Hidden panel cannot create a rule or deadline candidate | Not reachable | `hidden` |
| 24 | Docket/MRECS reconciliation | Import, local-record comparison, reconciliation tested | Hidden panel lacks local-record mapping and exact-source inspection | Not reachable | `hidden` |
| 25 | Discovery/disclosure | Requests, productions, gaps tested | Hidden panel lacks response/production mapping | Not reachable | `hidden` |
| 26 | Exhibit binder and provenance | Candidate, label review, derivative numbering, binder tested | Hidden panel only adds a candidate | Not reachable | `hidden` |
| 27 | Witness/statement comparison | Source-bound statements and comparison tested | Hidden panel cannot execute a usable two-statement comparison | Not reachable | `hidden` |
| 28 | Hearing preparation | Hearing, blockers, pack, notes tested | Hidden panel cannot assemble issue, authority, evidence, and missing proof | Not reachable | `hidden` |
| 29 | Appellate preservation and citations | Appeal, verifier, packet tested | Hidden panel cannot enter or verify citations/transcripts | Not reachable | `hidden` |
| 30 | UCCJEA/interstate review | Connections, proceedings, factors tested without conclusions | Hidden panel lacks dates/proceedings for meaningful conflict display | Not reachable | `hidden` |
| 31 | ICWA inquiry and notice review | Inquiry, notice, completeness tested without status inference | Hidden panel cannot perform notice/response review or exact-source inspection | Not reachable | `hidden` |

## Production surface truth

- `src/maine_family_law_llm/ui` is the authoritative production frontend. PyInstaller bundles it, and the loopback API serves it.
- `maine_family_law_llm/ui` is a byte-identical source mirror after this audit, but it is not the authoritative packaging input.
- `app/web` is a development/design-contract TSX tree. It is not built or shipped and was not counted.
- The installed application is version 6.0.4.0. Its JavaScript hash differs from current source and contains none of the slice 21–31 command markers.

## Why focused tests were not acceptance

The 30 focused tests prove useful backend behavior: encrypted local storage, source-safe IDs, review-required outputs, non-determination safeguards, receipts, and selected matter-scope checks. They do not prove the full desktop journey. In particular:

- the local slice routes do not attach the enterprise role dependency or server-owned audit envelope;
- slice panels display source IDs as text instead of opening the exact protected record/page;
- most panels expose only a fraction of their backend workflow;
- no browser-level synthetic end-to-end journey was present;
- the installed frozen application does not contain the features.

## Release-scope repairs

1. Removed all eleven production command-palette navigation entries from both UI copies.
2. Added a production dispatcher gate returning `404 feature_not_in_release_scope` for every slice route family unless an explicit development-only environment override is set.
3. Published an empty accepted/Store feature list and the eleven experimental-disabled feature IDs through runtime capabilities.
4. Corrected the production UI manifest so retained hidden overlays and dormant API strings cannot be counted as public workspace claims.
5. Updated focused tests to verify hidden navigation while continuing to test retained backend behavior.

## Tests

- Focused slice tests: **30 passed**.
- Release-scope acceptance tests: **3 passed**.
- Combined audit suite: **33 passed**.
- Python compilation: passed.
- Production and mirror JavaScript syntax: passed.
- Frozen reachability: failed for acceptance; the installed 6.0.4 package has no slice command markers.

## Remaining blockers before any feature can be accepted

1. Enforce authenticated roles and server-owned audit identity on every canonical route.
2. Use matter-scoped capability tokens to open exact source records/pages from every slice result.
3. Complete the meaningful workflow in the actual production workbench.
4. Add fictional-matter browser end-to-end coverage, including privacy and cross-matter denial.
5. Build, install, and verify a frozen package containing the exact accepted assets and routes.
6. Change the feature’s truth status to `verified_end_to_end` before adding it to Store copy.

Backend code and encrypted data formats were preserved. No slices 32–44 were added.
