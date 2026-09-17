# NH Family Law LLM: direct-copy 4B / 8B integration handoff

Prepared 2026-09-17. This is an implementation instruction for the NH project,
not a claim that NH integration, NH legal quality or Store qualification has
already passed.

## Mission — copy the working implementation, then adapt the jurisdiction

COPY DIRECTLY the existing local Qwen 4B/8B implementation from:

`D:\dev\Maine-Family-Law-LLM-github-main`

Integrate it into the NH Family Law LLM's CURRENT verified checkout. Do not
rebuild it from prose, create a replacement AI framework, or reconstruct
ProSe-SENTINEL. Preserve the donor's working transport, exact-context approval,
source-bound outputs, encryption, audit, hardware checks and production UI.
Adapt only the necessary NH host interfaces, authority adapters, storage
namespaces, citations, configuration, branding and tests.

The donor is a DIRTY WORKING TREE. Its HEAD at handoff is
`82364d869b4d2d427b93f32b812e857d28cc3e38`; that commit alone does NOT contain
all the implementation. Copy the on-disk files. Check their hashes against the
adjacent `NH_4B_8B_DONOR_FILES.json` before copying. A mismatch means inspect
and record donor drift, not reset either repository.

Work only in the NH checkout when executing this handoff. The NH destination
has not been inspected or selected by this handoff; verify it with Git before
writing. Do not guess a destination path. Read its AGENTS.md. Preserve all
existing changes. No reset, clean, stash, unrelated rewrite, push, upload or
publication. Keep scratch, QA profiles and build files in its own `dist`.
Measure free space first; use one bounded workspace. Do not copy model stores,
private corpora or multiple frozen runtimes. Do not modify the Maine donor.

## What is actually being transferred

- Provider: `curated_ollama_reasoning`.
- Exact supported model tags: `qwen3:4b`, `qwen3:8b`.
- Tasks proven for this handoff: `evidence_review`, `drafting`.
- This is general-purpose Qwen integration, NOT trained NH/Maine legal weights.
- Both tasks select original private-record quotations. The host verifies the
  returned quotation against the approved source and renders the original text.
  Drafting produces attributed working material, not unrestricted legal prose.
- Relevance, completeness, factual truth and legal conclusions are NOT verified
  by a successful quote match. Keep these limits visible.
- Ollama and weights are separately installed. No weights are in the Maine
  MSIX or this handoff. Do not copy unrelated proprietary Mainely Code,
  Northstar or MC_models material.
- The 9.0.1 in-chat setup checks hardware, disk space and existing components,
  requests explicit consent, installs only missing Ollama/model components,
  and verifies a fictional quotation through the actual review provider.
  Existing installations/models are reused, not replaced. The separate legal
  specialist admission catalog remains empty/unconfigured.
- The separate SENTINEL gateway and FAST INTERCHANGE LoRA worker are not this
  route. Do not make this integration depend on either one being operational.

Known donor proof: four real frozen-runtime model/task combinations passed,
8.684–10.474 seconds on the donor machine. Final-build UI directly exercised
4B drafting and 8B evidence review; all four combinations were also exercised
through the same model code before the last layout-only update. These are
fictional, bounded functional tests, not legal-quality or low-end-PC certification.
The full donor regression had 3,923 tests: 3,817 passed, 62 failed and 44 skipped;
all 62 failures subsequently have separate passing follow-ups. Do not call
this a single clean full-suite run. Do not inherit its pass result for NH.

Current donor package target: `dist/release/v9.0.1/msix/MaineFamilyLawLLM_9.0.1.0_x64.msix`.
Use the exact package hash and final evidence in
`dist/release/v9.0.1/RELEASE_VERIFICATION.json`, not a hash from an earlier build.
Installed-MSIX qualification, clean-machine installation, WACK, legal-quality
and Enterprise certification must not be inferred from functional reuse tests.

## 1. Copy inventory and integration rules

Paths below are relative to the donor. Preserve notices/licenses and record
source path, donor SHA-256, NH destination, copy/merge action, adaptation and
destination SHA-256. Copy whole small modules; transplant named blocks from
large host files. Do not overwrite NH's complete API, UI or package identity.

