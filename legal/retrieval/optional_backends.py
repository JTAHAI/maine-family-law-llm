"""Bounded optional retrieval backends for the local retrieval workbench."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import math
import os
import re
import sqlite3
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urlparse

from legal.retrieval.models import RetrievalDocument, RetrievalResult
from legal.retrieval.query_expansion import expand_query, tokenize

DENSE_DIMENSIONS = 128
MAX_DOCUMENTS = 20_000
MAX_TEXT_CHARS = 250_000
MAX_QUERY_CHARS = 2_000
MAX_RESULTS = 100
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


class RetrievalBackendError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackendStatus:
    backend_id: str
    available: bool
    enabled: bool
    version: str | None
    mode: str
    details: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _package_version(distribution: str) -> str | None:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return None


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def optional_backend_status() -> dict[str, Any]:
    qdrant_url = str(os.environ.get("MFL_QDRANT_URL") or "").strip()
    qdrant_allowed = is_loopback_qdrant_url(qdrant_url) if qdrant_url else False
    rows = [
        BackendStatus(
            backend_id="sqlite_fts5",
            available=_fts5_available(),
            enabled=True,
            version=sqlite3.sqlite_version,
            mode="embedded_local",
            details="SQLite FTS5 lexical index; no external service.",
        ),
        BackendStatus(
            backend_id="sqlite_vec",
            available=_module_available("sqlite_vec"),
            enabled=_module_available("sqlite_vec"),
            version=_package_version("sqlite-vec"),
            mode="optional_embedded_vector",
            details="Optional pre-v1 vector accelerator; deterministic local fallback remains active.",
        ),
        BackendStatus(
            backend_id="qdrant_loopback",
            available=_module_available("qdrant_client"),
            enabled=bool(qdrant_url and qdrant_allowed and _module_available("qdrant_client")),
            version=_package_version("qdrant-client"),
            mode="optional_loopback_service",
            details=(
                "Configured loopback endpoint."
                if qdrant_url and qdrant_allowed
                else "Disabled; only an explicit localhost/loopback endpoint is admitted."
            ),
        ),
        BackendStatus(
            backend_id="deepeval",
            available=_module_available("deepeval"),
            enabled=False,
            version=_package_version("deepeval"),
            mode="developer_ci_only",
            details="Optional evaluation adapter; never used as a legal correctness source.",
        ),
        BackendStatus(
            backend_id="promptfoo",
            available=False,
            enabled=False,
            version=None,
            mode="developer_ci_only",
            details="Node-based adversarial runner; intentionally absent from the application runtime.",
        ),
    ]
    return {
        "schema_version": "retrieval_optional_backends_v1",
        "backends": [row.to_dict() for row in rows],
        "local_only_default": True,
        "automatic_installation": False,
        "automatic_model_download": False,
        "review_required": True,
    }


def _fts5_available() -> bool:
    try:
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE VIRTUAL TABLE test_fts USING fts5(text)")
            return True
        finally:
            db.close()
    except sqlite3.Error:
        return False


def is_loopback_qdrant_url(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host in _LOOPBACK_HOSTS and parsed.username is None and parsed.password is None


class HashDenseEmbeddingAdapter:
    """Deterministic fixed-width local embedding used by the optional vector backend.

    This is a reproducible hashing projection, not a neural legal embedding model.
    It exists so the sqlite-vec/Qdrant adapter contract can be exercised without
    downloading model weights or making network calls.
    """

    model_name = "deterministic_hash_dense_embedding_v1"
    dimensions = DENSE_DIMENSIONS
    privacy_status = "local_no_external_calls"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        counts = Counter(tokenize(text[:MAX_TEXT_CHARS]))
        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = -1.0 if digest[4] & 1 else 1.0
            vector[index] += sign * (1.0 + math.log(max(count, 1)))
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    @staticmethod
    def cosine(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))

    @staticmethod
    def serialize(vector: list[float]) -> bytes:
        return struct.pack(f"{len(vector)}f", *vector)


class SQLiteHybridIndex:
    """Per-request embedded FTS5 + optional sqlite-vec index with explainable RRF."""

    def __init__(self, documents: Iterable[RetrievalDocument]):
        self.documents = list(documents)[:MAX_DOCUMENTS]
        self.embedding = HashDenseEmbeddingAdapter()

    def search(self, query: str, *, top_k: int = 10) -> tuple[list[RetrievalResult], dict[str, Any]]:
        query = " ".join(str(query or "").replace("\x00", " ").split())[:MAX_QUERY_CHARS]
        top_k = max(1, min(int(top_k or 10), MAX_RESULTS))
        if not query:
            return [], self._diagnostics("empty_query", False, 0, 0)
        db = sqlite3.connect(":memory:")
        db.row_factory = sqlite3.Row
        vector_enabled = False
        vector_error = ""
        try:
            self._create_fts(db)
            lexical = self._lexical_search(db, query, max(top_k * 4, 40))
            try:
                vector_enabled = self._create_vec(db)
                semantic = self._vec_search(db, query, max(top_k * 4, 40)) if vector_enabled else self._python_semantic(query, max(top_k * 4, 40))
            except Exception as exc:  # optional extension must fail closed to deterministic fallback
                vector_enabled = False
                vector_error = type(exc).__name__
                semantic = self._python_semantic(query, max(top_k * 4, 40))
            results = self._fuse(query, lexical, semantic)[:top_k]
            diagnostics = self._diagnostics(
                "pass",
                vector_enabled,
                len(lexical),
                len(semantic),
                vector_error=vector_error,
                result_count=len(results),
            )
            return results, diagnostics
        finally:
            db.close()

    def _create_fts(self, db: sqlite3.Connection) -> None:
        db.execute("CREATE VIRTUAL TABLE docs_fts USING fts5(source_id UNINDEXED, title, citation, text, tokenize='unicode61')")
        db.execute("CREATE TABLE doc_meta(rowid INTEGER PRIMARY KEY, source_id TEXT UNIQUE, document_index INTEGER)")
        for index, document in enumerate(self.documents):
            cursor = db.execute(
                "INSERT INTO docs_fts(source_id,title,citation,text) VALUES(?,?,?,?)",
                (document.source_id, document.title[:1_000], (document.citation or "")[:1_000], document.text[:MAX_TEXT_CHARS]),
            )
            db.execute(
                "INSERT INTO doc_meta(rowid,source_id,document_index) VALUES(?,?,?)",
                (cursor.lastrowid, document.source_id, index),
            )
        db.commit()

    def _create_vec(self, db: sqlite3.Connection) -> bool:
        if not _module_available("sqlite_vec"):
            return False
        sqlite_vec = importlib.import_module("sqlite_vec")
        db.enable_load_extension(True)
        try:
            sqlite_vec.load(db)
        finally:
            db.enable_load_extension(False)
        db.execute(f"CREATE VIRTUAL TABLE docs_vec USING vec0(embedding float[{self.embedding.dimensions}])")
        for rowid, document in enumerate(self.documents, start=1):
            vector = self.embedding.embed(f"{document.title}\n{document.citation or ''}\n{document.text}")
            db.execute("INSERT INTO docs_vec(rowid,embedding) VALUES(?,?)", (rowid, self.embedding.serialize(vector)))
        db.commit()
        return True

    def _lexical_search(self, db: sqlite3.Connection, query: str, limit: int) -> list[tuple[int, float, tuple[str, ...]]]:
        terms = list(dict.fromkeys(expand_query(query)))[:40]
        if not terms:
            return []
        fts_query = " OR ".join(f'"{term.replace(chr(34), "")}"' for term in terms if re.fullmatch(r"[\w-]+", term))
        if not fts_query:
            return []
        rows = db.execute(
            "SELECT rowid, bm25(docs_fts, 0.0, 2.0, 4.0, 1.0) AS score FROM docs_fts WHERE docs_fts MATCH ? ORDER BY score LIMIT ?",
            (fts_query, limit),
        ).fetchall()
        return [(int(row["rowid"]), 1.0 / (1.0 + max(float(row["score"]), 0.0)), tuple(terms)) for row in rows]

    def _vec_search(self, db: sqlite3.Connection, query: str, limit: int) -> list[tuple[int, float, tuple[str, ...]]]:
        vector = self.embedding.serialize(self.embedding.embed(" ".join(expand_query(query)) or query))
        rows = db.execute(
            "SELECT rowid, distance FROM docs_vec WHERE embedding MATCH ? AND k = ? ORDER BY distance",
            (vector, limit),
        ).fetchall()
        return [(int(row["rowid"]), max(0.0, 1.0 - float(row["distance"])), ()) for row in rows]

    def _python_semantic(self, query: str, limit: int) -> list[tuple[int, float, tuple[str, ...]]]:
        query_vector = self.embedding.embed(" ".join(expand_query(query)) or query)
        rows = []
        for rowid, document in enumerate(self.documents, start=1):
            vector = self.embedding.embed(f"{document.title}\n{document.citation or ''}\n{document.text}")
            score = self.embedding.cosine(query_vector, vector)
            if score > 0:
                rows.append((rowid, score, ()))
        return sorted(rows, key=lambda row: (-row[1], row[0]))[:limit]

    def _fuse(
        self,
        query: str,
        lexical: list[tuple[int, float, tuple[str, ...]]],
        semantic: list[tuple[int, float, tuple[str, ...]]],
    ) -> list[RetrievalResult]:
        rrf_k = 60
        scores: dict[int, float] = {}
        components: dict[int, dict[str, float]] = {}
        matched: dict[int, set[str]] = {}
        for name, weight, rows in (("fts5", 1.0, lexical), ("vector", 0.8, semantic)):
            for rank, (rowid, raw_score, terms) in enumerate(rows, start=1):
                contribution = weight / (rrf_k + rank)
                scores[rowid] = scores.get(rowid, 0.0) + contribution
                components.setdefault(rowid, {})[name] = contribution
                components[rowid][f"{name}_raw"] = float(raw_score)
                matched.setdefault(rowid, set()).update(terms)
        results: list[RetrievalResult] = []
        for rowid, score in scores.items():
            if rowid < 1 or rowid > len(self.documents):
                continue
            document = self.documents[rowid - 1]
            authority = {
                "verified_official_maine": 0.30,
                "verified_maine_law_court": 0.25,
                "verified_federal": 0.15,
                "user_provided_only": 0.0,
                "stale_unknown": -0.10,
            }.get(document.authority_status, -0.05)
            freshness = {"current": 0.15, "fresh": 0.10, "unknown": -0.05, "stale": -0.25}.get(document.freshness_status, 0.0)
            lane = 0.03 if document.source_class in {"private_record", "court_record"} else 0.0
            total = score + authority + freshness + lane
            component = dict(components.get(rowid, {}))
            component.update({"authority": authority, "freshness": freshness, "record_lane": lane})
            reasons = []
            if component.get("fts5"):
                reasons.append("lexical phrase or term match")
            if component.get("vector"):
                reasons.append("local semantic similarity")
            if authority > 0:
                reasons.append("verified authority boost")
            if freshness > 0:
                reasons.append("current-source boost")
            results.append(
                RetrievalResult(
                    document=document,
                    score=total,
                    method="sqlite_fts5_optional_vec_rrf",
                    matched_terms=tuple(sorted(matched.get(rowid, set()))),
                    explanation="; ".join(reasons) or "bounded local retrieval match",
                    component_scores=component,
                )
            )
        ranked = sorted(results, key=lambda row: (-row.score, row.document.source_id))
        return [row.with_rank(index + 1) for index, row in enumerate(ranked)]

    def _diagnostics(
        self,
        status: str,
        vector_enabled: bool,
        lexical_candidates: int,
        semantic_candidates: int,
        *,
        vector_error: str = "",
        result_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "schema_version": "embedded_hybrid_retrieval_diagnostics_v1",
            "status": status,
            "document_count": len(self.documents),
            "result_count": result_count,
            "lexical_backend": "sqlite_fts5",
            "semantic_backend": "sqlite_vec" if vector_enabled else "deterministic_hash_dense_fallback",
            "sqlite_vec_active": vector_enabled,
            "sqlite_vec_error_category": vector_error,
            "lexical_candidate_count": lexical_candidates,
            "semantic_candidate_count": semantic_candidates,
            "embedding_model": self.embedding.model_name,
            "network_used": False,
            "review_required": True,
        }

class QdrantLoopbackReadOnlyAdapter:
    """Read-only Qdrant query adapter restricted to an explicit loopback endpoint."""

    _COLLECTION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

    def __init__(self, *, url: str | None = None, client_factory: Any | None = None) -> None:
        self.url = str(url or os.environ.get("MFL_QDRANT_URL") or "").strip()
        self.client_factory = client_factory

    def status(self) -> dict[str, Any]:
        admitted = is_loopback_qdrant_url(self.url)
        return {
            "backend_id": "qdrant_loopback",
            "available": _module_available("qdrant_client") or self.client_factory is not None,
            "endpoint_admitted": admitted,
            "enabled": bool(admitted and (_module_available("qdrant_client") or self.client_factory is not None)),
            "read_only": True,
            "automatic_discovery": False,
            "network_scope": "loopback_only",
            "review_required": True,
        }

    def search(
        self,
        *,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        approved: bool = False,
    ) -> list[dict[str, Any]]:
        if approved is not True:
            raise RetrievalBackendError("Explicit approval is required for a loopback Qdrant query.")
        if not is_loopback_qdrant_url(self.url):
            raise RetrievalBackendError("Only an explicit localhost or loopback Qdrant endpoint is admitted.")
        collection = str(collection or "").strip()
        if not self._COLLECTION_RE.fullmatch(collection):
            raise RetrievalBackendError("Invalid Qdrant collection name.")
        if not query_vector or len(query_vector) > 4096:
            raise RetrievalBackendError("Invalid or oversized Qdrant query vector.")
        limit = max(1, min(int(top_k or 10), MAX_RESULTS))
        factory = self.client_factory
        if factory is None:
            if not _module_available("qdrant_client"):
                raise RetrievalBackendError("qdrant-client is not installed.")
            module = importlib.import_module("qdrant_client")
            factory = module.QdrantClient
        # No API key, cloud inference, writes, collection creation, or payload mutation.
        client = factory(url=self.url, timeout=5.0, check_compatibility=False)
        response = client.query_points(
            collection_name=collection,
            query=[float(value) for value in query_vector],
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        points = getattr(response, "points", response) or []
        results: list[dict[str, Any]] = []
        for point in list(points)[:limit]:
            payload = getattr(point, "payload", None) or {}
            if not isinstance(payload, dict):
                payload = {}
            source_id = str(payload.get("source_id") or payload.get("document_id") or getattr(point, "id", ""))[:256]
            results.append(
                {
                    "source_id": source_id,
                    "score": float(getattr(point, "score", 0.0) or 0.0),
                    "source_class": str(payload.get("source_class") or "unknown_source")[:80],
                    "jurisdiction": str(payload.get("jurisdiction") or "maine")[:40],
                    "authority_status": str(payload.get("authority_status") or "stale_unknown")[:80],
                    "freshness_status": str(payload.get("freshness_status") or "unknown")[:80],
                    "network_scope": "loopback_only",
                    "read_only": True,
                    "review_required": True,
                }
            )
        return results
