# 8.0.1 specialist release gate — BLOCKED

## Current specialist verification — 2026-09-05

No specialist is quality-qualified or production-admitted. Safe withholding or
partial quotation extraction is **not** a successful specialist review and does
not satisfy the requested GA release. Historical internal/template scores below
must not be used as current release evidence.

| Specialist | Latest verified evidence | Release state |
| --- | --- | --- |
| Evidence Review r0013 parent | 40/104 frozen mechanical cases; saved-output replay: 86 complete extract sets, 5 partial sets, 13 withheld | Blocked; extract sets are not verified explanations |
| Evidence correction, 4e-5 learning rate | 50/104 frozen cases, including one generation error; only 81 complete extract sets versus the parent's 86 | Rejected for promotion despite higher mechanical score |
| Evidence correction, 1e-5 learning rate | Training completed on 512 fictional rows. Actual CPU generation: 3/8 development checks; only 1/8 also passed the additional unquoted-explanation keyword diagnostic | Blocked; neither diagnostic proves semantic or legal accuracy |
| Evidence paired-source correction, 2e-5 learning rate | Trained on 128 of 512 new fictional rows. Real CPU generation: paired development 5/8 mechanical, 3/8 combined unquoted-keyword; original development 2/8 mechanical and combined | Rejected for promotion: misses material source changes, including supplied attachment, consent and recorded finding |
| Drafting r0003 | 12/22 frozen mechanical cases; saved-output replay: 15 complete extract sets, 7 withheld | Blocked |
| Parenting-plan Review r0002 | External research pack exists; internal development/test/challenge reports each contain 24 passing template cases; no completed out-of-template report found | Not independently qualified or integrated for release |
| Financial-disclosure Review | No completed substantive specialist pack found in the authorized model project | Not ready |
| Intake, Authority, Safety/privacy | Earlier fictional protocol/workflow adapters only | No substantive specialist qualification |

The 1e-5 CPU evaluation used two threads, below-normal process priority, no GPU,
and the existing shared base without copying it. All eight generations completed
in 172.329 seconds, including 23.641 seconds of activation. These are measurements
on this Ryzen 9 host, **not** a low-end-PC certification. No other workload was
stopped or reconfigured.

The original frozen evaluator and fixtures remain unchanged. An additional,
separately reported diagnostic removes quoted text before checking explanation
keywords. It catches copied source language masquerading as explanatory coverage;
even its pass does not establish polarity, causality, factual truth, or legal
accuracy. Three of the eight original meaning-keyword matches disappeared when
quoted source language was excluded. No score or qualifier was silently rewritten.

Correction work now includes 512 newly authored fictional examples arranged as
256 matched pairs. Within each pair the question is unchanged while a material
source fact changes: conflicting versus matching accounts, absent versus supplied
approval, missing versus readable attachments, unknown versus specified clock
settings, allegations versus explicitly recorded findings, negative versus
positive limited searches, requests versus confirmations, and absent versus
readable source bodies. Separate diagnostic pairs are never training input.
Integrity, exact quotations, privacy markers, source order, prompt parity and
development separation passed the mechanical audit; this is not attorney review.

A bounded 128-row CPU continuation completed on a subset of that corpus, not all
512 examples. It is not a release-qualified model. No model admission, Store
listing claim, or package inclusion is authorized by a training receipt alone.

Update at 19:55 America/New_York: the 128-row continuation completed in 2,269.453
seconds. Its new adapter is 40,422,168 bytes; all 392 tensors / 10,092,544
parameters are finite and the source/receipt hashes revalidated. RAM subsequently
cleared the unchanged 12 GiB initial guard. Both sequential CPU evaluation sets
completed: 16 actual generations with no generation errors, in 183.766 and
157.515 seconds respectively. No other application was stopped or reconfigured.

