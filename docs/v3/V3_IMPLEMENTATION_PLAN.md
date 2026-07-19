# Maine Family Law LLM v3.0.0 Implementation Plan

## Product promise

v3.0.0 is a calm, local-first family-justice navigator. The chat is the primary experience. Advanced controls, source inspection, and reviewer detail remain available through progressive disclosure rather than permanent dashboard clutter.

The product must help a parent, caregiver, child-serving professional, or reviewer understand:

1. what the question appears to involve;
2. what needs attention now;
3. what the next three practical steps are;
4. what information or records are missing;
5. what the answer may mean for a child’s safety, stability, routines, health, school, and relationships;
6. which statements are supported by Maine legal authority;
7. which statements come from the user’s private records; and
8. when human legal, court, advocacy, clinical, or emergency help is appropriate.

It must not rank parents, predict custody outcomes, diagnose adults or children, encourage retaliation, coach children, or turn unsupported allegations into facts.

## Non-negotiable constitutional identity

The normal application view must permanently display:

**WE THE PEOPLE**

**… establish JUSTICE …**

The bar may be slim, but this language may not be hidden in a menu, splash screen, About page, tooltip, or collapsed drawer.

Hover, keyboard focus, or tap on the identity opens an accessible popover containing:

> Justice does not belong to one institution or one profession, it belongs to the People which these institutions of government are meant to serve; it is Public.

The popover must close with Escape, outside click, pointer departure after a short delay, or focus departure. It must use accessible relationships, remain readable at 200% zoom, and never cover the composer.

## Approved keyboard interactions

### Ctrl+K — Command palette

Ctrl+K opens the command palette. A visible shortcut hint must appear in the slim top bar or composer so users do not have to discover it accidentally.

The palette must support:

- type-to-filter;
- Up/Down navigation;
- Enter to run;
- Escape to close;
- focus trapping and focus restoration;
- commands grouped by Conversation, Research, Matter, Evidence, View, Help, and Safety;
- plain-language labels rather than developer terminology;
- touch-accessible opening through a visible Commands button; and
- no critical feature available only through the palette.

Initial command set:

- New conversation
- Focus the message box
- Research Maine law
- Search my records
- Search both separately
- Open or close evidence drawer
- Open source list
- Choose matter
- Change answer style
- Open Help
- Open privacy information
- Open keyboard shortcuts
- Open Justice Lens

### Ctrl+J — Justice easter egg

Ctrl+J opens an accessible modal titled **You found the Justice key**. It displays a locally bundled public-domain image of the United States Constitution, cropped or initially zoomed to the phrase **establish Justice**.

The modal must:

- work by keyboard, touch, and visible command-palette entry;
- close with Escape, a close button, or outside click;
- restore focus;
- include useful alt text and a text-only fallback;
- avoid remote assets;
- respect reduced motion and high contrast; and
- contain no safety-critical or legal functionality that exists only as an easter egg.

The proximity of J to K is intentional: a mistyped command-palette shortcut should lead to a small moment of civic delight rather than an error.

## Constitutional delight system

Easter eggs must reinforce public service, source transparency, privacy, dignity, and restraint.

Approved candidates:

- Seal hover/focus: **The authority belongs to the source, not the model.**
- Local-only hover/focus: **Your family’s matter stays on this device.**
- Verified-source opening: a restrained parchment-rule or engraved-light transition.
- Command palette query `we the people`: surfaces **Open constitutional principles**.
- Command palette query `justice`: surfaces the Ctrl+J modal and Justice Lens.
- Empty unsupported answer: **The record must speak before the system does.**
- Triple-clicking the visible version label may reveal a small local build card, but never hidden diagnostics containing private paths.

Every easter egg must have keyboard and touch parity. No deadline, source status, safety warning, privacy control, or legal limitation may be hidden as an easter egg.

## Current implementation status

