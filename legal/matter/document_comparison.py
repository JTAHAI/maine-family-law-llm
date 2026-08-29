"""Encrypted, source-bound document comparison receipts.

This module compares only metadata and extracted text already admitted to one
local matter.  It never overwrites records, treats signatures as authentic,
or substitutes missing page images, tables, or parser output with guesses.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes, exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path


_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{2,119}\Z")
_HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
_MAX_STATE_BYTES = 8 * 1024 * 1024


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _safe_id(value: Any, field: str) -> str:
    candidate = str(value or "").strip()
    if not _ID_RE.fullmatch(candidate):
        raise IntakeWorkbenchError(f"document_comparison_{field}_invalid", 422)
    return candidate


def _safe_hash(value: Any, field: str) -> str:
    candidate = str(value or "").strip().lower()
    if not _HASH_RE.fullmatch(candidate):
        raise IntakeWorkbenchError(f"document_comparison_{field}_invalid", 422)
    return candidate


def _normalized_text(record: dict[str, Any]) -> str:
    text = str(
        record.get("text_content") or record.get("text_excerpt") or record.get("text") or ""
    )[:500_000]
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _count(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _record_inputs(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    record_id = _safe_id(record.get("evidence_id"), "record_id")
    source_hash = _safe_hash(record.get("source_hash"), "source_hash")
    parser_metadata = record.get("parser_metadata")
    parser_metadata = dict(parser_metadata) if isinstance(parser_metadata, dict) else {}
    page_image_hashes = record.get("page_image_hashes")
    if not isinstance(page_image_hashes, list):
        page_image_hashes = []
    valid_image_hashes = [
        str(item).lower()
        for item in page_image_hashes[:10_000]
        if _HASH_RE.fullmatch(str(item or "").lower())
    ]
    binding = {"record_id": record_id, "source_hash": source_hash}
    details = {
        "text": _normalized_text(record),
        "page_count": _count(record.get("page_count")),
        "source_type": str(record.get("source_type") or record.get("document_type") or "unknown")[:80],
        "parser_status": str(record.get("parser_status") or "unknown")[:80],
        "ocr_status": str(record.get("ocr_status") or "unknown")[:80],
        "table_count": _count(parser_metadata.get("table_count") or record.get("table_count")),
        "signature_count": _count(parser_metadata.get("signature_count") or record.get("signature_count")),
        "page_image_hashes": valid_image_hashes,
    }
    return binding, details


def _status(left: Any, right: Any) -> str:
    if left is None or right is None:
        return "unavailable_requires_review"
    return "same" if left == right else "changed_requires_review"


class DocumentComparisonStore:
    """One encrypted, append-only comparison ledger per matter."""

    schema = "maine_family_law_llm.document_comparison.v2"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).expanduser().resolve()
        self.root = self.case_root / "19_EVIDENCE_WORK_PRODUCT" / "document-comparisons"
        if (
            not self.case_root.is_dir()
            or self.case_root.is_symlink()
            or (self.root.exists() and self.root.is_symlink())
        ):
            raise IntakeWorkbenchError("document_comparison_store_unavailable", 409)
        self.root.mkdir(parents=True, exist_ok=True)
        self.encryptor = LocalEnvelopeEncryptor(
            encryption_key
            or os.environ.get("MAINE_MATTER_STORE_KEY")
            or LocalEnvelopeEncryptor.development_default
        )
        self.scope = hashlib.sha256(str(self.case_root).encode("utf-8")).hexdigest()[:24]

    @property
    def path(self) -> Path:
        return self.root / "comparisons.json.enc"

    @property
    def lock_path(self) -> Path:
        return self.root / ".comparisons.lock"

    def _default_state(self) -> dict[str, Any]:
        return {"schema": self.schema, "scope": self.scope, "comparisons": {}, "history": [], "revision": 0}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_state()
        try:
            state = self.encryptor.decrypt_json(
                strict_json_load_path(self.path, max_bytes=_MAX_STATE_BYTES, require_object=True)
            )
        except Exception as exc:
            raise IntakeWorkbenchError("document_comparison_store_unavailable", 409) from exc
        if state.get("schema") != self.schema or state.get("scope") != self.scope:
            raise IntakeWorkbenchError("document_comparison_cross_matter_access_denied", 404)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        envelope = self.encryptor.encrypt_json(state)
        atomic_write_bytes(self.path, json.dumps(envelope, sort_keys=True).encode("utf-8"), mode=0o600)

    def _public(self, comparison: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(comparison)
        result.pop("scope", None)
        return result

    def create(self, *, comparison_id: str, left_record: dict[str, Any], right_record: dict[str, Any]) -> dict[str, Any]:
        comparison_id = _safe_id(comparison_id, "id")
        left, left_details = _record_inputs(left_record)
        right, right_details = _record_inputs(right_record)
        if left["record_id"] == right["record_id"]:
            raise IntakeWorkbenchError("document_comparison_records_must_differ", 422)
        with exclusive_file_lock(self.lock_path):
            state = self._load()
            comparisons = dict(state.get("comparisons") or {})
            if comparison_id in comparisons:
                raise IntakeWorkbenchError("document_comparison_id_exists", 409)
            left_text, right_text = left_details["text"], right_details["text"]
            similarity = SequenceMatcher(None, left_text, right_text).ratio() if left_text or right_text else 0.0
            metadata_fields = {
                name: _status(left_details[name], right_details[name])
                for name in ("source_type", "parser_status", "ocr_status", "page_count")
            }
            page_images_available = bool(left_details["page_image_hashes"] and right_details["page_image_hashes"])
            comparison = {
                "comparison_id": comparison_id,
                "created_at": _now(),
                "left": left,
                "right": right,
                "text": {
                    "status": _status(left_text, right_text),
                    "similarity": round(similarity, 6),
                    "left_normalized_character_count": len(left_text),
                    "right_normalized_character_count": len(right_text),
                    "note": "Text is compared from admitted local extracts. Open either source to review exact wording.",
                },
                "structure": {
                    "status": _status(left_details["page_count"], right_details["page_count"]),
                    "left_page_count": left_details["page_count"],
                    "right_page_count": right_details["page_count"],
                    "metadata_fields": metadata_fields,
                },
                "tables": {
                    "status": _status(left_details["table_count"], right_details["table_count"]),
                    "left_table_count": left_details["table_count"],
                    "right_table_count": right_details["table_count"],
                    "note": "Table comparison is unavailable until both parser outputs contain table counts; it does not reconstruct missing tables.",
                },
                "signatures": {
                    "status": _status(left_details["signature_count"], right_details["signature_count"]),
                    "left_signature_count": left_details["signature_count"],
                    "right_signature_count": right_details["signature_count"],
                    "note": "Signature markers are parser metadata only and do not establish identity, execution, or authenticity.",
                },
                "page_images": {
                    "status": _status(left_details["page_image_hashes"], right_details["page_image_hashes"]),
                    "available": page_images_available,
                    "left_hash_count": len(left_details["page_image_hashes"]),
                    "right_hash_count": len(right_details["page_image_hashes"]),
                    "note": "Page-image comparison remains unavailable until both records have hash-bound page-image derivatives.",
                },
                "review_required": True,
                "local_only": True,
                "notice": "This comparison describes bounded differences in two source-bound records. It does not decide which version controls, whether a signature is authentic, or any legal or factual issue.",
            }
            before_hash = str((state.get("history") or [{}])[-1].get("event_hash") or "")
            event = {
                "event_id": f"document_comparison_{uuid.uuid4().hex}",
                "at": _now(),
                "action": "comparison_created",
                "comparison_id": comparison_id,
                "record_ids": [left["record_id"], right["record_id"]],
                "source_hashes": [left["source_hash"], right["source_hash"]],
                "previous_event_hash": before_hash,
                "review_required": True,
            }
            event["event_hash"] = _digest(event)
            comparison["audit_event_id"] = event["event_id"]
            comparisons[comparison_id] = comparison
            state["comparisons"] = comparisons
            state.setdefault("history", []).append(event)
            state["revision"] = int(state.get("revision") or 0) + 1
            self._save(state)
        return {"status": "pass", "comparison": self._public(comparison), "review_required": True}

    def get(self, comparison_id: str = "") -> dict[str, Any]:
        state = self._load()
        comparisons = dict(state.get("comparisons") or {})
        if comparison_id:
            item = comparisons.get(_safe_id(comparison_id, "id"))
            if not isinstance(item, dict):
                raise IntakeWorkbenchError("document_comparison_not_found", 404)
            return {"status": "pass", "comparison": self._public(item), "review_required": True}
        return {
            "status": "pass",
            "comparisons": [self._public(item) for _key, item in sorted(comparisons.items())],
            "review_required": True,
            "notice": "All comparison receipts are encrypted, matter-scoped, and remain review-required.",
        }

    def source_binding(self, comparison_id: str, side: str) -> dict[str, Any]:
        if side not in {"left", "right"}:
            raise IntakeWorkbenchError("document_comparison_side_invalid", 422)
        comparison = self.get(comparison_id).get("comparison") or {}
        binding = dict(comparison.get(side) or {})
        if not binding.get("record_id") or not binding.get("source_hash"):
            raise IntakeWorkbenchError("document_comparison_source_unavailable", 409)
        return {"status": "pass", "binding": binding, "review_required": True}
