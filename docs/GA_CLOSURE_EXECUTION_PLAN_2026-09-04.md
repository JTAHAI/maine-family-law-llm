# GA closure execution plan — 2026-09-04

## Decision and review boundary

The shortest credible route is ten closure batches, with app/security/build work
running alongside one bounded model-quality experiment. Evidence Review is the
first model gate; reuse a successful approach for Drafting. Do not start another
large continuation run until an independently worded small experiment improves
the failures described below.

Target: a useful local Windows release with qualified Evidence Review and
Drafting, a tested minimum hardware configuration, and one exact qualified MSIX.
Other specialist slots and incomplete roadmap features stay unavailable until
their own acceptance evidence exists. A maintenance release excluding specialists
is a separate possible milestone; it does not satisfy the two-specialist target.

This document is a plan, not GA certification. The review covered repository
structure, current changes, representative production security/source routes,
specialist runtime/training/evaluation, shipped UI, CI/build tooling, and existing
qualification artifacts. It did not dynamically exercise every route, run new
inference, repeat the full suite, inspect personal records, or install a package.

## Verified baseline

- Checkout: `D:\dev\Maine-Family-Law-LLM-github-main`, branch `main`, HEAD
  `258d1f091a614a1625acd285978cd6ce73daeb55`.
- Before this plan: 65 modified tracked files and 37 untracked entries. Preserve
  them. Git HEAD alone does not identify this dirty source tree.
- New read-only checks: 1,297 Python files compiled in memory without syntax
  failures; both production `workbench.js` files passed `node --check`.
  Root/src API, HTML, CSS and JavaScript mirrors are byte-identical.
- Latest completed full regression: **2,483 passed, 22 skipped, zero failed**, out
  of 2,505 collected. Evidence:
  `dist/qa801/ga-specialists-20260902/full-regression-final-r2/summary.json`.
  Its source snapshot SHA-256 is
  `4e4f486a96f737540004243777ed9c3d254931c8dd302a994283e7715373b297`.
  At least 28 existing files changed since that snapshot; this count excludes
  subsequently added files. Older summaries still saying `running` are stale.
- Skips include six missing authority/GA evidence checks, one actual Whisper
  WAV journey, fourteen symlink-privilege checks, and one POSIX executable-bit
  scenario. Only the last is inherently outside the Windows target; the others
  require applicable direct evidence or an explicit unsupported scope.
- Evidence r0013: real research artifacts; **40/104** frozen checks pass versus
  **87/87** internal checks. Drafting r0003: **12/22** frozen checks pass.
  Neither is quality-qualified or production-admitted. An incomplete later
  Drafting correction is not evidence of completion.
- `configs/fast_interchange_admission_trust.json` has no production trusted keys.
  The seven-slot fleet metadata is a plan, not seven available specialists.
- Existing frozen core UI observations cover useful fictional OCR/search/source
  preview/navigation work. They do not prove specialist inference or the latest
  installed MSIX. The current runtime appears to be the essential tier and lacks
  the full specialist dependency/assets set.
- No genuine release MSIX was found under this checkout's `dist`; `.msix` test
  fixtures must never be selected as release artifacts.

## Priority defects to close

1. **P1 — Job ownership/privacy:** `app/api/production.py:1216` exposes job
   list/create/read/cancel/recovery without session/tenant/matter ownership.
   Empty matter scope lists all jobs; the runtime can return payload/result/error
   fields and persists plain JSON (`src/maine_family_law_llm/runtime_kernel.py`).
   No private job contents were inspected in this review.
2. **P1 — Inconsistent request protection:** unique enterprise routes dispatch
   directly through `app/api/production.py:1300`; the local global firewall does
   not surround both apps. `app/api/security.py:95` permits a predictable signing
   secret fallback, and `:240` trusts role/tenant headers. Loopback binding is a
   mitigation; this review does not demonstrate remote exploitation.
3. **P1 — Authority shortcuts:** `app/api/routes/citations.py:15` has a demo
   authority index; `:29` accepts caller-supplied verification inputs.
   `app/api/routes/research.py:35` wraps supplied source cards rather than
   retrieving admitted authority. These legacy endpoints need production removal
   or integration with the canonical source resolver.
