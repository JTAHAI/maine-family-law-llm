# Compact specialist implementation — 2026-09-08

Status: implementation in progress; no specialist is GA-qualified.

Latest hardening pass: 2026-09-09. Resume **Installed serving-path ownership reconciliation**
at the end before repeating any model run. Historical sections retain
their original results; the latest section controls the immediate next action.

Current headline: new document-workspace indexes and draft revisions are now
encrypted, including temporary write contents, using the existing protected-key
envelope. Canonical filing-packet readers and both production UI mirrors have
been updated. The shipped-page fictional save/reopen and legacy read-only flow
passes; this is not a live model, frozen-app or installed-package result.
Legacy documents remain read-only until explicit confirmation. The actual UI now
supports inventory/hash review, confirmed draft-JSON conversion, encrypted exact
original recovery copies, authenticated interrupted-transaction recovery and
reopen/editing. New review packets and reviewer decisions are also encrypted;
their filing/authority consumers use a canonical authenticated reader. Other
private sidecars, large-matter performance/cancellation,
operator recovery UX and frozen/installed qualification remain open; Drafting
is not declared fully hardened. No specialist model has been promoted by this work.
No specialist is production-admitted. Do not repeat completed acquisition,
unchanged inference challenges or previously verified handoff tests as new proof.

Scheduled continuation: `mfl-compact-specialist-ga-hardening` runs
every 30 minutes. The next run must resume this report, not the old 200-slice
queue. Do not repeat completed acquisition or treat a transport/quote test as
semantic feature acceptance.

Owner request: deliver useful local Evidence Review and Drafting specialists,
each below **1,500,000,000 bytes including model dependencies**, with automatic
hardware checks. Reuse shared bases, keep all working data under this repo's
`dist`, preserve original files, and measure actual outputs rather than promote
models from unit tests. Public model acquisition and runtime integration are
authorized. No private corpus or proprietary Mainely Code assets are involved.

## Selected candidates

- Official `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, revision
  `91cad51170dc346986eccefdc2dd33a9da36ead9`, Q5_K_M weight file
  1,285,494,304 bytes. Apache-2.0 LICENSE included. Generic candidate for
  source-bound generation/adaptation; not a pretrained Maine specialist.
  Selected because the official Qwen3-1.7B GGUF only provides Q8 exceeding the
  cap, while the previously suggested Q4 conversion has no explicit license
  file/card declaration at its inspected revision.
- `narcolepticchicken/legalbenchrag-cuad-topone-reranker`, revision
  `ce341fa4fce71a445664ed382fd77ff65fc4806c`, complete selected inventory
  91,584,034 bytes; safetensors. Card declares Apache-2.0, base
  `cross-encoder/ms-marco-MiniLM-L6-v2`; training corpus CUAD attribution is
  required. This contract-passage scorer is not a legal truth verifier.
- Runtime: official llama.cpp CPU x64 b10865, source commit
  `d4389a4dd920d24c9592f1dc3badbd69be23bd09`; release ZIP 18,426,211 bytes,
  SHA-256 `c78058e6baac37e8b0cd3d1da1407ea9677f8d10c5281b3ba94d6dfa4a0265ae`.
- Comparison generator: `unsloth/Qwen3-1.7B-GGUF`, revision
  `d7f544eead698dbd1f15126ef60b45a1e1933222`, Q6_K weights
  1,417,755,200 bytes. Converter card declares Apache-2.0; the matching upstream
  Qwen LICENSE is downloaded and hash-verified at an immutable revision. Complete
  selected model + CPU engine is 1,459,100,999 bytes (plus the 1,078-byte engine
  license). Still a general-model candidate, not trained Maine-law expertise.

## Current work

`scripts/acquire_compact_model_candidates.py` downloads only pinned allowlisted
files into `dist/model-candidates/compact-fleet-20260908`, verifies publisher
hashes and exact sizes, checks disk space, resumes partial downloads, and records
acquisition receipts. It does not change production admission.

The existing PEFT backend supports FP32/FP16/BF16 only, and requires a single
safetensors base plus LoRA. Its signed schema cannot be relabeled GGUF. Integrate
a separately validated runtime path; preserve existing admission semantics.
Existing research adapters for Qwen3-0.6B cannot attach to the new Qwen2.5 base.

## Completion sequence

1. Acquire exact candidates and runtime; verify byte/hash/license inventories.
2. Bounded CPU generation and reranking with actual fictional inputs. Check
   context bounds, memory headroom, safe cancellation, restart and source spans.
3. Compare raw answers to existing failures and independently worded fictional
   cases. Preserve failures. Correct task behavior and evaluate again with a
   fresh holdout; model size alone is not evidence of quality.
4. Integrate approved runtime format into canonical host/API/production UI,
   source/provenance and review checks. Separate neural relevance from authority
   priority, exact citation/quote validation, and legal status.
5. Verify real UI journeys, keyboard/errors/cancellation, offline behavior,
   matter isolation, restart, frozen reachability and final package boundaries.
6. Only after all declared release gates pass, create the requested v9 MSIX
   containing the qualified models and publish an accurate final evidence report.

No MSIX, model admission, signing, training, UI acceptance or legal quality claim
has been completed by the acquisition step.

## Implemented and measured in this pass

- `legal/fast_interchange/compact_cpu.py`: real CPU GGUF inference under a
  three-GiB process budget and four-GiB available-memory startup gate, two CPU
  threads, 2,048-token context, 384-token completion bound, authenticated
  loopback-only native requests, fixed endpoints, no tools/download/provider
  discovery, no prompt logs, exact file hashes held under write-denying locks.
  No model/runtime snapshots are copied on each request.
- Windows Job Object: native process starts suspended, receives kernel memory
  and single-process limits, then resumes. Closing/crashing the owner kills the
  worker. Real abrupt-host-termination proof passed; worker shutdown was about
  0.22 seconds. Unrelated Ollama was neither closed nor modified.
- Cancellation drains the owned HTTP thread before reuse; undrained transport
  quarantines the worker. Context slot erasure is validated before/after each
  successful request. Cancellation, restart and clean shutdown were observed.
- Corrected chat-role separation and quote-reference placement. Source text
  stays in the user-data role; existing source/injection/output gates remain
  unchanged. No research candidate is registered in the production factory.
- `legal/fast_interchange/compact_reranker.py`: actual 92-MB contract-passage
  ranking on CPU, exact source hash/index in results, same-matter private-record
  scope, source length limits and safetensors-only local loading. The single
  three-passage smoke ranked the intended contract clause first. That is one
  narrow smoke, not a Maine relevance/entailment benchmark. Cold Python import
  cost varied (about 9–70 seconds); resident warm/ranked UI integration is NOT done.
- Downloads are pinned, size bounded, resumable and reused. GitHub CLI verified
  upstream runtime attestation against the exact ZIP. Eight unnecessary
  example/RPC DLLs (4,432,384 bytes) were removed after hash/process checks; the
  original ZIP remains recoverable. Engine MIT license is retained. OpenMP and
  transitive-notice review remains open.
- Added `requests` to the declared fast-interchange optional dependencies.

## Exact verification levels and failures

All evidence below is under `dist/model-candidates/compact-fleet-20260908`.

| Evidence | Observed result | Boundary |
| --- | --- | --- |
| `regression-tests-02.xml` | 235 passed, one existing FastAPI/TestClient deprecation warning | Focused unit/service/security regression, NOT the full app suite |
| `canonical-api-tests-01.xml` | 2 passed on Qwen2.5 before later task-guidance changes | Actual weights through canonical TestClient handlers, explicitly injected research factory/hardware adapter; not production registration or desktop |
| `canonical-api-kernel-tests-02.xml` | 2 passed, 1 failed | Kernel crash drill and Evidence passed; Qwen2.5 Drafting returned only “Review required” and failed acceptance. Preserve this regression. |
| `canonical-api-kernel-tests-03.xml` | 1 passed, 2 failed | Historical free-form path: kernel crash drill passed; Evidence/Drafting changed exact source text. The newer narrow excerpt path below does not qualify these failed free-form tasks. |
| `cpu-smoke-05.json` | 4/4 quote-bound outputs; raw narrative still flawed | Quote correctness does not establish supported conclusions or usable drafts |
| `cpu-independent-06.json`, `quality-assessment-06.json` | Qwen2.5: 1 semantic pass, 1 partial, 6 failures / 8 | Agent-authored fictional challenge and assistant review; not attorney-reviewed gold |
| `qwen3-independent-07.json`, `quality-assessment-07.json` | Qwen3: 4 semantic passes, 4 failures / 8 | Better on absence/requests, still wrong source attribution and entry/export dates; no GA promotion |
| `native-crash-tests-02.xml` | 1 passed | Actual Qwen3 native worker dies when its verified owning interpreter is forcibly terminated |

Qwen2.5 peak native RSS was about 1.19 GiB. Qwen3 peak native RSS was about
1.62 GiB; its eight challenge answers took 20.4–33.2 seconds each on two CPU
threads. This was a 32-GiB development machine with deliberate CPU limits, not
proof on a physical low-end PC. No provider/model networking is intended by the
worker; OS-level zero-outbound observation is still required before qualification.

## Release-critical remaining work (resume here)

1. **Quality first:** Qwen3 is the better current comparison, but neither
   generator is accepted. Fix attribution and date-field reasoning, require an
   actual draft rather than echoed instructions, and ensure source formatting
   does not collapse to a disclaimer. Do not merely add more text to the same
   monolithic prompt; that caused a measured Qwen2.5 regression. A bounded
   structured task path or independently evaluated adaptation is the next
   implementation hypothesis. No fixture in these proof files is training data.
   The latest canonical failure is useful evidence: the source begins
   `Fictional family record: an attachment...`, but both generated quotations
   began `An attachment...`. Do not loosen exact-quote validation to make this
   test green; model-selected, host-rendered source offsets can avoid copying
   errors, but must be labeled extractive assistance, not completed free-form
   Evidence Review or Drafting. Raw-semantic defects remain separately open.
2. The CPU connector is **research-only**. Existing signed admission only
   supports PEFT/safetensors (`fast_interchange_hotswap_v1`), and the canonical
   hardware function expects Torch precision. Implement a separately signed
   native ABI/model+engine inventory and CPU hardware policy before production
   selection; do not call GGUF “BF16” or fabricate an adapter inventory.
3. Integrate only a qualified narrow capability into the existing production
   source-preview → consent → run → cancel → source-card → review-required UI.
   Preserve encrypted audit, token binding, matter/role checks and no-tools
   policy. Research handler injection is explicitly not frozen/UI reachability.
4. Reranker: isolate/warm its runtime, broaden actual ranking evaluation,
   preserve official-authority priority and all source IDs, then integrate the
   protected retrieval path. Relevance must never become factual/legal truth.
5. Complete native dependency/notices audit, actual zero-outbound observation,
   physical modest-hardware checks, full app regression, desktop/frozen/MSIX
   qualification. Build no replacement MSIX that claims these specialists are
   ready before the corresponding gates pass. Version remains 8.0.2.

The owner's existing `current_codebase.zip` and `test.zip` were untouched.
This pass's entire candidate/proof directory occupies about 2.86 GB, including
two distinct comparison generators, the small reranker and one shared engine;
no external scratch folders or duplicate frozen runtimes were created.

## Resume commands

Use `dist/build-env/store/Scripts/python.exe -B`, `PYTHONDONTWRITEBYTECODE=1`,
and explicit repo-local `--basetemp dist/qa/compact-specialist-regression`.
Lint/format tool is available through `C:/Python314/python.exe -B -m ruff`;
use `--no-cache` and only the changed files.

`scripts/verify_compact_specialists.py --candidate qwen3-compact-comparison
--fixture dist/model-candidates/compact-fleet-20260908/independent-fictional-cases-v1.json
--output <new JSON path in the same candidate directory>` runs real outputs.
Do not rerun unchanged failed cases without a concrete implementation hypothesis.

For opt-in real canonical handler/kernel tests set
`MFL_RUN_COMPACT_CPU_API_PROOF=1`, `MFL_COMPACT_PROOF_CANDIDATE`, and a new
`MFL_COMPACT_PROOF_RUN_ID` (e.g. `04`), then run
`tests/test_compact_cpu_api_real.py tests/test_compact_cpu_crash_real.py`.
Keep prior receipts. Default test runs explicitly skip these real-weight drills;
do not count those skips as model/production verification.

## Bounded reasoning, reset and warm-up pass — 2026-09-08

The 256-token Qwen3 reasoning profile did **not** improve qualification. The
eight existing fictional, non-training challenges produced 3 raw semantic
passes, 1 partial and 4 failures under assistant inspection; no attorney review
is claimed. Entry/event/export dates and real drafting actions still fail.
The host accepted only checked extracts, never the unchecked narrative.
Evidence: `qwen3-bounded-reasoning-08.json`, its JSONL journal, and
`quality-assessment-08.json`. Reasoning token counts were 255, 255, 255, then
zero for the other five answers. A configured maximum is not evidence that
reasoning occurred on every request.

The independent **A → B → A** native test passed: repeated requests had identical
answers and measured reasoning counts after slot erasure and an intervening
request. This does not establish a general reset guarantee or semantic quality:
the repeated answer itself swapped the event and entry dates. Evidence:
`reasoning-reset-01.json`; 1 real test passed in 75.213 seconds, native peak RSS
1,732,370,432 bytes. No raw reasoning is stored or displayed.

Repairs in this pass:

- `compact_cpu.py`: artifact-bound 0/256 reasoning profiles; fixed per-request
  reasoning limits and separated output; reject leaked thought tags, malformed
  tokenization, over-budget reasoning, and invalid token usage. Only allowlisted
  numeric usage reaches the host. Context accounting reserves completion space;
  no silent source truncation or production admission change.
- Added an explicit fixed-synthetic warm operation. The generic provider warm
  prompt was incompatible with this connector's host-envelope guard. The new
  path checks the exact READY response and clears prior diagnostic text; it does
  not transmit matter data or imply specialist admission.
- `legal/agent_runtime/runtime.py`: private records no longer carry misleading
  legal-authority freshness/admission fields in the model prompt. Their
  statements remain unverified; actual authority metadata remains visible.
  Source bodies and manifests are not mutated. This fixes lane semantics, not
  the model's broader difficulty separating metadata from quotations.

Exact latest results:

| Evidence | Result |
| --- | --- |
| `reasoning-regression-final.xml` | 237 passed, 0 failed, 0 skipped; 23.006 seconds; one existing FastAPI/TestClient deprecation warning |
| `reasoning-reset-tests-01.xml` | 1 real native reset test passed; 75.213 seconds; not semantic acceptance |
| `canonical-api-tests-04.xml` | 2 failed, 0 passed; 103.720 seconds; both warm operations succeeded, but both task outputs failed exact source verification |
| `canonical-api-evidence_review-04.json` | Model fabricated a quote combining source meaning and prompt metadata; withheld |
| `canonical-api-drafting-04.json` | Model changed lowercase `an` to `An` and quoted its generated request as if it were record text; withheld |

The canonical tests explicitly inject the research factory and CPU hardware
adapter; they do not exercise production selection, desktop or a frozen app.
All owned native workers shut down. No new weights, runtime copies, MSIX,
version changes, commits or uploads were made. Free space on D: was
150,039,633,920 bytes after this pass. Existing model files were reused.
Lint initially found four overlong new test strings; fixed without changing
their runtime content. The final targeted lint and Git whitespace checks passed.

## Structured source selection and comparative quality — 2026-09-08

The planned excerpt path is now implemented and exercised with actual weights
through the canonical handlers. **Production discovery remains closed.** This
is research integration, not desktop/frozen/installed E2E or full Evidence Review.

- `compact_extracts.py`: receives approved source objects directly, binds matter,
  content/privacy hashes and unique single-use approval; builds at most twelve
  sentence candidates per record. The model chooses an allowed integer, never
  writes the quote, offsets, source identity or admission status. An irrelevant
  record, protected input, stale source, changed approval, injection or overflow
  blocks the result. All selected records must be represented.
- `SourceBoundGenerationClient` / `SourceSelectionResponse` in `providers.py`
  preserve the ordinary provider interface. Only the new research connector opts
  into direct source-object dispatch after canonical scope/approval checks.
- `runtime.py` independently verifies the structured response's provider, task,
  declared mode and completion status. `verify_selected_evidence_spans` validates
  every source hash, exact offset, quote hash, privacy exclusion and reference.
  Embedded quotations no longer confuse the legacy quotation-delimiter parser;
  the original free-form verifier remains unchanged and strict.
- Exact source cards derive from verified spans, not a model-written list of
  references. Verifier exceptions fail closed. No source/matter metadata is
  reconstituted by parsing model prompts or user-controlled XML.
- Output clearly says **one selected passage per record, not a completeness,
  relevance, factual or legal verification**. It no longer claims discarded
  narrative existed when the model only chose IDs. No-selection feedback says
  that this does not establish absence and offers safe record/question recovery.
- Structured selection now uses fixed greedy decoding and no reasoning. The
  free-form chat sampling profile is unchanged. This did not fix the measured
  semantic failures; do not treat deterministic output as accurate output.

Evidence (all in the existing candidate directory, no new model copies):

| Evidence | Result | Meaning |
| --- | --- | --- |
| `extract-real-02.json` | 7/7 positive multi-passage cases; 2/2 pre-inference blockers; real cancel/replay/restart and shutdown pass | First agent-authored fictional selection challenge, not attorney-reviewed or training data |
| `extract-canonical-api-02.xml` | 1 passed, 1 Drafting parameter deliberately deselected | Real Qwen3 + embedded-quotation fixture through canonical handlers with explicit research factory/hardware injection |
| `extract-final-03.xml` | 320 passed, 0 failures/errors/skips, 39.238 s | Focused host/service/quote/draft/safety regression, not the full app suite |
| `extract-holdout-03.json` | 9/12 relevance; 2/2 no-relevant-record abstentions; 1/1 injection block; cancel/restart pass | Fresh harder fictional holdout exposed three model failures |
| `extract-greedy-04.json` | Same 9/12 relevance and three safety/abstention cases | Comparison after deterministic decoding; now a known regression set, not an unseen holdout |
| `reranker-holdout-01.json` | 11/12 relevance; 3 cases explicitly not evaluated | Actual 91,584,034-byte passage ranker; abstention is not calibrated or established |
| `extract-canonical-api-05.xml` | 1 passed, Drafting deliberately deselected | Latest greedy selection + honest output notice; canonical research path only |
| `extract-final-05.xml` | 323 passed, 0 failures/errors/skips, 23.276 s | Final focused regression after deterministic selection and recovery-message repairs |

Latest canonical test duration: 14.878 seconds. It proved actual model warm/run,
the embedded quotation, exact source card, encrypted four-event audit, replay
rejection, wrong-matter rejection and owned worker shutdown. The explicit test
factory/hardware injection is still necessary; no production UI proof is implied.
Final targeted Ruff checks, in-memory syntax checks for 29 Python files and
`git diff --check` passed. Existing unrelated whole-file formatting in the legacy
provider and quote-verifier files was not rewritten. All owned native workers
were stopped; unrelated model processes were preserved. D: had 148,610,351,104
bytes free at the last check; free-space changes alone are not attributed to
this run because other applications remain active.

The Qwen3 harder-set failures were a missed fictional child's matching passage,
selection of an old amount instead of its correction, and confusion among
delivery/export/entry fields. Greedy decoding preserved those failures. The
small ranker corrected the first two but still selected the delivery mention
instead of the register entry date. No result was promoted to a verified fact.

The ranker's first case took 29.437 seconds including Python/Torch imports;
subsequent cases took 0.234–0.500 seconds including local reloads. This is NOT a
resident warm-pool benchmark or physical low-end-PC proof. Its Python/Torch
runtime footprint and isolated process lifetime remain unqualified for release.
Qwen3's first selection proof peaked at 1,762,709,504 native resident bytes under
the three-GiB kernel limit. Timing comparisons between runs are not controlled
benchmarks; unrelated applications were left running.

## Next bounded implementation

1. The ranker's **research canonical integration is now done**; reuse
   `CompactRankedResearchClient` and `IsolatedCompactRanker`. Do not add another
   adapter or process layer. Its task returns up to three exact candidate
   passages per record, never a fact/absence/completeness determination.
2. **Do not deploy the measured score cutoff.** On the separate test partition
   it confuses another person's appointment with the requested person's, and a
   private accusation/request with a judicial finding. It also rejects two
   relevant cases. A relevance logit is not entailment or confidence. Preserve
   these failures. Any further selector or verifier needs genuinely different,
   preregistered test cases; this partition is now a known regression set.
3. **Installed declared-dependency audit completed:** the conservative ranker,
   46-package and Python selection measures **814,223,054 bytes**. Installed
   RECORD checks pass, but tokenizers 0.22.2 lacks a bundled license text.
   Next resolve that notice gap from the pinned upstream source, then prove
   dynamic-import/native-DLL closure and immutable serving inventory. This is
   not yet the complete delivered or frozen runtime. No environment copies.
   This feeds an explicitly typed
   native/CPU admission inventory
   and hardware policy, then factory/release-scope and actual desktop reachability.
   Keep existing PEFT and human-evaluation gates intact. Do not relabel GGUF or a
   BERT ranker as a BF16/LoRA adapter. The normal hardware gate currently reports
   `specialist_resident_memory_requirement_missing` and
   `specialist_precision_requirement_invalid`; the research tests inject an
   explicitly labeled adapter rather than hiding that gap.
4. **Joined research-page flow now passes** (`ranked-browser-tests-04.xml`).
   The full shipped page exercises real canonical preview/run/cancel HTTP,
   actual weights, keyboard source drill-down and encrypted audit. Initial search
   and unrelated startup APIs are explicitly fictional; production factory and
   normal hardware admission are injected, not qualified. Both JS mirrors retain
   all candidates on one canonical source card, preserving citation numbering;
   details expand independently and the receipt labels relevance unknown.
   `sourceTextAtCodePoints` corrects Python/JavaScript offset differences.
   Signed production model selection → frozen/installed runtime remains unproved.
   Do not equate the research injection with production admission. Keep the
   research model unavailable in production until admission and whole-flow tests.
5. Complete OS-level zero-outbound observation, actual transitive dependency
   footprint/notices under the 1.5-GB cap, and physical modest-PC measurements.
   Reuse the existing runtime; no dependency/environment/model copies for trials.
6. Free-form Drafting remains unqualified. Source-bound task decomposition and
   explicit draft fields require their own meaningful, independently evaluated
   draft action; selected quotations alone are not a finished drafting feature.

No broader specialist, attorney, Store or Enterprise GA claim is supported.
The continuation automation remains active. No new model download, external
scratch directory, runtime copy, MSIX, version bump, commit or push in this pass.

## Isolated resident ranker — 2026-09-08, 20:30 UTC

Implemented `compact_ranker_process.py` and `compact_ranker_worker.py`, with the
existing `compact_reranker.py` refactored to hold hash-locked weights/tokenizer
once until explicit release. The production factory remains unchanged.

- CPU-only, two Torch threads, fixed private anonymous-pipe commands; no public
  port, user-supplied executable, tools, provider selection, remote code, model
  download or pickle IPC. Inputs/outputs are bounded strict JSON. Nonces and
  packet hashes prevent accepting an unrelated/replayed reply.
- Initial four-GiB available-memory gate; three-GiB kernel process-memory quota,
  with ownership installed while the interpreter is suspended. Cancellation
  drains the pipe thread and stops the owned job; failed cleanup quarantines it
  and retains the process handle for another cleanup attempt.
- The Windows virtual-environment launcher is bypassed in favor of the verified
  current interpreter with isolated mode and the configured runtime's trusted
  site-packages. No new environment or model copy was created.
- The scrubbed child environment uses a synthetic username and repository-local
  profile/cache/temp paths. Import initially failed because `getpass.getuser()`
  otherwise falls back to Unix `pwd` on Windows. Root-cause classification proved
  this; setting the synthetic identity fixed it without restoring credentials,
  the real profile, proxies, or changing the memory limit.
- Some Windows runs include a system `conhost.exe` helper in the job. The proof
  verifies its exact System32 path and waits for its exit. This is **one model
  interpreter plus the system helper**, not a claim that every OS process count
  was one. No visible console was requested.
- Scope/privacy/instruction guards run before loading and again after warm-up
  and inference. The host independently verifies score types, exact source IDs,
  source hashes, complete coverage, order and review-only flags. The neural score
  remains relevance only. Live weights stayed write-locked; the proof requested
  and was denied a write handle without attempting any modification.
- Failure diagnostics allow fixed stages/types, bounded error numbers, and
  missing-import identifiers during non-private warm-up only. No traceback,
  exception prose, record text or arbitrary paths is returned. Fixtures and
  receipts remain fictional. Existing in-process proof scripts now explicitly
  close their ranker too.

| Evidence | Observed result | Boundary |
| --- | --- | --- |
| `ranker-process-unit-01.xml` | 90 passed | Initial process/input/output tests plus existing CPU tests |
| `ranker-process-unit-02.xml` | Test-harness setup errors | A 256-KB adversarial value became a pytest parameter name; explicit short IDs repaired the harness, not a model output |
| `ranker-process-unit-03.xml` | 103 passed, 1.828 s | Corrected harness and expanded pipe/cleanup tests |
| `ranker-process-regression-04.xml` | 374 passed, 0 failures/errors/skips, 29.521 s | Final focused unit/service/security regression; not the whole app suite |
| `ranker-process-real-01.json` through `05.json` | Import failed safely | Preserved diagnostic progression ending in confirmed `pwd` root cause |
| `ranker-process-real-06.json` through `08.json` | Warm worked; ownership/exit assertions needed correction | Verified Windows console helper and replaced an immediate PID-existence assumption with actual process-exit waits |
| `ranker-process-real-09.json` | Real lifecycle passed | Warm 15.516 s; A/B/A rankings 0.031/0.047/0.031 s; cancellation after observed ranking CPU, thread drain, model/helper exit and restart passed |
| `ranker-process-real-10.json` | Final source-version lifecycle passed | Warm 15.282 s; A/B/A 0.031/0.031/0.032 s; all lifecycle assertions pass; peak working set 521,551,872 bytes, private memory 626,278,400 bytes |
| `ranker-process-crash-tests-01.xml` / `ranker-process-crash-01.json` | 1 actual crash test passed, 15.881 s | Abrupt termination of the verified disposable host stopped its model/helper in 0.063 s; no graceful worker cleanup could run in that host |
| `reranker-isolated-regression-02.json` | Same 11/12 relevance; 3 cases not evaluated | Known challenge through the isolated resident worker: 0.031–0.078 s per case after warm; not a new holdout or abstention proof |

The successful lifecycle run sampled about 522 MB resident and 626 MB private
memory in the model interpreter. The system console helper and desktop host are
not included in those figures. Peak working-set reporting was subsequently added
to the final run. A separate runtime/dependency inventory is still needed before
claiming the complete distributable meets the 1.5-GB limit; model files alone do
not establish it. No weights were trained, downloaded, promoted or repackaged.

The real isolated relevance regression intentionally exits nonzero for the still
wrong register-entry passage. Its 11 passes are not a claim of legal quality.
No canonical-API, desktop, frozen or installed-package integration is claimed for
this new resident ranker. Free-form Evidence/Drafting failures remain open.

## Ranked research review and negative cases — 2026-09-08, 20:55 UTC

This section supersedes the preceding pass's canonical-API limitation, **not**
its desktop/frozen/installed limitation or failed generator results.

- Added `compact_ranked_review.py`: model-inventory/policy/source-bound single-use
  approval, up to three exact candidate spans per record, resident serial ranking,
  busy rejection, cancellation and rechecking all sources between records and
  after inference. No raw generated narrative, new facts, tools, source omission,
  probability label or inferred absence. Original source/privacy offsets are not
  incorrectly rebased onto the sliced text sent to the scorer.
- Added `ranked_evidence_output.py`: each extra span passes the existing strict
  independent one-span verifier; duplicate, overlapping, out-of-range, forged,
  sensitive or missing-record spans withhold the entire result. The original
  one-excerpt mode still rejects multiple excerpts. The renderer explains that
  relevance is unknown and candidates can be returned when no answer exists.
- Added a typed `SourceRankingResponse`. Canonical dispatch checks exact response
  type, mode, provider/model/endpoint identity and completion. Fixed a host defect:
  source-bound tool requests are now rejected **before** the broker is invoked,
  rather than after a permitted read-only tool could already have executed.
- The production factory, signed admission and hardware schema were not relaxed.
  Model output never becomes authority, a finding, a legal conclusion or a draft.
  No new production navigation entry or Store claim was added.

Evidence in the existing `dist/model-candidates/compact-fleet-20260908`:

| Evidence | Exact result / limitation |
| --- | --- |
| `ranked-review-unit-01.xml` | 120 passed, 1 harness failure: the new test referenced a nonexistent result `.citations` property |
| `ranked-review-regression-02.xml` | 410 passed, 1 harness failure: the actual receipt serializes citation references as a list, not the test's assumed tuple; both failed attempts preserved |
| `ranked-review-regression-03.xml` | **416 passed, 0 failures/errors/skips, 27.153 s**; includes new shortlist/privacy/mutation/cancellation/tool/binding/calibration tests and existing service/API boundaries |
| `ranked-api-real-01.xml` / `ranked-canonical-api-01.json` | 1 real model/API test passed; first coherent research bridge |
| `ranked-api-real-02.xml` / `ranked-canonical-api-02.json` | **1 passed, 0 failures/errors/skips, 21.815 s** on final source; real warm and canonical preview/run, three source-bound passages, source card, encrypted audit, single-use approval, changed role/tenant/session rejection, wrong-matter rejection and clean shutdown |
| `ranker-calibration-and-heldout-v1.json` | Frozen before inference: 12 calibration cases (6 positive/6 negative), 12 separate test cases (6/6); six sentences per record; entirely fictional, agent-authored, not training or attorney gold |
| `ranked-review-quality-01.json` | 24 real ranking requests, 1 worker, 19.797 s including 17.547 s warm-up; peak working set 531,664,896 bytes; no execution errors; quality command correctly exits **1** |

Relevance measurements: top-1 retrieved a labeled relevant passage in all six
positive calibration cases and all six positive test cases. Top-3 contained all
labeled passages in all positive cases (mean Recall@3 1.0), including **both**
received and register-entry dates in the new compound-question case. This is a
small labeled retrieval test, not correctness/completeness or legal evaluation.
The older 11/12 single-selection result remains a failure on its known case.

The exploratory threshold was fixed at `2.058020353317261` from calibration
negatives **before** the test split. Calibration: 0/6 negative false accepts,
1/6 positive abstentions. Separate test: **2/6 negative false accepts and 2/6
positive abstentions**. The false accepts were `test-wrong-person-negative` and
`test-admin-not-judgment`. No threshold was installed or promoted; this is NOT a
filing-gate false-pass rate. The shortlist always clearly labels relevance unknown.

Final API scenario took 19.109 s including imports/warm/setup; it had one ranking
request and a 523,198,464-byte model-process peak working set. It used actual
weights but explicitly injected the research factory and hardware adapter; no
desktop, production factory, physical low-end PC, frozen or installed MSIX claim.
Existing FastAPI/TestClient deprecation warning remains. Targeted Ruff and
in-memory syntax checks for 29 changed Python files passed; both production JS
mirror syntax checks and `git diff --check` passed.

Version remains **8.0.2**. No download, training, runtime/model copy, MSIX, commit,
push, external scratch or unrelated-process termination occurred. All owned
workers exited. The new compact receipts/fixture occupy about 289 KB; original
weights and user archives are untouched. D: had 146,105,106,432 bytes free at the
last check; other projects remain active, so global disk changes are not assigned
to this run. The existing 30-minute hardening automation was confirmed ACTIVE;
  no duplicate automation was created.

## Candidate-preview UI — 2026-09-08, 21:17 UTC

Story: an already approved model response supplies exact source spans → the
existing source card retains its reference number → its preview exposes each
candidate and full excerpt with explicit relevance/review limitations.

- Updated both `src/maine_family_law_llm/ui/workbench.js` and its shipped mirror.
  The mapper keeps **one card per source** and attaches up to three candidates;
  no duplicate cards that shift `[1]`, `[2]` references. Each candidate is a native
  keyboard-operable disclosure in the existing source-preview markup/styles.
- Renderer checks safe integer bounds, source identity, source/quote hash shape,
  non-overlap, exact status and maximum count. Invalid sets show a recovery
  message, not partial fabricated candidate text. Source text is HTML-escaped.
  The server remains the cryptographic verifier; client shape checks do not
  independently prove hashes, relevance or admission.
- Fixed the existing UTF-16 offset defect: Python's source offsets are Unicode
  code points, not JavaScript string indices. Emoji before/in a quote now preserve
  the exact excerpt and absolute nonzero base offset. Combining characters are
  preserved, not normalized. Legacy single-excerpt rendering still works.
- Ranked receipts explicitly say **relevance unknown** and do not present model
  scores as confidence, evidence of absence or factual/legal findings.

Verification used the browser-verification skills. `agent-browser` was not
installed; the fallback used the existing bundled Playwright module and installed
Edge, with one reused repository-local disposable profile. No server, browser,
model, runtime or package was downloaded. No new public model selection or
navigation was added.

| Boundary / artifact | Result |
| --- | --- |
| Canonical API / real model | Prior `ranked-canonical-api-02.json` fictional response reused as data; no new inference or live API request in this UI pass |
| Shipped functions and styles → component DOM | `ranked-ui-02.json`: 17 JavaScript checks pass; same production functions and original source-preview HTML/styles, not a substitute development frontend |
| Candidate interaction | Mouse expansion and keyboard Enter expansion/collapse pass; source numbering stays fixed; all three candidates inspectable |
| CSS zoom and visual inspection | 720×800 viewport with CSS zoom 200%; vertical/horizontal bounds and `elementFromPoint` prove the selected candidate is unoccluded. Both final PNGs inspected. Actual browser/OS zoom and full modal focus trap were NOT tested |
| Focused API/UI/boundary regression | `ranked-ui-regression-01.xml`: **118 passed, 0 failures/errors/skips, 9.486 s**, one existing TestClient deprecation warning |
| Syntax/mirror integrity | Both production JS mirrors and the verification script parse; identical mirrors; Git whitespace checks pass |
| Whole production page → live model / frozen / installed package | **NOT TESTED**; production admission still closed |

Visual evidence: `ranked-ui-02-desktop.png`, `ranked-ui-02-css-zoom.png`.
These are conspicuously fictional component screenshots, **not Store assets**.
The first automatic UI report passed insufficient assertions, but visual review
rejected its screenshot: the harness had put the entire chat receipt into the
preview footer, covering content at zoom. `ranked-ui-01-visual-review.json`
explicitly overrides that automated visual-pass claim. The corrected second run
puts the receipt outside the preview and additionally checks vertical occlusion.
Do not reuse `ranked-ui-01.json` as a successful visual result.

All owned browsers closed. Cleanup of the generated profile at
`dist/qa/compact-ranked-ui/browser-profile` was **blocked by execution policy**;
no alternative deletion method was attempted. A read-only recheck confirms 184
files totaling **15,013,109 bytes** remain, and no browser command line references
that profile. No space was freed or claimed. Preserve screenshots/receipts and
source/model files. No model training/download, MSIX, version bump, commit or push.

## Installed ranker runtime audit — 2026-09-08

Added `scripts/audit_compact_ranker_runtime.py` and
`tests/test_compact_runtime_inventory.py`. The audit follows declared default
dependencies plus requested transitive extras using target-platform markers;
checks package identity/version, RECORD size/hash, file containment, mutation
during reads, declared licenses and existing notice files; and rechecks the six
model files against their existing acquisition receipt. It does not import
Torch/Transformers, perform inference, download packages or copy an environment.
Output uses portable logical paths, not personal filesystem prefixes.

The repository's Python launcher uses packages from an existing Store-build
environment outside its own `sys.prefix`. The first audit (`installed-01`)
correctly rejected those 20,113 paths under its initially selected root. That
**harness-location failure is preserved**, not described as missing or corrupted
product files. Its byte total is incomplete and must not be used. The corrected
audit requires an explicitly selected existing Windows venv with its configuration,
interpreter and site-packages present; no broad drive root is accepted.

Final measured result (`ranker-runtime-audit-installed-02.json`):

| Selection | Files | Bytes |
| --- | ---: | ---: |
| 46 installed distributions, excluding bytecode caches | 20,113 | 651,326,262 |
| Conservative CPython stdlib/DLL/interpreter selection | 3,713 | 71,312,758 |
| Existing pinned ranker model/tokenizer/config/card | 6 | 91,584,034 |
| **Measured selection total** | **23,832** | **814,223,054** |

This is below the strict **1,500,000,000-byte** target, but is neither a complete
frozen-package footprint nor a memory/hardware qualification. Stdlib tests and
declared package headers/tools remain counted rather than silently assuming they
can be stripped. No selection has been copied into an MSIX.

- **20,067 installed RECORD hashes checked successfully.** The 46 RECORD files
  themselves lack self-hashes; they and the selected Python files received fresh
  SHA-256 inventory hashes, which are consistency evidence, not publisher trust.
- **195 existing license/notice files** inventoried and hashed. Exactly one
  notice-inventory blocker remains: `tokenizers` 0.22.2 declares Apache licensing
  in its classifier but supplies no license text in its installed RECORD.
  The [official v0.22.2 source license](https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE)
  is available. It was inspected, not downloaded or bundled in this pass.
  Pin its immutable source revision, preserve attribution and verify any Rust
  transitive notices before claiming the packaging gap closed.
- Audit command exited **1** for that notice gap, after **282.578 seconds**.
  `installed_selection_integrity_passed=true`, `notice_inventory_complete=false`;
  `complete_runtime_qualified=false`, `production_admitted=false`, `ga_ready=false`.
- Both runs preserve their inventories. First run: **97.563 seconds**, incomplete
  root selection. Never substitute that small partial byte count for the final one.

Reproduction (the explicit venv is the already inspected Store-build dependency
environment referenced by the launcher, not a newly created environment):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& dist/build-env/store/Scripts/python.exe -B scripts/audit_compact_ranker_runtime.py --run-id <new-id> --package-runtime <existing-Store-build-venv>
& dist/build-env/store/Scripts/python.exe -B -m pytest tests/test_compact_runtime_inventory.py -q -p no:cacheprovider --basetemp dist/qa/compact-runtime-audit --junitxml dist/model-candidates/compact-fleet-20260908/<new-test-report>.xml
```

