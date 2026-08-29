# FAST INTERCHANGE: audited implementation handoff

Audit date: 2026-08-27. Checkout: `D:\dev\Maine-Family-Law-LLM-github-main`, branch `main`, HEAD `8fd54274ead2334be1f6b45216352796ab41e940`, with substantial pre-existing changes. Preserve them. Do not commit, publish, download models, train, start services, or rebuild packages merely because this document lists future work.

## Current truth

2026-08-28 follow-up: consult
[FAST_INTERCHANGE_SIGNED_WORKER_VERIFICATION.md](FAST_INTERCHANGE_SIGNED_WORKER_VERIFICATION.md)
before using this older defect list. Native signed admission, immutable loading,
task binding, owned-worker cancellation/restart, and source-UI recovery are now
implemented and locally tested. The new offline signed-pack controls remain
development-preview scope; full acquisition/recovery, real legal models,
hardware measurements, and frozen/installed-package proof are not complete.
Do not call the whole plan certified from focused or synthetic source tests.

Update: the later [FI-01 verification report](FAST_INTERCHANGE_FI01_VERIFICATION.md)
supersedes this audit's original caller-supplied-source defect and test counts.
The host now rehydrates protected references, requires a single-use scoped
approval, and checks source access before/after generation. Focused source/API
and production-source browser evidence exists; generation was synthetic and
the real model, admission, cancellation, hardware, and package gates stay open.

The seven capability slots are an **untrained specification**, not seven models. The native source implementation did not copy Mainely Code or LEGAL FAST INTERCHANGE files; see `legal/fast_interchange/PROVENANCE.json`. No approved weights, training corpus, adapters, admission receipts, or target-PC benchmark were supplied or validated in this audit. Other projects and private artifact directories were not scanned.

Keep `worker.py` consolidated for now. The original plan's proposed module/test filenames are design targets, not evidence that those modules exist. Do not burn time splitting working code merely to match filenames.

| Area | Actual implementation | Verified limit / outstanding work |
| --- | --- | --- |
| Fleet | `legal/fast_interchange/fleet.py`, `configs/fast_interchange_model_fleet.json` | Seven unique untrained capabilities; parser is not a fully closed admission schema. |
| Provenance | `legal/fast_interchange/PROVENANCE.json`, `NOTICE.md` | Native implementation record; not a rights grant for external weights. |
| Registry and artifacts | `ArtifactFile`, `ArtifactInventory`, `ArtifactBinding`, `FastInterchangeRelease`, `HotSwapRegistry` in `worker.py` | Declared-file hashes and shared inventory checks exist. No independently trusted registry fingerprint/signature, license/eval fields, or demonstrated exhaustive coverage of files the loader can consume. |
| Worker | `HotSwapManager`, `TransformersPeftAdapterBackend`, `create_worker_app`, `main` | Synthetic swap, fixed request, auth and quarantine tests. Cancellation, request-body streaming limit, signed admission and readiness guarantees remain incomplete. |
| Connector | `legal/agent_runtime/providers.py:FastInterchangeLocalClient` | Literal-loopback policy, host token, fixed request, returned-model/stop checks. No task-to-capability admission binding. |
| Host API | `maine_family_law_llm/api.py`, mirrored `src/.../api.py`: `/api/local-agent/status`, `/preview`, `/run` | Updated: protected server-rehydrated references, local session/matter binding, single-use approvals, encrypted audit, and replay/revocation tests. Real admitted-release routing remains open. |
| Production UI | Both `ui/workbench.html` and `ui/workbench.js` mirrors | Optional chooser, preview, run and review display exist. Static tests do not prove browser-to-worker E2E or real cancellation. |
| Tests | `test_fast_interchange_worker.py`, new `test_fast_interchange_completion_boundary.py`, `test_v540_local_agent_*` | This run: 30 passed, one socket test deliberately deselected, one upstream deprecation warning. No real models or GPU imported. |
| Release | Existing package predates current integration repairs | No current frozen/MSIX, installed-package, Store, or Enterprise certification. |

## Repair completed in this bounded audit

`TransformersPeftAdapterBackend.complete` previously truncated input at 2,048 tokens and unconditionally emitted `finish_reason=stop`. It now tokenizes without truncation, refuses over-budget input before generation, and requires an explicit configured EOS token at the end of output. Unknown stopping semantics and exhausted output without EOS fail closed before decoding or returning partial text.

`HotSwapManager.complete` now requires one completed assistant text choice, rejects tool-call/non-text/extra-choice payloads, returns only the fixed response fields, and quarantines on violations. The in-process worker API test proves partial text is withheld and a subsequent request is refused.

