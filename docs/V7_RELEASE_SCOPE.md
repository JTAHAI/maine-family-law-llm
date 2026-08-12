# v7.0.0 release scope

The v7 release uses a smaller-verified-scope policy. No feature is public merely because source code or an API route exists. A feature moves from candidate to public only after production-UI, frozen-runtime, installed-package, privacy, review-status, and end-to-end evidence pass.

## Current public scope

The public scope is limited to the 16 workflows listed in `configs/v700_release_scope.json`: launch, matter open, record import/inventory, deterministic parsing, OCR derivative creation, document privacy review, duplicate/change review, source-backed Maine research, exact official-source preview, citation/quote verification, drafting/revisions, review-required packets, the canonical filing gate, Local-only controls, and backup/restore.

## Hidden scope

Slices 21–31 remain hidden and unadvertised. Their backend data is preserved non-destructively; an explicit development-only override may expose them for engineering tests. Slices 32–44 are not part of this run. Timeline correction, claim-disposition, current guided forms, installed tracked-DOCX, command-center/snapshot, and missing-attachment coverage claims are also excluded because installed end-to-end proof is incomplete.

## Canonical manifest

`configs/v700_release_scope.json` is the source-controlled scope. Release tooling copies it to `dist/release/v7.0.0/release-scope.json`, which is the only generated input permitted for Store feature copy.
