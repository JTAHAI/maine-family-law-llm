# v3 Constitutional UI and Interaction Requirements

## Permanent identity

The slim application bar always shows `WE THE PEOPLE` and `… establish JUSTICE …` in the normal viewport. The product name may appear nearby but may not displace the constitutional identity.

## Identity popover

Trigger mechanisms:

- pointer hover;
- keyboard focus;
- Enter or Space while focused;
- tap or click.

Content:

> Justice does not belong to one institution or one profession, it belongs to the People which these institutions of government are meant to serve; it is Public.

Closing mechanisms:

- Escape;
- outside pointer click;
- focus leaving the identity and popover;
- pointer leaving after an intentional delay;
- explicit close control on narrow or touch layouts.

## Ctrl+K command palette

The shortcut must be visible as `Commands  Ctrl+K` or equivalent. It may appear as a compact button in the top bar and as a hint near the composer on first use.

The palette is an application navigation and action layer, not a developer console. It must not show internal paths, raw runtime internals, or private metadata.

The search should accept common language and aliases, including:

- `new`, `clear`, `start over`;
- `law`, `rules`, `statute`;
- `records`, `documents`, `my case`;
- `sources`, `citations`, `proof`;
- `help`, `shortcuts`, `privacy`;
- `justice`, `constitution`, `we the people`.

## Ctrl+J Justice modal

The modal uses a locally bundled public-domain Constitution image and starts focused on `establish Justice`. The source and public-domain status must be documented with the asset.

Fallback text:

> We the People of the United States, in Order to form a more perfect Union, establish Justice…

The modal may include a restrained caption explaining that the product’s purpose is to make source-grounded public legal information more understandable while preserving human review.

## Other approved easter eggs

1. Seal: `The authority belongs to the source, not the model.`
2. Local-only indicator: `Your family’s matter stays on this device.`
3. Unsupported answer: `The record must speak before the system does.`
4. Verified source: subtle parchment-rule transition.
5. Version label: optional triple-click local build card with version, build, and source commit only.
6. Command palette term `justice`: Justice modal and Justice Lens.
7. Command palette term `people`: constitutional principles card.

## Accessibility and safety guardrails

- No information may exist only on hover.
- No command may be keyboard-only.
- The palette and modal must trap focus and restore it.
- Target size, contrast, zoom, and screen-reader announcements are required.
- Reduced motion disables decorative transitions.
- Easter eggs never hide deadlines, safety actions, source quality, privacy controls, or product limitations.
- The Constitution asset must remain local and must not cause a network request.
