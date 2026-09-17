# Terra execution plan: in-app local AI setup through Store qualification

Date: 2026-09-12
Status: IMPLEMENTATION IN PROGRESS — Slices 01–03 have source-level focused verification; live model, frozen executable, installed MSIX, and release qualification remain required.
Working checkout: D:\dev\Maine-Family-Law-LLM-github-main
Inspected HEAD: 82364d869b4d2d427b93f32b812e857d28cc3e38, with extensive existing changes.
Inspected application version: pyproject.toml declares 8.0.2.
Intended release: v9 from the owner's prior direction; verify current release records before changing any version.
Scope: make local AI installable and useful through the existing Family Law LLM desktop UI.
Do not rebuild ProSe-SENTINEL AI, resume the unrelated 200-feature queue, or import private/proprietary project data.

## Current implementation record — 2026-09-12

The following safe prerequisites are now implemented in this checkout:

- Slice 01: the configured Sentinel route disables ambient proxies and redirects,
  validates response identity/completion/assistant shape, rejects tool output,
  limits fallback to availability failures, and withholds unbound source output.
- Slice 02: `/api/local-ai/setup` has an encrypted, tenant/session-partitioned,
  revision-checked device preference with a hash-chained receipt. The production
  workbench has an accessible local-AI setup panel; provider restoration applies
  one canonical state transition so protected Sentinel placeholders cannot leak.
- Slice 03: the bundled `configs/local_ai_catalog.json` is intentionally empty.
  Its fail-closed catalog API, hardware assessment, and plan endpoint expose no
  installable model until a production-admitted release catalog, resource profile,
  engine/import evidence, license record, and task-quality evidence exist.

Focused source tests, syntax checks, and mirror checks are recorded in
`dist/release/local-ai-setup/evidence/2026-09-12-slices-01-03.json`. This is not
live inference, frozen-app, package, Store, attorney, pilot, or Enterprise evidence.

## 1. Product outcome

A person installs the Family Law LLM, chooses “Set up AI” in chat, sees which model fits
their actual available hardware, sees the total download and disk requirement, and
chooses “Install recommended AI.” The app downloads approved artifacts, verifies them,
configures its runtime, runs a short fictional test, then offers “Use in chat.”

No terminal, environment-variable editor, manually entered endpoint, model tag, source ID,
or separate engineering instructions are part of the default journey. Existing Ollama
users get “Use an existing local installation” in Advanced settings. People can continue
using research, records, OCR, and forms while installation proceeds.

Evidence Review and Drafting appear only for model/task combinations that pass their
specific output and usefulness criteria. A general model may help explain selected
sources without being represented as a trained Maine-law specialist.

The first release must complete ONE qualified model path all the way through the installed
MSIX. Expand the catalog only after that path passes. One suitable installed model is
sufficient; do not force the ProSe 14B-primary/8B-fallback pair onto low-memory PCs.

## 2. What the code review actually found

This is a targeted review of model setup, provider execution, hardware, source binding,
production UI, and build entry points. It is not a full-repository regression certification.

| Surface | Existing code and useful capability | Gap or required decision |
|---|---|---|
| Sentinel transport | legal/agent_runtime/providers.py: SentinelOllamaLocalClient | Environment-only setup; no installer, download, warm/release, cancellation, or verified model inventory |
| HTTP boundary | _BoundedHttpClient, LoopbackEndpointPolicy | Sentinel uses default urlopen: ambient proxy and redirects are not disabled as in FastInterchangeLocalClient |
| Model output | Sentinel _request_model | Unstructured content; null content may become the string “None”; response model/role/completion are not enforced |
| Fallback | Sentinel generate_response | Retries any LocalModelError, including failures that should not retry; no single end-to-end time budget |
| Approval | api.py: _local_agent_binding | Effective primary and endpoint are bound, but fallback, artifact digest, prompt/schema revision, and execution policy are not |
| Hardware | api.py: _local_agent_hardware_readiness | All non-fast-interchange providers, including Sentinel, return not-evaluated with no blockers |
| Hardware implementation | legal/model_orchestration/hardware.py; legal/fast_interchange/hardware.py | Useful RAM/disk/GPU measurements, but the specialist check covers fp32/fp16/bf16 Torch, not quantized Ollama; Nvidia-oriented probing does not qualify every AMD/Intel device |
| Source checks | legal/agent_runtime/runtime.py | Host approval and quarantine exist; unknown/no citation withholding applies specifically to fast_interchange_local, not Sentinel |
| Truthful grounding | LocalAgentRunResult.to_dict; tests/test_local_model_grounding.py | Existing code correctly keeps model claims unverified. Preserve this; do not equate citation presence with claim truth |
| Offline pack manager | app/services/model_pack_service.py; app/api/model_packs.py | Durable import, verification, activation, recovery exist, but operator env setup and active-matter/admin scope are prerequisites |
| Pack format | MAX_PACK_BYTES; _bounded_zip; PackResume | 3 GiB cap, stored ZIP only, no ZIP64. This is not a ready large-Qwen download/install path |
| Warm lifecycle | legal/runtime/warm_model_pool.py | Releasable-worker and memory-pressure patterns exist; Sentinel does not implement the contract |
| Desktop UI | maine_family_law_llm/ui and src/maine_family_law_llm/ui | Provider chooser exists. No ordinary-user setup. Provider restoration does not centralize read-only state; switching away from Sentinel can retain its placeholder model text |
| Packaging | scripts/build-store-runtime.ps1, scripts/build-msix.ps1, scripts/prepare_msix_staging.py | Existing canonical pipeline; managed model-engine distribution and installed setup still need qualification |

