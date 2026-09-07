# Enterprise UX hardening — 2026-09-05

## Decision

**Enterprise GA: BLOCKED.** This is a verified engineering hardening pass, not
certification of every feature, a legal model, a frozen runtime, or a Store package.
No version was bumped, package built, model trained/downloaded, or code published.

The work was performed in `D:\dev\Maine-Family-Law-LLM-github-main`, branch `main`,
HEAD `258d1f091a614a1625acd285978cd6ce73daeb55`. The checkout already had 140 changed
or untracked files. Existing changes were preserved; cumulative Git differences
must not be attributed entirely to this pass.

## Defects repaired

| Area | Observed defect | Repair and evidence |
| --- | --- | --- |
| Header readability | Pale text over an almost-white status background | Removed the blanket status-span background; inspected actual rendered header. |
| Small windows | Fixed-height chat clipped Send at 640×480 | Reflow at short/narrow viewports; optional composer guidance collapsed; keyboard can reach Send at 640×450. |
| Horizontal scrolling | Viewport-width shell ignored the vertical scrollbar | Changed compact shell to containing-block percentage width; body and root both measured 625/625 client/scroll pixels. |
| Hidden panels | Closing the evidence rail reserved an empty grid column | Chat reclaims the rail space in compact workbench layouts. |
| Dialog navigation | Hidden/background controls remained reachable, and nested dialogs competed for focus | Shared isolation preserves prior inert state, excludes hidden/closed-details controls, restores visible openers, and closes only the top dialog through its cleanup handler. |
| Legacy dialogs | Custom document, record, retrieval, source-preview, and model dialogs bypassed shared isolation | Registered modal paths with the shared manager; transient source hover remains non-modal. Executable lifecycle tests and direct document/drawer checks are separate evidence levels. |
| View menu | Every menu item could become an independent Tab stop | Roving focus, arrow navigation, close-on-exit, and return to View summary. |
| Review status | A completed assistant answer displayed a green check | Answers say **Review required** or **Review blocked**; completion is never approval. |
| Uncertain saves | Generic error copy claimed records were preserved without a receipt | Unconfirmed writes warn that the operation may have completed; inspect saved state before retry. No rollback or preservation receipt is invented. |
| Text entry | Enter could send during IME composition | Composition and keyCode 229 are excluded from send behavior. |
| Official-source trust | Source-mode production chat returned seed citations while the UI reported no admitted authority | Server-owned production request context now requires the admitted authority product. Chat, source-list alias, and exact-source lookup fail closed; caller headers cannot downgrade the boundary. |
| Source UI fallback | Failed canonical source listing silently tried the generic source endpoint | Removed the fallback; official-source unavailability stays visible. |
| Version display | Public presentation said v9 while runtime/footer said 8.0.1 | Public presentation uses the canonical product version; no release version changed. |

Both shipped `workbench.html`, `.css`, and `.js` copies remain byte-identical.
The workbench source and packaged-asset contracts were tested; this does **not**
mean an existing frozen binary contains the repaired assets.

## Verification

- Final combined focused run: **228 passed, 0 failures, 0 errors, 0 skipped**, 46.213 seconds.
- Full test collection: **2,642 tests across 549 files**, exit 0. Full suite execution
  was not repeated in this pass; earlier full-regression receipts remain historical.
- Python compilation of `legal app src maine_family_law_llm scripts tests`: passed.
- Both production JavaScript mirrors: Node syntax checks passed.
- Targeted Ruff checks of the new boundary and regression tests: passed.
- `git diff --check`: passed; Git emitted existing LF/CRLF conversion warnings for
  two Store build files, not whitespace failures.
- Existing Starlette/httpx deprecation warning remains; dependencies were not changed.

