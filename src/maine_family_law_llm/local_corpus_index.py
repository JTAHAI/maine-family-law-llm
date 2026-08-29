"""Local-only, provenance-first content extraction and full-text retrieval.

The case builder keeps the original files read-only.  This module produces only
derived text, inventories, and a SQLite FTS5 index inside a case workspace.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import mailbox
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
import sys
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Callable, Iterable
from xml.etree import ElementTree

from pypdf import PdfReader

from .intake_understanding import parse_intake
from .local_only_boundary import local_only_network_boundary
from .search_normalization import (
    build_search_alias_text,
    normalize_search_query,
    normalized_match_text,
    normalized_snippet,
)


MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
MAX_DECOMPRESSION_RATIO = 200.0
INDEX_NAME = "private_content_index.sqlite"
INVENTORY_JSONL = "FULL_LOCAL_INVENTORY.jsonl"
INVENTORY_CSV = "FULL_LOCAL_INVENTORY.csv"
MAX_COMPATIBILITY_SCAN_RECORDS = 50_000
MAX_COMPATIBILITY_SCAN_CHARS = 256 * 1024 * 1024


_SEARCHABLE_TEXT_STATUSES = {
    "available",
    "partial_native_text",
    "native_text",
    "native_and_ocr_text",
    "ocr_text",
    "searchable",
}


def local_inventory_metrics(records: list[dict[str, Any]]) -> dict[str, int]:
    """Return non-duplicative local inventory counts for the UI and evidence.

    PDF parent rows summarize a document while ``pdf_page`` rows describe the
    actual pages.  Counting both made mixed PDFs appear to require OCR on every
    page.  This helper counts page rows first and only falls back to a parent
    row when no page-level inventory exists.
    """

    page_rows_by_parent: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        if row.get("source_type") not in {"pdf_page", "image_page"}:
            continue
        parent_id = str(row.get("parent_evidence_id") or "")
        if parent_id:
            page_rows_by_parent.setdefault(parent_id, []).append(row)

    ocr_candidate_pages = 0
    for row in records:
        source_type = str(row.get("source_type") or "").lower()
        if source_type in {"pdf_page", "image_page"}:
            if row.get("ocr_status") == "ocr_not_run" and not bool(
                row.get("text_content") or row.get("text_excerpt")
            ):
                ocr_candidate_pages += 1
            continue

        if row.get("ocr_status") != "ocr_not_run":
            continue
        evidence_id = str(row.get("evidence_id") or "")
        if evidence_id and evidence_id in page_rows_by_parent:
            # The page rows are authoritative for mixed native/scanned PDFs.
            continue
        locator = str(row.get("source_locator") or row.get("title") or "").lower()
        metadata = dict(row.get("parser_metadata") or {})
        if source_type in {"png", "jpg", "jpeg", "tif", "tiff", "webp", "heic", "image"} or locator.endswith(
            (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic")
        ):
            ocr_candidate_pages += 1
        elif source_type == "pdf" or locator.endswith(".pdf"):
            ocr_candidate_pages += max(
                1,
                int(metadata.get("image_only_pages") or row.get("page_count") or 0),
            )

    searchable_records = sum(
        1
        for row in records
        if row.get("text_status") in _SEARCHABLE_TEXT_STATUSES
        and bool(row.get("text_content") or row.get("text_excerpt"))
    )
    searchable_pages = sum(
        1
        for row in records
        if row.get("source_type") in {"pdf_page", "image_page"}
        and bool(row.get("text_content") or row.get("text_excerpt"))
    )
    ocr_candidate_documents = sum(
        1
        for row in records
        if row.get("ocr_status") == "ocr_not_run"
        and row.get("source_type") not in {"pdf_page", "image_page"}
    )
    return {
        "ocr_candidate_documents": ocr_candidate_documents,
        "ocr_candidate_pages": ocr_candidate_pages,
        "searchable_records": searchable_records,
        "searchable_pages": searchable_pages,
    }


@dataclass(slots=True)
class ParsedContent:
    text: str = ""
    parser_status: str = "parsed"
    text_status: str = "available"
    ocr_status: str = "not_needed"
    page_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: list[dict[str, Any]] = field(default_factory=list)
    children: list["ParsedContent"] = field(default_factory=list)
    locator: str = ""
    title: str = ""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return _safe_text(html.unescape(value))


def _rtf_to_text(value: str) -> str:
    value = re.sub(r"\\'[0-9a-fA-F]{2}", " ", value)
    value = re.sub(r"\\[a-zA-Z]+-?\d* ?", " ", value)
    return _safe_text(value.replace("{", " ").replace("}", " "))


def _office_xml_text(data: bytes, suffix: str) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if suffix == ".docx":
                names = [name for name in archive.namelist() if name.startswith("word/") and name.endswith(".xml")]
            elif suffix == ".pptx":
                names = [name for name in archive.namelist() if name.startswith("ppt/slides/") and name.endswith(".xml")]
            else:
                names = [name for name in archive.namelist() if name.startswith("xl/") and name.endswith(".xml")]
            pieces: list[str] = []
            for name in names:
                try:
                    root = ElementTree.fromstring(archive.read(name))
                    pieces.extend(node.text or "" for node in root.iter() if node.text)
                except (ElementTree.ParseError, KeyError):
                    continue
            return _safe_text(" ".join(pieces))
    except zipfile.BadZipFile:
        return ""


def _pdf_text(data: bytes) -> tuple[str, int, list[dict[str, Any]]]:
    """Extract native text page-by-page and preserve honest page provenance."""

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return "", 0, []
    page_rows: list[dict[str, Any]] = []
    combined: list[str] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:
            text = ""
            error = f"{exc.__class__.__name__}: {exc}"[:240]
        else:
            error = ""
        combined.append(text)
        page_rows.append(
            {
                "page_number": page_number,
                "text": text,
                "character_count": len(text),
                "word_count": len(re.findall(r"\b\w+\b", text)),
                "native_text": bool(text),
                "ocr_required": not bool(text),
                "parser_error": error,
            }
        )
    return "\n\n".join(text for text in combined if text).strip(), len(page_rows), page_rows


def _parse_archive(data: bytes, locator: str, depth: int) -> ParsedContent:
    if depth >= 2:
        return ParsedContent(parser_status="quarantined", text_status="not_available", metadata={"reason": "archive_depth_limit"})
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            total_size = sum(info.file_size for info in infos)
            if len(infos) > MAX_ARCHIVE_MEMBERS or total_size > MAX_ARCHIVE_BYTES:
                return ParsedContent(parser_status="quarantined", text_status="not_available", metadata={"reason": "archive_limits"})
            children: list[ParsedContent] = []
            skipped_unsafe = 0
            skipped_encrypted = 0
            skipped_ratio = 0
            for info in infos:
                member = Path(info.filename)
                ratio = float(info.file_size) / max(int(info.compress_size or 0), 1)
                if info.is_dir() or ".." in member.parts or member.is_absolute() or info.file_size > MAX_MEMBER_BYTES:
                    skipped_unsafe += 1
                    continue
                if info.flag_bits & 0x1:
                    skipped_encrypted += 1
                    continue
                if ratio > MAX_DECOMPRESSION_RATIO:
                    skipped_ratio += 1
                    continue
                try:
                    child_data = archive.read(info)
                except (KeyError, RuntimeError, zipfile.BadZipFile):
                    skipped_unsafe += 1
                    continue
                child_locator = f"{locator}!{info.filename}"
                child = parse_bytes(child_data, suffix=member.suffix.lower(), locator=child_locator, depth=depth + 1)
                child.locator = child_locator
                child.title = member.name
                child.metadata.update(
                    {
                        "original_content_sha256": _sha256_bytes(child_data),
                        "original_size_bytes": len(child_data),
                        "container_locator": locator,
                    }
                )
                children.append(child)
            text = "\n".join(child.text for child in children if child.text)
            return ParsedContent(
                text=text,
                children=children,
                metadata={
                    "archive_member_count": len(children),
                    "archive_members_declared": len(infos),
                    "archive_skipped_unsafe": skipped_unsafe,
                    "archive_skipped_encrypted": skipped_encrypted,
                    "archive_skipped_decompression_ratio": skipped_ratio,
                    "archive_max_decompression_ratio": MAX_DECOMPRESSION_RATIO,
                },
            )
    except zipfile.BadZipFile:
        return ParsedContent(parser_status="unreadable", text_status="not_available", metadata={"reason": "bad_zip"})


def _parse_email(data: bytes, locator: str, depth: int) -> ParsedContent:
    try:
        message = BytesParser(policy=policy.default).parsebytes(data)
    except Exception:
        return ParsedContent(parser_status="unreadable", text_status="not_available")
    fields = {key.lower().replace("-", "_"): str(message.get(key, "")) for key in ("From", "To", "Cc", "Subject", "Date", "Message-ID", "In-Reply-To", "References")}
    body: list[str] = []
    children: list[ParsedContent] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        payload = part.get_payload(decode=True) or b""
        content_type = part.get_content_type()
        filename = part.get_filename() or ""
        if filename:
            child_locator = f"{locator}!{filename}"
            child = parse_bytes(payload, suffix=Path(filename).suffix.lower(), locator=child_locator, depth=depth + 1)
            child.locator = child_locator
            child.title = filename
            child.metadata.update(
                {
                    "original_content_sha256": _sha256_bytes(payload),
                    "original_size_bytes": len(payload),
                    "container_locator": locator,
                }
            )
            children.append(child)
        elif content_type == "text/plain":
            body.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        elif content_type == "text/html":
            body.append(_html_to_text(payload.decode(part.get_content_charset() or "utf-8", errors="replace")))
    header_lines = [
        f"Subject: {fields.get('subject', '')}",
        f"From: {fields.get('from', '')}",
        f"To: {fields.get('to', '')}",
        f"Cc: {fields.get('cc', '')}",
        f"Date: {fields.get('date', '')}",
    ]
    prefix = "\n".join(value for value in (*header_lines, *body) if value and not value.endswith(": "))
    return ParsedContent(
        text=prefix.strip(),
        metadata=fields | {"attachment_count": len(children), "document_kind": "email"},
        children=children,
        title=fields.get("subject") or "Email message",
    )


def _parse_mbox(data: bytes, locator: str, depth: int) -> ParsedContent:
    if depth >= 2:
        return ParsedContent(parser_status="quarantined", text_status="not_available", metadata={"reason": "mailbox_depth_limit"})
    children: list[ParsedContent] = []
    with tempfile.TemporaryDirectory(prefix="mfl-mbox-") as temporary:
        path = Path(temporary) / "mailbox.mbox"
        path.write_bytes(data)
        try:
            box = mailbox.mbox(path, create=False)
            for index, message in enumerate(box, start=1):
                if index > 5000:
                    break
                raw = message.as_bytes(policy=policy.default)
                child_locator = f"{locator}!message-{index:05d}.eml"
                child = _parse_email(raw, child_locator, depth + 1)
                child.locator = child_locator
                child.title = str(message.get("Subject") or f"Email message {index}")
                children.append(child)
        except Exception as exc:
            return ParsedContent(parser_status="unreadable", text_status="not_available", metadata={"reason": f"mbox_error:{exc.__class__.__name__}"})
    return ParsedContent(
        text="\n\n".join(child.text for child in children if child.text),
        children=children,
        metadata={"mailbox_message_count": len(children), "document_kind": "mailbox"},
    )


def parse_bytes(data: bytes, *, suffix: str, locator: str, depth: int = 0) -> ParsedContent:
    suffix = suffix.lower()
    if len(data) > MAX_MEMBER_BYTES:
        return ParsedContent(parser_status="quarantined", text_status="not_available", metadata={"reason": "member_size_limit"})
    if data.startswith(b"MZ"):
        return ParsedContent(
            parser_status="quarantined",
            text_status="not_available",
            metadata={"reason": "executable_content_blocked"},
        )
    if suffix == ".pdf":
        if not data.lstrip().startswith(b"%PDF-"):
            return ParsedContent(
                parser_status="quarantined",
                text_status="not_available",
                metadata={"reason": "extension_content_mismatch"},
            )
        text, page_count, pages = _pdf_text(data)
        if page_count == 0:
            return ParsedContent(
                parser_status="unreadable",
                text_status="not_available",
                metadata={"reason": "malformed_pdf"},
            )
        image_only_pages = sum(1 for page in pages if not page["native_text"])
        if text and image_only_pages:
            text_status = "partial_native_text"
        else:
            text_status = "available" if text else "not_available"
        return ParsedContent(
            text=text,
            page_count=page_count,
            pages=pages,
            text_status=text_status,
            ocr_status="ocr_not_run" if image_only_pages else "not_needed",
            metadata={
                "native_text_pages": page_count - image_only_pages,
                "image_only_pages": image_only_pages,
                "searchable_pages": page_count - image_only_pages,
                "page_extraction": "native_pypdf",
            },
        )
    if suffix == ".eml":
        return _parse_email(data, locator, depth)
    if suffix in {".mbox", ".mbx"}:
        return _parse_mbox(data, locator, depth)
    if suffix in {".zip"}:
        return _parse_archive(data, locator, depth)
    if suffix in {".txt", ".md", ".csv", ".tsv", ".log", ".ics"}:
        return ParsedContent(text=data.decode("utf-8", errors="replace"))
    if suffix == ".json":
        decoded = data.decode("utf-8", errors="replace")
        try:
            value = json.loads(decoded)
            return ParsedContent(text=json.dumps(value, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            return ParsedContent(text=decoded, parser_status="parsed_with_warning", metadata={"warning": "invalid_json"})
    if suffix == ".xml":
        decoded = data.decode("utf-8", errors="replace")
        return ParsedContent(text=_html_to_text(decoded))
    if suffix in {".html", ".htm"}:
        return ParsedContent(text=_html_to_text(data.decode("utf-8", errors="replace")))
    if suffix == ".rtf":
        return ParsedContent(text=_rtf_to_text(data.decode("utf-8", errors="replace")))
    if suffix in {".docx", ".xlsx", ".pptx"}:
        if not zipfile.is_zipfile(io.BytesIO(data)):
            return ParsedContent(
                parser_status="quarantined",
                text_status="not_available",
                metadata={"reason": "extension_content_mismatch"},
            )
        text = _office_xml_text(data, suffix)
        return ParsedContent(
            text=text,
            parser_status="parsed" if text else "unreadable",
            text_status="available" if text else "not_available",
            metadata={} if text else {"reason": "malformed_office_document"},
        )
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic"}:
        return ParsedContent(parser_status="metadata_only", text_status="not_available", ocr_status="ocr_not_run", metadata={"media_kind": "image"})
    if suffix in {".mp3", ".m4a", ".wav", ".mp4", ".mov", ".avi", ".webm"}:
        return ParsedContent(parser_status="metadata_only", text_status="not_available", metadata={"media_kind": "audio_video", "transcription_status": "not_run"})
    return ParsedContent(parser_status="unsupported", text_status="not_available")


def parse_path(path: Path) -> ParsedContent:
    try:
        data = path.read_bytes()
    except OSError:
        return ParsedContent(parser_status="unreadable", text_status="not_available")
    parsed = parse_bytes(data, suffix=path.suffix.lower(), locator=path.name)
    parsed.locator = path.name
    parsed.title = path.name
    return parsed


DATE_VALUE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-](?:\d{2}|\d{4})|"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}(?:,\s*\d{4})?)\b",
    re.IGNORECASE,
)
CASE_NUMBER_PATTERN = re.compile(r"\b(?:docket|case)\s*(?:no\.?|number|#)?\s*[:#-]?\s*([A-Z0-9-]{5,})\b", re.IGNORECASE)


def _document_profile(text: str, title: str, suffix: str) -> dict[str, Any]:
    """Infer useful intake metadata without making a legal conclusion."""

    sample = f"{title}\n{text[:20000]}".lower()
    kinds: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("court_order", ("ordered and adjudged", "court order", "judgment", "it is hereby ordered")),
        ("motion_or_filing", ("motion to", "complaint for", "petition for", "plaintiff", "defendant")),
        ("hearing_notice", ("notice of hearing", "hearing date", "you are hereby notified")),
        ("email", ("subject:", "from:", "to:", "message-id")),
        ("message_export", ("text message", "sent from my iphone", "conversation export")),
        ("school_record", ("school", "teacher", "attendance", "report card", "iep")),
        ("medical_or_therapy_record", ("patient", "diagnosis", "treatment", "therapy", "clinical", "provider")),
        ("financial_record", ("pay stub", "gross income", "net income", "bank statement", "tax return")),
        ("police_or_safety_record", ("police report", "incident report", "protection from abuse", "domestic violence")),
        ("family_communication", ("parenting app", "ourfamilywizard", "talkingparents", "exchange", "pickup", "drop-off")),
    )
    document_kind = "unknown"
    for label, terms in kinds:
        if any(term in sample for term in terms):
            document_kind = label
            break
    if document_kind == "unknown":
        document_kind = {
            ".eml": "email",
            ".pdf": "pdf_document",
            ".docx": "word_document",
            ".xlsx": "spreadsheet",
            ".pptx": "presentation",
            ".zip": "archive",
        }.get(suffix, "file")
    issue_signals: list[str] = []
    issue_terms = {
        "parental_rights": ("parental rights", "custody", "primary residence", "parenting time"),
        "contact_or_exchange": ("contact", "visitation", "exchange", "pickup", "drop-off", "denied contact"),
        "possible_enforcement": ("contempt", "violation", "not following", "failed to comply", "obstruction", "interference"),
        "child_support": ("child support", "arrears", "support payment", "income affidavit"),
        "safety_or_pfa": ("protection from abuse", "domestic violence", "unsafe", "threat", "assault"),
        "school_or_health": ("school", "medical", "therapy", "counselor", "doctor"),
        "service_or_deadline": ("served", "service", "summons", "deadline", "hearing date"),
    }
    for label, terms in issue_terms.items():
        if any(term in sample for term in terms):
            issue_signals.append(label)
    dates = list(dict.fromkeys(DATE_VALUE_PATTERN.findall(text)))[:50]
    case_numbers = list(dict.fromkeys(match.group(1) for match in CASE_NUMBER_PATTERN.finditer(text)))[:10]
    headings = []
    for line in text.splitlines()[:250]:
        cleaned = line.strip()
        if 3 <= len(cleaned) <= 100 and (cleaned.isupper() or cleaned.endswith(":")):
            headings.append(cleaned.rstrip(":"))
    return {
        "document_kind": document_kind,
        "issue_signals": issue_signals,
        "dates_detected": dates,
        "case_numbers_detected": case_numbers,
        "headings_detected": list(dict.fromkeys(headings))[:30],
        "character_count": len(text),
        "word_count": len(re.findall(r"\b\w+\b", text)),
        "intake_parser": "deterministic_local_v2",
        "intake_interpretation_limit": "Metadata and routing signals only; not a finding of fact or law.",
    }


def _page_rows(parent: dict[str, Any], parsed: ParsedContent) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in parsed.pages:
        page_number = int(page.get("page_number") or 0)
        page_text = str(page.get("text") or "")
        page_row = dict(parent)
        page_row.update(
            {
                "evidence_id": f"{parent['evidence_id']}-P{page_number:04d}",
                "title": f"{parent.get('title') or parent['evidence_id']} — page {page_number}",
                "source_type": "pdf_page",
                "source_locator": f"{parent.get('source_locator', '')}#page={page_number}",
                "parent_evidence_id": parent["evidence_id"],
                "page_number": page_number,
                "page_count": 1,
                "parser_status": "parsed" if page_text else "image_only_page",
                "text_status": "available" if page_text else "not_available",
                "ocr_status": "not_needed" if page_text else "ocr_not_run",
                "text_content": page_text,
                "text_excerpt": page_text[:1200],
                "parser_metadata": {
                    "native_text": bool(page_text),
                    "ocr_required": not bool(page_text),
                    "character_count": int(page.get("character_count") or 0),
                    "word_count": int(page.get("word_count") or 0),
                },
                "duplicate_of": "",
            }
        )
        rows.append(page_row)
    return rows


def _flatten_children(parent: dict[str, Any], parsed: ParsedContent, prefix: str = "A") -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for child_index, child in enumerate(parsed.children, start=1):
        child_id = f"{parent['evidence_id']}-{prefix}{child_index:03d}"
        child_row = dict(parent)
        child_row.update(
            {
                "evidence_id": child_id,
                "title": child.title or f"Attachment {child_index}",
                "source_locator": child.locator,
                "parent_evidence_id": parent["evidence_id"],
                "source_hash": _sha256_bytes(child.text.encode("utf-8")) if child.text else "",
                "parser_status": child.parser_status,
                "text_status": child.text_status,
                "ocr_status": child.ocr_status,
                "page_count": child.page_count,
                "page_number": 0,
                "text_content": child.text,
                "text_excerpt": child.text[:1200],
                "parser_metadata": dict(child.metadata) | _document_profile(child.text, child.title, Path(child.title).suffix.lower()),
                "duplicate_of": "",
            }
        )
        flattened.append(child_row)
        flattened.extend(_page_rows(child_row, child))
        flattened.extend(_flatten_children(child_row, child, prefix=f"{prefix}{child_index:03d}A"))
    return flattened


def _write_inventory(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row if key != "text_content"})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_fts(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(".tmp.sqlite")
    if temporary.exists():
        temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE records USING fts5("
            "evidence_id UNINDEXED, title, source_type UNINDEXED, source_locator UNINDEXED, "
            "parent_evidence_id UNINDEXED, page_number UNINDEXED, parser_status UNINDEXED, "
            "ocr_status UNINDEXED, document_kind, issue_lanes, dates_detected, case_numbers, "
            "text, normalized_text)"
        )
        for row in rows:
            metadata = dict(row.get("parser_metadata") or {})
            source_text = str(row.get("text_content") or "")
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["evidence_id"],
                    row.get("title", ""),
                    row.get("source_type", ""),
                    row.get("source_locator", ""),
                    row.get("parent_evidence_id", ""),
                    int(row.get("page_number") or 0),
                    row.get("parser_status", ""),
                    row.get("ocr_status", ""),
                    metadata.get("document_kind", ""),
                    ", ".join(row.get("issue_lanes", []) or metadata.get("issue_signals", []) or []),
                    " ".join(metadata.get("dates_detected", []) or []),
                    " ".join(metadata.get("case_numbers_detected", []) or []),
                    source_text,
                    build_search_alias_text(source_text),
                ),
            )
        connection.commit()
    finally:
        connection.close()
    temporary.replace(path)


def rebuild_local_content_index(case_root: Path) -> dict[str, Any]:
    """Create a private, page-aware full-text index without modifying evidence."""

    manifest_path = case_root / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json"
    if not manifest_path.exists():
        return {"result": "unavailable", "reason": "source_manifest_missing"}
    source_rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    exact_hashes: dict[str, str] = {}
    source_mutation_pass = True
    parse_failures: list[dict[str, str]] = []
    with local_only_network_boundary():
        for source in source_rows:
            source_path = Path(str(source.get("source_path", "")))
            if not source_path.exists() or not source_path.is_file():
                parse_failures.append(
                    {"evidence_id": str(source.get("evidence_id") or ""), "reason": "source_missing"}
                )
                continue
            before_hash = str(source.get("source_hash") or "")
            parsed = parse_path(source_path)
            after_hash = _sha256_bytes(source_path.read_bytes())
            source_mutation_pass = source_mutation_pass and (not before_hash or before_hash == after_hash)
            row = dict(source)
            metadata = dict(parsed.metadata)
            metadata.update(_document_profile(parsed.text, source_path.name, source_path.suffix.lower()))
            row.update(
                {
                    "title": row.get("subject") or source_path.name,
                    "source_locator": source_path.name,
                    "parent_evidence_id": "",
                    "page_number": 0,
                    "parser_status": parsed.parser_status,
                    "text_status": parsed.text_status,
                    "ocr_status": parsed.ocr_status,
                    "page_count": parsed.page_count or row.get("page_count", 0),
                    "text_content": parsed.text,
                    "text_excerpt": parsed.text[:1200] or row.get("text_excerpt", ""),
                    "parser_metadata": metadata,
                }
            )
            if before_hash and before_hash in exact_hashes:
                row["duplicate_of"] = exact_hashes[before_hash]
            else:
                if before_hash:
                    exact_hashes[before_hash] = str(row["evidence_id"])
                row["duplicate_of"] = ""
            records.append(row)
            records.extend(_page_rows(row, parsed))
            records.extend(_flatten_children(row, parsed))
            if parsed.parser_status in {"unreadable", "unsupported", "quarantined"}:
                parse_failures.append(
                    {
                        "evidence_id": str(row.get("evidence_id") or ""),
                        "reason": parsed.parser_status,
                    }
                )
    index_root = case_root / "04_INDEXES"
    _write_inventory(index_root / INVENTORY_JSONL, records)
    _write_csv(index_root / INVENTORY_CSV, records)
    (index_root / "private_search_index.json").write_text(
        json.dumps(records, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_fts(index_root / INDEX_NAME, records)
    inventory_metrics = local_inventory_metrics(records)
    ocr_candidates = [
        row
        for row in records
        if row.get("ocr_status") == "ocr_not_run"
        and row.get("source_type") not in {"pdf_page", "image_page"}
    ]
    searchable_pages = inventory_metrics["searchable_pages"]
    image_only_pages = inventory_metrics["ocr_candidate_pages"]
    proof = {
        "result": "PASS" if source_mutation_pass else "FAIL",
        "source_evidence_modified": False,
        "source_mutation_pass": source_mutation_pass,
        "records_indexed": len(records),
        "root_documents": sum(1 for row in records if not row.get("parent_evidence_id")),
        "page_records": sum(1 for row in records if row.get("source_type") == "pdf_page"),
        "searchable_pages": searchable_pages,
        "image_only_pages": image_only_pages,
        "attachment_or_archive_children": sum(
            1
            for row in records
            if row.get("parent_evidence_id") and row.get("source_type") != "pdf_page"
        ),
        "document_kind_counts": dict(
            sorted(
                {
                    kind: sum(
                        1
                        for row in records
                        if dict(row.get("parser_metadata") or {}).get("document_kind") == kind
                    )
                    for kind in {
                        str(dict(row.get("parser_metadata") or {}).get("document_kind") or "unknown")
                        for row in records
                    }
                }.items()
            )
        ),
        "parse_failures": parse_failures[:200],
        "fts5_index": INDEX_NAME,
        "cloud_calls_made": 0,
        "network_boundary": "outbound_connections_dns_datagrams_blocked_accept_preserved",
        "ocr_candidates": len(ocr_candidates),
        "ocr_candidate_documents": inventory_metrics["ocr_candidate_documents"],
        "ocr_candidate_pages": inventory_metrics["ocr_candidate_pages"],
        "inventory_status": "ocr_choice_required" if inventory_metrics["ocr_candidate_pages"] else ("ready_with_warnings" if parse_failures else "ready"),
        "ocr_default": "not_run",
        "transcription_default": "not_run",
        "intake_parser": "deterministic_local_v2",
    }
    proof_path = case_root / "15_PROOF_VALIDATION" / "LOCAL_CORPUS_INDEX_PROOF.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof | {"proof_path": str(proof_path)}


def _ocr_candidates(case_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index_path = case_root / "04_INDEXES" / "private_search_index.json"
    if not index_path.exists():
        return [], []
    records = json.loads(index_path.read_text(encoding="utf-8"))
    candidates = [
        row
        for row in records
        if row.get("ocr_status") == "ocr_not_run" and row.get("source_type") != "pdf_page"
    ]
    return records, candidates


def _first_existing_executable(candidates: Iterable[str | Path]) -> str:
    for candidate in candidates:
        raw = str(candidate or "").strip()
        if raw and Path(raw).is_file():
            return raw
    return ""


def _bundled_tesseract_candidates() -> list[Path]:
    # Engine assets are beside the executable. Source modules can be loaded
    # from _internal/src in a frozen build, so their parent is not the bundle.
    root = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2]
    )
    return [
        root / "store" / "tesseract" / "tesseract.exe",
        root / "tesseract" / "tesseract.exe",
        root / "bin" / "tesseract.exe",
    ]


def _windows_tesseract_candidates() -> list[Path]:
    roots = [
        os.environ.get("LOCALAPPDATA", ""),
        os.environ.get("ProgramFiles", ""),
        os.environ.get("ProgramFiles(x86)", ""),
    ]
    candidates: list[Path] = []
    for root in roots:
        if not root:
            continue
        base = Path(root)
        candidates.extend(
            [
                base / "Programs" / "Tesseract-OCR" / "tesseract.exe",
                base / "Tesseract-OCR" / "tesseract.exe",
            ]
        )
    return candidates


def _pdfium_available() -> bool:
    try:
        import pypdfium2  # noqa: F401
    except Exception:
        return False
    return True


def local_ocr_engine_status() -> dict[str, Any]:
    """Describe local OCR dependencies without making a network request."""

    frozen = getattr(sys, "frozen", False)
    tesseract = os.environ.get("MFL_LOCAL_TESSERACT", "").strip() or _first_existing_executable(_bundled_tesseract_candidates())
    if not frozen and not tesseract:
        tesseract = shutil.which("tesseract") or _first_existing_executable(_windows_tesseract_candidates())
    pdftoppm = os.environ.get("MFL_LOCAL_PDFTOPPM", "").strip() or ("" if frozen else shutil.which("pdftoppm")) or ""
    mutool = os.environ.get("MFL_LOCAL_MUTOOL", "").strip() or ("" if frozen else shutil.which("mutool")) or ""
    pdfium = _pdfium_available()
    version = ""
    if tesseract:
        try:
            completed = subprocess.run(
                [tesseract, "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            version = (completed.stdout or completed.stderr).splitlines()[0].strip()
        except Exception:
            version = "installed; version unavailable"
    if pdftoppm:
        renderer = pdftoppm
        renderer_kind = "pdftoppm"
    elif mutool:
        renderer = mutool
        renderer_kind = "mutool"
    elif pdfium:
        renderer = "bundled_python_pdfium"
        renderer_kind = "pypdfium2"
    else:
        renderer = ""
        renderer_kind = ""
    return {
        "available": bool(tesseract),
        "tesseract": tesseract,
        "tesseract_version": version,
        "pdf_renderer": renderer,
        "pdf_renderer_kind": renderer_kind,
        "image_ocr_available": bool(tesseract),
        "pdf_ocr_available": bool(tesseract and renderer_kind),
        "bundled_pdf_renderer": bool(pdfium),
        "local_only": True,
        "network_used": False,
    }


def _candidate_files(candidates: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": str(row.get("evidence_id") or ""),
            "source_locator": str(row.get("source_locator") or ""),
            "page_count": int(row.get("page_count") or 0),
            "source_hash": str(row.get("source_hash") or ""),
            "source_type": str(row.get("source_type") or ""),
        }
        for row in candidates[:limit]
    ]


def local_ocr_choice(case_root: Path, *, approved: bool) -> dict[str, Any]:
    """Record an explicit OCR decision without ever making OCR automatic."""

    _, candidates = _ocr_candidates(case_root)
    candidate_files = _candidate_files(candidates)
    if not candidates:
        return {
            "status": "not_needed",
            "message": "All detected pages already contain searchable text. OCR is not needed.",
            "candidates": 0,
            "candidate_pages": 0,
            "candidate_files": [],
            "engine": local_ocr_engine_status(),
        }
    candidate_pages = sum(max(1, int(row.get("page_count") or 0)) for row in candidates)
    if not approved:
        return {
            "status": "declined",
            "message": "Scanned pages remain unsearchable for now.",
            "candidates": len(candidates),
            "candidate_pages": candidate_pages,
            "candidate_files": candidate_files,
            "engine": local_ocr_engine_status(),
        }
    engine = local_ocr_engine_status()
    if not engine["available"]:
        return {
            "status": "unavailable",
            "message": "Local OCR is not installed. Install Tesseract locally, then retry. Nothing was uploaded or transmitted.",
            "candidates": len(candidates),
            "candidate_pages": candidate_pages,
            "candidate_files": candidate_files,
            "engine": engine,
            "ocr_derived_text_created": 0,
        }
    return {
        "status": "ready",
        "message": "Local OCR is ready. Processing will stay on this computer.",
        "candidates": len(candidates),
        "candidate_pages": candidate_pages,
        "candidate_files": candidate_files,
        "engine": engine,
    }


def _email_attachment_bytes(data: bytes, name: str) -> bytes:
    message = BytesParser(policy=policy.default).parsebytes(data)
    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename() or ""
        if filename == name:
            return part.get_payload(decode=True) or b""
    raise FileNotFoundError(name)


def _candidate_bytes(row: dict[str, Any]) -> tuple[bytes, str]:
    source_path = Path(str(row.get("source_path") or ""))
    if source_path.is_symlink() or not source_path.is_file():
        raise FileNotFoundError("source_file_missing")
    if source_path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("source_file_too_large")
    data = source_path.read_bytes()
    suffix = source_path.suffix.lower()
    locator = str(row.get("source_locator") or source_path.name)
    parts = locator.split("!")
    if len(parts) > 3:
        raise ValueError("archive_depth_limit")
    for member_name in parts[1:]:
        if suffix == ".zip":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_ARCHIVE_MEMBERS or sum(info.file_size for info in infos) > MAX_ARCHIVE_BYTES:
                    raise ValueError("archive_limits")
                info = archive.getinfo(member_name)
                member = Path(info.filename)
                ratio = float(info.file_size) / max(int(info.compress_size or 0), 1)
                if (
                    member.is_absolute()
                    or ".." in member.parts
                    or info.is_dir()
                    or info.flag_bits & 0x1
                    or info.file_size > MAX_MEMBER_BYTES
                    or ratio > MAX_DECOMPRESSION_RATIO
                ):
                    raise ValueError("unsafe_archive_member")
                data = archive.read(info)
        elif suffix == ".eml":
            data = _email_attachment_bytes(data, member_name)
            if len(data) > MAX_MEMBER_BYTES:
                raise ValueError("unsafe_email_attachment")
        else:
            raise ValueError("nested_member_unsupported")
        suffix = Path(member_name).suffix.lower()
    return data, suffix


def _tesseract_tsv(tesseract: str, image_path: Path, *, language: str) -> tuple[str, float | None]:
    completed = subprocess.run(
        [tesseract, str(image_path), "stdout", "-l", language, "tsv"],
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "tesseract_failed").strip()[:500])
    lines: dict[tuple[str, str, str, str], list[str]] = {}
    confidences: list[float] = []
    for raw in completed.stdout.splitlines()[1:]:
        fields = raw.split("\t")
        if len(fields) < 12:
            continue
        text = fields[11].strip()
        if not text:
            continue
        key = (fields[1], fields[2], fields[3], fields[4])
        lines.setdefault(key, []).append(text)
        try:
            confidence = float(fields[10])
            if confidence >= 0:
                confidences.append(confidence)
        except ValueError:
            pass
    text = "\n".join(" ".join(words) for words in lines.values()).strip()
    confidence = sum(confidences) / len(confidences) if confidences else None
    return text, confidence


def _render_pdf(data: bytes, work_dir: Path, engine: dict[str, Any]) -> list[Path]:
    source = work_dir / "source.pdf"
    source.write_bytes(data)
    renderer = str(engine.get("pdf_renderer") or "")
    kind = str(engine.get("pdf_renderer_kind") or "")
    if not renderer:
        raise RuntimeError("local_pdf_renderer_not_installed")
    if kind == "pypdfium2":
        try:
            import pypdfium2 as pdfium
        except Exception as exc:
            raise RuntimeError("local_pdf_renderer_not_installed") from exc
        document = pdfium.PdfDocument(str(source))
        pages: list[Path] = []
        try:
            for index in range(len(document)):
                page = document[index]
                bitmap = None
                try:
                    bitmap = page.render(scale=200 / 72)
                    image = bitmap.to_pil()
                    output = work_dir / f"page-{index + 1:04d}.png"
                    image.save(output, format="PNG")
                    pages.append(output)
                finally:
                    if bitmap is not None and hasattr(bitmap, "close"):
                        bitmap.close()
                    if hasattr(page, "close"):
                        page.close()
        finally:
            if hasattr(document, "close"):
                document.close()
        if not pages:
            raise RuntimeError("pdf_render_produced_no_pages")
        return pages
    if kind == "pdftoppm":
        prefix = work_dir / "page"
        command = [renderer, "-png", "-r", "200", str(source), str(prefix)]
        pattern = "page-*.png"
    else:
        command = [renderer, "draw", "-r", "200", "-o", str(work_dir / "page-%04d.png"), str(source)]
        pattern = "page-*.png"
    completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=900)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or "pdf_render_failed").strip()[:500])
    pages = sorted(work_dir.glob(pattern))
    if not pages:
        raise RuntimeError("pdf_render_produced_no_pages")
    return pages


def _ocr_one(
    row: dict[str, Any],
    engine: dict[str, Any],
    *,
    language: str,
    page_numbers: set[int] | None = None,
) -> dict[str, Any]:
    data, suffix = _candidate_bytes(row)
    tesseract = str(engine.get("tesseract") or "")
    if not tesseract:
        raise RuntimeError("local_ocr_not_installed")
    with tempfile.TemporaryDirectory(prefix="mfl-local-ocr-") as temporary:
        work_dir = Path(temporary)
        if suffix == ".pdf":
            rendered = _render_pdf(data, work_dir, engine)
            selected_pages = [
                (number, image_path)
                for number, image_path in enumerate(rendered, start=1)
                if not page_numbers or number in page_numbers
            ]
            if not selected_pages:
                raise RuntimeError("ocr_candidate_pages_not_found")
        elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}:
            image = work_dir / f"source{suffix if suffix != '.jpeg' else '.jpg'}"
            image.write_bytes(data)
            selected_pages = [(1, image)]
        else:
            raise RuntimeError(f"ocr_format_unsupported:{suffix or 'unknown'}")
        page_results: list[dict[str, Any]] = []
        texts: list[str] = []
        confidences: list[float] = []
        for page_number, image_path in selected_pages:
            text, confidence = _tesseract_tsv(tesseract, image_path, language=language)
            texts.append(text)
            if confidence is not None:
                confidences.append(confidence)
            page_results.append(
                {
                    "page_number": page_number,
                    "confidence": round(confidence, 2) if confidence is not None else None,
                    "character_count": len(text),
                    "text": text,
                    "text_excerpt": text[:500],
                }
            )
        combined = "\n\n".join(text for text in texts if text).strip()
        if not combined:
            raise RuntimeError("ocr_returned_no_text")
        return {
            "text": combined,
            "pages": page_results,
            "page_count": len(selected_pages),
            "confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
        }


def run_local_ocr(
    case_root: Path,
    *,
    language: str = "eng",
    progress: Callable[[dict[str, Any]], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """OCR explicitly approved candidates and rebuild the local FTS5 index.

    This function performs only local file reads, local subprocess execution,
    and writes to the matter's derived ``04_INDEXES`` folder. It never mutates
    original records and executes inside the no-network boundary.
    """

    records, candidates = _ocr_candidates(case_root)
    choice = local_ocr_choice(case_root, approved=True)
    if choice["status"] != "ready":
        return choice
    engine = dict(choice["engine"])
    completed_count = 0
    failed: list[dict[str, str]] = []
    completed_page_rows: list[dict[str, Any]] = []
    completed_parent_ids: set[str] = set()
    cancelled = False
    total = len(candidates)
    missing_pages_by_parent: dict[str, set[int]] = {}
    for row in records:
        if row.get("source_type") != "pdf_page" or row.get("ocr_status") != "ocr_not_run":
            continue
        parent_id = str(row.get("parent_evidence_id") or "")
        page_number = int(row.get("page_number") or 0)
        if parent_id and page_number:
            missing_pages_by_parent.setdefault(parent_id, set()).add(page_number)
    completed_page_keys: set[tuple[str, int]] = set()
    with local_only_network_boundary():
        for position, candidate in enumerate(candidates, start=1):
            if should_cancel and should_cancel():
                cancelled = True
                break
            if progress:
                progress(
                    {
                        "status": "running",
                        "current": position,
                        "total": total,
                        "processed_documents": completed_count,
                        "processed_pages": len(completed_page_rows),
                        "evidence_id": str(candidate.get("evidence_id") or ""),
                        "source_locator": str(candidate.get("source_locator") or ""),
                    }
                )
            try:
                parent_id = str(candidate.get("evidence_id") or "")
                page_numbers = missing_pages_by_parent.get(parent_id)
                result = _ocr_one(candidate, engine, language=language, page_numbers=page_numbers)
            except Exception as exc:
                candidate["ocr_status"] = "ocr_failed"
                candidate["parser_status"] = "ocr_failed"
                metadata = dict(candidate.get("parser_metadata") or {})
                metadata["ocr_error"] = str(exc)[:500]
                metadata["ocr_engine"] = engine.get("tesseract_version") or "tesseract"
                candidate["parser_metadata"] = metadata
                failed.append(
                    {
                        "evidence_id": str(candidate.get("evidence_id") or ""),
                        "source_locator": str(candidate.get("source_locator") or ""),
                        "error": str(exc)[:500],
                    }
                )
                continue
            native_text = str(candidate.get("text_content") or "").strip()
            merged_text = "\n\n".join(value for value in (native_text, result["text"]) if value).strip()
            candidate["text_content"] = merged_text
            candidate["text_excerpt"] = merged_text[:1200]
            candidate["text_status"] = "native_and_ocr_text" if native_text else "ocr_text"
            candidate["ocr_status"] = "ocr_completed"
            candidate["parser_status"] = "ocr_completed"
            candidate["page_count"] = result["page_count"]
            metadata = dict(candidate.get("parser_metadata") or {})
            metadata.update(
                {
                    "ocr_derived": True,
                    "ocr_engine": engine.get("tesseract_version") or "tesseract",
                    "ocr_language": language,
                    "ocr_confidence": result["confidence"],
                    "ocr_pages": result["pages"],
                    "ocr_page_numbers": [int(page.get("page_number") or 0) for page in result["pages"]],
                    "native_text_preserved": bool(native_text),
                    "local_only": True,
                    "network_used": False,
                }
            )
            candidate["parser_metadata"] = metadata
            parent_id = str(candidate.get("evidence_id") or "")
            completed_parent_ids.add(parent_id)
            for page in result.get("pages", []):
                page_number = int(page.get("page_number") or 0)
                page_text = str(page.get("text") or page.get("text_excerpt") or "")
                page_row = dict(candidate)
                page_row.update(
                    {
                        "evidence_id": f"{parent_id}-P{page_number:04d}",
                        "title": f"{candidate.get('title') or parent_id} — page {page_number}",
                        "source_type": "pdf_page" if str(candidate.get("source_locator") or "").lower().endswith(".pdf") else "image_page",
                        "source_locator": f"{candidate.get('source_locator', '')}#page={page_number}",
                        "parent_evidence_id": parent_id,
                        "page_number": page_number,
                        "page_count": 1,
                        "parser_status": "ocr_completed",
                        "text_status": "ocr_text",
                        "ocr_status": "ocr_completed",
                        "text_content": page_text,
                        "text_excerpt": page_text[:1200],
                        "parser_metadata": {
                            "ocr_derived": True,
                            "ocr_engine": engine.get("tesseract_version") or "tesseract",
                            "ocr_language": language,
                            "ocr_confidence": page.get("confidence"),
                            "character_count": int(page.get("character_count") or len(page_text)),
                            "local_only": True,
                            "network_used": False,
                        },
                        "duplicate_of": "",
                    }
                )
                completed_page_rows.append(page_row)
                completed_page_keys.add((parent_id, page_number))
            completed_count += 1
            if progress:
                progress(
                    {
                        "status": "running",
                        "current": position,
                        "total": total,
                        "processed_documents": completed_count,
                        "processed_pages": len(completed_page_rows),
                        "source_locator": str(candidate.get("source_locator") or ""),
                    }
                )
    if completed_parent_ids:
        records = [
            row
            for row in records
            if not (
                row.get("source_type") in {"pdf_page", "image_page"}
                and (
                    str(row.get("parent_evidence_id") or ""),
                    int(row.get("page_number") or 0),
                )
                in completed_page_keys
            )
        ]
        records.extend(completed_page_rows)
    index_root = case_root / "04_INDEXES"
    _write_inventory(index_root / INVENTORY_JSONL, records)
    _write_csv(index_root / INVENTORY_CSV, records)
    (index_root / "private_search_index.json").write_text(
        json.dumps(records, indent=2, sort_keys=True), encoding="utf-8"
    )
    _write_fts(index_root / INDEX_NAME, records)
    remaining_metrics = local_inventory_metrics(records)
    remaining = remaining_metrics["ocr_candidate_documents"]
    summary = {
        "status": "cancelled" if cancelled else ("completed_with_warnings" if failed else "completed"),
        "completed": completed_count,
        "failed": len(failed),
        "remaining": remaining,
        "remaining_candidate_documents": remaining,
        "remaining_candidate_pages": remaining_metrics["ocr_candidate_pages"],
        "searchable_records": remaining_metrics["searchable_records"],
        "searchable_pages": remaining_metrics["searchable_pages"],
        "total_candidates": total,
        "failures": failed[:100],
        "engine": engine,
        "local_only": True,
        "network_used": False,
        "source_documents_modified": False,
    }
    if progress:
        progress(summary)
    proof_path = case_root / "15_PROOF_VALIDATION" / "LOCAL_OCR_PROOF.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary | {"proof_path": str(proof_path)}

def _fts_terms(value: str) -> list[str]:
    return list(normalize_search_query(value).terms)


def _clean_snippet(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fts_columns(connection: sqlite3.Connection) -> set[str]:
    try:
        return {str(row[1]) for row in connection.execute("PRAGMA table_info(records)").fetchall()}
    except sqlite3.DatabaseError:
        return set()


def _search_rows(connection: sqlite3.Connection, expression: str, limit: int) -> list[sqlite3.Row]:
    normalized_select = (
        "normalized_text" if "normalized_text" in _fts_columns(connection) else "'' AS normalized_text"
    )
    return connection.execute(
        "SELECT evidence_id, title, source_type, source_locator, parent_evidence_id, "
        "page_number, parser_status, ocr_status, document_kind, issue_lanes, text, "
        f"{normalized_select}, snippet(records, 12, '', '', ' … ', 36) AS snippet "
        "FROM records WHERE records MATCH ? ORDER BY bm25(records) LIMIT ?",
        (expression, max(1, min(limit, 300))),
    ).fetchall()


def _inventory_rows(case_root: Path) -> list[dict[str, Any]]:
    path = case_root / "04_INDEXES" / "private_search_index.json"
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def _matches_record_type(row: dict[str, Any], record_type_filter: str) -> bool:
    if record_type_filter != "pdf":
        return True
    source_type = str(row.get("source_type") or "").lower()
    document_kind = str(row.get("document_kind") or dict(row.get("parser_metadata") or {}).get("document_kind") or "").lower()
    locator = str(row.get("source_locator") or "").lower()
    return source_type in {"pdf", "pdf_page"} or document_kind == "pdf" or ".pdf" in locator


def _match_details(text: str, target: str, terms: list[str]) -> tuple[bool, list[str], str, float, str]:
    aliases = normalized_match_text(text)
    raw_canonical = normalize_search_query(text).canonical
    phrase = normalize_search_query(target).canonical
    matched_terms = [
        term for term in terms if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", aliases)
    ]
    exact_phrase = bool(phrase and phrase in aliases)
    required_terms = 1 if len(terms) <= 1 else min(2, len(terms))
    if not exact_phrase and len(matched_terms) < required_terms:
        return False, [], "", 0.0, ""
    if exact_phrase:
        match_type = "exact_phrase"
    elif len(matched_terms) == 1:
        match_type = "exact_token"
    else:
        match_type = "token_set"
    match_coverage = round(len(set(matched_terms)) / max(len(set(terms)), 1), 3)
    normalization = "direct"
    if exact_phrase and phrase not in raw_canonical:
        normalization = "hyphen_or_ocr_alias"
    return exact_phrase, matched_terms, match_type, match_coverage, normalization


def _enrich_inventory_fields(result: dict[str, Any], inventory: dict[str, dict[str, Any]]) -> dict[str, Any]:
    evidence_id = str(result.get("evidence_id") or "")
    source = dict(inventory.get(evidence_id) or {})
    parent_id = str(result.get("parent_evidence_id") or source.get("parent_evidence_id") or "")
    parent = dict(inventory.get(parent_id) or {}) if parent_id else {}
    root = parent or source
    source_hash = str(source.get("source_hash") or root.get("source_hash") or "")
    duplicate_of = str(root.get("duplicate_of") or source.get("duplicate_of") or "")
    canonical_id = duplicate_of or parent_id or evidence_id
    canonical_key = f"sha256:{source_hash}" if source_hash else f"record:{canonical_id}"
    result.update(
        {
            "source_hash": source_hash,
            "duplicate_of": duplicate_of,
            "canonical_document_key": canonical_key,
            "canonical_evidence_id": canonical_id,
        }
    )
    return result


def _result_from_row(
    row: dict[str, Any],
    *,
    query: str,
    target: str,
    terms: list[str],
    record_type_filter: str,
    inventory: dict[str, dict[str, Any]],
    sqlite_snippet: str = "",
) -> dict[str, Any] | None:
    if not _matches_record_type(row, record_type_filter):
        return None
    text = str(row.get("text") if "text" in row else row.get("text_content") or "")
    if not text.strip():
        return None
    exact_phrase, matched_terms, match_type, coverage, normalization = _match_details(
        text, target, terms
    )
    if not match_type:
        return None
    result = dict(row)
    snippet = normalized_snippet(text, target)
    if normalization == "direct" and sqlite_snippet:
        snippet = sqlite_snippet
    result.update(
        {
            "query": query,
            "search_target": target,
            "normalized_search_target": normalize_search_query(target).canonical,
            "exact_content_match": exact_phrase,
            "exact_phrase_match": exact_phrase,
            "exact_token_match": bool(matched_terms),
            "match_type": match_type,
            "matched_terms": matched_terms,
            "match_coverage": coverage,
            "match_normalization": normalization,
            "snippet": _clean_snippet(snippet or text[:500]),
            "ocr_derived": str(row.get("ocr_status") or "") == "ocr_completed",
            "source_lane": "private_record",
            "authority_status": "private_record_not_legal_authority",
            "duplicate_copy_count": 1,
            "duplicate_source_ids": [str(row.get("evidence_id") or "")],
            "duplicate_basenames": [Path(str(row.get("source_locator") or "")).name],
        }
    )
    return _enrich_inventory_fields(result, inventory)


def _collapse_duplicate_results(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    collapsed: dict[tuple[str, int, str], dict[str, Any]] = {}
    order: list[tuple[str, int, str]] = []
    for row in rows:
        canonical_key = str(row.get("canonical_document_key") or row.get("evidence_id") or "")
        page = int(row.get("page_number") or 0)
        snippet_key = normalize_search_query(str(row.get("snippet") or "")).canonical[:500]
        key = (canonical_key, page, snippet_key)
        if key not in collapsed:
            collapsed[key] = row
            order.append(key)
            continue
        current = collapsed[key]
        source_ids = list(current.get("duplicate_source_ids") or [])
        for source_id in row.get("duplicate_source_ids") or [row.get("evidence_id")]:
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
        basenames = list(current.get("duplicate_basenames") or [])
        for basename in row.get("duplicate_basenames") or [Path(str(row.get("source_locator") or "")).name]:
            if basename and basename not in basenames:
                basenames.append(basename)
        current["duplicate_source_ids"] = source_ids
        current["duplicate_basenames"] = basenames
        current["duplicate_copy_count"] = len(source_ids)
    return [collapsed[key] for key in order[: max(1, min(limit, 100))]]


def search_local_content_index(case_root: Path, query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search local content across hyphen, spacing, Unicode-dash, and OCR variants."""

    path = case_root / "04_INDEXES" / INDEX_NAME
    intake = parse_intake(query)
    target = intake.search_target or query
    record_type_filter = str(getattr(intake, "record_type_filter", "") or "")
    normalized_query = normalize_search_query(target)
    terms = list(normalized_query.terms)
    phrase = normalized_query.canonical.strip(' "“”')
    if not terms and not phrase:
        return []

    inventory_rows = _inventory_rows(case_root)
    inventory = {str(row.get("evidence_id") or ""): row for row in inventory_rows}
    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    normalized_index_available = False
    if path.exists():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        try:
            normalized_index_available = "normalized_text" in _fts_columns(connection)
            rows: list[sqlite3.Row] = []
            if len(phrase) >= 3:
                escaped = phrase.replace('"', '""')
                try:
                    rows.extend(_search_rows(connection, f'"{escaped}"', limit * 3))
                except sqlite3.OperationalError:
                    pass
            if terms:
                token_expression = " OR ".join(
                    f'"{term.replace(chr(34), "")}"' for term in terms[:16]
                )
                try:
                    rows.extend(_search_rows(connection, token_expression, limit * 6))
                except sqlite3.OperationalError:
                    pass
            for sqlite_row in rows:
                raw = dict(sqlite_row)
                evidence_id = str(raw.get("evidence_id") or "")
                if evidence_id in seen_ids:
                    continue
                seen_ids.add(evidence_id)
                result = _result_from_row(
                    raw,
                    query=query,
                    target=target,
                    terms=terms,
                    record_type_filter=record_type_filter,
                    inventory=inventory,
                    sqlite_snippet=str(raw.get("snippet") or ""),
                )
                if result:
                    candidates.append(result)
        finally:
            connection.close()

    # Compatibility and OCR fallback: older v5.2 indexes do not contain the
    # normalized alias column. Scan the already-derived local inventory only;
    # originals are not reopened and no network access is possible. The scan is
    # bounded so a pathological matter cannot turn one query into unbounded work.
    if not normalized_index_available:
        scanned_records = 0
        scanned_chars = 0
        for row in inventory_rows:
            if scanned_records >= MAX_COMPATIBILITY_SCAN_RECORDS or scanned_chars >= MAX_COMPATIBILITY_SCAN_CHARS:
                break
            evidence_id = str(row.get("evidence_id") or "")
            if evidence_id in seen_ids:
                continue
            source_text = str(row.get("text_content") or "")
            scanned_records += 1
            scanned_chars += len(source_text)
            result = _result_from_row(
                row,
                query=query,
                target=target,
                terms=terms,
                record_type_filter=record_type_filter,
                inventory=inventory,
            )
            if result:
                result["compatibility_scan"] = True
                candidates.append(result)
                seen_ids.add(evidence_id)

    page_parents = {
        str(row.get("parent_evidence_id") or "")
        for row in candidates
        if row.get("source_type") == "pdf_page" and row.get("parent_evidence_id")
    }
    candidates = [
        row
        for row in candidates
        if not (
            row.get("source_type") != "pdf_page"
            and str(row.get("evidence_id") or "") in page_parents
        )
    ]
    candidates.sort(
        key=lambda row: (
            0 if row.get("match_type") == "exact_phrase" else 1,
            -float(row.get("match_coverage") or 0.0),
            str(row.get("title") or "").casefold(),
            int(row.get("page_number") or 0),
        )
    )
    return _collapse_duplicate_results(candidates, limit)


