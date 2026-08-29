# FAST INTERCHANGE: operational completion and verification plan

Snapshot: 2026-08-27 America/New_York (2026-08-28 UTC evidence). This is an implementation handoff, not a completion certificate. No hosting account, upload, model download, training run, application change, or new package was created by this planning pass.

## Outcome required

Update, 2026-08-28: signed admission, immutable loading, bounded subprocess
execution, task binding, canonical cancellation, and production-UI recovery are
now implemented. See [the signed-worker verification report](FAST_INTERCHANGE_SIGNED_WORKER_VERIFICATION.md)
for the exact evidence levels and remaining limitations. Secure model-pack
download/distribution and full lifecycle management remain open. The bounded
offline signed-pack import/inspection/activation path now has service/API and
production-JavaScript tests, but its native file-picker browser journey is not
proven. Real legal artifacts/evaluation, hardware qualification, and a new
installed-package proof remain open. Do not treat these local runtime tests as
completion of the full operational plan.

Implementation update, 2026-08-28 UTC: the bounded release-preflight and FI-01
source/approval repairs now have 153 passing focused tests, one explicit skip,
and actual production-source browser evidence using a synthetic generation
client. See [the implementation report](FAST_INTERCHANGE_FI01_VERIFICATION.md)
for the earlier changes and limits. The signed-worker update above supersedes
its admission and worker-lifecycle snapshot. Real-model behavior and package
qualification remain open even where the corresponding local code tests pass.
No real legal model or new package was supplied by either update.

Deliver a desktop application that can acquire approved model data with explicit consent, run useful source-grounded inference locally on declared modest hardware, switch between seven real compatible capability adapters, and preserve privacy, source verification, cancellation, and review-required safeguards. Verify the exact installed MSIX, not merely Python handlers or a development frontend.

Use `D:\dev\Maine-Family-Law-LLM-github-main`. At inspection: branch `main`, HEAD `8fd54274ead2334be1f6b45216352796ab41e940`, 396 existing changed/untracked entries. Preserve all work. Mainely Code remains proprietary and out of scope. Consult `FAST_INTERCHANGE_TERRA_HANDOFF.md` for existing file-level FI-01 through FI-06 work; this document updates its package/test snapshot and adds the proposed distribution path. Do not rewrite the 200-slice backlog.

## Verified snapshot and limitations

- Current candidate: `dist/ga_today/fast_interchange_store_candidate_active_authority/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`.
- SHA-256 rechecked: `1839c427d5e49c994f195316ed57cbde7096586798d649cf21e31767949ce4d8`.
- Archive size: 1,591,350,737 bytes (1.59 decimal GB / 1.48 GiB). Uncompressed entries: 2,545,822,317 bytes, before installation overhead or optional models.
- Latest full application report: 1,787 total = **1,765 passed + 22 skipped**, zero failures/errors, 1,905.412 seconds. Report: `dist/ga_today/evidence/fast_interchange_release_full_regression_active_authority_repaired_junit.xml`. Do not repeat the earlier incorrect claim of 1,787 passes plus 22 skips. Later packaging-tool edits had focused tests, not a new full run.
- Exact extracted runtime: offline qualification and durable-restart, exhibit, and courtroom-media scripts reported passes. This does not prove installed MSIX behavior, every browser action, or real FAST INTERCHANGE inference.
- Isolated QA install: blocked by host sideload/developer policy, error `0x80073CFF`. WACK: not executed because elevation was unavailable. Preserve the user's installed Store package.
- Candidate is unsigned. Distinguish local installation trust from Partner Center upload requirements; do not invent a requirement to buy a certificate or label a self-created test certificate production signing.
- Seven FAST INTERCHANGE slots exist as specifications; zero trained capability adapters or approved shared-base weights are bundled. Real model inference, legal quality, target-PC performance, and Enterprise GA are not certified.

## Full model/data inventory in this candidate

Inspected the actual ZIP/MSIX entries, not only source requirements. Libraries such as PyTorch, Presidio, sqlite-vec, and qdrant-client are not generative models.

