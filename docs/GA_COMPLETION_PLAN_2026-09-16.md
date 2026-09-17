# GA completion plan — source-backed local workbench with 4B/8B reasoning

Date: 2026-09-16. Status: PLAN, NOT RELEASE CERTIFICATION.

Working tree: `D:\dev\Maine-Family-Law-LLM-github-main`.
Branch: `main`. HEAD: `82364d869b4d2d427b93f32b812e857d28cc3e38`.
Before this plan: 40 modified tracked files, 122 untracked Git entries (some are directories),
4,317 tracked insertions and 610 deletions. Preserve these changes and the owner's ZIPs.

## Outcome and scope

Finish the existing product rather than restart the 200-feature queue. Deliver a usable,
source-backed local chat, record/OCR/form workflows, and both 4B-class and 8B-class local
reasoning model options, with ordinary-user model setup and an exactly tested Windows
package. Do not rebuild the separate ProSe project or its legal drafter.

### Owner scope amendment — 2026-09-16

The owner explicitly permits this release without specialist models. This supersedes the
earlier specialist-inclusive release requirement and corresponding dependencies below.

- Qualify BOTH a 4B-class and an 8B-class reasoning model for the advertised general-chat
  and source-assisted tasks. Select exact upstream releases/quantizations only after license,
  runtime, hardware and actual answer-quality checks; no specific weights are admitted here.
- Recommend the 4B option only on measured compatible hardware; recommend 8B where measured
  headroom and usability support it. Keep one model resident by default, not both at once.
  Users need install only their selected option. Do not silently fetch or switch models.
- A PC that cannot run either safely retains useful core research/records/OCR/forms. Model
  parameter count is not a RAM requirement; measure quantization, context and whole-app peak.
- The former under-1.5-GB specialist target is not a required cap for these general reasoning
  options. Show real download, installed and peak disk costs; determine bundled versus
  optional delivery in Pass 13 rather than assuming either fits existing tier limits.
- Specialist training, compact extraction/ranker runtime closure and custom Evidence Review/
  Drafting model admission are deferred, not failed requirements of this release. Preserve
  their code/artifacts safely and keep their public activation and claims disabled.
- Existing non-specialist record-review and drafting tools can remain only when their actual
  behavior passes the feature matrix. General reasoning models are not advertised as trained
  Maine-law specialists; source fidelity and review-required safeguards still apply.
- Reasoning mode needs bounded context/output/time, cancel/unload and a useful final answer.
  Do not expose raw internal reasoning as verified evidence or require it as a quality metric.

Passes 09–12 now apply to the selected general-reasoning engine and model profiles. Reuse
the existing Sentinel/local-provider route where qualified; do NOT finish the unrelated
BERT/PEFT compact runtime as a prerequisite. Specialist-specific implementation instructions
in those passes remain deferred technical notes. Passes 17–18 are deferred in full; their
ordinary record/draft UI functionality is still covered by Pass 19. In later dependency
lists, replace 17–18 with the retained-feature sweep (19). Pass 23 evaluates general-chat
and source-assisted outcomes, not absent specialists. Later frozen/package checks exercise
both qualified reasoning profiles and only retained feature claims.

**A lawyer, attorney-reviewed dataset, or attorney pilot is not a release dependency in
this plan.** That is an explicit requested change from several existing project policies,
not a claim that those policies already pass. Preserve provenance, actual quality testing,
maintainer accountability, and the user's review-before-reliance workflow. Never rename
synthetic/operator-reviewed evidence as attorney-reviewed evidence.

Track four independent results: core application, each 4B/8B reasoning profile and advertised
task, installed package, and operational readiness. This revised round requires all four
to pass but does not require specialist completion. A model-empty core-only package would
still fall short of the new reasoning-model requirement.
Do not replace a failed Evidence Review model with a literal extractor and call the original
feature finished. Useful narrower tools may ship under their actual names and limitations.

## Review basis and observed blockers

This is a source/configuration/release-evidence review, not a new full-suite, live-model,
native-desktop or installed-package run. Existing roadmap claims were treated as historical
evidence pointers, not automatically accepted current functionality.