4. **P1 — Sensitive output:** Evidence and Drafting use duplicated closed-list,
   colon-only sensitive-label regexes (`legal/fast_interchange/evidence_output.py:17`,
   `drafting_output.py:19`). Existing fictional model outputs using `Personal
   access string:` and `Personal string:` bypass those patterns and the upstream
   filter. Exact quotation alone must not authorize publishing a protected span.
5. **P1 — Feature truth:** route presence currently yields
   `store_feature_claim_eligible: true` (`app/api/production.py:393`), while tier
   checks use module discovery. Neither proves usable installed functionality.
6. **P1 — Release automation:** the MSIX CI runs tests before dependency setup,
   can freeze twice, invokes an installer with a stale v7 default path, and its
   artifact glob can include a generated development signing PFX. Fix before
   using that workflow for public release.
7. **P2 — Accessibility:** view items have `role=menuitemradio` but update
   `aria-pressed`, not `aria-checked` (`src/.../ui/workbench.html:116`,
   `workbench.js:11832`). Marker-presence tests miss this behavior.

## Execution batches

### G01 — One release ledger and bounded workspace

Status: initial conservative ledger implemented 2026-09-04; full G01 closure is
still partial. The runtime now exposes one source-controlled
ledger that separates 54 legacy-reachable workspaces from zero current
Store-claim features, lists the blocked Evidence/Drafting candidates, and makes
every legacy feature's requalification evidence explicit. Focused release-scope,
gateway, and negative-claim tests passed. The complete per-feature action/API/UI/
tier/artifact join and roadmap reconciliation are still required. See
`GA_CLOSURE_HARDENING_2026-09-05.md` for implemented cross-batch repairs and their
verification limits; no whole-batch or GA completion is implied.

Files: `configs/v801_release_scope.json`, `configs/v800_release_scope.json`,
`configs/store_feature_tiers.json`, `configs/fast_interchange_model_fleet.json`,
`app/api/production.py`, `docs/RELEASE_8_0_1_SPECIALIST_STATUS.md`.

- Generate one feature manifest joining feature ID, real UI action, canonical
  route, required tier/assets/model/authority, useful result, test level and
  artifact hashes. Import accurate existing evidence; preserve historical reports.
- Reconcile all 200 roadmap entries against this manifest without treating
  source completion or route counts as installed E2E. Do not redo completed code.
- Separate app readiness, model quality/admission, Store qualification and
  Enterprise evidence. Replace stale status pointers with the latest receipts.
- Use one owned `dist/ga-closure/` workspace, the existing usable cache, and one
  runtime/staging tree. Preflight disk space. Preserve actual weights, current
  releases and compact evidence; clean only validated owned temporary artifacts.

Exit: no public feature lacks a declared, testable acceptance action; every
unfinished feature has an explicit unavailable state; no new scratch outside repo.

### G02 — Common session, matter and job protection

Files: `app/api/production.py`, `app/api/security.py`,
`legal/security/local_request_firewall.py`, `app/local_api_service.py`,
`src/maine_family_law_llm/api.py` and its mirror,
`src/maine_family_law_llm/runtime_kernel.py`.

- Put request-origin/host, bounded-body, rate, safe-error and audit policy around
  the common dispatcher. Preserve route-specific checks and private source gates.
- Bootstrap a random, protected local session secret; remove predictable
  production fallback. Bind capabilities to server-established identity/session,
  active matter, intended operation, expiry and replay policy.
- Derive job ownership server-side; scope listing/read/cancel; restrict recovery
  to authorized maintenance. Return safe metadata. Prohibit private content in
  generic job storage or encrypt it through the existing matter-key path.
- Keep single-user local operation explicit. Multi-user Enterprise claims need
  an actual authenticated principal and role mapping, not caller-selected headers.

Exit: parameterized tests across local/enterprise/overlap/alias routes reject
missing/forged/expired/replayed/wrong-matter sessions. Denials preserve records
and jobs. Restart and cancellation work through the same protected boundary.

### G03 — Canonical authority and verifier correctness

Files: `app/api/routes/citations.py`, `app/api/routes/research.py`,
`app/api/production.py`, canonical authority/verifier services,
`scripts/ingest-maine-authority.py`, `scripts/audit-authority-build.py`.

- Remove legacy demo/caller-trusted authority routes from production, or resolve
  their IDs through the same admitted immutable store as the desktop workbench.
