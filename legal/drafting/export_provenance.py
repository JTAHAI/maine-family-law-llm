"""Local export-provenance receipts and safe, review-required footer text."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-f0-9]{16,80}\Z")


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _text(value: Any, field: str, limit: int = 100) -> str:
    result = str(value or "").strip()
    if not result or len(result) > limit:
        raise IntakeWorkbenchError(f"{field}_invalid")
    return result


class ExportProvenanceStore:
    """Keeps export receipts encrypted in the active matter and never exposes paths."""

    schema = "maine_family_law_llm.export_provenance.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "19_DRAFTING" / "export-provenance"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("export_provenance_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me"
        )

    @property
    def path(self) -> Path:
        return self.root / "receipts.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".receipts.lock"

    def _default(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "receipts": [], "ledger": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=16 * 1024 * 1024, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("export_provenance_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        state.setdefault("receipts", [])
        state.setdefault("ledger", [])
        return state

    def _save(self, state: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(state), sort_keys=True).encode(), mode=0o600)

    @staticmethod
    def _public(value: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(value)
        result.pop("scope", None)
        result.pop("footer_text", None)
        result.update(
            {
                "review_required": True,
                "filing_ready": False,
                "local_only": True,
                "notice": "Export provenance identifies the local review state and source snapshot. It does not certify a filing, source authenticity, legal sufficiency, or court acceptance.",
            }
        )
        return result

    @staticmethod
    def _footer(receipt: dict[str, Any], *, markdown: bool) -> str:
        heading = "## Local export provenance — review required" if markdown else "LOCAL EXPORT PROVENANCE — REVIEW REQUIRED"
        lines = [
            heading,
            f"Product version: {receipt['product_version']}",
            f"Matter scope: {receipt['matter_scope_id']}",
            f"Document ID: {receipt['document_id']}",
            f"Document revision: {receipt['revision_id']}",
            f"Document SHA-256: {receipt['document_content_sha256']}",
            f"Source snapshot SHA-256: {receipt['source_snapshot_sha256']}",
            f"Review state: {receipt['review_state']}",
            f"Privacy state: {receipt['privacy_state']}",
            f"Export receipt ID: {receipt['receipt_id']}",
            "This local work product remains review-required and is not filing-ready.",
        ]
        return ("\n\n" if markdown else "\n").join(lines)

    def start(self, document: dict[str, Any], *, product_version: str, format_name: str) -> dict[str, Any]:
        document_id = _text(document.get("document_id"), "document_id", 80)
        revision_id = _text(document.get("current_revision_id"), "revision_id", 80)
        content = str(document.get("content") or "")
        if not content.strip() or not _ID.fullmatch(document_id) or not _ID.fullmatch(revision_id):
            raise IntakeWorkbenchError("export_provenance_document_invalid", 409)
        receipt = {
            "receipt_id": f"export_{uuid.uuid4().hex}",
            "document_id": document_id,
            "revision_id": revision_id,
            "document_content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            "source_snapshot_sha256": _digest(list(document.get("source_refs") or [])),
            "source_ref_count": len(list(document.get("source_refs") or [])),
            "product_version": _text(product_version, "product_version", 80),
            "format": _text(format_name, "format", 20).casefold(),
            "matter_scope_id": f"matter-{self.scope}",
            "review_state": "review_required_not_filing_ready",
            "privacy_state": "local_only_matter_private",
            "created_at": _now(),
            "status": "prepared",
            "review_required": True,
            "filing_ready": False,
        }
        receipt["footer_text"] = self._footer(receipt, markdown=receipt["format"] == "md")
        with exclusive_file_lock(self.lock):
            state = self._load()
            state["receipts"].append(receipt)
            event = {
                "event_id": f"export_provenance_{uuid.uuid4().hex}",
                "at": _now(),
                "action": "prepare_export_provenance",
                "receipt_id": receipt["receipt_id"],
                "document_id": document_id,
                "revision_id": revision_id,
                "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "",
                "review_required": True,
            }
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return receipt

    def complete(self, receipt_id: str, *, artifact_sha256: str, size_bytes: int) -> dict[str, Any]:
        receipt_id = _text(receipt_id, "export_receipt_id", 80)
        if not re.fullmatch(r"[a-f0-9]{64}", str(artifact_sha256 or "").casefold()):
            raise IntakeWorkbenchError("export_artifact_hash_invalid")
        with exclusive_file_lock(self.lock):
            state = self._load()
            receipt = next((row for row in state["receipts"] if row.get("receipt_id") == receipt_id), None)
            if receipt is None:
                raise IntakeWorkbenchError("export_provenance_receipt_not_found", 404)
            receipt["artifact_sha256"] = str(artifact_sha256).casefold()
            receipt["artifact_size_bytes"] = max(0, int(size_bytes))
            receipt["status"] = "completed"
            receipt["completed_at"] = _now()
            event = {
                "event_id": f"export_provenance_{uuid.uuid4().hex}",
                "at": _now(),
                "action": "complete_export_provenance",
                "receipt_id": receipt_id,
                "artifact_sha256": receipt["artifact_sha256"],
                "previous_event_hash": str(state["ledger"][-1].get("event_hash") or "") if state["ledger"] else "",
                "review_required": True,
            }
            event["event_hash"] = _digest(event)
            state["ledger"].append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
            return self._public(receipt)

    def receipts(self, document_id: str) -> dict[str, Any]:
        document_id = _text(document_id, "document_id", 80)
        return {
            "receipts": [self._public(row) for row in self._load()["receipts"] if row.get("document_id") == document_id],
            "review_required": True,
            "local_only": True,
        }