def summarize_local_search(query: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    intake = parse_intake(query)
    target = intake.search_target or query
    record_type_filter = str(getattr(intake, "record_type_filter", "") or "")
    exact_phrase = sum(1 for row in rows if row.get("match_type") == "exact_phrase")
    exact_token = sum(1 for row in rows if row.get("match_type") in {"exact_token", "token_set"})
    related = sum(1 for row in rows if row.get("match_type") == "fts_related")
    ocr = sum(1 for row in rows if row.get("ocr_derived"))
    documents = {
        str(row.get("canonical_document_key") or row.get("parent_evidence_id") or row.get("evidence_id") or "")
        for row in rows
    }
    pages = {
        (
            str(row.get("canonical_document_key") or row.get("parent_evidence_id") or row.get("evidence_id") or ""),
            int(row.get("page_number") or 0),
        )
        for row in rows
        if int(row.get("page_number") or 0) > 0
    }
    duplicate_collapsed = sum(max(0, int(row.get("duplicate_copy_count") or 1) - 1) for row in rows)
    normalization = normalize_search_query(target)
    return {
        "query": query,
        "search_target": target,
        "normalized_search_target": normalization.canonical,
        "search_terms": list(normalization.terms),
        "hyphen_normalization_applied": bool(
            normalization.hyphen_variant_used
            or normalize_search_query(query).hyphen_variant_used
            or normalize_search_query(query).canonical != normalize_search_query(target).canonical
        ),
        "record_type_filter": record_type_filter,
        "exact_phrase": exact_phrase,
        "exact_token": exact_token,
        "related": related,
        "ocr_derived": ocr,
        "result_count": len(rows),
        "document_count": len(documents),
        "page_count": len(pages),
        "duplicate_copy_count_collapsed": duplicate_collapsed,
        "response_kind": "local_search_results",
    }


def public_record_view(row: dict[str, Any]) -> dict[str, Any]:
    """Return a source-card-safe record with no absolute local paths."""

    return {
        "evidence_id": row.get("evidence_id", ""),
        "title": row.get("title") or row.get("subject") or row.get("evidence_id", "Record"),
        "source_type": row.get("source_type", ""),
        "source_locator": row.get("source_locator") or Path(str(row.get("source_path", ""))).name,
        "parent_evidence_id": row.get("parent_evidence_id", ""),
        "source_hash": row.get("source_hash", ""),
        "parser_status": row.get("parser_status", ""),
        "text_status": row.get("text_status", ""),
        "ocr_status": row.get("ocr_status", ""),
        "issue_lanes": row.get("issue_lanes", []),
        "privacy_status": row.get("privacy_status", ""),
        "text_excerpt": row.get("text_excerpt", ""),
    }


def is_direct_content_search(query: str) -> bool:
    summary = parse_intake(query)
    return summary.task == "record_search"
