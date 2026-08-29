from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.answering.review_scope import BoundAnswerReview, text_hash
from legal.data_boundaries import default_external_data_root, ensure_external_authority_root
from legal.production.authority_product import AuthorityProductVerifier
from legal.law_court import LawCourtIntelligenceExtractor
from legal.retrieval.models import RetrievalResult
from legal.retrieval.query_expansion import expand_query_guarded
from legal.retrieval.retrieval_pipeline import RetrievalPipeline
from legal.retrieval.authority_gap_detector import AuthorityGapDetector
from legal.verifiers import LegalOutputVerifier, SourceAuthorityIndex, extract_citations

_MAX_SOURCE_ID_LENGTH = 256
_MAX_CITATION_TEXT_CHARS = 100_000
_MAX_JSON_BYTES = 64 * 1024 * 1024
_MAX_JSONL_LINE_BYTES = 2 * 1024 * 1024
_MAX_JSONL_ROWS = 250_000
_MAX_SOURCE_TEXT_CHARS = 50_000
_MAX_VERIFY_TEXT_CHARS = 200_000
_MAX_VERIFY_SOURCE_IDS = 64
_MAX_VERIFY_CLAIMS = 128
_MAX_VERIFY_QUOTES = 128
_MAX_VERIFY_CLAIM_CHARS = 20_000
_MAX_VERIFY_QUOTE_CHARS = 20_000
_MAX_FORM_SYNC_ROWS = 250
_INTERACTIVE_HYBRID_MAX_DOCUMENTS = 12_000
_FORM_IDENTIFIER_RE = re.compile(r"^[A-Z]{1,8}-[A-Z0-9][A-Z0-9-]{0,126}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_RETRIEVAL_PIPELINE_CACHE: dict[tuple[str, int, int], RetrievalPipeline] = {}
_RETRIEVAL_FAST_TEXT_CACHE: dict[
    tuple[str, int, int],
    tuple[tuple[Any, str, str, str], ...],
] = {}
_RETRIEVAL_PIPELINE_LOCK = threading.RLock()


@dataclass(frozen=True)
class ActiveAuthorityProduct:
    data_root: Path
    build_id: str
    manifest_path: Path
    manifest: dict[str, Any]


class AuthorityProductService:
    """Read-only API facade over the verified active external authority generation."""

    def __init__(self, *, data_root: str | Path | None = None) -> None:
        runtime_mode = str(os.environ.get("MFL_RUNTIME_MODE") or "source").strip().lower()
        configured = data_root
        if configured is None and runtime_mode == "store":
            configured = os.environ.get("MFL_AUTHORITY_DATA_ROOT") or os.environ.get("MAINE_FAMILY_LAW_DATA_ROOT")
        if configured is None:
            configured = os.environ.get("MAINE_FAMILY_LAW_DATA_ROOT") or os.environ.get("MFL_AUTHORITY_DATA_ROOT")
        configured = configured or default_external_data_root()
        self.data_root = ensure_external_authority_root(configured)

    def status(self) -> dict[str, Any]:
        report = AuthorityProductVerifier(data_root=self.data_root).verify()
        payload = report.as_dict()
        payload["active"] = report.status == "pass"
        payload["review_required"] = True
        if report.status == "pass":
            active = self._active_product(verify_all=False)
            payload.update(
                {
                    "product_version": active.manifest.get("product_version"),
                    "freshness_counts": active.manifest.get("freshness_counts") or {},
                    "retrieval_document_count": active.manifest.get("retrieval_document_count", 0),
                    "parsed_record_counts": active.manifest.get("parsed_record_counts") or {},
                }
            )
        return payload

    def authority_gap_review(self, *, issue: str = "") -> dict[str, Any]:
        """Review only active parsed-authority metadata for visible coverage gaps."""
        active = self._active_product(verify_all=False)
        sources: list[dict[str, Any]] = []

        def rows() -> Iterable[dict[str, Any]]:
            for row in self._authority_gap_rows(active):
                if len(sources) < 50 and (row.get("record_id") or row.get("source_id")):
                    sources.append(self._authority_gap_card(row, active.build_id))
                yield row

        report = AuthorityGapDetector().review(rows(), issue=issue)
        report["build_id"] = active.build_id
        report["sources"] = sources
        report["sources_truncated"] = report["record_count"] > len(sources)
        return report

    def _authority_gap_rows(self, active: ActiveAuthorityProduct) -> Iterable[dict[str, Any]]:
        """Never substitute mutable ingestion rows for the selected build."""
        yield from self._iter_active_parsed_rows(active)

    def _iter_active_parsed_rows(self, active: ActiveAuthorityProduct) -> Iterable[dict[str, Any]]:
        """Yield parsed rows materialized inside one hash-checked active build.

        The mutable ``parsed_authority_store`` is an ingestion workspace, not an
        admitted source of truth.  Every public source and source-derived
        inspection path must read the build-local parsed artifacts instead.
        """
        found = False
        build_root = self.data_root / "authority_product" / "builds" / active.build_id
        for artifact in active.manifest.get("artifacts") or []:
            role = str(artifact.get("role") or "")
            if "parsed_collection:" not in role:
                continue
            path = self._artifact_path(active, role_contains=role)
            if not path.is_relative_to(build_root):
                raise ValueError("authority_gap_artifact_outside_selected_build")
            found = True
            # Consumers needing verified rows must exhaust the iterator before
            # returning them. Hash the bytes actually parsed, not only a prior
            # read of a pathname that may be replaced between check and use.
            yield from self._iter_jsonl(
                path, expected_sha256=str(artifact.get("sha256") or ""),
                expected_size=int(artifact.get("size") or -1),
            )
        if not found:
            raise ValueError("authority_gap_parsed_artifacts_missing")

    def list_sources(
        self,
        *,
        query: str = "",
        source_class: str = "",
        freshness: str = "",
        issue_tag: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List only source cards admitted by the verified active build."""

        active = self._active_product(verify_all=True)
        query_text = str(query or "").strip().casefold()[:300]
        class_filter = str(source_class or "").strip().casefold()[:100]
        freshness_filter = str(freshness or "").strip().casefold()[:100]
        issue_filter = str(issue_tag or "").strip().casefold()[:200]
        safe_limit = max(1, min(int(limit or 100), 250))
        safe_offset = max(0, int(offset or 0))
        card_path = self._artifact_path(active, role_contains="authority_layer:source_cards")
        document_path = self._artifact_path(active, role_contains="retrieval_index:hybrid_documents", required=False)
        document_text: dict[str, str] = {}
        if document_path is not None:
            for row in self._iter_jsonl(document_path):
                source_id = str(row.get("source_id") or row.get("record_id") or "")
                if source_id and source_id not in document_text:
                    document_text[source_id] = str(row.get("text") or "")[:2_000]

        rows: list[dict[str, Any]] = []
        freshness_counts: dict[str, int] = {}
        source_class_counts: dict[str, int] = {}
        for raw in self._iter_jsonl(card_path):
            card = self._source_inventory_card(raw, document_text=document_text)
            source_id = str(card.get("source_id") or "")
            if not source_id:
                continue
            source_class_value = str(card.get("source_class") or "").casefold()
            source_class_group = self._source_class_group(source_class_value)
            freshness_value = self._freshness_bucket(str(card.get("freshness_status") or ""))
            issue_values = [str(value).casefold() for value in card.get("issue_tags") or []]
            blob = " ".join(
                (str(card.get("title") or ""), str(card.get("citation") or ""), str(card.get("snippet") or ""), " ".join(issue_values))
            ).casefold()
            freshness_counts[freshness_value] = freshness_counts.get(freshness_value, 0) + 1
            source_class_counts[source_class_group] = source_class_counts.get(source_class_group, 0) + 1
            if class_filter and class_filter not in source_class_value and class_filter != source_class_group:
                continue
            if freshness_filter and freshness_filter != freshness_value:
                continue
            if issue_filter and issue_filter not in blob:
                continue
            if query_text and query_text not in blob:
                continue
            rows.append(card)
        rows.sort(key=lambda row: (str(row.get("title") or "").casefold(), str(row.get("source_id") or "")))
        return {
            "status": "pass",
            "build_id": active.build_id,
            "count": len(rows),
            "offset": safe_offset,
            "limit": safe_limit,
            "sources": rows[safe_offset : safe_offset + safe_limit],
            "counts": freshness_counts,
            "source_class_counts": source_class_counts,
            "source_boundary": "verified_active_immutable_authority_build",
            "review_required": True,
        }

    @staticmethod
    def _authority_gap_card(row: dict[str, Any], build_id: str) -> dict[str, Any]:
        fields = ("source_class", "freshness_status", "parser_status", "retrieved_at", "source_hash")
        return {
            "source_id": str(row.get("record_id") or row.get("source_id") or ""),
            "title": str(row.get("title") or "Admitted source metadata")[:300],
            "metadata": {
                **{name: row.get(name) for name in fields},
                "source_lane": "legal_authority",
                "authority_gap_build_id": build_id,
                "review_required": True,
            },
        }

    def authority_gap_source(self, source_id: str, *, build_id: str) -> dict[str, Any]:
        active = self._active_product(verify_all=False)
        if active.build_id != build_id:
            return {"status": "blocked", "blockers": ["authority_gap_build_changed"], "review_required": True}
        for row in self._authority_gap_rows(active):
            if str(row.get("record_id") or row.get("source_id") or "") != source_id:
                continue
            text = str(row.get("text") or "")
            span = row.get("source_span") if isinstance(row.get("source_span"), dict) else {}
            start, end = span.get("start_offset"), span.get("end_offset")
            exact = type(start) is int and type(end) is int and 0 <= start < end <= len(text)
            return {
                "status": "pass", "source_id": source_id, "build_id": active.build_id,
                "source_card": self._authority_gap_card(row, active.build_id),
                "source_text": text[:_MAX_SOURCE_TEXT_CHARS],
                "text_truncated": len(text) > _MAX_SOURCE_TEXT_CHARS,
                "source_span": span if exact else {},
                "source_span_preview": text[start:end][:_MAX_SOURCE_TEXT_CHARS] if exact else "",
                "review_required": True,
            }
        return {"status": "not_found", "source_id": source_id, "review_required": True}

    def resolve_citations(self, text: str) -> dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            return {"status": "blocked", "blockers": ["citation_text_required"], "resolutions": []}
        if len(text) > _MAX_CITATION_TEXT_CHARS:
            return {"status": "blocked", "blockers": ["citation_text_too_large"], "resolutions": []}
        active = self._active_product(verify_all=False)
        index_path = self._artifact_path(active, role_contains="authority_layer:citation_index")
        rows = self._read_json(index_path)
        if not isinstance(rows, list):
            raise ValueError("citation index must be a JSON array")
        index = SourceAuthorityIndex.from_rows([row for row in rows if isinstance(row, dict)])
        return {
            "status": "pass",
            "build_id": active.build_id,
            "resolutions": [resolution.to_dict() for resolution in index.resolve_text(text)],
            "review_required": True,
        }

    def search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        """Search only the verified active authority generation.

        This is the canonical public research boundary.  Bundled seed fixtures
        are useful for development tests, but must never be represented as the
        currently admitted authority product in a release answer.
        """

        query = str(query or "").strip()
        if not query:
            return {
                "status": "blocked",
                "blockers": ["authority_query_required"],
                "retrieved_sources": [],
                "review_required": True,
            }
        if len(query) > _MAX_CITATION_TEXT_CHARS:
            return {
                "status": "blocked",
                "blockers": ["authority_query_too_large"],
                "retrieved_sources": [],
                "review_required": True,
            }
        safe_limit = max(1, min(int(limit or 5), 20))
        active = self._active_product(verify_all=False)
        document_path = self._artifact_path(
            active, role_contains="retrieval_index:hybrid_documents"
        )
        citation_path = self._artifact_path(
            active, role_contains="authority_layer:citation_index"
        )
        cache_key = (
            active.build_id,
            document_path.stat().st_mtime_ns,
            citation_path.stat().st_mtime_ns,
        )
        with _RETRIEVAL_PIPELINE_LOCK:
            pipeline = _RETRIEVAL_PIPELINE_CACHE.get(cache_key)
            if pipeline is None:
                documents = list(self._iter_jsonl(document_path))
                citation_rows = self._read_json(citation_path)
                if not isinstance(citation_rows, list):
                    raise ValueError("citation index must be a JSON array")
                authority_index = SourceAuthorityIndex.from_rows(
                    [row for row in citation_rows if isinstance(row, dict)]
                )
                pipeline = RetrievalPipeline(
                    documents,
                    authority_index=authority_index,
                )
                _RETRIEVAL_PIPELINE_CACHE.clear()
                _RETRIEVAL_PIPELINE_CACHE[cache_key] = pipeline
                _RETRIEVAL_FAST_TEXT_CACHE.clear()
                _RETRIEVAL_FAST_TEXT_CACHE[cache_key] = tuple(
                    (
                        document,
                        document.title.casefold(),
                        str(document.citation or "").casefold(),
                        document.text.casefold(),
                    )
                    for document in pipeline.documents
                )
        citation_context = [
            resolution.to_dict() for resolution in pipeline.authority_index.resolve_text(query)
        ] if pipeline.authority_index is not None else []
        if not citation_context and len(pipeline.documents) <= _INTERACTIVE_HYBRID_MAX_DOCUMENTS:
            # This stays entirely local and bounded.  Larger corpora retain the
            # cached lexical fallback below so a semantic scan cannot freeze a
            # modest desktop.  Exact citations always take precedence.
            result = pipeline.retrieve(query, top_k=safe_limit, include_text=True)
            result["retrieval_stack"] = {
                **dict(result.get("retrieval_stack") or {}),
                "semantic": "deterministic_sparse_embedding_adapter_bounded_local",
                "interactive_hybrid_document_cap": _INTERACTIVE_HYBRID_MAX_DOCUMENTS,
                "active_document_count": len(pipeline.documents),
                "fallback_reason": None,
            }
        elif citation_context:
            by_source_id = {document.source_id: document for document in pipeline.documents}
            exact_results: list[RetrievalResult] = []
            for resolution in citation_context:
                source_id = str(resolution.get("source_id") or "")
                if resolution.get("status") != "found" or source_id not in by_source_id:
                    continue
                exact_results.append(
                    RetrievalResult(
                        document=by_source_id[source_id],
                        score=1000.0 - len(exact_results),
                        method="admitted_exact_citation",
                        rank=len(exact_results) + 1,
                        matched_terms=("exact_citation",),
                        explanation="Exact citation resolved to an admitted official source",
                        component_scores={"exact_citation": 1000.0 - len(exact_results)},
                    )
                )
            result = {
                "query": query,
                "retrieved_sources": [item.to_dict(include_text=True) for item in exact_results[:safe_limit]],
                "source_cards": [item.document.source_card().__dict__ for item in exact_results[:safe_limit]],
                "citation_resolution_context": citation_context,
                "metrics_available": ["recall_at_k", "mrr", "ndcg", "precision_at_k"],
                "retrieval_stack": {
                    "lexical": "bypassed_for_admitted_exact_citation",
                    "semantic": "bypassed_for_admitted_exact_citation",
                    "fusion": "not_required",
                    "authority_weighting": True,
                    "freshness_weighting": True,
                    "issue_posture_weighting": False,
                    "parent_child_chunk_aware": False,
                    "interactive_hybrid_document_cap": _INTERACTIVE_HYBRID_MAX_DOCUMENTS,
                    "active_document_count": len(pipeline.documents),
                    "fallback_reason": "admitted_exact_citation_priority",
                },
                "review_required": True,
            }
        else:
            expansion = expand_query_guarded(query)
            terms = expansion.terms[:32]
            ranked: list[RetrievalResult] = []
            for document, title_text, citation_text, body_text in _RETRIEVAL_FAST_TEXT_CACHE.get(cache_key, ()):
                matched: list[str] = []
                score = 0.0
                for term in terms:
                    if term in citation_text:
                        score += 8.0
                        matched.append(term)
                    elif term in title_text:
                        score += 4.0
                        matched.append(term)
                    elif term in body_text:
                        score += 1.0
                        matched.append(term)
                if not matched:
                    continue
                score += {
                    "verified_official_maine": 0.30,
                    "verified_maine_law_court": 0.25,
                    "verified_federal": 0.15,
                }.get(document.authority_status, -0.10)
                score += {
                    "current": 0.15,
                    "fresh": 0.10,
                    "known_extracted_timestamp": 0.05,
                    "stale": -0.25,
                }.get(document.freshness_status, 0.0)
                ranked.append(
                    RetrievalResult(
                        document=document,
                        score=score,
                        method="cached_lexical_authority_weighted",
                        matched_terms=tuple(sorted(set(matched))),
                        explanation="Bounded cached lexical search with authority and freshness weighting",
                        component_scores={"cached_lexical": score},
                    )
                )
            ranked.sort(key=lambda item: (-item.score, item.document.source_id))
            ranked = [item.with_rank(index + 1) for index, item in enumerate(ranked[:safe_limit])]
            result = {
                "query": query,
                "retrieved_sources": [item.to_dict(include_text=True) for item in ranked],
                "source_cards": [item.document.source_card().__dict__ for item in ranked],
                "citation_resolution_context": [],
                "metrics_available": ["recall_at_k", "mrr", "ndcg", "precision_at_k"],
                "retrieval_stack": {
                    "lexical": "bounded_cached_lexical",
                    "semantic": "deferred_for_interactive_latency",
                    "fusion": "authority_and_freshness_weighted",
                    "authority_weighting": True,
                    "freshness_weighting": True,
                    "issue_posture_weighting": False,
                    "parent_child_chunk_aware": False,
                    "interactive_hybrid_document_cap": _INTERACTIVE_HYBRID_MAX_DOCUMENTS,
                    "active_document_count": len(pipeline.documents),
                    "fallback_reason": "corpus_exceeds_bounded_interactive_hybrid_cap",
                    "query_expansion": expansion.receipt(),
                },
                "review_required": True,
            }
        return {
            "status": "pass",
            "build_id": active.build_id,
            **result,
            "review_required": True,
        }

    def get_source(self, source_id: str) -> dict[str, Any]:
        source_id = str(source_id).strip()
        if not source_id or len(source_id) > _MAX_SOURCE_ID_LENGTH:
            return {"status": "blocked", "blockers": ["source_id_invalid"], "source_id": source_id}
        active = self._active_product(verify_all=False)
        card_path = self._artifact_path(active, role_contains="authority_layer:source_cards")
        card = next((row for row in self._iter_jsonl(card_path) if str(row.get("source_id")) == source_id), None)
        if card is None:
            return {
                "status": "not_found",
                "source_id": source_id,
                "build_id": active.build_id,
                "review_required": True,
            }
        document_path = self._artifact_path(active, role_contains="retrieval_index:hybrid_documents", required=False)
        source_text = None
        if document_path is not None:
            document = next(
                (row for row in self._iter_jsonl(document_path) if str(row.get("source_id")) == source_id),
                None,
            )
            if document is not None:
                full_source_text = str(document.get("text") or "")
                source_text = full_source_text[:_MAX_SOURCE_TEXT_CHARS]
            else:
                full_source_text = ""
        return {
            "status": "pass",
            "build_id": active.build_id,
            "source_id": source_id,
            "source_card": self._safe_source_card(card),
            "source_text": source_text,
            "text_truncated": bool(source_text is not None and len(full_source_text) > _MAX_SOURCE_TEXT_CHARS),
            "review_required": True,
        }

    def authority_lineage(self, source_id: str) -> dict[str, Any]:
        """Trace one admitted parsed source to its immutable build artifacts.

        This is a provenance inspection path. It neither fetches nor updates a
        source, and it never turns source lineage into a conclusion about legal
        currentness, authority weight, or legal effect.
        """
        source_id = str(source_id or "").strip()
        if (
            not source_id
            or len(source_id) > _MAX_SOURCE_ID_LENGTH
            or "/" in source_id
            or "\\" in source_id
            or "\x00" in source_id
            or source_id in {".", ".."}
        ):
            return {
                "status": "blocked",
                "source_id": source_id,
                "blockers": ["source_id_invalid"],
                "review_required": True,
            }
        active = self._active_product(verify_all=True)
        parsed_row: dict[str, Any] | None = None
        for row in self._iter_active_parsed_rows(active):
            canonical_id = str(row.get("record_id") or row.get("source_id") or "")
            snapshot_id = str(row.get("source_id") or canonical_id)
            if source_id in {canonical_id, snapshot_id}:
                parsed_row = row
                break
        if parsed_row is None:
            return {
                "status": "not_found",
                "source_id": source_id,
                "build_id": active.build_id,
                "blockers": ["admitted_parsed_source_not_found"],
                "review_required": True,
            }

        canonical_id = str(parsed_row.get("record_id") or parsed_row.get("source_id") or source_id)
        snapshot_id = str(parsed_row.get("source_id") or canonical_id)
        snapshot_rows = [
            row
            for row in active.manifest.get("source_snapshots") or []
            if isinstance(row, dict) and str(row.get("source_id") or "") == snapshot_id
        ]
        snapshot = snapshot_rows[0] if len(snapshot_rows) == 1 else None
        metadata = parsed_row.get("metadata") if isinstance(parsed_row.get("metadata"), dict) else {}
        fetch_metadata = metadata.get("fetch_metadata") if isinstance(metadata.get("fetch_metadata"), dict) else {}
        source_url = str(parsed_row.get("source_url_or_path") or metadata.get("source_url_or_path") or "").strip()
        if not source_url.startswith(("https://", "http://")):
            source_url = ""
        source_span = parsed_row.get("source_span") if isinstance(parsed_row.get("source_span"), dict) else {}
        parser_audit = parsed_row.get("parser_audit") if isinstance(parsed_row.get("parser_audit"), dict) else {}
        source_hash = str(parsed_row.get("source_hash") or parsed_row.get("hash") or "")
        snapshot_hash = str(snapshot.get("sha256") or "") if snapshot else ""
        blockers: list[str] = []
        if snapshot is None:
            blockers.append("snapshot_not_materialized_in_active_build")
        elif source_hash and snapshot_hash and source_hash != snapshot_hash:
            blockers.append("parsed_source_hash_does_not_match_active_snapshot")
        if not source_url:
            blockers.append("official_source_url_not_admitted_for_parsed_node")
        if not isinstance(source_span.get("start_offset"), int) or not isinstance(source_span.get("end_offset"), int):
            blockers.append("exact_parsed_source_span_unavailable")

        official_url = {
            "url": source_url or None,
            "admitted": bool(source_url),
            "review_required": True,
        }
        retrieval_event = {
            "target_id": metadata.get("target_id"),
            "retrieved_at": parsed_row.get("retrieved_at"),
            "http_status": metadata.get("status_code"),
            "observed_final_url": metadata.get("final_url"),
            "attempt_count": fetch_metadata.get("attempt_count"),
            "robots_policy_result": fetch_metadata.get("robots_policy_result"),
            "network_used_by_inspector": False,
        }
        parsed_node = {
            "source_id": canonical_id,
            "snapshot_source_id": snapshot_id,
            "authority_kind": parsed_row.get("authority_kind"),
            "source_class": parsed_row.get("source_class"),
            "jurisdiction": parsed_row.get("jurisdiction"),
            "citation": parsed_row.get("citation"),
            "parser_status": parsed_row.get("parser_status") or parser_audit.get("status"),
            "parser_name": parser_audit.get("parser_name"),
            "parser_version": parser_audit.get("parser_version"),
            "source_span": source_span,
            "parsed_record_locator": {
                "relative_path": parsed_row.get("_parsed_relative_path"),
                "line_number": parsed_row.get("_parsed_line_number"),
            },
            "source_hash": source_hash or None,
        }
        snapshot_artifact = {
            "relative_path": snapshot.get("relative_path") if snapshot else None,
            "sha256": snapshot_hash or None,
            "size": snapshot.get("size") if snapshot else None,
            "materialized_in_active_build": snapshot is not None,
        }
        build = {
            "build_id": active.build_id,
            "build_fingerprint": active.manifest.get("build_fingerprint"),
            "manifest_sha256": self._sha256_file(active.manifest_path),
            "manifest_schema_version": active.manifest.get("schema_version"),
            "data_root_policy": active.manifest.get("data_root_policy"),
        }
        return {
            "schema_version": "authority_lineage_v1",
            "status": "needs_review" if blockers else "lineage_observed",
            "source_id": canonical_id,
            "build": build,
            "official_source": official_url,
            "retrieval_event": retrieval_event,
            "parsed_node": parsed_node,
            "snapshot": snapshot_artifact,
            "blockers": blockers,
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
            "notice": (
                "This traces admitted provenance in the active immutable authority build. It does not fetch, "
                "refresh, interpret, or determine the currentness, authority weight, legal effect, or outcome."
            ),
        }

    def law_court_opinion_enrichment(self, source_id: str) -> dict[str, Any]:
        """Expose deterministic, source-bound Law Court opinion metadata.

        The result is an inspection aid rather than a case brief or treatment
        conclusion: every extracted signal and excerpt remains review-required,
        and unavailable opinion fields stay unavailable instead of being filled
        from model memory or an external request.
        """
        source_id = str(source_id or "").strip()
        if (
            not source_id
            or len(source_id) > _MAX_SOURCE_ID_LENGTH
            or "/" in source_id
            or "\\" in source_id
            or "\x00" in source_id
            or source_id in {".", ".."}
        ):
            return {"status": "blocked", "source_id": source_id, "blockers": ["source_id_invalid"], "review_required": True}
        active = self._active_product(verify_all=True)
        matched_rows: list[dict[str, Any]] = []
        for row in self._iter_active_parsed_rows(active):
            canonical_id = str(row.get("record_id") or row.get("source_id") or "")
            snapshot_id = str(row.get("source_id") or canonical_id)
            authority_kind = str(row.get("authority_kind") or "").casefold()
            source_class = str(row.get("source_class") or "").casefold()
            if source_id in {canonical_id, snapshot_id} and ("opinion" in authority_kind or "law_court" in source_class):
                matched_rows.append(row)
        if not matched_rows:
            return {
                "status": "not_found",
                "source_id": source_id,
                "build_id": active.build_id,
                "blockers": ["admitted_law_court_opinion_not_found"],
                "review_required": True,
            }

        # Index/reference rows may intentionally share a canonical source ID
        # with a direct PDF extraction.  Prefer the admitted row that can
        # actually support an exact inspection; never let an empty reference
        # shadow the corresponding direct text merely because it was iterated
        # first.
        parsed_row = max(
            matched_rows,
            key=lambda row: (
                bool(str(row.get("text") or row.get("body") or row.get("instructions") or "")),
                len(str(row.get("text") or row.get("body") or row.get("instructions") or "")),
                str(row.get("parser_status") or "").casefold() in {"parsed", "complete", "success"},
            ),
        )

        canonical_id = str(parsed_row.get("record_id") or parsed_row.get("source_id") or source_id)
        snapshot_id = str(parsed_row.get("source_id") or canonical_id)
        snapshot = next(
            (
                row
                for row in active.manifest.get("source_snapshots") or []
                if isinstance(row, dict) and str(row.get("source_id") or "") == snapshot_id
            ),
            None,
        )
        text = str(parsed_row.get("text") or "")[:_MAX_VERIFY_TEXT_CHARS]
        source_hash = str(parsed_row.get("source_hash") or parsed_row.get("hash") or "")
        snapshot_hash = str(snapshot.get("sha256") or "") if snapshot else ""
        blockers: list[str] = []
        if snapshot is None:
            blockers.append("opinion_snapshot_not_materialized_in_active_build")
        elif source_hash and snapshot_hash and source_hash != snapshot_hash:
            blockers.append("opinion_parsed_hash_does_not_match_active_snapshot")
        if not text:
            blockers.append("opinion_text_unavailable")
        source_span = parsed_row.get("source_span") if isinstance(parsed_row.get("source_span"), dict) else {}
        source_start = source_span.get("start_offset") if isinstance(source_span.get("start_offset"), int) else 0

        def exact_span(start: int, end: int) -> dict[str, int]:
            return {"start_offset": source_start + start, "end_offset": source_start + end}

        paragraph_map: list[dict[str, Any]] = []
        # Some otherwise readable PDF extracts replace the paragraph glyph with
        # U+FFFD. Treat that explicit extracted marker the same as a printed
        # paragraph glyph, while keeping every returned locator in the exact
        # admitted text. This does not reconstruct or infer a missing marker.
        paragraph_marker = r"(?:\[\s*)?(?:¶|\uFFFD)\s*(\d+)\s*(?:\])?"
        paragraph_markers = list(re.finditer(r"(?:^|\n)\s*" + paragraph_marker, text))
        if not paragraph_markers:
            paragraph_markers = list(re.finditer(paragraph_marker, text))
        for index, marker in enumerate(paragraph_markers[:500]):
            start = marker.start()
            end = paragraph_markers[index + 1].start() if index + 1 < len(paragraph_markers) else len(text)
            excerpt = text[start:end].strip()
            if excerpt:
                paragraph_map.append(
                    {
                        "paragraph": marker.group(1),
                        "source_span": exact_span(start, end),
                        "preview": excerpt[:1_000],
                        "review_required": True,
                    }
                )
        if not paragraph_map:
            blockers.append("opinion_paragraph_map_unavailable")

        parsed_citations = extract_citations(text)[:250] if text else []
        cited_authorities = [
            {
                "citation": citation.to_dict(),
                "source_span": exact_span(citation.start, citation.end),
                "resolution_status": "not_resolved_by_opinion_enrichment",
                "review_required": True,
            }
            for citation in parsed_citations
        ]
        extractor = LawCourtIntelligenceExtractor()
        brief = extractor.extract_case_brief(text, source_id=canonical_id, citation=parsed_row.get("citation")) if text else {}
        disposition_value = str(brief.get("disposition") or "unknown")
        disposition_span: dict[str, int] | None = None
        for term in ("affirm", "vacat", "remand", "revers", "dismiss"):
            match = re.search(rf"\b{term}\w*\b", text, re.I)
            if match:
                disposition_span = exact_span(match.start(), match.end())
                break
        if disposition_value == "unknown" or disposition_span is None:
            blockers.append("opinion_disposition_exact_span_unavailable")

        neutral_excerpt: dict[str, Any] | None = None
        if paragraph_map:
            neutral_excerpt = {
                "status": "exact_source_excerpt",
                "source_span": paragraph_map[0]["source_span"],
                "text": paragraph_map[0]["preview"],
                "review_required": True,
            }
        elif text:
            first_end = min(len(text), 1_000)
            neutral_excerpt = {
                "status": "exact_source_excerpt",
                "source_span": exact_span(0, first_end),
                "text": text[:first_end],
                "review_required": True,
            }
        else:
            neutral_excerpt = {"status": "unavailable", "text": None, "review_required": True}

        panel_value = parsed_row.get("panel") or parsed_row.get("justices")
        official_url = str(parsed_row.get("source_url_or_path") or "")
        if not official_url.startswith(("https://", "http://")):
            official_url = ""
            blockers.append("opinion_official_url_not_admitted")
        return {
            "schema_version": "law_court_opinion_enrichment_v1",
            "status": "enrichment_observed" if not blockers else "needs_review",
            "source_id": canonical_id,
            "build": {
                "build_id": active.build_id,
                "build_fingerprint": active.manifest.get("build_fingerprint"),
                "manifest_sha256": self._sha256_file(active.manifest_path),
            },
            "opinion": {
                "title": parsed_row.get("title"),
                "citation": parsed_row.get("citation"),
                "decision_date": parsed_row.get("decision_date") or brief.get("decision_date"),
                "docket_number": parsed_row.get("docket_number") or brief.get("docket_number"),
                "court": parsed_row.get("court") or brief.get("court"),
                "panel": {"value": panel_value, "status": "admitted" if panel_value else "not_admitted", "review_required": True},
                "disposition": {
                    "value": disposition_value,
                    "status": "deterministic_signal_review_required",
                    "source_span": disposition_span,
                    "review_required": True,
                },
                "paragraph_map": paragraph_map,
                "cited_authorities": cited_authorities,
                "neutral_case_summary": neutral_excerpt,
                "exact_source_span": source_span or None,
                "source_hash": source_hash or None,
                "snapshot_sha256": snapshot_hash or None,
                "official_url": official_url or None,
            },
            "blockers": sorted(set(blockers)),
            "review_required": True,
            "network_used": False,
            "current_law_determined": False,
            "treatment_determined": False,
            "notice": (
                "Opinion metadata and excerpts are deterministic source-bound inspection aids. They do not determine "
                "a holding, treatment, current law, precedential weight, or outcome. Review the exact official source."
            ),
        }

    def rule_history_timeline(self, query: str) -> dict[str, Any]:
        """Show explicitly admitted amendment/effective-date metadata for rules.

        The timeline does not infer a rule's legal effect, supersession, or what
        applied on any date. Missing explicit metadata stays a blocker.
        """
        query = str(query or "").strip()
        if not query or len(query) > _MAX_SOURCE_ID_LENGTH:
            return {"status": "blocked", "query": query, "blockers": ["rule_query_invalid"], "review_required": True}
        active = self._active_product(verify_all=True)
        normalized_query = re.sub(r"[^a-z0-9]", "", query.casefold())
        snapshot_by_id = {
            str(row.get("source_id") or ""): row
            for row in active.manifest.get("source_snapshots") or []
            if isinstance(row, dict)
        }
        matches: list[dict[str, Any]] = []
        for row in self._iter_active_parsed_rows(active):
            kind = str(row.get("authority_kind") or "").casefold()
            source_class = str(row.get("source_class") or "").casefold()
            if "rule" not in kind and "rule" not in source_class:
                continue
            searchable = " ".join(
                str(row.get(key) or "")
                for key in ("record_id", "source_id", "citation", "rule_set", "rule_number", "title")
            )
            normalized_searchable = re.sub(r"[^a-z0-9]", "", searchable.casefold())
            if query.casefold() not in searchable.casefold() and normalized_query not in normalized_searchable:
                continue
            matches.append(row)
            if len(matches) >= 100:
                break
        if not matches:
            return {
                "status": "not_found",
                "query": query,
                "build_id": active.build_id,
                "timeline": [],
                "blockers": ["admitted_rule_not_found"],
                "review_required": True,
            }

        blockers: list[str] = []
        timeline: list[dict[str, Any]] = []
        for row in matches:
            text = str(row.get("text") or "")[:_MAX_VERIFY_TEXT_CHARS]
            source_span = row.get("source_span") if isinstance(row.get("source_span"), dict) else {}
            source_start = source_span.get("start_offset") if isinstance(source_span.get("start_offset"), int) else 0
            source_id = str(row.get("source_id") or row.get("record_id") or "")
            snapshot = snapshot_by_id.get(source_id)
            source_hash = str(row.get("source_hash") or row.get("hash") or "")
            snapshot_hash = str(snapshot.get("sha256") or "") if snapshot else ""
            row_blockers: list[str] = []
            if snapshot is None:
                row_blockers.append("rule_snapshot_not_materialized_in_active_build")
            elif source_hash and snapshot_hash and source_hash != snapshot_hash:
                row_blockers.append("rule_parsed_hash_does_not_match_active_snapshot")
            official_url = str(row.get("source_url_or_path") or "")
            if not official_url.startswith(("https://", "http://")):
                official_url = ""
                row_blockers.append("rule_official_url_not_admitted")
            effective_date = str(row.get("effective_date") or "").strip()
            raw_history = row.get("amendment_history") if isinstance(row.get("amendment_history"), list) else []
            history = [item for item in raw_history if isinstance(item, dict)][:100]
            event_rows: list[dict[str, Any]] = []
            for event, date in [("effective", effective_date), *[(str(item.get("event") or "amendment"), str(item.get("date") or "")) for item in history]]:
                if not date:
                    continue
                match = re.search(re.escape(date), text, re.I) if text else None
                if not match:
                    row_blockers.append("rule_history_event_exact_span_unavailable")
                    span = None
                else:
                    span = {"start_offset": source_start + match.start(), "end_offset": source_start + match.end()}
                event_rows.append(
                    {
                        "event": event,
                        "date": date,
                        "source_span": span,
                        "review_required": True,
                    }
                )
            if not event_rows:
                row_blockers.append("rule_effective_or_amendment_history_unavailable")
            blockers.extend(f"{code}:{str(row.get('record_id') or source_id)}" for code in row_blockers)
            timeline.append(
                {
                    "source_id": str(row.get("record_id") or source_id),
                    "snapshot_source_id": source_id,
                    "citation": row.get("citation"),
                    "title": row.get("title"),
                    "rule_set": row.get("rule_set"),
                    "rule_number": row.get("rule_number"),
                    "events": event_rows,
                    "source_hash": source_hash or None,
                    "snapshot_sha256": snapshot_hash or None,
                    "official_url": official_url or None,
                    "blockers": sorted(set(row_blockers)),
                    "review_required": True,
                }
            )
        blockers = sorted(set(blockers))
        return {
            "schema_version": "rule_history_timeline_v1",
            "status": "timeline_observed" if not blockers else "needs_review",
            "query": query,
            "build": {
                "build_id": active.build_id,
                "build_fingerprint": active.manifest.get("build_fingerprint"),
                "manifest_sha256": self._sha256_file(active.manifest_path),
            },
            "timeline": timeline,
            "blockers": blockers,
            "review_required": True,
            "network_used": False,
            "as_of_determined": False,
            "notice": (
                "This is an admitted metadata timeline only. It does not determine what rule version applied, whether "
                "a rule was superseded, or the legal effect of an amendment. Review the exact official source."
            ),
        }

    def citation_graph_neighbors(self, source_id: str) -> dict[str, Any]:
        """Return admitted parsed citation edges; an edge has no treatment conclusion."""
        source_id = str(source_id or "").strip()
        if not source_id or len(source_id) > _MAX_SOURCE_ID_LENGTH:
            return {"status": "blocked", "blockers": ["source_id_invalid"], "review_required": True}
        active = self._active_product(verify_all=False)
        graph_path = self._artifact_path(active, role_contains="authority_layer:authority_graph", required=False)
        if graph_path is None:
            return {"status": "unavailable", "build_id": active.build_id, "source_id": source_id, "edges": [], "blockers": ["authority_graph_not_in_active_build"], "review_required": True}
        graph = self._read_json(graph_path)
        if not isinstance(graph, dict):
            raise ValueError("authority graph must be a JSON object")
        edges = [dict(item) for item in list(graph.get(source_id) or []) if isinstance(item, dict)][:50]
        return {"status": "pass", "build_id": active.build_id, "source_id": source_id, "edges": edges, "edge_count": len(edges), "review_required": True, "boundary": "Parsed citation relationships only; not controlling weight, negative treatment, currentness, or legal effect."}

    def get_source_span(
        self,
        source_id: str,
        *,
        start_offset: int,
        end_offset: int,
    ) -> dict[str, Any]:
        """Return an exact span from the admitted parsed source text."""

        source_id = str(source_id or "").strip()
        if not source_id or len(source_id) > _MAX_SOURCE_ID_LENGTH:
            return {"status": "blocked", "blockers": ["source_id_invalid"], "review_required": True}
        try:
            requested_start = int(start_offset)
            requested_end = int(end_offset)
        except (TypeError, ValueError):
            return {"status": "blocked", "blockers": ["source_span_offsets_invalid"], "review_required": True}
        if requested_start < 0 or requested_end < requested_start:
            return {"status": "blocked", "blockers": ["source_span_offsets_invalid"], "review_required": True}
        active = self._active_product(verify_all=True)
        canonical_rows: list[dict[str, Any]] = []
        snapshot_rows: list[dict[str, Any]] = []
        for row in self._iter_active_parsed_rows(active):
            canonical_id = str(row.get("record_id") or row.get("source_id") or "")
            snapshot_id = str(row.get("source_id") or canonical_id)
            if canonical_id == source_id:
                canonical_rows.append(row)
            elif snapshot_id == source_id:
                snapshot_rows.append(row)
        candidates = canonical_rows or snapshot_rows
        for row in sorted(
            candidates,
            key=lambda item: len(str(item.get("text") or item.get("body") or item.get("instructions") or "")),
            reverse=True,
        ):
            text = str(row.get("text") or row.get("body") or row.get("instructions") or "")
            if requested_end > len(text):
                continue
            return {
                "status": "pass",
                "source_id": source_id,
                "build_id": active.build_id,
                "source_span": {"start_offset": requested_start, "end_offset": requested_end},
                "source_span_preview": text[requested_start:requested_end],
                "source_text": text[:_MAX_SOURCE_TEXT_CHARS],
                "text_truncated": len(text) > _MAX_SOURCE_TEXT_CHARS,
                "review_required": True,
            }
        if candidates:
            return {
                "status": "blocked",
                "source_id": source_id,
                "build_id": active.build_id,
                "blockers": ["source_span_outside_admitted_text"],
                "review_required": True,
            }
        return {"status": "not_found", "source_id": source_id, "review_required": True}


    def list_forms(self, *, query: str = "", limit: int = 100) -> dict[str, Any]:
        """List bounded official court-form cards from the verified active generation."""
        limit = max(1, min(int(limit or 100), 500))
        query_text = str(query or "").strip().casefold()[:300]
        active = self._active_product(verify_all=False)
        card_path = self._artifact_path(active, role_contains="authority_layer:source_cards")
        document_path = self._artifact_path(active, role_contains="retrieval_index:hybrid_documents", required=False)
        document_text: dict[str, str] = {}
        if document_path is not None:
            for row in self._iter_jsonl(document_path):
                source_id = str(row.get("source_id") or "")
                if source_id and source_id not in document_text:
                    document_text[source_id] = str(row.get("text") or "")[:200_000]
        form_re = __import__("re").compile(r"\b(?:FM|PA|CV|PB)[\s-]*\d{3}[A-Z]?\b", __import__("re").I)
        rows: list[dict[str, Any]] = []
        for raw in self._iter_jsonl(card_path):
            safe = self._safe_source_card(raw)
            source_id = str(safe.get("source_id") or safe.get("record_id") or "")
            title = str(safe.get("title") or "")
            citation = str(safe.get("citation") or "")
            metadata = safe.get("metadata") if isinstance(safe.get("metadata"), dict) else {}
            source_class = str(safe.get("source_class") or metadata.get("source_class") or metadata.get("source_type") or "").casefold()
            joined = " ".join((str(safe.get("form_id") or ""), str(metadata.get("form_id") or ""), title, citation, document_text.get(source_id, "")[:2_000]))
            match = form_re.search(joined)
            if "form" not in source_class and not match:
                continue
            if query_text and query_text not in joined.casefold():
                continue
            form_id = match.group(0).upper().replace(" ", "-") if match else str(safe.get("form_id") or metadata.get("form_id") or "").upper()
            form_id = __import__("re").sub(r"-+", "-", form_id)
            row = {
                "source_id": source_id,
                "form_id": form_id,
                "title": title or form_id or "Maine court form",
                "citation": citation or form_id,
                "source_class": safe.get("source_class") or metadata.get("source_class") or "court_form",
                "jurisdiction": safe.get("jurisdiction") or metadata.get("jurisdiction") or "maine",
                "authority_status": safe.get("authority_status") or metadata.get("authority_status") or "stale_unknown",
                "freshness_status": safe.get("freshness_status") or metadata.get("freshness_status") or "unknown",
                "version_date": safe.get("version_date") or metadata.get("version_date"),
                "source_hash": safe.get("source_hash") or safe.get("hash") or metadata.get("source_hash") or metadata.get("hash"),
                "issue_labels": safe.get("issue_labels") or metadata.get("issue_labels") or [],
                "source_url_or_path": safe.get("source_url_or_path"),
                "text": document_text.get(source_id, "")[:50_000],
                "review_required": True,
            }
            rows.append(row)
            if len(rows) >= limit:
                break
        rows.sort(key=lambda row: (str(row.get("form_id") or ""), str(row.get("title") or ""), str(row.get("source_id") or "")))
        return {
            "status": "pass",
            "build_id": active.build_id,
            "forms": rows,
            "count": len(rows),
            "query": query_text,
            "review_required": True,
        }

    def synchronize_forms(self, installed_forms: Iterable[dict[str, Any]] | None) -> dict[str, Any]:
        """Compare installed form metadata with the admitted active form catalog.

        This accepts identifiers, version dates, source IDs, and hashes only.
        It never reads a form file, fetches an official catalog, persists local
        form metadata, or treats a catalog match as filing approval.
        """
        if not isinstance(installed_forms, (list, tuple)):
            installed_rows: list[Any] = []
            input_error = "installed_form_metadata_invalid"
        else:
            installed_rows = list(installed_forms)
            input_error = ""
        if input_error or not installed_rows:
            return {
                "status": "blocked",
                "installed_forms": [],
                "blockers": [input_error or "installed_form_metadata_required"],
                "review_required": True,
                "completion_blocked": True,
                "network_used": False,
            }
        if len(installed_rows) > _MAX_FORM_SYNC_ROWS:
            return {
                "status": "blocked",
                "installed_forms": [],
                "blockers": ["installed_form_metadata_count_exceeded"],
                "review_required": True,
                "completion_blocked": True,
                "network_used": False,
            }

        allowed_fields = {"form_id", "source_id", "version_date", "sha256"}
        normalized: list[dict[str, str]] = []
        validation_blockers: list[str] = []
        for index, raw in enumerate(installed_rows):
            if not isinstance(raw, dict):
                validation_blockers.append(f"installed_form_metadata_invalid:{index}")
                continue
            unexpected = sorted(str(key) for key, value in raw.items() if key not in allowed_fields and value not in (None, "", [], {}))
            if unexpected:
                validation_blockers.append(f"installed_form_metadata_field_not_allowed:{index}")
                continue
            form_id = re.sub(r"-+", "-", re.sub(r"[\s_]+", "-", str(raw.get("form_id") or "").strip().upper()))
            source_id = str(raw.get("source_id") or "").strip()
            version_date = str(raw.get("version_date") or "").strip()
            sha256 = str(raw.get("sha256") or "").strip().lower()
            if not _FORM_IDENTIFIER_RE.fullmatch(form_id):
                validation_blockers.append(f"installed_form_id_invalid:{index}")
                continue
            if source_id and (len(source_id) > _MAX_SOURCE_ID_LENGTH or "/" in source_id or "\\" in source_id or "\x00" in source_id):
                validation_blockers.append(f"installed_form_source_id_invalid:{index}")
                continue
            if sha256 and not _SHA256_RE.fullmatch(sha256):
                validation_blockers.append(f"installed_form_hash_invalid:{index}")
                continue
            if version_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", version_date):
                validation_blockers.append(f"installed_form_version_date_invalid:{index}")
                continue
            if not version_date and not sha256:
                validation_blockers.append(f"installed_form_version_metadata_missing:{index}")
                continue
            normalized.append({"form_id": form_id, "source_id": source_id, "version_date": version_date, "sha256": sha256})

        if validation_blockers:
            return {
                "status": "blocked",
                "installed_forms": normalized,
                "rows": [],
                "blockers": sorted(set(validation_blockers)),
                "review_required": True,
                "completion_blocked": True,
                "network_used": False,
                "persistent_state_changed": False,
            }

        catalog = self.list_forms(limit=500)
        by_form_id: dict[str, list[dict[str, Any]]] = {}
        for row in catalog.get("forms") or []:
            if not isinstance(row, dict):
                continue
            form_id = str(row.get("form_id") or "").upper().replace(" ", "-")
            if form_id:
                by_form_id.setdefault(form_id, []).append(row)

        rows: list[dict[str, Any]] = []
        blockers: list[str] = []
        accepted_freshness = {"fresh", "current", "known_version_date"}
        for installed in normalized:
            candidates = by_form_id.get(installed["form_id"], [])
            if installed["source_id"]:
                source_matches = [row for row in candidates if str(row.get("source_id") or "") == installed["source_id"]]
                if source_matches:
                    candidates = source_matches
            admitted_candidate_versions = {str(row.get("version_date") or "") for row in candidates if str(row.get("version_date") or "")}
            admitted_candidate_hashes = {str(row.get("source_hash") or "").lower() for row in candidates if str(row.get("source_hash") or "")}
            if installed["sha256"]:
                hash_matches = [row for row in candidates if str(row.get("source_hash") or "").lower() == installed["sha256"]]
                if hash_matches:
                    candidates = hash_matches
            if installed["version_date"]:
                version_matches = [row for row in candidates if str(row.get("version_date") or "") == installed["version_date"]]
                if version_matches:
                    candidates = version_matches
            official = candidates[0] if candidates else None
            row_blockers: list[str] = []
            status = "catalog_match"
            if official is None:
                status = "not_in_active_official_catalog"
                row_blockers.append("form_not_in_active_official_catalog")
            else:
                if len(admitted_candidate_versions) > 1 or len(admitted_candidate_hashes) > 1:
                    status = "active_catalog_metadata_conflict"
                    row_blockers.append("active_catalog_form_metadata_conflict")
                freshness = str(official.get("freshness_status") or "unknown").casefold()
                official_hash = str(official.get("source_hash") or "").lower()
                official_version = str(official.get("version_date") or "")
                if freshness not in accepted_freshness:
                    status = "official_catalog_entry_not_current"
                    row_blockers.append("official_form_freshness_not_verified")
                if installed["sha256"] and official_hash and installed["sha256"] != official_hash:
                    status = "source_hash_mismatch"
                    row_blockers.append("installed_form_hash_differs_from_active_catalog")
                elif installed["sha256"] and not official_hash:
                    status = "official_hash_unavailable"
                    row_blockers.append("active_catalog_form_hash_unavailable")
                if installed["version_date"] and official_version and installed["version_date"] != official_version:
                    status = "version_date_mismatch"
                    row_blockers.append("installed_form_version_differs_from_active_catalog")
                elif installed["version_date"] and not official_version:
                    status = "official_version_unavailable"
                    row_blockers.append("active_catalog_form_version_unavailable")
            blockers.extend(f"{code}:{installed['form_id']}" for code in row_blockers)
            rows.append(
                {
                    "installed": installed,
                    "status": status,
                    "official": {
                        key: official.get(key)
                        for key in ("source_id", "form_id", "title", "citation", "freshness_status", "version_date", "source_hash", "source_url_or_path")
                    }
                    if official
                    else None,
                    "blockers": row_blockers,
                    "review_required": True,
                }
            )
        blockers = sorted(set(blockers))
        return {
            "schema_version": "form_catalog_synchronization_v1",
            "status": "synchronized_review_required" if not blockers else "completion_blocked",
            "authority_build_id": catalog.get("build_id"),
            "rows": rows,
            "installed_forms": normalized,
            "blockers": blockers,
            "completion_blocked": bool(blockers),
            "catalog_match_for_completion": not blockers,
            "review_required": True,
            "network_used": False,
            "persistent_state_changed": False,
            "notice": (
                "This compares local form metadata to the admitted active catalog only. A catalog match does not "
                "complete a form, determine filing readiness, or replace human review."
            ),
        }

    def verify_output(
        self,
        *,
        text: str,
        source_ids: Iterable[str] | None = None,
        quotes: Iterable[dict[str, Any]] | None = None,
        claims: Iterable[dict[str, Any] | str] | None = None,
        expected_jurisdiction: str = "maine",
        auto_extract_claims: bool = True,
        review_scope: BoundAnswerReview | None = None,
    ) -> dict[str, Any]:
        """Verify an answer against the immutable active authority generation.

        Caller-provided source metadata is intentionally ignored. Only source
        cards and text admitted into the verified active generation may support
        legal claims.
        """
        if not isinstance(text, str) or not text.strip():
            return {"status": "blocked", "blockers": ["verification_text_required"], "review_required": True}
        if len(text) > _MAX_VERIFY_TEXT_CHARS:
            return {"status": "blocked", "blockers": ["verification_text_too_large"], "review_required": True}

        explicit_ids = []
        seen_ids: set[str] = set()
        for raw in source_ids or []:
            source_id = str(raw).strip()
            if not source_id or len(source_id) > _MAX_SOURCE_ID_LENGTH or source_id in seen_ids:
                continue
            seen_ids.add(source_id)
            explicit_ids.append(source_id)
        if len(explicit_ids) > _MAX_VERIFY_SOURCE_IDS:
            return {"status": "blocked", "blockers": ["verification_source_count_exceeded"], "review_required": True}

        jurisdiction = str(expected_jurisdiction or "maine").strip().lower()
        if jurisdiction != "maine":
            return {"status": "blocked", "blockers": ["verification_jurisdiction_not_allowed"], "review_required": True}

        quote_rows: list[dict[str, Any]] = []
        for row in quotes or []:
            if not isinstance(row, dict):
                continue
            quoted_text = str(row.get("quoted_text") or "")
            source_id = str(row.get("source_id") or "").strip()
            if not quoted_text or len(quoted_text) > _MAX_VERIFY_QUOTE_CHARS:
                continue
            if not source_id or len(source_id) > _MAX_SOURCE_ID_LENGTH:
                continue
            quote_rows.append({"quoted_text": quoted_text, "source_id": source_id})
            if len(quote_rows) >= _MAX_VERIFY_QUOTES:
                break

        claim_rows: list[dict[str, Any] | str] = []
        for row in claims or []:
            if isinstance(row, str):
                if 0 < len(row) <= _MAX_VERIFY_CLAIM_CHARS:
                    claim_rows.append(row)
            elif isinstance(row, dict):
                claim = str(row.get("claim") or "")
                if not claim or len(claim) > _MAX_VERIFY_CLAIM_CHARS:
                    continue
                admitted_claim_sources = []
                for raw_source_id in row.get("source_ids") or []:
                    claim_source_id = str(raw_source_id).strip()
                    if claim_source_id in seen_ids and claim_source_id not in admitted_claim_sources:
                        admitted_claim_sources.append(claim_source_id)
                claim_rows.append({"claim": claim, "source_ids": admitted_claim_sources})
            if len(claim_rows) >= _MAX_VERIFY_CLAIMS:
                break
        active = self._active_product(verify_all=False)
        assertion_text = text
        if review_scope is not None:
            if (not isinstance(review_scope, BoundAnswerReview)
                    or review_scope.answer_sha256 != text_hash(text)
                    or review_scope.assertions.authority_build_id != active.build_id
                    or set(review_scope.assertions.source_ids) != set(explicit_ids)):
                return {"status": "blocked", "blockers": ["answer_review_scope_source_changed"], "review_required": True}
            assertion_text = review_scope.assertions.text
            quote_rows.extend({"source_id": source_id, "quoted_text": quoted_text}
                              for source_id, quoted_text in review_scope.assertions.quotes)
        citation_path = self._artifact_path(active, role_contains="authority_layer:citation_index")
        citation_rows = self._read_json(citation_path)
        if not isinstance(citation_rows, list):
            raise ValueError("citation index must be a JSON array")
        index = SourceAuthorityIndex.from_rows([row for row in citation_rows if isinstance(row, dict)])

        selected_ids = list(explicit_ids)
        for resolution in index.resolve_text(text):
            for candidate in resolution.candidates:
                source_id = str(candidate.get("source_id") or "").strip()
                if source_id and source_id not in seen_ids and len(selected_ids) < _MAX_VERIFY_SOURCE_IDS:
                    seen_ids.add(source_id)
                    selected_ids.append(source_id)
            if resolution.source_id and resolution.source_id not in seen_ids and len(selected_ids) < _MAX_VERIFY_SOURCE_IDS:
                seen_ids.add(resolution.source_id)
                selected_ids.append(resolution.source_id)
        for quote in quote_rows:
            source_id = str(quote.get("source_id") or "").strip()
            if source_id and source_id not in seen_ids and len(selected_ids) < _MAX_VERIFY_SOURCE_IDS:
                seen_ids.add(source_id)
                selected_ids.append(source_id)

        card_path = self._artifact_path(active, role_contains="authority_layer:source_cards")
        cards: dict[str, dict[str, Any]] = {}
        selected_set = set(selected_ids)
        for row in self._iter_jsonl(card_path):
            source_id = str(row.get("source_id") or row.get("record_id") or "")
            if source_id in selected_set:
                cards[source_id] = self._safe_source_card(row)
                if len(cards) == len(selected_set):
                    break

        document_path = self._artifact_path(active, role_contains="retrieval_index:hybrid_documents", required=False)
        documents: dict[str, dict[str, Any]] = {}
        if document_path is not None:
            for row in self._iter_jsonl(document_path):
                source_id = str(row.get("source_id") or row.get("record_id") or "")
                if source_id in selected_set:
                    documents[source_id] = row
                    if len(documents) == len(selected_set):
                        break

        source_texts: dict[str, str] = {}
        source_metadata: dict[str, dict[str, Any]] = {}
        unavailable: list[str] = []
        for source_id in selected_ids:
            card = cards.get(source_id) or {}
            document = documents.get(source_id) or {}
            text_value = str(document.get("text") or card.get("text") or "")[:_MAX_SOURCE_TEXT_CHARS]
            if not card and not document:
                unavailable.append(source_id)
                continue
            source_texts[source_id] = text_value
            metadata = {**document, **card}
            metadata["source_id"] = source_id
            metadata.setdefault("authority_status", "stale_unknown")
            metadata.setdefault("freshness_status", "unknown")
            metadata.setdefault("jurisdiction", "maine")
            for unsafe in ("snapshot_path", "path", "relative_path", "source_path"):
                metadata.pop(unsafe, None)
            source_metadata[source_id] = metadata

        from legal.verifiers.claim_support_verifier import extract_legal_claims

        # The canonical answer review always covers assertions, even if a caller
        # supplies a partial claim list or disables its legacy extraction flag.
        seen_claims = {row if isinstance(row, str) else row["claim"] for row in claim_rows}
        inferred_claims = extract_legal_claims(assertion_text)
        if any(len(claim) > _MAX_VERIFY_CLAIM_CHARS for claim in inferred_claims):
            return {"status": "blocked", "blockers": ["verification_claim_too_large"], "review_required": True}
        if len(inferred_claims) + len(claim_rows) > _MAX_VERIFY_CLAIMS:
            return {"status": "blocked", "blockers": ["verification_claim_count_exceeded"], "review_required": True}
        claim_rows.extend(claim for claim in inferred_claims if claim not in seen_claims)
        report = LegalOutputVerifier(index).verify_output(
            text=text,
            source_texts=source_texts,
            source_metadata=source_metadata,
            source_cards=cards,
            quotes=quote_rows,
            claims=claim_rows or None,
            auto_extract_claims=False,
            auto_extract_quotes=bool(quote_rows),
            expected_jurisdiction=jurisdiction,
        )
        report["claim_extraction"] = {
            "basis": review_scope.assertions.basis if review_scope else "unscoped_full_text",
            "assertion_text_sha256": text_hash(assertion_text),
            "answer_sha256": text_hash(text),
            "producer_bound": review_scope is not None,
            "caller_labels_trusted": False,
            "review_required": True,
        }
        if unavailable:
            report["blockers"] = sorted(set([*report.get("blockers", []), *[f"authority_source_unavailable:{item}" for item in unavailable]]))
            report["filing_ready_possible"] = False

        citation_pass = bool(report.get("citations")) and all(row.get("status") == "found" for row in report.get("citations", []))
        quote_pass = all(row.get("status") in {"exact_match", "fuzzy_match"} for row in report.get("quotes", []))
        claim_pass = bool(report.get("claims")) and all(row.get("status") == "supported" for row in report.get("claims", []))
        authority_pass = bool(source_metadata) and not any(str(item).startswith(("authority_not_verified:", "stale_or_unknown_freshness:", "jurisdiction_mismatch:")) for item in report.get("blockers", []))
        filing_gate = FilingReadyGate().evaluate({
            "authority_verified": authority_pass,
            "citations_resolved": citation_pass,
            "quotes_found": quote_pass,
            "legal_claims_supported": claim_pass,
            "facts_mapped_to_evidence": False,
            "procedure_posture_checked": False,
            "forms_current": not any("form" in str(meta.get("source_class") or "").lower() for meta in source_metadata.values()),
            "human_review_complete": False,
            "verification_report": report,
        })

        manifest_sha256 = self._sha256_file(active.manifest_path)
        source_receipts = []
        for source_id in selected_ids:
            source_text = source_texts.get(source_id, "")
            metadata = source_metadata.get(source_id, {})
            source_receipts.append({
                "source_id": source_id,
                "source_text_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
                "authority_status": metadata.get("authority_status"),
                "freshness_status": metadata.get("freshness_status"),
                "jurisdiction": metadata.get("jurisdiction"),
            })
        stable_report = {
            "schema_version": "authority_verification_receipt_v1",
            "authority_build_id": active.build_id,
            "authority_manifest_sha256": manifest_sha256,
            "answer_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "expected_jurisdiction": jurisdiction,
            "sources": source_receipts,
            "verification_report": report,
            "filing_gate_blockers": filing_gate.get("blockers", []),
        }
        receipt_sha256 = hashlib.sha256(json.dumps(stable_report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
        stable_report["receipt_sha256"] = receipt_sha256
        return {
            "status": "verified_pending_human_review" if not report.get("blockers") else "review_required",
            "authority_build_id": active.build_id,
            "authority_manifest_sha256": manifest_sha256,
            "selected_source_ids": selected_ids,
            "unavailable_source_ids": unavailable,
            "verification_report": report,
            "filing_gate": filing_gate,
            "verification_receipt": stable_report,
            "review_required": True,
        }

    def _active_product(self, *, verify_all: bool = False) -> ActiveAuthorityProduct:
        if self.data_root is None:
            raise FileNotFoundError("authority data root is not configured")
        if verify_all:
            verification = AuthorityProductVerifier(data_root=self.data_root).verify()
            if verification.status != "pass" or not verification.build_id or not verification.build_manifest_path:
                raise ValueError(f"active authority product is not verified: {verification.blockers}")
            manifest_path = Path(verification.build_manifest_path).resolve()
            build_id = verification.build_id
        else:
            pointer_path = self.data_root / "authority_product" / "ACTIVE_BUILD.json"
            pointer = self._read_json(pointer_path)
            if not isinstance(pointer, dict):
                raise ValueError("active authority pointer must be a JSON object")
            build_id = str(pointer.get("build_id") or "")
            if len(build_id) != 24 or any(char not in "0123456789abcdef" for char in build_id.lower()):
                raise ValueError("active authority build ID is invalid")
            manifest_path = self._safe_data_path(str(pointer.get("manifest_relative_path") or ""))
            if not manifest_path.is_file():
                raise ValueError("active authority manifest is unavailable")
            actual_manifest_hash = self._sha256_file(manifest_path)
            if actual_manifest_hash != str(pointer.get("manifest_sha256") or ""):
                raise ValueError("active authority manifest hash mismatch")
        manifest = self._read_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError("active authority manifest must be a JSON object")
        if str(manifest.get("build_id") or "") != build_id:
            raise ValueError("active authority pointer/build mismatch")
        return ActiveAuthorityProduct(
            data_root=self.data_root,
            build_id=build_id,
            manifest_path=manifest_path,
            manifest=manifest,
        )

    def _artifact_path(
        self,
        active: ActiveAuthorityProduct,
        *,
        role_contains: str,
        required: bool = True,
    ) -> Path | None:
        for row in active.manifest.get("artifacts") or []:
            if not isinstance(row, dict) or role_contains not in str(row.get("role") or ""):
                continue
            path = self._safe_data_path(str(row.get("relative_path") or ""))
            if not path.is_file():
                raise ValueError(f"authority artifact unavailable: {path}")
            if path.stat().st_size != int(row.get("size") or -1):
                raise ValueError(f"authority artifact size mismatch: {path.name}")
            if self._sha256_file(path) != str(row.get("sha256") or ""):
                raise ValueError(f"authority artifact hash mismatch: {path.name}")
            return path
        if required:
            raise FileNotFoundError(f"active authority artifact role not found: {role_contains}")
        return None

    def _safe_data_path(self, raw: str | Path) -> Path:
        if self.data_root is None:
            raise FileNotFoundError("authority data root is not configured")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = self.data_root / candidate
        lexical = Path(os.path.abspath(candidate))
        try:
            relative = lexical.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError(f"authority path escapes data root: {raw}") from exc
        current = self.data_root
        for part in relative.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise ValueError(f"symlinked authority path component is not allowed: {current}")
        resolved = lexical.resolve()
        try:
            resolved.relative_to(self.data_root)
        except ValueError as exc:
            raise ValueError(f"resolved authority path escapes data root: {raw}") from exc
        return resolved

    @staticmethod
    def _read_json(path: Path) -> Any:
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"unsafe authority JSON path: {path}")
        size = path.stat().st_size
        if size > _MAX_JSON_BYTES:
            raise ValueError("authority JSON size limit exceeded")
        payload = path.read_bytes()
        if len(payload) != size:
            raise ValueError("authority JSON changed while reading")
        return json.loads(payload.decode("utf-8"))

    @staticmethod
    def _iter_jsonl(
        path: Path, *, expected_sha256: str | None = None, expected_size: int | None = None
    ) -> Iterable[dict[str, Any]]:
        parsed_hash = hashlib.sha256()
        parsed_size = 0
        with path.open("rb") as handle:
            for index in range(1, _MAX_JSONL_ROWS + 2):
                line = handle.readline(_MAX_JSONL_LINE_BYTES + 1)
                if not line:
                    break
                if index > _MAX_JSONL_ROWS:
                    raise ValueError("authority JSONL row limit exceeded")
                if len(line) > _MAX_JSONL_LINE_BYTES:
                    raise ValueError("authority JSONL line size limit exceeded")
                parsed_hash.update(line)
                parsed_size += len(line)
                if not line.strip():
                    continue
                row = json.loads(line.decode("utf-8"))
                if isinstance(row, dict):
                    yield row
        if expected_sha256 is not None and (
            parsed_hash.hexdigest() != expected_sha256 or parsed_size != expected_size
        ):
            raise ValueError("authority parsed bytes changed during verified read")

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _source_class_group(source_class: str) -> str:
        lowered = str(source_class or "").casefold()
        if "statute" in lowered:
            return "statutes"
        if "rule" in lowered or "order" in lowered:
            return "rules"
        if "form" in lowered:
            return "forms"
        if "opinion" in lowered or "case" in lowered or "court" in lowered:
            return "opinions"
        return "federal" if "federal" in lowered else "other"

    @staticmethod
    def _freshness_bucket(value: str) -> str:
        status = str(value or "").casefold()
        if status in {"fresh", "current", "verified_current", "known_version_date"}:
            return "fresh"
        if "supersed" in status:
            return "superseded"
        if "retrieval" in status and "fail" in status:
            return "retrieval_failed"
        if "parser" in status and "fail" in status:
            return "parser_failed"
        if "stale" in status or "expired" in status:
            return "stale"
        return "unknown"

    @classmethod
    def _source_inventory_card(cls, raw: dict[str, Any], *, document_text: dict[str, str]) -> dict[str, Any]:
        """Normalize an admitted source card without exposing local paths."""

        card = cls._safe_source_card(raw)
        metadata = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
        source_id = str(card.get("source_id") or card.get("record_id") or metadata.get("source_id") or "")
        source_class = str(card.get("source_class") or metadata.get("source_class") or metadata.get("source_type") or "")
        freshness_status = str(card.get("freshness_status") or metadata.get("freshness_status") or "unknown")
        official_url = str(card.get("source_url_or_path") or card.get("official_url") or metadata.get("source_url_or_path") or "")
        if not official_url.lower().startswith(("https://", "http://")):
            official_url = ""
        source_span = card.get("source_span") if isinstance(card.get("source_span"), dict) else {}
        issue_tags = card.get("issue_tags") or card.get("issue_labels") or metadata.get("issue_tags") or metadata.get("issue_labels") or []
        if not isinstance(issue_tags, list):
            issue_tags = []
        text = document_text.get(source_id, "")
        return {
            "source_id": source_id,
            "title": str(card.get("title") or card.get("caption") or source_id or "Admitted authority source")[:300],
            "citation": str(card.get("citation") or card.get("citation_hint") or metadata.get("citation") or "") or None,
            "source_class": source_class,
            "source_class_group": cls._source_class_group(source_class),
            "jurisdiction": card.get("jurisdiction") or metadata.get("jurisdiction") or "Maine",
            "authority_status": card.get("authority_status") or metadata.get("authority_status") or "admitted_active_build",
            "freshness_status": freshness_status,
            "freshness_bucket": cls._freshness_bucket(freshness_status),
            "review_required": True,
            "official_url": official_url or None,
            "url": official_url or None,
            "source_lane": "legal_authority",
            "source_span": source_span,
            "issue_tags": issue_tags,
            "source_hash": card.get("source_hash") or card.get("hash") or metadata.get("source_hash") or metadata.get("hash"),
            "retrieved_at": card.get("retrieved_at") or metadata.get("retrieved_at"),
            "parser_status": card.get("parser_status") or metadata.get("parser_status"),
            "parser_name": card.get("parser_name") or card.get("parser") or metadata.get("parser_name") or metadata.get("parser"),
            "technical": {
                "source_id": source_id,
                "source_class": source_class,
                "source_hash": card.get("source_hash") or card.get("hash") or metadata.get("source_hash") or metadata.get("hash"),
                "retrieved_at": card.get("retrieved_at") or metadata.get("retrieved_at"),
                "parser_status": card.get("parser_status") or metadata.get("parser_status"),
                "source_span": source_span,
            },
            "snippet": text[:400] or str(card.get("description") or "Admitted source in the active authority build")[:400],
            "can_support_current_law_claim": cls._freshness_bucket(freshness_status) == "fresh",
            "source_span_preview": str(card.get("source_span_preview") or text[:400])[:400],
            "parser_warnings": list(card.get("parser_warnings") or metadata.get("parser_warnings") or []),
        }

    @staticmethod
    def _safe_source_card(card: dict[str, Any]) -> dict[str, Any]:
        safe = dict(card)
        safe.pop("snapshot_path", None)
        raw_locator = str(safe.get("source_url_or_path") or "")
        if raw_locator and not raw_locator.lower().startswith(("https://", "http://")):
            safe["source_url_or_path"] = None
        return safe
