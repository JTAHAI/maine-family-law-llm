# Contribution Guide

Contributions should keep this repo local-first and open-source-safe.

Do not add private client facts, raw corpora, databases, vector stores, model weights, caches, venvs, or generated proof junk to commits or release ZIPs.

When adding a source, update `data/sources/manifest.seed.json` or a future manifest file with explicit provenance and citation metadata. Add a small safe fixture for offline tests when practical.

Legal features must include tests that prove unsupported claims are refused and cited answers use retrieved sources only.
