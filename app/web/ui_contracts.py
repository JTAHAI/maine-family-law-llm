from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.web.ui_inventory import REQUIRED_UI_VIEWS

REQUIRED_UI_MARKERS = {
    "source_card": "data-source-card",
    "claim_drilldown": "data-claim-drilldown",
    "citation_drilldown": "data-citation-drilldown",
    "source_text_drilldown": "data-source-text-drilldown",
    "verifier_result_drilldown": "data-verifier-result-drilldown",
    "review_status": "data-review-status",
    "blocked_export_explanation": "data-blocked-export-explanation",
}

VIEW_SPECIFIC_MARKERS = {
    "ask.tsx": ["source_card", "claim_drilldown", "citation_drilldown", "source_text_drilldown", "verifier_result_drilldown"],
    "draft-workspace.tsx": ["review_status", "source_card", "blocked_export_explanation"],
    "filing-ready.tsx": ["review_status", "blocked_export_explanation", "verifier_result_drilldown"],
    "citation-report.tsx": ["citation_drilldown", "source_card", "verifier_result_drilldown"],
    "quote-report.tsx": ["source_text_drilldown", "verifier_result_drilldown"],
    "source-library.tsx": ["source_card", "source_text_drilldown"],
    "authority-matrix.tsx": ["source_card", "citation_drilldown"],
    "human-review-queue.tsx": ["review_status"],
    "admin-eval-dashboard.tsx": ["review_status", "blocked_export_explanation"],
}


@dataclass
class UICompletionReport:
    status: str
    required_view_count: int
    missing_views: list[str]
    missing_markers: dict[str, list[str]]
    drilldown_chain_required: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "required_view_count": self.required_view_count,
            "missing_views": self.missing_views,
            "missing_markers": self.missing_markers,
            "drilldown_chain_required": self.drilldown_chain_required,
        }


class UICompletionAuditor:
    def __init__(self, pages_dir: str | Path = "app/web/pages") -> None:
        self.pages_dir = Path(pages_dir)

    def audit(self) -> UICompletionReport:
        missing_views: list[str] = []
        missing_markers: dict[str, list[str]] = {}
        for view in REQUIRED_UI_VIEWS:
            path = self.pages_dir / view.file
            if not path.exists():
                missing_views.append(view.file)
                continue
            text = path.read_text(encoding="utf-8")
            required = VIEW_SPECIFIC_MARKERS.get(view.file, ["review_status"])
            absent = [marker_key for marker_key in required if REQUIRED_UI_MARKERS[marker_key] not in text]
            if absent:
                missing_markers[view.file] = absent
        status = "pass" if not missing_views and not missing_markers else "fail"
        return UICompletionReport(
            status=status,
            required_view_count=len(REQUIRED_UI_VIEWS),
            missing_views=missing_views,
            missing_markers=missing_markers,
            drilldown_chain_required=[
                "answer",
                "claim",
                "citation",
                "source_text",
                "verifier_result",
            ],
        )