The previous 18 focused passing tests were mock transport/API/static UI checks. They did
not demonstrate download/install, live Qwen inference, browser interaction, or MSIX behavior.
Do not reuse that count as proof of the new setup workflow.

### ProSe source review and selective reuse

Read:
- docs/handoffs/PROSE_SENTINEL_FAMILY_LAW_LLM_HANDOFF.md
- src/lib/prose/ai/sentinel/modelProfiles.js
- src/lib/ai/providerRuntimeAdapter.js
- src/lib/prose/ai/familyLawLlmRegistry.js
- src/lib/prose/ai/modelGateway.js
- src/app/api/pro-se/ai/gateway/route.js
- src/components/prose/legalDrafting/ProSeSentinelFamilyLawWorkspace.jsx
- tests/prose/prose-sentinel-family-law-llm.test.mjs

All under D:\dev\ProSe-Split-Editions. No Git metadata resolved there during this review,
and no top-level LICENSE file was returned by the targeted check. The handoff calls the
components PSA-owned; retain the user's explicit integration authorization and record
actual licenses before redistributing copied third-party code.

File SHA-256 anchors:
- handoff: e88c8c2a11ac01b91e77f2904626ee2acdcaf7c68c7a06a91f875ba1225380fb
- providerRuntimeAdapter.js: 399fa6925d50f0b4020802e6345339956bc4e83fb6462664f98e692aab94d097
- modelProfiles.js: 195fb9ee07d6b80c2c4eb4e62151f0ffa43032625e08f2609024f5a46b283e8e

Reuse the conversation-first interaction, explicit unsupported-jurisdiction handling,
server-side provider policy, structured source references, and bounded fallback intent.
Adapt these to the existing Python services and vanilla production UI.

Do not copy these donor weaknesses:
- URL validation allows network destinations suitable for its server context; that does
  not satisfy this desktop app's literal-loopback requirement.
- Missing claims can be manufactured as a response-level “supported” claim.
- Anchor membership alone does not prove claim support.
- The provider gateway branch initially emits grounded=true and empty source-card arrays;
  reconstruct real cards through the Family Law source resolver instead.
- Provider anchor validation occurs after the transport fallback returns; it is not a
  complete per-candidate output-quality fallback gate.
- Its editable draft is component state, without demonstrated durable encrypted revisions.
- No download/hardware wizard is delivered by the handoff. That work must be built here.

## 3. Implementation rules and release architecture

1. Preserve AGENTS.md and all existing changes. Git preflight first; work only here.
   During development use one owned dist/qa/local-ai-setup workspace, one runtime stage,
   existing model artifacts by verified reference, and compact evidence. No drive-root
   scratch directories, external QA clones, repeated model packs, or whole-donor copies.
2. Installed-user data is a separate concern: use a Windows per-user writable app model
   store outside the read-only MSIX installation. Developer fixture stores stay under dist
   through the existing explicit test injection boundary; do not weaken production path checks.
3. Default delivery recommendation: include a pinned portable local engine in the MSIX,
   then download the chosen model data through the app. Avoid a mandatory second installer.
   Prove the portable engine/runtime license, dependency inventory, Windows support,
   package behavior, and offline operation in Slice 04. If it cannot qualify, report the
   concrete blocker; do not quietly replace the first-run experience with command instructions.
4. Reuse an already installed, compatible Ollama only by explicit selection. Its externally
   owned files, service, models, and settings remain outside app removal/control.
