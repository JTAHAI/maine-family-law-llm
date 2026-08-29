"""Non-destructive, hold-aware retention planning with encrypted receipts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from legal.data_boundaries.retention import retention_policy_for
from legal.governance.legal_hold import LegalHoldStore
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
_MAX_STATE_BYTES = 1024 * 1024
_MAX_PLANS = 300
_SUPPORTED_DATA_CLASS = "user_provided_confidential_matter_data"


class RetentionPolicyEngineError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _safe(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text):
        raise RetentionPolicyEngineError(code)
    return text


def _root() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "retention-plans"
    return Path(os.environ.get("MFL_RETENTION_ENGINE_ROOT") or default).resolve()


def _approval_config() -> dict[str, Any]:
    root = Path(os.environ.get("MFL_PROJECT_ROOT") or Path(__file__).resolve().parents[2])
    path = Path(os.environ.get("MFL_RETENTION_APPROVAL_CONFIG") or root / "configs" / "retention_engine_approval.json").resolve()
    try:
        payload = strict_json_load_path(path, max_bytes=256 * 1024, require_object=True)
    except Exception:
        return {"approved_policy_refs": [], "maximum_recovery_window_days": 0, "config_sha256": ""}
    return {"approved_policy_refs": sorted(str(item) for item in payload.get("approved_policy_refs") or [] if _SAFE_ID.fullmatch(str(item))), "maximum_recovery_window_days": max(0, min(3650, int(payload.get("maximum_recovery_window_days") or 0))), "config_sha256": _digest(path.read_bytes())}


class RetentionPolicyEngine:
    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None, legal_holds: LegalHoldStore | None = None) -> None:
        self.root = Path(root or _root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")
        self.legal_holds = legal_holds or LegalHoldStore()

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": "retention_policy_engine_v1", "tenant_id": "", "plans": {}, "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise RetentionPolicyEngineError("retention_policy_engine_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "retention_policy_engine_v1" or not isinstance(state.get("plans"), dict):
            raise RetentionPolicyEngineError("retention_policy_engine_store_unavailable")
        return state

    def _write(self, path: Path, state: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True); atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)

    @staticmethod
    def _audit(state: dict[str, Any], *, tenant: str, plan_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
        basis = {"event_type": event_type, "recorded_at": _now(), "tenant_id": tenant, "plan_id": plan_id, "payload_hash": _digest(payload), "previous_hash": previous}
        event = {**basis, "event_hash": _digest(basis)}; state["audit"] = [*list(state.get("audit") or []), event][-_MAX_PLANS:]
        return event

    @staticmethod
    def _view(plan: dict[str, Any], audit: dict[str, Any] | None = None) -> dict[str, Any]:
        return {"plan_id": plan["plan_id"], "matter_scope": plan["matter_scope"], "artifact_ids": list(plan["artifact_ids"]), "artifact_count": len(plan["artifact_ids"]), "data_class": plan["data_class"], "retention_rule": plan["retention_rule"], "policy_ref": plan["policy_ref"], "status": plan["status"], "hold_blockers": list(plan.get("hold_blockers") or []), "recovery_window_days": plan["recovery_window_days"], "recovery_expires_at": plan.get("recovery_expires_at", ""), "deletion_performed": False, "source_drill_down": {"policy_ref": plan["policy_ref"], "retention_rule": plan["retention_rule"], "plan_hash": _digest(plan), "audit_event_hash": (audit or {}).get("event_hash", ""), "review_required": True}, "review_required": True}

    def preview(self, *, tenant_id: str, matter_scope: str, plan_id: str, artifact_ids: list[Any], policy_ref: str, recovery_window_days: int) -> dict[str, Any]:
        tenant = _safe(tenant_id, "retention_tenant_invalid"); matter = _safe(matter_scope, "retention_matter_scope_invalid"); plan = _safe(plan_id, "retention_plan_id_invalid"); policy = _safe(policy_ref, "retention_policy_ref_invalid")
        artifacts = sorted(set(_safe(item, "retention_artifact_id_invalid") for item in artifact_ids))
        if not artifacts or len(artifacts) > 200: raise RetentionPolicyEngineError("retention_artifact_ids_invalid")
        window = int(recovery_window_days)
        if not 1 <= window <= 3650: raise RetentionPolicyEngineError("retention_recovery_window_invalid")
        retention = retention_policy_for(_SUPPORTED_DATA_CLASS)
        hold_blockers = [artifact for artifact in artifacts if not self.legal_holds.deletion_check(matter_scope=matter, artifact_id=artifact)["allowed"]]
        status = "blocked" if hold_blockers else "preview"
        record = {"plan_id": plan, "matter_scope": matter, "artifact_ids": artifacts, "data_class": _SUPPORTED_DATA_CLASS, "retention_rule": retention.retain, "minimum_action": retention.minimum_action, "policy_ref": policy, "status": status, "hold_blockers": hold_blockers, "recovery_window_days": window, "recovery_expires_at": "", "applied_at": "", "cancelled_at": ""}
        path = self._path(tenant)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path)
            if state.get("tenant_id") and state["tenant_id"] != tenant: raise RetentionPolicyEngineError("retention_tenant_mismatch")
            if plan in state["plans"]: raise RetentionPolicyEngineError("retention_plan_id_exists")
            state["tenant_id"] = tenant; state["plans"][plan] = record
            audit = self._audit(state, tenant=tenant, plan_id=plan, event_type="retention_previewed", payload=record); self._write(path, state)
        return {"schema_version": "retention_policy_plan_v1", "status": status, "plan": self._view(record, audit), "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "Preview only. No deletion, export, or external request was performed."}

    def apply(self, *, tenant_id: str, matter_scope: str, plan_id: str, user_confirmed: bool) -> dict[str, Any]:
        if user_confirmed is not True: raise RetentionPolicyEngineError("retention_explicit_confirmation_required")
        tenant = _safe(tenant_id, "retention_tenant_invalid"); matter = _safe(matter_scope, "retention_matter_scope_invalid"); plan_id = _safe(plan_id, "retention_plan_id_invalid")
        path = self._path(tenant)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); plan = state["plans"].get(plan_id)
            if not isinstance(plan, dict) or plan.get("matter_scope") != matter: raise RetentionPolicyEngineError("retention_plan_not_found")
            current_holds = [artifact for artifact in plan["artifact_ids"] if not self.legal_holds.deletion_check(matter_scope=matter, artifact_id=artifact)["allowed"]]
            approval = _approval_config(); blockers = list(current_holds)
            if plan["policy_ref"] not in set(approval["approved_policy_refs"]): blockers.append("retention_policy_not_organization_approved")
            if plan["recovery_window_days"] > approval["maximum_recovery_window_days"]: blockers.append("retention_recovery_window_exceeds_approved_limit")
            plan["hold_blockers"] = current_holds
            if blockers:
                plan["status"] = "blocked"
            else:
                plan["status"] = "recovery_window_active"; plan["applied_at"] = _now(); plan["recovery_expires_at"] = (datetime.now(UTC) + timedelta(days=int(plan["recovery_window_days"]))).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            audit = self._audit(state, tenant=tenant, plan_id=plan_id, event_type="retention_apply_checked", payload={"plan": plan, "approval_config_sha256": approval["config_sha256"], "blockers": blockers}); self._write(path, state)
        return {"schema_version": "retention_policy_plan_v1", "status": plan["status"], "blockers": sorted(set(blockers)), "plan": self._view(plan, audit), "organization_approval_config_sha256": approval["config_sha256"], "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "Applying a plan starts only a recoverable review window. It never deletes a document; a separate controlled disposition process and human review remain required."}

    def cancel(self, *, tenant_id: str, matter_scope: str, plan_id: str) -> dict[str, Any]:
        tenant = _safe(tenant_id, "retention_tenant_invalid"); matter = _safe(matter_scope, "retention_matter_scope_invalid"); plan_id = _safe(plan_id, "retention_plan_id_invalid")
        path = self._path(tenant)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path); plan = state["plans"].get(plan_id)
            if not isinstance(plan, dict) or plan.get("matter_scope") != matter: raise RetentionPolicyEngineError("retention_plan_not_found")
            plan["status"] = "cancelled"; plan["cancelled_at"] = _now(); plan["recovery_expires_at"] = ""
            audit = self._audit(state, tenant=tenant, plan_id=plan_id, event_type="retention_cancelled", payload=plan); self._write(path, state)
        return {"schema_version": "retention_policy_plan_v1", "status": "cancelled", "plan": self._view(plan, audit), "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "The recoverable retention plan was cancelled. No deletion was performed."}

    def list(self, *, tenant_id: str, matter_scope: str) -> dict[str, Any]:
        tenant = _safe(tenant_id, "retention_tenant_invalid"); matter = _safe(matter_scope, "retention_matter_scope_invalid")
        state = self._load(self._path(tenant)); plans = [self._view(plan) for plan in state["plans"].values() if isinstance(plan, dict) and plan.get("matter_scope") == matter]
        plans.sort(key=lambda row: row["plan_id"])
        return {"schema_version": "retention_policy_plan_list_v1", "status": "review_required", "plans": plans, "active_recovery_count": sum(1 for plan in plans if plan["status"] == "recovery_window_active"), "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True}


__all__ = ["RetentionPolicyEngine", "RetentionPolicyEngineError"]
