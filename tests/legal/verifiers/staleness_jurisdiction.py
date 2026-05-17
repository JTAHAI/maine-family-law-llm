from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

CURRENT_LAW_PATTERNS = (
    r"\bcurrent\s+maine\s+law\b",
    r"\bcurrent\s+law\b",
    r"\bas\s+of\s+today\b",
    r"\bcurrently\s+requires\b",
    r"\bup[- ]to[- ]date\b",
)
STALE_FRESHNESS = {"stale", "unknown", "stale_unknown", "superseded"}
NEGATIVE_TREATMENT_UNSAFE = {
    "negative_treatment_unknown",
    "overruled_or_negative_treatment_unknown",
    "overruled",
    "limited",
    "distinguished_unknown",
}
FORM_CLASSES = {"court_forms_index", "form", "forms", "court_form_reference"}


@dataclass(frozen=True)
class SourceScopeCheck:
    source_id: str
    status: str
    blocker: bool
    message: str
    source_class: str = "unknown"
    jurisdiction: str = "unknown"
    freshness_status: str = "unknown"
    authority_status: str = "stale_unknown"
    negative_treatment_status: str | None = None
    form_version_status: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class ScopeVerificationReport:
    current_law_language_detected: bool
    checks: list[SourceScopeCheck] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_law_language_detected": self.current_law_language_detected,
            "checks": [check.to_dict() for check in self.checks],
            "blockers": sorted(set(self.blockers)),
            "warnings": sorted(set(self.warnings)),
            "verified": self.verified,
        }


class FreshnessJurisdictionTreatmentChecker:
    """Block unsafe current-law, wrong-jurisdiction, stale, and negative-treatment use."""

    def check(
        self,
        *,
        text: str,
        source_metadata: dict[str, dict[str, Any]] | Iterable[dict[str, Any]],
        expected_jurisdiction: str = "maine",
    ) -> dict[str, Any]:
        return self.check_scope(
            text=text,
            source_metadata=source_metadata,
            expected_jurisdiction=expected_jurisdiction,
        ).to_dict()

    def check_scope(
        self,
        *,
        text: str,
        source_metadata: dict[str, dict[str, Any]] | Iterable[dict[str, Any]],
        expected_jurisdiction: str = "maine",
    ) -> ScopeVerificationReport:
        sources = _coerce_sources(source_metadata)
        current_law_language = _has_current_law_language(text)
        checks: list[SourceScopeCheck] = []
        blockers: list[str] = []
        warnings: list[str] = []

        for source in sources:
            source_id = str(source.get("source_id") or source.get("record_id") or "unknown_source")
            source_class = str(source.get("source_class") or source.get("authority_kind") or "unknown")
            jurisdiction = str(source.get("jurisdiction") or "unknown").lower()
            authority_status = str(source.get("authority_status") or source.get("status") or "stale_unknown")
            freshness_status = str(source.get("freshness_status") or "unknown")
            negative_status = source.get("negative_treatment_status")
            form_version_status = source.get("form_version_status") or source.get("version_status")

            if jurisdiction not in {expected_jurisdiction.lower(), "federal", "unknown"}:
                status = "jurisdiction_mismatch"
                blocker = True
                message = "source jurisdiction does not match the requested Maine scope"
                blockers.append(f"jurisdiction_mismatch:{source_id}")
            elif freshness_status in STALE_FRESHNESS:
                status = "stale_or_unknown_freshness"
                blocker = current_law_language or freshness_status in {"stale", "superseded"}
                message = "source freshness is stale or unknown"
                if blocker:
                    blockers.append(f"stale_or_unknown_freshness:{source_id}")
                else:
                    warnings.append(f"freshness_warning:{source_id}")
            elif authority_status in {"contradicted", "not_found"}:
                status = authority_status
                blocker = True
                message = "source authority status blocks reliance"
                blockers.append(f"authority_status_blocked:{source_id}")
            elif negative_status in NEGATIVE_TREATMENT_UNSAFE:
                status = "negative_treatment_unknown"
                blocker = True
                message = "case treatment is unknown or unsafe"
                blockers.append(f"negative_treatment_unknown:{source_id}")
            elif _is_form(source_class, source) and form_version_status not in {"current", "known_current"}:
                status = "form_freshness_not_verified"
                blocker = True
                message = "form version or freshness is not verified current"
                blockers.append(f"form_freshness_not_verified:{source_id}")
            else:
                status = "verified_scope"
                blocker = False
                message = "source scope, freshness, and treatment metadata passed"

            checks.append(
                SourceScopeCheck(
                    source_id=source_id,
                    status=status,
                    blocker=blocker,
                    message=message,
                    source_class=source_class,
                    jurisdiction=jurisdiction,
                    freshness_status=freshness_status,
                    authority_status=authority_status,
                    negative_treatment_status=negative_status,
                    form_version_status=form_version_status,
                )
            )

        if current_law_language and not sources:
            blockers.append("current_law_claim_without_sources")

        return ScopeVerificationReport(
            current_law_language_detected=current_law_language,
            checks=checks,
            blockers=blockers,
            warnings=warnings,
        )


def _has_current_law_language(text: str) -> bool:
    return any(re.search(pattern, text or "", flags=re.I) for pattern in CURRENT_LAW_PATTERNS)


def _coerce_sources(source_metadata: dict[str, dict[str, Any]] | Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(source_metadata, dict):
        rows: list[dict[str, Any]] = []
        for source_id, source in source_metadata.items():
            row = dict(source)
            row.setdefault("source_id", source_id)
            rows.append(row)
        return rows
    return [dict(source) for source in source_metadata]


def _is_form(source_class: str, source: dict[str, Any]) -> bool:
    source_class_lower = source_class.lower()
    return (
        source_class_lower in FORM_CLASSES
        or "form" in source_class_lower
        or bool(source.get("form_id"))
        or str(source.get("citation") or "").upper().startswith(("FM-", "PA-"))
    )