- Require exact source/build hashes and spans; reject caller attempts to supply
  authority status, freshness, source text or verification success.
- Audit the actual accepted authority build and freshness. Exercise real statute,
  rule, opinion and form lookup, fake citation rejection, pinpoint and quotation
  matching, stale/unknown/wrong-jurisdiction handling, and source previews.
- Verify a clean install with no authority store gives clear setup guidance.
  Separately verify offline research after explicit admitted-source import.
  Do not label a fictional demo or a preconfigured developer data root as the
  clean-install real-authority experience. Keep authority products external.

Exit: genuine positive research/source journeys and adversarial rejection pass;
no production route establishes legal support from fabricated or caller-owned
authority metadata. Release claims reflect the actual first-run prerequisites.

### G04 — Shared model output boundary and trustworthy evaluation

Files: `legal/fast_interchange/evidence_output.py`, `drafting_output.py`,
`legal/security/injection_defense.py`, `scripts/run_mfl_specialist_regression.py`,
`scripts/summarize_mfl_specialist_quality.py`, and their focused tests.

- Centralize protected-span handling; preserve reviewer redactions and privacy
  exclusions through source selection, model context and final rendering. A
  growing regex label list alone is insufficient. Test punctuation, Unicode,
  unclassified identifiers, source order, middle/end positions and mixed safe spans.
- Preserve host-owned exact-source rendering and withheld unsupported narrative.
- Classify existing failures into actual privacy/source/detail failures versus
  wording-only rubric disputes. Retain the original strict results. Any corrected
  evaluator requires independent justification, versioning and a full rerun.
- Pin approved fixture hashes/case IDs/families/checks and evaluator/runtime
  hashes before execution; verify them afterward and during release revalidation.
- Treat repeatedly consulted frozen suites as regression data. Add a separately
  authored final holdout that is not used for training or checkpoint selection.
- Bound evaluator subprocesses, output capture and owned-process cleanup; persist
  progress per command. Run a short safety/generalization screen before expensive
  full suites, but never use that screen as the qualification gate.

Exit: reproduced output-boundary failures are blocked in both specialists;
changed/missing fixtures, partial runs and stale candidate hashes cannot qualify.

### G05 — One efficient Evidence correction experiment

Files: `scripts/train_mfl_adapter_continuation.py`, corrective corpus builders,
`scripts/audit_mfl_evidence_corrective_corpus.py`,
`scripts/run_mfl_correction_lane.py`, specialist regression tools.

- First audit training targets, semantic/structural split overlap, source order,
  privacy exclusions, EOS, tokenizer IDs and production prompt parity. Tokenizer
  mismatch or truncation has not been established as the present failure cause.
- Allow manifest-defined small pilots instead of requiring 25,600 rows and a
  minimum 3,200-row run. Validate consumed-example lineage across continuations.
- Add bounded atomic optimizer/RNG/checkpoint resume; enforce repository-local
  output/temp/cache paths and available-space checks in the trainer itself.
- Compare the existing base and candidate on the same independently worded
  development tasks. Train one small candidate using diverse source-based tasks,
  distractors, negations, conditions, omissions and abstention. Select on useful
  development results, not low loss or final epoch alone.
- Scale only if hard safety/source errors reach zero on the pilot and unfamiliar
  wording/detail performance improves. Otherwise change the data/task/adaptation
  design before spending another full training run.
- Require complete existing Evidence regression (104 cases), the separately
  protected final set, bounded natural completion and useful outputs. Validate
  semantic usefulness separately from keyword checks and safe empty responses.

Exit: an immutable Evidence candidate with hashes, provenance, exact-runtime
quality evidence and explicit scope. This alone does not grant production admission.

### G06 — Reuse the proven design for Drafting

Files: `scripts/build_mfl_drafting_corrective_corpus.py`,
`scripts/build_mfl_drafting_generalization_corpus.py`, `drafting_output.py`,
host task contracts, and the existing production draft/revision services.

- Start only after G05 demonstrates a useful generalization improvement. Train
  sequentially on the same GPU and reuse the shared base.
- Prove a meaningful draft action: user selects evidence and any admitted
  authority, receives a usable review draft with exact supporting spans, sees
  unsupported points, saves a revision and compares/exports a working copy.
- Be precise about scope: current deterministic Drafting is an excerpt-based
  working draft. Do not claim a full legal pleading generator from that result.
