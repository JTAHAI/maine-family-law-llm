"""Sanitized, local-only replay of allow-listed failure envelopes.

This is a recovery-aid test harness, not an exception replay engine.  It never
stores or accepts raw exception text, tracebacks, paths, prompts, record text,
identities, URLs, tokens, request bodies, or original operation inputs.  Each
replay is a deterministic reconstruction of one reviewed safe-error envelope
and is recorded as an encrypted, tenant-bound, hash-linked matter receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_MAX_STATE_BYTES = 512 * 1024
_MAX_RECEIPTS = 80

FAILURE_REPLAY_CATALOG: dict[str, dict[str, str | int]] = {
    "local_service_unreachable": {
        "safe_code": "local_service_unreachable",
        "http_status": 503,
        "affected_scope": "Only the requested local action was unavailable.",
        "preserved": "The active matter, originals, and review work were preserved.",
        "recovery": "Confirm the local service is running, then retry the original action.",
    },
    "no_active_matter": {
        "safe_code": "no_active_matter",
        "http_status": 409,
        "affected_scope": "The request had no active matter boundary.",
        "preserved": "No matter was opened, changed, or selected by the replay.",
        "recovery": "Open the intended local matter, verify its context, then retry.",
    },
    "storage_reserve_required": {
        "safe_code": "storage_reserve_required",
        "http_status": 409,
        "affected_scope": "A durable local write was refused before the safe reserve was exhausted.",
        "preserved": "Existing matter data and the local free-space reserve were preserved.",
        "recovery": "Review storage capacity or a verified backup; do not force an in-place write.",
    },
    "idempotency_request_in_progress": {
        "safe_code": "idempotency_request_in_progress",
        "http_status": 409,
        "affected_scope": "The same protected local action is already pending.",
        "preserved": "No duplicate mutation was created by the replay.",
        "recovery": "Wait for the original action to settle, then refresh before retrying.",
    },
    "dashboard_session_required": {
        "safe_code": "dashboard_session_required",
        "http_status": 403,
        "affected_scope": "The protected local dashboard session was missing or expired.",
        "preserved": "No matter receipt or private data was exposed.",
        "recovery": "Return to the local workbench, establish a current session, then retry.",
    },
    "authority_not_found": {
        "safe_code": "authority_not_found",
        "http_status": 404,
        "affected_scope": "The requested authority could not be verified from the local admitted source set.",
        "preserved": "No unsupported authority was promoted into a draft or filing result.",
        "recovery": "Review the citation, source freshness, and exact source span before relying on it.",
    },
}


class FailureReplayError(RuntimeError):
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


def failure_replay_catalog() -> dict[str, Any]:
    return {
        "schema_version": "runtime_failure_replay_catalog_v1",
        "scenarios": [
            {
                "scenario_id": scenario_id,
                "safe_code": row["safe_code"],
                "http_status": row["http_status"],
                "affected_scope": row["affected_scope"],
                "recovery": row["recovery"],
                "source_drill_down": {
                    "source_type": "allowlisted_sanitized_failure_contract",
                    "source_id": f"failure_replay:{scenario_id}",
                },
                "review_required": True,
            }
            for scenario_id, row in FAILURE_REPLAY_CATALOG.items()
        ],
        "raw_failures_accepted": False,
        "network_used": False,
        "review_required": True,
    }


def replay_sanitized_failure(scenario_id: object) -> dict[str, Any]:
    normalized = str(scenario_id or "").strip().lower()
    row = FAILURE_REPLAY_CATALOG.get(normalized)
    if row is None:
        raise FailureReplayError("failure_replay_scenario_not_allowlisted", status_code=422)
    return {
        "schema_version": "runtime_failure_replay_report_v1",
        "status": "replayed_sanitized_envelope",
        "scenario_id": normalized,
        "safe_envelope": {
            "code": row["safe_code"],
            "http_status": int(row["http_status"]),
            "affected_scope": row["affected_scope"],
            "preserved": row["preserved"],
            "recovery": row["recovery"],
        },
        "source_drill_down": {
            "source_type": "allowlisted_sanitized_failure_contract",
            "source_id": f"failure_replay:{normalized}",
            "original_failure_artifact_available": False,
        },
        "simulation_only": True,
        "original_operation_reexecuted": False,
        "raw_exception_accepted": False,
        "private_record_content_included": False,
        "paths_disclosed": False,
        "network_used": False,
        "review_required": True,
        "boundary": (
            "This replay reconstructs a reviewed safe-error envelope only. It does not reproduce the original "
            "failure, inspect logs, rerun a private operation, or prove that a production failure is fixed."
        ),
    }


class FailureReplayReceiptStore:
    schema_version = "runtime_failure_replay_receipts_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.path = self.case_root / "40_RUNTIME" / "failure-replay" / "receipts.json.enc"
        self.lock_path = self.path.parent / ".receipts.lock"

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version, "tenant_id": "", "receipts": [], "audit": []}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True)
            )
        except Exception as exc:
            raise FailureReplayError("failure_replay_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version:
            raise FailureReplayError("failure_replay_store_unavailable")
        return state

    def record(self, report: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        safe = json.loads(_canonical(report).decode("utf-8"))
        invalid = (
            safe.get("simulation_only") is not True
            or safe.get("original_operation_reexecuted") is not False
            or safe.get("raw_exception_accepted") is not False
            or safe.get("private_record_content_included") is not False
            or safe.get("paths_disclosed") is not False
        )
        if invalid:
            raise FailureReplayError("failure_replay_report_invalid")
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            existing_tenant = str(state.get("tenant_id") or "")
            if existing_tenant and existing_tenant != tenant_id:
                raise FailureReplayError("failure_replay_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            prior = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            report_hash = _digest(safe)
            basis = {
                "event_type": "sanitized_failure_replayed",
                "recorded_at": recorded_at,
                "report_hash": report_hash,
                "previous_hash": prior,
                "actor_role": str(actor_role)[:40],
                "tenant_id": tenant_id,
            }
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {
                "failure_replay_id": f"failure_replay_{audit['event_hash'][:24]}",
                "recorded_at": recorded_at,
                "report_hash": report_hash,
                "scenario_id": safe["scenario_id"],
                "review_required": True,
            }
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_RECEIPTS:]
            try:
                atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
            except Exception as exc:
                raise FailureReplayError("failure_replay_store_write_failed") from exc
        return {**safe, "audit_receipt": receipt, "audit_chain_head": audit["event_hash"]}

    def verify(self) -> dict[str, Any]:
        state = self._load()
        prior = ""
        valid = True
        for row in list(state.get("audit") or []):
            basis = {
                key: row.get(key)
                for key in ("event_type", "recorded_at", "report_hash", "previous_hash", "actor_role", "tenant_id")
            }
            if row.get("previous_hash") != prior or row.get("event_hash") != _digest(basis):
                valid = False
                break
            prior = str(row.get("event_hash") or "")
        return {
            "status": "pass" if valid else "blocked",
            "receipt_count": len(state.get("receipts") or []),
            "audit_chain_valid": valid,
            "review_required": True,
        }


__all__ = [
    "FAILURE_REPLAY_CATALOG",
    "FailureReplayError",
    "FailureReplayReceiptStore",
    "failure_replay_catalog",
    "replay_sanitized_failure",
]
