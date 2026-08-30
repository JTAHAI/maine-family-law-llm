# 8.0.1 specialist release gate — BLOCKED

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