| Observed fact | Basis | Consequence |
|---|---|---|
| Release remains 8.0.2 / 8.0.2.0, current qualification pending | `configs/release_feature_truth.json`, `configs/v802_release_scope.json` | Do not call this v9 or GA yet. |
| Current Store-claim feature list is empty; regression binds an older snapshot | Same truth manifest | Rebuild current feature evidence, not just a checklist of code files. |
| Latest existing MSIX is 277,083,294 bytes, built September 12 local time | `dist/store/msix/MaineFamilyLawLLM_8.0.2.0_x64.msix` | Candidate exists but predates September 13 chat changes. |
| Candidate SHA-256 independently rechecked | `ae8710345081c85faadb069ab5b730bc682ce13883dc2b6647cdcaa2519c24d7` | Historical package identity only; not current-source certification. |
| Build/privacy/sealed audits report pass; WACK says not_run | `dist/store/evidence/test-summary.txt`, private/sealed audits | Preserve results without inferring clean installation or Store acceptance. |
| Frozen smoke is healthy but reports `official_authority_product_unavailable`, `answer_grounded=false` | `dist/store/evidence/store-build-smoke.json` | Fail-closed behavior is tested; useful grounded research still needs installed proof. |
| No installable model profiles | `configs/local_ai_catalog.json`: unconfigured, revision 0, profiles empty | “Install recommended AI” is not delivered yet. |
| Setup exposes status/basic-mode/catalog/assess/plans, not transfer/activation jobs | `app/api/local_ai_setup.py` | Finish lifecycle, not another setup label. |
| Sentinel canonical readiness explicitly blocks missing resource profile, admission and task qualification | `maine_family_law_llm/api.py` | Configured transport is not a working admitted product path. |
| Compact production declarations are always rejected | `legal/fast_interchange/compact_admission.py` | Need a real qualification/admission implementation, not removal of the rejection alone. |
| Legacy production admission requires attorney-reviewed data | `legal/fast_interchange/admission.py` | Implement the requested non-lawyer policy explicitly and version it. |
| Compact locked allowlist wiring has focused tests, but complete serving inventory/production factory remain unfinished | Last sections of `docs/COMPACT_SPECIALIST_GA_PROGRESS.md`; provider factory | Dependency ownership accounting is not a qualified execution closure. |
| Historical generator challenges have attribution/date/draft-quality failures | Compact progress report and linked challenge reports | Existing weights must improve or task eligibility must stay blocked. |
| Workboard source-lane buttons both open the generic evidence panel | `bindConversationWorkboard` in production JS | Bind each action to that answer's lane and exact source IDs. |
| Download policy conflicts with proposed model installation | `configs/store_feature_tiers.json`: runtime downloads false; essential excludes Torch; bundled specialists currently require full tier | Reconcile model-data delivery, bundled engine and tier enforcement before implementing installs. |
| Packaging uses `src` as canonical and ships its UI | `store/pyinstaller/maine_family_law_llm.spec` | Dev-only UI is not acceptance evidence. |

Checks executed in this review: `git diff --check`, `node --check` for both workbench JS
copies, and SHA-256 equality for root/src API, answer contract, HTML, CSS and JS. These passed.
No Python test count, full E2E pass, new model quality result or GA decision is asserted.

## Execution rules

- Preserve the dirty tree; no cleanup, commit, push, version bump, download or build merely
  because this planning document exists. Those belong to the authorized execution phase.
- Use AGENTS.md: one repo-owned `dist` QA workspace, explicit temp/cache paths, disk budget
  before large operations, no external scratch clones, no repeated model/runtime copies.
  Keep compact evidence outside disposable fixture directories. Never delete user archives,
  original records, actual weights or unrelated environments.
- Reuse `docs/LOCAL_AI_SETUP_GA_TERRA_PLAN.md` and compact progress evidence. Its old
  “start Slice 01” instruction and historical pre-repair findings are not a restart order.
  Setup slices 01–03 already have source work; validate and finish them rather than rewrite.
