"""Source manifest contracts for the Maine Family Law LLM workbench."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


ALLOWED_SOURCE_TYPES = {
    "admin_order",
    "appellate_rule",
    "attorney_regulation",
    "bar_rule",
    "statute",
    "court_rule",
    "court_form",
    "ecourts_rule",
    "evidence_rule",
    "federal_case_law",
    "federal_court_form",
    "federal_court_guide",
    "federal_court_rule",
    "federal_ecf_guidance",
    "federal_relief_guidance",
    "federal_rule",
    "federal_service_guidance",
    "federal_statute",
    "first_circuit_opinion",
    "judicial_conduct_rule",
    "judicial_branch_guide",
    "judicial_discipline",
    "law_court_opinion",
    "law_court_opinion_index",
    "legal_aid_plain_language",
    "licensed_secondary",
    "professional_conduct_rule",
    "probate_rule",
    "rulemaking_notice",
    "standing_order",
    "us_supreme_court_opinion",
    "court_process",
    "constitutional_authority",
    "child_support_guidance",
    "safety_resource",
    "secondary",
}

SECONDARY_SOURCE_TYPES = {"secondary", "legal_aid_plain_language", "licensed_secondary"}
LEGAL_SOURCE_TYPES_REQUIRING_CITATIONS = ALLOWED_SOURCE_TYPES - {"safety_resource", *SECONDARY_SOURCE_TYPES}

ALLOWED_JURISDICTIONS = {
    "Maine",
    "United States",
    "Federal",
    "Federal - District of Maine",
    "Federal - First Circuit",
    "Federal - U.S. Supreme Court",
}

REQUIRED_MANIFEST_FIELDS = (
    "id",
    "title",
    "source_type",
    "jurisdiction",
    "official",
    "url",
    "effective_date",
    "retrieved_at",
    "version_label",
    "citation_hint",
    "license_or_terms_note",
    "source_priority",
    "notes",
)


class ManifestValidationError(ValueError):
    """Raised when source metadata is unsafe or incomplete."""


@dataclass(frozen=True)
class SourceManifestEntry:
    id: str
    title: str
    source_type: str
    jurisdiction: str
    official: bool
    url: str
    effective_date: str
    retrieved_at: str
    version_label: str
    citation_hint: str
    license_or_terms_note: str
    source_priority: int
    notes: str
    authority_class: str = ""
    corpus_lane: str = ""
    citation_aliases: tuple[str, ...] = ()
    parser: str = ""
    freshness_status: str = "needs_verification"
    required_for_ga: bool = False
    completion_status: str = "manifested"

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceManifestEntry":
        missing = [field for field in REQUIRED_MANIFEST_FIELDS if field not in payload]
        if missing:
            raise ManifestValidationError(f"missing required manifest fields: {', '.join(missing)}")
        official = payload["official"]
        if not isinstance(official, bool):
            raise ManifestValidationError("official must be a boolean")
        try:
            priority = int(payload["source_priority"])
        except Exception as exc:
            raise ManifestValidationError("source_priority must be an integer") from exc
        entry = cls(
            id=_required_text(payload, "id"),
            title=_required_text(payload, "title"),
            source_type=_required_text(payload, "source_type"),
            jurisdiction=_required_text(payload, "jurisdiction"),
            official=official,
            url=_required_text(payload, "url"),
            effective_date=_required_text(payload, "effective_date"),
            retrieved_at=_required_text(payload, "retrieved_at"),
            version_label=_required_text(payload, "version_label"),
            citation_hint=str(payload.get("citation_hint", "")).strip(),
            license_or_terms_note=_required_text(payload, "license_or_terms_note"),
            source_priority=priority,
            notes=str(payload.get("notes", "")).strip(),
            authority_class=str(payload.get("authority_class", "")).strip(),
            corpus_lane=str(payload.get("corpus_lane", "")).strip(),
            citation_aliases=_string_tuple(payload.get("citation_aliases", ())),
            parser=str(payload.get("parser", "")).strip(),
            freshness_status=str(payload.get("freshness_status", "needs_verification")).strip(),
            required_for_ga=bool(payload.get("required_for_ga", False)),
            completion_status=str(payload.get("completion_status", "manifested")).strip(),
        )
        validate_entry(entry)
        return entry

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ManifestValidationError(f"{key} is required")
    return value


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    raise ManifestValidationError("citation_aliases must be a string or list of strings")


def validate_entry(entry: SourceManifestEntry) -> SourceManifestEntry:
    if entry.source_type not in ALLOWED_SOURCE_TYPES:
        raise ManifestValidationError(f"bad source_type: {entry.source_type}")
    if entry.jurisdiction not in ALLOWED_JURISDICTIONS:
        raise ManifestValidationError(f"unsupported jurisdiction: {entry.jurisdiction}")
    if entry.source_type in SECONDARY_SOURCE_TYPES and entry.official:
        raise ManifestValidationError("secondary sources cannot be marked official")
    if entry.source_type in LEGAL_SOURCE_TYPES_REQUIRING_CITATIONS and not entry.citation_hint:
        raise ManifestValidationError("citation_hint required for legal/procedure/form sources")
    if not entry.url.startswith(("https://", "http://")):
        raise ManifestValidationError("url must be absolute http(s)")
    return entry


def validate_manifest(entries: list[SourceManifestEntry]) -> list[SourceManifestEntry]:
    seen: set[str] = set()
    for entry in entries:
        validate_entry(entry)
        if entry.id in seen:
            raise ManifestValidationError(f"duplicate source id: {entry.id}")
        seen.add(entry.id)

    official_priorities = [entry.source_priority for entry in entries if entry.official]
    if official_priorities:
        highest_official_priority = min(official_priorities)
        for entry in entries:
            if entry.source_type in SECONDARY_SOURCE_TYPES and entry.source_priority <= highest_official_priority:
                raise ManifestValidationError("secondary sources cannot outrank official sources")
    return entries


def load_manifest(path: str | Path) -> list[SourceManifestEntry]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ManifestValidationError("manifest root must be a list")
    entries = [SourceManifestEntry.from_dict(item) for item in payload]
    return validate_manifest(entries)


def write_manifest(path: str | Path, entries: list[SourceManifestEntry]) -> Path:
    validate_manifest(entries)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps([entry.to_dict() for entry in entries], indent=2) + "\n",
        encoding="utf-8",
    )
    return out
