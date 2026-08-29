"""Encrypted reviewer-handoff manifests; no silent sharing or external upload."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path

_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")


def _identifier(value: Any, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _ID.fullmatch(normalized):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return normalized


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ReviewerHandoffStore:
    """A case-scoped, encrypted reviewer-bundle ledger.

    A bundle is a *local review artifact*, not a transmission mechanism.  The
    ledger deliberately records only safe identifiers, hashes, and the
    user-provided review working text inside the encrypted active-matter
    store.  Reimport is append-only: it can surface a changed source scope but
    can never replace the exported handoff or silently merge a reviewer edit.
    """

    schema = "maine_family_law_llm.reviewer_handoff.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "41_REVIEWER_HANDOFF"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("handoff_store_unavailable", 409)
        key = encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY")
        self.encryptor = LocalEnvelopeEncryptor(key or "local-development-key-change-me")
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "handoffs.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".handoffs.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema": self.schema,
                "scope": self.scope,
                "handoffs": [],
                "bundles": [],
                "comments": [],
                "attestations": [],
                "reimports": [],
                "history": [],
                "revision": 0,
            }
        try:
            encrypted = strict_json_load_path(
                self.path, max_bytes=8 * 1024 * 1024, require_object=True
            )
            value = self.encryptor.decrypt_json(encrypted)
        except Exception as exc:
            raise IntakeWorkbenchError("handoff_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        # Version-one ledgers are intentionally upgraded in memory.  The next
        # mutation persists the additional append-only collections encrypted;
        # no historic manifest is rewritten or discarded.
        for collection in ("bundles", "comments", "attestations", "reimports"):
            if not isinstance(value.get(collection), list):
                value[collection] = []
        return value

    def _save(self, value: dict[str, Any]) -> None:
        encrypted = self.encryptor.encrypt_json(value)
        atomic_write_bytes(self.path, json.dumps(encrypted, sort_keys=True).encode(), mode=0o600)

    def _mutate(
        self,
        action: str,
        identifiers: list[str],
        update: Callable[[dict[str, Any]], Any],
    ) -> Any:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = update(value)
            event = {
                "event_id": f"handoff_{uuid.uuid4().hex}",
                "at": _now(),
                "action": action,
                "ids": identifiers,
                "previous_hash": value["history"][-1]["hash"] if value["history"] else "",
                "review_required": True,
            }
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = deepcopy(self._load())
        value.pop("scope", None)
        # Inventory intentionally omits comment bodies.  They can contain
        # private matter working text and are available only through a scoped
        # bundle/reconciliation review result.
        value["comments"] = [
            {key: item.get(key) for key in ("comment_id", "handoff_id", "bundle_hash", "target_kind", "target_id", "reviewer_safe_id", "created_at", "comment_hash")}
            for item in value["comments"]
        ]
        value.update(
            {
                "status": "review_required",
                "review_required": True,
                "local_only": True,
                "automatic_share": False,
                "external_upload": False,
                "bundle_generation": "manifest_only",
                "bundle_round_trip": {
                    "export": "local_review_bundle_only",
                    "comments": "encrypted_active_matter_only",
                    "attestations": "human_attestation_not_cryptographic_signature",
                    "reimport": "append_only_conflict_aware",
                    "automatic_merge": False,
                },
            }
        )
        return value

    def add(self, payload: dict[str, Any]) -> dict[str, Any]:
        handoff_id = _identifier(payload.get("handoff_id"), "handoff_id")
        record_values = payload.get("record_ids", [])
        if not isinstance(record_values, list):
            raise IntakeWorkbenchError("handoff_records_invalid")
        record_ids = [_identifier(item, "record_id") for item in record_values]
        if not record_ids or len(record_ids) > 500:
            raise IntakeWorkbenchError("handoff_records_invalid")
        reviewer_safe_id = _identifier(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        purpose = str(payload.get("purpose") or "").strip()
        if len(purpose) > 1_000:
            raise IntakeWorkbenchError("text_limit_exceeded")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(item["handoff_id"] == handoff_id for item in value["handoffs"]):
                raise IntakeWorkbenchError("duplicate_handoff_id", 409)
            manifest = {
                "handoff_id": handoff_id,
                "record_ids": record_ids,
                "reviewer_safe_id": reviewer_safe_id,
                "purpose": purpose,
                "encrypted_manifest": True,
                "review_required": True,
                "created_at": _now(),
            }
            manifest["manifest_hash"] = _hash(manifest)
            value["handoffs"].append(manifest)
            return deepcopy(manifest)

        return self._mutate("handoff_manifest_added", [handoff_id, *record_ids], update)

    @staticmethod
    def _handoff(value: dict[str, Any], handoff_id: str) -> dict[str, Any]:
        for item in value["handoffs"]:
            if item.get("handoff_id") == handoff_id:
                return item
        raise IntakeWorkbenchError("handoff_not_found", 404)

    @staticmethod
    def _bundle(value: dict[str, Any], bundle_id: str) -> dict[str, Any]:
        for item in value["bundles"]:
            if item.get("bundle_id") == bundle_id:
                return item
        raise IntakeWorkbenchError("reviewer_bundle_not_found", 404)

    @staticmethod
    def _bounded_text(value: Any, field: str, maximum: int = 4_000) -> str:
        text = str(value or "").strip()
        if not text:
            raise IntakeWorkbenchError(f"{field}_required")
        if len(text) > maximum:
            raise IntakeWorkbenchError("text_limit_exceeded")
        return text

    @staticmethod
    def _bundle_payload(manifest: dict[str, Any], bundle_id: str) -> dict[str, Any]:
        payload = {
            "schema": "maine_family_law_llm.reviewer_bundle.v1",
            "bundle_id": bundle_id,
            "handoff_id": manifest["handoff_id"],
            "base_manifest_hash": manifest["manifest_hash"],
            "record_refs": [
                {
                    "record_id": record_id,
                    "source_drill_down": {
                        "route": f"/api/reviewer-handoff/{manifest['handoff_id']}/records/{record_id}/source",
                        "review_required": True,
                    },
                }
                for record_id in manifest["record_ids"]
            ],
            "reviewer_safe_id": manifest["reviewer_safe_id"],
            "purpose": manifest["purpose"],
            "review_required": True,
            "local_only": True,
            "automatic_share": False,
            "external_upload": False,
            "legal_effect": "none",
            "created_at": _now(),
        }
        payload["bundle_hash"] = _hash(payload)
        return payload

    def export_bundle(self, handoff_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        handoff = _identifier(handoff_id, "handoff_id")
        bundle_id = _identifier(payload.get("bundle_id"), "bundle_id")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            manifest = self._handoff(value, handoff)
            if any(item.get("bundle_id") == bundle_id for item in value["bundles"]):
                raise IntakeWorkbenchError("duplicate_reviewer_bundle_id", 409)
            bundle = self._bundle_payload(manifest, bundle_id)
            value["bundles"].append(bundle)
            return deepcopy(bundle)

        bundle = self._mutate("reviewer_bundle_exported", [handoff, bundle_id], update)
        return {
            "bundle": bundle,
            "status": "review_required",
            "delivery": "not_sent_local_export_only",
            "review_required": True,
            "source_drill_down_available": True,
        }

    def add_comment(self, handoff_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        handoff = _identifier(handoff_id, "handoff_id")
        comment_id = _identifier(payload.get("comment_id"), "comment_id")
        bundle_id = _identifier(payload.get("bundle_id"), "bundle_id")
        reviewer = _identifier(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        target_kind = str(payload.get("target_kind") or "").strip().casefold()
        if target_kind not in {"record", "source_span", "claim", "draft_text", "artifact"}:
            raise IntakeWorkbenchError("reviewer_comment_target_kind_invalid")
        target_id = _identifier(payload.get("target_id"), "reviewer_comment_target_id")
        body = self._bounded_text(payload.get("body"), "reviewer_comment_body")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            manifest = self._handoff(value, handoff)
            bundle = self._bundle(value, bundle_id)
            if bundle["handoff_id"] != manifest["handoff_id"]:
                raise IntakeWorkbenchError("reviewer_bundle_handoff_mismatch", 409)
            if any(item.get("comment_id") == comment_id for item in value["comments"]):
                raise IntakeWorkbenchError("duplicate_reviewer_comment_id", 409)
            comment = {
                "comment_id": comment_id,
                "handoff_id": handoff,
                "bundle_hash": bundle["bundle_hash"],
                "reviewer_safe_id": reviewer,
                "target_kind": target_kind,
                "target_id": target_id,
                "body": body,
                "created_at": _now(),
                "review_required": True,
            }
            comment["comment_hash"] = _hash(comment)
            value["comments"].append(comment)
            return deepcopy(comment)

        comment = self._mutate("reviewer_bundle_comment_added", [handoff, bundle_id, comment_id], update)
        result = {
            "comment": comment,
            "status": "review_required",
        }
        if target_kind in {"record", "source_span"}:
            result["source_drill_down"] = self.source_reference(handoff, comment["target_id"])
        else:
            result["source_drill_down"] = {
                "kind": target_kind,
                "target_id": target_id,
                "review_required": True,
                "notice": "Inspect the owning claim, draft, or artifact in the active matter; this target is not a record-source locator.",
            }
        return result

    def attest(self, handoff_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        handoff = _identifier(handoff_id, "handoff_id")
        attestation_id = _identifier(payload.get("attestation_id"), "attestation_id")
        bundle_id = _identifier(payload.get("bundle_id"), "bundle_id")
        reviewer = _identifier(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        statement = self._bounded_text(payload.get("statement"), "reviewer_attestation_statement", 1_200)

        def update(value: dict[str, Any]) -> dict[str, Any]:
            manifest = self._handoff(value, handoff)
            bundle = self._bundle(value, bundle_id)
            if bundle["handoff_id"] != manifest["handoff_id"]:
                raise IntakeWorkbenchError("reviewer_bundle_handoff_mismatch", 409)
            if any(item.get("attestation_id") == attestation_id for item in value["attestations"]):
                raise IntakeWorkbenchError("duplicate_reviewer_attestation_id", 409)
            row = {
                "attestation_id": attestation_id,
                "handoff_id": handoff,
                "bundle_hash": bundle["bundle_hash"],
                "reviewer_safe_id": reviewer,
                "statement": statement,
                "created_at": _now(),
                "signature_kind": "human_attestation_not_cryptographic_signature",
                "cryptographically_verified": False,
                "review_required": True,
            }
            row["attestation_hash"] = _hash(row)
            value["attestations"].append(row)
            return deepcopy(row)

        row = self._mutate("reviewer_bundle_attested", [handoff, bundle_id, attestation_id], update)
        return {
            "attestation": row,
            "status": "review_required",
            "signature_notice": "A local human attestation was recorded; it is not a cryptographic signature or legal approval.",
        }

    def reimport(self, handoff_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        handoff = _identifier(handoff_id, "handoff_id")
        reimport_id = _identifier(payload.get("reimport_id"), "reimport_id")
        reviewer = _identifier(payload.get("reviewer_safe_id"), "reviewer_safe_id")
        bundle = payload.get("bundle")
        if not isinstance(bundle, dict):
            raise IntakeWorkbenchError("reviewer_bundle_required")
        claimed_hash = str(bundle.get("bundle_hash") or "")
        immutable = deepcopy(bundle)
        immutable.pop("bundle_hash", None)
        if not re.fullmatch(r"[a-f0-9]{64}", claimed_hash) or _hash(immutable) != claimed_hash:
            raise IntakeWorkbenchError("reviewer_bundle_hash_invalid", 409)
        bundle_id = _identifier(bundle.get("bundle_id"), "bundle_id")
        review_note = str(payload.get("review_note") or "").strip()
        if len(review_note) > 4_000:
            raise IntakeWorkbenchError("text_limit_exceeded")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            manifest = self._handoff(value, handoff)
            exported = self._bundle(value, bundle_id)
            if any(item.get("reimport_id") == reimport_id for item in value["reimports"]):
                raise IntakeWorkbenchError("duplicate_reviewer_reimport_id", 409)
            if exported["handoff_id"] != handoff or claimed_hash != exported["bundle_hash"]:
                raise IntakeWorkbenchError("reviewer_bundle_lineage_mismatch", 409)
            if bundle.get("handoff_id") != handoff or bundle.get("base_manifest_hash") != manifest["manifest_hash"]:
                raise IntakeWorkbenchError("reviewer_bundle_manifest_mismatch", 409)
            row = {
                "reimport_id": reimport_id,
                "handoff_id": handoff,
                "bundle_id": bundle_id,
                "bundle_hash": claimed_hash,
                "reviewer_safe_id": reviewer,
                "review_note": review_note,
                "reimported_at": _now(),
                "review_required": True,
            }
            row["reimport_hash"] = _hash(row)
            value["reimports"].append(row)
            return deepcopy(row)

        row = self._mutate("reviewer_bundle_reimported", [handoff, bundle_id, reimport_id], update)
        return {"reimport": row, "reconciliation": self.reconcile(handoff), "status": "review_required"}

    def reconcile(self, handoff_id: str) -> dict[str, Any]:
        handoff = _identifier(handoff_id, "handoff_id")
        value = self._load()
        manifest = deepcopy(self._handoff(value, handoff))
        bundles = [deepcopy(item) for item in value["bundles"] if item.get("handoff_id") == handoff]
        comments = [deepcopy(item) for item in value["comments"] if item.get("handoff_id") == handoff]
        attestations = [deepcopy(item) for item in value["attestations"] if item.get("handoff_id") == handoff]
        reimports = [deepcopy(item) for item in value["reimports"] if item.get("handoff_id") == handoff]
        blockers: list[str] = []
        if not bundles:
            blockers.append("reviewer_bundle_not_exported")
        if not reimports:
            blockers.append("reviewer_bundle_not_reimported")
        for bundle in bundles:
            if bundle.get("base_manifest_hash") != manifest.get("manifest_hash"):
                blockers.append("bundle_base_manifest_changed")
            returned = [item for item in reimports if item.get("bundle_hash") == bundle.get("bundle_hash")]
            if returned and bundle.get("record_refs") != self._bundle_payload(manifest, bundle["bundle_id"]).get("record_refs"):
                blockers.append("record_scope_changed_after_export")
        status = "conflict_review_required" if blockers else "review_required"
        return {
            "handoff_id": handoff,
            "status": status,
            "review_required": True,
            "automatic_merge": False,
            "blockers": sorted(set(blockers)),
            "lineage": {
                "manifest_hash": manifest["manifest_hash"],
                "bundle_hashes": [item["bundle_hash"] for item in bundles],
                "reimport_hashes": [item["reimport_hash"] for item in reimports],
                "history_hash": _hash(value["history"]),
            },
            "comments": comments,
            "attestations": attestations,
            "reimports": reimports,
            "source_drill_down": [self.source_reference(handoff, record_id) for record_id in manifest["record_ids"]],
            "next_action": "Inspect the exact active-matter records and resolve every listed conflict manually before using a reviewer work product.",
        }

    def source_reference(self, handoff_id: str, record_id: str, *, allow_unincluded: bool = False) -> dict[str, Any]:
        handoff = _identifier(handoff_id, "handoff_id")
        record = _identifier(record_id, "record_id")
        manifest = self._handoff(self._load(), handoff)
        if not allow_unincluded and record not in manifest["record_ids"]:
            raise IntakeWorkbenchError("reviewer_bundle_record_not_in_scope", 404)
        return {
            "handoff_id": handoff,
            "record_id": record,
            "source_drill_down": {
                "route": f"/api/records/{record}/integrity",
                "kind": "active_matter_record_integrity",
                "review_required": True,
                "automatic_open": False,
            },
            "status": "review_required",
        }

    def receipt(self) -> dict[str, Any]:
        value = self._load()
        receipt = {
            "revision": value["revision"],
            "handoffs_hash": _hash(value["handoffs"]),
            "history_hash": _hash(value["history"]),
            "review_required": True,
            "issued_at": _now(),
        }
        receipt["receipt_hash"] = _hash(receipt)
        return receipt