- Require all existing 22 Drafting regression cases plus independent final
  coverage for unfamiliar wording, invented sources, sensitive spans, missing
  context, unsupported facts and preserved originals.

Exit: the two intended specialist candidates each qualify on their own task.
Partial Parenting and planned Financial/other slots stay unavailable.

### G07 — Real hardware, app interaction and accessibility

Files: `legal/fast_interchange/hardware.py`, `process_backend.py`, `worker.py`,
`app/services/fast_interchange_worker_service.py`, `scripts/verify_evidence_review_in_app.py`,
production UI assets and packaged runtime configuration.

- Prove the actual shipped worker/dependencies, not a separate GPU diagnostic
  environment. Hardware preflight must check usable Torch backend and free RAM,
  with one base and one active adapter, bounded context and complete context reset.
- Measure an actual proposed low-end CPU-only configuration, a typical 16 GiB
  computer, and one supported GPU configuration. Driver visibility is not CUDA
  capability; a RAM-limited test on this larger machine is supplemental evidence.
- Current pair requirements allow up to 5 GiB worker RSS plus 1 GiB headroom.
  Do not promise 4 GiB-PC specialist support; even 8 GiB needs measurement with
  Windows, application, import/OCR and other normal memory use.
- FP32/FP16/BF16 Transformers/PEFT is implemented. Fleet NF4 metadata does not
  mean NF4 or GGUF support exists. If CPU budgets fail, perform one bounded
  quantized-backend feasibility experiment, then requalify tokenizer/EOS/output,
  admission ABI and every runtime guard before adding it to the release.
- Suggested initial UX targets to ratify before testing: progress within 150 ms,
  cancellation acknowledgement within 1 s, owned-worker shutdown within 5 s,
  and p95 warm useful completion within 15 s for a bounded Evidence task / 30 s
  for a bounded Drafting task. These are proposed budgets, not achieved results.
- Fix menu checked-state semantics, keyboard focus/return, 200% zoom, contrast,
  loading/empty/error states and hidden-panel navigation. Preserve default Both,
  Child Impact Lens on, and collapsed Chat layout.

Exit: user opens each specialist, approves context, gets a useful result, drills
to exact source, cancels, changes matter, closes/reopens and recovers work. Record
real UI evidence, memory/cold/warm/p95 timings and hardware-specific availability.

### G08 — One complete source regression and version freeze

- Run focused tests while implementing G02–G07. Once those changes stabilize,
  run `scripts/run_isolated_release_regression.py` with `--snapshot-source`, a
  new compact run directory under `dist/ga-closure/`, and the qualified interpreter.
- Collect current tests; retain every result and skip reason. Close native
  Whisper, symlink and missing authority/E2E coverage with applicable Windows
  evidence. Do not silently deselect or retry failures into a passing aggregate.
- Compress the original 22 core journeys and public-feature actions into shared
  fictional fixtures without dropping assertions: import/hash/OCR/duplicates,
  research/verification, source preview, timeline/history/claims, orders/coverage,
  drafts/revisions/forms, snapshots/packets/receipts, cancel/restart/backup/restore.
- Run cross-matter/tenant, hostile document/parser/archive, output privacy,
  Local-only, filing-gate and large-matter cases. Zero false filing-ready passes
  is required on the release attack set; quantify the tested set.
- Fix only release-critical defects. Then set the intended new version
  consistently, validate identity/language/capabilities/migrations, and freeze
  the complete source tree, dependencies and selected model/authority identities.

Exit: no unresolved P0/P1; current full regression complete; every advertised
workflow has meaningful positive evidence. A safe unavailable state proves only
the negative path and cannot qualify an advertised functioning specialist.

### G09 — Reproducible single build and exact-package qualification

Files: `.github/workflows/build-msix.yml`, `scripts/build-store-runtime.ps1`,
`scripts/build-msix.ps1`, `scripts/install-test-msix.ps1`,
`scripts/run-wack.ps1`, `scripts/audit_store_package.py`, PyInstaller spec/requirements.

- Install locked build/test dependencies before CI tests. Remove dependence on
  an undeclared external `.pth` build environment; record exact engine/dependency
  versions, hashes, source licenses, notices and advisory results.