5. Use a server-owned catalog and setup service. Browser requests contain opaque catalog,
   plan, and job IDs, not URLs, command lines, environment variables, arbitrary trust keys,
   model paths, or install scripts.
6. Keep download approval separate from sending matter context. Setup sends artifact
   requests only. Local-only inference remains local. Offline mode may show cached catalog
   entries; downloading requires a visible, scoped permission for that operation.
7. Use a single transfer owner. Prefer a host-controlled artifact downloader with approved
   origins and hashes, then a version-tested local runtime import. Do not independently
   download the same blobs through both the host and Ollama pull. Select the exact import
   method after checking the pinned engine API; do not assume newer docs match the binary.
8. Device setup must work before creating a matter. Reuse the current app session/origin
   and identity protections; use a per-user device-configuration scope. Matter content and
   generation remain on the existing matter/tenant/role scoped routes.
9. Environment settings remain an advanced operator override, not the normal setup method.
   Precedence: restrictive operator policy > verified persisted user configuration >
   bundled defaults. Reconcile conflicts visibly; ordinary requests cannot loosen policy.
10. Do not turn an installed model into an admitted legal specialist by toggling a boolean.
    Artifact integrity, technical readiness, task qualification, and human evaluation are
    separately recorded. Signing policy metadata uses an approved release process; no
    locally invented trust key counts as production approval.

## 4. User journey and screen contract

Entry points: chat's AI status chip, Settings > AI & downloads, and an unavailable task's
“Set up AI” action. Open one accessible setup panel with focus return. Chat remains the
default view, Both remains selected, Child Impact Lens remains on, auxiliary cards remain
collapsible. Use existing overlay/navigation helpers.

1. Check this computer: local-only inventory; summary “Recommended,” “May be slow,” or
   “Not enough room right now.” Explain RAM and disk independently; allow Refresh.
2. Choose: recommended card first, one small-model alternative if qualified, larger options
   under “More options.” Each shows exact download bytes, additional installed bytes,
   peak temporary space, supported tasks, expected speed basis, and license details.
3. Install: a single approval presents components and exact storage cost. Button reads
   “Install recommended AI.” A separate optional “Install another model” handles fallback.
4. Progress: named phase, byte progress, pause/cancel, and trustworthy ETA only when measured.
   A canceled download never displays Ready. Explain what is retained and can be removed.
5. Test: verify files, check hardware again, start runtime, generate a fictional response,
   verify expected source behavior, measure timing, and stop/unload if unsuccessful.
6. Use: show “Ready on this computer” for the tested task(s), “Try a sample,” and “Use in
   chat.” Preserve the user's existing message; return to the originating action.
7. Maintenance: storage used, active model/task, release memory, retry/repair, update,
   rollback, and remove selected app-owned model. No hidden accumulation of old versions.

All stages need keyboard operation, labeled controls, visible focus, readable contrast,
aria-live progress without token/byte spam, 200% zoom and narrow-window layout. Download
errors identify the phase, what remains usable, and a direct recovery action. Source
review and model readiness must remain intelligible without reading technical receipts.

## 5. Hardware and recommendation policy

Do not use parameter count, download size, total RAM, or GPU marketing name as a runtime
fit calculation. Record artifact quantization, engine build/backend, context length,
KV-cache allowance, available memory, app/OCR headroom, and observed peak use.

Candidate tiers, not promises of released weights:
- Basic: current deterministic search/forms/OCR and qualified small extraction tools.
  Always available where core app requirements pass.
- Compact generative: evaluate a permissively licensed 0.6B–1.7B quantized candidate.
  Preserve the owner's under-1.5-GB-per-small-model goal as a measured artifact criterion.
  Small size does not confer Evidence Review or Drafting qualification.
- Balanced: evaluate a quantized intermediate candidate only if Compact is inadequate.
- Larger: 8B and 14B from the handoff are optional higher-resource candidates.
  Neither is mandatory, nor automatically downloaded as a fallback.

Use a typed runtime-specific resource profile. Extend hardware assessment for the
Ollama/GGUF backend; do not pretend a q4 model is bf16 to reuse the Torch check.
Never add VRAM across GPUs or add integrated/shared GPU RAM to system RAM as independent
capacity. Distinguish driver visibility from a functioning backend. CPU eligibility
requires actual engine instruction-set support and a measured usable speed.

