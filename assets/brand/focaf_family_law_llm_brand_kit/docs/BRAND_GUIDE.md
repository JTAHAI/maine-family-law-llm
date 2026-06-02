# FOCaF Maine Family Law LLM Branding Guide

Version: 1.0  
Prepared for: Maine Family Law LLM / For Our Children & Families  
Generated: 2026-06-02

## Brand position

**Maine Family Law LLM** should feel like a calm, local, source-backed research workbench that belongs under the **For Our Children & Families** public-service umbrella. It should not feel like a law firm, a court portal, a campaign funnel, or a private case intake system.

Core promise:

> Local source-backed Maine family-law research, organized carefully, with review required before reliance.

Use these recurring trust phrases in the UI:

- Local source-backed
- Review required
- Not legal advice
- No private case intake
- For planning and research only
- Source cards first, conclusions second

## Logo concept

The special mark combines four ideas:

1. **A calm Maine-blue shield** for safety and public trust.
2. **A pine/river lightning form** for Maine, guidance, and fast local search.
3. **Two family dots under a protective arc** for child-first relationship stability.
4. **Stacked source cards/chat bubbles** for retrieved-source answers and reviewer handoff.

Avoid gavels, courtroom scales, aggressive shields, police-style badges, or anything that implies legal representation.

## Color palette

| Token | Hex | Use |
|---|---:|---|
| Ink Navy | `#07131F` | App background and dark shell |
| Deep Ocean | `#0C1D2B` | Header and page background |
| Harbor Panel | `#10283A` | Primary cards and panels |
| Harbor Panel 2 | `#153447` | Raised answers and source cards |
| Blue Spruce | `#285A7A` | Maine public-service blue, borders, secondary UI |
| River Teal | `#23D3C1` | Primary action, online status, active states |
| Sea Glass | `#8DECE2` | Highlights, focus rings, microcopy |
| Warm Paper | `#F6F1E7` | Light mode and printable materials |
| Soft Cream | `#FFF9EC` | Light notices and readable disclaimers |
| Review Gold | `#F6C96D` | Reviewer required / uncertainty |
| Safety Coral | `#FF8A7A` | Safety flags only |
| Pine Green | `#3EA97C` | Support-first/stability cues |

## Typography

Default to system fonts so the local/offline app does not depend on external font calls.

```css
--focaf-font-sans: Atkinson Hyperlegible, Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
--focaf-font-serif: Charter, Georgia, Cambria, "Times New Roman", serif;
--focaf-font-mono: "Cascadia Code", SFMono-Regular, ui-monospace, Consolas, "Liberation Mono", monospace;
```

Use the sans stack for almost everything. Use the serif stack only for formal source excerpts or statutory quotation blocks. Use mono only for IDs, JSON, citations, and manifest/debug details.

## UI tone

Write like a public-service research assistant:

- Clear before clever.
- Source-backed before persuasive.
- Calm before urgent.
- Reviewer-aware before confident.
- Support-first before court-first.

Do not use language like “winning custody,” “beat the other side,” “legal strategy engine,” or “case predictor.”

## App structure

Recommended top-level layout:

- Left / main column: ask form, conversation, latest answer, reviewer handoff.
- Right column: source library, prompt packs, source cards, source inspector.
- Header: brand mark, product name, local-AI status, no-intake/legal boundary.
- Footer: version, source manifest, health, topic JSON, starter packs JSON, no-private-intake reminder.

## Card styles

### 1. Legal notice card
Use warm gold border and dark translucent fill. This should appear above the question box.

Text pattern:

> This tool provides Maine family-law research from retrieved source snippets. It does not create an attorney-client relationship, does not replace review by a qualified professional, and does not accept private case intake.

### 2. Answer card
Use raised harbor panel, teal meta chips, and clear answer/review sections.

Required answer metadata chips:

- source grounded
- context used / no context used
- checklist / explanation / letter / script
- review required
- source count

### 3. Source card
Use compact raised cards with source type, title, effective date/status, excerpt, and two buttons: **Copy source card** and **Inspect source**.

### 4. Reviewer handoff card
Use review-gold accent. It should never look like an error; it should look like a safe professional checkpoint.

Include:

- Missing information
- Follow-up questions
- What a reviewer should verify
- Matched intent / topic / source count

### 5. Prompt chips
Rounded pill buttons. Keep text short. Use action labels that sound helpful and non-adversarial.

Good examples:

- Best-interest factors
- Parent contact schedule
- Child support checklist
- Organize evidence
- Missing-info checklist
- Served papers

## Accessibility

- Minimum visible focus ring: teal outer ring plus dark/white separation ring.
- Never rely on color alone; pair status color with text labels.
- Avoid tiny right-rail text. Minimum 14px for utility text, 16px for body text.
- Keep source-card actions reachable by keyboard.
- Honor `prefers-reduced-motion`.

## Legal and privacy boundaries

Every screen should preserve the same boundaries:

- Not legal advice.
- Review required before reliance.
- No attorney-client relationship.
- Do not paste child names, sealed records, medical details, allegations, or confidential court documents unless the actual target project has a clear private/local-only policy and the user understands it.
- No backend intake or public submission flow.

## Implementation files

- `css/focaf-family-law-llm-theme.css` — drop-in CSS theme.
- `data/design-tokens.json` — portable design tokens.
- `data/palette.json` — named palette and usage notes.
- `assets/logo/*.svg` — mark, horizontal lockup, wordmark.
- `assets/favicon/*` — SVG, PNG sizes, ICO, and browser manifest.
- `assets/social/*` — OpenGraph/social preview card.
- `examples/llm-screen.html` — static preview of the branded UI.
- `snippets/react-brand-shell.tsx` — React-ish shell/components you can adapt.
- `snippets/favicon-head.html` — HTML favicon tags.
