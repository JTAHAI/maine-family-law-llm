# v5.10.0 Evidence Work Product

## Components

- deterministic timeline builder;
- contempt/enforcement event ledger;
- hard-field conflict detector;
- opposing-language contradiction candidates;
- exhibit index;
- missing-record checklist;
- immutable JSON and HTML packet; and
- hash-bound receipt and active-build pointer.

## Trust model

The engine receives only already-indexed record rows from the host. It removes directory components from metadata, caps record and text volume, records source and text hashes, and stores generated artifacts inside the active external matter root. It never alters originals and never treats a record statement as proof.

## Local API

- `GET /api/evidence-work-product/status`
- `POST /api/evidence-work-product/build`
- `GET /api/evidence-work-product/active`
- `GET /api/evidence-work-product/verify`
- `GET /api/evidence-work-product/artifacts/{token}`

Artifact tokens are short-lived, matter-scoped, and contain no filesystem path.
