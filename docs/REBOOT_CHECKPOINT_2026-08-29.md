# Reboot checkpoint — 2026-08-29

User requested immediate pause for reboot. Do not resume without user direction.

## Repository and preservation

- Working checkout: the current repository checkout, branch `main`.
- HEAD before checkpoint: `cf695900aee7c9c5b07a8d87fcd9340beeee667f`.
- Snapshot saved under `refs/checkpoints/reboot-20260829-final-r5` using an isolated Git index; the real index, branch and working files remain unchanged.
- No commit to main, push, upload, publication, version bump or private-model import.
- Ignored build/evidence files remain on disk, not in the Git snapshot.

## Latest results — not release certification

- Full regression r4 completed: 2,281 passed, 22 skipped, **1 failed**, 2 warnings, 4,011.92 seconds. XML: `dist/ga_today/evidence/08_full_pytest_current_r4.xml`.
- Failure: `tests/test_v603_extended_hardening.py::test_pass50_ledger_is_serialized_across_processes`. One worker failed in `msvcrt.locking(..., LK_LOCK, 1)` with `OSError: [Errno 36] Resource deadlock avoided`. Do not suppress or label environmental without investigation. Investigate bounded Windows lock acquisition in `legal/release/release_candidate_operations.py` and reproduce the concurrent test before another full regression.
- Earlier r3 full regression: 2,281 passed, 22 skipped, no failures. This does not override the newer failure.
- Final command-center UI state regression: 7 passed. Empty snapshot no longer falsely reports current/green. Selected-scope snapshot no longer becomes stale merely because unrelated records exist; source mutations still invalidate it.
- Native Whisper canonical API test with generated fictional speech: 1 passed, no skips, 8.164 seconds. `dist/ga_today/evidence/08_native_whisper_real_engine_r5.xml`. Frozen browser transcription still pending.
- Latest Python compilation, production/mirrored JS syntax and diff checks passed.
- Exact r5 frozen runtime: 26/26 offline feature checks passed; 7,257 observed TCP samples, no external TCP observed. This is not OS-denied-network or installed-MSIX proof.
- Actual r5 production browser UI: Both and Child Impact Lens defaults, empty snapshot, selected-scope freeze, review-required packet and exact DOCX source drill-down passed. UI evidence: `dist/ga_today/evidence/08_v8_isolated_ui_navigation_r5_checkpoint.json`; associated screenshot/DOM evidence was retained only in the local QA workspace.

## Interrupted final package

- Build was interrupted at user request. No final r5 MSIX exists at checkpoint inspection; makeappx log and package map exist. Never label the partial output ready.
- Runtime: the local r5 QA runtime (`MaineFamilyLawLLM.exe`).
- Runtime SHA-256: `bcdba1f31799bd8cb130f81c8311428a3d028181485030bfeafc990ee9b741b6`.
- Output root and staging were local QA workspaces and are not public repository paths.
- Build command used the canonical `scripts\build-msix.ps1` script with unsigned, offline, full-tier options.
- Frozen startup and 12-engine inventory passed; staging reached 10,047/10,047 files before interruption.
- Older complete r4 MSIX: `dist/ga_today/release-candidate-r4-full/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`, SHA-256 `00a3863cdea13747f313ce23bf8ef81004e6eba5a3d2dc3e2e377b25be15b1da`, 1,594,548,770 bytes. Superseded by the final UI repair, not the final deliverable.
- Preserve prior builds. Check available C/D disk space before rebuilding; do not delete old outputs without exact scope authorization.

## Resume in this order

1. Confirm checkout/changes and reproduce/repair the Windows concurrent ledger-lock failure; focused concurrency regression first.
2. Complete the canonical full-tier package using current source, fresh validated output/staging paths where required, and rerun package privacy, engines, manifest, sealed archive and hash checks.
3. Run exact final runtime/package durable restart, tracked DOCX, privacy/security, backup/transfer and runtime/cancellation runners with new evidence filenames. Prior r2 runs passed but do not prove a newly rebuilt package.
4. Exercise real native Whisper through frozen production UI. QA holder supports `--synthetic-speech-fixture dist\ga_today\evidence\08_whisper_fictional_speech_r5.wav`; requires an existing paired package. This is generated fictional audio, not private data.
5. Finish regression and hash-bound closeout. Preserve failure artifacts and distinguish service/API, actual browser, frozen runtime and installed-package evidence.

## Unresolved release boundaries

- Seven real Qwen3-0.6B protocol adapters are development transport/safety weights, not production Maine-law models. The external pack is not in the MSIX. Still need admitted substantive training corpus, legal evaluation, attorney review and independent production admission.
- Roadmap includes admitted reranker/current form gaps and broader per-feature browser, keyboard, zoom and performance validation. Do not claim all 200 end-to-end certified.
- Isolated clean install/upgrade/reinstall, OS-denied-network proof and WACK remain unproved. WACK available but current host not elevated. Microsoft signs Store distribution; do not invent a production signing claim.
- Installed Store app already version 8.0.0.0; same-version QA package is not a new Store update. Obtain/confirm next version before submission work.
- Enterprise legal/security/product/operations and pilot/human sign-offs are not synthetic tests.
- Minor visual follow-ups: weak decorative header badge contrast; active-matter context in default Chat accessed through View rather than always visible.

**Status: PAUSED FOR REBOOT. Release remains blocked.**