`ranker-runtime-audit-tests-03.xml`: **25 passed, 0 failures/errors/skips, 0.713 s**.
Tests cover extras/cycles/platform markers, dependency mismatch/missing metadata,
credential-bearing URL redaction, tampering, path escape, weak hashes, notice
locations, bytecode exclusion, model receipt traversal/duplicates, overwrite
protection and full fictional audits that cannot promote themselves to GA.
Earlier test attempts also passed (21 and 22 respectively); counts are separate,
not added together. Targeted Ruff, in-memory Python syntax and `git diff --check`
pass. This was not another inference or full-app regression run.

Evidence hashes:

- `ranker-runtime-audit-installed-02.json`:
  `571e12adb49f610a312b8cc76866d4540e495fb37dbd8fc45c8c7d3c381c665c`
- `ranker-runtime-files-installed-02.jsonl`:
  `472ac7e2daa71518ec8c71c48d80ca5306026f640b47c49ebf8e4b6a33bc62e9`
- `ranker-runtime-audit-tests-03.xml`:
  `78938acd52a5abea7438da4a397ccc2ee31f89ff4bdaf2a398d1f1fb5ec6b971`

Remaining runtime work is actual loaded-module/native dependency observation,
publisher provenance, immutable locked serving inventory, transitive license
compliance, OS-level network observation, typed production admission/hardware
policy and exact frozen/installed reachability. Drafting quality and the ranker's
known semantic limitations remain unchanged. No GA, Store or Enterprise claim.

No weights/runtime/environment copies, model training, MSIX, version change,
commit, push or external scratch directory were created. The audit workers
exited. Cleanup of the owned synthetic pytest directory
`dist/qa/compact-runtime-audit` was **denied by execution policy before launch**;
no bypass was attempted. A read-only check confirms **80 files, 19,431 bytes**
remain, with no active test process. No reclaimed space is claimed. The earlier
browser-profile cleanup denial remains unchanged; user archives are untouched.

## Complete Evidence Review research interaction — 2026-09-08

The user's new direction is **full verticals only**. Prerequisite repairs belong
inside the corresponding user workflow; do not mark isolated backend, audit or
UI work as a completed production feature or resume unrelated feature batches.

Story verified: the complete shipped workbench page renders a fictional initial
record-search result → the user selects Review evidence → canonical HTTP preview
rehydrates the private source and binds approval → the user cancels a started
real worker without accepting an answer → obtains a fresh approval → actual
resident ranking returns exact passages → the real result/source-card UI opens
all three passages by keyboard → closing returns focus → Space reopens the source.
The canonical audit is encrypted and records cancellation and the subsequent run.

Implementation and weak links repaired:

- `tests/test_compact_ranked_browser_real.py` runs the actual ASGI routes over
  loopback HTTP and supervises one existing ranker, plus the whole-page browser
  driver `scripts/verify_compact_ranked_flow.mjs`. No copied app/runtime/model.
  Full page HTML, CSS, JavaScript and brand assets are served by the canonical app.
- Both production JS mirrors now disclose private process pipes instead of a
  fictitious model network endpoint, explicitly flag a non-production model
  binding, and call its result review-required output rather than a verified
  finding. Public model admission was not changed or bypassed by production code.
- Shared `bindSourceCardActivation` gives inline and sidebar cards Enter/Space
  activation. Nested buttons, forms and Technical disclosures retain their own
  actions; key repeats do not reopen dialogs. An enclosing collapsible panel is
  not mistaken for a nested control. This fixes an actual missing keyboard path.
- Both CSS mirrors improve the dark model-dialog kicker's contrast. Expanded
  candidate summaries have spacing so a focus ring does not crowd the quotation.
- Browser profiles are reused under the existing repository QA directory.
  The final harness explicitly confines browser TEMP/TMP/APPDATA/LOCALAPPDATA
  there. No installer, model download, cloud inference or runtime copy.

| Evidence | Exact result and scope |
| --- | --- |
| `ranked-browser-tests-01.xml` | 1 failed, 38.258 s: the synthetic initial SSE result omitted the production `payload` envelope; app correctly rejected an incomplete result; no model run |
| `ranked-browser-tests-02.xml` | 1 failed, 129.054 s: approval, real cancellation/retry and ranking passed; source test chose a hidden side-panel card, leaving focus on the old model button; inspection also found the missing card keyboard handler |
| `ranked-browser-tests-03.xml` | 1 failed, 34.804 s: repaired keyboard opening worked; harness counted the Technical disclosure as a fourth candidate and failed its overly broad selector |
| `ranked-browser-tests-04.xml` | **1 passed, 0 failures/errors/skips, 34.554 s**, six joined interaction assertions; no browser page errors |
| `ranked-browser-api-04.json` | Actual canonical preview/cancel/run routes; cancellation HTTP 200, canceled run HTTP 409, fresh successful run HTTP 200; encrypted audit; two worker starts, one completed rank request; peak worker RSS **523,452,416 bytes**; scenario 28.156 s; server and worker stopped |
| `ranked-browser-regression-01.xml` | **126 passed, 0 failures/errors/skips, 29.522 s**: scoped approvals/source binding, privacy, ranked review, output boundary and local-agent API/UI coverage |
| `ranked-ui-keyboard-final.json` | **18 JavaScript checks pass**, including nested-control and enclosing-panel behavior; no inference/browser rerun |
| `ranked-ui-flow-polish.json` | Final source-preview component: same **18 checks pass**, native mouse/keyboard disclosures, CSS 200% zoom and unobscured target checks pass; both final screenshots visually inspected; no browser errors |

The last whole-page flow precedes only the small enclosing-panel containment
guard and focus-spacing follow-up; those final changes were checked through
the focused JavaScript/component browser checks, not another full inference run.
Earlier failed receipts remain preserved. Do not aggregate retry counts into
independent model-quality samples. Existing TestClient deprecation warning remains.

Whole-page images: `ranked-browser-04-startup.png`, `-approval.png`, `-result.png`,
`-source.png`. Approval/source images were visually inspected; final focus-spacing
images are `ranked-ui-flow-polish-desktop.png` and `-css-zoom.png`. These are QA
evidence, **not Store listing assets**. Actual OS/browser zoom and a full-screen
reader audit were not executed. Source-dialog focus return and Enter/Space
activation were exercised; do not extend that result to every app dialog.

Important remaining boundaries:

- The initial search, corpus selection metadata, worker-status display and
  unrelated startup services are fictional fixtures. The harness explicitly
  injects the research client and CPU hardware adapter; ASGI lifespan is off.
  It does not qualify production startup, catalog/admission, all search behavior,
  physical low-end hardware or an installed/frozen package.
- The exact model returned a third, irrelevant bookmark sentence. The UI openly
  says relevance is unknown and no absence/finding is established. This run did
  not repair the previously measured semantic false accepts or qualify Drafting.
- Browser page request interception is not OS-level zero-outbound proof.
- The ranker runtime notice/provenance/admission blockers remain. Next full
  vertical is the honest install/readiness/activation path: pinned dependency
  and notice inventory → typed native/CPU admission and hardware policy →
  canonical status/activation → actual UI blockers and permitted operation →
  frozen reachability. Preserve existing PEFT and human-evaluation gates; a
  missing required approval stays blocked, never manufactured.

No MSIX, version change, commit, push, new model weights or private corpus use.
All owned browser/server/model processes closed. Cleanup of the newly generated
`dist/qa/compact-ranked-flow` (7,560 bytes) and `dist/qa/compact-ranked-regression`
(190,785 bytes) was denied by execution policy before launch. No alternative
deletion was attempted or freed space claimed. Do not use pytest's automatic
basetemp deletion to bypass those denials. Earlier denied cleanup targets remain
untouched. User archives and actual model files were preserved.

## Matter-bound model-pack readiness vertical — 2026-09-08

Completed path: shipped workbench → offline pack panel → canonical scoped HTTP
import/chunks/inspect → signed artifact identity drill-down → decline or explicit
activation → encrypted audit/state → honest readiness inventory. The browser
uses a tiny fictional structural pack with an ephemeral **test-only** signer.
Neither real model weights nor a production trust key are manufactured by this
test. Startup/search/corpus selection are fictional fixture responses and app
lifespan is disabled; pack operations and production page/assets are real.

Repairs:

- `ModelPackService.inventory` now separates no-active-pack, admission-blocked,
  development-only and production-admitted/runtime-unverified states. It never
  infers hardware readiness or model quality from installation/admission.
- Both shipped JS mirrors expose that distinction in plain language. The signed
  details remain available; review-required status is retained.
- Inventory responses have request/revision/matter ownership checks, including
  switching A → B → A. An old success or failure cannot replace a newer result.
- Scope changes invalidate pack/model selections and hide old details. In-flight
  transfers keep their original request scope, stop further chunks, and cannot
  automatically inspect or activate in the new matter. Late mutation results
  and canceled prefix-check results cannot repopulate the new context.
- The actual browser found a disabled Import button surviving the end of local
  preview generation. Local-agent busy-state notifications now refresh pack
  controls. Discard operations also remain locked until their response finishes.

New checks: `tests/test_model_pack_readiness.py`,
`tests/test_model_pack_browser_real.py`, `scripts/verify_model_pack_flow.mjs`,
and expanded `tests/test_fast_interchange_model_pack_ui.py`.

Evidence under `dist/model-candidates/compact-fleet-20260908`:

- `pack-readiness-01.xml`: 23 tests, 22 failures, 23.290 s. One expected-denial
  assertion omitted the canonical non-disclosing 404; 21 JS harness executions
  exceeded Windows' command-line limit. Fixed the assertion and used UTF-8 stdin.
- `pack-readiness-02.xml`: 23 passed, no failures/errors/skips, 24.930 s.
- `pack-browser-tests-01.xml`: one failed, 37.933 s. Fictional search fixture
  omitted `local_agent_available`; the UI correctly hid its specialist action.
- `pack-browser-tests-02.xml`: one failed, 36.799 s. Real disabled-button
  synchronization defect described above; no upload/activation occurred.
- `pack-browser-tests-03.xml`: **one passed**, no failures/errors/skips,
  **29.202 s**. Five joined browser assertions, no page errors or blocked external
  browser requests. `pack-browser-api-03.json` records actual HTTP requests and
  encrypted audit actions, including verification and authorized activation;
  server/browser closed. Scenario 25.687 s. No inference was started.
- `pack-browser-03-readiness.png`: inspected visually; readable research-only
  disclosure, disabled inference button, real signed-details disclosure and exact
  fictional source. This is QA evidence, not a Store screenshot.
- `pack-ui-final-03.xml`: **30 passed**, no failures/errors/skips, **6.894 s**;
  includes late canceled-prefix/matter-switch protection added after the browser
  run. That small final guard is covered by the focused JS test, not another
  full browser run. Previous successful focused receipts are retained, not
  counted as independent quality samples.
- `pack-regression-01.xml`: **126 passed**, no failures/errors/skips,
  **572.899 s**. Canonical pack import/readiness, archive bounds, role/scope,
  signatures/revocation/rollback, crash recovery, hardware policy and artifact
  registry tests. This run began before the final busy-state/prefix UI repairs;
  the subsequent 30-test UI/API receipt covers those final changes.
- Python AST validation, targeted Ruff and both JS syntax checks pass; production
  HTML/CSS/JS mirrors match. Existing TestClient deprecation warning remains.

The canonical readiness test also checks non-admin rejection, cross-matter and
cross-tenant non-disclosure, encrypted audit, revocation clearing available
models, original/installed artifact preservation, and **zero inference calls**.
This is an import/readiness vertical, not Evidence Review/Drafting model-quality
acceptance, genuine production signature admission, measured hardware readiness,
OS-level offline proof, frozen-app qualification or an MSIX release.

Remaining model-release prerequisites are unchanged: native compact-model
admission/factory/hardware integration; immutable dependency/license provenance;
semantic false-accept repair and broader independent evaluation; OS-level
network observation; full app/frozen/installed validation. Next full vertical
must connect the actual compact research runtime to an honest typed readiness
and permitted-activation path without pretending BERT/GGUF is a PEFT adapter or
weakening signature, revocation, licensing or evaluation requirements.

No weights/environment copies, downloads, model training, private corpus use,
MSIX, version change, commit or push occurred in this pass.

Cleanup was denied by execution policy **before launch** for these four new
owned QA targets. Read-only follow-up confirms they remain and no owned
pytest/Node/Edge process is active:

- `dist/qa/pack-readiness-current`: 30 files, 39,407 bytes.
- `dist/qa/pack-readiness-js`: empty.
- `dist/qa/pack-readiness-ui-final`: 9 files, 5,041 bytes.
- `dist/qa/pack-readiness-regression`: 1,253 files, 7,316,455 bytes.

