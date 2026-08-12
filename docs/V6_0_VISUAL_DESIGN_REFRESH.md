# v6.0 Visual Design Refresh

## Decision

Refresh palette, typography, spacing, surfaces, icon treatment, states, and micro-interactions while preserving the proven v5 workflow architecture.

## Non-negotiable boundaries

- No navigation or workflow rewrite.
- No control IDs or API paths removed.
- Local-only and review-required states remain prominent.
- No remote font, theme, analytics, or asset dependency.
- Existing accessibility, privacy, source, and evidence behavior remains intact.
- Historical v5 CSS selectors remain available for compatibility; the v6 body scope overrides their visual tokens.

## Palette intent

- **Atlantic:** institutional trust and primary dark surfaces.
- **Pine:** primary actions, focus, and local-first state.
- **Tide:** links and informational accents.
- **Warm paper:** reduced glare for long-form legal review.
- **Gold:** careful emphasis and release identity.
- **Berry:** danger and blocker emphasis without relying on red alone.

The canonical machine-readable policy is `configs/maine_v6_visual_design_policy.json`.
