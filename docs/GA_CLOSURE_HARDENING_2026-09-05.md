# GA closure hardening — 2026-09-05

This is an engineering progress report, not a GA certificate. Product/package
versions remain 8.0.1 / 8.0.1.0. No MSIX was built, signed, installed, submitted,
or published in this pass. Existing source changes and model weights were kept.

## Implemented

- A common ASGI boundary now checks loopback/Host/Origin, ambiguous framing,
  bounded streamed request bodies, body timeout, rate limits, safe response
  headers, and a consistent server-generated audit ID before either API target.
  Streaming responses retain the real disconnect channel after body replay.
- Capability approvals use a random process key when no operator secret is
  supplied. Public project paths are no longer key material. Tokens from a prior
  process, malformed objects/signatures/times, and consumed approvals fail closed.
- The unused generic `/api/runtime/jobs` family is closed in production, including
  list, create, read, cancel, and recovery. Its backing code/data were not deleted.
  Actual feature-specific, matter-scoped job APIs remain unchanged. Reopening the
  generic API requires authenticated ownership and protected storage, not a flag.
- `/api/citations/verify`, `/api/research`, and `/api/query` are development
  contracts only. They cannot expose demo indexes or caller-supplied authority
  through the production gateway. Production route/OpenAPI inventories omit them.
  The shipped workbench does not call these legacy paths.
  Dispatch, OpenAPI and contract auditing now share this exclusion policy. The
  auditor reports disabled endpoints separately and fails if they reappear. It
  also checks missing HTTP methods instead of silently excluding them. Historical
  inventory fixtures now include PATCH/DELETE and use the actual production scope.
- Evidence and Drafting share privacy-exclusion handling. Explicit reviewer/host
  spans protect unclassified values; malformed or stale annotations protect the
  entire source. Known sensitive labels support alternate separators. Context is
  masked before approval/transmission, offsets stay stable, and excerpt rendering
  rechecks exclusions. Original record content is not modified. Detection is not
  a claim to recognize all PII or to improve trained model understanding.
- The consulted specialist regression fixtures now have pinned hashes, exact case
  IDs and evaluator hashes checked before/after the runner. Evaluator processes
  have bounded output tails, timeouts, owned-process cleanup, and progress records.
  A timed-out/unclean evaluator stops further suite launches. These are consulted
  fictional regressions, not an independent blind holdout or attorney review.
  Standalone quality aggregation and retained-report revalidation now enforce the
  same pinned evaluator, fixture hashes, exact case order and complete suite set.
  Lowering a requested case minimum cannot omit a required suite. A plausible
  hash, a renamed/easier case, or an old success flag cannot establish this gate.
- The release ledger rejects malformed/ambiguous JSON, truthy-string flags and
  contradictory positive claims. Frozen loading uses the actual bundle root.
- Store CI installs test dependencies before collection, invokes one canonical
  unsigned build, excludes signing-key directories from uploads, and explicitly
  reports installation/offline/WACK as not evaluated. Install/WACK helpers require
  an exact candidate path. Uninstall has no default production identity. Production
  builds cannot silently create a development signer.
  Explicit development builds now select `MaineFamilyLawLLM.LocalQA` and a
  separate publisher instead of accidentally retaining the hydrated Store
  identity. Tests execute just that pure PowerShell identity block, not a build
  or certificate operation.
- The View menu now exposes `aria-checked`, supports arrow/Home/End/Escape keys,
  and returns focus after view selection. Unavailable authority produces source-
  setup guidance instead of promising immediately available legal research.
  Generic recovery no longer tells Store users to run a development script.
- A packaging test's leaked process environment was fixed after reproducing five
  subsequent chat failures. The failing order passes after full restoration;
  original failed evidence is retained instead of calling the issue flaky.
  Two expired-token fixtures were repaired to describe valid-but-expired tokens;
  malformed tokens remain rejected. No expiry or signature check was weakened.

## Verification boundaries

Evidence is under `dist/ga-closure/evidence/`; the complete automated run is under
`dist/ga-closure/full-regression/`. Its source-only snapshot is 35,709,712 bytes,
with tree SHA-256
`32bbecd4471a9e50c9a41fe2c6641a2e60f5329a7495afd1a3136f2b6654f5c9`.

- Initial focused boundary run: 153 passed.
- Expanded run: 178 tests, 173 passed and 5 order-dependent failures.
- Diagnostic isolated chat run: 30 passed.
- Repaired packaging→chat→startup-state run: 73 passed.
- Compilation: 1,308 Python files compiled in memory; no generated bytecode.
- Both mirrored workbench and component JavaScript bundles passed syntax checks.
- Changed package helpers passed PowerShell parsing; new/touched focused lint
  targets passed. This is not a repository-wide lint clean bill.
- First complete automated run: 2,611 tests; 2,567 passed, 22 failed, 22 skipped.
  Failures were two stale expiry fixtures and 20 contract assertions still
  requiring disabled authority demonstrations. Fixes and focused retests are
  retained separately. A fresh complete run of the repaired source is recorded
  in `dist/ga-closure/verification-final/summary.json`; the original failure
  summary is not overwritten or relabeled passing.