- Preserve existing private-data boundaries. Approved external official authority stays
  external; use isolated fictional fixtures under `dist`. No personal corpus in release
  training, test fixtures, screenshots, packages or public evidence.
- Every accepted capability must traverse service → canonical scoped API → production UI
  → meaningful action → exact source/artifact → visible review state → persistence/recovery
  → tests → frozen/installed proof. A text-presence test does not establish UI behavior.
- Record each result with source/dirty-file hashes, model/runtime/prompt/policy versions,
  dataset hash/type/count, command, duration, counts/skips, actual UI result and blockers.
  A code/prompt/weight change invalidates affected evidence; unrelated evidence can be reused
  only with an explicit dependency/hash match. Do not sum overlapping historical test runs.

## Ordered remaining passes

Pass numbers below are this completion plan, not the old legal slices or NEXT_200 IDs.
File names marked proposed do not imply existing implementation.

### Batch A — one truthful release contract

**01. Establish current source and feature baseline.**
Files: `configs/release_feature_truth.json`, `configs/v802_release_scope.json`,
`docs/NEXT_200_UPGRADES.md`, canonical API registration and PyInstaller specification.
Map every reachable navigation item, command/chat action and route to a stable feature ID,
service, persistence, tests and evidence. Reconcile old IDs without inventing a remaining
slice count from roadmap prose. Record exact dirty-file hashes; classify source-only,
tested, frozen-tested, installed-tested and hidden separately. Produce one current matrix.
Exit: every advertised/reachable feature is accounted for and no stale result is labeled current.

**02. Implement the no-lawyer release policy consistently.** Depends: 01.
Files: `legal/fast_interchange/admission.py`, `compact_admission.py`, `legal/evals/review_modes.py`,
`legal/production`, `legal/release`, release/enterprise/gold-eval policy JSONs and gate tests.
Reuse the existing `operator_source_backed` evaluation lane where appropriate. Introduce a
versioned engineering release profile distinguishing mechanical exact-source tests,
source-backed maintainer-scored tasks, synthetic challenges and optional external review.
Trace policy consumers; migrate schemas/grants deliberately, preserving expired/revoked,
tamper, provenance and no-test-key checks. Keep historical attorney-reviewed records true
to their original label; do not globally replace the word attorney or remove user review.
Exit: required release decisions no longer wait on lawyer signoff, while missing task,
runtime, security or package evidence still blocks. Add negative tests for fabricated review
metadata, unsigned/expired grants, and accidental promotion of old research candidates.

**03. Canonical routing and production asset integrity.** Depends: 01.
Files: both API mirrors, `app/api/main.py`, `app/api/routes`, `app/api/release_boundary.py`,
`store/pyinstaller/maine_family_law_llm.spec`, route/inventory tests.
Enumerate actual final mounted route+method pairs, effective ordering and intentional aliases.
Prove aliases preserve validation, role, tenant/matter scope, origin/session, audit and errors.
Test both import roots and packaged assets; prevent mirrored files from drifting in CI.
Exit: no unintended shadowed handler, public preview leak, missing packaged module or dead navigation.
Do not undertake a broad API/JS framework rewrite during release stabilization.

**04. Complete private state and migration hardening.** Depends: 03.
Files: `legal/documents/{storage,migration,migration_review,workspace}.py`,
`legal/review/{integrity,review_ledger,reviewer_queue,assignment_migration}.py`, relevant APIs.
Inventory every matter-private sidecar, temp write, draft/review/history record and diagnostic.
Verify encryption, atomic writes, revision conflicts, authenticated history and least privilege.
Finish legacy read-only → preview → explicit conversion → reopen → interrupted recovery flows.
Exit: fictional legacy/new matter survives restart, failed migration, duplicate retry, tampering
and backup restore without loss; originals remain recoverable and scope cannot be crossed.

### Batch B — useful answers and exact sources before more model work