Initial conservative engineering policy, to calibrate before public claims:
- concurrency=1, one resident model; start short chat at 2K context where the task permits;
- RAM requirement = engine/model measured peak at chosen context + app/OCR reserve +
  safety margin; unknown measurements cannot create a Recommended label;
- disk reservation = remaining download + verification/import duplication actually required
  by the backend + selected installed bytes + rollback retention + safety margin;
- suggested disk margin = max(2 GiB, 10% of additional peak footprint), with a concurrent-job
  reservation so two individually fitting jobs cannot overfill the volume;
- recheck headroom before each install, warm, run, and fallback load;
- stop/reject model load on unavailable memory readings, incompatible runtime, or exhaustion;
- low RAM may suggest closing unused apps, a smaller model, or basic mode; never close the
  user's apps, move files, change system paging, or download drivers automatically.

Recommendations must include measured/estimated/unknown basis and timestamp. Local test
results can refine advice on that PC; never extrapolate one RTX workstation to all PCs.

## 6. Contracts Terra must implement

New names below are PROPOSED files, not claims that they exist.

Catalog entry (configs/local_ai_catalog.json plus signed release metadata):
- schema_version, catalog_revision, profile_id, display_name, backend/runtime_version;
- model upstream/revision, artifact format/quantization, immutable digest and exact bytes;
- approved origin(s), bounded redirect policy, license/notice records, dependency digests;
- task capability list, quality evidence ID, publication status, review policy revision;
- resource profiles by backend/context, token/output limits, optional qualified fallback ID.
Separate engine distribution approval from model distribution approval and task admission.

Public API proposal under /api/local-ai/setup, registered once in app/api/local_ai_setup.py:
- GET /status: installed IDs, safe readiness, active profile, allowed next actions.
- POST /assess: optional selected catalog ID; local hardware inspection only.
- GET /catalog: cached verified catalog, no implicit network refresh.
- POST /catalog/refresh: explicit network operation, if update policy allows.
- POST /plans: catalog ID and storage-selection token -> immutable plan ID, costs, blockers.
- POST /jobs: plan ID + explicit confirmation + idempotency key -> bounded job.
- GET /jobs/{id}: scoped phase, progress, allowed actions; support reconnect.
- POST /jobs/{id}/pause, /resume, /cancel, /discard: revision-checked operations.
- POST /profiles/{id}/test, /activate, /release, /repair, /remove: exact inspected version,
  operation revision and user intent; reject stale or externally owned targets.
- GET /receipts/{id}: content-free installation/test receipt; generation receipts remain
  under their existing matter boundary.
Avoid a generic execute/command/URL proxy endpoint.

Status codes and state transitions must be explicit; do not use a 200 response with
ready=true after any incomplete phase. Proposed state sequence:
not_installed -> assessed -> awaiting_download_approval -> downloading -> verifying ->
installing -> awaiting_local_test -> testing -> ready.
Branches: blocked, failed, paused, canceled, quarantined, update_available, rolling_back.
Activation is an atomic pointer update after verified installation and successful test.
The previous active version remains usable if an update fails.

Bind approved generation to profile ID/revision, engine identity, primary and any eligible
fallback artifact digests, prompt/schema revision, task, source manifest, matter/session,
context/token limits and execution policy. A changed profile invalidates pending approval.
Do not overload model_binding in a way that implies this generic route has a specialist
admission; introduce a separate execution_binding and update lifecycle code explicitly.

## 7. Ordered implementation batches (12 coherent slices)

Every slice below includes a service/API/UI/test path or strengthens the existing path.
Do not create twelve separate frameworks. New modules should stay small and domain-specific.
Finish the acceptance checks for each slice before expanding to more models.

### Slice 01 — repair the existing Sentinel generation boundary

Files: legal/agent_runtime/providers.py, endpoint.py, runtime.py; both api.py mirrors;
tests/test_sentinel_ollama_local_provider.py and test_local_model_grounding.py.
Add strict message/object/string/model/done/finish_reason validation, bounded structured
JSON, unknown/duplicate-key rejection, bounded nesting/arrays, and safe errors. Disable
redirects and ambient proxies. Restrict fallback to explicit availability/timeouts/resource
failures, with one shared deadline, at most one fallback, no repeat of the same model.
Schema/integrity/source/policy failures must withhold, not silently retry.

Use an explicit structured output schema: answer blocks/claims with source IDs and exact
quote spans, unsupported items and review actions. Host reconstructs source cards, checks
exact spans, and separately marks interpretation/support unknown when not proved. Do not
infer supported from an attached ID. Reject tool calls and unauthorized action fields.
Preserve useful deterministic answer when model output is rejected.

