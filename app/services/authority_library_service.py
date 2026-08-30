from __future__ import annotations

import json
import os
import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from legal.connectors import OfficialAuthorityIngestor, OfficialSourceFetcher, load_official_source_targets
from legal.connectors.base import SourceTarget
from legal.connectors.parser_regression import ParserRegressionCorpus
from legal.data_boundaries import default_external_data_root, ensure_external_authority_root, is_inside_project_repo
from legal.authority_store import ParsedAuthorityStoreBuilder
from legal.production.authority_product import AuthorityProductPublisher, AuthorityProductVerifier
from legal.production.source_update_engine import SourceUpdateEngine
from legal.authority_store.authority_layer import ParsedAuthorityIndexBuilder
from legal.retrieval.index_builder import RetrievalIndexBuilder
from app.services.authority_product_service import AuthorityProductService


_DEFAULT_FIXTURE_BY_TARGET_ID = {
    "me-revisor-title-19a-index": "mrs-title-19a-domestic-relations.html",
    "me-courts-civil-rules": "maine-rules-civil-family-division.html",
    "me-courts-rules-index": "maine-rules-civil-family-division.html",
    "me-courts-forms-index": "maine-court-forms-family.html",
    "me-judicial-branch-appeals": "maine-judicial-branch-appeals.html",
}

