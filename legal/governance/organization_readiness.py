"""Honest, separated organization-readiness decision dashboard."""

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

_PASS_EVIDENCE = tuple(f"pass{number}_{name}.json" for number, name in (
    (161, "admin_console_acceptance"), (162, "role_policy_simulator"), (163, "separation_of_duties_acceptance"), (164, "signed_policy_pack_lifecycle_acceptance"), (165, "legal_hold_controls_acceptance"), (166, "retention_policy_engine_acceptance"), (167, "audit_verification_console_acceptance"), (168, "configuration_export_acceptance"), (169, "offline_entitlement_acceptance"),
))
_MAX_STATE_BYTES = 512 * 1024


class OrganizationReadinessError(ValueError):
    pass


def _canonical(value: Any) -> bytes: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
def _digest(value: Any) -> str: return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()
def _now() -> str: return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class OrganizationReadinessDashboard:
    def __init__(self, project_root: str | Path, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.project_root = Path(project_root).resolve(); default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "organization-readiness"
        self.root = Path(root or os.environ.get("MFL_ORGANIZATION_READINESS_ROOT") or default).resolve(); self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path: return self.root / f"{_digest(tenant_id)[:32]}.json.enc"
    def _evidence(self) -> list[dict[str, Any]]:
        rows = []
        for name in _PASS_EVIDENCE:
            path = self.project_root / "dist" / "ga_today" / "evidence" / name
            try: payload = strict_json_load_path(path, max_bytes=2 * 1024 * 1024, require_object=True); status = str(payload.get("status") or "unknown")
            except Exception: status = "unavailable"
            rows.append({"evidence_id": name.removesuffix(".json"), "status": status[:60], "sha256": _digest(path.read_bytes()) if path.is_file() else ""})
        return rows

    def build(self, *, tenant_id: str) -> dict[str, Any]:
        evidence = self._evidence(); code_pass = all(row["status"] == "pass" for row in evidence)
        lanes = [
            {"lane": "engineering", "decision": "ready_for_internal_review" if code_pass else "blocked", "basis": "local_governance_acceptance_evidence", "blockers": [] if code_pass else ["governance_acceptance_evidence_incomplete"]},
            {"lane": "legal", "decision": "blocked", "basis": "external_attorney_review_required", "blockers": ["live_official_authority_and_attorney_review_evidence_required"]},
            {"lane": "security", "decision": "blocked", "basis": "independent_security_assessment_required", "blockers": ["external_security_assessment_and_owner_signoff_required"]},
            {"lane": "privacy", "decision": "review_required", "basis": "local_privacy_controls_and_package_audit_still_require_release_evidence", "blockers": ["final_package_privacy_audit_required"]},
            {"lane": "operations", "decision": "blocked", "basis": "external_operational_readiness_required", "blockers": ["production_runbook_drill_and_operations_signoff_required"]},
            {"lane": "accessibility", "decision": "blocked", "basis": "frozen_app_accessibility_validation_required", "blockers": ["assistive_technology_and_frozen_runtime_evidence_required"]},
            {"lane": "pilot", "decision": "blocked", "basis": "external_controlled_pilot_required", "blockers": ["attorney_sandbox_and_controlled_pilot_evidence_required"]},
            {"lane": "microsoft_store", "decision": "not_evaluated", "basis": "store_submission_qualification_is_separate", "blockers": ["signed_msix_install_offline_wack_and_store_submission_evidence_required"]},
        ]
        return {"schema_version": "organization_readiness_dashboard_v1", "tenant_scope": tenant_id, "overall_decision": "not_ready_for_enterprise_ga", "lanes": lanes, "governance_evidence": evidence, "source_drill_down": {"evidence_count": len(evidence), "evidence_hashes": {row["evidence_id"]: row["sha256"] for row in evidence}, "review_required": True}, "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "Each decision lane is independent. Local engineering evidence does not create attorney review, pilot evidence, Store qualification, or Enterprise GA approval."}

    def receipt(self, dashboard: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
        if dashboard.get("tenant_scope") != tenant_id or dashboard.get("private_record_content_included") is not False: raise OrganizationReadinessError("organization_readiness_scope_invalid")
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            if path.exists():
                try: state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
                except Exception as exc: raise OrganizationReadinessError("organization_readiness_receipt_store_unavailable") from exc
            else: state = {"schema_version": "organization_readiness_receipts_v1", "tenant_id": "", "receipts": [], "audit": []}
            if state.get("schema_version") != "organization_readiness_receipts_v1" or (state.get("tenant_id") and state.get("tenant_id") != tenant_id): raise OrganizationReadinessError("organization_readiness_receipt_store_unavailable")
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or ""); dashboard_hash = _digest(dashboard); basis = {"event_type": "organization_readiness_refreshed", "tenant_id": tenant_id, "dashboard_hash": dashboard_hash, "previous_hash": previous, "recorded_at": _now()}; event = {**basis, "event_hash": _digest(basis)}; receipt = {"receipt_id": f"readiness_{event['event_hash'][:24]}", "dashboard_hash": dashboard_hash, "overall_decision": dashboard["overall_decision"], "review_required": True}
            state["tenant_id"] = tenant_id; state["receipts"] = [*list(state.get("receipts") or []), receipt][-160:]; state["audit"] = [*list(state.get("audit") or []), event][-160:]
            path.parent.mkdir(parents=True, exist_ok=True); atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {"dashboard": dashboard, "receipt": receipt, "network_used": False, "review_required": True}


__all__ = ["OrganizationReadinessDashboard", "OrganizationReadinessError"]