Regression baseline: 10 failures and 2 passes reproduced before the repair. Final focused run: 30 passed, zero failures/errors/skips, one deselected socket-based test. These are synthetic contract/API tests; tensor stubs test control flow, not Transformers/PEFT correctness or performance. The fixed 2,048/1,024 budgets are conservative provisional limits, not hardware-tuned model limits.

## Ordered implementation batches

Do one batch at a time. Test a coherent boundary, update evidence, and leave all downstream gates closed. No UI completion badge or production admission status until its evidence exists.

### FI-01 — source truth before model integration (P1)

Files: `app/services/authority_library_service.py`, `app/services/authority_product_service.py`, authority API routes, both desktop API files, both workbench JS mirrors. Reuse the immutable-generation path added for Slice 30; do not create a second authority store.

1. The prior browser audit demonstrated that the generic Evidence inventory can render a changed mutable ingestion row as official authority. Bind generic source lists and exact previews to one verified active generation; fail closed without it. Remove authority fallback to seed fixtures or private-record lists. Preserve separately labeled private-record access.
2. For FAST INTERCHANGE preview/run, accept source references and exact spans, then rehydrate content server-side. Authority references need active build ID, source ID, source hash and exact offsets. Private records need the authenticated active matter, record capability and immutable artifact hash. Reject cross-matter/stale/tampered references. Do not treat posted `authority_status` or posted prose as admission proof.
3. Bind the preview approval to actor/session, matter, exact source generation, provider/model, task and run. A changed field or source generation requires another preview. Retain review-required even when bindings pass.
4. Prove canonical global role/session enforcement and fail-closed audit behavior via HTTP tests, not direct Python handler calls. Matter-private durable receipts must use the existing encrypted store; do not introduce a plaintext transcript log.

Acceptance: add `tests/test_fast_interchange_host_source_binding.py`; cover forged source text/status, mutable canary, stale build, wrong hash/span, cross-matter, revoked token, missing actor, changed model/task, audit failure, and an authorized fictional source. Rerun Slice 30 and immutable-authority tests plus `test_v540_local_agent_api_ui.py`. Do not enable worker-backed UI success while this gate fails.

### FI-02 — trusted releases and exhaustive artifacts (P1)

Files: registry/artifact classes in `worker.py`, fleet parser, `PROVENANCE.json` only if actual authorized files are imported. Test file: `tests/test_fast_interchange_artifact_registry.py`.

1. Add a versioned, strictly typed closed release schema carrying independently verified admission, license IDs/approval, evidence digests, hardware/context limits, quantization, tokenizer, prompt-template and runtime fingerprints. Define canonical bytes before signatures/digests. A self-declared `admitted_for_production` string is not admission.
2. Verify the registry against an operator-controlled trust anchor or explicitly approved fingerprint supplied out of band. Never create your own approval certificate and call it production admission. Reject duplicate JSON keys, duplicate model IDs, unknown admission states, placeholder hashes and mixed incompatible templates/runtime/base/tokenizer settings.
3. Ensure every file the loader can open is in an inventory and lies under the declared base/tokenizer/adapter directory. Test unlisted config/weight files, symlink or junction escapes, case-folded duplicate paths, alternate data streams, zero-byte artifacts and absolute paths. Keep artifact roots external to repo/MSIX.
4. Replace verify-once assumptions with an immutable loading strategy. Demonstrate that mutation after first use or before switching back cannot load unverified bytes. Avoid rehashing an entire multi-GB base on every chat request: prove immutability/identity first, then cache safely; otherwise fail closed.
5. Startup must refuse to bind without valid token, trusted registry, allowed release and validated artifacts. `/healthz` must distinguish configured/cold/ready/quarantined, not advertise a fully ready inference engine before activation.

Acceptance: synthetic fixtures may use test-only trust with unmistakable test labels; production mode rejects them. No real weights are necessary to test these contracts. Do not migrate an old unsigned registry into trusted admission automatically.

### FI-03 — worker lifecycle and cancellation (P1)

Files: `worker.py` request middleware, completion endpoint, manager and optional backend; host client cancellation contract. Tests: `tests/test_fast_interchange_worker_contract.py`, `tests/test_fast_interchange_quarantine.py`.

1. Bound actual streamed body bytes, not just caller `Content-Length`; reject duplicate keys/non-finite numbers/extra fields without echoing input. Disable unneeded OpenAPI routes. Test Unicode/bad auth headers, hostile origins and safe error bodies.
2. Move blocking inference off the ASGI event loop with a bounded single-generation queue. Cancellation must signal the active backend, clear private context in `finally`, and leave a truthful canceled/quarantined state. Merely aborting a browser fetch does not stop generation. Test queue-full, timeout, disconnect, cancellation during activation/generation/cleanup, and subsequent-request isolation.
3. Quarantine on identity/completion/context-clear failures; release resources predictably. Test request interleaving, base reuse, adapter switching and no retained cross-matter text. Clear exception references before admitting another request after failures.
4. Keep explicit CPU opt-in and lazy ML imports. Safetensors-only/offline loader behavior and exact tokenizer/chat-template application need real-library tests before admission. Preserve the new no-truncation and explicit-EOS checks. Do not declare speed or memory guarantees from fake backends.

