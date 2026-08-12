# Maine Family Law LLM v5.12.0 — Explainable Hybrid Retrieval and Evaluation

v5.12.0 adds a bounded local retrieval and evaluation workbench without making vector similarity, model scoring, or provider consensus a source of legal truth.

## Embedded hybrid retrieval

- SQLite FTS5 provides the default local lexical index.
- Exact legal terms and citations receive visible lexical evidence.
- A deterministic fixed-width local embedding supplies an offline semantic fallback.
- `sqlite-vec` is an optional accelerator and is never installed or downloaded automatically.
- Results use bounded reciprocal-rank fusion with visible authority, freshness, and source-lane components.
- Every result explains why it matched and preserves the legal-authority/private-record lane.

## Optional Qdrant boundary

Qdrant remains disabled by default. Only an explicitly configured `localhost`, `127.0.0.1`, or `::1` HTTP(S) endpoint is admitted. Credentials embedded in the URL, cloud hosts, arbitrary schemes, automatic discovery, and public binding are refused.

## Attorney-gold evaluation

The evaluation endpoint requires:

- an external verified authority retrieval index;
- an external `maine_rag_retrieval_gold.jsonl` dataset;
- rows explicitly marked attorney reviewed;
- relevant source IDs and a query; and
- private-data training disabled.

Seed, synthetic, non-attorney, malformed, and private-training rows cannot satisfy the minimum. Reports include Recall@5/10/20, precision, MRR, nDCG, dataset hash, row counts, misses, and failure clusters.

## Main-workbench experience

The verified-record inspector now opens a large retrieval workbench with backend status, lane selection, result limits, explainable ranked cards, and configured attorney-gold evaluation. Retrieval rank never certifies factual truth, legal correctness, authenticity, credibility, or filing readiness.

Product version: **5.12.0**. Microsoft Store package target: **5.12.0.0**. UI build: **39**.
