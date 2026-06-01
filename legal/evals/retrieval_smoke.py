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
    blockers: list[dict[str, Any]] = field(default_factory=list)
    thresholds: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "eval_root": self.eval_root,
            "case_count": self.case_count,
            "metrics": self.metrics,
            "thresholds": self.thresholds,
            "blockers": self.blockers,
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

    def run(
        self,
        *,
        write_report: bool = True,
        top_k: int = 20,
        min_case_count: int = 1,
        min_recall_at_20: float = 0.9,
        max_case_count: int | None = None,
        progress_interval: int = 10,
    ) -> RetrievalSmokeEvalReport:
        index_builder = RetrievalIndexBuilder(data_root=self.data_root)
        documents = index_builder.load_documents()
        authority_index = self._load_authority_index()
        pipeline = RetrievalPipeline(documents, authority_index=authority_index)
        effective_max_case_count = max_case_count if max_case_count is not None else max(25, int(min_case_count))
        cases = self._build_cases(documents, max_case_count=effective_max_case_count)
        failures: list[dict[str, Any]] = []
        metric_rows: list[dict[str, Any]] = []
        started_at = datetime.now(timezone.utc)
        for index, case in enumerate(cases, start=1):
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
            if write_report and progress_interval > 0 and (index % progress_interval == 0 or index == len(cases)):
                self._write_progress(
                    completed=index,
                    total=len(cases),
                    started_at=started_at,
                    case=case,
                    latest_metrics=metrics,
                    failures=len(failures),
                )
        aggregate = self._aggregate(metric_rows)
        thresholds = {
            "top_k": top_k,
            "min_case_count": min_case_count,
            "min_recall_at_20": min_recall_at_20,
            "max_case_count": effective_max_case_count,
            "progress_report": str(self.eval_root / "retrieval_smoke_progress.json"),
            "basis": "source-derived smoke cases; not attorney-reviewed GA gold",
        }
        blockers = self._blockers(cases=cases, aggregate=aggregate, thresholds=thresholds)
        status = "pass" if not blockers else "blocked"
        report = RetrievalSmokeEvalReport(
            status=status,
            data_root=str(self.data_root),
            eval_root=str(self.eval_root),
            case_count=len(cases),
            metrics={**aggregate, "per_case": metric_rows},
            failures=failures,
            blockers=blockers,
            thresholds=thresholds,
        )
        if write_report:
            self.eval_root.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(report.as_dict(), indent=2, sort_keys=True)
            (self.eval_root / "retrieval_smoke_eval.json").write_text(payload, encoding="utf-8")
            # Compatibility copy for local operators monitoring <data-root>/retrieval_smoke_report.json.
            (self.data_root / "retrieval_smoke_report.json").write_text(payload, encoding="utf-8")
        return report

    def _load_authority_index(self) -> SourceAuthorityIndex | None:
        path = self.data_root / "authority_layer" / "citation_index.json"
        if not path.exists():
            return None
        rows = json.loads(path.read_text(encoding="utf-8"))
        return SourceAuthorityIndex.from_rows(rows)

    @staticmethod
    def _build_cases(documents, *, max_case_count: int | None = None) -> list[RetrievalEvalCase]:
        """Build a bounded smoke sample from indexed authority.

        Full-corpus source-derived smoke can create thousands of cases. With the
        current deliberately simple lexical/semantic stack that makes local GA
        runs CPU-bound for hours while adding little signal beyond the required
        release smoke threshold. Prefer exact citation/form/statute cases first
        because they are deterministic, auditable, and tied to official source
        identifiers; add issue-label cases only when room remains.
        """
        cap = max_case_count if max_case_count is not None and max_case_count > 0 else None
        exact_cases: list[RetrievalEvalCase] = []
        issue_cases: list[RetrievalEvalCase] = []
        seen_queries: set[str] = set()
        for document in documents:
            if document.citation and extract_citations(document.citation):
                query = document.citation
                if query not in seen_queries:
                    exact_cases.append(
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
                    issue_cases.append(
                        RetrievalEvalCase(
                            query=query,
                            relevant_source_ids={document.source_id},
                            case_type="issue_lookup",
                            expected_source_class=document.source_class,
                        )
                    )
                    seen_queries.add(key)
        cases = exact_cases + issue_cases
        return cases[:cap] if cap is not None else cases

    def _write_progress(
        self,
        *,
        completed: int,
        total: int,
        started_at: datetime,
        case: RetrievalEvalCase,
        latest_metrics: dict[str, Any],
        failures: int,
    ) -> None:
        self.eval_root.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        elapsed = max((now - started_at).total_seconds(), 0.001)
        seconds_per_case = elapsed / max(completed, 1)
        remaining = max(total - completed, 0) * seconds_per_case
        payload = {
            "status": "running" if completed < total else "finalizing",
            "generated_at": now.isoformat(),
            "completed_cases": completed,
            "total_cases": total,
            "percent_complete": round(completed / max(total, 1) * 100, 2),
            "elapsed_seconds": round(elapsed, 2),
            "estimated_seconds_remaining": round(remaining, 2),
            "failures_so_far": failures,
            "latest_case": case.as_dict(),
            "latest_metrics": latest_metrics,
        }
        text = json.dumps(payload, indent=2, sort_keys=True)
        (self.eval_root / "retrieval_smoke_progress.json").write_text(text, encoding="utf-8")
        (self.data_root / "retrieval_smoke_progress.json").write_text(text, encoding="utf-8")

    @staticmethod
    def _blockers(*, cases: list[RetrievalEvalCase], aggregate: dict[str, float], thresholds: dict[str, Any]) -> list[dict[str, Any]]:
        blockers: list[dict[str, Any]] = []
        min_case_count = int(thresholds["min_case_count"])
        min_recall = float(thresholds["min_recall_at_20"])
        if not cases:
            blockers.append({"code": "no_eval_cases", "message": "No retrieval smoke cases could be derived from indexed authority."})
        if len(cases) < min_case_count:
            blockers.append(
                {
                    "code": "insufficient_case_count",
                    "message": "Retrieval smoke eval case count is below the configured release threshold.",
                    "actual": len(cases),
                    "minimum": min_case_count,
                }
            )
        recall = float(aggregate.get("recall_at_20", 0.0))
        if recall < min_recall:
            blockers.append(
                {
                    "code": "recall_at_20_below_threshold",
                    "message": "Retrieval smoke Recall@20 is below the configured release threshold.",
                    "actual": recall,
                    "minimum": min_recall,
                }
            )
        return blockers

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
