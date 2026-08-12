"""Matter-local explainable retrieval and external attorney-gold evaluation."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable

from legal.documents.workspace import workspace_paths
from legal.evals.attorney_retrieval_eval import AttorneyRetrievalEvalError, run_attorney_retrieval_eval
from legal.retrieval.index_builder import RetrievalIndexBuilder
from legal.retrieval.models import RetrievalDocument, coerce_document
from legal.retrieval.optional_backends import SQLiteHybridIndex, is_loopback_qdrant_url, optional_backend_status

MAX_QUERY_CHARS = 2_000
MAX_DOCUMENTS = 20_000
MAX_RESULTS = 100
MAX_LABELS = 64
MAX_LABEL_CHARS = 96
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RetrievalWorkbenchError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _text(row: dict[str, Any]) -> str:
    for key in ("text", "snippet", "text_excerpt", "derived_text", "content", "search_text"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _labels(value: Any) -> list[str]:
    """Normalize one label or a bounded label collection without iterating strings."""
    if isinstance(value, str):
        candidates = re.split(r"[,;|\n]+", value)
    elif isinstance(value, (list, tuple, set, frozenset)):
        candidates = list(value)
    else:
        candidates = []
    labels: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        label = " ".join(str(raw or "").replace("\x00", " ").split())[:MAX_LABEL_CHARS]
        key = label.casefold()
        if label and key not in seen:
            seen.add(key)
            labels.append(label)
        if len(labels) >= MAX_LABELS:
            break
    return labels


def _inside(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def _validated_external_root(root: Path | None, *, label: str) -> Path | None:
    if root is None:
        return None
    candidate = Path(root).expanduser()
    lexical = candidate.absolute()
    resolved = candidate.resolve(strict=False)
    project = PROJECT_ROOT.resolve(strict=True)
    if _inside(lexical, project) or _inside(resolved, project):
        raise RetrievalWorkbenchError(
            f"{label}_inside_source_tree",
            f"The external {label.replace('_', ' ')} must be stored outside the source tree.",
            status_code=409,
        )
    if candidate.exists() and candidate.is_symlink():
        raise RetrievalWorkbenchError(
            f"{label}_symlink_refused",
            f"A symlinked external {label.replace('_', ' ')} was refused.",
            status_code=409,
        )
    return resolved


def private_record_documents(records: Iterable[dict[str, Any]]) -> list[RetrievalDocument]:
    documents: list[RetrievalDocument] = []
    for row in records:
        if not isinstance(row, dict):
            continue
        text = _text(row)
        source_id = str(row.get("evidence_id") or row.get("source_id") or row.get("id") or "").strip()
        if not source_id or not text:
            continue
        documents.append(coerce_document({
            "source_id": source_id,
            "document_id": str(row.get("document_id") or source_id),
            "title": str(row.get("title") or row.get("safe_filename") or source_id),
            "text": text,
            "source_class": "private_record",
            "jurisdiction": "maine",
            "authority_status": "user_provided_only",
            "freshness_status": "unknown",
            "issue_labels": _labels(row.get("issue_labels") or row.get("issue_lanes")),
            "procedural_postures": _labels(row.get("procedural_postures")),
            "metadata": {
                "page_number": int(row.get("page_number") or 0),
                "source_hash": str(row.get("source_hash") or ""),
                "parser_status": str(row.get("parser_status") or ""),
                "ocr_status": str(row.get("ocr_status") or ""),
                "source_lane": "private_record",
                "does_not_prove": "A private-record match does not prove that an allegation is true or establish a legal conclusion.",
            },
        }))
        if len(documents) >= MAX_DOCUMENTS:
            break
    return documents


class RetrievalWorkbenchService:
    def __init__(self, case_root: Path, *, authority_data_root: Path | None = None, eval_root: Path | None = None):
        paths = workspace_paths(case_root)
        self.case_root = paths.case_root
        self.workspace_root = paths.root
        configured_authority = str(os.environ.get("MFL_AUTHORITY_DATA_ROOT") or "").strip()
        configured_eval = str(os.environ.get("MFL_EVAL_ROOT") or "").strip()
        self.authority_data_root = (authority_data_root or (Path(configured_authority) if configured_authority else None))
        self.eval_root = (eval_root or (Path(configured_eval) if configured_eval else None))

    def status(self, *, private_record_count: int = 0) -> dict[str, Any]:
        blockers: list[str] = []
        try:
            authority_root = _validated_external_root(self.authority_data_root, label="authority_data_root")
        except RetrievalWorkbenchError as exc:
            authority_root = None
            blockers.append(exc.code)
        try:
            eval_root = _validated_external_root(self.eval_root, label="eval_root")
        except RetrievalWorkbenchError as exc:
            eval_root = None
            blockers.append(exc.code)
        authority_ready = bool(authority_root and (authority_root / "embedding_store" / "retrieval_index_manifest.json").is_file())
        eval_ready = bool(eval_root and (eval_root / "maine_rag_retrieval_gold.jsonl").is_file())
        qdrant_url = str(os.environ.get("MFL_QDRANT_URL") or "").strip()
        return {
            "schema_version": "retrieval_workbench_status_v1",
            "backends": optional_backend_status(),
            "private_record_count": min(max(int(private_record_count), 0), MAX_DOCUMENTS),
            "authority_index_configured": authority_ready,
            "attorney_gold_dataset_configured": eval_ready,
            "qdrant_endpoint_admitted": bool(qdrant_url and is_loopback_qdrant_url(qdrant_url)),
            "automatic_network_calls": False,
            "default_mode": "embedded_local",
            "blockers": blockers,
            "review_required": True,
        }

    def authority_documents(self) -> list[RetrievalDocument]:
        if not self.authority_data_root:
            return []
        root = _validated_external_root(self.authority_data_root, label="authority_data_root")
        if root is None:
            return []
        try:
            return RetrievalIndexBuilder(data_root=root).load_documents()[:MAX_DOCUMENTS]
        except Exception:
            return []

    def search(
        self,
        query: str,
        *,
        private_records: Iterable[dict[str, Any]] = (),
        include_private_records: bool = True,
        include_authority: bool = True,
        top_k: int = 10,
    ) -> dict[str, Any]:
        query = " ".join(str(query or "").replace("\x00", " ").split())[:MAX_QUERY_CHARS]
        if not query:
            raise RetrievalWorkbenchError("query_required", "A retrieval query is required.")
        documents: list[RetrievalDocument] = []
        lane_counts = {"private_record": 0, "legal_authority": 0}
        if include_private_records:
            private = private_record_documents(private_records)
            documents.extend(private)
            lane_counts["private_record"] = len(private)
        if include_authority:
            authority = self.authority_documents()
            documents.extend(authority)
            lane_counts["legal_authority"] = len(authority)
        if not documents:
            return {
                "status": "blocked_no_indexed_documents",
                "query": query,
                "results": [],
                "diagnostics": {"document_count": 0, "network_used": False, "review_required": True},
                "blockers": ["no_indexed_private_records_or_verified_authority"],
                "review_required": True,
            }
        results, diagnostics = SQLiteHybridIndex(documents).search(query, top_k=max(1, min(int(top_k or 10), MAX_RESULTS)))
        rows = []
        for result in results:
            payload = result.to_dict(include_text=False)
            payload["why_this_matched"] = {
                "summary": result.explanation,
                "matched_terms": list(result.matched_terms),
                "component_scores": result.component_scores,
                "source_lane": result.document.metadata.get("source_lane") or ("private_record" if result.document.source_class == "private_record" else "legal_authority"),
            }
            rows.append(payload)
        return {
            "status": "pass" if rows else "no_matches",
            "query": query,
            "results": rows,
            "source_cards": [row["source_card"] for row in rows],
            "lane_counts": lane_counts,
            "diagnostics": diagnostics,
            "blockers": [] if rows else ["no_retrieval_match"],
            "what_this_does_not_prove": "Retrieval rank does not establish legal correctness, factual truth, authenticity, credibility, or filing readiness.",
            "review_required": True,
        }

    def evaluate_attorney_gold(self, *, min_rows: int = 1, top_k: int = 20) -> dict[str, Any]:
        if not self.eval_root:
            raise RetrievalWorkbenchError("eval_root_not_configured", "An external evaluation root is not configured.", status_code=409)
        eval_root = _validated_external_root(self.eval_root, label="eval_root")
        if eval_root is None:
            raise RetrievalWorkbenchError("eval_root_not_configured", "An external evaluation root is not configured.", status_code=409)
        dataset = eval_root / "maine_rag_retrieval_gold.jsonl"
        documents = self.authority_documents()
        if not documents:
            raise RetrievalWorkbenchError("authority_index_not_configured", "A verified external authority retrieval index is required.", status_code=409)
        index = SQLiteHybridIndex(documents)
        def search(query: str, limit: int) -> list[str]:
            results, _ = index.search(query, top_k=limit)
            return [row.source_id for row in results]
        try:
            report = run_attorney_retrieval_eval(dataset, search=search, min_attorney_rows=min_rows, top_k=top_k)
        except AttorneyRetrievalEvalError as exc:
            raise RetrievalWorkbenchError("attorney_gold_invalid", str(exc), status_code=409) from exc
        payload = report.to_dict()
        payload["failure_triage"] = self._triage_inline(payload.get("failures") or [], documents)
        return payload

    @staticmethod
    def _triage_inline(failures: list[dict[str, Any]], documents: list[RetrievalDocument]) -> dict[str, Any]:
        by_id = {row.source_id: row for row in documents}
        clusters: dict[str, int] = {}
        tickets = []
        for failure in failures[:500]:
            query = str(failure.get("query") or "")
            expected = list(failure.get("expected_source_ids") or [])
            retrieved = list(failure.get("retrieved_source_ids") or [])
            if any(value not in by_id for value in expected):
                reason = "missing_authority"
            elif any(by_id[value].freshness_status == "stale" for value in expected if value in by_id):
                reason = "stale_source"
            elif re_has_citation(query):
                reason = "missed_exact_citation"
            else:
                reason = "semantic_miss"
            clusters[reason] = clusters.get(reason, 0) + 1
            tickets.append({"reason": reason, "query": query, "expected_source_ids": expected, "retrieved_source_ids": retrieved})
        return {"status": "pass" if not tickets else "needs_retrieval_fixes", "clusters": clusters, "tickets": tickets, "review_required": True}


def re_has_citation(query: str) -> bool:
    import re
    return bool(re.search(r"\b(?:\d{1,2}-?[A-Z]?\s+M\.R\.S\.|\d{4}\s+ME\s+\d+|(?:FM|PA|CV|PB)-?\s?\d{3})\b", query, re.I))