**05. Make official authority available in the real user journey.** Depends: 01,03.
Files: `legal/authority_store`, `legal/retrieval`, `legal/data_boundaries`, authority setup UI;
reuse `scripts/ingest-maine-authority.py`, `audit-authority-build.py`, parsed/index audits.
Identify the active approved external build, source classes/counts, metadata, snapshot hashes,
freshness and rights basis. Make acquisition/selection/activation and absence recovery usable;
no developer-only path assumptions. Keep authenticated official authority separate from generic
source libraries, private records, model memory and demonstration fixtures.
Exit: an ordinary installed user can obtain/select allowed local authority, ask a supported
question and inspect exact source spans offline; missing/stale data is visibly limited.

**06. Close retrieval, citation, quote and claim verification.** Depends: 02,05.
Files: `legal/verifiers`, `legal/law_court`, `legal/forms`, retrieval/evaluation runners.
Test exact statute/rule/case/form lookup, pinpoints, false citations, normalized quote offsets,
fuzzy/not-found states, unsupported/contradicted/stale/jurisdiction-mismatched claims and forms.
Measure Recall@5/10/20, MRR, nDCG, exact citation/quote accuracy on identified data, not a
generic success count. Use explicit source-backed scoring without lawyer-required labels.
Exit: unsupported current-law wording and stale-form completion fail closed; users can inspect
why and correct the source. Case summaries cannot invent negative treatment.

**07. Finish helpful, fast model-optional chat.** Depends: 03,05,06.
Files: both `family_answer_contract.py` copies, production workbench JS/CSS, local agent runtime,
`tests/test_conversation_workboard.py` and conversation/regression suites.
Fix workboard source actions to resolve the originating answer's source IDs and lane, including
old-message and changed-matter rejection. Show date-normalization assumptions, not inferred
dates as established facts. Answer the user's question before checklists; keep details collapsed,
Both and Child Impact Lens defaults, follow-up context and a usable no-model response.
Exit: actual UI handles follow-up, ambiguity, missing law/records, contradictory evidence,
cancel/retry and error recovery without fabricated facts or repetitive disclaimer-only replies.
Use behavioral tests; the existing workboard string-presence test misses the lane-button defect.

**08. OCR-to-form and document intake completion.** Depends: 04,06,07.
Files: `legal/forms/header_suggestions.py`, document intelligence/import services, forms APIs/UI.
Prove mixed PDF/scanned PDF/DOCX/email import, parser/OCR status, exact duplicates/changed copies,
malformed files, missing attachments, source-page previews and cancellation. Preview header
suggestions from selected records with confidence/basis/conflicts; explicitly confirm each update.
Exit: court/docket/party information never silently overwrites existing values, OCR errors remain
correctable, stale templates stay blocked and saved sessions reopen in the same matter.

### Batch C — finish the model execution foundation once

**09. Qualify a minimal reproducible serving runtime.** Depends: 02,03.
Files: `compact_source_imports.py`, `compact_artifacts.py`, `compact_ranker_worker.py`,
`scripts/reconcile_compact_runtime.py`, `plan_compact_observed_selection.py`, runtime inventories.
Finish required Python/native/data/notice selection and Windows platform mapping classification.
Authenticate origins rather than treating installed RECORD self-hashes as publisher proof.
Retain source-only/allowlist enforcement; prove the selected environment actually runs with all
nonselected dependencies absent, not merely that a broad dev environment once loaded it.
Exit: reproducible licensed runtime closure, real inference parity and measured complete bytes.
Do not repeat the unchanged 23,833-file verifier or raise timeouts and call startup fixed.

**10. Bound preparation, warm lifecycle and hardware use.** Depends: 09.
Files: `compact_artifacts.py`, compact process/CPU wrappers, `legal/runtime/warm_model_pool.py`,
`legal/model_orchestration/hardware.py`, `legal/fast_interchange/hardware.py`.
Run blocking file verification in an owned cancellable process; retain verified leases for
warm requests. Test warm/switch/reset/unload, memory pressure, OOM, cancel, crash and owner death.
Measure whole-app reserve, OCR concurrency, context/KV costs and disk peaks per backend.
Exit: no stale response, leaked worker, cross-request context, user-process termination or
unbounded preparation. Real modest-PC results support any Recommended hardware label.