- Build the runtime once and package that exact verified artifact. Current CI
  freezes separately and `build-msix.ps1` freezes again; eliminate duplicate work
  with a hash-verified reuse contract or a single canonical build invocation.
- Select tier and specialist pack explicitly. Essential mode excludes Torch and
  cannot be described as the full specialist edition. Validate actual bundled
  assets and required dependencies against the selected feature manifest.
- Pass explicit package paths everywhere. Installer default points to v7 and
  WACK defaults to v8.0.0; neither may choose a stale candidate automatically.
- Produce an unsigned Partner Center submission artifact. Microsoft Store signs
  it. Keep any approved isolated-QA signing key/certificate outside public
  artifact globs; never upload PFX/password files. Model admission signatures
  serve a separate purpose and must remain valid.
- Re-run package private-data, test/cache residue, binary/license, dependency,
  engine, map, language, identity, sealed-payload and archive audits after final
  pruning/staging. Preserve exact MSIX SHA-256, size and source/runtime/model hashes.
- Test clean installation, core and both model journeys, OS-blocked outbound
  operation, graceful shutdown, restart, uninstall/reinstall and supported upgrade
  with fictional data in an isolated Windows environment. Preserve the user's
  real Store installation. Run WACK on the explicit candidate and save the result.

Exit: one installable exact candidate passes its applicable install/offline/
upgrade/WACK/privacy checks. Any candidate byte change invalidates affected
evidence and requires requalification.

### G10 — Honest admission, decision and delivery

- Start obtaining required independent evaluation/signoff evidence during G04,
  so it does not first appear as a blocker after building.
- Current model policy requires attorney-reviewed evaluation and production
  signed admission (`legal/fast_interchange/admission.py`,
  `scripts/validate_bundled_mfl_specialists.py`). Provision an authorized release
  key and exact grants only after requirements are met; never promote a test key.
- Current Enterprise/production-legal policy additionally requires 2,750
  attorney-reviewed rows, qualifying metrics, pilot evidence, and legal/security/
  product/operations signoffs (`configs/maine_production_promotion_policy.json`).
  These are this project's policy requirements, not assertions about Microsoft
  Store requirements. Automated tests cannot establish these human facts.
- A deliberately limited local-assistant release policy is a separate explicit
  scope decision if the current human-evidence requirements cannot be supplied.
  Do not silently remove them or rename synthetic checks as human review.
- Assemble one final decision linking feature truth, full regression, model
  provenance/quality/admission, hardware/UI, package and installation hashes.
  Report Store readiness and Enterprise readiness separately.
- Generate README/site/Store copy and screenshots only from accepted installed
  functionality. Hand over the MSIX, SHA-256, release notes and rollback notes.
  Publication is a distinct action, outside this planning review.

Exit: release assertions are reproducible from the exact shipped artifact; any
unmet external requirement is explicitly blocked and excluded from claims.

## Parallelism and stop rules

- After G01, app/security/source repairs (G02–G03), model boundaries/evaluation
  (G04), and CI/build/UX preparation (parts of G07/G09) can run independently with
  disjoint files. Serialize edits to the production API/UI and shared model gates.
- GPU work is sequential: small Evidence pilot, qualified Evidence run, then
  Drafting. Avoid competing training/inference that invalidates resource results.
- G08 waits for current source changes and real model/UI evidence. G09 builds
  once after freeze; G10 ties the verdict to that exact package. Begin the external
  evaluation/admission process early; do not defer that dependency to the end.
- No new feature queue or broad rewrite. Keep useful encrypted storage, source
  re-resolution, context approvals, scoped cancellation and audit machinery.
- Keep personal corpus/personalized training out of public models, fixtures,
  code, package and release reports. Personal experiments need separate private
  provenance, storage, privacy testing and authorization; none are part of this
  public GA plan.
- Keep one candidate experiment and one owned temporary build workspace at a
  time. Retain compact receipts and needed weights; never delete broad directories
  or work around a denied cleanup action.
- Engineering/build effort becomes estimable after G01–G04. Model generalization,
  genuinely low-end runtime viability and required external human evidence have
  uncertain duration. No defensible same-day full-GA promise exists today.

## First implementation batch

Start with G01 and the demonstrated P1 defects in G02–G04: job ownership,
common request protection, demo-authority removal and protected model spans.
These directly reduce release risk and make the next model experiment and final
package evidence trustworthy.
