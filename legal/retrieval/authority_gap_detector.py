"""Fail-closed coverage review for an admitted authority corpus."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any


class AuthorityGapDetector:
    """Report corpus metadata gaps without deciding what law applies.

    This class accepts only already-admitted source metadata. It never fetches,
    supplements, or silently substitutes sources, and it treats unknown or
    stale freshness as review blockers rather than evidence of completeness.
    """

    MATERIAL_CLASSES = ("statute", "rule", "opinion", "form")
    # Exact metadata aliases, not a substring heuristic. These identify only
    # observed metadata classes; an index is not proof of material coverage.
    SOURCE_CLASS_ALIASES = {
        "statute": {"statute", "statute_section", "statute_title_index", "statute_title_pdf"},
        "rule": {"rule", "court_rule", "court_rules_index", "court_rules_pdf", "court_rules_text"},
        "opinion": {
            "opinion",
            "law_court_opinion",
            "law_court_opinion_index",
            "law_court_opinion_pdf",
        },
        "form": {"form", "court_form", "court_forms_index", "court_form_pdf", "court_form_text"},
    }

    def review(self, records: Iterable[dict[str, Any]], *, issue: str = "") -> dict[str, Any]:
        classes: Counter[str] = Counter()
        freshness: Counter[str] = Counter()
        record_count = 0
        for row in records:
            record_count += 1
            classes[self._source_class(row)] += 1
            freshness[str(row.get("freshness_status") or "").strip().casefold() or "unknown"] += 1
        missing_classes = [
            name
            for name in self.MATERIAL_CLASSES
            if not self.SOURCE_CLASS_ALIASES[name].intersection(classes)
        ]
        known_classes = set().union(*self.SOURCE_CLASS_ALIASES.values())
        blockers: list[str] = []
        if not record_count:
            blockers.append("no_admitted_sources_for_review")
        if missing_classes:
            blockers.append("source_class_coverage_incomplete")
        if set(classes) - known_classes:
            blockers.append("source_class_review_required")
        if any(state != "fresh" for state in freshness):
            blockers.append("freshness_review_required")
        return {
            "schema_version": "authority_gap_review_v1",
            "status": "needs_review" if blockers else "metadata_coverage_observed",
            "issue": str(issue or "").strip()[:500] or None,
            "review_scope": "active_corpus_metadata",
            "issue_filter_applied": False,
            "record_count": record_count,
            "source_class_counts": dict(sorted(classes.items())),
            "freshness_counts": dict(sorted(freshness.items())),
            "missing_material_source_classes": missing_classes,
            "blockers": blockers,
            "review_required": True,
            "completeness_determined": False,
            "current_law_determined": False,
            "boundary": (
                "This is a metadata coverage review of the active admitted corpus. "
                "It does not determine whether a source is legally required, "
                "current law is complete, or a legal conclusion."
            ),
        }

    @staticmethod
    def _source_class(record: dict[str, Any]) -> str:
        return (
            str(record.get("source_class") or record.get("authority_kind") or "").strip().casefold()
            or "unknown"
        )
