from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal.connectors.base import ParserAuditEvent, RetrievedSource, SourceFetcher, SourceTarget
from legal.connectors.http_fetcher import OfficialSourceFetchError
from legal.connectors.maine_forms import parse_form_text, parse_forms_index
from legal.connectors.maine_revisor import parse_revisor_html
from legal.connectors.maine_rules import parse_rules_index, parse_rules_text
from legal.connectors.pdf_text import extract_pdf_text
from legal.connectors.maine_sjc_opinions import parse_law_court_opinion_index, parse_law_court_opinion_text
from legal.corpus.source_normalizer import stable_source_id
from legal.corpus.source_registry import SourceRecord
from legal.corpus.source_snapshotter import SourceSnapshotter
from legal.data_boundaries import DataClass


@dataclass(frozen=True)
class IngestedAuthority:
    source_record: SourceRecord
    snapshot_path: str
    parser_audit: ParserAuditEvent
    canonical_count: int = 0
    canonical_examples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        record = self.source_record.to_manifest_record()
        record["snapshot_path"] = self.snapshot_path
        record["parser_audit"] = self.parser_audit.to_dict()
        record["canonical_count"] = self.canonical_count
        record["canonical_examples"] = self.canonical_examples
        return record


@dataclass(frozen=True)
class FailedAuthorityIngestion:
    target: SourceTarget
    failure_code: str
    message: str
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    attempts: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_exception(cls, exc: OfficialSourceFetchError) -> "FailedAuthorityIngestion":
        return cls(
            target=exc.target,
            failure_code=exc.code,
            message=exc.message,
            attempts=[attempt.as_dict() for attempt in exc.attempts],
        )

    @classmethod
    def from_unexpected(cls, target: SourceTarget, exc: Exception) -> "FailedAuthorityIngestion":
        return cls(
            target=target,
            failure_code="unexpected_ingest_error",
            message=f"{type(exc).__name__}: {exc}",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target.target_id,
            "source_class": self.target.source_class,
            "jurisdiction": self.target.jurisdiction,
            "url": self.target.url,
            "parser_name": self.target.parser_name,
            "failure_code": self.failure_code,
            "message": self.message,
            "failed_at": self.failed_at.isoformat(),
            "attempts": self.attempts,
        }