The candidate is **rejected for promotion**. It calls an attachment body missing
despite supplied content, fails to acknowledge documented consent, and treats a
source explicitly recording a fictional finding as merely an unresolved
allegation. The paired set mechanically passes some of these incorrect answers;
neither original scores nor the additional lexical diagnostic certify meaning.
All fictional answers were inspected as engineering diagnostics, not independent
human or attorney review. The full 104-case evaluation was not repeated for this
already failing candidate. The bounded follow-up has reached its stop condition;
no repeated training or new package build is underway.

Evidence (repository-local, ignored model workspace):

- `dist/model-candidates/generalization-pilot-20260905/evidence-review-decision.json`
- `dist/model-candidates/generalization-pilot2-20260905/candidate-development-cpu.json`
- `dist/model-candidates/generalization-pilot2-20260905/candidate-development-cpu-explanations-final.json`
- `dist/model-candidates/generalization-pilot2-20260905/counterfactual-data/audit.json`
- `dist/model-candidates/generalization-pilot2-20260905/training-counterfactual-cpu/`
- `dist/model-candidates/generalization-pilot2-20260905/counterfactual-decision.json`
- `dist/model-candidates/generalization-pilot2-20260905/counterfactual-candidate-development-cpu.json`
- `dist/model-candidates/generalization-pilot2-20260905/counterfactual-candidate-original-development-cpu.json`

The prior full application regression completed with **2,643 passes, 22 documented
platform skips and no failures/errors** across 2,665 collected tests. Its source
snapshot and hashes are recorded in `full-regression-postfix/summary.json` inside
the same model workspace. That earlier application result is not new-model E2E,
an installed-package qualification, or a substitute for the focused checks on
subsequent research tooling changes.

Remaining specialist-release gates: complete and accurate unfamiliar-source
responses; independent quality evidence satisfying the existing admission policy;
hash-bound production admission; actual production UI/API, low-memory hardware,
frozen-runtime and installed-package verification using the final admitted
artifacts. No new specialist-bearing MSIX or GA claim was produced by these
research checks.

## Historical r0011 verification — 2026-09-03

This update supersedes any earlier wording that could be read as r0011 being a
usable Evidence Review specialist. It is not usable or releasable today.

- A fresh production-UI → canonical-API → loopback-worker run used only the
  repository's fictional pickup-note matter. The host preserved two exact,
  hashed source excerpts and review-required status, but the actual r0011
  inference call reached the 120-second safety deadline. The host returned its
  safe `local_model_failed_review_required` fallback; it did not accept model
  prose. The owned worker stopped cleanly and removed its temporary model
  snapshot.
- The desktop runtime was CPU-only even though the driver could see an RTX
  3060. Hardware preflight and worker launch now distinguish driver inventory
  from the installed Torch runtime, and map a usable GPU by UUID rather than
  assuming driver and Torch device indexes match. The UI now tells a person
  when CPU fallback, rather than the detected GPU, would execute the model.
- An isolated, offline GPU diagnostic loaded the real shared base and r0011
  adapter on the RTX 3060. At both 64 and 256-token budgets it failed to stop
  naturally and did not reproduce both exact fictional source values. Raw
  output was withheld; only its SHA-256, bounded timing, and safety verdict
  were retained. This is a real-weight failure, not a successful specialist
  result.

Current evidence is limited to the small, repository-local fictional records
under `dist/qa801/evidence-r0011/`; it contains no client record, raw model
answer, model snapshot, corpus, or credential. r0011 remains hidden from the
production registry and excluded from the MSIX. The next admissible action is
a new immutable corrective candidate with held-out exact-source and natural
completion tests, followed by independent review and admission; changing UI
text, timeouts, or trust settings cannot repair these weight-quality failures.

