# FAST INTERCHANGE signed-worker implementation and local verification

Date: 2026-08-28. Scope: native FAST INTERCHANGE integration only. This is not a
claim that every operational slice, seven legal models, or Store/Enterprise GA
is complete. Mainely Code remains excluded. No proprietary source, model,
corpus, credential, or binary was copied.

## Implemented

- Independent Ed25519 admission over both complete registries, release and
  capability identity, licensing/evaluation metadata, pinned library versions,
  generation limits, and prompt-template identity. Public trust is provisioned
  separately; the shipped trust configuration deliberately contains no keys.
- Signature, expiry, revocation, duplicate/unknown fields, catalog sequence,
  same-sequence conflicts, and trust-revision rollback checks. Local high-water
  state is encrypted using the existing OS-protected vault mechanism. It is
  **not** a hardware-backed anti-rollback anchor against the same OS account.
- Exhaustive artifact-directory inventories; Windows reserved-name, alternate
  stream, traversal, link/junction, unlisted-file, and hash/size defenses.
  Loading uses owned snapshots verified during copying. Windows read handles
  deny write/delete sharing until worker shutdown. The base snapshot is reused;
  a changed installed original cannot silently change the loaded snapshot.
- Bounded safetensors headers, offsets, tensor allocation, supported model
  configuration, adapter configuration, and loader-layout validation. Remote
  code and implicit downloads are forbidden. This version supports reviewed
  Llama/Mistral/Qwen2/Qwen3-style, single-safetensors base layouts. CPU inference
  is explicitly opt-in and fp32; fp16/bf16 require the corresponding validated
  GPU profile. NF4, GGUF, sharded bases, and general low-RAM performance have not
  been qualified by this work.
- Fixed authenticated loopback v2 requests. A one-use reservation binds model,
  task, release fingerprint, and request ID; the response must echo that exact
  identity. Streamed input bytes are bounded independently of Content-Length.
  Cross-origin requests and provider redirects are rejected; ambient proxies
  cannot redirect FAST INTERCHANGE traffic.
- One serialized generation, at most four live reservations, bounded replay
  memory, and a 120-second operation deadline. Blocking inference runs outside
  the ASGI event loop. The production entry point owns an inference subprocess;
  cooperative cancellation has a bounded hard-termination fallback. A canceled
  child can be replaced without retaining prior request context. Identity,
  cleanup, or completion failures quarantine the worker.
- Host approval now binds signed model admission as well as exact sources,
  question, task, matter, local role/session, and endpoint. Cancellation is a
  canonical matter/session-protected, encrypted-audited action. Late or canceled
  output is withheld. Local roles/session headers are not enterprise identity
  federation or multi-user authentication.
- The actual production UI has the seven-task selector, exact release and
  admission disclosure, generation cancellation, confirmation, recovery,
  incompatible-task refusal, and live status announcements. Other providers
  retain an honest “does not cancel generation” close action.
- A separate offline signed-pack service now supports bounded chunked local
  copy, cryptographic inspection, exact artifact/layout verification, separate
  activation consent, cancellation, encrypted scope-bound state, interrupted
  verification reporting, and deletion of only an explicitly discarded staging
  copy. The user's original ZIP and installed versions are not deleted. The
  format accepts uncompressed, non-ZIP64 ZIPs up to 3 GiB and rejects extra
  files, links, executables, unsafe paths, and oversized central directories.
  Approved pack data stays outside the source tree and matter folders. UNC and
  mapped network stores are refused. One base is stored per complete pack.
- Catalog inspection checks current trust/rollback bounds without advancing
  admission. Only activation advances admission; canceling a newer inspected
  catalog cannot obsolete the active one. Host and worker can resolve the same
  explicitly selected active pack. Neither starts a worker automatically.
- CLI import without the optional API dependencies works again. Source-release
  scans prune already-excluded build trees before descending, preserving the
  existing private-state findings and source inclusion rules.

Canonical host routes: `GET /api/local-agent/status`,
`POST /api/local-agent/preview`, `POST /api/local-agent/run`, and
`POST /api/local-agent/cancel`. Both packaged source mirrors are kept identical.

