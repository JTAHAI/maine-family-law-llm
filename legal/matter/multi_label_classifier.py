from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .document_inventory import InventoryEntry

_LABEL_RULES: dict[str, tuple[str, ...]] = {
    "court_order": ("order", "judgment", "decree", "ordered", "temporary order"),
    "pleading": ("complaint", "petition", "summons", "answer", "counterclaim"),
    "motion": ("motion", "moves this court", "requested relief"),
    "service": ("service", "served", "proof of service", "return of service"),
    "hearing": ("hearing", "conference", "mediation", "trial", "transcript"),
    "parental_rights": ("parental rights", "residence", "contact schedule", "custody"),
    "child_support": ("child support", "fm-050", "fm-084", "support worksheet"),
    "financial": ("paystub", "pay stub", "tax return", "bank statement", "income", "w-2"),
    "protection": ("protection from abuse", "pfa", "protection order", "harassment"),
    "school": ("school", "teacher", "iep", "attendance", "report card"),
    "medical": ("medical", "doctor", "hospital", "therapy", "medication", "diagnosis"),
    "communication": ("email", "text message", "conversation", "message thread", "voicemail"),
    "law_enforcement": ("police", "sheriff", "incident report", "dispatch", "criminal"),
    "gal": ("guardian ad litem", "gal report", "gal recommendation"),
    "evidence": ("exhibit", "attachment", "photo", "screenshot", "recording"),
    "appellate": ("appeal", "notice of appeal", "law court", "appellate"),
    "settlement": ("settlement", "mediation agreement", "stipulation", "proposal"),
}


@dataclass(frozen=True)
class LabelMatch:
    label: str
    confidence: float
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DocumentLabelResult:
    relative_path: str
    labels: tuple[LabelMatch, ...]
    status: str
    review_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "labels": [item.to_dict() for item in self.labels],
            "status": self.status,
            "review_reasons": list(self.review_reasons),
        }


class MultiLabelMatterClassifier:
    """Conservative many-to-many classifier that never moves or renames files."""

    def classify(
        self,
        *,
        relative_path: str,
        text_excerpt: str = "",
        readable: bool = True,
    ) -> DocumentLabelResult:
        filename = Path(relative_path).name.lower()
        content = text_excerpt[:200_000].lower()
        combined = f"{filename}\n{content}"
        matches: list[LabelMatch] = []
        for label, terms in _LABEL_RULES.items():
            matched = tuple(sorted({term for term in terms if term in combined}))
            if not matched:
                continue
            filename_hits = sum(1 for term in matched if term in filename)
            confidence = min(0.98, 0.55 + 0.12 * len(matched) + 0.08 * filename_hits)
            matches.append(LabelMatch(label, round(confidence, 3), matched))

        matches.sort(key=lambda item: (-item.confidence, item.label))
        reasons: list[str] = []
        if not readable:
            reasons.append("content_unreadable_or_not_extracted")
        if not matches:
            reasons.append("no_conservative_label_match")
        if matches and max(item.confidence for item in matches) < 0.7:
            reasons.append("low_confidence")
        if len(matches) > 5:
            reasons.append("broad_bundle_or_combined_document")

        status = "classified"
        if not matches:
            status = "unclassified"
        elif reasons:
            status = "review_required"
        return DocumentLabelResult(
            relative_path=relative_path,
            labels=tuple(matches),
            status=status,
            review_reasons=tuple(sorted(set(reasons))),
        )

    def classify_inventory(
        self,
        entries: Iterable[InventoryEntry],
        excerpts: dict[str, str] | None = None,
    ) -> tuple[DocumentLabelResult, ...]:
        excerpts = excerpts or {}
        results = [
            self.classify(
                relative_path=entry.relative_path,
                text_excerpt=excerpts.get(entry.relative_path, ""),
                readable=entry.relative_path in excerpts or entry.extension in {".txt", ".md"},
            )
            for entry in entries
        ]
        return tuple(sorted(results, key=lambda item: item.relative_path.casefold()))
