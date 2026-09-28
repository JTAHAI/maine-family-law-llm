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