### A. Copy the reusable runtime directly

Copy the complete `legal/agent_runtime/` package:

- `__init__.py`, `contracts.py`, `endpoint.py`, `providers.py`, `runtime.py`,
  `qwen_review.py`, `tools.py`.
- Preserve the complete `CuratedOllamaReasoningClient`, its typed
  `QwenEvidenceResponse`, and the `build_local_client` dispatch branch.
- Preserve `LocalAgentRuntime`, `_specialist_contract`, `_build_prompt`,
  output validation/rendering and `LocalAgentRunResult.to_dict()` safeguards.

Copy these directly, reconciling compatible existing NH versions:

- `app/services/local_agent_context_service.py`
- `app/services/local_agent_run_service.py`
- `legal/fast_interchange/specialists.py`
- `legal/fast_interchange/evidence_output.py`
- `legal/fast_interchange/drafting_output.py`
- `legal/model_orchestration/hardware.py`
- `legal/local_ai/__init__.py`, `setup.py`, `catalog.py`, `installer.py`
- `app/api/local_ai_setup.py`
- `configs/local_ai_catalog.json` (retain empty catalog until real admission).

The copied modules are NOT standalone. Resolve their full import closure in NH,
including package initializers and imports inside methods. Reuse identical NH
dependencies; copy missing donor dependencies with provenance. Do not satisfy
missing imports using stubs, mocked production modules or disabled verification.
Mandatory integration dependencies include:

- `legal/security/`: protected_spans, prompt_injection, injection_defense,
  local_request_firewall, local_api_abuse_guard, local_encryption, durable_io,
  strict_json, and their actual transitive imports.
- `app/api/security.py`: role/session/origin/audit/review-response contracts.
- `legal/verifiers/citation_parser.py`: jurisdiction-sensitive; see section 4.
- `app/services/authority_product_service.py`: adapt to NH's admitted authority
  service; NEVER silently retain the Maine store as the NH authority provider.
- Existing record-token resolution, matter selection, vault-key resolution,
  request limits, exception shaping and endpoint registration in the NH host.
- Other specialist/compact modules imported by the copied runtime: preserve
  already present compatible modules. Inventory optional imports explicitly;
  unsupported modes must remain unavailable, not silently claimed as working.

The file hash inventory lists transfer entry points, not a claim that its list
alone is the complete transitive dependency closure. Produce a resolved import
inventory and smoke-import the final frozen build as well as source Python.

### B. Transplant the canonical API blocks, not the entire application

Donor canonical implementation is `src/maine_family_law_llm/api.py` with a
matching `maine_family_law_llm/api.py` mirror. Locate by symbol, not line number:

- `LocalAgentPreviewRequest`, `LocalAgentExecuteRequest`, `LocalAgentCancelRequest`
- `_local_agent_record_source`, `_local_agent_context_service`, `_local_agent_scope`
- `_local_agent_audit_store`, `_local_agent_binding`
- `_local_agent_runtime_from_request`, `_local_agent_hardware_readiness`
- `/api/local-agent/status`, `/api/local-agent/preview`, `/api/local-agent/run`
- Cancellation/run-state integration where applicable. Qwen window close is
  NOT engine cancellation; preserve the honest label and bounded timeout.
- Router registration for `app.api.local_ai_setup` under `/api`.

Wire the copied blocks to NH's real authenticated local API, active matter,
record token loader and encrypted audit. Bind BOTH the requested route and
effective provider/endpoint/model in the approval, plus task, tenant, session,
matter and source/context hashes. Rehydrate sources server-side at execution.
Browser-supplied excerpt text, paths and model-supplied references are not trusted.
Preserve expiry/replay/run-state handling. Detect duplicate method/path pairs
and aliases which bypass guards. Do not expose specialist worker management
buttons merely because unrelated worker routes exist in the donor.

Device setup routes to integrate with the same protections:

```text
GET  /api/local-ai/setup/status
POST /api/local-ai/setup/basic-mode
GET  /api/local-ai/setup/catalog
POST /api/local-ai/setup/assess
POST /api/local-ai/setup/plans
POST /api/local-ai/installation/prepare
POST /api/local-ai/installation/start
GET  /api/local-ai/installation/jobs/{job_id}
POST /api/local-ai/installation/jobs/{job_id}/cancel
```

### C. Copy the actual production UI sections and styles

Donor: `src/maine_family_law_llm/ui/workbench.{html,js,css}` plus matching root
package mirrors. First establish which NH assets its frozen executable loads.
Do NOT substitute `app/web` or an unshipped development frontend as evidence.

Transplant complete connected blocks and dependencies:

- `local-agent-modal` markup, provider/model/task controls, exact source list,
  hardware result, explicit approval, loading, failure and recovery states.
- `applyLocalAgentProviderState`, `refreshLocalAgentPreview`,
  `openLocalAgentDialog`, `runApprovedLocalAgent`, `closeLocalAgentDialog`,
  `cancelLocalAgentGeneration`, `renderLocalAgentReceipt`, `setLocalAgentBusy`.
- Evidence Review / Draft from records actions on real answer source cards;
  exact-source inspector links and source-check details on the resulting output.
- `local-ai-chat-setup`, `startLocalAiConversationSetup`,
  `renderLocalAiConversationSetup`, `checkLocalAiConversation`,
  `bindLocalAiConversationActions`, `isLocalAiSetupQuestion`, and the associated
  event registration, fetch/security helpers and styles.
- `prepareLocalAiInstall`, `pollLocalAiInstall`, `localAiInstallPolls`, and the
  model-choice/progress controls. Every JSON POST must declare Content-Type:
  application/json; preserve the browser regression for this requirement.
- Settings counterparts `renderLocalAiSetup`, `loadLocalAiSetup`,
  `chooseLocalAiBasicMode`, `showLocalAiProfileAssessment` where NH ships them.
- Trace any setup-intent/backend answer-contract dependency in
  `family_answer_contract.py` and the canonical `/ask` route; copy only the
  connected setup behavior, not Maine's entire legal answer templates.
- `recentWorkNotice` fix: native collapsed details inside `.chat-scroll`, not
  a fourth chat-grid row. Preserve keyboard access and focus return.

Keep model-specific approval invalidation. Display quoted-text checks separately
from unverified facts/law. Avoid a green "verified" badge for unchecked claims.
Adapt user-visible Maine labels to NH; retain the Child Impact Lens and combined
source default if consistent with NH's existing UX. Plain-language model choices
should remain reachable in chat without technical configuration knowledge.

## 2. Preserve these transport and output invariants exactly

1. Allowlist only the exact two Qwen tags; do not broaden to arbitrary model names.
2. Literal loopback only, fixed curated endpoint, no proxy, redirects, remote
   fallback, provider discovery, implicit download or startup network activity.
3. Preserve the raw Qwen non-thinking prompt envelope. Older installed templates
   ignored `think:false`; the explicit empty thinking block fixed the donor run.
4. Preserve request limits: 5,000 UTF-8 prompt bytes, 8,192 context tokens,
   2,048 output-token limit, temperature zero; reject rather than silently truncate.
5. Require correct response model, `done:true`, `done_reason:stop`, valid bounded
   response JSON, no tool calls, no unfinished thinking/control tokens.
6. Evidence/drafting require the typed excerpts response. Match each quote to
   its approved indexed source, verify offsets/hashes and privacy boundaries,
   then render host-owned text. Do not display the discarded generated narrative.
7. Preserve source coverage/protected-span checks and per-span bounds. A source
   reference or a regex match alone never proves factual/legal support.
8. Retain `keep_alive:0` so idle 4B residency does not block 8B headroom. No cross-
   matter chat/KV history is supplied by this request path.
9. Preserve visible review-required status, provenance receipts and filing gates.
   A model cannot grant itself permission to file, sign, serve or execute tools.

## 3. Hardware and installation boundaries

Copy the actual readiness algorithm, not just its friendly text. Current donor
thresholds are 4B: 6 GiB available RAM OR 4 GiB available VRAM; 8B: 10 GiB
available RAM OR 5.5 GiB available VRAM. GPU use additionally needs at least
2 GiB available system RAM. Check live availability again before the request;
unknown hardware must not imply a pass. These are execution gates, not a claim
that all PCs at the threshold run quickly. Measure NH performance independently.

