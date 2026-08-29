"""Durable local job and event kernel.

The kernel deliberately uses only the Python standard library and an external
runtime-data location.  It provides the restart, cancellation, idempotency and
audit primitives used by long-running document, retrieval and model work.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}
_default_kernel: DurableJobKernel | None = None
_default_kernel_lock = threading.Lock()


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def default_kernel_path() -> Path:
    configured = str(os.environ.get("MFL_RUNTIME_STATE_ROOT") or "").strip()
    if configured:
        root = Path(configured).expanduser().resolve(strict=False)
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "runtime"
    else:
        root = Path.home() / ".local" / "state" / "maine-family-law-llm"
    return root / "runtime-kernel.sqlite3"


class DurableJobKernel:
    schema_version = 1

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or default_kernel_path()).expanduser().resolve(strict=False)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                if connection.in_transaction:
                    connection.execute("COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise
            finally:
                connection.close()

    def _initialize(self) -> None:
        with self._transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    matter_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    error_json TEXT,
                    idempotency_key TEXT,
                    attempt INTEGER NOT NULL DEFAULT 0,
                    progress REAL NOT NULL DEFAULT 0,
                    lease_owner TEXT,
                    lease_expires_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    version INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(job_type, matter_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS jobs_status_idx ON jobs(status, updated_at);
                CREATE INDEX IF NOT EXISTS jobs_matter_idx ON jobs(matter_id, created_at);
                CREATE TABLE IF NOT EXISTS job_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS job_events_job_idx ON job_events(job_id, event_id);
                """
            )
            connection.execute(
                "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(self.schema_version),),
            )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _decode(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        return json.loads(value)

    def _event(
        self,
        connection: sqlite3.Connection,
        job_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO job_events(job_id, event_type, payload_json, created_at) VALUES(?,?,?,?)",
            (job_id, event_type, self._json(payload or {}), _now()),
        )

    def create_job(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        matter_id: str = "local",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        normalized_type = job_type.strip().casefold().replace(" ", "_")
        if not normalized_type or len(normalized_type) > 100:
            raise ValueError("job_type must contain 1-100 normalized characters")
        normalized_matter = matter_id.strip() or "local"
        if len(normalized_matter) > 200:
            raise ValueError("matter_id is too long")
        key = (idempotency_key or "").strip() or None
        with self._transaction() as connection:
            if key:
                existing = connection.execute(
                    "SELECT * FROM jobs WHERE job_type=? AND matter_id=? AND idempotency_key=?",
                    (normalized_type, normalized_matter, key),
                ).fetchone()
                if existing is not None:
                    return self._row(existing)
            job_id = f"job-{uuid.uuid4().hex}"
            now = _now()
            connection.execute(
                """INSERT INTO jobs(
                    job_id, job_type, matter_id, status, payload_json, idempotency_key,
                    created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    job_id,
                    normalized_type,
                    normalized_matter,
                    "queued",
                    self._json(payload),
                    key,
                    now,
                    now,
                ),
            )
            self._event(connection, job_id, "job_created", {"status": "queued"})
            return self._row(
                connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            )

    def claim_job(self, job_id: str, worker_id: str, *, lease_seconds: int = 120) -> dict[str, Any]:
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["status"] != "queued":
                raise RuntimeError(f"job_not_claimable:{row['status']}")
            now = datetime.now(UTC)
            lease = now + timedelta(seconds=max(15, min(3600, lease_seconds)))
            connection.execute(
                """UPDATE jobs SET status='running', attempt=attempt+1, lease_owner=?,
                    lease_expires_at=?, updated_at=?, version=version+1 WHERE job_id=?""",
                (worker_id, lease.isoformat().replace("+00:00", "Z"), _now(), job_id),
            )
            self._event(connection, job_id, "job_claimed", {"worker_id": worker_id})
            return self._row(
                connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            )

    def heartbeat(self, job_id: str, worker_id: str, progress: float) -> dict[str, Any]:
        bounded = max(0.0, min(1.0, float(progress)))
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if (
                row["status"] not in {"running", "cancel_requested"}
                or row["lease_owner"] != worker_id
            ):
                raise RuntimeError("job_lease_not_owned")
            lease = (datetime.now(UTC) + timedelta(seconds=120)).isoformat().replace("+00:00", "Z")
            connection.execute(
                "UPDATE jobs SET progress=?, lease_expires_at=?, updated_at=?, "
                "version=version+1 WHERE job_id=?",
                (bounded, lease, _now(), job_id),
            )
            return self._row(
                connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            )

    def finish_job(
        self,
        job_id: str,
        worker_id: str,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        status = "failed" if error else "completed"
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["lease_owner"] != worker_id or row["status"] not in {
                "running",
                "cancel_requested",
            }:
                raise RuntimeError("job_lease_not_owned")
            if row["status"] == "cancel_requested":
                status = "cancelled"
            connection.execute(
                """UPDATE jobs SET status=?, result_json=?, error_json=?, progress=?,
                    lease_owner=NULL, lease_expires_at=NULL, completed_at=?, updated_at=?,
                    version=version+1 WHERE job_id=?""",
                (
                    status,
                    self._json(result or {}) if result is not None else None,
                    self._json(error or {}) if error is not None else None,
                    1.0 if status == "completed" else float(row["progress"]),
                    _now(),
                    _now(),
                    job_id,
                ),
            )
            self._event(connection, job_id, f"job_{status}", result or error or {})
            return self._row(
                connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            )

    def request_cancel(self, job_id: str) -> dict[str, Any]:
        with self._transaction() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            if row["status"] == "queued":
                status = "cancelled"
                completed_at = _now()
            elif row["status"] == "running":
                status = "cancel_requested"
                completed_at = None
            else:
                return self._row(row)
            connection.execute(
                "UPDATE jobs SET status=?, completed_at=?, updated_at=?, "
                "version=version+1 WHERE job_id=?",
                (status, completed_at, _now(), job_id),
            )
            self._event(connection, job_id, "cancel_requested", {"resulting_status": status})
            return self._row(
                connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            )

    def recover_expired(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        point = (now or datetime.now(UTC)).isoformat().replace("+00:00", "Z")
        recovered: list[dict[str, Any]] = []
        with self._transaction() as connection:
            rows = connection.execute(
                """SELECT * FROM jobs WHERE status IN ('running','cancel_requested')
                    AND lease_expires_at IS NOT NULL AND lease_expires_at < ?""",
                (point,),
            ).fetchall()
            for row in rows:
                status = "cancelled" if row["status"] == "cancel_requested" else "queued"
                connection.execute(
                    """UPDATE jobs SET status=?, lease_owner=NULL, lease_expires_at=NULL,
                        updated_at=?, completed_at=?, version=version+1 WHERE job_id=?""",
                    (status, _now(), _now() if status == "cancelled" else None, row["job_id"]),
                )
                self._event(connection, row["job_id"], "job_recovered", {"status": status})
                recovered.append(
                    self._row(
                        connection.execute(
                            "SELECT * FROM jobs WHERE job_id=?", (row["job_id"],)
                        ).fetchone()
                    )
                )
        return recovered

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
            return self._row(row) if row is not None else None

    def list_jobs(self, *, matter_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        bounded = max(1, min(500, int(limit)))
        with self._connect() as connection:
            if matter_id:
                rows = connection.execute(
                    "SELECT * FROM jobs WHERE matter_id=? ORDER BY created_at DESC LIMIT ?",
                    (matter_id, bounded),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (bounded,)
                ).fetchall()
            return [self._row(row) for row in rows]

    def events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM job_events WHERE job_id=? ORDER BY event_id", (job_id,)
            ).fetchall()
            return [
                {
                    "event_id": int(row["event_id"]),
                    "job_id": row["job_id"],
                    "event_type": row["event_type"],
                    "payload": self._decode(row["payload_json"], {}),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def health(self) -> dict[str, Any]:
        with self._connect() as connection:
            counts = {
                row["status"]: int(row["count"])
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM jobs GROUP BY status"
                ).fetchall()
            }
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        return {
            "status": "ok" if integrity == "ok" else "degraded",
            "schema_version": self.schema_version,
            # A health endpoint must not disclose a local path. The dedicated
            # integrity monitor supplies a bounded, receipt-backed diagnostic
            # view without exposing this database's location or contents.
            "database_path_disclosed": False,
            "database_fingerprint": hashlib.sha256(
                str(self.path).encode("utf-8")
            ).hexdigest()[:24],
            "integrity": integrity,
            "job_counts": counts,
        }

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "matter_id": row["matter_id"],
            "status": row["status"],
            "payload": self._decode(row["payload_json"], {}),
            "result": self._decode(row["result_json"], None),
            "error": self._decode(row["error_json"], None),
            "idempotency_key": row["idempotency_key"],
            "attempt": int(row["attempt"]),
            "progress": float(row["progress"]),
            "lease_owner": row["lease_owner"],
            "lease_expires_at": row["lease_expires_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
            "version": int(row["version"]),
        }


def get_runtime_kernel() -> DurableJobKernel:
    """Return the process singleton and recover work abandoned by a dead process."""

    global _default_kernel
    expected_path = default_kernel_path()
    with _default_kernel_lock:
        if _default_kernel is None or _default_kernel.path != expected_path:
            _default_kernel = DurableJobKernel(expected_path)
            _default_kernel.recover_expired()
        return _default_kernel


__all__ = [
    "ACTIVE_STATUSES",
    "DurableJobKernel",
    "TERMINAL_STATUSES",
    "default_kernel_path",
    "get_runtime_kernel",
]