- **Pass 0 — complete:** the canonical v2.09.2 rollback baseline was reconciled and the v3 interaction requirements were captured.
- **Pass 1 — complete:** the product is now versioned as **3.0.0**, MSIX build **3.0.0.1**, and the browser workbench is split into packaged HTML, CSS, JavaScript, and local SVG assets.
- To fix the immediately visible UI/UX defects in the approved screenshots, Pass 1 deliberately pulled forward the visible shell portions of Pass 2 and Pass 3: the oversized hero is now a slim permanent constitutional bar; the permanent right rail is now a closed evidence drawer; the duplicate answer dashboard was removed from the main view; the composer is compact; and Ctrl+K/Ctrl+J are working interactions.
- **Pass 2 — complete:** the slim constitutional bar now includes full accessible popover controls, privacy and matter affordances, local-status disclosure, complete grouped command coverage, keyboard-shortcut help, and restrained civic easter eggs.
- Pass 3 remains open for deeper evidence-drawer, source-lane, composer, and responsive chat refinement.
- Microsoft Store packaging, frozen-runtime smoke, and WACK must be rerun on Windows before any v3 release claim.

## Pass sequence

### Pass 0 — Baseline reconciliation

- Establish one canonical repository tree.
- Preserve the unmerged v2.14.0 nested worktree as a separate reference archive.
- Remove nested-repository ambiguity from the canonical tree.
- Repair stale tests that still require the deleted context pill bar.
- Capture the approved v3 UX, constitutional identity, Ctrl+K, and Ctrl+J requirements as machine-readable contracts.
- Preserve v2.09.2 / MSIX 2.9.2.0 as the rollback baseline.

### Pass 1 — v3 UI architecture

- Split the monolithic embedded UI into local templates, CSS, JavaScript, components, and contracts.
- Keep a compatibility renderer while the migration proceeds.
- Add strict local asset serving and content-security policy.
- Begin product version 3.0.0 with an incrementing build component.

### Pass 2 — Slim constitutional bar

- Replace the large hero with a compact permanent identity bar.
- Implement the mission popover.
- Add visible Ctrl+K shortcut hint.
- Add compact privacy, matter, health, Help, and New conversation affordances.

### Pass 3 — Chat-first shell and command palette

- Remove the permanent dashboard rail.
- Add contextual evidence drawer.
- Remove duplicate Latest answer presentation.
- Implement Ctrl+K command palette.
- Add responsive composer controls for Maine law, My records, and Both.

### Pass 4 — Need-first guided entry

- Ask what happened before asking the user to classify a role.
- Add pathways for service, hearings, safety, orders, parenting, support, evidence, and uncertainty.

### Pass 5 — Structured family answer contract

- What this means
- What to do now
- Next three steps
- What to gather
- Missing information
- Child and family considerations
- Maine-law support
- Private-record support
- When to get human help

### Pass 6 — Child Impact Lens

- Surface safety, stability, routines, school, health, communication, transitions, and missing information.
- Prevent ranking, diagnosis, coaching, and weaponized language.

### Pass 7 — Family-preserving practical tools

- Child-focused message rewrite
- Parenting-plan preparation
- “What can I say to my child?” support
- One-page family handoff

### Pass 8 — Safety, privacy, and deadline shield

- Safety interrupt
- Privacy shield
- Deadline verification
- Served-paper and hearing preparation
- Versioned official help resources

### Pass 9 — Documents in chat

- Local drag-and-drop
- Page-level extraction
- Missing-page and OCR uncertainty
- Explicit add-to-matter action

### Pass 10 — Trustworthy authority experience

- Inline Law and Record markers
- Exact supporting snippets
- Freshness and official-source status
- Clear explanation of what each source does and does not prove

### Pass 11 — Accessibility and cognitive-load completion

- Keyboard, screen reader, high contrast, zoom, reduced motion, reading width, and plain-language completion
- Full parity for popovers, command palette, modals, drawers, and easter eggs

### Pass 12 — Real-family validation and release gate

- Test with self-represented parents, caregivers, attorneys, legal-aid/court-help staff, advocates, clinicians, and accessibility reviewers using fictional matters only.
- Measure time to first useful step, law-versus-record comprehension, uncertainty comprehension, accessibility completion, and whether the experience feels calm and non-blaming.
