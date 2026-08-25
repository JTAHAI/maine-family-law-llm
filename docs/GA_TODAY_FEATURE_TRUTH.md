# Feature truth: specialized workbenches 21–44

Audit date: 2026-08-12

## Decision

All 24 specialized workbenches now have an evidence-backed `verified_end_to_end` status in the current v8 source and full-tier frozen runtime. They are publicly reachable from the shipped command palette and complete this path:

`matter service → canonical loopback API → matter-scoped encrypted store → shipped desktop UI → meaningful fictional action → exact-source inspector → review-required result → focused tests → frozen-runtime reachability`

This status does not assert attorney validation, legal advice, a jurisdictional decision, automated filing, or that Microsoft has already distributed this exact post-release source revision.

## Feature status

| Slice | Specialized workbench | Meaningful verified action | Status |
|---|---|---|---|
| 21 | Matter intake, posture, and issue tree | Create/resume intake and retain unknown/disputed posture and issue sources | `verified_end_to_end` |
| 22 | Operative orders and supersession | Record exact terms and compare an amendment without deciding which order governs | `verified_end_to_end` |
| 23 | Service, notice, deadlines, and hearings | Create a source-bound event, rule, and review-required deadline candidate | `verified_end_to_end` |
| 24 | Docket/MRECS reconciliation | Import a fictional docket entry and compare it with a local record | `verified_end_to_end` |
| 25 | Discovery/disclosure | Map a request, partial production, and missing-response gap | `verified_end_to_end` |
| 26 | Exhibits and provenance | Create a candidate, derivative label, numbering, binder, and receipt | `verified_end_to_end` |
| 27 | Witness/statement comparison | Compare two source-bound statements without credibility scoring | `verified_end_to_end` |
| 28 | Hearing preparation | Assemble a hearing issue with authority, evidence, missing proof, and pack | `verified_end_to_end` |
| 29 | Appellate preservation | Verify a record citation and expose missing record components | `verified_end_to_end` |
| 30 | UCCJEA interstate review | Display conflicting state connections without deciding jurisdiction | `verified_end_to_end` |
| 31 | ICWA inquiry and notice review | Record documented inquiry/notice without inferring child status | `verified_end_to_end` |
| 32 | Guardianship/adoption/probate pathways | Create a source-bound care-pathway record and review gaps | `verified_end_to_end` |
| 33 | Protection and safety records | Organize a source-bound safety record without external contact | `verified_end_to_end` |
| 34 | Parenting schedule/logistics | Create an exact order term and neutral schedule scenario | `verified_end_to_end` |
| 35 | Mediation/negotiation | Create and compare source-bound proposals | `verified_end_to_end` |
| 36 | Property/debt/valuation | Record a valuation candidate while leaving characterization and division undetermined | `verified_end_to_end` |
| 37 | Modification circumstances | Record source-bound change candidates without determining materiality | `verified_end_to_end` |
| 38 | FOAA requests | Create a local request draft without sending it | `verified_end_to_end` |
| 39 | Filing/MRECS readiness | Validate a package and expose blockers without filing | `verified_end_to_end` |
| 40 | Image evidence | Record immutable image provenance and derivative status | `verified_end_to_end` |
| 41 | Email integrity | Record header, attachment, and export hashes | `verified_end_to_end` |
| 42 | Reviewer handoff | Create an encrypted local handoff manifest and receipt | `verified_end_to_end` |
| 43 | Language access | Create a review-required accessible working copy | `verified_end_to_end` |
| 44 | Resource navigator | Record a verified resource candidate without automatic contact | `verified_end_to_end` |

## Production controls

- The authoritative frontend is `src/maine_family_law_llm/ui`; `maine_family_law_llm/ui` remains byte-identical.
- Every slice route is reachable through `app.api.production:app` and receives a server-generated audit event ID plus the local-desktop reviewer role envelope.
- Specialized route responses enforce `local_only: true` and `review_required: true`.
- Private stores are encrypted under the active matter. Exact source opening uses an opaque, short-lived capability and exposes a safe locator—not a filesystem path.
- The command palette exposes 24 specialized entries. No environment override is required.
- The command palette also exposes 10 Matter Productivity Studio entries backed by the canonical `/api/productivity` and hearing-media routes.
- Productivity state is matter-scoped and AES-GCM encrypted; every mutation appends a hash-chained audit event and remains review-required.
- The ten capabilities perform meaningful local actions: manifest review, confirmed recipes, media transcription, ICS export, hardware planning, exact-source pinning, redaction review, corrective action queues, source-bound presentation, and encrypted backup/isolated restore.
- The frozen full-tier v8 executable contains both production UI asset copies and all 24 command markers.

## Verification results

- Python compilation: passed.
- Production and mirror JavaScript syntax: passed.
- Focused acceptance, accessibility, production UI, and packaging suite: **103 passed**.
- Dedicated UI/contrast regression subset: **35 passed**.
- Production-browser journey: passed on a fictional matter, including exact-source hash verification and a persisted source-bound property item with append-only history.
- Frozen-runtime smoke: passed (launch, local API, fictional workflow, external-data boundary, packaged assets).
- Frozen specialized route reachability: **24/24** accepted features; 23 inventory routes plus intake creation, all local-only, review-required, audited, and role-enveloped.
- Frozen production command inventory: **24/24** entries present.
- Adaptive layout: chat width increased from **908 px** to **1,202 px** after hiding shortcut cards and to **1,566 px** after hiding both supporting rails at a 1600 px viewport; state persisted after reload.

## Evidence

- `dist/ga_today/evidence/02_feature_truth_manifest.json`
- `dist/verified-workbench-runtime/evidence/store-build-smoke.json`
- `dist/verified-workbench-runtime/evidence/specialized-feature-reachability.json`
- `dist/verified-workbench-runtime/evidence/focaf-runtime-asset-audit.json`

No specialized feature remains hidden or disabled in the current accepted source scope. Additional non-slice source capabilities retain their existing qualification status.

## Add-on Studio acceptance (capabilities 55–74)

The Add-on Studio adds twenty tenant- and matter-scoped local tools behind the canonical `/api/addons` route family. All twenty have a shipped command-palette entry, guided production UI action, role enforcement, AES-GCM state and artifacts, hash-chained audit history, review-required result, exact-result and artifact drill-down, and an immutable human review decision.

- Capabilities 55–74: `verified_end_to_end` through service, canonical API, rendered production UI, fictional user action, exact result, immutable review, focused tests, and fresh essential-tier frozen executable.
- Capability 55 uses bundled, SHA-256-pinned whisper.cpp 1.9.2 and a compact English model. A fictional WAV completed through the source and frozen production UI with timestamped segments and no runtime download.
- Rendered source and frozen UI: 20/20 meaningful tool actions, 20/20 exact-result inspections, 20/20 immutable review decisions, artifact drill-down, and integrity verification passed.
- Responsive UI: no horizontal body overflow at 800×720 and the primary action remained visible.

The authorized 8.0.0 gate is satisfied. Product version 8.0.0 and package target 8.0.0.0 are frozen; MSIX packaging, installation, WACK, and Store publication remain separate qualification steps.
