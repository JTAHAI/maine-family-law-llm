# Local Deliberation Workspace

The local deliberation workspace is a review-required, local-only analysis host for blind first-pass legal reasoning, claim alignment, dissent preservation, omission hunting, and deterministic verification.

## What it does

- Creates a versioned deliberation run from a frozen question, matter, and scope.
- Keeps worker turns blind during the first pass so no worker sees the other worker identities or raw positions.
- Maintains a claim ledger that preserves agreement, dissent, corrections, and unresolved questions.
- Uses a read-only local tool broker for authority, records, evidence, and verification tasks.
- Produces a final synthesis that is still marked review-required.

## Safety constraints

- No outbound traffic.
- No remote MCP providers.
- No browser automation.
- No model provider calls outside the local host.
- No write access through the deliberation broker.

## API surface

- `GET /api/deliberation/presets`
- `GET /api/deliberation/tools`
- `POST /api/deliberation/runs`
- `POST /api/deliberation/runs/{run_id}/confirm`
- `POST /api/deliberation/runs/{run_id}/start`
- `POST /api/deliberation/runs/{run_id}/cancel`
- `GET /api/deliberation/runs/{run_id}`
- `GET /api/deliberation/runs/{run_id}/events`
- `GET /api/deliberation/runs/{run_id}/claims`
- `GET /api/deliberation/runs/{run_id}/positions`
- `GET /api/deliberation/runs/{run_id}/synthesis`
- `POST /api/deliberation/runs/{run_id}/tools/{tool_name}`

## UI surface

- `/deliberation`
