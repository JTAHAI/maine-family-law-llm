# FAST INTERCHANGE r0002 retraining handoff

## Current decision

`mfl-fast-interchange-protocol-r0001` is not eligible for activation.  Its
seven adapters have valid hashes, load against one shared Qwen3-0.6B base, and
switch cleanly, but each failed the application backend's bounded completion
contract at both 32 and 128 generated tokens.  The worker withheld every
partial response as designed.

Evidence:

- `dist/ga_today/evidence/08_fast_interchange_development_pack_cpu_v5_completion.json`
- `dist/ga_today/evidence/08_fast_interchange_development_pack_cpu_v6_completion_128.json`

This handoff is for a new, external `r0002` development pack.  It is not
authority to treat it as a Maine-law model, create a signing key, activate a
worker, loosen a completion gate, use private matter data, or include weights
in the repository or MSIX.

## r0002 development outcome

The external `mfl-fast-interchange-protocol-r0002` pack has now met the narrow
development load/swap/generate contract.  Every one of its seven protocol and
safety adapters completed the host's fixed framing at both 32 and 128 output
tokens with a `stop` finish reason, while maintaining one resident adapter,
distinct adapter forwards, cleared context, verified artifact snapshots, and
zero permitted external downloads.  The evidence is:

- `dist/ga_today/evidence/08_fast_interchange_development_pack_gpu_r0002_completion_32.json`
- `dist/ga_today/evidence/08_fast_interchange_development_pack_gpu_r0002_completion_128.json`

This result replaces neither the r0001 failure record nor the admission
requirements below.  r0002 used only synthetic protocol/safety rows.  It has
no Maine authority or client corpus, no substantive legal-quality evaluation,
no attorney review, and no independent signed admission.  Its registry state
is deliberately `unadmitted_protocol_smoke`; the production worker refuses it
and this document does not authorize changing that policy.  A later
substantive training run must use a new release ID and preserve every boundary
below.

## Non-negotiable training boundary

- Use only an explicitly approved base-model artifact and license receipt.
- Use only rights-cleared, privacy-reviewed, non-client training rows.  The
  protocol/safety lane may use company-owned synthetic rows; substantive
  Maine-law behavior additionally requires the separately admitted authority
  corpus and evaluation process.
- Keep exactly one capability per adapter: `intake_triage`, `evidence_review`,
  `authority_review`, `drafting`, `parenting_plan_review`,
  `financial_disclosure_review`, or `safety_privacy_review`.
- Train and test with the host's fixed role framing
  `fi-fixed-role-v1:[ROLE]\\nCONTENT;join=\\n`; do not substitute an
  unrecorded chat template.
- Ensure each target includes the tokenizer's actual end-of-turn/EOS token and
  that the loss labels retain that token.  A response cut at `max_new_tokens`
  is a failure, not an acceptable short answer.
- Pass `--visible-device <physical-ordinal>` to the project-side builder when
  the parent session has hidden CUDA.  It is process-local, maps the selected
  physical device to child ordinal `cuda:0`, and records both the selected
  ordinal and device identity in the immutable training receipt.  It never
  changes the machine-wide environment.
- Train on a qualified GPU environment.  On 2026-08-29 this desktop's parent
  process had deliberately inherited `CUDA_VISIBLE_DEVICES=-1`, which makes
  Torch report zero devices even though Windows exposes an RTX 3060 and GTX
  1080.  Do **not** change the machine-wide setting: launch only the training
  child with an explicit visible-device argument (for example `0` for the RTX
  3060) and record the resulting device identity in the run receipt.  A
  process-local probe then reported the two GPUs correctly.  This removes the
  local hardware-visibility blocker; it does not remove the corpus, evaluation,
  or human-admission gates.

## Required r0002 artifacts

Keep artifacts outside this repository and outside the MSIX.  Produce a new
immutable root containing:

1. One shared base and tokenizer inventory, with SHA-256, source, revision,
   license, and approval receipt.
2. Seven adapter directories, each containing only its adapter config and
   Safetensors weights.
3. A release registry and artifact registry compatible with
   `legal.fast_interchange.worker.HotSwapRegistry`.
4. Training-run receipts with source class, dataset digest, split lineage,
   hardware, software versions, fixed framing digest, EOS-label assertion,
   and no-private-data assertion.
5. A pack manifest that continues to mark the release unadmitted and
   review-required until independent admission is complete.

Never reuse r0001 artifact hashes or release IDs for r0002.

## Required verification commands

Run from this repository with the actual r0002 root and base provenance file:

```powershell
$env:PYTHONPATH = (Get-Location).Path
& '<approved-python>\\python.exe' scripts\\verify_fast_interchange_development_pack.py `
  --pack-root '<external-r0002-pack-root>' `
  --base-provenance '<external-base-provenance.json>' `
  --output 'dist\\ga_today\\evidence\\08_fast_interchange_r0002_forward.json' `
  --allow-cpu

& '<approved-python>\\python.exe' scripts\\verify_fast_interchange_development_pack.py `
  --pack-root '<external-r0002-pack-root>' `
  --base-provenance '<external-base-provenance.json>' `
  --output 'dist\\ga_today\\evidence\\08_fast_interchange_r0002_completion_32.json' `
  --allow-cpu --exercise-completions --max-new-tokens 32

& '<approved-python>\\python.exe' scripts\\verify_fast_interchange_development_pack.py `
  --pack-root '<external-r0002-pack-root>' `
  --base-provenance '<external-base-provenance.json>' `
  --output 'dist\\ga_today\\evidence\\08_fast_interchange_r0002_completion_128.json' `
  --allow-cpu --exercise-completions --max-new-tokens 128
```

The two completion reports must each return
`PASS_DEVELOPMENT_LOAD_AND_GENERATE` for every capability.  Record hashes and
lengths only; do not retain test completion text in release evidence.

## Admission remains separate

Passing this handoff establishes only a development runtime result.  Before
the product may import or invoke a pack, require all of the following:

- independent signed admission and trusted public key;
- exact artifact, base, tokenizer, runtime, and prompt-template compatibility;
- held-out quality and safety evaluation appropriate to the asserted scope;
- source, quote, claim, privacy, filing, cancellation, and restart tests;
- explicit human release approval; and
- separately measured target-hardware performance.

The current UI and API must continue to describe an unavailable or unadmitted
pack honestly until those conditions exist.