Total **7,360,903 bytes** of fictional fixtures; no freed space is claimed.
Do not bypass this denial by another deletion tool or by reusing these names as
pytest basetemps (which automatically delete previous contents). Older denied
targets remain untouched. The existing browser profile was reused, not copied
or deleted. Model weights, user archives and prior evidence were preserved.

## Real hardware → approval → ranking vertical — 2026-09-08

The research ranker now uses the **normal canonical hardware assessor**. Its
binding declares its actual FP32 CPU-only worker policy and the same 3 GiB
resident limit enforced by the worker/job object; the host adds its existing
1 GiB reserve. This is a research ABI, **not a PEFT grant or signed production
admission**. The research factory remains explicitly injected in the proof;
normal production factory registration remains unavailable.

Repairs across the vertical:

- `legal/fast_interchange/hardware.py`: missing/unrecognized Torch runtime fails
  closed even for FP32 CPU; GPU index 0 works in the existing index fallback;
  CPU-only workers do not advertise GPU execution/VRAM requirements; unknown
  execution policy cannot grant readiness.
- `legal/model_orchestration/hardware.py`: zero/unavailable free RAM is never
  replaced by total installed capacity. Unknown headroom gets a warning and
  conservative concurrency/context recommendations.
- `compact_ranked_review.py` supplies actual worker limits so tests no longer
  substitute a permissive hardware assessor.
- Both canonical API mirrors record an encrypted `hardware_blocked` event before
  refusing execution. The initial audit edit reached only the root mirror;
  execution inspection proved the runtime uses `src/maine_family_law_llm/api.py`.
  That mirror was repaired too, and byte-equality is now checked by the UI test.
- Both production JS mirrors explain unavailable runtime and unknown/exhausted
  RAM while leaving Run disabled and exact-source inspection available.
- The isolated approval-dialog JS harness now includes the real busy notifier
  added in the previous vertical and reads code through UTF-8 stdin. Its six
  missing-helper failures were fixed, not suppressed.

The real API proof injects zero available RAM for one denial and an unavailable
runtime for one refused run. Recovery uses the actual machine probe and existing
Torch runtime, never a replacement hardware assessor. It verifies no child
before denial, a fresh preview/approval, actual ranking, source spans, scope and
single-use controls, encrypted refusal/result audit, and clean worker shutdown.

The shipped-page browser flow adds zero-RAM denial, real hardware recovery,
explicit consent, real child startup cancellation, retry, and exact-source
keyboard drill-down. Startup/search metadata remain fictional fixtures. Eight
assertions pass; no page errors or blocked external browser requests. This is
not OS-level outbound observation, frozen/installed proof or legal-quality data.

### Evidence correction: cancellation timing

An additional PID assertion exposed that the earlier asynchronous browser wait
could proceed on a false observation. Earlier browser passes (including
`hardware-browser-tests-01.xml`) prove cancellation of an approved request but
must **not alone** be cited as proof of canceling an already-started child.
Their successful ranking/source results are unaffected. The receipts are kept.

`hardware-browser-tests-02.xml` deliberately failed the stronger assertion. Its
test cleanup joined the server before stopping inference and reported the server
still running at that instant. The pytest process subsequently exited; later
process inventory found no surviving owned process. Cleanup now cancels/releases
the owned client before joining the server and records cleanup errors explicitly.

The final driver polls resolved JSON with an explicit boolean and child PID
check. `ranked-browser-hardware-03.json` records a live child PID **32708** with
one resumed worker before cancellation; the final server receipt records
**two worker starts, one completed rank request**, encrypted `cancel_requested`
and `canceled` events, all owned processes closed and no cleanup errors. Do not
turn an earlier harness false positive into independent model-quality evidence.

### Exact results

All files below are under `dist/model-candidates/compact-fleet-20260908`.

| Receipt | Result |
| --- | --- |
| `hardware-vertical-unit-01.xml` | 54 passed, 0 failed/errors/skips, 4.837 s |
| `hardware-canonical-tests-01.xml` | 1 failed, 80.170 s: root-only audit repair missing from loaded source mirror; real ranking completed but audit assertion failed |
| `hardware-canonical-tests-02.xml` | 1 passed, 0 failed/errors/skips, 26.041 s; scenario 23.125 s; real worker peak 523,902,976 bytes |
| `hardware-vertical-regression-01.xml` | 129 tests, 123 passed / 6 failed, 41.519 s: isolated JS harness omitted new busy notifier |
| `hardware-vertical-regression-02.xml` | 129 passed, 0 failed/errors/skips, 35.882 s |
| `hardware-ui-final.xml` | 20 passed, 0 failed/errors/skips, 4.264 s |
| `hardware-browser-tests-01.xml` | 1 reported pass, 31.695 s; cancellation-start claim superseded by stronger check |
| `hardware-browser-tests-02.xml` | 1 failed, 20.688 s: explicit child-start assertion caught the earlier weak wait |
| `hardware-browser-tests-03.xml` | 1 passed, 0 failed/errors/skips, 31.550 s; scenario 24.875 s; peak worker RSS 522,670,080 bytes |

Blocked/ready/source screenshots are `ranked-browser-hardware-03-*.png`; the
matching first-pass blocked/ready screens and final ready screen were visually
inspected. No new styling hides an incomplete feature. Targeted Ruff, AST and
JS syntax checks pass; API and production asset mirrors match. Existing
TestClient deprecation warning remains. Counts overlap; do not add retry runs
as unique test cases or evaluation samples.

No model weights changed and semantic relevance/false-accept limitations are
unchanged. No model download, training, runtime copy, MSIX, version change,
commit, push, attorney approval, production admission or GA certification.
Production native admission/factory, licensing/runtime provenance, semantic
quality, OS offline observation and frozen/installed qualification remain open.

Cleanup of `dist/qa/hardware-vertical-current` (4 fictional files, **8,262 bytes**)
and empty `dist/qa/hardware-vertical-regression` was denied before launch. No
bypass or reclaimed-space claim. **Do not reuse these basetemp names**, which
would trigger automatic deletion. Older denied targets and user artifacts were
untouched. No owned test/browser/model process remains.

## 2026-09-08 — Python-network denial and recovery vertical

**Delivered boundary:** isolated research ranker → canonical preview/run/cancel
→ scoped single-use approval and encrypted result audit → actual shipped-page
failure/recovery → real local model ranking → exact source keyboard drill-down.
The production factory remains closed to this research model. This is not GA,
frozen-app, installed-package, legal-quality or zero-native-network evidence.

### Runtime and interaction repairs

- `compact_network_guard.py` installs a child-only Python audit tripwire before
  model-library imports. Socket creation (including loopback), connection, DNS,
  datagram sends and standard HTTP/URL requests are refused. Arguments, hosts,
  URLs and credentials are not retained or returned. Anonymous pipe IPC works.
- Installation self-tests the exact hook and fails closed if an existing hook
  silently refuses registration. A caught denial permanently taints the child:
  no warm/rank result may be returned after it. The parent checks a versioned
  warm acknowledgement, maps the bounded failure and stops the owned process.
- The canonical runtime gives a plain-language explanation, preserves source
  records, and records the failed result through the existing encrypted audit.
  It does not recommend disabling Local-only. Consumed approval cannot replay.
- Fixed a discovered production UI defect: failed/blocked results previously
  closed the dialog and could show a success toast. They now keep review open,
  preserve the original answer, disable the used approval and explain recovery.
- Enlarged the status/recovery text to at least 14 px with stronger contrast;
  retained its polite, atomic status announcement and forced-colors text color.
  Final actual-browser geometry confirms the text stays inside the 1440×1000
  viewport. This is not a complete 200%-zoom or accessibility audit.

### Evidence, commands and exact results

All receipts remain under `dist/model-candidates/compact-fleet-20260908`.
Use `dist/build-env/store/Scripts/python.exe -B -m pytest`,
`PYTHONDONTWRITEBYTECODE=1`, `-q --tb=short -p no:cacheprovider`, and each
receipt's named, repository-local `--basetemp` and `--junitxml`.

| Receipt | Result |
| --- | --- |
| `network-vertical-unit-01.xml` | 73 passed, 0 failures/errors/skips, 3.908 s |
| `network-canonical-tests-01.xml` | 1 passed, 0 failures/errors/skips, 45.724 s |
| `network-regression-01.xml` | 252 passed, 0 failures/errors/skips, 34.382 s |
| `network-browser-tests-01.xml` | 1 passed, 39.094 s; first visual exposed undersized recovery text |
| `network-browser-tests-02.xml` | 1 passed, 0 failures/errors/skips, 39.196 s; final readable status |

The 252-test command covers `test_compact_network_guard`,
`test_compact_ranker_process`, `test_compact_ranked_review`,
`test_fast_interchange_ui_lifecycle`, `test_fast_interchange_host_source_binding`,
`test_fast_interchange_hardware_readiness`, `test_evidence_review_output_boundary`
and `test_fast_interchange_specialist_tasks` (all under `tests`, `.py`).
Overlapping runs/retries are not unique quality samples.

API proof uses `MFL_RUN_RANKED_API_PROOF=1`, proof ID `network-01` and
`tests/test_compact_ranked_api_real.py`. It tests an explicit caught DNS-call
fault inside the real child (not a model forward pass), confirms discarded
output, stopped child, replay rejection and recovery to actual model inference.
Scenario 42.859 s; peak worker RSS **523,677,696 bytes**. Tenant, role, session,
matter and encrypted receipt checks pass. No private corpus was used.

Browser proof uses `MFL_RUN_RANKED_BROWSER_PROOF=1`, proof ID `network-02`,
`tests/test_compact_ranked_browser_real.py`, the existing Node/Playwright/Edge
runtime, and `scripts/verify_compact_ranked_flow.mjs`. Nine joined assertions:
page boot, hardware refusal, measured CPU recovery, exact source approval,
observed-child cancellation, caught-network-error recovery, actual ranking,
three exact source passages, and keyboard dialog return/reopen. Startup/search
are fictional fixtures and the research factory is explicitly injected.
Scenario **32.187 s**, one completed rank, peak RSS **521,785,344 bytes**;
zero page errors, zero intercepted external browser requests, all owned workers,
server and browser closed, no cleanup errors. The request filter does not
observe native browser/worker network traffic. Final screenshot:
`ranked-browser-network-02-network-blocked.png`; source/result/approval/startup
screens and DOM/API JSON receipts accompany it. Both blocked screenshots were
visually inspected. Browser skills directed full-flow verification; unavailable
agent-browser CLI was replaced by existing Playwright without installation.

Targeted Ruff, production/mirrored JS and driver syntax, mirror equality and
`git diff --check` pass. Existing TestClient deprecation remains. A read-only
PowerShell inventory initially had a syntax error and was corrected; no files
were changed by that failed command. No automated tests failed in this pass.

### Limits and next release boundary

