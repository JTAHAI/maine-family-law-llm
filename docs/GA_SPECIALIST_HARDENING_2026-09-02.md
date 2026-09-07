# Specialist GA hardening — release remains blocked

This pass preserves product version 8.0.1. It does not admit a specialist,
claim attorney review, create production credentials, publish a release, or
represent a model-empty maintenance package as the requested two-specialist v9.

## Implemented safeguards and repairs

- Quality evidence is bound to the exact candidate pack hash and release
  fingerprint. Reports from different weights, changed fixtures, incomplete
  runs, disabled adapters, or failed worker cleanup cannot qualify a candidate.
- Package validation checks signed artifact coverage and rejects unlisted
  adapter files. Static CPU compatibility is no longer called CPU qualification.
- FP32-admitted specialists can use the CPU-only runtime on a computer that also
  has a GPU. BF16/FP16 CPU fallback remains blocked.
- The Store build environment uses pypdf 6.16.1. Security floors and the build
  gate reject the three newly identified 6.15.0 PDF-parser vulnerabilities.
  The existing large build dependency cache was not duplicated or modified.
- Unsigned MSIX submissions correctly defer package signing to Microsoft Store.
  An invalid existing signature still fails. This is separate from model
  admission and does not permit unreviewed weights to ship.
- Header Matter/Evidence controls now open a visible Workbench panel from Chat
  view, move keyboard focus into it, and return focus when it closes.
- Direct import-help questions return concise application instructions rather
  than irrelevant legal-analysis checklists.
- The model-empty optional-import path works without loading Pydantic worker
  contracts. Synthetic test credentials and authority-root fixtures no longer
  trigger unrelated production privacy guards.
- The legacy networked-source metadata report no longer independently claims
  production legal readiness from self-declared counts and review labels.
- Source preflight and the repository doctor are now read-only. They no longer
  delete caches, `.proofs`, or local runtime state before inspecting the source.
  Quarantined roots are reported without recursively scanning their contents.
- Replay-state tests now use separate registry roots for their distinct
  fictional encryption keys. The production integrity guard remains unchanged:
  wrong-key replay state still fails closed.
- Chat completion says "Response ready for review," including when record
  matches are present but the authority lane is unavailable.

## Actual UI observations

The production HTML/JavaScript was exercised through the canonical local API
with isolated, fictional data. This was **source UI**, not a frozen executable
or installed MSIX, and used no admitted specialist.

The corpus builder imported 14 fictional mixed records. In the UI, the matter
was selected, local OCR required explicit consent, and all 15 document/page
entries became searchable. Chat found the OCR notice and both fictional orders.
The source inspector rendered the original PDF page, displayed its verified
hash, hid filesystem paths, and labeled OCR limitations. A clean QA-server
shutdown/restart retained the active matter and searchable OCR index.

Comparison currently exposes matching records and their exact terms; this pass
does not certify model reasoning about those records. The OCR search card has
no admitted character-range pinpoint and correctly says so. Drafting's model
action remained disabled without an admitted model and host credential. That
is a verified safety boundary, **not functioning specialist Drafting**.

The browser verification skill drove actual controls and screenshots; it found
the hidden-drawer defect rather than treating static navigation tests as UI proof.

## Frozen-runtime observations

The full frozen 8.0.1 runtime built successfully with the patched PDF dependency.
Its startup/API/sample-workflow smoke passed; all 103 public printables resolved
with correct hashes. No unapproved specialist pack was included.

The actual frozen executable served the production UI. Fictional record search,
OCR source drill-down, PDF page rendering, Chat-to-Matter navigation, focus
return, and the unadmitted-Drafting block were exercised successfully. The first
preview attempt used the wrong QA vault for the existing encrypted fictional
matter and failed closed. Preserving that matter's original QA vault restored
rendering without a production-code change or audit bypass.

The completion-message JavaScript was refreshed in both external runtime asset
locations and retested. Release-audit utilities changed after the binary build;
this runtime is verification evidence, not the final release candidate. Both QA
processes were explicitly terminated, so graceful shutdown is not certified.
Installed-MSIX, specialist inference, and full offline qualification remain open.

## Model work and evidence

The corrected Evidence candidate completed 12,800 fictional training examples
(3,200 optimizer steps) on the RTX 3060. Its generated-answer internal regression
passed 87/87. Seven completed independent frozen suites passed only 37/88
mechanical cases. Failures include missing details and generic qualifications;
keyword failures are not automatically proof of hallucination. The eighth suite
was refused because an unrelated Ollama runner became active. It was not killed
or bypassed. Evidence is blocked, and the durable supervisor moved to Drafting's
separate correction run. Neither specialist is admitted or certified.
The corpus and worker implementation hashes remain pinned throughout.

Live status and immutable reports are under:

- `dist/model-candidates/correction-lane-20260902/lane-status.json`
- `dist/model-candidates/correction-lane-20260902/evidence_review/regression/`
- `dist/model-candidates/correction-lane-20260902/drafting/`
- `dist/qa801/ga-specialists-20260902/full-regression-readonly-isolated/summary.json`
- `dist/qa801/ga-specialists-20260902/GA_READINESS.json`
- `dist/qa801/ga-specialists-20260902/ui-smoke/`
- `dist/qa801/ga-specialists-20260902/frozen-ui-r2/`

Do not treat a low training loss, internal-template pass, successful adapter
load, or synthetic regression pass as Maine-law expertise or attorney review.

## Exact release prerequisites

1. Both new candidates pass all frozen quality suites, bound to their exact
   hashes; no failed family or old candidate report is substituted.
2. Both pass actual CPU/hardware-budget and source-UI journeys, including exact
   source drill-down, review status, cancellation, isolation, and clean shutdown.
3. Independent legal-quality evaluation and approved production model-admission
   artifacts are supplied. The production trust catalog currently has no keys;
   no test signer may be promoted to production.
4. The final source regression passes. Skipped native-engine and archived
   authority/E2E evidence checks are not counted as release proof.
5. Build one exact, admitted release; verify its frozen runtime, package privacy,
   installed/offline workflows, upgrade/rollback, and required Store checks.

All new work and QA storage stays inside this repository. External model inputs
are read-only. No new root-drive scratch directories or duplicate runtime fleets
are needed. One previously denied QA cleanup target is retained; it must not be
deleted indirectly through an ancestor or a different tool.