Update, 2026-09-01: Evidence Review r0011 supersedes r0010 as the current
development research candidate. It passed a real-weight, production-source
UI/API journey with fictional records on CPU. The host exposed two exact
verified quotations, withheld all raw model narrative, preserved exact source
offsets through the UI drill-down, kept review required, wrote encrypted audit
state, and shut down without leaving a model snapshot. The deterministic output
boundary now also suppresses strongly labeled sensitive values and can retain
safe verified excerpts while rejecting an inexact or sensitive proposed quote.
See [`EVIDENCE_REVIEW_R0011_E2E.md`](EVIDENCE_REVIEW_R0011_E2E.md).

This proves a bounded, verifier-mediated research path—not a general legal
answering model. r0011 passed 87/87 held-out failure-family mechanical checks,
but passed only 5/12 cases on the older free-wording regression. Its raw
narrative remains hidden, production admission remains unavailable, and the
overall specialist release gate remains **BLOCKED**. The r0010 report is retained
only as historical evidence.

Current maintenance-package work is recorded in `configs/v801_release_scope.json`
and `docs/RELEASE_NOTES_v8.0.1.md`. It may produce an 8.0.1 MSIX with research
models excluded. The specialist acceptance gate described below remains blocked;
the historical statements about version/build actions refer to the earlier pass.

Recorded 2026-08-30. The requested target is **8.0.1**, not a rename of the
existing 8.0.0 package. No version was changed, new MSIX built, model admitted,
commit made, or upload performed in this pass.

## Current r0004 development workflow candidate

`mfl-fast-interchange-workflow-r0004` replaces the failed r0003 protocol
weights only as a **development source-bound workflow candidate**. It contains
seven distinct LoRA adapters trained on 252 company-owned, fictional, non-client
rows. The rows contain no Maine authority, legal conclusion, court form, real
person, confidential matter record, or attorney-reviewed evaluation.

The adapters were trained against the read-only, pinned Apache-2.0
`Qwen/Qwen3-0.6B` base on this host's RTX 3060. The model artifacts are adapter
files only, under ignored `dist/model-candidates/r0004-source-bound-workflow`;
the 1.5 GB shared base remains external and read-only. The candidate is neither
bundled nor publicly reachable in the application.

| Capability | Held-out fictional task checks | Development result |
| --- | --- | --- |
| Intake triage | 2/2 | Passed |
| Evidence review | 2/2 | Passed |
| Authority review | 2/2 | Passed |
| Drafting | 2/2 | Passed |
| Parenting-plan review | 2/2 | Passed |
| Financial-disclosure review | 2/2 | Passed |
| Safety/privacy review | 2/2 | Passed |

The acceptance runner exercised the actual candidate weights through a verified
private snapshot, the production PEFT backend, the immutable worker framing,
and the production host's source-bound prompt. It recorded 14/14 passed,
bounded natural stops, one active adapter per capability, and zero Python socket
connection attempts. It retains only check states, SHA-256 values, and timings;
it does not retain answers or source text. Peak GPU allocation was 1.34 GiB and
the 14 cases completed in 132.812 seconds on the RTX 3060. Those measurements
are this-machine development observations—not a low-end PC certification.

Evidence:

- `dist/qa801/r0004-workflow-specialist-gpu.json`
  (`F368B85E76E5999D6F58663F27E2B47E91FD41CADB8ABC6F03E9E8777D1CDAF6`)
- `dist/qa801/r0004-workflow-guards-final.xml`: 76 passed, 0 failed/errors/skips.
- `dist/qa801/r0004-workflow-runtime-final.xml`: 96 passed, 0 failed/errors/skips.

This is meaningful evidence that the seven adapters perform the tested
**source-handling workflow**. It is not evidence of current Maine law,
substantive legal accuracy, attorney review, human admission, production UI
operation, frozen-package reachability, Store GA, or Enterprise GA. Production
admission remains intentionally unavailable.

## Historical r0003 protocol-model results

The external, read-only `mfl-fast-interchange-protocol-r0003` pack contains one
Qwen3-0.6B base and seven protocol/safety LoRA adapters. It is not an admitted
Maine-law specialist release. Testing used its real weights, the production
prompt builder, the actual PEFT worker in an owned subprocess, and fourteen
fictional tasks. No generated answer text or private matter data was retained.

