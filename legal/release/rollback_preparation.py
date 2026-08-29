"""Fail-closed rollback preparation for an isolated MSIX release rehearsal.

This module prepares evidence and operator instructions only.  It never
installs, uninstalls, downgrades, restores, or reads a user's matter data.
Rollback is deliberately limited to a disposable isolated environment with
fictional data and a separately verified encrypted-backup recovery result.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.release.msix_upgrade_qualification import (
    MsixUpgradeQualificationError,
    read_identity,
    sha256_file,
)

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _version(value: str) -> tuple[int, int, int, int]:
    parts = value.split(".")
    if len(parts) != 4 or any(not part.isdigit() for part in parts):
        raise ValueError("msix_manifest_version_invalid")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _safe_backup_evidence(path: str | Path | None, *, candidate_sha256: str) -> tuple[dict[str, Any] | None, list[str]]:
    if path is None:
        return None, ["isolated_backup_recovery_evidence_missing"]
    evidence_path = Path(path).resolve()
    try:
        raw = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, ["isolated_backup_recovery_evidence_unreadable"]
    if not isinstance(raw, dict):
        return None, ["isolated_backup_recovery_evidence_invalid"]
    blockers: list[str] = []
    if raw.get("status") != "pass":
        blockers.append("isolated_backup_recovery_not_passed")
    if str(raw.get("candidate_package_sha256") or "") != candidate_sha256:
        blockers.append("backup_evidence_candidate_hash_mismatch")
    if raw.get("isolated_recovery_restore") != "pass":
        blockers.append("isolated_backup_restore_not_verified")
    if raw.get("active_matter_unchanged") is not True:
        blockers.append("active_matter_preservation_not_verified")
    if raw.get("synthetic_data_only") is not True:
        blockers.append("rollback_rehearsal_requires_fictional_data")
    backup_sha256 = str(raw.get("backup_sha256") or "").casefold()
    if not _HASH_RE.fullmatch(backup_sha256):
        blockers.append("backup_evidence_hash_missing")
    safe = {
        "status": str(raw.get("status") or "unknown"),
        "candidate_package_sha256": str(raw.get("candidate_package_sha256") or ""),
        "backup_sha256": backup_sha256,
        "isolated_recovery_restore": str(raw.get("isolated_recovery_restore") or "unknown"),
        "active_matter_unchanged": raw.get("active_matter_unchanged") is True,
        "synthetic_data_only": raw.get("synthetic_data_only") is True,
    }
    return safe, blockers


def build_rollback_preparation(
    *,
    candidate_package: str | Path,
    rollback_package: str | Path,
    backup_evidence: str | Path | None = None,
) -> dict[str, Any]:
    """Build a hash-bound, no-side-effect rollback rehearsal plan."""

    candidate_path = Path(candidate_package).resolve()
    rollback_path = Path(rollback_package).resolve()
    blockers: list[str] = []
    try:
        candidate_identity = read_identity(candidate_path)
        rollback_identity = read_identity(rollback_path)
    except MsixUpgradeQualificationError as exc:
        return {
            "schema_version": "msix_rollback_preparation_v1",
            "generated_at": _now(),
            "status": "blocked",
            "blockers": [str(exc)],
            "review_required": True,
            "store_or_enterprise_claim": "not_made",
        }
    candidate_sha256 = sha256_file(candidate_path)
    rollback_sha256 = sha256_file(rollback_path)
    for field in ("name", "publisher", "architecture", "executable", "language"):
        if getattr(candidate_identity, field) != getattr(rollback_identity, field):
            blockers.append(f"rollback_package_{field}_changed")
    try:
        if _version(candidate_identity.version) <= _version(rollback_identity.version):
            blockers.append("candidate_version_not_greater_than_rollback_version")
    except ValueError as exc:
        blockers.append(str(exc))
    backup, backup_blockers = _safe_backup_evidence(backup_evidence, candidate_sha256=candidate_sha256)
    blockers.extend(backup_blockers)
    rollback_steps = [
        {"id": "confirm_isolated_target", "requirement": "Use a disposable isolated Windows environment; never a user's installed package or live matter."},
        {"id": "verify_encrypted_backup_recovery", "requirement": "Verify the linked fictional backup in an isolated recovery copy and retain its hash-bound receipt."},
        {"id": "capture_current_fictional_state_hashes", "requirement": "Record only aggregate fictional matter, draft, and revision-history hashes before the rehearsal."},
        {"id": "install_rollback_package_in_isolation", "requirement": "Install only the hash-bound fallback package in the isolated environment; do not automate a user-device downgrade."},
        {"id": "verify_local_api_and_production_ui", "requirement": "Launch the fallback, verify the local API and shipped production UI with fictional data, and record safe results."},
        {"id": "verify_fictional_state_preservation", "requirement": "Compare the recorded fictional-state hashes and preserve any recovery copy; never overwrite the source state."},
        {"id": "restart_and_record_operator_decision", "requirement": "Restart the isolated app, record blockers and an authorized human decision. A failed check requires forward recovery, not silent continuation."},
    ]
    return {
        "schema_version": "msix_rollback_preparation_v1",
        "generated_at": _now(),
        "status": "prepared_for_isolated_rollback_rehearsal" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "candidate": {"file_name": candidate_path.name, "sha256": candidate_sha256, "identity": candidate_identity.as_dict()},
        "rollback": {"file_name": rollback_path.name, "sha256": rollback_sha256, "identity": rollback_identity.as_dict()},
        "backup_recovery_evidence": backup,
        "required_isolated_steps": rollback_steps,
        "forward_recovery_if_blocked": [
            "Preserve the isolated evidence and backup receipt without changing the active matter.",
            "Do not attempt package or data rollback on a user device.",
            "Correct the release defect, build a new signed candidate, and repeat isolated qualification.",
        ],
        "safety_boundary": {
            "modifies_user_store_package": False,
            "modifies_active_matter": False,
            "requires_explicit_isolated_runner": True,
            "synthetic_data_only": True,
            "network_required": False,
            "automatic_rollback_allowed": False,
            "review_required": True,
        },
        "store_or_enterprise_claim": "not_made",
    }


def validate_rollback_rehearsal(plan: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Validate an external isolated-runner result against this exact plan."""

    required = {str(step["id"]) for step in plan.get("required_isolated_steps", []) if isinstance(step, dict)}
    completed = {
        str(row.get("id"))
        for row in (result.get("steps") if isinstance(result, dict) and isinstance(result.get("steps"), list) else [])
        if isinstance(row, dict) and row.get("status") == "pass"
    }
    blockers = list(plan.get("blockers") or [])
    candidate = plan.get("candidate") if isinstance(plan.get("candidate"), dict) else {}
    rollback = plan.get("rollback") if isinstance(plan.get("rollback"), dict) else {}
    if str(result.get("candidate_sha256") or "") != str(candidate.get("sha256") or ""):
        blockers.append("runner_candidate_package_hash_mismatch")
    if str(result.get("rollback_sha256") or "") != str(rollback.get("sha256") or ""):
        blockers.append("runner_rollback_package_hash_mismatch")
    missing = sorted(required - completed)
    if missing:
        blockers.append("runner_required_rollback_steps_incomplete")
    if result.get("synthetic_data_only") is not True:
        blockers.append("runner_fictional_data_not_confirmed")
    if result.get("active_matter_unchanged") is not True:
        blockers.append("runner_active_matter_preservation_not_confirmed")
    return {
        "status": "pass" if not blockers else "blocked",
        "blockers": sorted(set(blockers)),
        "completed_steps": sorted(completed),
        "missing_steps": missing,
        "review_required": True,
        "store_or_enterprise_claim": "not_made",
    }


__all__ = ["build_rollback_preparation", "validate_rollback_rehearsal"]
