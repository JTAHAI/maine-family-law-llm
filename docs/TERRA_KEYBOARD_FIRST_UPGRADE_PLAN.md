# Keyboard-First Upgrade Plan for Terra

## Purpose

Make Maine Family Law LLM easier for a self-represented parent or trusted
supporter to use at a stressful moment. This plan deliberately favors fewer,
clearer choices over more workspaces. It is an implementation queue, not a
claim that any listed feature is released, legally current, attorney reviewed,
or model-qualified.

## Review findings

The current workbench has a strong local/privacy posture, source cards,
review-required states, a default Chat view, and a collapsible evidence drawer.
However, it exposes a very large amount of operational and governance UI in
one HTML/JS surface (the current workbench is roughly 220 KB HTML and 1.4 MB
JS). A person asking a simple question can encounter corpus controls,
authority-update controls, model pack management, admin policy flows, and
advanced review tools before they understand the next safe action. The next
upgrade should reduce cognitive load without hiding safety information or
weakening any existing matter, audit, role, encryption, or filing gate.

## Mandatory vertical-slice contract

For every slice, Terra must deliver all applicable pieces in the same batch:

1. A narrow service and a single canonical API route family.
2. Active-matter, tenant, role, encryption, and append-only audit enforcement
   before a private read or write.
3. A production UI entry in the canonical `src/maine_family_law_llm/ui`
   assets and the required mirrored assets, with no dead navigation.
4. One meaningful fictional user action and source/artifact drill-down.
5. Visible review-required, blocker, and recovery states.
6. Focused service/API, matter-isolation, UI-entry, keyboard, and no-private-
   data tests; rebuild/frozen reachability when the shipped asset changes.

Do not put a placeholder button in the public UI. Keep unavailable authority,
unadmitted model, attorney-review, pilot, Store, and Enterprise states visibly
blocked. Do not copy client data, authority stores, weights, indexes, logs, or
build scratch into the repository or package.

## Batch 1 — Calm first five minutes

### Slice K1: Situation-first start screen

Replace the initial wall of controls with four plain-language starts: “I have
court papers,” “I need to understand a Maine family-law question,” “I want to
organize records,” and “I am worried someone may be unsafe.” Each start must
explain what it will and will not do, preserve Local-only and review-required
status, and take the user to a reversible next step.

Acceptance: keyboard-select each start with a fictional profile; no private
files are read before explicit selection; the browser/frozen route has no
console errors; source and review status remain visible.

### Slice K2: Matter context that makes sense

Show one concise, persistent context chip: current matter name, whether it is
General Maine Law or a private matter, record count, and review status. A
single “Change” control opens the scoped picker. Wrong-matter operations must
fail closed and return focus to the picker with a plain-language recovery.

Acceptance: create/select two fictional matters, attempt a cross-matter
action, verify denial/audit/no data disclosure, then return to the previous
chat location.

### Slice K3: One next-safe-action card

Add a context-sensitive card at the top of Chat containing exactly one primary
next action and at most two alternatives. It may recommend import, ask,
inspect source, or review a blocker; it must never recommend a legal outcome
or filing. The rationale must be sourced from current UI state, not model text.

Acceptance: empty matter, OCR-pending matter, source-backed answer, and
blocked draft each display an honest next action and no false green state.

### Slice K4: Progressive disclosure and beginner mode

Move model-pack management, authority update, governance, diagnostics, and
other operator tooling behind an explicit “Advanced local controls” entry.
Remember only a local preference, not matter content. The default chat view
must stay useful with the side rails collapsed.

Acceptance: default layout has no clipped primary control at 1280×720 and
200% zoom; opening/closing Advanced controls preserves chat draft/focus; no
operator route becomes accessible by a hidden keyboard shortcut alone.

## Batch 2 — Ask, understand, verify

### Slice K5: Better question composer

Turn the composer into a short guided prompt with optional context chips:
“what happened,” “what document,” “what is most urgent,” and “what would help
next.” It must accept free text without forcing a template and display the
selected retrieval lane as Both by default with Child Impact Lens on.

Acceptance: submit a free-text fictional question and a chip-assisted
question; both preserve the selected lane and show the same review boundaries.

### Slice K6: Answer anatomy

Render each response in stable sections: plain answer, what supports it,
what is uncertain, and next safe step. Source cards are separate from model
analysis. If no admitted authority exists, the answer must say so and avoid
“current Maine law” language.

