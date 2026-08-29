"""Content-free storage forecasting and reviewed cleanup candidates.

The monitor never deletes a file.  It measures the active matter filesystem,
uses the same reserve policy as durable writes, and aggregates only known
runtime temporary-file candidates.  Candidate paths and matter content remain
inside the encrypted receipt and are never returned by the API.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock, required_write_reserve_bytes
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_MAX_STATE_BYTES = 512 * 1024
_MAX_RECEIPTS = 80
_MAX_SCAN_FILES = 3000
_MAX_SCAN_SECONDS = 1.5


class StoragePressureError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _temporary_candidates(case_root: Path) -> dict[str, Any]:
    runtime = case_root / "40_RUNTIME"
    if not runtime.is_dir() or runtime.is_symlink():
        return {"scan_status": "not_present", "scanned_file_count": 0, "candidate_categories": []}
    started = time.monotonic()
    scanned = 0
    temp_count = 0
    temp_bytes = 0
    for directory, dirs, names in os.walk(runtime, followlinks=False):
        dirs[:] = [item for item in dirs if not (Path(directory) / item).is_symlink()]
        for name in names:
            if scanned >= _MAX_SCAN_FILES or time.monotonic() - started > _MAX_SCAN_SECONDS:
                return {"scan_status": "bounded", "scanned_file_count": scanned, "candidate_categories": [{"candidate_kind": "orphan_atomic_temporary_file", "count": temp_count, "estimated_reclaimable_bytes": temp_bytes, "requires_explicit_review": True, "automatic_deletion": False}]}
            scanned += 1
            if not (name.startswith(".") and name.endswith(".tmp")):
                continue
            path = Path(directory) / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                temp_count += 1
                temp_bytes += int(path.stat().st_size)
            except OSError:
                continue
    return {"scan_status": "complete", "scanned_file_count": scanned, "candidate_categories": [{"candidate_kind": "orphan_atomic_temporary_file", "count": temp_count, "estimated_reclaimable_bytes": temp_bytes, "requires_explicit_review": True, "automatic_deletion": False}]}


def forecast_storage_pressure(case_root: str | Path, *, anticipated_write_bytes: int = 512 * 1024 * 1024) -> dict[str, Any]:
    root = Path(case_root).resolve()
    try:
        usage = shutil.disk_usage(root)
    except OSError as exc:
        raise StoragePressureError("storage_capacity_unavailable", status_code=503) from exc
    reserve = required_write_reserve_bytes()
    anticipated = max(0, min(int(anticipated_write_bytes), 4 * 1024 * 1024 * 1024))
    remaining = int(usage.free) - reserve - anticipated
    status = "blocked" if remaining < 0 else "degraded" if int(usage.free) < reserve + 2 * anticipated else "ready"
    candidates = _temporary_candidates(root)
    return {
        "schema_version": "runtime_storage_pressure_v1",
        "status": status,
        "free_bytes": int(usage.free),
        "total_bytes": int(usage.total),
        "minimum_write_reserve_bytes": reserve,
        "anticipated_write_bytes": anticipated,
        "forecast_remaining_after_write_bytes": max(0, remaining),
        "write_gate": {"status": "allow" if status != "blocked" else "block", "enforced_by": "durable_local_write_boundary", "reason": "storage_reserve_required" if status == "blocked" else "reserve_preserved"},
        "cleanup_candidates": candidates,
        "paths_disclosed": False,
        "private_record_content_included": False,
        "automatic_cleanup_performed": False,
        "network_used": False,
        "review_required": True,
    }


class StoragePressureReceiptStore:
    schema_version = "runtime_storage_pressure_receipts_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
        self.path = self.case_root / "40_RUNTIME" / "storage-pressure" / "receipts.json.enc"
        self.lock_path = self.path.parent / ".receipts.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists(): return {"schema_version": self.schema_version, "tenant_id": "", "receipts": [], "audit": []}
        try: state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc: raise StoragePressureError("storage_pressure_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version: raise StoragePressureError("storage_pressure_store_unavailable")
        return state

    def record(self, report: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        text = _canonical(report).decode("utf-8", errors="replace")
        if "\\\\" in text or ":/" in text or ":\\" in text: raise StoragePressureError("storage_pressure_private_path_refused")
        safe = json.loads(text)
        if safe.get("automatic_cleanup_performed") is not False or safe.get("paths_disclosed") is not False: raise StoragePressureError("storage_pressure_report_invalid")
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            if state.get("tenant_id") and state["tenant_id"] != tenant_id: raise StoragePressureError("storage_pressure_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at, report_hash = _now(), _digest(safe)
            basis = {"event_type": "storage_pressure_checked", "recorded_at": recorded_at, "report_hash": report_hash, "previous_hash": previous, "actor_role": str(actor_role)[:40], "tenant_id": tenant_id}
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {"forecast_id": f"storage_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "report_hash": report_hash, "status": safe["status"], "review_required": True}
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_RECEIPTS:]
            atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {**safe, "audit_receipt": receipt, "audit_chain_head": audit["event_hash"]}

    def verify(self) -> dict[str, Any]:
        state, previous, valid = self._load(), "", True
        for row in list(state.get("audit") or []):
            basis = {key: row.get(key) for key in ("event_type", "recorded_at", "report_hash", "previous_hash", "actor_role", "tenant_id")}
            if row.get("previous_hash") != previous or row.get("event_hash") != _digest(basis): valid = False; break
            previous = str(row.get("event_hash") or "")
        return {"status": "pass" if valid else "blocked", "receipt_count": len(state.get("receipts") or []), "audit_chain_valid": valid, "review_required": True}


__all__ = ["StoragePressureError", "StoragePressureReceiptStore", "forecast_storage_pressure"]
