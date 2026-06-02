from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.connectors.maine_forms import normalize_form_id, parse_form_text, parse_forms_index
from legal.connectors.maine_revisor import parse_revisor_html, parse_revisor_section_html
from legal.connectors.maine_rules import parse_rules_index, parse_rules_text
from legal.connectors.pdf_text import extract_pdf_text
from legal.connectors.maine_sjc_opinions import parse_law_court_opinion_index, parse_law_court_opinion_text
from legal.data_boundaries import StoreName


@dataclass(frozen=True)
class ParsedAuthorityFinding:
    code: str
    message: str
    source_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "source_id": self.source_id}


@dataclass
class ParsedAuthorityBuildReport:
    status: str
    data_root: str
    manifest_path: str
    parsed_store: str
    total_manifest_records: int = 0
    parsed_record_count: int = 0
    output_files: dict[str, str] = field(default_factory=dict)
    counts_by_collection: dict[str, int] = field(default_factory=dict)
    findings: list[ParsedAuthorityFinding] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "manifest_path": self.manifest_path,
            "parsed_store": self.parsed_store,
            "total_manifest_records": self.total_manifest_records,
            "parsed_record_count": self.parsed_record_count,
            "counts_by_collection": self.counts_by_collection,
            "output_files": self.output_files,
            "findings": [finding.as_dict() for finding in self.findings],
        }


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"authority source manifest not found: {path}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        raise ValueError("authority source manifest must be a JSON array")
    return [item for item in loaded if isinstance(item, dict)]


def _snapshot_path(record: dict[str, Any], official_store: Path) -> Path:
    value = str(record.get("snapshot_path") or "")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = official_store / path
    return path