class OfficialAuthorityIngestor:
    """Fetch, snapshot, parse, and manifest official authority targets.

    This component writes raw snapshots and build evidence into an external data
    root. It never places the official corpus inside the releasable source repo.
    """

    def __init__(
        self,
        *,
        fetcher: SourceFetcher,
        snapshot_base_dir: str | Path,
    ) -> None:
        self.fetcher = fetcher
        self.snapshotter = SourceSnapshotter(snapshot_base_dir)
        self.failed: list[FailedAuthorityIngestion] = []

    @staticmethod
    def source_id_for_target(target: SourceTarget) -> str:
        return stable_source_id(target.source_class, target.url)

    def _parse(
        self, retrieved: RetrievedSource, *, source_id: str
    ) -> tuple[ParserAuditEvent, int, list[dict[str, Any]], str]:
        target = retrieved.target
        canonical_count = 0
        examples: list[dict[str, Any]] = []
        freshness_status = "retrieved_timestamp_known"

        if target.parser_name == "maine_rules_pdf":
            pdf_text = extract_pdf_text(retrieved.content)
            rules, audit = parse_rules_text(pdf_text, source_id=source_id, url=target.url)
            canonical_count = len(rules)
            examples = [
                {"document_id": rule.document_id, "title": rule.title, "rule_number": rule.rule_number}
                for rule in rules[:3]
            ]
            freshness_status = "rules_pdf_retrieved_and_text_extracted"
            return audit, canonical_count, examples, freshness_status

        if target.parser_name in {"maine_form_pdf", "maine_form_text"}:
            source_text = extract_pdf_text(retrieved.content) if "pdf" in target.expected_content_type.lower() else retrieved.text
            form, audit = parse_form_text(source_text, source_id=source_id, url=target.url)
            canonical_count = 1 if form.form_id else 0
            examples = [{"document_id": form.document_id, "title": form.title, "form_id": form.form_id}]
            freshness_status = form.retrieved_freshness_status
            return audit, canonical_count, examples, freshness_status

        if target.parser_name == "maine_law_court_opinion_pdf":
            opinion_text = extract_pdf_text(retrieved.content)
            opinion, audit = parse_law_court_opinion_text(opinion_text, source_id=source_id, url=target.url)
            canonical_count = 1 if opinion.title else 0
            examples = [{"opinion_id": opinion.opinion_id, "title": opinion.title, "citation": opinion.citation}]
            freshness_status = "opinion_pdf_retrieved_and_text_extracted"
            return audit, canonical_count, examples, freshness_status

        if "pdf" in target.expected_content_type.lower() or target.parser_name == "pdf_snapshot":
            audit = ParserAuditEvent(
                source_id=source_id,
                parser_name=target.parser_name,
                parser_version="snapshot_only_v1",
                status="snapshot_only",
                message="PDF saved as official source snapshot; text extraction handled by parsed-authority/OCR worker.",
                extracted_count=0,
                metadata={"freshness_strategy": target.freshness_strategy},
            )
            return audit, canonical_count, examples, freshness_status

        text = retrieved.text
        if target.parser_name in {"maine_revisor_title_index", "maine_revisor_section"}:
            document, audit = parse_revisor_html(text, source_id=source_id, url=target.url)
            canonical_count = len(getattr(document, "section_links", [])) or 1
            freshness_status = document.retrieved_freshness_status
            examples = getattr(document, "section_links", [])[:3]
            if not examples and getattr(document, "section_number", None):
                examples = [
                    {
                        "document_id": document.document_id,
                        "title": document.title,
                        "section_number": document.section_number,
                    }
                ]
            return audit, canonical_count, examples, freshness_status

        if target.parser_name == "maine_forms_index":
            forms, audit = parse_forms_index(text, source_id=source_id, url=target.url)
            canonical_count = len(forms)
            examples = [
                {"document_id": form.document_id, "title": form.title, "form_id": form.form_id}
                for form in forms[:3]
            ]
            freshness_status = "forms_index_retrieved"
            return audit, canonical_count, examples, freshness_status

        if target.parser_name == "maine_rules_index":
            rules, audit = parse_rules_index(text, source_id=source_id, url=target.url)
            canonical_count = len(rules)
            examples = [
                {"document_id": rule.document_id, "title": rule.title, "rule_number": rule.rule_number}
                for rule in rules[:3]
            ]
            freshness_status = "rules_index_retrieved"
            return audit, canonical_count, examples, freshness_status

        if target.parser_name == "maine_law_court_opinion_index":
            opinions, audit = parse_law_court_opinion_index(text, source_id=source_id, url=target.url)
            canonical_count = len(opinions)
            examples = [
                {"opinion_id": opinion.opinion_id, "title": opinion.title, "href": opinion.href}
                for opinion in opinions[:3]
            ]
            freshness_status = "opinion_index_retrieved"
            return audit, canonical_count, examples, freshness_status

        audit = ParserAuditEvent(
            source_id=source_id,
            parser_name=target.parser_name,
            parser_version="unknown_parser_v1",
            status="unparsed",
            message="no parser registered for target parser_name",
            warnings=[target.parser_name],
        )
        return audit, canonical_count, examples, freshness_status

    def ingest_target(self, target: SourceTarget) -> IngestedAuthority:
        problems = target.validate()
        if problems:
            raise ValueError(f"invalid source target {target.target_id!r}: {', '.join(problems)}")
        source_id = self.source_id_for_target(target)
        retrieved = self.fetcher.fetch(target)
        snapshot = self.snapshotter.write(retrieved, source_id=source_id)
        audit, canonical_count, examples, freshness_status = self._parse(retrieved, source_id=source_id)
        parser_status = audit.status
        record = SourceRecord(
            source_id=source_id,
            source_class=target.source_class,
            jurisdiction=target.jurisdiction,
            retrieved_at=retrieved.retrieved_at,
            hash=retrieved.sha256,
            parser_status=parser_status,
            freshness_status=freshness_status,
            data_class=DataClass.OFFICIAL_PUBLIC_AUTHORITY,
            source_url_or_path=target.url,
            parser_version=audit.parser_version,
            metadata={
                "target_id": target.target_id,
                "content_type": retrieved.content_type,
                "status_code": retrieved.status_code,
                "final_url": retrieved.final_url,
                "expected_content_type": target.expected_content_type,
                "freshness_strategy": target.freshness_strategy,
            },
        )
        return IngestedAuthority(
            source_record=record,
            snapshot_path=str(snapshot.raw_path),
            parser_audit=audit,
            canonical_count=canonical_count,
            canonical_examples=examples,
        )

    def ingest_all(
        self,
        targets: list[SourceTarget],
        *,
        continue_on_error: bool = True,
    ) -> list[IngestedAuthority]:
        ingested: list[IngestedAuthority] = []
        self.failed = []
        for target in targets:
            try:
                ingested.append(self.ingest_target(target))
            except OfficialSourceFetchError as exc:
                failure = FailedAuthorityIngestion.from_exception(exc)
                self.failed.append(failure)
                if not continue_on_error:
                    raise
            except Exception as exc:
                failure = FailedAuthorityIngestion.from_unexpected(target, exc)
                self.failed.append(failure)
                if not continue_on_error:
                    raise
        return ingested

    def write_manifest(
        self, ingested: list[IngestedAuthority] | list[dict[str, Any]], *, filename: str = "source_manifest.json"
    ) -> Path:
        records: list[dict[str, Any]] = []
        for item in ingested:
            if isinstance(item, IngestedAuthority):
                records.append(item.to_dict())
            else:
                records.append(item)
        return self.snapshotter.write_manifest(records, filename=filename)

    def write_failure_report(self, *, filename: str = "failed_sources.json") -> Path:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "failed_count": len(self.failed),
            "failures": [failure.to_dict() for failure in self.failed],
        }
        path = self.snapshotter.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def write_ingest_run_report(
        self,
        *,
        ingested: list[IngestedAuthority],
        manifest_path: Path,
        filename: str = "ingest_run_report.json",
    ) -> Path:
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "manifest_path": str(manifest_path),
            "ingested_count": len(ingested),
            "failed_count": len(self.failed),
            "source_class_counts": {},
            "failure_codes": {},
        }
        for item in ingested:
            source_class = item.source_record.source_class
            report["source_class_counts"][source_class] = report["source_class_counts"].get(source_class, 0) + 1
        for failure in self.failed:
            report["failure_codes"][failure.failure_code] = report["failure_codes"].get(failure.failure_code, 0) + 1
        path = self.snapshotter.base_dir / filename
        path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        return path
