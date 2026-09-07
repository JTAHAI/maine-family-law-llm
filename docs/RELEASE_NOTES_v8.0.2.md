# Maine Family Law LLM 8.0.2

Maintenance release candidate, package version 8.0.2.0, build 55. This advances
the installed 8.0.1.0 version without changing the Microsoft Store identity,
publisher, x64 architecture, en-us language, or matter-storage schema.

## What's new in this version

- Improved chat layout, text readability, collapsible panels, and keyboard navigation.
- Chat starts with Both sources selected and Child Impact Lens enabled.
- Clearer source availability, review-required notices, and recovery guidance.
- Fixed private-record chat failing when the optional authority library is unavailable.
- Stronger protection for local requests, private source excerpts, and model approvals.
- More reliable cancellation, matter switching, and local model hardware checks.
- Packaging and startup reliability fixes for the Windows desktop app.

Newly trained Evidence Review, Drafting, and other research specialist models are
not included in this update. They have not met the required quality and admission
gates. Existing model import remains subject to integrity, compatibility, license,
and admission checks; the app does not automatically download models.

Legal work remains review-required. Official-source research requires an approved
local authority collection. An empty installation must show setup guidance rather
than fabricate source-backed answers. This release does not claim attorney
approval or Enterprise certification.

## Qualification

Current build, regression, frozen-runtime, package audit, installation and WACK
results must be read from `dist/store/evidence/` and the current maintenance
qualification receipt under `dist/ga-closure/store-802/`. This document is not
proof of successful certification. Do not infer qualification from the version.
