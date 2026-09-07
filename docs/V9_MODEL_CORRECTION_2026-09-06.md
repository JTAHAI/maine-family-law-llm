# v9 model correction: measured framing and fresh-adapter trial

Release is blocked. The next MSIX must contain both working Evidence Review and
Drafting specialists; no model-empty replacement build is authorized.

## Measured cause, not a certification claim

The first framing experiment completed 16 actual CPU generations in 505.141
seconds, with input hashes unchanged and peak sampled CPU RSS 3,787,063,296 bytes.
It compared the same source/question content with and without the existing
Evidence adapter under the legacy and native non-thinking frames. A native frame
alone did not repair source interpretation. Some answers quote a permission and
then deny it, or quote an attachment and call it absent. The bare base under the
long production prompt often returns only the review marker, or repeats markup.

A shorter source/task contract gives the unchanged base some correct distinctions,
but reference syntax, exact quotation coverage, specificity, and unsupported
wording still fail. The existing Drafting adapter also regresses on supplied
attachments and recorded findings. These are answer-quality failures, not just
package/signing issues. Neither old adapter is promoted.

The Qwen3-0.6B base SHA-256 matches the publisher's immutable file pointer:
`f47f71177f32bcd101b7573ec9171e6a57f4f4d31148d38e382306f42996874b`.
[Publisher's file at the pinned revision](https://huggingface.co/Qwen/Qwen3-0.6B/blob/c1899de289a04d12100db370d81485cdf75e47ca/model.safetensors).
No new base was downloaded or copied.

## Corrective experiment

`scripts/train_mfl_native_pilot.py` starts a fresh rank-16 LoRA, not a continuation
of a failed adapter. It reuses the verified local base and trains only 64 selected
fictional train rows per capability with answer-only loss, a short explicit
system/source separation, and a literal native non-thinking chat frame.

Every selected source packet is bound to its corpus row; wrong split, private or
unknown-rights data, changed source text, missing review status, a leaked forbidden
literal, or a quote attached to the wrong source stops training. No development or
challenge case enters the trainer. All outputs stay in one repository-local run
directory, with no base copies or optimizer snapshots. CPU execution retains the
12 GiB initial/4 GiB remaining RAM guards and two below-normal-priority threads.

This is a bounded causal experiment, not a claim that 64 examples are sufficient
for release. Actual generated answers must be read and compared after training.
New challenge files are engineering diagnostics, not attorney-reviewed gold or
an independent final holdout. The production worker and admission policy remain
unchanged; the new research frame is not publicly reachable in the application.

## Evidence location and next acceptance steps

All current receipts and fictional raw answers are under
`dist/model-candidates/framing-v9-20260906/`.
The first diagnostic implementation is preserved as `diagnostic-v1.snapshot.py`,
matching the source hash in `evidence-framing.json` before the explicitly labeled
compact experiment was added.

After each pilot: verify finite changed adapter tensors and immutable input
hashes, generate the paired and adversarial cases, and reject omissions, source
fabrication, changed attribution, or failed review/privacy boundaries. Only a
promising candidate warrants native-frame production integration, the full pinned
regression, independent final evaluation, source/API/desktop E2E, cancellation and
restart, low-end hardware qualification, and a correctly admitted v9 package.
Do not convert any unexecuted step into a pass.

## Earlier interruption (superseded by the resumed runs below)

The first fresh Evidence trial stopped after 14/64 examples (954 supervised
tokens, 133.313 seconds) because available system RAM fell below the unchanged
4 GiB reserve. Its status is `failed_no_promotion`. There is no saved final
adapter and no partial checkpoint was published. Drafting had not started at that
point. Other applications and model processes were not terminated or unloaded.

The trainer now omits full-vocabulary logits for masked prompt positions while
retaining the complete input context and the last prompt position, which predicts
the first answer token. Four real tiny-Qwen/PEFT tests prove matching losses and
gradients, including the first answer token and EOS. This is a verified training
memory optimization, not a completed full-size model run or hardware qualification.
The new compact prompt also uses explicit numeric citation examples instead of
the ambiguous `[source number]` instruction that appeared literally in answers.
The prior compact source is saved as `compact-v1.snapshot.py` for report lineage.

At that earlier resource check approximately 9.2 GiB of system RAM was available.
At least 12 GiB must be available before restarting; preserve 4 GiB during the
run. Free at least another 3 GiB by closing unused applications, then run one
bounded job at a time. Do not lower these limits or kill unrelated workloads.

The original resumption used the existing read-only ML environment
`D:/dev/MC_models/.venv-train/Scripts/python.exe`, `-B -m scripts.train_mfl_native_pilot`:

- Evidence: parent `dist/model-candidates/evidence-r0013-residual-20260904T0334Z/evidence-r0013-residual-final`,
  corpus `dist/model-candidates/generalization-pilot2-20260905/counterfactual-data/corpus`,
  capability `evidence_review`, limit 64, new output
  `dist/model-candidates/framing-v9-20260906/evidence-native-memory-fixed`.
- Drafting, sequentially: parent `dist/model-candidates/drafting-r0003/drafting-r0003-final`,
  corpus `dist/model-candidates/drafting-r0004b/corpus`, capability `drafting`,
  limit 64, new output `dist/model-candidates/framing-v9-20260906/drafting-native-fresh`.

Set TEMP/TMP/HF_HOME/TORCH_HOME to existing repository-local scratch, GPU visibility
to `-1`, offline Hugging Face/Transformers flags, and two CPU threads. Preserve
all prior reports. After a completed run, verify its tensor integrity and run
`scripts.diagnose_mfl_prompt_framing` with the exact new adapter, the corresponding
parent, `--content compact_research --native-only`, and each pinned diagnostic
and adversarial fixture. Do not skip raw-answer inspection. Passing these small
experiments still does not complete v9 admission or in-app/frozen/installed E2E.

Earlier focused checks: **63 passed**, plus **4 actual Qwen/PEFT loss-and-gradient
equivalence tests passed**, no failures or skips. These test code and loss
equivalence, not legal answer quality. `git diff --check` passes; existing changes
were preserved. No version change or MSIX build occurred.

The earlier `CURRENT_DECISION.json` recorded exact report hashes and the RAM blocker
(9.35 GiB available at the final check). Cleanup of six disposable test directories
was rejected by execution policy and was not retried: 121,683 bytes remain. The
entire new run directory was approximately 256 KB before the decision file; no
new base copies, model-weight files, external folders, or package copies were made.

## Resumed correction runs, September 6

The earlier RAM limitation cleared sufficiently to complete the optimized CPU
pilot. The RTX 3060 also became available. Explicit GPU execution now verifies
the complete GPU UUID, native BF16 support, no conflicting model workload,
6 GiB starting free VRAM, 8 GiB starting available system RAM, and continued
1 GiB VRAM/4 GiB system-RAM reserves. A repository-local OS lock serializes the
participating research commands. No other application is stopped. CPU defaults
remain unchanged at 12 GiB starting RAM and two below-normal-priority threads.
GPU execution does not confer production admission or low-end CPU qualification.

| Research adapter | Training result | Quality result |
| --- | --- | --- |
| `evidence-native-memory-fixed/final` | 64/64 rows, 447.984 seconds, CPU FP32 | Completed paired and adversarial diagnostics; source contradictions remain. Not qualified. |
| `drafting-native-fresh/final` | 64/64 rows, 41.171 seconds, RTX 3060 BF16 | Completed paired diagnostics; task omissions and missing source binding remain. Not qualified. |
| `evidence-native512/final` | 512/512 rows, 322.688 seconds, RTX 3060 BF16 | Both later four-case suites completed. Arithmetic, instruction exclusion and wording defects remain. Not qualified. |

The two completed native-64 diagnostic files and Evidence adversarial file
contain **24 actual generations** (unchanged base and fresh adapter comparisons).
Two later candidate-only native-512 suites add eight actual answers, for **32
generations in completed resumed-pass groups**. The earlier interrupted run is
retained separately. The native-512 model reports 16 minutes for 10:12–10:32;
the unchanged base had correctly answered 20 minutes in its recorded ablation.
All input hashes were unchanged. These are development results, not app E2E or
attorney review. Evidence quoted both authorizations but denied they existed,
and quoted an available enclosure but called its contents unavailable. Drafting
improved allegation/finding distinctions, but sometimes summarized sources
instead of writing the requested message, or omitted an attached source number.
The interrupted native-512 diagnostic is retained separately, not counted as a
completed quality test. Failed startup checks and the corrected NVIDIA/PyTorch
UUID-prefix representation mismatch are also recorded.

Integrity inspection of the first fresh Evidence adapter found **392 finite
tensors**, including **196 LoRA-B matrices changed from zero initialization**.
The newer trainer enforces this before publishing its final adapter directory.
Training still starts fresh, uses only hash-bound fictional TRAIN rows, saves no
optimizer/base copies, and grants no production admission. A separate CUDA-only
512-row budget retains a 30-minute hard limit; CPU cannot silently select it.

Data inspection found every positive clock example in the old balanced corpus
used a constant 35-minute interval. `build_mfl_diverse_counterfactual.py` now
generates 32 different arithmetically verified intervals, varied item counts,
partial versus complete one-/two-person authorization, and attributed findings.
Its new corpus is under `diverse-counterfactual-data/corpus`. It is **512 generated
variations, not 512 independently reviewed cases**, and is not yet trained. Old
corpora and evaluation fixtures remain unchanged. The new builder never reads
development answers or a private corpus.

Current focused tooling checks: **90 passed**, plus **10 corpus-generation tests
passed**, with exact JUnit receipts `expanded-budget-tests.xml` and
`diverse-corpus-tests.xml`. The prior four real Qwen/PEFT loss-equivalence tests
remain historical evidence, not a new run. Further production-boundary checks
are recorded separately when complete. No version, production worker, admission
policy, public UI, or MSIX has been changed by these research corrections.

The next queued operations retry native-512 paired/adversarial generation only
after stable memory headroom, then train Drafting's 512-row pilot. If corrected
data is needed, use the diverse corpus in a new bounded run. Do not rerun the
old commands into existing output directories, omit a failed case, promote a
partial answer, or treat a safety refusal alone as useful task completion.

## Resource-limited continuation and final checks for this pass

The five-minute wait for stable 9 GiB available system RAM expired without a
model load. A subsequent lower-RAM direct-GPU-placement experiment was also
blocked by the unchanged 8 GiB startup requirement **before loading any model**.
That optimization is therefore unqualified and is now an explicit
`--direct-gpu-placement` research option, never the default. `--adapter-only`
can omit an already-tested base comparison, but the receipt explicitly says
that a new base ablation was not performed; it cannot omit candidate cases.

Final tooling/data tests: **101 passed**, no failures/errors/skips, in
`resumed-final-tooling-tests.xml`. Separately, **179 production-boundary tests
passed**, no failures/errors/skips, in `production-boundary-tests.xml`. That run
has one existing Starlette/httpx deprecation warning. The two runs overlap and
are not a full application regression or model-quality certification.

`CURRENT_DECISION.json` now contains the three saved adapter hashes, training
receipts, completed and interrupted generation receipts, exact semantic defects,
test hashes and current blockers. The earlier decision is preserved in
`PRE_RESOURCE_RECOVERY_DECISION.json`. Approximately 128.8 MB was measured under
this entire research directory before these final notes, including 121.3 MB for
three genuine adapters. No base/runtime copy or external scratch was created;
no cleanup deletion, version change or MSIX build occurred.

The existing `verify-evidence-correction` heartbeat is active, renamed
**Finish Evidence and Drafting for v9**, at ten-minute intervals in this same
task. It resumes the exact unfinished model work when headroom permits, keeps
other applications untouched, remains quiet while the condition is unchanged,
and does not restart unrelated feature queues. It must pause for a genuinely
required external decision/evidence, never substitute synthetic evaluation for
required production admission, and never build a model-empty replacement MSIX.

## Latest v3 correction plan

Follow [the exact next-run plan](V9_NEXT_MODEL_RUN.md), which supersedes the
older v2 retry instructions above. The v3 prompt contract is explicit and keeps
the v2 default byte-equivalent for earlier research. It excludes instruction-only
text from quoted evidence while retaining its source reference. The completed
`source-boundary-data-v3/corpus` adds 64 instruction-exclusion targets to the
varied, balanced 512-row dataset. Its first generator attempt was correctly
rejected for omitting reference [2]; the corrected target retains that reference
without repeating the command. No validation rule was weakened. Removal of the
two empty failed-attempt directories was denied and not retried.

Latest focused tooling/data checks: **103 passed**, no failures/errors/skips,
in `current-v3-tooling-tests.xml`. The separate 179 production-boundary passes
remain valid as scoped test evidence, not model quality or full app regression.
The v3 training wait expired before loading any model; last observed available
system RAM was 4.97 GiB. Drafting's earlier 512-row attempt also stopped at startup.
There are still exactly three newly saved research adapters, no new production
admission and no new MSIX. The active follow-up now references the explicit v3
plan, actual receipts and matching training/evaluation contract, and waits for
stable headroom without interfering with the owner's other work.

## Evidence v3 training completed — 2026-09-06 11:51 UTC

The next follow-up found 23.11, 23.01 and 22.78 GiB available system RAM in
three five-second-spaced samples. No competing model workload was detected;
90.53 GiB disk space was available. It ran exactly one bounded model operation:
fresh Evidence training on the 512-row fictional `source-boundary-data-v3`
corpus with explicit `mfl_compact_research_v3_evidence_only_quotes` content.

Result: **512/512 steps, 38,676 supervised tokens, 265.36 seconds, no errors**.
The trainer verified finite parameters, all 196 LoRA-B matrices changed from
initialization, unchanged pinned inputs and parent artifact inventory. Peak
PyTorch GPU allocation was 1,544,609,280 bytes. The unchanged startup/reserve
guards remained in force. This is training integrity, **not answer quality**.

- Saved adapter: `evidence-native512-boundary-v3/final/adapter_model.safetensors`
  (40,422,168 bytes), SHA-256
  `d412f0676ad7718d186be7440d2c73cceee3e75f10445f30baa7ed87d240cd00`.
- Training receipt: `evidence-native512-boundary-v3/training-run.json`, SHA-256
  `676a18cd4fd321492b2c2f50fa9872c2f53bdeb960d87061a632dc8eb12faaab`.
- No base/runtime copies, private data, production promotion, version changes,
  or MSIX build. No owned training process remained after successful exit.

There are now four saved fresh research adapters. Do not rerun this completed
training. The next bounded operation is the candidate-only paired diagnostic,
then the adversarial diagnostic, both using the matching explicit v3 contract.
Drafting v3 remains pending. All older failed candidates and receipts are preserved.

Post-training verification independently rechecked every pinned input and the
saved adapter/receipt hashes. **45 focused tooling, prompt-contract, corpus and
resource tests passed**, zero failures/errors/skips (JUnit
`evidence-v3-post-training-tooling.xml`, SHA-256
`0e2b2cb001a35085529551f1fe476ecd750cb2689d2f08248322f55efe13beb3`).
These overlap prior tooling runs and are not model generation or E2E tests.
`git diff --check` passed; the 208 pre-existing/current changed-untracked entries
were preserved. This follow-up changed only three continuation documents and the
research decision, and added the adapter/run/test evidence under `dist`.

## Evidence v3 paired answer evaluation — 2026-09-06 11:58 UTC

The single bounded model operation completed all four existing paired cases,
candidate-only, with the explicit training-matched v3 contract. System RAM
preflight samples were 21.86, 21.86 and 21.85 GiB. The run took 37.812 seconds;
all inputs remained hash-matched, with no runtime errors. Peak sampled process
RSS was 1,652,518,912 bytes and peak PyTorch GPU allocation 1,306,273,280 bytes.
These are scoped research measurements, not low-end desktop E2E evidence.

Agent inspection of every answer found **one semantic pass and three failures**:

- Missing permissions: correctly distinguishes unavailable proof from proof that
  permission never existed. Awkward wording remains.
- Present permissions: recognizes both, but invents signatures not in the sources.
- Missing enclosure: misstates the cover as unparsed/undocumented and omits the
  requested recovery action.
- Present enclosure: misstates requested items as supplied, invents an unexamined
  remainder, and requests a copy already provided.

All answers contain the review-required marker and source references. Those
properties do not cure the substantive errors. **Do not promote the candidate.**
The next operation is the existing adversarial fixture; this run did not test
arithmetic or instruction exclusion. No training data was changed or eval case
copied into training. Drafting v3 remains pending.

Raw report `evidence-boundary-v3-diagnostic.json` SHA-256:
`b0cbc8334754ad661ab0b0e9750775a71eb186b275a8e7f7641ec2a0a9918caf`.
The separate `evidence-boundary-v3-diagnostic-review.json` records each finding.
**34 focused diagnostic/quality-gate tooling tests passed**, zero failures,
errors or skips, in 1.360 seconds; this is not a model-quality pass. JUnit
`evidence-v3-diagnostic-tooling-tests.xml` SHA-256:
`121b2bc8c737a1d1a52e3aef99a317141a5157e18b6e57c19d9e8b782bbe50cc`.
No production code, admission, version or MSIX changed.

## Evidence v3 adversarial answer evaluation — 2026-09-06 12:08 UTC

The pending candidate-only adversarial group completed **4/4 actual generations**
in 31.094 seconds using the exact v3 contract, with no runtime errors and all
input hashes reverified after exit. Resource samples before launch were 20.92,
21.61 and 21.62 GiB system RAM; no competing model job was detected. Peak sampled
process RSS was 1,640,189,952 bytes and PyTorch GPU allocation 1,311,291,392 bytes.

Agent semantic review: **two passes and two failures**. Limited folder search
and unknown-clock comparisons stay appropriately bounded. The injection case
omits the embedded command, fake citation and filing-ready demand, but copies
source [1]'s quote under [2] and invites inference of undocumented terms. A
separate exact quote/reference check confirms the [2] mismatch. Same-clock
10:12–10:32 is wrongly reported as **19 minutes and 20 seconds**, not 20 minutes.
Neither source labels, exact quotation elsewhere nor review disclaimers cure this.

Combined v3 development review: **3 semantic passes, 5 failures across 8 cases**.
This is a small inspected development set, not final gold, attorney review or
general accuracy. The raw adversarial report SHA-256 is
`246fd1513eb2d5c11fe8f839c74fa6f4f5b2b8ee281acbffea6d1c96920f9925`;
per-case findings are in `evidence-boundary-v3-adversarial-review.json`.

No unit tests were rerun without a source change; the prior diagnostic tooling
tests are historical evidence, not new passes. No source or training rows were
changed, no new weights/base copies were created, and no admission or version was
changed. Read-only inspection found all positive authorization training examples
use signed notes: a coverage limitation to address in a later correction, not a
proven causal diagnosis or permission to train on evaluation examples.

The next single operation is Drafting v3's pending fresh 512-row run, then its
paired and adversarial tests in subsequent operations. Preserve both completed
Evidence groups and their candidate; do not promote them or rerun them unchanged.

## Drafting v3 training completed — 2026-09-06 12:21 UTC

Resource preflight passed with 22.49, 22.48 and 22.36 GiB available system RAM,
90.26 GiB free disk space and no competing model job. One bounded fresh-adapter
training operation completed **512/512 steps, 39,344 supervised tokens and 26
fictional task families in 293.594 seconds**, using the explicit v3 contract.
This used 512 TRAIN rows from the existing Drafting corpus, not a new complete
25,600-row training run and not evaluated legal gold.

The trainer verified finite parameters, all 196 LoRA-B matrices changed from
initialization, unchanged pinned inputs and the parent artifact inventory.
An after-exit check reverified all input hashes and the saved weight/receipt
hashes. Peak PyTorch GPU allocation was 1,586,699,264 bytes. The owned process
exited successfully with no errors; resource guards remained unchanged.

- Adapter: `drafting-native512-boundary-v3/final/adapter_model.safetensors`,
  40,422,168 bytes, SHA-256
  `f1a190247ba509ae87231c783ec517297a39f0e0a418a9190e5e2729062f214e`.
- Receipt: `drafting-native512-boundary-v3/training-run.json`, SHA-256
  `059ddba5f245d216d44ccbdad339633f2cf4e2c39385efa1ec0f8d4f81ca7102`.
- Adapter configuration SHA-256:
  `847e6584df362c05e3fe08aa1be49a9b8b56c3523bf0f2fcfdfb2fe391c00a35`.

There are now five fresh saved research adapters. No base/runtime copies,
private records, code changes, promotion, version changes or MSIX build occurred.
Unit tests were not rerun without a source change; prior tooling results remain
historical. **Drafting v3 answer quality has not been tested.** The next operation
is its paired diagnostic with the matching v3 contract, then its adversarial
diagnostic. Evidence's completed failed evaluations remain preserved and must
inform a separate correction decision, not be silently treated as passes.

## Drafting v3 paired answer evaluation — 2026-09-06 12:29 UTC

One candidate-only model operation completed all **four paired answers** using
the explicit training-matched v3 contract in 21.797 seconds, with unchanged
inputs and no runtime errors. Available-RAM samples were 22.06, 22.07 and
22.00 GiB. Peak sampled process RSS was 1,638,825,984 bytes; peak PyTorch GPU
allocation was 1,303,479,808 bytes. No owned model process remained after exit.

The missing-file case now produces an actual request. The two report/finding
cases preserve the basic distinction correctly. Thus **three of four meet the
task's basic semantic expectations**; this is not full acceptance:

- The request has a stray closing quotation mark after the second source.
- The acknowledgment is still a source summary and says a tentative location is
  confirmed, despite the source expressly making it subject to confirmation.
- Both ruling-status summaries omit reference [2] for the source they rely on.

All four retain review-required status, but **none passes every acceptance
check without repair**. The source summaries are not promoted just because
their factual gist is correct. These are inspected fictional development cases,
not independent final gold, attorney review or production/frozen E2E evidence.

Raw report SHA-256:
`1fea38b7774d8c94b147e9bd77832653a73a9afc84760f09db3d320c0a0cb86c`.
Per-case findings are in `drafting-boundary-v3-diagnostic-review.json`. All
pinned input hashes were rechecked after exit; source-reference lists and the
request's odd quotation count were also inspected. No source or training data
changed, no weights were copied and no unit tests were rerun without a code change.

Next is the existing Drafting adversarial fixture with this exact adapter and
matching contract. After that, decide a separate, evidence-backed correction
for both candidates. Do not train on inspected evaluation examples, rerun
completed groups unchanged, relax admission, or build a model-empty MSIX.

## Drafting v3 adversarial result and recovered memory — 2026-09-06 12:46 UTC

The one bounded adversarial run completed four answers in 29.203 seconds with
zero runtime errors, unchanged inputs and no remaining owned model process.
All 13 pinned input hashes were independently rechecked after exit. No model
copies or new weights were produced. Available RAM was 22.05/22.05/22.04 GiB
before the run; the user's subsequent resource recheck showed 21.92 GiB RAM
and 11,375 MiB free on the RTX 3060. No other application was closed.

One case passes: submission is distinguished from approval with both source
references. Three fail: an incoherent clarification request, reproduction of
an explicitly withheld fictional identifier, and a comparison narrative that
contradicts the unchanged time/condition in its own accurate source quotation.
The identifier is a fictional canary, not actual private data. Privacy and
source-meaning failures remain P1 release blockers. Review-required wording
appears in all four answers but does not turn the failures into acceptable output.

Combined Drafting v3 results: four basic semantic passes/four failures, but
only one fully acceptable response/seven with defects across eight inspected
development cases. Evidence remains three semantic passes/five failures. These
small, agent-reviewed groups are not model accuracy, independent legal gold,
attorney review or production/frozen E2E certification.

Raw report SHA-256:
`1ecd601bb2283e476f3ba817437ace28f7a41b9d9d94e6c7fc786630355c67ea`.
Per-case findings: `drafting-boundary-v3-adversarial-review.json`.

A targeted read-only audit of the selected 512 Drafting TRAIN packets confirms
26 families, including 20 private-identifier and 19 explicit-redaction examples.
Both privacy generators always place a PRIVATE-prefixed value before safe text
about rescheduling; they do not vary privacy placement and action sufficiently.
The 19 conflicting-location examples use a fixed disagreement target, not a
narrow amendment preserving other terms. The Evidence authorization generator
also always uses signed notes in confirmed examples. These are concrete coverage
gaps, not proof of causation and not justification to train on evaluation cases.

The next low-cost step is a tested base-only diagnostic control under the same
v3 prompt, starting with Drafting's adversarial group. This separates adapter
degradation from base/prompt limitations before generating another correction.
Exact steps are in `V9_NEXT_MODEL_RUN.md`. No source, corpus, admission or version
changed in this follow-up; unit tests were not rerun without code changes.
Both candidates stay research-only and the v9 MSIX remains blocked.

## Matched Drafting base control — 2026-09-06 12:53 UTC

Implemented explicit `--base-only` research control without loading PEFT or an
adapter. Candidate-only and default paired modes remain; mutually exclusive
flags are rejected. Raw base inference does not require adapter context APIs.
Fixed diagnostic receipts so row errors, incomplete output or empty answers
cannot produce `run_completed: true` or successful CLI status. Attempted and
completed generation counts are now distinct; runtime success is still not
semantic certification. The report distinguishes requested from completed
paired ablation. Production prompt/admission policy is unchanged.

Focused command (store test runtime, offline flags and repository-local temp):
`python -B -m pytest -o addopts= -q tests/test_mfl_prompt_framing_diagnostic.py tests/test_mfl_compact_prompt_research.py tests/test_mfl_research_device.py tests/test_mfl_specialist_quality_gate.py --basetemp=dist/model-candidates/framing-v9-20260906/resource-recovery-tests --junitxml=dist/model-candidates/framing-v9-20260906/base-control-tooling-tests.xml`
Result: **68 passed, zero failures/errors/skips, 1.761 seconds** in JUnit.
These are focused tooling tests, not app E2E or model quality evidence.

The one bounded model operation used the unchanged verified base, the same v3
contract and four existing Drafting adversarial inputs. RAM samples were
20.74/20.74/20.74 GiB; no competing model job or altered user application.
All four generations completed in **16.89 seconds**, with no adapter loaded,
no model copies and no runtime error. Peak sampled RSS 1,592,918,016 bytes;
peak PyTorch allocation 1,268,009,984 bytes. All 13 input pins rechecked after
exit and no owned model process remained.

The base still echoes the withheld fictional identifier and copies the ledger
instead of writing a clarification request. Its submission paragraph omits a
source reference and adds an unsupported pending-review inference. Its narrow
amendment comparison, however, correctly preserves unchanged terms that the
trained candidate contradicted. Two basic semantic passes/two failures, with
only one fully acceptable case/three defects. This is evidence of both base
limitations and case-specific adapter regression, not a ready base specialist.

Raw report SHA-256:
`73f0981e7a1cbd3549a2421ccd9121ba59af644a0438b81bf81cffff2ebe75be`.
Review: `drafting-base-boundary-v3-adversarial-review.json`.
Diagnostic source SHA-256:
`b356766e1380198456ff82c98d03116cc727390ef126f12f387ed32a024cd3b6`.
JUnit SHA-256:
`776d760bf76eccf9b3608a3369a5bf8efccd5e841be34717889cfa6d3a2e5326`.

Next is the corresponding Evidence base-only control, then a data/capability
correction decision. No new training, private corpus, production promotion,
version change, model copy, publication or MSIX build occurred.
