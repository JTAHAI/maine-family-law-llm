"""Private, local-only health and dependency dashboard primitives.

The dashboard intentionally reports readiness rather than pretending every
optional engine is installed or every external authority build is current.  A
user-triggered snapshot is stored in the active matter as an encrypted,
hash-linked audit receipt.  Neither the response nor the receipt includes a
filesystem path, record text, prompt, credential, or remote endpoint.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_MAX_STATE_BYTES = 512 * 1024
_MAX_SNAPSHOTS = 80
_SAFE_COMPONENT_STATUSES = frozenset({"ready", "degraded", "unavailable", "blocked"})


class HealthDashboardError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_component(
    component_id: str,
    *,
    status: str,
    summary: str,
    details: dict[str, Any] | None = None,
    required_for_core: bool = False,
) -> dict[str, Any]:
    normalized = str(status or "blocked").strip().casefold()
    if normalized not in _SAFE_COMPONENT_STATUSES:
        normalized = "blocked"
    return {
        "component_id": component_id,
        "status": normalized,
        "summary": str(summary or "status unavailable")[:240],
        "details": details or {},
        "required_for_core": bool(required_for_core),
        "review_required": True,
    }


def _safe_authority_status(authority_status: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        raw = dict(authority_status() or {})
        active = raw.get("active") is True and raw.get("status") == "pass"
        details = {
            "active_build_available": active,
            "build_id": str(raw.get("build_id") or "")[:128] or None,
            "retrieval_document_count": int(raw.get("retrieval_document_count") or 0),
            "freshness_counts": raw.get("freshness_counts") if isinstance(raw.get("freshness_counts"), dict) else {},
        }
        blockers = [str(item)[:120] for item in list(raw.get("blockers") or [])[:12]]
        if blockers:
            details["blockers"] = blockers
        return _safe_component(
            "authority",
            status="ready" if active else "degraded",
            summary="Active admitted authority build is available." if active else "Authority needs review before it can support a current-law statement.",
            details=details,
        )
    except Exception:
        return _safe_component(
            "authority",
            status="blocked",
            summary="Authority readiness could not be read. Review the local authority setup.",
            details={"active_build_available": False, "error_code": "authority_status_unavailable"},
        )


def _safe_ocr_status(ocr_status: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        raw = dict(ocr_status() or {})
        engine = dict(raw.get("engine") or {})
        ready = raw.get("status") == "ready"
        return _safe_component(
            "ocr",
            status="ready" if ready else "unavailable",
            summary="Local OCR is ready." if ready else "Local OCR is not ready; scanned pages remain review-required.",
            details={
                "engine_available": bool(engine.get("available")),
                "pdf_ocr_available": bool(engine.get("pdf_ocr_available")),
                "one_click_install_available": bool(raw.get("one_click_available")),
                "documents_read_for_check": False,
                "network_used_for_check": False,
            },
        )
    except Exception:
        return _safe_component(
            "ocr",
            status="blocked",
            summary="OCR readiness could not be checked.",
            details={"error_code": "ocr_status_unavailable", "network_used_for_check": False},
        )


def _safe_backup_status(backup_status: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        raw = dict(backup_status() or {})
        ready = raw.get("status") == "ready"
        blockers = [str(item)[:120] for item in list(raw.get("blockers") or [])[:12]]
        return _safe_component(
            "backup",
            status="ready" if ready else "degraded",
            summary="External backup rehearsal is configured." if ready else "Backup is not configured or needs review; local matter data is not exported by this check.",
            details={
                "backup_root_configured": bool(raw.get("backup_root_configured")),
                "restore_mode": str(raw.get("restore_mode") or "isolated_rehearsal_only")[:120],
                "blockers": blockers,
            },
        )
    except Exception:
        return _safe_component(
            "backup",
            status="blocked",
            summary="Backup readiness could not be checked.",
            details={"error_code": "backup_status_unavailable"},
        )


def collect_dashboard(
    *,
    case_root: str | Path,
    runtime_health: Callable[[], dict[str, Any]],
    authority_status: Callable[[], dict[str, Any]],
    ocr_status: Callable[[], dict[str, Any]],
    backup_status: Callable[[], dict[str, Any]],
    runtime_kernel: Any,
    matter_id: str,
) -> dict[str, Any]:
    """Return a bounded, content-free health snapshot for one active matter."""

    root = Path(case_root).resolve()
    components: list[dict[str, Any]] = []
    try:
        health = dict(runtime_health() or {})
        health_ok = health.get("status") == "ok"
        components.append(
            _safe_component(
                "api",
                status="ready" if health_ok else "degraded",
                summary="The local API responded with its embedded runtime health." if health_ok else "The local API is running with one or more embedded-runtime checks needing review.",
                details={
                    "runtime_status": str(health.get("status") or "unknown")[:40],
                    "runtime_blocker_count": len(list(health.get("blockers") or [])),
                    "network_used_for_check": False,
                },
                required_for_core=True,
            )
        )
    except Exception:
        components.append(_safe_component("api", status="blocked", summary="The embedded runtime health could not be read.", details={"error_code": "runtime_health_unavailable"}, required_for_core=True))

    try:
        jobs = list(runtime_kernel.list_jobs(matter_id=matter_id, limit=500))
        active = sum(1 for row in jobs if str(row.get("status") or "") in {"queued", "running", "cancel_requested"})
        components.append(
            _safe_component(
                "database",
                status="ready",
                summary="The local durable job database is available for the active matter.",
                details={"active_job_count": active, "observed_job_count": len(jobs), "matter_scope": "active_matter_only"},
                required_for_core=True,
            )
        )
    except Exception:
        components.append(_safe_component("database", status="blocked", summary="The local durable job database could not be read.", details={"error_code": "runtime_database_unavailable", "matter_scope": "active_matter_only"}, required_for_core=True))

    components.append(_safe_authority_status(authority_status))

    try:
        active_models = sum(1 for row in runtime_kernel.list_jobs(matter_id=matter_id, limit=500) if "model" in str(row.get("job_type") or ""))
        components.append(
            _safe_component(
                "model",
                status="ready",
                summary="The local runtime can schedule approved model work; no model is downloaded by this check.",
                details={"active_or_observed_model_job_count": active_models, "remote_provider_enabled": False, "model_download_started": False},
            )
        )
    except Exception:
        components.append(_safe_component("model", status="degraded", summary="Local model runtime status needs review.", details={"error_code": "model_runtime_status_unavailable", "remote_provider_enabled": False}))

    components.append(_safe_ocr_status(ocr_status))
    video_available = importlib.util.find_spec("cv2") is not None
    components.append(
        _safe_component(
            "media",
            status="ready" if video_available else "unavailable",
            summary="Local audio and video review dependencies are available." if video_available else "Video review dependency is unavailable; media actions will fail closed.",
            details={"local_video_decoder_available": video_available, "network_used_for_check": False, "media_files_read_for_check": False},
        )
    )

    try:
        usage = shutil.disk_usage(root)
        low_space = usage.free < 512 * 1024 * 1024
        components.append(
            _safe_component(
                "storage",
                status="degraded" if low_space else "ready",
                summary="Local storage needs attention before large imports." if low_space else "Local storage is available for the active matter.",
                details={"free_bytes": int(usage.free), "total_bytes": int(usage.total), "path_disclosed": False},
                required_for_core=True,
            )
        )
    except Exception:
        components.append(_safe_component("storage", status="blocked", summary="Local storage could not be checked.", details={"error_code": "storage_status_unavailable", "path_disclosed": False}, required_for_core=True))

    components.append(_safe_backup_status(backup_status))
    now = datetime.now(UTC)
    components.append(
        _safe_component(
            "clock",
            status="ready" if now.tzinfo is UTC else "degraded",
            summary="The local clock supplied a UTC review timestamp." if now.tzinfo is UTC else "The local clock needs review before relying on time-sensitive receipts.",
            details={"utc_timestamp": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"), "network_time_checked": False},
            required_for_core=True,
        )
    )

    critical_failed = [row["component_id"] for row in components if row["required_for_core"] and row["status"] in {"blocked", "unavailable"}]
    optional_attention = [row["component_id"] for row in components if not row["required_for_core"] and row["status"] != "ready"]
    return {
        "schema_version": "local_health_dependency_dashboard_v1",
        "status": "blocked" if critical_failed else ("degraded" if optional_attention else "ready"),
        "components": components,
        "core_blockers": critical_failed,
        "review_attention": optional_attention,
        "matter_scope": "active_matter_only",
        "network_used": False,
        "private_paths_included": False,
        "private_record_content_included": False,
        "review_required": True,
    }


class HealthDependencyDashboardStore:
    """Encrypt user-triggered health receipts inside one active matter."""

    schema_version = "local_health_dependency_dashboard_store_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        self.encryptor = LocalEnvelopeEncryptor(key)
        self.root = self.case_root / "40_RUNTIME" / "health-dashboard"
        self.path = self.root / "snapshots.json.enc"
        self.lock_path = self.root / ".snapshots.lock"

    def _empty(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tenant_id": "",
            "revision": 0,
            "snapshots": [],
            "audit": [],
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            raw = strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True)
            state = self.encryptor.decrypt_json(raw)
        except Exception as exc:
            raise HealthDashboardError("health_dashboard_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version:
            raise HealthDashboardError("health_dashboard_store_unavailable")
        if not isinstance(state.get("snapshots"), list) or not isinstance(state.get("audit"), list):
            raise HealthDashboardError("health_dashboard_store_unavailable")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        try:
            atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        except Exception as exc:
            raise HealthDashboardError("health_dashboard_store_write_failed") from exc

    @staticmethod
    def _safe_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        serialized = _canonical(snapshot)
        text = serialized.decode("utf-8", errors="replace")
        # Snapshots must never become a diagnostic escape hatch for local paths
        # or record contents. The API constructs a component allow-list above.
        if "\\\\" in text or ":/" in text or ":\\" in text:
            raise HealthDashboardError("health_dashboard_private_path_refused")
        return json.loads(text)

    def record(self, snapshot: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        safe_snapshot = self._safe_snapshot(snapshot)
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            existing_tenant = str(state.get("tenant_id") or "")
            if existing_tenant and existing_tenant != tenant_id:
                raise HealthDashboardError("health_dashboard_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            snapshot_hash = _digest(safe_snapshot)
            audit_basis = {
                "event_type": "health_dashboard_viewed",
                "recorded_at": recorded_at,
                "snapshot_hash": snapshot_hash,
                "previous_hash": previous,
                "actor_role": str(actor_role or "reviewer")[:40],
                "tenant_id": str(tenant_id or "local-desktop")[:80],
            }
            audit = {**audit_basis, "event_hash": _digest(audit_basis)}
            receipt = {
                "snapshot_id": f"health_{audit['event_hash'][:24]}",
                "recorded_at": recorded_at,
                "snapshot_hash": snapshot_hash,
                "status": safe_snapshot.get("status"),
                "component_statuses": {str(row.get("component_id")): str(row.get("status")) for row in list(safe_snapshot.get("components") or []) if isinstance(row, dict)},
                "review_required": True,
            }
            state["snapshots"] = [*list(state.get("snapshots") or []), receipt][-_MAX_SNAPSHOTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_SNAPSHOTS:]
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {**safe_snapshot, "audit_receipt": receipt, "audit_chain_head": audit["event_hash"]}

    def verify(self) -> dict[str, Any]:
        state = self._load()
        previous = ""
        valid = True
        for row in list(state.get("audit") or []):
            basis = {key: row.get(key) for key in ("event_type", "recorded_at", "snapshot_hash", "previous_hash", "actor_role", "tenant_id")}
            if row.get("previous_hash") != previous or row.get("event_hash") != _digest(basis):
                valid = False
                break
            previous = str(row.get("event_hash") or "")
        return {"status": "pass" if valid else "blocked", "snapshot_count": len(state.get("snapshots") or []), "audit_chain_valid": valid, "review_required": True}
