"""Non-destructive, bounded integrity checks for the local runtime database.

This is intentionally a monitor rather than a repair utility.  It opens the
durable-job SQLite database read-only, limits virtual-machine work and elapsed
time, returns a content-free report, and records an encrypted active-matter
receipt.  A failed check preserves the original database and gives recovery
guidance; it never runs VACUUM, REINDEX, recover, or any write-capable repair
command.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_MAX_STATE_BYTES = 512 * 1024
_MAX_SNAPSHOTS = 80
_MAX_VM_STEPS = 160_000
_MAX_CHECK_SECONDS = 2.5


class DatabaseIntegrityError(RuntimeError):
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


def _safe_database_fingerprint(path: Path) -> str:
    info = path.stat()
    # Metadata gives a useful correlation point without reading a potentially
    # multi-gigabyte private database or disclosing its name/location.
    return _digest({"size": int(info.st_size), "mtime_ns": int(info.st_mtime_ns), "mode": int(info.st_mode)})


def _recovery_guidance(status: str) -> list[str]:
    if status == "pass":
        return ["No repair was attempted. Keep normal encrypted backups and review runtime health before a release decision."]
    return [
        "Stop affected local work and preserve the original runtime database; do not overwrite or delete it.",
        "Use an already-verified encrypted backup or isolated recovery rehearsal to inspect a copy.",
        "Do not run SQLite repair, VACUUM, REINDEX, or recovery commands from this workbench; a human must review recovery evidence.",
    ]


def run_database_integrity_check(database_path: str | Path, *, max_seconds: float = _MAX_CHECK_SECONDS, max_vm_steps: int = _MAX_VM_STEPS) -> dict[str, Any]:
    """Run only bounded, read-only SQLite checks and return no filesystem path."""

    path = Path(database_path).expanduser().resolve(strict=False)
    started = time.monotonic()
    safe_max_seconds = max(0.1, min(float(max_seconds), _MAX_CHECK_SECONDS))
    safe_max_steps = max(1_000, min(int(max_vm_steps), _MAX_VM_STEPS))
    checks: list[dict[str, Any]] = []
    base = {
        "schema_version": "runtime_database_integrity_v1",
        "database_path_disclosed": False,
        "database_content_read": False,
        "destructive_repair_attempted": False,
        "network_used": False,
        "review_required": True,
        "check_limits": {"max_seconds": safe_max_seconds, "max_vm_steps": safe_max_steps},
    }
    try:
        path_stat = path.lstat()
        if path.is_symlink() or not path.is_file():
            raise DatabaseIntegrityError("runtime_database_regular_file_required")
        fingerprint = _safe_database_fingerprint(path)
    except DatabaseIntegrityError:
        raise
    except OSError as exc:
        raise DatabaseIntegrityError("runtime_database_unavailable", status_code=503) from exc

    steps = 0
    deadline = started + safe_max_seconds

    def _progress() -> int:
        nonlocal steps
        steps += 1_000
        return int(steps > safe_max_steps or time.monotonic() > deadline)

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=1.0, isolation_level=None)
        connection.set_progress_handler(_progress, 1_000)
        # Read-only diagnostic pragmas. `quick_check(1)` intentionally returns
        # at most the first integrity problem and is interrupted at our bound.
        quick_rows = [str(row[0])[:240] for row in connection.execute("PRAGMA quick_check(1)").fetchall()]
        quick_ok = quick_rows == ["ok"]
        checks.append({"check_id": "sqlite_quick_check", "status": "pass" if quick_ok else "blocked", "finding_count": 0 if quick_ok else len(quick_rows), "bounded": True})
        if quick_ok:
            foreign_rows = connection.execute("PRAGMA foreign_key_check").fetchmany(8)
            checks.append({"check_id": "foreign_key_check", "status": "pass" if not foreign_rows else "blocked", "finding_count": len(foreign_rows), "bounded": True})
        journal_mode_row = connection.execute("PRAGMA journal_mode").fetchone()
        checks.append({"check_id": "journal_mode_read", "status": "pass", "journal_mode": str(journal_mode_row[0]).lower()[:24] if journal_mode_row else "unknown", "bounded": True})
    except sqlite3.OperationalError as exc:
        message = str(exc).casefold()
        code = "runtime_database_check_timed_out" if "interrupted" in message else "runtime_database_integrity_failed"
        checks.append({"check_id": "sqlite_readonly_check", "status": "blocked", "finding_count": 1, "bounded": True, "error_code": code})
    except sqlite3.DatabaseError:
        checks.append({"check_id": "sqlite_readonly_check", "status": "blocked", "finding_count": 1, "bounded": True, "error_code": "runtime_database_integrity_failed"})
    except OSError:
        checks.append({"check_id": "sqlite_readonly_check", "status": "blocked", "finding_count": 1, "bounded": True, "error_code": "runtime_database_unavailable"})
    finally:
        if connection is not None:
            connection.close()
    elapsed_ms = int(round((time.monotonic() - started) * 1000))
    status = "pass" if checks and all(row["status"] == "pass" for row in checks) else "blocked"
    return {
        **base,
        "status": status,
        "database_fingerprint": fingerprint,
        "checks": checks,
        "elapsed_ms": elapsed_ms,
        "recovery_guidance": _recovery_guidance(status),
    }


class DatabaseIntegrityReceiptStore:
    """Encrypted, tenant-bound audit history for non-destructive checks."""

    schema_version = "runtime_database_integrity_receipts_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        self.encryptor = LocalEnvelopeEncryptor(key)
        self.root = self.case_root / "40_RUNTIME" / "database-integrity"
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
            raise DatabaseIntegrityError("runtime_database_integrity_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version or not isinstance(state.get("receipts"), list) or not isinstance(state.get("audit"), list):
            raise DatabaseIntegrityError("runtime_database_integrity_store_unavailable")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        try:
            atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        except Exception as exc:
            raise DatabaseIntegrityError("runtime_database_integrity_store_write_failed") from exc

    @staticmethod
    def _safe_report(report: dict[str, Any]) -> dict[str, Any]:
        serialized = _canonical(report)
        text = serialized.decode("utf-8", errors="replace")
        if "\\\\" in text or ":/" in text or ":\\" in text:
            raise DatabaseIntegrityError("runtime_database_integrity_private_path_refused")
        safe = json.loads(text)
        if safe.get("database_path_disclosed") is not False or safe.get("destructive_repair_attempted") is not False:
            raise DatabaseIntegrityError("runtime_database_integrity_report_invalid")
        return safe

    def record(self, report: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        safe = self._safe_report(report)
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            prior_tenant = str(state.get("tenant_id") or "")
            if prior_tenant and prior_tenant != tenant_id:
                raise DatabaseIntegrityError("runtime_database_integrity_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            report_hash = _digest(safe)
            basis = {"event_type": "runtime_database_integrity_checked", "recorded_at": recorded_at, "report_hash": report_hash, "previous_hash": previous, "actor_role": str(actor_role or "reviewer")[:40], "tenant_id": str(tenant_id)[:80]}
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {"check_id": f"dbcheck_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "report_hash": report_hash, "status": safe.get("status"), "review_required": True}
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_SNAPSHOTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_SNAPSHOTS:]
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {**safe, "audit_receipt": receipt, "audit_chain_head": audit["event_hash"]}

    def verify(self) -> dict[str, Any]:
        state = self._load()
        previous = ""
        valid = True
        for row in list(state.get("audit") or []):
            basis = {key: row.get(key) for key in ("event_type", "recorded_at", "report_hash", "previous_hash", "actor_role", "tenant_id")}
            if row.get("previous_hash") != previous or row.get("event_hash") != _digest(basis):
                valid = False
                break
            previous = str(row.get("event_hash") or "")
        return {"status": "pass" if valid else "blocked", "receipt_count": len(state.get("receipts") or []), "audit_chain_valid": valid, "review_required": True}


__all__ = ["DatabaseIntegrityError", "DatabaseIntegrityReceiptStore", "run_database_integrity_check"]
