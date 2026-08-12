from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.connectors import OfficialAuthorityIngestor, OfficialSourceFetcher, load_official_source_targets
from legal.connectors.base import SourceTarget
from legal.data_boundaries import default_external_data_root, ensure_external_authority_root, is_inside_project_repo
from legal.authority_store import ParsedAuthorityStoreBuilder
from legal.production.authority_product import AuthorityProductPublisher, AuthorityProductVerifier
from legal.production.source_update_engine import SourceUpdateEngine
from legal.authority_store.authority_layer import ParsedAuthorityIndexBuilder


_DEFAULT_FIXTURE_BY_TARGET_ID = {
    "me-revisor-title-19a-index": "mrs-title-19a-domestic-relations.html",
    "me-courts-civil-rules": "maine-rules-civil-family-division.html",
    "me-courts-rules-index": "maine-rules-civil-family-division.html",
    "me-courts-forms-index": "maine-court-forms-family.html",
    "me-judicial-branch-appeals": "maine-judicial-branch-appeals.html",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, *, limit: int = 4000) -> str:
    text = str(value or "")
    return text[:limit]


def _safe_relative(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.name


def _mask_path(value: str | Path | None) -> str:
    if not value:
        return ""
    path = Path(value)
    return path.name if path.is_absolute() else str(path).replace("\\", "/")


def _metadata_value(row: dict[str, Any], key: str) -> Any:
    metadata = row.get("metadata")
    if isinstance(metadata, dict) and metadata.get(key) not in (None, ""):
        return metadata.get(key)
    return row.get(key)


def _fetch_metadata_value(row: dict[str, Any], key: str) -> Any:
    metadata = row.get("fetch_metadata")
    if isinstance(metadata, dict):
        value = metadata.get(key)
        if value not in (None, ""):
            return value
    return row.get(key)


def _sanitize_paths(payload: Any) -> Any:
    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {
                "data_root",
                "current_manifest_path",
                "previous_manifest_path",
                "manifest_path",
                "build_manifest_path",
                "active_pointer_path",
                "manifest_relative_path",
                "parsed_store",
                "source_manifest_path",
                "snapshot_path",
                "relative_path",
                "raw_path",
                "source_snapshots",
                "artifacts",
                "outputs",
                "output_files",
            }:
                if key in {"source_snapshots", "artifacts"} and isinstance(value, list):
                    sanitized[key] = [_sanitize_paths(item) for item in value]
                elif key in {"outputs", "output_files"} and isinstance(value, dict):
                    sanitized[key] = {str(inner_key): _mask_path(inner_value) for inner_key, inner_value in value.items()}
                else:
                    sanitized[key] = _mask_path(value)
            else:
                sanitized[key] = _sanitize_paths(value)
        return sanitized
    if isinstance(payload, list):
        return [_sanitize_paths(item) for item in payload]
    return payload


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _source_class_group(source_class: str) -> str:
    lowered = source_class.lower()
    if "statute" in lowered:
        return "statutes"
    if "rule" in lowered or "order" in lowered:
        return "rules"
    if "form" in lowered:
        return "forms"
    if "opinion" in lowered or "case" in lowered:
        return "opinions"
    return "federal" if lowered.startswith("federal") else "statutes"


def _freshness_bucket(freshness_status: str) -> str:
    value = freshness_status.lower().strip()
    if value in {"fresh", "current", "verified_current", "known_version_date"}:
        return "fresh"
    if value in {"stale", "stale_or_superseded", "superseded"}:
        return "stale"
    if value in {"retrieval_failed", "parser_failed"}:
        return value
    if value in {"unknown", "needs_verification", "stale_unknown", "unknown_until_version_extracted"}:
        return "unknown"
    return value or "unknown"


@dataclass
class AuthorityUpdateJob:
    job_id: str
    status: str = "queued"
    created_at: str = field(default_factory=_utc_now)
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    cancel_requested: bool = False
    progress: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "message": self.message,
            "cancel_requested": self.cancel_requested,
            "progress": self.progress,
            "result": self.result,
        }


