# Public Release Hardening

This repository can be staged publicly as source code only. Public release does not mean the legal product is production ready.

Required before publishing:

1. Run `python scripts/prepare-public-github-release.py`.
2. Run `python scripts/build-public-attribution-kit.py`.
3. Run `python scripts/run-public-supply-chain-hardening.py`.
4. Run `python scripts/run-quality-checks.py`.
5. Confirm no official legal corpora, private matter files, runtime databases, model weights, OCR caches, embeddings, or attorney-reviewed gold data are inside the source tree.

Windows staging from the intended local path:

```powershell
cd C:\dev\ME_FM_LLM
.\scripts\build-local-github-stage.ps1 -RepoRoot C:\dev\ME_FM_LLM -DataRoot C:\dev\ME_FM_LLM_data
```

The attribution kit creates `LICENSE.md`, `NOTICE.md`, `ATTRIBUTION.md`, and `CITATION.cff`. Counsel should review the draft attribution license before public release or commercial use.
