"""Encrypted, tenant-bound simulations of fictional role-policy outcomes."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.authz import ROLE_PERMISSIONS, RBACPolicy, UserContext
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
_MAX_STATE_BYTES = 512 * 1024
_MAX_ROWS = 80
_KNOWN_PERMISSIONS = tuple(sorted({item for permissions in ROLE_PERMISSIONS.values() for item in permissions}))


class RolePolicySimulationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "role-policy-simulations"
    return Path(os.environ.get("MFL_ROLE_POLICY_SIMULATION_ROOT") or base).resolve()


def simulate_role_policy(*, simulation_id: str, fictional_roles: list[Any], permissions: list[Any], tenant_id: str) -> dict[str, Any]:
    safe_id = str(simulation_id or "").strip()
    if not _SAFE_ID.fullmatch(safe_id):
        raise RolePolicySimulationError("role_policy_simulation_id_invalid")
    roles = [str(item or "").strip().casefold() for item in fictional_roles]
    if not roles or len(roles) > 8 or any(role not in ROLE_PERMISSIONS for role in roles):
        raise RolePolicySimulationError("role_policy_simulation_roles_invalid")
    requested = [str(item or "").strip() for item in permissions] or list(_KNOWN_PERMISSIONS)
    if len(requested) > len(_KNOWN_PERMISSIONS) or any(permission not in _KNOWN_PERMISSIONS for permission in requested):
        raise RolePolicySimulationError("role_policy_simulation_permissions_invalid")
    unique_roles = tuple(sorted(set(roles)))
    policy = RBACPolicy()
    fictional_user = UserContext(user_id=f"simulation:{safe_id}", tenant_id=tenant_id, roles=unique_roles, matter_ids=())
    results = []
    for permission in sorted(set(requested)):
        granting = sorted(role for role in unique_roles if permission in ROLE_PERMISSIONS[role])
        allowed = policy.can(fictional_user, permission)
        results.append({"permission": permission, "decision": "allow" if allowed else "deny", "basis_roles": granting, "denial_reason": "" if allowed else "permission_not_granted_by_selected_roles", "source_drill_down": {"policy": "legal.security.authz.ROLE_PERMISSIONS", "selected_roles": list(unique_roles)}})
    denied = [row["permission"] for row in results if row["decision"] == "deny"]
    return {"schema_version": "role_policy_simulation_v1", "status": "review_required", "simulation_id": safe_id, "tenant_scope": tenant_id, "fictional_user_only": True, "selected_roles": list(unique_roles), "permission_results": results, "allowed_count": len(results) - len(denied), "denied_count": len(denied), "denied_permissions": denied, "policy_change_applied": False, "private_record_content_included": False, "paths_disclosed": False, "network_used": False, "review_required": True, "notice": "This is a fictional policy preview. It does not create a user, change a role, alter a policy pack, or authorize an export."}


class RolePolicySimulationStore:
    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.root = Path(root or _root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": "role_policy_simulation_store_v1", "tenant_id": "", "simulations": [], "audit": []}
        try:
            payload = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise RolePolicySimulationError("role_policy_simulation_store_unavailable") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != "role_policy_simulation_store_v1":
            raise RolePolicySimulationError("role_policy_simulation_store_unavailable")
        return payload

    def record(self, simulation: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
        if simulation.get("tenant_scope") != tenant_id or simulation.get("fictional_user_only") is not True or simulation.get("policy_change_applied") is not False:
            raise RolePolicySimulationError("role_policy_simulation_boundary_invalid")
        path = self._path(tenant_id); lock = path.with_suffix(path.suffix + ".lock")
        with exclusive_file_lock(lock):
            state = self._load(path)
            if state.get("tenant_id") and state["tenant_id"] != tenant_id:
                raise RolePolicySimulationError("role_policy_simulation_tenant_mismatch")
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now(); simulation_hash = _digest(simulation)
            basis = {"event_type": "role_policy_simulated", "recorded_at": recorded_at, "simulation_hash": simulation_hash, "previous_hash": previous, "tenant_id": tenant_id}
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {"simulation_receipt_id": f"role_sim_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "simulation_hash": simulation_hash, "review_required": True}
            state["simulations"] = [*list(state.get("simulations") or []), {"simulation_id": simulation["simulation_id"], "simulation_hash": simulation_hash, "receipt": receipt}][-_MAX_ROWS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_ROWS:]
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {"receipt": receipt, "audit_chain_head": audit["event_hash"], "review_required": True}


__all__ = ["RolePolicySimulationError", "RolePolicySimulationStore", "simulate_role_policy"]