Acceptance: official, private-record, mixed, missing-source, and unavailable-
authority fixtures produce the correct lane labels, exact source controls, and
review marker.

### Slice K7: Ask-to-source shortcut

Make every cited source or record reachable by keyboard and pointer from the
response. The inspector must show title/type, hash, freshness/OCR limitation,
exact span if admitted, and a safe statement when no exact span exists.

Acceptance: open and close a fictional scanned-PDF preview, DOCX preview, and
unavailable exact span; focus returns to the originating citation each time.

### Slice K8: Answer correction without blame

Add “This does not look right” beside the answer. It records a non-mutating,
matter-scoped correction receipt, offers source/wording/context reasons, and
runs the existing verifier rather than silently overwriting an answer.

Acceptance: correct a fictional answer, inspect its audit/source receipt,
reopen the matter, and show that the original remains intact.

## Batch 3 — Records that feel safe and understandable

### Slice K9: Import readiness and consent

Before a scan/import, show file count, estimated local space, supported types,
what will be created, and whether OCR is needed. Use a single explicit
consent control. No path or filename leaks into status/error text.

Acceptance: fictional PDF/DOCX/email import, oversized file, malformed file,
and cancellation all show preserved state and an actionable next step.

### Slice K10: Record inventory in human language

Present duplicate, changed copy, unreadable, OCR-pending, and missing-
attachment findings as a short review queue. Each item must state the exact
record relationship and offer inspect/keep/review, never silently deduplicate.

Acceptance: exact duplicate, changed copy, scanned PDF, and missing attachment
fixtures all produce source-bound, review-required entries.

### Slice K11: Timeline and conflict review

Give users a single timeline view with “needs review” event clusters.
Correcting a date must create an append-only candidate with source links—not
rewrite the record or decide whose account is true.

Acceptance: conflicting fictional dates, source drill-down, correction,
history reopening, and cross-matter denial.

### Slice K12: Evidence coverage map

Show what the matter has, what may be missing, and why it matters in ordinary
language. The map must distinguish a missing file from a missing fact and an
allegation from a finding.

Acceptance: fixture with partial discovery, missing attachment, and disputed
claim; no result labels an allegation a finding.

## Batch 4 — Draft without accidental filing

### Slice K13: Drafting start from selected support

Start a draft only from a selected purpose plus verified source/evidence items.
Show the exact input scope before generation and preserve an empty working
draft when the user cancels.

Acceptance: create a fictional review-required draft; verify source receipt,
scope, cancellation, restart, and no external request in Local-only mode.

### Slice K14: Claim and citation blocker panel

Replace generic warnings with a compact table: unsupported factual claim,
unsupported legal claim, stale/unknown authority, contradiction, missing
field, and human review. Each row has a precise drill-down and correction
action. No “ready to file” visual state can coexist with a blocker.

Acceptance: adversarial fixture has zero false passes through the canonical
filing gate and through every public alias/export action.

### Slice K15: Revision review that non-lawyers can use

Offer “What changed?” first, with grouped plain-language changes; keep full
tracked review and DOCX export as optional detail. Maintain original/working
copy distinction and source-linked rationales.

Acceptance: compare two fictional revisions, undo a proposed edit, reopen,
and export a review-only copy with provenance.

### Slice K16: Forms guidance, not form completion theater

Show a form’s source, version/freshness, prerequisites, fields still needing
human input, and explicit stale warning. A stale form blocks final-like export.

Acceptance: stale and current fictional form fixtures differ visibly; no form
is represented as court-filed or legally complete.

## Batch 5 — Prepare for the next real-world interaction

### Slice K17: Court-day checklist

Create a low-stress, printable, matter-scoped checklist from selected records,
hearing information, accessibility needs, and open blockers. It is a planning
aid, not legal advice or a predicted outcome.

Acceptance: fictional hearing with missing proof creates a review-required
checklist and receipt; no real contact details are required.

### Slice K18: Parenting-plan logistics preview

Provide a calendar-like, neutral schedule preview that highlights exchanges,
school/holiday conflicts, and unanswered details without deciding custody or
best interests. Keep Child Impact Lens visibly on by default.

Acceptance: fictional conflicting dates and schedule entries surface as review
items with no jurisdictional or legal conclusion.

### Slice K19: Communication helper

Offer brief, neutral, child-focused message templates based only on user-
entered text. Flag escalation/safety wording and never send messages or
contact anyone.