def _jsonl_append(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            count += 1
    return count


def _base_record(record: dict[str, Any], *, authority_kind: str, source_span: dict[str, int | None]) -> dict[str, Any]:
    return {
        "authority_kind": authority_kind,
        "source_id": record.get("source_id"),
        "source_class": record.get("source_class"),
        "jurisdiction": record.get("jurisdiction"),
        "source_hash": record.get("hash"),
        "snapshot_path": record.get("snapshot_path"),
        "source_url_or_path": record.get("source_url_or_path"),
        "retrieved_at": record.get("retrieved_at"),
        "freshness_status": record.get("freshness_status"),
        "parser_status": record.get("parser_status"),
        "source_span": source_span,
        "parser_audit": record.get("parser_audit", {}),
    }

_CITATION_RE = re.compile(r"\b(20\d{2}\s+ME\s+\d+)\b")
_FORM_ID_RE = re.compile(r"\b(FM|PA|CV|PB)-?\s?(\d{3}[A-Z]?)\b", re.I)


def _first_nonempty(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _canonical_examples(record: dict[str, Any]) -> list[dict[str, Any]]:
    examples = record.get("canonical_examples")
    if isinstance(examples, list):
        return [item for item in examples if isinstance(item, dict)]
    return []


def _record_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _parser_metadata(record: dict[str, Any]) -> dict[str, Any]:
    parser_audit = record.get("parser_audit")
    if not isinstance(parser_audit, dict):
        return {}
    metadata = parser_audit.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _fallback_form_id(*, parsed_form_id: str | None, title: str | None, url: str, record: dict[str, Any]) -> tuple[str | None, str | None]:
    candidates: list[tuple[str | None, str]] = [
        (parsed_form_id, "parsed_text"),
        (title, "parsed_title"),
        (url, "source_url"),
        (_record_metadata(record).get("target_id"), "target_id"),
    ]
    for example in _canonical_examples(record):
        candidates.extend(
            [
                (example.get("form_id"), "canonical_example"),
                (example.get("citation"), "canonical_example"),
                (example.get("title"), "canonical_example"),
            ]
        )
    for value, source in candidates:
        if not value:
            continue
        match = _FORM_ID_RE.search(str(value))
        if match:
            return normalize_form_id(match.group(0)), source
    basename = url.rsplit("/", 1)[-1].split("?", 1)[0].split("#", 1)[0].strip()
    stem = basename.rsplit(".", 1)[0].strip() if basename else ""
    if stem:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").upper()
        if slug:
            return f"OFFICIAL-FORM-{slug}", "source_url_filename_fallback"
    source_id = str(record.get("source_id") or "").strip()
    if source_id:
        slug = re.sub(r"[^A-Za-z0-9]+", "-", source_id).strip("-").upper()
        if slug:
            return f"OFFICIAL-FORM-{slug}", "source_id_fallback"
    return None, None


def _fallback_opinion_citation(*, parsed_citation: str | None, text: str, record: dict[str, Any]) -> tuple[str | None, str | None]:
    candidates: list[tuple[str | None, str]] = [
        (parsed_citation, "parsed_text"),
        (_parser_metadata(record).get("citation"), "parser_audit_metadata"),
        (_record_metadata(record).get("citation"), "record_metadata"),
        (_record_metadata(record).get("target_id"), "target_id"),
        (record.get("source_url_or_path"), "source_url"),
        (text, "extracted_text"),
    ]
    for example in _canonical_examples(record):
        candidates.extend(
            [
                (example.get("citation"), "canonical_example"),
                (example.get("title"), "canonical_example"),
            ]
        )
    for value, source in candidates:
        if not value:
            continue
        match = _CITATION_RE.search(str(value))
        if match:
            return match.group(1), source
    return None, None


class ParsedAuthorityStoreBuilder:
    """Build structured authority JSONL files from raw official snapshots."""

    def __init__(self, *, data_root: str | Path) -> None:
        self.data_root = Path(data_root).resolve()
        self.official_store = self.data_root / StoreName.OFFICIAL_AUTHORITY.value
        self.parsed_store = self.data_root / "parsed_authority_store"
        self.manifest_path = self.official_store / "source_manifest.json"
        self.findings: list[ParsedAuthorityFinding] = []

    def build(self) -> ParsedAuthorityBuildReport:
        records = _load_manifest(self.manifest_path)
        if self.parsed_store.exists():
            for old in self.parsed_store.rglob("*.jsonl"):
                old.unlink()
        output_files: dict[str, str] = {}
        counts_by_collection: dict[str, int] = {}
        parsed_record_count = 0

        for record in records:
            collection, rows = self._rows_for_manifest_record(record)
            if not collection:
                continue
            output_path = self.parsed_store / collection
            count = _jsonl_append(output_path, rows)
            output_files[collection] = str(output_path)
            counts_by_collection[collection] = counts_by_collection.get(collection, 0) + count
            parsed_record_count += count

        record_counts = {"statutes": 0, "rules": 0, "forms": 0, "opinions": 0}
        for collection, count in counts_by_collection.items():
            if collection.startswith("statutes/"):
                record_counts["statutes"] += count
            elif collection.startswith("rules/"):
                record_counts["rules"] += count
            elif collection.startswith("forms/"):
                record_counts["forms"] += count
            elif collection.startswith("opinions/"):
                record_counts["opinions"] += count
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_manifest_path": str(self.manifest_path),
            "parsed_store": str(self.parsed_store),
            "record_counts": record_counts,
            "counts_by_collection": counts_by_collection,
            "output_files": output_files,
            "findings": [finding.as_dict() for finding in self.findings],
        }
        self.parsed_store.mkdir(parents=True, exist_ok=True)
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True)
        (self.parsed_store / "parsed_authority_manifest.json").write_text(
            manifest_text, encoding="utf-8"
        )
        (self.parsed_store / "parsed_manifest.json").write_text(
            manifest_text, encoding="utf-8"
        )
        status = "pass" if parsed_record_count > 0 and not any(f.code.endswith("_failed") for f in self.findings) else "blocked"
        return ParsedAuthorityBuildReport(
            status=status,
            data_root=str(self.data_root),
            manifest_path=str(self.manifest_path),
            parsed_store=str(self.parsed_store),
            total_manifest_records=len(records),
            parsed_record_count=parsed_record_count,
            output_files=output_files,
            counts_by_collection=counts_by_collection,
            findings=self.findings,
        )

    def _rows_for_manifest_record(self, record: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
        source_id = str(record.get("source_id") or "")
        source_class = str(record.get("source_class") or "")
        parser_name = str(record.get("parser_audit", {}).get("parser_name") or "")
        path = _snapshot_path(record, self.official_store)
        if not path.exists():
            self.findings.append(
                ParsedAuthorityFinding("snapshot_missing", f"Snapshot not found: {path}", source_id)
            )
            return None, []
        content = path.read_bytes()
        span = {"start_offset": 0, "end_offset": len(content)}
        if parser_name == "maine_rules_pdf":
            try:
                pdf_text = extract_pdf_text(content)
                rules, _audit = parse_rules_text(
                    pdf_text, source_id=source_id, url=str(record.get("source_url_or_path") or "")
                )
                return "rules/rules_index.jsonl", [
                    {
                        **_base_record(record, authority_kind="court_rule_reference", source_span=span),
                        "record_id": rule.document_id,
                        "title": rule.title,
                        "citation": rule.citation,
                        "rule_set": rule.rule_set,
                        "rule_number": rule.rule_number,
                        "href": rule.source_location.url_or_path,
                        "text": pdf_text,
                    }
                    for rule in rules
                ]
            except Exception as exc:
                self.findings.append(
                    ParsedAuthorityFinding("parse_failed", f"{type(exc).__name__}: {exc}", source_id)
                )
                return None, []

        if parser_name == "maine_form_pdf" or source_class == "court_form_pdf":
            try:
                form_text = extract_pdf_text(content)
                form, _audit = parse_form_text(
                    form_text, source_id=source_id, url=str(record.get("source_url_or_path") or "")
                )
                clean_text = str(form.text or form_text or "").strip()
                if not clean_text:
                    self.findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_row_quarantined",
                            "court_form_pdf produced no extractable text; skipped direct parsed row",
                            source_id,
                        )
                    )
                    return None, []
                form_id, form_id_source = _fallback_form_id(
                    parsed_form_id=form.form_id or form.citation,
                    title=form.title,
                    url=str(record.get("source_url_or_path") or ""),
                    record=record,
                )
                if not form_id:
                    self.findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_row_quarantined",
                            "court_form_pdf produced no stable form identifier; skipped direct parsed row",
                            source_id,
                        )
                    )
                    return None, []
                return "forms/forms.jsonl", [
                    {
                        **_base_record(record, authority_kind="court_form", source_span=span),
                        "record_id": form.document_id,
                        "title": form.title,
                        "citation": form.citation or form_id,
                        "form_id": form_id,
                        "form_id_source": form_id_source,
                        "version_date": form.version_date,
                        "required_fields": list(getattr(form, "required_fields", []) or []),
                        "stale_form_risk": form.stale_form_risk,
                        "text": clean_text,
                    }
                ]
            except Exception as exc:
                self.findings.append(
                    ParsedAuthorityFinding("parse_failed", f"{type(exc).__name__}: {exc}", source_id)
                )
                return None, []

        if parser_name == "maine_law_court_opinion_pdf" or source_class == "law_court_opinion_pdf":
            try:
                opinion_text = extract_pdf_text(content)
                clean_text = str(opinion_text or "").strip()
                if not clean_text:
                    self.findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_row_quarantined",
                            "law_court_opinion_pdf produced no extractable text; skipped direct parsed row",
                            source_id,
                        )
                    )
                    return None, []
                opinion, _audit = parse_law_court_opinion_text(
                    clean_text, source_id=source_id, url=str(record.get("source_url_or_path") or "")
                )
                citation, citation_source = _fallback_opinion_citation(
                    parsed_citation=opinion.citation,
                    text=clean_text,
                    record=record,
                )
                if not citation:
                    self.findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_row_quarantined",
                            "law_court_opinion_pdf produced no stable official citation; skipped direct parsed row",
                            source_id,
                        )
                    )
                    return None, []
                return "opinions/opinions.jsonl", [
                    {
                        **_base_record(record, authority_kind="law_court_opinion", source_span=span),
                        "record_id": opinion.opinion_id,
                        "title": opinion.title,
                        "citation": citation,
                        "citation_source": citation_source,
                        "decision_date": opinion.decision_date,
                        "docket_number": opinion.docket_number,
                        "court": getattr(opinion, "court", None) or "Maine Supreme Judicial Court",
                        "href": opinion.href,
                        "text": clean_text,
                    }
                ]
            except Exception as exc:
                self.findings.append(
                    ParsedAuthorityFinding("parse_failed", f"{type(exc).__name__}: {exc}", source_id)
                )
                return None, []

        if path.suffix.lower() == ".pdf" or parser_name == "pdf_snapshot" or source_class == "statute_title_pdf":
            return "statutes/pdf_snapshots.jsonl", [
                {
                    **_base_record(record, authority_kind="statute_title_pdf_snapshot", source_span=span),
                    "record_id": f"{source_id}:pdf-snapshot",
                    "title": record.get("metadata", {}).get("target_id", source_id),
                    "citation": None,
                    "text_available": False,
                    "requires_ocr_or_pdf_text_worker": True,
                }
            ]
        text = content.decode("utf-8", errors="replace")
        try:
            if parser_name == "maine_revisor_section" or source_class == "statute_section":
                section, _audit = parse_revisor_section_html(text, source_id=source_id, url=str(record.get("source_url_or_path") or ""))
                return "statutes/statute_sections.jsonl", [
                    {
                        **_base_record(record, authority_kind="statute_section", source_span=span),
                        "record_id": section.document_id,
                        "title": section.title,
                        "citation": section.citation,
                        "title_number": section.title_number,
                        "section_number": section.section_number,
                        "section_heading": section.section_heading,
                        "subsections": section.subsections,
                        "subsection_count": len(section.subsections),
                        "data_extracted_at": section.metadata.get("data_extracted_at"),
                        "text": section.text,
                    }
                ]

            if parser_name == "maine_revisor_title_index" or source_class == "statute_title_index":
                document, _audit = parse_revisor_html(text, source_id=source_id, url=str(record.get("source_url_or_path") or ""))
                rows = [
                    {
                        **_base_record(record, authority_kind="statute_title_index", source_span=span),
                        "record_id": document.document_id,
                        "title": document.title,
                        "citation": document.citation,
                        "title_number": document.title_number,
                        "chapter_count": len(document.chapters),
                        "section_reference_count": len(document.section_links),
                        "data_extracted_at": document.data_extracted_at,
                    }
                ]
                for link in document.section_links:
                    rows.append(
                        {
                            **_base_record(record, authority_kind="statute_section_reference", source_span=span),
                            "record_id": link.get("source_id"),
                            "title": link.get("text"),
                            "citation": f"{link.get('title')} M.R.S. § {link.get('section')}",
                            "title_number": link.get("title"),
                            "section_number": link.get("section"),
                            "href": link.get("href"),
                            "parse_depth": "index_reference_not_full_section_text",
                        }
                    )
                return "statutes/statute_title_indexes.jsonl", rows
            if parser_name == "maine_rules_index" or source_class in {"court_rules_index", "court_policy_index"}:
                rules, _audit = parse_rules_index(text, source_id=source_id, url=str(record.get("source_url_or_path") or ""))
                return "rules/rules_index.jsonl", [
                    {
                        **_base_record(record, authority_kind="court_rule_reference", source_span=span),
                        "record_id": rule.document_id,
                        "title": rule.title,
                        "citation": rule.citation,
                        "rule_set": rule.rule_set,
                        "rule_number": rule.rule_number,
                        "href": rule.source_location.url_or_path,
                    }
                    for rule in rules
                ]
            if parser_name == "maine_forms_index" or source_class == "court_forms_index":
                forms, _audit = parse_forms_index(text, source_id=source_id, url=str(record.get("source_url_or_path") or ""))
                return "forms/forms_index.jsonl", [
                    {
                        **_base_record(record, authority_kind="court_form_reference", source_span=span),
                        "record_id": form.document_id,
                        "title": form.title,
                        "citation": form.citation,
                        "form_id": form.form_id,
                        "version_date": form.version_date,
                        "stale_form_risk": form.stale_form_risk,
                        "href": form.source_location.url_or_path,
                    }
                    for form in forms
                ]
            if parser_name == "maine_form_text" or source_class == "court_form_text":
                url = str(record.get("source_url_or_path") or "")
                form, _audit = parse_form_text(text, source_id=source_id, url=url)
                clean_text = str(form.text or text or "").strip()
                if not clean_text:
                    self.findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_row_quarantined",
                            "court_form_text produced no extractable text; skipped direct parsed row",
                            source_id,
                        )
                    )
                    return None, []
                form_id, form_id_source = _fallback_form_id(
                    parsed_form_id=form.form_id or form.citation,
                    title=form.title,
                    url=url,
                    record=record,
                )
                if not form_id:
                    self.findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_row_quarantined",
                            "court_form_text produced no stable form identifier; skipped direct parsed row",
                            source_id,
                        )
                    )
                    return None, []
                return "forms/forms.jsonl", [
                    {
                        **_base_record(record, authority_kind="court_form", source_span=span),
                        "record_id": form.document_id,
                        "title": form.title,
                        "citation": form.citation or form_id,
                        "form_id": form_id,
                        "form_id_source": form_id_source,
                        "version_date": form.version_date,
                        "required_fields": list(getattr(form, "required_fields", []) or []),
                        "stale_form_risk": form.stale_form_risk,
                        "text": clean_text,
                    }
                ]
            if parser_name == "maine_law_court_opinion_index" or source_class == "law_court_opinion_index":
                opinions, _audit = parse_law_court_opinion_index(text, source_id=source_id, url=str(record.get("source_url_or_path") or ""))
                return "opinions/opinion_index.jsonl", [
                    {
                        **_base_record(record, authority_kind="law_court_opinion_reference", source_span=span),
                        "record_id": opinion.opinion_id,
                        "title": opinion.title,
                        "citation": opinion.citation,
                        "decision_date": opinion.decision_date,
                        "docket_number": opinion.docket_number,
                        "court": getattr(opinion, "court", None) or "Maine Supreme Judicial Court",
                        "href": opinion.href,
                    }
                    for opinion in opinions
                ]
        except Exception as exc:
            self.findings.append(
                ParsedAuthorityFinding("parse_failed", f"{type(exc).__name__}: {exc}", source_id)
            )
            return None, []
        self.findings.append(
            ParsedAuthorityFinding("unsupported_source_class", f"No parsed-store builder for {source_class}", source_id)
        )
        return None, []


