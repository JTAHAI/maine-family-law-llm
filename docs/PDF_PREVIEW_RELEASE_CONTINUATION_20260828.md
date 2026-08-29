# PDF preview release continuation — 2026-08-28

Decision: **BLOCKED for Store and Enterprise release.** The protected PDF-preview repair passed the scoped checks below. This is not certification of all features, the entire roadmap, legal model quality, or the installed Store application.

## Repair and production behavior

- Replaced the PDF plug-in/iframe dependency in both production UI copies with a locally rendered, hash-verified PNG page. Ordinary PDFs and image-only scanned PDFs now display through the same protected path.
- Added `legal/document_intelligence/pdf_preview.py` and the existing worker dispatch integration. Request and response temporary files are AES-GCM encrypted; the random one-use key travels only in the child environment. The worker admits at most a 32 MiB PDF and an 8 MiB PNG, limits the raster edge to 1600 pixels, runs one render at a time, and has a 25-second process timeout.
- The canonical `/api/records/preview/{token}` path enforces role, tenant, session, active matter, inspect capability, expiry, recorded original hash, and source consistency after rendering. A failed encrypted audit or vault blocks the response. The browser checks source/page/raster hashes and audit/review-required headers before displaying the page.
- Corrected an intermediate implementation that wrongly required an environment matter key. The existing default is a symbolic selector for a random OS-protected vault key, not a literal development encryption key. The final candidate was tested with an isolated production-managed vault and **no environment matter key**.
- Closing the inspector cancels display and prevents a late result from reopening it. An already-running worker can continue until its timeout. Page controls, focus trapping/return, the review-required badge, and original/copy actions remain available.
- Indexed text is explicitly labeled **“Indexed source text — page scope not verified”**. It may contain other pages or OCR errors and is not presented as the exact text of the displayed page.
- Removed in-process PDF parsing solely to discover an unknown page count; the isolated renderer supplies the count. Fixed CLI test subprocesses to use `sys.executable`, avoiding an unrelated base interpreter without project dependencies.

The renderer is a bounded subprocess, not an OS network sandbox or Windows hard memory cap. Encrypted temporary files do not imply secure memory erasure. Native PDF forms/scripts are not executed; the raster derivative does not replace full-fidelity original review.

## Evidence and exact results

Evidence root: `dist/ga_today/evidence/pdf_preview_continuation_20260828c/`.

| Proof level | Actual result | Boundary |
| --- | --- | --- |
| Full automated baseline | 2,147 passed; 22 skipped; 0 failures; 1,637.22 seconds | Managed-vault follow-up occurred during this run; not a final whole-tree version freeze. |
| Managed-vault follow-up | 67 passed; 0 skipped/failures | Focused correction tests. |
| Final current-source focused suite | 101 passed; 0 skipped/failures | PDF worker/API, inspector boundaries, qualification provenance, CLI. Runs overlap; do not add totals. |
| Final static checks | Python compile, both production workbench JS copies, component JS, collection, and `git diff --check` passed | See exact commands and timings in `managed_final_commands.json`. |
| Frozen canonical API | 26 workflow checks passed | Actual executable, fictional matter, managed vault; installed/OS-offline qualification correctly remains blocked. |
| Production UI served by frozen executable | 9 fresh browser checks passed | Record search, PDF pages 1/2, keyboard wrap, Escape focus return, cancellation, no late reopen, scanned PDF, 1280×720 primary actions. Not native WebView or installed-MSIX proof. |
| Durable frozen restart | 16 checks passed | Draft, revision, original hash, review status, and audit chain survived owned QA process termination and restart. Not native UI quit. |
| Exact candidate binding | 41 checks passed | Source → served assets → frozen executable → exact MSIX, manifest identity/language, resources, privacy and sealed-payload audits. |
| Optional adapter library, separate source environment | 1 passed, using Python 3.14 and actual PEFT libraries | Tiny locally constructed non-legal weights. No downloads or training. Not real legal inference or frozen-package qualification. |

The 22 full-suite skips are 14 unavailable Windows symlink-privilege cases, one unsupported POSIX executable-mode case, six missing archived authority/GA evidence checks, and one optional PEFT dependency absent from the Store test environment. Missing release evidence remains a blocker; skips are not passes. A later source-only PEFT check does not erase the Store-environment skip.

Earlier builds and failed/interrupted qualification attempts are preserved as superseded evidence. The initial full run was stopped after two test-harness defects were identified; the replacement full run completed. The early explicit-key preview build must not be substituted for the managed-vault candidate below.

Browser screenshots are correctly encoded JPEG QA artifacts, not final Store screenshots. API raster derivatives are true PNGs. The second-page and scanned-page screenshots were visually inspected; no private matter was used.

## Current engineering candidate

- Package: `dist/ga_today/fast_interchange_release_pdfpreview_managed_20260828/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`
- Size: **1,591,809,173 bytes**.
- SHA-256: `6de1887e7d86373fd8dc405a52ba5b1117721010b60138431b0a33f96d245fcf`
- Frozen executable SHA-256: `da3d4a459732b83dbcfd26e29477d0eb9df1bc08f02418cfcf316933c3583cd8`
- Version remains 8.0.0.0; unsigned engineering build. No certificate was created. Identity/publisher and x64 are unchanged; language is `en-us`, without `x-generate`.
- No publication, upload, commit, push, model download/training, or replacement of the user's Store installation occurred.

## Remaining release gates and next actions

1. **Legal model artifacts:** all seven FAST INTERCHANGE slots remain `specified_untrained`. The shared base is unselected; the production trust-key map and approved download-origin list are empty. Obtain rights-cleared base/tokenizer, legally usable corpus and trained adapters, reviewed evaluation/admission, and approved distribution/signing decisions. Do not silently download a substitute or use Mainely Code proprietary material.
2. **Isolated Windows installation:** qualify this exact candidate through clean install, upgrade/reinstall, and WACK in an approved isolated environment. Earlier host policy error `0x80073CFF` and WACK elevation limitations remain unresolved. Never uninstall the user's real package as a shortcut.
3. **Installed application and offline proof:** execute the native UI/core journeys, native shutdown/reopen, and OS-enforced Local-only test. Python network guards and best-effort TCP observations are not OS-level zero-network proof. Recreate missing current authority and complete GA journey evidence; skipped archives do not establish readiness.
4. **Enterprise evidence:** run actual model/hardware benchmarks on supported modest PCs, attorney-reviewed evaluations, required controlled pilot, and legal/security/product/operations sign-offs. Synthetic tests cannot supply these approvals.
5. **Final release freeze:** after these inputs and any resulting repairs, rerun the complete frozen-source regression and final package qualification. This continuation deliberately does not declare a whole-tree freeze or authorize Store submission.

The machine-readable handoff is `RELEASE_CONTINUATION.json`; `RELEASE_ARTIFACT_MANIFEST.json` binds evidence hashes. Git identity and the preserved dirty-worktree inventory are recorded there and in `source_after_verification.json`.
