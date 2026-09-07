# Evidence Review r0010: production-source E2E verification

Recorded 2026-09-01. The exact external pack
`mfl-evidence-review-research-evidence-r0010-corrective-final` is operational as
a **fictional-data research candidate**. It is not admitted for legal/client use.

## What passed

- The production-source desktop UI and canonical local API loaded a clearly
  fictional matter containing two conflicting pickup-time records.
- The user selected the exact private-record context and explicitly approved it
  before dispatch to the loopback worker.
- The real Qwen3-0.6B + Evidence Review LoRA weights loaded on CPU and completed
  with a natural stop in 49.135 seconds.
- Host verification accepted two exact source quotations and bound them to the
  approved source IDs, hashes, and character offsets.
- Unverified model narrative was withheld. The UI continued to show
  `Review required`, both source cards, source-check details, and a hash-bound
  provenance receipt.
- The exact private-record preview opened from the model response.
- The matter audit and idempotency state were encrypted. The worker remained
  authenticated and loopback-only with remote providers disabled.
- Production trust rejected the QA signer. The signer was enabled only inside
  the isolated fictional E2E harness and did not create production admission.
- Clean shutdown removed the single verified 1.56 GB runtime snapshot. Zero
  model-snapshot directories remained; retained E2E evidence was 137,821 bytes.
- Focused output-boundary, worker, source-binding, and completion-boundary tests
  passed: **98 passed, 0 failed, 0 errors** in 18.89 seconds.

Evidence is under `dist/qa801/evidence-r0010/`; that directory is ignored build
evidence rather than a model copy. The external pack was read in place and was
not modified.

## Release truth

The upstream diagnostics still mark r0010's quality gate failed. The app's
fail-closed output boundary is why this fictional E2E run was safe: only exact
verified extracts reached the visible answer and the remaining narrative was
withheld. This result proves that the adapter, canonical API, production UI,
source drill-down, verifier, encrypted audit, and cleanup path work together.

It does **not** establish substantive Maine-law accuracy, attorney review,
production admission, frozen-app reachability, installed-MSIX operation, Store
readiness, or Enterprise GA. Those gates remain blocked until the exact weights
pass independent quality review and receive production admission.
