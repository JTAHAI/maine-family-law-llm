from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.retrieval.index_builder import RetrievalIndexBuilder
from legal.verifiers.citation_parser import extract_citations


@dataclass(frozen=True)
class RetrievalFailureTicket:
    reason: str
    query: str
    expected_source_ids: list[str]
    retrieved_source_ids: list[str]
    remediation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "query": self.query,
            "expected_source_ids": self.expected_source_ids,
            "retrieved_source_ids": self.retrieved_source_ids,
            "remediation": self.remediation,
            "metadata": self.metadata,
        }


class RetrievalFailureTriage:
    """Classify retrieval misses into actionable pass-25 failure buckets."""

    REMEDIATION = {
        "missed_exact_citation": "add or repair exact citation lookup / citation parser normalization",
        "wrong_source_class": "adjust source-class and authority/freshness boosting",
        "stale_source": "refresh source snapshot or block current-law language",
        "semantic_miss": "add query expansion terms or improve embeddings/reranker",
        "bad_chunking": "rechunk parent/child authority records and preserve citation/title in child chunk",
        "missing_authority": "ingest the missing official authority source before release",
    }

    def __init__(self, *, data_root: str | Path, eval_root: str | Path | None = None) -> None:
        self.data_root = Path(data_root).resolve()
        self.eval_root = Path(eval_root).resolve() if eval_root else self.data_root / "eval_store"

    def run(self, *, smoke_report_path: str | Path | None = None, write_report: bool = True) -> dict[str, Any]:
        smoke_path = Path(smoke_report_path) if smoke_report_path else self.eval_root / "retrieval_smoke_eval.json"
        report = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.exists() else {"failures": []}
        documents = RetrievalIndexBuilder(data_root=self.data_root).load_documents()
        document_by_id = {document.source_id: document for document in documents}
        tickets = [self._ticket_for_failure(failure, document_by_id) for failure in report.get("failures", [])]
        clusters: dict[str, int] = {}
        for ticket in tickets:
            clusters[ticket.reason] = clusters.get(ticket.reason, 0) + 1
        query_expansion_map = self._query_expansion_map(tickets)
        output = {
            "status": "pass" if not tickets else "needs_retrieval_fixes",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data_root": str(self.data_root),
            "failure_count": len(tickets),
            "clusters": clusters,
            "tickets": [ticket.as_dict() for ticket in tickets],
            "query_expansion_map": query_expansion_map,
        }
        if write_report:
            self.eval_root.mkdir(parents=True, exist_ok=True)
            (self.eval_root / "retrieval_failure_triage.json").write_text(
                json.dumps(output, indent=2, sort_keys=True), encoding="utf-8"
            )
            with (self.eval_root / "retrieval_failure_tickets.jsonl").open("w", encoding="utf-8") as fh:
                for ticket in tickets:
                    fh.write(json.dumps(ticket.as_dict(), sort_keys=True) + "\n")
        return output

    def _ticket_for_failure(self, failure: dict[str, Any], document_by_id: dict[str, Any]) -> RetrievalFailureTicket:
        query = str(failure.get("query") or "")
        expected = [str(value) for value in failure.get("expected_source_ids", [])]
        retrieved = [str(value) for value in failure.get("retrieved_source_ids", [])]
        expected_class = failure.get("expected_source_class")
        reason = "semantic_miss"
        if extract_citations(query):
            reason = "missed_exact_citation"
        elif expected and any(source_id not in document_by_id for source_id in expected):
            reason = "missing_authority"
        elif expected and any(document_by_id.get(source_id) and document_by_id[source_id].freshness_status == "stale" for source_id in expected):
            reason = "stale_source"
        elif expected and any(document_by_id.get(source_id) and not document_by_id[source_id].chunk_id for source_id in expected):
            reason = "bad_chunking"
        elif expected_class and retrieved:
            top_doc = document_by_id.get(retrieved[0])
            if top_doc and top_doc.source_class != expected_class:
                reason = "wrong_source_class"
        return RetrievalFailureTicket(
            reason=reason,
            query=query,
            expected_source_ids=expected,
            retrieved_source_ids=retrieved,
            remediation=self.REMEDIATION[reason],
            metadata={"expected_source_class": expected_class, "original_failure": failure},
        )

    @staticmethod
    def _query_expansion_map(tickets: list[RetrievalFailureTicket]) -> dict[str, list[str]]:
        expansion: dict[str, list[str]] = {}
        for ticket in tickets:
            if ticket.reason != "semantic_miss":
                continue
            terms = [term for term in ticket.query.lower().replace("/", " ").split() if len(term) > 3]
            if terms:
                expansion[ticket.query] = sorted(set(terms + [term.replace("-", "_") for term in terms]))
        return expansion
