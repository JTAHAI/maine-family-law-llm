"""Deterministic synthetic power-loss resilience drill for durable writes.

This is not a hardware power-cut certification.  It fault-injects the atomic
write protocol at named boundaries in a disposable synthetic workspace and
verifies that each private artifact is either the prior complete generation or
the next complete generation, never a partial file.  The drill covers the
same shape of state used by imports, encrypted stores, index-pointer swaps,
backup manifests, and export receipts without reading a user record.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_MAX_STATE_BYTES = 512 * 1024
_MAX_RECEIPTS = 60
_FAULT_POINTS = (
    "after_write",
    "after_file_sync_before_replace",
    "after_replace_before_directory_sync",
)


class SimulatedPowerLoss(RuntimeError):
    """A deterministic test-only interruption at one durable-write boundary."""


class PowerLossResilienceError(RuntimeError):
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


def _payloads() -> dict[str, tuple[bytes, bytes]]:
    encryptor = LocalEnvelopeEncryptor("synthetic-power-loss-drill-key")
    return {
        "import_manifest": (b'{"generation":"previous","record_hash":"a"}', b'{"generation":"next","record_hash":"b"}'),
        "review_state_write": (b'{"generation":"previous","review":"required"}', b'{"generation":"next","review":"required"}'),
        "encrypted_state": (
            _canonical(encryptor.encrypt_json({"generation": "previous", "synthetic_private_value": "not returned"})),
            _canonical(encryptor.encrypt_json({"generation": "next", "synthetic_private_value": "not returned"})),
        ),
        "index_pointer_swap": (b'{"active_generation":"previous"}', b'{"active_generation":"next"}'),
        "backup_manifest": (b'{"backup_generation":"previous","verified":true}', b'{"backup_generation":"next","verified":true}'),
        "export_receipt": (b'{"export_generation":"previous","review_required":true}', b'{"export_generation":"next","review_required":true}'),
    }


def _fault(point: str):
    def inject(current: str) -> None:
        if current == point:
            raise SimulatedPowerLoss(point)

    return inject


def run_power_loss_resilience_drill(*, workspace_parent: str | Path | None = None) -> dict[str, Any]:
    """Run a disposable, deterministic fault drill with no user data.

    The returned result deliberately contains operation labels, hashes, and
    state classifications only.  The temporary workspace is removed before
    return even on a simulated interruption.
    """

    parent: str | None = None
    if workspace_parent is not None:
        candidate = Path(workspace_parent).resolve()
        candidate.mkdir(parents=True, exist_ok=True)
        parent = str(candidate)
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="mfll-power-loss-drill-", dir=parent) as directory:
        root = Path(directory)
        for operation, (previous, next_value) in _payloads().items():
            target = root / f"{operation}.state"
            for fault_point in _FAULT_POINTS:
                atomic_write_bytes(target, previous, mode=0o600)
                interrupted = False
                try:
                    atomic_write_bytes(target, next_value, mode=0o600, fault_injector=_fault(fault_point))
                except SimulatedPowerLoss:
                    interrupted = True
                observed = target.read_bytes() if target.exists() else b""
                state = "previous_generation_preserved" if observed == previous else "next_generation_committed" if observed == next_value else "invalid"
                leftovers = list(root.glob(f".{target.name}.*.tmp"))
                results.append(
                    {
                        "operation": operation,
                        "fault_point": fault_point,
                        "interrupted": interrupted,
                        "outcome": state,
                        "orphan_temporary_file_count": len(leftovers),
                        "previous_generation_hash": _digest(previous),
                        "next_generation_hash": _digest(next_value),
                        "observed_generation_hash": _digest(observed),
                        "status": "pass" if interrupted and state != "invalid" and not leftovers else "blocked",
                    }
                )
    failed = [row for row in results if row["status"] != "pass"]
    return {
        "schema_version": "runtime_power_loss_resilience_v1",
        "status": "pass" if not failed else "blocked",
        "simulation_only": True,
        "physical_power_cut_verified": False,
        "operations": results,
        "operation_count": len(results),
        "failed_operation_count": len(failed),
        "covered_artifact_classes": ["import_manifest", "review_state_write", "encrypted_state", "index_pointer_swap", "backup_manifest", "export_receipt"],
        "network_used": False,
        "private_record_content_used": False,
        "private_paths_included": False,
        "review_required": True,
        "notice": "Synthetic fault injection only. It does not certify a physical power cut, filesystem firmware, hardware, backup medium, or packaged build.",
    }


class PowerLossResilienceReceiptStore:
    """Encrypted active-matter receipts for explicit synthetic resilience drills."""

    schema_version = "runtime_power_loss_resilience_receipts_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        self.encryptor = LocalEnvelopeEncryptor(key)
        self.root = self.case_root / "40_RUNTIME" / "power-loss-resilience"
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
            raise PowerLossResilienceError("power_loss_receipt_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version or not isinstance(state.get("receipts"), list) or not isinstance(state.get("audit"), list):
            raise PowerLossResilienceError("power_loss_receipt_store_unavailable")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        try:
            atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        except Exception as exc:
            raise PowerLossResilienceError("power_loss_receipt_store_write_failed") from exc

    @staticmethod
    def _safe_report(report: dict[str, Any]) -> dict[str, Any]:
        text = _canonical(report).decode("utf-8", errors="replace")
        if "\\\\" in text or ":/" in text or ":\\" in text:
            raise PowerLossResilienceError("power_loss_private_path_refused")
        safe = json.loads(text)
        if safe.get("simulation_only") is not True or safe.get("physical_power_cut_verified") is not False or safe.get("private_record_content_used") is not False:
            raise PowerLossResilienceError("power_loss_report_invalid")
        return safe

    def record(self, report: dict[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        safe = self._safe_report(report)
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            previous_tenant = str(state.get("tenant_id") or "")
            if previous_tenant and previous_tenant != tenant_id:
                raise PowerLossResilienceError("power_loss_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            report_hash = _digest(safe)
            basis = {"event_type": "runtime_power_loss_drill", "recorded_at": recorded_at, "report_hash": report_hash, "previous_hash": previous, "actor_role": str(actor_role or "admin")[:40], "tenant_id": str(tenant_id)[:80]}
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {"drill_id": f"power_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "report_hash": report_hash, "status": safe.get("status"), "simulation_only": True, "review_required": True}
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_RECEIPTS:]
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


__all__ = ["PowerLossResilienceError", "PowerLossResilienceReceiptStore", "SimulatedPowerLoss", "run_power_loss_resilience_drill"]