Acceptance: deterministic fake-backend tests first. A loopback transport test requires authorization to start a temporary QA worker; stop it in `finally` and retain no token/prompt logs. Never add a public listener or automatic worker startup.

### FI-04 — capability routing and host controls (P1)

Files: `legal/agent_runtime/providers.py`, `runtime.py`, existing request models in both API mirrors and both production UI mirrors. Tests: `tests/test_fast_interchange_host_integration.py`, `tests/test_fast_interchange_ui.py`, `tests/test_fast_interchange_no_secret_leak.py`.

1. Map an explicit approved host task to exactly one admitted release capability. Free text, model output and browser-supplied adapter IDs cannot choose a route. Keep model-selection permission separate from source access permission.
2. Revalidate exact context and capability immediately before dispatch. Host owns quote/claim/source/verifier and filing gates; no worker self-report can replace them. Distinguish generated analysis from legal authority and factual findings.
3. Show unavailable/cold/running/canceled/quarantined/review-required states and recovery actions in the existing chooser/dialog. No separate training dashboard, remote fallback, model download or token field.
4. Test safe provider failures, mismatched identity, wrong capability, revoked release, token absence/leakage, private text/path redaction and clipboard/receipt boundaries. Preserve default Local-only behavior without discovery or health calls.

Acceptance: a fictional production UI action must reach the canonical API, approved test worker, protected result and exact source drill-down. Capture DOM/screenshots and request/artifact IDs; no current package claim from source-only UI.

### FI-05 — package boundary and modest-PC evaluation (separate authorization)

Files: `store/pyinstaller/maine_family_law_llm.spec`, packaging/audit scripts, `pyproject.toml` only if justified, `tests/test_fast_interchange_packaging.py`.

First verify source imports with ML extras blocked, fleet/config packaging reachability, and no weights/token/corpus/registry/cache in staged assets. Rebuild only when authorized; hash and inspect the exact resulting MSIX. Use isolated fictional profiles, never uninstall the user's package. Prove optional-lane unavailable state and later authorized synthetic-worker behavior through the frozen production UI. Keep WACK/install evidence separate.

Only with approved external model/runtime artifacts: measure cold/warm latency, first token where supported, adapter switch, peak RAM/VRAM, cancellation, restart and memory release on actual target machines. The current backend has no demonstrated quantized modest-hardware performance. Do not choose a base or install GPU packages without an explicit artifact/license/hardware decision.

### FI-06 — actual models and legal evaluation (external gate)

Required inputs: rights-cleared base/tokenizer and runtime versions; permitted training corpus with privacy review; seven separate capability recipes/adapters; immutable inventories; independent admission/revocation trust; held-out safety and legal-quality evaluations; authorized human review; target-PC measurements. Record exactly which inputs remain absent. Do not generate a model-admission success artifact until a real admitted model exists. LoRA generation does not satisfy the separate cross-encoder/reranker requirement.

## Commands and evidence discipline

Current socket-free suite:

```powershell
python -m pytest -o addopts= -q tests/test_fast_interchange_completion_boundary.py tests/test_fast_interchange_worker.py tests/test_v540_local_agent_runtime.py tests/test_v540_local_agent_api_ui.py -k 'not synthetic_host_to_native_worker_path' --junitxml=dist/ga_today/evidence/fast_interchange_prerequisite_junit.xml
python -m ruff check legal/fast_interchange/worker.py tests/test_fast_interchange_completion_boundary.py
python -m compileall -q legal/fast_interchange tests/test_fast_interchange_completion_boundary.py
git diff --check
```

The single deselection is intentional: this heartbeat did not authorize starting a worker network service. TestClient calls are in-process. Each future batch must name what it excludes and why; failing tests must not be hidden by changing selection.

Record current Git identity, dirty-tree scope, source hashes, exact command/count/duration, fictional-only basis and outstanding blockers in a new evidence file. The current evidence is `dist/ga_today/evidence/fast_interchange_plan_audit.json`. Keep old evidence immutable. Separate synthetic contracts, loopback transport, browser integration, frozen app, hardware, model admission and human certification.

The generic authority-inventory prerequisite and the subsequent bounded FI-01 source/approval path were repaired on 2026-08-28. The later report above records canonical HTTP and actual source-UI verification, plus remaining immutable-manifest, enterprise identity, OCR-derivative, admission, real-model and package limitations. Do not repeat the superseded claim that preview/run still accept caller source prose; do not turn the source-only synthetic proof into real lightweight law-model certification.