UI: safe recoverable failure, actual model/fallback receipt, no false green badge.
Acceptance: fixture model returns null, array, wrong model, incomplete completion, unknown
source, tool call, malicious URL, redirect, oversized body, wrong schema, and missing claims.
Each must produce a controlled error with no private request transmitted remotely.
Mutating fallback configuration between preview/run must invalidate approval.

### Slice 02 — persist local setup and expose truthful status

Proposed app/services/local_ai_setup_service.py, legal/agent_runtime/sentinel_config.py,
app/api/local_ai_setup.py; existing identity, local encryption, durable I/O helpers;
API mirrors and small setup panel in production UI mirrors.

Implement versioned per-user configuration, immutable execution profiles and safe operator
override reconciliation. Configuration contains no matter text. Use atomic writes and
existing protected key provisioning; inspect LocalEnvelopeEncryptor's real key path rather
than assuming its development-default string is the stored production key.

Device setup before a matter must work; generation still requires active matter scope.
Avoid requiring Windows elevation for normal per-user setup. Application role enforcement
must derive from authenticated identity, not trust a browser-supplied admin header.
UI centralizes provider control state on open/change/restore; remove placeholder leakage.
Acceptance: new-user no-env setup, corrupted config recovery, restart, role denial, forged
origin/session, cross-user job access, and unchanged existing advanced provider behavior.

### Slice 03 — verified catalog plus hardware recommendations

Proposed legal/model_orchestration/local_ai_recommendations.py, configs/local_ai_catalog.json;
reuse hardware.py and existing model registry/admission concepts. Add /assess, /catalog,
and /plans with a first working “Check this computer” screen.

Implement resource equations above, disk location token through native picker, unknown
hardware state, engine-specific GPU backend support and conservative context presets.
Release catalog has only distributable entries with actual evidence; unqualified candidates
live in development fixtures and cannot become installable specialist cards.

Acceptance: CPU-only low-memory, unknown telemetry, Nvidia, AMD/Intel unknown backend,
full disk, selected different volume, shared memory, competing download reservations,
and big-model override attempt. Recommendations show reasons and never load a model.

### Slice 04 — deliver and control the local engine

Files: scripts/build-store-runtime.ps1, prepare_msix_staging.py and bundle inventory;
proposed legal/agent_runtime/managed_ollama.py. Reuse Fast Interchange managed-process
ownership/cancellation patterns after targeted review, without importing its LoRA ABI.

Choose/pin the exact standalone Windows engine distribution, verify license, hashes,
runtime libs, offline behavior, allowed Windows versions and architecture. Prefer bundling
that runtime in the MSIX. Launch only the owned executable with fixed arguments, explicit
model/temp directories, hidden window, controlled environment, loopback and bounded health
checks. No shell interpolation, global installation mutation, or automatic update/pull.

Use one owned service/port and verified process ownership. Loopback alone is not
authentication; do not expose engine administrative controls through arbitrary browser
origins. Prove app session/CSRF protection and document the same-user OS threat boundary.
Apply the strongest supported engine origin/network configuration for the pinned version.

UI: engine available/missing/incompatible, test/retry; no console popup.
Acceptance: existing unrelated Ollama, occupied port, malicious executable substitution,
unsupported OS, crash, stale PID, clean shutdown and no outbound request on startup.
Do not kill or reconfigure an externally owned Ollama to make the test pass.

### Slice 05 — real model download, verification and installation

Proposed app/services/local_ai_download_service.py, using durable job/state helpers.
Connect /plans and /jobs to the same setup screen; implement one qualified artifact first.

Use approved HTTPS destinations, request/redirect restrictions, bounded streaming, actual
bytes/hash checks, retry limits, range resume with server validators, disk rechecks and
atomic activation. Partials cannot be loaded. Do not trust tag names or Content-Length alone.
Pin a release digest, quantization, tokenizer/template and runtime compatibility.

Do not force large models through the 3-GiB non-ZIP64 FI importer or simply raise its cap.
Use the backend's content-addressed blob installation path with verified files. Keep the FI
archive path for its established format. Confirm the pinned engine's import API using a
small fixture before acquiring large payloads.

UI: actual progress, download approval, destination and disk estimate, network unavailable
recovery. No matter data, source text or hardware inventory sent to model hosts.
Acceptance: real bounded download from the intended origin, hash mismatch, redirected private
address, interrupted stream, missing lengths, dishonest length, 416/range ignored, expired
catalog, full disk during transfer and concurrent job collision.

