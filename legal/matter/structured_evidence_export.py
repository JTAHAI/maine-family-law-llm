"""Scoped, local CSV/JSON evidence exports with encrypted receipt lineage."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID = re.compile(r"[a-z][a-z0-9_-]{2,79}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_STATES = {"review_required", "verified", "unresolved", "blocked"}


def _id(value: Any, field: str) -> str:
    normalized = str(value or "").strip().casefold()
    if not _ID.fullmatch(normalized):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return normalized


def _text(value: Any, field: str, maximum: int) -> str:
    normalized = " ".join(str(value or "").split())
    if not normalized:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(normalized) > maximum:
        raise IntakeWorkbenchError(f"{field}_limit_exceeded")
    return normalized


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StructuredEvidenceExportStore:
    """Active-matter export boundary; only receipts, never raw exports, persist."""

    schema = "maine_family_law_llm.structured_evidence_export.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "50_STRUCTURED_EVIDENCE_EXPORTS"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("structured_export_store_unavailable", 409)
        self.scope = hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24]
        self.encryptor = LocalEnvelopeEncryptor(encryption_key or os.environ.get("MAINE_MATTER_STORE_KEY") or "local-development-key-change-me")

    @property
    def path(self) -> Path:
        return self.root / "exports.json.enc"

    @property
    def lock(self) -> Path:
        return self.root / ".exports.lock"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.schema, "scope": self.scope, "exports": [], "history": [], "revision": 0}
        try:
            value = self.encryptor.decrypt_json(strict_json_load_path(self.path, max_bytes=8 * 1024 * 1024, require_object=True))
        except Exception as exc:
            raise IntakeWorkbenchError("structured_export_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, action: str, identifiers: list[str], update: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = update(value)
            event = {"event_id": f"structured_export_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": identifiers, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = self._load()
        return {"exports": [{key: item[key] for key in ("export_id", "formats", "row_count", "manifest_hash", "artifact_hashes", "review_required", "created_at")} for item in value["exports"]], "revision": value["revision"], "status": "review_required", "review_required": True, "local_only": True, "automatic_download": False, "raw_matter_store_exported": False}

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        export_id = _id(payload.get("export_id"), "structured_export_id")
        scope_id = _id(payload.get("scope_id"), "structured_export_scope_id")
        if payload.get("privacy_acknowledged") is not True:
            raise IntakeWorkbenchError("structured_export_privacy_acknowledgement_required", 409)
        formats = payload.get("formats")
        if not isinstance(formats, list) or not formats or any(item not in {"csv", "json"} for item in formats):
            raise IntakeWorkbenchError("structured_export_formats_invalid")
        formats = sorted(set(formats))
        rows_input = payload.get("rows")
        if not isinstance(rows_input, list) or not rows_input or len(rows_input) > 500:
            raise IntakeWorkbenchError("structured_export_rows_invalid")
        rows: list[dict[str, Any]] = []
        for raw in rows_input:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("structured_export_rows_invalid")
            source_hash = str(raw.get("source_hash") or "").strip().casefold()
            if not _SHA256.fullmatch(source_hash):
                raise IntakeWorkbenchError("structured_export_source_hash_invalid")
            source_ref = raw.get("source_ref")
            if not isinstance(source_ref, dict) or not any(str(source_ref.get(key) or "").strip() for key in ("record_id", "source_id", "artifact_id")):
                raise IntakeWorkbenchError("structured_export_source_locator_required")
            state = str(raw.get("review_state") or "").strip().casefold()
            if state not in _STATES:
                raise IntakeWorkbenchError("structured_export_review_state_invalid")
            rows.append({"evidence_id": _id(raw.get("evidence_id"), "structured_export_evidence_id"), "source_hash": source_hash, "source_ref": {str(key): str(value)[:240] for key, value in source_ref.items() if key in {"record_id", "source_id", "artifact_id", "span", "page"}}, "review_state": state, "label": _text(raw.get("label"), "structured_export_label", 600), "review_required": True})
        if len({row["evidence_id"] for row in rows}) != len(rows):
            raise IntakeWorkbenchError("structured_export_evidence_duplicate")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(row["export_id"] == export_id for row in value["exports"]):
                raise IntakeWorkbenchError("structured_export_exists", 409)
            manifest = {"schema": "maine_family_law_llm.structured_evidence_export_package.v1", "export_id": export_id, "scope_id": scope_id, "rows": [{key: row[key] for key in ("evidence_id", "source_hash", "source_ref", "review_state", "review_required")} for row in rows], "review_required": True, "local_only": True, "privacy_warning": "Review scope and recipient before any separate external transfer.", "created_at": _now()}
            manifest["manifest_hash"] = _hash(manifest)
            # Keep the schema and scope at the top level so a recipient can
            # validate the JSON artifact without knowing our internal receipt
            # envelope.  The same manifest remains available separately.
            package = {**manifest, "evidence": rows}
            artifacts: dict[str, dict[str, str]] = {}
            if "json" in formats:
                content = json.dumps(package, indent=2, sort_keys=True).encode()
                artifacts["json"] = {"base64": base64.b64encode(content).decode(), "sha256": hashlib.sha256(content).hexdigest(), "filename": f"{export_id}.json", "media_type": "application/json"}
            if "csv" in formats:
                stream = io.StringIO(newline="")
                writer = csv.DictWriter(stream, fieldnames=["evidence_id", "source_hash", "source_locator", "review_state", "label", "review_required"])
                writer.writeheader()
                for row in rows:
                    writer.writerow({"evidence_id": row["evidence_id"], "source_hash": row["source_hash"], "source_locator": json.dumps(row["source_ref"], sort_keys=True, separators=(",", ":")), "review_state": row["review_state"], "label": row["label"], "review_required": "true"})
                content = stream.getvalue().encode()
                artifacts["csv"] = {"base64": base64.b64encode(content).decode(), "sha256": hashlib.sha256(content).hexdigest(), "filename": f"{export_id}.csv", "media_type": "text/csv"}
            receipt = {"export_id": export_id, "formats": formats, "row_count": len(rows), "manifest_hash": manifest["manifest_hash"], "artifact_hashes": {name: artifact["sha256"] for name, artifact in artifacts.items()}, "review_required": True, "automatic_download": False, "created_at": _now()}
            value["exports"].append(receipt)
            return {"export": {"manifest": manifest, "artifacts": artifacts}, "receipt": receipt, "status": "review_required", "local_only": True, "automatic_download": False, "raw_matter_store_exported": False}

        return self._mutate("structured_evidence_export_created", [export_id, scope_id, *[row["evidence_id"] for row in rows]], update)
