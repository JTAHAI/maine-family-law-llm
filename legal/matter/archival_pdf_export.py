"""Local, source-bound archival PDF review derivatives.

The module deliberately produces a conservative PDF *review derivative*, not
an asserted PDF/A conformance artifact.  PDF/A requires a configured converter
and an independent conformance validator; neither is silently substituted with
metadata.  This keeps the useful local export path available while making its
limitation visible in every receipt and in the generated document itself.
"""

from __future__ import annotations

import base64
import hashlib
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


def _identifier(value: Any, field: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not _ID.fullmatch(candidate):
        raise IntakeWorkbenchError(f"{field}_invalid")
    return candidate


def _text(value: Any, field: str, maximum: int) -> str:
    candidate = " ".join(str(value or "").split())
    if not candidate:
        raise IntakeWorkbenchError(f"{field}_required")
    if len(candidate) > maximum:
        raise IntakeWorkbenchError(f"{field}_limit_exceeded")
    return candidate


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _pdf_text(value: str) -> bytes:
    encoded = value.encode("latin-1", "replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _wrap_line(value: str, width: int = 86) -> list[str]:
    words = value.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def _build_review_pdf(*, title: str, export_id: str, items: list[dict[str, Any]]) -> bytes:
    """Build a dependency-free, readable PDF review derivative.

    This intentionally has no PDF/A metadata or claim.  The generated file is
    a bounded local artifact whose exact source hashes and limits are visible.
    """
    lines = [
        "CONFIDENTIAL REVIEW DERIVATIVE — NOT A FILING",
        "PDF/A conformance is NOT verified; inspect conversion limitations in the receipt.",
        f"Review export: {export_id}",
        f"Title: {title}",
        "Review required: source locators and hashes must be checked before use.",
        "",
    ]
    for item in items:
        lines.extend(_wrap_line(f"Item {item['item_id']} · source hash {item['source_hash']}"))
        lines.extend(_wrap_line(f"Locator: {json.dumps(item['source_ref'], sort_keys=True, separators=(',', ':'))}"))
        lines.extend(_wrap_line(f"Reviewer summary: {item['summary']}"))
        lines.append("")
    pages = [lines[offset : offset + 44] for offset in range(0, len(lines), 44)] or [[""]]
    objects: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    page_refs: list[str] = []
    for index, page_lines in enumerate(pages):
        page_object = 4 + (index * 2)
        content_object = page_object + 1
        page_refs.append(f"{page_object} 0 R")
        content_lines = [b"BT", b"/F1 10 Tf", b"48 744 Td"]
        for line_index, line in enumerate(page_lines):
            if line_index:
                content_lines.append(b"0 -16 Td")
            content_lines.append(b"(" + _pdf_text(line) + b") Tj")
        content_lines.append(b"ET")
        stream = b"\n".join(content_lines) + b"\n"
        objects[page_object] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_object} 0 R >>".encode()
        )
        objects[content_object] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >>".encode()
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