| Bundled model/data | Purpose |
| --- | --- |
| spaCy `en_core_web_lg` 3.8.0 | English NLP/privacy-analysis support: NER, parser, sentence recognizer, tagger, tok2vec, vectors, and lookup tables |
| Docling `docling-layout-heron/model.safetensors` | Document layout |
| Docling `tableformer_fast.safetensors` | Table extraction, fast variant |
| Docling `tableformer_accurate.safetensors` | Table extraction, accurate variant |
| RapidOCR `ch_PP-OCRv4_det_mobile.pth` | OCR detection |
| RapidOCR `ch_PP-OCRv4_rec_mobile.pth` | OCR recognition |
| RapidOCR `ch_ptocr_mobile_v2.0_cls_mobile.pth` | OCR orientation/classification |
| RapidOCR `en_PP-OCRv3_det_mobile.pth` | English OCR detection |
| RapidOCR `en_PP-OCRv4_rec_mobile.pth` | English OCR recognition |
| RapidOCR `PP-OCRv6_det_small.onnx` | OCR detection |
| RapidOCR `PP-OCRv6_rec_small.onnx` | OCR recognition |
| RapidOCR `ch_ppocr_mobile_v2.0_cls_mobile.onnx` | OCR orientation/classification |
| Whisper `ggml-tiny.en-q5_1.bin` | Quantized English speech transcription |
| Tesseract `eng.traineddata` | English OCR |
| Tesseract `osd.traineddata` | Orientation/script detection |

Six RapidOCR weight files appear in both `_internal/rapidocr/models` and the Docling model tree. Matching names/sizes are a deduplication candidate, not proof either path can be removed. Hash both copies and test every consumer before changing packaging. spaCy subcomponents above belong to one pipeline, not separate chat models. The archive also contains a small `parser_regression/malformed_download_v1.bin` fixture; determine whether it is a required packaged self-test or unintended test residue rather than calling it a model.

Absent: an approved generative base/tokenizer, all seven trained law adapters, and an independently admitted legal reranker. `configs/fast_interchange_model_fleet.json` explicitly says `specified_untrained_no_artifacts` and `unselected_pending_rights_and_evaluation`.

| Planned slot | Capability to prove with a real adapter |
| --- | --- |
| `family-intake-triage-small` | Identify a missing intake fact and ask a grounded follow-up |
| `family-evidence-review-small` | Compare conflicting source-bound statements without promoting allegations to findings |
| `family-authority-review-small` | Explain an admitted authority passage with exact source drill-down |
| `family-drafting-small` | Produce a review-required draft and expose unsupported claims |
| `family-parenting-plan-review-small` | Identify a fictional scheduling conflict without deciding custody |
| `family-financial-disclosure-review-small` | Identify a missing disclosure and verify arithmetic without making a legal award |
| `family-safety-privacy-review-small` | Flag a fictional privacy/safety issue without assuming emergency adjudication |

## Distribution recommendation, not yet enabled

1. **Hugging Face public model repositories:** recommended primary for redistributable public models/adapters, licenses, model cards, and pinned revisions. Free public storage is best-effort, not an unlimited contractual allocation or availability guarantee. Use the upstream publisher's pinned files when redistribution is not permitted; do not mirror restricted artifacts.
2. **GitHub Releases:** practical backup for project-owned model packs and signed metadata. Individual assets must be under 2 GiB; GitHub documents no total release-size or bandwidth quota. This is Releases, not GitHub Pages or Git LFS. Split packs along manifest file boundaries if necessary.
3. **Cloudflare R2 Standard:** production distribution alternative with 10 GB-month storage, 1 million Class A operations, and 10 million Class B operations free monthly, and no direct egress charge. Excess storage/operations can incur charges. Production access needs a custom domain rather than the rate-limited development `r2.dev` endpoint. Domain/subscription costs and account authorization are separate.

