# Supply Chain Security

The project keeps its source tree dependency-light and separates code from external legal data. Supply-chain evidence is generated locally and should be attached to release review.

Controls:

- `pyproject.toml` declares the package and optional dependency groups.
- GitHub CI runs tests and source quality evidence.
- `scripts/run-public-supply-chain-hardening.py` emits a source SBOM-style inventory and verifies required scripts/workflows.
- `scripts/build-release-provenance.py` emits deterministic source-tree hashes.
- External resource collection writes to an external data root, not the repository.

This evidence does not prove legal correctness. Legal correctness requires live official-source manifests, parsed authority stores, attorney-reviewed gold data, measured verifier/retrieval metrics, pilot/security evidence, and owner signoffs.
