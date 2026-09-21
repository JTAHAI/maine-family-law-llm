# Make the local 4B/8B models useful task specialists

Status: foundation pass partially implemented; **not specialist-model quality or release-certified**.
Date: 2026-09-19. Repository: `D:\dev\Maine-Family-Law-LLM-github-main`.
Reviewed baseline: `main`, `115c0e247c0f61ab4a8b37f5f84f9741b8dce4cc`.
The tree was clean before this review. Only this planning document is added.

## Recommendation

Keep the existing Qwen3 4B and 8B route. First specialize the application's
task execution, source selection, output contracts and verification; then train
small task adapters against those same contracts and evaluate the deployed
quantizations. A task prompt is not trained weights, an exact quote is not a
verified conclusion, and a successful generation is not a successful user task.

Prioritize Evidence Review and Drafting. Do not start seven simultaneous training
campaigns or reopen the unrelated 200-feature backlog. Reuse the current scoped
API, approval/audit infrastructure, record/authority services and desktop UI.
Keep specialist training distinct from an ordinary user's installation: users
should choose a task in chat, not learn training or model-serving tools.

## Implementation update — first Evidence/Drafting foundation pass

Implemented 2026-09-19; this is a bounded source/runtime/UI pass, **not a
specialist-model quality admission or release decision**.

- Added a hash-bound host task profile for the curated 4B/8B Qwen route. The
  profile records the task, model class, output mode, prompt/output limits and
  review-only/non-admitted status in the approval binding and receipt metadata.
- Added an exact prompt-budget preflight. The desktop approval panel now blocks
  an oversized packet before it is transmitted and reports the remaining byte
  budget. The canonical and frozen-package source mirrors are kept identical.
- Reworked evidence selections to display the complete original sentence or
  paragraph around a selected phrase. Ambiguous repeated phrases are withheld;
  a short phrase can no longer render without a preceding negation or nearby
  qualification. The structured contract and verifier now agree on a 1,200
  character limit, and multiple distinct passages from one record are allowed.
- Added bounded, source-linked review cues (`possible_conflict`,
  `missing_material`, `qualification`, and related fixed categories). They are
  rendered as model suggestions to inspect, not factual findings. Drafting
  presents the same cues as a working-outline review list alongside its exact
  source material.
- Added cancel state to the curated Qwen client. Cancel prevents a late response
  from being rendered and requests release of the model; it deliberately does
  not kill the shared local Ollama service. The UI/API route records the run as
  canceled rather than accepting the late result.

Verification after the implementation:

- 132 focused API, UI, task-contract, span and new regression tests passed;
  0 failed, 0 errors, 0 skipped. JS syntax and Python compilation passed.
- Six opt-in canonical API runs completed against the installed `qwen3:4b` and
  `qwen3:8b` models across fictional missing-attachment, conflicting-record and
  attributed-drafting scenarios. All were review-required/exact-source outputs.
  The run took 65.854 seconds total. This shows the deployed path works; it does
  not qualify legal reasoning, factual completeness or trained-specialist quality.
- Evidence is retained under the repo-owned
  `dist/qa/qwen-specialists-pass01-20260919/` directory. No model download,
  training, package build, publication, push or private-data processing occurred.
- The curated Qwen selector now exposes only Evidence Review and Drafting. The
  remaining five task labels are not falsely presented as Qwen specialists.

## 1. What is actually present

- Optional local `qwen3:4b` and `qwen3:8b` through Ollama. The 9.0.1 MSIX does
  **not** bundle these weights; the in-chat setup downloads missing components
  with consent and can reuse existing installations.
- Seven host-owned task instructions in `legal/fast_interchange/specialists.py`:
  intake, evidence, authority, drafting, parenting, financial and safety/privacy.
  These are not seven fine-tuned Qwen models.
- Evidence and drafting both request the same `excerpts` JSON. The host rebuilds
  original quotations and withholds other model prose. Drafting currently yields
  source-bound working material, not a complete generative drafting specialist.
- Exact source approval, active-matter/session scope, encrypted audit receipts,
  review-required output, injection checks and hardware preflight already exist.
- `LocalAgentRunResult` explicitly does not certify factual claims, legal claims,
  relevance or current law. Preserve that honesty when adding richer outputs.
- Previous frozen/UI evidence establishes narrow fictional task execution. It
  does not establish broad evidence-analysis or drafting quality. The current
  release report also records missing clean-install, installed-MSIX and WACK proof.

### Confirmed constraints and repair priorities

| Finding | Source | Consequence / priority |
| --- | --- | --- |
| Exact substrings can omit a preceding negation | `legal/agent_runtime/qwen_review.py`, `legal/fast_interchange/evidence_output.py` | P1 source-presentation issue: exactness alone does not preserve meaning. |
| Provider accepts quote lengths up to 3,000 characters; verifier allows 600 | `providers.py`, `evidence_output.py` | P1 contract mismatch: an otherwise permitted model response can be withheld. |
| Verifier permits only one span per selected record and requires every record | `verify_selected_evidence_spans` | Cannot express multiple relevant passages or honestly mark an irrelevant record. |
| Context service permits up to 80,000 characters; curated provider rejects prompts over 5,000 UTF-8 bytes | `local_agent_context_service.py`, `providers.py` | Preview and execution have incompatible capacity; safe refusal but poor usability. |
| Evidence/drafting accept only private-record spans | `evidence_output.py`, `drafting_output.py` | Do not simply mix authority and records into the current contract. Implement typed lanes. |
| Qwen has no `cancel()` method; registration requires one | `providers.py`, canonical API preview/run/cancel | Current Qwen route does not advertise request cancellation. Unloading is not cancellation. |
| Every Qwen call uses `stream=False`, `keep_alive=0`, `think=False` | `providers.py` | No incremental progress from generation; repeated reloads; no task-specific reasoning policy. |
| Curated model binding identifies a tag/class/policy, not the installed immutable artifact digest | `providers.py`, `_local_agent_binding` | Installation pins must also bind execution; a matching response tag is insufficient. |
| Browser tool requests are correctly rejected; broker definitions are not automatic tool integration | canonical `/api/local-agent/run`, `tools.py` | New retrieval/calculation steps must be host-owned and scoped, not arbitrary model tools. |
| Seven tasks appear in the selector, but evidence/drafting are the narrowly hardened typed path | production `workbench.html`, `qwen_review.py` | Qualify each task separately; do not advertise all seven as proven specialists. |

