"""Confirmed, single-file legacy assignment migration; never restores authority.

The original bytes and receipt live inside the new authenticated ledger, so an
atomic replacement either preserves the old file or installs the complete new
one. There is no plaintext backup, second commit, or destructive rollback.
"""

from __future__ import annotations

import base64
import hashlib
import json

from legal.documents import storage
from legal.documents.workspace import get_document
from legal.review import filing_packet as filing
from legal.security.durable_io import read_bounded_regular_file

SCHEMA = "reviewer_assignment_migration_v1"
MAX_LEGACY_BYTES = 1_000_000


def validate(value, events):
    if not isinstance(value, dict) or set(value) != {"original_base64", "receipt"}:
        raise ValueError("assignment_migration_invalid")
    receipt = value["receipt"]
    if not isinstance(receipt, dict) or set(receipt) != {
        "schema",
        "original_sha256",
        "original_bytes",
        "event_count",
        "document_count",
        "confirmed_document_id",
        "confirmed_revision_id",
        "migrated_at",
        "historical_only",
    }:
        raise ValueError("assignment_migration_receipt_invalid")
    raw = base64.b64decode(value["original_base64"], validate=True)
    original = [json.loads(line) for line in raw.splitlines() if line.strip()]
    count = receipt["event_count"]
    if (
        receipt["schema"] != SCHEMA
        or receipt["historical_only"] is not True
        or type(count) is not int
        or not 0 < count <= filing.MAX_ASSIGNMENTS
        or len(raw) > MAX_LEGACY_BYTES
        or receipt["original_bytes"] != len(raw)
        or receipt["original_sha256"] != hashlib.sha256(raw).hexdigest()
        or len(original) != count
        or original != events[:count]
        or receipt["document_count"] != len({row["document_id"] for row in original})
        or any(
            not filing._ID_RE.fullmatch(str(receipt[key]))
            for key in ("confirmed_document_id", "confirmed_revision_id")
        )
        or not isinstance(receipt["migrated_at"], str)
    ):
        raise ValueError("assignment_migration_original_mismatch")
    return count


def preview(store, ledger, document):
    """No write, no other-document titles/IDs, no original private prose in API."""
    if ledger.migration:
        return {
            "status": "migrated",
            "receipt": ledger.migration["receipt"],
            "review_required": True,
            "historical_assignments_activated": False,
        }
    if ledger.authenticated:
        return {"status": "not_needed", "review_required": True}
    blockers = []
    if not ledger or ledger.original_bytes > MAX_LEGACY_BYTES:
        blockers.append("legacy_assignment_migration_size_or_count_limit")
    try:
        root, _ = storage._location(store.assignments)
        legacy_workspace = storage.policy(root)["legacy_read_only"]
    except (OSError, ValueError, KeyError) as exc:
        raise filing.ReviewedFilingPacketError(
            "assignment_migration_workspace_unverified",
            "Workspace privacy status could not be verified. Keep the original files and key; "
            "no migration is allowed until the workspace can be verified.",
            status_code=409,
        ) from exc
    if legacy_workspace:
        blockers.append("encrypted_draft_workspace_required_first")
    if document.get("status") == "deleted":
        blockers.append("restore_document_before_assignment_migration")
    return {
        "status": "blocked" if blockers else "preview",
        "original_sha256": ledger.original_sha256,
        "original_bytes": ledger.original_bytes,
        "event_count": len(ledger),
        "document_count": len({row["document_id"] for row in ledger}),
        "expected_revision_id": document["current_revision_id"],
        "blockers": blockers,
        "scope": "all_reviewer_assignment_history_in_active_matter",
        "review_required": True,
        "historical_assignments_activated": False,
    }


def migrate(store, document_id, *, expected_revision_id, original_sha256, confirmed):
    if confirmed is not True:
        raise filing.ReviewedFilingPacketError(
            "assignment_migration_confirmation_required", "Review and confirm the migration first."
        )
    if not filing._SHA_RE.fullmatch(str(original_sha256)):
        raise filing.ReviewedFilingPacketError(
            "assignment_migration_preview_required",
            "Reload the exact assignment preview first.",
            status_code=409,
        )
    with filing._LOCK, filing._assignment_guard(store.root / ".assignments.lock"):
        document = get_document(store.case_root, document_id, include_history=False)
        if document.get("status") == "deleted":
            raise filing.ReviewedFilingPacketError(
                "assignment_migration_document_deleted",
                "Restore the document and reload the preview before migration.",
                status_code=409,
            )
        if document["current_revision_id"] != expected_revision_id:
            raise filing.ReviewedFilingPacketError(
                "assignment_revision_stale",
                "The document changed. Reload before confirming migration.",
                status_code=409,
            )
        ledger = store._assignment_rows()
        if ledger.migration and ledger.migration["receipt"]["original_sha256"] == original_sha256:
            return store.assignments_for(document_id)  # Lost response: no second migration/write.
        plan = preview(store, ledger, document)
        if plan["status"] != "preview" or plan["original_sha256"] != original_sha256:
            raise filing.ReviewedFilingPacketError(
                "assignment_migration_preview_stale",
                "Assignment history changed or is not eligible. "
                "Reload its preview; no migration was applied.",
                status_code=409,
            )
        try:
            raw = read_bounded_regular_file(store.assignments, max_bytes=MAX_LEGACY_BYTES)
            if hashlib.sha256(raw).hexdigest() != original_sha256:
                raise ValueError("assignment_migration_preview_stale")
            migration = {
                "original_base64": base64.b64encode(raw).decode("ascii"),
                "receipt": {
                    "schema": SCHEMA,
                    "original_sha256": original_sha256,
                    "original_bytes": len(raw),
                    "event_count": len(ledger),
                    "document_count": plan["document_count"],
                    "confirmed_document_id": document_id,
                    "confirmed_revision_id": expected_revision_id,
                    "migrated_at": filing._utc_now(),
                    "historical_only": True,
                },
            }
            validate(migration, ledger)
            encoded = storage.encode(
                store.assignments,
                {
                    "schema": "encrypted_reviewer_assignments_v2",
                    "events": list(ledger),
                    "migration": migration,
                },
            )
            # Recheck immediately before commit; cooperating writers share this lock.
            if (
                hashlib.sha256(
                    read_bounded_regular_file(store.assignments, max_bytes=MAX_LEGACY_BYTES)
                ).hexdigest()
                != original_sha256
            ):
                raise ValueError("assignment_migration_preview_stale")
            filing.atomic_write_bytes(store.assignments, encoded)
        except (OSError, ValueError, TypeError) as exc:
            raise filing.ReviewedFilingPacketError(
                "assignment_migration_unavailable",
                "Migration could not be confirmed. Reload assignment history before retrying. "
                "Keep this workspace and its original protected key.",
                status_code=409,
            ) from exc
        return store.assignments_for(document_id)
