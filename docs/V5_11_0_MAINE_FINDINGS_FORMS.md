# v5.11.0 Maine Findings and Forms Workbench

## Trust boundary

The host performs deterministic review. It does not decide best interests, credibility, legal sufficiency, contempt, or filing readiness. Private-record matches are review candidates. Court-form status comes only from the verified active authority generation.

## Main API

- `GET /api/findings-forms/status`
- `POST /api/findings-forms/documents/{document_id}/review`
- `GET /api/findings-forms/documents/{document_id}/active`
- `GET /api/findings-forms/verify`
- `POST /api/findings-forms/complete`
- `GET /api/findings-forms/artifacts/{token}`

## Fail-closed rules

- Missing material best-interest factors remain blockers.
- Restrictions without explanatory findings remain blockers.
- Third-party parenting-decision delegation remains a blocker.
- PFA overlap without independent family-case analysis remains a blocker.
- Unknown or stale forms remain blockers.
- Missing required form fields remain blockers.
- A changed document revision makes an earlier completion stale.
- Working-copy output is never labeled an official completed PDF or filing-ready document.