Review reproductions used fictional strings only:

1. Source: `The receipt was requested, but no receipt was supplied.`
   Candidate quote: `receipt was supplied`. Current verifier returns
   `quoted_spans_bound_review_required`, no blocker, factual verification false.
   This is a verifier-level reproduction, **not evidence that a live model chose it**.
2. An exact 648-character quote is withheld with source/coverage blockers.
3. Two exact passages from the same source are withheld as invalid selection.

These issues should be repaired before increasing narrative freedom.

## 2. Target task behavior

| Task | What the person should receive | Model responsibility | Host responsibility |
| --- | --- | --- | --- |
| Evidence review | What each record says; possible conflicts; qualifications; missing material; exact source buttons | Candidate issue/relationship labels and concise attributed explanations | Immutable spans, dates/speakers, coverage inventory, duplicate handling and validation |
| Drafting | Editable outline and useful paragraphs with statement-level sources and explicit gaps | Organize and phrase supported material without changing its meaning | Approved fact ledger, citation resolution, revision history, review/export gates |
| Authority review | Plain-language answer from applicable admitted sources, including uncertainty and freshness | Explain the supplied authorities and identify limitations | Official-source retrieval, exact citation/span resolution, jurisdiction/currency checks |
| Intake / form assistance | A useful next-step checklist and reusable header suggestions | Classify the request and ask the most useful missing question | OCR confidence, confirmed fields, original/working-copy separation, no invented deadlines |
| Parenting-plan review | Schedule conflicts, ambiguous conditions and practical questions | Explain candidate conflicts and child-impact considerations | Time-zone/date calculations and exact order/plan terms; no custody prediction |
| Financial-disclosure review | Requested/produced/partial/missing matrix with transparent totals | Map document descriptions and explain gaps | Decimal arithmetic, units/periods, duplicate detection and source receipts |
| Safety/privacy review | Specific disclosure risks and previewable redactions | Suggest additional contextual risks | Deterministic identifier checks and protected-span rules; no automatic disclosure |

Evidence, allegations, court findings, legal authority and model interpretation
must remain distinct data types. Do not infer legal truth from an NLI score or
from agreement between 4B and 8B.

## 3. Execution batches: 18 bounded passes

Names marked **new** are proposed modules, not existing functionality. Each pass
must include canonical API integration, production chat interaction, scoped state
where needed, source/artifact opening, review status and focused tests. Do not
close a pass on backend code or a text-presence UI assertion alone.
The frozen build ships the `src/maine_family_law_llm` application/UI. Preserve
the repository's required root-package mirrors and test their parity; do not
implement a feature only in an unshipped frontend or an alternate API copy.

### Batch A — repair the task boundary first

**01. Versioned task profiles, artifact binding and quality baseline.**
Extend `legal/fast_interchange/specialists.py`, `legal/agent_runtime/providers.py`,
`legal/local_ai/installer.py` and `_local_agent_binding` in the canonical API.
Add **new** `legal/agent_runtime/task_profiles.py` and a versioned profile config.
Bind task, base digest, optional adapter digest, tokenizer/template, decoding,
output schema, context policy and verifier version into approval and receipts.
Resolve installed identity locally before preview and again before dispatch;
model/profile changes invalidate approval. Availability, integrity, measured task
quality and release permission remain separate states. Build a baseline runner
around `tests/test_curated_qwen_api_real.py` and `verify_qwen_frozen_workflow.py`;
do not depend exclusively on historical external PEFT evaluators.
Acceptance: changing a tag's underlying artifact fails closed; chat shows the
actual task qualification; measured baseline includes useful-task success, not
only JSON validity and refusal. Never mark an unmeasured task qualified.

**02. Meaning-preserving source spans and consistent contracts.**
Extend `contracts.py`, `qwen_review.py`, `evidence_output.py`, `drafting_output.py`.
Add **new** `legal/agent_runtime/span_catalog.py`. Host assigns stable span IDs
with record version/hash, original offsets, page/paragraph/OCR lineage and
adjacent context. Model selects IDs; host supplies quotation text. Eliminate
ambiguous first-occurrence `.find()` matching. Permit multiple nonduplicate spans
per source and explicit `not_relevant`, `insufficient_context`, `unprocessed`
coverage states. These are selection states, never proof of global absence.
Preserve complete clauses plus qualification/negation context; if boundaries are
uncertain, expand the displayed context or withhold the narrowed interpretation.
Use one shared length/schema policy from preview through verification.
Acceptance: the three reproduced cases have deliberate, tested behavior;
negations, exceptions, quoted replies and repeated phrases cannot silently
change displayed meaning. Every rendered span opens the correct original location.

**03. Token-budgeted, source-aware context assembly.**
Extend `app/services/local_agent_context_service.py`, `contracts.py` and provider
preview; add **new** `legal/agent_runtime/context_planner.py`. Count the actual
template, task instructions, source metadata, source tokens, question, schema,
reserved output and reasoning allowance. Use the pinned tokenizer when available;
otherwise use an explicitly conservative validated fallback, not an assumed
characters-per-token ratio. Expose the budget before approval. Start with short
issue-specific passages and neighboring qualifications; use bounded multi-pass
jobs for large selections, with a visible processed/remaining inventory.
Acceptance: an approved preview cannot later exceed its declared provider budget;
no silent truncation; page/source identities survive chunking and restart.

**04. Real Qwen cancellation and bounded progress.**
Extend `providers.py`, `app/services/local_agent_run_service.py`, canonical
preview/run/cancel and production `workbench.js`. Implement cancellable transport,
timeouts and owned job state; do not kill a user's shared Ollama service. Prove
that aborting transport actually stops that request on the pinned runtime.
Stream progress or validated result units, not unchecked prose or hidden reasoning.
Acceptance: cancel during load/generation/verification, matter switch, disconnect
and late completion all prevent a stale answer from appearing; other work survives.

