# FAST INTERCHANGE execution plan

## Decision and scope

Maine Family Law LLM will gain an optional, local-only FAST INTERCHANGE lane for a small shared base model with one active LoRA adapter at a time. The intended seven capabilities are:

1. `intake_triage`
2. `evidence_review`
3. `authority_review`
4. `drafting`
5. `parenting_plan_review`
6. `financial_disclosure_review`
7. `safety_privacy_review`

The lane is a local inference feature, not a legal-certification system. It must never make a filing-ready decision, determine custody, infer a factual finding, decide that a source is current law, or bypass the application's existing source, claim, quote, filing, privacy, and human-review controls.

There are no approved base weights, legal corpus, trained adapters, artifact registry, model release, or legal-quality benchmark in the repository today. The first implementation milestone is therefore a complete **model-empty runtime**, not an imagined trained fleet.

Implementation update, 2026-08-28: server-rehydrated source/approval binding,
independent signed admission, exhaustive immutable loader snapshots, capability
routing, owned-subprocess cancellation/restart, and production-source UI
recovery now have implementation and local tests. A bounded offline signed-pack
import/inspection/separate-activation path is also implemented. See the
[signed-worker verification report](FAST_INTERCHANGE_SIGNED_WORKER_VERIFICATION.md)
for exact evidence levels and open defects. This is still **partial operational
completion**: live distribution and full pack lifecycle, the native file-picker
journey, real admitted legal artifacts/evaluation, modest-hardware measurements,
and exact frozen/installed-package qualification remain unproven. The original
[ordered Terra handoff](FAST_INTERCHANGE_TERRA_HANDOFF.md) is a scope reference,
not an instruction to repeat repairs already documented in the newer report.

Recovery follow-up, 2026-08-28: offline import restart/resume, journaled
activation recovery, current-trust version reactivation, and recoverable
remove/restore are implemented. The production-source browser now proves the
native file-picker-to-activation path with a fictional structural pack, plus
cross-session resume and accessible explicit consent. See
[pack recovery verification](FAST_INTERCHANGE_PACK_RECOVERY_VERIFICATION.md)
and its final regression evidence. The earlier native-picker limitation is
superseded for this connection; real legal artifacts, distribution, target
hardware, human evaluation, and exact frozen/installed qualification remain
separate, unmet gates. Do not promote the old MSIX using new source evidence.

## Non-negotiable boundaries

Latest release-continuation evidence:
[authority audit and compound-claim release continuation](AUTHORITY_CLAIM_RELEASE_CONTINUATION_20260828.md).
This supersedes the prior engineering candidate for the changed verifier and
filing gate; consult its current evidence before using any MSIX. Earlier
[frozen PDF preview verification](PDF_PREVIEW_RELEASE_CONTINUATION_20260828.md)
and [OCR/runtime repairs](FAST_INTERCHANGE_RELEASE_CONTINUATION_20260828.md)
remain historical evidence. Real legal models, native/installed qualification,
and authority/human gates are still blocked; this is not GA certification.

Current implementation/evidence supplement:
[signed admission and worker lifecycle verification](FAST_INTERCHANGE_SIGNED_WORKER_VERIFICATION.md).
The older audit defects listed above are historical; the supplement identifies
the repaired source paths and remaining operational gates without promoting
unavailable legal weights or unqualified packages.

- Mainely Code remains proprietary and must not be imported, referenced at runtime, packaged, scanned, or added to attribution as a dependency.
- LEGAL FAST INTERCHANGE is the family-law successor for the authorized open-source portions. Preserve a file-level import/provenance record before importing any code.
- Do not import weights, adapters, corpora, evaluation rows, credentials, binaries, virtual environments, build outputs, or user data.
- No worker starts automatically, downloads a model, discovers a provider, telemeters, or calls a non-loopback address.
- The browser UI never receives, stores, logs, or displays a worker bearer token.
- The MSIX contains worker source only if its code dependencies are compatible and package-audited. It contains no legal model artifact by default.
- Every model output remains `review_required`; all supplied source text remains data, never executable instruction.

## Target architecture

```text
Production desktop UI
  -> canonical /api/local-agent preview and exact-context approval
  -> LocalAgentRuntime (source manifest, injection scan, provenance receipt)
  -> FastInterchangeLocalClient
  -> literal loopback only, bearer-authenticated worker at 127.0.0.1:8105
  -> serialized HotSwapManager
  -> verified immutable artifact registry
  -> one shared base + one compatible LoRA adapter

No shared KV cache, no tool calls, no streaming, no remote fallback.
```

