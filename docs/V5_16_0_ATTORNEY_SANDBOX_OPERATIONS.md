# v5.16.0 Attorney Sandbox Operations

v5.16.0 turns the existing fail-closed attorney-sandbox controls into a bounded operational workflow for Pass 48. It still does not verify attorney identity, accept private matters, create attorney signoff, or close the Pass 48 launch gate by itself.

## Operational workflow

The external pilot root now supports two independent hash-chained ledgers:

- `attorney-sandbox-ledger.jsonl` for participant eligibility, synthetic/public sessions, and feedback;
- `attorney-sandbox-operations-ledger.jsonl` for programs, cohorts, assignments, structured reviews, session completion, feedback triage, eval-candidate exports, and external attestation references.

The workbench can:

1. Create a public/synthetic review program from the bundled attorney review question library.
2. Bind the question queue to a deterministic SHA-256 manifest.
3. Form a cohort only from participants already recorded as eligible in the external sandbox ledger.
4. Create bounded assignments and sessions with explicit data classification.
5. Record structured review dispositions, five review ratings, finding codes, response-artifact hashes, verifier-report hashes, and sanitized comments.
6. Refuse session completion until every assigned question has a structured review.
7. Route review findings into a separate eval-candidate generation that remains `needs_attorney_review`, is never counted as gold automatically, and prohibits private training use.
8. Triage high and critical feedback through controlled status transitions, with remediation/retest hashes required before closure.
9. Record hashes of external identity-audit and program-signoff evidence without claiming the application verified the underlying evidence.
10. Build and verify an immutable JSON, HTML, receipt, and artifact-manifest evidence packet.

## Exit readiness

The operational status remains blocked until the configured minimums are met. The default policy requires:

- two eligible reviewers;
- two completed review sessions;
- twelve completed structured reviews;
- complete coverage of every assigned question;
- no unresolved high/critical feedback blocker;
- no unsafe-review blocker;
- an external identity-audit evidence hash;
- an external program-signoff evidence hash.

Even after those conditions are met, the status is only `ready_for_external_pass48_gate`. The application always reports `pass48_complete: false`. The separate Pass 48–51 external launch-evidence gate must examine the actual evidence and signoff.

## Data boundary

Allowed data is limited to:

- synthetic scenarios;
- public official authority.

The workflow refuses real private matters, sealed or juvenile records, client-confidential material, email addresses, Social Security numbers, Windows absolute paths, and private-training use. Review artifacts are referenced by SHA-256 rather than copied into the operations ledger.

## API

```text
GET  /api/attorney-sandbox-operations/status
POST /api/attorney-sandbox-operations/programs
POST /api/attorney-sandbox-operations/cohorts
POST /api/attorney-sandbox-operations/assignments
POST /api/attorney-sandbox-operations/reviews
POST /api/attorney-sandbox-operations/sessions/complete
POST /api/attorney-sandbox-operations/feedback/triage
POST /api/attorney-sandbox-operations/attestations
POST /api/attorney-sandbox-operations/eval/export
POST /api/attorney-sandbox-operations/evidence/build
GET  /api/attorney-sandbox-operations/artifacts/{token}
```

Artifact downloads use short-lived opaque capabilities and are independently reverified before delivery.

## CLI

```powershell
python .\scripts\run-v516-attorney-sandbox-operations.py `
  --pilot-root D:\MFL_Pilot\Pass48 `
  status

python .\scripts\run-v516-attorney-sandbox-operations.py `
  --pilot-root D:\MFL_Pilot\Pass48 `
  create-program --program-id pass48-attorney-sandbox --max-questions 48

python .\scripts\run-v516-attorney-sandbox-operations.py `
  --pilot-root D:\MFL_Pilot\Pass48 `
  build-evidence
```

The pilot root must remain outside the source repository.
