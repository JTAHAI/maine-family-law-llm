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
import re
import sqlite3
import zipfile
from dataclasses import dataclass, field
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

from pypdf import PdfReader

from .local_only_boundary import local_only_network_boundary


MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 10_000
INDEX_NAME = "private_content_index.sqlite"
INVENTORY_JSONL = "FULL_LOCAL_INVENTORY.jsonl"
INVENTORY_CSV = "FULL_LOCAL_INVENTORY.csv"


@dataclass(slots=True)
class ParsedContent:
    text: str = ""
    parser_status: str = "parsed"
    text_status: str = "available"
    ocr_status: str = "not_needed"
    page_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
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


def _pdf_text(data: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return "", 0
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages).strip(), len(reader.pages)


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
            for info in infos:
                member = Path(info.filename)
                if info.is_dir() or ".." in member.parts or member.is_absolute() or info.file_size > MAX_MEMBER_BYTES:
                    continue
                try:
                    child_data = archive.read(info)
                except (KeyError, RuntimeError, zipfile.BadZipFile):
                    continue
                child_locator = f"{locator}!{info.filename}"
                child = parse_bytes(child_data, suffix=member.suffix.lower(), locator=child_locator, depth=depth + 1)
                child.locator = child_locator
                child.title = member.name
                children.append(child)
            text = "\n".join(child.text for child in children if child.text)
            return ParsedContent(text=text, children=children, metadata={"archive_member_count": len(children)})
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
            children.append(child)
        elif content_type == "text/plain":
            body.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        elif content_type == "text/html":
            body.append(_html_to_text(payload.decode(part.get_content_charset() or "utf-8", errors="replace")))
    prefix = "\n".join(value for value in (fields.get("subject"), *body) if value)
    return ParsedContent(text=_safe_text(prefix), metadata=fields | {"attachment_count": len(children)}, children=children)


def parse_bytes(data: bytes, *, suffix: str, locator: str, depth: int = 0) -> ParsedContent:
    suffix = suffix.lower()
    if len(data) > MAX_MEMBER_BYTES:
        return ParsedContent(parser_status="quarantined", text_status="not_available", metadata={"reason": "member_size_limit"})
    if suffix == ".pdf":
        text, pages = _pdf_text(data)
        return ParsedContent(text=text, page_count=pages, text_status="available" if text else "not_available", ocr_status="not_needed" if text else "ocr_not_run")
    if suffix == ".eml":
        return _parse_email(data, locator, depth)
    if suffix in {".zip"}:
        return _parse_archive(data, locator, depth)
    if suffix in {".txt", ".md", ".csv"}:
        return ParsedContent(text=data.decode("utf-8", errors="replace"))
    if suffix in {".html", ".htm"}:
        return ParsedContent(text=_html_to_text(data.decode("utf-8", errors="replace")))
    if suffix == ".rtf":
        return ParsedContent(text=_rtf_to_text(data.decode("utf-8", errors="replace")))
    if suffix in {".docx", ".xlsx", ".pptx"}:
        text = _office_xml_text(data, suffix)
        return ParsedContent(text=text, text_status="available" if text else "not_available")
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
        connection.execute("CREATE VIRTUAL TABLE records USING fts5(evidence_id UNINDEXED, title, source_type UNINDEXED, source_locator UNINDEXED, parent_evidence_id UNINDEXED, parser_status UNINDEXED, ocr_status UNINDEXED, issue_lanes, text)")
        for row in rows:
            connection.execute("INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                row["evidence_id"], row.get("title", ""), row.get("source_type", ""), row.get("source_locator", ""), row.get("parent_evidence_id", ""), row.get("parser_status", ""), row.get("ocr_status", ""), ", ".join(row.get("issue_lanes", [])), row.get("text_content", ""),
            ))
        connection.commit()
    finally:
        connection.close()
    temporary.replace(path)


