# v3.0.0 Pass 01 — Constitutional family-justice shell

## Product and package

- Product version: **3.0.0**
- MSIX build target: **3.0.0.1**
- Pass status: source implementation and focused validation complete
- Windows Store package build, frozen-runtime smoke, and WACK: not run in this Linux review environment

## Browser workbench

- Split the former embedded, monolithic browser UI into packaged local HTML, CSS, JavaScript, and SVG assets.
- Replaced the oversized constitutional hero with a slim permanent bar that keeps **WE THE PEOPLE** and **... establish JUSTICE ...** visible.
- Added the approved mission statement as an accessible hover, focus, and tap popover.
- Added a visible **Ctrl+K** command palette with filtering and keyboard navigation.
- Added the **Ctrl+J** Justice easter egg with a locally bundled Constitution facsimile.
- Made the conversation the primary workspace and converted the always-visible, clipped right rail into a closed evidence drawer with Setup, Evidence, Review, and Starters tabs.
- Removed the duplicate empty-transcript label and moved the duplicate Latest answer dashboard into the drawer as review detail.
- Reduced header and composer height, preserved a visible search-lane selector, and moved secondary export actions into a compact More menu.
- Changed copied links to privacy-safe settings links that exclude questions, matter context, private records, corpus paths, and local filesystem paths.
- Added local-only security headers and bundled-asset serving.
- Added focus trapping/restoration for overlays and focus restoration for the evidence drawer.

## Desktop launcher

- Replaced the flat wall of equally weighted buttons with task-oriented tabs: **Start here**, **Review & export**, and **Support & tools**.
- Made **Open Local AI Chat** the primary action.
- Grouped matter setup, installed corpus, review/export, and support actions.
- Added the constitutional identity header, mission hover text, local-only state, status bar, and correct v3.0.0 display version.

## Validation

- JavaScript syntax validation passed.
- Python source compilation passed.
- Focused regression group: **88 tests passed**.
- FastAPI TestClient smoke passed for `/`, CSS, JavaScript, Justice SVG, and health endpoints.
- Standalone bundled-asset browser interaction smoke passed for the default chat, evidence drawer, Ctrl+K palette, and Ctrl+J modal.

## Release boundary

This pass does not claim current-law certification, attorney review, filing readiness, Windows Store certification, frozen-runtime smoke, or WACK completion. Outputs remain source-grounded when possible, review-required, local-first, and not legal advice.
