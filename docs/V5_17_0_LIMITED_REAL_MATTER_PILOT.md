# v5.17.0 Limited Real-Matter Pilot

v5.17.0 implements the software-side operations for the planned Pass 49 limited real-matter pilot. It does not claim that a pilot occurred or that any attorney, client, tenant, court, or Store approved the product.

## Control model

The pilot ledger is external to the source repository and records only opaque identifiers, SHA-256 evidence references, enumerated outcomes, and control status. It refuses private narrative fields, party names, addresses, dates of birth, source excerpts, credentials, and absolute paths.

A pilot program requires:

- a named tenant allowlist;
- a hash of external Pass 48 evidence;
- an eligible attorney-sandbox participant record;
- explicit real-matter consent evidence;
- privacy-notice evidence;
- tenant-isolation and encryption evidence;
- a matter-store manifest hash;
- retention-policy versioning;
- human review and export restrictions;
- required work-product hashes;
- daily review evidence;
- incident handling; and
- an external attorney signoff reference.

## Required work products

Each enrolled matter must identify hash-bound versions of:

- issue tree;
- posture summary;
- timeline;
- evidence map;
- authority matrix; and
- red-flag report.

Optional packet, citation, quote, claim-support, form-freshness, and missing-record artifacts may also be recorded by hash.

## Fail-closed events

Any recorded data-leakage event, cross-matter access event, or unsupported filing-ready export attempt permanently blocks the software-side readiness status for that pilot evidence set. Open incidents, incomplete daily review, missing work products, missing consent/control evidence, and missing attorney signoff also block readiness.

## Evidence packet

The application can generate deterministic JSON, HTML, receipt, and manifest artifacts. The packet is content-addressed and reverified before opaque download. It expressly records that private matter content is not included and that Pass 49 remains incomplete pending external evidence review.

## API

- `GET /api/limited-real-matter-pilot/status`
- `POST /api/limited-real-matter-pilot/programs`
- `POST /api/limited-real-matter-pilot/matters`
- `POST /api/limited-real-matter-pilot/work-products`
- `POST /api/limited-real-matter-pilot/daily-reviews`
- `POST /api/limited-real-matter-pilot/exports`
- `POST /api/limited-real-matter-pilot/incidents`
- `POST /api/limited-real-matter-pilot/incidents/update`
- `POST /api/limited-real-matter-pilot/signoffs`
- `POST /api/limited-real-matter-pilot/evidence/build`
- `GET /api/limited-real-matter-pilot/artifacts/{token}`

## Release boundary

The application always reports `pass49_complete: false`. It does not independently validate client consent, attorney identity, legal usefulness, tenant isolation, encryption, or signoff. Those facts must be established through genuine external pilot evidence and the existing Pass 49 launch-evidence gate.