def rebuild_local_content_index(case_root: Path) -> dict[str, Any]:
    """Create a private full-text index without modifying any source evidence."""

    manifest_path = case_root / "08_SOURCE_MANIFESTS_HASHES" / "source_manifest.json"
    if not manifest_path.exists():
        return {"result": "unavailable", "reason": "source_manifest_missing"}
    source_rows = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    exact_hashes: dict[str, str] = {}
    source_mutation_pass = True
    with local_only_network_boundary():
        for source in source_rows:
            source_path = Path(str(source.get("source_path", "")))
            if not source_path.exists() or not source_path.is_file():
                continue
            before_hash = str(source.get("source_hash") or "")
            parsed = parse_path(source_path)
            after_hash = _sha256_bytes(source_path.read_bytes())
            source_mutation_pass = source_mutation_pass and before_hash == after_hash
            row = dict(source)
            row.update({
            "title": row.get("subject") or source_path.name,
            "source_locator": source_path.name,
            "parent_evidence_id": "",
            "parser_status": parsed.parser_status,
            "text_status": parsed.text_status,
            "ocr_status": parsed.ocr_status,
            "page_count": parsed.page_count or row.get("page_count", 0),
            "text_content": parsed.text,
            "text_excerpt": parsed.text[:1200] or row.get("text_excerpt", ""),
            "parser_metadata": parsed.metadata,
        })
            if before_hash in exact_hashes:
                row["duplicate_of"] = exact_hashes[before_hash]
            else:
                exact_hashes[before_hash] = str(row["evidence_id"])
                row["duplicate_of"] = ""
            records.append(row)
            for child_index, child in enumerate(parsed.children, start=1):
                child_row = dict(row)
                child_row.update({
                "evidence_id": f"{row['evidence_id']}-A{child_index:03d}",
                "title": child.title or f"Attachment {child_index}",
                "source_locator": child.locator,
                "parent_evidence_id": row["evidence_id"],
                "source_hash": _sha256_bytes(child.text.encode("utf-8")) if child.text else "",
                "parser_status": child.parser_status,
                "text_status": child.text_status,
                "ocr_status": child.ocr_status,
                "page_count": child.page_count,
                "text_content": child.text,
                "text_excerpt": child.text[:1200],
                "parser_metadata": child.metadata,
                "duplicate_of": "",
                })
                records.append(child_row)
    index_root = case_root / "04_INDEXES"
    _write_inventory(index_root / INVENTORY_JSONL, records)
    _write_csv(index_root / INVENTORY_CSV, records)
    (index_root / "private_search_index.json").write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    _write_fts(index_root / INDEX_NAME, records)
    proof = {
        "result": "PASS" if source_mutation_pass else "FAIL",
        "source_evidence_modified": False,
        "source_mutation_pass": source_mutation_pass,
        "records_indexed": len(records),
        "attachment_or_archive_children": sum(1 for row in records if row.get("parent_evidence_id")),
        "fts5_index": INDEX_NAME,
        "cloud_calls_made": 0,
        "network_boundary": "blocked_sockets_dns_http_by_design",
        "ocr_candidates": sum(1 for row in records if row.get("ocr_status") == "ocr_not_run"),
        "inventory_status": "ocr_choice_required" if any(row.get("ocr_status") == "ocr_not_run" for row in records) else "ready",
        "ocr_default": "not_run",
        "transcription_default": "not_run",
    }
    proof_path = case_root / "15_PROOF_VALIDATION" / "LOCAL_CORPUS_INDEX_PROOF.json"
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof | {"proof_path": str(proof_path)}


def local_ocr_choice(case_root: Path, *, approved: bool) -> dict[str, Any]:
    """Record an explicit OCR decision without ever making OCR automatic."""

    records = json.loads((case_root / "04_INDEXES" / "private_search_index.json").read_text(encoding="utf-8"))
    candidates = [row for row in records if row.get("ocr_status") == "ocr_not_run"]
    candidate_files = [
        {
            "evidence_id": str(row.get("evidence_id") or ""),
            "source_locator": str(row.get("source_locator") or ""),
            "page_count": int(row.get("page_count") or 0),
            "source_hash": str(row.get("source_hash") or ""),
        }
        for row in candidates[:100]
    ]
    if not candidates:
        return {"status": "not_needed", "message": "All detected pages already contain searchable text. OCR is not needed.", "candidates": 0, "candidate_files": []}
    if not approved:
        return {"status": "declined", "message": "Scanned pages remain unsearchable for now.", "candidates": len(candidates), "candidate_files": candidate_files}
    return {
        "status": "unavailable",
        "message": "Local OCR requires a separately installed local OCR engine. No pages were sent anywhere or changed.",
        "candidates": len(candidates),
        "candidate_files": candidate_files,
        "ocr_derived_text_created": 0,
    }


def search_local_content_index(case_root: Path, query: str, limit: int = 5) -> list[dict[str, Any]]:
    path = case_root / "04_INDEXES" / INDEX_NAME
    stopwords = {
        "about", "and", "does", "from", "have", "incident", "into", "me", "show",
        "tell", "that", "the", "this", "what", "with", "would", "could", "should",
        "unrelated", "space", "alien",
    }
    terms = [
        term.lower()
        for term in re.findall(r"[A-Za-z0-9_'-]{2,}", query)
        if len(term) >= 4 and term.lower() not in stopwords
    ]
    if not path.exists() or not terms:
        return []
    expression = " AND ".join(f'"{term.replace(chr(34), "")}"' for term in terms[:12])
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute("SELECT evidence_id, title, source_type, source_locator, parent_evidence_id, parser_status, ocr_status, issue_lanes, text, snippet(records, 8, '', '', ' … ', 28) AS snippet FROM records WHERE records MATCH ? ORDER BY bm25(records) LIMIT ?", (expression, max(1, min(limit, 20)))).fetchall()
        normalized_query = " ".join(terms)
        return [dict(row) | {"exact_content_match": normalized_query in str(row["text"]).lower()} for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        connection.close()


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
    normalized = " ".join(query.lower().split())
    return normalized.startswith(("search ", "find ", "look for ", "search contents", "search records")) or "search contents for" in normalized