Use existing installed Ollama models for initial QA after checking their IDs.
Donor observed digest prefixes: 4B `359d7dd4bcda`, 8B `500a1f067a9f`.
Record full local digests, engine version and hardware in NH evidence. A tag
match is not authenticated weight admission. Confirm exact model licenses and
redistribution terms before any acquisition, modification or bundling.

Copy the implemented setup path directly; do not replace it with download links
or shell instructions for end users:

1. Copy `legal/local_ai/installer.py`, keeping the fixed model allowlist, full
   registry-manifest hashes and official Ollama installer URL/size/SHA-256.
   Validate any future pin update against official sources. Keep the publisher
   check and the OS-bundled PowerShell module path fix.
2. Copy canonical `/api/local-ai/installation/prepare`, `/start`,
   `/jobs/{job_id}` and `/jobs/{job_id}/cancel` routes. Keep the tenant/session,
   role, origin, review-response and audit guard. No generic URL/shell endpoint.
3. Copy production UI `prepareLocalAiInstall`, `pollLocalAiInstall`, the model
   choice buttons and `bindLocalAiConversationActions` wiring. Show component
   inventory, download/space estimate, consent, progress, safe stop/retry and
   Use in chat. Do not make ordinary startup download or probe an engine.
4. Preserve single-use expiring plans, serialized jobs, encrypted progress and
   hashed event history. Cross-session/tenant access must fail. After restart,
   interrupted jobs must explain recovery; completed components are reused.
5. Preserve skip logic independently for engine, 4B and 8B. A stopped signed
   engine is started, not reinstalled. Matching model manifests skip pulls;
   differing revisions fail closed rather than overwrite existing models.
6. Check install-cache, engine and model volumes independently. Allow only
   approved HTTPS installer redirects; verify size/hash and Authenticode before
   executing. Keep private records entirely out of setup traffic.
7. Keep the real provider's fictional exact-quotation smoke. A successful
   HTTP request alone is not readiness. The smoke is not legal evaluation.
8. Preserve the separate specialist catalog and admission boundaries. Installing
   general Qwen does not admit an NH-law specialist or verify legal correctness.
9. In NH, test engine missing/present/stopped; model missing/present/partial;
   wrong hash/publisher; low disk/RAM; consent replay; session mismatch;
   cancellation; offline failure/retry; both model tasks through frozen UI.
   Mocked cold-install coverage is not a real clean-Windows installation pass.

Maine's live reuse drill exercised both installed models without downloads.
Re-run it in NH and independently qualify a clean Windows installation. Do not
copy donor evidence as NH's own result or claim the handoff certifies installation.

## 4. Adapt NH authority — do not rename Maine law into NH law

The evidence/drafting path above uses PRIVATE RECORDS and deliberately remains
usable when no authority collection exists. Preserve that lazy initialization.
Do not disable private-record review just because NH authority is unavailable.

For the NH authority/research lane:

1. Identify NH's actual accepted authority manifest, trust policy, external root,
   parser store, indexes, citation resolver, exact-source preview and form catalog.
   Verify official sources and current metadata during implementation. This
   handoff supplies no legal interpretation or pre-approved NH authority bundle.
2. Inject/adapt NH's authority product service into `LocalAgentContextService`.
   Keep admitted-build verification, unique source IDs, hash/snapshot lineage,
   exact span rehydration, freshness and fail-closed error handling.
3. Use a separate NH authority namespace and trust roots. Do NOT copy Maine
   authority stores, indexes, signed manifests, evaluation approvals or private
   records; do not just change a manifest's jurisdiction string to NH.
4. Map real NH statutes, court rules, appellate opinions and court forms into
   NH's existing source-class policy. Preserve official-source priority. Set
   applicability per source; federal/interstate authority must remain explicitly
   classified rather than silently labeled NH state law.