# These are operational review intervals, not legal conclusions about whether a
# source is current.  A source can be within its operational check interval and
# still require legal/freshness review; a source outside it is surfaced for an
# explicit operator decision rather than silently refreshed.
_FRESHNESS_THRESHOLDS_DAYS = {
    "statutes": 45,
    "rules": 45,
    "forms": 30,
    "opinions": 90,
    "federal": 90,
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
    record_metadata = row.get("metadata")
    nested_fetch_metadata = record_metadata.get("fetch_metadata") if isinstance(record_metadata, dict) else None
    if isinstance(nested_fetch_metadata, dict):
        value = nested_fetch_metadata.get(key)
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


def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write an authority control record without exposing a partial pointer."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("authority control record may not be a symlink")
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


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
        # Merely opening the workbench must not create an authority store.
        # Ingest/update operations initialize their layout explicitly.
        root = self._require_data_root()
        active = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        try:
            direct_authority = AuthorityProductService(data_root=root).direct_authority_coverage()
        except (FileNotFoundError, OSError, ValueError):
            direct_authority = {
                "status": "blocked",
                "counts_by_kind": {},
                "missing_kinds": [],
                "direct_exact_source_count": 0,
                "source_provided_pinpoint_count": 0,
                "source_bound_drafting_available": False,
                "blockers": ["direct_authority_coverage_unavailable"],
                "review_required": True,
                "current_law_determined": False,
                "network_used": False,
            }
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
            "direct_authority": direct_authority,
            "source_bound_drafting_available": bool(
                direct_authority.get("source_bound_drafting_available")
            ),
        }

    @staticmethod
    def _parse_retrieved_at(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            # The timestamp lacks an admitted timezone.  It may still be
            # displayed, but it cannot establish a reliable age calculation.
            return None
        return parsed.astimezone(timezone.utc)

    def freshness_dashboard(self, *, now: datetime | None = None) -> dict[str, Any]:
        """Return a source-metadata operations dashboard for human review.

        This inspects only the active external authority metadata.  It does
        not fetch, modify, activate, or substitute sources, and it never
        treats a check interval as a determination that law is current.
        """
        root = self.ensure_layout()
        observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        active = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        update_report = self._latest_update_report(root)
        rows = self._source_rows(root)
        source_class_counts = self._source_class_counts(rows)
        freshness_counts = self._freshness_counts(rows)
        classes: dict[str, dict[str, Any]] = {
            name: {
                "source_class": name,
                "threshold_days": threshold,
                "source_count": 0,
                "within_threshold": 0,
                "overdue": 0,
                "retrieval_date_unknown": 0,
                "parser_failures": 0,
                "freshness_status_counts": {},
            }
            for name, threshold in _FRESHNESS_THRESHOLDS_DAYS.items()
        }
        overdue_sources: list[dict[str, Any]] = []
        parser_failures: list[dict[str, Any]] = []
        date_unknown_sources: list[dict[str, Any]] = []
        for row in rows:
            source_id = str(row.get("source_id") or row.get("record_id") or "").strip()
            source_class = _source_class_group(str(row.get("source_class") or row.get("source_type") or ""))
            summary = classes.setdefault(
                source_class,
                {
                    "source_class": source_class,
                    "threshold_days": _FRESHNESS_THRESHOLDS_DAYS.get(source_class, 90),
                    "source_count": 0,
                    "within_threshold": 0,
                    "overdue": 0,
                    "retrieval_date_unknown": 0,
                    "parser_failures": 0,
                    "freshness_status_counts": {},
                },
            )
            freshness_bucket = _freshness_bucket(str(row.get("freshness_status") or "unknown"))
            parser_audit = row.get("parser_audit") if isinstance(row.get("parser_audit"), dict) else {}
            parser_status = str(row.get("parser_status") or parser_audit.get("status") or "unknown").casefold()
            retrieved_at = self._parse_retrieved_at(row.get("retrieved_at"))
            summary["source_count"] += 1
            status_counts = summary["freshness_status_counts"]
            status_counts[freshness_bucket] = int(status_counts.get(freshness_bucket, 0)) + 1
            public_row = {
                "source_id": source_id,
                "source_class": source_class,
                "freshness_status": freshness_bucket,
                "retrieved_at": str(row.get("retrieved_at") or "") or None,
                "parser_status": parser_status or "unknown",
                "review_required": True,
            }
            parser_failed = freshness_bucket == "parser_failed" or parser_status in {
                "failed",
                "error",
                "parser_failed",
                "unparsed",
            }
            if parser_failed:
                summary["parser_failures"] += 1
                parser_failures.append({**public_row, "reason": "parser_failure"})
            if retrieved_at is None:
                summary["retrieval_date_unknown"] += 1
                date_unknown_sources.append({**public_row, "reason": "retrieval_date_missing_or_invalid"})
                continue
            age_days = max(0, int((observed_at - retrieved_at).total_seconds() // 86_400))
            public_row["age_days"] = age_days
            public_row["threshold_days"] = summary["threshold_days"]
            if age_days > int(summary["threshold_days"]):
                summary["overdue"] += 1
                overdue_sources.append({**public_row, "reason": "operational_check_interval_elapsed"})
            else:
                summary["within_threshold"] += 1

        # Stable sort helps a human compare two refreshes without conflating
        # result order with a priority or legal-materiality ranking.
        overdue_sources.sort(key=lambda item: (str(item.get("source_class") or ""), str(item.get("source_id") or "")))
        parser_failures.sort(key=lambda item: (str(item.get("source_class") or ""), str(item.get("source_id") or "")))
        date_unknown_sources.sort(key=lambda item: (str(item.get("source_class") or ""), str(item.get("source_id") or "")))
        blockers: list[str] = []
        if active.status != "pass":
            blockers.append("active_authority_build_unverified")
        if overdue_sources:
            blockers.append("operational_source_freshness_review_required")
        if parser_failures:
            blockers.append("authority_parser_failures_require_review")
        if date_unknown_sources:
            blockers.append("authority_retrieval_dates_missing_or_invalid")
        if int(freshness_counts.get("stale") or 0) > 0:
            blockers.append("authority_metadata_marks_sources_stale")
        if int(freshness_counts.get("unknown") or 0) > 0:
            blockers.append("authority_metadata_freshness_unknown")
        last_accepted_build = {
            "build_id": active.build_id or str(self._active_pointer(root).get("build_id") or ""),
            "verified": active.status == "pass",
            "verification_status": active.status,
            "verification_blockers": list(active.blockers or []),
            "last_successful_update": update_report.get("generated_at")
            if update_report.get("status") == "pass"
            else None,
        }
        return {
            "schema_version": "authority_freshness_dashboard_v1",
            "status": "needs_review" if blockers else "metadata_observed",
            "observed_at": observed_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "last_accepted_build": last_accepted_build,
            "source_class_thresholds": classes,
            "source_class_counts": source_class_counts,
            "freshness_counts": freshness_counts,
            "overdue_sources": overdue_sources,
            "parser_failures": parser_failures,
            "retrieval_date_unknown_sources": date_unknown_sources,
            "blockers": sorted(set(blockers)),
            "review_required": True,
            "current_law_determined": False,
            "network_used": False,
            "notice": (
                "Operational check intervals and parser metadata are review signals only. "
                "They do not determine legal currentness, completeness, or legal effect."
            ),
        }

    @staticmethod
    def _normalized_official_url(value: Any) -> str:
        """Normalize an observed public URL without following or requesting it."""
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return ""
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return ""
        path = parsed.path.rstrip("/") or "/"
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, parsed.query, ""))

    @staticmethod
    def _availability_report_findings(update_report: dict[str, Any]) -> list[dict[str, Any]]:
        findings = update_report.get("findings") if isinstance(update_report, dict) else []
        return [item for item in findings if isinstance(item, dict)] if isinstance(findings, list) else []

    def availability_monitor(self) -> dict[str, Any]:
        """Expose stored official-source availability evidence for review.

        The monitor is intentionally offline.  It does not probe URLs, accept a
        redirect, replace an official source with a mirror, or determine that
        an authority remains available/current.  It makes the last admitted
        fetch and update metadata inspectable so an operator can decide whether
        an explicit, controlled update is needed.
        """
        root = self.ensure_layout()
        active = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        update_report = self._latest_update_report(root)
        rows = self._source_rows(root)
        issues: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add_issue(source_id: str, code: str, *, source_class: str = "", expected_url: str = "", observed_url: str = "", status_code: Any = None) -> None:
            key = (source_id, code)
            if key in seen:
                return
            seen.add(key)
            issues.append(
                {
                    "source_id": source_id or "__unidentified_source__",
                    "source_class": _source_class_group(source_class),
                    "code": code,
                    "expected_official_url": expected_url or None,
                    "observed_url": observed_url or None,
                    "http_status": int(status_code) if isinstance(status_code, int) else None,
                    "review_required": True,
                    "mirror_substitution": False,
                }
            )

        for row in rows:
            source_id = str(row.get("source_id") or row.get("record_id") or "").strip()
            source_class = str(row.get("source_class") or row.get("source_type") or "")
            expected_url = self._normalized_official_url(row.get("source_url_or_path") or row.get("url"))
            final_url = self._normalized_official_url(
                _metadata_value(row, "final_url") or _fetch_metadata_value(row, "final_url")
            )
            status_code = _metadata_value(row, "status_code") or _fetch_metadata_value(row, "status_code")
            if not expected_url:
                add_issue(source_id, "official_url_missing_or_unusable", source_class=source_class)
            if final_url and expected_url and final_url != expected_url:
                add_issue(
                    source_id,
                    "official_url_moved_or_redirected_review_required",
                    source_class=source_class,
                    expected_url=expected_url,
                    observed_url=final_url,
                    status_code=status_code,
                )
            previous_hash = str(_metadata_value(row, "previous_sha256") or row.get("previous_snapshot_hash") or "").strip()
            current_hash = str(row.get("source_hash") or row.get("hash") or "").strip()
            if previous_hash and current_hash and previous_hash != current_hash:
                add_issue(source_id, "source_hash_changed_review_required", source_class=source_class, expected_url=expected_url)
            robots = str(_fetch_metadata_value(row, "robots_policy_result") or "").casefold()
            error_markers = " ".join(
                str(_fetch_metadata_value(row, key) or "")
                for key in ("failure_code", "error_code", "error_type", "fetch_status", "status")
            ).casefold()
            if any(marker in error_markers for marker in ("tls", "ssl", "certificate")):
                add_issue(source_id, "tls_or_certificate_failure_review_required", source_class=source_class, expected_url=expected_url)
            try:
                numeric_status = int(status_code) if status_code not in (None, "") else None
            except (TypeError, ValueError):
                numeric_status = None
            if numeric_status in {401, 403, 429, 451} or "disallow" in robots or "restricted" in error_markers:
                add_issue(
                    source_id,
                    "official_source_access_restricted_review_required",
                    source_class=source_class,
                    expected_url=expected_url,
                    observed_url=final_url,
                    status_code=numeric_status,
                )

        for source_id in update_report.get("changed_since_last_build", {}).get("hash_changed", []) if isinstance(update_report.get("changed_since_last_build"), dict) else []:
            add_issue(str(source_id), "source_hash_changed_review_required")
        for finding in self._availability_report_findings(update_report):
            source_id = str(finding.get("source_id") or "")
            code = str(finding.get("code") or "").casefold()
            if any(marker in code for marker in ("tls", "ssl", "certificate")):
                add_issue(source_id, "tls_or_certificate_failure_review_required")
            if any(marker in code for marker in ("robots", "access", "forbidden", "restricted", "http_401", "http_403", "http_429", "http_451")):
                add_issue(source_id, "official_source_access_restricted_review_required")
            if any(marker in code for marker in ("redirect", "moved", "url_changed")):
                add_issue(source_id, "official_url_moved_or_redirected_review_required")

        issues.sort(key=lambda item: (str(item["code"]), str(item["source_id"])))
        categories = {
            "moved_urls": [item for item in issues if item["code"] == "official_url_moved_or_redirected_review_required"],
            "changed_hashes": [item for item in issues if item["code"] == "source_hash_changed_review_required"],
            "tls_failures": [item for item in issues if item["code"] == "tls_or_certificate_failure_review_required"],
            "access_restrictions": [item for item in issues if item["code"] == "official_source_access_restricted_review_required"],
            "url_metadata_gaps": [item for item in issues if item["code"] == "official_url_missing_or_unusable"],
        }
        blockers = [item["code"] for item in issues]
        if active.status != "pass":
            blockers.append("active_authority_build_unverified")
        return {
            "schema_version": "official_source_availability_monitor_v1",
            "status": "needs_review" if blockers else "metadata_observed",
            "observed_at": _utc_now(),
            "last_update_report_at": update_report.get("generated_at") or None,
            "last_accepted_build": {
                "build_id": active.build_id or str(self._active_pointer(root).get("build_id") or ""),
                "verified": active.status == "pass",
                "verification_status": active.status,
            },
            "source_count": len(rows),
            "issues": issues,
            "categories": categories,
            "blockers": sorted(set(blockers)),
            "review_required": True,
            "availability_determined": False,
            "current_law_determined": False,
            "network_used": False,
            "mirror_substitution": False,
            "notice": (
                "This reviews stored fetch and update metadata only. It does not request any URL, "
                "accept redirects, substitute mirrors, determine source availability, or determine current law."
            ),
        }

    def parser_regression_corpus(self) -> dict[str, Any]:
        """Run only the bundled synthetic parser-shape corpus.

        This is a local engineering control, not an authority update.  The
        fixtures cannot be retrieved, searched as legal authority, or used to
        establish a source's legal content or currentness.
        """
        result = ParserRegressionCorpus(self.fixture_dir / "parser_regression").run()
        result["fixture_root_label"] = "parser_regression"
        return result

    def parser_regression_fixture(self, fixture_id: str) -> dict[str, Any]:
        safe_id = str(fixture_id or "").strip()
        if not safe_id or len(safe_id) > 160 or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-_." for character in safe_id.casefold()):
            return {
                "status": "blocked",
                "fixture_id": safe_id[:160],
                "blockers": ["parser_regression_fixture_id_invalid"],
                "review_required": True,
                "can_support_legal_claim": False,
            }
        return ParserRegressionCorpus(self.fixture_dir / "parser_regression").run_fixture(safe_id)

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
        admission = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        if admission.status != "pass":
            return {
                "status": "blocked",
                "count": 0,
                "offset": max(0, int(offset or 0)),
                "limit": max(1, min(int(limit or 100), 250)),
                "build_id": admission.build_id,
                "sources": [],
                "counts": {},
                "source_class_counts": {},
                "blockers": sorted(set(["active_authority_build_unverified", *list(admission.blockers or [])])),
                "source_boundary": "verified_active_immutable_authority_build_required",
                "review_required": True,
            }
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
        admission = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        if admission.status != "pass":
            return {
                "status": "blocked",
                "source_id": source_id,
                "build_id": admission.build_id,
                "blockers": sorted(set(["active_authority_build_unverified", *list(admission.blockers or [])])),
                "review_required": True,
            }
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
        source_id = str(source_id or "").strip()
        admission = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify()
        if admission.status != "pass":
            return {
                "status": "blocked",
                "source_id": source_id,
                "build_id": admission.build_id,
                "blockers": sorted(set(["active_authority_build_unverified", *list(admission.blockers or [])])),
                "review_required": True,
            }
        row = self._find_source_row(root, source_id)
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

    def compare_builds(self, candidate_build_id: str) -> dict[str, Any]:
        """Compare a verified staged build to the active immutable build.

        The result deliberately compares admitted source identities and hashes
        only.  It is a review aid, never a legal-effect or completeness result.
        """
        root = self._require_data_root()
        candidate, candidate_blockers = self._verified_build_manifest(root, candidate_build_id)
        if candidate is None:
            return {
                "status": "blocked",
                "candidate_build_id": str(candidate_build_id or ""),
                "blockers": candidate_blockers,
                "review_required": True,
            }
        active_build_id = self._active_build_id(root)
        active: dict[str, Any] | None = None
        active_blockers: list[str] = []
        if active_build_id:
            active, active_blockers = self._verified_build_manifest(root, active_build_id)
        candidate_sources = self._sources_by_id(candidate)
        active_sources = self._sources_by_id(active or {})
        added = sorted(set(candidate_sources) - set(active_sources))
        removed = sorted(set(active_sources) - set(candidate_sources))
        hash_changed = sorted(
            source_id
            for source_id in set(candidate_sources) & set(active_sources)
            if candidate_sources[source_id] != active_sources[source_id]
        )
        unchanged = sorted(
            source_id
            for source_id in set(candidate_sources) & set(active_sources)
            if candidate_sources[source_id] == active_sources[source_id]
        )
        return {
            "status": "needs_review",
            "candidate_build_id": str(candidate.get("build_id") or candidate_build_id),
            "active_build_id": active_build_id or None,
            "candidate_verified": True,
            "active_build_verified": active is not None if active_build_id else None,
            "active_build_blockers": active_blockers,
            "source_diff": {
                "added": added,
                "removed": removed,
                "hash_changed": hash_changed,
                "unchanged_count": len(unchanged),
            },
            "review_required": True,
            "boundary": "This compares admitted source IDs and hashes only. It does not determine legal effect, currentness, or completeness.",
        }

    def activate_build(self, build_id: str, *, operation: str = "activate") -> dict[str, Any]:
        """Atomically activate an already staged and verified authority build."""
        root = self._require_data_root()
        manifest, blockers = self._verified_build_manifest(root, build_id)
        if manifest is None:
            return {"status": "blocked", "build_id": str(build_id or ""), "blockers": blockers, "review_required": True}
        active_before = self._active_build_id(root)
        target_build_id = str(manifest.get("build_id") or build_id)
        if operation == "rollback" and target_build_id == active_before:
            return {
                "status": "blocked",
                "build_id": target_build_id,
                "blockers": ["rollback_target_is_already_active"],
                "review_required": True,
            }
        product_root = root / "authority_product"
        if product_root.is_symlink():
            return {"status": "blocked", "build_id": target_build_id, "blockers": ["authority_product_root_symlinked"], "review_required": True}
        manifest_path = product_root / "builds" / target_build_id / "authority_product_manifest.json"
        pointer = {
            "schema_version": str(manifest.get("schema_version") or "1.1"),
            "build_id": target_build_id,
            "manifest_relative_path": manifest_path.relative_to(root).as_posix(),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "activated_at": _utc_now(),
            "activation_operation": operation,
            "review_required": True,
        }
        history = product_root / "activation_receipts.jsonl"
        if history.is_symlink():
            return {"status": "blocked", "build_id": target_build_id, "blockers": ["authority_activation_history_symlinked"], "review_required": True}
        with self._lock:
            _atomic_write_json(product_root / "ACTIVE_BUILD.json", pointer)
            receipt = {
                "receipt_id": uuid.uuid4().hex,
                "recorded_at": _utc_now(),
                "operation": operation,
                "build_id": target_build_id,
                "previous_build_id": active_before or None,
                "review_required": True,
            }
            with history.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(receipt, sort_keys=True, ensure_ascii=False) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return {
            "status": "pass",
            "operation": operation,
            "build_id": target_build_id,
            "previous_build_id": active_before or None,
            "activation_receipt": receipt,
            "review_required": True,
            "boundary": "Activation changes the selected verified local authority build. It does not determine legal effect or make a legal conclusion.",
        }

    @staticmethod
    def _sources_by_id(manifest: dict[str, Any]) -> dict[str, str]:
        rows = manifest.get("source_snapshots") if isinstance(manifest.get("source_snapshots"), list) else []
        return {
            str(row.get("source_id")): str(row.get("sha256") or "")
            for row in rows
            if isinstance(row, dict) and str(row.get("source_id") or "")
        }

    def _verified_build_manifest(self, root: Path, build_id: str) -> tuple[dict[str, Any] | None, list[str]]:
        candidate = str(build_id or "").strip().lower()
        verification = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify(build_id=candidate)
        if verification.status != "pass":
            return None, sorted(set(verification.blockers or ["authority_build_verification_failed"]))
        path = root / "authority_product" / "builds" / candidate / "authority_product_manifest.json"
        try:
            manifest = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return None, ["authority_product_manifest_invalid"]
        if not isinstance(manifest, dict) or str(manifest.get("build_id") or "") != candidate:
            return None, ["authority_product_manifest_identity_invalid"]
        return manifest, []

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
                snapshot_manifest_path = ingestor.write_manifest([item.to_dict() for item in ingested])
                # The ingestor keeps its working manifest beside snapshots, but
                # every downstream authority gate reads the canonical external
                # store location.  Promote the completed manifest atomically so
                # an interrupted update cannot leave mixed generations behind.
                manifest_path = root / "official_authority_store" / "source_manifest.json"
                _atomic_write_json(manifest_path, _load_json(snapshot_manifest_path))
                failed_path = ingestor.write_failure_report()
                update_report = SourceUpdateEngine(data_root=root).run(write_report=True)
                parsed_report = ParsedAuthorityStoreBuilder(data_root=root).build()
                ParsedAuthorityIndexBuilder(data_root=root).build(write=True)
                retrieval_report = RetrievalIndexBuilder(data_root=root, repo_root=self.repo_root).build()
                publication = AuthorityProductPublisher(data_root=root, repo_root=self.repo_root).publish(product_version="authority-library", activate=False)
                verification = AuthorityProductVerifier(data_root=root, repo_root=self.repo_root).verify(build_id=publication.build_id)
                staged = publication.status == "pass" and verification.status == "pass" and not ingestor.failed
                build_diff = self.compare_builds(str(publication.build_id or "")) if staged else {}
                job.result = {
                    "status": "staged" if staged else "partial",
                    "build_id": publication.build_id,
                    "target_count": len(targets),
                    "ingested_count": len(ingested),
                    "failed_count": len(ingestor.failed),
                    "manifest_path": _mask_path(manifest_path),
                    "failed_sources_path": _mask_path(failed_path),
                    "source_update_report": _sanitize_paths(update_report.as_dict()),
                    "parsed_authority_report": _sanitize_paths(parsed_report.as_dict()),
                    "retrieval_index_report": _sanitize_paths(retrieval_report.as_dict()),
                    "publication": _sanitize_paths(publication.as_dict()),
                    "verification": _sanitize_paths(verification.as_dict()),
                    "build_diff": _sanitize_paths(build_diff),
                    "activation_performed": False,
                    "next_action": "review_staged_build_then_activate_explicitly" if staged else None,
                    "review_required": True,
                }
                job.status = "completed" if staged else "failed"
                job.message = "Authority update staged for explicit review and activation." if staged else "Authority update did not produce an activatable build."
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
        """Return only parsed rows admitted by the active immutable build.

        ``parsed_authority_store`` is a mutable ingestion workspace.  It must
        not become a public authority inventory merely because an operator has
        begun an update.  When no verified active generation exists, callers
        receive an empty inventory and their existing status/blocker paths
        remain review-required rather than silently falling back to staging.
        """
        try:
            product = AuthorityProductService(data_root=root)
            active = product._active_product(verify_all=True)
            return list(product._iter_active_parsed_rows(active))
        except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
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
            if source_id in {
                str(row.get("source_id") or ""),
                str(row.get("record_id") or ""),
            }:
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