[Python documents that audit hooks are not a sandbox](https://docs.python.org/3/library/sys.html#sys.addaudithook).
This tripwire catches audited Python operations by trusted dependencies; native
network calls or malicious Python can bypass it. It does not establish OS
network isolation, prevent every conceivable exfiltration channel, or qualify
an immutable runtime. Those requirements remain open. Audited operation names
come from the [official event table](https://docs.python.org/3/library/audit_events.html).

Model files and all prior semantic failures are unchanged. The ranker still
returns relevance-unknown candidates, including irrelevant text; it is not full
Evidence Review. Drafting is not qualified. Next work remains semantic quality,
closed runtime/license provenance, production native admission/activation, OS
offline observation, and frozen/installed end-to-end qualification. No MSIX,
training, download, version change, commit, push or admission bypass occurred.

Cleanup of only this pass's five generated `dist/qa/network-vertical-*` targets
(370 fictional files, **213,695 bytes** total, plus empty directories) was denied
before process launch. Nothing was deleted or reclaimed; no bypass attempted.
Do not reuse these five basetemp names: pytest would attempt automatic deletion.
Earlier denied targets, models, runtime, browser profile, archives and user data
were untouched. No new runtime/model copies or external scratch folders.

## 2026-09-08 evening — Claim-grounding truth through UI and transcript

**Defect fixed:** `/api/local-agent/run` previously set `grounded=true` merely
because the context contained a source. That also applied to failed runs and
relevance-unknown passage ranking. The UI could display a green “source grounded”
badge. Source availability is not claim support or legal verification.

`LocalAgentRunResult.to_dict()` now emits conservative `grounded=false` plus
`output_grounding` (`local_model_grounding_v1`). This distinguishes available
source context, checked quotation text, unverified model output and withheld
output. Factual/legal claims, relevance and current law remain explicitly
unverified. Failed runs cannot inherit a successful quotation status. The
canonical API no longer overwrites that classification.

Both production UI mirrors use the narrower label in the visible chat banner,
answer details and badges. Legacy model payloads with `grounded=true` no longer
get a green claim/currentness badge. Ordinary host-answer rendering is unchanged.
The context details also no longer say “Nothing was sent to a model” after a
model run; they identify the approved packet and point to the outcome receipt.
The actual consented transcript export preserves the new fields and all review
limitations. No new public model, product feature, admission bypass or legal
quality claim was added.

### Verification and the export failure retained

All receipts below are in `dist/model-candidates/compact-fleet-20260908`.

| Receipt | Actual result |
| --- | --- |
| `grounding-unit-01.xml` | 63 passed; 0 failures/errors/skips; 4.728 s |
| `grounding-canonical-tests-01.xml` | 1 passed; 33.441 s; real ranker after caught-network fault, scope/replay/audit checks |
| `grounding-regression-01.xml` | 268 passed; 0 failures/errors/skips; 40.910 s |
| `grounding-final-unit.xml` | 21 passed; 5.225 s; includes corrected post-run manifest wording |
| `grounding-related-ui.xml` | 10 passed; 2.919 s; existing answer/evidence presentation |
| `grounding-browser-tests-01.xml` | 1 passed; 44.888 s; real ranking, truth labels, exact sources and confirmed transcript download |
| `grounding-browser-tests-02.xml` | 1 failed; 51.839 s; browser closed during transcript download after preceding checks passed |
| `grounding-browser-tests-03.xml` | 1 failed; 37.283 s; added lifecycle diagnostics reproduced browser closure during export consent, before cleanup |
| `grounding-browser-chromium.xml` | 1 passed; 44.058 s; all 12 joined assertions including post-run wording and confirmed transcript export |

Do not count overlapping runs as unique tests or model-quality samples. The
268-test regression adds `test_local_model_grounding.py` and
`test_v540_local_agent_api_ui.py` to the prior network-vertical test list.
Related UI tests are `test_best_interest_chat_answer.py` and
`test_v520_answer_first_evidence.py`. Commands, IDs and limits are recorded in
`claim-grounding-vertical.json`. All tests used repository-local basetemp and
disabled bytecode/pytest cache. Existing TestClient deprecation remains.

The final comparison used already-installed **Chromium 151.0.7922.34**, an
ephemeral test profile, the shipped page, canonical HTTP endpoints, normal
hardware assessor, real resident ranker and explicitly injected research factory.
Startup/search remain fictional fixtures. Twelve assertions passed, zero page
errors, zero intercepted external browser requests; one completed rank, peak
worker RSS **522,305,536 bytes**, scenario **36.828 s**. All owned processes
closed and no worker/server cleanup error. Source, result, blocked-state and
approval screenshots, DOM/API receipts and the fictional transcript are saved.
The result screenshots for initial Edge and final Chromium were visually read.
This is not frozen/installed proof or OS-level network observation.

**Edge export qualification remains blocked.** Installed Edge reports
**152.0.4191.66**. A [similar persistent-profile download crash is reported in
Playwright's tracker](https://github.com/microsoft/playwright/issues/42506), but
the local controls did not establish that as the root cause: a tiny data-URL
download passed (`edge-download-control-01.json`), while a separate Blob/confirm
control timed out without a download (`edge-download-control-02.json`). Both
controls omitted the app, API and model; both browser processes exited zero at
cleanup. No matching Application Error event was found in the scoped time check.
Do not relabel the two app-flow failures as a proven environment limitation or
claim that switching QA engines fixes installed WebView behavior. Actual package
export needs direct qualification before release. Browser/investigation skills
guided the boundary checks; unavailable agent-browser CLI was replaced with
existing Playwright, without installing a browser or copying a runtime.

No model weights changed; semantic and production-admission blockers remain.
Ruff, JS syntax, mirror equality and diff checks pass. No MSIX, training,
download, version bump, commit, push or publishing occurred.

Cleanup of the nine `dist/qa/grounding-vertical-*` targets and empty
`dist/qa/compact-transcript-downloads` was denied before launch: **396 fictional
files / 246,891 bytes** remain; none were deleted. Exact paths and absence of
reparse points were checked; no bypass. Do not reuse these basetemp names.
The browser harness now routes downloads into the caller's fresh, validated
repository-local QA TEMP, avoiding implicit cleanup of that denied shared
download directory. This final harness path-routing change is syntax-checked;
the recorded browser comparison predates it. Model/runtime/profile copies and
all previously denied targets were untouched.

## Transcript-delivery vertical — 2026-09-09 UTC

Completed the existing research-result -> exact-source -> local transcript
workflow through the shipped page and canonical API. This does **not** admit a
specialist or qualify a frozen/installed package.

Production JS/HTML/CSS mirrors now share a bounded TXT/JSON export lifecycle:

- Consent is always required, including when an earlier private conversation is
  followed by a public-law answer. Cancelling does not serialize or download data.
- Hidden download anchors are attached to the document; URLs survive the click
  task for up to 60 seconds rather than being immediately revoked. A maximum of
  four pending links and 16 MiB per file bound retained export resources.
- Page exit, conversation clear and successful matter-switch session reset revoke
  pending links. Already downloaded external files cannot be retracted.
- Serialization/download-initiation failures show a safe recovery message and
  preserve the conversation. No raw exception, path or private text enters it.
- A persistent 14px live status says **Download requested**, never an unobserved
  **saved** claim. TXT/JSON preserve exact sources and unverified model-claim state.

The browser/verification skills guided full-flow testing, using the existing
Playwright fallback because agent-browser CLI is unavailable. The first patched
run using the old persistent Edge profile still closed at TXT `download.saveAs`.
The lifecycle defect was real, but fixing it did **not** establish the root cause
or resolve that separate failure. No profile was deleted or reset.

Two subsequent comparisons with the same installed **Edge 152.0.4191.66**, using
ephemeral contexts under repository QA TEMP, passed both exports. The final one
also confirmed visible-conversation clear revokes pending links. This narrows the
failure toward the persistent-profile/context path; it does not prove a particular
corrupt profile setting or qualify the user's installed browser/package.

| Evidence | Exact result |
|---|---|
| `transcript-unit-01.xml` | 22 passed; 5.322 s |
| `transcript-regression-01.xml` | 298 passed; 41.326 s; before final reset cleanup |
| `transcript-browser-edge-01.xml` | 1 failed; 39.906 s; reused-profile export closure |
| `transcript-browser-edge-fresh-01.xml` | 1 passed; 39.393 s; real TXT and JSON downloads |
| `transcript-final-unit.xml` | 33 passed; 6.235 s; final production assets |
| `transcript-browser-edge-final.xml` | 1 passed; 37.005 s; 16 joined checks |

Every row has zero collection errors/skips. Runs overlap; do not add them as
unique test cases or quality samples. Initial Ruff found five line-length errors
in the new test; repaired, formatted and rechecked successfully. Production JS,
harness syntax, production mirror equality and `git diff --check` pass. Existing
Starlette TestClient deprecation remains.

Final real scenario: **29.954 s**, one completed CPU rank, **522,489,856 bytes**
peak worker RSS, zero JS page errors or intercepted external browser requests.
All owned worker/browser/server processes closed without cleanup errors. The
network test is still a Python audit-hook fault, not OS-level isolation. The
research factory and fictional initial search/startup remain explicit fixtures.
Actual model processing, canonical approval/run, encrypted audit, exact sources,
keyboard cancellation and resulting TXT/JSON bytes were exercised. Final export
screenshots were visually checked; files are fictional and not Store assets.

Evidence: `dist/model-candidates/compact-fleet-20260908/transcript-delivery-vertical.json`
and `verification-snapshot-transcript-delivery.json`, plus the named JUnit reports
and `ranked-browser-export-edge-final-*` artifacts in that same directory.

The compact NLI candidate `cross-encoder/nli-deberta-v3-small` was inspected only:
pinned repository revision `fa2804872c3b4bd748f38c0185cc85775361e735`, upstream
567,605,820-byte safetensors, Apache-2.0 declared in its
[publisher model card](https://huggingface.co/cross-encoder/nli-deberta-v3-small).
It is a generic SNLI/MultiNLI classifier, not a Maine-law specialist. No weights
were downloaded, integrated, evaluated or advertised. The existing broken export
boundary took precedence over opening another unverified model path.

**Still blocked:** persistent-profile export failure; frozen/installed export
qualification; specialist semantic quality; signed native production admission;
runtime license/closure and OS-level network evidence; full release regression.
No model was promoted, no MSIX/version change, no commit/push/publish, no runtime
or model copies, and no personal corpus was used.

Cleanup of this pass's six exact `dist/qa/transcript-vertical-*` targets was
denied before launch after reparse/process/path checks. **398 fictional files /
236,079 bytes** remain; none were deleted. Do not retry with another tool or
reuse these pytest basetemps (pytest would implicitly delete them). Existing
cleanup-denied profiles, models, evidence, archives and release artifacts remain
untouched. A read-only inventory command initially had a PowerShell pipeline
syntax error; corrected before any cleanup attempt, with no state changed.

## Compact NLI qualification prerequisite — 2026-09-09 00:50 UTC run

Resumed model quality work after checking Git/AGENTS/current processes. No other
owned qualification job was running. Acquired **one** pinned research candidate,
`cross-encoder/nli-deberta-v3-small`, under
`dist/model-candidates/compact-fleet-20260908/text-relation-nli`. No runtime/base
copies, other-project edits or private corpus use. This is a failed qualification
prerequisite, **not a delivered UI feature or a completed production vertical**.

Acquisition uses the existing bounded HTTPS downloader, selected files only,
immutable revision `fa2804872c3b4bd748f38c0185cc85775361e735`, Git/LFS hashes and
the publisher's Apache-2.0 model-card declaration. Safetensors hash:
`ebc79588dd73ccfb6a3f6078519cfbf512c5305384c5ea1845bc71cd32216e86`.
The generic SNLI/MultiNLI model is not relabeled as Maine-law expertise. Full
redistribution/native-license qualification is still open.

- Model/tokenizer/card: **576,268,033 bytes**, seven files.
- Previously audited selected runtime/Python: **722,639,020 bytes**, reused in place.
- Combined declared selection: **1,298,907,053 bytes**, below 1,500,000,000.
- Runtime audit basis: `ranker-runtime-audit-installed-02.json`, SHA-256
  `571e12adb49f610a312b8cc76866d4540e495fb37dbd8fc45c8c7d3c381c665c`.
- This arithmetic is not proof of a complete frozen runtime; the existing
  tokenizers license/native closure blockers remain. Disk preflight showed ~138GB
  free on D before acquisition. No duplicate runtime was downloaded.

Added `scripts/verify_compact_nli_candidate.py`: a fixed 24-case fictional
challenge, with expected labels frozen before inference and excluded from the
tokenizer inputs. Source arrays are not user-controlled inputs. The subprocess
uses the real Python interpreter, isolated imports, CPU/two threads, a suspended
Windows child attached to the existing 3GiB/one-process Job Object before resume,
a 120-second deadline, memory-headroom checks, bounded output, pinned/locked
artifacts, no remote code/pickle, and a child-only Python network tripwire. This
tripwire is not an OS sandbox. Every child is closed in `finally`.

**Actual model result: 20/24**, reproduced exactly after process restart. All eight
positive and eight explicit-contradiction cases passed. Four of eight unknown
cases were incorrectly labeled contradiction: wrong-person attribution, promised
future delivery, a calendar entry versus cancellation, and witness credibility.
There were **0/16 false entailments on this tiny authored challenge**, not a claim
of a zero release false-pass rate. Scores are not calibrated truth probabilities.
No thresholds were tuned or labels changed to obtain a passing result.

| Evidence | Result |
|---|---|
| `nli-quality-first-01.json` | Import failed in 6.39s: missing sanitized PATH caused Torch `KeyError`; no model inference |
| `nli-quality-path-fixed-02.json` | Real CPU inference; 20/24; 23.657s total; 796,401,664B peak RSS |
| `nli-quality-restart-03.json` | Independent fresh child; same fixture/predictions/probabilities; 20/24; 22.016s total; 796,807,168B peak RSS |
| `nli-unit-01.xml` | 71 passed, no failures/errors/skips, 3.068s |
| `nli-final-unit.xml` | 73 passed, no failures/errors/skips, 3.099s |

The PATH repair supplies only the real interpreter directory, not the user's
ambient PATH. Torch's installed `__init__.py:276` indexed the missing variable.
No package installation or shared-environment modification was required. The
initial successful inference script returned zero for execution despite semantic
failures; repaired its command contract so semantic failure exits **1**, runtime
failure exits **2**, and only a passed *synthetic challenge* exits zero. No exit
code implies GA/admission. The final restart correctly exited 1.

Restart warm timings (23 cases after first forward): median **125ms**, nearest-rank
p95 **141ms**, max **141ms**; first forward **219ms**, model load **2.531s**. This is
not an end-to-end app latency benchmark or all-low-end-hardware qualification.
Fixture hash is `e355eab49c6fd98e153dfc0d12e419e6da2a67f127e9c19c2af895466776e1bc`.
The two successful inference runs are repeated measurements of the **same 24
cases**, not 48 independent samples or attorney-reviewed gold.

Software tests cover input/label separation, strict output/finite probabilities,
incomplete/forged responses, semantic-failure exit status, and runtime-inclusive
download budgeting, plus existing acquisition/network guards. Ruff, formatting
and diff checks pass. No production service/API/UI/admission/version was changed
by this prerequisite. No frozen/installed/MSIX test or build was performed.

**Decision: RESEARCH_ONLY / SYNTHETIC_CHALLENGE_FAILED.** Keep this candidate out
of production labels and release claims. Next model work: predeclare a broader,
separate source-attribution/temporal challenge before implementing a model-backed
review path; explicitly distinguish absence of support from contradiction. Do
not silently collapse the observed errors or infer a finding from a classifier.
Once an evidence-backed behavior is selected, implement it through the protected
canonical service/UI and real artifact drill-down, not a new static preview.

Cleanup of the two exact `dist/qa/nli-qualification-*` basetemps was denied before
launch after path/reparse/process checks. Eight tiny fictional test files totaling
**50 bytes** remain; no deletion or bypass. Do not reuse those basetemp names.
The reusable `nli-scratch` directory is empty. Actual weights/receipts/evidence
are preserved, and all owned model processes stopped.

## Separate attribution challenge and verifier-boundary hardening — 01:20 UTC run

Read AGENTS/progress/Git/processes; no duplicate workload. Reused the exact NLI
weights, runtime and empty `nli-scratch`, with **no download or model/runtime
copy**. Added a separate, predeclared 36-case fictional challenge in
`scripts/compact_nli_attribution_challenge.py`: six categories (role, attribution,
time, scope, negation, authenticity), each balanced across entailment/neutral/
contradiction in two disjoint 18-case partitions. No calibration, threshold
tuning, training, prompt adaptation or expectation changes used either partition.
The second partition is a separate authored software evaluation, not attorney gold.

The qualification runner now selects only named fixed challenges; the parent
freezes expected pairs/labels before spawning the child, and the child echoes
their canonical hash. Only premise/hypothesis text reaches the tokenizer. Added
an exact worker-response schema so a child cannot overwrite host admission,
fixture identity or failure state through extra fields. Wrong hashes, unexpected
fields, network-attempt flags, invalid timing/memory/version values, empty
challenges and malformed outputs fail closed. Model scores still cannot certify
facts, authenticity, judicial findings, source completeness or current law.

**Real result: 26/36**, command exit **1** (semantic qualification failure).
`nli-quality-attribution-01.json` retains every expected label, probability,
prediction and confusion matrix:

| Partition | Correct | False entailments | False contradictions |
|---|---:|---:|---:|
| `cal` (18 cases; not fitted) | 14/18 | 0 | 4 |
| `eval` (18 separate cases) | 12/18 | 0 | 6 |
| Combined | 26/36 | 0 | 10 |

Of 12 neutral cases, nine became false contradictions. One positive role-matching
case was also called a contradiction (Reviewer Ash/yellow binder). All 12 explicit
contradictions were classified correctly. These failures are not relabeled as
abstentions or hidden behind a passing entailment-only statistic. Zero false
entailments on 24 negative examples is **not** a proven release false-pass rate.

Runtime: **21.875s** whole isolated run, **2.203s** model load, first forward
**250ms**, remaining 35 warm cases median **94ms**, nearest-rank p95 **125ms**;
worker-reported peak RSS **798,928,896 bytes**. Worker exited and Job/handles closed.
No Python network attempt was detected; no OS-level network certification or app
latency claim. Combined selected model/runtime footprint is unchanged at
1,298,907,053 bytes; its frozen dependency closure remains unqualified.

Fixture SHA-256:
`e6d1ccc7e8b1f7211dcb6cab2f8ef57b61cf01259274b784bd6f62be15db5937`.
The formatting-only corrections after inference preserve this exact fixture hash.

Tests: `nli-attribution-unit-01.xml` **28 passed**, 1.895s;
`nli-attribution-final-unit.xml` **132 passed**, 3.442s. Both zero failures/errors/
skips. The final run includes qualification, acquisition, network-tripwire and
ranker-process tests; counts overlap. Initial Ruff found three long source lines;
split adjacent string literals without changing text, then Ruff and diff checks
passed. No product API/UI/factory/admission/version changed in this run, and no
new feature is advertised as integrated. No frozen/installed/MSIX work performed.

**RESEARCH_ONLY / SYNTHETIC_CHALLENGE_FAILED remains the decision.** Do not expose
this candidate's contradiction labels or use it as an automatic claim verifier.
The remaining useful work is not repeated scoring of this same failing fixture:
continue the bounded source-bound Drafting path and runtime/license qualification
with existing artifacts; any proposed NLI integration first needs a defensible,
separately evaluated behavior rather than relabeling these errors to pass.

Evidence index: `verification-snapshot-nli-attribution.json` in the compact fleet
directory. All old cleanup-denied paths remain untouched. This pass's two QA
directories contain zero and four small fictional fixture files respectively
(**25 bytes** total). They were inspected for reparse points and active users;
no deletion was attempted this pass, and no space-recovery claim is made.

## Drafting handoff hardening — 2026-09-09

Continued the existing source-bound Drafting path; no new model or production
admission. Git main remains `82364d869b4d2d427b93f32b812e857d28cc3e38`.
Preserved all pre-existing changes, archives, release packages and model weights.

Defects repaired:

- The renderer now rejects mutated verifier envelopes, rehashed attempts to
  change review/filing/claim status, and invalid or boolean source indexes before
  indexing. This hash is internal integrity checking, NOT a signature/admission.
  The canonical runtime withholds output on these failures.
- The shipped answer-to-draft handler checks the result's originating matter.
  Local-model results missing that scope or explicitly withheld are not copied.
  An editor retains its original matter ID through save; the canonical create
  API rejects a changed matter with HTTP 409 and captures the destination root
  once. The new request field is optional for legacy API compatibility: this is
  a stale-editor guard, **not a new authorization or tenant-isolation mechanism**.
- Source/provenance references and a bounded host-written limitations note survive
  save/reopen in the immutable first revision. Partial model results remain marked
  partial; facts, law, relevance and freshness remain unverified. No arbitrary
  model-authored blocker string is promoted into that note.
- The first browser pass found the generic safe-error mapper hid the server's
  recovery instructions. Fixed the actual save handler to tell the user nothing
  was saved, editor text is preserved, and to reopen the original matter.

Verification:

| Evidence | Exact result | Boundary |
|---|---|---|
| `drafting-handoff-unit-01.xml` | 39 passed, 6.093s | Verifier, runtime, canonical save and shipped JS handlers |
| `drafting-handoff-browser-01.xml` | 1 failed, 38.023s | Wrong-matter save rejected; vague UI recovery message exposed |
| `drafting-handoff-browser-02.xml` | 1 passed, 6.229s | Fixed full shipped-page answer → editor → rejected cross-matter save → save/reopen |
| `drafting-handoff-regression-01.xml` | 178 passed, 1 skipped, 26.582s | Workspace, model scope, grounding, output, UI lifecycle and transcript regression |

The skip is `test_workspace_refuses_symlink_root`: Windows symlink privilege
unavailable. It is not relabeled a pass. Ruff check/format and JS syntax pass;
UI/API mirrors and `git diff --check` pass. Existing httpx/TestClient deprecation
warning remains. Counts overlap; do not sum them as unique tests.

Browser: Edge 152.0.4191.66, headless ephemeral context, 1440×1000, zero page errors
or observed external page requests. Four checked boundaries; screenshot/DOM and
canonical request results in `drafting-handoff-browser-02.ui.json`, its PNG and
`drafting-handoff-browser-02.json`. The model response was deterministic fictional
test input processed by the actual runtime verifier/renderer; startup/search
were fixtures, document API/storage were real. This is **not live model inference,
source-inspector coverage, frozen-app, installed-package or legal-quality proof**.
Browser and loopback server closed. No MSIX, model download/copy/training or push.

**Newly confirmed release blocker: draft-storage privacy.** The existing
`legal/documents/workspace.py` writes index/revision JSON with draft text, notes
and source references in plaintext (`_write_index`, `_write_revision`, and
commit/reject revision rewrites). The handoff does not fix encryption by claiming
that encrypted model audit receipts also encrypt documents. No real data was
used. Drafting is therefore NOT marked as a fully hardened/accepted vertical.

Next bounded vertical must address this storage boundary before admission:
use the existing protected-vault/envelope implementation; bind ciphertext to
matter and artifact identity; preserve readable legacy documents non-destructively;
cover create/propose/commit/reject/reopen and intentional exports; verify wrong
key, tampering, cross-matter substitution, interrupted writes, restart, backup
and migration behavior. Inventory every direct JSON reader before changing the
format. Do not silently make old releases unable to recover existing documents.
Production role/tenant checks and source-drill-down still need complete evidence
for the saved-specialist-draft path, independently of the passing stale-editor
guard. The model quality, native admission, licenses, OS network and final package
blockers recorded above are unchanged. No additional specialist is GA-approved.

## Draft storage encryption — 2026-09-09

This pass addresses the plaintext index/revision boundary discovered above.
It is a joined new-workspace storage vertical, not complete Drafting, whole-matter
privacy, specialist quality, frozen-runtime or release certification. Git main
remains `82364d869b4d2d427b93f32b812e857d28cc3e38`; version unchanged.

Implementation and defects repaired:

- `legal/documents/storage.py` uses the existing protected local key and AES-GCM
  envelope. New indexes/revisions, including temporary write bytes, are encrypted.
  Authenticated contents bind the workspace identity and relative artifact path.
  Only the current envelope algorithm/KDF and exact bounded field shape are
  accepted; the shared decryptor's historical demo-format compatibility is NOT
  inherited by this new storage format. Wrong keys, malformed envelopes,
  ciphertext edits, path/workspace substitution and plaintext downgrade fail closed.
- `legal/documents/workspace.py` reads/writes through that codec and exposes a
  canonical revision reader. Creation, proposal, commit/reject, soft-delete/restore,
  save/reopen, intentional export and safe error paths retain review-required status.
  Original committed revision bytes remain unchanged by later revision actions.
- The first broader regression exposed four filing-packet failures: its revision
  loader still parsed plaintext directly. `legal/review/filing_packet.py` now uses
  the canonical encryption-aware reader; existing content-hash checks remain.
- Both actual production JS/CSS mirrors expose storage scope and recovery guidance.
  Legacy workspaces retain their original files and readable text, while editing,
  save/propose/commit/reject/delete/restore controls are disabled. The server rejects
  new JSON writes to those stores independently of the UI. No silent migration.
- Visual inspection rejected the first browser pass despite its passing text
  assertions: the new notice was clipped by flex shrinking. A scoped CSS repair
  and geometry assertions now prove the whole notice fits and does not overlap
  the editor. The final legacy screenshot was visually inspected as well.

Verified boundaries include per-file interrupted atomic replacement, a fresh
interpreter reopen, complete fictional backup relocation with the original key,
and the existing `ProductivitySuiteStore` incremental backup/restore service.
The latter restores into its isolated recovery directory, not over a live matter.
No actual private matter, user vault, model directory or runtime was copied.

Important remaining limits:

- **Legacy migration remains a release blocker.** Existing plaintext drafts are
  readable but intentionally read-only. Do not ship this as a seamless upgrade
  or tell users to delete identity/key files. Next implement an explicit,
  previewed migration with a verified recovery copy, content/ID/history hashes,
  interrupted-transition recovery, canonical matter/role enforcement and an
  actual production UI action. Preserve existing files until recovery is proven.
- Imported originals, explicit exports, audit metadata and other review sidecars
  are not encrypted by this layer. `all_workspace_files_encrypted` remains false.
  Audit validity tests do not establish authenticated whole-matter audit security.
- Complete workspace plus identity remains intentionally portable with its key;
  this is artifact substitution protection, not a replacement for API authorization.
  Full role/tenant/source-inspector qualification remains separately required.
- Multi-file transaction crash recovery, cross-machine protected-key recovery and
  low-end hardware latency were not proven by these per-file/restart fixtures.
- Browser tests use actual shipped assets and canonical document routes/storage,
  but deterministic fictional model output and startup/search fixtures. No model
  inference, frozen app or installed package was tested in this pass. Browser
  and loopback server shut down. Page-observed zero external requests is not an
  OS-level zero-network certificate.

No model download, training, model/runtime copy, MSIX build, version change,
publication, commit or push. All new QA data stays under repository `dist`.
Historical cleanup-denied paths remain untouched; no deletion or reclaimed-space
claim. New fixture directories contain only small fictional workspace data.

Exact verification receipts (all under `dist/model-candidates/compact-fleet-20260908`):

| Receipt | Result | Seconds |
|---|---|---|
| `workspace-encryption-unit-01.xml` | 27 passed, 1 skipped | 115.939 |
| `workspace-encryption-regression-01.xml` | 62 passed, 4 failed, 1 skipped; plaintext filing reader found | 95.833 |
| `workspace-encryption-regression-02.xml` | 66 passed, 1 skipped; filing reader fixed | 162.327 |
| `workspace-encryption-final-envelope.xml` | 73 passed, 1 skipped; strict envelope rejection added | 138.239 |
| `workspace-encryption-browser-01.xml` | 1 passed automatically; subsequent visual review found clipping | 22.615 |
| `workspace-encryption-browser-02.xml` | 1 passed; notice geometry repaired and checked | 14.509 |
| `workspace-encryption-browser-final.xml` | 1 passed; legacy read-only interaction added | 17.736 |
| `workspace-encryption-browser-envelope-final.xml` | 1 passed against final codec; seven joined checks | 12.101 |

Counts overlap: do not sum iterations as unique tests. The one regression skip
is `test_workspace_refuses_symlink_root` because Windows symlink privilege is
unavailable. Existing Starlette/httpx deprecation warning remains. Six modified
Python modules parse; focused Ruff check/format, both JS syntax checks, harness
syntax, mirror-byte equality and `git diff --check` pass.

Final regression command, using the existing Store Python runtime and a fictional
`MAINE_MATTER_STORE_KEY`, `PYTHONDONTWRITEBYTECODE=1` and installed Node on PATH:

```powershell
dist/build-env/store/Scripts/python.exe -B -m pytest tests/test_document_workspace_encryption.py tests/test_drafting_handoff.py tests/test_v520_document_workspace.py tests/test_v520_document_workspace_api.py tests/test_v520_document_workspace_ui.py tests/test_v570_revision_bound_review_ledger.py tests/test_v570_review_workbench_ui_api.py tests/test_v5140_reviewed_filing_packet.py -q --tb=short -p no:cacheprovider --basetemp dist/qa/workspace-encryption-final-envelope --junitxml dist/model-candidates/compact-fleet-20260908/workspace-encryption-final-envelope.xml
```

Final browser command uses `MFL_DRAFT_HANDOFF_BROWSER=1`,
`MFL_DRAFT_HANDOFF_ID=encrypted-envelope-final`, `MFL_PROOF_NODE` and
`MFL_PROOF_NODE_MODULES` pointing to the existing bundled Node/Playwright runtime:

```powershell
dist/build-env/store/Scripts/python.exe -B -m pytest tests/test_drafting_handoff_browser.py -q --tb=short -p no:cacheprovider --basetemp dist/qa/workspace-encryption-browser-envelope-final --junitxml dist/model-candidates/compact-fleet-20260908/workspace-encryption-browser-envelope-final.xml
```

Do not reuse these basetemp names: pytest may implicitly delete an existing path.
Final DOM/screenshots, canonical requests and storage receipts are in
`drafting-handoff-browser-encrypted-envelope-final.ui.json`, its `.ui.png` and
`.ui.legacy.png`, and `drafting-handoff-browser-encrypted-envelope-final.json`.
Browser Edge 152.0.4191.66, ephemeral context, 1440x1000, zero page errors or
observed external page requests. Hash-index all receipts, source changes and
historical failures in `verification-snapshot-workspace-encryption.json`.

**Next action:** close the reviewed legacy migration and private-review-sidecar
boundaries through service → canonical API → protected matter scope → actual
production UI → fictional migration/recovery action → tests. Do not count a
static migration notice as that implementation. Only after the complete Drafting
privacy/interaction path passes should its admission/packaging qualification resume.

## Legacy migration review — 2026-09-09 02:50 UTC heartbeat

Read AGENTS and the complete progress history; verified Git root/main/HEAD and
preserved all existing changes. No owned model/test workload was active. This
pass implemented the **review prerequisite**, not the full migration executor
or a completed Drafting feature. No legacy workspace was converted.

Joined path: actual drafting UI → explicit inspection → canonical scoped POST
`/api/document-workspace/migration-review` → bounded real index/revision scan
→ encrypted audit receipt → visible blockers and keyboard hash disclosure →
open the original read-only draft. Startup/search/model text in the browser
harness remain fictional doubles; document APIs, inspection and storage are real.

- `legal/documents/migration_review.py` bounds the inventory to 256 JSON files
  and 16 MiB. It checks index schema, document/revision identity, exact content
  hashes, references, allowed statuses, reparse components, missing/unindexed
  documents and changes to bytes or file membership during the scan. It does not
  return private text or absolute paths. Originals, exports and other review
  sidecars remain explicitly outside this inventory's qualification.
- `app/api/document_migration.py` reuses the canonical explicit local
  role/tenant/session identity and active-matter resolver, checks scope again
  after scanning and requires a successful encrypted audit write before release
  of the inventory. Invalid requests do not echo arbitrary private extra fields.
  This is the existing desktop identity model, **not new multi-user tenant ACL
  certification**. Full legacy document API role/tenant qualification stays open.
- Both API and production JS mirrors expose this same route/action. UI responses
  are bound to a request epoch/matter; refresh and corpus changes invalidate the
  old review. Reinspection replaces rather than duplicates its disclosure.
  Safe failure guidance preserves documents; migration/filing readiness stays false.
- A native disclosure exposes exact revision IDs, stored-file SHA-256 and sizes.
  Its action is accurately labeled **Open current draft**, not “open this historical
  revision.” The first visual inspection found the hash crowding that button.
  Fixed with separate stacked text/action elements and actual geometry assertions.

Evidence under `dist/model-candidates/compact-fleet-20260908`:

| Receipt | Exact result | Seconds |
|---|---|---|
| `document-migration-review-01.xml` | 10 passed; zero failures/errors/skips | 13.793 |
| `document-migration-regression-01.xml` | 63 passed; zero failures/errors/skips | 59.204 |
| `document-migration-review-final.xml` | 13 passed; adds audit-failure, route registration and validation privacy | 4.098 |
| `document-migration-browser-01.xml` | 1 automated pass; visual inspection found crowded hash/action | 14.925 |
| `document-migration-browser-final.xml` | 1 passed; eight joined checks, corrected geometry | 16.138 |

Counts overlap and are not independent quality samples. The regression includes
`test_document_migration_review.py`, `test_document_workspace_encryption.py`,
`test_drafting_handoff.py`, `test_v520_document_workspace_api.py` and
`test_v520_document_workspace_ui.py`. Commands use the existing Store Python:
`dist/build-env/store/Scripts/python.exe -B -m pytest <named tests> -q --tb=short
-p no:cacheprovider --basetemp dist/qa/document-migration-regression-01
--junitxml dist/model-candidates/compact-fleet-20260908/document-migration-regression-01.xml`.
Final review-only run substitutes its test filename and `document-migration-review-final`
basetemp/receipt. A fictional key and `PYTHONDONTWRITEBYTECODE=1` keep test state
within the repo; existing TestClient deprecation warning remains.

Browser uses `tests/test_drafting_handoff_browser.py`, opt-in
`MFL_DRAFT_HANDOFF_BROWSER=1`, `MFL_DRAFT_HANDOFF_ID=migration-review-final`,
existing Node/Playwright variables, `dist/qa/document-migration-browser-final`
and the named final JUnit receipt. Edge 152.0.4191.66, ephemeral context,
1440x1000. Zero page errors/observed external page requests, owned browser/server
closed, originals byte-identical. Browser/verification skills guided the full
flow and visual review using existing Playwright because agent-browser is absent.
Final screenshot `drafting-handoff-browser-migration-review-final.ui.migration.png`
was inspected; matching `.ui.json` and API JSON retain requests/DOM/evidence.
No inference, OS-level network observation, frozen/installed or Store proof.

Five modified Python modules parse; focused Ruff, both production JS/harness
syntax, API/UI mirror equality and `git diff --check` pass. No model download,
training, runtime/model copy, MSIX, version change, commit, push or external work.
All five new QA folders hold **204,595 bytes** of fictional fixtures. No cleanup
attempt, deletion or reclaimed-space claim; historical denied targets untouched.

**Next implementation, not another unchanged review test:** a reviewed,
content-hash-bound migration executor with a verified recoverable original copy,
bounded capacity preflight, journaled interrupted-transition recovery and explicit
confirmation through this canonical UI. Inventory private review sidecars before
selecting an all-workspace conversion strategy; do not blindly rename the live
directory or strand consumers of historical revision paths. Recovery must preserve
IDs, notes, hashes, original text and audit/review history. Keep legacy writes
blocked until that executor/recovery path passes. No migration button should
claim success before actual conversion and reopen verification.

Specialist semantic quality, native admission, licenses/closure, OS networking,
full app/frozen/installed qualification remain blocked and unchanged. This
review prerequisite does not close the complete Drafting vertical. Continue the
existing automation; independent authorized work remains and no user decision
is required at this point. Evidence index: `verification-snapshot-migration-review.json`.

## Confirmed legacy JSON migration — 2026-09-09 03:20 UTC heartbeat

The prior read-only review now connects to a **real confirmed conversion**.
Scope is strictly the inspected draft index/revision JSON, NOT all matter files.
Git main/HEAD unchanged; existing user/source/model/archive changes preserved.
AGENTS/progress and owned-process checks found no duplicate workload.

`legal/documents/migration.py` stages encrypted replacements and byte-exact
encrypted originals under one workspace-local transaction. It checks the reviewed
manifest again, reserves disk capacity (eight times inspected bytes plus reserve),
verifies every original/replacement/preimage, then publishes an authenticated
pending journal before installing the storage identity and replacing live JSON.
No live directory rename, unrelated-file rewrite or plaintext recovery copy.
The 256-file/16-MiB inventory bound remains. Failed preparation reuses its one
authenticated staging directory only when the original preview still matches.

The final receipt has an authenticated completion flag. Pending transactions
revalidate and resume under a process/file lock on workspace open; altered live
files or corrupt staging are refused, not overwritten. A completed workspace
can be copied/restored elsewhere with its identity/key; a pending transaction
remains location-bound. Internal `original_snapshot` recovers exact original
bytes without restoring them over live files, including when a candidate is
corrupted. Authenticated status no longer falsely says migration never occurred.

Canonical POST `/api/document-workspace/migration-execute` requires exact
preview hash, strict explicit confirmation, local admin role and active scope.
It records encrypted confirmation/completion audit events and captures the
original root. The automatic recovery journal is authenticated; a crash-resumed
operation need not have reached the API completion audit event. That distinction
is retained rather than claiming every interrupted request returned success.

Actual UI: inspect → keyboard ID/hash disclosure → decline with **zero execution
requests** → confirm scope/key/recovery warning → execute → reopen identical
draft text with editing restored → visible review-required completion receipt.
The first screenshot caught completion being overwritten by “Opening…”; moved
the final message after reopen. A later visual check found tiny status text;
raised workspace feedback to 14 px, nonshrinking, and checked full text height.
No legal/filing status or model admission becomes approved through migration.

All receipts below are under `dist/model-candidates/compact-fleet-20260908`:

| Receipt | Result | Seconds |
|---|---|---|
| `document-migration-execute-01.xml` | 22 passed, zero failures/errors/skips | 50.232 |
| `document-migration-execute-regression.xml` | 98 passed, 1 skipped; before final completion/relocation checks | 187.429 |
| `document-migration-execute-final.xml` | 48 passed, zero failures/errors/skips; final service/API/storage | 90.064 |
| `document-migration-execute-browser-01.xml` | 1 pass; UI completion timing subsequently repaired | 21.634 |
| `document-migration-execute-browser-final.xml` | 1 pass; completion after reopen | 20.626 |
| `document-migration-receipt-browser-final.xml` | 1 pass; final authenticated receipt/status | 20.266 |
| `document-migration-readable-browser-final.xml` | 1 pass; nine joined checks and readable receipt | 19.731 |

Tests exercise preparation, identity, live revision/index and receipt faults;
no duplicate stage on retry; stale preview, missing confirmation/admin, wrong
matter, capacity denial, corrupted replacement, changed live file, exact original
recovery and relocation of a completed fictional workspace. **Real crash drill:**
a disposable child calls `os._exit(71)` after replacing a live revision; a fresh
interpreter resumes the journal and reads the original content. This is process
crash evidence, NOT power-loss, disk-controller failure or cross-user key recovery.

Regression command: existing Store Python `-B -m pytest` with
`test_document_migration_execute`, `test_document_migration_review`,
`test_document_workspace_encryption`, `test_drafting_handoff`,
`test_v520_document_workspace`, `test_v520_document_workspace_api`,
`test_v520_document_workspace_ui`, `test_v570_revision_bound_review_ledger`,
`test_v570_review_workbench_ui_api`, `test_v5140_reviewed_filing_packet`
(all `tests/*.py`), `-q --tb=short -p no:cacheprovider`, repo-local basetemp
`dist/qa/document-migration-execute-regression`, and the named JUnit receipt.
Final 48-test command uses the first three files and
`dist/qa/document-migration-execute-final`. Fictional key/bytecode/cache settings
remain as above. One broader-suite skip is unavailable Windows symlink privilege.
Existing TestClient deprecation remains. Overlapping runs are not unique samples.

Final browser uses the existing handoff harness with
`MFL_DRAFT_HANDOFF_BROWSER=1`, `MFL_DRAFT_HANDOFF_ID=migration-readable-final`,
existing Node/Playwright variables and basetemp
`dist/qa/document-migration-readable-browser-final`. Edge 152.0.4191.66,
1440x1000 ephemeral context; zero page errors/observed external page requests.
Final `.ui.migrated.png` visually inspected; `.ui.json` reports font 14 px,
height/scrollHeight both 58 px. API receipt independently decrypts the recovery
originals and compares their exact pre-migration bytes. Owned child/browser/server
processes all closed. Startup/search/model response remain fictional fixtures:
**no model inference, frozen or installed package was tested here**.

Ruff, both JS/harness syntax, API/UI mirror equality and diff checks pass. Initial
lint caught fixture-import naming and one long test string; repaired without
removing assertions. No runtime/model copies, downloads, training, MSIX, version
change, commit, push, private corpus use or external scratch folders. This pass's
seven QA directories total **1,102,981 bytes** of fictional data. No deletion or
reclaimed-space claim; historical cleanup-denied targets untouched.

Remaining limits and next work:

- Inventory/encrypt the other private review sidecars through their actual
  consumers and UI before claiming the whole Drafting storage boundary complete.
- Large bounded migrations need measured latency/progress/cancellation, and an
  operator-facing recovery path for corrupted journals/stages or moved pending
  transactions. A repeated execute after completion currently refuses a new
  legacy migration; normal reopen shows verified completed storage. Do not label
  all of these failure/upgrade paths a seamless GA experience yet.
- Full legacy API tenant/role qualification, OS protected-key recovery on another
  machine, full app regression and frozen/installed qualification remain open.
- Specialist semantic failures, signed native admission, runtime/license closure
  and OS-level network evidence are unchanged. No specialist became GA-ready.

Continue independent authorized hardening; do not repeat unchanged model failures
or count this as model training. Evidence index:
`verification-snapshot-confirmed-migration.json`.

## Encrypted revision-bound reviews — 2026-09-09

### Implementation and user action

- `legal/review/review_ledger.py` now encrypts new requests (including fact spans)
  and decisions (including reviewer notes) before any temporary write. It reuses
  the existing protected-key workspace codec with workspace/path binding, strict
  envelope validation, bounded reads and durable atomic writes.
- A reentrant, workspace-local cross-process lock serializes review operations.
  Two real Python processes presenting one confirmation token produce exactly
  one committed decision and one blocked attempt. A partially consumed request
  cannot create a second decision. This is not an external immutable audit anchor.
- Historical plaintext records remain untouched and inspectable but do not count
  as authenticated approval. Invalid/legacy decision history blocks subsequent
  approval and filing consumption; the UI directs the user to preserve history
  and create a new working draft for a fresh review. No silent legacy migration.
- Filing packets and authority-change impact now read requests through
  `read_review_request`; neither falls back to an older approval when the latest
  history fails authentication. Existing private filing packet exports and
  assignment files are NOT encrypted by this change.
- Five existing canonical review routes require explicit local role, tenant,
  client session and expected active-matter headers. Content-free access receipts
  use the encrypted local-agent audit chain. A failed pre-action audit prevents
  writes; completion-audit failure returns an error instructing history reload.
  These local headers are not independent multi-user identity authentication.
- The shipped workbench sends the expected matter, discards stale results,
  prevents duplicate decision clicks, shows encryption/revalidation limits,
  retains review blockers and opens matched indexed record text with source ID,
  hash, offsets and the private-record-versus-authority distinction. Source offsets
  now use original-string matches rather than expanded casefold positions.
- Review detail text and controls are at least 14px; stacked signoff controls
  avoid clipped option labels. Both production asset/API mirrors match.

### Evidence and exact scope

- `review-encryption-01.xml`: 19 passed, 0 failed, 75.149 seconds.
- `review-storage-boundary-01.xml`: 11 passed, 0 failed, 21.471 seconds.
- `review-storage-boundary-final.xml`: 16 passed, 0 failed, 34.890 seconds,
  including cross-workspace substitution, wrong key/ciphertext/plaintext,
  missing scope, different tenant, audit failure, private validation error,
  canonical route uniqueness, Unicode source offsets and two-process replay.
- `review-storage-regression-final.xml`: 40 collected, 33 passed, 7 failed,
  107.871 seconds. All seven failed in the authority-generation fixture before
  reaching the changed consumer: repo-local synthetic data was being described
  as external to the real checkout. This failed run is retained, not suppressed.
- `review-authority-fixture-final.xml` retains the intermediate fixture repair:
  service generation cases recovered; API cases still used real configuration.
  The final fixture uses two repository-local sibling identities and explicitly
  fictional API configuration, while real publisher/verifier/impact isolation
  remains active. No production isolation function is monkeypatched or changed.
- `review-authority-fixture-verified.xml`: 8 passed, 0 failed, 42.455 seconds.
  Together with the 19 review/filing regressions and final 16 boundary tests,
  all 43 distinct focused service/API tests pass; the shipped-page browser proof
  is a separate passing test (44 distinct tests across these runs, not a full suite).
- Browser first attempt failed solely on a hard-coded expected source length
  (35 versus actual 37); the source was correct. The screenshot exposed tiny
  controls, which were repaired. Historical failures/screenshots remain available.
- `review-storage-browser-readable.xml`: 1 passed, 0 failed, 40.021 seconds.
  Its `drafting-handoff-browser-review-storage-readable.ui.json` records 10 joined
  actions: shipped page, source-bound handoff, wrong-matter save denial,
  save/reopen, review prepare, keyboard source drill-down, blocked decision,
  encrypted persistence and reopen, plus the earlier confirmed JSON migration.
  This uses real canonical review/document APIs and storage, but fictional
  authority/indexed-record configuration and a deterministic model-response double.
  It is NOT model inference, frozen executable or installed MSIX proof.
- Python syntax passed for the five changed production Python files. JavaScript
  syntax, mirrored hashes and `git diff --check` passed. Focused new tests and
  review modules pass Ruff F checks; the existing API still has five unrelated
  unused imports, and full legacy-file Ruff includes existing style debt. No
  whole-repository lint/regression success is claimed.

### Remaining work / next boundary

1. Resume from `verification-snapshot-encrypted-reviews.json`, preserving the
   failed/intermediate and final passing evidence. No current process is left running.
2. Qualify authenticated review-history head anchoring/truncation detection and
   legacy-review recovery/migration without rewriting historical approvals.
   New ciphertext authentication does not alone prove complete-history retention.
3. Inventory filing assignments, generated packets and authority-impact private
   sidecars before extending encryption; protect all canonical and alias readers.
4. Authority configuration still depends on the working directory in some
   constructor boundary checks; test and harden this as its own coherent vertical.
5. Full multi-user role/tenant authentication, broad regression, large-matter
   performance/cancellation, frozen/installed verification and protected-key
   disaster recovery remain unqualified.
6. Specialist semantic failures, native signed admission, runtime/license closure
   and OS network proof remain unchanged. No new model run, download, training,
   version change, MSIX, commit, push or promotion occurred in this pass.

All QA fixtures and compact evidence remained under this repository's `dist`.
No runtime/model copies, external scratch directories or deletion attempts.
Continue the next full vertical; do not represent this pass as specialist GA.

## Retained review head and interrupted commit recovery — 2026-09-09

### Delivered path

- `legal/review/integrity.py` provides an encrypted, workspace/path-bound local
  head with expected decision count and final chain hash. A missing newest
  decision, missing head with retained history, corrupt head, reordered or
  identity-mismatched decision blocks review trust and filing consumption.
- Existing history is never silently sealed/promoted. A fresh review initializes
  an empty head only when no decisions already exist. Legacy/unsealed history is
  preserved and requires a new working draft for a fresh review.
- A single encrypted pending journal binds the already-confirmed decision,
  consumed request and previous request hash before the first decision write.
  Recovery checks all existing chain entries and the unchanged request before
  finishing. It never overwrites a changed or corrupt existing record.
- The existing cross-process review lock covers journal, decision, consumption
  and head advancement. Interrupted writes resume on canonical review access.
  The head records that recovery occurred, and replay still cannot add a second
  decision. The journal does not run models or take a new review decision.
- Canonical API receipts distinguish observed recovery from integrity blocking.
  They contain hashes, not private notes. Recovery does not make a stale revision
  current or confer filing approval. Reviewer queue status/filing flags now agree
  with the current revision and verified history.
- Production UI explicitly explains recovered decisions and incomplete history.
  A discovered control-reset bug was fixed: document refresh can no longer
  re-enable blocked review buttons or display a green document-open status while
  review history is incomplete. Legacy draft storage also keeps review mutations
  disabled until migration. API/UI mirrors remain synchronized.

### Tests and limitations

- `review-head-01.xml`: 23 passed, 0 failed, 97.882 seconds.
- `review-head-regression.xml`: 50 passed, 0 failed, 395.311 seconds, including
  prior privacy, canonical API, revision review, filing packet and fictional
  authority-change consumer regressions.
- `review-head-final.xml`: 17 passed, 0 failed, 140.627 seconds. Includes two
  additional cases: a recovered decision stays stale after a changed draft,
  and a corrupt encrypted head fails closed without being repaired/overwritten.
  Across the focused runs there are 52 distinct service/API tests, not a full
  repository suite. The browser proof is a separate test.
- Real-process proof deliberately exits the child Python process with code 73
  after its durable decision write, then recovers in a fresh process. Three
  separate interrupted-write phases are also tested. This is not proof against
  storage hardware failure, every Windows shutdown mode or power loss.
- First browser run failed because shared controls re-enabled review preparation
  after incomplete-history rendering. Failure DOM/screenshot/XML are retained.
  The repair passed `review-head-browser-02.xml`: 1 test, 90.129 seconds. It uses
  the shipped workbench and canonical API/storage, explicit fictional authority
  and indexed-record configuration, and a deterministic model-response double.
- Final gating run `review-head-browser-final.xml` found a second timing bug:
  a delayed refresh could enable commit during recovery. Both UI mirrors now
  use a shared review-busy flag and stale-history/document-open response epochs.
- `review-head-browser-busy-guard.xml` did NOT pass: it timed out at the harness's
  100-second child-process limit (108.803 seconds total pytest time). The new
  recovered/truncated UI screenshots and completed API trace were preserved,
  but the whole joined journey did not finish. Do not call the current assets
  fully E2E certified from the earlier passing browser run.
- The final trace reached legacy migration execution (200) and review/history
  reopen after successful review recovery/truncation actions. Small-fixture
  review API calls took roughly 5–12 seconds, including an 11,797 ms review-queue
  response. This is a release-blocking qualification/performance finding, not an
  unexplained environment excuse. Profile duplicate head/request decryption and
  repeated UI refreshes, fix latency without weakening key derivation, then run
  the full final journey again. Do not merely raise the timeout and claim speed.
- No real matter/corpus, live model, frozen executable, installed package, model
  acquisition/training, version bump, MSIX build, commit or push was involved.
- A retained local head detects inconsistency relative to that head. It is NOT
  an external timestamp, independent immutable audit anchor or proof against
  replacing the entire workspace (head included) with an older complete copy.
- Large-matter latency/cancellation and full multi-user authentication remain
  unqualified. The timings above include encryption, API/harness setup and
  synthetic actions; do not relabel them model inference performance.

### Next independent work

1. Read `verification-snapshot-review-head.json` and the final timeout trace.
   Prioritize small-matter review latency and robust bounded browser-run cleanup,
   then repeat final UI qualification. Keep the current status BLOCKED for final
   UI acceptance. All 52 distinct focused service/API tests passed, not the final
   combined browser run. Preserve historical failures as well as passing results.
2. Continue the private-sidecar inventory: filing assignments, generated packets
   and authority-impact artifacts, including every canonical/alias consumer,
   scoped audit, actual UI action and recovery. Do not encrypt bytes without
   updating all readers or confuse intentional exports with encrypted storage.
3. Harden the authority configuration constructor boundary independently of the
   process working directory; the prior fixture finding remains an open issue.
4. Continue compact specialist semantic/admission/runtime-license work only with
   a changed hypothesis or input. Existing model failures remain genuine GA
   blockers; review-history work does not promote any specialist.

All scratch remains in repository `dist`; no model/runtime copies or external
QA directories. Fresh fictional test records were removed only for deliberate
corruption/truncation tests. All owned test/browser processes are stopped.
The timed-out browser left a 17,653,178-byte generated profile at
`dist/qa/review-head-browser-busy-guard/test_shipped_draft_save_reopen0/playwright_chromiumdev_profile-QQZQcj`.
Its verified, scoped cleanup was rejected by tool policy: zero bytes reclaimed.
Do NOT retry its deletion through another tool, shell, parent-directory cleanup,
or pytest basetemp reuse. The profile remains for user-managed cleanup.

## Review read budget and reviewer-input isolation — 2026-09-09

Status: **PASS_FOCUSED_REVIEW_VERTICAL**. This supersedes the preceding final
source-UI timeout blocker for this narrow joined journey, not model or release GA.
The previous failed runs and immutable snapshots remain preserved.

### Implementation and measured behavior

- `legal/review/review_ledger.py` now verifies the same authenticated decision
  rows that history/commit just read, rather than reading/decrypting them again.
  Queue history and pending packet summaries share one locked operation. There
  is no cross-request plaintext cache, KDF reduction or encryption-format change.
- `legal/documents/workspace.py` supports omitting archival revision history for
  internal review reads. The current revision is STILL decrypted and its content
  hash checked. Existing API/default document responses retain revision history.
- `legal/review/reviewer_queue.py` uses the current revision from the authenticated
  history response, not the earlier inventory, and retains all blocking states.
- A real-encryption fictional one-document queue dropped from 12 decryptions to
  7. Single-run service timing was 2.953 seconds before and 1.125 seconds after.
  This is a bounded local observation, not a hardware-independent performance SLA.
- Browser verification found an additional privacy/interaction defect: reviewer
  notes remained visible after changing matters. Both production JS mirrors now
  clear uncommitted facts, notes, reviewer identity, claim annotations and exact-
  revision attestation on a new document/matter. They reset the decision to request
  changes; committed notes remain available only in their own encrypted history.
- The browser runner preserves content-limited fictional progress evidence and
  closes its own ephemeral browser on its 90-second watchdog, before the unchanged
  100-second parent timeout. No timeout was increased to manufacture a pass.

### Verification

- `review-budget-before.xml`: intentional red regression demonstrating duplicate
  reads before repair; corresponding counts/timing in `review-budget-before.json`.
- `review-budget-regression.xml`: 34 passed, 0 failures, 121.122 seconds.
- `review-budget-consumers.xml`: 89 passed, 1 skipped, 0 failures, 336.719 seconds.
  Includes draft storage/migration, canonical review routes, filing-packet and
  authority-impact consumers, read budgets and reauthentication after corruption.
  Skip: Windows symlink privilege unavailable; this is NOT a passing symlink test.
- `review-budget-browser.xml`: initial complete joined journey passed; 65.491
  seconds pytest. Subsequent screenshot inspection caught the reviewer-input
  carry-over, so that image alone was not accepted as final isolation evidence.
- `review-budget-browser-isolation.xml`: final assets passed, 95.231 seconds
  pytest / 92.406 seconds API harness including post-browser storage assertions.
  All 13 browser checks passed: shipped page, source-based draft handoff, wrong-
  matter rejection preserving editor text, save/reopen, exact private-source
  drill-down, encrypted decision, interrupted-write recovery, history truncation
  blocking, readable notices, input isolation, legacy read-only behavior, inventory
  hashes and confirmed migration/reopen with exact recoverable originals.
- Deduplicated final coverage: **123 passed, 1 skipped, 0 failures** (122 focused
  service/API/contract tests plus one browser test). This is NOT the full app suite.
- Final observed canonical queue requests: 766–4,657 ms, mean 2,262.6 ms over
  15 requests. The earlier 11,797 ms response was reduced, but small-matter latency
  is still variable; large-matter behavior and cancellation are not qualified.
- No page errors or browser-origin external requests observed. These checks are
  not an OS-wide zero-network measurement. Model/authority results are fictional
  fixtures; no real model inference or legal-quality validation was performed.
- Python syntax (four changed files), production JS/harness syntax, focused Ruff,
  mirror equality and `git diff --check` pass. No source files changed after the
  final applicable tests, other than this progress/evidence documentation.

### Evidence and boundaries

All evidence is under `dist/model-candidates/compact-fleet-20260908/`:
`review-read-budget-acceptance.json`, the XML/JSON files above, and
`drafting-handoff-browser-read-budget-isolation-20260909.ui.*` screenshots.
`verification-snapshot-review-read-budget.json` hashes the retained evidence and
current source. `freeze_review_read_budget.py` records exact deduplicated tests.

All owned test servers/browser processes stopped. Both new browser profiles were
automatically removed on normal close. Small fictional fixtures/evidence remain
inside repository `dist`; no model/runtime copy or external QA directory was made.
The older policy-denied 17,653,178-byte profile was not touched or retried.

Next full vertical: finish private filing/assignment/authority-impact sidecar
privacy and consumer/UI recovery, then large-matter review progress/cancellation.
Production specialist semantic quality/admission, native runtime notices, OS-level
network evidence and exact frozen/MSIX qualification remain release blockers.
No models trained/downloaded, version changed, MSIX built, commit or push made.

## Encrypted reviewer assignments and scoped packet access — 2026-09-09

Status: **PASS_FOCUSED_ASSIGNMENT_VERTICAL**, not specialist or release GA.

The next sidecar audit found plaintext reviewer labels/notes and packet JSON
routes missing the explicit expected-matter/session checks already used by the
review ledger. `legal/review/filing_packet.py` now writes the assignment ledger
as workspace/path-bound authenticated ciphertext, atomically under a process
file lock. The historical filename remains `assignments.jsonl`, but new content
is a versioned encrypted envelope. Consumers decode and verify the event chain;
only authenticated assignments for the current revision count as active.

Legacy plaintext bytes are preserved, inspectable and NOT active authorization.
New assignment writes to a legacy ledger fail closed pending an explicit reviewed
migration. No silent conversion, deletion or promotion of old metadata occurs.
Exported packets remain separate unencrypted artifacts, explicitly disclosed in
the UI; this does not claim all workspace sidecars are encrypted. A whole-ledger
backup rollback is not externally anchored, and labels do not verify credentials.

Both API mirrors now scope/audit the six packet JSON routes: status, diff, read
assignments, assign, build and verify. The existing artifact-token boundary remains
in place. Production JS supplies the expected matter and guards stale responses.
The assignment UI exposes encrypted/legacy state, loading/error behavior, exact
revision and event SHA-256 inspection, and review-required/identity limitations.
Legacy mutation is disabled; labels and packet approvals clear on document/matter
change. Assignment actions require confirmed authenticated storage status.

Browser testing caught an actual initial-load navigation race: a user selection
could be superseded by workspace initialization and leave a blank new draft.
The UI now installs matter ownership before presenting selectable documents, and
respects a newer selection instead of resetting it after asynchronous loading.
The second run exposed a test-ordering issue: the harness switched matters before
reopening finished. The API correctly rejected stale scope; the test now awaits
the fresh response and completed document-open state. Both failures are retained.

### Exact verification

- `assignment-privacy.xml`: 35 passed, 1 failed. The wrong-key test expected the
  assignment exception, but draft authentication correctly rejected the key first.
  The expectation was corrected to accept either safe authentication boundary.
- `assignment-privacy-final.xml`: 61 passed, zero failures/skips, 234.135 seconds.
  Includes encrypted reopen, changed revision, legacy inspection, wrong key,
  changed ciphertext, cross-matter ciphertext, exclusive-thread conflicts, atomic
  write failure preservation, six-route role/session/tenant/matter checks, encrypted
  audit and audit failure, plus review-ledger/packet regression consumers.
- `assignment-browser-privacy-final.xml`: 1 passed, 38.360 seconds pytest;
  browser 33.914 seconds, API harness 34.891 seconds. Five joined checks passed:
  actual navigation, create plus revision/hash drill-down, reopen, wrong-matter
  denial, and legacy history with mutations disabled. No page errors or browser-
  origin external requests. This is not OS-wide zero-network evidence.
- Final screenshot review confirmed readable wrapped hashes and escaped reviewer
  text; no injected HTML element was created. The browser-verification workflow
  materially found the navigation defect above. Agent-browser was unavailable;
  the existing isolated Playwright/Edge harness was used.
- A final storage-constructor redirect guard was then added before directory
  creation, with a safe API error handler. `assignment-privacy-guard-final.xml`:
  four passed, 19.009 seconds. These supplement the earlier browser proof; they
  do not constitute another full joined/frozen/installed qualification.
- Deduplicated current focused tests: **64 passed**, zero failures/skips. Not a
  full repository suite. Python/JS syntax, focused Ruff, mirror hashes and diff
  whitespace checks pass. Existing deprecation warning remains documented in XML.

### Artifacts and next work

Evidence: `dist/model-candidates/compact-fleet-20260908/assignment-privacy-acceptance.json`,
the XML/JSON/screenshots named above and `verification-snapshot-assignment-privacy.json`.
All owned servers/browser processes stopped; no new browser profiles remain.
Retained fictional QA files total 1,860,340 bytes, all under repository `dist/qa`.
No model/runtime copies or drive-root QA directories. Older policy-denied cleanup
targets remain untouched.

Next: reviewed legacy-assignment migration and packet/authority-impact private
sidecar inventory, then large-matter progress/cancellation. Review status and
artifact error paths must remain consistent across actual production UI and
canonical APIs. Compact specialist semantic quality/admission, native runtime
licenses, OS network proof and exact frozen/MSIX qualification remain open.
No model inference/training/download, version bump, MSIX, commit or push this run.

## Confirmed legacy-assignment migration — 2026-09-09

The reviewer-assignment path now includes explicit migration of legacy plaintext
history. This is a bounded source-application vertical, not model or release GA.

### Implemented path

- `legal/review/assignment_migration.py`: read-only preview identifies the exact
  original SHA-256, bytes, event count and number of affected documents. Scope is
  **all reviewer assignment history in the active matter**, not just the open
  draft. The UI makes that scope explicit before confirmation.
- The canonical `POST /api/reviewed-filing-packet/documents/{document_id}/assignments/migrate`
  requires strict boolean confirmation, the preview hash, the current revision,
  and existing matter/tenant/role/session guards. Requested/completed events use
  the encrypted local audit. Missing privacy verification and deleted documents
  fail closed with safe errors. No private originals or raw paths enter responses.
- A single atomic ledger replacement contains both the unchanged historical
  events and their **byte-exact original file** inside authenticated encryption,
  plus a migration receipt. There is no plaintext backup or multi-file commit.
  Interrupted pre-commit work preserves the old bytes; post-commit retries read
  the completed receipt without writing another copy.
- Migrated history remains historical and inactive permanently. Encryption does
  not validate old identities or reactivate assignments. New assignment events
  are separately revision-bound, and preserving the migration original/receipt
  is required on every subsequent write.
- Actual workbench: View > Full workbench > Draft > saved document > Filing review.
  Users inspect the preview, explicitly confirm, handle stale-preview errors,
  inspect the encrypted-original receipt/hash, create a new assignment and reopen
  it. Confirmation clears on reload/document change, stale responses are ignored,
  and controls disable during commit. Disclosures are 14px with keyboard focus and
  wrapping, including the 1280px-wide browser check.

### Verification and retained limitations

Exact commands, totals, durations, source/artifact hashes and earlier attempts are
recorded in `dist/model-candidates/compact-fleet-20260908/assignment-migration-acceptance.json`.
The final combined service/API/production-manifest suite is
`assignment-migration-all-final.xml`; the source-UI proof is
`assignment-migration-browser-final.xml` and
`assignment-browser-migration-final.ui.json` (eight joined checks).

The real Edge UI run passed with no page errors or browser-origin external
requests. It includes stale-preview rejection/recovery, keyboard confirmation,
exact original/hash inspection, no activation of historical assignments, and
new-assignment reopen. Its backend harness independently verifies encrypted
state, original preservation, scope isolation and audit events. Unrelated API
GETs were fictional fixtures; no real matter, model inference or external
authority was used. Screenshots were inspected locally. Agent-browser CLI was
unavailable; the existing isolated Playwright/Edge harness was used instead.

Two test-authoring defects were corrected and their failed runs preserved:
the completion-audit fault injector initially had the wrong positional signature;
the deleted-draft test initially named a nonexistent soft-delete helper. Neither
was relabeled a product success. The final combined suite uses the corrections.
Additional service guards for corrupt privacy metadata and deleted drafts were
added after the browser process loaded its service; those branches and the final
combined service/API suite were verified afterward, not claimed as a new frozen
or installed-app run.

The existing Store module collector discovers the new migration module and the
production UI manifest passes. **Frozen executable and installed MSIX: NOT RUN.**
There is no new MSIX, model, training, version bump, commit or push. New-file Ruff,
six-file Python syntax, JS syntax, mirror equality and whitespace checks pass.
The API mirrors still contain five pre-existing unused imports each, verified
against HEAD; this is not a repository-wide clean-lint claim.

Migration is bounded to 1,000,000 original bytes and 2,000 events. Keep the full
workspace and original protected key; older apps cannot read the encrypted
ledger. This does not erase prior filesystem remnants, encrypt existing exports,
prove whole-workspace rollback resistance, verify professional identities, or
qualify large-matter latency/cancellation. All new QA and evidence stay in repo
`dist`, with no model/runtime copies. Closed browser profiles were removed by the
browser itself; previously denied cleanup paths remain untouched.

Next vertical: packet/authority-impact private-sidecar scope, integrity and actual
UI error/recovery paths; then large-matter progress/cancellation. Specialist
semantic quality, signed admission, native runtime notices/provenance, OS-level
Local-only proof, and full frozen/MSIX qualification remain release blockers.

## Authority comparison scope, provenance and recovery — 2026-09-09

Status: **PASS_FOCUSED_SOURCE_VERTICAL**. This is a release-critical protection
repair, not a new model or legal conclusion engine.

Inspection found that the production desktop authority-change JSON endpoints
did not share the explicit expected-matter/browser-session checks used by review
assignments. All five desktop JSON operations and all five matter-addressed
counterparts now use the same local role, tenant, session, expected-matter and
encrypted requested/completed audit path. Changing the active matter during an
operation suppresses its response. This does not establish independent multi-user
identity; the existing token-bound artifact-download path remains separate.

Both packet-creation APIs require an explicit revision ID and strict approval.
The service rejects a mismatched revision before writing artifacts. Private review
directory redirects are refused before creation, and the encrypted access audit
validates its event chain before appending. Safe alias errors preserve workspace
and review error codes. Status inspection now reports a corrupt/stale saved packet
as a visible blocker instead of silently treating it as an absent packet.

The actual workbench supplies expected matter identity, shows a busy state, blocks
duplicate actions, ignores stale responses and clears approval when the document
or generation selection changes. Source drill-down exposes the exact revision,
generation IDs, before/after SHA-256 and freshness with keyboard-operable, 14px
wrapping disclosures. Generation changes remain review signals, not findings
about legal materiality, current law or negative treatment. Explicitly approved
packet copies are **unencrypted exports within the matter**; the UI now states
that clearly. This is not a claim that all private sidecars are encrypted.

### Exact verification

- `authority-boundary-unit-01.xml`: 50 passed, two fixture failures. An imported
  autouse fixture was invoked twice; module-qualified explicit setup corrected
  the tests without bypassing the production authority-root boundary.
- `authority-boundary-regression-final.xml`: **55 passed**, no skips/failures,
  98.705 seconds. Includes both route families' protection matrix, revision
  binding, audit tampering/failure, mid-request matter change, existing impact
  consumers and production asset-manifest checks.
- `authority-boundary-errors-final.xml`: **2 passed**, no skips/failures. These
  supplement the final visible-corruption and safe-alias-constructor branches.
- `authority-boundary-browser-final.xml`: **1 passed**, seven joined actions.
  Actual Edge/source workbench and canonical APIs prove comparison, exact
  source-hash/revision inspection, keyboard activation, approval clearing,
  wrong-matter rejection/reload recovery, explicitly approved exact-revision
  packet creation, and visible blocking after deliberate fictional packet
  corruption. No stale download links remain in that blocked state.
- **58 distinct passing focused checks** across the final files, not the whole
  repository suite. Four-file Python syntax, new-test Ruff, JS syntax, mirror
  equality and diff whitespace checks pass. Existing API unused imports remain
  outside this repair; no repository-wide clean-lint claim is made.

The browser skill's CLI remains unavailable; the established isolated
Playwright/Edge fallback was used and its screenshot inspected. No page errors or
browser-origin external requests were observed. This is not an OS-wide network
audit. Generations and all matter records were deterministic fictional fixtures;
actual source ingestion and legal-quality validation were not performed. The
browser created packet artifacts but did not execute a browser download.

Evidence: `dist/model-candidates/compact-fleet-20260908/authority-boundary-acceptance.json`
and `verification-snapshot-authority-boundary.json`, with commands, source/artifact
hashes, exact timings, retained failed attempts and boundaries. All owned browser
and server processes stopped; no profiles remain. New QA fixtures total
**1,091,938 bytes**, only inside repository `dist`; no models/runtimes were copied.

Frozen executable and installed MSIX: **NOT RUN**. No version bump, model
inference/training/download, MSIX build, commit or push occurred. Remaining work:
private packet metadata beyond explicit exports and legacy recovery; large-matter
progress/cancellation; compact specialist semantic quality and signed admission;
native runtime notices/provenance; OS-level Local-only and full package proof.

## Compact runtime notice and timeout recovery vertical — 2026-09-09

Status: **PASS_FOCUSED_RECOVERY_VERTICAL_AND_NOTICE_INVENTORY**;
**BLOCKED_SPECIALIST_GA**. No specialist has been promoted or advertised as
production-ready, and no version, MSIX, commit or push changed.

The installed Tokenizers 0.22.2 wheel lacked a license-text inventory entry. The
new `scripts/qualify_compact_tokenizers_notice.py` acquires only a pinned 2,747,786-byte
Windows wheel and an 11,357-byte release-tag license. It does not install anything,
extract the wheel, copy a runtime, or touch another project's files. All 28 original
wheel payload files match the installed runtime byte-for-byte. The license is
pinned to source commit `f383101a26663708484cac0727792aad74f78234`, its Git blob and
SHA-256 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`.

The read-only runtime audit accepts this supplemental notice only with explicit
`--include-tokenizers-notice` and a fresh wheel/content comparison, not an unchecked
receipt or classifier. Wrong versions, altered payloads, missing files, unexpected
recorded files, direct-URL installs, bad licenses, redirected downloads, archive
traversal, duplicate/case-colliding names and links fail closed. The tests exposed
Windows ZIP-name normalization: the reader now checks the original archive spelling
as well as the normalized path. Two intermediate failing notice-test attempts are
retained, not reported as passing.

Measured selected footprint, including the supplemental notice:
**814,234,411 bytes**, comprising 651,337,619 package/notice bytes, 71,312,758 Python
runtime bytes and 91,584,034 model bytes. The audit covers 46 distributions and took
496.765 seconds. Installed RECORD checks and combined notice inventory pass; the
installed environment itself remains unchanged and lacks that notice. This does
not prove a wheel's build from the source tag, native/transitive license compliance,
dynamic import closure, final MSIX inclusion or production admission. The wheel is
verification evidence, not part of the measured serving selection.

### Timeout repair through the actual source workbench

The first browser/model attempt passed page boot, RAM denial/recovery, source
approval, real worker cancellation and caught-network-attempt rejection, but its
90-second result wait expired during the later real model cold load. The read-only
runtime audit was concurrently active. This is a **retained failed run**; concurrency
is context, not a demonstrated cause or an excuse to relabel the failure.

The canonical model host and both production JavaScript mirrors now give an explicit
timeout explanation: no new answer accepted, original records/answer unchanged,
direct source inspection available, and fresh preview/approval required for retry.
The pipe deadline test verifies that timeout calls stop and releases the blocked
reader. No runtime deadline was increased, no output was accepted on failure, and
no model gate was relaxed. The browser test now observes blocked completion instead
of assuming every completed action closes its dialog. It uses fresh repo-local
ephemeral Edge contexts, never the older cleanup-denied profile.

After the audit finished, the final actual-model/source-UI retry passed **17 joined
checks**, including explicit timeout-fault recovery, approved resident ranking,
exact source offsets and hashes, keyboard source inspection/focus return,
review-required/unknown-relevance labels, canceled export, confirmed TXT and JSON
downloads, and revocation of pending export links when clearing the conversation.
One real ranking request completed; peak resident memory was **522,633,216 bytes**.
The full browser/server lifecycle took 72.172 seconds, not a per-query latency claim.
All owned workers, browser and server stopped; no page errors or browser-origin
external requests were observed. OS-wide zero-network behavior is not proven.

### Exact final verification and boundaries

- `compact-notice-regression-final.xml`: **254 passed**, 0 failed/errors/skips,
  29.568 seconds. Includes supplemental notice/adversarial inventory, isolated
  process deadline, exact spans, source/matter/role/session binding, single-use
  approval, encrypted audit failure/tamper and production asset-manifest tests.
- `compact-notice-browser-02.xml`: **1 passed**, 78.902 seconds. Actual production
  page and canonical HTTP with a real resident ranker; explicitly fictional
  startup/search and research-factory injection. Timeout/network faults are
  marked injections and are not called successful inference.
- **255 distinct passing focused tests**, not 255 features or roadmap slices,
  and not the full app regression. Earlier 199-test and notice-only runs remain
  separate evidence; they are not added again to the distinct total.
- Changed-file Ruff, Python syntax, JavaScript syntax, JS mirror equality and
  whitespace checks pass. Existing unrelated changes are preserved.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-notice-recovery-acceptance.json`
and `verification-snapshot-notice-recovery.json`. Only about 2.8 MB of public
wheel/license material was acquired; remaining new files are repo-local test,
audit and fictional screenshot/receipt evidence. No model/runtime copies were made.
Previously denied cleanup paths remain untouched.

The browser-verification skills guided full UI → canonical API → worker → exact
sources/export checks. Their CLI was unavailable; the existing isolated
Playwright/Edge fallback was used and screenshots visually inspected.

Remaining: repeatable cold-start/load behavior, free-form Evidence/Drafting semantic
quality, calibrated relevance/abstention, signed compact-model production integration,
native/dynamic closure and final packaged notices, OS-level isolation, full
regression and frozen/installed qualification. The successful retry does not erase
the earlier timeout or make this a legal-quality, Store or enterprise certification.

## Compact cold-start diagnosis — 2026-09-09

Status: **MEASURED_RESEARCH_RUNTIME_ONLY**, not a newly accepted product feature.
The prior cold-start timeout was investigated without another runtime audit,
model/runtime copies, downloads, package build, or concurrent owned inference job.

`scripts/diagnose_compact_ranker_startup.py` runs at most three serial, real isolated
workers, using the existing pinned model and unchanged 90-second cold-load deadline.
Child instrumentation logs only fixed phase names and relative timings; it never
logs records, prompts or raw exception messages. High-resolution `perf_counter`
replaced the initial Windows coarse timer, which had rounded one fast request to
zero. The old zero value is retained as a timer-resolution limitation, not an
instant-inference claim. Missing, forged, oversized and non-monotonic traces fail
closed; a cleanup failure remains a failure in the saved report.

Four process-cold starts using the unchanged loader completed in **15.226–16.453
seconds**. OS disk caches were not flushed; this is not a reboot-cold or low-end-PC
qualification. The two detailed unchanged-loader profiles attribute approximately
**10.08–10.98 seconds to Transformers import**, **2.40–2.52 seconds to Torch import**,
and **1.52–1.60 seconds to model/tokenizer loading**. Two high-resolution warm
single-passage fixture calls took **14.3 ms and 18.6 ms**; these are not full
Evidence Review timings, throughput guarantees, or legal-quality measurements.
Final measured peak resident memory was **519,098,368 bytes**.

A fixed BERT-class loader was tried in two separate research worker runs. It did
not establish a reliable improvement: it mostly moved time from model loading
into import. The experiment was removed, and the production ranker module's hash
was verified identical to the previous accepted source snapshot:
`1b656424cace7b4cb1b09a16d1ecfd13a9ad1be1cbc7b9ea1caf62a52b62fd5d`.
No speculative performance change or new production model was retained.

Verification: **70 focused diagnostic/process tests passed**, no failures/skips,
1.406 seconds; changed-file Ruff and whitespace checks pass. This number is not
added to the previous 255 as if the overlapping process tests were new. Six real
research worker starts completed overall (four unchanged-loader measurements and
two discarded loader experiments), and every owned worker stopped. The final
instrumented run includes current implementation/model hashes. No browser, frozen
or installed-package retest was needed for the diagnostic-only retained changes;
none is claimed by this measurement.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-startup-diagnostic-acceptance.json`.
Earlier failed browser evidence is preserved. These serial successes do not prove
why that timeout occurred or establish reliable cold starts under load. Next work
should target the measured import/runtime closure and repeatable load behavior,
while model semantic-quality, calibrated relevance, production admission and
frozen/MSIX gates remain closed. Do not replace an unqualified specialist with an
unqualified generic model or resume unrelated feature slices.

## Runtime identity repair through the actual workbench — 2026-09-09

Status: **PASS_SOURCE_UI_RESEARCH_VERTICAL; SPECIALIST_GA_BLOCKED**.

The next dependency-closure check found a real isolation defect: `-I` still
initializes the base interpreter's global site-packages. The old bootstrap then
appended the selected venv with `site.addsitedir`, allowing global packages to win.
A diagnostic using the selected Transformers 5.14.1 therefore saw global
Safetensors 0.7.0 instead of the audited venv's 0.8.0. Prior cold-start/UI runs
remain valid observations of those runs, but **do not qualify the audited selected
runtime**. Their earlier speed numbers must not be transferred to this environment.

The resident worker now starts with `-I -S -B`, explicit dependency/application
paths, and a retained PyWin32 DLL handle. It executes no ambient `.pth` or
`sitecustomize` startup code. The repo Python launcher is itself a shim to an
existing dependency venv, so selection resolves the actually loaded dependency
location, not the launcher's empty `sys.prefix` site directory. Mixed critical
dependency locations fail closed. External environments were not edited.
Network-fault and timing test hooks now find the `-c` argument instead of assuming
an argument index; cancellation and kernel process ownership remain unchanged.

The corrected worker performed real CPU inference: first measured process-cold
warm-up **38.373 seconds**, then a one-passage call **13.9 ms**, peak resident memory
**449,396,736 bytes**. This is not reboot-cold, low-end-device, substantive Evidence
Review quality or an SLA. No timeout was increased. The following actual-source
workbench → canonical HTTP → selected worker → exact source preview → confirmed
TXT/JSON export journey passed **17 joined checks**. Its browser/server lifecycle
took **35.594 seconds**; one real ranking request completed and peak memory was
**453,242,880 bytes**. Hardware denial/recovery, actual child cancellation, injected
network and timeout rejection, new approval, encrypted audit, review labels,
source offsets/hashes and keyboard focus were exercised. Browser/server/workers
closed; no page errors or browser external requests occurred. Python network
guard tests are not proof of OS-wide isolation.

Final regression: **250 focused tests passed**, zero failures/errors/skips,
34.096 seconds; **one browser test passed**, 42.852 seconds including setup.
The initial 101-test attempt retained one test-assertion failure: the test expected
the internal code in the deliberately sanitized public exception message. It now
asserts the separate safe code without weakening the product boundary. Final
counts are 251 distinct tests, not features or a full application regression.
Actual child tests confirm selected package versions and reject mixed dependencies;
a malicious `.pth`/`sitecustomize` fixture and ambient PYTHONPATH cannot take over.

A single RECORD-checked **7,543,231-byte Python-only BERT overlay** was also
explored inside repo dist, with notices and exclusive/versioned manifests. It is
**not activated**: Auto-model loading still imports missing `transformers.models.align`.
All failed experiment reports are preserved; no partial overlay enters the
production factory. No models, native libraries or complete runtimes were copied,
and no downloads, external scratch directories, release build or version change
occurred. Earlier cleanup-denied paths remain untouched.

The browser verification skills guided full-flow and visual inspection, using the
existing Playwright/Edge harness because their CLI is absent. Screenshots show
readable review-required labels and exact candidate expansion; this remains a
fictional research-provider injection, not frozen or installed-package evidence.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-runtime-isolation-acceptance.json`.
Next: qualify a minimal compatible runtime closure without ambient dependencies,
then address ranking/abstention and Evidence/Drafting semantic quality. Existing
free-form specialist quality failures, production admission, native provenance,
full regression, frozen/installed MSIX and low-end hardware qualification remain
open. **No new GA specialist is accepted.**

## Fixed scalar BERT loader and model-output parity — 2026-09-09

Status: **PASS_FIXED_LOADER_SOURCE_UI_VERTICAL; QUALITY_STILL_BLOCKED**.

After repairing the selected-runtime identity, replaced generic Auto-class
discovery with the fixed BERT tokenizer/classifier that this ranker's pinned
architecture actually uses. The 7.54-MB Python overlay now loads the real model
without importing the missing unrelated Align architecture. The default worker
still uses the existing selected full dependency venv; the overlay remains an
opt-in research closure experiment, not a shipped runtime or production admission.
No additional runtime/model copy or download was made in this pass.

Also closed an output-interpretation defect: the old code flattened arbitrary
logits and silently took their first value. The worker now rejects anything other
than a `(1, 1)` scalar relevance result. It verifies the exact BERT classifier,
head count, one-label mapping and supported tokenizer, rejects decoder/cross-
attention configurations, and preserves nonfinite-score rejection. No confidence,
truth, source, privacy or review gate was relaxed.

Three measured full-selected-runtime cold starts completed in **8.649, 8.671 and
9.042 seconds**; the two detailed warm one-passage calls took **14.0 and 13.6 ms**.
The earlier selected Auto-class run took 38.373 seconds. These are observations on
this CPU-limited development machine, not a controlled speedup percentage or a
low-end-PC SLA; available RAM and OS caches differed. No cold-load deadline changed.
The overlay ran separately in 7.524 and 8.110 seconds. All owned workers stopped.

Full-runtime and overlay runs used identical pinned weights and the existing
fictional, non-training holdout. **All 41 passage scores were identical** across
12 cases (maximum difference 0). This qualifies score parity only: relevance
passed **11/12**, with the separate-date-fields case still choosing delivery text
instead of the register-entry date. **Three abstention cases were not evaluated**
because no calibrated abstention threshold exists. No prompt/threshold was tuned
to make this known failure pass. Both relevance commands and failures are retained.
The first parity test itself misread the report's reference/ranks structure;
that assertion was repaired and checked against the preserved runs without
duplicating inference. The replay is explicitly labeled, not another model run.

The actual production-source workbench/canonical HTTP research flow was rerun
with the fixed loader: real CPU ranking, matter/role/source-bound approval,
encrypted audit, exact quotation drill-down, review-required labels, hardware
denial, cancellation, network/timeout failure recovery, keyboard focus and
confirmed exports all passed. This is still a fictional startup/search fixture
with research-factory injection, **not frozen or installed MSIX certification**.
The browser-verification skill workflow used the existing Playwright/Edge fallback
and the result screenshot was visually inspected. No page error or browser
external request was observed; OS-wide zero-network proof remains outstanding.

Exact counts, timings, hashes and retained attempts are frozen in
`dist/model-candidates/compact-fleet-20260908/compact-fixed-bert-acceptance.json`.
Final focused regression: **278 passed**, zero failures/errors/skips, 30.758 seconds.
The real source-browser test passed in **28.482 seconds** (browser/server lifecycle
23.281 seconds, peak worker memory 454,799,360 bytes). With the separate recorded-
score parity assertion, **280 distinct focused tests passed**; the earlier 28
boundary tests are not counted twice. This is not the full repository suite.
Next: pursue broader ranking/date-attribution and calibrated abstention quality,
and qualify the minimal dependency/native notice closure for a real package.
Do not rerun unchanged positive smokes as new legal-quality proof. Evidence and
Drafting generators remain unqualified; production admission, full regression,
frozen/installed and physical low-end hardware gates remain open. Version 8.0.2
is unchanged; no MSIX was built and no GA model was accepted.

## Pinned comparison model and CPU precision — 2026-09-09

Status: **RESEARCH_COMPARISON_TESTED; NOT_SELECTED_FOR_RELEASE**.

To test a different small architecture against the unresolved attribution errors,
acquired the publisher's [mxbai-rerank-xsmall-v1](https://huggingface.co/mixedbread-ai/mxbai-rerank-xsmall-v1/tree/b5c6e9da73abc3711f593f705371cdbe9e0fe422)
at pinned revision `b5c6e9da73abc3711f593f705371cdbe9e0fe422`. Its Apache-2.0 LICENSE,
model card, tokenizer and Safetensors inventories were size/hash-verified. One
copy occupies **152,862,657 bytes**, including its optional SentencePiece file;
no pickle, repository Python code, alternate ONNX weights or runtime copy was
downloaded. Selected dependency/Python/notice inventory plus this model totals
**875,513,034 bytes**. That is a declared installed selection under the 1.5-GB cap,
not qualified final native closure or a release-package size.

The same isolated, local-only research worker now supports this exact allowlisted
scalar DeBERTa profile as a comparison. Weights, architecture, label count and
tokenizer are validated; unknown weights and cross-profile relabeling fail closed.
Its pinned 128k-entry Unigram tokenizer exceeded the original 200k JSON-item limit.
The first warm failure is preserved; a 400k-item/9-MB bound is used **only for this
model's tokenizer.json**, not other config, record, API or evidence JSON.

Explicit CPU FP32 loading now matches the declared hardware policy instead of
depending on library/model precision defaults. The earlier comparison run took
62.141 seconds to warm and 1.78–3.99 seconds per multi-passage case. With explicit
FP32, warm-up measured **12.875 seconds**, case calls **0.141–0.312 seconds**, and
peak resident memory **949,719,040 bytes**. These observations are not controlled
hardware benchmarks: disk caches and free memory differed, and FP32 uses more RAM.
Worker deadlines, memory limits, network guard and review/admission gates stayed intact.

**The comparison did not improve quality:** both runs passed **9/12** existing
fictional, non-training relevance cases versus the current BERT ranker's 11/12.
Different children, separate date fields and unrelated participants still failed.
No threshold or prompt was tuned to the expected answers; all raw scores and
selected passages remain recorded. It is a generic reranker, not a Maine-law
specialist, and is not selected as a replacement or publicly activated.

Clarification of prior benchmark exclusions: the three excluded cases consist of
**two unanswerable/partially irrelevant cases and one document-injection case**,
not three pure abstention cases. The runner excluded all expected-blocker rows;
neither this comparison nor previous reports prove their rejection. Separate
source/injection boundary tests remain distinct evidence. Calibrated abstention
and substantive legal/factual correctness are still unqualified.

The full production-source workbench/canonical API research journey passed with
**both** the comparison and existing BERT model: actual CPU result, approved source
packet, hardware denial/recovery, cancellation, injected network/timeout recovery,
encrypted audit, source/hash/offset drill-down, keyboard focus and confirmed exports.
Each run passed 17 joined assertions. Their browser/server lifecycles were 39.734
and 26.313 seconds; no page errors or browser external requests occurred. Every
owned worker/browser/server closed. The model identity is now explicit in browser
evidence; the production factory is still not enabled by the test injection.
The source-preview screenshot was visually inspected using the existing browser
verification fallback. No frozen app, installed MSIX, OS-wide network isolation,
attorney-reviewed evaluation or legal-specialist GA certification is claimed.

**330 focused regression tests passed**, zero failures/errors/skips, 34.467 seconds.
The two real browser executions passed in 46.357 and 33.734 seconds, respectively.
The earlier 80-test run overlaps regression and is not counted again. Python/JS
syntax, changed-file Ruff and whitespace checks pass. Existing unrelated changes,
user archives and cleanup-denied paths were preserved. No version bump or MSIX.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-comparison-acceptance.json`.
Next useful step is an independently worded attribution/unanswerable challenge
with separately defined calibration/evaluation roles before changing ranking
policy or acquiring another model. Keep the faster, better-scoring BERT research
path as the baseline. Free-form Evidence/Drafting, model admission, native closure,
full regression, frozen/installed and physical low-end qualification remain open.

## Answer-bearing cutoff generalization — 2026-09-09

Status: **EXPERIMENT_COMPLETED; CUTOFF_NOT_USEFUL_ENOUGH_TO_INSTALL**.

Created a separately worded, predeclared fictional challenge with 16 calibration
and 16 evaluation cases. Each partition has eight answer-bearing and eight
unanswerable cases. The requested target is a concrete field or attributed
statement in the supplied text, **not whether the reported event is true**.
Negative examples may still be useful context; they must not be hidden from a
reviewer simply because they do not supply the requested field. The fixtures are
assistant-authored, not independent human gold or attorney-reviewed evaluation,
and neither partition is authorized training data.

The existing pinned BERT ranker scored all 32 cases through its actual isolated
CPU worker: 32 bounded requests, 64 query/passage scores. A single exploratory
cutoff was calculated only from calibration scores, written with a hash receipt
**before evaluation**, and checked unchanged afterward. Evaluation expected
answers never entered model requests or cutoff fitting. All raw scores and IDs
are preserved; no outcome was dropped.

- Calibration: raw top passage correct on 8/8 answerable cases. The cutoff
  retained 5/8 correct answers and rejected all eight unanswerable cases.
- Evaluation: raw top passage correct on 6/8 answerable cases. The frozen cutoff
  retained **only 1/8 correct answers (12.5% coverage)** and abstained on the other
  15 cases. Zero false answer acceptances were observed in these 16 cases.
- The two raw attribution errors confused a registry entry with its underlying
  event date, and an approved amount with the requested amount. These are model
  relevance failures, not parser errors or evidence of factual contradiction.

**Zero observed false acceptances is not sufficient:** retaining only one of
eight available answers is not useful enough, and this small sample does not
prove real-world safety. The cutoff was **not installed**, the existing
review-required shortlist remains unchanged, and no specialist/admission status
was advanced. Do not lower this cutoff using these evaluation answers and then
claim the same rows as a new holdout.

Actual run: warm-up 16.711 seconds, total 17.442 seconds, peak resident memory
462,438,400 bytes; the owned worker stopped. These are development-PC observations,
not low-end qualification. No model, runtime, browser profile or external scratch
copy/download was made. Only compact repo-local scripts, fixtures/tests and
evidence were added. No UI/API behavior changed, so no new browser/frozen/MSIX
run is claimed for this diagnostic-only slice.

The runner also fails closed on invalid/overflowing cutoff scores, evaluation
data passed to the calibration fitter, cutoff-file tampering and cleanup failure.
Its failure report preserves sanitized errors rather than losing the evidence
when worker cleanup throws. **16 focused experiment tests passed**, zero
failures/errors/skips, 4.527 seconds; the prior 15-test run overlaps and is not
added to that count. Changed-file Ruff, Python syntax and whitespace checks pass.

Evidence: `dist/model-candidates/compact-fleet-20260908/ranker-abstention-acceptance.json`.
Next: retain this rejected cutoff as evidence and address attributed-field
selection using a genuinely different, source-bound implementation hypothesis
and a new evaluation partition. Do not acquire another generic model or rerun
unchanged positive smokes merely to show activity. Production admission, useful
Evidence/Drafting quality, native/runtime package closure, full regression,
frozen/installed and physical modest-hardware gates remain open.

## Context-only extractive QA qualification — 2026-09-09

Status: **REAL_INFERENCE_COMPLETED; AUTOMATIC_ANSWER_ACCEPTANCE_BLOCKED**.

Tested a different mechanism rather than another scalar relevance cutoff:
`deepset/minilm-uncased-squad2`, pinned revision
`934656cdda79824eabf503ed56e15c01ddbdbe3f`. It predicts start/end positions and
a no-answer comparator. It is an extractive SQuAD2 reader, **not a trained
Maine-law specialist, legal verifier or LoRA adapter**.

Attribution: deepset, *minilm-uncased-squad2*,
[pinned model card](https://huggingface.co/deepset/minilm-uncased-squad2/blob/934656cdda79824eabf503ed56e15c01ddbdbe3f/README.md).
The card declares [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
not Apache-2.0. The downloaded weights are unmodified. This project adds its own
bounded inference wrapper and fictional tests; no endorsement is implied.
Retain attribution, license links and modification notices in any redistribution;
this research receipt is not a completed Store/legal-compliance audit. The
downloader now matches each allowlisted candidate's actual declared license and
rejects mismatches; existing Apache receipts remain unchanged.

One model inventory was downloaded: **133,704,718 bytes**. With the previously
audited selected Python/runtime/notice inventory, the measured selection is
**856,355,095 bytes**, below the 1,500,000,000-byte limit. This is not a qualified
native dependency closure or final MSIX measurement. No runtime/model copies,
external QA directories, private records, model training or package builds were
created for this experiment.

The research implementation now provides:

- Explicit `BertForQuestionAnswering` and local tokenizer, CPU FP32; no Auto-class
  discovery, remote code, generator, tools or downloaded executable code.
- All six exact file hashes/sizes pinned and write-denying locks held during
  use, not just the weights. The existing isolated `-I -S` worker, selected
  runtime, Windows job ownership, scrubbed environment and Python network guard
  are reused. This is **not an OS-level zero-network certification**.
- A distinct `extract` operation, never misrepresented as scalar ranking or
  production PEFT admission. Matter scope, protected spans and document-injection
  screening are checked before loading and again across the process boundary.
- At most 512 input tokens, no silent truncation, at most 32 answer tokens,
  context-only offsets, exact source hashes and parent-side substring validation.
  Every result remains review-required and explicitly not truth-verified.
  `no_candidate` does not prove absence of evidence.

The predeclared fictional challenge has eight answerable and eight unanswerable
questions. Expected answers never enter model requests. The fixed zero no-answer
margin was not tuned on these rows. **13/16 strict matches**: 7/8 answerable
exact matches and 6/8 correct abstentions. All three mismatches remain recorded:

- `qa-07`: `6 p.m` instead of `6 p.m.` — a punctuation boundary mismatch, not
  an invented time. Do not relabel this as a newly passing exact-match result.
- `qa-09`: returned a date when the question asked for an unrecorded time.
- `qa-12`: returned a scheduled pickup time for a question about actual pickup,
  despite the text explicitly saying actual pickup was unrecorded.

The last two are substantive **false answer acceptances (2/8 unanswerable
cases)**. The original report's broader `false_answer_acceptances: 3` counts all
non-null strict mismatches, including punctuation; subsequent runner output also
separately records unanswerable acceptances. No original report was rewritten.
Exact copying prevents invented strings but does **not** establish the answer's
meaning or correct attribution. This candidate therefore remains research-only,
unadvertised and absent from public navigation/provider admission. No E2E/GA
feature was claimed from these service-level tests.

First real CPU run: 58.20 seconds cold warm-up, 58.61 seconds total, peak resident
memory **497,709,056 bytes**, 16 requests; owned worker stopped. A later independent
transport regression warmed QA in 12.01 seconds and the existing BERT ranker in
19.87 seconds. These variable development-PC observations are not a speedup claim
or physical low-end qualification.

Verification: **274 focused regression tests passed** (6.143 seconds) plus
**2 opt-in actual-model transport tests passed** (33.034 seconds), zero failures,
errors or skips. The earlier 136-test run overlaps and is not added. Real transport
tests verify exact span/source binding, unchanged scalar-ranker protocol, clean
owned-worker shutdown, and oversized QA input rejection without truncation.
Additional unit tests cover scope mutation, pre-cancel, admission rejection,
invalid logits/offsets, response tampering and license mismatch. Ruff, syntax and
diff-whitespace checks pass. No new production UI, frozen-app or installed-package
test is claimed: no public UI/API feature was activated.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-span-reader-acceptance.json`.
Next coherent hypothesis: an explicit source-field review contract that separates
date/time, scheduled/actual, and attributed/established claims before accepting an
extraction. Define new fictional evaluation cases before changing that policy;
do not retune on these 16 rows and call them a fresh holdout. Only after meaningful
quality and safety gates pass should that contract be wired through the canonical
matter/role/audit API, actual UI, provenance inspection, cancellation and frozen
runtime. Automatic Evidence/Drafting quality, production admission, runtime
closure and release qualification remain blockers. **Zero GA specialists.**

## Ranker metadata integrity and recovery — 2026-09-09

Status: **INTEGRITY_RECOVERY_VERTICAL_VERIFIED_IN_SOURCE_UI; SPECIALIST_GA_BLOCKED**.

Before attempting new source-field acceptance, inspection found a prerequisite
trust gap: the BERT/DeBERTa rankers pinned the weight digest and architecture, but
accepted tokenizer/configuration hashes supplied by a mutable local acquisition
receipt. An edited receipt could therefore authorize different tokenization while
retaining the original weight hash. This is an observed code boundary defect,
not evidence that the actual downloaded models had been tampered with.

The completed repair follows the existing workflow from model inventory through
isolated execution, canonical API, encrypted audit, production-page failure
display, restoration, fresh approval, inference and exact-source review:

- `compact_ranker_pins.py` now binds **all 15 files** across the two selected
  rankers: weights, tokenizers, special tokens, configuration and notices. Missing,
  duplicate, extra, mixed-folder, wrong-size and changed-hash inventories fail
  before optional model-library import. File contents are still hash-checked and
  write-locked before use. This supplements, not replaces, admission rules.
- The canonical pinned acquisition command revalidated both existing inventories
  against their original upstream revisions, license declarations, exact sizes
  and published hashes. All files were reused; no new model download or copy.
  Mixedbread's receipt also matches its prior frozen evidence verbatim.
- Worker artifact-verification failures become one safe integrity code, without
  paths, exception text or document content. The canonical runtime supplies a
  recovery explanation and review-required, withheld result. Existing rejection
  behavior for unknown weight identities is preserved.
- Both production JS mirrors now route that failure code from HTTP-200
  review-required failure responses as well as ordinary errors. The UI says the
  original records/answer are unchanged, allows direct source inspection, and
  directs restoration of a verified package followed by fresh preview/approval.
  It explicitly warns against editing the receipt to bypass verification.

Meaningful fictional browser action: approve a selected record, simulate a
tokenizer receipt mutation **in memory only**, observe rejection and disabled
resubmission, restore the original inventory, rebuild approval, then run the real
BERT ranker and inspect all three exact source candidates. Original model files
were never modified. The canonical run remains matter/session-bound and audited;
an approval cannot be replayed after failure. No model output from the bad
inventory is accepted.

The first browser attempt correctly blocked the model but exposed a second UX
defect: the UI handled only timeout/network warning codes and displayed generic
recovery text for integrity failures. That defect was fixed, then the browser
flow passed. The failure screenshot/report is preserved rather than overwritten.
The browser-verification skills guided the full UI → API → worker → encrypted
audit → recovery check. Because the agent-browser CLI is absent, the existing
repository Playwright/installed-Edge harness was used; no browser was downloaded.

Final verification:

- **342 focused regression tests passed**, 33.238 seconds, zero failures/errors/
  skips. Includes pin tampering, scope, protected spans, worker lifecycle, safe
  response serialization, consumed approval, encrypted audit and transcript
  boundaries. The earlier unit/regression/API runs overlap and are not added.
- **One actual browser/model scenario passed**, 64.294 seconds in pytest;
  browser/API run 57.671 seconds, **18 assertions**, zero page errors or observed
  browser external requests. Both server and owned worker stopped, browser closed,
  no cleanup errors. Peak worker resident memory: **455,122,944 bytes**.
- UI checks include failed-inventory recovery, hardware denial/recovery,
  cancellation, Python-network denial, timeout recovery, real inference, exact
  source expansion, keyboard focus return, and consent-bound transcript export.
  The new integrity-blocked screenshot was visually inspected: recovery text and
  disabled approval remain visible at the tested 1440×1000 viewport.
- Changed compact-module Ruff, Python syntax, both production JS syntax checks,
  browser-script syntax, mirror equality and diff-whitespace checks pass.

The browser uses the actual shipped source page and canonical HTTP API with an
explicit research client plus fictional startup/search fixtures. **It does not
prove the production provider factory, frozen executable, installed MSIX,
OS-level zero-network isolation, model semantic quality or low-end hardware.**
No model/admission/version/public feature list was advanced; no package, commit,
push, new model/runtime copy or external scratch folder was created. All new QA
trees together total 413,762 bytes, excluding compact screenshots/reports in the
evidence directory. Unrelated processes and user changes were untouched.

Evidence: `dist/model-candidates/compact-fleet-20260908/ranker-pins-acceptance.json`.
Remaining next task is still the explicitly typed source-field review hypothesis
described above, with new evaluation examples before policy changes. The QA model
still confuses unrecorded time with a recorded date and scheduled with actual
events. Do not silently promote that failed experiment or infer fact verification
from exact copying. Evidence/Drafting quality, production admission, native
runtime closure, frozen/installed and physical modest-hardware qualification
remain open. **Zero GA specialists; no new MSIX.**

## Explicit typed-field experiment — 2026-09-09

Status: **RESEARCH_POLICY_MEASURED; PUBLIC_ACCEPTANCE_NOT_GRANTED**.

Implemented the next recorded hypothesis using the already acquired MiniLM QA
reader, not another model download or training run. The caller must explicitly
choose `clock_time`, `calendar_date` or `money` and `source_field` or
`reported_event`; this is not automatic intent detection or an established-fact
request. The request hash binds the policy, query, selected source, matter and
field/basis. All source offsets/hashes, matter scope, protected-span and injection
checks remain in place. `established_fact` and legal-finding contracts are rejected.

The research guard validates narrow literal field forms and checks the entire
approved excerpt for uncertainty/absence wording. Reported-event requests also
require explicit event wording and reject recognized plan, conditional or
attribution language. Unknown formats are withheld rather than normalized into
invented values. A partial calendar date remains partial: **no year, timezone,
currency, factual truth or legal significance is inferred**. Every candidate
remains review-required, source-assertion-unverified, truth-unverified and
production-unadmitted. No candidate does not establish absence.

Before inference, created **24 separately worded fictional cases**, 12 answerable
and 12 unanswerable, covering time/date confusion, requested/paid amounts,
scheduled/actual events, attribution, conditional events and wrong-record fields.
The cases are assistant-authored reference annotations, **not training data,
independent human gold or attorney review**. Expected answers never enter worker
requests. The policy and fixture hash were frozen before the first model load;
the policy file was checked unchanged afterward. No cutoff or guard was tuned on
the evaluation outcomes.

Actual isolated CPU results:

- Raw QA: **16/24 exact matches**; answered **7/12 unanswerable questions**.
- Typed review: **20/24 exact matches**; **0/12 unanswerable acceptances** and
  zero wrong answerable acceptances in this small test set.
- Useful correct-answer coverage: **8/12 (66.7%)**. Four valid answers remain
  withheld: the model itself missed one plainly listed meeting time; the
  conservative whole-excerpt guard rejected three valid fields because another
  part of the excerpt mentioned a plan or undocumented attendance.

The four misses (`field-04`, `field-07`, `field-08`, `field-12`) are preserved.
This is measurable improvement over raw QA, **not proof of real-world safety or
a GA specialist**. The literal/keyword checks cannot establish entity/event
attribution generally. Do not hide missing coverage or loosen the guard using
these answers and then call these same cases a fresh holdout.

Warm-up: **12.402 seconds**; total **13.078 seconds** for 24 model requests;
peak resident memory **498,864,128 bytes**. The owned worker stopped. These are
development-PC CPU measurements, not a low-end SLA. The selected model plus
previously audited Python/runtime/notice bytes remains **856,355,095 bytes**;
native/package closure is still unqualified. No model/base/runtime was copied or
downloaded and no external scratch, browser profile, MSIX or private data was used.

**194 focused regression tests passed**, zero failures/errors/skips, 3.965 seconds.
Earlier 69/190-test runs overlap and are not added. Tests cover invalid date/time/
amount forms, qualifiers, unsupported factual contracts, source tampering,
wrong-matter input, request-hash binding, malformed fixtures and existing span,
worker, network and inventory boundaries. Fixture validation was strengthened
after inference without changing the frozen fixture or filtering policy; no
second inference was relabeled as new evidence. Ruff, syntax and whitespace checks
pass. No public API/UI/frozen/installed test is claimed because this qualification
experiment was deliberately not registered as a user-facing feature.

Evidence: `dist/model-candidates/compact-fleet-20260908/typed-fields-acceptance.json`.
Next: design narrowly scoped clause/context handling with new adversarial cases
that distinguish the selected field from other planned, disputed or absent
fields. Preserve all original context for human review. Also address the missed
plainly listed field without pretending a deterministic fallback is model
inference. Only after useful quality/coverage survives that evaluation should
the explicit contract be integrated through canonical role/matter approval,
encrypted audit, actual source-inspection UI, cancellation and frozen reachability.
Unrestricted Evidence/Drafting quality, admission and release qualification
remain blockers. **Zero GA specialists; no new MSIX.**

## Clause context and honest literal lookup — 2026-09-09

Status: **RESEARCH_CONTEXT_POLICY_MEASURED; NO_PUBLIC_FEATURE_OR_ADMISSION**.

Implemented the next recorded clause/context hypothesis, preserving the existing
whole-excerpt guard as an unchanged baseline. The new research wrapper validates
the **entire original source** for matter scope, privacy, injection and exact
span/hash integrity before selecting a bounded clause. Plans about another field
no longer automatically erase a separate reported-event candidate. Original
offsets/hash are restored in the result, the selected context range is recorded,
and the full original context is explicitly required for human review.

Disputes, allegations, conditional accounts, explicit retractions and other
recognized qualifications remain global: selecting a favorable clause must not
drop a later contradiction. The splitter is a narrow heuristic, **not a general
sentence/semantic parser or factual verifier**. Unsupported/ambiguous inputs
remain withheld. Review-required, truth-unverified and admission boundaries did
not change.

Before inference, froze a new 24-case fictional challenge: 12 answerable and 12
unanswerable, including separate plans/actual-event text, later disputes,
conditions, wrong-person fields, missing values and ambiguous numeric dates.
No expected answer entered a model request; no score threshold/policy was tuned
after seeing the results. Actual isolated CPU results:

- Raw QA: **13/24 exact matches**, including **10/12 unanswerable questions
  incorrectly answered**.
- Clause-context review: **23/24 exact matches**; correct candidates retained for
  **11/12 answerable questions (91.7%)**; **0/12 unanswerable acceptances** and no
  wrong answerable acceptance in this test set.
- The unchanged whole-excerpt baseline was also applied to these same saved raw
  outputs, without repeating inference: it retained **3/12** correct answers and
  accepted **3/12** unanswerable questions. This comparison is on the new cases,
  not a claim that the previous different 24-case challenge regressed.

The remaining miss is `clause-11`: the model returned no candidate for a receipt
stating that **92 dollars was paid**. It was not reclassified as a pass. These
assistant-authored fictional cases are not independent human gold, attorney
review, broad family-law quality certification or evidence of real-world
zero-error behavior. All policy/source hashes and raw outputs remain preserved.

Also implemented a separate **deterministic literal-field lookup** for an
operator-specified exact label. It recognizes only `Label: value` and
`lists the Label as value`, checks the literal time/date/money form, rejects
duplicate/qualified/unsupported values, and returns exact source offsets plus
the original hash. The result explicitly says `model_inference: false`, identifies
its deterministic producer, and has **no fake model confidence/score**. It does
not guess labels or convert source statements into established facts.

That lookup was tested separately on new fictional labeled examples, including
the plainly listed meeting-time format that earlier QA missed. **It was not
substituted into the 24-case model results or claimed to solve the narrative
92-dollar miss.** Combining lanes or exposing this as a user feature still needs
an explicit canonical request/approval contract and UI evidence.

Measured CPU warm-up **11.173 seconds**, total **11.774 seconds**, 24 requests,
peak resident memory **495,468,544 bytes**; owned worker stopped. No model download,
base/runtime copy, training, external scratch, private corpus, browser profile or
MSIX was created. The model/runtime selection remains 856,355,095 bytes before
uncompleted native/package qualification; this machine is not a low-end benchmark.

**229 focused regression tests passed**, zero failures/errors/skips, 4.167 seconds.
Earlier overlapping 58/228/229-test runs are not added. Tests exercise global
qualification preservation, original Unicode offsets/hash, wrong-matter/source
tampering, document injection, typed forms, request binding, deterministic-lane
label/ambiguity boundaries and existing worker/network/inventory protection.
Changed-file Ruff, syntax and diff-whitespace checks pass. No public API/UI,
production factory, frozen or installed proof was executed or implied.

Evidence: `dist/model-candidates/compact-fleet-20260908/clause-fields-acceptance.json`.
Next: use this narrow candidate-review contract for a coherent **research-only**
canonical API/production-source-UI integration, preserving explicit field/basis
selection, model-versus-deterministic provenance, full-context drill-down,
encrypted audit, consent, cancellation, hardware and one-use approvals. Keep it
out of production admission/public feature claims until that path and broader
quality/coverage are genuinely proven. Do not call a source-field locator the
completed unrestricted Evidence Review or Drafting specialist. The narrative
amount miss, broader semantic quality, release admission, native closure,
frozen/installed and physical modest-hardware qualification remain blockers.
**Zero GA specialists; no new MSIX.**

## Research QA approval and source-inspection vertical — 2026-09-09

Status: **RESEARCH_SOURCE_UI_PATH_VERIFIED; NOT_PUBLIC_OR_FROZEN_ACCEPTANCE**.

Added `compact_field_client.py` and `compact_field_output.py`. The QA client takes
an explicit, fixed field/basis contract, publishes it in the model binding, uses
only approved source objects and the existing isolated CPU span worker, and
rejects changed contracts, wrong matter, marked/quarantined document instructions,
malformed spans and changed source state. Every source is screened before the
first dispatch. No labels/basis are inferred from record instructions. Only
research injection can construct this client; the production factory is unchanged.

The canonical host now recognizes a distinct `SourceFieldResponse` and repeats
the type/context/original-hash checks independently. It reconstructs the answer;
it does not trust provider prose or a provider's claim of verification. Exceptions,
binding changes and forged rows fail closed. A valid run may retain no candidate:
the result explicitly says this does not establish absence and retains the source
card for direct inspection. The separate deterministic locator is not used or
misrepresented as inference. Model provenance, typed basis, review requirements,
unverified fact/law status and original-context hashes survive the receipt.

Both production JavaScript mirrors show the fixed field contract before approval
and distinguish source-field candidates from established findings. A no-candidate
receipt no longer has the generic successful-quotation headline. The ordinary
source inspector already supported a single exact span plus the original approved
source block; that existing path is reused, not replaced by the reranker layout.

The actual shipped source page, canonical `/api/local-agent/preview`, `/run` and
`/cancel` handlers, real MiniLM QA worker and encrypted audit were exercised with
a fictional session scheduled for 09:00 but reported as beginning at 09:25.
The model returned **09:25**. This is one UI integration fixture, not a fresh
semantic quality holdout and not a replacement for the prior failed QA cases.
The tested profile was **clock_time / reported_event**. Other types/bases have
boundary tests but are not newly claimed as browser-verified profiles.

**19 browser assertions passed**: page startup; zero-RAM denial without worker
start; real host CPU/headroom recovery; visible contract and original context;
canceling an actual owned worker without replacing the prior answer; injected
timeout recovery; an in-memory forged tokenizer receipt rejected by the real child
inventory check; fresh approval; real inference; unverified-fact badges; exact
field plus original context inspection; Enter/Space/focus return; correct
post-run context wording; canceled and confirmed TXT/JSON exports; and revocation
of pending private export links. The browser used existing Edge 152.0.4191.66.
No page errors or external browser requests were observed. This is not an
OS-level network isolation proof. The previous ranker-only caught-network fault
was deliberately not relabeled as a span-worker test.

The first browser run failed because its assertion expected a collapsible ranking
card, while the DOM already contained `Exact source span: 09:25` and the complete
fictional sentence. Corrected that test selector; did not relabel the first run
as passing. The second run passed, **37.843 seconds pytest**, **30.359 seconds
browser/API harness**, **490,545,152 bytes peak worker RSS**, one completed QA
request, three worker starts including canceled/failed starts. Worker, browser
and loopback harness stopped; no cleanup errors were reported. The source
inspector screenshot was visually inspected at 1440×1000.

Final focused regression: **484 passed, 0 failed/errors/skipped, 41.834 seconds**.
With the separate real browser test: **485 distinct passing tests**. Earlier
unit/regression runs overlap and are not added. Coverage includes canonical
identity/tenant/session/matter protection, single-use approvals, changed model
contract and stale record rejection, encrypted audit, safe abstention with source
cards, independent host verifier exceptions, existing source/ranker/privacy,
hardware and specialist UI behavior. The initial unit failures were incorrect
test use of the preview tuple and sanitized error message, fixed in the harness.
An existing Starlette TestClient deprecation warning remains, not a product
failure. Targeted Ruff, seven-file AST syntax, production JavaScript syntax,
mirror hashes and Git whitespace checks pass.

Browser skills were used to trace the complete interaction. `agent-browser` was
not installed; the existing repository-local Playwright harness and installed
Edge were used without downloading a browser. No new model, runtime copy, private
data, external scratch, version change, MSIX, commit or push. Selected QA model
plus audited runtime remains **856,355,095 bytes**, before unresolved final native
dependency/package qualification. Unrelated external workloads were untouched.

Evidence: `dist/model-candidates/compact-fleet-20260908/field-vertical-acceptance.json`;
raw `ranked-browser-api-field-01/02.json`, `ranked-browser-field-01/02.json`, their
fictional screenshots/exports, and `field-vertical-regression-final.xml` are retained.

Next: make research selection operational through an explicit, admission-compatible
host configuration (not a test-only factory override and not a production gate
bypass); exercise no-candidate/repeated/mixed-record user journeys with the real
QA worker and fresh independently worded cases. The current field contract is
still a narrow heuristic, not general entity/event attribution or completed
Evidence/Drafting. Preserve the narrative 92-dollar miss and other prior quality
failures. Native/runtime closure, physical low-end hardware, frozen/installed
reachability, broader semantic quality and production admission remain blockers.
**Zero GA specialists; no new MSIX; no publicly enabled research model.**

## Mixed, withheld and recovered field-review outcomes — 2026-09-09

Status: **RESEARCH_MULTI_RECORD_UI_TRANSITIONS_VERIFIED; NOT_PUBLIC_ADMISSION**.

The existing signed compatibility schema accepts only `fast_interchange_hotswap_v1`
PEFT packages. A compact QA reader is not such a package. Corrected the research
client's inherited ranker descriptor to **`compact_span_research_v1`** and require
that exact descriptor at the independent host field-output boundary. Added tests
that both research ABIs remain rejected by the existing signed PEFT schema.
No trust key, grant, compatibility allowlist or production factory was relaxed.
Operational selection still requires a distinct compact-admission design; setting
an environment flag or relabeling the weights is not an acceptable shortcut.

Extended the actual source-page/canonical-HTTP/real-CPU-QA proof to select immutable
fictional record sets sequentially in one conversation:

- Mixed: REC-1 retains 09:25; REC-2's unknown actual start is withheld. Two separate
  source cards remain, and the withheld record cannot inherit the first span.
- Fully withheld: REC-2 is incomplete and REC-3 contains a disputed 10:20 account.
  Neither value is retained, both original source cards remain inspectable, no
  quote-checked badge appears and absence is not established.
- Recovered: a new REC-4 returns 11:10. Its result/card contains no stale REC-2,
  REC-3, 09:25, 10:20 or previous no-candidate status. Each run has a distinct
  hash-bound receipt and the audit remains encrypted.

Improved the end-user vertical: per-source withholding explanations now distinguish
model non-selection, uncertainty, plans, disputes and format mismatch without
printing raw exception codes. A model miss takes precedence over secondary
whole-excerpt keywords, so a missed valid field is not explained as absent evidence.
The no-candidate receipt says no value was retained and provides a source-inspection
recovery action instead of the confusing `0 quotations match` paragraph.

Review receipt/status text in both production CSS mirrors now has a 14px minimum,
1.5 line height and dark text. Real browser measurements verified 14px body and
paragraphs, no horizontal overflow, and RGB(21,59,85) on RGB(247,250,252) in all
three states. The withheld screenshot was visually inspected at 1440×1000; the
message and recovery instructions are visible and readable. This is a targeted
readability check, not complete accessibility or 200%-zoom certification.

Final real focused transitions: **one browser test passed, five real QA requests,
one worker start, 492,064,768-byte peak RSS**, 21.750 seconds harness / **29.685 seconds
pytest**. All three transitions, distinct receipts, source identities, keyboard
inspection/focus return, and review/grounding states passed. No page errors or
external browser requests were observed. Browser/server/worker stopped cleanly.
The same verified weights/runtime were reused; no model or runtime copy/download.

Preserved failures and scope:

- `field-sequence-01` clicked the preceding message before the new streamed answer
  rendered; the old selection was correctly reviewed. Added an explicit wait for
  the new review button. This was a test synchronization error, not proof of a
  product stale-source defect.
- `field-sequence-02` correctly rendered the withheld state but its test expected
  lowercase text despite the CSS uppercase heading. Corrected that assertion.
- Switched to the new focused transition mode instead of repeatedly replaying the
  historical cancellation/network/export matrix. `field-transitions-01` passed;
  `field-transitions-02` additionally passed the repaired readability checks.
- One added unit test caught explanation precedence: a model returning no candidate
  was described using an incidental planned-event keyword. Corrected that product
  explanation and reran the focused regression.

Final **494 focused tests passed, 0 failures/errors/skips, 41.993 seconds**. Together
with the separate final real browser test: **495 distinct passing tests**. Earlier
overlapping runs are not added. The preexisting Starlette TestClient deprecation
warning remains. Targeted Ruff, six-file AST syntax, production JS syntax and Git
whitespace checks passed. The browser skills used the existing Playwright/Edge
fallback because `agent-browser` was absent; no browser download was needed.

Evidence: `dist/model-candidates/compact-fleet-20260908/field-transitions-acceptance.json`.
Raw `ranked-browser-field-transitions-02.json` and its API report, screenshots,
`field-transitions-02.xml`, and `field-sequence-regression-fixed.xml` are retained.
The raw harness report retains its inherited hardware-fault-description text;
**no zero-memory fault was injected in the focused transition-only run**. Its
normal hardware gate ran; prior full runs covered the injected denial. Fictional
startup/search are fixtures (including their simplified index count), not a real
production search/index acceptance result. Python/OS networking, frozen/installed
behavior and legal quality were not newly certified by these transitions.

Next bounded implementation: a separate, closed compact runtime/grant contract
binding model inventory, exact runtime closure, task/field/basis, policy hash,
license evidence, evaluation evidence and development/production scope. Reuse
existing trusted-key/revocation/rollback semantics; never masquerade QA as PEFT or
mint production/human approval. Only then wire an explicitly authorized research
selection into the canonical factory and test denial/default-hidden behavior plus
the same actual UI. Current research factory injection is not operational public
installation. Broader entity/event quality, prior model misses, native closure,
physical low-end hardware and frozen/package gates remain open.
**Zero GA specialists. No MSIX, version change, commit/push or public activation.**

## Compact signed-declaration prerequisite — 2026-09-09

Status: **DECLARATION_BOUNDARY_TESTED; INTERNAL_PREREQUISITE_ONLY**.
This is not a new accepted feature or a completed public vertical. The previous
source-UI proof still uses an injected research client; it is not public model
installation or production admission.

Added `legal/fast_interchange/compact_admission.py` and
`tests/test_compact_admission.py`. This is a separate closed contract, not an
extension of PEFT's `fast_interchange_hotswap_v1` compatibility allowlist:

- Signed Ed25519 declarations bind model and runtime inventory hashes, exact
  task/ABI/field/basis, host-owned policy hash, rights/notices/evaluation evidence
  hashes, development/production scope, review-required and no-promotion flags.
- The inventory declares model **plus runtime** bytes strictly below
  1,500,000,000. Reject unsafe/absolute/traversal/reserved filenames, case-folded
  duplicates, file/directory collisions, missing weights/runtime entries and
  ambiguous JSON, invalid numbers or oversized/deep inputs.
- Field policies are keyed by `typed_source_field_review:<field>:<basis>`;
  ranking uses `record_passage_ranking`. A clock-time/reported-event approval
  cannot be reused for money or a different attribution basis. The map must be
  supplied by trusted host code, never imported/UI data.
- Reuses existing provisioned public trust, revocation, encrypted anti-rollback
  state and inspection-only no-advancement semantics. Invalid input cannot
  advance state. No production signer or private signing key was created.
- A valid declaration explicitly reports `artifact_bytes_verified=false`,
  `runtime_qualified=false`, `production_admitted=false` and `runnable=false`.
  All production-scope grants are rejected, even a trusted non-test signature
  claiming human/native evidence. Hashes bind declarations, not the truth or
  acceptance of the underlying rights, evaluation, file bytes or native closure.
  Missing human review has a real `null`, not a manufactured approval hash.

Final focused regression: **219 passed; 0 failures/errors/skips; 36.203 seconds**.
Breakdown: 75 new compact declaration tests, 43 existing PEFT artifact-registry
tests, 30 field-client tests, 7 canonical field API tests, 52 host source-binding
tests and 12 hardware-readiness tests. Doubles/synthetic declarations only; no
fresh inference, browser, physical low-end, frozen or installed-package proof.
The existing Starlette TestClient deprecation warning remains. Targeted Ruff and
Git whitespace checks passed. Initial test-file decorator syntax errors were
repaired; the failed collection XML is preserved, not counted as success.
The intermediate 107 passing tests overlap the final 219 and are not added.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-admission-acceptance.json`
and `compact-admission-regression-01.xml`. This pass adds no API, navigation,
factory activation, model copy/download, training, runtime clone or MSIX.

Next coherent vertical (do not skip the byte boundary):

1. Add a locked, bounded compact artifact verifier using existing pinned model
   files and actual runtime inventory. Validate real size/hash, exact required
   files, notices, symlinks/reparse points and file-change races before worker
   start. Bind exact policy and selected task to the returned immutable identity.
   A signed declaration alone must never construct a client.
2. Integrate verified **development-only** selection through the canonical
   factory and existing explicit preview/approval flow, default-hidden otherwise.
   Preserve role/matter authorization, source and policy bindings, hardware gate,
   encrypted audit, source drill-down, review-required status and cancellation.
   No downloadable trust key or synthetic production promotion.
3. Prove that path through the actual production source page without the current
   injected client; include denial/revocation/stale-file/wrong-task tests, a
   meaningful fictional review action and clean worker shutdown. Qualify frozen
   reachability separately. Do not claim this prerequisite completed that path.

Still open: real native dependency closure/packaging, semantic limitations and
model misses, independent quality evaluation, physical low-end testing and
frozen/installed acceptance. No qualified general Evidence Review or Drafting
specialist. **Zero GA specialists; no version change, MSIX, commit or push.**

## Locked compact artifact selection — 2026-09-09

Status: **INTERNAL_LOCK_BOUNDARY_TESTED; FULL_RUNTIME_CHECK_TIMED_OUT**.
This remains a prerequisite, not a publicly delivered vertical. No production
factory, API, navigation, model admission, version or MSIX was changed.

Added `legal/fast_interchange/compact_artifacts.py`, its Windows tests, and
`scripts/verify_compact_artifact_selection.py`. The declaration-to-selected-bytes
path now freezes input documents, verifies the signed declaration without state
advancement, binds code-owned model pins and the declared notice-file inventory,
resolves every dependency root before any expensive artifact read, hashes actual
files through native Windows read handles, and rechecks trust/revocation before
advancing encrypted rollback state. It holds files against writes/deletes and
ancestor directories against replacement. Native handles avoid the CRT descriptor
limit with large inventories. Cancellation and all failure exits release handles;
the receipt is unavailable after its lease closes. Receipt copies cannot change
the lease's task identity. No model/runtime copies or private signing keys.

Corrected actual compatibility defects in the preceding declaration schema:

- The measured runtime has 23,827 files, exceeding the old 20,000-entry limit.
  The bounded limit is now 32,768, with the total byte/JSON/tree limits retained.
- Empty `__init__.py`, `py.typed` and metadata files are legitimate; zero-byte
  non-weight entries are supported and must still hash correctly. Empty weights
  remain forbidden.
- Actual distribution filenames contain interior spaces, parentheses and plus
  signs. Those are allowed; traversal, absolute paths, streams, reserved device
  names, boundary whitespace, trailing dots and case/path collisions stay denied.

Final focused regression: **227 collected; 225 passed; 0 failures/errors;
2 skipped; 25.680 seconds**. Files: 75 compact declaration tests, 22 artifact
tests (20 pass, 2 skip), 43 existing artifact-registry tests, 50 ranker pin tests,
30 field-client tests and 7 field API tests. Real Windows tests prove write/rename
denial, parent-rename denial, actual junction rejection, hash/size/notice failures,
hard-link alias rejection, cancellation, stale trust and cleanup on exceptions.
The two actual symbolic-link cases are explicitly skipped because this account
lacks Windows symbolic-link creation privilege; do not call those proven. Existing
Starlette TestClient deprecation warning remains. Targeted Ruff and syntax checks
pass. Earlier overlapping unit runs are not additive.

Real-file experiment reused the six code-pinned MiniLM files and the prior
hash-pinned installed runtime inventory. It did not regenerate dependency metadata,
download, train, run inference, create a signer, copy a runtime or use real matters.

- `compact-locked-files-real01.json`: stopped after 5,336 files / 261,950,580
  bytes because the proof script used the notice parent directory instead of its
  existing versioned subdirectory. Fixed by reusing the notice module's canonical
  directory. The initial script reported cleanup as false on failures without
  observing it; that reporting defect was corrected. The first process exited.
- `compact-locked-files-real02.json`: **not passed**. Reached 19,274 files /
  768,406,537 bytes, then exceeded the 600-second verification budget. Total
  duration including unwinding was **622.094 seconds**. Native handles closed and
  the process exited. This checked the selected model and only part of the
  runtime; it is NOT complete runtime, signed-admission, native-closure or
  package proof. It reports the last attempted logical inventory path.
- The selected-file target remains 23,833 files / 856,355,095 bytes, below the
  1.5-billion-byte cap by declaration and prior inventory. The present run did
  **not** finish independently re-verifying all of them under read locks.

Observed preparation-performance blocker: the broad installed selection includes
**9,375 Torch C++ headers (39,245,962 bytes)**, plus other development/general
architecture material. Do not simply omit files and claim native closure, rerun
this unchanged slow experiment, or raise the timeout and call performance fixed.
The current `runnable=false`, `native_closure_qualified=false` and production
denial remain correct. No new real inference, browser, frozen or MSIX acceptance.

Next coherent vertical:

1. Determine and test the minimal fixed Bert CPU serving/runtime selection from
   the actual worker's Python/native imports and data/notices needs. Use pinned
   inventories and keep completeness/rights review explicit; do not delete or
   modify the shared installed environment. No duplicate runtime per attempt.
2. Put potentially blocking verification in an owned cancellable process and
   reuse the resulting read-locked lease across warm requests. Per-chunk checks
   alone cannot interrupt a slow Windows file open. Do not repeat full runtime
   hashing per chat or hide minutes of preparation behind a frozen UI.
3. Connect the closed compact development contract to
   `legal/agent_runtime/providers.py:build_local_client` only after the selected
   execution closure is verified. The present factory still constructs the PEFT
   client; do not masquerade QA as PEFT or accept a receipt as executable admission.
   Preserve default-hidden behavior, canonical preview/approval, matter/role scope,
   hardware limits, encrypted audit, exact source review and explicit research
   limitations. Then prove that entire UI path without injected clients.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-artifact-acceptance.json`,
both real-file reports and `compact-artifact-regression-03.xml`.

Cleanup was denied by tool policy before execution; **no space was reclaimed**.
Do not retry with a different command/tool or reuse these denied fixture paths:

- `dist/qa/compact-artifact-locks-01`
- `dist/qa/compact-artifact-regression-01`
- `dist/qa/compact-artifact-regression-02`
- `dist/qa/compact-artifact-regression-03`

Their measured combined logical size is 14,812,679 bytes (about 14.8 MB), all
synthetic fixtures under the repository; actual model/runtime copies added: zero.
Preserve the compact XML/JSON evidence separately. Other projects and user archives
were untouched. **Zero GA specialists; no MSIX, version change, commit or push.**

## Source-only worker imports and observed serving selection — 2026-09-09

Status: **SOURCE_IMPORT_BOUNDARY_AND_REAL_READER_SMOKE_PASSED; CLOSURE_NOT_QUALIFIED**.

Did not repeat the unchanged 23,833-file timed-out verifier. Added a research-only
trace engine to the existing private-pipe/Windows-job worker, observing loaded
Python modules, open attempts and native mappings for the warm forward pass and
two fictional prompts. No private matter text, model copy, runtime copy or download.
The trace is a diagnostic, not a public API or evidence that every attempted file
open succeeded. All three trace snapshots were retained; they contain logical
root labels rather than user profile paths.

Found and repaired an actual trust-boundary weakness: `-B` prevented cache writes
but still permitted existing cached `.pyc` files outside the source inventory to
supply executable code. Baseline trace contained **2,691 cached-bytecode paths**.

- Added `compact_source_imports.py`: the owned child installs source-only loading
  inline before application/dependency imports, rejects bytecode-only loaders and
  removes ambient zip entries from its initial import path. The host is untouched.
- Worker checks the installed policy before each protocol iteration. Its warm
  acknowledgement must include `compact_source_only_v1`; the parent rejects a
  missing/different policy. Field and ranked-review approval bindings now carry
  this policy identity. Network tripwire, hardware limits and review flags remain.
- Actual child tests preserve a valid old `.pyc` timestamp/size while changing the
  source and prove the new source executes. Explicit bytecode-only loading is
  rejected, and fresh source import creates no cache. These protections are not
  a complete import allowlist, native sandbox or source-byte admission mechanism.

The source-only trace (`serving-trace-cpu02-*`) completed: **one worker, one warm
forward pass plus two real requests, 496,693,248-byte peak RSS, 76.469 seconds
including tracing, clean shutdown, zero observed `.pyc`/`.pyo` paths**. The same
fictional prompts returned `09:25` and `92 dollars` before and after the fix. They
are runtime checks, not an independent quality dataset or a repair of the different
historical money-attribution failure. No weights were trained or modified.

Separate, uninstrumented smoke `source-only-real-serving-01.json`:

- New worker preparation: **12.25 seconds** on this machine with previously-used
  files; this is not a cold-disk or physical low-end hardware benchmark.
- Two warm extraction requests: **0.032 and 0.015 seconds**, both exact expected
  spans, one worker, **493,420,544-byte peak RSS**, clean shutdown.
- Worker timings only, not full-app chat latency, p95, whole-matter performance,
  native packaging or evidence of substantive Maine-law expertise.

The observed candidate selection retains all audit metadata/notices and reduces
the accounted subset to **4,573 files / 487,792,756 runtime bytes**. With the model
that accounted subset is 621,497,474 bytes. **It is incomplete:** 1,084 observed
runtime paths are absent from the previous inventory, including actual Pillow
modules/native extensions; 46 Windows mapping paths also require platform/native
classification. Do not advertise the subset as a complete delivered footprint or
exclude these dependencies silently. Observation alone is not import enforcement.

Final tests: **160 passed; 0 failures/errors/skips; 10.514 seconds**. Includes actual
child source-loader tests, runtime selection, private protocol/network guards,
field client/API and ranked-review behavior, and non-promoting selection planning.
An earlier dependency-identity test hit its historical 15-second timeout after
source compilation was enabled. Its timeout now matches the existing 90-second
worker warm limit; this was not called a performance fix. Separate real timings
above remain visible. The failed XML is retained. Existing Starlette deprecation
warning remains; targeted Ruff and syntax/whitespace checks pass. Overlapping
earlier unit and trace runs are not added to the final 160-test total.

Next task, without another unchanged full-inventory hash run:

1. Reconcile the 1,084 observed runtime paths against their actual installed
   package ownership, origins, licenses/notices, RECORD hashes and sizes. Separate
   actual imported/native files from failed optional open attempts. Keep unknown
   or additional bytes as blockers; do not silently omit Pillow/scientific/other
   optional packages that the shared environment actually loads.
2. Establish a reproducible, enforced serving selection covering required Python,
   data and native files; trace coverage alone is insufficient. Preserve the
   source-only rule unless a separately verified code-cache design is implemented.
3. Complete cancellable owned-process artifact preparation and lease reuse, then
   canonical default-hidden development selection and actual UI acceptance without
   an injected client. Preserve all matter, review, source, privacy and audit gates.
   Physical low-end headroom, broader quality, frozen and installed qualification
   remain unproved; small observed RSS does not bypass the existing hardware gate.

Evidence: `dist/model-candidates/compact-fleet-20260908/source-runtime-acceptance.json`,
`observed-serving-selection-cpu02.json`, the two trace sets and the uninstrumented
smoke. No public activation, new MSIX, version change, commit or push. Previous
cleanup-denied paths remain untouched; no deletion retry. **Zero GA specialists.**

## Installed serving-path ownership reconciliation — 2026-09-09

Status: **LOCAL_INTEGRITY_ACCOUNTED; PUBLISHER_AND_SERVING_CLOSURE_NOT_QUALIFIED**.

Reconciled the previous 1,084 unaccounted observations without copying models or
environments: **921 existing files, 163 absent optional metadata probes**. Actual
imports/native mappings implicate 11 additional packages: accelerate, defusedxml,
dill, fonttools, h2, hpack, hyperframe, Pillow, pypdf, scipy and torchvision.
Their locally declared license notices and installed RECORD checks passed. This
does not authenticate publisher origin or grant legal clearance. The remaining
102 package owners were observed through metadata inspection, not actual imports.
Do not ship all of them merely because their metadata was probed, or remove them
and assume serving behavior is unchanged without an enforced-selection parity run.

`runtime-reconciliation-gaps02.json` records 888 files checked against installed
RECORD digests and 33 RECORD self-entry snapshots. Self-entry hashes are not
publisher authentication: the [PyPA installed RECORD specification](https://packaging.python.org/en/latest/specifications/recording-installed-packages/#the-record-file)
allows empty hash fields. The earlier gaps01 report is preserved, including its
overly broad classification of those self entries as absent-hash blockers.
Six missing-notice cases remain explicitly **metadata-observation-only**:
antlr4_python3_runtime, docling, latex2mathml, presidio_analyzer, rapidocr, sqlite_vec.
There were no integrity mismatches, ambiguous owners or metadata scan errors in
this actual run. Repeat duration: **3.157 seconds**, warm filesystem cache, not a
cold-disk benchmark (first read-only run: 21.750 seconds).

Additional distinct bytes: **79,566,562**. Accounted model plus runtime subset:
**701,064,036 bytes**, still not a complete delivered footprint. All qualification
and production-admission flags remain false. The script executes no installed
package code during metadata ownership inspection and does not fetch declared URLs.

Repairs and verification:

- Reject oversized files and already-wrong RECORD sizes before reading contents.
- Reject unsafe Windows paths, reserved names, control characters and malformed or
  duplicate RECORD entries; notices use declared license paths as well as names.
- Synthetic integration cases distinguish missing required imports from optional
  probes, detect same-size tampering and ambiguous ownership, preserve existing
  evidence, and prevent any integrity pass from becoming production admission.
- Exact final test counts, commands and artifact hashes are in
  `runtime-reconciliation-acceptance.json`; this is dependency-boundary testing,
  not a new inference, full production UI, frozen-app or installed-package proof.

Next: establish an enforced serving selection with complete notices and native
dependencies, including classification of the 46 Windows mappings. Retain the
source-only policy. Complete owned cancellable preparation and retained artifact
leases, then canonical default-hidden factory/UI acceptance without injection.
Broader semantic quality, independent review, physical low-end headroom and
frozen/installed tests remain release blockers. No new MSIX, public activation,
version change, commit, push, training or download. No cleanup retry or external
project writes. **Zero GA-qualified specialists.**

Heartbeat verification 2026-09-09: repository-local runtime boundary tests
(`test_compact_runtime_reconciliation.py`, `test_compact_runtime_inventory.py`,
and `test_compact_runtime_selection.py`) completed successfully: **59 passed**.
This rechecks reconciliation policy only; it does not change the recorded
publisher/notices, specialist-quality, frozen-app, installed-package, or GA
blockers above.

## Hash-bound source-import allowlist prerequisite — 2026-09-10

Status: **INTERNAL_IMPORT_BOUNDARY_HARDENED; NOT YET LEASE-WIRED**.

The disposable compact worker previously enforced source-only imports, which
prevented ambient bytecode execution but did not restrict imported source or
extension modules to a verified serving selection. `compact_source_imports.py`
now supports an optional SHA-256-bound logical allowlist covering repository,
selected package-runtime, and Python-runtime paths. When present, it rejects an
unlisted source or extension module before execution; malformed, oversized, or
hash-altered allowlists fail before any application/dependency source import.
The normal source-only policy remains the default when no verified allowlist is
provided, so existing research workers and PEFT admission behavior are unchanged.

Focused verification: **13 passed**, zero failures, using
`tests/test_compact_source_imports.py` and
`tests/test_compact_runtime_selection.py`. The new cases prove allowed-source
execution, unlisted-source rejection, and allowlist-digest tampering rejection.
Targeted Ruff and `git diff --check` also pass.

This does not yet construct an allowlist from a complete locked runtime
inventory, retain an artifact lease, activate a production factory, run model
inference, or qualify native dependencies. It therefore does not change the
development-only, review-required, unadmitted, or non-GA status of any
specialist. Next: bind the completed selected-file inventory to a cancellable
lease and pass only that locked allowlist to the owned worker before a real
non-injected UI/API proof.

## Lease-derived worker allowlist wiring — 2026-09-11

Status: **LOCKED-LEASE_WIRING_TESTED; PRODUCTION_FACTORY_STILL_DENIED**.

The existing Windows `verified_compact_artifacts` context now derives the
worker's source/native-extension allowlist only after every declared inventory
byte is SHA-256 verified under read handles. Runtime rows rooted at
`repository`, `package_runtime`, or `python_runtime` are normalized and sorted
into `compact_source_allowlist_v1`; model and notice rows remain integrity
governed but are not treated as importable code. The lease creates its one
allowlist under the owned worker scratch directory with exclusive creation,
hashes it, locks its directory chain and opens it with read-only sharing. Thus
the child receives a digest plus a file which cannot be replaced, renamed or
modified until the owning `ExitStack` closes. The generated allowlist is removed
after its native handle closes; no persistent scratch artifact is left.

`IsolatedCompactRanker` accepts that lease only as an explicit optional locked
boundary. Research workers still use the pre-existing source-only behavior.
When a lease is supplied, startup passes only the lease-generated allowlist and
the warm response must report `compact_source_allowlist_v1`; an old
`compact_source_only_v1` acknowledgement closes the worker and fails. This
prevents a wiring regression from silently falling back to unlocked imports.
Cancellation is checked before each verified file and each 1 MiB read; normal
exit, cancellation, startup exception and consumer exceptions unwind the same
native handles. The owned ranker already kills/reaps its child on any exchange
failure before the enclosing lease context releases the locks.

Focused command:
`dist/build-env/store/Scripts/python.exe -m pytest -q tests/test_compact_artifacts.py tests/test_compact_source_imports.py tests/test_compact_ranker_process.py --basetemp dist/qa/compact-lease-wire-r2`.
It collected **85** tests: **83 passed, 2 skipped, 0 failed**. The new cases
exercise lease-generated allowlist hashing, write denial, cleanup, and rejection
of an unlocked warm acknowledgement. `python -m compileall -q
legal/fast_interchange` and `git diff --check` passed. The selected build Python
does not bundle Ruff, so lint was not represented as run.

Evidence: `dist/model-candidates/compact-fleet-20260908/compact-serving-lease-acceptance.json`.

This is not a production compact-worker activation. The currently observed
runtime selection remains explicitly incomplete, no signed complete inventory
or production grant exists, and `CompactDeclarationVerifier` still rejects a
production-scope compact grant. Accordingly no public/canonical provider factory
was enabled, no real locked worker inference was claimed, and no specialist,
package scope, version, MSIX, Store, or GA status changed. The next blocker is a
complete signed minimal serving inventory with native/platform classification;
only then can a non-injected canonical factory be safely connected and tested.

Follow-up native-loader and cancellation checks (2026-09-12): the same hash-bound bootstrap now
has a direct regression test using Python's actual `_sqlite3` extension module.
It starts when the extension's `python_runtime/...` logical identity is present
in the signed-format allowlist and fails before execution when it is absent.
The current focused set collected **88** tests: **86 passed, 2 skipped, 0
failed**. It also proves cancellation before child startup causes no worker
launch, and cancellation during generated-allowlist acquisition removes the
scratch document. This proves the extension-loader guard itself, not the compact
runtime's full native graph or an admitted serving selection.
