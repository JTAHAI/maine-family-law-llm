# v5.18.0 GA Release Candidate

v5.18.0 implements the software-side operations for planned Pass 50. It freezes a versioned artifact inventory, records explicit external signoff references, tracks P0/P1 blockers, runs the existing release-candidate auditor, and builds immutable evidence packets.

It does not claim that external legal data, attorney-reviewed evaluations, pilot completion, security/legal/product/ops approval, Microsoft Store certification, or GA approval exists.

## Required artifact types

- source repository ZIP
- external data build manifest
- parsed authority manifest
- retrieval index manifest
- gold evaluation pack manifest
- release metrics JSON
- security evidence packet
- pilot evidence packet
- rollback package
- release notes

## Required signoff roles

Security, legal, product, and operations must each be explicitly approved through genuine external evidence. The application records opaque labels and hashes; it does not independently verify signer authority.

## API

- `GET /api/ga-release-candidate/status`
- `POST /api/ga-release-candidate/candidates`
- `POST /api/ga-release-candidate/artifacts`
- `POST /api/ga-release-candidate/signoffs`
- `POST /api/ga-release-candidate/blockers`
- `POST /api/ga-release-candidate/freeze`
- `POST /api/ga-release-candidate/evidence/build`
- `GET /api/ga-release-candidate/artifacts/{token}`

## Fail-closed boundary

`pass50_complete` always remains false inside this software-side operations layer. The separate external launch-evidence gate must validate the signed Pass 50 report.
