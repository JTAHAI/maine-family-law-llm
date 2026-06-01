from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from legal.connectors.base import SourceTarget
from legal.corpus.source_normalizer import slugify
from legal.data_boundaries import StoreName


@dataclass(frozen=True)
class DerivedTargetFinding:
    code: str
    message: str
    record_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "record_id": self.record_id}


@dataclass
class DerivedAuthorityTargetsReport:
    status: str
    data_root: str
    output_path: str
    target_count: int = 0
    counts_by_source_class: dict[str, int] = field(default_factory=dict)
    findings: list[DerivedTargetFinding] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "data_root": self.data_root,
            "output_path": self.output_path,
            "target_count": self.target_count,
            "counts_by_source_class": self.counts_by_source_class,
            "findings": [finding.as_dict() for finding in self.findings],
        }


class AuthorityFollowupTargetBuilder:
    """Derive second-wave official targets from parsed authority index records.

    Pass 19 can fetch official index pages and title PDFs.  This builder turns
    those official index records into a deterministic target catalog for the
    next live ingest wave: statute sections, rule PDFs, court form PDFs, and Law
    Court opinion PDFs.  The output is a source-target catalog, not evidence that
    the targets have been fetched or parsed.
    """

    PARSED_COLLECTIONS = (
        "statutes/statute_title_indexes.jsonl",
        "rules/rules_index.jsonl",
        "forms/forms_index.jsonl",
        "opinions/opinion_index.jsonl",
    )

    def __init__(self, *, data_root: str | Path) -> None:
        self.data_root = Path(data_root).resolve()
        self.parsed_store = self.data_root / "parsed_authority_store"
        self.output_path = self.data_root / StoreName.OFFICIAL_AUTHORITY.value / "derived_authority_targets.json"
        self.findings: list[DerivedTargetFinding] = []

    def build(self, *, write: bool = True, max_targets: int | None = None) -> DerivedAuthorityTargetsReport:
        targets: dict[str, SourceTarget] = {}
        for row in self._iter_rows():
            for target in self._targets_for_row(row):
                if target.target_id not in targets:
                    targets[target.target_id] = target
                if max_targets is not None and len(targets) >= max_targets:
                    break
            if max_targets is not None and len(targets) >= max_targets:
                break

        rows = [self._target_to_dict(target) for target in sorted(targets.values(), key=lambda item: item.target_id)]
        counts: dict[str, int] = {}
        for target in rows:
            source_class = str(target["source_class"])
            counts[source_class] = counts.get(source_class, 0) + 1

        if write:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text(
                json.dumps(
                    {
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "source": "parsed_authority_store_indexes",
                        "target_count": len(rows),
                        "targets": rows,
                    },
                    indent=2,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        status = "pass" if rows else "blocked"
        if not rows:
            self.findings.append(
                DerivedTargetFinding(
                    "no_derived_targets",
                    "No follow-up targets could be derived. Build parsed authority indexes first.",
                )
            )
        return DerivedAuthorityTargetsReport(
            status=status,
            data_root=str(self.data_root),
            output_path=str(self.output_path),
            target_count=len(rows),
            counts_by_source_class=counts,
            findings=self.findings,
        )

    def _iter_rows(self) -> Iterable[dict[str, Any]]:
        for relative in self.PARSED_COLLECTIONS:
            path = self.parsed_store / relative
            if not path.exists():
                self.findings.append(
                    DerivedTargetFinding("parsed_collection_missing", f"Missing parsed collection: {relative}")
                )
                continue
            for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    loaded = json.loads(line)
                except json.JSONDecodeError as exc:
                    self.findings.append(
                        DerivedTargetFinding("parsed_jsonl_invalid", f"{relative}:{index}: {exc}")
                    )
                    continue
                if isinstance(loaded, dict):
                    yield loaded

    def _targets_for_row(self, row: dict[str, Any]) -> list[SourceTarget]:
        target = self._target_for_row(row)
        return [target] if target is not None else []

    def _target_for_row(self, row: dict[str, Any]) -> SourceTarget | None:
        kind = str(row.get("authority_kind") or "")
        record_id = str(row.get("record_id") or row.get("source_id") or "")
        if kind == "statute_title_index":
            return self._curated_core_statute_section_target(row)

        href = str(row.get("href") or "").strip()
        source_url = str(row.get("source_url_or_path") or "").strip()
        url = _absolute_url(href, source_url)
        if not url:
            self.findings.append(DerivedTargetFinding("missing_href", "Parsed row has no follow-up URL.", record_id))
            return None

        if kind == "statute_section_reference":
            title = _clean_component(str(row.get("title_number") or row.get("section_number") or "section"))
            section = _clean_component(str(row.get("section_number") or record_id or "unknown"))
            return SourceTarget(
                target_id=f"me-revisor-section-{title}-{section}",
                source_class="statute_section",
                jurisdiction=str(row.get("jurisdiction") or "maine"),
                url=url,
                parser_name="maine_revisor_section",
                expected_content_type="text/html",
                priority=1,
                freshness_strategy="revisor_data_extracted_timestamp",
                notes="Derived from official Maine Revisor title index; fetches full statute section text.",
            )

        if kind == "court_rule_reference":
            rule = _clean_component(str(row.get("rule_number") or row.get("citation") or record_id or "rule"))
            is_pdf = _looks_like_pdf(url)
            return SourceTarget(
                target_id=f"me-court-rule-{rule}",
                source_class="court_rule_pdf" if is_pdf else "court_rule_text",
                jurisdiction=str(row.get("jurisdiction") or "maine"),
                url=url,
                parser_name="maine_rules_pdf" if is_pdf else "maine_rules_index",
                expected_content_type="application/pdf" if is_pdf else "text/html",
                priority=1,
                freshness_strategy="page_updated_or_retrieved_timestamp",
                notes="Derived from official Maine Judicial Branch rules index; fetches direct rule/standing-order text.",
            )

        if kind == "court_form_reference":
            form_id = _clean_component(str(row.get("form_id") or row.get("citation") or record_id or "form"))
            is_pdf = _looks_like_pdf(url)
            return SourceTarget(
                target_id=f"me-court-form-{form_id}",
                source_class="court_form_pdf" if is_pdf else "court_form_text",
                jurisdiction=str(row.get("jurisdiction") or "maine"),
                url=url,
                parser_name="maine_form_pdf" if is_pdf else "maine_form_text",
                expected_content_type="application/pdf" if is_pdf else "text/html",
                priority=1,
                freshness_strategy="form_version_or_retrieved_timestamp",
                notes="Derived from official Maine Judicial Branch forms index; fetches direct form text/PDF.",
            )

        if kind == "law_court_opinion_reference":
            opinion = _clean_component(str(row.get("citation") or row.get("docket_number") or record_id or "opinion"))
            return SourceTarget(
                target_id=f"me-lawcourt-opinion-{opinion}",
                source_class="law_court_opinion_pdf" if _looks_like_pdf(url) else "law_court_opinion_text",
                jurisdiction=str(row.get("jurisdiction") or "maine"),
                url=url,
                parser_name="maine_law_court_opinion_pdf" if _looks_like_pdf(url) else "maine_law_court_opinion_index",
                expected_content_type="application/pdf" if _looks_like_pdf(url) else "text/html",
                priority=1,
                freshness_strategy="retrieved_timestamp_and_opinion_metadata",
                notes="Derived from official Maine Law Court opinion index; fetches direct opinion PDF/text.",
            )
        return None

    def _curated_core_statute_section_target(self, row: dict[str, Any]) -> SourceTarget | None:
        """Add a minimal direct statute-section target when title indexes expose only chapter rows.

        Maine Revisor title index pages sometimes expose chapter/table structure
        without direct section links.  The direct-authority gate still needs at
        least one fetched statute section from the official Revisor site before
        downstream retrieval/source-card evidence can claim direct statutory
        coverage.  Keep this fallback narrow and deterministic: it is a
        bootstrap target, not a substitute for broader statutory coverage.
        """
        title_number = str(row.get("title_number") or "").upper()
        if title_number != "19-A":
            return None
        return SourceTarget(
            target_id="me-revisor-section-19-a-1653",
            source_class="statute_section",
            jurisdiction=str(row.get("jurisdiction") or "maine"),
            url="https://legislature.maine.gov/statutes/19-A/title19-Asec1653.html",
            parser_name="maine_revisor_section",
            expected_content_type="text/html",
            priority=1,
            freshness_strategy="revisor_data_extracted_timestamp",
            notes="Curated bootstrap direct statute-section target derived from the official Title 19-A index.",
        )

    @staticmethod
    def _target_to_dict(target: SourceTarget) -> dict[str, Any]:
        return {
            "target_id": target.target_id,
            "source_class": target.source_class,
            "jurisdiction": target.jurisdiction,
            "url": target.url,
            "parser_name": target.parser_name,
            "expected_content_type": target.expected_content_type,
            "priority": target.priority,
            "freshness_strategy": target.freshness_strategy,
            "notes": target.notes,
        }


def _absolute_url(href: str, base_url: str) -> str:
    href = _strip_control_chars(href.strip())
    base_url = _strip_control_chars(base_url.strip())
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return _quote_url_path(href)
    if base_url.startswith(("http://", "https://")):
        return _quote_url_path(urljoin(base_url, href))
    return _quote_url_path(href)


def _strip_control_chars(value: str) -> str:
    return "".join(ch for ch in value if ord(ch) >= 32 and ord(ch) != 127)


def _quote_url_path(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return url
    parts = urlsplit(url)
    path = quote(parts.path, safe="/%:@")
    query = quote(parts.query, safe="=&%/:+?@,")
    return urlunsplit((parts.scheme, parts.netloc, path, query, ""))


def _looks_like_pdf(url: str) -> bool:
    return bool(re.search(r"\.pdf(?:$|[?#])", url, flags=re.I))


def _clean_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-").lower()
    return cleaned or slugify(value or "unknown")