### Batch B — deliver the two priority specialists

**05. Evidence comparison and coverage vertical.**
Add **new** `legal/agent_runtime/evidence_task.py` and a typed result contract.
Input is an approved question, immutable record selection and span catalog.
Output includes attributed statements, source pairs, possible conflicts,
qualifications, missing attachments and coverage limitations. Retrieve likely
counterevidence, not just passages supporting the question. Deterministic checks
handle exact times/amounts/identities; semantic relationships remain clearly
labeled model suggestions unless separately established. Save a review-required
artifact using existing matter encryption/audit conventions and reopen it in chat.
Acceptance: a fictional order/amendment/message/receipt set produces a useful
comparison with both sides and missing proof; no allegation becomes a finding;
unread records and duplicates cannot imply complete coverage or corroboration.

**06. Actual source-backed drafting vertical.**
Add **new** `legal/agent_runtime/drafting_task.py`; extend `drafting_output.py`
and reuse `legal/drafting` services. Separate three stages: approved fact/authority
ledger, editable outline, paragraph generation. Each factual sentence references
ledger entries and each legal proposition references admitted authority; link
checking is not semantic verification. Compare dates, numbers, parties, negations,
attribution and scope against those entries; flag uncertain paraphrases for review.
Templates may provide neutral structure, never invented case facts. Never remove
the current withholding rule globally to make generation appear successful.
Acceptance: create an editable, meaningfully useful draft from a fictional matter;
the missing receipt stays missing, requested actions do not become ordered actions,
and unsupported requested wording is flagged rather than silently included as fact.

**07. Authority-assisted reasoning and citation vertical.**
Reuse existing authority resolver, retrieval, freshness, quote/claim checks and
`CapabilityToolBroker`; add a typed authority-task handler, not an unscoped tool
agent. Bind any expanded source set into a new approval or the explicitly approved
host work plan. Keep private records and authority in separate result lanes.
Acceptance: current/unknown/stale/wrong-jurisdiction and nonexistent citations
produce distinct visible results; exact cited passages open; an unavailable
authority store cannot be replaced by model memory labeled as current Maine law.

**08. Save, revise and export the new task artifacts.**
Reuse encrypted matter persistence, draft revision/dual-view/export services and
the filing gate. Save candidate statements, user corrections, source hashes and
the task profile. Record/model/authority changes mark affected output stale.
Acceptance: review -> edit -> compare -> save -> reopen -> review-required export
retains source links and blockers; originals are unchanged; unsupported claims,
stale forms and incomplete review cannot be hidden by an alternate export route.

### Batch C — make it fast and easy on ordinary PCs

**09. Measured hardware routing and safe warm sessions.**
Extend `legal/model_orchestration/hardware.py`, `adaptive.py`, `providers.py` and
local-AI setup. Recommend 4B first; offer 8B for a measured quality benefit with
enough headroom. Use actual whole-app RAM/VRAM/context requirements and an explicit
user-approved profile. Keep one base resident for a short idle window where safe,
with release on low memory, switch, shutdown and an accessible unload action.
Weight residency is distinct from conversation/KV reuse: no private prompt cache
may cross matter boundaries. Do not silently choose another model after approval.
Acceptance: cold/warm p50/p95 latency, first useful output, memory peak and unload
are measured on CPU-only and GPU tiers; cross-matter canaries never leak; a real
low-memory refusal gives a useful non-model path rather than freezing the app.

**10. Task-specific decoding and optional deeper review.**
Move decoding into the versioned profiles. Keep fast constrained extraction as
default; benchmark a bounded thinking pass for hard comparisons, not every click.
Compare current settings with upstream-recommended settings on held-out tasks.
The current raw no-thinking template must not be retained unchanged for a thinking
profile. Pin and test the chat template/runtime response parser; reserve output
capacity, cap duration and show only a useful final explanation with source links.
Acceptance: quality improvement is measured per task at an acceptable latency;
incomplete reasoning never appears as a completed answer or leaks internal text.

**11. In-chat task guidance and corrective feedback.**
Extend the existing chat actions in `src/maine_family_law_llm/ui/workbench.js`
and `workbench.html`. Offer plain-language goals: compare records, explain a
source, prepare a draft, reuse form details. Ask one useful clarifying question
only when needed. Show reviewed source count, remaining coverage, next action,
progress, cancel and a concise result. Make corrections source-linked and locally
encrypted. Correcting an answer must NOT silently train or export private records.
Acceptance: a nontechnical user completes setup/reuse and a task without provider
names, paths or shell commands; keyboard/focus/zoom tests cover error and retry.

### Batch D — specialize the remaining assigned roles

**12. Intake and OCR-assisted repetitive forms.**
Reuse `legal/forms/header_suggestions.py` and existing intake/form-session services.
Let the model classify the task and propose missing questions; let OCR/source-bound
field extraction supply candidate court/docket/party fields. Require confirmation
before reuse, distinguish conflicting/OCR-uncertain values, and never overwrite an
original. Acceptance: scan -> exact crop/text -> confirmed header -> second form
reuse -> correction history works; wrong-matter and stale-form attempts fail closed.

**13. Parenting-plan review.**
Connect the existing task profile to exact order/plan spans and deterministic
schedule calculations. Show overlaps, ambiguous pickup conditions, holiday/date
conflicts and child-impact questions. Acceptance: conflicting orders, daylight
saving/time zones and missing agreement remain explicit; no inferred custody
award, credibility judgment or claim that a proposal is binding.

**14. Financial-disclosure review.**
Connect the task to request/response inventories, decimal arithmetic and document
periods. Acceptance: partial statement, missing months, duplicate bank record and
unknown value remain distinct; totals cite included items and exclusions; the
model cannot invent income, resolve contested ownership or silently change units.

