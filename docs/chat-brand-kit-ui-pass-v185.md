# Pass v1.85 — FOCAF brand-kit UI integration

This pass makes the local browser workbench visibly branded and easier to verify during local testing.

## Changes

- Added the provided `FOCaF Maine Family Law LLM` brand kit as first-class repo files under `assets/brand/focaf_family_law_llm_brand_kit/`.
- Mounted local brand assets at `/brand-assets` when the FastAPI workbench starts from the repo.
- Wired favicon, manifest, design-token CSS, theme CSS, logo mark, horizontal logo, and social-card artwork into the served local workbench.
- Reworked the top of the workbench into a more polished FOCAF branded hero shell.
- Added runtime diagnostics showing whether brand assets are mounted.
- Kept Enter-to-submit behavior and the v1.84 appeals routing regression coverage.
- Added v1.85 tests for brand asset presence, UI markers, runtime diagnostics, and static asset serving.

## Safety / claims

The UI remains legal-information-only, source-backed, review-required, and not filing-ready. This pass does not claim attorney review, legal signoff, real-matter pilot, production GA, or filing-ready output.