| Capability | Meaningful task checks | Production status |
| --- | --- | --- |
| Intake triage | 0/2 passed | Unadmitted; blocked |
| Evidence review | 0/2 passed | Unadmitted; blocked |
| Authority review | 0/2 passed | Unadmitted; blocked |
| Drafting | 0/2 passed | Unadmitted; blocked |
| Parenting-plan review | 0/2 passed | Unadmitted; blocked |
| Financial-disclosure review | 0/2 passed | Unadmitted; blocked |
| Safety/privacy review | 0/2 passed | Unadmitted; blocked |

All fourteen generations stopped naturally, with one resident adapter and zero
Python-socket connection attempts under a test denial guard. None supplied the
requested details, required source references, or an exact source quote. Their
15–51-character responses are not useful specialist work. A disclaimer or
successful neural forward pass does not change that result.

This is **not UI E2E, frozen-package inference, attorney review, OS-level
network isolation, or enterprise certification**. These weights were not
activated through the production gate to manufacture such evidence.

### CPU observations, not a minimum-hardware certification

- First attempt exceeded the unchanged 120-second activation deadline. No task
  ran in that attempt; peak sampled worker RSS was about 4.73 GiB.
- A separate diagnostic allowed up to 360 seconds for activation only. It
  loaded in 69.96 seconds, after the earlier attempt had already warmed system
  caches. The production deadline was not increased.
- Subsequent adapter swaps took 0.70–1.57 seconds; answers took 6.79–60.12 seconds.
- Four CPU threads, FP32, peak sampled worker RSS about 4.73 GiB. The host has
  31.91 GiB RAM and was running other work. These are observational timings,
  not a controlled benchmark for a 4–8 GiB PC.

## Repairs implemented

- Seven different host-owned task instructions selected from the trusted model
  capability, not record text. Task-contract hashes appear in result metadata.
- Exact-source status and freshness are included in the approved-context prompt.
- Missing/invalid specialist source references, including `[0]`, cause output
  withholding with a blocker and retained access to the host's source-backed answer.
- CPU thread count is capped at four, reserving a core where possible. Diagnostic
  CPU selection is explicit; FP32 and admission compatibility checks remain.
- The parent polls worker/descendant RSS against the admitted limit, terminates
  only its owned worker on excess, and fails closed if monitoring is unavailable.
  This is not a kernel allocation quota or a VRAM measurement.
- Before a new worker starts, available RAM must cover the policy budget plus
  1 GiB of headroom. This final preflight addition has focused synthetic tests;
  it was added after the real-weight diagnostic and is not separately certified
  by that earlier run.
- A held-out fictional task harness now rejects constant protocol replies. The
  legacy protocol builder no longer inserts the smoke evaluation prompt into
  training. Existing r0002/r0003 weights are unchanged and still contaminated
  by their historical in-training smoke prompt. The constant-target builder is
  still **not** a specialist trainer.

## Build footprint

New Store output, staging, temporary files, model caches and build environments
must be dedicated children of this repository's ignored `dist/`. Path guards
reject external/broad paths, overlapping output/staging/temp directories and
reparse-point traversal. Defaults no longer create `C:\mfl6`.

Offline builds may read the existing external build environment and pinned
engine caches without modifying them. New dependencies/caches stay in `dist/`.
Free-space checks run before build cleanup. Collected runtime and final MSIX
use in-repository moves instead of retaining duplicate copies.

These script changes passed path/parser/packaging tests; **no complete new
package build has been performed**. Their build-output footprint is therefore
not yet end-to-end qualified. The model evaluation's temporary snapshots were
closed and removed. Current retained QA reports/fictional fixtures are about
24 MiB under `dist/qa801`, not multi-gigabyte drive-root trees.

## Verification and evidence