**15. Safety/privacy review.**
Extend existing protected spans/redaction checks with task-specific suggestions.
Acceptance: source preview -> proposed redactions -> user confirmation -> safe
derivative; original remains intact, identifiers do not leak into logs/feedback,
and a model's failure to spot a risk never disables deterministic safeguards.

### Batch E — train, qualify and deliver genuine specialized weights

**16. Prove the serving/export path before substantial training.**
Use one tiny explicitly non-release adapter to verify the exact approved Qwen3
base revision -> PEFT training -> export/conversion -> target runtime path.
4B and 8B need separate compatible adapters; old 0.6B adapters are not transferable.
Do not assume the legacy BF16 fast-interchange worker or an Ollama model alias
provides Qwen3 adapter hot-swap. Verify load, swap, reset, hash identity and outputs
on the pinned serving build. If dynamic adapters are not supported reliably, use
a measured merged/quantized model per approved task or one validated multi-task
model, with the full disk cost shown. Never claim a shared base saves disk when
the chosen export physically duplicates it.

**17. Rights-cleared, task-balanced training and objective qualification.**
Build on `fast_interchange_workflow_training_data.py` only for protocol scaffolding;
its small templates do not establish domain competence. Add **new** dataset
manifest/builder/trainer/evaluator scripts in this repo. Start with diverse,
source-bound evidence and drafting examples, including successful useful answers,
counterexamples, false premises, corrections, long records, OCR noise and abstention.
Freeze training/development/blind-test separation by matter, document/template
family and near-duplicate cluster. Public-source access alone is not a dataset
license; record permission/provenance. No personal corpus enters public weights.

Train a 4B Evidence Review adapter first, then Drafting; use LoRA/QLoRA where the
measured hardware/runtime supports it. Start with a small diverse pilot and a
learning curve, not an arbitrary example-count target. Tune rank/sequence length/
batch accumulation using observed memory. Cache preprocessing once, retain bounded
checkpoints, resume safely and stop when held-out utility stops improving. An 8B
teacher can propose examples, but its answers are not gold without source checking.
Train 8B adapters only if baseline 8B still has specific measured gaps and the
benefit justifies training/inference/storage cost.

Evaluate base, workflow-specialized base, adapter-enabled and final quantized
serving artifacts with the SAME blind tasks. Include an adapter-disabled ablation.
Promote trained weights only if they improve useful-task performance without a
safety regression; unchanged weights or successful forward passes do not qualify.
Record base/adapter/dataset/template/runtime hashes and exact sample counts.

**18. Per-task admission, in-chat delivery and final package qualification.**
Extend existing model registry/catalog/install policy rather than invent a second
unscoped downloader. Bind each task/quantization/profile to its own quality report.
Reuse models already installed only after identity checks; display download/peak
disk costs; allow cancel/retry/rollback with no duplicate full-pack copies. Keep
failed tasks unavailable under their specialist names while useful ordinary chat
remains available. Run real canonical API, production UI, frozen executable and
isolated installed-MSIX journeys against exact final weights. Re-run full release
regression, offline/security/privacy, clean install/restart/upgrade and applicable
Store checks. Version/release claims follow evidence, not the existence of a pack.

## 4. Proposed acceptance gates — adopt before measuring candidates

These are proposed engineering gates, not claims of present capability or guarantees
about every future legal matter. No lawyer-volunteer dependency is introduced.

- At least 200 blind, distinct scenarios for each initially advertised evidence
  and drafting task, with represented adversarial categories and separate scores
  for each model/profile/quantization. Add new blind sets after tuning against failures.
- Zero critical failures on the release challenge set: fabricated citation or
  source, material negation reversal, wrong-party attribution, invented date/amount,
  allegation promoted to finding, cross-matter disclosure or filing-gate bypass.
- Proposed utility floor: at least 90% meaningful task completion and 95% correct
  source attribution/critical-detail preservation on eligible tasks. Publish exact
  denominators, per-category results and uncertainty, not a rounded aggregate alone.
  A known critical error blocks even if the aggregate exceeds these floors.
- Count unnecessary refusals, omitted counterevidence, unsupported specificity,
  follow-up burden and time-to-useful-output. All-refusal and all-quote output
  cannot pass a comparison/drafting usefulness test.
- Verify deterministic components mechanically; score semantic usefulness against
  independent source-bound rubrics, with maintainer review of critical cases.
  Model-based graders may assist but cannot solely approve their own outputs.
- Report CPU-only versus GPU measurements separately. Set per-tier response budgets
  from actual baseline measurements before claiming minimum hardware or speed.
- Save a compact result receipt per scenario; screenshots/DOM only where useful;
  no raw private prompts, repeated runtime copies or per-test base-weight copies.
- A new task/profile/version invalidates affected evidence. Unit/API success is
  separate from live inference, UI, frozen and installed-package success.

## 5. Source and validation notes

Current review ran:

```powershell
python -m pytest -q tests/test_qwen_review_hardening.py tests/test_fast_interchange_specialist_tasks.py -o cache_dir=dist/qa/qwen-specialist-plan-20260919/cache --basetemp dist/qa/qwen-specialist-plan-20260919/pytest --junitxml dist/qa/qwen-specialist-plan-20260919/results.xml
```

Result: **73 passed, 0 failed, 0 errors, 0 skipped**, JUnit time **1.881 seconds**.
Python was `C:\Python314\python.exe`; TEMP/TMP were explicitly repo-local and
bytecode writing disabled. The three additional direct verifier probes described
above are diagnostic reproductions, not included in the 73-test count.
No new live inference, training, model acquisition, application implementation,
MSIX build, commit, push or release certification occurred in this review.

Primary technical references checked on 2026-09-19:

- [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B) and
  [Qwen3-8B model card](https://huggingface.co/Qwen/Qwen3-8B): both list Apache-2.0;
  preserve the exact revision's license/notices. They document thinking/non-thinking
  modes and decoding recommendations, not Maine-law task qualification.
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs):
  schemas constrain shape, not the factual correctness of generated fields.
