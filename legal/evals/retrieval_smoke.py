from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.evals.retrieval_metrics import summarize_ranked_retrieval
from legal.retrieval.index_builder import RetrievalIndexBuilder
from legal.retrieval.retrieval_pipeline import RetrievalPipeline
from legal.verifiers.citation_parser import extract_citations
from legal.verifiers.citation_resolver import SourceAuthorityIndex


@dataclass(frozen=True)
class RetrievalEvalCase:
    query: str
    relevant_source_ids: set[str]
    case_type: str
    expected_source_class: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "relevant_source_ids": sorted(self.relevant_source_ids),
            "case_type": self.case_type,
            "expected_source_class": self.expected_source_class,
        }


@dataclass
class RetrievalSmokeEvalReport:
    status: str
    data_root: str
    eval_root: str
    case_count: int
    metrics: dict[str, Any]
    failures: list[dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "eval_root": self.eval_root,
            "case_count": self.case_count,
            "metrics": self.metrics,
            "failures": self.failures,
        }


class RetrievalSmokeEvalRunner:
    """Measured smoke eval over real parsed/indexed authority artifacts.

    This is not a substitute for attorney-reviewed gold. It proves the retrieval stack can
    measure Recall@k/MRR/nDCG against source-derived exact citation and issue cases.
    """

    def __init__(self, *, data_root: str | Path, eval_root: str | Path | None = None) -> None:
        self.data_root = Path(data_root).resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else self.data_root / "eval_store"

    def run(self, *, write_report: bool = True, top_k: int = 20) -> RetrievalSmokeEvalReport:
        index_builder = RetrievalIndexBuilder(data_root=self.data_root)
        documents = index_builder.load_documents()
        authority_index = self._load_authority_index()
        pipeline = RetrievalPipeline(documents, authority_index=authority_index)
        cases = self._build_cases(documents)
        failures: list[dict[str, Any]] = []
        metric_rows: list[dict[str, Any]] = []
        for case in cases:
            response = pipeline.retrieve(case.query, top_k=top_k, include_text=False)
            retrieved_ids = [row["source_id"] for row in response["retrieved_sources"]]
            metrics = summarize_ranked_retrieval(retrieved_ids, case.relevant_source_ids, ks=(5, 10, 20))
            metric_rows.append({"case": case.as_dict(), "retrieved_source_ids": retrieved_ids, "metrics": metrics})
            if metrics["recall_at_20"] < 1.0:
                failures.append(
                    {
                        "reason": "retrieval_miss",
                        "query": case.query,
                        "case_type": case.case_type,
                        "expected_source_ids": sorted(case.relevant_source_ids),
                        "retrieved_source_ids": retrieved_ids,
                        "expected_source_class": case.expected_source_class,
                    }
                )
        aggregate = self._aggregate(metric_rows)
        status = "pass" if cases and aggregate.get("recall_at_20", 0.0) >= 0.9 else "blocked"
        report = RetrievalSmokeEvalReport(
            status=status,
            data_root=str(self.data_root),
            eval_root=str(self.eval_root),
            case_count=len(cases),
            metrics={**aggregate, "per_case": metric_rows},
            failures=failures,
        )
        if write_report:
            self.eval_root.mkdir(parents=True, exist_ok=True)
            (self.eval_root / "retrieval_smoke_eval.json").write_text(
                json.dumps(report.as_dict(), indent=2, sort_keys=True), encoding="utf-8"
            )
        return report

    def _load_authority_index(self) -> SourceAuthorityIndex | None:
        path = self.data_root / "authority_layer" / "citation_index.json"
        if not path.exists():
            return None
        rows = json.loads(path.read_text(encoding="utf-8"))
        return SourceAuthorityIndex.from_rows(rows)

    @staticmethod
    def _build_cases(documents) -> list[RetrievalEvalCase]:
        cases: list[RetrievalEvalCase] = []
        seen_queries: set[str] = set()
        for document in documents:
            if document.citation and extract_citations(document.citation):
                query = document.citation
                if query not in seen_queries:
                    cases.append(
                        RetrievalEvalCase(
                            query=query,
                            relevant_source_ids={document.source_id},
                            case_type="exact_citation_lookup",
                            expected_source_class=document.source_class,
                        )
                    )
                    seen_queries.add(query)
            for label in document.issue_labels[:1]:
                query = label.replace("_", " ")
                key = f"issue:{query}:{document.source_id}"
                if key not in seen_queries:
                    cases.append(
                        RetrievalEvalCase(
                            query=query,
                            relevant_source_ids={document.source_id},
                            case_type="issue_lookup",
                            expected_source_class=document.source_class,
                        )
                    )
                    seen_queries.add(key)
        return cases

    @staticmethod
    def _aggregate(metric_rows: list[dict[str, Any]]) -> dict[str, float]:
        if not metric_rows:
            return {"recall_at_5": 0.0, "recall_at_10": 0.0, "recall_at_20": 0.0, "mrr": 0.0, "ndcg_at_20": 0.0}
        keys = ["recall_at_5", "recall_at_10", "recall_at_20", "mrr", "ndcg_at_20"]
        aggregate: dict[str, float] = {}
        for key in keys:
            aggregate[key] = round(
                sum(float(row["metrics"].get(key, 0.0)) for row in metric_rows) / len(metric_rows), 3
            )
        return aggregate