Canonical pack routes are `GET /api/model-packs`, `POST /api/model-packs/imports`,
`GET /api/model-packs/imports/{job_id}`, and `POST` actions `chunks`, `inspect`,
`cancel`, `activate`, and `discard` below that import ID. Mutations require the
existing local admin acknowledgment, current matter, tenant, and browser-session
scope. This is local-desktop protection, not enterprise identity management.

## Evidence levels

1. Service/API/security tests use fictional records and explicit test-only
   catalogs. Test keys can never admit production scope. Seven-slot routing and
   switching tests use distinct synthetic adapter artifacts, not trained models.
2. Process tests start an actual owned Windows subprocess, deliberately ignore
   cancellation inside the synthetic backend, prove termination/deadline, then
   prove clean restart and subsequent isolated requests.
3. The actual installed CPU libraries—PyTorch, Transformers, PEFT, and
   safetensors—load a locally constructed tiny neural model and LoRA adapter.
   Two deterministic responses pass with socket connections prohibited. These
   hand-constructed weights have **no legal knowledge** and are not trained law
   models, gold evaluations, or modest-hardware speed evidence.
4. Browser evidence exercises the production source UI, canonical local API,
   actual authenticated worker HTTP, and owned synthetic inference subprocess.
   It includes exact source approval, cancellation while the worker reports
   running, confirmed cancellation, mismatched-task refusal, a subsequent
   successful request, hash-bound receipt, and original-source inspection.
5. No new frozen executable or MSIX was built or installed. The old package is
   not evidence for these source changes.
6. Offline-pack service/canonical API tests perform real local ZIP import,
   signature/byte/layout checks, distinct activation, and restart with ephemeral
   test-only trust. JavaScript tests execute the production import controls for
   consent, chunking, cancellation, duplicate clicks, errors, and activation.
   The browser rendered the real controls and queried their empty inventory,
   but native file selection was not available through this browser connection.
   **File-selection-to-activation browser E2E remains unproven.** The fixture's
   structural tensors are not a usable or legally trained model.

Browser artifacts are under
`dist/ga_today/evidence/fast_interchange_operational/20260828-signed-worker-ui/`.
The original `.capture.jpg` images are retained; `.png` files are true PNG
re-encodings at 1265×712. They are fictional QA evidence, not final Store assets.
Artifacts 05 and 07 intentionally preserve the discovered generic-error UX
defects; 09 and 10 show their repaired behavior. Final recovery/source evidence
is in 11 and 12. No private matter data is used.

Machine-readable test counts, exact commands, durations, file hashes, and final
regression state belong in the companion `verification.json`,
`verification.txt`, and `artifact-manifest.json`; do not infer a pass from this
document alone. The first full regression attempt was stopped to repair the
forced-EOS-at-output-limit defect. It is not a completed or passing run.
The next full run completed with 1,913 passes, 5 failures, and 22 skips. Its
failures covered a source-scanner false positive in a test assertion, readiness
checks affected by that assertion, an API mirror mismatch during editing, and
the optional-dependency import defect. The repaired affected group subsequently
passed all 16 tests. A separate focused run passed all 175 FAST INTERCHANGE
tests (including 26 offline-pack and 7 pack-UI unit tests). Historical failures
are retained. Two subsequent full regressions each completed with 1,953 passed,
22 skipped, zero failures and zero errors (1,975 collected). The final repeat,
after all source-code edits, took 972.551 seconds in JUnit (972.58 seconds in the
console). SHA-256 checks found no drift in 29 watched integration inputs during
that repeat. The 175-test focused run and 23-test final-polish run also passed.

The 22 skips are not passes: six missing archived GA/authority evidence tests,
one missing native Whisper input fixture, fourteen unavailable Windows symlink
privilege tests, and one unsupported POSIX-mode test. The read-only source
hygiene audit checked 2,090 files and found no policy findings. The loaded app
has 644 method/path pairs and no duplicate or normalized-parameter collisions.
These results do not remove the operational and package blockers below.

