# 8.0.1 build checkpoint for Terra

User requested a checkpoint at the next safe stop, before switching to Terra.
Do not restart the feature backlog or rebuild a successful candidate first.

## Workspace and preservation

- Actual checkout: the current repository checkout (not a historical v6.0.3 directory).
- Branch: `main`; starting HEAD: `cf695900aee7c9c5b07a8d87fcd9340beeee667f`.
- The worktree contains substantial pre-existing changes. Preserve all of them.
- No commit, push, Store submission, certificate creation, model download, or training was performed by this build run.
- Generated build output stays under this repository's ignored `dist` directory. Do not create C-drive staging trees.

## Completed verification

- Python in-memory compilation: 1,258 files passed; production JavaScript syntax checks passed.
- Full test collection: 2,365 tests, no deselections. Original complete run: 2,336 passed, 7 failed, 22 skipped.
- Repaired release documentation/current-version assertions and reran the **entire** affected batches 07, 08, and 09.
- Effective full regression: **2,343 passed, 0 failed, 22 skipped**. Skip reasons are in the JSON reports (principally Windows symlink privileges and POSIX executable-mode behavior).
- Original results retained: `dist/release/v8.0.1/regression/summary.json`.
- Repaired batch evidence/accounting: `dist/release/v8.0.1/regression-metadata-repair/summary.json`.
- Test runner: `scripts/run_isolated_release_regression.py`; each batch uses a fresh interpreter and reconciles JUnit test identities with exact collection. Its one external authority-fixture temporary root was automatically removed.
- Cached Store environment dependency audit: 159 distributions; no known vulnerabilities; `en-core-web-lg` was skipped by PyPI vulnerability lookup. See `dist/release/v8.0.1/dependency-audit.json`.
- Actual frozen 8.0.1 executable built and startup smoke passed. An empty authority store correctly produced `official_authority_product_unavailable`, not a fabricated grounded answer.

## Candidate and evidence

- Expected exact candidate: `dist/v801/msix/MaineFamilyLawLLM_8.0.1.0_x64.msix`.
- Paired frozen runtime: `dist/v801/runtime/MaineFamilyLawLLM.exe`.
- Build log: `dist/release/v8.0.1/build.log`.
- Canonical package audits: `dist/v801/evidence/`.
- **Read `dist/release/v8.0.1/CHECKPOINT.json` for final build outcome, exact hash, size, audit statuses, and retained files.** This document alone is not a release certificate.
- Package is intentionally unsigned for Microsoft Store signing; no developer certificate was substituted for production signing.
- Build completed successfully. Final MSIX: **1,594,559,623 bytes**; SHA-256:
  `a98ef67094d866c17949e9a18f7522cd56d164c042ceda07af75a7c1cad82be0`.
- The exact MSIX passed private-data, manifest, engine inventory, sealed archive,
  path, and size-budget audits; paired executable bytes match.
- Store identity/publisher/x64 preserved; package version 8.0.1.0; language en-us.
- Version metadata is 8.0.1, build 54. Existing storage schema is unchanged.
- Scope: `configs/v801_release_scope.json`; notes: `docs/RELEASE_NOTES_v8.0.1.md`.

## Models: do not bypass admission

No new production-admitted legal weights are included. The newly completed
`mfl-evidence-review-research-r0003` adapter exists in the authorized model
project, but its latest reviewed report is **6/12**, with `production_admitted`,
`rc_complete`, and `attorney_reviewed` all false. Its 25,600 examples are
fictional research data, not admitted substantive Maine-law training.

Read-only evidence is retained in the separately authorized model workspace:
the model-training report and its training-run receipt. Those external paths
are intentionally not part of this public repository or release package.

The separate seven-adapter r0004 workflow candidate under
`dist/model-candidates/r0004-source-bound-workflow` remains unadmitted too.
Do not relabel protocol weights as legal expertise or ship them through an
admission bypass. Do not copy or modify unrelated proprietary assets.

## Exact next work (not executed at checkpoint)

