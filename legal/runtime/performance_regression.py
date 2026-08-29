"""Local performance-budget review gates with honest evidence boundaries.

The gate stores only allow-listed numeric observations and their evidence
classification.  It deliberately does not collect prompts, record text,
filesystem paths, package contents, host names, or machine identifiers.  A
passing operator-supplied observation is still review-required; frozen-app,
installed-package, and CI evidence must be recorded by their own qualified
test harnesses before a release may rely on it.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_MAX_STATE_BYTES = 512 * 1024
_MAX_RECEIPTS = 80
_MAX_OBSERVATION_COUNT = 32
_ALLOWED_EVIDENCE_KINDS = {
    "operator_supplied_unverified",
    "synthetic_local_test",
    "ci_measurement",
    "frozen_app_measurement",
    "installed_package_measurement",
}

# These are deliberately conservative starting budgets, not release evidence.
# Package qualification and the performance test harness can provide stronger
# evidence later without changing the matter-scoped review contract.
DEFAULT_PERFORMANCE_BUDGETS: dict[str, dict[str, Any]] = {
    "launch_ms": {"budget": 15_000, "unit": "ms", "label": "Application launch"},
    "matter_open_ms": {"budget": 7_500, "unit": "ms", "label": "Open an active matter"},
    "mixed_import_ms": {"budget": 90_000, "unit": "ms", "label": "Import a mixed fictional record set"},
    "search_ms": {"budget": 4_000, "unit": "ms", "label": "Matter search"},
    "ask_first_feedback_ms": {"budget": 6_000, "unit": "ms", "label": "Ask first useful feedback"},
    "draft_ms": {"budget": 90_000, "unit": "ms", "label": "Create a review-required draft"},
    "packet_ms": {"budget": 90_000, "unit": "ms", "label": "Generate a review-required packet"},
    "peak_memory_mib": {"budget": 2_048, "unit": "MiB", "label": "Peak application memory"},
    "package_size_mib": {"budget": 2_048, "unit": "MiB", "label": "MSIX package size"},
}


class PerformanceGateError(RuntimeError):
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


def performance_budget_catalog() -> dict[str, Any]:
    """Return the public, content-free budget catalog."""

    return {
        "schema_version": "runtime_performance_gate_catalog_v1",
        "metrics": [
            {"metric_id": metric_id, **spec}
            for metric_id, spec in DEFAULT_PERFORMANCE_BUDGETS.items()
        ],
        "required_metric_ids": list(DEFAULT_PERFORMANCE_BUDGETS),
        "review_required": True,
        "release_evidence_claimed": False,
    }


def _bounded_observations(observations: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(observations, Mapping):
        raise PerformanceGateError("performance_observations_required", status_code=422)
    if len(observations) > _MAX_OBSERVATION_COUNT:
        raise PerformanceGateError("performance_observation_count_exceeded", status_code=422)
    unknown = set(observations) - set(DEFAULT_PERFORMANCE_BUDGETS)
    if unknown:
        raise PerformanceGateError("performance_metric_not_allowlisted", status_code=422)
    normalized: dict[str, int] = {}
    for metric_id, raw in observations.items():
        if isinstance(raw, bool):
            raise PerformanceGateError("performance_value_invalid", status_code=422)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise PerformanceGateError("performance_value_invalid", status_code=422) from exc
        if value < 0 or value > 86_400_000:
            raise PerformanceGateError("performance_value_out_of_range", status_code=422)
        normalized[str(metric_id)] = value
    return normalized


def evaluate_performance_gates(
    observations: Mapping[str, Any], *, evidence_kind: str = "operator_supplied_unverified"
) -> dict[str, Any]:
    """Classify allow-listed metrics without misrepresenting missing evidence."""

    values = _bounded_observations(observations)
    kind = str(evidence_kind or "").strip().lower()
    if kind not in _ALLOWED_EVIDENCE_KINDS:
        raise PerformanceGateError("performance_evidence_kind_invalid", status_code=422)
    metrics: list[dict[str, Any]] = []
    blocked_count = 0
    missing_count = 0
    for metric_id, spec in DEFAULT_PERFORMANCE_BUDGETS.items():
        value = values.get(metric_id)
        if value is None:
            status = "not_measured"
            missing_count += 1
        elif value <= int(spec["budget"]):
            status = "within_budget"
        else:
            status = "over_budget"
            blocked_count += 1
        metrics.append(
            {
                "metric_id": metric_id,
                "label": spec["label"],
                "unit": spec["unit"],
                "budget": int(spec["budget"]),
                "observed": value,
                "status": status,
                "source_drill_down": {
                    "evidence_kind": kind if value is not None else "not_measured",
                    "independent_qualified_evidence_required": kind
                    not in {"frozen_app_measurement", "installed_package_measurement"},
                },
                "review_required": True,
            }
        )
    overall_status = "blocked" if blocked_count else "incomplete" if missing_count else "within_budget"
    package_or_frozen = kind in {"frozen_app_measurement", "installed_package_measurement"}
    return {
        "schema_version": "runtime_performance_gate_report_v1",
        "status": overall_status,
        "metric_count": len(metrics),
        "measured_metric_count": len(values),
        "missing_metric_count": missing_count,
        "over_budget_metric_count": blocked_count,
        "metrics": metrics,
        "evidence_kind": kind,
        "operator_supplied": kind == "operator_supplied_unverified",
        "frozen_or_installed_measurement": package_or_frozen,
        "release_eligible": bool(package_or_frozen and not blocked_count and not missing_count),
        "release_evidence_claimed": False,
        "private_record_content_included": False,
        "paths_disclosed": False,
        "network_used": False,
        "review_required": True,
        "boundary": (
            "This is a local performance review receipt. It does not certify a release, "
            "a frozen executable, an installed MSIX, hardware coverage, or real-matter performance."
        ),
    }


class PerformanceGateReceiptStore:
    """Encrypted tenant-bound receipt chain for local performance reviews."""

    schema_version = "runtime_performance_gate_receipts_v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None) -> None:
        self.case_root = Path(case_root).resolve()
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or "local-development-key-change-me"
        )
        self.path = self.case_root / "40_RUNTIME" / "performance-gates" / "receipts.json.enc"
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
            raise PerformanceGateError("performance_gate_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != self.schema_version:
            raise PerformanceGateError("performance_gate_store_unavailable")
        return state

    def record(self, report: Mapping[str, Any], *, actor_role: str, tenant_id: str) -> dict[str, Any]:
        safe = json.loads(_canonical(report).decode("utf-8"))
        if safe.get("private_record_content_included") is not False or safe.get("paths_disclosed") is not False:
            raise PerformanceGateError("performance_gate_report_invalid")
        if safe.get("release_evidence_claimed") is not False:
            raise PerformanceGateError("performance_gate_release_claim_refused")
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            existing_tenant = str(state.get("tenant_id") or "")
            if existing_tenant and existing_tenant != tenant_id:
                raise PerformanceGateError("performance_gate_tenant_mismatch", status_code=403)
            state["tenant_id"] = tenant_id
            prior = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now()
            report_hash = _digest(safe)
            basis = {
                "event_type": "performance_gates_reviewed",
                "recorded_at": recorded_at,
                "report_hash": report_hash,
                "previous_hash": prior,
                "actor_role": str(actor_role)[:40],
                "tenant_id": tenant_id,
            }
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {
                "performance_review_id": f"performance_{audit['event_hash'][:24]}",
                "recorded_at": recorded_at,
                "report_hash": report_hash,
                "status": safe["status"],
                "evidence_kind": safe["evidence_kind"],
                "review_required": True,
            }
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_RECEIPTS:]
            try:
                atomic_write_bytes(self.path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
            except Exception as exc:
                raise PerformanceGateError("performance_gate_store_write_failed") from exc
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
    "DEFAULT_PERFORMANCE_BUDGETS",
    "PerformanceGateError",
    "PerformanceGateReceiptStore",
    "evaluate_performance_gates",
    "performance_budget_catalog",
]