**11. Freeze and run honest task-quality qualification.** Depends: 02,06,09; starts before tuning.
Files: `legal/evals`, `configs/mfl_specialist_regression_baseline.json`, compact challenge scripts,
specialist regression runner; proposed versioned task acceptance manifest.
Keep consulted regression cases separate from sealed, scenario-family-held-out cases. Bind exact
model/tokenizer/quantization/runtime/prompt and decoding settings. Score actual output correctness,
attribution, omissions, uncertainty and usefulness, not load success or model self-confidence.
Use fictional records and admitted official sources; no private corpus. Qualify each named task
separately. Fix failures, then use an untouched challenge set rather than tuning to the test.
Exit: pass the preregistered metrics below; no unsupported legal-expertise or lawyer-review claim.

**12. Production admission and canonical model selection.** Depends: 02,09–11.
Files: `compact_admission.py`, `admission.py`, `legal/agent_runtime/providers.py`, registry/host,
`legal/local_ai/catalog.py`, model-pack service and mirrored canonical API readiness.
Implement production qualification with hash-bound runtime, rights, task evidence and owner-managed
release trust. Add an explicit compact backend factory; do not masquerade GGUF/extraction as PEFT
BF16. Replace unconditional production denial only when actual prerequisites verify. Admission
must bind task/profile, prompt, source/approval policy and revocation/rollback rules.
Exit: real non-injected canonical selection accepts the qualified release and rejects every
tampered, research-only, mismatched or stale grant. Store signing is not model-admission signing.

### Batch D — model setup without engineering chores

**13. Resolve distribution/tier policy and hardware recommendations.** Depends: 09–12.
Files: `configs/store_feature_tiers.json`, local-AI catalog/setup, build policy, hardware APIs.
Choose one owned portable engine path as the normal route; keep an externally owned Ollama
installation opt-in and untouched. Distinguish bundled executable engines from approved model
data downloads. Resolve current essential/full exclusions and runtime-download prohibitions.
Exit: accurate bytes, working-set reserve, CPU/backend compatibility and measured/unknown labels;
unsupported devices receive a useful core mode, not a false Ready state.

**14. Deliver the pinned release catalog.** Depends: 11–13.
Files: `configs/local_ai_catalog.json`, `legal/local_ai/catalog.py`, catalog routes and proposed
signed catalog/provenance records. Publish only verified tasks with exact revision, hash, bytes,
licenses, runtime compatibility, approved origins and quality receipts. No automatic discovery.
Exit: valid offline cache plus explicit refresh behavior; expiry/revocation/downgrade/bad signatures
block activation appropriately. Distribution rights and host availability must actually exist;
do not wait on an attorney to provide them or fabricate permission.

**15. Install, resume, cancel, repair and remove safely.** Depends: 13,14.
Files: `legal/local_ai`, `app/api/local_ai_setup.py`, model-pack service, workbench setup panel.
Implement the missing server-owned job lifecycle with bounded transfer, disk reservations,
idempotency, resumed-download validation, complete artifact verification and atomic activation.
Persist progress/recovery; separate network consent from matter-context consent. Never execute
downloaded installer scripts or accept browser-supplied arbitrary URLs/paths/commands.
Exit: interrupted download/reboot, wrong hash, full disk, conflicting jobs, cancellation, repair,
rollback and removal work through actual UI without duplicate blobs or deleting external models.

**16. First-use model test and chat activation.** Depends: 07,10,12,15.
Files: local-AI lifecycle service, provider/runtime, scoped preview/approve/run APIs and UI.
Connect Check PC → Install → fictional test → Use in chat → Release memory, with live status,
bounded progress and focus return. Recheck artifacts, hardware and exact-context approval on run.
Keep source cards, failed verification and provisional model text distinct. Preserve prior good
answers on cancellation/fallback; forbid stale completion after matter/model change.
Exit: real weights through the normal production factory/UI, no environment editing or injected
test client. Repeat offline after application restart. Do not auto-download fallback models.

### Batch E — fully realized task verticals and remaining public features

