# Connections & Deliberation

This slice adds a review-required path for optional provider connections. Local-only mode remains the default, and no provider traffic should occur unless the operator explicitly connects a provider and approves an outbound manifest.

## Verified provider catalog

Revalidation date: **August 6, 2026**

The catalog currently includes:

- OpenAI
- Gemini
- xAI

These entries are capability records, not automatic promises of transmission support. The current slice intentionally keeps endpoint and model selection operator-controlled so we do not guess provider-specific API details.

## Connection workflow

1. Choose a provider.
2. Provide BYOK credentials.
3. Pick the pinned model ID.
4. Set the endpoint URL and request path explicitly.
5. Review the provider retention and data-control summary.
6. Connect or disconnect the provider.
7. Run an explicit health check if you want a local readiness view.

Credentials are stored in Windows Credential Manager only. No plaintext API keys are written to config files or exported into manifests.

## Consent modes

- Local only: no external traffic.
- Question only: question and task instructions only.
- Selected excerpts: only the user-selected excerpts.
- Selected document: requires a second confirmation before preview.
- Whole matter: prohibited in this slice.

## Outbound manifest

Before anything can move toward transmission, the user must preview:

- the exact question
- the exact excerpt IDs
- the provider and pinned model
- the exact payload that would be transmitted
- the tool permissions
- the estimated usage
- the retention and data-control summary
- the payload SHA-256 hash

The manifest is immutable after approval. If the payload, provider, model, source selection, tool permissions, or redactions change, the approval is invalidated.

## Cancellation and failure states

The slice preserves explicit cancellation and visible failure reporting. Provider runs can be cancelled, disconnected, or revoked without revealing credential values.

The current implementation is intentionally conservative:

- local-only flows stay on the local machine;
- provider discovery is explicit, not backgrounded;
- consent never auto-renews;
- provider transport remains app-mediated;
- unsupported or unverified paths fail closed.

## Troubleshooting

- If a provider does not connect, check that the endpoint URL, request path, and pinned model ID are filled in.
- If the manifest preview rejects a change, rebuild the preview from the edited question or excerpt list.
- If a credential needs to be removed, use revoke instead of edit-in-place.
- If you want to return to the default posture, disconnect all providers and switch back to local only.