Exact final test command (using the repository's existing Store Python):

```powershell
& dist/build-env/store/Scripts/python.exe -m pytest -q tests/test_enterprise_ux_interaction_boundaries.py tests/test_full_ux_hardening_v700.py tests/test_ga_ux_accessibility_polish.py tests/test_ga_workbench_source_availability.py tests/test_public_workbench_ux_upgrades_v209.py tests/test_v500_responsive_ux_hardening.py tests/test_production_chat_accessible_metadata.py tests/test_production_authority_lane_boundary.py tests/test_ga_gateway_closure.py tests/test_chat_streaming.py tests/test_fast_interchange_hardware_readiness.py tests/test_fast_interchange_ui_lifecycle.py tests/test_pass126_keyboard_command_system_acceptance.py tests/test_record_inspector_media_boundary.py tests/test_v900_prose_legal_ops_and_sentinel.py tests/test_v500_source_flyout_and_open_ux.py tests/test_v520_answer_first_evidence.py tests/test_v530_hyphen_search_and_evidence.py tests/test_store_packaging.py --basetemp=dist/enterprise-ux/tests-final --junitxml=dist/enterprise-ux/evidence/verified-regression.xml -o cache_dir=dist/enterprise-ux/pytest-cache
```

## Actual browser evidence

The canonical `app.api.production:app` gateway was started on loopback port 8769
with a fictional repository-local profile and deliberately unavailable authority.
The real `/public` workbench was exercised through browser input, not DOM mutation.
The user's existing app/tab was not used. The owned server was stopped, owned tab
closed, and temporary browser viewport override reset afterward.

- Modern chat, full workbench, view menu, settings, AI controls, document workspace,
  compact evidence drawer, and the no-authority answer were exercised.
- Actual fictional question: “FICTIONAL QA ONLY: What sources are available for
  reviewing a parenting order?” Final answer had zero source cards and visibly
  blocked substantive legal research; no model memory/seed authority was substituted.
- The final warm no-authority response displayed 16 ms first feedback and 54 ms
  total. An earlier run displayed 446/455 ms. These are individual UI observations,
  **not** model inference benchmarks or a performance acceptance distribution.
- Compact evidence drawer: modal role, zero outside keyboard controls, Escape
  returns to the View summary, no lingering inert regions.
- Document workspace: modal isolation and Escape recovery; missing matter errors
  remain visible. This did not create a real/private matter or prove drafting E2E.
- 640×450: Send received keyboard focus with its bottom at 375.23 px; no horizontal
  overflow after the final fix. Vertical scrolling at small heights is intentional.
- Final browser console error query returned no errors.
- Actual OS/browser 200% zoom, Narrator, forced-colors rendering, full cancellation
  and restart integrity, and every model/source-positive workflow were **not proven**.
  Enlarged text, narrow CSS viewport, semantic checks, and CSS guards are narrower evidence.

Screenshots and DOM receipts are under `dist/enterprise-ux/evidence/`:

- `chat-verified.png`: fictional blocked-source answer, review badge, readable header
  (1280×900 PNG).
- `small-window-verified-png.png`: final scrollbar-free 640×450 viewport keyboard
  path (the browser's captured image excludes scrollbar space: 625×439 PNG).
- `production-chat-dom.txt`: actual fictional answer and control semantics.
- Earlier screenshots and failed intermediate JUnit results are retained as historical
  debugging evidence; they are not the final acceptance baseline.
- The browser originally returned JPEG bytes despite the requested .png filenames.
  The two final baselines were re-encoded as PNG without resizing or visual edits;
  the original captures remain unchanged and their actual encoding is recorded.

## Remaining release blockers

1. **Trusted Enterprise identity/session bootstrap is not established.** Local
   loopback protections and role/capability checks do not make caller role/tenant
   headers a trusted multi-user identity system.
2. **Specialist legal quality is still blocked.** Existing Evidence r0013 receipt
   reports 40 semantic passes out of 104 attempts, `decision=BLOCKED`; this pass did
   not train or re-evaluate weights. The admission trust store has no trusted keys.
   No research weight was promoted. Drafting also lacks a fresh passing admission.
3. **Whole-product acceptance remains incomplete.** Reconcile the feature truth
   ledger and actual navigation before advertising legacy/development surfaces.
4. **Full current-tree regression and source-positive E2E still required.** The QA
   profile deliberately had no admitted authority or private matter. Passing its
   fail-closed path is not proof that an admitted library, draft, export, or source
   drill-down works end to end in the intended deployment.
5. **Fresh frozen/MSIX qualification is absent.** Existing runtime/build artifacts
   predate these changes. Rebuild once source gates pass, then test isolated install,
   restart, offline workflows, privacy/engine audits, and applicable WACK checks.
6. **Accessibility coverage is incomplete.** Test native zoom, assistive technology,
   high contrast, remaining dense-panel labels, and all nested source-positive flows.
7. **Reproducibility remains limited.** Existing repository Store Python uses a
   pre-existing external site-packages overlay; this was not a clean dependency build.

No test result in this report supplies an attorney, independent security, pilot,
operations, or organizational sign-off.

## Disk hygiene

No model or frozen-runtime copies were created. All new fixtures, profiles, caches,
screenshots, and logs stayed under `dist/enterprise-ux` in this repository.
After process/path/reparse checks, deletion of the identified disposable directories
was denied by execution policy. It was not retried through another tool or shell.
Approximately 28 MiB remain; the JSON receipt records exact measured sizes.
Earlier denied cleanup paths under `dist/ga-closure` were not touched.
