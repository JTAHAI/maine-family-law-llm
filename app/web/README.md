# Web surface status

The installed product has one production frontend:
`src/maine_family_law_llm/ui/workbench.html`, `workbench.css`, and
`workbench.js`. It is bundled into the desktop executable, served from the
loopback origin, and validated by `production_ui_manifest()`.

The TSX files in this directory are design and route contracts retained for
compatibility with the requirements suite. They are not built, shipped, or
used as evidence that a feature is reachable. Runtime capability claims must
come from `/api/runtime/capabilities` and `/api/runtime/ui-manifest`.