Acceptance: fictional neutral, hostile, and safety-sensitive messages get
clear boundaries; source/record text is not logged or leaked.

### Slice K20: Resource handoff

Show verified, locally bundled resource categories (safety, court help,
accessibility, mediation) with a clear “this is not legal representation”
boundary. External links must be opt-in and labeled before navigation.

Acceptance: no-network mode shows local guidance; an external link requires a
deliberate user action and does not carry private matter data.

## Batch 6 — Accessibility and resilience as primary workflows

### Slice K21: Keyboard journey certification

Certify complete keyboard paths for starting a matter, asking, opening a
source, opening/closing a drawer or dialog, starting/cancelling import, and
reviewing a draft. Repair traps, tab-order jumps, and focus loss.

### Slice K22: Readability controls

Add a compact reader control for text size, line spacing, high contrast, and
reduced motion. Save locally without including any matter content. Validate
at 200% zoom and Windows forced colors.

### Slice K23: Plain-language error contract

Every critical error must contain: what happened, what was preserved, scope,
safe error ID, one recovery action, and optional technical detail. Prohibit raw
paths, record text, prompts, secrets, or stack traces.

### Slice K24: Long-job center

Consolidate import/OCR/index/model-pack tasks into a visible job center with
start time, phase, measurable progress, cancel, partial result, retry rule,
and matter scope. It must not expose private input/result text.

Acceptance for K21–K24: keyboard-only, screen-reader semantic, zoom/overflow,
reduced-motion, cancellation, restart, and privacy tests in source and frozen
runtime.

## Batch 7 — Local AI that people can trust

### Slice K25: Hardware readiness explanation

Before a local model pack is considered, provide a read-only device check:
CPU/RAM/GPU/VRAM/disk/runtime availability, what is measured, and which
capability it affects. Do not collect hardware telemetry or make a model-
quality claim from capacity alone.

### Slice K26: Specialist availability card

Replace technical model controls in normal Chat with one card: unavailable,
research-only, admitted, or active; task capability; expected local impact;
and why it is blocked. Only an admitted, signed pack may be selectable.

### Slice K27: Safe model switching

For an admitted pack only, show the selected specialist, clear prior task
context, load status, local timeout, cancel, fallback, and an immutable
receipt. The default response remains review-required and source-bound.

### Slice K28: Model quality transparency

Show release ID, capability, evaluation basis, known limitations, admission
status, and exact reason research models are unavailable. Never show synthetic
tests as attorney review or label a generic base model a Maine-law expert.

Acceptance: unadmitted Evidence/Drafting packs remain blocked end-to-end;
fake signature/manifest fails closed; admitted-pack test fixture proves the
full UI/API lifecycle without importing real weights into the repository.

## Batch 8 — Release discipline and supportability

### Slice K29: Release-scope truth manifest

Generate public feature wording from an evidence-backed manifest. A feature
can be advertised only after a current service/API/UI/frozen result; hidden,
experimental, and unavailable features are excluded automatically.

### Slice K30: One-button fictional self-check

Provide a disposable, clearly fictional local self-check that exercises
launch, matter, import, source preview, draft blocker, cancellation, restart,
and no-network result. It must not alter user matters or claim legal quality.

### Slice K31: Safe support bundle

Create an opt-in support receipt containing only release/environment hashes,
safe error IDs, and user-selected non-private diagnostics. Preview it before
export; never include matter records, paths, prompts, logs, credentials, or
authority data.

### Slice K32: Final release gates

Automate current source compile/collection/regression, package privacy audit,
frozen core journey, local-only network capture, accessibility critical path,
and MSIX install/rollback when the environment supports it. Report missing
human/legal/WACK/pilot evidence as blockers, never as passes.

## Execution order and batch exit criteria

Run batches in order. Do not start the next batch while the current batch has
a P0/P1 failure, a dead public UI entry, a broken source/mirror pair, a
cross-matter/privacy failure, or a release-test regression. At each batch exit
create one compact evidence receipt under `dist/qa801/evidence/` containing:

- changed production files and canonical routes;
- fictional scenario IDs only;
- exact tests/commands/counts/duration;
- source/frozen/MSIX level achieved;
- user-visible limitations and blockers;
- SHA-256 hashes for artifacts.

The final release decision remains separate from development progress. It
requires current package evidence and every external prerequisite actually
present; it cannot be achieved by styling a blocked feature as complete.