Sources checked for this plan: [Hugging Face storage](https://huggingface.co/docs/hub/main/storage-limits), [pinned HF downloads](https://huggingface.co/docs/huggingface_hub/guides/download), [GitHub release quotas](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases), [R2 pricing](https://developers.cloudflare.com/r2/pricing/), [R2 production limits](https://developers.cloudflare.com/r2/platform/limits/), [Microsoft Store policies](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies).

These hosts distribute bytes; none supplies model admission or legal validation. Downloading model data is not remote inference. Downloads still expose ordinary connection metadata such as IP address to the host, which must be disclosed. Do not upload matters, prompts, training records, evaluation stores, or credentials.

Current `configs/store_feature_tiers.json` deliberately disallows runtime downloads. Do not flip that flag alone. This proposed explicit-download mode requires the complete manager and tests below, a documented policy change, and updated Store dependency/disclosure review. Strict Local-only mode continues to make zero external requests. Support offline import of the same signed packs for disconnected users.

## Ordered implementation and acceptance gates

### 0. Establish an honest baseline and repair release evidence

- Run Git root/branch/HEAD/status/diff checks and save the inventory before edits. Discover applicable AGENTS.md instructions. No reset, clean, stash, or unrelated rewrite.
- In `src/maine_family_law_llm/store_preflight.py`, final readiness is currently calculated before adding `wack:package_hash_mismatch`. Fix ordering so every required blocker participates. A report that says `pass` or `completed` for a different package must not qualify this candidate. Define actual WACK success, not just process completion.
- Extend `tests/test_store_preflight.py` for pass-status mismatched/missing hashes, contradictory report fields, stale paths/reports, actual WACK failure, and correctly bound success. Bind all install/offline/WACK evidence to the final SHA, not a filename/default path.
- Make `scripts/qualify-v700-qa-msix.ps1` reject unknown arguments and stale reused work roots. Correct parameters are `-FinalMsix` and `-EvidenceRoot`; WACK uses `-PackagePath` and `-OutputRoot`. Preserve historical failed reports.
- Reconcile historical test-count and package-status prose without replacing source evidence. Classify each skipped test; required archived-E2E evidence is missing proof, not a pass.

Exit: no known false-ready path in evidence tooling; current blockers recorded.

### 1. Finish host source, matter, role, and approval binding (FI-01)

Edit existing authority services, `legal/agent_runtime/runtime.py` and `providers.py`, and both canonical desktop API/UI mirrors as needed. The generic immutable authority-list repair is a prerequisite, not completion of this gate.

- Preview/run accept references, not trusted caller-provided source prose/status. Rehydrate authority from one verified immutable build; require source ID, hash, exact span, and build identity. Bind private records to authenticated actor, active matter, record capability, and immutable artifact hash.
- Bind approval to actor/session/matter, provider/model/release/capability/task, source generation, and exact context. Recheck immediately before dispatch; expired, changed, revoked, or replayed approvals fail closed.
- Canonical HTTP tests must prove roles, matter isolation, audit failure handling, encryption of private durable receipts, and safe errors. Do not merely invoke handler functions directly.
- Add `tests/test_fast_interchange_host_source_binding.py`: forged text/status, wrong/mutated/stale build, wrong hash/span, cross-matter, missing actor, revoked capability, changed task/model, audit failure, and authorized fictional success. Include a concurrent active-build switch to detect inconsistent pointer reads.

Exit: model input is server-authorized source data; source drill-down matches exactly what was approved.

### 2. Finish trusted model admission and immutable loading (FI-02)

Use registry/inventory classes in `legal/fast_interchange/worker.py` and `fleet.py`; do not reorganize files just to match suggested module names.

- Strict schema: base, tokenizer, adapter, template, runtime, format/quantization, capability, compatibility limits, licenses, evaluation IDs, release state, file sizes/hashes, and independently signed admission.
- Pin an operator-approved trust anchor in the application. A hash or a self-declared production flag is not permission/admission. Test keys must never be production trust. Define key rotation, expiry, revocation, and rollback protection.
- Enumerate every loader-consumable file. Reject unlisted files, unknown fields, duplicate JSON keys/IDs, conflicting Windows case, alternate data streams, symlinks/junction escapes, unsafe config imports, wrong tensors, and oversized allocations.
- Prevent mutation between verification and loading/reactivation. Avoid rehashing multi-GB weights each request only after proving a safe immutable identity/cache strategy.
- Add `tests/test_fast_interchange_artifact_registry.py`; test offline loading with remote-code execution disabled, no automatic tokenizer/model fetch, and revoked releases rejected.

Exit: an untrusted download cannot become an admitted model, and verification remains valid at actual load time.

### 3. Implement secure optional model-pack acquisition

Keep download code outside the inference worker. Suggested new ownership: `app/services/model_pack_service.py`, canonical `/api/model-packs` catalog/status and authenticated install/cancel/remove/import actions, and the existing production model chooser. Reuse established job, audit, and encryption facilities rather than a parallel state system. Names are implementation targets, not existing routes.

- Display pack purpose, publisher/license, exact version, download/installed/staging size, hardware needs, consent, and dependencies. One compatible base is shared by its seven adapters; do not download seven copies.
- Use an app-trusted signed catalog with pinned artifact hashes, byte counts, immutable IDs, and approved HTTPS origins. Validate every redirect; reject arbitrary URLs, embedded credentials, downgrade, private/link-local destinations, and unapproved hosts. Cross-origin redirects must not carry credentials. No user or developer secret in the bundle/browser.
- Bound body size, concurrency, disk space, retries, and time. Resume only if the immutable artifact/ETag and range semantics match; a changed response must never append to stale partial bytes. Cover 200/206/416, 429, timeout, interrupted connection, and exhausted disk.
- Stage outside the repository/MSIX and outside matter stores. Verify signatures, size, and content hashes before atomic activation; keep last-known-good packs. No executable installers, pip, remote scripts, or unsafe pickle-style model loads. Existing bundled `.pth` files are not an exemption for new untrusted downloads.
- Show progress, cancellation, recoverable errors, installed version, shared-base dependencies, and removal impact. Never remove a base used by an active/dependent adapter. Corrupt packs stay quarantined; startup must survive partial state.
- Strict Local-only refuses all outbound acquisition, discovery, and update checks. Explicit download mode contacts only approved model hosts and sends no matter content; returning to Local-only blocks again. Offline signed-pack import must produce identical admission results.
- Add meaningful service, canonical API, and browser tests for valid install/import, revoked/corrupt pack, malicious archive/path, wrong signature, cancel/resume/restart, interrupted activation, rollback, missing base, and no-network enforcement.

Exit: a real approved artifact can be installed from a chosen host and from an offline file, with the same verified identity. Mock downloads prove failure handling only, not live delivery.

### 4. Finish worker lifecycle, cancellation, and capability routing (FI-03/04)

- Bound streamed request bytes, not only Content-Length. Keep fixed authenticated loopback requests, no arbitrary tools/URLs, no public listener, no silent provider fallback, and no token in UI/logs.
- Keep blocking generation off the ASGI event loop; serialize generation with a bounded queue. Cancel must stop actual backend work, clear request context in `finally`, and leave truthful canceled/quarantined state. Browser fetch abortion alone is insufficient.
- Verify reset before/after each request and adapter switch, including errors and concurrent/cross-matter requests. Quarantine identity, cleanup, or completion failures. Preserve no silent truncation and explicit EOS requirements.
- Route an approved task to exactly one admitted capability. Client text/model output cannot pick an adapter or override host source/quote/claim/filing gates. Display cold/ready/running/canceling/canceled/quarantined/review-required states honestly.
- Test real-library loading/tokenization/quantization on supported Windows CPU runtime. Do not assume the planned NF4 path runs efficiently on every CPU or that installed GPUs are usable by this Python runtime.

Exit: actual generation, cancellation, restart, and seven-slot switching work without retained private context. Synthetic backend results are separately labeled.

### 5. Obtain and evaluate actual model artifacts (FI-06)

- Select a specific rights-cleared small base and tokenizer, immutable revision, compatible runtime/quantization, and redistribution route. Record a decision; do not reuse proprietary weights. External hosting does not supply missing permission.
- Establish authorized privacy-reviewed training data, provenance, splits, one-capability recipes, and reproducibility. Produce seven compatible real adapters. Pin all outputs and run separate held-out tests per capability.
- If shipping an interim grounded general base, label it general and leave specialized slots unadmitted; never count it as seven trained law adapters. This does not satisfy the requested full seven-slot completion.
- Use current admitted Maine authority, exact citations/spans, valid/fake citations, mismatched quotes, stale/wrong-jurisdiction authority, conflicting facts, and missing evidence. Legal/claim/quote statuses remain host-owned and review-required.
- Record dataset type/count, contamination controls, exact metrics, reviewer identity/approval where applicable, failure profile, and release/revocation decision. Synthetic tests are not attorney review. Acquire independent reranker artifacts/evidence only if that capability is advertised.

Exit: every advertised slot has real weights, successful inference, a documented license and compatibility chain, and the required independent evaluation. Missing external inputs remain explicit blockers while other safe code work proceeds.

### 6. Reduce package size without disabling advertised safeguards

Current uncompressed groups: Docling models 633,340,089 bytes; spaCy model 445,142,969; PyTorch 378,079,570; Tesseract 249,434,472. These are not compressed-download savings and must not be subtracted from 1.59 GB to claim a finished installer size.

- Inspect `configs/store_feature_tiers.json`, `scripts/build-store-runtime.ps1`, `scripts/build-msix.ps1`, `store/pyinstaller/maine_family_law_llm.spec`, and model resolvers. The existing essential tier excludes some full-intelligence payloads; it is not equivalent to the full edition until missing features are provided and tested.
- Keep application code, required inference engines/DLLs, parsers, and a safe offline baseline in MSIX. Only independently verified data packs move out. Moving weights does not remove the PyTorch dependency; a smaller backend requires a separately measured compatibility change or Store-delivered package strategy, not downloading an unreviewed runtime.
- Deduplicate verified identical OCR assets through one canonical resolver; validate fast/accurate/English/other supported workflows before removal. Measure whether a smaller privacy pipeline meets the same required detection thresholds; do not trade away protection for a size target.
- Model-less startup must stay useful and explain missing capabilities, not pretend they are operational. Store copy must disclose download and hardware requirements; do not claim all AI works offline immediately after MSIX installation when it needs packs first.
- Audit exact archive contents, licenses/notices, dependency inventory, unintended fixtures, no secrets/private data/caches, and compressed/uncompressed size after rebuilding. No promised size reduction before measurement.

Exit: smaller measured candidate with every claimed capability passing after its disclosed setup, no silent runtime installer, and a working offline-import route.

### 7. Run actual production UI and hardware E2E

Identify the frozen application's real UI assets; preserve/test both mirrors as required by packaging. Use isolated, clearly fictional matter data. Do not substitute static HTML, a route unit test, or a development-only server for installed-app evidence.

For each of the seven capabilities: launch -> select/create matter -> choose task -> acquire/import approved pack -> verify admission -> select exact sources -> preview/approve -> real inference -> review-required result -> exact source drill-down -> encrypted/audited receipt -> close/reopen. Add cross-matter refusal, unsupported claim, stale authority, missing record, and revoked release journeys.

Also prove first-run without internet/models, download interrupted/canceled/resumed, generation canceled during load and output, switching adapters, busy queue, wrong model identity, low-memory failure, corrupted cache, removal dependency protection, upgrade/rollback, and restart integrity. Test keyboard/focus, contrast, zoom, visible error/recovery, and no leaked paths/tokens/private text.

Measure actual declared target machines (start with an 8 GB CPU-only PC and a 16 GB PC; GPU only if advertised). Before tuning, set and record numeric release budgets for cold load, warm answer time, adapter switch, cancellation, and peak memory. Collect at least 10 cold starts and 50 warm requests per advertised hardware/runtime profile; publish p50/p95, timeout/OOM counts, model/context sizes, and raw evidence. Declare unsupported hardware honestly. Generated speed claims require measurements, not model parameter counts.

Each result row records level, action, expected/actual result, API route, matter/source/artifact IDs, model/base/adapter hashes, duration, DOM/screenshot evidence, pass/fail/skip, and failure artifact. No private matter data. Mark mock, real model, source UI, frozen runtime, and installed MSIX levels separately.

### 8. Full regression and exact-package qualification

Run focused tests after each coherent repair, then one full release run after final code changes. Do not keep rebuilding the 1.59 GB package to test a source-only change.

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short
git diff --check
python -m compileall -q legal app src maine_family_law_llm scripts tests
node --check src\maine_family_law_llm\ui\workbench.js
node --check maine_family_law_llm\ui\workbench.js
python -m pytest --collect-only -q
python -m pytest --junitxml=dist\ga_today\evidence\fast_interchange_operational_full_junit.xml
```

Add the new focused tests from gates 0-4; never list a proposed test file as passing before it exists. Run duplicate-route/contracts, protected-source/filing adversarial tests (zero false passes on declared set), backup/restore, privacy/secret/package-boundary, accessibility, and Local-only network interception. Preserve commands, environment, counts, durations, all skips, and P0/P1 blockers.

Rebuild through `scripts/build-msix.ps1` into a new candidate directory with unchanged approved Store identity and no unrelated version bump. Reuse the existing offline/durable/exhibit/media scripts with their explicit runtime and package arguments, then add the real FAST INTERCHANGE production-UI journeys. Bind every report to the exact new package hash. A package rebuilt after a fix requires renewed relevant evidence.

Use an approved isolated Windows user/Sandbox/VM/QA strategy for clean install, model setup, all core journeys, shutdown/restart, uninstall/reinstall, and upgrade from an available valid prior package with fictional data. Test offline core use after pack installation and completely disconnected first-run/offline import. Run WACK with the approved elevation path. Do not modify host security policy or uninstall the user's Store package to force a pass. Report unavailable environment/upgrade tests as NOT EXECUTED, not success.

Exit: full suite completed; no P0/P1 defects; exact installed app passes real-model journeys; Local-only proven; package privacy pass; filing adversarial false-pass rate zero; required Store qualification evidence present. Human legal/security/product/operations approval and pilot evidence remain separate Enterprise gates.

## Required output and stop discipline

Use a unique run directory under `dist/ga_today/evidence/fast_interchange_operational/`; do not overwrite historical evidence. Produce baseline, model/pack inventories, source-binding/security results, real-model per-capability matrix, download/offline matrix, hardware metrics, package/install/upgrade/WACK reports, and a SHA-256 artifact manifest. Keep weights, corpora, personal data, secrets, and raw private logs outside repository/package/evidence bundles.

Final decision must report independently: CODE_VERIFIED, REAL_MODEL_OPERATIONAL, INSTALLED_PACKAGE_VERIFIED, STORE_READINESS, ENTERPRISE_READINESS. Each has pass/blocked/not_evaluated plus exact prerequisites; never collapse them into an unsupported blanket certification. Update public pages only after the user's working-and-Store-ready threshold is met, and do not publish/upload automatically.

Next work after the 2026-08-28 signed-worker pass: complete gate 3's acquisition
and recovery lifecycle, including transactional activation recovery, explicit
rollback/removal safety, restart/resume, and native file-picker browser proof.
Live delivery needs a selected approved host and a genuinely admitted artifact;
do not invent either or turn synthetic import success into delivery proof.
Obtain the licensed base/tokenizer, authorized training corpus, seven compatible
adapters, independent evaluations, and operator trust before claiming gate 5.
Then measure actual target hardware and rebuild/qualify the exact package.
The prior preflight and FI-01 source-binding repairs do not need repeating.
