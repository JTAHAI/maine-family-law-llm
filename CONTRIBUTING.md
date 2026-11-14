# Contributing

Contributions should preserve the source-only boundary: no legal corpora, no private matter data, no model weights, no vector stores, and no generated runtime databases.

## Licensing contributions

Project-authored source code and documentation are licensed under Apache-2.0; see [LICENSE.md](LICENSE.md). Unless explicitly stated otherwise, contributions intentionally submitted for inclusion are made under that license, consistent with its Section 5 and any separately executed contribution agreement. Contribute only material you have the right to submit. Retain existing copyright and attribution notices, and identify any third-party material and its license in the pull request.

Project acceptance, safety, and release-review requirements do not add restrictions to downstream software-license permissions. See [NOTICE.md](NOTICE.md) for the separate data and safety boundaries and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for existing third-party notices.

## Validation

Before opening a pull request, run:

```bash
python -m pytest -q
python scripts/run-quality-checks.py
python scripts/build-enterprise-acceptance-evidence.py enterprise_acceptance_evidence.json
```

For Windows local testing under `C:\dev\ME_FM_LLM`, use `scripts/run-final-local-acceptance.ps1` after staging the external data root at `C:\dev\ME_FM_LLM_data`.

### Privileged matter-key maintenance

The loopback matter-key mutation and its capability-mint action require a
separately provisioned maintenance credential. Configure the server process
with `MFL_MATTER_KEY_ADMIN_TENANT` and `MFL_MATTER_KEY_ADMIN_BEARER_SHA256` (the
SHA-256 of the ASCII representation of a random 32-byte hex token). Send the
token as `Authorization: Bearer <token>` on both requests, with the matching
tenant and admin role. Keep the token out of shell history, logs, and all
repository files. Changing the configured digest revokes the old credential.
Local research, working drafts, and matter-key status require no maintenance
token. This credential is not an enterprise identity provider.

For an offline filing reviewer, provision one operator-approved reviewer ID,
tenant, and active matter ID through `MFL_FILING_REVIEWER_ID`,
`MFL_FILING_REVIEWER_TENANT`, and `MFL_FILING_REVIEWER_MATTER_ID`. Set
`MFL_FILING_REVIEWER_BEARER_SHA256` to the SHA-256 of the ASCII encoding of a
fresh random 32-byte lowercase hex token. Give the token only to the authorized
reviewer. Enter it in the workbench before preparing, recording and downloading
the filing copy. Remove the configuration or rotate the token to revoke
existing approvals. This authenticates the delegated credential; it does not
establish professional licensure. The first authorized export is exact text
only, with facts backed by verified staged TXT records; other formats remain
review-required working copies.