The existing application remains the policy enforcement point. The worker is a narrow inference appliance. It must not contain a second matter store, authority resolver, filing gate, or user-facing web UI.

## Phase 0 — controlled consolidation

### Inputs

- Source project: `D:\dev\LEGAL FAST INTERCHANGE`.
- Consumer project: this repository.
- Source guide: `D:\dev\LEGAL FAST INTERCHANGE\docs\HOTSWAP_MODELS.md`.
- Current public fleet plan: `configs\fast_interchange_model_fleet.json`.

### Required actions

1. Confirm the source project has an explicit, recorded redistribution decision compatible with this repository's license before copying implementation files. A user direction authorizing this family-law successor must be recorded in the import manifest; it does not convey Mainely Code rights.
2. Implement or import only the runtime required for the worker: canonical hashing, closed contracts, release registry, artifact inventory, hot-swap manager, and worker entrypoint.
3. Place imported/adapted code under `legal\fast_interchange\`; do not embed the source project's package name in the public application API.
4. Add `legal\fast_interchange\PROVENANCE.json` with source-relative path, source SHA-256, destination path, import date, authorization note, and changes after import.
5. Add `legal\fast_interchange\NOTICE.md` stating that no Mainely Code source, trademark, weight, corpus, adapter, credential, or binary is included.
6. Exclude the external source project and all artifact roots from packaging and repository scans.

### Acceptance

- A source-copy verifier proves every imported file is listed and hash-accounted for.
- `rg` confirms no `D:\dev\MAINELY`, source-project path, credential, weight, or corpus path is present in shipped code or MSIX staging.
- The package imports without `torch`, `transformers`, `peft`, or `safetensors` installed.

## Phase 1 — model-empty contracts

### New modules

- `legal\fast_interchange\contracts.py`
- `legal\fast_interchange\fleet.py`
- `legal\fast_interchange\artifacts.py`
- `legal\fast_interchange\release_registry.py`
- `legal\fast_interchange\hotswap.py`
- `legal\fast_interchange\worker.py`
- `legal\fast_interchange\__init__.py`

### Closed data contracts

`FastInterchangeFleet` must require exactly the seven capability IDs above, unique slot IDs, `lora` adapter kind, `specified_untrained` or an approved lifecycle status, `shared_kv_cache: false`, `remote_downloads: false`, and `promotion_authority: false`.

`ModelRelease` must include at least:

- immutable `release_id` and `model_id`;
- one capability only;
- lifecycle status (`candidate`, `test_only`, `admitted_for_dev`, `admitted_with_limits`, or `admitted_for_production`);
- exact base, tokenizer, adapter, adapter-config, runtime, prompt-template, evaluation, and release fingerprints;
- artifact sizes and SHA-256 values;
- base-model and adapter license identifiers plus approval status;
- hardware minima, context limit, quantization, worker ABI version, and fixed-generation policy;
- evidence hashes and release/admission receipts;
- explicit human-review and no-promotion flags.

`ArtifactBinding` must use relative paths below one configured external artifact root. It must reject absolute paths, traversal, symlinks escaping the root, empty manifests, duplicate paths, placeholder hashes, zero-byte declared artifacts, incompatible base/tokenizer digests, and incompatible adapter ABI/version.

### Acceptance

- Empty fleet plan loads and remains unavailable for real inference.
- A release cannot represent more than one family-law capability.
- A missing model artifact produces a typed, safe failure—not a download attempt.
- All registry and receipt state is outside the source repository and encrypted where it is matter-associated.

## Phase 2 — isolated hot-swap worker

### Worker behavior

The worker must bind only to `127.0.0.1` or `::1`, reject host names and all non-loopback destinations, and use a separate bearer secret of at least 32 UTF-8 bytes. It exposes only:

- `GET /healthz` — content-free readiness and quarantine status;
- authenticated `GET /v1/models` — admitted immutable release metadata only;
- authenticated `POST /v1/chat/completions` — one fixed completion contract.

The worker accepts exactly these request keys:

```json
{
  "model": "admitted-release-model-id",
  "messages": [{"role": "system|user", "content": "bounded text"}],
  "temperature": 0,
  "top_p": 1,
  "max_tokens": 1024,
  "stream": false
}
```

It rejects tools, function calling, images, arbitrary paths, adapter IDs, runtime flags, streaming, remote endpoints, arbitrary sampling values, incomplete completions, excess body size, unrecognized JSON keys, duplicate JSON keys, and a model not registered in the immutable release registry.

### Hot-swap lifecycle

1. Verify the artifact registry and shared base/tokenizer inventory before first activation.
2. Verify the selected release is admitted for the requested capability.
3. Serialize all completions with one worker lock.
4. Clear Python/engine context before request use.
5. Activate an adapter only when base, tokenizer, quantization, runtime ABI, and prompt-template fingerprints match.
6. Generate with `use_cache=False`; do not retain a KV cache across requests or adapter changes.
7. Clear context after generation, including on exception and cancellation.
8. Validate returned model identity and stop reason.
9. Quarantine the worker on identity mismatch, artifact mismatch, adapter activation failure, generation failure, or context-clear failure.
10. Require an operator restart and a new health check after quarantine; never silently retry with a different adapter.

### Backends

- `FakeAdapterBackend` is test-only and supplies deterministic synthetic completions.
- `TransformersPeftAdapterBackend` is optional and imported lazily. It may use CPU only when the operator explicitly enables CPU mode.
- GPU/4-bit support is optional. It cannot be presumed because this host's Python torch runtime is CPU-only.
- `torch`, `transformers`, `peft`, `safetensors`, and any accelerator-specific component are optional extras, never base application dependencies.

### Acceptance

- A fake backend proves base reuse, adapter switch, context clearing before/after each run, and quarantine on every unsafe state.
- Starting the worker without a token, an artifact registry, an artifact root, a validated registry fingerprint, or an admitted release fails before binding a port.
- A loopback HTTP test proves the exact request headers/body and proves that the bearer secret is absent from all response bodies and logs.

## Phase 3 — canonical application integration

### Service and API ownership

1. Retain `legal\agent_runtime\providers.FastInterchangeLocalClient` as the only application-to-worker client.
2. It reads `MAINE_FAST_INTERCHANGE_WORKER_TOKEN` from the desktop host process only.
3. It accepts only a literal loopback endpoint, validates release-model IDs, fixes generation controls, and rejects a returned model-ID mismatch or non-`stop` completion.
4. `GET /api/local-agent/status` advertises FAST INTERCHANGE as external, disabled by default, token-required, unbundled, and admission-required.
5. Existing `/api/local-agent/preview` remains non-networking and produces the source/context manifest.
6. Existing `/api/local-agent/run` remains the only path that may call the worker, only after exact manifest approval and source-instruction quarantine.
7. The host's provenance receipt records provider ID, release-model ID, loopback endpoint class, request/manifest hashes, safe timing, and review status—never a worker token, local path, model prompt, or generated raw matter text beyond the existing protected result path.

### UI ownership

1. Add `FAST INTERCHANGE admitted local worker` to the existing optional local-model chooser.
2. Selecting it fills `http://127.0.0.1:8105` and an example release-model ID, but does not start a worker or imply an installed model.
3. The UI says the host-only token, externally admitted release, and separately operated worker are required.
4. It never offers an artifact path, adapter selector, token input, download button, train button, model marketplace, or “ready” badge.
5. All normal source-card, exact-context-preview, review-required, cancel, error, and focus behavior remains intact.