**17. Evidence Review specialist acceptance — DEFERRED this round.** Future dependencies: 04,06,11,16.
Files: evidence/compact output, ranked/field review services, agent runtime, source inspector,
evidence UI and real API/browser tests. User selects records, reviews support/dispute/qualification/
missing context, drills into exact spans, records a review and reopens it.
Test negation, speaker/date/money attribution, missing attachments, unfamiliar wording and malicious
records. Relevance scores and extracted spans must never become findings or proof of truth.
Exit: advertised Evidence Review workflow passes task-quality and actual UI/persistence gates.
If only extraction passes, report extraction ready and Evidence Review still blocked.

**18. Source-bound Drafting specialist acceptance — DEFERRED this round.** Future dependencies: 04,06,11,16.
Files: `legal/fast_interchange/drafting_output.py`, existing drafting/workspace/revision services,
draft handoff API/UI and corresponding browser tests. Use existing drafting capabilities; integrate
the separate future drafter only through a qualified contract, not a donor rebuild.
Exit: selected verified sources → useful editable working draft → unsupported-claim blockers →
save/reopen → comparison → reviewed export with exact provenance. Test allegation/finding distinction,
unrequested relief, fake citation, lost qualifications and original-document preservation.
Templates or copied source excerpts alone do not prove generated Drafting quality.

**19. Close every remaining advertised feature path.** Depends: 01,03,04,06,08.
Use the feature matrix to batch existing domain workflows by shared service, not old slice number:
intake/orders/deadlines/docket; discovery/exhibits/witness/hearing/appellate; jurisdiction/inquiry;
parenting/finance; communications/media/redaction; collaboration/export/automation/productivity.
For each: meaningful fictional action, scope/role negative case, exact source/artifact, review state,
save/reopen and error/cancel behavior in the shipped UI. Avoid inventing legal outcomes.
Exit: each retained public feature has a current result; failed/incomplete routes and navigation
are consistently restricted. Deferral must be explicit and excluded from accepted claims, not
described as completing all features. No need to build unrelated new capabilities for GA.

**20. Critical UX, accessibility and low-end performance.** Depends: 07,08,16–19.
Files: production HTML/JS/CSS mirrors; existing frozen-UI accessibility and navigation scripts.
Test real 1280×720 and 1920×1080 windows, 200% zoom, keyboard/focus/dialog return, readable contrast,
high contrast, screen-reader semantics and reduced motion. Chat-first default; other cards
collapse without stranded focus or overlapping actions. Show active matter and safe scope always.
Exit: every critical flow has understandable empty/loading/error/cancel states and recovery,
no known P0/P1 UX defect, and measured cold/warm response and large-matter performance.
Capture a compact fictional screenshot/DOM set, not hundreds of duplicated builds.

### Batch F — security, recovery and current-tree regression

**21. Whole-path privacy, security and adversarial gate.** Depends: 03–20 as applicable.
Reuse security/local-only/filing-gate tests and audit scripts; include parent and owned children.
Test cross-matter/tenant access, stale approvals, origin/session abuse, injection, malicious files,
path/junction/archive attacks, unsafe HTML, arbitrary tools/URLs, audit tampering and log leakage.
Observe/deny outbound traffic during offline startup, OCR, search, model use, draft, packet and
shutdown; a Python mock alone is insufficient proof for native children.
Exit: zero accepted critical unsafe outputs and zero filing-gate false passes on the declared
attack set; no silent network activity, secret/private-text leaks or P0/P1 findings.

**22. Backup, recovery and release operations.** Depends: 04,15,21.
Files: existing backup/restore, revision, runtime operations and recovery UI; `SECURITY.md`,
`SUPPORT.md`, update/rollback runbooks. Test wrong-key/tampered backup, partial restore, interrupted
write, disk exhaustion, model rollback and old-to-new matter migration on fictional data.
Define support ownership, vulnerability handling, redacted diagnostics, update/revocation policy
and a practical recovery drill. Exclude attorney-pilot requirements; retain actual operator evidence.
Exit: recovery preserves records/drafts/history and is usable without editing databases or logs.