### Slice 06 — restart, cancel, repair and storage cleanup

Extend the SAME job service/UI with durable leases, idempotency, pause/reconnect, orphaned
job recovery, removal and previous-version rollback. Capture progress events without
unbounded log retention. Treat cancellation requested and cancellation confirmed separately.

One blob store, one transfer owner, reference counting for shared weights. Never delete an
externally owned installation, shared in-use blob, current/previous protected release, or
matter. Verify paths, junctions, locks and active processes before deletion. Show actual
reclaimed bytes, not the nominal model size.

Acceptance: kill/restart app mid-download/verify/import/activate; restart Windows; cancel
during verification; same job resumed twice; rollback after failure; power-loss-like
pointer recovery; removing one adapter retains a shared base; low disk stays bounded.
No assertion that stopping HTTP polling also stopped the server download.

### Slice 07 — first local test, activation, warm/release and switching

Use managed runtime, existing warm_model_pool patterns and /profiles/{id}/test.
Run a deterministic fictional prompt with fixed source IDs, expected exact quotations and
an absent-source test. Measure activation, first usable result, total duration, RAM/VRAM
peak and backend. This is a device test, not legal-quality evaluation.

Use synthetic warm-up only after opt-in and hardware approval. Keep one model resident,
release on request/pressure/idle, clear context on matter changes. Test fallback under
memory pressure after releasing primary; recheck capacity and share the operation deadline.
No automatic download of a missing fallback. Failed test preserves current active model.

UI: “Testing on this computer,” progress/cancel, truthful failure and a useful basic-mode
action. Enable Ready only after successful verification and local test.
Acceptance: real selected weights, no canned response client, wrong runtime identity,
OOM, process crash, canceled inference, release and repeated matter switches.
Verify model memory is actually released where promised.

### Slice 08 — useful chat, Evidence Review and Drafting

Files: existing family_answer_contract.py, legal/agent_runtime/runtime.py,
legal/fast_interchange/evidence_output.py and drafting_output.py, document workspace
and review/revision services, both production UI mirrors. Reuse existing verifiers;
do not route Sentinel around their decisions.

Default chat gives a fast useful host response while optional model processing is visible.
Any generated draft/interpretation stays provisional until verification. If streaming is
used, stream progress first or clearly provisional content; never make unverified claims
look accepted. Cancel keeps the previous good answer. No stale completion after a switch.

User selects source cards/documents by title, never technical source IDs. Evidence task
compares actual source passages with support/dispute/missing context. Drafting saves an
explicit working copy with encrypted revision/source receipts, unsupported claims and
blockers. Connect header suggestions to selected OCR records and explicit confirmation,
preserving conflicts and existing values. Do not hallucinate form labels or hidden fields.

Acceptance: real fictional mixed records -> select -> ask -> source drill-down -> evidence
comparison -> editable draft -> save/reopen -> diff -> cancel -> restart. Validate active
matter/role, exact span/hash, privacy, quoted text vs finding, and no automatic export/filing.
A task that cannot pass is unavailable with a useful alternative; source-free general chat
can still give generic help without invented law or record facts.

### Slice 09 — model task-quality qualification

Add a pinned task evaluation manifest and separate hidden challenge suite. Reuse suitable
existing compact/ranked/source/verifier tests; do not rewrite the training/eval infrastructure.
Pin weights, base, tokenizer, quantization, runtime, prompt, generation settings and dataset.

Before testing, freeze requirements and contamination checks. Training examples, public
smoke examples and device warm-ups cannot become hidden gold. Use fictional records plus
approved official Maine authority fixtures with freshness metadata. No personal corpus in
this release lane. Separate mechanical source tests from substantive legal-quality review.

Proposed engineering minimum for each advertised Evidence/Drafting capability:
- at least 200 held-out cases per task, including at least 50 adversarial/missing/conflicting
  source cases; hold out scenario families and wording, not just shuffled rows;
- zero accepted fabricated citations/quotes, cross-matter disclosures or external actions;
- at least 95% pass on preregistered supported-task rubric;
- at least 90% task completion on answerable cases so blanket refusal cannot pass;
- report false abstention, attribution errors, qualification loss, latency, and failure rates
  separately with denominators. Higher existing project requirements prevail.
These are proposed release gates, not results or substitutes for human/legal evaluation.

