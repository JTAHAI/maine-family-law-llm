# Authority and claim-boundary release continuation — 2026-08-28

Release remains **BLOCKED**. This is a software/evidence repair, not admission
of real legal authority, real model inference, attorney review, Store
qualification, or Enterprise certification. No version change, publication,
upload, commit, push, certificate creation, or modification of the user's Store
installation is part of this continuation.

## Completed engineering results

| Check | Observed result |
| --- | --- |
| Python compilation; production/mirror/component JavaScript syntax | Pass |
| Test collection | 2,227 tests |
| Focused regression | 74 passed, no failures |
| Full regression | 2,204 passed, 23 skipped, no failures; 1,642.91 seconds |
| Frozen canonical API | 22 checks per fixture, 44 total; both owned QA processes stopped |
| Production UI on exact frozen HTTP assets | 6 sparse-fixture and 5 complete-fixture checks passed |
| Fictional durable restart | 16 checks passed |
| Current source/runtime/HTTP/MSIX and package-audit binding | 45 checks passed |
| Post-regression evidence-isolation tooling delta | 7 tests passed; no packaged runtime code changed |

New unsigned engineering candidate:
`dist/ga_today/fast_interchange_release_claim_gate_20260828/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`.
Size: 1,591,811,084 bytes. SHA-256:
`3ace791afd0826a5aacab0843bdeaec0ea0a80d479582267c524c85346b4c551`.
The canonical offline build completed in 1,011.969 seconds. Store identity,
publisher, version 8.0.0.0, x64 and `en-us` remain unchanged. No Store-ready or
installed-package certification is implied.

## Defects and repairs

The full suite also regenerated four pre-existing sample/conversation reports:
`docs/external-evidence/pass47a_47h_conversation_pilot_readiness_summary.json`,
`docs/external-evidence/pass47e_conversation_eval_report.json`,
`docs/external-evidence/pass47i_47t_product_polish_summary.json`, and
`docs/sample-evidence/pass47_legal_red_team_report.json`. Their before/after
hashes are retained; their new generated contents have not been reset to HEAD
or passed off as unchanged user edits. The conversation tests now use temporary
outputs and assert repository reports remain byte-for-byte unchanged. The
red-team CLI now keeps its sidecar alongside an explicit custom output. Seven
targeted tests pass after these tooling-only repairs. The full-suite result
above precedes this final test/tooling delta, not the packaged verifier fixes.

The old authority acceptance runner asserted that live ingestion and fixed
numbers of tests had succeeded without executing those operations. It also
read mutable ingestion artifacts and historical retrieval results rather than
pinning the verified active generation. Those assertions cannot support a
current release decision.

`scripts/run-ga-authority-acceptance.py` now accepts an explicit external data
root, exact candidate MSIX, and new evidence directory. It reads one verified,
hash-bound build; checks declared artifact bytes, metadata, source-class
minimums and measured freshness; rejects ambiguous or escaped paths and
duplicate-key/nonfinite JSON; rechecks the build after its probes; and reports
unexecuted work as unexecuted. It neither downloads nor activates authority,
modifies the external store, runs pytest, nor reuses historical metrics. The
package check in this runner is an authority-data boundary check only, not a
replacement for the canonical package/private-data audit.

The new negative tests exposed a real compound-claim false pass: a strong match
to the first clause and a citation-number scoring bonus could mask an added
assertion absent from the source. The conservative lexical verifier now marks
uncovered added clauses/list items as partial support. This is not a semantic
entailment model; exact source inspection and human review remain required.

Partial support now blocks the canonical verification report, filing gate,
factual evidence map and release metric's blocked-status classification.
Optimistic summary aliases or an override cannot clear a failing claim report.
Malformed claim rows fail closed instead of raising an unchecked exception.
Fully source-matched positive controls remain supported but do not bypass
human review.

## Evidence and reproduction

Evidence root:
`dist/ga_today/evidence/authority_audit_continuation_20260828d/`.

- `source_before.json` and `source_before_build.json`: preserved-worktree and
  build-input inventories.
- `regression_commands.json`: observed compilation, production JavaScript,
  collection, focused and full-suite commands, exit codes and durations.