- Completed rerun: **2,622 tests; 2,599 passed, one failed, 22 skipped** in
  1,991.953 seconds. The sole failure was a test still expecting the production
  identity to be hardcoded in the build script. Its assertion now verifies the
  unchanged canonical identity config and script bindings. No application,
  packaging, configuration or UI code changed after this rerun's source snapshot.
- The complete affected batch then ran again: **249 tests; 248 passed, one
  skipped**, in 39.546 seconds. Four parametrized case IDs containing the old
  snapshot directory were rebound to the new snapshot; no cases were dropped.
  The initial failed selection attempt ran zero tests and is retained. See
  `dist/ga-closure/packaging-retest/rebound-summary.json`.
- Resolved unique coverage: **2,600 passed, 22 skipped, no unresolved automated
  failure**, from the completed rerun plus the whole affected-batch correction.
  This is **not** a single clean full-suite run. The raw full-run result remains
  `fail`; the composite coverage does not establish GA or a version-freeze gate.
  Full-rerun source SHA-256:
  `29f5982b95e33297ac143b1cd72819c1e63c8cc6ba523325a4acadc6ff44a078`.
  Test-only correction snapshot SHA-256:
  `7ad7939772e27b099eb7fc925ccb6fe5eba5e90b16750e63df0e6749e4a0b055`.
- Additional focused receipts: 34 qualification/QA-identity tests, 38 gateway/
  contract tests, 59 production-contract/quality tests, and 37 final route-audit
  tests passed. Counts overlap and must not be added as unique suite coverage.
- A direct, five-test inventory check passed four and failed one because its
  deliberate external-data fixture was placed inside the real source repo. The
  full runner uses a bounded source snapshot and sibling fixture root, preserving
  the production prohibition; no external drive folder or guard bypass was used.
- `pip check` passed. Fourteen project-defined offline dependency floors passed;
  this does not replace a current vulnerability or exact-package license audit.

The browser verification used the production UI assets through
`app.api.production:app`, but from source, with an isolated empty QA profile and
no admitted authority or specialist. The observed source-server title was
**Personal edition**, not an installed public Store shell. It verified defaults (Both and Child Impact
Lens on), keyboard view selection, checked states, focus return, the no-authority
message and the actual source-setup action. The observed 1265px viewport had no
horizontal overflow; no JavaScript console errors were observed. A screenshot
was inspected in the task. This was not a frozen/installed-app, 200% zoom,
screen-reader-user, positive legal-answer, or real-model-inference qualification.
The QA tab and its owned server were stopped; the user's personal tab was untouched.

## Still required before release claims

1. Finish per-feature action/API/UI/tier/artifact evidence reconciliation. The
   conservative ledger is implemented, but G01's full roadmap join is not done.
2. Complete trusted desktop-session/bootstrap integration and any real multi-user
   identity/role mapping required by Enterprise deployment. Header role labels and
   loopback policy are not proof of an authenticated Enterprise principal.
3. Audit the actual admitted authority build and verify positive exact-source
   research plus clear clean-install/offline setup. Disabling demos is not a
   substitute for that positive journey.
4. Complete runtime/evaluator-dependency provenance binding and independently
   authored final holdout work. Pinned fixture/evaluator revalidation is now
   enforced, but trusted evidence generation and actual model quality correction
   are not replaced by those integrity checks.
5. Evidence r0013 remains failed at 40/104 on its existing strict regression;
   Drafting r0003's prior result is 12/22. No new training, real inference, legal
   qualification or admission occurred here. The production trust store remains
   empty; no test key, fabricated review or approval was substituted.
6. Qualify actual CPU/hardware budgets, complete critical accessibility journeys,
   and finish exact-source full regression. Current tests use Python 3.11.9 with
   the pre-existing external site-packages overlay; this is not a reproducible
   clean build environment.
7. Build one exact candidate with approved feature scope, reproduce dependencies,
   and perform package privacy/engine audits, isolated install/restart/upgrade,
   installed-offline workflows, and WACK as applicable. Preserve Microsoft Store
   signing versus separate local QA signing.
8. Obtain any human/legal/pilot/organizational evidence required by the project's
   release policy. Software tests do not supply those approvals.

Until those gates pass, Store and Enterprise GA are **not established**. The final
engineering receipt records remaining blockers rather than advertising completion.

## Evidence and workspace

The final receipt is `dist/ga-closure/evidence/ga-closure-summary.json` with a
plain-text companion and `artifact-manifest.json`. The Git worktree remained
dirty: 140 changed/untracked files at evidence capture, including pre-existing
user work; no commit, reset, stash, version bump, push or publication was made.

All three test-runner fixture roots were removed by their managed cleanup. Three
small source snapshots and compact reports are retained (no runtime or model-pack
duplicates). The owned QA workspace measured 118,251,416 bytes before final
receipt generation. An explicit cleanup of 4,970,160 bytes under `work` and `ui`
was blocked by execution policy before starting. Those disposable fictional
fixtures remain; no bypass was attempted. User models, records, corpus and the
installed application were not deleted or modified.
