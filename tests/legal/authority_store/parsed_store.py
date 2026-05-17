from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from legal.connectors.maine_forms import parse_forms_index
from legal.connectors.maine_revisor import parse_revisor_html
from legal.connectors.maine_rules import parse_rules_index, parse_rules_text
from legal.connectors.pdf_text import extract_pdf_text
from legal.connectors.maine_sjc_opinions import parse_law_court_opinion_index
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
                    }
                    for rule in rules
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
                        "court": opinion.court,
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
    """Audit parsed authority store outputs without requiring live network access."""

    REQUIRED_COLLECTIONS = {
        "statutes/statute_title_indexes.jsonl": 1,
        "rules/rules_index.jsonl": 1,
        "forms/forms_index.jsonl": 1,
        "opinions/opinion_index.jsonl": 1,
    }

    def __init__(self, *, data_root: str | Path, required_collections: dict[str, int] | None = None) -> None:
        self.data_root = Path(data_root).resolve()
        self.parsed_store = self.data_root / "parsed_authority_store"
        self.required_collections = required_collections or self.REQUIRED_COLLECTIONS

    def run(self) -> dict[str, Any]:
        findings: list[ParsedAuthorityFinding] = []
        counts: dict[str, int] = {}
        for relative, minimum in self.required_collections.items():
            path = self.parsed_store / relative
            if not path.exists():
                findings.append(ParsedAuthorityFinding("parsed_collection_missing", f"Missing {relative}"))
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
        status = "pass" if not findings else "blocked"
        return {
            "status": status,
            "data_root": str(self.data_root),
            "parsed_store": str(self.parsed_store),
            "counts_by_collection": counts,
            "findings": [finding.as_dict() for finding in findings],
        }
