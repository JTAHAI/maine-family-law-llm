"""Privacy-safe, tenant-scoped administration-console summary and receipts."""

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

_MAX_RECEIPTS = 80
_MAX_STATE_BYTES = 512 * 1024
_POLICY_FILES = (
    "maine_enterprise_security_controls.json",
    "maine_governance_compliance_packet.json",
    "maine_export_policy.json",
    "reviewed_filing_packet_policy.json",
)
_RELEASE_EVIDENCE = (
    "pass156_wack_qualification.json",
    "pass157_store_asset_validation.json",
    "pass158_package_size_budget.json",
    "pass159_rollback_preparation.json",
    "pass160_signed_update_metadata.json",
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _default_root() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "admin-console"
    return Path(os.environ.get("MFL_ADMIN_CONSOLE_ROOT") or base).resolve()


def _safe_json_status(path: Path) -> dict[str, Any]:
    try:
        raw = strict_json_load_path(path, max_bytes=2 * 1024 * 1024, require_object=True)
    except Exception:
        return {"status": "unavailable", "sha256": ""}
    return {"status": str(raw.get("status") or "unknown")[:60], "sha256": _digest(path.read_bytes())}


def _authority_status() -> dict[str, Any]:
    try:
        from app.services import AuthorityLibraryService

        raw = AuthorityLibraryService().status()
        if not isinstance(raw, dict):
            raise ValueError("authority_status_invalid")
        return {
            "status": str(raw.get("status") or "unknown")[:60],
            "active_build_id": str(raw.get("active_build_id") or "")[:120],
            "source_count": int(raw.get("source_count") or 0),
            "review_required": True,
            "source_drill_down": {"route": "/api/authority/status", "kind": "official_authority_metadata"},
        }
    except Exception:
        return {
            "status": "unavailable",
            "active_build_id": "",
            "source_count": 0,
            "review_required": True,
            "source_drill_down": {"route": "/api/authority/status", "kind": "official_authority_metadata"},
        }


def build_admin_console_summary(*, project_root: str | Path, tenant_id: str) -> dict[str, Any]:
    """Return only safe administration posture; never enumerate people or matters."""

    root = Path(project_root).resolve()
    policies: list[dict[str, Any]] = []
    for name in _POLICY_FILES:
        path = root / "configs" / name
        policies.append({"policy_id": name.removesuffix(".json"), "present": path.is_file(), "sha256": _digest(path.read_bytes()) if path.is_file() else ""})
    evidence: list[dict[str, Any]] = []
    for name in _RELEASE_EVIDENCE:
        row = _safe_json_status(root / "dist" / "ga_today" / "evidence" / name)
        evidence.append({"artifact_id": name.removesuffix(".json"), **row})
    authority = _authority_status()
    blockers = [
        "account_directory_external_identity_provider_required",
        "human_review_required_for_exports",
    ]
    if authority["status"] not in {"ready", "pass", "ok", "active"}:
        blockers.append("authority_status_requires_review")
    blockers.extend(f"release_evidence_requires_review:{row['artifact_id']}" for row in evidence if row["status"] not in {"pass", "ready", "ok"})
    return {
        "schema_version": "enterprise_admin_console_v1",
        "status": "review_required",
        "tenant_scope": {"tenant_id": tenant_id, "cross_tenant_enumeration": False, "matter_content_included": False},
        "users_and_roles": {
            "directory_mode": "external_identity_provider_required",
            "account_management_available": False,
            "request_role": "admin",
            "supported_roles": ["attorney", "reviewer", "admin", "paralegal"],
            "notice": "This local workbench does not enumerate or provision people. Identity lifecycle remains an external enterprise control.",
        },
        "policy": {"policy_count": sum(1 for row in policies if row["present"]), "policies": policies, "source_drill_down": {"kind": "policy_hash", "review_required": True}},
        "authority": authority,
        "release_evidence": {"artifact_count": len(evidence), "artifacts": evidence, "source_drill_down": {"kind": "release_evidence_hash", "review_required": True}},
        "blocked_exports": {"status": "blocked", "blockers": sorted(set(blockers)), "filing_ready": False, "review_required": True},
        "private_record_content_included": False,
        "paths_disclosed": False,
        "network_used": False,
        "review_required": True,
    }


class AdminConsoleReceiptStore:
    """Encrypted, tenant-bound audit receipt chain for explicit console refreshes."""

    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.root = Path(root or _default_root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": "enterprise_admin_console_receipts_v1", "tenant_id": "", "receipts": [], "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise ValueError("admin_console_receipt_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "enterprise_admin_console_receipts_v1":
            raise ValueError("admin_console_receipt_store_unavailable")
        return state

    def record(self, summary: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
        if summary.get("private_record_content_included") is not False or summary.get("paths_disclosed") is not False:
            raise ValueError("admin_console_summary_boundary_invalid")
        path = self._path(tenant_id); lock = path.with_suffix(path.suffix + ".lock")
        with exclusive_file_lock(lock):
            state = self._load(path)
            existing = str(state.get("tenant_id") or "")
            if existing and existing != tenant_id:
                raise ValueError("admin_console_tenant_mismatch")
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now(); summary_hash = _digest(summary)
            basis = {"event_type": "admin_console_refreshed", "recorded_at": recorded_at, "summary_hash": summary_hash, "previous_hash": previous, "tenant_id": tenant_id}
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {"receipt_id": f"admin_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "summary_hash": summary_hash, "review_required": True}
            state["receipts"] = [*list(state.get("receipts") or []), receipt][-_MAX_RECEIPTS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_RECEIPTS:]
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {"receipt": receipt, "audit_chain_head": audit["event_hash"], "receipt_count": len(state["receipts"]), "review_required": True}


__all__ = ["AdminConsoleReceiptStore", "build_admin_console_summary"]
