# Pass v1.86 — Classic desktop FOCAF research workbench UI

This pass converts the local browser workbench into a dense classic desktop-style FOCAF research interface matching the requested layout reference.

## User-visible changes

- Added a Windows-style application shell with title bar, menu bar, window controls, and bottom status bar.
- Added the FOCAF hero header with app icon, secure status, review-required / not-legal-advice indicators, and FOCAF identity block.
- Reworked the top control strip into role, answer style, topic filter, focus context, and source-loading controls.
- Reworked the main body into a two-column layout: large research chat workspace plus a right FOCAF sidebar.
- Added sidebar panels for status, prompt shortcuts, question starters, starter packs, and recent source cards.
- Added bottom tab-style regions for latest answer, source inspector, transcript / reviewer handoff, and runtime diagnostics.
- Preserved Enter-to-submit, source cards, transcript export, reviewer handoff metadata, FOCAF brand assets, and appeals routing.

## Safety

- Outputs remain legal information, not legal advice.
- Review-required status remains visible.
- No filing-ready, attorney review, legal signoff, production GA, or real-matter pilot claim is made.