Include false allegations vs findings, stale/wrong-jurisdiction law, missing attachment,
changed orders, prompt/OCR injection, unfamiliar wording, and unsupported requested relief.
No supported label from the model's own confidence. Calibrate quantized artifacts directly.
UI catalog task eligibility follows the signed task evidence. Failed task remains disabled.
Attorney/pilot/enterprise evidence, when required by project policy, remains an explicit
separate blocker; do not manufacture it or silently reduce those policies.

### Slice 10 — whole-journey UX and performance verification

Use actual production desktop assets and canonical API, not an unshipped frontend.
Test no existing runtime, compatible existing runtime, no model, offline, low RAM, full disk,
slow connection, interrupted download, failed test, repair, and first successful use.

Keyboard, screen-reader semantics, contrast, reduced motion, 200% zoom, 1024x768 and
1366x768 desktop windows, dialog focus return and progress announcements.
Check default Both/Child Impact Lens, collapsed panels and chat width after closing setup.

Proposed timing targets, measured on each advertised hardware tier:
- local UI acknowledges an action within 200 ms p95;
- available deterministic host answer within 2 seconds p95 on the fixed small fixture;
- cancellation acknowledges within 500 ms; discarded result never appears afterward;
- owned generation stops/releases within a measured declared upper bound;
- model chat target: first usable result within 15 seconds warm and bounded 60-second
  short-answer completion. If the claimed Recommended tier misses, choose a smaller model,
  narrow advertised workload, or mark it slow; do not hide time behind a spinner.
Model targets depend on workload and must be calibrated, not advertised from mock tests.

Keep one compact fictional screenshot set and DOM/console logs, without private paths/data.
Record p50/p95 and sample counts, cold/warm separately. Hardware simulations do not prove
real-device speed; obtain actual evidence for every public performance claim.

### Slice 11 — frozen executable and installed MSIX qualification

Use canonical scripts with inspected current parameters; do not infer obsolete flags from
old commands. Freeze versions only after full required regression passes. Keep Store
identity, publisher, architecture, executable and approved capabilities consistent.

Prove the exact frozen exe loads the changed UI and new modules. In an isolated approved
Windows account/Sandbox/VM, clean-install the exact package and perform setup -> download ->
test -> chat/evidence/draft -> offline restart -> repair -> uninstall/reinstall.
Leave the user's real Store install untouched.

The package must not require Python, Node, pip, an environment editor, or developer paths.
Use writable per-user model state and verify package identity/virtualization behavior.
Verify both online download consent and offline core/inference, including all child
processes, provider discovery, update and telemetry behavior.

Audit exact package for private records, credentials, data/index/eval stores, development
tools, source exports (including untracked ZIPs), caches and debug logs. Include required
engine/model notices. Run dependency/license/binary inventory, WACK when available/required,
migration, rollback, and state survival. Microsoft Store signing is separate from model
catalog/admission signing. Do not generate a production certificate or publish automatically.

### Slice 12 — release decision and user-facing handoff

Generate accepted capabilities from current evidence, exact package digest, device/quality
qualification, hidden tasks, known limitations and reproducible run commands.
Create accurate release notes/What's New and current fictional Store screenshots only
after the exact package is qualified.

Decisions: SETUP_GA_READY or BLOCKED; STORE_GA_READY/BLOCKED/NOT_EVALUATED; and
ENTERPRISE_GA_READY/BLOCKED/NOT_EVALUATED independently. Ready requires full required tests,
real first-run installation, actual selected-model tasks, offline/cancellation/restart,
package privacy and no P0/P1 defect. No route-only or synthetic model certification.
Do not mark all specialists ready when only one task/model is qualified.
GitHub publishing, Store submission and uploads are a separate explicit release action.

## 8. Test and evidence execution contract

Each implemented slice adds compact evidence under dist/release/local-ai-setup/evidence:
slice ID, source revision plus dirty file hashes, command, runtime/backend, artifact digest,
dataset type/hash/count, duration, exact pass/fail/skip counts and reasons, captured user
action/API/result, blockers, repairs, and evidence-file hashes. Report not-run levels.

Use existing tests where meaningful:
- tests/test_sentinel_ollama_local_provider.py
- tests/test_v540_local_agent_http_adapters.py
- tests/test_v540_local_agent_api_ui.py
- tests/test_fast_interchange_host_source_binding.py
- tests/test_fast_interchange_hardware_readiness.py
- tests/test_fast_interchange_model_packs.py
- tests/test_model_pack_readiness.py
- tests/test_local_model_grounding.py
- tests/test_evidence_review_output_boundary.py
- tests/test_drafting_output_boundary.py
- tests/test_local_form_header_suggestions.py
- tests/test_model_pack_browser_real.py
- tests/test_v604_store_runtime_inventory.py