The installer checkbox sizing and disabled-control readability were repaired;
the declared disabled-text/background pair has a 5.986:1 contrast ratio.
Activation explicitly states it is non-cancellable once confirmed. The final
polish tests passed, but a post-polish screenshot attempt hit browser transport
timeouts. Screenshot 13 is the pre-polish empty state, not proof of the final
rendering or the native-file-selection journey.

## Operator boundary

Both host and worker need an independently approved external release registry,
artifact registry, signed catalog, public trust file, and external admission
state directory. The corresponding environment names are:

```
MFL_FAST_INTERCHANGE_ARTIFACT_ROOT
MFL_FAST_INTERCHANGE_RELEASE_REGISTRY
MFL_FAST_INTERCHANGE_ARTIFACT_REGISTRY
MFL_FAST_INTERCHANGE_ADMISSION_CATALOG
MFL_FAST_INTERCHANGE_ADMISSION_TRUST
MFL_FAST_INTERCHANGE_STATE_ROOT
```

The worker's bearer credential is `MFL_FAST_INTERCHANGE_WORKER_TOKEN`; the host
uses the same credential via `MAINE_FAST_INTERCHANGE_WORKER_TOKEN`. Never place
it in the browser, model catalog, source repository, evidence, or package.
`MFL_FAST_INTERCHANGE_ALLOW_CPU=1` explicitly enables the CPU profile.
`python -m legal.fast_interchange.worker` fails closed when admission is absent.
No test-key or test-release override is accepted by the production entry point.

For offline-pack mode, provision `MFL_FAST_INTERCHANGE_PACK_ROOT` on a local
external disk folder plus the independent trust and state paths above. Leave
the four manual artifact/registry/catalog variables unset in that mode. Mixed
partial configuration fails closed. The pack root contains data only, not a
runtime installer; the worker's optional libraries must already be present.
Import a pack containing `releases.json`, `artifacts.json`, `admission.json`, and
exactly the signed loader files. Do not put trust keys or secrets in the ZIP.

The Settings disclosure and operator environment are prerequisites, not a
completed consumer onboarding flow. The new import UI is development-preview
scope until its native-file journey and exact installed build are qualified.

## Still required; not implemented or certified by this pass

- Approved-host download with consent, redirects/DNS/resume/range controls and
  live delivery proof. Offline import remains intentionally distinct from a
  downloader. The later [offline-pack recovery verification](FAST_INTERCHANGE_PACK_RECOVERY_VERIFICATION.md)
  supersedes this report's
  older recovery limitation: bounded cross-session resume, journaled
  activation recovery, recoverable inactive-pack removal/restore, and their
  focused browser/fault tests are implemented for a fictional structural pack.
  They do not prove real-model acquisition, redistribution rights, a hosted
  delivery service, or a general rollback bypass; current trust and admission
  checks still apply before activation.
- A selected rights-cleared, licensed base/tokenizer and seven actually trained
  compatible family-law adapters; authorized corpus and provenance; exact
  artifacts and admitted releases. No such fleet is supplied by these tests.
- Real legal evaluation, current official-authority/quote/claim checks on those
  weights, attorney review, and independent admission. Dataset labels or test
  signatures are not substitutes for those activities.
- Actual 8-GB/16-GB hardware measurements, quality/latency/memory budgets,
  seven-adapter real-model E2E, cancellation, and restart under supported loads.
- New frozen-runtime and installed-MSIX tests against the repaired assets,
  isolated install/upgrade/offline checks, package privacy/engine audit, approved
  signing, and required WACK/Store qualification. Enterprise human sign-offs and
  pilots remain separate.

Existing candidate (unchanged):
`dist/ga_today/fast_interchange_store_candidate_active_authority/msix/MaineFamilyLawLLM_8.0.0.0_x64.msix`.
Size: 1,591,350,737 bytes. SHA-256:
`1839c427d5e49c994f195316ed57cbde7096586798d649cf21e31767949ce4d8`.
Inspection confirms it contains the **older** worker and no new admission trust
configuration. Do not upload it as though it contains this pass.