- `dist/qa801/specialist-release-guards.xml`: 98 passed, 0 failed/errors/skips.
- `dist/qa801/specialist-integration-final.xml`: 138 passed, 0 failed/errors/skips.
- `dist/qa801/r0003-specialist-cpu.json`: first activation timeout; 14 not executed.
- `dist/qa801/r0003-specialist-cpu-diagnostic.json`: 0 passed / 14 failed / 0 not executed.
- `dist/qa801/RELEASE_8_0_1_GATE.json`: commands, evidence hashes and blockers.

The **236 passing focused tests** exercise code contracts, loopback/API/matter
boundaries, output gates, source binding, cancellation, UI integration contracts,
and build guards. They are not 236 passing model-quality or installed UI tests.

### Current full-regression result

On 2026-08-30, the current tree was collected and run with its temporary
authority fixture explicitly outside the repository:

**Historical evidence only: do not rerun the external `--basetemp` below.**
The owner's repository-only instruction now prohibits those scratch paths.
The isolated runner now keeps fixtures under its repository `dist` output;
authority tests needing another repository identity must use a synthetic one.
The full suite has not been requalified after this storage-policy change.

```text
python -m pytest -q --tb=short \
  --basetemp=<historical-external-QA-workspace> \
  --junitxml=dist\qa801\full-r0004-regression-final.xml
```

It exercised 2,361 tests and finished with **1 failure, 22 skips, and 2
warnings**. The sole failure was a `MemoryError` when the test runner attempted
to allocate a 1 MiB upload block in
`test_recoverable_remove_restore_and_explicit_reactivation[False]`. It occurred
after 509 tests in one long-lived Python process. The exact model-pack modules
were then replayed together in a fresh, isolated process and passed, including
both parametrizations of the failed recovery test. The offline-build guard also
passes 13/13 after its fixture was corrected to prevent a fallback into the
user's legacy build cache.

This makes the recovery feature evidence positive but leaves the default
single-process full-suite run **not clean**. It is recorded as a test-runner
resource limitation, not relabeled as a passing full regression, and it must
be resolved or the suite must have an approved isolated-runner policy before
release qualification.

Earlier failed test runs remain in evidence. Two packaging failures and eight
authority fixture setup errors came from tests assuming a temp root outside the
repository. Fixture bundle/data roots now use distinct QA siblings; the real
external-authority guard was not relaxed. The source-smoke test correctly
reports a repo-contained QA matter as inside the source bundle, not as proof of
external installed storage. A transport test was updated to expect the new
blocking result for its deliberately uncited synthetic reply.

## Work needed before 8.0.1 can promise working legal specialists

1. Select and record a rights-cleared substantive source set, with per-source
   terms, hashes, retrieval dates, parser state, and explicit training approval.
   The existing source library is not blanket permission to use every source for
   model training.
2. Build a separate immutable candidate from that approved input, keeping every
   held-out evaluation family outside training. The r0004 synthetic workflow
   candidate is not a shortcut around that task.
3. Run independent, intended-scope human evaluation. Do not create an attorney
   review, pilot, signature, or production trust receipt locally.
4. Qualify a low-memory inference format/runtime and its exact compatibility,
   startup, latency, cancellation, isolation, and restart behavior on target PCs.
   RTX 3060 observations do not establish a 4–8 GiB PC experience.
5. Obtain an independent signed admission for the exact hashes, licenses,
   compatibility policy, and reviewed evaluation evidence. Keep unadmitted
   candidates hidden and the production registry fail-closed.
6. Then run each admitted specialist through canonical API, real production UI,
   exact-source drill-down, review blockers, frozen app, installed package, full
   regression, and exact-package privacy qualification.
7. Resolve the current single-process full-suite memory failure, then preserve a
   clean full-regression result using the required external authority fixture.
8. Only after those gates pass, set 8.0.1/8.0.1.0 and build/qualify the exact
   new MSIX inside the repository. Microsoft Store performs Store signing;
   missing local production signing is not the present blocker.