**23. Independent usability and outcome challenge.** Depends: 17–22.
Use a task assessor who did not tune the cases; no lawyer credential required. Score plain-language
helpfulness, successful task completion and misleading certainty against explicit source-backed
rubrics. Distinguish automated checks, maintainer review and actual non-lawyer user observation.
Exercise stress, unfamiliar wording, low literacy and assistive-technology paths. Model-as-judge
may flag cases but cannot be the sole ground truth or sole safety decision.
Exit: measured critical-journey success and resolved release-critical findings. If user observation
has not happened, say so; do not manufacture a pilot or enterprise organizational certification.

**24. Complete regression on the exact integrated source.** Depends: 01–23.
Run compilation, both JS syntax checks, test collection, full pytest and required opt-in real-model
and UI tests. Inspect tests skipped by default, markers, environment gates and unavailable fixtures.
Run route/asset contracts, performance/cancel, authority, model-quality, accessibility, backup,
network and filing attacks. Refresh dependency vulnerability/license/unexpected-binary audit.
Exit: no P0/P1 failure, required suites completed, precise counts/durations/skips with impact and
source hashes. Flakes need reproduction/repair, not repeated retries until one run looks green.
Any repairs loop back to affected passes; do not reset the entire roadmap.

### Batch G — exact delivered product and release

**25. Frozen executable acceptance and source freeze.** Depends: 24.
Files: canonical build/spec/runtime scripts and frozen journey runners. Resolve the intended
version once acceptance succeeds; keep package identity/publisher/architecture consistent.
Freeze source/policy/model selection, build once, prove exact asset/config/module hashes and
exercise the full retained feature matrix against the frozen process, not a development server.
Exit: launch, real sources, actual selected models, core tasks, cancel, shutdown/restart work
without developer Python, Node, caches, environment overrides or injected providers.

**26. Final MSIX and supply-chain/private-data audit.** Depends: 25.
Files: `scripts/build-msix.ps1`, `prepare_msix_staging.py`, package/sealed audits, notices and SBOM.
Build the selected tier with qualified model delivery, verify manifest/language/assets/engine
inventory and calculate exact SHA-256. Validate all required data/engine licenses and excludes:
no personal records, databases, authority/index/eval stores, credentials, caches, debug logs,
owner ZIP exports or unintended tests/tools. Classify deliberate runtime fixtures explicitly.
Exit: exact final archive passes audits and disk budgets. No production-signing claim from a
self-generated certificate; Microsoft Store signing and local QA installation are separate.

**27. Isolated installation, offline, upgrade and WACK.** Depends: 26.
Use a disposable Windows account/Sandbox/VM or approved QA identity, not the user's real Store
installation. Clean install → first launch → authority/model setup → actual core/specialist
journeys → offline restart → upgrade from available supported predecessor → uninstall/reinstall.
Test model/data retention semantics and rollback preparation. WACK report/status binds exact bytes.
Exit: the delivered package works on the declared Windows/hardware baseline, no P0/P1 install
failure and all required checks executed. Unavailable environment/old installer/WACK is explicitly
not-run, not success; determine release impact against the chosen release requirements.

**28. Freeze accepted claims and release handoff.** Depends: 01–27.
Update feature truth, per-model task admissions, release scope, migration/support notes, README,
Store copy, What's New and fictional screenshots from the qualified installed UI. Record separate
core/task/package/operations decisions and exact package/evidence hashes; never auto-convert them
to Microsoft certification, lawyer approval or independent enterprise endorsement.
Exit: no unresolved release-critical blocker and every public claim maps to current evidence.
Commit/push/site publishing/Store upload remain explicit release operations, not audit side effects.
If any source, weights or package bytes change afterward, rerun affected qualification first.

## Quality and performance gate proposal

These are proposed release criteria, not observed scores or a guarantee of legal correctness.
Freeze them before evaluation; retain stricter applicable engineering gates. Remove credential
dependencies in Pass 02 without silently lowering safety/usefulness requirements.

- Each 4B/8B profile's advertised general-chat/source-assisted task set: at least 200 held-out cases,
  including at least 50 adversarial/missing/conflicting-source cases; split by scenario family.