class _FixtureFetcher:
    def __init__(self, fixture_dir: Path, mapping: dict[str, str]) -> None:
        self.fixture_dir = fixture_dir
        self.mapping = mapping

    def fetch(self, target: SourceTarget):
        fixture_name = self.mapping.get(target.target_id)
        if not fixture_name:
            raise FileNotFoundError(f"fixture missing for {target.target_id}")
        path = self.fixture_dir / fixture_name
        if not path.is_file():
            raise FileNotFoundError(path)
        from legal.connectors.base import RetrievedSource
        content = path.read_bytes()
        content_type = "application/pdf" if path.suffix.lower() == ".pdf" else "text/html"
        return RetrievedSource(
            target=target,
            content=content,
            retrieved_at=datetime.now(timezone.utc),
            content_type=content_type,
            status_code=200,
            final_url=target.url,
        )


class AuthorityLibraryService:
    _lock = threading.Lock()
    _jobs: dict[str, AuthorityUpdateJob] = {}
    _active_job_id: str = ""

    def __init__(
        self,
        *,
        data_root: str | Path | None = None,
        repo_root: str | Path | None = None,
        fixture_dir: str | Path | None = None,
    ) -> None:
        runtime_mode = str(os.environ.get("MFL_RUNTIME_MODE") or "source").strip().lower()
        configured = data_root
        if configured is None and runtime_mode == "store":
            configured = os.environ.get("MFL_AUTHORITY_DATA_ROOT") or os.environ.get("MAINE_FAMILY_LAW_DATA_ROOT")
        if configured is None:
            configured = os.environ.get("MAINE_FAMILY_LAW_DATA_ROOT") or os.environ.get("MFL_AUTHORITY_DATA_ROOT")
        configured = configured or default_external_data_root()
        self.data_root = ensure_external_authority_root(configured)
        self.repo_root = Path(repo_root).expanduser().resolve() if repo_root else Path(__file__).resolve().parents[2]
        self.fixture_dir = Path(fixture_dir).expanduser().resolve() if fixture_dir else self.repo_root / "data" / "fixtures"

    @classmethod
    def active_job(cls) -> AuthorityUpdateJob | None:
        with cls._lock:
            if cls._active_job_id:
                return cls._jobs.get(cls._active_job_id)
        return None

    @classmethod
    def get_job(cls, job_id: str) -> AuthorityUpdateJob | None:
        with cls._lock:
            return cls._jobs.get(job_id)

    def ensure_layout(self) -> Path:
        root = self._require_data_root()
        self._ensure_containment(root)
        for relative in (
            "official_authority_store/snapshots",
            "official_authority_store/update_reports",
            "official_authority_store/failed_sources",
            "parsed_authority_store/statutes",
            "parsed_authority_store/rules",
            "parsed_authority_store/forms",
            "parsed_authority_store/opinions",
            "parsed_authority_store/federal",
            "embedding_store",
        ):
            (root / relative).mkdir(parents=True, exist_ok=True)
        return root

    def status(self) -> dict[str, Any]:
        root = self.ensure_layout()
        active = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        update_report = self._latest_update_report(root)
        source_rows = self._source_rows(root)
        counts = self._freshness_counts(source_rows)
        source_class_counts = self._source_class_counts(source_rows)
        builds = self.list_builds(limit=10)["builds"]
        job = self.active_job()
        return {
            "status": "pass" if active.status == "pass" else "blocked",
            "active": active.status == "pass",
            "review_required": True,
            "data_root_configured": True,
            "data_root_label": root.name,
            "build_id": active.build_id,
            "last_successful_update": update_report.get("generated_at") if update_report.get("status") == "pass" else update_report.get("generated_at", ""),
            "last_update_report": _sanitize_paths(update_report),
            "running_update": bool(job and job.status in {"queued", "running"}),
            "running_update_job": job.as_dict() if job else None,
            "source_counts": {
                "total": len(source_rows),
                "fresh": counts.get("fresh", 0),
                "stale": counts.get("stale", 0),
                "unknown": counts.get("unknown", 0),
                "superseded": counts.get("superseded", 0),
                "retrieval_failed": counts.get("retrieval_failed", 0),
                "parser_failed": counts.get("parser_failed", 0),
            },
            "source_class_counts": source_class_counts,
            "changed_since_last_build": update_report.get("changed_since_last_build") or {},
            "builds": builds[:5],
            "update_report_available": bool(update_report),
            "current_law_claims_supported": bool(counts.get("fresh")),
        }

    def list_builds(self, *, limit: int = 20) -> dict[str, Any]:
        root = self._require_data_root()
        builds_root = root / "authority_product" / "builds"
        builds: list[dict[str, Any]] = []
        if builds_root.exists():
            for manifest_path in sorted(builds_root.glob("*/authority_product_manifest.json"), reverse=True):
                try:
                    manifest = _load_json(manifest_path)
                except Exception:
                    continue
                if not isinstance(manifest, dict):
                    continue
                builds.append(
                    {
                        "build_id": manifest.get("build_id"),
                        "product_version": manifest.get("product_version"),
                        "generated_at": manifest.get("generated_at"),
                        "source_count": manifest.get("source_count", 0),
                        "artifact_count": manifest.get("artifact_count", 0),
                        "freshness_counts": manifest.get("freshness_counts") or {},
                        "parsed_record_counts": manifest.get("parsed_record_counts") or {},
                        "active": self._active_pointer(root).get("build_id") == manifest.get("build_id"),
                        "manifest_relative_path": _safe_relative(manifest_path, root),
                    }
                )
        builds = builds[: max(0, int(limit or 0)) or 20]
        return {"status": "pass", "builds": builds, "count": len(builds), "review_required": True}

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
        root = self._require_data_root()
        rows = self._source_rows(root)
        q = query.casefold().strip()
        class_filter = source_class.casefold().strip()
        freshness_filter = freshness.casefold().strip()
        issue_filter = issue_tag.casefold().strip()
        filtered: list[dict[str, Any]] = []
        for row in rows:
            source_class_value = str(row.get("source_class") or "").casefold()
            source_class_group = _source_class_group(source_class_value)
            freshness_value = _freshness_bucket(str(row.get("freshness_status") or ""))
            issue_values = [str(item).casefold() for item in row.get("issue_tags") or row.get("issue_labels") or []]
            blob = " ".join(
                [
                    str(row.get("title") or ""),
                    str(row.get("citation") or ""),
                    str(row.get("text") or ""),
                    " ".join(issue_values),
                ]
            ).casefold()
            if class_filter and class_filter not in source_class_value and class_filter != source_class_group:
                continue
            if freshness_filter and freshness_filter != freshness_value:
                continue
            if issue_filter and issue_filter not in blob:
                continue
            if q and q not in blob:
                continue
            filtered.append(self._present_source_row(row, root))
        start = max(0, int(offset or 0))
        end = start + max(1, min(int(limit or 100), 250))
        page = filtered[start:end]
        return {
            "status": "pass",
            "count": len(filtered),
            "offset": start,
            "limit": end - start,
            "build_id": self._active_build_id(root),
            "sources": page,
            "counts": self._freshness_counts(rows),
            "source_class_counts": self._source_class_counts(rows),
            "review_required": True,
        }

    def get_source(self, source_id: str) -> dict[str, Any]:
        root = self._require_data_root()
        source_id = str(source_id or "").strip()
        if not source_id:
            return {"status": "blocked", "blockers": ["source_id_required"], "review_required": True}
        row = self._find_source_row(root, source_id)
        if row is None:
            return {"status": "not_found", "source_id": source_id, "review_required": True}
        present = self._present_source_row(row, root)
        source_text = _safe_text(row.get("text") or row.get("body") or row.get("instructions") or "", limit=12_000)
        return {
            "status": "pass",
            "source_id": source_id,
            "build_id": self._active_build_id(root),
            "source_card": present,
            "source_text": source_text or None,
            "source_span": row.get("source_span") or {},
            "parsed_record": _sanitize_paths(row),
            "source_span_preview": _safe_text((row.get("source_span_preview") or source_text or "")[:800], limit=800),
            "review_required": True,
        }

    def get_source_span(self, source_id: str, *, start_offset: int | None = None, end_offset: int | None = None) -> dict[str, Any]:
        root = self._require_data_root()
        row = self._find_source_row(root, str(source_id or "").strip())
        if row is None:
            return {"status": "not_found", "review_required": True}
        text = str(row.get("text") or row.get("body") or row.get("instructions") or "")
        span = row.get("source_span") if isinstance(row.get("source_span"), dict) else {}
        start = int(start_offset if start_offset is not None else span.get("start_offset", 0) or 0)
        end = int(end_offset if end_offset is not None else span.get("end_offset", min(len(text), start + 400)) or min(len(text), start + 400))
        start = max(0, min(start, len(text)))
        end = max(start, min(end, len(text)))
        return {
            "status": "pass",
            "source_id": row.get("source_id"),
            "source_span": {"start_offset": start, "end_offset": end},
            "preview": text[start:end],
            "source_text": text[:12_000],
            "source_card": self._present_source_row(row, root),
            "review_required": True,
        }

    def get_update_report(self, build_id: str) -> dict[str, Any]:
        root = self._require_data_root()
        report_dir = root / "official_authority_store" / "update_reports"
        for path in sorted(report_dir.glob("*.json")):
            try:
                payload = _load_json(path)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if str(payload.get("build_id") or "") == str(build_id or ""):
                return {"status": "pass", "build_id": build_id, "update_report": payload, "review_required": True}
        return {"status": "not_found", "build_id": build_id, "review_required": True}

    def update(
        self,
        *,
        dry_run: bool = False,
        source_classes: Iterable[str] | None = None,
        fixture_mode: bool = False,
        force_refresh: bool = False,
        allow_live: bool = False,
        max_targets: int | None = None,
    ) -> dict[str, Any]:
        root = self.ensure_layout()
        targets = load_official_source_targets()
        if source_classes:
            wanted = {str(item).casefold() for item in source_classes if str(item).strip()}
            targets = [
                target
                for target in targets
                if target.source_class.casefold() in wanted or _source_class_group(target.source_class.casefold()) in wanted
            ]
        if max_targets is not None:
            targets = targets[: max(0, int(max_targets))]
        job = AuthorityUpdateJob(job_id=uuid.uuid4().hex)
        with self._lock:
            self._jobs[job.job_id] = job
            self._active_job_id = job.job_id
        if dry_run:
            job.status = "completed"
            job.started_at = _utc_now()
            job.finished_at = _utc_now()
            job.result = {
                "status": "pass",
                "mode": "dry_run",
                "target_count": len(targets),
                "source_classes": sorted({target.source_class for target in targets}),
                "data_root_layout": True,
                "review_required": True,
            }
            return job.as_dict()

        def _run() -> None:
            job.status = "running"
            job.started_at = _utc_now()
            try:
                fetcher = self._build_fetcher(targets, fixture_mode=fixture_mode, allow_live=allow_live, force_refresh=force_refresh)
                ingestor = OfficialAuthorityIngestor(fetcher=fetcher, snapshot_base_dir=root / "official_authority_store" / "snapshots")
                ingested = ingestor.ingest_all(targets, continue_on_error=True)
                if job.cancel_requested:
                    job.status = "canceled"
                    job.message = "Update canceled before publication."
                    return
                manifest_path = ingestor.write_manifest([item.to_dict() for item in ingested])
                failed_path = ingestor.write_failure_report()
                update_report = SourceUpdateEngine(data_root=root).run(write_report=True)
                parsed_report = ParsedAuthorityStoreBuilder(data_root=root).build()
                ParsedAuthorityIndexBuilder(data_root=root).build(write=True)
                publication = AuthorityProductPublisher(data_root=root, repo_root=self.repo_root).publish(product_version="authority-library", activate=True)
                verification = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify(build_id=publication.build_id)
                job.result = {
                    "status": "pass" if publication.status == "pass" and verification.status == "pass" and not ingestor.failed else "partial",
                    "build_id": publication.build_id,
                    "target_count": len(targets),
                    "ingested_count": len(ingested),
                    "failed_count": len(ingestor.failed),
                    "manifest_path": _mask_path(manifest_path),
                    "failed_sources_path": _mask_path(failed_path),
                    "source_update_report": _sanitize_paths(update_report.as_dict()),
                    "parsed_authority_report": _sanitize_paths(parsed_report.as_dict()),
                    "publication": _sanitize_paths(publication.as_dict()),
                    "verification": _sanitize_paths(verification.as_dict()),
                    "review_required": True,
                }
                job.status = "completed" if publication.status == "pass" and verification.status == "pass" and not ingestor.failed else "failed"
                job.message = "Authority update finished."
            except Exception as exc:
                job.status = "failed"
                job.message = f"{type(exc).__name__}: {exc}"
                job.result = {"status": "blocked", "error": job.message, "review_required": True}
            finally:
                job.finished_at = _utc_now()
                with self._lock:
                    self._active_job_id = ""

        thread = threading.Thread(target=_run, name=f"authority-update-{job.job_id}", daemon=True)
        thread.start()
        return job.as_dict()

    def cancel_update(self, job_id: str | None = None) -> dict[str, Any]:
        job = self.get_job(job_id) if job_id else self.active_job()
        if job is None:
            return {"status": "not_running", "review_required": True}
        job.cancel_requested = True
        if job.status in {"queued", "running"}:
            job.status = "canceled"
            job.message = "Cancellation requested."
        return job.as_dict()

    def _build_fetcher(self, targets: list[SourceTarget], *, fixture_mode: bool, allow_live: bool, force_refresh: bool):
        if fixture_mode:
            return _FixtureFetcher(self.fixture_dir, _DEFAULT_FIXTURE_BY_TARGET_ID)
        if not allow_live:
            raise ValueError("live authority ingestion requires allow_live=True or fixture_mode=True")
        return OfficialSourceFetcher(timeout_seconds=30.0, min_delay_seconds=0.5, max_retries=1, strict_content_type=False)

    def _require_data_root(self) -> Path:
        if self.data_root is None:
            raise FileNotFoundError("authority data root is not configured")
        self._ensure_containment(self.data_root)
        return self.data_root

    def _ensure_containment(self, root: Path) -> None:
        resolved = Path(root).expanduser().resolve()
        if is_inside_project_repo(resolved, self.repo_root):
            raise ValueError("authority data root must be outside the source repository")
        if os.name == "nt":
            forbidden_roots = [Path(os.environ.get("WINDIR", r"C:\\Windows")).resolve(), Path(os.environ.get("ProgramFiles", r"C:\\Program Files")).resolve()]
            for forbidden in forbidden_roots:
                try:
                    resolved.relative_to(forbidden)
                except ValueError:
                    continue
                raise ValueError("authority data root may not be inside a Windows system directory")
        forbidden_workspaces = [self.repo_root / "dist", self.repo_root / "build", self.repo_root / "installer", self.repo_root / "store"]
        for workspace in forbidden_workspaces:
            try:
                resolved.relative_to(workspace.resolve())
            except ValueError:
                continue
            raise ValueError("authority data root may not be inside a packaging or build workspace")

    def _source_rows(self, root: Path) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        parsed_root = root / "parsed_authority_store"
        for path in sorted(parsed_root.rglob("*.jsonl")):
            rows.extend(_load_jsonl(path))
        if rows:
            return rows
        if self._active_pointer(root).get("build_id"):
            return self._source_cards_from_active_build(root)
        return []

    def _source_cards_from_active_build(self, root: Path) -> list[dict[str, Any]]:
        build_id = self._active_build_id(root)
        if not build_id:
            return []
        manifest_path = root / "authority_product" / "builds" / build_id / "authority_product_manifest.json"
        if not manifest_path.is_file():
            return []
        manifest = _load_json(manifest_path)
        cards: list[dict[str, Any]] = []
        for row in manifest.get("source_snapshots") or []:
            if isinstance(row, dict):
                cards.append(row)
        return cards

    def _find_source_row(self, root: Path, source_id: str) -> dict[str, Any] | None:
        for row in self._source_rows(root):
            if str(row.get("source_id") or row.get("record_id") or "") == source_id:
                return row
        return None

    def _present_source_row(self, row: dict[str, Any], root: Path) -> dict[str, Any]:
        source_class = str(row.get("source_class") or row.get("source_type") or "")
        freshness_status = str(row.get("freshness_status") or "unknown")
        source_span = row.get("source_span") if isinstance(row.get("source_span"), dict) else {}
        source_url = str(row.get("source_url_or_path") or row.get("url") or "")
        snapshot_path = str(row.get("snapshot_path") or row.get("relative_path") or "")
        issue_tags = row.get("issue_tags") or row.get("issue_labels") or []
        title = str(row.get("title") or row.get("caption") or row.get("document_id") or row.get("source_id") or "Source")
        citation = str(row.get("citation") or row.get("citation_hint") or "")
        text = str(row.get("text") or row.get("body") or row.get("instructions") or "")
        snippet = text[:400]
        technical = {
            "source_id": row.get("source_id") or row.get("record_id"),
            "source_class": source_class,
            "source_hash": row.get("source_hash") or row.get("hash"),
            "retrieved_at": row.get("retrieved_at"),
            "parser_status": row.get("parser_status"),
            "parser_name": row.get("parser_name") or row.get("parser"),
            "snapshot_relative_path": _mask_path(snapshot_path),
            "source_url_or_path": source_url or None,
            "source_span": source_span,
            "previous_snapshot_hash": row.get("previous_sha256") or row.get("previous_snapshot_hash"),
            "content_type": _metadata_value(row, "content_type"),
            "byte_count": _metadata_value(row, "byte_count"),
            "robots_policy_result": _fetch_metadata_value(row, "robots_policy_result"),
            "retry_count": _fetch_metadata_value(row, "retry_count") or _fetch_metadata_value(row, "attempt_count"),
        }
        return {
            "source_id": row.get("source_id") or row.get("record_id"),
            "title": title,
            "citation": citation or None,
            "source_class": source_class,
            "source_class_group": _source_class_group(source_class),
            "jurisdiction": row.get("jurisdiction") or "Maine",
            "authority_status": row.get("authority_status") or ("verified_official_maine" if freshness_status in {"fresh", "current"} else "stale_unknown"),
            "freshness_status": freshness_status,
            "freshness_bucket": _freshness_bucket(freshness_status),
            "review_required": True,
            "official_url": source_url or None,
            "url": source_url or None,
            "source_lane": "legal_authority",
            "source_span": source_span,
            "issue_tags": issue_tags,
            "source_hash": row.get("source_hash") or row.get("hash"),
            "retrieved_at": row.get("retrieved_at"),
            "parser_status": row.get("parser_status"),
            "parser_name": row.get("parser_name") or row.get("parser") or row.get("parser_audit", {}).get("parser_name"),
            "technical": technical,
            "snippet": snippet or row.get("description") or "Official source",
            "can_support_current_law_claim": freshness_status in {"fresh", "current", "verified_current", "known_version_date"},
            "source_span_preview": _safe_text(str(row.get("source_span_preview") or snippet or ""), limit=400),
            "parser_warnings": list(row.get("parser_warnings") or row.get("parser_audit", {}).get("warnings") or []),
            "previous_snapshot_hash": row.get("previous_sha256") or row.get("previous_snapshot_hash"),
        }

    def _active_build_id(self, root: Path) -> str:
        return str(self._active_pointer(root).get("build_id") or "")

    def _active_pointer(self, root: Path) -> dict[str, Any]:
        path = root / "authority_product" / "ACTIVE_BUILD.json"
        if not path.is_file():
            return {}
        try:
            loaded = _load_json(path)
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _latest_update_report(self, root: Path) -> dict[str, Any]:
        report_path = root / "source_update_report.json"
        if not report_path.is_file():
            return {}
        try:
            loaded = _load_json(report_path)
        except Exception:
            return {}
        return loaded if isinstance(loaded, dict) else {}

    def _freshness_counts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"fresh": 0, "stale": 0, "unknown": 0, "superseded": 0, "retrieval_failed": 0, "parser_failed": 0}
        for row in rows:
            counts[_freshness_bucket(str(row.get("freshness_status") or "unknown"))] = counts.get(_freshness_bucket(str(row.get("freshness_status") or "unknown")), 0) + 1
        return counts

    def _source_class_counts(self, rows: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            key = _source_class_group(str(row.get("source_class") or "federal"))
            counts[key] = counts.get(key, 0) + 1
        return counts