5. Audit `qwen_review.py`'s `_LEGAL` regex and
   `legal/verifiers/citation_parser.py`: the donor recognizes Maine citations.
   Add an explicit NH parser/adapter with tested NH formats from official fixtures.
   Prefer NH's canonical exact resolver to duplicating heuristics. Keep Maine
   examples as negative/wrong-jurisdiction tests, never relabel them as NH law.
6. Search copied code/config/UI for Maine, M.R.S., M.R.Civ.P., Law Court, Maine
   URLs, court/form IDs and jurisdiction defaults. Classify each occurrence as
   display text, executable jurisdiction logic, legacy schema compatibility,
   provenance notice or negative fixture. No global search-and-replace.
7. Separate NH app-data directories, vault/key scope, approvals, audit audience,
   environment settings and browser state from Maine. A copied placeholder
   development-key label is NOT an encryption key: preserve the OS-protected
   random vault-key resolver. Prove the two editions cannot share private state
   or reuse each other's approval tokens.
8. Keep stale, unknown, unadmitted and wrong-jurisdiction authority from supporting
   unqualified "current NH law" wording. Citation existence is not claim support.
9. Preserve three separate lanes: admitted official authority, private evidence,
   and model analysis. A private record quoting a statute does not become authority.
10. If NH authority is not ready, mark NH legal research unavailable with a useful
    recovery action; release no claim that NH authority verification has passed.

Do not change the private-record-only quote verifier to accept authority just
to make a mixed-source test pass. Connecting NH legal citations to prose drafting
is a separate output-contract change requiring new acceptance tests.

## 5. Efficient ordered implementation batches

Complete each batch before moving forward; do not recreate the donor's backlog.

1. **Inventory and copy:** Git identities, donor hashes, destination map, import
   closure, actual frozen UI mapping. Copy modules and integrate NH host seams.
2. **Protection and transport:** compile/import; loopback, request bounds, approval,
   matter/tenant/session isolation, audit/vault persistence and negative tests.
3. **Record review vertical:** fictional NH matter -> search -> exact approval ->
   real 4B/8B -> checked original quotations -> source inspector -> audit receipt.
4. **Drafting vertical:** same records -> each model -> source-attributed working
   draft -> save/reopen -> visible limitations/blockers. Never promote allegations.
5. **NH authority vertical:** accepted NH build -> retrieval -> exact citation/span
   -> source card -> freshness and jurisdiction decisions -> source drill-down.
6. **UX/hardware:** in-chat setup, low-memory failures, absent engine/model,
   model switching, errors, keyboard/focus, small viewport and restart.
7. **Frozen/package proof:** canonical NH build, final frozen real-model tests,
   payload privacy/license audit, exact artifact hashes, isolated installation
   and offline proof where available. Preserve NH Store identity/version policy.

Do not copy Maine's Appx identity, publisher, version freeze, GA decision,
application version files or release manifests into NH. Build a new NH package;
do not rebrand/repackage the existing Maine MSIX.

## 6. Copy and adapt the regression tests

Start with these actual donor files, preserving negative assertions:

```text
tests/test_qwen_review_hardening.py
tests/test_curated_qwen_api_real.py
tests/test_v540_local_agent_http_adapters.py
tests/test_v540_local_agent_runtime.py
tests/test_v540_local_agent_api_ui.py
tests/test_fast_interchange_host_source_binding.py
tests/test_local_model_grounding.py
tests/test_local_ai_setup.py
tests/test_local_ai_installer.py
tests/test_evidence_review_output_boundary.py
tests/test_fast_interchange_specialist_tasks.py
tests/test_matter_vault_encryption.py
tests/test_pass114_recent_work_continuity_acceptance.py
tests/test_v500_responsive_ux_hardening.py
tests/test_v800_control_strip_layout.py
scripts/verify_qwen_frozen_workflow.py
scripts/verify_local_ai_setup_reuse.py
```

Adapt package imports/paths, expected NH labels, storage namespaces and authority
fixtures, NOT protective assertions. Copy the tests' actual fixture dependencies.
The live tests are opt-in: set `MFL_RUN_REAL_LOCAL_QWEN=1` and
`MFL_QWEN_EVIDENCE_DIR` to NH's repository-local evidence directory (or deliberately
rename these settings and their consumers together). A skipped live test is not
proof. Set TEMP/TMP and pytest `--basetemp` inside the NH checkout.

