from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RetrievalIndexFinding:
    code: str
    message: str
    path: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {"code": self.code, "message": self.message}
        if self.path is not None:
            payload["path"] = self.path
        return payload


@dataclass
class RetrievalIndexAuditReport:
    status: str
    readiness: str
    data_root: str
    embedding_store: str
    manifest_path: str | None
    document_count: int = 0
    vector_count: int = 0
    source_card_count: int = 0
    parent_child_count: int = 0
    lookup_counts: dict[str, int] = field(default_factory=dict)
    findings: list[RetrievalIndexFinding] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "readiness": self.readiness,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "embedding_store": self.embedding_store,
            "manifest_path": self.manifest_path,
            "document_count": self.document_count,
            "vector_count": self.vector_count,
            "source_card_count": self.source_card_count,
            "parent_child_count": self.parent_child_count,
            "lookup_counts": self.lookup_counts,
            "findings": [finding.as_dict() for finding in self.findings],
            "blockers": sorted(set(self.blockers)),
        }


class RetrievalIndexAuditor:
    """Audit external retrieval index artifacts before they are treated as usable.

    The builder writes dependency-free BM25/vector/hybrid files. This auditor checks
    that those files exist outside the repo, are internally consistent, and contain
    the lookup artifacts needed by exact citation/form/case/statute retrieval.
    """

    REQUIRED_FILES = {
        "bm25_documents": ("bm25", "documents.jsonl"),
        "vector_embeddings": ("vector", "vectors.jsonl"),
        "hybrid_documents": ("hybrid", "retrieval_documents.jsonl"),
        "parent_child_chunks": ("hybrid", "parent_child_chunks.jsonl"),
        "source_cards": ("hybrid", "source_cards.jsonl"),
        "exact_citation_lookup": ("hybrid", "exact_citation_lookup.json"),
        "form_id_lookup": ("hybrid", "form_id_lookup.json"),
        "case_name_lookup": ("hybrid", "case_name_lookup.json"),
        "statute_section_lookup": ("hybrid", "statute_section_lookup.json"),
    }

    LOOKUP_FILES = {
        "exact_citation": ("hybrid", "exact_citation_lookup.json"),
        "form_id": ("hybrid", "form_id_lookup.json"),
        "case_name": ("hybrid", "case_name_lookup.json"),
        "statute_section": ("hybrid", "statute_section_lookup.json"),
    }

    def __init__(self, *, data_root: str | Path, repo_root: str | Path | None = None) -> None:
        self.data_root = Path(data_root).expanduser().resolve()
        self.repo_root = Path(repo_root).expanduser().resolve() if repo_root else None
        self.embedding_store = self.data_root / "embedding_store"
        self.manifest_path = self.embedding_store / "retrieval_index_manifest.json"

    def audit(self, *, require_direct_lookups: bool = False) -> RetrievalIndexAuditReport:
        findings: list[RetrievalIndexFinding] = []
        blockers: list[str] = []

        if self.repo_root and self._is_relative_to(self.embedding_store, self.repo_root):
            self._block(
                findings,
                blockers,
                "embedding_store_inside_repo",
                "Retrieval indexes must live under the external data root, not inside the source repository.",
                self.embedding_store,
            )

        manifest: dict[str, Any] = {}
        if not self.manifest_path.exists():
            self._block(findings, blockers, "manifest_missing", "Missing retrieval_index_manifest.json.", self.manifest_path)
        else:
            try:
                loaded = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    manifest = loaded
                else:
                    self._block(findings, blockers, "manifest_invalid", "Retrieval manifest must be a JSON object.", self.manifest_path)
            except json.JSONDecodeError as exc:
                self._block(findings, blockers, "manifest_invalid", f"Retrieval manifest JSON parse failed: {exc}", self.manifest_path)

        file_counts: dict[str, int] = {}
        for label, parts in self.REQUIRED_FILES.items():
            path = self.embedding_store.joinpath(*parts)
            if not path.exists():
                self._block(findings, blockers, "required_index_file_missing", f"Missing required index artifact: {label}.", path)
                file_counts[label] = 0
                continue
            if path.suffix == ".jsonl":
                file_counts[label] = self._count_jsonl(path, findings, blockers)
            elif path.suffix == ".json":
                file_counts[label] = self._count_json_mapping(path, findings, blockers)
            if file_counts[label] == 0 and label in {"bm25_documents", "vector_embeddings", "hybrid_documents", "source_cards"}:
                self._block(findings, blockers, "required_index_file_empty", f"Required index artifact is empty: {label}.", path)

        lookup_counts = {
            name: file_counts.get(self._lookup_label_to_required_label(name), 0)
            for name in self.LOOKUP_FILES
        }
        if require_direct_lookups:
            for name, count in lookup_counts.items():
                if count <= 0:
                    self._block(
                        findings,
                        blockers,
                        "required_lookup_empty",
                        f"Direct-authority retrieval handoff requires a non-empty {name} lookup.",
                        self.embedding_store.joinpath(*self.LOOKUP_FILES[name]),
                    )

        document_count = file_counts.get("hybrid_documents", 0)
        vector_count = file_counts.get("vector_embeddings", 0)
        source_card_count = file_counts.get("source_cards", 0)
        parent_child_count = file_counts.get("parent_child_chunks", 0)

        if document_count != vector_count:
            self._block(findings, blockers, "document_vector_count_mismatch", "Hybrid document count must match vector count.", self.embedding_store)
        if document_count != source_card_count:
            self._block(findings, blockers, "document_source_card_count_mismatch", "Every retrieval document must have a source card.", self.embedding_store)
        if parent_child_count and parent_child_count != document_count:
            self._block(findings, blockers, "document_parent_child_count_mismatch", "Every retrieval document must have a parent-child chunk row.", self.embedding_store)

        for manifest_key, actual in (
            ("document_count", document_count),
            ("vector_count", vector_count),
            ("exact_citation_count", lookup_counts.get("exact_citation", 0)),
            ("form_lookup_count", lookup_counts.get("form_id", 0)),
            ("case_lookup_count", lookup_counts.get("case_name", 0)),
            ("statute_lookup_count", lookup_counts.get("statute_section", 0)),
        ):
            if manifest and manifest_key in manifest and int(manifest.get(manifest_key) or 0) != actual:
                self._block(
                    findings,
                    blockers,
                    "manifest_count_mismatch",
                    f"Manifest {manifest_key}={manifest.get(manifest_key)!r} does not match artifact count {actual}.",
                    self.manifest_path,
                )

        if manifest.get("lookup_value_contract"):
            candidate_path = self.embedding_store / "hybrid" / "exact_citation_candidates.json"
            if not candidate_path.exists():
                self._block(
                    findings,
                    blockers,
                    "exact_citation_candidates_missing",
                    "The multi-candidate lookup contract requires exact_citation_candidates.json.",
                    candidate_path,
                )
            else:
                self._count_json_mapping(candidate_path, findings, blockers)

        artifact_hashes = manifest.get("artifact_hashes") if isinstance(manifest.get("artifact_hashes"), dict) else {}
        for relative, expected_hash in artifact_hashes.items():
            try:
                artifact_path = (self.embedding_store / str(relative)).resolve()
                artifact_path.relative_to(self.embedding_store.resolve())
                if artifact_path.is_symlink() or not artifact_path.is_file():
                    raise ValueError("artifact missing or symlinked")
                digest = hashlib.sha256()
                with artifact_path.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                actual_hash = digest.hexdigest()
                if actual_hash != str(expected_hash):
                    self._block(
                        findings,
                        blockers,
                        "index_artifact_hash_mismatch",
                        f"Expected {expected_hash}; found {actual_hash}.",
                        artifact_path,
                    )
            except (OSError, ValueError) as exc:
                self._block(
                    findings,
                    blockers,
                    "index_artifact_path_invalid",
                    f"Invalid hashed retrieval artifact {relative!r}: {exc}",
                    self.embedding_store / str(relative),
                )

        required_indexes = {"bm25", "vector", "hybrid"}
        indexes = set(manifest.get("indexes") or []) if manifest else set()
        if manifest and not required_indexes.issubset(indexes):
            self._block(
                findings,
                blockers,
                "manifest_missing_index_family",
                "Retrieval manifest must list bm25, vector, and hybrid indexes.",
                self.manifest_path,
            )

        status = "pass" if not blockers else "blocked"
        return RetrievalIndexAuditReport(
            status=status,
            readiness="retrieval_indexes_ready" if status == "pass" else "retrieval_indexes_blocked",
            data_root=str(self.data_root),
            embedding_store=str(self.embedding_store),
            manifest_path=str(self.manifest_path) if self.manifest_path.exists() else None,
            document_count=document_count,
            vector_count=vector_count,
            source_card_count=source_card_count,
            parent_child_count=parent_child_count,
            lookup_counts=lookup_counts,
            findings=findings,
            blockers=blockers,
        )

    @staticmethod
    def _lookup_label_to_required_label(name: str) -> str:
        return {
            "exact_citation": "exact_citation_lookup",
            "form_id": "form_id_lookup",
            "case_name": "case_name_lookup",
            "statute_section": "statute_section_lookup",
        }[name]

    @staticmethod
    def _block(
        findings: list[RetrievalIndexFinding],
        blockers: list[str],
        code: str,
        message: str,
        path: str | Path | None = None,
    ) -> None:
        blockers.append(code)
        findings.append(RetrievalIndexFinding(code=code, message=message, path=str(path) if path is not None else None))

    @staticmethod
    def _count_jsonl(path: Path, findings: list[RetrievalIndexFinding], blockers: list[str]) -> int:
        count = 0
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                RetrievalIndexAuditor._block(
                    findings,
                    blockers,
                    "index_jsonl_invalid",
                    f"Invalid JSONL at line {line_number}: {exc}",
                    path,
                )
                continue
            count += 1
        return count

    @staticmethod
    def _count_json_mapping(path: Path, findings: list[RetrievalIndexFinding], blockers: list[str]) -> int:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            RetrievalIndexAuditor._block(findings, blockers, "lookup_json_invalid", f"Invalid lookup JSON: {exc}", path)
            return 0
        if not isinstance(loaded, dict):
            RetrievalIndexAuditor._block(findings, blockers, "lookup_json_invalid", "Lookup artifact must be a JSON object.", path)
            return 0
        return len(loaded)

    @staticmethod
    def _is_relative_to(path: Path, possible_parent: Path) -> bool:
        try:
            path.resolve().relative_to(possible_parent.resolve())
            return True
        except ValueError:
            return False