1. Confirm `CHECKPOINT.json` says the package build passed. Rehash the MSIX and compare its hash. Do not rebuild solely to resume tests.
2. Run the prepared exact-candidate frozen regression driver:

   ```powershell
   python -B dist\release\v8.0.1\run_frozen_acceptance.py
   ```

   It sequentially runs durable draft/restart, navigation continuity,
   privacy/security, and reliability against the paired runtime and MSIX.
   Each existing runner checks packaged executable bytes. Evidence goes to
   `dist/release/v8.0.1/frozen-acceptance`. It refuses existing output.
   Use a new evidence location if an earlier attempt exists; retain failures.
   These are frozen canonical-API checks, not installed-native-UI certification.

3. Run the fictional import/OCR/privacy/source-preview qualification, keeping
   temporary state under repository dist:

   ```powershell
   $env:TEMP = (Join-Path (Get-Location) 'dist\build-temp')
   $env:TMP = $env:TEMP
   $env:PYTHONDONTWRITEBYTECODE = '1'
   python -B scripts\run-installed-offline-qualification.py --runtime-executable dist\v801\runtime\MaineFamilyLawLLM.exe --evidence-root dist\release\v8.0.1\offline --hold-seconds 600
   ```

   This starts a hidden, isolated frozen service with fictional records, not
   the user's real Store app. `browser-ready.json` contains its exact URL.
   Use the browser skill to inspect that production UI and perform meaningful
   fictional actions. Verify Both mode and Child Impact Lens default on,
   chat/side-panel interactions, review status, and exact source drill-down.
   Record observed behavior/screenshots; do not infer UI success from routes.
   Put `stop-probe` in that evidence directory after browser work to allow
   clean driver completion. The script's overall exit 2 is expected when only
   installed-MSIX/OS-network qualification is absent; **check the separate
   `feature_check_status` and all blockers**. A genuine feature failure is not
   an environmental skip. The fixture directory is not automatically removed
   by this particular legacy runner; clean only its newly owned directory
   after the process exits, with validated absolute paths.

4. Record actual UI results as `dist/release/v8.0.1/browser-verification.json`
   with `status`, meaningful actions, results, and evidence paths. A prepared
   optional evidence aggregator is `dist/release/v8.0.1/finalize_release_evidence.py`.
   Inspect its inputs/status-field expectations before running it. It has not
   been executed at this checkpoint and must not fabricate absent reports.
5. Installed clean-install/upgrade/uninstall and WACK remain **not executed**.
   Current process is not elevated. Do not uninstall the user's real Store
   package or claim an unsigned frozen smoke is an installed-MSIX test.
   OS-level zero-network proof, attorney evaluation, and enterprise sign-offs
   are also not established by these software checks.
6. If a real product defect appears, preserve its failure evidence, repair it,
   rerun focused/full applicable tests, and rebuild only if shipped bytes change.
7. Deliver the exact MSIX with hash and honest qualification/model boundaries.

## Repairs in this run

- Bounded the model-pack test upload helper's final read to avoid an unnecessary
  one-MiB EOF allocation in the exhausted full-suite interpreter. Production
  chunk-size/security behavior was not weakened.
- Added sequential isolated regression/coverage-accounting runner and four tests.
- Updated canonical version sources, intended current-release fixtures, and
  release documentation to 8.0.1/build 54; no blanket replacement of historical schemas.
- Retained old-package preflight now explicitly expects the old 8.0.0 package
  to fail the current 8.0.1 identity check.
- Added honest maintenance scope with both research model candidates excluded.
- Pinned future PyInstaller cache output under repo `dist/build-temp` as well.
  The already-running build had loaded the prior cache setting before this
  build-only containment fix; no runtime bytes were changed by that setting.

This is a **working-tree/build checkpoint**, not a Git commit or a claim that
all specialist AI, all planned features, Store GA, or Enterprise GA are complete.

## Cleanup limitation

Deletion of the following newly generated disposable folders was rejected by
the environment policy after read-only containment/reparse checks. They remain
intact; do not bypass that rejection with a different tool or deletion script.
The user can remove them manually if desired. Approximately 2.90 GB total:

- `dist/v801-stage`: 2,548,434,161 bytes, staging copy only.
- `dist/v801/build`: 348,579,101 bytes, build scratch only.
- `dist/v801/pyinstaller`: empty collection output directory.

**Keep `dist/v801/runtime`, `dist/v801/msix`, and `dist/v801/evidence`** for the
paired-runtime verification handoff. No old C-drive folders were touched.