Required cases:

- 4B and 8B, BOTH evidence and drafting, through actual shipped UI and canonical
  API. Record model digest, exact source IDs/hashes, request/result, duration,
  screenshot/DOM, receipt and frozen/package identity.
- Missing attachment; requested receipt missing; conflicting proposed times
  without acceptance; allegation vs finding; duplicate vs corroboration;
  uncertain clock/date; source instructions/tool injection; sensitive identifiers.
- Reject unknown source, altered quotation, omitted selected record, invalid
  index, wrong model, incomplete/length-limited response, malformed JSON, tool
  call, reserved prompt token, oversized UTF-8 input and verifier exception.
- Preview then alter model/endpoint/task/matter/session/source; execution must
  fail pending fresh approval. Verify cross-tenant/matter access is rejected.
- Audit tamper, missing audit key, protected plaintext leakage, raw private paths,
  unsafe rendered HTML, restart and source hash changed after preview.
- NH valid citation, fake citation, pinpoint, exact/mismatched quote, stale form,
  unknown freshness, duplicate source ID, wrong-jurisdiction Maine authority.
  Mark fixture-only results distinctly from live official-authority evidence.
- Engine stopped/model missing/insufficient RAM or VRAM: helpful error, originals
  unchanged, normal source-backed chat still available. Never silently downgrade
  to an arbitrary remote model. Explain Qwen's close-vs-cancel limitation honestly.
- Local-only startup/hardware assessment makes no discovery/download/provider
  request; approved inference contacts only the selected loopback runtime.

Run NH's full suite after focused tests. Keep original failures/skips and reasons;
record follow-ups separately. Test final frozen assets, not just a dev server.
Use the adapted frozen harness with `--runtime <NH executable> --output <NH
repo>/dist/qa/nh-qwen/frozen`; use `--serve` only for UI inspection and stop the
owned process afterward. No real family data in fixtures or screenshots.

## 7. Evidence and completion contract

Create inside NH, without copying donor PASS labels:

```text
docs/NH_4B_8B_INTEGRATION.md
dist/qa/nh-qwen/copy-provenance.json
dist/qa/nh-qwen/dependency-closure.json
dist/qa/nh-qwen/nh-authority-adaptation.json
dist/qa/nh-qwen/functional-matrix.json
dist/qa/nh-qwen/security-and-hardware.json
dist/qa/nh-qwen/frozen-verification.json
dist/qa/nh-qwen/release-decision.json
```

Statuses must distinguish source tests, real inference, production UI, frozen
executable, installed package, NH authority evidence and legal-output quality.
Only mark the specific verified feature usable with its actual limitations.
Record unsupported modes as unavailable. Report exact outstanding blockers;
never transfer Maine's results as NH certification.

Deliver the integrated code, provenance and test matrix, concise What's New,
and NH MSIX ONLY after its own build/verification gates allow it. If external
evidence is absent, finish all safe implementation and report the precise gap.
No fabricated attorney, pilot, Store, unrestricted-drafting or legal-quality claims.

## Donor evidence for reference, not transferable certification

- `dist/release/v9.0.0/RELEASE_VERIFICATION.json` and `.md`
- `dist/release/v9.0.1/RELEASE_VERIFICATION.json`
- `dist/qa/v901-setup/live-reuse.json`
- `dist/qa/v901-setup/regression-final.xml`
- `dist/release/v9.0.0/release-scope.json`
- `dist/release/v9.0.0/evidence/final-runtime-binding.json`
- `dist/qa/v9-qwen/frozen/frozen-qwen.json`
- `dist/qa/v9-qwen/media/browser-verification.json`
- `docs/RELEASE_NOTES_v9.0.0.md`

Important regression to preserve: earlier free-form 4B drafting changed a missing
requested receipt into a claim that no receipt had been requested. The current
quotation-only boundary was added because of that observed failure. Do not remove
it for fluency or describe the limited fix as unrestricted drafting quality.