- `regression_focused.xml` and `regression_full.xml`: exact test results and
  skip reasons. Early failing XML files are retained as regression-discovery
  evidence, not included as passing release evidence.
- `build_commands.json`: canonical offline unsigned engineering build command.
- `frozen_claims.json`: synthetic source → actual frozen canonical API → claim
  verdict → filing blocker → exact source/span/receipt checks. No development
  server substitutes for this runtime.
- `browser_checks.json` and associated DOM/screenshots: actual production
  assets served by that executable, tested separately from API-only checks.
- `complete_fixture/`: a second run of the same exact executable with full
  synthetic retrieval-card metadata. The first sparse fixture proves the
  missing-range warning; this second fixture proves the positive exact-source
  preview, hash/date/parser presentation, receipt, blockers and focus return.
- `durable_restart.json`: fictional draft/history preservation across an owned
  QA process restart. This is not native Windows Quit or an installed upgrade.
- `exact-final-msix.json`: runtime, production assets and changed verifier/gate
  source bound to the exact MSIX, plus canonical package audit results.
- `current_authority/04_authority_acceptance.json`: current configured
  authority-root audit; missing authority is not replaced with a test fixture.
- `RELEASE_CONTINUATION.json`, `.txt` and `RELEASE_ARTIFACT_MANIFEST.json`:
  consolidated observed results, classifications, blockers and SHA-256s.

The test interpreter is the existing Store build environment's Python 3.11.
`run_checks.py --suite regression` and `run_checks.py --suite build` in the
evidence directory retain the exact argument lists and durations. Evidence
runners refuse to overwrite previous output; select fresh paths for a new run.
The canonical build remains `scripts/build-msix.ps1 -FeatureTier full -Offline
-Unsigned`, with dedicated new output/staging directories. No dependencies or
legal models are downloaded by this continuation.

## Required release inputs still missing

Known P2 usability issue: automatic claim extraction includes advisory/template
text. The sparse synthetic answer's UI report showed 0/9 supported claims and
eight blockers. This demonstrates a functioning conservative safeguard, not
successful legal-answer acceptance. A subsequent repair must separate typed,
provenance-bound legal assertions from workflow guidance, with adversarial
coverage; simply hiding these blockers or lowering thresholds is not a fix.

Next bounded code pass: reproduce the candidate list from
`browser_verification_dom.txt` through
`legal/verifiers/claim_support_verifier.py::extract_legal_claims` and
`app/services/authority_product_service.py::verify_output`. Distinguish typed
answer assertions from source-status metadata and workflow guidance at the
producer, not by trusting caller-supplied labels or dropping every unmatched
sentence. Preserve unknown/legal-looking assertions as review candidates.
Cover quoted-sentence punctuation, a genuine exact claim, an unsupported added
clause disguised as guidance, stale metadata, and caller attempts to mark a
claim nonlegal. Then repeat the real frozen chat's **Verify support** action,
source preview and filing-blocker tests. This pass has not been implemented or
certified by the current evidence.

1. The configured authority-data directory has no active verified build.
   Provision/admit reviewed official-source artifacts outside the repository,
   then run real citation, pinpoint, quote, form-freshness, Law Court and
   retrieval acceptance. Source-derived smoke rows are not attorney gold.
2. FAST INTERCHANGE's base remains unselected; all seven adapters are
   `specified_untrained`. No trusted admission key or approved distribution
   origin is configured. Supply rights-cleared, trained/evaluated artifacts and
   signed admission, or explicitly select a release scope without legal-model
   inference. Structural packs are not operational legal weights.
3. Qualify the exact candidate in an approved isolated Windows installation.
   The earlier isolated install hit `0x80073CFF`; WACK needed elevation. Those
   results are prerequisites, not successful tests of this new candidate.
   Do not alter the user's real Store package or weaken host policy.
4. Native WebView/Quit, installed upgrade/reinstall, and OS-enforced offline
   workflows need direct proof. An in-app browser and TCP observations do not
   establish these properties.
5. Real legal-model quality, modest-hardware performance, attorney-reviewed
   evaluation, controlled pilot and required human sign-offs remain separate
   external gates. Synthetic tests cannot satisfy them.

Do not update public feature/release claims or promote the engineering MSIX on
the strength of these scoped repairs alone.
