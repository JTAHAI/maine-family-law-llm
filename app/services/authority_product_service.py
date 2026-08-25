from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from legal.drafting.filing_ready_gate import FilingReadyGate
from legal.data_boundaries import default_external_data_root, ensure_external_authority_root
from legal.production.authority_product import AuthorityProductVerifier
from legal.authority_store.authority_layer import iter_parsed_authority_rows
from legal.retrieval.models import RetrievalResult
from legal.retrieval.query_expansion import expand_query_guarded
from legal.retrieval.retrieval_pipeline import RetrievalPipeline
from legal.verifiers import LegalOutputVerifier, SourceAuthorityIndex

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
_INTERACTIVE_HYBRID_MAX_DOCUMENTS = 12_000
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
        self._active_product(verify_all=False)
        for row in iter_parsed_authority_rows(self.data_root):
            row_source_id = str(row.get("record_id") or row.get("source_id") or "")
            if row_source_id != source_id:
                continue
            text = str(row.get("text") or row.get("body") or row.get("instructions") or "")
            start = max(0, min(int(start_offset), len(text)))
            end = max(start, min(int(end_offset), len(text)))
            return {
                "status": "pass",
                "source_id": source_id,
                "build_id": self._active_product(verify_all=False).build_id,
                "source_span": {"start_offset": start, "end_offset": end},
                "source_span_preview": text[start:end],
                "source_text": text[:_MAX_SOURCE_TEXT_CHARS],
                "text_truncated": len(text) > _MAX_SOURCE_TEXT_CHARS,
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

    def verify_output(
        self,
        *,
        text: str,
        source_ids: Iterable[str] | None = None,
        quotes: Iterable[dict[str, Any]] | None = None,
        claims: Iterable[dict[str, Any] | str] | None = None,
        expected_jurisdiction: str = "maine",
        auto_extract_claims: bool = True,
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

        report = LegalOutputVerifier(index).verify_output(
            text=text,
            source_texts=source_texts,
            source_metadata=source_metadata,
            source_cards=cards,
            quotes=quote_rows,
            claims=claim_rows or None,
            auto_extract_claims=auto_extract_claims,
            auto_extract_quotes=bool(quote_rows),
            expected_jurisdiction=jurisdiction,
        )
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
    def _iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
        with path.open("rb") as handle:
            for index in range(1, _MAX_JSONL_ROWS + 2):
                line = handle.readline(_MAX_JSONL_LINE_BYTES + 1)
                if not line:
                    break
                if index > _MAX_JSONL_ROWS:
                    raise ValueError("authority JSONL row limit exceeded")
                if len(line) > _MAX_JSONL_LINE_BYTES:
                    raise ValueError("authority JSONL line size limit exceeded")
                if not line.strip():
                    continue
                row = json.loads(line.decode("utf-8"))
                if isinstance(row, dict):
                    yield row

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _safe_source_card(card: dict[str, Any]) -> dict[str, Any]:
        safe = dict(card)
        safe.pop("snapshot_path", None)
        raw_locator = str(safe.get("source_url_or_path") or "")
        if raw_locator and not raw_locator.lower().startswith(("https://", "http://")):
            safe["source_url_or_path"] = None
        return safe
