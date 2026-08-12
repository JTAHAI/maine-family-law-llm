# v5.12.0 Hybrid Retrieval and Evaluation Workbench

## Trust boundary

The host owns document admission, source lanes, rank fusion, authority and freshness weighting, evaluation admission, and release gating. Optional engines are replaceable workers.

## Backends

1. SQLite FTS5 lexical baseline — always local and dependency free when FTS5 is available.
2. sqlite-vec — optional embedded vector acceleration.
3. Deterministic hash-dense fallback — local, reproducible, and not represented as a neural legal model.
4. Qdrant — optional loopback service only; disabled by default.

## API

- `GET /api/retrieval-workbench/status`
- `POST /api/retrieval-workbench/search`
- `POST /api/retrieval-workbench/evaluate`

## Evaluation integrity

Attorney-reviewed JSONL remains external to the repository. Dataset hash, sample counts, reviewer status, failure rows, and metric basis are preserved. Missing or insufficient reviewed data blocks evaluation instead of producing a release pass.