class ArchivalPdfExportStore:
    """Encrypted active-matter receipt ledger for bounded review-only PDFs."""

    schema = "maine_family_law_llm.archival_pdf_export.v1"

    def __init__(self, case_root: str | Path, *, encryption_key: str | None = None):
        self.case_root = Path(case_root).resolve()
        self.root = self.case_root / "49_ARCHIVAL_PDF_EXPORTS"
        if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):
            raise IntakeWorkbenchError("archival_pdf_store_unavailable", 409)
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
            raise IntakeWorkbenchError("archival_pdf_store_unavailable", 409) from exc
        if value.get("schema") != self.schema or value.get("scope") != self.scope:
            raise IntakeWorkbenchError("cross_matter_access_denied", 404)
        return value

    def _save(self, value: dict[str, Any]) -> None:
        atomic_write_bytes(self.path, json.dumps(self.encryptor.encrypt_json(value), sort_keys=True).encode(), mode=0o600)

    def _mutate(self, action: str, identifiers: list[str], update: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        with exclusive_file_lock(self.lock):
            value = self._load()
            result = update(value)
            event = {"event_id": f"archival_pdf_{uuid.uuid4().hex}", "at": _now(), "action": action, "ids": identifiers, "previous_hash": value["history"][-1]["hash"] if value["history"] else "", "review_required": True}
            event["hash"] = _hash(event)
            value["history"].append(event)
            value["revision"] += 1
            self._save(value)
            return result

    def inventory(self) -> dict[str, Any]:
        value = self._load()
        return {"exports": [{key: item[key] for key in ("export_id", "pdf_sha256", "manifest_hash", "item_count", "pdf_a_status", "review_required", "created_at")} for item in value["exports"]], "revision": value["revision"], "status": "review_required", "review_required": True, "local_only": True, "automatic_download": False, "pdf_a_conformance": "not_verified"}

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        export_id = _identifier(payload.get("export_id"), "archival_pdf_export_id")
        title = _text(payload.get("title"), "archival_pdf_title", 240)
        if payload.get("acknowledged_pdf_a_limitations") is not True:
            raise IntakeWorkbenchError("archival_pdf_limitations_acknowledgement_required", 409)
        raw_items = payload.get("items")
        if not isinstance(raw_items, list) or not raw_items or len(raw_items) > 50:
            raise IntakeWorkbenchError("archival_pdf_items_invalid")
        items: list[dict[str, Any]] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                raise IntakeWorkbenchError("archival_pdf_items_invalid")
            source_hash = str(raw.get("source_hash") or "").strip().casefold()
            if not _SHA256.fullmatch(source_hash):
                raise IntakeWorkbenchError("archival_pdf_source_hash_invalid")
            source_ref = raw.get("source_ref")
            if not isinstance(source_ref, dict) or not any(str(source_ref.get(key) or "").strip() for key in ("record_id", "source_id", "artifact_id")):
                raise IntakeWorkbenchError("archival_pdf_source_locator_required")
            items.append({"item_id": _identifier(raw.get("item_id"), "archival_pdf_item_id"), "source_hash": source_hash, "source_ref": {str(key): str(value)[:240] for key, value in source_ref.items() if key in {"record_id", "source_id", "artifact_id", "span", "page"}}, "summary": _text(raw.get("summary"), "archival_pdf_summary", 600)})
        if len({item["item_id"] for item in items}) != len(items):
            raise IntakeWorkbenchError("archival_pdf_item_duplicate")

        def update(value: dict[str, Any]) -> dict[str, Any]:
            if any(row["export_id"] == export_id for row in value["exports"]):
                raise IntakeWorkbenchError("archival_pdf_export_exists", 409)
            pdf_bytes = _build_review_pdf(title=title, export_id=export_id, items=items)
            manifest = {"schema": "maine_family_law_llm.archival_pdf_review_export.v1", "export_id": export_id, "title": title, "items": [{key: item[key] for key in ("item_id", "source_hash", "source_ref")} for item in items], "review_required": True, "pdf_a_status": "not_verified", "conversion_limitations": ["No configured PDF/A converter or independent conformance validator is available.", "This is a review derivative, not a filing artifact or preservation certification."], "created_at": _now()}
            manifest["manifest_hash"] = _hash(manifest)
            receipt = {"export_id": export_id, "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(), "manifest_hash": manifest["manifest_hash"], "item_count": len(items), "pdf_a_status": "not_verified", "review_required": True, "automatic_download": False, "created_at": _now()}
            value["exports"].append(receipt)
            return {"export": {"pdf_base64": base64.b64encode(pdf_bytes).decode(), "media_type": "application/pdf", "filename": f"{export_id}-review-derivative.pdf", "manifest": manifest}, "receipt": receipt, "status": "review_required", "local_only": True, "automatic_download": False, "pdf_a_conformance": "not_verified"}

        return self._mutate("archival_pdf_review_export_created", [export_id, *[item["item_id"] for item in items]], update)
