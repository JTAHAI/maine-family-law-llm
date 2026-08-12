from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.authority_store.authority_layer import (
    ParsedAuthorityRecord,
    _statute_pinpoints,
    load_parsed_authority_records,
)
from legal.retrieval.embedding_adapter import DeterministicEmbeddingAdapter
from legal.retrieval.models import RetrievalDocument
from legal.verifiers.citation_parser import citation_aliases, extract_citations


@dataclass
class RetrievalIndexBuildReport:
    status: str
    data_root: str
    embedding_store: str
    document_count: int = 0
    vector_count: int = 0
    exact_citation_count: int = 0
    form_lookup_count: int = 0
    case_lookup_count: int = 0
    statute_lookup_count: int = 0
    findings: list[dict[str, Any]] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "embedding_store": self.embedding_store,
            "document_count": self.document_count,
            "vector_count": self.vector_count,
            "exact_citation_count": self.exact_citation_count,
            "form_lookup_count": self.form_lookup_count,
            "case_lookup_count": self.case_lookup_count,
            "statute_lookup_count": self.statute_lookup_count,
            "findings": self.findings,
            "outputs": self.outputs,
        }


class RetrievalIndexBuilder:
    """Build dependency-free BM25/vector/hybrid artifacts outside the source repo.

    The vector artifact is a deterministic sparse embedding index.  It is deliberately
    swappable with a production embedding backend once the same external-store contract
    is satisfied.
    """

    def __init__(self, *, data_root: str | Path, repo_root: str | Path | None = None) -> None:
        self.data_root = Path(data_root).resolve()
        self.repo_root = Path(repo_root).resolve() if repo_root else None
        self.embedding_store = self.data_root / "embedding_store"
        self.adapter = DeterministicEmbeddingAdapter()

    def build(self) -> RetrievalIndexBuildReport:
        findings: list[dict[str, Any]] = []
        if self.repo_root and self._is_relative_to(self.embedding_store, self.repo_root):
            findings.append(
                {
                    "code": "embedding_store_inside_repo",
                    "message": "Retrieval indexes must be built under an external data root, not in the source repository.",
                    "path": str(self.embedding_store),
                }
            )
        records = load_parsed_authority_records(self.data_root)
        documents = [self._document_from_record(record) for record in records if self._document_text(record)]
        if not documents:
            findings.append({"code": "no_retrieval_documents", "message": "No parsed authority records were indexable."})

        self._reset_store()
        exact_lookup: dict[str, str | list[str]] = {}
        exact_candidates: dict[str, list[str]] = {}
        form_lookup: dict[str, str | list[str]] = {}
        case_lookup: dict[str, str | list[str]] = {}
        statute_lookup: dict[str, str | list[str]] = {}
        source_cards: list[dict[str, Any]] = []
        parent_child_rows: list[dict[str, Any]] = []

        for document in documents:
            if document.citation:
                for citation in extract_citations(document.citation):
                    for alias in citation_aliases(citation):
                        self._add_lookup_candidate(exact_lookup, alias, document.source_id)
                        self._add_candidate_list(exact_candidates, alias, document.source_id)
                    if citation.kind == "maine_statute" and citation.title and citation.section:
                        self._add_lookup_candidate(statute_lookup, f"{citation.title}:{citation.section}", document.source_id)
                    if citation.kind == "maine_case":
                        self._add_lookup_candidate(case_lookup, citation.normalized, document.source_id)
                    if citation.kind == "maine_form" and citation.form_id:
                        self._add_lookup_candidate(form_lookup, citation.form_id, document.source_id)
            if document.source_class in {"court_form", "court_forms_index"} or document.metadata.get("form_id"):
                form_id = str(document.metadata.get("form_id") or document.citation or "").strip()
                if form_id:
                    self._add_lookup_candidate(form_lookup, form_id.upper(), document.source_id)
            if document.title:
                self._add_lookup_candidate(case_lookup, document.title.lower(), document.source_id)
            source_cards.append(document.source_card().__dict__)
            parent_child_rows.append(
                {
                    "parent_document_id": document.parent_document_id or document.document_id or document.source_id,
                    "chunk_id": document.chunk_id or document.source_id,
                    "source_id": document.source_id,
                    "citation": document.citation,
                    "source_hash": document.metadata.get("hash"),
                }
            )

        for record in records:
            for pinpoint, _span in _statute_pinpoints(record):
                for citation in extract_citations(pinpoint):
                    for alias in citation_aliases(citation):
                        self._add_lookup_candidate(exact_lookup, alias, record.canonical_source_id)
                        self._add_candidate_list(exact_candidates, alias, record.canonical_source_id)

        documents_by_id = {document.source_id: document for document in documents}
        for lookup in (exact_lookup, form_lookup, case_lookup, statute_lookup):
            self._rank_lookup_values(lookup, documents_by_id)
        for values in exact_candidates.values():
            values.sort(key=lambda source_id: self._candidate_rank(documents_by_id.get(source_id), source_id))

        outputs = self._write_outputs(
            documents=documents,
            exact_lookup=exact_lookup,
            exact_candidates=exact_candidates,
            form_lookup=form_lookup,
            case_lookup=case_lookup,
            statute_lookup=statute_lookup,
            source_cards=source_cards,
            parent_child_rows=parent_child_rows,
        )
        status = "pass" if not findings else "blocked"
        report = RetrievalIndexBuildReport(
            status=status,
            data_root=str(self.data_root),
            embedding_store=str(self.embedding_store),
            document_count=len(documents),
            vector_count=len(documents),
            exact_citation_count=len(exact_lookup),
            form_lookup_count=len(form_lookup),
            case_lookup_count=len(case_lookup),
            statute_lookup_count=len(statute_lookup),
            findings=findings,
            outputs=outputs,
        )
        manifest = report.as_dict()
        manifest["indexes"] = ["bm25", "vector", "hybrid"]
        manifest["artifact_hashes"] = {
            str(Path(path).resolve().relative_to(self.embedding_store.resolve())): self._sha256_file(Path(path))
            for label, path in outputs.items()
            if label not in {"retrieval_index_manifest", "index_manifest"} and Path(path).is_file()
        }
        manifest["artifact_hash_algorithm"] = "sha256"
        manifest["lookup_value_contract"] = "single_source_id_or_ranked_source_id_list"
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True)
        self._atomic_write_text(self.embedding_store / "retrieval_index_manifest.json", manifest_text)
        self._atomic_write_text(self.embedding_store / "index_manifest.json", manifest_text)
        return report

    def load_documents(self) -> list[RetrievalDocument]:
        path = self.embedding_store / "hybrid" / "retrieval_documents.jsonl"
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [RetrievalDocument(**row) for row in rows]

    def _reset_store(self) -> None:
        for subdir in ("bm25", "vector", "hybrid"):
            path = self.embedding_store / subdir
            path.mkdir(parents=True, exist_ok=True)
            for old in path.rglob("*"):
                if old.is_file():
                    old.unlink()
        self.embedding_store.mkdir(parents=True, exist_ok=True)

    def _write_outputs(
        self,
        *,
        documents: list[RetrievalDocument],
        exact_lookup: dict[str, str | list[str]],
        exact_candidates: dict[str, list[str]],
        form_lookup: dict[str, str | list[str]],
        case_lookup: dict[str, str | list[str]],
        statute_lookup: dict[str, str | list[str]],
        source_cards: list[dict[str, Any]],
        parent_child_rows: list[dict[str, Any]],
    ) -> dict[str, str]:
        bm25_docs = self.embedding_store / "bm25" / "documents.jsonl"
        vectors = self.embedding_store / "vector" / "vectors.jsonl"
        hybrid_docs = self.embedding_store / "hybrid" / "retrieval_documents.jsonl"
        parent_child = self.embedding_store / "hybrid" / "parent_child_chunks.jsonl"
        source_cards_path = self.embedding_store / "hybrid" / "source_cards.jsonl"
        exact_path = self.embedding_store / "hybrid" / "exact_citation_lookup.json"
        exact_candidates_path = self.embedding_store / "hybrid" / "exact_citation_candidates.json"
        form_path = self.embedding_store / "hybrid" / "form_id_lookup.json"
        case_path = self.embedding_store / "hybrid" / "case_name_lookup.json"
        statute_path = self.embedding_store / "hybrid" / "statute_section_lookup.json"

        with bm25_docs.open("w", encoding="utf-8") as bm25_fh, hybrid_docs.open("w", encoding="utf-8") as hybrid_fh, vectors.open("w", encoding="utf-8") as vector_fh:
            for document in documents:
                payload = self._document_payload(document)
                bm25_fh.write(json.dumps(payload, sort_keys=True) + "\n")
                hybrid_fh.write(json.dumps(payload, sort_keys=True) + "\n")
                vector_fh.write(
                    json.dumps(
                        {
                            "source_id": document.source_id,
                            "document_id": document.document_id,
                            "chunk_id": document.chunk_id,
                            "embedding_model": self.adapter.model_name,
                            "privacy_status": self.adapter.privacy_status,
                            "vector": self.adapter.embed(" ".join([document.title, document.citation or "", document.text])),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        with parent_child.open("w", encoding="utf-8") as fh:
            for row in parent_child_rows:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        with source_cards_path.open("w", encoding="utf-8") as fh:
            for row in source_cards:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
        for path, lookup in (
            (exact_path, exact_lookup),
            (exact_candidates_path, exact_candidates),
            (form_path, form_lookup),
            (case_path, case_lookup),
            (statute_path, statute_lookup),
        ):
            self._atomic_write_text(path, json.dumps(lookup, indent=2, sort_keys=True))

        return {
            "bm25_documents": str(bm25_docs),
            "vector_embeddings": str(vectors),
            "hybrid_documents": str(hybrid_docs),
            "parent_child_chunks": str(parent_child),
            "exact_citation_lookup": str(exact_path),
            "exact_citation_candidates": str(exact_candidates_path),
            "form_id_lookup": str(form_path),
            "case_name_lookup": str(case_path),
            "statute_section_lookup": str(statute_path),
            "source_cards": str(source_cards_path),
            "retrieval_index_manifest": str(self.embedding_store / "retrieval_index_manifest.json"),
            "index_manifest": str(self.embedding_store / "index_manifest.json"),
        }

    def _document_from_record(self, record: ParsedAuthorityRecord) -> RetrievalDocument:
        row = record.row
        text = self._document_text(record)
        return RetrievalDocument(
            source_id=record.canonical_source_id,
            document_id=record.canonical_source_id,
            chunk_id=f"{record.canonical_source_id}:chunk:0",
            parent_document_id=record.canonical_source_id,
            title=record.title or record.canonical_source_id,
            text=text,
            source_class=record.source_class,
            jurisdiction=record.jurisdiction,
            authority_status=record.authority_status,
            freshness_status=record.freshness_status,
            citation=record.citation,
            url_or_path=row.get("source_url_or_path") or row.get("href"),
            issue_labels=tuple(row.get("issue_labels") or self._issue_labels_from_record(record)),
            procedural_postures=tuple(row.get("procedural_postures") or ()),
            metadata={
                "hash": record.source_hash,
                "snapshot_source_id": record.snapshot_source_id,
                "authority_kind": record.authority_kind,
                "source_span": record.source_span,
                "form_id": row.get("form_id"),
                "version_date": row.get("version_date"),
                "stale_form_risk": row.get("stale_form_risk"),
            },
        )

    @staticmethod
    def _document_text(record: ParsedAuthorityRecord) -> str:
        row = record.row
        parts = [record.title, record.citation or ""]
        for field_name in ("text", "summary", "holding", "holdings", "instructions", "filing_context"):
            value = row.get(field_name)
            if isinstance(value, list):
                parts.append(" ".join(str(item) for item in value))
            elif value:
                parts.append(str(value))
        if row.get("section_number"):
            parts.append(f"section {row.get('section_number')}")
        if row.get("rule_number"):
            parts.append(f"rule {row.get('rule_number')}")
        if row.get("form_id"):
            parts.append(str(row.get("form_id")))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _issue_labels_from_record(record: ParsedAuthorityRecord) -> tuple[str, ...]:
        haystack = " ".join([record.title, record.citation or "", str(record.row)]).lower()
        labels: set[str] = set()
        if any(term in haystack for term in ("custody", "parental rights", "residence", "contact")):
            labels.add("parental_rights_responsibilities")
        if "support" in haystack:
            labels.add("child_support")
        if "divorce" in haystack:
            labels.add("divorce")
        if "protection from abuse" in haystack or "pfa" in haystack:
            labels.add("protection_from_abuse")
        if "findings" in haystack or "rule 52" in haystack:
            labels.add("Rule_52_findings")
        return tuple(sorted(labels))

    @staticmethod
    def _document_payload(document: RetrievalDocument) -> dict[str, Any]:
        return {
            "source_id": document.source_id,
            "text": document.text,
            "title": document.title,
            "document_id": document.document_id,
            "chunk_id": document.chunk_id,
            "parent_document_id": document.parent_document_id,
            "source_class": document.source_class,
            "jurisdiction": document.jurisdiction,
            "authority_status": document.authority_status,
            "freshness_status": document.freshness_status,
            "citation": document.citation,
            "url_or_path": document.url_or_path,
            "issue_labels": list(document.issue_labels),
            "procedural_postures": list(document.procedural_postures),
            "metadata": document.metadata,
        }

    @staticmethod
    def _candidate_rank(document: RetrievalDocument | None, source_id: str) -> tuple[int, int, int, str]:
        if document is None:
            return (9, 9, 9, source_id)
        authority_rank = {
            "verified_official_maine": 0,
            "verified_maine_law_court": 1,
            "verified_federal": 2,
            "verified_public_api": 3,
            "user_provided_only": 7,
            "stale_unknown": 8,
        }.get(str(document.authority_status), 6)
        source_rank = {
            "statute_section": 0,
            "court_rule": 0,
            "law_court_opinion": 0,
            "court_form": 0,
            "federal_authority": 1,
            "statute_title_index": 4,
            "court_rules_index": 4,
            "court_forms_index": 4,
            "law_court_opinions_index": 4,
        }.get(str(document.source_class), 2)
        freshness_rank = {
            "fresh": 0,
            "current": 0,
            "superseded": 6,
            "stale": 7,
            "unknown": 8,
        }.get(str(document.freshness_status).lower(), 5)
        return (authority_rank, freshness_rank, source_rank, source_id)

    @classmethod
    def _rank_lookup_values(
        cls,
        lookup: dict[str, str | list[str]],
        documents_by_id: dict[str, RetrievalDocument],
    ) -> None:
        for key, value in list(lookup.items()):
            if not isinstance(value, list):
                continue
            ranked = sorted(
                set(value),
                key=lambda source_id: cls._candidate_rank(documents_by_id.get(source_id), source_id),
            )
            lookup[key] = ranked[0] if len(ranked) == 1 else ranked

    @staticmethod
    def _add_lookup_candidate(lookup: dict[str, str | list[str]], key: str, source_id: str) -> None:
        normalized_key = str(key).strip()
        if not normalized_key:
            return
        existing = lookup.get(normalized_key)
        if existing is None:
            lookup[normalized_key] = source_id
            return
        if isinstance(existing, str):
            if existing != source_id:
                lookup[normalized_key] = [existing, source_id]
            return
        if source_id not in existing:
            existing.append(source_id)
            existing.sort()

    @staticmethod
    def _add_candidate_list(lookup: dict[str, list[str]], key: str, source_id: str) -> None:
        values = lookup.setdefault(str(key).strip(), [])
        if source_id not in values:
            values.append(source_id)
            values.sort()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _atomic_write_text(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _is_relative_to(path: Path, possible_parent: Path) -> bool:
        try:
            path.resolve().relative_to(possible_parent.resolve())
            return True
        except ValueError:
            return False