- At least 95% supported-task rubric pass and at least 90% completion on answerable cases.
  Report refusals, false abstention, omissions and attribution errors separately. An empty,
  disclaimer-only answer cannot earn task-completion credit.
- Zero accepted fabricated citations/quotes, cross-matter disclosures or unauthorized actions
  on the release set. Report raw model errors and host-withheld errors separately. Gate repair
  cannot disguise a model that generates mostly unusable responses.
- Field extraction requires correct field/actor/date/amount attribution and abstention, not
  just an exact substring somewhere in the record. Rankers require relevance metrics, not
  a legal-support claim. Evaluate the quantized deployed artifact, not only its original base.
- Report numerators, denominators and uncertainty; zero observed critical failures does not
  prove a zero failure probability. Test non-lawyer-validated tasks only to the supported scope.
- Initial performance targets to measure/calibrate: UI feedback within 200 ms; warm compact
  task first useful result within 15 s; short answer completes within 60 s on a Recommended
  profile. Establish preparation/cancel bounds before qualification. No unbounded spinner.
- Measure p50/p95 with sample counts, cold versus warm, whole-app plus worker RAM and actual
  modest-device operation. Do not extrapolate a workstation's constrained CPU run to all PCs.

## Efficient execution and stopping rules

Critical path: **01–02 → 09–12 (general reasoning only) → 13–16 → 19–24 → 25–28**.
Passes 17–18 are deferred; 26 passes remain in this release plan, not 26 proven defects.
Authority, chat, forms and
private-state work (03–08) can be developed independently of model experiments, but must
converge before final regression. Pass 19 is a matrix-driven closure sweep, not a new 200-slice build.

Start with policy/baseline and selection of the existing supported reasoning runtime, not another
specialist training marathon. Qualify one 4B profile end to end first, then reuse that pipeline
to qualify the 8B profile. Do not bundle failed research packs to satisfy a model count.
Keep specialist runtime closure and the future separate drafter out of the critical path.
Deferring specialists explicitly is allowed; claiming them complete is not.

Run cheap source/focused checks after each change; run expensive full regression after coherent
integration, real-model challenges when relevant behavior changes, and final packaging only
after source/model qualification. Reuse verified immutable inputs without duplicating them.

Suggested compact evidence root: `dist/release/ga-completion-20260916/evidence`.
Use one manifest linking the feature matrix, policy revision, runtime/model task reports,
hardware/installation evidence, UI results, security/recovery, full-suite report, package audit
and final decision. Proposed root only; this review did not create test/build artifacts there.

If model quality fails, repair the task pipeline or retrain with rights-cleared data and a new
holdout; do not lift admission gates. If an actual platform/rights/hardware prerequisite needs
an owner decision, report its exact missing artifact/action. Lawyer availability is not one
of those prerequisites under this plan.

## Completion statement required at the end

List accepted and hidden features, actual model identities/tasks and measured quality, source
snapshot, exact MSIX size/hash, test-level counts, installed/offline/upgrade results, recovery
instructions and all remaining limitations. Declare full planned GA only when retained tasks
and delivery pass. Otherwise state which axis remains blocked; no blanket “all 200 certified.”

## Implementation update — 2026-09-16

The first bounded general-reasoning vertical is now implemented in the current
worktree. The optional local-model dialog defaults to a curated, literal-loopback
Qwen route that permits only `qwen3:4b` or `qwen3:8b`; it keeps its fixed
`127.0.0.1:11434` origin even if a browser submits another endpoint. The host
requires a source reference, exact context approval, a completed matching model
identity, and a valid `[n]` source reference before it shows an answer. Otherwise
it withholds the model output and keeps review-required status visible.

Focused unit, API, mirror, syntax and compile checks pass. An opt-in real test
using only the repository's fictional-matter fixture completed through the
canonical API with the installed `qwen3:8b`. Direct fictional source-bound
acceptance also completed with `qwen3:4b` and `qwen3:8b`. This is runtime-path
evidence only: neither model has legal-quality, Maine-authority, specialist,
Store-package, frozen-app, or GA admission from these runs.

No model bytes, version, MSIX, external service, Git commit or publication was
changed by this implementation update.
