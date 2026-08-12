# Local Intelligence Control Center

This project keeps local model artifacts, benchmark outputs, and runtime profiles outside the repository and outside the MSIX payload.

## What lives in the external model store

The control center resolves a per-user model root outside the checkout. The layout is intentionally narrow:

- `registry/`
- `artifacts/`
- `runtime_profiles/`
- `benchmark_runs/`
- `health/`
- `logs/`
- `cache/`
- `quarantine/`
- `routing/`

## Admission flow

1. Import a candidate model record.
2. Validate the model against the role catalog and admission policy.
3. Review the hardware profile and estimate the memory/disk cost.
4. Benchmark the model on local evidence only.
5. Admit it as `admitted_for_dev`, `admitted_with_limits`, or `admitted_for_production`.
6. Quarantine or reject the record if the artifact, license, privacy posture, or benchmark evidence is incomplete.

## Role and routing rules

- Generator roles may not certify legal validity.
- Certification tasks stay deterministic and cannot be self-attested by a model.
- If no admitted model is available for a task, the system falls back to deterministic rule-based routing or human review.
- Model routing always exposes the selected role, any candidate model IDs, and the fallback mode.

## Hardware profiling

The hardware profiler reports:

- operating system and architecture
- logical CPU count
- total and available memory
- free disk space under the model store
- GPU hints if they are safely detectable
- low-memory and low-disk warnings

The profiler is advisory. It should not be treated as a benchmark.

## Packaging boundaries

The source tree and MSIX payload must not contain:

- model weights
- model caches
- benchmark outputs
- registry snapshots
- quarantine artifacts
- user-private matter folders

The packaging and cleanup scripts enforce those exclusions so the release artifacts remain deterministic and reviewable.

## Failure and degraded mode

When no model is admitted, the control center should still be usable:

- list the available policy and hardware context
- show the routing fallback
- explain why the selected task stayed in deterministic mode
- keep review-required outputs visible instead of silently failing open

## Operator guidance

- Keep model artifacts outside the checkout.
- Record the artifact hash, license, privacy status, and benchmark evidence before admission.
- Prefer the smallest model that meets the role policy.
- Re-run the hardware estimate after significant storage or memory changes.
- Quarantine any record that loses provenance or fails validation.