class ParsedAuthorityStoreAuditor:
    """Audit parsed authority store outputs without requiring live network access.

    The default audit validates first-wave index parsing.  ``require_direct_authority``
    promotes the audit to the Pass 20/23 handoff contract: direct statute
    sections, direct forms, and direct Law Court opinions must exist and carry
    enough text/metadata to support retrieval, source cards, and citation/quote
    verification.
    """

    REQUIRED_COLLECTIONS = {
        "statutes/statute_title_indexes.jsonl": 1,
        "rules/rules_index.jsonl": 1,
        "forms/forms_index.jsonl": 1,
        "opinions/opinion_index.jsonl": 1,
    }
    DIRECT_AUTHORITY_COLLECTIONS = {
        "statutes/statute_sections.jsonl": 1,
        "forms/forms.jsonl": 1,
        "opinions/opinions.jsonl": 1,
    }
    DIRECT_REQUIRED_FIELDS = {
        "statute_section": ("citation", "title_number", "section_number", "text"),
        "court_form": ("form_id", "title", "text"),
        "law_court_opinion": ("citation", "title", "text"),
    }

    def __init__(
        self,
        *,
        data_root: str | Path,
        required_collections: dict[str, int] | None = None,
        require_direct_authority: bool = False,
    ) -> None:
        self.data_root = Path(data_root).resolve()
        self.parsed_store = self.data_root / "parsed_authority_store"
        self.required_collections = dict(required_collections or self.REQUIRED_COLLECTIONS)
        self.require_direct_authority = require_direct_authority
        if require_direct_authority:
            self.required_collections.update(self.DIRECT_AUTHORITY_COLLECTIONS)

    def run(self) -> dict[str, Any]:
        findings: list[ParsedAuthorityFinding] = []
        counts: dict[str, int] = {}
        authority_kind_counts: dict[str, int] = {}
        direct_counts = {"statute_section": 0, "court_form": 0, "law_court_opinion": 0}
        reference_count = 0
        full_text_count = 0

        for relative, minimum in self.required_collections.items():
            path = self.parsed_store / relative
            if not path.exists():
                code = (
                    "missing_direct_authority_collection"
                    if relative in self.DIRECT_AUTHORITY_COLLECTIONS
                    else "parsed_collection_missing"
                )
                findings.append(ParsedAuthorityFinding(code, f"Missing {relative}"))
                counts[relative] = 0
                continue
            rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            counts[relative] = len(rows)
            if len(rows) < minimum:
                findings.append(
                    ParsedAuthorityFinding(
                        "parsed_collection_minimum_not_met",
                        f"{relative} has {len(rows)} rows; {minimum} required.",
                    )
                )
            for index, line in enumerate(rows, start=1):
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    findings.append(ParsedAuthorityFinding("parsed_jsonl_invalid", f"{relative}:{index}: {exc}"))
                    continue
                for field_name in ("record_id", "source_id", "source_hash", "source_span", "freshness_status"):
                    if row.get(field_name) in (None, ""):
                        findings.append(
                            ParsedAuthorityFinding(
                                "parsed_required_field_missing",
                                f"{relative}:{index} missing {field_name}",
                                str(row.get("source_id") or ""),
                            )
                        )
                authority_kind = str(row.get("authority_kind") or "unknown")
                authority_kind_counts[authority_kind] = authority_kind_counts.get(authority_kind, 0) + 1
                if authority_kind.endswith("_reference") or authority_kind.endswith("_index"):
                    reference_count += 1
                if str(row.get("text") or "").strip():
                    full_text_count += 1
                if authority_kind in direct_counts:
                    direct_counts[authority_kind] += 1
                    self._validate_direct_row(
                        row=row,
                        relative=relative,
                        index=index,
                        authority_kind=authority_kind,
                        findings=findings,
                    )

        if self.require_direct_authority:
            for authority_kind, count in direct_counts.items():
                if count < 1:
                    findings.append(
                        ParsedAuthorityFinding(
                            "direct_authority_kind_missing",
                            f"No direct parsed records found for {authority_kind}. Run follow-up target ingest and rebuild parsed authority.",
                        )
                    )

        readiness = self._readiness(direct_counts=direct_counts, full_text_count=full_text_count)
        status = "pass" if not findings else "blocked"
        return {
            "status": status,
            "readiness": readiness,
            "require_direct_authority": self.require_direct_authority,
            "data_root": str(self.data_root),
            "parsed_store": str(self.parsed_store),
            "counts_by_collection": counts,
            "authority_kind_counts": authority_kind_counts,
            "direct_authority": {
                "required_kinds": sorted(direct_counts),
                "counts_by_kind": direct_counts,
                "full_text_record_count": full_text_count,
                "reference_record_count": reference_count,
            },
            "findings": [finding.as_dict() for finding in findings],
        }

    def _validate_direct_row(
        self,
        *,
        row: dict[str, Any],
        relative: str,
        index: int,
        authority_kind: str,
        findings: list[ParsedAuthorityFinding],
    ) -> None:
        for field_name in self.DIRECT_REQUIRED_FIELDS.get(authority_kind, ()):  # defensive for future kinds
            if row.get(field_name) in (None, "") or (field_name == "text" and not str(row.get(field_name)).strip()):
                findings.append(
                    ParsedAuthorityFinding(
                        "direct_authority_required_field_missing",
                        f"{relative}:{index} {authority_kind} missing {field_name}",
                        str(row.get("source_id") or ""),
                    )
                )

    @staticmethod
    def _readiness(*, direct_counts: dict[str, int], full_text_count: int) -> str:
        if all(count > 0 for count in direct_counts.values()):
            return "direct_authority_ready"
        if any(count > 0 for count in direct_counts.values()) or full_text_count > 0:
            return "direct_authority_partial"
        return "index_only"
