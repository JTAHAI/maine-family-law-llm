# Public GitHub Release Checklist

This repository can be prepared for a public source release only as a clean source-code project. It must not include official Maine corpus snapshots, parsed authority stores, vector indexes, private matter files, OCR caches, model weights, runtime databases, secrets, or attorney-reviewed private work product.

Before publishing:

1. Run `python scripts/prepare-public-github-release.py --project-root . --output public_release_readiness.json`.
2. Run `python scripts/build-release-provenance.py --project-root . --output release_provenance.json`.
3. Run `python scripts/run-quality-checks.py`.
4. Confirm the only `.txt` file in the source tree is `PASS_CHANGES.txt`.
5. Confirm `post_ga_repo_review_build_path.json` still distinguishes source readiness from production legal-data readiness.
6. Choose and commit a final license only after legal review. Until then, do not imply that third-party official source snapshots or licensed materials are bundled or sublicensed.

Production legal readiness remains separate from public source readiness. A public repository is not a certified legal data product unless the external authority manifests, attorney-reviewed evals, measured metrics, pilot evidence, security packet, and owner signoffs are attached as release evidence.
