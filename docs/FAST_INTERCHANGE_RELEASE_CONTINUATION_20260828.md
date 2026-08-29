# FAST INTERCHANGE release continuation — 2026-08-28

Decision: **BLOCKED** for Store and Enterprise GA. This is scoped engineering
verification, not certification of every roadmap feature or a version freeze.

## Candidate and verification boundary

Candidate: `dist/ga_today/fast_interchange_release_textfallback_20260828/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`

- Bytes: 1,591,792,644.
- SHA-256: `d374aa245ee4395b5be41babcd34c5c5c5906a28b837a8bb55ba771479c03527`.
- Frozen EXE SHA-256: `f3aca36782786f2815b1c5970a2a6576a8438ac1e18964f0c6a91e05003498e0`.
- Unsigned engineering build; existing Store version remains 8.0.0.0.
- No upload, signing certificate creation, version bump, commit, or push.

Evidence directory: `dist/ga_today/evidence/release_continuation_20260828b/`.
Its `RELEASE_CONTINUATION.json`, text summary, and artifact manifest record the
exact checks and hashes. These local reports are not a Store submission bundle.

## Repairs and direct evidence

1. A real frozen searchable-PDF OCR call exposed missing OCRmyPDF `Occulta.ttf`.
   The package now includes required fonts, ICC data, and notices. Missing or
   empty resources fail the engine inventory. OCR preserves the original and
   returns hash-verified PDF and text derivatives through the canonical API.
2. The qualification runner no longer counts developer-Python parsing, privacy,
   or OCR calls as frozen-app operations. It verifies actual runtime instance,
   canonical actions, completed OCR text, source/artifact hashes, and real engines.
3. Irrelevant inspector controls now remain hidden. The production UI fetches
   protected media and exposes review-required status. PDF recovery displays
   indexed text and safe original/download actions, with explicit OCR and visual
   fidelity limitations. Native PDF rendering was blank in this browser and is
   **not certified**; recovery is not a replacement for visual-source review.
4. The evidence assembler rejects stale or mismatched executables and incomplete
   restart reports. Actual EXE bytes inside the supplied MSIX must match.
5. A committed fictional draft survived owned-process termination/restart with
   the same revision, content hash, and valid audit history. This is not native
   application quit or installed-package upgrade evidence.

## Exact test levels

- Full automated suite: **2,087 passed, 21 skipped, zero failures**, 1,596.501 s.
  Fourteen skips require unavailable symlink privileges; one requires POSIX
  executable mode semantics; six lack archived authority/GA evidence and remain
  release-evidence gaps, not successful tests.
- Final changed-surface regression: **70 passed, zero failures/skips**. It covers
  final incremental preview and evidence-harness edits made during/after the full
  run. Counts overlap and must not be summed. No final whole-tree freeze claimed.
- Python compilation, production/mirrored JavaScript syntax, collection,
  fatal Python lint checks, and Git whitespace validation pass.
- Rebuilt frozen API: **23 scoped feature checks pass**. Offline qualification
  correctly remains blocked: driver socket guards and TCP polling are not
  OS-level zero-network or installed-package proof.
- Browser against frozen API: **six scoped actions pass** (fictional record
  question, image inspection, focus wrap/Escape, PDF text recovery, draft import,
  revision proposal). Native commit dialog, full accessibility, and all advertised
  workflows are not certified. The browser uses a fresh QA application origin,
  not a separately installed Windows application.
- Restart: **16 checks pass**; exact-package/source/served-asset binding: **40
  checks pass**. Package privacy, path, sealed-payload, and engine audits pass.
- The core API matrix verifies 10/14 scoped journeys; browser observations are
  kept separately rather than promoted into a full native-navigation certificate.

## Required next actions

1. Supply/select rights-cleared base/tokenizer, authorized corpus, trained
   adapters, and independent admission. All seven legal model slots remain
   `specified_untrained`; production trust has zero keys and zero approved
   download origins. Bundled OCR/document engines are not legal LLMs.
2. Use an isolated Windows QA environment permitted to install the candidate and
   run WACK. Historical registration failed with host policy `0x80073CFF`; WACK
   needs elevation. Neither was reclassified as success or retried as fresh proof.
3. Prove installed offline workflows, upgrade/reinstall, native quit, and native
   PDF viewing. Complete current admitted-authority/core-UI evidence, modest-PC
   real-model benchmarks, and required legal/security/pilot/sign-off gates.
4. Choose and freeze an approved later package version only after the gates pass.

Do not repurpose Mainely Code or proprietary weights. Do not relabel model-empty
or fictional tests as trained legal inference, attorney evaluation, or pilot data.
Earlier failed reports and the original user's worktree changes remain preserved.