Proposed additions: tests/test_local_ai_setup_api.py, test_local_ai_catalog.py,
test_local_ai_recommendations.py, test_local_ai_download_recovery.py,
test_local_ai_managed_runtime.py, test_local_ai_setup_browser.py.
These must assert outcomes and attacks, not just the presence of a button/string.

Baseline commands (resolve the existing interpreter; do not recreate a build environment):
git rev-parse --show-toplevel
git status --short
git diff --check
dist\build-env\store\Scripts\python.exe -m compileall -q legal app maine_family_law_llm src
node --check maine_family_law_llm\ui\workbench.js
node --check src\maine_family_law_llm\ui\workbench.js
dist\build-env\store\Scripts\python.exe -m pytest --collect-only
dist\build-env\store\Scripts\python.exe -m pytest <focused-test-files> --basetemp dist\qa\local-ai-setup

Before reuse of basetemp, verify it belongs to this run and no active process uses it;
pytest can replace its contents. Use one owned fixture workspace and preserve compact
evidence outside that scratch tree. After integration run the full release-relevant suite,
then frozen and installed journeys. Enumerate skips and release impact, never suppress.

Provenance record: docs/SENTINEL_INTEGRATION_PROVENANCE.json (proposed).
Track exact donor input hashes, what behavior was adapted, local output files, licenses,
and excluded donor areas. Copy no uploads, data, private records or entire report trees.

Final evidence files (proposed):
- catalog-and-licenses.json
- hardware-and-recommendations.json
- download-install-recovery.json
- runtime-offline-network.json
- model-task-quality.json
- production-ui-journeys.json
- frozen-and-installed-package.json
- release-decision.json
- artifact-manifest.json

## 9. Release blockers to resolve, not gloss over

- Current UI has no download/install path; environment configuration is insufficient.
- Sentinel transport/output/fallback/approval weaknesses listed above.
- No runtime-specific Sentinel hardware qualification through the canonical API.
- No pinned public release catalog, distribution rights records and artifact/task receipts
  established by this review.
- No demonstrated complete first-use path with an actual chosen model on a low-end PC.
- No evidence here that both requested specialist tasks meet quality thresholds.
- No installed MSIX proof of this new setup flow or its network/process boundary.
- Exact model distribution hosting/import mechanism and pinned portable engine must be
  qualified before enabling Install.
- Operator/trust provisioning must be delivered by the release process; normal users should
  never be asked to mint keys or edit manifests.
- Human, legal, operational or pilot gates remain only where required by existing policy,
  accurately listed separately from engineering test completion.

## 10. Authoritative references checked during planning

These inform architecture, not claims that integration has passed. Recheck against the
exact pinned version during implementation; APIs and packaging details can change.

- Ollama Windows: https://docs.ollama.com/windows
  Describes native Windows deployment and a standalone distribution suitable for embedding.
  Account for engine dependencies and disk footprint; installation is not just model bytes.
- Ollama chat API: https://docs.ollama.com/api/chat
  Documents structured format, completion fields, thinking controls, and keep_alive.
  Use these as contracts and test the selected runtime version.
- Ollama create API: https://docs.ollama.com/api/create
  Confirms model creation/configuration exists; this review does not establish the exact
  local-file/blob import contract. Verify that against pinned API before large transfers.
- Ollama FAQ: https://docs.ollama.com/faq
  Review supported local network, model storage and runtime controls for the chosen build.
- Qwen3-0.6B upstream card: https://huggingface.co/Qwen/Qwen3-0.6B
  Marks the base Apache-2.0. Separately verify each quantized derivative, adapter, tokenizer,
  training input, and redistribution notice; permissive licensing is not legal-task quality.
- Microsoft packaged desktop execution:
  https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes
  Validate installed writable paths and packaging behavior on the actual candidate.

## 11. Ready-to-run Terra instruction

Read this plan and AGENTS.md. Confirm the existing worktree and preserve every current
change. Start Slice 01, then implement Slices 02–12 in order, with each usable vertical
tested before expansion. Use the existing Python app, canonical APIs and production UI
mirrors; adapt the explicitly supplied ProSe contract without rebuilding ProSe-SENTINEL AI.
Prioritize one qualified compact model through in-app setup, actual use and installed
MSIX before adding the optional larger models. Keep development files inside this repo,
reuse verified model blobs, and record exact tests and blockers. Do not call a downloaded,
loadable or source-citing model a qualified specialist without the task evidence.