- [Ollama thinking](https://docs.ollama.com/capabilities/thinking): inspect support on
  the actual installed version; do not assume current web docs match every client.
- [Ollama import](https://docs.ollama.com/import) and
  [Modelfile reference](https://docs.ollama.com/modelfile): validate the intended
  export/import path; this review did not establish Qwen3 adapter hot-swap support.
- [Hugging Face PEFT quantization](https://huggingface.co/docs/peft/main/en/developer_guides/quantization):
  adapter training with quantized bases is an available approach, not a guarantee
  of fit on this device. Pin a tested stable training/runtime dependency set.

## First implementation batch

Implement passes **01–04**, then immediately deliver **05–06** against a blind
evidence/drafting set. Do not spend another cycle training weights around the
current quote-only contract. Run the small serving-compatibility experiment in
pass 16 before committing to a large training job. Keep all generated work inside
one bounded `dist` area under this checkout, as required by `AGENTS.md`.

## Implementation update — 2026-09-19

The first bounded implementation pass is in the current working tree.  It adds
hash-bound task profiles, exact byte-budget preflight, sentence-context expansion
for selected phrases, bounded model review cues, source-bound Drafting outline
sections, response-discard cancellation, and UI disclosure that only Evidence
Review and Drafting are current local-Qwen workflows.  The new Drafting headings
are a fixed host vocabulary and point only to revalidated record extracts; they
cannot contain model-authored allegations, factual findings, or legal analysis.

Focused static and API regression on this checkout: **134 passed, 0 failed, 0
errors, 0 skipped** in 6.600 seconds.  Evidence: `dist/qa/qwen-specialists-pass02-20260919/results.xml`.

The opt-in six-case real-Ollama canonical-API run was attempted after this
change and **did not establish live inference**.  All six calls failed closed
with `local_model_unavailable`; no response was accepted or rendered.  At that
time no listener existed at `127.0.0.1:11434`, even though the installed Ollama
executable and `ollama serve` processes were present.  Direct Ollama diagnostics
reported that configured model path `D:\\OllamaModels` was not accessible and
timed out waiting for the server.  This is an environment/runtime blocker, not
evidence that either Qwen model completed an end-to-end run.  Receipts:
`dist/qa/qwen-specialists-pass02-20260919/live/results.xml` and the six
fictional-only response receipts in that same directory.

Do not call Evidence Review or Drafting model-qualified, specialist-trained,
frozen-app verified, package verified, or GA-ready until the loopback runtime is
repaired and the planned blind quality and deployment gates pass.

The local service was then restarted with the existing per-user model library
configuration (no model was downloaded, replaced, or altered).  The same six
fictional canonical-API cases then passed: **6 passed, 0 failed, 0 errors, 0
skipped** in 76.684 seconds.  This proved the loopback route, model identity,
matter scope, approval token, encrypted audit, source-span verification and
review-required rendering for `qwen3:4b` and `qwen3:8b`; it also exercised the
Drafting outline parser where the model supplied a permitted section.  Evidence:
`dist/qa/qwen-specialists-pass02-20260919/live-repaired/results.xml`.  It is
fictional-only canonical-API evidence—not blind task-quality, production desktop
UI, frozen package, or legal-specialist certification.

## Authority-specialization implementation update — 2026-09-20

The current local-Qwen contract now includes **Authority Review** as a third
host-bounded workflow. It accepts only fresh, host-verified immutable official
Maine authority source spans; the model can select literal passages but cannot
write a legal conclusion, establish current law, resolve jurisdiction, select
controlling authority, or determine application to a person or matter. The same
approval token, active-matter scope, encrypted audit receipt, source-card
drill-down, fixed loopback route, identity validation, and review-required
rendering apply. Stale, non-official, changed, incomplete, or unverified
authority is withheld before rendering.

Focused compile, production-JavaScript syntax, API/UI, source-binding, and
authority-boundary regression: **117 passed, 0 failed, 0 errors, 0 skipped**
in 21.579 seconds. Evidence:
`dist/qa/qwen-maine-authority-pass01-20260920/results-final2.xml`.

No external authority data root is configured in this environment, so this pass
did not run the new workflow on actual official Maine material and did not train
or alter any model. The next real specialization prerequisite is a versioned,
external official-authority build that passes the existing ingestion, freshness,
parser, provenance, and public-data training-policy gates. That data product,
plus the blind task-quality gates in this plan, remains required before calling
either model Maine-law specialized or release-qualified.

## Authority provenance tightening — 2026-09-20

Authority Review now requires more than a source-status label.  An immutable
authority build retains a public official-source URL and jurisdiction in each
snapshot record.  Before a local model sees an authority passage, the host
rechecks that the active immutable build has an admitted public URL, Maine
jurisdiction, fresh status, hash-bound source text, and lineage with no
provenance blockers. The approval/source card exposes only safe provenance
fields (official URL, jurisdiction, retrieval time, parser status, snapshot
hash, and build ID), never local paths. A model-selected passage is withheld
when any of that chain is absent or changes.

Focused compile, production JavaScript syntax, UI/API lifecycle, Qwen boundary,
and immutable host-source regression: **118 passed, 0 failed, 0 errors, 0
skipped** in **30.149 seconds**. Evidence:
`dist/qa/authority-provenance-pass02-20260920/results-final.xml`.

The fixture used by the broader immutable-authority suite is intentionally
rejected when a test runner locates the authority root inside this repository;
that is the production external-data boundary functioning as designed, not a
release pass. The host-binding suite models its source product as an external
authority sibling and passed under the repository-local QA workspace. No live
authority source, training corpus, model weights, package, or release claim was
created by this change.

## Installed-model identity binding — 2026-09-20

The curated local-Qwen route now obtains the selected model's exact digest and
installed size from Ollama's literal-loopback `/api/tags` inventory at preview,
again at dispatch, and once more before accepting a result. Both known Ollama
digest encodings (bare 64-hex and `sha256:<hex>`) normalize to one strict
identity; short prefixes and missing/duplicate inventory entries are blocked.
The approval binds that identity, and a changed tag/digest withholds the result.
The preview tells a person that the installed artifact was checked and shows a
short digest without suggesting that integrity equals legal quality.

Focused mock/HTTP/API/UI/source-bound regression: **86 passed, 0 failed, 0
errors, 0 skipped** in **25.129 seconds**. Evidence:
`dist/qa/qwen-artifact-identity-pass03-20260920/results.xml`.

The opt-in real canonical-API matrix then passed all six fictional scenarios
against the installed `qwen3:4b` and `qwen3:8b` models with the new digest
binding: **6 passed, 0 failed, 0 errors, 0 skipped** in **69.194 seconds**.
It covered missing attachment, conflicting records, and attributed drafting;
each run bound the local artifact, matter scope, one-use approval, encrypted
audit, exact source excerpts and review-required rendering. Evidence:
`dist/qa/qwen-artifact-identity-pass03-20260920/live-repaired/results.xml`.
This is fictional-only local runtime evidence. It does not show model training,
Maine-law expertise, blind legal-quality evaluation, desktop/frozen-package
reachability, Store qualification, or GA admission.

## Result-receipt identity and task disclosure — 2026-09-20

The completed local-model result now repeats the exact installed-artifact
binding and its task boundary inside the hash-bound receipt, rather than
leaving that information only in the pre-run approval dialog.  The receipt
shows a short installed-artifact digest only when the API supplied a complete
identity; otherwise it explicitly says no identity was recorded.  It also
labels the host-bound task, source-bound scope, and the fact that artifact
integrity is not legal-quality certification.  This prevents a copied result
from looking more qualified than the approved run that produced it.

Focused production-UI lifecycle, local-agent API, and grounding regression:
**33 passed, 0 failed, 0 errors, 0 skipped**. Production and mirrored
JavaScript syntax checks, Python compilation, `git diff --check`, and exact
production-UI mirror comparison also passed. Evidence:
`dist/qa/receipt-artifact-binding-pass05-20260920/results.xml`.

This is an integrity and usability improvement only. It does not supply a
rights-cleared authority corpus, trained Maine-law specialist, blind
quality evaluation, frozen-runtime evidence, package qualification, or GA
admission.

## Authority-result source drill-down — 2026-09-20

The final answer's inline authority cards now recognize the same admitted
`official_source_url` that was presented for approval. A person can therefore
open an authority's public source from the completed review-required result,
without hunting for or recreating the preview. The existing safe URL validator
still permits only HTTP(S), so a record-supplied path, active content URI, or
other scheme cannot become a link.

Focused source-card, source-bound local-agent, API/UI lifecycle, Qwen boundary,
and grounding regression: **115 passed, 0 failed, 0 errors, 0 skipped**. The
two production JavaScript mirrors passed syntax checks, their hashes matched,
and `git diff --check` passed. Evidence:
`dist/qa/authority-result-drilldown-pass06-20260920/results.xml`.

This makes provenance easier to inspect; it does not change source admission,
prove authority currency, or qualify the underlying local model for legal use.

## Evidence-review coverage inventory — 2026-09-20

Evidence Review can now return a fixed-vocabulary, complete coverage inventory
alongside its exact selected excerpts: `selected_excerpt`, `not_relevant`,
`insufficient_context`, or `unprocessed`. The host accepts this inventory only
when every approved record is represented exactly once and every selected
excerpt agrees with its state. Without a complete inventory, the existing
all-record exact-excerpt rule remains in force. Invalid, incomplete, duplicate,
or mismatched coverage remains withheld.

Coverage is displayed in the source-bound answer and result receipt as a model
suggestion—not a completeness finding. In particular, a record marked with no
excerpt never establishes absence or irrelevance. This gives a person a useful
review queue without allowing a small model to silently erase counterevidence.

Focused structured-output/parser, exact-span, UI lifecycle, API, source-binding,
and grounding regression: **146 passed, 0 failed, 0 errors, 0 skipped**. Python
compilation, production JavaScript syntax, mirror equality, and `git diff --check`
passed. Evidence:
`dist/qa/evidence-coverage-inventory-pass07-20260920/results-full.xml`.

No live model inference or legal-quality claim was made for this change. A
rights-cleared corpus and blind quality gate remain prerequisites for specialist
admission.

## Measured 8B timeout recovery — 2026-09-20

The opt-in fictional canonical-API run was repeated after the coverage change.
`qwen3:4b` completed all three scenarios (missing attachment, conflicting
records, and attributed drafting): **3 passed, 0 failed** in 53.509 seconds.
On this machine, `qwen3:8b` completed the attributed-drafting scenario in
92.023 seconds but timed out at the existing 120-second safety limit for the
two Evidence Review scenarios. Those two results were correctly withheld; no
partial response was rendered or accepted. Evidence is retained in
`dist/qa/evidence-coverage-inventory-pass07-20260920/live-qwen3-4b/` and
`dist/qa/evidence-coverage-inventory-pass07-20260920/live-qwen3-8b/`.

The runtime and UI now give a clear fail-closed recovery route for a timed-out
curated 8B run: sources remain unchanged, no automatic model switch occurs,
and the person can intentionally retry with fewer passages or choose 4B. This
is a local performance observation, not a claim that 4B is legally better.

Focused timeout, parser, API/UI, source-binding, exact-span, and grounding
regression: **147 passed, 0 failed, 0 errors, 0 skipped**. Python compilation,
production JavaScript syntax, UI mirror equality, and `git diff --check`
passed. Evidence:
`dist/qa/qwen-8b-timeout-recovery-pass08-20260920/results-full.xml`.

The current 8B timeout is a release-relevant usability limitation for this
device's Evidence Review route. It has not been hidden or relabeled as a model
quality result, and neither model is a Maine-law-qualified specialist.

## Plain-language 4B-first guidance — 2026-09-20

The production local-model chooser now describes 4B as the recommended first
option for lower-memory local review, without promising a fast response. It describes 8B as larger and
potentially slower, and explains before approval that a late output is withheld
and the app never silently changes the selected model. This is a recovery and
expectation-setting improvement based on the measured runtime result above; it
does not rank legal quality or claim either general model is a specialist.

Focused task-profile, local-agent API/UI lifecycle, and grounding regression:
**51 passed, 0 failed, 0 errors, 0 skipped**. Production HTML/JavaScript mirror
checks, syntax checks, Python compilation, and `git diff --check` passed.
Evidence: `dist/qa/qwen-8b-guidance-pass09-20260920/results.xml`.

## Bounded Qwen selection output — 2026-09-20

The source-selection profile now caps model generation at 768 tokens instead of
2,048. The approved task needs constrained JSON selection, not a long
free-form answer; the host subsequently renders only rechecked source text. The
cap is part of the hash-bound task profile and is sent to the local runtime as
`num_predict`, so a profile change invalidates a prior approval.

After this change, one repeat of the fictional 8B missing-attachment journey
completed with a source-bound, review-required result rather than timing out.
Measured elapsed time was still **121.295 seconds**, so this is not evidence
that 8B is fast enough for ordinary use on this device. 4B remains the
recommended default; no silent fallback was added.

Focused regression: **147 passed, 0 failed, 0 errors, 0 skipped**. An opt-in
real canonical-API 8B journey also passed (fictional-only; no quality claim).
Evidence: `dist/qa/qwen-output-budget-pass10-20260920/results-full.xml` and
`dist/qa/qwen-output-budget-pass10-20260920/live-qwen3-8b-missing/`.

The task-profile and execution-policy revisions were also advanced to v2/v8,
respectively. A saved preview from the preceding contract cannot be reused for
this changed selection/coverage policy. Focused profile and HTTP-boundary tests:
**37 passed, 0 failed, 0 errors, 0 skipped**. Evidence:
`dist/qa/qwen-profile-version-pass11-20260920/results.xml`.

## Official-source link policy — 2026-09-20

Authority-review result cards now pass the public-source URL through the same
`safeExternalUrl` allow-list used by the rest of the production workbench
before rendering a user-clicked "Open official source" action. This replaces a
weaker scheme-only check and keeps local paths, non-web schemes, and malformed
values out of the UI. The underlying authority result remains review-required;
the link is provenance drill-down, not an endorsement or a legal conclusion.

Focused UI/API regression: **11 passed, 0 failed, 0 errors, 0 skipped**.
Production and mirror JavaScript syntax, Python compilation, mirror parity, and
`git diff --check` also passed. Evidence:
`dist/qa/authority-preview-url-policy-pass12-20260920/results.xml`.

## Official-authority host boundary — 2026-09-20

The local-model authority lane now requires HTTPS, an admitted Maine official
host, no URL credentials, and only the default HTTPS port before host-verified
authority text can enter a local-model context or be rendered as an authority
extract. A forged `admitted` label paired with an arbitrary, downgrade, or
lookalike URL is withheld. This is a provenance and privacy boundary; it does
not establish that any model is a Maine-law specialist.

Focused authority, context, API/UI, and verifier regression: **92 passed, 0
failed, 0 errors, 0 skipped**. Python compilation and `git diff --check`
passed. Evidence:
`dist/qa/official-authority-url-boundary-pass13-20260920/results.xml`.

## User-clicked external-link boundary — 2026-09-20

The production workbench now rejects source-card links with embedded
credentials or loopback hosts in addition to active and file schemes. Opening
an admitted public source remains an explicit user action; the app does not
fetch it. This prevents model or record metadata from presenting a deceptive
or local-service URL as an external source action.

Focused production UI/API regression: **30 passed, 0 failed, 0 errors, 0
skipped**. Both JavaScript bundles passed syntax checks, their hashes matched,
and `git diff --check` passed. Evidence:
`dist/qa/external-link-boundary-pass14-20260920/results.xml`.

The official-host predicate also has direct regression coverage for normal
official HTTPS URLs and rejected downgrade, credential-lookalike, and nondefault
port variants. Combined authority and production-UI regression: **37 passed,
0 failed, 0 errors, 0 skipped**. Evidence:
`dist/qa/authority-url-and-ui-polish-pass15-20260920/results.xml`.

## Source-bound local-AI regression checkpoint — 2026-09-20

The consolidated deterministic regression covers source-card safety, curated
task profiles, encrypted matter-scoped approval/audit flow, artifact identity,
provider loopback boundaries, cancellation/late-result handling, exact spans,
authority provenance, and review-required output states. It uses fictional test
records and transport doubles; it is not a legal-quality evaluation or an
assertion that either general Qwen model is a qualified Maine-law specialist.

Result: **159 passed, 0 failed, 0 errors, 0 skipped**. Production/mirror API,
HTML, and JavaScript assets matched; Python compilation, JavaScript syntax, and
`git diff --check` passed. Evidence:
`dist/qa/source-bound-local-ai-regression-pass16-20260920/results.xml`.

## HTTPS authority-status consistency — 2026-09-20

The general authority-status verifier now uses the same strict official-Maine
HTTPS predicate as the local-model authority boundary. An HTTP downgrade can no
longer receive an official-Maine status merely because its host name matches.
This is source-integrity hardening, not a freshness update or a current-law
determination.

Focused authority, source-bound local-model, and verifier regression: **86
passed, 0 failed, 0 errors, 0 skipped**. Python compilation and `git diff
--check` passed. Evidence:
`dist/qa/authority-verifier-https-pass17-20260920/results.xml`.

## Local-only and privacy regression checkpoint — 2026-09-20

The security regression was made portable for the repository-only QA policy:
its synthetic matter remains outside its *configured synthetic project root*,
and it copies only the non-private injection-policy fixture required by that
test route. The production rule is unchanged: a real matter store must be
outside the real source checkout.

The focused suite exercised outbound network denial, injection/tool denial,
encrypted matter isolation, backup/restore integrity, session and tenant
scope, parser attacks, filing-gate false passes, and local-only workflow
boundaries. Result: **92 passed, 0 failed, 0 errors, 0 skipped**. This is
deterministic local security evidence, not Store, Enterprise, legal-quality, or
specialist-model certification. Evidence:
`dist/qa/local-only-security-boundary-pass18-20260920/results.xml`.

## Real local Qwen 4B canonical-API checkpoint — 2026-09-20

Three opt-in, fictional-only runs completed through the canonical API against
the already-installed `qwen3:4b` loopback artifact: missing attachment,
conflicting records, and attributed working-draft review. Each retained
matter-scoped source references, encrypted audit/approval flow, exact-span
verification, artifact binding, and visible review-required status. No model
download, external authority access, or user matter was used.

Result: **3 passed, 0 failed, 0 errors, 0 skipped**. Measured end-to-end test
durations were 43.463s, 64.514s, and 44.949s. This proves the constrained
fictional runtime path, not response speed suitability, Maine-law quality,
specialist training, admission, or legal correctness. Evidence:
`dist/qa/qwen4b-canonical-api-pass19-20260920/`.

## Runtime-expectation and task-availability polish — 2026-09-20

The actual Qwen 4B runtime measurement above showed 43–65 second fictional
reviews on this device. The UI no longer calls 4B "faster"; it presents it as
the lower-memory first choice and says either model may take a minute or more.
When the curated Qwen provider is selected, unsupported task names are now
hidden rather than merely disabled. The API remains the final enforcement
boundary, so a manipulated browser request still cannot invoke an unavailable
Qwen task.

Focused UI, source-bound task, and grounding regression: **56 passed, 0
failed, 0 errors, 0 skipped**. Production/mirror HTML and JavaScript matched;
JavaScript syntax, Python compilation, and `git diff --check` passed. Evidence:
`dist/qa/qwen-runtime-expectations-pass20-20260920/results.xml`.

## Official-authority link parity — 2026-09-20

The pre-run local-model approval dialog now applies the same strict host,
HTTPS, and default-port predicate as the server before it renders an "Open
official source" provenance link. A generic public URL can still be presented
in ordinary source preview only after a person clicks it, but it cannot acquire
the stronger official-authority label in the approval dialog. The canonical API
also has a regression guard proving a crafted request cannot select a curated
Qwen task that the UI hides.

Focused UI, canonical API, authority-verifier, and source-bound output
regression: **50 passed, 0 failed, 0 errors, 0 skipped**. Production/mirror
JavaScript hashes matched; both bundles passed syntax checks and `git diff
--check` passed. Evidence:
`dist/qa/official-authority-ui-boundary-pass23-20260920/results.xml`.

## Quarantined-document transmission proof — 2026-09-20

The canonical preview-and-run test now proves the transmission boundary, not
only the approval UI: an instruction-like fictional record remains available
for human inspection, is visibly identified as quarantined, and reaches the
local worker only as an offset-preserving masked projection. The hostile text
cannot appear in the worker prompt or be reframed as filing-ready output.

Focused source-binding, privacy, and curated-Qwen regression: **80 passed, 0
failed, 0 errors, 0 skipped**. Python compilation and `git diff --check`
passed. This is a deterministic safety check, not a legal-quality or model
admission result. Evidence:
`dist/qa/quarantined-document-transmission-pass24-20260920/results.xml`.

## Pre-dispatch cancellation proof — 2026-09-20

The canonical local-agent cancellation route is now covered through the
matter-scoped HTTP flow. A canceled preview invokes the registered local
client's cancel method, records a review-required receipt, and prevents the
single-use approval from dispatching a later model request. This does not claim
that a shared local inference server can terminate every underlying process;
it proves that a canceled result is not accepted by the workbench.

Focused source-binding, curated-Qwen, and cancellation regression: **88
passed, 0 failed, 0 errors, 0 skipped**. Python compilation, production
JavaScript syntax, and `git diff --check` passed. Evidence:
`dist/qa/local-agent-cancel-boundary-pass25-20260920/results.xml`.

## Source-metadata prompt boundary — 2026-09-20

Human-readable source titles and locators remain in the approval manifest and
source drill-down, but are no longer transmitted to local models. Filenames,
OCR labels, and other metadata can be user-controlled; omitting them closes a
second, unscanned instruction channel while preserving the host-normalized
source ID and numbered citation reference the constrained output contract
needs.

Focused runtime, source-binding, curated-Qwen, and specialist-contract
regression: **130 passed, 0 failed, 0 errors, 0 skipped**. Python compilation
and `git diff --check` passed. This is prompt-boundary hardening, not legal
quality or specialist-model admission. Evidence:
`dist/qa/source-metadata-prompt-boundary-pass28-20260920/results.xml`.

## Official-source-card label boundary — 2026-09-20

All production UI actions labeled "Open official source" now use the same
strict Maine-authority HTTPS host predicate as the canonical provenance path.
An ordinary public URL can remain safely previewable where appropriate, but it
cannot inherit an official-authority action label merely because an item was
placed in the law lane.

Focused UI, canonical local-agent, error-boundary, and source-verifier
regression: **53 passed, 0 failed, 0 errors, 0 skipped**. Production/mirror
JavaScript hashes matched; syntax and `git diff --check` passed. Evidence:
`dist/qa/official-source-card-label-boundary-pass29-20260920/results.xml`.

## Consolidated source-bound hardening checkpoint — 2026-09-20

The current focused regression combines canonical local-agent runtime and
approval flow, exact source binding, curated-Qwen constraints, production UI
and error safety, authority provenance, privacy, and verifier boundaries. It
uses deterministic fictional fixtures except for the separately recorded
opt-in Qwen 4B runtime checkpoint. It does not establish Maine-law quality,
specialist admission, attorney review, Store readiness, or Enterprise GA.

Result: **128 passed, 0 failed, 0 errors, 0 skipped**. Python compilation,
both production JavaScript syntax checks, production/mirror JavaScript hash
comparison, and `git diff --check` passed. Evidence:
`dist/qa/source-bound-local-ai-hardening-final-pass30-20260920/results.xml`.

The remaining release-quality prerequisites are external: a rights-cleared,
admitted Maine authority corpus tied to model training; qualified hidden legal
evaluation; and the required human/legal and release-admission evidence. No
general Qwen runtime or synthetic test is represented as satisfying those
requirements.
