"""Fail-closed, tenant-scoped separation-of-duties review receipts.

This module evaluates an approval *proposal* using opaque fictional actor
references.  It cannot activate authority, sign a release, or replace the
independent human approvals it makes visible for review.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
_REQUIRED = (
    ("authority_activation", "authority_activator"),
    ("security_approval", "security_approver"),
    ("legal_sign_off", "legal_signer"),
    ("release_approval", "release_approver"),
)
_MAX_STATE_BYTES = 512 * 1024
_MAX_ROWS = 80


class SeparationOfDutiesError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _root() -> Path:
    default = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "MaineFamilyLawLLM" / "separation-of-duties"
    return Path(os.environ.get("MFL_SEPARATION_OF_DUTIES_ROOT") or default).resolve()


def _safe(value: Any, code: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text):
        raise SeparationOfDutiesError(code)
    return text


def evaluate_separation_of_duties(*, review_id: str, approvals: list[Any], tenant_id: str) -> dict[str, Any]:
    """Return a review-required, fail-closed independence evaluation.

    `actor_ref` and `artifact_ref` must be opaque safe identifiers.  A single
    actor may never cover more than one required responsibility.
    """

    review = _safe(review_id, "separation_of_duties_review_id_invalid")
    if not isinstance(approvals, list) or len(approvals) != len(_REQUIRED):
        raise SeparationOfDutiesError("separation_of_duties_required_approvals_invalid")
    by_stage: dict[str, dict[str, Any]] = {}
    for row in approvals:
        if not isinstance(row, dict):
            raise SeparationOfDutiesError("separation_of_duties_approval_invalid")
        stage = str(row.get("stage") or "").strip()
        if stage in by_stage:
            raise SeparationOfDutiesError("separation_of_duties_duplicate_stage")
        by_stage[stage] = row
    results: list[dict[str, Any]] = []
    actor_refs: list[str] = []
    for stage, required_role in _REQUIRED:
        row = by_stage.get(stage)
        if row is None:
            raise SeparationOfDutiesError("separation_of_duties_required_stage_missing")
        supplied_role = str(row.get("role") or "").strip()
        actor_ref = _safe(row.get("actor_ref"), "separation_of_duties_actor_ref_invalid")
        artifact_ref = _safe(row.get("artifact_ref"), "separation_of_duties_artifact_ref_invalid")
        approved = row.get("approved")
        if type(approved) is not bool:
            raise SeparationOfDutiesError("separation_of_duties_approved_boolean_required")
        actor_refs.append(actor_ref)
        results.append(
            {
                "stage": stage,
                "required_role": required_role,
                "supplied_role": supplied_role,
                "actor_ref": actor_ref,
                "artifact_ref": artifact_ref,
                "approved": approved,
                "role_matches": supplied_role == required_role,
                "source_drill_down": {
                    "artifact_ref": artifact_ref,
                    "kind": "opaque_approval_artifact_reference",
                    "review_required": True,
                },
            }
        )
    duplicate_refs = sorted({actor for actor in actor_refs if actor_refs.count(actor) > 1})
    for row in results:
        row["independent_actor"] = row["actor_ref"] not in duplicate_refs
    blockers: list[str] = []
    if duplicate_refs:
        blockers.extend(f"actor_ref_reused:{actor}" for actor in duplicate_refs)
    blockers.extend(f"role_mismatch:{row['stage']}" for row in results if not row["role_matches"])
    blockers.extend(f"approval_missing:{row['stage']}" for row in results if not row["approved"])
    passed = not blockers
    return {
        "schema_version": "separation_of_duties_review_v1",
        "status": "review_required" if passed else "blocked",
        "review_id": review,
        "tenant_scope": tenant_id,
        "required_stages": [stage for stage, _role in _REQUIRED],
        "approval_results": results,
        "independent_actor_count": len(set(actor_refs)),
        "duplicate_actor_refs": duplicate_refs,
        "blockers": blockers,
        "independence_satisfied": passed,
        "authority_activation_performed": False,
        "release_approval_performed": False,
        "private_record_content_included": False,
        "paths_disclosed": False,
        "network_used": False,
        "review_required": True,
        "notice": "This checks opaque approval references for separation of duties. It does not activate authority, create a legal sign-off, or approve a release; independent accountable humans and their external evidence remain required.",
    }


class SeparationOfDutiesReceiptStore:
    """Encrypted tenant-bound receipt chain for explicit SoD review actions."""

    def __init__(self, root: str | Path | None = None, *, encryption_key: str | None = None) -> None:
        self.root = Path(root or _root()).resolve()
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    def _path(self, tenant_id: str) -> Path:
        return self.root / f"{_digest(tenant_id)[:32]}.json.enc"

    def _load(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"schema_version": "separation_of_duties_receipts_v1", "tenant_id": "", "reviews": [], "audit": []}
        try:
            state = self.encryptor.decrypt_json(strict_json_load_path(path, max_bytes=_MAX_STATE_BYTES, require_object=True))
        except Exception as exc:
            raise SeparationOfDutiesError("separation_of_duties_receipt_store_unavailable") from exc
        if not isinstance(state, dict) or state.get("schema_version") != "separation_of_duties_receipts_v1":
            raise SeparationOfDutiesError("separation_of_duties_receipt_store_unavailable")
        return state

    def record(self, evaluation: dict[str, Any], *, tenant_id: str) -> dict[str, Any]:
        if evaluation.get("tenant_scope") != tenant_id or evaluation.get("review_required") is not True or evaluation.get("authority_activation_performed") is not False or evaluation.get("release_approval_performed") is not False:
            raise SeparationOfDutiesError("separation_of_duties_receipt_boundary_invalid")
        path = self._path(tenant_id)
        with exclusive_file_lock(path.with_suffix(path.suffix + ".lock")):
            state = self._load(path)
            if state.get("tenant_id") and state["tenant_id"] != tenant_id:
                raise SeparationOfDutiesError("separation_of_duties_tenant_mismatch")
            state["tenant_id"] = tenant_id
            previous = str((state.get("audit") or [{}])[-1].get("event_hash") or "")
            recorded_at = _now(); evaluation_hash = _digest(evaluation)
            basis = {"event_type": "separation_of_duties_evaluated", "recorded_at": recorded_at, "evaluation_hash": evaluation_hash, "previous_hash": previous, "tenant_id": tenant_id}
            audit = {**basis, "event_hash": _digest(basis)}
            receipt = {"receipt_id": f"sod_{audit['event_hash'][:24]}", "recorded_at": recorded_at, "evaluation_hash": evaluation_hash, "status": evaluation["status"], "review_required": True}
            state["reviews"] = [*list(state.get("reviews") or []), {"review_id": evaluation["review_id"], "receipt": receipt}][-_MAX_ROWS:]
            state["audit"] = [*list(state.get("audit") or []), audit][-_MAX_ROWS:]
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(path, _canonical(self.encryptor.encrypt_json(state)), mode=0o600)
        return {"receipt": receipt, "audit_chain_head": audit["event_hash"], "review_required": True}


__all__ = ["SeparationOfDutiesError", "SeparationOfDutiesReceiptStore", "evaluate_separation_of_duties"]
