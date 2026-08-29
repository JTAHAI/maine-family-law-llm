# FAST INTERCHANGE local-worker connector

Maine Family Law LLM can use an optional, separately operated FAST INTERCHANGE worker on a literal loopback address. This connector is off by default. It does not start a worker, download a base model, install adapters, train a model, or package model artifacts.

The connector sends a fixed, non-streaming completion request only after the application's existing exact-context preview and approval path succeeds. It sends no tool request, accepts no caller-supplied artifact path or adapter identifier, and requires a model identity that the external worker has already admitted. The worker token must be set only in the host process environment as `MAINE_FAST_INTERCHANGE_WORKER_TOKEN`; it is never entered in the UI, saved in browser storage, returned by an API, written to an evidence receipt, or included in an MSIX package.

## Current fleet status

The seven planned adapter roles are intake, evidence, authority, drafting, parenting, financial, and safety/privacy review. Their public plan is in [fast_interchange_model_fleet.json](../configs/fast_interchange_model_fleet.json). Every slot is `specified_untrained`; no base, corpus, adapter, registry, release, benchmark, or legal-performance claim is bundled or implied.

## Operator boundary

An operator must separately supply a local worker, a 32-byte-or-longer worker secret, an admitted release-model ID, artifact/license provenance, and evaluation evidence. The expected default endpoint is `http://127.0.0.1:8105`, but it must remain a literal loopback IP. The connector fixes sampling to temperature `0`, top-p `1`, maximum output `1024`, and `stream: false`.

The connector remains review-required and cannot certify law, evidence, claims, filing readiness, or a model release. If the worker is unavailable, missing its host-only secret, rejects the release-model ID, returns a different identity, or returns an incomplete result, the run fails closed.

## Provenance boundary

LEGAL FAST INTERCHANGE is the authorized family-law successor for the portions being open sourced. Mainely Code remains proprietary and is not imported, bundled, connected to, or represented by this connector. This repository contains a native, model-empty FAST INTERCHANGE-compatible worker implementation, a clean connector, and a public untrained fleet specification. It does not carry copied Mainely Code source, weights, datasets, adapters, credentials, or training material. The file-level boundary is recorded in [PROVENANCE.json](../legal/fast_interchange/PROVENANCE.json).
