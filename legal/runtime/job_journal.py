"""Content-free active-matter journal for durable local runtime jobs.

The durable kernel remains the source of truth for job execution.  This module
turns its state into a reviewable journal without exposing job inputs, results,
errors, record paths, or prompt text.  Every explicit journal refresh leaves an
encrypted, hash-linked active-matter receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_MAX_STATE_BYTES = 512 * 1024
_MAX_RECEIPTS = 80
_SAFE_STAGE_RE = re.compile(r"[a-z0-9][a-z0-9_:-]{0,99}")
_SAFE_JOB_ID_RE = re.compile(r"job-[a-f0-9]{16,64}")
_TERMINAL = frozenset({"completed", "failed", "cancelled"})


class JobJournalError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=lambda _value: "<unavailable>").encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _safe_stage(value: Any, *, fallback: str) -> str:
    candidate = str(value or "").strip().casefold()
    return candidate if _SAFE_STAGE_RE.fullmatch(candidate) else fallback


def _safe_job_id(value: Any) -> str:
    candidate = str(value or "").strip().casefold()
    return candidate if _SAFE_JOB_ID_RE.fullmatch(candidate) else f"job-{_hash(candidate)[:24]}"


def _safe_int(value: Any, *, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return minimum


def _safe_progress(value: Any) -> float:
    try:
        return round(max(0.0, min(1.0, float(value))), 4)
    except (TypeError, ValueError):
        return 0.0


def _public_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": _safe_int(row.get("event_id")),
        "stage": _safe_stage(row.get("event_type"), fallback="unclassified_stage"),
        "recorded_at": str(row.get("created_at") or "")[:40],
    }


def _public_job(kernel: Any, row: dict[str, Any]) -> dict[str, Any]:
    job_id = _safe_job_id(row.get("job_id"))
    try:
        events = [_public_event(dict(event)) for event in list(kernel.events(str(row.get("job_id") or "")))[-60:]]
    except Exception:
        events = []
    status = _safe_stage(row.get("status"), fallback="unknown")
    stage = events[-1]["stage"] if events else status
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    error = row.get("error") if isinstance(row.get("error"), dict) else {}
    return {
        "job_id": job_id,
        "job_type": _safe_stage(row.get("job_type"), fallback="unclassified_job"),
        "status": status,
        "stage": stage,
        "progress": _safe_progress(row.get("progress")),
        "attempt": _safe_int(row.get("attempt")),
        "created_at": str(row.get("created_at") or "")[:40],
        "updated_at": str(row.get("updated_at") or "")[:40],
        "completed_at": str(row.get("completed_at") or "")[:40] or None,
        "input_hash": _hash(payload),
        "result_receipt_hash": _hash(result) if result else None,
        "error_receipt_hash": _hash(error) if error else None,
        "cancellation_requested": status == "cancel_requested",
        "terminal": status in _TERMINAL,
        "events": events,
        "review_required": True,
    }


def collect_job_journal(*, kernel: Any, matter_id: str) -> dict[str, Any]:
    """Return bounded public job-state metadata for exactly one matter scope."""

    try:
        rows = list(kernel.list_jobs(matter_id=matter_id, limit=500))
    except Exception as exc:
        raise JobJournalError("runtime_job_journal_unavailable") from exc
    jobs = [_public_job(kernel, dict(row)) for row in rows]
    active = [row for row in jobs if not row["terminal"]]
    cancelled = [row for row in jobs if row["status"] == "cancelled"]
    retrying = [row for row in jobs if int(row["attempt"]) > 1]
    return {
        "schema_version": "runtime_job_journal_v1",
        "status": "ready",
        "matter_scope": "active_matter_only",
        "jobs": jobs,
        "counts": {
            "total": len(jobs),
            "active": len(active),
            "cancelled": len(cancelled),
            "retried": len(retrying),
            "terminal": len(jobs) - len(active),
        },
        "job_inputs_exposed": False,
        "job_results_exposed": False,
        "private_paths_included": False,
        "network_used": False,
        "review_required": True,
    }


class JobJournalReceiptStore:
    """Encrypted tenant-bound journal-view receipts for an active matter."""

    schema_version = "runtime_job_journal_receipts_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        self.encryptor = LocalEnvelopeEncryptor(key)
        self.root = self.case_root / "40_RUNTIME" / "job-journal"
        self.path = self.root / "receipts.json.enc"
        self.lock_path = self.root / ".receipts.lock"

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "tenant_id": "", "revision": 0, "receipts": [], "audit": []}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise JobJournalError("runtime_job_journal_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version:
            raise JobJournalError("runtime_job_journal_store_unavailable")
        if not isinstance(state.get("receipts"), list) or not isinstance(state.get("audit"), list):
            raise JobJournalError("runtime_job_journal_store_unavailable")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        try:
            atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        except Exception as exc:
            raise JobJournalError("runtime_job_journal_store_write_failed") from exc

    def record(self, journal: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        text = _canonical(journal).decode("utf-8", errors="replace")
        if "\\\\" in text or ":/" in text or ":\\" in text:
            raise JobJournalError("runtime_job_journal_private_path_refused")
        public_journal = json.loads(text)
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            existing_tenant = str(state.get("tenant_id") or "")
            if existing_tenant and existing_tenant != tenant_id:
                raise JobJournalError("runtime_job_journal_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            journal_hash = _hash(public_journal)
            basis = {
                "event_type": "runtime_job_journal_viewed",
                "recorded_at": recorded_at,
                "journal_hash": journal_hash,
                "previous_hash": previous,
                "actor_role": str(actor_role or "reviewer")[:40],
                "tenant_id": tenant_id,
            }
            audit = {**basis, "event_hash": _hash(basis)}
            receipt = {
                "journal_id": f"journal_{audit['event_hash'][:24]}",
                "recorded_at": recorded_at,
                "journal_hash": journal_hash,
                "job_count": int(dict(public_journal.get("counts") or {}).get("total") or 0),
                "review_required": True,
            }
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_RECEIPTS:]
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {**public_journal, "audit_receipt": receipt, "audit_chain_head": audit["event_hash"]}

    def verify(self) -> dict[str, Any]:
        state = self._load()
        previous = ""
        valid = True
        for row in list(state.get("audit") or []):
            basis = {key: row.get(key) for key in ("event_type", "recorded_at", "journal_hash", "previous_hash", "actor_role", "tenant_id")}
            if row.get("previous_hash") != previous or row.get("event_hash") != _hash(basis):
                valid = False
                break
            previous = str(row.get("event_hash") or "")
        return {"status": "pass" if valid else "blocked", "receipt_count": len(state.get("receipts") or []), "audit_chain_valid": valid, "review_required": True}