### Acceptance

- API unit tests prove no request can run without exact context approval and source cards.
- UI tests prove the token name/value cannot appear in HTML, browser storage, status payloads, screenshots, error strings, or clipboard features.
- An unauthenticated/misconfigured worker produces a recovery-safe error and does not fall back to an external provider.

## Phase 4 — task routing and output control

Do not let free-form user text select an adapter. The host maps an explicit, reviewed task to one capability and one admitted model route. The mapping is:

| Host task | FAST INTERCHANGE capability | Output boundary |
| --- | --- | --- |
| Intake review | `intake_triage` | Questions/gaps only; no legal conclusion |
| Evidence review | `evidence_review` | Source-bound observations only |
| Authority review | `authority_review` | Retrieval aid; official source/verifier still controls |
| Draft assist | `drafting` | Review-required draft only |
| Parenting review | `parenting_plan_review` | Schedule/logistics review, no custody decision |
| Financial review | `financial_disclosure_review` | Missing-data and arithmetic review, no final legal calculation |
| Safety/privacy review | `safety_privacy_review` | Safety/privacy flags, no emergency adjudication |

Structured candidate output is a second milestone. Before enabling it, the host must validate request binding, exact source quotes, candidate schema, verifier states, source citations, source freshness, filing gates, and human-review status. Free-form worker prose never bypasses those validators.

## Phase 5 — model admission and evaluation

No model moves beyond `candidate` without all of the following external inputs:

1. Rights-cleared base-model license and immutable base artifact.
2. Rights-cleared, privacy-reviewed, synthetic or properly authorized training data.
3. One-capability-only adapter run with reproducible training recipe and dataset split evidence.
4. Adapter/base/tokenizer/runtime/quantization hashes and signed artifact inventory.
5. Hardware measurements on target modest PCs: cold start, warm prompt latency, adapter-switch latency, total task latency, peak RAM, peak VRAM, CPU/GPU utilization, failure/retry cost, and clean release behavior.
6. Synthetic safety, injection, quote, citation, hallucination, privacy, cancellation, and restart evaluations.
7. Held-out legal-quality evaluation. Synthetic results must never be called attorney review.
8. Human review and release approval recorded separately from model self-report.
9. Explicit failure profile, fallback route, rollback release, and revocation plan.

For the cross-encoder blocker, an independent local reranker artifact needs its own license, hash, hardware plan, retrieval benchmark, and admission record. A LoRA generation worker does not satisfy that requirement.

## Phase 6 — certification matrix

Every evidence row must name its proof level. Do not collapse the levels.

| Level | Required proof | What it does not prove |
| --- | --- | --- |
| Contract | Unit tests with fake backend | Real model quality or hardware speed |
| Worker | Isolated loopback worker with synthetic artifacts | Legal model performance |
| Host E2E | Production UI → canonical API → worker → protected receipt | Admitted legal model quality |
| Hardware | Actual target-PC benchmark | Cross-device performance |
| Model admission | Rights/eval/reviewer evidence | Enterprise GA/pilot approval |
| Frozen package | Rebuilt exact MSIX with optional lane and privacy audit | Store or Enterprise GA |

Required test files:

- `tests/test_fast_interchange_fleet.py`
- `tests/test_fast_interchange_artifact_registry.py`
- `tests/test_fast_interchange_hotswap.py`
- `tests/test_fast_interchange_worker_contract.py`
- `tests/test_fast_interchange_quarantine.py`
- `tests/test_fast_interchange_host_integration.py`
- `tests/test_fast_interchange_ui.py`
- `tests/test_fast_interchange_local_only.py`
- `tests/test_fast_interchange_no_secret_leak.py`
- `tests/test_fast_interchange_packaging.py`

Required evidence files:

- `dist\ga_today\evidence\fast_interchange_contract.json`
- `dist\ga_today\evidence\fast_interchange_synthetic_worker_e2e.json`
- `dist\ga_today\evidence\fast_interchange_ui_e2e.json`
- `dist\ga_today\evidence\fast_interchange_package_boundary.json`
- `dist\ga_today\evidence\fast_interchange_model_admission.json` only when a real admitted model exists.

## Phase 7 — packaging and release

1. Keep the worker source, fleet plan, connector documentation, and tests in the source tree.
2. Keep model registries, external artifact roots, weights, adapters, caches, training data, logs, and worker secrets outside the repository and MSIX.
3. Rebuild the MSIX after source integration.
4. Audit the exact package for forbidden artifact extensions, private data, secrets, source project paths, authority stores, and evaluation data.
5. Run frozen-runtime UI proof using an isolated fictional profile. The test must select the FAST INTERCHANGE option and show the truthful unavailable/admission-required state unless a separately admitted synthetic worker is intentionally configured.
6. Do not represent the existing package build as containing this lane; it predates the completed source integration.

## Execution order and stop conditions

1. Establish provenance/import scope.
2. Add model-empty contracts and test them.
3. Add the isolated worker and fake-backend tests.
4. Complete the connector, API, UI, no-secret, and local-only tests.
5. Run a synthetic-worker production UI E2E path.
6. Rebuild and inspect the MSIX.
7. Obtain artifact/legal/evaluation inputs before any real model-admission work.

Stop and report `BLOCKED` if a rights decision, artifact license, source provenance, worker secret, external model registry, hardware dependency, or evaluation prerequisite is absent. Do not solve a missing model by downloading one, using a remote provider, reusing proprietary weights, or calling a synthetic worker a legal model.

## Latest release continuation — 2026-08-28

See [protected PDF preview and managed-vault verification](PDF_PREVIEW_RELEASE_CONTINUATION_20260828.md) for the current rebuilt engineering MSIX, exact package hash, full-baseline/final-delta test results, fresh frozen-UI proof, and remaining gates. This supersedes the earlier explicit-key preview candidate, not the model-admission prerequisites. All seven legal adapter slots remain untrained/unadmitted; the current Store and Enterprise decisions remain **BLOCKED**.
